from pydantic import BaseModel, Field
from typing import Dict, Optional

class MacroComponents(BaseModel):
    risk_free_rate_rf: float = Field(description="The risk-free rate of the country (e.g. 0.045 for 4.5%)")
    market_credit_spread: Optional[float] = Field(None, description="The corporate credit spread (e.g. BAA - 10Y)")
    capital_structure_multiplier: Optional[float] = Field(None, description="The structural multiplier derived from equity/bond vol ratio")
    inflation_yoy: float = Field(description="Year-over-year inflation rate (e.g. CPI for US, IPCA for BR)")
    dynamic_country_risk_premium_crp: Optional[float] = Field(None, description="Country Risk Premium for emerging markets (Brazil only)")
    usd_brl_1y_annualized_vol: Optional[float] = Field(None, description="USD/BRL exchange rate volatility (Brazil only)")
    sp500_1y_annualized_vol: Optional[float] = Field(None, description="S&P 500 annualized volatility (Brazil only)")
    pure_sovereign_risk_ratio: Optional[float] = Field(None, description="Exchange rate vol vs US equity vol ratio (Brazil only)")
    derived_inflation_differential: Optional[float] = Field(None, description="Fisher inflation differential (Brazil only)")

class MacroIndicatorsResponse(BaseModel):
    country: str = Field(description="Country name (e.g. 'USA', 'Brazil')")
    currency: str = Field(description="Primary currency code (e.g. 'USD', 'BRL')")
    market_risk_premium: float = Field(description="The calculated equity risk premium (e.g. 0.053 for 5.3%)")
    components: MacroComponents = Field(description="Breakdown of individual components and intermediate outputs")
    reference_period: str = Field(description="The latest date/period represented by the data (ISO format: YYYY-MM-DD)")
