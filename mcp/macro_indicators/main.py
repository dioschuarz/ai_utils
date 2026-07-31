import os
import logging
import asyncio
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastmcp import FastMCP
from contextlib import asynccontextmanager

from schemas import MacroIndicatorsResponse, MacroComponents
from cache import MacroCacheManager
from pipeline import run_macro_pipeline
from database import save_indicators_to_db, get_indicators_from_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Resolve backup file path dynamically (service directory vs project root context)
backup_file = "production_macro_indicators.json"
if not os.path.exists(backup_file) and os.path.exists("mcp/macro_indicators/production_macro_indicators.json"):
    backup_file = "mcp/macro_indicators/production_macro_indicators.json"

# In-memory cache manager with 24-hour TTL
cache_manager = MacroCacheManager(ttl_seconds=86400, backup_file=backup_file)

# Hardcoded fallback default values if both external APIs and cache backup are unavailable
FALLBACK_DEFAULTS = {
    "US": MacroIndicatorsResponse(
        country="USA",
        currency="USD",
        market_risk_premium=0.06,  # 6.0% ERP default
        components=MacroComponents(
            risk_free_rate_rf=0.045,  # 4.5% US RF default
            market_credit_spread=0.015,
            capital_structure_multiplier=2.6,
            inflation_yoy=0.035
        ),
        reference_period="2026-06-01"
    ),
    "BR": MacroIndicatorsResponse(
        country="Brazil",
        currency="BRL",
        market_risk_premium=0.0836,  # Default Brazil ERP
        components=MacroComponents(
            risk_free_rate_rf=0.105,  # 10.5% SELIC default
            dynamic_country_risk_premium_crp=0.0304,
            usd_brl_1y_annualized_vol=0.15,
            sp500_1y_annualized_vol=0.12,
            pure_sovereign_risk_ratio=1.2,
            inflation_yoy=0.045,
            derived_inflation_differential=1.01
        ),
        reference_period="2026-06-01"
    )
}

async def run_daily_sync():
    """Runs calculation and saves to memory + Supabase. Implements retry with exponential backoff on API failures."""
    fred_api_key = os.getenv("FRED_API_KEY")
    if not fred_api_key:
        logger.warning("FRED_API_KEY not found in environment. Skipping API calculation sync, relying on Supabase/backup.")
        return

    max_attempts = 5
    backoff = 5.0
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"Executing daily macro sync attempt {attempt}/{max_attempts}...")
            # run_macro_pipeline makes network requests
            results = run_macro_pipeline(fred_api_key)
            for c_key, c_val in results.items():
                # Set in local cache
                cache_manager.set(c_key, c_val)
                # Save to Supabase
                save_indicators_to_db(
                    country_code=c_key,
                    currency=c_val.currency,
                    mrp=c_val.market_risk_premium,
                    rf=c_val.components.risk_free_rate_rf,
                    inflation=c_val.components.inflation_yoy,
                    crp=c_val.components.dynamic_country_risk_premium_crp,
                    components=c_val.components.model_dump(),
                    reference_period=c_val.reference_period
                )
            logger.info("Daily macro indicators sync completed successfully.")
            return
        except Exception as e:
            logger.error(f"Daily macro indicators sync failed on attempt {attempt}: {e}")
            if attempt == max_attempts:
                logger.critical("Daily macro sync failed completely. Will retry in 24 hours.")
                break
            await asyncio.sleep(backoff)
            backoff *= 2.0

async def daily_sync_loop():
    """Loops indefinitely, running the calculations and saving to DB/cache once a day."""
    # First sync on boot
    await run_daily_sync()
    while True:
        # Sleep for 24 hours (86400 seconds)
        await asyncio.sleep(86400)
        await run_daily_sync()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background task for daily sync
    sync_task = asyncio.create_task(daily_sync_loop())
    logger.info("Background daily sync loop started.")
    yield
    # Clean up background task on shutdown
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        logger.info("Background daily sync loop stopped.")

app = FastAPI(
    title="Alpha-Guardian Macro Indicators Service",
    description="Dual-protocol REST + MCP service for dynamic US and Brazil macroeconomic data.",
    lifespan=lifespan
)

mcp = FastMCP(
    "Alpha-Guardian-Macro-Indicators",
)

def resolve_indicators(country: str) -> MacroIndicatorsResponse:
    """Resolve indicators by checking local cache, database, or fallback file."""
    key = country.upper()
    if key == "USA":
        key = "US"
    elif key == "BRAZIL":
        key = "BR"
        
    if key not in ["US", "BR"]:
        raise HTTPException(status_code=400, detail=f"Unsupported country code: {country}. Supported: US, BR")

    # 1. Try memory cache hit (valid TTL)
    cached = cache_manager.get(key)
    if cached:
        return cached

    # 2. Try Supabase database fallback
    try:
        db_indicators = get_indicators_from_db(key)
        if db_indicators:
            logger.info(f"Database cache hit for {key}")
            components = db_indicators["components"]
            comp_model = MacroComponents(
                risk_free_rate_rf=db_indicators["risk_free_rate_rf"],
                market_credit_spread=components.get("market_credit_spread"),
                capital_structure_multiplier=components.get("capital_structure_multiplier"),
                inflation_yoy=db_indicators["inflation_yoy"],
                dynamic_country_risk_premium_crp=db_indicators["dynamic_country_risk_premium_crp"],
                usd_brl_1y_annualized_vol=components.get("usd_brl_1y_annualized_vol"),
                sp500_1y_annualized_vol=components.get("sp500_1y_annualized_vol"),
                pure_sovereign_risk_ratio=components.get("pure_sovereign_risk_ratio"),
                derived_inflation_differential=components.get("derived_inflation_differential")
            )
            data_resp = MacroIndicatorsResponse(
                country=db_indicators["country"],
                currency=db_indicators["currency"],
                market_risk_premium=db_indicators["market_risk_premium"],
                components=comp_model,
                reference_period=db_indicators["reference_period"]
            )
            cache_manager.set(key, data_resp)
            
            # Check 90 day age check
            updated_at = db_indicators["updated_at"]
            from datetime import datetime, timezone
            age_days = (datetime.now(timezone.utc) - updated_at).days
            if age_days > 90:
                logger.critical(f"UNACCEPTABLE: Macro indicators in database for {key} are {age_days} days old (older than 90 days)!")
            elif age_days > 30:
                logger.warning(f"Macro indicators in database for {key} are stale: {age_days} days old.")
                
            return data_resp
    except Exception as e:
        logger.error(f"Error querying indicators from Supabase: {e}")

    # 3. Try stale local file cache fallback
    stale_entry = cache_manager.cache.get(key)
    if stale_entry:
        logger.warning(f"Returning stale local file cache fallback for {key}")
        return stale_entry.data

    # 4. Critical fallback to database seeding with default values
    logger.critical(f"No DB record or file available for {key}. Seeding database with defaults.")
    default_data = FALLBACK_DEFAULTS[key]
    cache_manager.set(key, default_data)
    save_indicators_to_db(
        country_code=key,
        currency=default_data.currency,
        mrp=default_data.market_risk_premium,
        rf=default_data.components.risk_free_rate_rf,
        inflation=default_data.components.inflation_yoy,
        crp=default_data.components.dynamic_country_risk_premium_crp,
        components=default_data.components.model_dump(),
        reference_period=default_data.reference_period
    )
    return default_data

# ==============================================================================
# REST Endpoints
# ==============================================================================

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.get("/indicators/{country}")
async def get_indicators_endpoint(country: str):
    """Retrieve macroeconomic indicators for US or BR."""
    return resolve_indicators(country)

@app.get("/indicators")
async def get_all_indicators_endpoint():
    """Retrieve macroeconomic indicators for all supported countries."""
    return {
        "US": resolve_indicators("US"),
        "BR": resolve_indicators("BR")
    }

# ==============================================================================
# FastMCP Tools
# ==============================================================================

@mcp.tool()
async def get_macro_indicators(country: str) -> str:
    """
    Returns macroeconomic indicators (risk-free rate, market risk premium,
    inflation) for a country code ('US' or 'BR').
    """
    try:
        data = resolve_indicators(country)
        return data.model_dump_json(indent=2)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def get_all_macro_indicators() -> str:
    """
    Returns macroeconomic indicators for all supported countries.
    """
    try:
        data = {
            "US": resolve_indicators("US"),
            "BR": resolve_indicators("BR")
        }
        import json
        return json.dumps({k: v.model_dump() for k, v in data.items()}, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    """Health check endpoint."""
    return JSONResponse({"status": "healthy"})

if __name__ == "__main__":
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))
    mcp.run(
        transport="http",
        host=host,
        port=port,
        stateless_http=True,
        json_response=True,
    )
