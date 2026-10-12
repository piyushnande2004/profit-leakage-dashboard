# DAX Measures and Calculated Columns

Load `data/clean_sales.csv` into Power BI Desktop. The table will be named **clean_sales**.
If your file has no discount or customer column, skip the measures that use them.

## Date table (Modeling > New table)
```DAX
Date = CALENDARAUTO()
```
Add columns to it (Table tools > New column):
```DAX
Year = YEAR('Date'[Date])
Month Number = MONTH('Date'[Date])
Month = FORMAT('Date'[Date], "MMM yyyy")
Month Sort = YEAR('Date'[Date]) * 100 + MONTH('Date'[Date])
```
Select the `Month` column > Column tools > **Sort by column** > `Month Sort`.
Then Model view: drag `Date[Date]` onto `clean_sales[order_date]` (many-to-one, single direction).
Select the Date table > **Mark as date table**.

## Core measures (create in a table called `_Measures` via Enter data, or on clean_sales)
```DAX
Total Sales = SUM(clean_sales[sales])
Total Profit = SUM(clean_sales[profit])
Profit Margin % = DIVIDE([Total Profit], [Total Sales])
Order Lines = COUNTROWS(clean_sales)
Loss Lines = CALCULATE(COUNTROWS(clean_sales), clean_sales[profit] < 0)
Loss Line % = DIVIDE([Loss Lines], [Order Lines])
Total Losses = -CALCULATE(SUM(clean_sales[profit]), clean_sales[profit] < 0)
Avg Discount % = AVERAGE(clean_sales[discount])
```

## Leakage measures
```DAX
Discount Threshold = 0.30
High Discount Loss =
    -CALCULATE(SUM(clean_sales[profit]),
               clean_sales[discount] > [Discount Threshold],
               clean_sales[profit] < 0)
High Discount Lines =
    CALCULATE(COUNTROWS(clean_sales), clean_sales[discount] > [Discount Threshold])
Margin High Discount % =
    VAR s = CALCULATE(SUM(clean_sales[sales]), clean_sales[discount] > [Discount Threshold])
    VAR p = CALCULATE(SUM(clean_sales[profit]), clean_sales[discount] > [Discount Threshold])
    RETURN DIVIDE(p, s)
```
Tip: replace the fixed `Discount Threshold` with a **What-if parameter** (Modeling > New parameter, 0 to 0.6, step 0.05)
and a slicer, so viewers can move the threshold themselves.

## Time intelligence
```DAX
Sales LY = CALCULATE([Total Sales], SAMEPERIODLASTYEAR('Date'[Date]))
Sales YoY % = DIVIDE([Total Sales] - [Sales LY], [Sales LY])
Sales PM = CALCULATE([Total Sales], DATEADD('Date'[Date], -1, MONTH))
Sales MoM % = DIVIDE([Total Sales] - [Sales PM], [Sales PM])
Profit YTD = TOTALYTD([Total Profit], 'Date'[Date])
```

## Ranking and Pareto
```DAX
Sub-Category Profit Rank = RANKX(ALL(clean_sales[sub_category]), [Total Profit], , DESC)
Customer Profit Rank = RANKX(ALL(clean_sales[customer]), [Total Profit], , DESC)
Is Top 20% Customer =
    VAR n = DISTINCTCOUNT(clean_sales[customer])
    RETURN IF([Customer Profit Rank] <= n * 0.2, "Top 20%", "Other 80%")
```

## Calculated column: discount band (Table view > clean_sales > New column)
```DAX
Discount Band =
    SWITCH(TRUE(),
        clean_sales[discount] = 0, "0%",
        clean_sales[discount] <= 0.10, "1-10%",
        clean_sales[discount] <= 0.20, "11-20%",
        clean_sales[discount] <= 0.30, "21-30%",
        clean_sales[discount] <= 0.40, "31-40%",
        "Above 40%")
Discount Band Order =
    SWITCH(TRUE(), clean_sales[discount] = 0, 1, clean_sales[discount] <= 0.10, 2,
        clean_sales[discount] <= 0.20, 3, clean_sales[discount] <= 0.30, 4,
        clean_sales[discount] <= 0.40, 5, 6)
```
Set `Discount Band` > Sort by column > `Discount Band Order`.
