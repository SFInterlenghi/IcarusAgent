"""Read-only SQLite query tools for the IEE knowledge base.

These are plain Python functions (no ADK dependency) — they will be wrapped
as ADK FunctionTools in Sprint 4. All functions return empty values on miss
and never raise exceptions.
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager


def _db_path() -> Path:
    from config.settings import settings
    return settings.DB_PATH


@contextmanager
def _conn(db_path: Path | None = None):
    path = db_path or _db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def _citation(chapter: int, category_code: str, item_symbol: str) -> str:
    return f"Ch.{chapter}/{category_code}/{item_symbol}"


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------

def lookup_category(code: str, db_path: Path | None = None) -> dict:
    """Return metadata for an equipment category by its 2-letter IEE code.

    Returns an empty dict if the code is not in the KB.
    """
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT code, name, chapter, page FROM equipment_category WHERE code = ?",
            (code.upper(),),
        ).fetchone()
    if row is None:
        return {}
    return dict(row)


def list_items(category_code: str, db_path: Path | None = None) -> list[dict]:
    """Return all equipment items for a category code (e.g. 'AG').

    Each entry contains: item_symbol, description, page, citation.
    Returns an empty list if the category code is unknown.
    """
    with _conn(db_path) as conn:
        cat = conn.execute(
            "SELECT chapter FROM equipment_category WHERE code = ?",
            (category_code.upper(),),
        ).fetchone()
        if cat is None:
            return []
        chapter = cat["chapter"]
        rows = conn.execute(
            "SELECT id, item_symbol, description, page "
            "FROM equipment_item WHERE category_code = ? ORDER BY id",
            (category_code.upper(),),
        ).fetchall()

    return [
        {
            "item_symbol": r["item_symbol"],
            "description": r["description"],
            "page": r["page"],
            "citation": _citation(chapter, category_code.upper(), r["item_symbol"]),
        }
        for r in rows
    ]


def get_item_detail(
    item_symbol: str,
    category_code: str | None = None,
    db_path: Path | None = None,
) -> dict:
    """Return full detail for an equipment item including materials and bounds.

    Args:
        item_symbol:   IEE item symbol, e.g. "MIXER" or "ANCHOR REV".
        category_code: Optional 2-letter category code to disambiguate symbols
                       that appear in multiple categories (e.g. PORT PROP in AG and MX).
        db_path:       Override DB path (used in tests).

    Returns a dict with keys: item_symbol, category_code, description, page,
    citation, materials, bounds. Returns an empty dict if not found.
    """
    with _conn(db_path) as conn:
        if category_code:
            row = conn.execute(
                "SELECT ei.id, ei.item_symbol, ei.category_code, ei.description, ei.page, "
                "       ec.chapter "
                "FROM equipment_item ei "
                "JOIN equipment_category ec ON ec.code = ei.category_code "
                "WHERE ei.item_symbol = ? AND ei.category_code = ?",
                (item_symbol.upper(), category_code.upper()),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT ei.id, ei.item_symbol, ei.category_code, ei.description, ei.page, "
                "       ec.chapter "
                "FROM equipment_item ei "
                "JOIN equipment_category ec ON ec.code = ei.category_code "
                "WHERE ei.item_symbol = ? "
                "ORDER BY ei.id LIMIT 1",
                (item_symbol.upper(),),
            ).fetchone()

        if row is None:
            return {}

        item_id = row["id"]
        materials = [
            dict(r)
            for r in conn.execute(
                "SELECT material, is_default FROM item_material WHERE item_id = ? ORDER BY id",
                (item_id,),
            ).fetchall()
        ]
        bounds = [
            {"parameter": r["parameter"], "raw_text": r["raw_text"]}
            for r in conn.execute(
                "SELECT parameter, raw_text FROM design_bound WHERE item_id = ? ORDER BY id",
                (item_id,),
            ).fetchall()
        ]

    return {
        "item_symbol": row["item_symbol"],
        "category_code": row["category_code"],
        "description": row["description"],
        "page": row["page"],
        "citation": _citation(row["chapter"], row["category_code"], row["item_symbol"]),
        "materials": materials,
        "bounds": bounds,
    }


def search_items(keyword: str, db_path: Path | None = None) -> list[dict]:
    """Search items by keyword match on symbol or description (case-insensitive LIKE).

    Returns a list of matches with: item_symbol, category_code, description,
    page, citation. Returns an empty list on no match.
    """
    pattern = f"%{keyword}%"
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT ei.item_symbol, ei.category_code, ei.description, ei.page, ec.chapter "
            "FROM equipment_item ei "
            "JOIN equipment_category ec ON ec.code = ei.category_code "
            "WHERE ei.item_symbol LIKE ? OR ei.description LIKE ? "
            "ORDER BY ei.category_code, ei.item_symbol",
            (pattern, pattern),
        ).fetchall()

    return [
        {
            "item_symbol": r["item_symbol"],
            "category_code": r["category_code"],
            "description": r["description"],
            "page": r["page"],
            "citation": _citation(r["chapter"], r["category_code"], r["item_symbol"]),
        }
        for r in rows
    ]
