# IcarusAgent — Knowledge Base Schema

> Updated each time `etl/schema.sql` changes. Lives alongside `etl/schema.sql`.

## Tables

### `equipment_category`
| Column | Type | Notes |
|---|---|---|
| `code` | TEXT PK | 2-letter IEE code (e.g. `AG`, `AT`) |
| `name` | TEXT | Full category name (e.g. `Agitators`) |
| `chapter` | INT | PDF chapter number |
| `page` | INT | First page in PDF |

### `equipment_item`
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `category_code` | TEXT FK | → `equipment_category.code` |
| `item_symbol` | TEXT | Model symbol (e.g. `MIXER`, `DIRECT`) |
| `description` | TEXT | Extracted prose description |
| `page` | INT | Source PDF page |

### `design_bound`
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `item_id` | INT FK | → `equipment_item.id` |
| `parameter` | TEXT | e.g. `Driver Power`, `Liquid Volume` |
| `raw_text` | TEXT | Full bound text as extracted from PDF, e.g. `0.25 - 3 HP [0.75 - 2.22 KW]` |

> **Sprint 1 decision:** `raw_text` is used instead of `min_val`/`max_val` because PDF bound values are textual and format varies significantly per item (mixed imperial/metric, min/max on separate lines, footnoted values). The `raw_text` is sufficient for the informational chatbot use case. Structured numeric extraction can be layered on in a later sprint if needed.

### `item_material`
| Column | Type | Notes |
|---|---|---|
| `item_id` | INT FK | → `equipment_item.id` |
| `material` | TEXT | e.g. `Carbon Steel`, `304 SS` |

## Indexes
- `idx_item_symbol` on `equipment_item(item_symbol)`
- `idx_cat_code` on `equipment_category(code)`

## Current Population Status

| Sprint | Scope | Status |
|---|---|---|
| Sprint 1 | Ch.2 (AG, AT, BL, K, MX) | ✅ Complete — 5 categories, 40 items |
| Sprint 6 | Ch.3–16 | Pending |
