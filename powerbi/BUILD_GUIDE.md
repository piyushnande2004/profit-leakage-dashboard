# Power BI Build Guide (about 60-90 minutes)

You need **Power BI Desktop** (free, Windows). A `.pbix` file can only be created inside Power BI Desktop,
so this guide gives you every step. Use the cleaned file produced by this project.

## Step 1: Get the data
1. Run `python run_pipeline.py` (or download **Cleaned data** from the app's Export tab).
2. Power BI Desktop > **Get data > Text/CSV** > choose `data/clean_sales.csv` > **Transform Data**.

## Step 2: Power Query clean-up (this shows "data cleaning" skills)
- Set types: `order_date` = Date, `sales` / `profit` = Fixed decimal number, `discount` = Percentage,
  `quantity` = Whole number.
- Rename the query to `clean_sales`.
- Check Column quality / Column profile (View tab) and note any errors in your documentation.
- **Close & Apply**.

## Step 3: Model
Follow `DAX_measures.md`: create the Date table, relationship, measures and the Discount Band column.

## Step 4: Build 3 pages

### Page 1: Executive Overview
- Cards: Total Sales, Total Profit, Profit Margin %, Loss Line %
- Line chart: Month (axis) x Total Sales and Total Profit
- Clustered column: Profit by Category
- Slicers: Year, Region, Category

### Page 2: Profit Leakage (your headline page)
- Column chart: Total Profit by Discount Band (conditional formatting: negative = red)
- Line or column: Loss Line % by Discount Band
- Cards: High Discount Loss, High Discount Lines, Margin High Discount %
- Table: Sub-Category, Total Sales, Total Profit, Profit Margin %, with data bars on profit
- Optional: What-if parameter slicer for the discount threshold

### Page 3: Customers and Regions
- Map or bar: Profit Margin % by Region
- Matrix: Category (rows) x Region (columns) showing Profit Margin %, with conditional formatting (red to green)
- Bar: top 10 and bottom 10 customers by Total Profit (Top N filter)
- Donut: Top 20% vs Other 80% customers, using `Is Top 20% Customer`

## Step 5: Polish
- Titles on every visual, consistent colors (red = loss, green = profit).
- Tooltips, a navigation bar with page buttons, and a one-line takeaway text box on each page.
- File > Options > turn on Q&A only if it helps.

## Step 6: Share
- Take screenshots of all 3 pages for your GitHub README (save in `screenshots/`).
- Save the `.pbix` in the repo (under 100 MB).
- Publish to web only if your Power BI account and college or company policy allow it.

## What to say in an interview
"I cleaned the data in Power Query, modelled it with a date table, wrote DAX measures for margin, loss rate
and high-discount loss, and built three pages so a manager can see where discounts turn into losses."
