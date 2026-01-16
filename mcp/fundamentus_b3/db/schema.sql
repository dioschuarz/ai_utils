-- Enable JSONB support (already available in PostgreSQL 16)
-- Create table for B3 stock cache with TTL support

CREATE TABLE IF NOT EXISTS b3_stock_cache (
    ticker TEXT PRIMARY KEY,
    data JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

-- GIN index on JSONB data for efficient searches
CREATE INDEX IF NOT EXISTS idx_b3_stock_cache_data_gin
    ON b3_stock_cache USING GIN (data);

-- Index on expires_at for efficient cleanup queries
CREATE INDEX IF NOT EXISTS idx_b3_stock_cache_expires_at
    ON b3_stock_cache (expires_at);

-- Index on updated_at for monitoring
CREATE INDEX IF NOT EXISTS idx_b3_stock_cache_updated_at
    ON b3_stock_cache (updated_at);

