from typing import Dict, List
from core.schemas import ValuationRequest, ValuationResult, PeerCompany
from methodologies.base import BaseMethodology

class CCAMethodology(BaseMethodology):
    """
    Comparable Company Analysis (CCA) valuation methodology.
    """

    @property
    def name(self) -> str:
        return "CCA"

    def calculate(
        self,
        request: ValuationRequest,
        financial_data: Dict[str, float],
        peers: List[Dict[str, float]]
    ) -> ValuationResult:
        
        fallback_applied = False
        assumptions = []
        
        # 1. Extract target inputs
        current_price = financial_data.get("current_price", 0.0)
        shares_outstanding = financial_data.get("shares_outstanding", 0.0)
        market_cap = financial_data.get("market_cap", 0.0) or (current_price * shares_outstanding)
        total_debt = financial_data.get("total_debt", 0.0)
        total_cash = financial_data.get("total_cash", 0.0)
        eps = financial_data.get("eps", 0.0)
        revenue = financial_data.get("total_revenue", 0.0)
        # Operating cash flow acts as a high-quality proxy for EBITDA
        ebitda = financial_data.get("ebitda", 0.0) or financial_data.get("operating_cash_flow", 0.0)

        # 2. Gather peer multiples split by country (BR vs US)
        br_pes, br_ev_ebitdas, br_ev_revenues = [], [], []
        us_pes, us_ev_ebitdas, us_ev_revenues = [], [], []
        peer_companies = []

        for idx, p in enumerate(peers):
            ticker = p.get("ticker", f"PEER{idx}")
            mcap = p.get("market_cap", 0.0)
            multiples = p.get("multiples", {})
            
            peer_companies.append(PeerCompany(
                ticker=ticker,
                market_cap=mcap,
                multiples=multiples
            ))

            is_br = ticker.upper().endswith(".BR") or ticker.upper().endswith(".SA")
            
            pe = multiples.get("P/E")
            ev_eb = multiples.get("EV/EBITDA")
            ev_rev = multiples.get("EV/Revenue")
            
            if pe is not None:
                if is_br: br_pes.append(float(pe))
                else: us_pes.append(float(pe))
            if ev_eb is not None:
                if is_br: br_ev_ebitdas.append(float(ev_eb))
                else: us_ev_ebitdas.append(float(ev_eb))
            if ev_rev is not None:
                if is_br: br_ev_revenues.append(float(ev_rev))
                else: us_ev_revenues.append(float(ev_rev))

        # Check total peers count
        if len(peer_companies) < 2 or (
            not br_pes and not br_ev_ebitdas and not br_ev_revenues and
            not us_pes and not us_ev_ebitdas and not us_ev_revenues
        ):
            return self.create_diagnostic_result(
                reason_code="INSUFFICIENT_PEERS",
                explanation=f"CCA requires at least 2 comparable peer companies. Only {len(peer_companies)} were found.",
                triggering_metrics={"peer_count": float(len(peer_companies))},
                analytical_implication="Comparable Company Analysis relies on a statistically meaningful peer group. Without sufficient peers, we cannot establish representative sector multiples.",
                baseline_metrics={
                    "shares_outstanding": shares_outstanding,
                    "current_price": current_price
                },
                peer_comparison=peer_companies,
                assumptions=assumptions
            )

        # Determine target country
        is_target_brl = request.ticker.upper().endswith(".BR") or request.ticker.upper().endswith(".SA") or financial_data.get("currency") == "BRL"

        # Calculate averages for BR
        avg_pe_br = sum(br_pes) / len(br_pes) if br_pes else (sum(us_pes) / len(us_pes) if us_pes else 0.0)
        avg_ev_ebitda_br = sum(br_ev_ebitdas) / len(br_ev_ebitdas) if br_ev_ebitdas else (sum(us_ev_ebitdas) / len(us_ev_ebitdas) if us_ev_ebitdas else 0.0)
        avg_ev_rev_br = sum(br_ev_revenues) / len(br_ev_revenues) if br_ev_revenues else (sum(us_ev_revenues) / len(us_ev_revenues) if us_ev_revenues else 0.0)

        # Calculate averages for US
        avg_pe_us = sum(us_pes) / len(us_pes) if us_pes else (sum(br_pes) / len(br_pes) if br_pes else 0.0)
        avg_ev_ebitda_us = sum(us_ev_ebitdas) / len(us_ev_ebitdas) if us_ev_ebitdas else (sum(br_ev_ebitdas) / len(br_ev_ebitdas) if br_ev_ebitdas else 0.0)
        avg_ev_rev_us = sum(us_ev_revenues) / len(us_ev_revenues) if us_ev_revenues else (sum(br_ev_revenues) / len(br_ev_revenues) if br_ev_revenues else 0.0)

        avg_pe = avg_pe_br if is_target_brl else avg_pe_us
        avg_ev_ebitda = avg_ev_ebitda_br if is_target_brl else avg_ev_ebitda_us
        avg_ev_rev = avg_ev_rev_br if is_target_brl else avg_ev_rev_us

        assumptions.append(f"Derived multiples from peer group of {len(peer_companies)} companies")
        if br_pes or br_ev_ebitdas or br_ev_revenues:
            if is_target_brl:
                assumptions.append(f"BR Peer Averages - P/E: {avg_pe_br:.1f}x, EV/EBITDA: {avg_ev_ebitda_br:.1f}x, EV/Rev: {avg_ev_rev_br:.1f}x")
            else:
                assumptions.append("Local peer group (Brazil) used exclusively for country-risk normalization.")
        if us_pes or us_ev_ebitdas or us_ev_revenues:
            assumptions.append(f"US Peer Averages - P/E: {avg_pe_us:.1f}x, EV/EBITDA: {avg_ev_ebitda_us:.1f}x, EV/Rev: {avg_ev_rev_us:.1f}x")

        # 3. Valuation Helper
        def compute_valuation(pe_mult, ev_ebitda_mult, ev_rev_mult):
            vals = []
            if eps > 0 and pe_mult > 0:
                vals.append(eps * pe_mult)
            if ebitda > 0 and ev_ebitda_mult > 0 and shares_outstanding > 0:
                target_ev = ebitda * ev_ebitda_mult
                target_equity = target_ev - total_debt + total_cash
                val = target_equity / shares_outstanding
                if val > 0:
                    vals.append(val)
            if revenue > 0 and ev_rev_mult > 0 and shares_outstanding > 0:
                target_ev_rev = revenue * ev_rev_mult
                target_equity_rev = target_ev_rev - total_debt + total_cash
                val = target_equity_rev / shares_outstanding
                if val > 0:
                    vals.append(val)
            
            if vals:
                return sum(vals) / len(vals), False
            else:
                return (current_price if current_price > 0 else 10.0), True

        # Calculate values
        intrinsic_value_br, fb_br = compute_valuation(avg_pe_br, avg_ev_ebitda_br, avg_ev_rev_br)
        intrinsic_value_us, fb_us = compute_valuation(avg_pe_us, avg_ev_ebitda_us, avg_ev_rev_us)

        # Apply peer weights if specified in adjustment parameters
        weight_local = None
        weight_us = None
        if request.adjustment_params and "peer_weight_local" in request.adjustment_params:
            weight_local = float(request.adjustment_params["peer_weight_local"])
        if request.adjustment_params and "peer_weight_us" in request.adjustment_params:
            weight_us = float(request.adjustment_params["peer_weight_us"])

        if weight_local is not None or weight_us is not None:
            # Fallback to defaults for missing weights
            w_local = weight_local if weight_local is not None else (1.0 if is_target_brl else 0.0)
            w_us = weight_us if weight_us is not None else (0.0 if is_target_brl else 1.0)
            
            total_w = w_local + w_us
            if total_w > 0:
                w_local /= total_w
                w_us /= total_w
                intrinsic_value = (w_local * intrinsic_value_br) + (w_us * intrinsic_value_us)
                fallback_applied = fb_br if w_local > w_us else fb_us
                assumptions.append(f"Blended peer valuation: {w_local*100:.0f}% Local/BR Peer Valuation ({intrinsic_value_br:.2f}) and {w_us*100:.0f}% US Benchmark Peer Valuation ({intrinsic_value_us:.2f})")
            else:
                intrinsic_value = intrinsic_value_br if is_target_brl else intrinsic_value_us
                fallback_applied = fb_br if is_target_brl else fb_us
        else:
            intrinsic_value = intrinsic_value_br if is_target_brl else intrinsic_value_us
            fallback_applied = fb_br if is_target_brl else fb_us

        if fallback_applied:
            assumptions.append("No valid multiples or positive financial bases found; fallback to current market price")

        # Compute Verdicts
        def get_verdict(val):
            if val <= 0 or current_price <= 0:
                return "INSUFFICIENT_DATA"
            mos = ((val - current_price) / val) * 100
            if mos > 20:
                return "UNDERVALUED"
            elif mos < -10:
                return "OVERVALUED"
            else:
                return "FAIRLY_VALUED"

        verdict_br = get_verdict(intrinsic_value_br)
        verdict_us = get_verdict(intrinsic_value_us)

        assumptions.append(f"BR CCA Valuation: {intrinsic_value_br:.2f} (Verdict: {verdict_br})")
        assumptions.append(f"US CCA Valuation: {intrinsic_value_us:.2f} (Verdict: {verdict_us})")

        baseline_metrics = {
            "current_price": current_price,
            "market_cap": market_cap,
            "total_revenue": revenue,
            "operating_cash_flow": financial_data.get("operating_cash_flow", 0.0),
            "ebitda": ebitda,
            "shares_outstanding": shares_outstanding,
            "eps": eps,
            "total_debt": total_debt,
            "total_cash": total_cash,
            "book_value": financial_data.get("book_value", 0.0),
            "peer_avg_pe": avg_pe,
            "peer_avg_ev_ebitda": avg_ev_ebitda,
            "peer_avg_ev_revenue": avg_ev_rev,
        }

        return ValuationResult(
            intrinsic_value=round(intrinsic_value, 2),
            methodology_name=self.name,
            assumptions=assumptions,
            baseline_metrics=baseline_metrics,
            peer_comparison=peer_companies,
            fallback_applied=fallback_applied,
            metadata={
                "peer_count": len(peer_companies),
                "avg_pe": avg_pe,
                "avg_ev_ebitda": avg_ev_ebitda,
                "avg_ev_revenue": avg_ev_rev,
                "intrinsic_value_br": float(intrinsic_value_br),
                "intrinsic_value_us": float(intrinsic_value_us),
                "verdict_br": verdict_br,
                "verdict_us": verdict_us
            }
        )
