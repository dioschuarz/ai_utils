from typing import Dict, List
from core.schemas import ValuationRequest, ValuationResult
from methodologies.base import BaseMethodology

class SOTPMethodology(BaseMethodology):
    """
    Sum of the Parts (SOTP) valuation methodology.
    Values segment parts or total EBITDA using comparable peer multiples.
    """

    @property
    def name(self) -> str:
        return "SOTP"

    def calculate(
        self,
        request: ValuationRequest,
        financial_data: Dict[str, float],
        peers: List[Dict[str, float]]
    ) -> ValuationResult:
        
        assumptions = []
        
        # 1. Extract inputs
        current_price = financial_data.get("current_price", 0.0)
        shares_outstanding = financial_data.get("shares_outstanding", 0.0)
        total_debt = financial_data.get("total_debt", 0.0)
        total_cash = financial_data.get("total_cash", 0.0)
        ebitda = financial_data.get("ebitda", 0.0) or financial_data.get("operating_cash_flow", 0.0)
        
        # Check shares_outstanding
        if shares_outstanding <= 0:
            return self.create_diagnostic_result(
                reason_code="MISSING_DATA",
                explanation="Shares outstanding must be positive to compute intrinsic value per share.",
                triggering_metrics={"shares_outstanding": shares_outstanding},
                analytical_implication="The company's shares outstanding data is not available, which prevents converting the aggregate equity value into a per-share value.",
                baseline_metrics={"shares_outstanding": shares_outstanding, "current_price": current_price}
            )
            
        # Check EBITDA
        if ebitda <= 0:
            return self.create_diagnostic_result(
                reason_code="MISSING_EBITDA",
                explanation=f"SOTP requires positive EBITDA/operating cash flow base. EBITDA: {ebitda:,.0f}.",
                triggering_metrics={"ebitda": ebitda},
                analytical_implication="Banks and other financial firms do not report traditional EBITDA, rendering SOTP EBITDA-multiple valuation inapplicable.",
                baseline_metrics={
                    "ebitda": ebitda,
                    "shares_outstanding": shares_outstanding,
                    "current_price": current_price
                }
            )
            
        # Extract peer EV/EBITDA multiples split by country (BR vs US)
        br_ev_ebitdas = []
        us_ev_ebitdas = []
        peer_companies = []
        for idx, p in enumerate(peers):
            ticker = p.get("ticker", f"PEER{idx}")
            mcap = p.get("market_cap", 0.0)
            multiples = p.get("multiples", {})
            peer_companies.append({
                "ticker": ticker,
                "market_cap": mcap,
                "multiples": multiples
            })
            val = multiples.get("EV/EBITDA")
            if val is not None:
                if ticker.upper().endswith(".BR") or ticker.upper().endswith(".SA"):
                    br_ev_ebitdas.append(float(val))
                else:
                    us_ev_ebitdas.append(float(val))
                    
        peer_ev_ebitdas = br_ev_ebitdas + us_ev_ebitdas

        # Determine if target is Brazilian
        is_target_brl = request.ticker.upper().endswith(".BR") or request.ticker.upper().endswith(".SA") or financial_data.get("currency") == "BRL"
        
        # Calculate averages
        avg_br = sum(br_ev_ebitdas) / len(br_ev_ebitdas) if br_ev_ebitdas else None
        avg_us = sum(us_ev_ebitdas) / len(us_ev_ebitdas) if us_ev_ebitdas else None
        
        # BR valuation multiple
        br_multiple = avg_br if avg_br is not None else (avg_us if avg_us is not None else 10.0)
        # US valuation multiple
        us_multiple = avg_us if avg_us is not None else (avg_br if avg_br is not None else 10.0)
        
        # Select primary multiple for logging
        if is_target_brl:
            primary_multiple = br_multiple
            primary_label = "BR Peer Group (local market)" if avg_br is not None else "US Peer Group (fallback)"
        else:
            primary_multiple = us_multiple
            primary_label = "US Peer Group (local market)" if avg_us is not None else "BR Peer Group (fallback)"
            
        # Overall fallback if no multiples are found at all
        fallback_applied = (avg_br is None and avg_us is None)
        if fallback_applied:
            assumptions.append(f"Using default EV/EBITDA multiple of 10.0x (no peer multiples available)")
        else:
            assumptions.append(f"Derived primary EV/EBITDA multiple of {primary_multiple:.1f}x from {primary_label}")
            
        # Add reference assumptions
        if avg_br is not None:
            assumptions.append(f"Local BR Peer Average EV/EBITDA: {avg_br:.1f}x")
        if avg_us is not None:
            assumptions.append(f"Global US Peer Average EV/EBITDA: {avg_us:.1f}x")
            
        if avg_br is not None and avg_us is not None:
            # Highlight macro discount/premium
            if avg_us != 0:
                diff_pct = ((avg_us - avg_br) / avg_us) * 100
                if diff_pct >= 0:
                    assumptions.append(f"Macro valuation gap: BR peers trade at a {diff_pct:.1f}% discount relative to US peers due to country risk and macro factors")
                else:
                    assumptions.append(f"Macro valuation gap: BR peers trade at a {abs(diff_pct):.1f}% premium relative to US peers due to market conditions")
                    
        # 2. Calculation
        # BR Equity Value and Intrinsic Value
        enterprise_value_br = ebitda * br_multiple
        equity_value_br = enterprise_value_br - total_debt + total_cash
        intrinsic_value_br = max(0.0, equity_value_br / shares_outstanding) if equity_value_br > 0 else 0.0

        # US Equity Value and Intrinsic Value
        enterprise_value_us = ebitda * us_multiple
        equity_value_us = enterprise_value_us - total_debt + total_cash
        intrinsic_value_us = max(0.0, equity_value_us / shares_outstanding) if equity_value_us > 0 else 0.0

        # Determine primary metrics for legacy interface and diagnostic compatibility
        primary_equity_value = equity_value_br if is_target_brl else equity_value_us
        primary_enterprise_value = enterprise_value_br if is_target_brl else enterprise_value_us
        intrinsic_value = intrinsic_value_br if is_target_brl else intrinsic_value_us
        
        if primary_equity_value <= 0:
            return self.create_diagnostic_result(
                reason_code="NEGATIVE_EQUITY_VALUE",
                explanation=f"Computed primary equity value ({primary_equity_value:,.0f}) is negative or zero after subtracting total debt ({total_debt:,.0f}) from enterprise value ({primary_enterprise_value:,.0f}).",
                triggering_metrics={
                    "enterprise_value": primary_enterprise_value,
                    "total_debt": total_debt,
                    "total_cash": total_cash
                },
                analytical_implication="The company's debt burden is larger than the projected enterprise value, leaving no residual value for equity holders.",
                baseline_metrics={
                    "enterprise_value": primary_enterprise_value,
                    "total_debt": total_debt,
                    "total_cash": total_cash,
                    "shares_outstanding": shares_outstanding
                },
                assumptions=assumptions
            )
            
        # Compute BR Verdict
        verdict_br = "INSUFFICIENT_DATA"
        if br_multiple is not None and intrinsic_value_br > 0:
            mos_br = ((intrinsic_value_br - current_price) / intrinsic_value_br) * 100
            if mos_br > 20:
                verdict_br = "UNDERVALUED"
            elif mos_br < -10:
                verdict_br = "OVERVALUED"
            else:
                verdict_br = "FAIRLY_VALUED"
                
        # Compute US Verdict
        verdict_us = "INSUFFICIENT_DATA"
        if us_multiple is not None and intrinsic_value_us > 0:
            mos_us = ((intrinsic_value_us - current_price) / intrinsic_value_us) * 100
            if mos_us > 20:
                verdict_us = "UNDERVALUED"
            elif mos_us < -10:
                verdict_us = "OVERVALUED"
            else:
                verdict_us = "FAIRLY_VALUED"
                
        assumptions.append(f"BR SOTP Valuation: {intrinsic_value_br:.2f} (Verdict: {verdict_br})")
        assumptions.append(f"US SOTP Valuation: {intrinsic_value_us:.2f} (Verdict: {verdict_us})")
        
        baseline_metrics = {
            "current_price": current_price,
            "shares_outstanding": shares_outstanding,
            "total_debt": total_debt,
            "total_cash": total_cash,
            "ebitda": ebitda,
            "peer_avg_ev_ebitda": primary_multiple
        }
        
        from core.schemas import PeerCompany
        peers_list = [PeerCompany(ticker=p["ticker"], market_cap=p["market_cap"], multiples=p["multiples"]) for p in peer_companies]
        
        macro_gap_pct = None
        if avg_br is not None and avg_us is not None and avg_us != 0:
            macro_gap_pct = float(((avg_us - avg_br) / avg_us) * 100)

        return ValuationResult(
            intrinsic_value=round(intrinsic_value, 2),
            methodology_name=self.name,
            assumptions=assumptions,
            baseline_metrics=baseline_metrics,
            peer_comparison=peers_list,
            fallback_applied=fallback_applied,
            metadata={
                "avg_peer_ev_ebitda": float(primary_multiple),
                "enterprise_value": float(primary_enterprise_value),
                "equity_value": float(primary_equity_value),
                "local_peer_avg": float(avg_br) if avg_br is not None else None,
                "global_peer_avg": float(avg_us) if avg_us is not None else None,
                "macro_gap_pct": macro_gap_pct,
                "intrinsic_value_br": float(intrinsic_value_br),
                "intrinsic_value_us": float(intrinsic_value_us),
                "verdict_br": verdict_br,
                "verdict_us": verdict_us
            }
        )
