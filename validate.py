"""
validate.py - STEP 4 of the pipeline: check that the load really worked.

Each check is a small function. It returns None when everything is fine,
or a short message that explains what is wrong.
"""

import config
import db

log = config.get_logger()


# ---------- Individual checks ----------
def check_row_count(con, run_id, expected_loaded):
    """Did the database receive exactly the rows we sent?"""
    actual = con.execute(
        "SELECT COUNT(*) FROM sales WHERE run_id = ?", [run_id]
    ).fetchone()[0]
    if actual != expected_loaded:
        return f"expected {expected_loaded} sales rows, database has {actual}"


def check_totals(con, run_id, clean):
    """Does the money in the database match the money in our clean table?"""
    db_total = con.execute(
        "SELECT COALESCE(SUM(total), 0) FROM sales WHERE run_id = ?", [run_id]
    ).fetchone()[0]
    expected = round(float(clean["total"].sum()), 2)
    if abs(float(db_total) - expected) > 0.01:
        return f"total mismatch: expected {expected}, database has {db_total}"


def check_reconciliation(rows_read, duplicates, rejected, loaded):
    """Every row we read must be accounted for: read = duplicates + rejected + loaded."""
    accounted = duplicates + rejected + loaded
    if rows_read != accounted:
        return (f"rows do not add up: read {rows_read}, "
                f"but duplicates + rejected + loaded = {accounted}")


def check_rejected_saved(con, source_file, expected_rejected):
    """Were all rejected rows stored in the rejected_rows table?"""
    actual = con.execute(
        "SELECT COUNT(*) FROM rejected_rows WHERE source_file = ?", [source_file]
    ).fetchone()[0]
    if actual != expected_rejected:
        return f"expected {expected_rejected} rejected rows saved, found {actual}"


def check_orphans(con):
    """No sale may point to a customer, product or run that does not exist."""
    queries = {
        "customer": "SELECT COUNT(*) FROM sales s LEFT JOIN customers c "
                    "ON c.customer_id = s.customer_id WHERE c.customer_id IS NULL",
        "product": "SELECT COUNT(*) FROM sales s LEFT JOIN products p "
                   "ON p.product_id = s.product_id WHERE p.product_id IS NULL",
        "run": "SELECT COUNT(*) FROM sales s LEFT JOIN pipeline_runs r "
               "ON r.run_id = s.run_id WHERE r.run_id IS NULL",
    }
    for name, sql in queries.items():
        count = con.execute(sql).fetchone()[0]
        if count:
            return f"{count} sales rows point to a missing {name}"


# ---------- Run all checks ----------
def validate(con, run_id, source_file, rows_read, duplicates, clean, rejected):
    """Run every check. Raises ValueError if any check fails."""
    results = {
        "row count": check_row_count(con, run_id, len(clean)),
        "totals match": check_totals(con, run_id, clean),
        "rows add up": check_reconciliation(rows_read, duplicates, len(rejected), len(clean)),
        "rejected saved": check_rejected_saved(con, source_file, len(rejected)),
        "no orphan rows": check_orphans(con),
    }

    failures = []
    for name, problem in results.items():
        if problem is None:
            log.info("[%s] CHECK OK     : %s", source_file, name)
        else:
            log.error("[%s] CHECK FAILED : %s -> %s", source_file, name, problem)
            failures.append(f"{name}: {problem}")

    if failures:
        raise ValueError("Validation failed: " + "; ".join(failures))
    return True


if __name__ == "__main__":
    import extract
    import load
    import transform

    con = db.get_connection()
    db.create_tables(con)

    for file in extract.find_csv_files():
        run_id = load.start_run(con, file.name)
        raw = extract.extract(file)
        clean, rejected, dups = transform.transform(raw)
        load.save_rejected(con, rejected, run_id, file.name)
        loaded = load.load_clean_rows(con, clean, run_id)
        validate(con, run_id, file.name, len(raw), dups, clean, rejected)
        load.finish_run(con, run_id, "SUCCESS", len(raw), dups, len(rejected), loaded)

    print("\nAll files passed validation.")
    con.close()