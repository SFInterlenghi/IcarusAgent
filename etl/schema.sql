-- Icarus KB schema
-- Note: design_bound uses raw_text (not numeric min/max) because PDF bounds
-- are textual (e.g., "0.25 - 3 HP [0.75 - 2.22 KW]") and format varies per item.
-- This is explicitly noted in docs/data_schema.md.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS equipment_category (
    code    TEXT PRIMARY KEY,
    name    TEXT NOT NULL,
    chapter INT  NOT NULL,
    page    INT  NOT NULL
);

CREATE TABLE IF NOT EXISTS equipment_item (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    category_code TEXT    NOT NULL,
    item_symbol   TEXT    NOT NULL,
    description   TEXT,
    page          INT,
    FOREIGN KEY (category_code) REFERENCES equipment_category (code)
);

CREATE TABLE IF NOT EXISTS design_bound (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id   INT  NOT NULL,
    parameter TEXT NOT NULL,
    raw_text  TEXT,
    FOREIGN KEY (item_id) REFERENCES equipment_item (id)
);

CREATE TABLE IF NOT EXISTS item_material (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id  INT  NOT NULL,
    material TEXT NOT NULL,
    is_default INT NOT NULL DEFAULT 0,
    FOREIGN KEY (item_id) REFERENCES equipment_item (id)
);

CREATE INDEX IF NOT EXISTS idx_item_symbol ON equipment_item (item_symbol);
CREATE INDEX IF NOT EXISTS idx_cat_code    ON equipment_item (category_code);
