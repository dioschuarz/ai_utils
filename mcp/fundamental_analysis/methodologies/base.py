from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from core.schemas import ValuationRequest, ValuationResult

class BaseMethodology(ABC):
    """
    Abstract base class for all fundamental analysis valuation methodologies.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        The canonical name of the valuation methodology (e.g., 'DCF', 'CCA').
        """
        pass

    @abstractmethod
    def calculate(
        self,
        request: ValuationRequest,
        financial_data: Dict[str, float],
        peers: List[Dict[str, float]]
    ) -> ValuationResult:
        """
        Performs the specific financial valuation calculation.

        Args:
            request: The original ValuationRequest containing inputs and parameters.
            financial_data: A dictionary of key financial metrics for the target company.
            peers: A list of financial metrics dictionaries for comparable peer companies.

        Returns:
            A structured ValuationResult containing the intrinsic value, assumptions,
            baseline metrics, peer comparisons, and metadata.
        """
        pass

    def create_diagnostic_result(
        self,
        reason_code: str,
        explanation: str,
        triggering_metrics: Dict[str, Optional[float]],
        analytical_implication: str,
        baseline_metrics: Optional[Dict[str, Optional[float]]] = None,
        peer_comparison: Optional[List] = None,
        assumptions: Optional[List[str]] = None
    ) -> ValuationResult:
        """
        Helper method to construct a standard ValuationResult containing a diagnostic error.
        """
        from core.schemas import ValuationDiagnostic, ValuationResult
        # Clean any float or list of float values for json serializability (convert None or NaN gracefully)
        cleaned_metrics = {}
        for k, v in triggering_metrics.items():
            if v is not None:
                if isinstance(v, list):
                    cleaned_metrics[k] = [float(x) for x in v if x is not None]
                else:
                    cleaned_metrics[k] = float(v)
            else:
                cleaned_metrics[k] = None

        cleaned_baseline = {}
        if baseline_metrics:
            for k, v in baseline_metrics.items():
                if v is not None:
                    if isinstance(v, list):
                        cleaned_baseline[k] = [float(x) for x in v if x is not None]
                    else:
                        cleaned_baseline[k] = float(v)
                else:
                    cleaned_baseline[k] = None

        return ValuationResult(
            intrinsic_value=None,
            methodology_name=self.name,
            assumptions=assumptions or [f"Valuation failed: {explanation}"],
            baseline_metrics=cleaned_baseline,
            peer_comparison=peer_comparison or [],
            diagnostic=ValuationDiagnostic(
                reason_code=reason_code,
                explanation=explanation,
                triggering_metrics=cleaned_metrics,
                analytical_implication=analytical_implication
            ),
            fallback_applied=True,
            metadata={}
        )

