-- ============================================================================
-- Profit Leakage Analysis: SQL queries (SQLite syntax, also valid in PostgreSQL with
-- minor changes: replace order_month with TO_CHAR(order_date,'YYYY-MM')).
-- Table: sales(order_id, order_date, customer, product, category, sub_category, region,
--              sales, quantity, discount, profit, is_loss, order_month, order_year)
-- Run all:  python run_sql.py
-- ============================================================================

-- name: 01_monthly_sales_profit_mom_growth
-- Window function LAG(): month-over-month growth
WITH m AS (
    SELECT order_month AS month, ROUND(SUM(sales), 2) AS sales, ROUND(SUM(profit), 2) AS profit
    FROM sales WHERE order_month IS NOT NULL GROUP BY order_month)
SELECT month, sales, profit,
       ROUND(100.0 * profit / sales, 1) AS margin_pct,
       ROUND(100.0 * (sales - LAG(sales) OVER (ORDER BY month)) / LAG(sales) OVER (ORDER BY month), 1) AS sales_mom_pct
FROM m ORDER BY month;

-- name: 02_yearly_growth
SELECT order_year, ROUND(SUM(sales), 0) AS sales, ROUND(SUM(profit), 0) AS profit,
       ROUND(100.0 * (SUM(sales) - LAG(SUM(sales)) OVER (ORDER BY order_year))
             / LAG(SUM(sales)) OVER (ORDER BY order_year), 1) AS sales_yoy_pct
FROM sales WHERE order_year IS NOT NULL GROUP BY order_year ORDER BY order_year;

-- name: 03_profit_by_discount_band
-- CASE WHEN bucketing: the core "leakage" query
SELECT CASE WHEN discount = 0 THEN '1) 0%'
            WHEN discount <= 0.10 THEN '2) 1-10%'
            WHEN discount <= 0.20 THEN '3) 11-20%'
            WHEN discount <= 0.30 THEN '4) 21-30%'
            WHEN discount <= 0.40 THEN '5) 31-40%'
            ELSE '6) Above 40%' END AS discount_band,
       COUNT(*) AS order_lines, ROUND(SUM(sales), 0) AS sales, ROUND(SUM(profit), 0) AS profit,
       ROUND(100.0 * SUM(profit) / SUM(sales), 1) AS margin_pct,
       ROUND(100.0 * SUM(is_loss) / COUNT(*), 1) AS loss_line_pct
FROM sales GROUP BY 1 ORDER BY 1;

-- name: 04_top_loss_making_sub_categories
SELECT sub_category, category, COUNT(*) AS order_lines, ROUND(SUM(sales), 0) AS sales,
       ROUND(SUM(profit), 0) AS profit, ROUND(100.0 * SUM(profit) / SUM(sales), 1) AS margin_pct
FROM sales GROUP BY sub_category, category HAVING SUM(profit) < 0 ORDER BY profit LIMIT 10;

-- name: 05_sub_category_rank_within_category
-- RANK() with PARTITION BY
SELECT category, sub_category, ROUND(SUM(profit), 0) AS profit,
       RANK() OVER (PARTITION BY category ORDER BY SUM(profit) DESC) AS rank_in_category
FROM sales GROUP BY category, sub_category ORDER BY category, rank_in_category;

-- name: 06_region_performance
SELECT region, COUNT(*) AS order_lines, ROUND(SUM(sales), 0) AS sales, ROUND(SUM(profit), 0) AS profit,
       ROUND(100.0 * SUM(profit) / SUM(sales), 1) AS margin_pct, ROUND(AVG(discount) * 100, 1) AS avg_discount_pct
FROM sales GROUP BY region ORDER BY margin_pct;

-- name: 07_category_by_region_margin_matrix
SELECT category, region, ROUND(100.0 * SUM(profit) / SUM(sales), 1) AS margin_pct
FROM sales GROUP BY category, region ORDER BY category, margin_pct;

-- name: 08_loss_lines_above_30pct_discount_by_region
SELECT region, COUNT(*) AS loss_lines, ROUND(-SUM(profit), 0) AS total_loss
FROM sales WHERE discount > 0.30 AND profit < 0 GROUP BY region ORDER BY total_loss DESC;

-- name: 09_top_20_customers_share_of_profit
-- CTE + cumulative SUM() OVER
WITH c AS (
    SELECT customer, SUM(profit) AS profit FROM sales GROUP BY customer),
t AS (SELECT SUM(profit) AS total FROM c)
SELECT customer, ROUND(profit, 0) AS profit,
       ROUND(100.0 * profit / total, 2) AS share_pct,
       ROUND(100.0 * SUM(profit) OVER (ORDER BY profit DESC) / total, 1) AS cumulative_share_pct
FROM c, t ORDER BY profit DESC LIMIT 20;

-- name: 10_customer_quintiles_by_profit
-- NTILE(): Pareto check (quintile 1 = top 20% of customers)
WITH c AS (SELECT customer, SUM(profit) AS profit FROM sales GROUP BY customer),
q AS (SELECT customer, profit, NTILE(5) OVER (ORDER BY profit DESC) AS quintile FROM c)
SELECT quintile, COUNT(*) AS customers, ROUND(SUM(profit), 0) AS profit FROM q GROUP BY quintile ORDER BY quintile;

-- name: 11_running_total_profit
SELECT month, profit, ROUND(SUM(profit) OVER (ORDER BY month), 0) AS running_profit
FROM (SELECT order_month AS month, ROUND(SUM(profit), 0) AS profit FROM sales
      WHERE order_month IS NOT NULL GROUP BY order_month) ORDER BY month;

-- name: 12_best_and_worst_month_each_year
WITH m AS (SELECT order_year AS yr, order_month AS month, SUM(profit) AS profit FROM sales
           WHERE order_month IS NOT NULL GROUP BY order_year, order_month),
r AS (SELECT yr, month, ROUND(profit, 0) AS profit,
             RANK() OVER (PARTITION BY yr ORDER BY profit DESC) AS best_rank,
             RANK() OVER (PARTITION BY yr ORDER BY profit ASC) AS worst_rank FROM m)
SELECT yr, month, profit, CASE WHEN best_rank = 1 THEN 'Best month' ELSE 'Worst month' END AS label
FROM r WHERE best_rank = 1 OR worst_rank = 1 ORDER BY yr, label;

-- name: 13_loss_making_products_with_enough_volume
-- Only products sold at least 20 times (avoids noise)
SELECT product, COUNT(*) AS order_lines, ROUND(SUM(profit), 0) AS profit
FROM sales GROUP BY product HAVING COUNT(*) >= 20 AND SUM(profit) < 0 ORDER BY profit LIMIT 10;

-- name: 14_recoverable_profit_if_discounts_capped_at_30pct
-- UPPER BOUND: assumes capped-discount lines would at least break even
SELECT ROUND(SUM(CASE WHEN discount > 0.30 AND profit < 0 THEN -profit ELSE 0 END), 0) AS recoverable_profit_upper_bound,
       ROUND(SUM(profit), 0) AS current_profit
FROM sales;
