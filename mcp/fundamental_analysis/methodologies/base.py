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
