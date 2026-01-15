# Damodaran MCP Valuation Server

FastMCP server exposing Damodaran valuation tools backed by a local Postgres cache.

## Services
- MCP server (SSE): `http://localhost:8000`
- Postgres (host): `localhost:5433` → container `5432`

## Environment
Create a `.env` file in this folder with:

```
MCP_HOST=0.0.0.0
MCP_PORT=8000

POSTGRES_HOST=damodaran-db
POSTGRES_PORT=5432
POSTGRES_DB=damodaran
POSTGRES_USER=damodaran
POSTGRES_PASSWORD=damodaran
POSTGRES_SSLMODE=disable

DAMODARAN_BETAS_URL=https://www.stern.nyu.edu/~adamodar/pc/datasets/betas.xls
DAMODARAN_COUNTRY_RISK_URL=https://www.stern.nyu.edu/~adamodar/pc/datasets/ctryprem.xls
DAMODARAN_RATINGS_URL=https://www.stern.nyu.edu/~adamodar/pc/datasets/ratings.xls
DAMODARAN_MARGIN_URL=https://www.stern.nyu.edu/~adamodar/pc/datasets/margin.xls
DAMODARAN_ROC_URL=https://www.stern.nyu.edu/~adamodar/pc/datasets/roc.xls
DAMODARAN_SALESCAP_URL=https://www.stern.nyu.edu/~adamodar/pc/datasets/salescap.xls
```

## Build and Run (Docker)
1. Ensure the external network exists:

```
docker network create investment-net
```

2. Start services:

```
docker compose -f /home/ds/projects/ai_utils/mcp/damodaran_valuation/docker-compose.yml up --build
```

## Ingestion
Run ingestion after the DB is up:

```
docker compose -f /home/ds/projects/ai_utils/mcp/damodaran_valuation/docker-compose.yml run --rm damodaran-mcp \
  python -m damodaran_valuation.ingestion
```

## Tools
- `get_sector_metrics(sector_name)`
- `get_country_risk_premium(country)`
- `calculate_levered_beta(sector_name, current_de_ratio)`
- `get_synthetic_spread(interest_coverage_ratio)`
- `get_sector_benchmarks(sector_name)`

