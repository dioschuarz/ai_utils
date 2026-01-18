"""Ingest Damodaran datasets into Postgres."""

from __future__ import annotations

import io
import re
from typing import Dict, Iterable, Optional, Tuple

import pandas as pd
import requests

from config import get_settings
from db import get_conn


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


def _load_margins(payload: bytes) -> Dict[str, dict]:
    df = pd.read_excel(
        io.BytesIO(payload),
        sheet_name="Industry Averages",
        skiprows=8,
    )
    sector_col = _find_column(df, ["Industry Name", "Industry"])
    op_margin_mean_col = _find_column(
        df,
        [
            "Pre-tax, Pre-stock compensation Operating Margin",
            "Pre-tax Unadjusted Operating Margin",
            "Pre-tax Operating Margin",
            "Pretax Operating Margin",
            "Operating Margin (Pretax)",
        ],
    )
    ebitda_mean_col = _find_column(
        df,
        [
            "EBITDA/Sales",
            "EBITDA / Sales",
            "EBITDA Margin",
        ],
    )

    records: Dict[str, dict] = {}
    for _, row in df.iterrows():
        sector = row.get(sector_col)
        if not isinstance(sector, str):
            continue
        sector = sector.strip()
        if not sector or sector.lower() in {"total", "average"}:
            continue
        key = _normalize_key(sector)
        records[key] = {
            "sector_name": sector,
            "operating_margin_mean": _to_ratio(row.get(op_margin_mean_col)),
            "ebitda_margin_mean": _to_ratio(row.get(ebitda_mean_col)),
        }
    return records


def _load_roc(payload: bytes) -> Dict[str, dict]:
    df = pd.read_excel(
        io.BytesIO(payload),
        sheet_name="Industry Averages",
        skiprows=7,
        header=0,
    )
    sector_col = _find_column(df, ["Industry Name", "Industry"])
    roic_mean_col = _find_column(
        df,
        [
            "Normalized ROIC (last 10 years)",
            "Unadjusted pre-tax ROIC",
            "ROIC",
            "Return on Capital (ROIC)",
        ],
    )
    wacc_mean_col = None
    try:
        wacc_mean_col = _find_column(
            df,
            [
                "Cost of Capital",
                "Cost of Capital (WACC)",
                "WACC",
            ],
        )
    except KeyError:
        pass  # WACC not available

    records: Dict[str, dict] = {}
    for _, row in df.iterrows():
        sector = row.get(sector_col)
        if not isinstance(sector, str):
            continue
        sector = sector.strip()
        if not sector or sector.lower() in {"total", "average"}:
            continue
        key = _normalize_key(sector)
        records[key] = {
            "roic_mean": _to_ratio(row.get(roic_mean_col)) if roic_mean_col else None,
            "cost_of_capital_mean": _to_ratio(row.get(wacc_mean_col)) if wacc_mean_col else None,
        }
    return records


def _load_capex(payload: bytes) -> Dict[str, dict]:
    """Load Sales/Capital and Reinvestment Rate from capex.xls file."""
    df = pd.read_excel(
        io.BytesIO(payload),
        sheet_name="Industry Averages",
        skiprows=7,
        header=0,
    )
    sector_col = _find_column(df, ["Industry Name", "Industry"])
    
    # Sales/Capital pode estar em diferentes formatos no capex.xls
    sales_cap_mean_col = None
    try:
        sales_cap_mean_col = _find_column(
            df,
            [
                "Sales/ Invested Capital (LTM)",
                "Sales/Invested Capital (LTM)",
                "Sales/Capital Ratio",
                "Sales to Capital",
                "Sales/Capital",
                "Sales to Invested Capital",
                "Sales/Invested Capital",
            ],
        )
    except KeyError:
        pass  # Pode não estar disponível
    
    # Reinvestment Rate
    reinvest_mean_col = None
    try:
        reinvest_mean_col = _find_column(
            df,
            [
                "Reinvestment Rate",
                "Reinvestment rate",
                "Reinvestment",
            ],
        )
    except KeyError:
        pass
    

    records: Dict[str, dict] = {}
    for _, row in df.iterrows():
        sector = row.get(sector_col)
        if not isinstance(sector, str):
            continue
        sector = sector.strip()
        if not sector or sector.lower() in {"total", "average"}:
            continue
        key = _normalize_key(sector)
        records[key] = {
            "sales_to_capital_mean": _to_float(row.get(sales_cap_mean_col)) if sales_cap_mean_col else None,
            "reinvestment_rate_mean": _to_ratio(row.get(reinvest_mean_col)) if reinvest_mean_col else None,
        }
    return records


def _load_wacc(payload: bytes) -> Dict[str, dict]:
    """Load WACC (Cost of Capital) benchmarks from wacc.xls."""
    # WACC tem header na linha 17 (skiprows=17), mas o header está na linha 1 dos dados
    df = pd.read_excel(
        io.BytesIO(payload),
        sheet_name="Industry Averages",
        skiprows=17,
        header=None,
    )
    # Linha 1 (índice 1) tem os nomes das colunas
    df.columns = df.iloc[1]
    df = df[2:]  # Pular linha 0 (vazia) e linha 1 (header)
    sector_col = _find_column(df, ["Industry Name", "Industry"])
    
    wacc_mean_col = None
    try:
        wacc_mean_col = _find_column(
            df,
            [
                "Cost of Capital (Local Currency)",
                "Cost of Capital",
                "WACC",
                "Weighted Average Cost of Capital",
                "Cost of Capital (WACC)",
            ],
        )
    except KeyError:
        pass
    
    records: Dict[str, dict] = {}
    for _, row in df.iterrows():
        sector = row.get(sector_col)
        if not isinstance(sector, str):
            continue
        sector = sector.strip()
        if not sector or sector.lower() in {"total", "average"}:
            continue
        key = _normalize_key(sector)
        records[key] = {
            "cost_of_capital_mean": _to_ratio(row.get(wacc_mean_col)) if wacc_mean_col else None,
        }
    return records


def _load_roe(payload: bytes) -> Dict[str, dict]:
    """Load ROE benchmarks from roe.xls (adjusted for R&D when available)."""
    df = pd.read_excel(
        io.BytesIO(payload),
        sheet_name="Industry Averages",
        skiprows=7,
        header=0,
    )
    sector_col = _find_column(df, ["Industry Name", "Industry"])

    roe_col = None
    try:
        roe_col = _find_column(
            df,
            [
                "ROE (adjusted for R&D)",
                "ROE (unadjusted)",
                "ROE",
                "Return on Equity",
            ],
        )
    except KeyError:
        pass

    records: Dict[str, dict] = {}
    for _, row in df.iterrows():
        sector = row.get(sector_col)
        if not isinstance(sector, str):
            continue
        sector = sector.strip()
        if not sector or sector.lower() in {"total", "average"}:
            continue
        key = _normalize_key(sector)
        records[key] = {
            "roe_mean": _to_ratio(row.get(roe_col)) if roe_col else None,
        }
    return records


def _load_reinvestment(payload: bytes) -> Dict[str, dict]:
    """Load reinvestment rate (fundamental growth in EBIT) from fundgrEB.xls."""
    df = pd.read_excel(
        io.BytesIO(payload),
        sheet_name="Industry Averages",
        skiprows=7,
        header=0,
    )
    sector_col = _find_column(df, ["Industry Name", "Industry"])
    reinvest_col = _find_column(df, ["Reinvestment Rate", "Reinvestment rate"])

    records: Dict[str, dict] = {}
    for _, row in df.iterrows():
        sector = row.get(sector_col)
        if not isinstance(sector, str):
            continue
        sector = sector.strip()
        if not sector or sector.lower() in {"total", "average"}:
            continue
        key = _normalize_key(sector)
        records[key] = {
            "reinvestment_rate_mean": _to_ratio(row.get(reinvest_col)),
        }
    return records


def _merge_benchmarks(
    margins: Dict[str, dict],
    roc: Dict[str, dict],
    capex: Dict[str, dict],
    wacc: Dict[str, dict] = None,
    roe: Dict[str, dict] = None,
    reinvest: Dict[str, dict] = None,
) -> list[dict]:
    """Merge benchmark data from multiple sources."""
    if wacc is None:
        wacc = {}
    if roe is None:
        roe = {}
    if reinvest is None:
        reinvest = {}
    
    records: list[dict] = []
    for key, margin_row in margins.items():
        roc_row = roc.get(key)
        # Require at least margins and roc
        if not roc_row:
            continue
        
        # Merge all available data
        merged = {**margin_row, **roc_row}
        
        # Adicionar dados de capex se disponíveis (Sales/Capital)
        capex_row = capex.get(key) if capex else {}
        if capex_row:
            merged.update(capex_row)
        else:
            # Defaults para campos de capex
            merged.setdefault("sales_to_capital_mean", None)
        
        # Adicionar WACC se disponível (sobrescreve o None do ROC se houver)
        wacc_row = wacc.get(key) if wacc else {}
        if wacc_row:
            # WACC do arquivo wacc.xls tem prioridade sobre o None do ROC
            if wacc_row.get("cost_of_capital_mean") is not None:
                merged["cost_of_capital_mean"] = wacc_row["cost_of_capital_mean"]

        # Adicionar ROE se disponível
        roe_row = roe.get(key) if roe else {}
        if roe_row and roe_row.get("roe_mean") is not None:
            merged["roe_mean"] = roe_row["roe_mean"]
        else:
            merged.setdefault("roe_mean", None)

        # Adicionar reinvestment rate se disponível (fundgrEB tem prioridade)
        reinvest_row = reinvest.get(key) if reinvest else {}
        if reinvest_row and reinvest_row.get("reinvestment_rate_mean") is not None:
            merged["reinvestment_rate_mean"] = reinvest_row["reinvestment_rate_mean"]
        else:
            merged.setdefault("reinvestment_rate_mean", None)
        
        records.append(merged)
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
    margin_payload = _download_excel(settings.damodaran_margin_url)
    roc_payload = _download_excel(settings.damodaran_roc_url)
    
    # Carregar capex (substitui salescap)
    capex = {}
    try:
        capex_payload = _download_excel(settings.damodaran_capex_url)
        capex = _load_capex(capex_payload)
    except Exception as e:
        print(f"Warning: Could not load capex dataset: {e}")
    
    # Carregar WACC (opcional, mas recomendado)
    wacc = {}
    try:
        wacc_payload = _download_excel(settings.damodaran_wacc_url)
        wacc = _load_wacc(wacc_payload)
    except Exception as e:
        print(f"Warning: Could not load wacc dataset: {e}")

    # Carregar ROE
    roe = {}
    try:
        roe_payload = _download_excel(settings.damodaran_roe_url)
        roe = _load_roe(roe_payload)
    except Exception as e:
        print(f"Warning: Could not load roe dataset: {e}")

    # Carregar Reinvestment Rate (fundamental growth em EBIT)
    reinvest = {}
    try:
        fundgreb_payload = _download_excel(settings.damodaran_fundgreb_url)
        reinvest = _load_reinvestment(fundgreb_payload)
    except Exception as e:
        print(f"Warning: Could not load fundgrEB dataset: {e}")

    betas = _load_betas(betas_payload)
    countries = _load_country_risk(country_payload)
    ratings = _load_synthetic_ratings(ratings_payload)
    margins = _load_margins(margin_payload)
    roc = _load_roc(roc_payload)
    
    # Merge incluindo WACC, ROE e Reinvestment Rate (fundgrEB)
    benchmarks = _merge_benchmarks(margins, roc, capex, wacc, roe, reinvest)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "TRUNCATE sector_betas, sector_benchmarks, country_risk, synthetic_ratings;"
            )
            cur.executemany(
                """
                INSERT INTO sector_betas
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
            cur.executemany(
                """
                INSERT INTO sector_benchmarks
                    (
                        sector_name,
                        operating_margin_mean,
                        ebitda_margin_mean,
                        roic_mean,
                        roe_mean,
                        cost_of_capital_mean,
                        sales_to_capital_mean,
                        reinvestment_rate_mean
                    )
                VALUES (
                    %(sector_name)s,
                    %(operating_margin_mean)s,
                    %(ebitda_margin_mean)s,
                    %(roic_mean)s,
                    %(roe_mean)s,
                    %(cost_of_capital_mean)s,
                    %(sales_to_capital_mean)s,
                    %(reinvestment_rate_mean)s
                )
                """,
                benchmarks,
            )
        conn.commit()


def main() -> None:
    ingest()


if __name__ == "__main__":
    main()
