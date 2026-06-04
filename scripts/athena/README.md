# Athena and Power BI

Athena exposes the Gold Parquet folders in S3 as queryable tables. Power BI can
then connect to Athena without copying data into another database.

## Data flow

```text
Silver Parquet
  -> Spark Gold dimensions, facts, and marts
  -> s3://olist-lakehouse-data/gold/<model>/
  -> Athena / AWS Glue Data Catalog
  -> Power BI
```

## Register the Gold tables

Prerequisites:

- Gold files exist under `s3://olist-lakehouse-data/gold/`.
- Athena can write query results to
  `s3://olist-lakehouse-data/athena-results/`.
- The Airflow AWS identity can use Athena, read the Gold S3 prefix, write the
  Athena results prefix, and read/write Glue Data Catalog metadata.

Run the Airflow DAG `olist_athena_refresh`. It executes:

1. `create_tables.sql` to register the dimensions, facts, and marts.
2. `create_views.sql` to create Power BI-friendly views.

The Gold folders are not partitioned, so Athena automatically sees replacement
Parquet files at the same S3 locations. Run the DAG again when tables or views
are missing. For a table schema or location change, alter or drop the existing
Glue table before rerunning because the DDL uses `IF NOT EXISTS`.

## Test queries

```sql
SELECT *
FROM olist_lakehouse.vw_sales_daily
ORDER BY order_purchase_date
LIMIT 100;
```

```sql
SELECT
    product_category_name_english,
    count(*) AS items,
    round(sum(price), 2) AS product_revenue
FROM olist_lakehouse.vw_item_sales_detail
GROUP BY product_category_name_english
ORDER BY product_revenue DESC
LIMIT 20;
```

```sql
SELECT
    customer_state,
    count(DISTINCT order_id) AS orders,
    round(sum(total_order_value), 2) AS total_revenue
FROM olist_lakehouse.vw_order_detail
GROUP BY customer_state
ORDER BY total_revenue DESC;
```

## Connect Power BI

1. Install the Amazon Athena ODBC driver on the Power BI Desktop machine.
2. Create an ODBC DSN with:
   - AWS Region: `ap-southeast-1`
   - Catalog: `AwsDataCatalog`
   - Workgroup: `primary`, or a dedicated Power BI workgroup
   - S3 output location: `s3://olist-lakehouse-data/athena-results/`
3. In Power BI Desktop, select **Get Data > Amazon Athena**.
4. Select the DSN and choose a connectivity mode.
5. Select the `olist_lakehouse` database and load the required tables or views.

Use `Import` for this Olist dataset. It gives faster visuals and avoids an
Athena query for every click. Use `DirectQuery` only when freshness is more
important than visual latency and Athena scan cost.

For Power BI Service scheduled refresh, install an on-premises data gateway and
configure the Athena driver as a **System DSN** on the gateway machine.

## Fast dashboard model

For a quick prototype, import these views:

- `vw_sales_daily`
- `vw_order_detail`
- `vw_item_sales_detail`
- `vw_payment_method_summary`
- `vw_review_score_summary`

The views are already shaped for common visuals and need minimal modeling.

## Recommended star schema

For a reusable semantic model, import:

- `dim_dates`
- `dim_customers`
- `dim_products`
- `dim_sellers`
- `fact_orders`
- `fact_order_items`

Create one-to-many, single-direction relationships:

```text
dim_dates[date_key]       -> fact_orders[purchase_date_key]
dim_dates[date_key]       -> fact_order_items[purchase_date_key]
dim_customers[customer_key] -> fact_orders[customer_key]
dim_customers[customer_key] -> fact_order_items[customer_key]
dim_products[product_key] -> fact_order_items[product_key]
dim_sellers[seller_key]   -> fact_order_items[seller_key]
```

Do not create a direct relationship between `fact_orders` and
`fact_order_items`. They have different grains and can cause double counting.

Example DAX measures:

```DAX
Total Revenue = SUM(fact_orders[total_order_value])

Orders = DISTINCTCOUNT(fact_orders[order_id])

Average Order Value = DIVIDE([Total Revenue], [Orders])

Items Sold = COUNTROWS(fact_order_items)

Product Revenue = SUM(fact_order_items[price])

Freight Revenue = SUM(fact_orders[freight_revenue])

Average Review Score = AVERAGE(fact_orders[avg_review_score])

Delayed Orders =
CALCULATE(
    [Orders],
    fact_orders[delivery_delay_days] > 0
)

Delayed Order Rate = DIVIDE([Delayed Orders], [Orders])
```

## Dashboard pages

### Executive overview

- KPI cards: Total Revenue, Orders, Average Order Value, Items Sold
- Line chart: `dim_dates[date_day]` by Total Revenue and Orders
- Bar or donut chart: `fact_orders[order_status]` by Orders
- Map or filled map: `dim_customers[customer_state]` by Total Revenue

### Product and seller performance

- Bar chart: product category by Product Revenue
- Table: seller, orders, products, and revenue
- Slicers: date, category, seller state, customer state

### Delivery and customer experience

- KPI cards: Average Review Score and Delayed Order Rate
- Bar chart: order status by Orders
- Distribution chart: delivery delay days
- Bar chart: review score by review count

## Refresh behavior

The current Gold DAG uses `schedule=None` and writes a complete snapshot with
`overwrite`. This means the dashboard is batch-refreshed, not real-time CDC.

- With Power BI `Import`, refresh the semantic model after the Gold pipeline
  completes.
- With `DirectQuery`, visuals query the latest files visible to Athena, but the
  Gold pipeline still determines data freshness.
