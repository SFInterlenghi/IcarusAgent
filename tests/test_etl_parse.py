"""Sprint 1 validation: ETL pipeline for Chapter 2 Agitators."""

import sqlite3
from pathlib import Path
import pytest

from etl.extract_pdf import get_chapter_pages, extract_pages
from etl.parse_equipment import parse_chapter
from etl.load_sqlite import build_db, verify_no_chapter
from config.settings import settings

PDF = settings.PDF_PATH
DB = Path("data/test_icarus_kb.sqlite")

EXPECTED_CODES = {"AG", "AT", "BL", "K", "MX"}

REQUIRED_AG_ITEMS = {"DIRECT", "ANCHOR", "HIGH SHEAR", "GEAR DRIVE", "MECH SEAL",
                     "PORT PROP", "FIXED PROP", "SAN PORT", "COUNT ROT"}
REQUIRED_AT_ITEMS = {"MIXER", "OPEN TOP", "REACTOR"}


@pytest.fixture(scope="module")
def parsed():
    pages = get_chapter_pages(2, PDF)
    return parse_chapter(pages, chapter=2)


@pytest.fixture(scope="module")
def db(parsed, tmp_path_factory):
    db_path = tmp_path_factory.mktemp("db") / "test.sqlite"
    pages = get_chapter_pages(2, PDF)
    result = parse_chapter(pages, chapter=2)
    from etl.load_sqlite import create_schema, load_parsed
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    create_schema(conn)
    load_parsed(conn, result)
    conn.close()
    return db_path


# ---------------------------------------------------------------------------
# Extract tests
# ---------------------------------------------------------------------------

def test_extract_returns_correct_page_count():
    pages = extract_pages(PDF, 43, 80)
    assert len(pages) == 38  # pages 43–80 inclusive


def test_extract_pages_are_numbered_correctly():
    pages = extract_pages(PDF, 43, 80)
    nums = [p for p, _ in pages]
    assert nums[0] == 43
    assert nums[-1] == 80


def test_chapter2_has_non_empty_pages():
    pages = get_chapter_pages(2, PDF)
    non_empty = [p for p, t in pages if t.strip()]
    assert len(non_empty) >= 30


# ---------------------------------------------------------------------------
# Parse tests
# ---------------------------------------------------------------------------

def test_parsed_category_codes(parsed):
    codes = {c.code for c in parsed.categories}
    assert codes == EXPECTED_CODES, f"Got codes: {codes}"


def test_all_categories_chapter2(parsed):
    for cat in parsed.categories:
        assert cat.chapter == 2


def test_ag_item_count(parsed):
    ag_items = [i for i in parsed.items if i.category_code == "AG"]
    assert len(ag_items) >= 12, f"AG has only {len(ag_items)} items"


def test_ag_required_items(parsed):
    ag_symbols = {i.item_symbol for i in parsed.items if i.category_code == "AG"}
    missing = REQUIRED_AG_ITEMS - ag_symbols
    assert not missing, f"Missing AG items: {missing}"


def test_at_required_items(parsed):
    at_symbols = {i.item_symbol for i in parsed.items if i.category_code == "AT"}
    missing = REQUIRED_AT_ITEMS - at_symbols
    assert not missing, f"Missing AT items: {missing}; found: {at_symbols}"


def test_no_null_item_symbols(parsed):
    for item in parsed.items:
        assert item.item_symbol and item.item_symbol.strip(), \
            f"Null/empty symbol in category {item.category_code}"


def test_item_pages_within_chapter2_range(parsed):
    for item in parsed.items:
        assert 43 <= item.page <= 80, \
            f"Item {item.item_symbol} has out-of-range page {item.page}"


def test_at_mixer_has_materials(parsed):
    mixer = next(
        (i for i in parsed.items if i.category_code == "AT" and i.item_symbol == "MIXER"),
        None,
    )
    assert mixer is not None, "MIXER not found in AT"


def test_ag_direct_has_materials(parsed):
    direct = next(
        (i for i in parsed.items if i.category_code == "AG" and i.item_symbol == "DIRECT"),
        None,
    )
    assert direct is not None, "DIRECT not found in AG"
    assert direct.materials, f"DIRECT has no materials; got: {direct}"


def test_ag_direct_has_bounds(parsed):
    direct = next(
        (i for i in parsed.items if i.category_code == "AG" and i.item_symbol == "DIRECT"),
        None,
    )
    assert direct is not None
    assert direct.bounds, f"DIRECT has no bounds; item: {direct}"


# ---------------------------------------------------------------------------
# SQLite tests
# ---------------------------------------------------------------------------

def test_db_category_codes(db):
    conn = sqlite3.connect(str(db))
    codes = {row[0] for row in conn.execute("SELECT code FROM equipment_category")}
    conn.close()
    assert codes == EXPECTED_CODES


def test_db_fk_integrity(db):
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = ON")
    issues = conn.execute("PRAGMA foreign_key_check").fetchall()
    conn.close()
    assert not issues, f"FK violations: {issues}"


def test_db_no_null_symbols(db):
    conn = sqlite3.connect(str(db))
    bad = conn.execute(
        "SELECT id FROM equipment_item WHERE item_symbol IS NULL OR item_symbol = ''"
    ).fetchall()
    conn.close()
    assert not bad, f"Null symbol row ids: {bad}"


def test_verify_no_chapter_37(db):
    """Chapter 37 (release notes) must never appear."""
    ok = verify_no_chapter(db, 37)
    assert ok, "Chapter 37 rows found — release notes ingested in error"
