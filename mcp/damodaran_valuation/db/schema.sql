CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS sector_betas (
    sector_name TEXT PRIMARY KEY,
    unlevered_beta NUMERIC NOT NULL,
    effective_tax_rate NUMERIC NOT NULL,
    avg_de_ratio NUMERIC NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sector_betas_name_trgm
    ON sector_betas USING GIN (sector_name gin_trgm_ops);

CREATE TABLE IF NOT EXISTS country_risk (
    country TEXT PRIMARY KEY,
    equity_risk_premium NUMERIC NOT NULL,
    country_risk_premium NUMERIC NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_country_risk_name_trgm
    ON country_risk USING GIN (country gin_trgm_ops);

CREATE TABLE IF NOT EXISTS synthetic_ratings (
    id SERIAL PRIMARY KEY,
    min_icr NUMERIC,
    max_icr NUMERIC,
    rating TEXT NOT NULL,
    spread NUMERIC NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_synthetic_ratings_range
    ON synthetic_ratings (min_icr, max_icr);

CREATE TABLE IF NOT EXISTS sector_benchmarks (
    sector_name TEXT PRIMARY KEY,
    operating_margin_mean NUMERIC,
    ebitda_margin_mean NUMERIC,
    roic_mean NUMERIC,
    roe_mean NUMERIC,
    cost_of_capital_mean NUMERIC,
    sales_to_capital_mean NUMERIC,
    reinvestment_rate_mean NUMERIC
);

CREATE INDEX IF NOT EXISTS idx_sector_benchmarks_name_trgm
    ON sector_benchmarks USING GIN (sector_name gin_trgm_ops);

