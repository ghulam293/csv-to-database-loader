"""
reports.py - business reports from the database, written in SQL.

    python reports.py             -> print all reports
    python reports.py --export    -> also save each report as a CSV in reports/
"""

import argparse

import config
import db

REPORT_DIR = config.BASE_DIR / "reports"

# Each report: (title, SQL query). Add your own at the bottom!
REPORTS = [
    (
        "Overview",
        """SELECT COUNT(*)                        AS orders,
                  CAST(SUM(quantity) AS INTEGER)  AS units_sold,
                  COUNT(DISTINCT customer)        AS customers,
                  ROUND(SUM(total), 2)            AS revenue,
                  ROUND(AVG(total), 2)            AS avg_order_value
           FROM v_sales_detail""",
    ),
    (
        "Revenue by category",
        """SELECT category,
                  COUNT(*)                        AS orders,
                  CAST(SUM(quantity) AS INTEGER)  AS units,
                  ROUND(SUM(total), 2)            AS revenue,
                  ROUND(100 * SUM(total) / SUM(SUM(total)) OVER (), 1) AS pct_of_revenue
           FROM v_sales_detail
           GROUP BY category
           ORDER BY revenue DESC""",
    ),
    (
        "Top products",
        """SELECT product, category,
                  CAST(SUM(quantity) AS INTEGER)  AS units,
                  ROUND(SUM(total), 2)            AS revenue
           FROM v_sales_detail
           GROUP BY product, category
           ORDER BY revenue DESC
           LIMIT 5""",
    ),
    (
        "Top customers",
        """SELECT customer,
                  COUNT(*)                        AS orders,
                  ROUND(SUM(total), 2)            AS total_spent
           FROM v_sales_detail
           GROUP BY customer
           ORDER BY total_spent DESC
           LIMIT 5""",
    ),
    (
        "Monthly revenue and growth",
        """WITH monthly AS (
               SELECT strftime(order_date, '%Y-%m') AS month,
                      SUM(total)                    AS revenue
               FROM sales
               GROUP BY month
           )
           SELECT month,
                  ROUND(revenue, 2) AS revenue,
                  ROUND(100 * (revenue - LAG(revenue) OVER (ORDER BY month))
                        / LAG(revenue) OVER (ORDER BY month), 1) AS growth_pct
           FROM monthly
           ORDER BY month""",
    ),
    (
        "Why rows were rejected",
        """SELECT reason, COUNT(*) AS rows_rejected
           FROM rejected_rows
           GROUP BY reason
           ORDER BY rows_rejected DESC""",
    ),
    (
        "Pipeline run history (latest 10)",
        """SELECT run_id, source_file, rows_read, rows_duplicate,
                  rows_rejected, rows_loaded, substr(status, 1, 40) AS status
           FROM pipeline_runs
           ORDER BY run_id DESC
           LIMIT 10""",
    ),
]


def slug(title):
    """'Top customers' -> 'top_customers' (used for file names)."""
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in title.lower())
    return "_".join(part for part in cleaned.split("_") if part)


def run_reports(con, export=False):
    db.create_tables(con)          # makes sure the tables exist, even on a new database
    sales_count = con.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
    if sales_count == 0:
        print("No sales data yet. Run:  python main.py")
        return

    if export:
        REPORT_DIR.mkdir(exist_ok=True)

    for title, sql in REPORTS:
        table = con.execute(sql).df()
        print(f"\n=== {title} ===")
        print(table.to_string(index=False) if len(table) else "(no rows)")
        if export:
            table.to_csv(REPORT_DIR / f"{slug(title)}.csv", index=False)

    if export:
        print(f"\nReports saved in: {REPORT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Business reports")
    parser.add_argument("--export", action="store_true", help="save reports as CSV files")
    args = parser.parse_args()

    con = db.get_connection()
    run_reports(con, export=args.export)
    con.close()