"""Extract raw text from Aspen Icarus Reference PDF, chapter by chapter."""

import sys
from pathlib import Path
import fitz  # PyMuPDF

# 1-indexed, inclusive page ranges per chapter
CHAPTER_RANGES: dict[int, tuple[int, int]] = {
    2: (43, 80),
    # Chapters 3-16 populated in Sprint 6
    3:  (81,  95),
    4:  (95,  107),
    5:  (107, 190),
    6:  (190, 210),
    7:  (210, 255),
    8:  (255, 290),
    9:  (290, 310),
    10: (310, 390),
    11: (390, 440),
    12: (440, 530),
    13: (530, 610),
    14: (610, 680),
    15: (680, 750),
    16: (750, 780),
}


def extract_pages(pdf_path: Path, first: int, last: int) -> list[tuple[int, str]]:
    """Return [(1-indexed page number, page text), ...] for pages first..last inclusive."""
    doc = fitz.open(str(pdf_path))
    results: list[tuple[int, str]] = []
    for i in range(first - 1, min(last, doc.page_count)):
        results.append((i + 1, doc[i].get_text()))
    return results


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
