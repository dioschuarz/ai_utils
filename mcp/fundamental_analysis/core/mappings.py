"""ISIC Taxonomy mappings and dynamic cache resolver."""

import os
import csv
import logging
import re
from typing import Dict, List, Optional, Any
from rapidfuzz import fuzz
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


class TaxonomyInitializationError(Exception):
    """Raised when the taxonomy cache fails to initialize from both DB and CSV."""
    pass


class TaxonomyLookupError(ValueError):
    """Raised when an exact match lookup is performed for an ISIC code that does not exist."""
    pass


# Temporary empty stub to prevent intermediate integration crashes
GICS_MAPPINGS: Dict[str, Any] = {}


def normalize_sector(sector: str) -> str:
    """Normalize sector names to standard keys."""
    if not sector:
        return ""
    s = sector.lower().strip()
    if "tech" in s:
        return "InfoTech"
    if "health" in s:
        return "HealthCare"
    if "financial" in s:
        return "Financials"
    if "basic" in s or "material" in s:
        return "Materials"
    if "defensive" in s or "staple" in s:
        return "Cons Stap"
    if "cyclical" in s or "discretionary" in s:
        return "Cons Disc"
    if "comm" in s:
        return "Comm Serv"
    if "industrial" in s:
        return "Indust"
    if "energy" in s:
        return "Energy"
    if "estate" in s:
        return "Real Estate"
    if "utility" in s or "utilities" in s:
        return "Utilities"
    return sector.title().strip()


def _get_db_connection_url() -> Optional[str]:
    """Resolve database URL. Handles host/container name swap for local access."""
    url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_POSTGRES_URL")
    if not url:
        return None
    if not os.path.exists("/.dockerenv") and "supabase-db" in url:
        url = url.replace("supabase-db:5432", "localhost:54322")
    return url


def _load_from_db() -> Dict[str, Dict[str, Any]]:
    """Query the taxonomy rows from Supabase."""
    db_url = _get_db_connection_url()
    if not db_url:
        raise ValueError("No database URL configured in environment.")

    engine = create_engine(db_url, connect_args={"connect_timeout": 3})
    data = {}
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT isic_code, isic_description, division_code, division_description, "
            "group_code, group_description, class_code, class_description, "
            "primary_method_1, primary_method_2, supporting_method_1, supporting_method_2, "
            "sensitivity_method, valuation_rationale, us_stocks, br_stocks "
            "FROM isic_taxonomy.isic_rev5_taxonomy"
        ))
        columns = list(result.keys())
        for row in result:
            row_dict = dict(zip(columns, row))
            code = str(row_dict["isic_code"]).strip().zfill(4)
            row_dict["isic_code"] = code
            data[code] = row_dict
    return data


def _load_from_csv() -> Dict[str, Dict[str, Any]]:
    """Parse local fallback CSV copy."""
    dir_path = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(dir_path, "isic_rev5_taxonomy.csv")
    if not os.path.exists(csv_path):
        # Fallback to backend seeds path
        csv_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(dir_path))),
            "backend", "db", "seeds", "isic_rev5_taxonomy.csv"
        )
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Local CSV fallback file not found at {csv_path}")

    data = {}
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f, skipinitialspace=True, doublequote=True)
        for row in reader:
            clean_row = {}
            for k, v in row.items():
                if k in ("section_code", "section_description"):
                    continue
                if v is not None:
                    v = v.strip()
                    if v == "":
                        v = None
                clean_row[k] = v

            code = clean_row.get("isic_code")
            if code:
                code = str(code).strip().zfill(4)
                clean_row["isic_code"] = code
                data[code] = clean_row
    return data


class ISICCache:
    """In-memory singleton cache loader for ISIC Rev 5 taxonomy."""
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ISICCache, cls).__new__(cls)
            cls._instance._data = {}
            cls._instance._initialized = False
        return cls._instance

    def initialize(self):
        if self._initialized:
            return

        # Try database first
        try:
            logger.info("Attempting to load ISIC taxonomy from database...")
            self._data = _load_from_db()
            self._initialized = True
            logger.info(f"Successfully loaded {len(self._data)} ISIC codes from database.")
            return
        except Exception as e:
            logger.warning(f"Failed to load ISIC taxonomy from database: {e}. Falling back to local CSV...")

        # Fall back to CSV
        try:
            self._data = _load_from_csv()
            self._initialized = True
            logger.info(f"Successfully loaded {len(self._data)} ISIC codes from fallback CSV.")
        except Exception as e:
            logger.error(f"Failed to load ISIC taxonomy from fallback CSV: {e}")
            raise TaxonomyInitializationError(
                f"Failed to initialize ISIC taxonomy from both database and CSV: {e}"
            ) from e

    def get_row(self, isic_code: str) -> Dict[str, Any]:
        """Get taxonomy row by exact ISIC code match. Raises error if missing."""
        self.initialize()
        if isic_code not in self._data:
            raise TaxonomyLookupError(f"ISIC code {isic_code} not found in taxonomy.")
        return self._data[isic_code]

    def get_all_rows(self) -> Dict[str, Dict[str, Any]]:
        """Retrieve all taxonomy rows."""
        self.initialize()
        return self._data


STOPWORDS = {"and", "or", "of", "for", "in", "on", "at", "with", "by", "to", "activities", "services", "manufacturing", "other", "n.e.c."}


def _clean_text_for_matching(text: str) -> str:
    """Clean text by removing punctuation, casing, and stopwords."""
    if not text:
        return ""
    words = re.findall(r'\w+', text.lower())
    filtered_words = [w for w in words if w not in STOPWORDS]
    return " ".join(filtered_words)


def resolve_isic_code(sector: str, industry: str) -> Optional[str]:
    """
    Resolves an ISIC Rev 5 code from sector and industry.
    Runs case-insensitive exact matching first, then fuzzy matching.
    """
    if not sector and not industry:
        return None

    # Handle financials/banks explicitly to avoid fuzzy pluralization mismatch
    sec_lower = (sector or "").lower()
    ind_lower = (industry or "").lower()
    if "financial" in sec_lower or "bank" in ind_lower or "monetary" in ind_lower or "insurance" in ind_lower:
        if "bank" in ind_lower or "monetary" in ind_lower:
            return "6411"
        return "6499"
    if "energy" in sec_lower or "oil" in ind_lower or "gas" in ind_lower or "petroleum" in ind_lower:
        return "0610"

    cache = ISICCache()
    all_rows = cache.get_all_rows()

    # 1. Case-insensitive exact match against class_description or isic_description
    if industry:
        ind_clean = industry.strip().lower()
        for code, row in all_rows.items():
            class_desc = (row.get("class_description") or "").strip().lower()
            isic_desc = (row.get("isic_description") or "").strip().lower()
            if ind_clean == class_desc or ind_clean == isic_desc:
                return code

    # 2. Fuzzy match against taxonomy descriptions using rapidfuzz token_set_ratio
    search_query = f"{industry or ''} {sector or ''}"
    clean_query = _clean_text_for_matching(search_query)

    best_code = None
    best_score = 0.0

    for code, row in all_rows.items():
        descs = [
            row.get("class_description") or "",
            row.get("group_description") or "",
            row.get("division_description") or "",
            row.get("isic_description") or ""
        ]

        row_best_score = 0.0
        for desc in descs:
            if not desc:
                continue
            clean_desc = _clean_text_for_matching(desc)
            if not clean_desc:
                continue
            score = fuzz.token_set_ratio(clean_query, clean_desc) / 100.0
            if score > row_best_score:
                row_best_score = score

        if row_best_score > best_score:
            best_score = row_best_score
            best_code = code

    if best_score >= 0.70:
        return best_code

    # 3. Fallback: Division-level description matching or default first class
    if sector or industry:
        best_div_code = None
        best_div_score = 0.0
        for code, row in all_rows.items():
            div_desc = row.get("division_description") or ""
            if not div_desc:
                continue
            clean_div = _clean_text_for_matching(div_desc)
            score = fuzz.token_set_ratio(clean_query, clean_div) / 100.0
            if score > best_div_score:
                best_div_score = score
                best_div_code = code
        if best_div_score >= 0.50:
            return best_div_code

    return "0111"


def find_gics_sub_industry(sector: str, industry: str) -> Optional[str]:
    """Compatibility bridge to resolve_isic_code."""
    return resolve_isic_code(sector, industry)


def get_isic_suggestions(invalid_code: str, query: str = None) -> List[Dict[str, str]]:
    """
    Generate top 3 to 5 closest matches for suggestions.
    Formats suggestions to include both the code and class description.
    """
    cache = ISICCache()
    all_rows = cache.get_all_rows()

    search_query = query or invalid_code
    if not search_query:
        return []

    clean_query = _clean_text_for_matching(search_query)
    scored_matches = []

    for code, row in all_rows.items():
        descs = [
            row.get("class_description") or "",
            row.get("isic_description") or ""
        ]

        row_best_score = 0.0
        for desc in descs:
            if not desc:
                continue
            clean_desc = _clean_text_for_matching(desc)
            if not clean_desc:
                continue
            score = fuzz.token_set_ratio(clean_query, clean_desc) / 100.0
            if score > row_best_score:
                row_best_score = score

        class_desc = row.get("class_description") or row.get("isic_description") or ""
        scored_matches.append((code, row_best_score, class_desc))

    scored_matches.sort(key=lambda x: x[1], reverse=True)
    top_matches = scored_matches[:5]

    return [
        {
            "isic_code": code,
            "class_description": f"{code} - {desc}"
        }
        for code, score, desc in top_matches
    ]
