CREATE OR REPLACE VIEW olist_lakehouse.vw_sales_daily AS
SELECT
    order_purchase_date,
    orders,
    items,
    item_revenue,
    freight_revenue,
    total_revenue,
    payment_value,
    CASE
        WHEN orders = 0 THEN 0.0
        ELSE total_revenue / orders
    END AS avg_order_value
FROM olist_lakehouse.mart_sales_daily;

CREATE OR REPLACE VIEW olist_lakehouse.vw_order_detail AS
SELECT
    o.order_id,
    o.order_status,
    d.date_day AS order_purchase_date,
    d."year" AS purchase_year,
    d.quarter AS purchase_quarter,
    d."month" AS purchase_month,
    c.customer_unique_id,
    c.customer_city,
    c.customer_state,
    o.item_count,
    o.product_count,
    o.seller_count,
    o.item_revenue,
    o.freight_revenue,
    o.total_order_value,
    o.payment_value,
    o.avg_review_score,
    o.delivery_delay_days,
    CASE
        WHEN o.delivery_delay_days > 0 THEN true
        ELSE false
    END AS is_delayed
FROM olist_lakehouse.fact_orders AS o
LEFT JOIN olist_lakehouse.dim_customers AS c
    ON o.customer_key = c.customer_key
LEFT JOIN olist_lakehouse.dim_dates AS d
    ON o.purchase_date_key = d.date_key;

CREATE OR REPLACE VIEW olist_lakehouse.vw_item_sales_detail AS
SELECT
    i.order_id,
    i.order_item_id,
    i.order_status,
    d.date_day AS order_purchase_date,
    d."year" AS purchase_year,
    d.quarter AS purchase_quarter,
    d."month" AS purchase_month,
    c.customer_state,
    p.product_id,
    p.product_category_name_english,
    s.seller_id,
    s.seller_city,
    s.seller_state,
    i.price,
    i.freight_value,
    i.total_item_value
FROM olist_lakehouse.fact_order_items AS i
LEFT JOIN olist_lakehouse.dim_dates AS d
    ON i.purchase_date_key = d.date_key
LEFT JOIN olist_lakehouse.dim_customers AS c
    ON i.customer_key = c.customer_key
LEFT JOIN olist_lakehouse.dim_products AS p
    ON i.product_key = p.product_key
LEFT JOIN olist_lakehouse.dim_sellers AS s
    ON i.seller_key = s.seller_key;

CREATE OR REPLACE VIEW olist_lakehouse.vw_payment_method_summary AS
SELECT
    payment_type,
    count(DISTINCT order_id) AS orders,
    count(*) AS payment_records,
    round(sum(payment_value), 2) AS payment_value,
    round(avg(payment_installments), 2) AS avg_installments
FROM olist_lakehouse.fact_order_payments
GROUP BY payment_type;

CREATE OR REPLACE VIEW olist_lakehouse.vw_review_score_summary AS
SELECT
    review_score,
    count(DISTINCT order_id) AS orders,
    count(*) AS reviews
FROM olist_lakehouse.fact_order_reviews
GROUP BY review_score;
