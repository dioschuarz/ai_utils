from typing import Dict, List
from core.schemas import ValuationRequest, ValuationResult
from methodologies.base import BaseMethodology
from methodologies.cca import CCAMethodology

class PTAMethodology(BaseMethodology):
    """
    Precedent Transaction Analysis (PTA) methodology.
    Uses Comparable Company Analysis (CCA) valuation as a baseline and applies a control premium (default 25%).
    """

    @property
    def name(self) -> str:
        return "PTA"

    def calculate(
        self,
        request: ValuationRequest,
        financial_data: Dict[str, float],
        peers: List[Dict[str, float]]
    ) -> ValuationResult:
        
        # CCA calculation is the base
        cca = CCAMethodology()
        cca_result = cca.calculate(request, financial_data, peers)
        
        # If CCA failed, return it directly
        if cca_result.intrinsic_value is None:
            # Propagate diagnostic error
            diagnostic = cca_result.diagnostic
            return self.create_diagnostic_result(
                reason_code=diagnostic.reason_code if diagnostic else "INSUFFICIENT_PEERS",
                explanation=diagnostic.explanation if diagnostic else "PTA relies on CCA, which failed due to insufficient peers.",
                triggering_metrics=diagnostic.triggering_metrics if diagnostic else {"peer_count": 0.0},
                analytical_implication=diagnostic.analytical_implication if diagnostic else "Cannot establish precedent transaction multiples without peer data.",
                baseline_metrics=cca_result.baseline_metrics,
                peer_comparison=cca_result.peer_comparison,
                assumptions=cca_result.assumptions
            )
            
        # Apply acquisition control premium (default 25%)
        control_premium = 0.25
        if request.adjustment_params and "control_premium" in request.adjustment_params:
            control_premium = float(request.adjustment_params["control_premium"])
            
        intrinsic_value = float(cca_result.intrinsic_value) * (1.0 + control_premium)
        
        # Post-Calculation Validator: PTA > CCA
        if control_premium > 0 and float(cca_result.intrinsic_value) > 0:
            assert intrinsic_value > float(cca_result.intrinsic_value), f"PTA valuation ({intrinsic_value:.2f}) must be > CCA baseline ({cca_result.intrinsic_value:.2f}) when control premium is positive."
        
        assumptions = list(cca_result.assumptions)
        assumptions.append(f"PTA Valuation: Applied control/acquisition premium of {control_premium * 100:.1f}% over CCA baseline valuation of {cca_result.intrinsic_value:.2f}")
        
        current_price = financial_data.get("current_price", 0.0)
        metadata = {**cca_result.metadata}
        
        if "intrinsic_value_br" in metadata:
            val_br = round(metadata["intrinsic_value_br"] * (1.0 + control_premium), 2)
            metadata["intrinsic_value_br"] = val_br
            if current_price > 0 and val_br > 0:
                mos = ((val_br - current_price) / val_br) * 100
                metadata["verdict_br"] = "UNDERVALUED" if mos > 20 else ("OVERVALUED" if mos < -10 else "FAIRLY_VALUED")
                
        if "intrinsic_value_us" in metadata:
            val_us = round(metadata["intrinsic_value_us"] * (1.0 + control_premium), 2)
            metadata["intrinsic_value_us"] = val_us
            if current_price > 0 and val_us > 0:
                mos = ((val_us - current_price) / val_us) * 100
                metadata["verdict_us"] = "UNDERVALUED" if mos > 20 else ("OVERVALUED" if mos < -10 else "FAIRLY_VALUED")
                
        metadata["control_premium"] = control_premium
        
        return ValuationResult(
            intrinsic_value=round(intrinsic_value, 2),
            methodology_name=self.name,
            assumptions=assumptions,
            baseline_metrics=cca_result.baseline_metrics,
            peer_comparison=cca_result.peer_comparison,
            fallback_applied=cca_result.fallback_applied,
            metadata=metadata
        )
