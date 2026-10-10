"""Unit tests for transform.py - small, fast, no database needed."""

import pandas as pd

import transform

COLUMNS = ["order_id", "customer", "product", "quantity", "price", "order_date"]
GOOD_ROW = ["1", "  ali khan ", "laptop", "2", "10.50", "2026-01-05"]


def make_raw(*rows):
    """Build a raw (all-text) table like extract.py would give us."""
    return pd.DataFrame(list(rows), columns=COLUMNS, dtype=str)


def test_good_row_is_cleaned_and_total_calculated():
    clean, rejected, dups = transform.transform(make_raw(GOOD_ROW))

    assert len(clean) == 1
    assert len(rejected) == 0
    assert clean.iloc[0]["customer"] == "Ali Khan"      # spaces removed, capitals fixed
    assert clean.iloc[0]["product"] == "Laptop"
    assert clean.iloc[0]["total"] == 21.0                # 2 x 10.50


def test_exact_duplicate_rows_are_removed():
    clean, rejected, dups = transform.transform(make_raw(GOOD_ROW, GOOD_ROW))

    assert dups == 1
    assert len(clean) == 1


def test_missing_quantity_is_rejected_with_reason():
    row = ["2", "sara", "mouse", "", "5.00", "2026-01-06"]
    clean, rejected, dups = transform.transform(make_raw(row))

    assert len(clean) == 0
    assert "missing/invalid quantity" in rejected.iloc[0]["reason"]


def test_invalid_date_is_rejected():
    row = ["3", "bilal", "mouse", "1", "5.00", "not-a-date"]
    clean, rejected, dups = transform.transform(make_raw(row))

    assert len(clean) == 0
    assert "invalid date" in rejected.iloc[0]["reason"]


def test_negative_price_and_zero_quantity_are_rejected():
    negative_price = ["4", "hamza", "mouse", "1", "-5.00", "2026-01-07"]
    zero_quantity = ["5", "zara", "mouse", "0", "5.00", "2026-01-08"]
    clean, rejected, dups = transform.transform(make_raw(negative_price, zero_quantity))

    assert len(clean) == 0
    assert len(rejected) == 2


def test_one_row_can_have_several_problems():
    row = ["abc", "", "mouse", "1", "5.00", "2026-01-09"]
    clean, rejected, dups = transform.transform(make_raw(row))
    reason = rejected.iloc[0]["reason"]

    assert "invalid order_id" in reason
    assert "missing customer" in reason


def test_rows_add_up():
    """read = duplicates + rejected + clean (nothing may disappear)."""
    bad = ["6", "omar", "mouse", "", "5.00", "2026-01-10"]
    raw = make_raw(GOOD_ROW, GOOD_ROW, bad)
    clean, rejected, dups = transform.transform(raw)

    assert len(raw) == dups + len(rejected) + len(clean)