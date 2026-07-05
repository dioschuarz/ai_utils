from typing import Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field

class PeerCompany(BaseModel):
    ticker: str
    market_cap: float
    multiples: Dict[str, float]

class ValuationRequest(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol (e.g., AAPL)")
    isic_code: str = Field(..., description="ISIC Rev 5 classification code")
    isic_division: Optional[str] = Field(None, description="ISIC Division description")
    isic_group: Optional[str] = Field(None, description="ISIC Group description")
    isic_class: Optional[str] = Field(None, description="ISIC Class description")
    specific_methodology: Optional[str] = Field(None, description="Force a specific methodology")
    financial_overrides: Optional[Dict[str, float]] = Field(None, description="User-provided values to override fetched data")
    adjustment_params: Optional[Dict[str, Union[float, str, bool]]] = None

    # Backward compatibility fields
    gics_sector: Optional[str] = None
    gics_industry_group: Optional[str] = None
    gics_industry: Optional[str] = None
    gics_sub_industry: Optional[str] = None
    gics_sub_industry_id: Optional[str] = None


class ValuationDiagnostic(BaseModel):
    reason_code: str = Field(..., description="Machine-readable error/diagnostic code (e.g. NEGATIVE_FREE_CASH_FLOW)")
    explanation: str = Field(..., description="Human-readable explanation of why the valuation failed")
    triggering_metrics: Dict[str, Optional[Union[float, List[float]]]] = Field(..., description="Dict of metrics that triggered the diagnostic")
    analytical_implication: str = Field(..., description="Analytical/investment implication of the failure condition")

class ValuationResult(BaseModel):
    intrinsic_value: Optional[float] = Field(None, description="Computed intrinsic value per share, or null if infeasible")
    methodology_name: str
    assumptions: List[str]
    baseline_metrics: Dict[str, Optional[Union[float, List[float]]]]
    peer_comparison: List[PeerCompany]
    diagnostic: Optional[ValuationDiagnostic] = Field(None, description="Populated only when intrinsic_value is null")
    heuristic_vs_peers: Optional[Literal["undervalued", "overvalued", "fairly_valued", "ERROR"]] = None
    heuristic_vs_baseline: Optional[Literal["undervalued", "overvalued", "fairly_valued", "ERROR"]] = None
    fallback_applied: bool
    metadata: Dict[str, Union[str, float, int, bool, None]]
    adjustment_result: Optional["AdjustmentEngineResult"] = None


class RuleCondition(BaseModel):
    field: str
    operator: Literal["eq", "neq", "lt", "lte", "gt", "gte", "in", "not_in", "exists", "missing"]
    value: Optional[Union[str, float, List[str], List[float]]] = None
    boundary_policy: Optional[Literal["inclusive", "exclusive"]] = None

class RuleAction(BaseModel):
    parameter: str
    action_type: Literal["set", "multiply", "add", "clamp", "disable_methodology", "set_weight"]
    value: Union[str, float, bool, List[float]]
    reason: str

class AdjustmentRule(BaseModel):
    rule_id: str
    description: str
    affected_methodology: str
    conditions: List[RuleCondition]
    actions: List[RuleAction]
    priority: int = 0
    enabled: bool = True

class CompanyEconomicProfile(BaseModel):
    ticker: str
    as_of_source: str
    growth_profile: Literal["declining", "stable", "growth", "high_growth"]
    cash_flow_profile: Literal["negative", "volatile", "normalized_positive", "stable_positive"]
    dividend_profile: Literal["none", "inconsistent", "stable", "high_yield"]
    profitability_profile: Literal["distressed", "low_return", "profitable", "high_return"]
    balance_sheet_profile: Literal["negative_equity", "levered", "balanced", "net_cash"]
    input_metrics: Dict[str, Optional[Union[float, List[float]]]]
    classification_reasons: List[str]

class AdjustmentRuleTrace(BaseModel):
    rule_id: str
    affected_methodology: str
    triggered: bool
    triggering_metrics: Dict[str, Optional[Union[float, List[float], str]]]
    applied_actions: List[RuleAction]
    explanation: str

class MethodologyConfiguration(BaseModel):
    methodology_name: str
    eligible_by_isic: bool
    economically_applicable: bool
    base_parameters: Dict[str, Union[float, str, bool]]
    final_parameters: Dict[str, Union[float, str, bool]]
    applied_adjustments: List[AdjustmentRuleTrace]
    diagnostic: Optional[ValuationDiagnostic] = None

class AdjustmentEngineResult(BaseModel):
    ticker: str
    isic_code: Optional[str]
    profile: CompanyEconomicProfile
    methodology_configurations: List[MethodologyConfiguration]
    ruleset_version: str
