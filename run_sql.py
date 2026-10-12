"""
Loads the cleaned data into a SQLite database and runs every query in sql/queries.sql.
Results are saved as CSV files in outputs/sql_results/ and previewed in the terminal.
Usage: python run_sql.py            (uses data/clean_sales.csv from run_pipeline.py)
"""
import re
import sqlite3
from pathlib import Path
import pandas as pd


def run_all(clean_csv="data/clean_sales.csv", sql_file="sql/queries.sql", out_dir="outputs/sql_results", verbose=True):
    df = pd.read_csv(clean_csv)
    con = sqlite3.connect(":memory:")
    df.to_sql("sales", con, index=False)
    text = Path(sql_file).read_text(encoding="utf-8")
    blocks = re.split(r"^-- name: (\S+)\s*$", text, flags=re.M)[1:]
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    results = {}
    for name, body in zip(blocks[::2], blocks[1::2]):
        try:
            res = pd.read_sql_query(body.strip(), con)
            res.to_csv(Path(out_dir) / f"{name}.csv", index=False)
            results[name] = res
            if verbose:
                print(f"\n== {name}  ({len(res)} rows)")
                print(res.head(5).to_string(index=False))
        except Exception as e:      # a query may need a column the uploaded file does not have
            results[name] = None
            if verbose:
                print(f"\n== {name}  SKIPPED ({str(e).splitlines()[0]})")
    con.close()
    return results


if __name__ == "__main__":
    run_all()
