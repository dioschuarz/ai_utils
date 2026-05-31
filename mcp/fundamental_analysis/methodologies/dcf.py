from typing import Dict, List
from core.schemas import ValuationRequest, ValuationResult
from methodologies.base import BaseMethodology

class DCFMethodology(BaseMethodology):
    """
    Discounted Cash Flow (DCF) valuation methodology.
    """

    @property
    def name(self) -> str:
        return "DCF"

    def calculate(
        self,
        request: ValuationRequest,
        financial_data: Dict[str, float],
        peers: List[Dict[str, float]]
    ) -> ValuationResult:
        
        fallback_applied = False
        assumptions = []
        
        # 1. Extract inputs
        current_price = financial_data.get("current_price", 0.0)
        shares_outstanding = financial_data.get("shares_outstanding", 0.0)
        market_cap = financial_data.get("market_cap", 0.0) or (current_price * shares_outstanding)
        total_debt = financial_data.get("total_debt", 0.0)
        total_cash = financial_data.get("total_cash", 0.0)
        
        # 2. Free Cash Flow (FCF) base resolution
        fcf = financial_data.get("free_cash_flow", 0.0)
        ocf = financial_data.get("operating_cash_flow", 0.0)
        revenue = financial_data.get("total_revenue", 0.0)
        
        base_fcf = 0.0
        if fcf > 0:
            base_fcf = fcf
            assumptions.append(f"Using reported Free Cash Flow of {fcf:,.2f} as base")
        elif ocf > 0:
            base_fcf = ocf * 0.8
            fallback_applied = True
            assumptions.append(f"Using Operating Cash Flow * 0.8 ({base_fcf:,.2f}) as FCF proxy due to negative/missing FCF")
        elif revenue > 0:
            base_fcf = revenue * 0.1
            fallback_applied = True
            assumptions.append(f"Using 10% of Revenue ({base_fcf:,.2f}) as FCF proxy due to missing cash flow data")
        else:
            # Last resort fallback based on market cap or price
            base_fcf = max(market_cap * 0.05, 10.0)
            fallback_applied = True
            assumptions.append(f"Using simulated FCF based on 5% of Market Cap/Price proxy ({base_fcf:,.2f}) due to lack of financial statement data")

        # 3. Resolve growth rate
        rev_growth = financial_data.get("revenue_growth", 0.05)
        growth_rate = 0.05  # Default 5%
        if 0.01 <= rev_growth <= 0.25:
            growth_rate = rev_growth
            assumptions.append(f"Using historical revenue growth rate of {growth_rate * 100:.1f}% for forecast period")
        else:
            assumptions.append(f"Using default mid-term growth rate of {growth_rate * 100:.1f}%")

        # 4. Resolve WACC (discount rate)
        # Determine currency/markets
        is_brl = request.ticker.endswith(".SA") or financial_data.get("currency") == "BRL"
        rf = 0.105 if is_brl else 0.045
        erp = 0.06
        beta = financial_data.get("beta", 1.0)
        if beta <= 0.4 or beta > 3.0:
            beta = 1.0
            
        ke = rf + beta * erp
        
        # Weighted Cost of Capital (WACC) estimation
        equity_weight = 1.0
        debt_weight = 0.0
        if market_cap > 0 or total_debt > 0:
            total_val = market_cap + total_debt
            if total_val > 0:
                equity_weight = market_cap / total_val
                debt_weight = total_debt / total_val
                
        kd = rf + 0.02  # Debt premium of 2.0%
        tax_rate = 0.25
        
        estimated_wacc = (equity_weight * ke) + (debt_weight * kd * (1 - tax_rate))
        # Clamp WACC to reasonable boundaries
        wacc = max(0.06, min(estimated_wacc, 0.15))
        assumptions.append(f"Calculated WACC of {wacc * 100:.2f}% (Beta={beta}, Cost of Equity={ke*100:.1f}%, Cost of Debt={kd*100:.1f}%)")

        # 5. Forecast cash flows (5 years)
        forecasted_fcf = []
        discounted_fcf = []
        for year in range(1, 6):
            fcf_y = base_fcf * ((1 + growth_rate) ** year)
            forecasted_fcf.append(fcf_y)
            df = fcf_y / ((1 + wacc) ** year)
            discounted_fcf.append(df)

        # 6. Terminal Value
        terminal_growth = 0.025
        tv = forecasted_fcf[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
        discounted_tv = tv / ((1 + wacc) ** 5)
        
        assumptions.append(f"Terminal growth rate of {terminal_growth * 100:.1f}%")
        
        # 7. Enterprise Value and Equity Value
        enterprise_value = sum(discounted_fcf) + discounted_tv
        equity_value = enterprise_value - total_debt + total_cash
        
        if equity_value <= 0:
            # Fallback if debt exceeds enterprise value
            equity_value = max(market_cap * 0.5, total_cash)
            fallback_applied = True
            assumptions.append("Applied debt-distress valuation fallback (debt exceeds Enterprise Value)")
            
        # 8. Intrinsic Value per share
        if shares_outstanding > 0:
            intrinsic_value = equity_value / shares_outstanding
        else:
            intrinsic_value = current_price * 1.05 if current_price > 0 else 10.0
            fallback_applied = True
            assumptions.append("Missing shares outstanding; estimated intrinsic value with a standard premium over current price")
            
        # Format baseline metrics
        baseline_metrics = {
            "current_price": current_price,
            "market_cap": market_cap,
            "total_revenue": revenue,
            "free_cash_flow": fcf,
            "operating_cash_flow": ocf,
            "shares_outstanding": shares_outstanding,
            "total_debt": total_debt,
            "total_cash": total_cash,
            "wacc": wacc,
            "growth_rate": growth_rate,
        }
        
        # Structure peer companies from input list
        peer_companies = []
        for idx, peer_raw in enumerate(peers):
            from core.schemas import PeerCompany
            peer_companies.append(PeerCompany(
                ticker=peer_raw.get("ticker", f"PEER{idx}"),
                market_cap=peer_raw.get("market_cap", 0.0),
                multiples=peer_raw.get("multiples", {})
            ))

        return ValuationResult(
            intrinsic_value=round(intrinsic_value, 2),
            methodology_name=self.name,
            assumptions=assumptions,
            baseline_metrics=baseline_metrics,
            peer_comparison=peer_companies,
            fallback_applied=fallback_applied,
            metadata={
                "wacc": wacc,
                "growth_rate": growth_rate,
                "terminal_growth": terminal_growth,
                "enterprise_value": enterprise_value,
                "equity_value": equity_value
            }
        )
