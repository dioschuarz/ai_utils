from typing import Dict, List
from core.schemas import ValuationRequest, ValuationResult
from methodologies.base import BaseMethodology

class rDCFMethodology(BaseMethodology):
    """
    Revenue-based Discounted Cash Flow (rDCF) valuation methodology.
    Projects revenue growth and applies operating margins to forecast cash flows.
    """

    @property
    def name(self) -> str:
        return "rDCF"

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
        market_cap = financial_data.get("market_cap", 0.0) or (current_price * shares_outstanding)
        total_debt = financial_data.get("total_debt", 0.0)
        total_cash = financial_data.get("total_cash", 0.0)
        revenue = financial_data.get("total_revenue", 0.0)
        operating_margins = financial_data.get("operating_margins", 0.0)
        
        # Check shares_outstanding
        if shares_outstanding <= 0:
            return self.create_diagnostic_result(
                reason_code="MISSING_DATA",
                explanation="Shares outstanding must be positive to compute intrinsic value per share.",
                triggering_metrics={"shares_outstanding": shares_outstanding},
                analytical_implication="Shares outstanding is missing.",
                baseline_metrics={"shares_outstanding": shares_outstanding, "current_price": current_price}
            )
            
        # Check operating margins
        if operating_margins <= 0:
            return self.create_diagnostic_result(
                reason_code="NEGATIVE_OPERATING_MARGINS",
                explanation=f"{request.ticker} has non-positive operating margins ({operating_margins*100:.1f}%).",
                triggering_metrics={"operating_margins": operating_margins},
                analytical_implication="The Revenue-based DCF model requires positive operating margins to project positive operating cash flows. Unprofitable companies with negative operating margins cannot be valued under this cash flow model.",
                baseline_metrics={
                    "operating_margins": operating_margins,
                    "total_revenue": revenue,
                    "shares_outstanding": shares_outstanding,
                    "current_price": current_price
                }
            )
            
        # Check revenue
        if revenue <= 0:
            return self.create_diagnostic_result(
                reason_code="MISSING_DATA",
                explanation="rDCF requires positive revenue to project future cash flows.",
                triggering_metrics={"total_revenue": revenue},
                analytical_implication="Revenue is missing or zero.",
                baseline_metrics={"total_revenue": revenue, "shares_outstanding": shares_outstanding}
            )

        # Resolve WACC (discount rate) dynamically
        is_brl = request.ticker.endswith(".SA") or financial_data.get("currency") == "BRL"
        country_code = "BR" if is_brl else "US"
        rf = 0.105 if is_brl else 0.045
        erp = 0.06
        inflation_rate = 0.045 if is_brl else 0.035
        
        try:
            from providers.macro_client import MacroClient
            macro_client = MacroClient()
            indicators = macro_client.get_indicators(country_code)
            rf = float(indicators["components"]["risk_free_rate_rf"])
            erp = float(indicators["market_risk_premium"])
            inflation_rate = float(indicators["components"].get("inflation_yoy", inflation_rate))
            assumptions.append(f"Loaded dynamic macro indicators: RF={rf*100:.2f}%, ERP={erp*100:.2f}%")
        except Exception:
            assumptions.append(f"Using fallback macro indicators: RF={rf*100:.2f}%, ERP={erp*100:.2f}%")
            
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
                
        kd = rf + 0.02
        tax_rate = 0.25
        estimated_wacc = (equity_weight * ke) + (debt_weight * kd * (1 - tax_rate))
        wacc = max(0.06, min(estimated_wacc, 0.15))
        assumptions.append(f"Derived WACC of {wacc * 100:.2f}% (Beta={beta})")

        # Resolve growth rate
        rev_growth = financial_data.get("revenue_growth", 0.05)
        growth_rate = 0.05
        if 0.01 <= rev_growth <= 0.25:
            growth_rate = rev_growth
            assumptions.append(f"Using revenue growth rate of {growth_rate * 100:.1f}%")
        else:
            assumptions.append(f"Using default growth rate of {growth_rate * 100:.1f}%")

        # 2. Project Revenues and operating cash flows (5 years)
        # OCF = Revenue * Margin
        forecasted_ocf = []
        discounted_ocf = []
        for year in range(1, 6):
            rev_y = revenue * ((1 + growth_rate) ** year)
            ocf_y = rev_y * operating_margins
            forecasted_ocf.append(ocf_y)
            df = ocf_y / ((1 + wacc) ** year)
            discounted_ocf.append(df)

        # Terminal Value
        terminal_growth = 0.025
        tv = forecasted_ocf[-1] * (1.0 + terminal_growth) / (wacc - terminal_growth)
        discounted_tv = tv / ((1.0 + wacc) ** 5)
        assumptions.append(f"Terminal growth rate of {terminal_growth * 100:.1f}%")

        # 3. Enterprise Value and Equity Value
        enterprise_value = sum(discounted_ocf) + discounted_tv
        equity_value = enterprise_value - total_debt + total_cash
        
        if equity_value <= 0:
            return self.create_diagnostic_result(
                reason_code="NEGATIVE_EQUITY_VALUE",
                explanation=f"Computed equity value ({equity_value:,.0f}) is negative or zero after subtracting total debt ({total_debt:,.0f}) from enterprise value ({enterprise_value:,.0f}).",
                triggering_metrics={
                    "enterprise_value": enterprise_value,
                    "total_debt": total_debt,
                    "total_cash": total_cash
                },
                analytical_implication="The company's debt burden is larger than the projected enterprise value derived from revenue projections, leaving no equity value.",
                baseline_metrics={
                    "book_value": financial_data.get("book_value", 0.0),
                    "total_debt": total_debt,
                    "shares_outstanding": shares_outstanding,
                    "current_price": current_price
                },
                assumptions=assumptions
            )
            
        intrinsic_value = equity_value / shares_outstanding
        assumptions.append(f"rDCF Valuation: {intrinsic_value:.2f} (EV={enterprise_value:,.0f} - Debt + Cash)")

        baseline_metrics = {
            "current_price": current_price,
            "shares_outstanding": shares_outstanding,
            "total_revenue": revenue,
            "operating_margins": operating_margins,
            "total_debt": total_debt,
            "total_cash": total_cash,
            "wacc": wacc,
            "growth_rate": growth_rate
        }
        
        return ValuationResult(
            intrinsic_value=round(intrinsic_value, 2),
            methodology_name=self.name,
            assumptions=assumptions,
            baseline_metrics=baseline_metrics,
            peer_comparison=[],
            fallback_applied=False,
            metadata={
                "wacc": wacc,
                "growth_rate": growth_rate,
                "terminal_growth": terminal_growth,
                "enterprise_value": enterprise_value,
                "equity_value": equity_value
            }
        )
