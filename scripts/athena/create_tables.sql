CREATE DATABASE IF NOT EXISTS olist_lakehouse;

CREATE EXTERNAL TABLE IF NOT EXISTS olist_lakehouse.dim_customers (
    customer_key string,
    customer_id string,
    customer_unique_id string,
    customer_zip_code_prefix string,
    customer_city string,
    customer_state string,
    _gold_processed_at timestamp
)
STORED AS PARQUET
LOCATION 's3://olist-lakehouse-data/gold/dim_customers/';

CREATE EXTERNAL TABLE IF NOT EXISTS olist_lakehouse.dim_geolocation (
    geolocation_key string,
    geolocation_zip_code_prefix string,
    geolocation_city string,
    geolocation_state string,
    geolocation_lat double,
    geolocation_lng double,
    _gold_processed_at timestamp
)
STORED AS PARQUET
LOCATION 's3://olist-lakehouse-data/gold/dim_geolocation/';

CREATE EXTERNAL TABLE IF NOT EXISTS olist_lakehouse.dim_products (
    product_key string,
    product_id string,
    product_category_name string,
    product_category_name_english string,
    product_name_length int,
    product_description_length int,
    product_photos_qty int,
    product_weight_g int,
    product_length_cm int,
    product_height_cm int,
    product_width_cm int,
    _gold_processed_at timestamp
)
STORED AS PARQUET
LOCATION 's3://olist-lakehouse-data/gold/dim_products/';

CREATE EXTERNAL TABLE IF NOT EXISTS olist_lakehouse.dim_sellers (
    seller_key string,
    seller_id string,
    seller_zip_code_prefix string,
    seller_city string,
    seller_state string,
    _gold_processed_at timestamp
)
STORED AS PARQUET
LOCATION 's3://olist-lakehouse-data/gold/dim_sellers/';

CREATE EXTERNAL TABLE IF NOT EXISTS olist_lakehouse.dim_dates (
    date_key int,
    date_day date,
    `year` int,
    quarter int,
    `month` int,
    `day` int,
    week_of_year int,
    day_of_week int,
    _gold_processed_at timestamp
)
STORED AS PARQUET
LOCATION 's3://olist-lakehouse-data/gold/dim_dates/';

CREATE EXTERNAL TABLE IF NOT EXISTS olist_lakehouse.fact_orders (
    order_key string,
    customer_key string,
    purchase_date_key int,
    order_id string,
    customer_id string,
    order_status string,
    order_purchase_timestamp timestamp,
    order_approved_at timestamp,
    order_delivered_carrier_date timestamp,
    order_delivered_customer_date timestamp,
    order_estimated_delivery_date timestamp,
    delivery_delay_days int,
    item_count bigint,
    product_count bigint,
    seller_count bigint,
    item_revenue double,
    freight_revenue double,
    total_order_value double,
    payment_count bigint,
    payment_type_count bigint,
    max_payment_installments int,
    payment_value double,
    review_count bigint,
    avg_review_score double,
    _gold_processed_at timestamp
)
STORED AS PARQUET
LOCATION 's3://olist-lakehouse-data/gold/fact_orders/';

CREATE EXTERNAL TABLE IF NOT EXISTS olist_lakehouse.fact_order_items (
    order_item_key string,
    order_key string,
    customer_key string,
    product_key string,
    seller_key string,
    purchase_date_key int,
    order_id string,
    order_item_id int,
    customer_id string,
    product_id string,
    seller_id string,
    order_status string,
    order_purchase_timestamp timestamp,
    shipping_limit_date timestamp,
    price double,
    freight_value double,
    total_item_value double,
    _gold_processed_at timestamp
)
STORED AS PARQUET
LOCATION 's3://olist-lakehouse-data/gold/fact_order_items/';

CREATE EXTERNAL TABLE IF NOT EXISTS olist_lakehouse.fact_order_payments (
    payment_key string,
    order_key string,
    customer_key string,
    purchase_date_key int,
    order_id string,
    payment_sequential int,
    customer_id string,
    order_status string,
    payment_type string,
    payment_installments int,
    payment_value double,
    _gold_processed_at timestamp
)
STORED AS PARQUET
LOCATION 's3://olist-lakehouse-data/gold/fact_order_payments/';

CREATE EXTERNAL TABLE IF NOT EXISTS olist_lakehouse.fact_order_reviews (
    review_key string,
    order_key string,
    customer_key string,
    purchase_date_key int,
    review_id string,
    order_id string,
    customer_id string,
    order_status string,
    review_score int,
    review_comment_title string,
    review_comment_message string,
    review_creation_date timestamp,
    review_answer_timestamp timestamp,
    _gold_processed_at timestamp
)
STORED AS PARQUET
LOCATION 's3://olist-lakehouse-data/gold/fact_order_reviews/';

CREATE EXTERNAL TABLE IF NOT EXISTS olist_lakehouse.mart_sales_daily (
    order_purchase_date date,
    orders bigint,
    items bigint,
    item_revenue double,
    freight_revenue double,
    total_revenue double,
    payment_value double,
    _gold_processed_at timestamp
)
STORED AS PARQUET
LOCATION 's3://olist-lakehouse-data/gold/mart_sales_daily/';

CREATE EXTERNAL TABLE IF NOT EXISTS olist_lakehouse.mart_sales_by_customer_state (
    customer_state string,
    orders bigint,
    customers bigint,
    total_revenue double,
    avg_order_value double,
    _gold_processed_at timestamp
)
STORED AS PARQUET
LOCATION 's3://olist-lakehouse-data/gold/mart_sales_by_customer_state/';

CREATE EXTERNAL TABLE IF NOT EXISTS olist_lakehouse.mart_product_category_performance (
    product_category_name_english string,
    orders bigint,
    products bigint,
    items bigint,
    total_revenue double,
    avg_item_price double,
    _gold_processed_at timestamp
)
STORED AS PARQUET
LOCATION 's3://olist-lakehouse-data/gold/mart_product_category_performance/';

CREATE EXTERNAL TABLE IF NOT EXISTS olist_lakehouse.mart_seller_performance (
    seller_id string,
    seller_state string,
    seller_city string,
    orders bigint,
    products bigint,
    total_revenue double,
    avg_item_value double,
    _gold_processed_at timestamp
)
STORED AS PARQUET
LOCATION 's3://olist-lakehouse-data/gold/mart_seller_performance/';

CREATE EXTERNAL TABLE IF NOT EXISTS olist_lakehouse.mart_order_status_summary (
    order_status string,
    orders bigint,
    avg_delivery_delay_days double,
    total_revenue double,
    _gold_processed_at timestamp
)
STORED AS PARQUET
LOCATION 's3://olist-lakehouse-data/gold/mart_order_status_summary/';
