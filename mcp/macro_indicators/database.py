import os
import time
import json
import logging
from typing import Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

def get_db_connection(max_retries: int = 5, initial_backoff: float = 1.0):
    """Establishes database connection to Supabase with retries and exponential backoff."""
    host = os.getenv("POSTGRES_HOST", "supabase-db")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    dbname = os.getenv("POSTGRES_DB", "postgres")

    backoff = initial_backoff
    for attempt in range(1, max_retries + 1):
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=dbname,
                connect_timeout=5
            )
            logger.info(f"Successfully connected to Supabase DB on {host}:{port}")
            return conn
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt}/{max_retries} failed on {host}:{port}: {e}")
            if attempt == max_retries:
                logger.error("Max database connection retries reached.")
                raise e
            time.sleep(backoff)
            backoff *= 2.0

def save_indicators_to_db(country_code: str, currency: str, mrp: float, rf: float, inflation: float, crp: Optional[float], components: Dict[str, Any], reference_period: str) -> bool:
    """Saves macroeconomic indicators to public.macro_indicators cache table on Supabase."""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO macro_indicators.macro_indicators (
                    country, currency, market_risk_premium, risk_free_rate_rf, inflation_yoy, 
                    dynamic_country_risk_premium_crp, components, reference_period, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, timezone('utc'::text, now()))
                ON CONFLICT (country) DO UPDATE SET
                    currency = EXCLUDED.currency,
                    market_risk_premium = EXCLUDED.market_risk_premium,
                    risk_free_rate_rf = EXCLUDED.risk_free_rate_rf,
                    inflation_yoy = EXCLUDED.inflation_yoy,
                    dynamic_country_risk_premium_crp = EXCLUDED.dynamic_country_risk_premium_crp,
                    components = EXCLUDED.components,
                    reference_period = EXCLUDED.reference_period,
                    updated_at = timezone('utc'::text, now());
                """,
                (
                    country_code, currency, mrp, rf, inflation, crp, 
                    json.dumps(components), reference_period
                )
            )
            conn.commit()
            logger.info(f"Saved macro indicators to Supabase DB for {country_code}")
            return True
    except Exception as e:
        logger.error(f"Failed to save indicators to DB for {country_code}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_indicators_from_db(country_code: str) -> Optional[Dict[str, Any]]:
    """Retrieves the latest available cached macro indicators for a country from Supabase DB."""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT country, currency, market_risk_premium, risk_free_rate_rf, inflation_yoy, 
                       dynamic_country_risk_premium_crp, components, reference_period, updated_at
                FROM macro_indicators.macro_indicators
                WHERE country = %s;
                """,
                (country_code,)
            )
            row = cur.fetchone()
            if row:
                # Convert components back from json string/dict
                if isinstance(row["components"], str):
                    row["components"] = json.loads(row["components"])
                return dict(row)
            return None
    except Exception as e:
        logger.error(f"Failed to retrieve indicators from DB for {country_code}: {e}")
        return None
    finally:
        if conn:
            conn.close()
