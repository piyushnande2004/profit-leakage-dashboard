"""
Profit Leakage Analyzer: upload ANY company's sales file (CSV / Excel) and get an instant analysis.
Run:  streamlit run app.py
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

import analysis as an
import report_excel

st.set_page_config(page_title="Profit Leakage Analyzer", layout="wide")
st.title("Profit Leakage Analyzer")
st.caption("Upload any company's sales file (CSV or Excel). The app detects your columns, cleans the data "
           "and shows where money is being lost, then exports an Excel report and a Power BI-ready file.")

SAMPLES = {"Sample 1: Superstore-style retailer": "data/superstore_sample.csv",
           "Sample 2: ElectroMart (different column names, no profit column)": "data/electromart_sample.csv"}
NONE = "(none)"
COLORS = {"Loss": "#dc2626", "Profit": "#16a34a"}

# ------------------------------------------------------------------ sidebar: data source
src = st.sidebar.radio("Data source", ["Upload my file"] + list(SAMPLES))
cur = st.sidebar.text_input("Currency symbol", "₹")


@st.cache_data(show_spinner=False)
def load(content, name):
    return an.read_any(content, name)


if src == "Upload my file":
    up = st.sidebar.file_uploader("CSV or Excel file", type=["csv", "xlsx", "xls"])
    if up is None:
        st.info("Upload a sales file in the sidebar, or pick a sample dataset to see how it works.\n\n"
                "**Minimum needed:** a Sales/Revenue column, plus either a Profit column or a Cost column. "
                "Dates, customers, products, categories, regions and discounts unlock more analysis.")
        st.stop()
    raw, name = load(up.getvalue(), up.name), up.name
else:
    path = SAMPLES[src]
    raw, name = load(path, path), path

dayfirst = st.sidebar.checkbox("Dates are day-first (31-12-2025)", value="electromart" in name.lower(),
                               key=f"dayfirst_{name}")

# ------------------------------------------------------------------ column mapping
guess = an.guess_mapping(raw.columns)
mapping = {}
with st.sidebar.expander("Column mapping (auto-detected, edit if wrong)", expanded=False):
    options = [NONE] + list(raw.columns)
    for f in an.ORDER:
        idx = options.index(guess[f]) if f in guess else 0
        choice = st.selectbox(an.LABELS[f], options, index=idx, key=f"{name}_{f}")
        mapping[f] = None if choice == NONE else choice

try:
    df_all, quality = an.clean(raw, mapping, dayfirst=dayfirst)
except ValueError as e:
    st.error(f"{e} Open 'Column mapping' in the sidebar and choose the right columns.")
    st.stop()
if df_all.empty:
    st.error("No usable rows after cleaning. Check the column mapping and the day-first date setting.")
    st.stop()

# ------------------------------------------------------------------ filters
df = df_all
st.sidebar.header("Filters")
if "order_date" in df and df.order_date.notna().any():
    lo, hi = df.order_date.min().date(), df.order_date.max().date()
    rng = st.sidebar.date_input("Date range", (lo, hi), min_value=lo, max_value=hi, key=f"dr_{name}")
    if isinstance(rng, tuple) and len(rng) == 2:
        df = df[(df.order_date.isna()) | ((df.order_date.dt.date >= rng[0]) & (df.order_date.dt.date <= rng[1]))]
for f, label in [("region", "Region"), ("category", "Category")]:
    if f in df:
        vals = sorted(df[f].unique())
        sel = st.sidebar.multiselect(label, vals, default=vals, key=f"{name}_flt_{f}")
        df = df[df[f].isin(sel)]
if df.empty:
    st.warning("The current filters leave no data.")
    st.stop()

k = an.kpis(df)
mapped_txt = ", ".join(f"{an.LABELS[f].split('  ')[0]} = '{c}'" for f, c in mapping.items() if c)
st.caption(f"Detected columns: {mapped_txt}")


def sign_bar(t, x, y, horizontal=False, title=""):
    t = t.assign(result=lambda d: d.profit.lt(0).map({True: "Loss", False: "Profit"}))
    fig = px.bar(t, x=y if horizontal else x, y=x if horizontal else y, color="result",
                 color_discrete_map=COLORS, orientation="h" if horizontal else "v", title=title)
    fig.update_layout(showlegend=False, margin=dict(t=50, b=10))
    return fig


tabs = st.tabs(["Overview", "Profit leakage", "Products & categories", "Regions & customers",
                "Data quality", "Export"])

# ------------------------------------------------------------------ Overview
with tabs[0]:
    c = st.columns(5)
    c[0].metric("Sales", an.money(k["sales"], cur))
    c[1].metric("Profit", an.money(k["profit"], cur))
    c[2].metric("Profit margin", f"{k['margin']:.1%}")
    c[3].metric("Loss-making lines", f"{k['loss_share']:.0%}")
    c[4].metric("Average discount", f"{k['avg_discount']:.1%}" if k["avg_discount"] is not None else "n/a")
    st.subheader("Key findings")
    for t in an.insights(df, cur):
        st.markdown(f"- {t}")
    m = an.monthly(df)
    if m is not None and len(m) > 1:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(x=m.order_month, y=m.sales, name="Sales", marker_color="#93c5fd"), secondary_y=False)
            fig.add_trace(go.Scatter(x=m.order_month, y=m.profit, name="Profit", mode="lines+markers",
                            line=dict(color="#16a34a", width=3)), secondary_y=True)
            fig.update_yaxes(title_text="Sales", secondary_y=False)
            fig.update_yaxes(title_text="Profit", secondary_y=True)
            fig.update_layout(title="Monthly sales (bars) and profit (line)", legend_title_text="", margin=dict(t=50))
            st.plotly_chart(fig, width="stretch")

# ------------------------------------------------------------------ Profit leakage
with tabs[1]:
    if "discount" not in df:
        st.info("No discount column was found, so discount leakage can't be analysed. "
                "Map a discount column in the sidebar if your file has one.")
    else:
        mx = float(df.discount.max())
        if mx <= 0:
            st.info("This file has no discounts above 0%.")
        else:
            top = max(0.05, round(mx - 0.05, 2))
            thr = st.slider("Flag orders discounted above", 0.0, top, min(0.30, top), 0.05, format="%.2f")
            lk = an.leakage(df, thr)
            a, b, c2, d = st.columns(4)
            a.metric("Loss-making lines above threshold", f"{lk['orders']:,}")
            b.metric("Money lost on them", an.money(lk["loss"], cur))
            c2.metric("Margin above threshold", f"{lk['high_margin']:.1%}")
            d.metric("Margin at or below", f"{lk['other_margin']:.1%}")
            st.caption("Recoverable profit is an upper bound: it assumes these lines would at least break even if "
                       "the discount were capped. Real recovery depends on whether customers still buy.")
            bands = an.discount_bands(df)
            left, right = st.columns(2)
            left.plotly_chart(sign_bar(bands, "band", "profit", title="Profit by discount band"), width="stretch")
            right.plotly_chart(px.bar(bands, x="band", y="loss_order_pct", title="% of lines that lose money")
                               .update_layout(margin=dict(t=50)), width="stretch")
            st.subheader("Worst 15 order lines")
            show = [c_ for c_ in ["order_id", "order_date", "customer", "product", "region", "sales", "discount", "profit"]
                    if c_ in df]
            st.dataframe(df.nsmallest(15, "profit")[show], width="stretch")

# ------------------------------------------------------------------ Products
with tabs[2]:
    fields = [f for f in ["category", "sub_category", "product"] if f in df]
    if not fields:
        st.info("No category or product columns were mapped.")
    else:
        f = st.radio("Group by", fields, horizontal=True, format_func=lambda x: x.replace("_", " ").title())
        t = an.by_field(df, f)
        view = pd.concat([t.head(15), t.tail(15)]).drop_duplicates(f) if len(t) > 30 else t
        st.plotly_chart(sign_bar(view, f, "profit", horizontal=True, title=f"Profit by {f.replace('_', ' ')}"),
                        width="stretch")
        lm = an.loss_makers(df, f, 15)
        st.subheader("Loss-making " + f.replace("_", " ") + "s")
        st.dataframe(lm if len(lm) else pd.DataFrame({"result": ["None: every group is profitable"]}),
                     width="stretch")

# ------------------------------------------------------------------ Regions & customers
with tabs[3]:
    left, right = st.columns(2)
    reg = an.by_field(df, "region")
    if reg is not None:
        left.plotly_chart(sign_bar(reg.sort_values("margin_pct"), "region", "margin_pct",
                                   title="Profit margin % by region"), width="stretch")
        if "category" in df:
            piv = df.groupby(["category", "region"]).apply(lambda g: g.profit.sum() / g.sales.sum() * 100,
                                                           include_groups=False).unstack().round(1)
            right.plotly_chart(px.imshow(piv, text_auto=True, color_continuous_scale="RdYlGn", aspect="auto",
                                         title="Margin % heatmap: category x region"), width="stretch")
    else:
        left.info("No region column mapped.")
    par = an.customer_pareto(df)
    if par is not None:
        fig = px.line(par, x="customer_pct", y="cum_profit_share",
                      title="Customer concentration: cumulative share of profit",
                      labels={"customer_pct": "% of customers (best first)", "cum_profit_share": "% of profit"})
        st.plotly_chart(fig, width="stretch")
        st.dataframe(par.head(10), width="stretch")

# ------------------------------------------------------------------ Data quality
with tabs[4]:
    st.subheader("Cleaning log")
    st.dataframe(quality, width="stretch")
    st.subheader("Column mapping used")
    st.dataframe(pd.DataFrame([(an.LABELS[f].split("  ")[0], c) for f, c in mapping.items() if c],
                              columns=["Field", "Column in your file"]), width="stretch")
    st.subheader("Cleaned data preview")
    st.dataframe(df.head(100), width="stretch")

# ------------------------------------------------------------------ Export
with tabs[5]:
    st.write("Download the results as files you can open in Excel and Power BI.")
    out = df.copy()
    if "order_date" in out:
        out["order_date"] = out["order_date"].dt.strftime("%Y-%m-%d")
    memo = "# Profit Leakage: Findings Memo\n\n" + "\n".join(f"- {t}" for t in an.insights(df, cur))
    c1, c2, c3 = st.columns(3)
    c1.download_button("Excel report (formulas + charts)", report_excel.build_excel(df, quality, cur),
                       "profit_leakage_report.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    c2.download_button("Cleaned data (CSV for Power BI / SQL)", out.to_csv(index=False), "clean_sales.csv", "text/csv")
    c3.download_button("Findings memo (Markdown)", memo, "insights_memo.md", "text/markdown")
    st.caption("Load clean_sales.csv into Power BI Desktop and follow powerbi/BUILD_GUIDE.md to build the dashboard.")
