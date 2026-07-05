from typing import Dict, List
from core.schemas import ValuationRequest, ValuationResult
from methodologies.base import BaseMethodology

class DDMMethodology(BaseMethodology):
    """
    Dividend Discount Model (DDM) valuation methodology.
    Uses the Gordon Growth Model to discount projected dividends.
    """

    @property
    def name(self) -> str:
        return "DDM"

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
        dividend_rate = financial_data.get("dividend_rate", 0.0)
        dividend_yield = financial_data.get("dividend_yield", 0.0)
        roe = financial_data.get("return_on_equity", 0.0)
        payout_ratio = financial_data.get("payout_ratio", 0.0)
        
        # Check shares_outstanding
        if shares_outstanding <= 0:
            return self.create_diagnostic_result(
                reason_code="MISSING_DATA",
                explanation="Shares outstanding must be positive to compute intrinsic value per share.",
                triggering_metrics={"shares_outstanding": shares_outstanding},
                analytical_implication="Shares outstanding is missing.",
                baseline_metrics={"shares_outstanding": shares_outstanding, "current_price": current_price}
            )
            
        # Check if dividend is paid
        if dividend_rate <= 0 and dividend_yield <= 0:
            return self.create_diagnostic_result(
                reason_code="NO_DIVIDEND_HISTORY",
                explanation=f"{request.ticker} does not pay dividends (dividendRate: {dividend_rate}, dividendYield: {dividend_yield}).",
                triggering_metrics={"dividend_rate": dividend_rate, "dividend_yield": dividend_yield},
                analytical_implication="The Dividend Discount Model relies entirely on cash returned to shareholders via dividends. Companies that do not pay dividends cannot be valued under this methodology.",
                baseline_metrics={
                    "dividend_rate": dividend_rate,
                    "dividend_yield": dividend_yield,
                    "shares_outstanding": shares_outstanding,
                    "current_price": current_price
                }
            )
            
        # Resolve cost of equity (ke) via CAPM
        is_brl = request.ticker.endswith(".SA") or financial_data.get("currency") == "BRL"
        country_code = "BR" if is_brl else "US"
        rf = 0.105 if is_brl else 0.045
        erp = 0.06
        
        try:
            from providers.macro_client import MacroClient
            macro_client = MacroClient()
            indicators = macro_client.get_indicators(country_code)
            rf = float(indicators["components"]["risk_free_rate_rf"])
            erp = float(indicators["market_risk_premium"])
            assumptions.append(f"Loaded dynamic macro indicators: RF={rf*100:.2f}%, ERP={erp*100:.2f}%")
        except Exception:
            assumptions.append(f"Using fallback macro indicators: RF={rf*100:.2f}%, ERP={erp*100:.2f}%")
            
        beta = financial_data.get("beta", 1.0)
        if beta <= 0.4 or beta > 3.0:
            beta = 1.0
            
        ke = rf + beta * erp
        assumptions.append(f"Derived Cost of Equity (ke) of {ke*100:.2f}% (Beta={beta})")
        
        # Calculate dividend growth rate (g) using sustainable growth rate formula: g = ROE * (1 - payoutRatio)
        g = 0.03  # Default 3%
        if request.adjustment_params and "terminal_growth" in request.adjustment_params:
            g = float(request.adjustment_params["terminal_growth"])
            assumptions.append(f"Using adjusted dividend growth rate (g) of {g*100:.2f}%")
        elif roe > 0:
            retention_ratio = max(0.0, min(1.0 - payout_ratio, 1.0))
            g_raw = roe * retention_ratio
            assumptions.append(f"Calculated raw sustainable dividend growth rate (g) of {g_raw*100:.2f}% (ROE={roe*100:.1f}%, Retention={retention_ratio*100:.1f}%)")
            
            # Apply nominal GDP growth cap or dynamic GDP growth cap
            nominal_gdp_growth = 0.04
            if request.adjustment_params and "nominal_gdp_growth" in request.adjustment_params:
                nominal_gdp_growth = float(request.adjustment_params["nominal_gdp_growth"])
            elif is_brl:
                nominal_gdp_growth = 0.075  # 7.5% for BR
                
            g = min(g_raw, nominal_gdp_growth)
            if g < g_raw:
                assumptions.append(f"Capped sustainable dividend growth rate to nominal GDP growth rate proxy of {g*100:.2f}%")
        else:
            rev_growth = financial_data.get("revenue_growth", 0.0)
            if 0.01 <= rev_growth <= 0.10:
                g = rev_growth
                assumptions.append(f"Using revenue growth rate of {g*100:.1f}% as dividend growth rate proxy")
            else:
                assumptions.append(f"Using default dividend growth rate of {g*100:.1f}%")
                
        # Check growth exceeds cost of equity before capping
        if g >= ke:
            return self.create_diagnostic_result(
                reason_code="GROWTH_EXCEEDS_COST_OF_EQUITY",
                explanation=f"Sustainability growth rate ({g*100:.2f}%) exceeds or equals the Cost of Equity ({ke*100:.2f}%).",
                triggering_metrics={"growth_rate": g, "cost_of_equity": ke},
                analytical_implication="The Gordon Growth Model requires the cost of equity to be strictly greater than the growth rate. A sustainable growth rate higher than the discount rate implies an infinite valuation, rendering the model invalid.",
                baseline_metrics={
                    "dividend_rate": dividend_rate,
                    "growth_rate": g,
                    "cost_of_equity": ke,
                    "shares_outstanding": shares_outstanding,
                    "current_price": current_price
                },
                assumptions=assumptions
            )
            
        # 2. Gordon Growth Model calculation
        # Value = Div * (1 + g) / (ke - g)
        intrinsic_value = dividend_rate * (1.0 + g) / (ke - g)
        
        assumptions.append(f"DDM Valuation: {intrinsic_value:.2f} (Div={dividend_rate:.2f} * (1 + {g*100:.1f}%) / ({ke*100:.1f}% - {g*100:.1f}%))")
        
        baseline_metrics = {
            "current_price": current_price,
            "shares_outstanding": shares_outstanding,
            "dividend_rate": dividend_rate,
            "dividend_yield": dividend_yield,
            "return_on_equity": roe,
            "payout_ratio": payout_ratio,
            "growth_rate": g,
            "cost_of_equity": ke
        }
        
        return ValuationResult(
            intrinsic_value=round(intrinsic_value, 2),
            methodology_name=self.name,
            assumptions=assumptions,
            baseline_metrics=baseline_metrics,
            peer_comparison=[],
            fallback_applied=False,
            metadata={
                "cost_of_equity": ke,
                "dividend_growth_rate": g
            }
        )
