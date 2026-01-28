print("DEBUG: IMPORTING MODULES...")
import asyncio
import json
import logging
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from mcp.server.fastmcp import FastMCP
from typing import Dict, Any, Optional
from .config import get_settings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# NOTE: Langfuse tracing is handled by the CLIENT (mcp_client.py)
# We do NOT use @observe here to avoid duplicate traces.
# The client's @observe(as_type="tool") already creates spans within the LangGraph trace.

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Load settings
settings = get_settings()

# Initialize FastMCP Server
mcp = FastMCP(
    "Alpha-Guardian-Technical-Analyst",
    host=settings.mcp_host,
    port=settings.mcp_port
)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    before_sleep=lambda retry_state: logger.warning(f"Retrying fetch data due to error: {retry_state.outcome.exception()}")
)
async def fetch_history_async(ticker: str, period: str = "5y") -> pd.DataFrame:
    """
    Converte a chamada bloqueante do yfinance em assíncrona
    usando um executor de thread.
    Includes robust retry logic for API stability.
    """
    def get_data():
        try:
            stock = yf.Ticker(ticker)
            # Ensure we have data
            df = stock.history(period=period)
            
            if df is None or df.empty:
                raise ValueError(f"Ticker {ticker} not found or no data available (period={period}).")
            return df
        except TypeError as e:
            # Catch known yfinance issue: 'NoneType' object is not subscriptable
            if "'NoneType' object is not subscriptable" in str(e):
                logger.warning(f"Hit yfinance NoneType bug for {ticker} (period={period}).")
                raise ValueError(f"yfinance internal error (NoneType bug) for {ticker}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            raise

    # Executa a chamada síncrona em uma thread separada para não travar o loop
    return await asyncio.to_thread(get_data)

@mcp.tool()
async def analyze_ticker_full(ticker: str) -> str:
    """
    Performs a complete technical analysis (2 years) including:
    - Momentum (RSI, MACD)
    - Trend (SMA 50/200 - Golden Cross)
    - Volatility (Bollinger Bands)
    - Volume (OBV)
    
    Returns a JSON string with the analysis.
    """
    try:
        logger.info(f"Analyzing ticker: {ticker}")
        
        # Try progressive periods to handle Yahoo Finance API limitations
        # 2y is enough for SMA200 (~504 trading days)
        df = None
        periods_to_try = ["2y", "1y"]
        last_error = None
        
        for period in periods_to_try:
            try:
                df = await fetch_history_async(ticker, period=period)
                if df is not None and not df.empty:
                    logger.info(f"Successfully fetched data for {ticker} with period {period}")
                    break
            except Exception as e:
                last_error = e
                logger.warning(f"Failed to fetch {ticker} with period {period}: {e}")
                continue
        
        if df is None or df.empty:
            error_msg = str(last_error) if last_error else "No data available"
            return json.dumps({"error": f"No data available for {ticker}: {error_msg}"})
        
        # --- Processamento de Indicadores (Pandas-TA) ---
        # Momentum
        df.ta.rsi(length=14, append=True)
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        
        # Tendência e Volatilidade
        df.ta.sma(length=50, append=True)
        df.ta.sma(length=200, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        
        # Volume (Confirmação de tendência)
        df.ta.obv(append=True)

        # Extração da última linha para análise do estado atual
        if len(df) < 50: # Relaxed requirement significantly since we might fallback to 1y
             # But if we need SMA200, we need 200 bars.
             # If we only got 1y data (~252 bars), we are fine.
             # If we got less, SMA200 will be NaN.
             pass

        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Handle potential NaN values safely
        def safe_get(val, default=0):
            if val is None:
                return default
            return val if pd.notna(val) else default

        # --- Lógica de Sinais ---
        analysis = {
            "metadata": {
                "ticker": ticker,
                "last_close": round(float(last['Close']), 2),
                "timestamp": str(last.name)
            },
            "momentum": {
                "rsi": round(safe_get(last.get('RSI_14')), 2),
                "rsi_state": "Overbought" if safe_get(last.get('RSI_14')) > 70 else ("Oversold" if safe_get(last.get('RSI_14')) < 30 else "Neutral"),
                "macd_signal": "Bullish" if safe_get(last.get('MACD_12_26_9')) > safe_get(last.get('MACDs_12_26_9')) else "Bearish"
            },
            "trend": {
                "golden_cross": bool(safe_get(last.get('SMA_50')) > safe_get(last.get('SMA_200'))),
                "price_vs_sma50": "Above" if float(last['Close']) > safe_get(last.get('SMA_50')) else "Below",
                "bollinger_pos": "Upper" if float(last['Close']) > safe_get(last.get('BBU_20_2.0')) else ("Lower" if float(last['Close']) < safe_get(last.get('BBL_20_2.0')) else "Middle")
            },
            "volume_confirmation": {
                "obv_trend": "Increasing" if safe_get(last.get('OBV')) > safe_get(prev.get('OBV')) else "Decreasing",
                "volume_vs_avg": "High" if float(last['Volume']) > df['Volume'].tail(20).mean() else "Normal"
            }
        }

        return json.dumps(analysis, indent=2)

    except Exception as e:
        error_msg = str(e)
        if "RetryError" in type(e).__name__:
            try:
                # Extract the last exception from the retry wrapper
                error_msg = str(e.last_attempt.output()) if not e.last_attempt.failed else str(e.last_attempt.exception())
            except:
                pass
        
        logger.error(f"Error analyzing {ticker}: {error_msg}")
        return json.dumps({"error": f"Failed to analyze {ticker}: {error_msg}"})

@mcp.tool()
async def get_key_levels(ticker: str) -> str:
    """
    Identifies structural Support and Resistance levels 
    based on Price Action of the last 6 months.
    """
    try:
        df = await fetch_history_async(ticker, period="6mo")
        
        if df is None or df.empty:
            return json.dumps({"error": f"No data available for {ticker}"})
        
        # Filter out rows with invalid data (zeros in OHLC columns)
        df_valid = df[(df['Low'] > 0) & (df['High'] > 0) & (df['Open'] > 0) & (df['Close'] > 0)]
        
        if df_valid.empty:
            return json.dumps({"error": f"No valid price data available for {ticker}"})
        
        # Cálculo simplificado de máxima/mínima do período
        support = df_valid['Low'].min()
        resistance = df_valid['High'].max()
        current = df['Close'].iloc[-1]  # Use latest close even if other values are zero
        
        levels = {
            "ticker": ticker,
            "current_price": round(float(current), 2),
            "major_support": round(float(support), 2),
            "major_resistance": round(float(resistance), 2),
            "distance_to_resistance": f"{round(((resistance/current)-1)*100, 2)}%"
        }
        
        return json.dumps(levels, indent=2)
    except Exception as e:
        error_msg = str(e)
        if "RetryError" in type(e).__name__:
            try:
                # Extract the last exception from the retry wrapper
                error_msg = str(e.last_attempt.output()) if not e.last_attempt.failed else str(e.last_attempt.exception())
            except:
                pass

        logger.error(f"Error getting levels for {ticker}: {error_msg}")
        return json.dumps({"error": f"Failed to get levels for {ticker}: {error_msg}"})

if __name__ == "__main__":
    try:
        print(f"DEBUG: Starting uvicorn manually with host={settings.mcp_host} port={settings.mcp_port}")
        import uvicorn
        # Run the SSE app directly
        uvicorn.run(mcp.sse_app, host=settings.mcp_host, port=settings.mcp_port)
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
