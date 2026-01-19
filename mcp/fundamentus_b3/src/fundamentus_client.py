"""Wrapper for the pyfundamentus library to fetch B3 stock data.

This module provides enterprise-grade extraction of fundamental data from Fundamentus,
including balance sheet and income statement metrics for comprehensive financial analysis.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict

from fundamentus.main.fundamentus_pipeline import FundamentusPipeline
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _make_json_serializable(obj: Any) -> Any:
    """
    Recursively convert numpy/pandas/Decimal types to Python native types for JSON serialization.
    
    Args:
        obj: Any object that might contain numpy/pandas/Decimal types
        
    Returns:
        Object with all types converted to Python native types
    """
    if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_serializable(item) for item in obj]
    if pd.isna(obj):
        return None
    return obj


def _extract_information_item_value(item: Any) -> Any:
    """
    Extract value from InformationItem object or return the value directly.
    
    Args:
        item: InformationItem object or direct value
        
    Returns:
        Extracted value (Decimal, str, dict, or None)
    """
    if item is None:
        return None
    
    # Check if it's an InformationItem (has 'value' attribute)
    if hasattr(item, 'value'):
        return item.value
    
    # If it's already a dict, recursively extract values
    if isinstance(item, dict):
        return {k: _extract_information_item_value(v) for k, v in item.items()}
    
    # Otherwise return as-is
    return item


def _safe_get_nested(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """
    Safely get nested dictionary value.
    
    Args:
        data: Dictionary to search
        keys: Path of keys to traverse
        default: Default value if not found
        
    Returns:
        Value at path or default
    """
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def normalize_ticker(ticker: str) -> str:
    """
    Normalize ticker format.
    
    Examples:
        - "PETR4.SA" -> "PETR4"
        - "petr4" -> "PETR4"
        - "PETR4" -> "PETR4"
    """
    # Remove .SA suffix if present
    clean = ticker.replace(".SA", "").replace(".sa", "")
    # Convert to uppercase
    return clean.upper().strip()


def _fetch_pyfundamentus_data(ticker: str, max_retries: int = 3) -> Dict[str, Any]:
    """
    Fetch raw data from pyfundamentus for a given ticker with retry logic.
    
    Args:
        ticker: Stock ticker (e.g., "PETR4")
        max_retries: Maximum number of retry attempts
        
    Returns:
        Dictionary with transformed_information from pyfundamentus
        
    Raises:
        ValueError: If ticker is not found or data cannot be retrieved after retries
    """
    import time
    
    last_exception = None
    
    for attempt in range(1, max_retries + 1):
        try:
            pipeline = FundamentusPipeline(ticker)
            response = pipeline.get_all_information()
            
            if not hasattr(response, 'transformed_information'):
                raise ValueError(f"Invalid response from pyfundamentus for {ticker}")
            
            data = response.transformed_information
            
            # Validate that we got some data
            if not data or not isinstance(data, dict):
                raise ValueError(f"Empty or invalid data structure for {ticker}")
            
            # Check for critical fields to ensure data quality
            if 'price_information' not in data:
                raise ValueError(f"Missing price_information for {ticker}")
            
            return data
            
        except ValueError as e:
            # Don't retry on ValueError (e.g., ticker not found)
            raise
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                wait_time = 2 ** attempt  # Exponential backoff: 2s, 4s, 8s
                logger.warning(
                    f"Attempt {attempt}/{max_retries} failed for {ticker}: {e}. "
                    f"Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
            else:
                logger.error(
                    f"All {max_retries} attempts failed for {ticker}: {e}",
                    exc_info=True
                )
    
    # If we get here, all retries failed
    raise ValueError(
        f"Failed to fetch data for {ticker} after {max_retries} attempts: {str(last_exception)}"
    )


def _map_pyfundamentus_to_normalized(pyfund_data: Dict[str, Any], ticker: str) -> Dict[str, Any]:
    """
    Map pyfundamentus data structure to normalized format.
    
    Args:
        pyfund_data: Dictionary from pyfundamentus transformed_information
        ticker: Normalized ticker symbol
        
    Returns:
        Dictionary with normalized and categorized stock data
    """
    result = {"ticker": ticker}
    
    # Helper to extract InformationItem values
    def get_value(*keys):
        value = _safe_get_nested(pyfund_data, *keys)
        return _extract_information_item_value(value)
    
    # ===== IDENTIFICAÇÃO E PREÇO =====
    result["ticker_raw"] = get_value("stock_identification", "name") or ticker
    result["empresa"] = get_value("stock_identification", "ticker")
    result["cotacao"] = get_value("price_information", "price")
    result["data_ultima_cotacao"] = get_value("price_information", "date")
    result["tipo"] = get_value("detailed_information", "stock_type")
    result["setor"] = get_value("financial_summary", "sector")
    result["subsetor"] = get_value("financial_summary", "subsector")
    
    # 52 semanas (nested structure)
    var_52w = get_value("detailed_information", "variation_52_weeks")
    if isinstance(var_52w, dict):
        result["min_52_semanas"] = _extract_information_item_value(var_52w.get("lowest_value"))
        result["max_52_semanas"] = _extract_information_item_value(var_52w.get("highest_value"))
    
    result["volume_medio_2m"] = get_value("detailed_information", "traded_volume_per_day")
    result["valor_mercado"] = get_value("financial_summary", "market_valuation")
    result["valor_firma"] = get_value("financial_summary", "enterprise_valuation")
    result["ultimo_balanco"] = get_value("financial_summary", "last_financial_statement")
    result["numero_acoes"] = get_value("financial_summary", "number_of_shares")
    
    # ===== MÚLTIPLOS DE VALUATION =====
    result["pl"] = get_value("valuation_indicators", "price_divided_by_profit_title")
    result["pvp"] = get_value("valuation_indicators", "price_divided_by_asset_value")
    result["psr"] = get_value("valuation_indicators", "price_divided_by_net_revenue")
    result["dy"] = get_value("valuation_indicators", "dividend_yield")
    result["p_ebit"] = get_value("valuation_indicators", "price_divided_by_ebit")
    result["p_ativo"] = get_value("valuation_indicators", "price_divided_by_total_assets")
    result["p_ativ_circ_liq"] = get_value("valuation_indicators", "price_divided_by_net_current_assets")
    result["ev_ebitda"] = get_value("valuation_indicators", "enterprise_value_by_ebitda")
    result["ev_ebit"] = get_value("valuation_indicators", "enterprise_value_by_ebit")
    result["vpa"] = get_value("detailed_information", "equity_value_per_share")
    result["lpa"] = get_value("detailed_information", "earnings_per_share")
    result["p_cap_giro"] = get_value("valuation_indicators", "price_by_working_capital")
    
    # ===== RENTABILIDADE E MARGENS =====
    result["roic"] = get_value("profitability_indicators", "return_on_invested_capital")
    result["roe"] = get_value("profitability_indicators", "return_on_equity")
    result["marg_bruta"] = get_value("profitability_indicators", "gross_profit_divided_by_net_revenue")
    result["marg_ebit"] = get_value("profitability_indicators", "ebit_divided_by_net_revenue")
    result["marg_liquida"] = get_value("profitability_indicators", "net_income_divided_by_net_revenue")
    result["ebit_ativo"] = get_value("profitability_indicators", "ebit_divided_by_total_assets")
    result["giro_ativos"] = get_value("profitability_indicators", "net_revenue_divided_by_total_assets")
    result["crescimento_receita_5anos"] = get_value("profitability_indicators", "net_revenue_growth_last_5_years")
    
    # ===== SOLVÊNCIA E ENDIVIDAMENTO =====
    result["div_bruta_patrim"] = get_value("indebtedness_indicators", "gross_debt_by_equity")
    result["div_liquida_patrim"] = get_value("indebtedness_indicators", "net_debt_by_equity")
    result["div_liquida_ebitda"] = get_value("indebtedness_indicators", "net_debt_by_ebitda")
    result["liquidez_corrente"] = get_value("indebtedness_indicators", "current_liquidity")
    
    # ===== BALANÇO PATRIMONIAL =====
    result["ativo_total"] = get_value("balance_sheet", "total_assets")
    result["ativo_circulante"] = get_value("balance_sheet", "current_assets")
    result["caixa"] = get_value("balance_sheet", "cash")
    result["patrimonio_liquido"] = get_value("balance_sheet", "equity")
    result["divida_bruta"] = get_value("balance_sheet", "gross_debt")
    result["divida_liquida"] = get_value("balance_sheet", "net_debt")
    
    # ===== DEMONSTRATIVO DE RESULTADOS (DRE) =====
    # 12 meses
    income_12m = get_value("income_statement", "twelve_months")
    if isinstance(income_12m, dict):
        result["receita_liquida_12m"] = _extract_information_item_value(income_12m.get("revenue"))
        result["ebit_12m"] = _extract_information_item_value(income_12m.get("ebit"))
        result["lucro_liquido_12m"] = _extract_information_item_value(income_12m.get("net_income"))
    
    # 3 meses
    income_3m = get_value("income_statement", "three_months")
    if isinstance(income_3m, dict):
        result["receita_liquida_3m"] = _extract_information_item_value(income_3m.get("revenue"))
        result["ebit_3m"] = _extract_information_item_value(income_3m.get("ebit"))
        result["lucro_liquido_3m"] = _extract_information_item_value(income_3m.get("net_income"))
    
    # Remove None values from flat structure (but keep them in categorized structure)
    result = {k: v for k, v in result.items() if v is not None}
    
    # ===== CATEGORIZED METRICS FOR EASY ACCESS =====
    # Valuation Metrics
    result["valuation"] = {
        "cotacao": result.get("cotacao"),
        "pl": result.get("pl"),
        "pvp": result.get("pvp"),
        "psr": result.get("psr"),
        "dy": result.get("dy"),
        "ev_ebitda": result.get("ev_ebitda"),
        "ev_ebit": result.get("ev_ebit"),
        "vpa": result.get("vpa"),
        "lpa": result.get("lpa"),
    }
    
    # Profitability Metrics
    result["profitability"] = {
        "roic": result.get("roic"),
        "roe": result.get("roe"),
        "marg_bruta": result.get("marg_bruta"),
        "marg_ebit": result.get("marg_ebit"),
        "marg_liquida": result.get("marg_liquida"),
        "ebit_ativo": result.get("ebit_ativo"),
    }
    
    # Solvency and Leverage
    result["solvency"] = {
        "div_bruta_patrim": result.get("div_bruta_patrim"),
        "div_liquida_patrim": result.get("div_liquida_patrim"),
        "div_liquida_ebitda": result.get("div_liquida_ebitda"),
        "divida_bruta": result.get("divida_bruta"),
        "divida_liquida": result.get("divida_liquida"),
    }
    
    # Liquidity Metrics
    result["liquidity"] = {
        "liquidez_corrente": result.get("liquidez_corrente"),
        "caixa": result.get("caixa"),
        "ativo_circulante": result.get("ativo_circulante"),
    }
    
    # Balance Sheet (Absolute Values)
    result["balance_sheet"] = {
        "ativo_total": result.get("ativo_total"),
        "ativo_circulante": result.get("ativo_circulante"),
        "patrimonio_liquido": result.get("patrimonio_liquido"),
        "caixa": result.get("caixa"),
    }
    
    # Income Statement (DRE - LTM)
    result["income_statement"] = {
        "receita_liquida_12m": result.get("receita_liquida_12m"),
        "ebit_12m": result.get("ebit_12m"),
        "lucro_liquido_12m": result.get("lucro_liquido_12m"),
    }
    
    # Efficiency Metrics
    result["efficiency"] = {
        "giro_ativos": result.get("giro_ativos"),
    }
    
    # Growth Metrics
    result["growth"] = {
        "crescimento_receita_5anos": result.get("crescimento_receita_5anos"),
    }
    
    # Legacy compatibility: Keep old metric names for backward compatibility
    result["div_brut_patrim"] = result.get("div_bruta_patrim")  # Old name
    
    # Convert all Decimal/numpy/pandas types to Python native types for JSON serialization
    result = _make_json_serializable(result)
    
    return result


def get_papel_data(ticker: str) -> Dict[str, Any]:
    """
    Fetch and normalize comprehensive data for a single ticker from Fundamentus.
    
    This function extracts:
    - Valuation multiples (P/L, P/VP, EV/EBITDA, etc.)
    - Profitability metrics (ROIC, ROE, Margins)
    - Solvency and leverage (D/E, Interest Coverage)
    - Liquidity ratios (Current Ratio, Working Capital)
    - Balance Sheet items (Assets, Liabilities, Equity)
    - Income Statement items (Revenue, EBIT, EBITDA, Net Income)
    
    Args:
        ticker: Stock ticker (e.g., "PETR4", "PETR4.SA", "petr4")
        
    Returns:
        Dictionary with normalized and categorized stock data
        
    Raises:
        ValueError: If ticker is not found or data cannot be retrieved
    """
    normalized_ticker = normalize_ticker(ticker)
    
    if not normalized_ticker:
        raise ValueError("Ticker cannot be empty")
    
    try:
        # Fetch data from pyfundamentus (with retry logic)
        pyfund_data = _fetch_pyfundamentus_data(normalized_ticker)
        
        # Map to normalized format
        result = _map_pyfundamentus_to_normalized(pyfund_data, normalized_ticker)
        
        # Validate critical fields are present
        if not result.get("cotacao"):
            logger.warning(f"Missing cotacao for {normalized_ticker}")
        
        return result
        
    except ValueError:
        # Re-raise ValueError as-is (ticker not found, etc.)
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error fetching data for {normalized_ticker}: {e}",
            exc_info=True
        )
        raise ValueError(f"Failed to fetch data for {normalized_ticker}: {str(e)}")


def get_papel_list() -> list[str]:
    """
    Get list of all available tickers from Fundamentus.
    
    Note: pyfundamentus doesn't have a direct method to list all tickers.
    This function returns an empty list. Consider implementing a static list
    or alternative scraping method if needed.
    
    Returns:
        List of normalized ticker symbols (currently empty)
    """
    logger.warning("get_papel_list() not implemented for pyfundamentus - returning empty list")
    # TODO: Implement static list or alternative method to get all tickers
    return []


def search_tickers(query: str) -> list[Dict[str, Any]]:
    """
    Search for tickers by name or segment.
    
    Note: pyfundamentus doesn't have a direct search method.
    This function returns an empty list. Consider implementing a static list
    with search functionality if needed.
    
    Args:
        query: Search query (ticker code or company name)
        
    Returns:
        List of dictionaries with ticker information (currently empty)
    """
    logger.warning(f"search_tickers() not implemented for pyfundamentus - query: {query}")
    # TODO: Implement static list with search functionality
    return []
