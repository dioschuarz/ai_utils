import math
from typing import Dict, List
from core.schemas import ValuationRequest, ValuationResult
from methodologies.base import BaseMethodology

# Standard normal cumulative distribution function (N(x))
def ndtr(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

class RealOptionsMethodology(BaseMethodology):
    """
    Real Options valuation methodology.
    Uses Black-Scholes call option pricing model to value equity as a call option on company assets.
    """

    @property
    def name(self) -> str:
        return "Real Options"

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
        book_value = financial_data.get("book_value", 0.0)
        total_debt = financial_data.get("total_debt", 0.0)
        
        # Check shares_outstanding
        if shares_outstanding <= 0:
            return self.create_diagnostic_result(
                reason_code="MISSING_DATA",
                explanation="Shares outstanding must be positive to compute intrinsic value per share.",
                triggering_metrics={"shares_outstanding": shares_outstanding},
                analytical_implication="Shares outstanding is missing.",
                baseline_metrics={"shares_outstanding": shares_outstanding, "current_price": current_price}
            )
            
        # Check book value
        if book_value <= 0:
            return self.create_diagnostic_result(
                reason_code="INVALID_UNDERLYING_ASSET",
                explanation=f"Real Options requires positive book value. Found book value: {book_value}.",
                triggering_metrics={"book_value": book_value},
                analytical_implication="Real Options pricing models view firm equity as a call option on its underlying asset base. A negative book value implies that asset base is negative or invalid, making the option underlying pricing mathematically invalid.",
                baseline_metrics={
                    "book_value": book_value,
                    "shares_outstanding": shares_outstanding,
                    "current_price": current_price
                }
            )
            
        # 2. Black-Scholes Variables Setup
        # Asset value S = book value of equity (aggregate) + total debt
        asset_value = (book_value * shares_outstanding) + total_debt
        strike_price = total_debt if total_debt > 0 else 1.0  # Avoid division by zero
        
        is_brl = request.ticker.endswith(".SA") or financial_data.get("currency") == "BRL"
        country_code = "BR" if is_brl else "US"
        rf = 0.105 if is_brl else 0.045
        
        try:
            from providers.macro_client import MacroClient
            macro_client = MacroClient()
            indicators = macro_client.get_indicators(country_code)
            rf = float(indicators["components"]["risk_free_rate_rf"])
            assumptions.append(f"Loaded dynamic risk-free rate: {rf*100:.2f}%")
        except Exception:
            assumptions.append(f"Using fallback risk-free rate: {rf*100:.2f}%")
            
        beta = financial_data.get("beta", 1.0)
        if beta <= 0.4 or beta > 3.0:
            beta = 1.0
            
        # Volatility proxy: scale beta to represent asset volatility (typically 20% to 50%)
        sigma = max(0.15, min(beta * 0.25, 0.60))
        time_to_maturity = 10.0  # 10 year horizon
        
        assumptions.append(f"Model parameters: Asset Volatility={sigma*100:.1f}%, Maturity={time_to_maturity:.1f} years, Risk-Free Rate={rf*100:.2f}%")
        
        # 3. Black-Scholes Calculation
        d1 = (math.log(asset_value / strike_price) + (rf + (sigma ** 2) / 2.0) * time_to_maturity) / (sigma * math.sqrt(time_to_maturity))
        d2 = d1 - sigma * math.sqrt(time_to_maturity)
        
        call_option_value = asset_value * ndtr(d1) - strike_price * math.exp(-rf * time_to_maturity) * ndtr(d2)
        intrinsic_value = call_option_value / shares_outstanding
        
        assumptions.append(f"Real Options Valuation: {intrinsic_value:.2f} (Call Option Value={call_option_value:,.0f} / Shares={shares_outstanding:,.0f})")
        
        baseline_metrics = {
            "current_price": current_price,
            "shares_outstanding": shares_outstanding,
            "book_value": book_value,
            "total_debt": total_debt,
            "asset_value": asset_value,
            "strike_price": strike_price,
            "intrinsic_value": intrinsic_value
        }
        
        return ValuationResult(
            intrinsic_value=round(intrinsic_value, 2),
            methodology_name=self.name,
            assumptions=assumptions,
            baseline_metrics=baseline_metrics,
            peer_comparison=[],
            fallback_applied=False,
            metadata={
                "asset_value": asset_value,
                "strike_price": strike_price,
                "volatility": sigma,
                "d1": d1,
                "d2": d2
            }
        )
