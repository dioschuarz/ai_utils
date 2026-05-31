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

        # 2. Gather peer multiples
        peer_pes = []
        peer_ev_ebitdas = []
        peer_ev_revenues = []
        
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
            
            if multiples.get("P/E"):
                peer_pes.append(float(multiples["P/E"]))
            if multiples.get("EV/EBITDA"):
                peer_ev_ebitdas.append(float(multiples["EV/EBITDA"]))
            if multiples.get("EV/Revenue"):
                peer_ev_revenues.append(float(multiples["EV/Revenue"]))

        # 3. Handle peer multiples fallback
        if len(peer_companies) < 2 or (not peer_pes and not peer_ev_ebitdas and not peer_ev_revenues):
            fallback_applied = True
            # Sector-specific default multiples
            sector = (request.gics_sector or "").lower()
            if "tech" in sector or "information technology" in sector:
                avg_pe, avg_ev_ebitda, avg_ev_rev = 28.0, 18.0, 6.0
                assumptions.append("Applied default Technology multiples fallback")
            elif "financial" in sector:
                avg_pe, avg_ev_ebitda, avg_ev_rev = 12.0, 8.0, 2.0
                assumptions.append("Applied default Financials multiples fallback")
            elif "energy" in sector:
                avg_pe, avg_ev_ebitda, avg_ev_rev = 10.0, 5.5, 1.5
                assumptions.append("Applied default Energy multiples fallback")
            else:
                avg_pe, avg_ev_ebitda, avg_ev_rev = 18.0, 11.0, 3.0
                assumptions.append("Applied default broad-market multiples fallback")
        else:
            avg_pe = sum(peer_pes) / len(peer_pes) if peer_pes else 0.0
            avg_ev_ebitda = sum(peer_ev_ebitdas) / len(peer_ev_ebitdas) if peer_ev_ebitdas else 0.0
            avg_ev_rev = sum(peer_ev_revenues) / len(peer_ev_revenues) if peer_ev_revenues else 0.0
            assumptions.append(f"Derived multiples from peer group of {len(peer_companies)} companies")

        # 4. Perform valuations
        valuations = []
        
        # P/E Valuation
        if eps > 0 and avg_pe > 0:
            pe_val = eps * avg_pe
            valuations.append(pe_val)
            assumptions.append(f"P/E Valuation: {pe_val:.2f} (EPS={eps:.2f} * Peer P/E={avg_pe:.1f}x)")
            
        # EV/EBITDA Valuation
        if ebitda > 0 and avg_ev_ebitda > 0 and shares_outstanding > 0:
            target_ev = ebitda * avg_ev_ebitda
            target_equity = target_ev - total_debt + total_cash
            ev_ebitda_val = target_equity / shares_outstanding
            if ev_ebitda_val > 0:
                valuations.append(ev_ebitda_val)
                assumptions.append(f"EV/EBITDA Valuation: {ev_ebitda_val:.2f} (EBITDA/OCF={ebitda:,.0f} * Peer EV/EBITDA={avg_ev_ebitda:.1f}x)")
                
        # EV/Revenue Valuation
        if revenue > 0 and avg_ev_rev > 0 and shares_outstanding > 0:
            target_ev_rev = revenue * avg_ev_rev
            target_equity_rev = target_ev_rev - total_debt + total_cash
            ev_rev_val = target_equity_rev / shares_outstanding
            if ev_rev_val > 0:
                valuations.append(ev_rev_val)
                assumptions.append(f"EV/Revenue Valuation: {ev_rev_val:.2f} (Revenue={revenue:,.0f} * Peer EV/Rev={avg_ev_rev:.1f}x)")

        # 5. Average the valid valuations
        if valuations:
            intrinsic_value = sum(valuations) / len(valuations)
        else:
            intrinsic_value = current_price if current_price > 0 else 10.0
            fallback_applied = True
            assumptions.append("No valid multiples or positive financial bases found; fallback to current market price")

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
            }
        )
