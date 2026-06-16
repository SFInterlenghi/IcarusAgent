"""Sprint 2 validation: read-only KB query tools."""

import pytest
from pathlib import Path
from agent.tools import lookup_category, list_items, get_item_detail, search_items
from config.settings import settings

DB = settings.DB_PATH  # built by Sprint 1 ETL


# ---------------------------------------------------------------------------
# lookup_category
# ---------------------------------------------------------------------------

def test_lookup_known_category():
    result = lookup_category("AG", DB)
    assert result["code"] == "AG"
    assert result["name"] == "Agitators"
    assert result["chapter"] == 2
    assert isinstance(result["page"], int)


def test_lookup_category_case_insensitive():
    lower = lookup_category("ag", DB)
    upper = lookup_category("AG", DB)
    assert lower == upper


def test_lookup_unknown_category_returns_empty():
    result = lookup_category("ZZ", DB)
    assert result == {}


def test_lookup_all_chapter2_categories():
    for code in ("AG", "AT", "BL", "K", "MX"):
        r = lookup_category(code, DB)
        assert r, f"Category {code} not found"
        assert r["chapter"] == 2


# ---------------------------------------------------------------------------
# list_items
# ---------------------------------------------------------------------------

def test_list_items_ag_returns_12():
    items = list_items("AG", DB)
    assert len(items) == 12


def test_list_items_at_returns_7():
    items = list_items("AT", DB)
    assert len(items) == 7


def test_list_items_includes_citation():
    items = list_items("AG", DB)
    direct = next(i for i in items if i["item_symbol"] == "DIRECT")
    assert direct["citation"] == "Ch.2/AG/DIRECT"


def test_list_items_unknown_category_returns_empty():
    result = list_items("ZZ", DB)
    assert result == []


def test_list_items_all_have_citation():
    items = list_items("MX", DB)
    assert all("citation" in i and i["citation"].startswith("Ch.") for i in items)


# ---------------------------------------------------------------------------
# get_item_detail
# ---------------------------------------------------------------------------

def test_get_item_detail_direct():
    r = get_item_detail("DIRECT", "AG", DB)
    assert r["item_symbol"] == "DIRECT"
    assert r["category_code"] == "AG"
    assert r["citation"] == "Ch.2/AG/DIRECT"
    assert r["materials"], "DIRECT must have at least 1 material"
    assert r["bounds"], "DIRECT must have at least 1 bound"


def test_get_item_detail_mixer_citation():
    r = get_item_detail("MIXER", "AT", DB)
    assert r, "MIXER not found"
    assert r["citation"] == "Ch.2/AT/MIXER"
    assert "bounds" in r


def test_get_item_detail_anchor():
    r = get_item_detail("ANCHOR", "AG", DB)
    assert r["citation"] == "Ch.2/AG/ANCHOR"
    assert r["materials"]


def test_get_item_detail_anchor_rev():
    r = get_item_detail("ANCHOR REV", "AG", DB)
    assert r["citation"] == "Ch.2/AG/ANCHOR REV"


def test_get_item_detail_without_category():
    # When no category given, returns first match
    r = get_item_detail("STATIONARY", db_path=DB)
    assert r["item_symbol"] == "STATIONARY"
    assert r["category_code"] == "K"
    assert r["citation"] == "Ch.2/K/STATIONARY"


def test_get_item_detail_ambiguous_with_category():
    # PORT PROP exists in both AG and MX; category disambiguates
    ag = get_item_detail("PORT PROP", "AG", DB)
    mx = get_item_detail("PORT PROP", "MX", DB)
    assert ag["category_code"] == "AG"
    assert mx["category_code"] == "MX"
    assert ag["citation"] == "Ch.2/AG/PORT PROP"
    assert mx["citation"] == "Ch.2/MX/PORT PROP"


def test_get_item_detail_unknown_returns_empty():
    r = get_item_detail("NONEXISTENT", "AG", DB)
    assert r == {}


def test_get_item_detail_wrong_category_returns_empty():
    r = get_item_detail("MIXER", "AG", DB)  # MIXER is AT, not AG
    assert r == {}


def test_get_item_detail_case_insensitive():
    lower = get_item_detail("direct", "ag", DB)
    upper = get_item_detail("DIRECT", "AG", DB)
    assert lower["citation"] == upper["citation"]


# ---------------------------------------------------------------------------
# search_items
# ---------------------------------------------------------------------------

def test_search_anchor_finds_ag_anchor():
    results = search_items("anchor", DB)
    symbols = [r["item_symbol"] for r in results]
    assert "ANCHOR" in symbols
    cats = [r["category_code"] for r in results if r["item_symbol"] == "ANCHOR"]
    assert "AG" in cats


def test_search_anchor_also_finds_anchor_rev():
    results = search_items("anchor", DB)
    symbols = [r["item_symbol"] for r in results]
    assert "ANCHOR REV" in symbols


def test_search_results_include_citation():
    results = search_items("mixer", DB)
    assert all(r["citation"].startswith("Ch.") for r in results)


def test_search_case_insensitive():
    lower = search_items("blender", DB)
    upper = search_items("BLENDER", DB)
    assert {r["item_symbol"] for r in lower} == {r["item_symbol"] for r in upper}


def test_search_no_match_returns_empty():
    results = search_items("xyznonexistentxyz", DB)
    assert results == []


def test_search_description_match():
    # "sanitary" appears in descriptions of SAN FIXED, SAN PORT, HIGH SHEAR, etc.
    results = search_items("sanitary", DB)
    assert len(results) >= 1
