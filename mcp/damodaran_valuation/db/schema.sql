CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS sector_metrics (
    sector_name TEXT PRIMARY KEY,
    unlevered_beta NUMERIC NOT NULL,
    effective_tax_rate NUMERIC NOT NULL,
    avg_de_ratio NUMERIC NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sector_metrics_name_trgm
    ON sector_metrics USING GIN (sector_name gin_trgm_ops);

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

