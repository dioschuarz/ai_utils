"""FastMCP server exposing Damodaran valuation tools."""

from __future__ import annotations

from typing import Any, Dict

import psycopg
from mcp.server.fastmcp import FastMCP

from damodaran_valuation.config import get_settings
from damodaran_valuation.db import get_conn

_settings = get_settings()
mcp = FastMCP(
    "damodaran-valuation",
    host=_settings.mcp_host,
    port=_settings.mcp_port,
)


def _fetchone(query: str, params: tuple[Any, ...]) -> Dict[str, Any] | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _normalized_column_expr(column: str) -> str:
    return f"LOWER(REGEXP_REPLACE({column}, '[^a-z0-9]+', ' ', 'g'))"


def _similarity_lookup(table: str, column: str, value: str) -> Dict[str, Any] | None:
    normalized = _normalize_text(value)
    # Prefer exact match (case/space insensitive) before fuzzy matching.
    exact = _fetchone(
        f"""
        SELECT *
        FROM {table}
        WHERE {_normalized_column_expr(column)} = %s
        LIMIT 1
        """,
        (normalized,),
    )
    if exact:
        return exact
    try:
        return _fetchone(
            f"""
            SELECT *
            FROM {table}
            ORDER BY similarity({column}, %s) DESC
            LIMIT 1
            """,
            (value,),
        )
    except psycopg.errors.UndefinedFunction:
        return _fetchone(
            f"""
            SELECT *
            FROM {table}
            WHERE {column} ILIKE %s
            ORDER BY LENGTH({column}) ASC
            LIMIT 1
            """,
            (f"%{value}%",),
        )


def _maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


@mcp.tool()
def get_sector_metrics(sector_name: str) -> Dict[str, Any]:
    """Return sector unlevered beta, tax rate, and average D/E ratio."""
    row = _similarity_lookup("sector_betas", "sector_name", sector_name)
    if not row:
        return {"error": f"Sector not found: {sector_name}"}
    return {
        "sector_name": row["sector_name"],
        "unlevered_beta": float(row["unlevered_beta"]),
        "effective_tax_rate": float(row["effective_tax_rate"]),
        "average_de_ratio": float(row["avg_de_ratio"]),
    }


@mcp.tool()
def get_country_risk_premium(country: str) -> Dict[str, Any]:
    """Return equity risk premium and country risk premium for a country."""
    row = _similarity_lookup("country_risk", "country", country)
    if not row:
        return {"error": f"Country not found: {country}"}
    return {
        "country": row["country"],
        "equity_risk_premium": float(row["equity_risk_premium"]),
        "country_risk_premium": float(row["country_risk_premium"]),
    }


@mcp.tool()
def calculate_levered_beta(sector_name: str, current_de_ratio: float) -> Dict[str, Any]:
    """Apply Hamada formula using sector unlevered beta and tax rate."""
    row = _similarity_lookup("sector_betas", "sector_name", sector_name)
    if not row:
        return {"error": f"Sector not found: {sector_name}"}
    beta_u = float(row["unlevered_beta"])
    tax = float(row["effective_tax_rate"])
    beta_l = beta_u * (1 + (1 - tax) * current_de_ratio)
    return {
        "sector_name": row["sector_name"],
        "unlevered_beta": beta_u,
        "effective_tax_rate": tax,
        "current_de_ratio": current_de_ratio,
        "levered_beta": beta_l,
    }


@mcp.tool()
def get_synthetic_spread(interest_coverage_ratio: float) -> Dict[str, Any]:
    """Return rating and spread for the ICR interval containing the input."""
    row = _fetchone(
        """
        SELECT rating, spread, min_icr, max_icr
        FROM synthetic_ratings
        WHERE (%s >= min_icr OR min_icr IS NULL)
          AND (%s < max_icr OR max_icr IS NULL)
        ORDER BY min_icr DESC NULLS LAST
        LIMIT 1
        """,
        (interest_coverage_ratio, interest_coverage_ratio),
    )
    if not row:
        return {"error": f"No spread found for ICR: {interest_coverage_ratio}"}
    return {
        "rating": row["rating"],
        "spread": float(row["spread"]),
        "min_icr": None if row["min_icr"] is None else float(row["min_icr"]),
        "max_icr": None if row["max_icr"] is None else float(row["max_icr"]),
    }


@mcp.tool()
def get_sector_benchmarks(sector_name: str) -> Dict[str, Any]:
    """Return benchmark metrics for a sector (means only)."""
    row = _similarity_lookup("sector_benchmarks", "sector_name", sector_name)
    if not row:
        return {"error": f"Sector not found: {sector_name}"}
    return {
        "sector_name": row["sector_name"],
        "operating_margin_mean": _maybe_float(row["operating_margin_mean"]),
        "ebitda_margin_mean": _maybe_float(row["ebitda_margin_mean"]),
        "roic_mean": _maybe_float(row["roic_mean"]),
        "roe_mean": _maybe_float(row["roe_mean"]),
        "cost_of_capital_mean": _maybe_float(row["cost_of_capital_mean"]),
        "sales_to_capital_mean": _maybe_float(row["sales_to_capital_mean"]),
        "reinvestment_rate_mean": _maybe_float(row["reinvestment_rate_mean"]),
    }


def main() -> None:
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()

