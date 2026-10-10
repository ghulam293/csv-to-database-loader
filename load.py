"""
load.py - STEP 3 of the pipeline: save data into the DuckDB database.

Order matters: customers and products FIRST, then sales,
because a sale needs a customer_id and a product_id that already exist.
"""

import json

import pandas as pd

import config
import db

log = config.get_logger()


# ---------- Run history ----------
def start_run(con, source_file):
    """Add a row to pipeline_runs and return its run_id."""
    run_id = con.execute(
        "INSERT INTO pipeline_runs (source_file, started_at, status) "
        "VALUES (?, now(), 'RUNNING') RETURNING run_id",
        [source_file],
    ).fetchone()[0]
    return run_id


def finish_run(con, run_id, status, rows_read=0, rows_duplicate=0,
               rows_rejected=0, rows_loaded=0):
    """Fill in the results of a run (success or failure)."""
    con.execute(
        """UPDATE pipeline_runs
           SET finished_at = now(), status = ?, rows_read = ?,
               rows_duplicate = ?, rows_rejected = ?, rows_loaded = ?
           WHERE run_id = ?""",
        [status, rows_read, rows_duplicate, rows_rejected, rows_loaded, run_id],
    )


# ---------- Load clean rows ----------
def load_clean_rows(con, clean, run_id):
    """Insert customers, products, then sales. Returns number of sales loaded."""
    if clean.empty:
        return 0

    # Build the products table (name + category) from config.py
    products = pd.DataFrame({"name": clean["product"].unique()})
    products["category"] = (
        products["name"].map(config.PRODUCT_CATEGORY).fillna(config.DEFAULT_CATEGORY)
    )

    # Let DuckDB read our pandas tables directly in SQL
    con.register("clean_df", clean)
    con.register("products_df", products)

    # 1. Dimension tables. ON CONFLICT DO NOTHING = skip names that already exist
    con.execute(
        "INSERT INTO customers (name) SELECT DISTINCT customer FROM clean_df "
        "ON CONFLICT DO NOTHING"
    )
    con.execute(
        "INSERT INTO products (name, category) SELECT name, category FROM products_df "
        "ON CONFLICT DO NOTHING"
    )

    # 2. Sales table. JOIN swaps names for IDs.
    #    INSERT OR REPLACE = if order_id already exists, update it (safe re-runs)
    con.execute(
        """INSERT OR REPLACE INTO sales
           SELECT c.order_id, cu.customer_id, p.product_id, ?,
                  c.quantity, c.price, CAST(c.order_date AS DATE), c.total
           FROM clean_df c
           JOIN customers cu ON cu.name = c.customer
           JOIN products  p  ON p.name  = c.product""",
        [run_id],
    )

    con.unregister("clean_df")
    con.unregister("products_df")
    return len(clean)


# ---------- Save rejected rows ----------
def save_rejected(con, rejected, run_id, source_file):
    """Store bad rows in the database AND in a CSV file inside rejected/."""
    # Re-running a file replaces its old rejected rows (no duplicates piling up)
    con.execute("DELETE FROM rejected_rows WHERE source_file = ?", [source_file])
    if rejected.empty:
        return

    rows = [
        (run_id, source_file, json.dumps(row.drop("reason").to_dict()), row["reason"])
        for _, row in rejected.iterrows()
    ]
    con.executemany(
        "INSERT INTO rejected_rows (run_id, source_file, raw_data, reason) "
        "VALUES (?, ?, ?, ?)",
        rows,
    )

    config.REJECT_DIR.mkdir(exist_ok=True)
    out_file = config.REJECT_DIR / f"rejected_{source_file}"
    rejected.to_csv(out_file, index=False)
    log.warning("[%s] %d rejected rows saved to %s", source_file, len(rejected), out_file)


if __name__ == "__main__":
    # Quick demo: run extract -> transform -> load for every CSV file
    import extract
    import transform

    con = db.get_connection()
    db.create_tables(con)

    for file in extract.find_csv_files():
        run_id = start_run(con, file.name)
        raw = extract.extract(file)
        clean, rejected, dups = transform.transform(raw)
        save_rejected(con, rejected, run_id, file.name)
        loaded = load_clean_rows(con, clean, run_id)
        finish_run(con, run_id, "SUCCESS", len(raw), dups, len(rejected), loaded)
        log.info("[%s] Loaded %d rows", file.name, loaded)

    print("\nsales rows       :", con.execute("SELECT COUNT(*) FROM sales").fetchone()[0])
    print("customers        :", con.execute("SELECT COUNT(*) FROM customers").fetchone()[0])
    print("products         :", con.execute("SELECT COUNT(*) FROM products").fetchone()[0])
    print("rejected rows    :", con.execute("SELECT COUNT(*) FROM rejected_rows").fetchone()[0])
    print("\nFirst 5 sales (joined view):")
    print(con.execute("SELECT * FROM v_sales_detail ORDER BY order_id LIMIT 5").df().to_string(index=False))
    con.close()