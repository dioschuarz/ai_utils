from typing import Dict, List
from core.schemas import ValuationRequest, ValuationResult
from methodologies.base import BaseMethodology

class NAVMethodology(BaseMethodology):
    """
    Net Asset Value (NAV) valuation methodology.
    For standard companies, this corresponds to the book value of equity.
    """

    @property
    def name(self) -> str:
        return "NAV"

    def calculate(
        self,
        request: ValuationRequest,
        financial_data: Dict[str, float],
        peers: List[Dict[str, float]]
    ) -> ValuationResult:
        
        assumptions = []
        
        # 1. Extract inputs
        book_value = financial_data.get("book_value", 0.0)
        shares_outstanding = financial_data.get("shares_outstanding", 0.0)
        current_price = financial_data.get("current_price", 0.0)
        
        # Check book_value
        if book_value <= 0 or shares_outstanding <= 0:
            reason = "INVALID_BOOK_VALUE" if book_value <= 0 else "MISSING_DATA"
            explanation = f"NAV requires positive book value. Found book value: {book_value}."
            if shares_outstanding <= 0:
                explanation = "NAV requires positive shares outstanding."
            return self.create_diagnostic_result(
                reason_code=reason,
                explanation=explanation,
                triggering_metrics={
                    "book_value": book_value,
                    "shares_outstanding": shares_outstanding
                },
                analytical_implication="Net Asset Value relies on a positive net equity base. A negative book value indicates that liabilities exceed assets, making the company insolvent on a book-value basis and rendering a traditional NAV valuation invalid.",
                baseline_metrics={
                    "book_value": book_value,
                    "shares_outstanding": shares_outstanding,
                    "current_price": current_price
                }
            )
            
        intrinsic_value = book_value
        assumptions.append(f"NAV Valuation: {intrinsic_value:.2f} (based on Book Value Per Share of {book_value:,.2f})")
        
        baseline_metrics = {
            "current_price": current_price,
            "shares_outstanding": shares_outstanding,
            "book_value": book_value,
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
                "book_value": book_value
            }
        )
