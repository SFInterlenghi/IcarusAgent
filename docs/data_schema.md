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
| `item_id` | INT FK | → `equipment_item.id` |
| `parameter` | TEXT | e.g. `volume`, `power`, `pressure` |
| `min_val` | REAL | Minimum design value |
| `max_val` | REAL | Maximum design value |
| `unit` | TEXT | e.g. `m3`, `kW`, `bar` |

> ⚠️ If PDF table layouts resist deterministic extraction, `min_val`/`max_val` may be replaced with a single `raw_text` TEXT column for the PoC. This change requires user approval per the escalation gate in ROADMAP.md.

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
| Sprint 1 | Ch.2 (AG, AT, BL, K, MX) | Pending |
| Sprint 6 | Ch.3–16 | Pending |
