import asyncio
import logging
import os
from typing import Any, Dict, List, Optional
import yfinance as yf
from core.mappings import find_gics_sub_industry

logger = logging.getLogger(__name__)

# Predefined static peer groups removed as per dynamic ISIC Rev 5 database schema requirements.

class YFinanceClient:
    """
    Wrapper client for Yahoo Finance API to fetch data for fundamental analysis.
    """

    @staticmethod
    def _normalize_ticker_for_yfinance(symbol: str) -> str:
        """Convert .BR suffix to .SA for yfinance compatibility and strip .US suffix.
        
        yfinance uses .SA for B3 (Brazilian) tickers, but our system
        uses .BR (e.g., PETR4.BR -> PETR4.SA).
        """
        import re
        symbol_upper = symbol.strip().upper()
        if symbol_upper.endswith(".SA.BR"):
            return symbol_upper[:-6] + ".SA"
        if symbol_upper.endswith(".BR"):
            return symbol_upper[:-3] + ".SA"
        if symbol_upper.endswith(".US"):
            return symbol_upper[:-3]
        # Auto-append .SA for B3 tickers matching typical format (4 letters + 1-2 digits)
        if re.match(r"^[A-Z]{4}[0-9]{1,2}$", symbol_upper):
            return symbol_upper + ".SA"
        return symbol

    async def get_ticker_info(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch comprehensive ticker info from Yahoo Finance in a thread-safe async manner.
        """
        yf_symbol = self._normalize_ticker_for_yfinance(symbol)
        try:
            ticker = await asyncio.to_thread(yf.Ticker, yf_symbol)
            info = await asyncio.to_thread(lambda: ticker.info)
            return info if isinstance(info, dict) else {}
        except Exception as e:
            logger.error(f"Failed to fetch ticker info for {symbol} (yf: {yf_symbol}): {e}")
            return {}

    async def get_isic_classification(self, symbol: str) -> Dict[str, str]:
        """
        Retrieve sector, industry, and resolved ISIC code.
        """
        from core.mappings import ISICCache, resolve_isic_code
        info = await self.get_ticker_info(symbol)
        sector = info.get("sector", "")
        industry = info.get("industry", "")
        
        isic_code = resolve_isic_code(sector, industry) or "0111"
        
        # Get taxonomy row to fill class descriptions
        cache = ISICCache()
        try:
            row = cache.get_row(isic_code)
            isic_division = row.get("division_description") or ""
            isic_group = row.get("group_description") or ""
            isic_class = row.get("class_description") or ""
        except Exception:
            isic_division = ""
            isic_group = ""
            isic_class = ""
            
        return {
            "sector": sector,
            "industry": industry,
            "isic_division": isic_division,
            "isic_group": isic_group,
            "isic_class": isic_class,
            "isic_code": isic_code
        }

    async def get_gics_classification(self, symbol: str) -> Dict[str, str]:
        """Deprecated compatibility wrapper."""
        res = await self.get_isic_classification(symbol)
        return {
            **res,
            "sub_industry_id": res["isic_code"],
            "sub_industry": res["isic_class"],
            "industry_group": res["isic_group"]
        }

    async def get_peers(self, symbol: str, isic_code: str) -> List[Dict[str, Any]]:
        """
        Auto-select peer companies from the same ISIC code/division.
        Queries dynamic cache/DB and handles division-level fallback.
        """
        from core.mappings import ISICCache
        
        def _normalize_br_ticker(ticker: str) -> str:
            t = ticker.strip().upper()
            if t.endswith(".SA.BR"):
                t = t[:-6]
            if t.endswith(".BR"):
                t = t[:-3]
            if not t.endswith(".SA"):
                t = t + ".SA"
            return t

        peer_tickers = []
        normalized_symbol = symbol.upper().replace(".SA", "").replace(".BR", "")
        
        cache = ISICCache()
        try:
            row = cache.get_row(isic_code)
        except Exception as e:
            logger.warning(f"Could not retrieve taxonomy row for ISIC {isic_code}: {e}")
            row = {}

        # 1. Parse US and BR peers for this specific class
        us_peers_raw = row.get("us_stocks") or ""
        br_peers_raw = row.get("br_stocks") or ""
        
        us_peers = [t.strip().upper() for t in us_peers_raw.split(",") if t.strip()]
        br_peers = [_normalize_br_ticker(t) for t in br_peers_raw.split(",") if t.strip()]
        
        class_peers = br_peers + us_peers
        
        # Filter out the target stock
        for t in class_peers:
            norm_t = t.upper().replace(".SA", "").replace(".BR", "")
            if norm_t != normalized_symbol:
                peer_tickers.append(t)

        # 2. Division-level peer fallback logic
        if len(peer_tickers) < 6:
            div_code = row.get("division_code")
            if div_code:
                logger.info(f"Fewer than 6 class peers found for {symbol}. Aggregating division peers for division {div_code}...")
                all_rows = cache.get_all_rows()
                div_br_peers = []
                div_us_peers = []
                for code, r in all_rows.items():
                    if r.get("division_code") == div_code:
                        r_us = r.get("us_stocks") or ""
                        r_br = r.get("br_stocks") or ""
                        for t in r_us.split(","):
                            t_clean = t.strip().upper()
                            if t_clean and t_clean not in div_us_peers:
                                div_us_peers.append(t_clean)
                        for t in r_br.split(","):
                            t_clean = _normalize_br_ticker(t)
                            if t_clean and t_clean not in div_br_peers:
                                div_br_peers.append(t_clean)
                                
                # Merge division peers, avoiding duplicates and target stock
                for t in (div_br_peers + div_us_peers):
                    norm_t = t.upper().replace(".SA", "").replace(".BR", "")
                    if norm_t == normalized_symbol:
                        continue
                    if norm_t not in [x.upper().replace(".SA", "").replace(".BR", "") for x in peer_tickers]:
                        peer_tickers.append(t)

        # 3. Fetch details for each peer company
        # Balanced peer selection (US & BR)
        br_tickers = []
        us_tickers = []
        for t in peer_tickers:
            if t.upper().endswith(".SA") or t.upper().endswith(".BR"):
                br_tickers.append(t)
            else:
                us_tickers.append(t)
                
        # select at least 3 from each country if possible, up to 6 total
        selected_tickers = []
        num_br = len(br_tickers)
        num_us = len(us_tickers)
        
        if num_br >= 3 and num_us >= 3:
            selected_tickers = br_tickers[:3] + us_tickers[:3]
        elif num_br < 3:
            selected_tickers = br_tickers + us_tickers[:(6 - num_br)]
        elif num_us < 3:
            selected_tickers = us_tickers + br_tickers[:(6 - num_us)]
            
        selected_tickers = selected_tickers[:6]  # safety cap

        peers_list = []
        for ticker in selected_tickers:
            try:
                peer_info = await self.get_ticker_info(ticker)
                if not peer_info:
                    continue
                    
                pe = peer_info.get("trailingPE") or peer_info.get("forwardPE")
                ev_ebitda = peer_info.get("enterpriseToEbitda")
                ev_rev = peer_info.get("enterpriseToRevenue")
                pb = peer_info.get("priceToBook")
                
                multiples = {}
                if pe: multiples["P/E"] = float(pe)
                if ev_ebitda: multiples["EV/EBITDA"] = float(ev_ebitda)
                if ev_rev: multiples["EV/Revenue"] = float(ev_rev)
                if pb: multiples["P/B"] = float(pb)
                
                peers_list.append({
                    "ticker": ticker,
                    "market_cap": float(peer_info.get("marketCap", 0.0) or 0.0),
                    "multiples": multiples
                })
            except Exception as e:
                logger.warning(f"Failed to fetch peer metrics for {ticker}: {e}")
                
        return peers_list

    async def get_financial_data(self, symbol: str) -> Dict[str, Any]:
        """
        Retrieve relevant financial metrics from YFinance info and cashflow history.
        """
        yf_symbol = self._normalize_ticker_for_yfinance(symbol)
        info = {}
        cf_df = None
        try:
            ticker = await asyncio.to_thread(yf.Ticker, yf_symbol)
            info = await asyncio.to_thread(lambda: ticker.info)
            if not isinstance(info, dict):
                info = {}
            cf_df = await asyncio.to_thread(lambda: ticker.cashflow)
        except Exception as e:
            logger.error(f"Failed to fetch financial data for {symbol} (yf: {yf_symbol}): {e}")

        # Extract financial variables
        metrics = {
            "current_price": info.get("currentPrice") or info.get("previousClose") or 0.0,
            "market_cap": info.get("marketCap") or 0.0,
            "total_revenue": info.get("totalRevenue") or 0.0,
            "operating_cash_flow": info.get("operatingCashflow") or 0.0,
            "free_cash_flow": info.get("freeCashflow") or 0.0,
            "shares_outstanding": info.get("sharesOutstanding") or 0.0,
            "eps": info.get("trailingEps") or info.get("forwardEps") or 0.0,
            "total_debt": info.get("totalDebt") or 0.0,
            "total_cash": info.get("totalCash") or 0.0,
            "book_value": info.get("bookValue") or 0.0,
            "ebitda": info.get("ebitda") or 0.0,
            "return_on_equity": info.get("returnOnEquity") or 0.0,
            "operating_margins": info.get("operatingMargins") or 0.0,
            "dividend_rate": info.get("dividendRate") or 0.0,
            "dividend_yield": info.get("dividendYield") or 0.0,
            "payout_ratio": info.get("payoutRatio") or 0.0,
            "beta": info.get("beta") or 1.0,
            "revenue_growth": info.get("revenueGrowth") or 0.0,
            "profit_margins": info.get("profitMargins") or 0.0,
            "enterprise_value": info.get("enterpriseValue") or 0.0,
        }
        
        # Clean and typecast
        cleaned = {k: float(v) if v is not None else 0.0 for k, v in metrics.items()}
        cleaned["currency"] = str(info.get("currency") or "USD")

        # Extract cashflow history
        free_cash_flow_history = []
        operating_cash_flow_history = []
        capex_history = []

        if cf_df is not None and not cf_df.empty:
            import pandas as pd
            def extract_row_values(df, possible_keys: List[str]) -> List[float]:
                for key in possible_keys:
                    matched_key = next((idx for idx in df.index if idx.strip().lower() == key.lower()), None)
                    if matched_key:
                        row = df.loc[matched_key]
                        if isinstance(row, pd.Series):
                            return [float(val) for val in row.dropna().tolist()]
                        elif pd.notna(row):
                            return [float(row)]
                return []

            free_cash_flow_history = extract_row_values(cf_df, ["Free Cash Flow"])
            operating_cash_flow_history = extract_row_values(cf_df, ["Operating Cash Flow"])
            raw_capex = extract_row_values(cf_df, ["Capital Expenditure", "Purchase of PPE", "Purchase of Property, Plant and Equipment"])
            capex_history = [abs(val) for val in raw_capex]

        # Fallbacks for history if not populated
        if not free_cash_flow_history and cleaned.get("free_cash_flow", 0.0) != 0.0:
            free_cash_flow_history = [cleaned["free_cash_flow"]]
        if not operating_cash_flow_history and cleaned.get("operating_cash_flow", 0.0) != 0.0:
            operating_cash_flow_history = [cleaned["operating_cash_flow"]]
        if not capex_history and cleaned.get("operating_cash_flow", 0.0) != 0.0:
            capex_history = [abs(cleaned["operating_cash_flow"] - cleaned["free_cash_flow"])]

        cleaned["free_cash_flow_history"] = free_cash_flow_history
        cleaned["operating_cash_flow_history"] = operating_cash_flow_history
        cleaned["capex_history"] = capex_history

        return cleaned

