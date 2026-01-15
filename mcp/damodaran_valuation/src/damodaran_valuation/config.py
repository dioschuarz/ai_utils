"""Configuration helpers for the Damodaran MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    mcp_host: str
    mcp_port: int
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_sslmode: str
    damodaran_betas_url: str
    damodaran_country_risk_url: str
    damodaran_ratings_url: str
    damodaran_margin_url: str
    damodaran_roc_url: str
    damodaran_roe_url: str
    damodaran_fundgreb_url: str
    damodaran_capex_url: str
    damodaran_wacc_url: str


def get_settings() -> Settings:
    return Settings(
        mcp_host=os.getenv("MCP_HOST", "0.0.0.0"),
        mcp_port=int(os.getenv("MCP_PORT", "8000")),
        db_host=os.getenv("POSTGRES_HOST", "damodaran-db"),
        db_port=int(os.getenv("POSTGRES_PORT", "5433")),
        db_name=os.getenv("POSTGRES_DB", "damodaran"),
        db_user=os.getenv("POSTGRES_USER", "damodaran"),
        db_password=os.getenv("POSTGRES_PASSWORD", "damodaran"),
        db_sslmode=os.getenv("POSTGRES_SSLMODE", "disable"),
        damodaran_betas_url=os.getenv(
            "DAMODARAN_BETAS_URL",
            "https://www.stern.nyu.edu/~adamodar/pc/datasets/betas.xls",
        ),
        damodaran_country_risk_url=os.getenv(
            "DAMODARAN_COUNTRY_RISK_URL",
            "https://www.stern.nyu.edu/~adamodar/pc/datasets/ctryprem.xls",
        ),
        damodaran_ratings_url=os.getenv(
            "DAMODARAN_RATINGS_URL",
            "https://www.stern.nyu.edu/~adamodar/pc/datasets/ratings.xls",
        ),
        damodaran_margin_url=os.getenv(
            "DAMODARAN_MARGIN_URL",
            "https://www.stern.nyu.edu/~adamodar/pc/datasets/margin.xls",
        ),
        damodaran_roc_url=os.getenv(
            "DAMODARAN_ROC_URL",
            "https://www.stern.nyu.edu/~adamodar/pc/datasets/roc.xls",
        ),
        damodaran_roe_url=os.getenv(
            "DAMODARAN_ROE_URL",
            "https://www.stern.nyu.edu/~adamodar/pc/datasets/roe.xls",
        ),
        damodaran_fundgreb_url=os.getenv(
            "DAMODARAN_FUNDGREB_URL",
            "https://www.stern.nyu.edu/~adamodar/pc/datasets/fundgrEB.xls",
        ),
        damodaran_capex_url=os.getenv(
            "DAMODARAN_CAPEX_URL",
            "https://www.stern.nyu.edu/~adamodar/pc/datasets/capex.xls",
        ),
        damodaran_wacc_url=os.getenv(
            "DAMODARAN_WACC_URL",
            "https://www.stern.nyu.edu/~adamodar/pc/datasets/wacc.xls",
        ),
    )

