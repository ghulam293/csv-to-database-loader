"""
db.py - database connection and table design (the ERD in code).
Run this file directly to create the tables:  python db.py
"""

import duckdb

import config

SCHEMA = """
CREATE SEQUENCE IF NOT EXISTS seq_customer_id START 1;
CREATE SEQUENCE IF NOT EXISTS seq_product_id  START 1;
CREATE SEQUENCE IF NOT EXISTS seq_run_id      START 1;
CREATE SEQUENCE IF NOT EXISTS seq_reject_id   START 1;

CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY DEFAULT nextval('seq_customer_id'),
    name        VARCHAR NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY DEFAULT nextval('seq_product_id'),
    name       VARCHAR NOT NULL UNIQUE,
    category   VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id         INTEGER PRIMARY KEY DEFAULT nextval('seq_run_id'),
    source_file    VARCHAR NOT NULL,
    started_at     TIMESTAMP NOT NULL,
    finished_at    TIMESTAMP,
    rows_read      INTEGER,
    rows_duplicate INTEGER,
    rows_rejected  INTEGER,
    rows_loaded    INTEGER,
    status         VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS sales (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    product_id  INTEGER NOT NULL REFERENCES products(product_id),
    run_id      INTEGER NOT NULL,
    quantity    INTEGER NOT NULL CHECK (quantity > 0),
    price       DECIMAL(10, 2) NOT NULL CHECK (price > 0),
    order_date  DATE NOT NULL,
    total       DECIMAL(12, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS rejected_rows (
    reject_id   INTEGER PRIMARY KEY DEFAULT nextval('seq_reject_id'),
    run_id      INTEGER NOT NULL,
    source_file VARCHAR NOT NULL,
    raw_data    VARCHAR NOT NULL,
    reason      VARCHAR NOT NULL
);

CREATE OR REPLACE VIEW v_sales_detail AS
SELECT s.order_id, c.name AS customer, p.name AS product, p.category,
       s.quantity, s.price, s.total, s.order_date
FROM sales s
JOIN customers c ON c.customer_id = s.customer_id
JOIN products  p ON p.product_id  = s.product_id;
"""


def get_connection():
    """Open (or create) the DuckDB database file."""
    return duckdb.connect(str(config.DB_PATH))


def create_tables(con):
    """Create every table, sequence and view. Safe to run many times."""
    con.execute(SCHEMA)


def list_tables(con):
    """Return the names of all tables in the database."""
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' ORDER BY table_name"
    ).fetchall()
    return [r[0] for r in rows]


if __name__ == "__main__":
    con = get_connection()
    create_tables(con)
    print("Database:", config.DB_PATH)
    print("Tables  :", list_tables(con))
    con.close()
