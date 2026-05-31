import asyncio
import logging
import os
from typing import Any, Dict, List, Optional
import yfinance as yf
from core.mappings import find_gics_sub_industry

logger = logging.getLogger(__name__)

# Predefined high-quality peer groups for common GICS sub-industries to ensure offline/sandbox compatibility
_STATIC_PEERS = {
    # Energy
    "10101010": ["RIG", "VAL", "NE", "DO", "HP"],  # Oil & Gas Drilling
    "10101020": ["SLB", "HAL", "BKR", "FTI"],      # Oil & Gas Equipment & Services
    "10102010": ["XOM", "CVX", "SHEL", "TTE", "BP", "PETR4.BR"],  # Integrated Oil & Gas
    "10102020": ["COP", "EOG", "PXD", "OXY", "HES"],  # Oil & Gas Exploration & Production
    
    # Materials
    "15101010": ["LIN", "APD", "PX", "SHW", "VALE3.BR"],  # Commodity Chemicals / Mining
    
    # Industrials
    "20101010": ["GE", "RTX", "LMT", "NOC", "BA"],  # Aerospace & Defense
    
    # Consumer Discretionary
    "25102010": ["TSLA", "TM", "F", "GM", "HMC"],  # Automobile Manufacturers
    
    # Consumer Staples
    "30202010": ["PG", "KO", "PEP", "PM", "UL"],   # Household & Personal Products / Beverages
    
    # Health Care
    "35101010": ["JNJ", "LLY", "NVO", "MRK", "ABBV", "PFE"], # Pharmaceuticals
    "35201010": ["AMGN", "GILD", "VRTX", "REGN", "BIIB"],   # Biotechnology
    
    # Financials
    "40101010": ["JPM", "BAC", "WFC", "C", "BBAS3.BR", "ITUB4.BR"],  # Diversified Banks
    "40301010": ["CB", "PGR", "ALL", "TRV", "PSSA3.BR"],  # Insurance - Property & Casualty
    
    # Information Technology
    "45102010": ["MSFT", "ORCL", "SAP", "CRM", "INTU"],  # Application Software
    "45103010": ["AAPL", "HPQ", "DELL", "STX", "WDC"],   # Technology Hardware, Storage & Peripherals
    "45301010": ["NVDA", "AVGO", "AMD", "QCOM", "INTC"], # Semiconductors
    
    # Communication Services
    "50101020": ["DIS", "NFLX", "CMCSA", "CHTR", "WBD"], # Interactive Media / Entertainment
    
    # Utilities
    "55101010": ["NEE", "DUK", "SO", "AEP", "SRE"],      # Electric Utilities
    
    # Real Estate
    "60101010": ["PLD", "AMT", "EQIX", "CCI", "WY"],     # Specialized REITs
}

# Sector fallback peers
_SECTOR_FALLBACK_PEERS = {
    "Energy": ["XOM", "CVX", "BP", "SHEL"],
    "Materials": ["LIN", "SHW", "FCX", "NUE"],
    "Industrials": ["CAT", "HON", "GE", "UNP"],
    "Consumer Discretionary": ["AMZN", "HD", "MCD", "NKE"],
    "Consumer Staples": ["PG", "KO", "PEP", "WMT"],
    "Health Care": ["JNJ", "LLY", "PFE", "MRK"],
    "Financials": ["JPM", "BAC", "MS", "GS"],
    "Information Technology": ["MSFT", "AAPL", "NVDA", "CSCO"],
    "Communication Services": ["GOOGL", "META", "NFLX", "DIS"],
    "Utilities": ["NEE", "DUK", "SO", "AEP"],
    "Real Estate": ["PLD", "AMT", "EQIX", "SPG"],
}

class YFinanceClient:
    """
    Wrapper client for Yahoo Finance API to fetch data for fundamental analysis.
    """

    @staticmethod
    def _normalize_ticker_for_yfinance(symbol: str) -> str:
        """Convert .BR suffix to .SA for yfinance compatibility.
        
        yfinance uses .SA for B3 (Brazilian) tickers, but our system
        uses .BR (e.g., PETR4.BR -> PETR4.SA).
        """
        if symbol.upper().endswith(".BR"):
            return symbol[:-3] + ".SA"
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

    async def get_gics_classification(self, symbol: str) -> Dict[str, str]:
        """
        Retrieve sector, industry, and resolved GICS sub-industry ID.
        """
        info = await self.get_ticker_info(symbol)
        sector = info.get("sector", "")
        industry = info.get("industry", "")
        
        # Resolve GICS sub-industry ID using our fuzzy mappings lookup
        sub_industry_id = find_gics_sub_industry(sector, industry) or "10101010"
        
        return {
            "sector": sector,
            "industry": industry,
            "industry_group": sector,  # Default fallback
            "sub_industry": industry,  # Default fallback
            "sub_industry_id": sub_industry_id
        }

    async def get_peers(self, symbol: str, sub_industry_id: str) -> List[Dict[str, Any]]:
        """
        Auto-select peer companies from the same GICS sub-industry.
        Queries local DB if available, and merges/falls back to pre-configured mappings.
        """
        peer_tickers = []
        
        # 1. Query Supabase DB if host environment config is active
        db_host = os.getenv("POSTGRES_HOST")
        if db_host:
            try:
                # Resolve sector/industry first
                gics = await self.get_gics_classification(symbol)
                industry = gics["industry"]
                
                # Fetch peers in the same industry from public.ticker_enrichment
                import psycopg2
                conn = psycopg2.connect(
                    host=db_host,
                    port=os.getenv("POSTGRES_PORT", "5432"),
                    user=os.getenv("POSTGRES_USER", "postgres"),
                    password=os.getenv("POSTGRES_PASSWORD", "postgres"),
                    database=os.getenv("POSTGRES_DB", "postgres")
                )
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT ticker FROM public.ticker_enrichment WHERE industry = %s AND ticker != %s LIMIT 10;",
                        (industry, symbol)
                    )
                    rows = cur.fetchall()
                    peer_tickers = [row[0] for row in rows]
                conn.close()
                logger.info(f"Retrieved peers from DB for {symbol} ({industry}): {peer_tickers}")
            except Exception as e:
                logger.warning(f"Failed to fetch peers from DB for {symbol}: {e}. Falling back to static mappings.")

        # 2. Merge/Fall back to static peers if DB query returned nothing or is disabled
        if not peer_tickers:
            peer_tickers = _STATIC_PEERS.get(sub_industry_id, []).copy()
            # If target symbol is in the list, remove it
            if symbol in peer_tickers:
                peer_tickers.remove(symbol)
                
        # 3. Last fallback: sector list
        if not peer_tickers:
            gics = await self.get_gics_classification(symbol)
            fallback = _SECTOR_FALLBACK_PEERS.get(gics["sector"], [])
            peer_tickers = [t for t in fallback if t != symbol]

        # 4. Fetch details for each peer company
        peers_list = []
        for ticker in peer_tickers[:5]:  # Limit to top 5 peers to manage latency
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

    async def get_financial_data(self, symbol: str) -> Dict[str, float]:
        """
        Retrieve relevant financial metrics from YFinance info.
        """
        info = await self.get_ticker_info(symbol)
        
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
            "cost_of_equity": 0.0,
            "residual_income_per_share": 0.0,
        }
        
        # Clean and typecast
        return {k: float(v) if v is not None else 0.0 for k, v in metrics.items()}
