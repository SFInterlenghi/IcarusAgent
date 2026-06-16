"""Parse raw PDF page text into structured equipment records for Chapter 2."""

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CategoryRecord:
    code: str
    name: str
    chapter: int
    page: int


@dataclass
class ItemRecord:
    category_code: str
    item_symbol: str
    description: str
    page: int
    materials: list[str] = field(default_factory=list)
    default_material: str = ""
    bounds: list[tuple[str, str]] = field(default_factory=list)  # (parameter, raw_text)


@dataclass
class ParseResult:
    categories: list[CategoryRecord] = field(default_factory=list)
    items: list[ItemRecord] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# "Agitators (AG)" — category header with 2-letter code
_CAT_RE = re.compile(
    r"^(?P<name>[A-Z][A-Za-z ,/]+?)\s*\((?P<code>[A-Z]{1,3})\)\s*$"
)

# Lines to unconditionally skip (PDF noise)
_SKIP_RES = [
    re.compile(r"^\d+-\d+\s*$"),                # "2-2", "3-1" page refs
    re.compile(r"^Aspen Icarus Reference Guide"), # running chapter header
    re.compile(r"^\*{1,3}$"),                    # lone asterisks (footnote markers)
]

# Reference/table section headers — suppress item detection until next category
_REF_SECTION_RE = re.compile(
    r"^(?:"
    r"Description of "
    r"|General Nomenclature"
    r"|Impeller Types?"
    r"|Impeller Materials?"
    r"|Impeller Type References?"
    r"|Legend for Impellers?"
    r")",
    re.IGNORECASE,
)

# Item symbol: uppercase letters, digits, spaces, hyphens only; 2-30 chars.
# Does NOT allow lowercase, commas, asterisks, parentheses, slashes.
_ITEM_RE = re.compile(r"^[A-Z][A-Z0-9][A-Z0-9 \-]*$")
_ITEM_MAX_LEN = 30
_ITEM_MIN_LEN = 3  # excludes 2-char variable codes like FN, RN, MM

# Measurement unit tokens that appear as table column headers — never real items.
_UNIT_TOKENS: frozenset[str] = frozenset({
    "INCHES", "MM", "GPH", "GPM", "LPH",
    "HP", "KW", "MW",
    "PSIG", "KPA", "BAR",
    "PCF", "KG", "LB",
    "CF", "M3", "GAL",
    "RPM", "HZ",
    "DEG", "INCH",
    "INCHES MM", "GPH M3", "M3H",
})

# "Material:  *CS*, SS304" — value may be on same line or next line
_MATERIAL_RE = re.compile(r"^Materials?\s*:\s*(.*)$", re.IGNORECASE)

# Any "Parameter name:  optional-inline-value"
_PARAM_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 ,/()\-\.]+?)\s*:\s*(.*)$")

# Chapter 2 known categories (code → (name, approx_start_page))
CHAPTER_2_CATEGORIES: dict[str, tuple[str, int]] = {
    "AG": ("Agitators",      44),
    "AT": ("Agitated Tanks", 51),
    "BL": ("Blenders",       68),
    "K":  ("Kneaders",       71),
    "MX": ("Mixers",         72),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_noise(line: str) -> bool:
    return any(p.match(line) for p in _SKIP_RES)


def _is_item_symbol(line: str) -> bool:
    stripped = line.strip()
    if not (_ITEM_MIN_LEN <= len(stripped) <= _ITEM_MAX_LEN):
        return False
    if stripped in _UNIT_TOKENS:
        return False
    # Option lines like "SS304 - SS304" or "GEAR - Gear drive" use " - " / " – " separator
    if " - " in stripped or " – " in stripped:
        return False
    if not _ITEM_RE.match(stripped):
        return False
    return True


def _parse_materials(raw: str) -> tuple[list[str], str]:
    """Return (list_of_materials, default_material) from '*CS*, SS304, SS316'."""
    materials: list[str] = []
    default = ""
    for part in raw.split(","):
        m = part.strip().strip("*")
        if not m:
            continue
        materials.append(m)
        if "*" in part and not default:
            default = m
    return materials, default


# ---------------------------------------------------------------------------
# Parser state machine
# ---------------------------------------------------------------------------

class _State:
    IDLE = "IDLE"
    IN_CATEGORY = "IN_CATEGORY"
    IN_ITEM = "IN_ITEM"
    IN_PARAM = "IN_PARAM"
    IN_MATERIAL = "IN_MATERIAL"


def parse_chapter(pages: list[tuple[int, str]], chapter: int = 2) -> ParseResult:
    """
    Parse a list of (page_num, text) tuples into a ParseResult.
    Expects pages from etl.extract_pdf.get_chapter_pages().
    """
    result = ParseResult()
    cat_map: dict[str, CategoryRecord] = {}

    current_cat: CategoryRecord | None = None
    current_item: ItemRecord | None = None
    current_param_label: str = ""
    current_param_lines: list[str] = []
    in_reference_section: bool = False
    state = _State.IDLE

    def _flush_param() -> None:
        nonlocal current_param_label, current_param_lines
        if current_item and current_param_label:
            raw = " ".join(current_param_lines).strip()
            current_item.bounds.append((current_param_label, raw))
        current_param_label = ""
        current_param_lines = []

    def _flush_item() -> None:
        nonlocal current_item
        if current_item:
            current_item.description = current_item.description.strip()
            result.items.append(current_item)
        current_item = None

    for page_num, page_text in pages:
        for raw_line in page_text.splitlines():
            line = raw_line.strip()
            if not line or _is_noise(line):
                continue

            # ---- Reference/table section detection (any state) ----
            # Suppress item detection inside reference tables (impeller types etc.)
            # Guard: exclude parameter labels, which end with ':' (e.g. "Impeller type:")
            if _REF_SECTION_RE.match(line) and not line.endswith(":"):
                in_reference_section = True
                continue

            # ---- Category header detection (any state) ----
            cat_m = _CAT_RE.match(line)
            if cat_m:
                code = cat_m.group("code")
                name = cat_m.group("name").strip()
                if code in CHAPTER_2_CATEGORIES:
                    _flush_param()
                    _flush_item()
                    in_reference_section = False  # reset on new category
                    if code not in cat_map:
                        cat_rec = CategoryRecord(
                            code=code, name=name,
                            chapter=chapter, page=page_num,
                        )
                        cat_map[code] = cat_rec
                        result.categories.append(cat_rec)
                    current_cat = cat_map[code]
                    state = _State.IN_CATEGORY
                    continue

            # Skip all further processing while in a reference table section
            if in_reference_section:
                continue

            # ---- Material line (IN_ITEM or IN_PARAM) ----
            mat_m = _MATERIAL_RE.match(line)
            if mat_m and state in (_State.IN_ITEM, _State.IN_PARAM):
                if state == _State.IN_PARAM:
                    _flush_param()
                raw_mat = mat_m.group(1).strip()
                if raw_mat and current_item and not current_item.materials:
                    mats, default = _parse_materials(raw_mat)
                    current_item.materials = mats
                    current_item.default_material = default
                    state = _State.IN_ITEM
                else:
                    state = _State.IN_MATERIAL
                continue

            # ---- Consume the line AFTER a "Material:" header with no inline value ----
            if state == _State.IN_MATERIAL:
                if current_item and not current_item.materials:
                    mats, default = _parse_materials(line)
                    current_item.materials = mats
                    current_item.default_material = default
                state = _State.IN_ITEM
                continue  # this line is fully consumed as a material value; do not re-process

            # ---- Item symbol detection (when inside a known category) ----
            if (
                state in (_State.IN_CATEGORY, _State.IN_ITEM, _State.IN_PARAM)
                and current_cat
                and _is_item_symbol(line)
            ):
                _flush_param()
                _flush_item()
                current_item = ItemRecord(
                    category_code=current_cat.code,
                    item_symbol=line.strip(),
                    description="",
                    page=page_num,
                )
                state = _State.IN_ITEM
                continue

            # ---- Parameter label line ----
            param_m = _PARAM_RE.match(line)
            if param_m and state in (_State.IN_ITEM, _State.IN_PARAM):
                label = param_m.group(1).strip()
                inline_val = param_m.group(2).strip()
                # Real parameter labels are NOT all-uppercase and are longer than 2 chars.
                # (Option-list prefixes like "STD" or "VFD" are all-caps; skip them.)
                is_real_param = (
                    not label.isupper()
                    and len(label) > 2
                    and label.lower() not in ("material", "materials")
                )
                if is_real_param:
                    _flush_param()
                    current_param_label = label
                    current_param_lines = [inline_val] if inline_val else []
                    state = _State.IN_PARAM
                    continue

            # ---- Collect continuation text ----
            if state == _State.IN_PARAM:
                current_param_lines.append(line)
            elif state == _State.IN_ITEM and current_item:
                if not current_item.description:
                    current_item.description = line

    # Flush any remaining state
    _flush_param()
    _flush_item()

    return result
