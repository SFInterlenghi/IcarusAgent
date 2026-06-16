"""Sprint 6 validation: ETL fan-out to Chapters 3–16."""

import sqlite3
from pathlib import Path
import pytest

from config.settings import settings
from etl.load_sqlite import build_db, verify_no_chapter

PDF = settings.PDF_PATH

_EXPECTED_CATEGORIES = {
    # Ch.2
    "AG", "AT", "BL", "K", "MX",
    # Ch.3
    "AC", "GC", "FN",
    # Ch.4
    "MOT", "TUR",
    # Ch.5
    "HE", "RB", "FU",
    # Ch.6
    "PAK",
    # Ch.7
    "CP", "GP", "P",
    # Ch.8
    "DDT", "TW", "DTW",
    # Ch.9
    "C", "EJ", "VP",
    # Ch.10
    "HT", "VT",
    # Ch.11
    "CR", "FL", "M", "ST",
    # Ch.12
    "CRY", "E", "WFE", "AD", "D", "DD", "RD", "TDS",
    # Ch.13
    "CO", "CE", "EL", "FE", "HO", "S",
    # Ch.14
    "CT", "DC", "F", "SE", "T", "VS",
    # Ch.15
    "CTW", "STB", "HU", "RU", "EG", "WTS",
    # Ch.16
    "FLR", "STK",
}


@pytest.fixture(scope="module")
def full_db(tmp_path_factory):
    """Build the full Ch.2-16 DB in a temp directory."""
    db_path = tmp_path_factory.mktemp("full_db") / "icarus_full.sqlite"
    build_db(db_path, list(range(2, 17)), PDF)
    return db_path


# ---------------------------------------------------------------------------
# Category coverage
# ---------------------------------------------------------------------------

def test_all_categories_present(full_db):
    conn = sqlite3.connect(str(full_db))
    codes = {row[0] for row in conn.execute("SELECT code FROM equipment_category")}
    conn.close()
    missing = _EXPECTED_CATEGORIES - codes
    assert not missing, f"Missing category codes: {missing}"


def test_chapter_coverage(full_db):
    conn = sqlite3.connect(str(full_db))
    chapters = {row[0] for row in conn.execute("SELECT DISTINCT chapter FROM equipment_category")}
    conn.close()
    expected = set(range(2, 17))
    assert expected == chapters, f"Missing chapters: {expected - chapters}"


# ---------------------------------------------------------------------------
# Item counts and spot checks
# ---------------------------------------------------------------------------

def test_ch2_items_unchanged(full_db):
    """Ch.2 item counts must be identical to the Sprint 1 baseline."""
    conn = sqlite3.connect(str(full_db))
    counts = {
        row[0]: row[1]
        for row in conn.execute(
            "SELECT category_code, COUNT(*) FROM equipment_item "
            "WHERE category_code IN ('AG','AT','BL','K','MX') "
            "GROUP BY category_code"
        )
    }
    conn.close()
    assert counts.get("AG") == 12
    assert counts.get("AT") == 7


def test_ch3_compressors_have_items(full_db):
    conn = sqlite3.connect(str(full_db))
    items = [
        row[0] for row in conn.execute(
            "SELECT item_symbol FROM equipment_item WHERE category_code = 'AC'"
        )
    ]
    conn.close()
    assert items, "No items found for Air Compressors (AC)"
    assert "CENTRIF M" in items or any("CENTRIF" in i for i in items)


def test_ch4_motor_items(full_db):
    conn = sqlite3.connect(str(full_db))
    items = [
        row[0] for row in conn.execute(
            "SELECT item_symbol FROM equipment_item WHERE category_code = 'MOT'"
        )
    ]
    conn.close()
    assert items, "No items found for Electrical Motors (MOT)"


def test_ch5_heat_exchanger_items(full_db):
    conn = sqlite3.connect(str(full_db))
    items = [
        row[0] for row in conn.execute(
            "SELECT item_symbol FROM equipment_item WHERE category_code = 'HE'"
        )
    ]
    conn.close()
    assert items, "No items found for Heat Exchangers (HE)"


def test_ch7_centrifugal_pumps(full_db):
    conn = sqlite3.connect(str(full_db))
    items = [
        row[0] for row in conn.execute(
            "SELECT item_symbol FROM equipment_item WHERE category_code = 'CP'"
        )
    ]
    conn.close()
    assert items, "No items found for Centrifugal Pumps (CP)"


def test_ch16_flares_items(full_db):
    conn = sqlite3.connect(str(full_db))
    items = [
        row[0] for row in conn.execute(
            "SELECT item_symbol FROM equipment_item WHERE category_code = 'FLR'"
        )
    ]
    conn.close()
    assert items, "No items found for Flares (FLR)"


# ---------------------------------------------------------------------------
# Citation format
# ---------------------------------------------------------------------------

def test_all_items_have_valid_category(full_db):
    conn = sqlite3.connect(str(full_db))
    orphans = conn.execute(
        "SELECT ei.id, ei.category_code FROM equipment_item ei "
        "LEFT JOIN equipment_category ec ON ei.category_code = ec.code "
        "WHERE ec.code IS NULL"
    ).fetchall()
    conn.close()
    assert not orphans, f"Items with unknown category_code: {orphans}"


def test_no_null_item_symbols(full_db):
    conn = sqlite3.connect(str(full_db))
    bad = conn.execute(
        "SELECT id FROM equipment_item WHERE item_symbol IS NULL OR item_symbol = ''"
    ).fetchall()
    conn.close()
    assert not bad, f"Null/empty symbol row ids: {bad}"


# ---------------------------------------------------------------------------
# Chapter 37 exclusion
# ---------------------------------------------------------------------------

def test_chapter_37_excluded(full_db):
    ok = verify_no_chapter(full_db, 37)
    assert ok, "Chapter 37 rows found — release notes must never be ingested"
