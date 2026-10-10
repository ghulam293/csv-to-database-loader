"""
extract.py - STEP 1 of the pipeline: read raw CSV files.

We read every column as TEXT on purpose. Cleaning and converting
types is the job of transform.py, so bad values never crash the reading.
"""

import pandas as pd

import config

REQUIRED_COLUMNS = ["order_id", "customer", "product", "quantity", "price", "order_date"]

log = config.get_logger()


def find_csv_files():
    """Return a sorted list of all CSV files inside the data folder."""
    return sorted(config.DATA_DIR.glob("*.csv"))


def extract(path):
    """Read one CSV file and return it as a pandas table (DataFrame)."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"{path.name} is missing columns: {missing}")

    df = df[REQUIRED_COLUMNS]
    log.info("[%s] Extracted %d rows", path.name, len(df))
    return df


if __name__ == "__main__":
    files = find_csv_files()
    print("CSV files found:", [f.name for f in files])
    for file in files:
        table = extract(file)
        print(table.head(10).to_string())