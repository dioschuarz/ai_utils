from typing import List, Optional
from core.mappings import GICS_MAPPINGS
from core.schemas import ValuationRequest
from methodologies.base import BaseMethodology
from methodologies.dcf import DCFMethodology
from methodologies.cca import CCAMethodology
from methodologies.dummy import DummyMethodology

class ValuationDispatcher:
    """
    Dispatcher to resolve GICS sub-industry ID to the most appropriate
    valuation methodology.
    """

    def __init__(self):
        self._methodologies = {
            "DCF": DCFMethodology(),
            "CCA": CCAMethodology(),
            "DUMMY": DummyMethodology()
        }

    def get_available_methodologies(self, sub_industry_id: str) -> List[str]:
        """
        Get the list of methodology names mapped to a GICS sub-industry.
        """
        mappings = GICS_MAPPINGS.get(sub_industry_id, [])
        return [m["methodology_name"] for m in mappings]

    def select_methodology(self, request: ValuationRequest) -> BaseMethodology:
        """
        Selects and instantiates the methodology class based on request parameters
        and GICS mappings.
        """
        # 1. Check if specific methodology is requested
        if request.specific_methodology:
            method_name = request.specific_methodology.upper()
            if method_name in self._methodologies:
                return self._methodologies[method_name]
            # Fall back to default if requested methodology is not implemented
            
        # 2. Look up GICS sub-industry ID mappings
        sub_id = request.gics_sub_industry_id
        if sub_id:
            available = self.get_available_methodologies(sub_id)
            # Find the first supported methodology in the list
            for method_name in available:
                norm_name = method_name.upper()
                if norm_name in self._methodologies:
                    return self._methodologies[norm_name]

        # 3. Default fallback
        return self._methodologies["DCF"]
