import logging
from fastmcp import FastMCP
from starlette.responses import JSONResponse
from core.config import get_settings
from core.schemas import ValuationRequest, ValuationResult
from providers.yfinance_client import YFinanceClient
from core.dispatcher import ValuationDispatcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

mcp = FastMCP(
    "Alpha-Guardian-Fundamental-Analyst",
)

class ValuationIndependenceGuard:
    """Checks compiled results for duplication and hardcoded cloning errors."""
    @staticmethod
    def validate_independence(results: list) -> list:
        non_error_vals = []
        for r in results:
            val = r.intrinsic_value if hasattr(r, "intrinsic_value") else r.get("intrinsic_value")
            if val is not None and val != "ERROR":
                non_error_vals.append(val)
        if len(non_error_vals) != len(set(non_error_vals)) and len(non_error_vals) > 1:
            logger.warning("UNRELIABLE VALUATION: Multiple methodologies returned the exact same non-error intrinsic value!")
            for r in results:
                if hasattr(r, "metadata"):
                    # Pydantic metadata dict can be modified
                    r.metadata["independence_status"] = "WARNING: Potential replication conflict detected"
                elif isinstance(r, dict):
                    r.setdefault("metadata", {})["independence_status"] = "WARNING: Potential replication conflict detected"
        return results

@mcp.tool()
async def get_isic_mappings() -> str:
    """
    Returns the complete ISIC Rev 5 taxonomy mappings dict to let taxonomy_solver nodes select valid IDs.
    """
    from core.mappings import ISICCache
    import json
    cache = ISICCache()
    return json.dumps(cache.get_all_rows(), indent=2)

@mcp.tool()
async def get_gics_mappings() -> str:
    """Deprecated compatibility wrapper for get_isic_mappings."""
    return await get_isic_mappings()

@mcp.tool()
async def get_isic_suggestions(invalid_code: str, query: str = None) -> str:
    """
    Returns top 3-5 closest valid matches for suggestions, formatting them to return both the isic_code and its class_description.
    """
    from core.mappings import get_isic_suggestions
    import json
    suggestions = get_isic_suggestions(invalid_code, query)
    return json.dumps(suggestions, indent=2)


@mcp.tool()
async def execute_valuation(
    ticker: str,
    isic_code: str = None,
    specific_methodology: str = None,
    # Compatibility parameter
    gics_sub_industry_id: str = None,
) -> str:
    """
    Executes financial valuation(s) for a given stock ticker, automatically
    resolving ISIC classification and applying the most relevant methodologies.
    """
    resolved_isic = isic_code or gics_sub_industry_id
    
    # Extract user context for logging and multi-tenant tracking
    try:
        from backend.api.dependencies import current_user_id
        active_user_id = current_user_id.get()
        logger.info(f"Executing valuation for ticker: {ticker}, ISIC: {resolved_isic} (User ID: {active_user_id})")
    except Exception as e:
        active_user_id = None
        logger.info(f"Executing valuation for ticker: {ticker}, ISIC: {resolved_isic} (No active user session: {e})")
    
    # 1. Initialize yfinance client
    client = YFinanceClient()
    
    # 2. Fetch ISIC classification
    if resolved_isic:
        from core.mappings import ISICCache
        cache = ISICCache()
        try:
            row = cache.get_row(resolved_isic)
            classification = {
                "sector": row.get("division_description"),
                "industry": row.get("class_description"),
                "isic_division": row.get("division_description"),
                "isic_group": row.get("group_description"),
                "isic_class": row.get("class_description"),
                "isic_code": resolved_isic
            }
        except Exception:
            classification = await client.get_isic_classification(ticker)
    else:
        classification = await client.get_isic_classification(ticker)
        
    resolved_isic = classification["isic_code"]
    
    # 3. Fetch financial data
    financial_data = await client.get_financial_data(ticker)
    
    # 4. Fetch peers
    peers = await client.get_peers(ticker, resolved_isic)
    
    # 5. Build request schema
    request = ValuationRequest(
        ticker=ticker,
        isic_code=resolved_isic,
        isic_division=classification.get("isic_division"),
        isic_group=classification.get("isic_group"),
        isic_class=classification.get("isic_class"),
        specific_methodology=specific_methodology,
        # backward compatibility
        gics_sub_industry_id=resolved_isic,
        gics_sub_industry=classification.get("isic_class"),
        gics_sector=classification.get("sector"),
        gics_industry=classification.get("industry")
    )
    
    # 6. Execute calculation (ISIC-aware dispatcher and dynamic adjustment engine)
    dispatcher = ValuationDispatcher()
    
    from adjustment.engine import build_adjustment_result
    eligible_methodologies = dispatcher.get_available_methodologies(resolved_isic)
    if specific_methodology:
        eligible_methodologies = [specific_methodology]
        
    adj_result = build_adjustment_result(ticker, resolved_isic, financial_data, eligible_methodologies)
    methodology = dispatcher.select_methodology(request)
    
    if not methodology:
        # Unsupported methodology
        from core.schemas import ValuationDiagnostic
        result = ValuationResult(
            intrinsic_value=None,
            methodology_name=specific_methodology or "Unknown",
            assumptions=[f"Requested methodology {specific_methodology} is not supported by this service."],
            baseline_metrics={},
            peer_comparison=[],
            diagnostic=ValuationDiagnostic(
                reason_code="UNSUPPORTED_METHODOLOGY",
                explanation=f"Requested methodology {specific_methodology} is not supported by this service.",
                triggering_metrics={},
                analytical_implication="The fundamental analysis service does not contain an engine for the requested methodology name."
            ),
            fallback_applied=True,
            metadata={}
        )
    else:
        # Find the configuration for this methodology
        m_config = next((c for c in adj_result.methodology_configurations if c.methodology_name == methodology.name), None)
        
        if m_config and not m_config.economically_applicable:
            # Economically inapplicable - return diagnostic result without calculating formula
            diag = m_config.diagnostic
            result = ValuationResult(
                intrinsic_value=None,
                methodology_name=methodology.name,
                assumptions=[f"Valuation failed: {diag.explanation}"],
                baseline_metrics={},
                peer_comparison=[],
                diagnostic=diag,
                fallback_applied=True,
                metadata={}
            )
        else:
            if m_config:
                request.adjustment_params = m_config.final_parameters
            result = methodology.calculate(request, financial_data, peers)
            
        result.adjustment_result = adj_result
        if m_config:
            import json
            result.metadata["final_parameters"] = json.dumps(m_config.final_parameters)
            result.metadata["applied_adjustments"] = json.dumps([t.model_dump() for t in m_config.applied_adjustments])
            result.metadata["ruleset_version"] = adj_result.ruleset_version
    
    # 7. Perform heuristic calculations
    current_price = financial_data.get("current_price", 0.0)
    intrinsic_value = result.intrinsic_value
    
    if intrinsic_value is None:
        result.heuristic_vs_baseline = None
        result.heuristic_vs_peers = None
    else:
        # Margin of safety / baseline comparison
        if intrinsic_value > 0 and current_price > 0:
            mos_pct = ((intrinsic_value - current_price) / intrinsic_value) * 100
            if mos_pct > 20:
                result.heuristic_vs_baseline = "undervalued"
            elif mos_pct < -10:
                result.heuristic_vs_baseline = "overvalued"
            else:
                result.heuristic_vs_baseline = "fairly_valued"
                
        # Peer comparison heuristic (compare target P/E with average peer P/E if available)
        target_eps = financial_data.get("eps", 0.0)
        if target_eps > 0 and current_price > 0:
            target_pe_multiple = current_price / target_eps
            peer_pes = [p.multiples["P/E"] for p in result.peer_comparison if p.multiples.get("P/E")]
            if peer_pes:
                avg_peer_pe = sum(peer_pes) / len(peer_pes)
                if target_pe_multiple < avg_peer_pe * 0.9:
                    result.heuristic_vs_peers = "undervalued"
                elif target_pe_multiple > avg_peer_pe * 1.1:
                    result.heuristic_vs_peers = "overvalued"
                else:
                    result.heuristic_vs_peers = "fairly_valued"
                
    return result.model_dump_json(indent=2)

@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    """Health check endpoint."""
    return JSONResponse({"status": "healthy"})

if __name__ == "__main__":
    mcp.run(
        transport="http",
        host=settings.mcp_host,
        port=settings.mcp_port,
        stateless_http=True,
        json_response=True,
    )
