"""
Builds an Excel report: a Summary sheet driven by live FORMULAS (SUM, SUMIFS, COUNTIF, AVERAGE, IFERROR)
that point at the Clean_Data sheet, plus analysis tables and a chart.
"""
import io
import pandas as pd
from openpyxl.chart import LineChart, BarChart, Reference
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
import analysis as an

FONT = "Arial"
HEAD_FILL = PatternFill("solid", start_color="1F3864")
INPUT_FILL = PatternFill("solid", start_color="FFFF99")
NUM = '#,##0;[Red]-#,##0'
PCT = '0.0%;[Red]-0.0%'


def _style_header(ws, row=1):
    for c in ws[row]:
        if c.value is not None:
            c.font = Font(name=FONT, bold=True, color="FFFFFF")
            c.fill = HEAD_FILL
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _autofit(ws, minw=10, maxw=40):
    for col in ws.columns:
        width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(width + 2, minw), maxw)


def _write_table(writer, name, df):
    if df is None or len(df) == 0:
        return
    df.to_excel(writer, sheet_name=name, index=False)
    ws = writer.sheets[name]
    _style_header(ws)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = Font(name=FONT)
            if isinstance(c.value, float):
                c.number_format = '#,##0.0;[Red]-#,##0.0'
    ws.freeze_panes = "A2"
    _autofit(ws)


def build_excel(df, quality_log, currency="₹", threshold=0.30):
    """Return the .xlsx file as bytes."""
    buf = io.BytesIO()
    cols = list(df.columns)
    n = len(df) + 1
    L = {c: get_column_letter(cols.index(c) + 1) for c in cols}
    rng = lambda c: f"Clean_Data!${L[c]}$2:${L[c]}${n}"

    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        data = df.copy()
        if "order_date" in data:
            data["order_date"] = data["order_date"].dt.strftime("%Y-%m-%d")
        data.to_excel(w, sheet_name="Clean_Data", index=False)
        ws = w.sheets["Clean_Data"]
        _style_header(ws); ws.freeze_panes = "A2"; _autofit(ws)
        for c in ws[2: min(n, 400)]:        # fonts for the visible part; keeps big files fast
            for x in c:
                x.font = Font(name=FONT)

        tables = {
            "Monthly": an.monthly(df), "Discount_Bands": an.discount_bands(df),
            "By_Category": an.by_field(df, "category"), "By_SubCategory": an.by_field(df, "sub_category"),
            "By_Region": an.by_field(df, "region"), "Loss_Products": an.loss_makers(df, "product", 25),
            "Top_Customers": (an.customer_pareto(df).head(25) if "customer" in df else None),
            "Data_Quality": quality_log,
        }
        for name, t in tables.items():
            _write_table(w, name, t)

        # ---------------- Summary sheet with formulas
        s = w.book.create_sheet("Summary", 0)
        s["A1"] = "Profit Leakage Summary"; s["A1"].font = Font(name=FONT, size=16, bold=True)
        s["A2"] = f"All figures are live formulas on the Clean_Data sheet. Currency: {currency}"
        s["A2"].font = Font(name=FONT, italic=True, color="595959")
        rows = [("Total sales", f"=SUM({rng('sales')})", NUM),
                ("Total profit", f"=SUM({rng('profit')})", NUM),
                ("Profit margin", "=IFERROR(B5/B4,0)", PCT),
                ("Order lines", f"=COUNTA({rng('sales')})", '#,##0'),
                ("Loss-making lines", f'=COUNTIF({rng("profit")},"<0")', '#,##0'),
                ("Loss-making share", "=IFERROR(B8/B7,0)", PCT),
                ("Total losses on those lines", f'=SUMIF({rng("profit")},"<0")', NUM)]
        s["A3"], s["B3"] = "Metric", "Value"
        for i, (label, f, fmt) in enumerate(rows, start=4):
            s[f"A{i}"], s[f"B{i}"] = label, f
            s[f"B{i}"].number_format = fmt
        r = 4 + len(rows)
        if "discount" in df:
            s[f"A{r}"], s[f"B{r}"] = "Average discount", f"=AVERAGE({rng('discount')})"
            s[f"B{r}"].number_format = PCT; r += 1
            s[f"A{r + 1}"] = "Discount threshold (edit me)"
            s[f"B{r + 1}"] = threshold; s[f"B{r + 1}"].number_format = '0%'
            s[f"B{r + 1}"].font = Font(name=FONT, color="0000FF"); s[f"B{r + 1}"].fill = INPUT_FILL
            t = f"$B${r + 1}"
            s[f"A{r + 2}"] = "Loss on lines discounted above threshold"
            s[f"B{r + 2}"] = f'=-SUMIFS({rng("profit")},{rng("discount")},">"&{t},{rng("profit")},"<0")'
            s[f"B{r + 2}"].number_format = NUM
            s[f"A{r + 3}"] = "Lines affected"
            s[f"B{r + 3}"] = f'=COUNTIFS({rng("discount")},">"&{t},{rng("profit")},"<0")'
            s[f"A{r + 4}"] = ("Assumption: capping the discount lets these lines at least break even, so the loss above "
                              "is an UPPER BOUND on recoverable profit.")
            s[f"A{r + 4}"].font = Font(name=FONT, italic=True, color="595959")
            r += 6
        if "region" in df:
            s[f"A{r}"], s[f"B{r}"], s[f"C{r}"], s[f"D{r}"] = "Region", "Sales", "Profit", "Margin"
            for c in "ABCD":
                s[f"{c}{r}"].font = Font(name=FONT, bold=True, color="FFFFFF"); s[f"{c}{r}"].fill = HEAD_FILL
            for j, reg in enumerate(sorted(df["region"].unique()), start=r + 1):
                s[f"A{j}"] = reg
                s[f"B{j}"] = f"=SUMIFS({rng('sales')},{rng('region')},$A{j})"
                s[f"C{j}"] = f"=SUMIFS({rng('profit')},{rng('region')},$A{j})"
                s[f"D{j}"] = f"=IFERROR(C{j}/B{j},0)"
                s[f"B{j}"].number_format = s[f"C{j}"].number_format = NUM
                s[f"D{j}"].number_format = PCT
        for row in s.iter_rows(min_row=3):
            for c in row:
                if c.font is None or c.font.name != FONT:
                    c.font = Font(name=FONT, bold=c.font.bold, italic=c.font.italic, color=c.font.color, size=c.font.size)
        for c in s[3]:
            if c.value:
                c.font = Font(name=FONT, bold=True, color="FFFFFF"); c.fill = HEAD_FILL
        s.column_dimensions["A"].width = 44
        for col in "BCD":
            s.column_dimensions[col].width = 16

        # ---------------- Charts
        if tables["Monthly"] is not None:
            m = w.sheets["Monthly"]; k = len(tables["Monthly"]) + 1
            ch = LineChart(); ch.title = "Monthly sales and profit"; ch.height, ch.width = 8, 18
            ch.add_data(Reference(m, min_col=2, max_col=3, min_row=1, max_row=k), titles_from_data=True)
            ch.set_categories(Reference(m, min_col=1, min_row=2, max_row=k))
            m.add_chart(ch, "L2")
        if tables["Discount_Bands"] is not None:
            d = w.sheets["Discount_Bands"]; k = len(tables["Discount_Bands"]) + 1
            ch = BarChart(); ch.title = "Profit by discount band"; ch.height, ch.width = 8, 14
            ch.add_data(Reference(d, min_col=3, min_row=1, max_row=k), titles_from_data=True)
            ch.set_categories(Reference(d, min_col=1, min_row=2, max_row=k))
            d.add_chart(ch, "K2")
    return buf.getvalue()
