from typing import List, Optional
from core.schemas import ValuationRequest
from methodologies.base import BaseMethodology
from methodologies.dcf import DCFMethodology
from methodologies.cca import CCAMethodology
from methodologies.dummy import DummyMethodology
from methodologies.asset_based import AssetBasedMethodology
from methodologies.pta import PTAMethodology
from methodologies.sotp import SOTPMethodology
from methodologies.ddm import DDMMethodology
from methodologies.nav import NAVMethodology
from methodologies.rim import RIMMethodology
from methodologies.real_options import RealOptionsMethodology
from methodologies.replacement import ReplacementMethodology
from methodologies.rdcf import rDCFMethodology
from methodologies.ev import EVMethodology

class EVDACFMethodology(EVMethodology):
    """
    Enterprise Value / Debt-Adjusted Cash Flow (EV-DACF) valuation methodology.
    Inherits calculation logic from EVMethodology but has a distinct identity.
    """
    @property
    def name(self) -> str:
        return "EV-DACF"

class ValuationDispatcher:
    """
    Dispatcher to resolve GICS sub-industry ID to the most appropriate
    valuation methodology.
    """

    def __init__(self):
        self._methodologies = {
            "DCF": DCFMethodology(),
            "CCA": CCAMethodology(),
            "DUMMY": DummyMethodology(),
            "ASSET-BASED": AssetBasedMethodology(),
            "ASSET_BASED": AssetBasedMethodology(),
            "PTA": PTAMethodology(),
            "SOTP": SOTPMethodology(),
            "DDM": DDMMethodology(),
            "NAV": NAVMethodology(),
            "RIM": RIMMethodology(),
            "REAL-OPTIONS": RealOptionsMethodology(),
            "REAL_OPTIONS": RealOptionsMethodology(),
            "REPLACEMENT": ReplacementMethodology(),
            "RDCF": rDCFMethodology(),
            "EV": EVMethodology(),
            "EV-DACF": EVDACFMethodology(),
            "EV_DACF": EVDACFMethodology()
        }

    def get_available_methodologies(self, isic_code: str) -> List[str]:
        """
        Get the list of methodology names mapped to an ISIC code.
        """
        from core.mappings import ISICCache
        cache = ISICCache()
        try:
            row = cache.get_row(isic_code)
        except Exception:
            return []
        
        methods = []
        for col in ["primary_method_1", "primary_method_2", "supporting_method_1", "supporting_method_2"]:
            val = row.get(col)
            if val:
                # Handle split methods like "DCF / rDCF"
                for part in val.split("/"):
                    norm = part.strip().upper()
                    if norm:
                        methods.append(norm)
        return methods

    def select_methodology(self, request: ValuationRequest) -> BaseMethodology:
        """
        Selects and instantiates the methodology class based on request parameters
        and ISIC mappings.
        """
        # 1. Check if specific methodology is requested
        if request.specific_methodology:
            method_name = request.specific_methodology.upper().replace("-", "_").replace(" ", "_").strip()
            if method_name in self._methodologies:
                return self._methodologies[method_name]
            alt_name = method_name.replace("_", "-")
            if alt_name in self._methodologies:
                return self._methodologies[alt_name]
            return None  # Return None if requested methodology is not supported
            
        # 2. Look up ISIC code mappings
        sub_id = request.isic_code
        if sub_id:
            available = self.get_available_methodologies(sub_id)
            # Find the first supported methodology in the list
            for method_name in available:
                norm_name = method_name.upper().replace("-", "_").replace(" ", "_").strip()
                if norm_name in self._methodologies:
                    return self._methodologies[norm_name]
                alt_name = norm_name.replace("_", "-")
                if alt_name in self._methodologies:
                    return self._methodologies[alt_name]

        # 3. Default fallback
        return self._methodologies["DCF"]
