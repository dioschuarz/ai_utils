from typing import Dict, List
from core.schemas import ValuationRequest, ValuationResult, PeerCompany
from methodologies.base import BaseMethodology

class DummyMethodology(BaseMethodology):
    """
    Dummy methodology for testing the decoupling interface and end-to-end flows.
    """

    @property
    def name(self) -> str:
        return "Dummy"

    def calculate(
        self,
        request: ValuationRequest,
        financial_data: Dict[str, float],
        peers: List[Dict[str, float]]
    ) -> ValuationResult:
        
        # Calculate a mock intrinsic value
        current_price = financial_data.get("current_price", 10.0)
        intrinsic_value = current_price * 1.1  # 10% premium
        
        # Structure the baseline metrics
        baseline_metrics = {
            "eps": financial_data.get("eps", 0.0),
            "book_value": financial_data.get("book_value", 0.0),
            "current_price": current_price
        }
        
        # Map peers
        peer_companies = []
        for idx, peer_raw in enumerate(peers):
            peer_companies.append(PeerCompany(
                ticker=peer_raw.get("ticker", f"PEER{idx}"),
                market_cap=peer_raw.get("market_cap", 0.0),
                multiples=peer_raw.get("multiples", {})
            ))
            
        return ValuationResult(
            intrinsic_value=round(intrinsic_value, 2),
            methodology_name=self.name,
            assumptions=["Assumed dummy baseline", "Default WACC 8.0%", "Growth 5.0%"],
            baseline_metrics=baseline_metrics,
            peer_comparison=peer_companies,
            heuristic_vs_peers="fairly_valued",
            heuristic_vs_baseline="fairly_valued",
            fallback_applied=False,
            metadata={"source": "dummy_methodology"}
        )
