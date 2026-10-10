# CSV to Database Loader

A data pipeline that reads messy CSV files, cleans and validates them,
loads them into a DuckDB database, and produces SQL reports.

## Flow

extract.py -> transform.py -> load.py -> validate.py -> reports.py

## Setup

    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt

## Usage

    python main.py                 # process every CSV in data/
    python main.py sales_jan.csv   # process one file
    python reports.py              # print business reports
    python reports.py --export     # also save reports as CSV
    python -m pytest -v            # run the tests

## Files

| File | Job |
|---|---|
| config.py | Paths, settings, logging |
| db.py | Database connection and tables |
| extract.py | Read CSV files as text |
| transform.py | Clean data, reject bad rows with a reason |
| load.py | Write to the database, run history |
| validate.py | Quality checks after loading |
| main.py | Runs the whole pipeline |
| reports.py | SQL reports |
| tests/ | Unit and integration tests |

## Design decisions

- Safe re-runs: loading uses upserts, so running a file twice never duplicates data.
- Rollback: load and validation share one transaction; a failed check undoes the load.
- Rejected rows are kept with the reason, not silently dropped.
- Every run is recorded in the pipeline_runs table.
