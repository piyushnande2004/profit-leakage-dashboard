# Data Dictionary (cleaned file: `data/clean_sales.csv`)

| Column | Type | Meaning | Notes |
|---|---|---|---|
| order_id | text | Order or invoice number | Optional |
| order_date | date (YYYY-MM-DD) | Date of the order | Unreadable dates become blank |
| customer | text | Customer name or ID | Missing values filled with "Unknown" |
| product | text | Product name | Optional |
| category | text | Product category | Optional |
| sub_category | text | Product sub-category | Optional |
| region | text | Region, state or zone | Optional |
| sales | number | Revenue after discount | Required |
| quantity | integer | Units sold | Optional |
| discount | fraction (0 to 1) | Discount given. 0.20 means 20% | Files with 0-100 values are divided by 100 |
| cost | number | Cost of the line | Only present if the file had cost instead of profit |
| profit | number | Sales minus cost | Calculated when the file has no profit column |
| is_loss | 0 / 1 | 1 if profit is below 0 | Added by the cleaning step |
| order_month | text (YYYY-MM) | Month of the order | Added |
| order_year | integer | Year of the order | Added |

## Cleaning rules (applied automatically)
1. Trim spaces, convert blank text to missing.
2. Strip currency symbols and commas from numbers ("Rs 1,200" becomes 1200).
3. Remove fully duplicated rows.
4. Drop rows with no sales or profit value.
5. Fill missing text fields with "Unknown".
6. Parse dates (day-first can be switched on in the app).

## Assumptions
- If the file has a Cost column and no Profit column: **Profit = Sales - Cost** (cost is treated as the total cost of the line, not per unit).
- "Recoverable profit" from capping discounts is an **upper bound**: it assumes capped lines would at least break even and ignores lost sales volume.
- The bundled sample files are **simulated**, with planted problems, not real company data.
