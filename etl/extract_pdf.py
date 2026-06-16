"""Extract raw text from Aspen Icarus Reference PDF, chapter by chapter."""

import sys
from pathlib import Path
import fitz  # PyMuPDF

# 1-indexed, inclusive page ranges per chapter (derived from PDF table of contents)
CHAPTER_RANGES: dict[int, tuple[int, int]] = {
    2:  (43,   80),
    3:  (81,   94),
    4:  (95,  106),
    5:  (107, 152),
    6:  (153, 162),
    7:  (163, 194),
    8:  (195, 226),
    9:  (227, 233),
    10: (234, 280),
    11: (281, 294),
    12: (295, 314),
    13: (315, 338),
    14: (339, 378),
    15: (379, 388),
    16: (389, 398),
}


def extract_pages(pdf_path: Path, first: int, last: int) -> list[tuple[int, str]]:
    """Return [(1-indexed page number, page text), ...] for pages first..last inclusive."""
    doc = fitz.open(str(pdf_path))
    try:
        results: list[tuple[int, str]] = []
        for i in range(first - 1, min(last, doc.page_count)):
            results.append((i + 1, doc[i].get_text()))
        return results
    finally:
        doc.close()


def get_chapter_pages(chapter: int, pdf_path: Path | None = None) -> list[tuple[int, str]]:
    if pdf_path is None:
        # Lazy import to keep etl modules independently importable
        from config.settings import settings
        pdf_path = settings.PDF_PATH
    first, last = CHAPTER_RANGES[chapter]
    return extract_pages(pdf_path, first, last)


def _main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Extract PDF pages to text")
    ap.add_argument("--pages", required=True, help="Page range e.g. 43-80")
    ap.add_argument("--check", action="store_true", help="Run sanity checks and exit")
    ap.add_argument("--pdf", default=None, help="Path to PDF (default: settings.PDF_PATH)")
    args = ap.parse_args()

    from config.settings import settings
    pdf_path = Path(args.pdf) if args.pdf else settings.PDF_PATH

    first, last = map(int, args.pages.split("-"))
    pages = extract_pages(pdf_path, first, last)

    if args.check:
        non_empty = [(p, t) for p, t in pages if t.strip()]
        empty_nums = [p for p, t in pages if not t.strip()]
        print(f"Extracted {len(pages)} pages ({first}-{last})")
        print(f"Non-empty: {len(non_empty)}  Empty: {len(empty_nums)}")
        if empty_nums:
            print(f"Empty pages: {empty_nums}")
        if non_empty:
            print(f"First non-empty page {non_empty[0][0]}: {non_empty[0][1][:80]!r}")
        if len(pages) != (last - first + 1):
            print(f"ERROR: expected {last - first + 1} pages, got {len(pages)}")
            sys.exit(1)
        print("check-ok")
    else:
        for page_num, text in pages:
            print(f"=== page {page_num} ===")
            print(text)


if __name__ == "__main__":
    _main()
