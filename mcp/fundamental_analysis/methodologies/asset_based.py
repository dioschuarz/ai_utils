from typing import Dict, List
from core.schemas import ValuationRequest, ValuationResult
from methodologies.base import BaseMethodology

class AssetBasedMethodology(BaseMethodology):
    """
    Asset-Based valuation methodology.
    Calculates value per share as Book Value (Equity) / Shares Outstanding.
    """

    @property
    def name(self) -> str:
        return "Asset-Based"

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
        
        # 2. Check for missing/invalid inputs
        if book_value <= 0 or shares_outstanding <= 0:
            reason = "INVALID_BOOK_VALUE" if book_value <= 0 else "MISSING_DATA"
            explanation = f"Asset-Based valuation requires positive book value. Found book value: {book_value}."
            if shares_outstanding <= 0:
                explanation = "Asset-Based valuation requires positive shares outstanding."
            return self.create_diagnostic_result(
                reason_code=reason,
                explanation=explanation,
                triggering_metrics={
                    "book_value": book_value,
                    "shares_outstanding": shares_outstanding
                },
                analytical_implication="Asset-Based valuation relies on tangible net worth (book equity). A negative or zero book value indicates the company has net liabilities exceeding assets, making a standard equity-based net asset valuation invalid.",
                baseline_metrics={
                    "book_value": book_value,
                    "shares_outstanding": shares_outstanding,
                    "current_price": current_price
                }
            )
            
        # 3. Calculate VPA
        # In our system (and yfinance/fundamentus), the 'book_value' field contains Book Value Per Share (VPA).
        # We do not divide by shares_outstanding since it is already per share.
        intrinsic_value = book_value
        assumptions.append(f"Asset-Based Valuation: {intrinsic_value:.2f} (Book Value Per Share={book_value:,.2f})")
        
        baseline_metrics = {
            "book_value": book_value,
            "shares_outstanding": shares_outstanding,
            "current_price": current_price,
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
                "book_value": book_value,
                "shares_outstanding": shares_outstanding
            }
        )
