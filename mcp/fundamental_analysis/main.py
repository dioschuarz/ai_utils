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

@mcp.tool()
async def execute_valuation(
    ticker: str,
    gics_sub_industry_id: str = None,
    specific_methodology: str = None,
) -> str:
    """
    Executes financial valuation(s) for a given stock ticker, automatically
    resolving GICS classification and applying the most relevant methodologies.
    """
    logger.info(f"Executing valuation for ticker: {ticker}")
    
    # 1. Initialize yfinance client
    client = YFinanceClient()
    
    # 2. Fetch GICS classification
    gics = await client.get_gics_classification(ticker)
    resolved_sub_industry = gics_sub_industry_id or gics["sub_industry_id"]
    
    # 3. Fetch financial data
    financial_data = await client.get_financial_data(ticker)
    
    # 4. Fetch peers
    peers = await client.get_peers(ticker, resolved_sub_industry)
    
    # 5. Build request schema
    request = ValuationRequest(
        ticker=ticker,
        gics_sector=gics["sector"],
        gics_industry_group=gics["industry_group"],
        gics_industry=gics["industry"],
        gics_sub_industry=gics["sub_industry"],
        gics_sub_industry_id=resolved_sub_industry,
        specific_methodology=specific_methodology
    )
    
    # 6. Execute calculation (GICS-aware dispatcher)
    dispatcher = ValuationDispatcher()
    methodology = dispatcher.select_methodology(request)
    result = methodology.calculate(request, financial_data, peers)
    
    # 7. Perform heuristic calculations (T014)
    current_price = financial_data.get("current_price", 0.0)
    intrinsic_value = result.intrinsic_value
    
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
