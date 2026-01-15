"""Ingest Damodaran datasets into Postgres."""

from __future__ import annotations

import io
import re
from typing import Iterable, Optional, Tuple

import pandas as pd
import requests

from damodaran_valuation.config import get_settings
from damodaran_valuation.db import get_conn


def _download_excel(url: str) -> bytes:
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.content


def _normalize_key(value: object) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _find_column(df: pd.DataFrame, candidates: Iterable[str]) -> str:
    normalized_map = {_normalize_key(col): col for col in df.columns}
    for candidate in candidates:
        key = _normalize_key(candidate)
        if key in normalized_map:
            return normalized_map[key]
    raise KeyError(f"Missing columns, tried: {', '.join(candidates)}")


def _to_float(value) -> Optional[float]:
    if pd.isna(value):
        return None
    if isinstance(value, str):
        cleaned = value.strip().replace("%", "")
        cleaned = cleaned.replace(",", "")
        if cleaned in {"", "NA", "N/A", "-"}:
            return None
        value = cleaned
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_ratio(value) -> Optional[float]:
    numeric = _to_float(value)
    if numeric is None:
        return None
    if numeric > 1.0:
        return numeric / 100.0
    return numeric


def _load_betas(payload: bytes) -> list[dict]:
    df = pd.read_excel(
        io.BytesIO(payload),
        sheet_name="Industry Averages",
        skiprows=9,
    )
    sector_col = _find_column(df, ["Industry Name", "Industry"])
    beta_col = _find_column(df, ["Unlevered beta", "Unlevered Beta"])
    tax_col = _find_column(df, ["Effective Tax Rate", "Effective Tax rate", "Tax Rate"])
    de_col = _find_column(
        df,
        [
            "Average D/E Ratio",
            "Average D/E",
            "Average Debt/Equity Ratio",
            "Debt/Equity",
            "D/E Ratio",
            "D/E",
        ],
    )

    records: list[dict] = []
    for _, row in df.iterrows():
        sector = row.get(sector_col)
        if not isinstance(sector, str):
            continue
        sector = sector.strip()
        if not sector or sector.lower() in {"total", "average"}:
            continue
        beta = _to_float(row.get(beta_col))
        tax = _to_ratio(row.get(tax_col))
        de_ratio = _to_ratio(row.get(de_col))
        if beta is None or tax is None or de_ratio is None:
            continue
        records.append(
            {
                "sector_name": sector,
                "unlevered_beta": beta,
                "effective_tax_rate": tax,
                "avg_de_ratio": de_ratio,
            }
        )
    return records


def _load_country_risk(payload: bytes) -> list[dict]:
    df = pd.read_excel(
        io.BytesIO(payload),
        sheet_name="ERPs by country",
        skiprows=7,
    )
    country_col = _find_column(df, ["Country"])
    erp_col = _find_column(
        df,
        [
            "Total Equity Risk Premium",
            "Equity Risk Premium",
            "ERP",
            "Equity Risk Premium (ERP)",
        ],
    )
    crp_col = _find_column(
        df,
        [
            "Country Risk Premium",
            "Country Risk Premium3",
            "CRP",
            "Country risk premium",
        ],
    )

    records: list[dict] = []
    for _, row in df.iterrows():
        country = row.get(country_col)
        if not isinstance(country, str):
            continue
        country = country.strip()
        if not country:
            continue
        erp = _to_ratio(row.get(erp_col))
        crp = _to_ratio(row.get(crp_col))
        if erp is None or crp is None:
            continue
        records.append(
            {
                "country": country,
                "equity_risk_premium": erp,
                "country_risk_premium": crp,
            }
        )
    return records


def _parse_icr_range(value) -> Tuple[Optional[float], Optional[float]]:
    if pd.isna(value):
        return None, None
    text = str(value).strip()
    if not text:
        return None, None

    text = text.replace("≥", ">=").replace("≤", "<=")
    match = re.search(r"(-?\d+(\.\d+)?)", text)
    if not match:
        return None, None

    if ">=" in text or ">" in text or "greater" in text:
        return float(match.group(1)), None
    if "<=" in text or "<" in text or "less" in text:
        return None, float(match.group(1))

    if "to" in text:
        parts = re.split(r"\s+to\s+", text, maxsplit=1)
        if len(parts) == 2:
            return _to_float(parts[0]), _to_float(parts[1])

    if "-" in text:
        parts = text.split("-", maxsplit=1)
        if len(parts) == 2:
            return _to_float(parts[0]), _to_float(parts[1])

    return _to_float(text), _to_float(text)


def _load_synthetic_ratings(payload: bytes) -> list[dict]:
    df = pd.read_excel(io.BytesIO(payload), sheet_name="Start here Ratings sheet", header=None)

    records: list[dict] = []
    collecting = False
    for _, row in df.iterrows():
        lower = _to_float(row.get(0))
        upper = _to_float(row.get(1))
        rating = row.get(2)
        spread = _to_ratio(row.get(3))

        is_candidate = (
            lower is not None
            and upper is not None
            and isinstance(rating, str)
            and rating.strip() != ""
            and spread is not None
        )

        if is_candidate and not collecting:
            collecting = True

        if collecting:
            if not is_candidate:
                break
            records.append(
                {
                    "min_icr": lower,
                    "max_icr": upper,
                    "rating": rating.strip(),
                    "spread": spread,
                }
            )

    return records


def ingest() -> None:
    settings = get_settings()
    betas_payload = _download_excel(settings.damodaran_betas_url)
    country_payload = _download_excel(settings.damodaran_country_risk_url)
    ratings_payload = _download_excel(settings.damodaran_ratings_url)

    betas = _load_betas(betas_payload)
    countries = _load_country_risk(country_payload)
    ratings = _load_synthetic_ratings(ratings_payload)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE sector_metrics, country_risk, synthetic_ratings;")
            cur.executemany(
                """
                INSERT INTO sector_metrics
                    (sector_name, unlevered_beta, effective_tax_rate, avg_de_ratio)
                VALUES (%(sector_name)s, %(unlevered_beta)s, %(effective_tax_rate)s, %(avg_de_ratio)s)
                """,
                betas,
            )
            cur.executemany(
                """
                INSERT INTO country_risk
                    (country, equity_risk_premium, country_risk_premium)
                VALUES (%(country)s, %(equity_risk_premium)s, %(country_risk_premium)s)
                """,
                countries,
            )
            cur.executemany(
                """
                INSERT INTO synthetic_ratings
                    (min_icr, max_icr, rating, spread)
                VALUES (%(min_icr)s, %(max_icr)s, %(rating)s, %(spread)s)
                """,
                ratings,
            )
        conn.commit()


def main() -> None:
    ingest()


if __name__ == "__main__":
    main()

