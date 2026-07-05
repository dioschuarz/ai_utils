import logging
import random
import time
import datetime
from typing import Dict, Optional
import requests
import polars as pl
from schemas import MacroIndicatorsResponse, MacroComponents

logger = logging.getLogger(__name__)

class MacroHTTPClient:
    """Resilient HTTP Client with exponential backoff and jitter."""
    def __init__(self, max_retries: int = 5, base_backoff: float = 2.0):
        self.session = requests.Session()
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        
    def get(self, url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> requests.Response:
        attempt = 0
        while True:
            try:
                response = self.session.get(url, headers=headers, timeout=timeout)
                if response.status_code == 200:
                    return response
                if response.status_code in [429, 500, 502, 503, 504]:
                    attempt += 1
                    if attempt > self.max_retries: 
                        logger.error(f"HTTP GET failed after {self.max_retries} attempts. Status: {response.status_code}")
                        return response
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        sleep_time = int(retry_after) + random.uniform(0.5, 1.5)
                    else:
                        sleep_time = (self.base_backoff * (2 ** (attempt - 1))) + random.random()
                    logger.warning(f"Throttled/Server error ({response.status_code}). Retrying in {sleep_time:.2f}s...")
                    time.sleep(sleep_time)
                    continue
                return response
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as net_err:
                attempt += 1
                if attempt > self.max_retries: 
                    raise net_err
                sleep_time = (self.base_backoff * (2 ** (attempt - 1))) + random.random()
                logger.warning(f"Network error. Retrying in {sleep_time:.2f}s...")
                time.sleep(sleep_time)

http_client = MacroHTTPClient(max_retries=5, base_backoff=2.0)
headers = {"User-Agent": "MacroAPIBackend/18.0"}

def fetch_fred_series(series_id: str, api_key: str) -> pl.DataFrame:
    """Fetch observations from FRED API and return a Polars DataFrame."""
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={api_key}&file_type=json"
    res = http_client.get(url, timeout=10)
    res.raise_for_status()
    data = res.json()["observations"]
    # Filter missing values (represented as ".")
    df = pl.DataFrame(data).filter(pl.col("value") != ".").sort("date")
    return df

def run_macro_pipeline(fred_api_key: str) -> Dict[str, MacroIndicatorsResponse]:
    """Execute the entire US and Brazil macroeconomic indicators pipeline."""
    if not fred_api_key:
        raise ValueError("FRED_API_KEY is required to run the macro pipeline.")
        
    logger.info("Running US macro indicators pipeline...")
    series_to_fetch = {
        "rf_10y": "GS10",               
        "corporate_yield": "BAA",       
        "us_market_total": "SP500",     
        "cpi_index": "CPIAUCSL"         
    }
    raw_frames = {}
    for key, series_id in series_to_fetch.items():
        raw_frames[key] = fetch_fred_series(series_id, fred_api_key)
        
    # US Calculations
    us_rf = round(float(raw_frames["rf_10y"]["value"][-1]), 2)
    baa_yield = round(float(raw_frames["corporate_yield"]["value"][-1]), 2)
    market_credit_spread = baa_yield - us_rf
    
    # Downsample SP500 daily to Monthly
    df_sp_monthly = raw_frames["us_market_total"].with_columns([
        pl.col("date").str.to_date("%Y-%m-%d"),
        pl.col("value").cast(pl.Float64)
    ]).sort("date").with_columns([
        pl.col("date").dt.year().alias("year"),
        pl.col("date").dt.month().alias("month")
    ]).group_by(["year", "month"]).agg([
        pl.col("value").last(),
        pl.col("date").last()
    ]).sort("date")
    
    # SP500 Monthly Annualized Vol
    df_sp_returns = df_sp_monthly.with_columns(
        (pl.col("value") / pl.col("value").shift(1) - 1).alias("monthly_return")
    ).drop_nulls()
    sigma_equity_monthly = df_sp_returns["monthly_return"].std() * (12 ** 0.5)
    
    # Corporate Yield Monthly Annualized Vol (Merton Duration Isolation)
    df_baa_monthly = raw_frames["corporate_yield"].with_columns([
        pl.col("date").str.to_date("%Y-%m-%d"),
        pl.col("value").cast(pl.Float64)
    ]).sort("date")
    
    df_baa_calc = df_baa_monthly.with_columns([
        (pl.col("value") / 100).alias("y"),
        (pl.col("value") - pl.col("value").shift(1)).alias("delta_y")
    ]).with_columns(
        ((1.0 - (1.0 + pl.col("y"))**(-10)) / pl.col("y")).alias("duration")
    ).with_columns(
        (-pl.col("duration").shift(1) * (pl.col("delta_y") / 100)).alias("bond_monthly_return")
    ).drop_nulls()
    sigma_bond_monthly = df_baa_calc["bond_monthly_return"].std() * (12 ** 0.5)
    
    # Capital Structure Multiplier & MRP
    capital_structure_multiplier = sigma_equity_monthly / sigma_bond_monthly
    us_mrp = round(market_credit_spread * capital_structure_multiplier, 2)
    
    # SP500 1Y Daily Annualized Vol (for BRL coupling)
    df_sp_1y = raw_frames["us_market_total"].tail(252).with_columns(pl.col("value").cast(pl.Float64))
    df_sp_daily_calc = df_sp_1y.with_columns(
        (pl.col("value") / pl.col("value").shift(1) - 1).alias("daily_return")
    ).drop_nulls()
    sigma_equity_daily = df_sp_daily_calc["daily_return"].std() * (252 ** 0.5)
    
    # US Inflation
    df_cpi = raw_frames["cpi_index"]
    us_inflation = round(((float(df_cpi["value"][-1]) - float(df_cpi["value"][-13])) / float(df_cpi["value"][-13])) * 100, 2)
    
    ref_date = str(raw_frames["rf_10y"]["date"][-1])
    
    us_response = MacroIndicatorsResponse(
        country="USA",
        currency="USD",
        market_risk_premium=round(us_mrp / 100, 4),  # Convert 5.3% to 0.053
        components=MacroComponents(
            risk_free_rate_rf=round(us_rf / 100, 4),  # Convert 4.32% to 0.0432
            market_credit_spread=round(market_credit_spread / 100, 4),
            capital_structure_multiplier=round(capital_structure_multiplier, 4),
            inflation_yoy=round(us_inflation / 100, 4)
        ),
        reference_period=ref_date
    )
    
    logger.info("Running Brazil macro indicators pipeline...")
    today = datetime.date.today()
    one_year_ago = today - datetime.timedelta(days=365)
    data_inicial_str = one_year_ago.strftime("%d/%m/%Y")
    data_final_str = today.strftime("%d/%m/%Y")
    
    # BCB Exchange Rate
    bcb_fx_url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados?formato=json&dataInicial={data_inicial_str}&dataFinal={data_final_str}"
    res_fx = http_client.get(bcb_fx_url, headers=headers, timeout=10)
    res_fx.raise_for_status()
    
    df_fx = pl.DataFrame(res_fx.json())
    df_fx_clean = df_fx.with_columns([
        pl.col("data").str.to_date("%d/%m/%Y"),
        pl.col("valor").cast(pl.Float64)
    ]).sort("data")
    
    # BCB IPCA Inflation
    bcb_inf_url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.13522/dados/ultimos/1?formato=json"
    res_bcb = http_client.get(bcb_inf_url, headers=headers, timeout=10)
    res_bcb.raise_for_status()
    br_inflation = float(res_bcb.json()[0]["valor"])
    br_date = "-".join(reversed(res_bcb.json()[0]["data"].split("/")))
    
    # BCB SELIC Risk-Free Rate
    bcb_selic_url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1178/dados/ultimos/1?formato=json"
    res_selic = http_client.get(bcb_selic_url, headers=headers, timeout=10)
    res_selic.raise_for_status()
    br_selic = float(res_selic.json()[0]["valor"])
    
    # 1Y Daily Annualized FX Vol
    df_fx_calc = df_fx_clean.with_columns(
        (pl.col("valor") / pl.col("valor").shift(1) - 1).alias("daily_return")
    ).drop_nulls()
    sigma_fx = df_fx_calc["daily_return"].std() * (252 ** 0.5)
    
    # Sovereign Risk Ratio
    pure_sovereign_risk_ratio = round(sigma_fx / sigma_equity_daily, 4) if sigma_equity_daily else 1.0
    
    # Country Risk Premium
    calculated_crp = round((market_credit_spread / 100) * (1 + pure_sovereign_risk_ratio), 4)
    
    # Fisher Inflation Differential
    inflation_differential = (1 + (br_inflation / 100)) / (1 + (us_inflation / 100))
    
    # Brazil MRP
    total_brazil_mrp = round(((us_mrp / 100) * inflation_differential) + calculated_crp, 4)
    
    br_response = MacroIndicatorsResponse(
        country="Brazil",
        currency="BRL",
        market_risk_premium=total_brazil_mrp,
        components=MacroComponents(
            risk_free_rate_rf=round(br_selic / 100, 4),
            dynamic_country_risk_premium_crp=calculated_crp,
            usd_brl_1y_annualized_vol=round(sigma_fx, 4),
            sp500_1y_annualized_vol=round(sigma_equity_daily, 4),
            pure_sovereign_risk_ratio=pure_sovereign_risk_ratio,
            inflation_yoy=round(br_inflation / 100, 4),
            derived_inflation_differential=round(inflation_differential, 4)
        ),
        reference_period=br_date
    )
    
    return {
        "US": us_response,
        "BR": br_response
    }
