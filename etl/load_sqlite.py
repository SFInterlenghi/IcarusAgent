"""Load parsed equipment records into SQLite knowledge base."""

import sqlite3
import sys
from pathlib import Path

from etl.extract_pdf import get_chapter_pages, CHAPTER_RANGES
from etl.parse_equipment import parse_chapter


def _schema_sql() -> str:
    return (Path(__file__).parent / "schema.sql").read_text()


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_schema_sql())
    conn.commit()


def load_parsed(conn: sqlite3.Connection, result) -> None:
    """Insert ParseResult into the open connection (idempotent per code+symbol)."""
    cur = conn.cursor()

    for cat in result.categories:
        cur.execute(
            "INSERT OR REPLACE INTO equipment_category (code, name, chapter, page) "
            "VALUES (?, ?, ?, ?)",
            (cat.code, cat.name, cat.chapter, cat.page),
        )

    for item in result.items:
        cur.execute(
            "INSERT INTO equipment_item (category_code, item_symbol, description, page) "
            "VALUES (?, ?, ?, ?)",
            (item.category_code, item.item_symbol, item.description, item.page),
        )
        item_id = cur.lastrowid

        for mat in item.materials:
            is_default = 1 if mat == item.default_material else 0
            cur.execute(
                "INSERT INTO item_material (item_id, material, is_default) VALUES (?, ?, ?)",
                (item_id, mat, is_default),
            )

        for param, raw_text in item.bounds:
            cur.execute(
                "INSERT INTO design_bound (item_id, parameter, raw_text) VALUES (?, ?, ?)",
                (item_id, param, raw_text),
            )

    conn.commit()


def build_db(db_path: Path, chapters: list[int], pdf_path: Path | None = None) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    create_schema(conn)

    for chapter in chapters:
        print(f"Processing chapter {chapter}…")
        pages = get_chapter_pages(chapter, pdf_path)
        result = parse_chapter(pages, chapter=chapter)
        print(
            f"  Found {len(result.categories)} categories, "
            f"{len(result.items)} items"
        )
        load_parsed(conn, result)

    conn.close()
    print(f"DB written: {db_path}")


def verify_no_chapter(db_path: Path, chapter: int) -> bool:
    """Return True if zero items from the given chapter exist in the DB."""
    conn = sqlite3.connect(str(db_path))
    (count,) = conn.execute(
        "SELECT COUNT(*) FROM equipment_item ei "
        "JOIN equipment_category ec ON ei.category_code = ec.code "
        "WHERE ec.chapter = ?",
        (chapter,),
    ).fetchone()
    conn.close()
    return count == 0


def _parse_chapter_arg(arg: str) -> list[int]:
    """'2' → [2]; '3-16' → [3,4,...,16]"""
    if "-" in arg:
        a, b = arg.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(arg)]


def _main() -> None:
    import argparse
    from config.settings import settings

    ap = argparse.ArgumentParser(description="Build Icarus SQLite KB")
    ap.add_argument("--chapter", default="2", help="Chapter or range, e.g. 2 or 3-16")
    ap.add_argument("--db", default=None, help="Output DB path")
    ap.add_argument("--pdf", default=None, help="PDF path")
    ap.add_argument(
        "--verify-no-chapter",
        type=int,
        metavar="N",
        help="Assert chapter N has zero rows and exit",
    )
    args = ap.parse_args()

    db_path = Path(args.db) if args.db else settings.DB_PATH
    pdf_path = Path(args.pdf) if args.pdf else settings.PDF_PATH

    if args.verify_no_chapter is not None:
        ok = verify_no_chapter(db_path, args.verify_no_chapter)
        if ok:
            print(f"verify-ok: chapter {args.verify_no_chapter} has 0 rows")
        else:
            print(f"FAIL: chapter {args.verify_no_chapter} has rows in DB")
            sys.exit(1)
        return

    chapters = _parse_chapter_arg(args.chapter)
    # Guard: only known chapters
    unknown = [c for c in chapters if c not in CHAPTER_RANGES]
    if unknown:
        print(f"Unknown chapters (not yet in CHAPTER_RANGES): {unknown}")
        sys.exit(1)

    build_db(db_path, chapters, pdf_path)


if __name__ == "__main__":
    _main()
