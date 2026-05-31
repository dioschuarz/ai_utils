import asyncio
import logging
import time
import json
from datetime import datetime, timezone
from typing import Annotated, Optional, List, Dict, Tuple
import xml.etree.ElementTree as ET

import httpx
import yfinance
from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from .config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_settings = get_settings()
mcp = FastMCP("news-discovery-mcp")

# 1-hour cache TTL
CACHE_TTL = 3600
# Cache format: { (ticker, source): (timestamp, articles_list) }
_cache: Dict[Tuple[str, str], Tuple[float, List[dict]]] = {}


class NormalizedNewsArticleDTO(BaseModel):
    """Represents news metadata discovered from external providers."""
    source: str = Field(..., description="Source identifier (e.g. tavily, yahoo)")
    title: str = Field(..., description="Normalized article title")
    url: str = Field(..., description="Canonical URL of the article")
    published_at: str = Field(..., description="ISO 8601 published timestamp")
    confidence_score: float = Field(..., description="Discovery confidence score (0.0 to 1.0)")
    snippet: Optional[str] = Field(default=None, description="Optional preview/summary snippet")


async def _discover_yahoo(ticker: str, max_results: int) -> List[dict]:
    """Fetch news from Yahoo Finance using yfinance."""
    loop = asyncio.get_event_loop()
    def fetch_yf_news():
        yf_ticker = yfinance.Ticker(ticker)
        return yf_ticker.news

    raw_news = await loop.run_in_executor(None, fetch_yf_news)
    if not raw_news:
        return []

    articles = []
    for item in raw_news:
        content = item.get("content", {})
        title = content.get("title", "")
        url = content.get("canonicalUrl", {}).get("url") or item.get("link", "")
        
        # Parse publication date
        pub_date_str = content.get("pubDate") or item.get("providerPublishTime")
        if isinstance(pub_date_str, int):
            published_at = datetime.fromtimestamp(pub_date_str, tz=timezone.utc).isoformat()
        elif isinstance(pub_date_str, str):
            published_at = pub_date_str
        else:
            published_at = datetime.now(timezone.utc).isoformat()

        if not title or not url:
            continue

        articles.append({
            "source": "yahoo",
            "title": title,
            "url": url,
            "published_at": published_at,
            "confidence_score": 0.9,
            "snippet": content.get("summary") or content.get("description"),
        })
    return articles


async def _discover_tavily(ticker: str, max_results: int) -> List[dict]:
    """Fetch news using Tavily Search API."""
    api_key = _settings.tavily_api_key
    if not api_key:
        logger.warning("TAVILY_API_KEY is not set. Skipping Tavily discovery.")
        return []

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": f"{ticker} stock news market updates",
        "search_depth": "basic",
        "max_results": max_results,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        articles = []
        for item in results:
            published_date = item.get("published_date") or datetime.now(timezone.utc).isoformat()
            articles.append({
                "source": "tavily",
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "published_at": published_date,
                "confidence_score": round(item.get("score", 0.8), 2),
                "snippet": item.get("content", ""),
            })
        return articles


async def _discover_tickertick(ticker: str, max_results: int) -> List[dict]:
    """Fetch news from Tickertick API."""
    url = f"{_settings.tickertick_api_url}/feed"
    params = {
        "q": f"tt:{ticker.lower()}",
        "n": max_results
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        stories = data.get("stories", [])
        articles = []
        for story in stories:
            published_date_ms = story.get("time")
            if published_date_ms:
                published_at = datetime.fromtimestamp(published_date_ms / 1000.0, tz=timezone.utc).isoformat()
            else:
                published_at = datetime.now(timezone.utc).isoformat()
                
            articles.append({
                "source": "tickertick",
                "title": story.get("title", ""),
                "url": story.get("url") or story.get("link") or "",
                "published_at": published_at,
                "confidence_score": 0.85,
                "snippet": story.get("description") or "",
            })
        return articles


async def _discover_rss(ticker: str, max_results: int) -> List[dict]:
    """Fetch news from generic RSS feed (Yahoo RSS feed as fallback)."""
    rss_url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(rss_url)
        response.raise_for_status()
        xml_data = response.text

        root = ET.fromstring(xml_data)
        articles = []
        
        for item in root.findall(".//item")[:max_results]:
            title = item.find("title")
            link = item.find("link")
            pub_date = item.find("pubDate")
            description = item.find("description")

            title_text = title.text if title is not None else ""
            link_text = link.text if link is not None else ""
            pub_date_text = pub_date.text if pub_date is not None else ""
            desc_text = description.text if description is not None else ""

            if not title_text or not link_text:
                continue

            articles.append({
                "source": "rss",
                "title": title_text,
                "url": link_text,
                "published_at": pub_date_text,
                "confidence_score": 0.7,
                "snippet": desc_text,
            })
        return articles


@mcp.tool(
    name="discover_news",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def discover_news(
    ticker: Annotated[str, Field(description="Stock ticker symbol (e.g. AAPL, PETR4)")],
    source: Annotated[str, Field(description="Discovery provider: 'yahoo', 'tavily', 'tickertick', or 'rss'")] = "yahoo",
    max_results: Annotated[int, Field(description="Maximum number of news articles to return")] = 10,
    market_context: Annotated[Optional[str], Field(description="Optional context to filter or focus search results")] = None,
    date_filter: Annotated[Optional[str], Field(description="Optional ISO date filter to exclude older articles")] = None,
) -> str:
    """Discover news articles metadata for a given stock ticker."""
    cache_key = (ticker.upper(), source.lower())
    
    # Check cache
    if cache_key in _cache:
        timestamp, cached_articles = _cache[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            logger.info(f"Cache hit for {ticker} ({source})")
            return json.dumps(cached_articles[:max_results])

    logger.info(f"Fetching news for {ticker} from {source}...")
    articles = []
    
    try:
        if source == "yahoo":
            articles = await _discover_yahoo(ticker, max_results * 2)
        elif source == "tavily":
            articles = await _discover_tavily(ticker, max_results * 2)
        elif source == "tickertick":
            articles = await _discover_tickertick(ticker, max_results * 2)
        elif source == "rss":
            articles = await _discover_rss(ticker, max_results * 2)
        else:
            logger.warning(f"Unknown source '{source}', falling back to yahoo")
            articles = await _discover_yahoo(ticker, max_results * 2)
    except Exception as e:
        logger.error(f"Discovery error: {e}", exc_info=True)
        # Fallback to yahoo
        if source != "yahoo":
            logger.info(f"Falling back to yahoo for {ticker}")
            try:
                articles = await _discover_yahoo(ticker, max_results * 2)
            except Exception as fe:
                logger.error(f"Fallback failed: {fe}")

    # Deduplicate articles by canonicalizing URLs
    seen_urls = set()
    deduped_articles = []
    for art in articles:
        url = art["url"]
        # Basic normalization: strip query parameters and slash
        normalized_url = url.split("?")[0].rstrip("/")
        if normalized_url not in seen_urls:
            seen_urls.add(normalized_url)
            deduped_articles.append(art)

    # Cache the result
    _cache[cache_key] = (time.time(), deduped_articles)

    return json.dumps(deduped_articles[:max_results])


from starlette.responses import JSONResponse

@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    """Health check endpoint."""
    return JSONResponse({"status": "healthy"})


def main() -> None:
    logger.info(f"Starting News Discovery MCP on {_settings.mcp_host}:{_settings.mcp_port}")
    mcp.run(
        transport="http",
        host=_settings.mcp_host,
        port=_settings.mcp_port,
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
