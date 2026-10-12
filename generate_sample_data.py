"""
Creates two practice datasets (SIMULATED, not real company data):
  1. data/superstore_sample.csv   - office-supplies retailer, USD-style columns (like Kaggle's Superstore)
  2. data/electromart_sample.csv  - electronics retailer, DIFFERENT column names, no profit column,
                                    discount in %, dd-mm-yyyy dates. Used to test the "upload any file" feature.
Planted problems (so the analysis has real findings): heavy discounts on Tables/Bookcases/Machines,
a loss-making Central region, plus duplicates and missing values to clean.
"""
import numpy as np
import pandas as pd
from pathlib import Path

Path("data").mkdir(exist_ok=True)


def superstore(n=10000, seed=7):
    r = np.random.default_rng(seed)
    subs = {  # sub-category: (category, base margin on list price, avg list price, P(high discount))
        "Phones": ("Technology", 0.18, 220, 0.20), "Accessories": ("Technology", 0.28, 60, 0.15),
        "Machines": ("Technology", 0.10, 900, 0.45), "Copiers": ("Technology", 0.32, 1200, 0.10),
        "Chairs": ("Furniture", 0.12, 280, 0.35), "Tables": ("Furniture", 0.10, 450, 0.60),
        "Bookcases": ("Furniture", 0.09, 330, 0.55), "Furnishings": ("Furniture", 0.20, 70, 0.20),
        "Binders": ("Office Supplies", 0.34, 30, 0.25), "Paper": ("Office Supplies", 0.42, 25, 0.10),
        "Storage": ("Office Supplies", 0.16, 110, 0.25), "Art": ("Office Supplies", 0.33, 20, 0.10),
        "Appliances": ("Office Supplies", 0.20, 150, 0.20),
    }
    names = list(subs)
    sub = r.choice(names, n, p=np.array([6, 8, 3, 2, 6, 3, 3, 8, 14, 13, 7, 8, 5]) / 86)
    region = r.choice(["West", "East", "Central", "South"], n, p=[0.32, 0.28, 0.24, 0.16])
    dates = pd.to_datetime("2023-01-01") + pd.to_timedelta(r.integers(0, 365 * 3, n), unit="D")
    # more orders in later years and in Nov/Dec
    keep = r.random(n) < (0.55 + 0.15 * (dates.year - 2023) + 0.25 * dates.month.isin([11, 12]))
    idx = np.where(keep)[0]
    sub, region, dates = sub[idx], region[idx], dates[idx]
    m = len(idx)
    cat = np.array([subs[s][0] for s in sub])
    base = np.array([subs[s][1] for s in sub])
    price = np.array([subs[s][2] for s in sub]) * r.uniform(0.7, 1.3, m)
    p_hi = 0.55 * np.array([subs[s][3] for s in sub]) + np.where(region == "Central", 0.12, 0.0)
    hi = r.random(m) < p_hi
    discount = np.where(hi, r.choice([0.3, 0.4, 0.5], m, p=[0.4, 0.35, 0.25]),
                        r.choice([0.0, 0.1, 0.2], m, p=[0.55, 0.25, 0.20]))
    qty = r.integers(1, 8, m)
    gross = price * qty
    sales = gross * (1 - discount)
    profit = gross * (base - discount) * r.uniform(0.9, 1.1, m)
    cust_w = r.lognormal(0, 1.1, 600)
    cust_ids = r.choice(600, m, p=cust_w / cust_w.sum())
    first = ["Aarav", "Anita", "Rohan", "Priya", "Sam", "Maya", "John", "Sara", "Vikram", "Neha", "Alex", "Zoya"]
    last = ["Sharma", "Patil", "Khan", "Rao", "Smith", "Brown", "Gupta", "Nair", "Singh", "Das", "Lee", "Roy"]
    cust = [f"{first[c % 12]} {last[(c // 12) % 12]} {c:03d}" for c in cust_ids]
    d = pd.DataFrame({
        "Order ID": [f"ORD-{i:06d}" for i in range(1, m + 1)],
        "Order Date": dates.strftime("%Y-%m-%d"), "Customer Name": cust,
        "Product Name": [f"{s} Model {r.integers(1, 7)}" for s in sub],
        "Category": cat, "Sub-Category": sub, "Region": region,
        "Sales": sales.round(2), "Quantity": qty, "Discount": discount, "Profit": profit.round(2)})
    d = d.sort_values("Order Date").reset_index(drop=True)
    # dirty data to clean
    d = pd.concat([d, d.sample(50, random_state=1)], ignore_index=True)
    d.loc[d.sample(25, random_state=2).index, "Customer Name"] = None
    return d


def electromart(n=6000, seed=11):
    r = np.random.default_rng(seed)
    items = {"Laptop": ("Computers", 55000, 0.12, 0.55), "Desktop": ("Computers", 42000, 0.14, 0.30),
             "Smartphone": ("Mobiles", 24000, 0.10, 0.30), "Tablet": ("Mobiles", 20000, 0.12, 0.25),
             "Smart TV": ("Home", 38000, 0.13, 0.50), "Refrigerator": ("Home", 32000, 0.15, 0.35),
             "Headphones": ("Accessories", 3500, 0.35, 0.15), "Charger": ("Accessories", 900, 0.45, 0.10),
             "Printer": ("Computers", 11000, 0.16, 0.30)}
    names = list(items)
    item = r.choice(names, n, p=[0.1, 0.06, 0.14, 0.07, 0.07, 0.05, 0.22, 0.2, 0.09])
    state = r.choice(["Maharashtra", "Karnataka", "Delhi", "Tamil Nadu", "Gujarat", "Telangana"], n,
                     p=[0.28, 0.2, 0.17, 0.14, 0.11, 0.10])
    dates = pd.to_datetime("2024-04-01") + pd.to_timedelta(r.integers(0, 540, n), unit="D")
    price = np.array([items[i][1] for i in item]) * r.uniform(0.85, 1.15, n)
    margin = np.array([items[i][2] for i in item])
    p_hi = np.array([items[i][3] for i in item]) + np.where(state == "Delhi", 0.15, 0)
    hi = r.random(n) < p_hi
    disc = np.where(hi, r.choice([20, 25, 30], n), r.choice([0, 5, 10], n, p=[0.5, 0.3, 0.2]))
    qty = r.integers(1, 4, n)
    gross = price * qty
    revenue = gross * (1 - disc / 100)
    cost = gross * (1 - margin) * r.uniform(0.97, 1.03, n)
    cw = r.lognormal(0, 1.0, 400)
    cid = r.choice(400, n, p=cw / cw.sum())
    d = pd.DataFrame({
        "Invoice No": [f"INV{i:05d}" for i in range(1, n + 1)],
        "Invoice Date": dates.strftime("%d-%m-%Y"), "Client": [f"Client {c:03d}" for c in cid],
        "Item": item, "Item Category": [items[i][0] for i in item], "State": state,
        "Qty": qty, "Revenue": revenue.round(0), "Cost": cost.round(0), "Disc %": disc})
    return d.sort_values("Invoice No").reset_index(drop=True)


if __name__ == "__main__":
    superstore().to_csv("data/superstore_sample.csv", index=False)
    electromart().to_csv("data/electromart_sample.csv", index=False)
    print("Created data/superstore_sample.csv and data/electromart_sample.csv")
