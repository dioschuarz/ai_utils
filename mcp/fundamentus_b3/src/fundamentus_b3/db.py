"""Database utilities for the Fundamentus MCP server."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from fundamentus_b3.config import get_settings


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    settings = get_settings()
    conn = psycopg.connect(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        sslmode=settings.db_sslmode,
        row_factory=dict_row,
    )
    try:
        yield conn
    finally:
        conn.close()


