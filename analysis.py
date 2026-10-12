"""
Core engine: load ANY sales file, auto-detect its columns, clean it, and analyse profit leakage.
Works with CSV or Excel files whose columns have different names (Revenue vs Sales, State vs Region, ...).
"""
import io
import re
import numpy as np
import pandas as pd

# ---------------------------------------------------------------- column detection
# Synonyms are listed in priority order. Standard field names are used everywhere else.
FIELDS = {
    "sub_category": ["sub category", "subcategory", "sub cat", "product type"],
    "category": ["category", "item category", "product category", "department", "segment"],
    "order_id": ["order id", "invoice no", "invoice number", "invoice id", "order no", "order number",
                 "transaction id", "bill no", "invoice"],
    "order_date": ["order date", "invoice date", "transaction date", "purchase date", "bill date", "date"],
    "customer": ["customer name", "customer", "client", "client name", "buyer", "customer id"],
    "product": ["product name", "item name", "product", "item", "sku", "description"],
    "region": ["region", "state", "zone", "territory", "market", "area", "city"],
    "sales": ["sales", "revenue", "net sales", "sales amount", "total sales", "amount", "net revenue"],
    "quantity": ["quantity", "qty", "units", "units sold"],
    "discount": ["discount", "disc", "discount %", "disc %", "discount rate", "discount pct"],
    "cost": ["cost", "total cost", "cogs", "cost price", "cost of goods sold"],
    "profit": ["profit", "net profit", "gross profit", "earnings"],
}
LABELS = {
    "order_id": "Order / Invoice ID", "order_date": "Order date", "customer": "Customer",
    "product": "Product", "category": "Category", "sub_category": "Sub-category", "region": "Region / State",
    "sales": "Sales / Revenue  (required)", "quantity": "Quantity", "discount": "Discount",
    "cost": "Cost (if no profit column)", "profit": "Profit",
}
ORDER = ["sub_category", "category", "order_id", "order_date", "customer", "product", "region",
         "sales", "quantity", "discount", "cost", "profit"]
TEXT_FIELDS = ["order_id", "customer", "product", "category", "sub_category", "region"]


def _norm(s):
    return re.sub(r"[^a-z0-9%]+", " ", str(s).lower()).strip()


def guess_mapping(columns):
    """Return {standard_field: column_name_in_file} using synonym matching."""
    normed = {c: _norm(c) for c in columns}
    mapping, used = {}, set()
    for f in ORDER:                                   # pass 1: exact name match, in synonym priority
        for syn in FIELDS[f]:
            hit = next((c for c, n in normed.items() if c not in used and n == syn), None)
            if hit:
                mapping[f] = hit; used.add(hit); break
    for f in ORDER:                                   # pass 2: name contains a synonym
        if f in mapping:
            continue
        for syn in FIELDS[f]:
            if len(syn) < 4:
                continue
            hit = next((c for c, n in normed.items() if c not in used and syn in n), None)
            if hit:
                mapping[f] = hit; used.add(hit); break
    return mapping


def read_any(file_or_bytes, name="data.csv"):
    """Read a CSV / Excel upload (bytes or path) into a DataFrame."""
    low = name.lower()
    if isinstance(file_or_bytes, (bytes, bytearray)):
        file_or_bytes = io.BytesIO(file_or_bytes)
    if low.endswith((".xlsx", ".xls", ".xlsm")):
        return pd.read_excel(file_or_bytes)
    try:
        return pd.read_csv(file_or_bytes)
    except UnicodeDecodeError:
        if hasattr(file_or_bytes, "seek"):
            file_or_bytes.seek(0)
        return pd.read_csv(file_or_bytes, encoding="latin-1")


# ---------------------------------------------------------------- cleaning
def _to_num(s):
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce")
    return pd.to_numeric(s.astype(str).str.replace(r"[^\d.\-]", "", regex=True), errors="coerce")


def clean(raw, mapping, dayfirst=False):
    """Standardise columns, fix types, remove duplicates. Returns (clean_df, quality_log_df)."""
    log = []
    mapping = {f: c for f, c in mapping.items() if c}
    if "sales" not in mapping:
        raise ValueError("A Sales / Revenue column is required.")
    if "profit" not in mapping and "cost" not in mapping:
        raise ValueError("Need either a Profit column or a Cost column (profit = sales - cost).")

    df = pd.DataFrame({f: raw[c] for f, c in mapping.items()})
    log.append(("Rows in file", len(df), "-"))

    for f in TEXT_FIELDS:
        if f in df:
            df[f] = df[f].astype("string").str.strip().replace("", pd.NA)
    for f in ["sales", "quantity", "discount", "cost", "profit"]:
        if f in df:
            df[f] = _to_num(df[f])

    if "profit" not in df:
        df["profit"] = df["sales"] - df["cost"]
        log.append(("Profit column missing", len(df), "Calculated as Sales - Cost"))
    if "order_date" in df:
        df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce", dayfirst=dayfirst)
        bad = int(df["order_date"].isna().sum())
        log.append(("Unreadable dates", bad, "Rows kept; excluded from monthly trend" if bad else "None found"))
    if "discount" in df:
        if df["discount"].max() > 1.5:
            df["discount"] = df["discount"] / 100
            log.append(("Discount stored as %", len(df), "Converted to fraction (10 -> 0.10)"))
        df["discount"] = df["discount"].fillna(0)

    dups = int(df.duplicated().sum())
    df = df.drop_duplicates()
    log.append(("Duplicate rows", dups, "Removed" if dups else "None found"))

    miss = int(df[["sales", "profit"]].isna().any(axis=1).sum())
    df = df.dropna(subset=["sales", "profit"])
    log.append(("Rows missing Sales or Profit", miss, "Dropped" if miss else "None found"))

    for f in TEXT_FIELDS:
        if f in df:
            n = int(df[f].isna().sum())
            if n:
                df[f] = df[f].fillna("Unknown")
                log.append((f"Missing {f.replace('_', ' ')}", n, "Filled with 'Unknown'"))

    neg = int((df["sales"] < 0).sum())
    log.append(("Negative sales values (returns?)", neg, "Kept - review manually" if neg else "None found"))

    df["is_loss"] = (df["profit"] < 0).astype(int)
    if "order_date" in df:
        df["order_month"] = df["order_date"].dt.strftime("%Y-%m")
        df["order_year"] = df["order_date"].dt.year
    log.append(("Rows after cleaning", len(df), "Ready for analysis"))
    return df.reset_index(drop=True), pd.DataFrame(log, columns=["Check", "Count", "Action"])


# ---------------------------------------------------------------- analysis
def money(x, cur="₹"):
    return f"-{cur}{abs(x):,.0f}" if x < 0 else f"{cur}{x:,.0f}"


def kpis(df):
    s, p = df["sales"].sum(), df["profit"].sum()
    return dict(sales=s, profit=p, margin=p / s if s else 0,
                lines=len(df), loss_share=df["is_loss"].mean(),
                avg_discount=df["discount"].mean() if "discount" in df else None)


def _summ(g):
    out = g.agg(sales=("sales", "sum"), profit=("profit", "sum"), orders=("sales", "size"),
                loss_orders=("is_loss", "sum"))
    out["margin_pct"] = (out.profit / out.sales * 100).round(1)
    out["loss_order_pct"] = (out.loss_orders / out.orders * 100).round(1)
    return out


def monthly(df):
    if "order_month" not in df:
        return None
    m = _summ(df.dropna(subset=["order_month"]).groupby("order_month")).reset_index()
    m["sales_mom_pct"] = (m.sales.pct_change() * 100).round(1)
    m["profit_mom_pct"] = (m.profit.pct_change() * 100).round(1)
    return m


BANDS = [-0.001, 0.0, 0.10, 0.20, 0.30, 0.40, 10]
BAND_LABELS = ["0%", "1-10%", "11-20%", "21-30%", "31-40%", "Above 40%"]


def discount_bands(df):
    if "discount" not in df:
        return None
    d = df.assign(band=pd.cut(df["discount"], BANDS, labels=BAND_LABELS))
    return _summ(d.groupby("band", observed=True)).reset_index()


def by_field(df, field):
    if field not in df:
        return None
    return _summ(df.groupby(field)).reset_index().sort_values("profit")


def loss_makers(df, field, top=10):
    t = by_field(df, field)
    return None if t is None else t[t.profit < 0].head(top)


def customer_pareto(df):
    if "customer" not in df:
        return None
    c = df.groupby("customer").profit.sum().sort_values(ascending=False).reset_index()
    pos = c.profit.clip(lower=0)          # share of profit earned by profitable customers
    c["cum_profit_share"] = (pos.cumsum() / pos.sum() * 100).round(1)
    c["customer_pct"] = ((np.arange(len(c)) + 1) / len(c) * 100).round(1)
    return c


def leakage(df, threshold=0.30):
    """Loss-making orders that were discounted above `threshold`. Recovery is an UPPER BOUND:
    it assumes those orders would at least break even if the discount had been capped."""
    if "discount" not in df:
        return None
    hit = df[(df.discount > threshold) & (df.profit < 0)]
    high = df[df.discount > threshold]
    return dict(threshold=threshold, orders=len(hit), loss=-hit.profit.sum(),
                high_orders=len(high), high_margin=(high.profit.sum() / high.sales.sum()) if len(high) else 0,
                other_margin=(df[df.discount <= threshold].profit.sum() / df[df.discount <= threshold].sales.sum())
                if (df.discount <= threshold).any() else 0)


def insights(df, cur="₹", threshold=0.30):
    out, k = [], kpis(df)
    out.append(f"Sales were {money(k['sales'], cur)} with profit of {money(k['profit'], cur)} "
               f"({k['margin']:.1%} margin). {k['loss_share']:.0%} of order lines lost money.")
    if "discount" in df and not (df.discount > threshold).any():
        threshold = float(df.discount.quantile(0.75))     # adapt when discounts never exceed 30%
    lk = leakage(df, threshold)
    if lk and lk["high_orders"]:
        out.append(f"Orders discounted above {threshold:.0%} earn a {lk['high_margin']:.1%} margin versus "
                   f"{lk['other_margin']:.1%} for the rest. {lk['orders']:,} of them lost a combined "
                   f"{money(lk['loss'], cur)}; capping those discounts could recover up to that amount.")
    for field, label in [("sub_category", "sub-categories"), ("product", "products"), ("category", "categories")]:
        lm = loss_makers(df, field, 3)
        if lm is not None and len(lm):
            names = ", ".join(f"{r[field]} ({money(r.profit, cur)})" for _, r in lm.iterrows())
            out.append(f"Loss-making {label}: {names}.")
            break
    reg = by_field(df, "region")
    if reg is not None and len(reg) > 1:
        w, b = reg.sort_values("margin_pct").iloc[0], reg.sort_values("margin_pct").iloc[-1]
        out.append(f"Weakest region: {w.region} at {w.margin_pct}% margin; strongest: {b.region} at {b.margin_pct}%.")
    par = customer_pareto(df)
    if par is not None and len(par) >= 10:
        top = par[par.customer_pct <= 20].cum_profit_share.max()
        n_loss = int((par.profit < 0).sum())
        out.append(f"The top 20% of customers generate {top:.0f}% of the profit earned by profitable customers; "
                   f"{n_loss} customers are loss-making in total ({money(par[par.profit < 0].profit.sum(), cur)}).")
    m = monthly(df)
    if m is not None and len(m) >= 2:
        b, w = m.loc[m.profit.idxmax()], m.loc[m.profit.idxmin()]
        out.append(f"Best month: {b.order_month} ({money(b.profit, cur)} profit); "
                   f"worst month: {w.order_month} ({money(w.profit, cur)}).")
    return out
