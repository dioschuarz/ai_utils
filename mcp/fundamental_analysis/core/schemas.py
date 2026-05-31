from typing import Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field

class PeerCompany(BaseModel):
    ticker: str
    market_cap: float
    multiples: Dict[str, float]

class ValuationRequest(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol (e.g., AAPL)")
    gics_sector: Optional[str] = Field(None, description="Optional GICS sector name or code")
    gics_industry_group: Optional[str] = Field(None, description="Optional GICS industry group name or code")
    gics_industry: Optional[str] = Field(None, description="Optional GICS industry name or code")
    gics_sub_industry: Optional[str] = Field(None, description="Optional GICS sub-industry name or code")
    gics_sub_industry_id: Optional[str] = Field(None, description="Optional: Explicit GICS sub-industry ID to bypass lookup")
    financial_overrides: Optional[Dict[str, float]] = Field(None, description="Optional: User-provided values to override fetched data")
    specific_methodology: Optional[str] = Field(None, description="Optional: Force a specific methodology instead of GICS-based dispatch")

class ValuationResult(BaseModel):
    intrinsic_value: float
    methodology_name: str
    assumptions: List[str]
    baseline_metrics: Dict[str, float]
    peer_comparison: List[PeerCompany]
    heuristic_vs_peers: Optional[Literal["undervalued", "overvalued", "fairly_valued"]] = None
    heuristic_vs_baseline: Optional[Literal["undervalued", "overvalued", "fairly_valued"]] = None
    fallback_applied: bool
    metadata: Dict[str, Union[str, float, int, bool]]
