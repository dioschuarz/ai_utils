from typing import Dict, List
from core.schemas import ValuationRequest, ValuationResult
from methodologies.base import BaseMethodology

class ReplacementMethodology(BaseMethodology):
    """
    Replacement Cost valuation methodology.
    Estimates the replacement cost of assets and derives equity value per share.
    """

    @property
    def name(self) -> str:
        return "Replacement"

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
            
        # Check if financials/bank
        is_financial = False
        isic_code = getattr(request, "isic_code", None) or getattr(request, "gics_sub_industry_id", None) or ""
        isic_division_desc = getattr(request, "isic_division", None) or ""
        sector_info = ""
        
        if isic_code and len(isic_code) >= 2 and isic_code[:2] in ("64", "65", "66"):
            is_financial = True
            sector_info = f"ISIC code prefix {isic_code[:2]}"
        elif isic_division_desc and any(kw in isic_division_desc.lower() for kw in ("financial", "bank", "insurance")):
            is_financial = True
            sector_info = f"ISIC division: {isic_division_desc}"
        elif getattr(request, "gics_sector", None) == "Financials" or "bank" in str(getattr(request, "gics_industry", "")).lower() or "financials" in str(getattr(request, "gics_sector", "")).lower():
            is_financial = True
            sector_info = f"GICS sector: {getattr(request, 'gics_sector', '')}"
            
        if is_financial:
            return self.create_diagnostic_result(
                reason_code="INSUFFICIENT_ASSET_DATA",
                explanation=f"Replacement cost valuation is not applicable to Financials sector companies ({sector_info}).",
                triggering_metrics={"total_debt": total_debt},
                analytical_implication="Financial services firms and banks have complex balance sheets where standard tangible asset replacement calculations are not economically meaningful.",
                baseline_metrics={
                    "book_value": book_value,
                    "total_debt": total_debt,
                    "shares_outstanding": shares_outstanding,
                    "current_price": current_price
                }
            )

        # Derived Total Assets = bookValue * sharesOutstanding + totalDebt
        derived_assets = (book_value * shares_outstanding) + total_debt
        
        if derived_assets <= 0:
            return self.create_diagnostic_result(
                reason_code="INSUFFICIENT_ASSET_DATA",
                explanation=f"Replacement valuation requires positive derived total assets. Found derived assets: {derived_assets:,.0f}.",
                triggering_metrics={"derived_assets": derived_assets},
                analytical_implication="Replacement cost valuation requires physical asset data. When derived total assets are negative or zero, we cannot compute a replacement value.",
                baseline_metrics={
                    "book_value": book_value,
                    "total_debt": total_debt,
                    "shares_outstanding": shares_outstanding,
                    "current_price": current_price
                }
            )
            
        # Standard replacement cost factor (assets are valued at a premium of 15% due to replacement/inflation premium)
        replacement_premium = 0.15
        replacement_assets = derived_assets * (1.0 + replacement_premium)
        
        # Deduct total debt to get equity value
        equity_value = replacement_assets - total_debt
        
        if equity_value <= 0:
            return self.create_diagnostic_result(
                reason_code="NEGATIVE_EQUITY_VALUE",
                explanation=f"Computed equity replacement value ({equity_value:,.0f}) is negative or zero.",
                triggering_metrics={"replacement_assets": replacement_assets, "total_debt": total_debt},
                analytical_implication="The company's debt burden is larger than the estimated replacement cost of its asset base, leaving no equity replacement value.",
                baseline_metrics={
                    "book_value": book_value,
                    "total_debt": total_debt,
                    "shares_outstanding": shares_outstanding,
                    "current_price": current_price
                }
            )
            
        intrinsic_value = equity_value / shares_outstanding
        assumptions.append(f"Replacement Cost Valuation: {intrinsic_value:.2f} (Assets={derived_assets:,.0f} * {1.0 + replacement_premium:.2f} - Debt={total_debt:,.0f})")
        
        baseline_metrics = {
            "current_price": current_price,
            "shares_outstanding": shares_outstanding,
            "book_value": book_value,
            "total_debt": total_debt,
            "derived_assets": derived_assets,
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
                "derived_assets": derived_assets,
                "replacement_assets": replacement_assets,
                "replacement_premium": replacement_premium
            }
        )
