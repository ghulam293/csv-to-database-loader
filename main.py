"""
main.py - connects ALL steps into one command.

    python main.py                  -> process every CSV in data/
    python main.py sales_jan.csv    -> process only that file

Flow for each file:  extract -> transform -> load -> validate
If anything goes wrong, the file is rolled back and marked FAILED,
and the pipeline continues with the next file.
"""

import argparse
import sys

import config
import db
import extract
import load
import transform
import validate

log = config.get_logger()


def process_file(con, path):
    """Run the full pipeline for ONE file. Returns True on success."""
    name = path.name
    run_id = load.start_run(con, name)
    rows_read = duplicates = rejected_count = 0

    try:
        # 1 + 2: read and clean (nothing is written to the database yet)
        raw = extract.extract(path)
        rows_read = len(raw)
        clean, rejected, duplicates = transform.transform(raw)
        rejected_count = len(rejected)

        # 3 + 4: load and validate inside ONE transaction.
        # If validation fails, everything is undone (rollback).
        con.begin()
        load.save_rejected(con, rejected, run_id, name)
        loaded = load.load_clean_rows(con, clean, run_id)
        validate.validate(con, run_id, name, rows_read, duplicates, clean, rejected)
        con.commit()

        load.finish_run(con, run_id, "SUCCESS", rows_read, duplicates, rejected_count, loaded)
        log.info("[%s] SUCCESS: read=%d duplicates=%d rejected=%d loaded=%d",
                 name, rows_read, duplicates, rejected_count, loaded)
        return True

    except Exception as error:
        try:
            con.rollback()          # undo a half-finished load
        except Exception:
            pass                    # no transaction was open, nothing to undo
        load.finish_run(con, run_id, f"FAILED: {error}"[:200],
                        rows_read, duplicates, rejected_count, 0)
        log.error("[%s] FAILED: %s", name, error)
        return False


def print_summary(con, how_many):
    """Show the results of the runs we just did."""
    summary = con.execute(
        """SELECT run_id, source_file AS file, rows_read AS read,
                  rows_duplicate AS dup, rows_rejected AS rejected,
                  rows_loaded AS loaded, substr(status, 1, 45) AS status
           FROM (SELECT * FROM pipeline_runs ORDER BY run_id DESC LIMIT ?)
           ORDER BY run_id""",
        [how_many],
    ).df()
    print("\n=== RUN SUMMARY ===")
    print(summary.to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description="CSV to DuckDB pipeline")
    parser.add_argument("files", nargs="*",
                        help="CSV file names inside data/ (default: all files)")
    args = parser.parse_args()

    config.ensure_folders()

    # Decide which files to process
    if args.files:
        paths = []
        for file_name in args.files:
            path = config.DATA_DIR / file_name
            if path.exists():
                paths.append(path)
            else:
                log.error("File not found: %s", path)
    else:
        paths = extract.find_csv_files()

    if not paths:
        log.error("No CSV files to process. Put files in %s", config.DATA_DIR)
        return 1

    con = db.get_connection()
    db.create_tables(con)

    results = [process_file(con, path) for path in paths]

    print_summary(con, len(paths))
    con.close()
    return 0 if all(results) else 1      # exit code 1 = something failed


if __name__ == "__main__":
    sys.exit(main())