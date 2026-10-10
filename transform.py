"""
transform.py - STEP 2 of the pipeline: clean and check the data.

Input : raw table from extract.py (everything is text)
Output: clean rows, rejected rows (with a reason), and a duplicate count
"""

import pandas as pd

import config

log = config.get_logger()


# ---------- Small cleaning steps ----------
def clean_text(df):
    """Remove extra spaces and fix capital letters: '  ali khan ' -> 'Ali Khan'."""
    df = df.copy()
    for col in ["customer", "product"]:
        df[col] = df[col].str.strip().str.title()
    return df


def remove_duplicates(df):
    """Drop rows that are exactly the same. Returns (table, how_many_removed)."""
    before = len(df)
    df = df.drop_duplicates()
    return df, before - len(df)


def add_converted_columns(df):
    """
    Convert text to numbers and dates in NEW columns (ending with _n).
    errors='coerce' means: if a value is bad, make it empty instead of crashing.
    """
    df = df.copy()
    df["order_id_n"] = pd.to_numeric(df["order_id"], errors="coerce")
    df["quantity_n"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["price_n"] = pd.to_numeric(df["price"], errors="coerce")
    df["date_n"] = pd.to_datetime(df["order_date"], errors="coerce")
    return df


# ---------- Validation rules ----------
def find_problems(row):
    """Return a list of everything wrong with ONE row. Empty list = row is good."""
    problems = []

    if pd.isna(row["order_id_n"]) or row["order_id_n"] % 1 != 0:
        problems.append("invalid order_id")

    if not row["customer"]:
        problems.append("missing customer")

    if not row["product"]:
        problems.append("missing product")

    if pd.isna(row["quantity_n"]):
        problems.append("missing/invalid quantity")
    elif row["quantity_n"] <= 0:
        problems.append("quantity must be > 0")
    elif row["quantity_n"] % 1 != 0:
        problems.append("quantity must be a whole number")

    if pd.isna(row["price_n"]):
        problems.append("missing/invalid price")
    elif row["price_n"] <= 0:
        problems.append("price must be > 0")

    if pd.isna(row["date_n"]):
        problems.append("invalid date")

    return problems


# ---------- Main transform function ----------
def transform(raw):
    """Returns (clean_rows, rejected_rows, duplicate_count)."""
    df = clean_text(raw)
    df, duplicate_count = remove_duplicates(df)
    df = add_converted_columns(df)

    # Check every row and write the reasons in a new column
    df["reason"] = df.apply(lambda row: "; ".join(find_problems(row)), axis=1)
    is_bad = df["reason"] != ""

    # Rejected rows keep their ORIGINAL values, so you can see what was wrong
    rejected = raw.loc[df[is_bad].index].copy()
    rejected["reason"] = df.loc[is_bad, "reason"]

    # Clean rows get proper data types
    good = df[~is_bad]
    clean = pd.DataFrame({
        "order_id": good["order_id_n"].astype(int),
        "customer": good["customer"],
        "product": good["product"],
        "quantity": good["quantity_n"].astype(int),
        "price": good["price_n"].astype(float),
        "order_date": good["date_n"].dt.strftime("%Y-%m-%d"),
    })
    clean["total"] = (clean["quantity"] * clean["price"]).round(2)

    log.info("Transform: %d clean, %d rejected, %d duplicates removed",
             len(clean), len(rejected), duplicate_count)
    return clean, rejected, duplicate_count


if __name__ == "__main__":
    import extract

    for file in extract.find_csv_files():
        raw = extract.extract(file)
        clean, rejected, dups = transform(raw)
        print(f"\n===== {file.name} =====")
        print("CLEAN ROWS:")
        print(clean.to_string(index=False))
        print("REJECTED ROWS:")
        print(rejected.to_string(index=False) if len(rejected) else "(none)")
        