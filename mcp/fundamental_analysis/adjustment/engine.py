import copy
from typing import Dict, List, Optional, Tuple, Union
from core.schemas import (
    CompanyEconomicProfile,
    RuleCondition,
    RuleAction,
    AdjustmentRule,
    AdjustmentRuleTrace,
    MethodologyConfiguration,
    AdjustmentEngineResult,
    ValuationDiagnostic
)
from adjustment.rules import load_thresholds_and_rules

REQUIRED_METRIC_KEYS = [
    "current_price", "total_revenue", "revenue_growth", "free_cash_flow",
    "operating_cash_flow", "free_cash_flow_history", "operating_cash_flow_history",
    "capex_history", "dividend_rate", "dividend_yield", "payout_ratio",
    "return_on_equity", "operating_margins", "profit_margins", "book_value",
    "total_debt", "total_cash", "shares_outstanding", "beta", "currency", "ebitda"
]

UNDERLYING_METRICS_MAP = {
    "growth_profile": ["revenue_growth"],
    "cash_flow_profile": ["free_cash_flow", "free_cash_flow_history"],
    "dividend_profile": ["dividend_yield"],
    "profitability_profile": ["return_on_equity"],
    "balance_sheet_profile": ["book_value"],
}

def extract_metrics(financial_data: dict) -> dict:
    """Safely extracts and cleans required metrics from raw financial data."""
    extracted = {}
    for key in REQUIRED_METRIC_KEYS:
        val = financial_data.get(key)
        if val is None:
            if key in ("free_cash_flow_history", "operating_cash_flow_history", "capex_history"):
                extracted[key] = []
            else:
                extracted[key] = None
        else:
            if key in ("free_cash_flow_history", "operating_cash_flow_history", "capex_history"):
                extracted[key] = [float(x) for x in val if x is not None]
            elif key == "currency":
                extracted[key] = str(val)
            else:
                extracted[key] = float(val)
    return extracted

def classify_growth(metrics: dict, thresholds: dict, reasons: list) -> str:
    """Derives growth profile classification from metrics and thresholds."""
    growth_cfg = thresholds.get("growth", {})
    rev_growth = metrics.get("revenue_growth")
    
    if rev_growth is None:
        reasons.append("revenue_growth is missing, defaulting to stable growth")
        return "stable"
        
    high_growth_cagr = growth_cfg.get("high_growth_cagr", 0.20)
    growth_cagr = growth_cfg.get("growth_cagr", 0.10)
    stable_cagr = growth_cfg.get("stable_cagr", 0.02)
    
    if rev_growth >= high_growth_cagr:
        reasons.append(f"revenue_growth ({rev_growth:.1%}) is above high growth threshold ({high_growth_cagr:.1%})")
        return "high_growth"
    elif rev_growth >= growth_cagr:
        reasons.append(f"revenue_growth ({rev_growth:.1%}) is above growth threshold ({growth_cagr:.1%})")
        return "growth"
    elif rev_growth >= stable_cagr:
        reasons.append(f"revenue_growth ({rev_growth:.1%}) is above stable growth threshold ({stable_cagr:.1%})")
        return "stable"
    else:
        reasons.append(f"revenue_growth ({rev_growth:.1%}) indicates declining or low growth")
        return "declining"

def classify_cash_flow(metrics: dict, thresholds: dict, reasons: list) -> str:
    """Derives cash flow profile classification from metrics and thresholds."""
    fcf = metrics.get("free_cash_flow")
    fcf_history = metrics.get("free_cash_flow_history", [])
    
    if fcf is None or (fcf <= 0 and not fcf_history):
        reasons.append("free cash flow is negative or missing without history")
        return "negative"
        
    pos_count = sum(1 for x in fcf_history if x > 0)
    total_count = len(fcf_history)
    
    if total_count >= 3 and pos_count == total_count:
        reasons.append("free cash flow history is consistently positive over at least 3 years")
        return "stable_positive"
    elif pos_count >= total_count / 2 and total_count > 0:
        reasons.append("free cash flow is positive on average but exhibits historical volatility")
        return "volatile"
    elif fcf > 0:
        reasons.append("free cash flow is currently positive, but history is limited or volatile")
        return "normalized_positive"
    else:
        reasons.append("free cash flow is negative or predominantly negative in historical data")
        return "negative"

def classify_dividend(metrics: dict, thresholds: dict, reasons: list) -> str:
    """Derives dividend profile classification from metrics and thresholds."""
    div_yield = metrics.get("dividend_yield")
    div_cfg = thresholds.get("dividend", {})
    
    if div_yield is None or div_yield <= 0:
        reasons.append("dividend yield is zero or not paid")
        return "none"
        
    high_yield = div_cfg.get("high_yield", 0.05)
    stable_yield = div_cfg.get("stable_yield", 0.015)
    
    if div_yield >= high_yield:
        reasons.append(f"dividend yield ({div_yield:.1%}) is high yield (>= {high_yield:.1%})")
        return "high_yield"
    elif div_yield >= stable_yield:
        reasons.append(f"dividend yield ({div_yield:.1%}) is stable dividend yield (>= {stable_yield:.1%})")
        return "stable"
    else:
        reasons.append(f"dividend yield ({div_yield:.1%}) is inconsistent or low yield")
        return "inconsistent"

def classify_profitability(metrics: dict, thresholds: dict, reasons: list) -> str:
    """Derives profitability profile classification from metrics and thresholds."""
    roe = metrics.get("return_on_equity")
    prof_cfg = thresholds.get("profitability", {})
    
    if roe is None or roe < prof_cfg.get("distressed_roe", 0.0):
        reasons.append(f"return on equity ({roe}) is negative or distressed")
        return "distressed"
        
    high_return = prof_cfg.get("high_return_roe", 0.20)
    profitable = prof_cfg.get("profitable_roe", 0.05)
    
    if roe >= high_return:
        reasons.append(f"return on equity ({roe:.1%}) indicates high profitability return")
        return "high_return"
    elif roe >= profitable:
        reasons.append(f"return on equity ({roe:.1%}) is profitable")
        return "profitable"
    else:
        reasons.append(f"return on equity ({roe:.1%}) indicates low return profitability")
        return "low_return"

def classify_balance_sheet(metrics: dict, thresholds: dict, reasons: list) -> str:
    """Derives balance sheet profile classification from metrics and thresholds."""
    book_value = metrics.get("book_value")
    if book_value is None or book_value < 0:
        reasons.append("book value is negative, indicating negative equity")
        return "negative_equity"
        
    debt = metrics.get("total_debt") or 0.0
    cash = metrics.get("total_cash") or 0.0
    ebitda = metrics.get("ebitda")
    
    if debt == 0 or cash > debt:
        reasons.append("company holds net cash or zero debt")
        return "net_cash"
        
    bs_cfg = thresholds.get("balance_sheet", {})
    levered_threshold = bs_cfg.get("levered_debt_to_ebitda", 3.5)
    
    if ebitda and ebitda > 0 and (debt / ebitda) > levered_threshold:
        reasons.append(f"debt to EBITDA ratio ({debt / ebitda:.2f}) indicates highly levered balance sheet")
        return "levered"
        
    reasons.append("balance sheet indicates moderate, balanced leverage")
    return "balanced"

def derive_economic_profile(ticker: str, metrics: dict, thresholds: dict) -> CompanyEconomicProfile:
    """Calculates all classifications to construct the CompanyEconomicProfile."""
    reasons = []
    growth = classify_growth(metrics, thresholds, reasons)
    cash_flow = classify_cash_flow(metrics, thresholds, reasons)
    dividend = classify_dividend(metrics, thresholds, reasons)
    profitability = classify_profitability(metrics, thresholds, reasons)
    balance_sheet = classify_balance_sheet(metrics, thresholds, reasons)
    
    clean_metrics = {}
    for k in ("revenue_growth", "dividend_yield", "free_cash_flow_history", "book_value", "return_on_equity", "free_cash_flow", "ebitda"):
        clean_metrics[k] = metrics.get(k)
        
    return CompanyEconomicProfile(
        ticker=ticker,
        as_of_source="yfinance",
        growth_profile=growth,
        cash_flow_profile=cash_flow,
        dividend_profile=dividend,
        profitability_profile=profitability,
        balance_sheet_profile=balance_sheet,
        input_metrics=clean_metrics,
        classification_reasons=reasons
    )

def get_field_value(field: str, profile: CompanyEconomicProfile) -> Optional[Union[str, float, List[float]]]:
    """Helper to fetch field values from a CompanyEconomicProfile or its input metrics."""
    parts = field.split(".")
    if len(parts) == 2 and parts[0] == "profile":
        return getattr(profile, parts[1], None)
    return profile.input_metrics.get(field)

def compare_bounds(op: str, val: Union[float, int], field_val: Union[float, int], inclusive: bool) -> bool:
    """Helper to evaluate boundary conditions deterministically."""
    if op in ("lt", "lte"):
        return field_val <= val if (inclusive or op == "lte") else field_val < val
    if op in ("gt", "gte"):
        return field_val >= val if (inclusive or op == "gte") else field_val > val
    return False

def evaluate_condition(cond: RuleCondition, profile: CompanyEconomicProfile) -> bool:
    """Evaluates a single condition predicate against a profile."""
    field_val = get_field_value(cond.field, profile)
    if cond.operator == "exists":
        return field_val is not None
    if cond.operator == "missing":
        return field_val is None
    if field_val is None:
        return False
        
    op = cond.operator
    val = cond.value
    if op == "eq":
        return field_val == val
    if op == "neq":
        return field_val != val
    if op in ("lt", "lte", "gt", "gte"):
        return compare_bounds(op, val, field_val, cond.boundary_policy == "inclusive")
    if op == "in":
        return field_val in val
    if op == "not_in":
        return field_val not in val
    return False

def make_diagnostic(reason_code: str, ticker: str, profile: CompanyEconomicProfile) -> ValuationDiagnostic:
    """Helper to create a standard ValuationDiagnostic for inapplicable models."""
    if reason_code == "ECONOMICALLY_INAPPLICABLE_NO_DIVIDENDS":
        explanation = f"{ticker} has no dividend history or yield, making DDM invalid."
        trigger = {"dividend_yield": profile.input_metrics.get("dividend_yield")}
    elif reason_code == "ECONOMICALLY_INAPPLICABLE_DISTRESSED_CASH_FLOW":
        explanation = f"{ticker} exhibits negative or distressed cash flow history, making DCF invalid."
        trigger = {"free_cash_flow": profile.input_metrics.get("free_cash_flow")}
    elif reason_code == "ECONOMICALLY_INAPPLICABLE_NEGATIVE_EQUITY":
        explanation = f"{ticker} exhibits negative book value, making equity-based RIM/Asset models invalid."
        trigger = {"book_value": profile.input_metrics.get("book_value")}
    else:
        explanation = f"{ticker} is inapplicable for this methodology."
        trigger = {}
        
    return ValuationDiagnostic(
        reason_code=reason_code,
        explanation=explanation,
        triggering_metrics=trigger,
        analytical_implication="Methodology configuration marked economically inapplicable based on derived economic profile."
    )

def get_base_params(methodology_name: str) -> dict:
    """Gets the default baseline configuration for a methodology."""
    if methodology_name == "DCF":
        return {"forecast_horizon": 5, "use_normalized_fcf": False, "wacc_sensitivity_range": 0.02, "terminal_growth": 0.02, "methodology_weight": 1.0}
    elif methodology_name == "DDM":
        return {"terminal_growth": 0.025, "methodology_weight": 0.5}
    return {"methodology_weight": 1.0}

def apply_rule_action(action: RuleAction, final_params: dict) -> Tuple[bool, Optional[str]]:
    """Modifies the target parameters dict based on rule action type."""
    param = action.parameter
    atype = action.action_type
    val = action.value
    
    economically_applicable = True
    disable_reason = None
    
    if atype in ("set", "set_weight"):
        final_params[param] = val
    elif atype == "add":
        final_params[param] = final_params.get(param, 0.0) + val
    elif atype == "multiply":
        final_params[param] = final_params.get(param, 1.0) * val
    elif atype == "clamp":
        curr = final_params.get(param, 0.0)
        final_params[param] = max(val[0], min(val[1], curr))
    elif atype == "disable_methodology":
        economically_applicable = False
        disable_reason = str(val)
        
    return economically_applicable, disable_reason

def check_rule_conditions(rule: AdjustmentRule, profile: CompanyEconomicProfile) -> Tuple[bool, dict]:
    """Helper to evaluate all conditions for a rule and build triggering metrics map."""
    triggering_metrics = {}
    for cond in rule.conditions:
        if not evaluate_condition(cond, profile):
            return False, {}
            
        parts = cond.field.split(".")
        name = parts[1] if len(parts) == 2 else cond.field
        if name in UNDERLYING_METRICS_MAP:
            for und in UNDERLYING_METRICS_MAP[name]:
                if und in profile.input_metrics:
                    triggering_metrics[und] = profile.input_metrics[und]
        else:
            trigger_val = getattr(profile, name, None) or profile.input_metrics.get(cond.field)
            triggering_metrics[name] = trigger_val
            
    return True, triggering_metrics

def evaluate_and_apply_rules(
    method_name: str,
    rules: List[AdjustmentRule],
    profile: CompanyEconomicProfile,
    base_params: dict
) -> Tuple[dict, List[AdjustmentRuleTrace], bool, Optional[str]]:
    """Evaluates all rules for a methodology, applying modifications and logging traces."""
    final_params = copy.deepcopy(base_params)
    traces = []
    economically_applicable = True
    disable_reason = None
    
    for rule in rules:
        if not rule.enabled or rule.affected_methodology not in (method_name, "ALL"):
            continue
            
        triggered, metrics = check_rule_conditions(rule, profile)
        if triggered:
            applied_actions = []
            for action in rule.actions:
                app, reason = apply_rule_action(action, final_params)
                if not app:
                    economically_applicable = False
                    disable_reason = reason
                applied_actions.append(action)
                
            traces.append(AdjustmentRuleTrace(
                rule_id=rule.rule_id,
                affected_methodology=rule.affected_methodology,
                triggered=True,
                triggering_metrics=metrics,
                applied_actions=applied_actions,
                explanation=rule.description
            ))
            
    traces.sort(key=lambda x: x.rule_id)
    return final_params, traces, economically_applicable, disable_reason

def build_adjustment_result(
    ticker: str,
    isic_code: Optional[str],
    financial_data: dict,
    eligible_methodologies: List[str]
) -> AdjustmentEngineResult:
    """Main function called by fundamental analysis service to perform dynamic adjustment."""
    thresholds, rules = load_thresholds_and_rules()
    metrics = extract_metrics(financial_data)
    profile = derive_economic_profile(ticker, metrics, thresholds)
    
    configs = []
    for mname in eligible_methodologies:
        base_params = get_base_params(mname)
        final_params, traces, applicable, reason_code = evaluate_and_apply_rules(mname, rules, profile, base_params)
        
        diag = None
        if not applicable and reason_code:
            diag = make_diagnostic(reason_code, ticker, profile)
            
        configs.append(MethodologyConfiguration(
            methodology_name=mname,
            eligible_by_isic=True,
            economically_applicable=applicable,
            base_parameters=base_params,
            final_parameters=final_params,
            applied_adjustments=traces,
            diagnostic=diag
        ))
        
    configs.sort(key=lambda x: x.methodology_name)
    
    return AdjustmentEngineResult(
        ticker=ticker,
        isic_code=isic_code,
        profile=profile,
        methodology_configurations=configs,
        ruleset_version=str(thresholds.get("version", "2026-06-04"))
    )
