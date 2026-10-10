"""Integration tests: run the real pipeline on a temporary database."""

import pytest

import config
import db
import main
import validate

CSV_TEXT = """order_id,customer,product,quantity,price,order_date
1,ali khan,Laptop,1,850.00,2026-01-05
2,SARA AHMED,Mouse,3,12.50,2026-01-06
2,SARA AHMED,Mouse,3,12.50,2026-01-06
3,bilal raza,Keyboard,,25.00,2026-01-07
"""   # 4 rows read: 2 good, 1 duplicate, 1 rejected


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """A temporary data folder and database, so tests never touch your real data."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(config, "DATA_DIR", data_dir)
    monkeypatch.setattr(config, "REJECT_DIR", tmp_path / "rejected")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.duckdb")

    con = db.get_connection()
    db.create_tables(con)
    yield data_dir, con
    con.close()


def count(con, table):
    return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_good_file_loads_successfully(workspace):
    data_dir, con = workspace
    csv_file = data_dir / "test_sales.csv"
    csv_file.write_text(CSV_TEXT)

    assert main.process_file(con, csv_file) is True
    assert count(con, "sales") == 2
    assert count(con, "customers") == 2
    assert count(con, "rejected_rows") == 1

    status, loaded = con.execute(
        "SELECT status, rows_loaded FROM pipeline_runs"
    ).fetchone()
    assert status == "SUCCESS" and loaded == 2


def test_running_twice_does_not_duplicate_data(workspace):
    data_dir, con = workspace
    csv_file = data_dir / "test_sales.csv"
    csv_file.write_text(CSV_TEXT)

    main.process_file(con, csv_file)
    main.process_file(con, csv_file)

    assert count(con, "sales") == 2
    assert count(con, "customers") == 2
    assert count(con, "rejected_rows") == 1       # replaced, not doubled
    assert count(con, "pipeline_runs") == 2       # history keeps both runs


def test_file_with_missing_columns_is_marked_failed(workspace):
    data_dir, con = workspace
    bad_file = data_dir / "bad.csv"
    bad_file.write_text("order_id,customer\n1,ali\n")

    assert main.process_file(con, bad_file) is False
    assert count(con, "sales") == 0
    status = con.execute("SELECT status FROM pipeline_runs").fetchone()[0]
    assert status.startswith("FAILED")


def test_failed_validation_rolls_back_the_load(workspace, monkeypatch):
    data_dir, con = workspace
    csv_file = data_dir / "test_sales.csv"
    csv_file.write_text(CSV_TEXT)
    monkeypatch.setattr(validate, "check_totals", lambda *a, **k: "forced failure")

    assert main.process_file(con, csv_file) is False
    assert count(con, "sales") == 0               # load was undone
    status = con.execute("SELECT status FROM pipeline_runs").fetchone()[0]
    assert "forced failure" in status