"""
One command, whole project:   python run_pipeline.py [optional_path_to_your_file.csv|xlsx]
  1. loads + auto-maps + cleans the file   2. saves data/clean_sales.csv (use this in Power BI)
  3. runs all SQL queries                  4. builds the Excel report   5. writes the insight memo
"""
import sys
from pathlib import Path
import analysis as an
import report_excel
import run_sql

path = sys.argv[1] if len(sys.argv) > 1 else "data/superstore_sample.csv"
CUR = "₹"
Path("outputs").mkdir(exist_ok=True)

raw = an.read_any(path, path)
mapping = an.guess_mapping(raw.columns)
print("Detected columns:", mapping)
df, log = an.clean(raw, mapping, dayfirst="electromart" in path.lower())
print(log.to_string(index=False))

out = df.copy()
if "order_date" in out:
    out["order_date"] = out["order_date"].dt.strftime("%Y-%m-%d")
out.to_csv("data/clean_sales.csv", index=False)

run_sql.run_all(verbose=False)
print("SQL results saved in outputs/sql_results/")

Path("outputs/profit_leakage_report.xlsx").write_bytes(report_excel.build_excel(df, log, CUR))
print("Excel report saved: outputs/profit_leakage_report.xlsx")

memo = ["# Profit Leakage: Findings Memo", ""] + [f"- {t}" for t in an.insights(df, CUR)]
Path("outputs/insights_memo.md").write_text("\n".join(memo), encoding="utf-8")
print("\n".join(memo))
