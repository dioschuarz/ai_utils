from typing import Dict, List
from core.schemas import ValuationRequest, ValuationResult
from methodologies.base import BaseMethodology

class RIMMethodology(BaseMethodology):
    """
    Residual Income Model (RIM) valuation methodology.
    Combines book value with the present value of expected residual income.
    """

    @property
    def name(self) -> str:
        return "RIM"

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
        roe = financial_data.get("return_on_equity", 0.0)
        
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
                reason_code="INVALID_BOOK_VALUE",
                explanation=f"RIM requires positive book value. Found book value: {book_value}.",
                triggering_metrics={"book_value": book_value},
                analytical_implication="Residual Income Model requires a positive starting book equity base. A negative book value indicates accumulated losses that exceed equity, preventing residual income calculation.",
                baseline_metrics={
                    "book_value": book_value,
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
        
        # Check if ROE < Cost of Equity
        if roe < ke:
            return self.create_diagnostic_result(
                reason_code="ROE_BELOW_COST_OF_EQUITY",
                explanation=f"{request.ticker} has ROE ({roe*100:.1f}%) below its Cost of Equity ({ke*100:.1f}%).",
                triggering_metrics={"return_on_equity": roe, "cost_of_equity": ke},
                analytical_implication="When return on equity is less than the cost of capital, the company's projects destroy economic value for shareholders, resulting in a negative residual income valuation component.",
                baseline_metrics={
                    "book_value": book_value,
                    "return_on_equity": roe,
                    "cost_of_equity": ke,
                    "shares_outstanding": shares_outstanding,
                    "current_price": current_price
                },
                assumptions=assumptions
            )
            
        # 2. RIM Calculation
        # IV = Book Value + PV of Residual Income
        # Residual Income = (ROE - ke) * Book Value
        # PV of perpetual residual income = Residual Income / ke
        residual_income_pv = ((roe - ke) * book_value) / ke
        intrinsic_value = book_value + residual_income_pv
        
        assumptions.append(f"RIM Valuation: {intrinsic_value:.2f} (BV={book_value:.2f} + PV of Residual Income={residual_income_pv:.2f})")
        
        baseline_metrics = {
            "current_price": current_price,
            "shares_outstanding": shares_outstanding,
            "book_value": book_value,
            "return_on_equity": roe,
            "cost_of_equity": ke,
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
                "cost_of_equity": ke,
                "residual_income_pv": residual_income_pv
            }
        )
