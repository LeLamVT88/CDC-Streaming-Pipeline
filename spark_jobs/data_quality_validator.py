"""Data Quality Validator for Silver Layer"""

from pyspark.sql.functions import col, avg, min as f_min, max as f_max, sum as f_sum
from silver_utils import get_spark

def validate_table(spark, path, table_name):
    # Detect format: local (parquet) or dbfs (delta)
    fmt = "parquet" if not path.startswith("dbfs:") else "delta"
    df = spark.read.format(fmt).load(path)
    total = df.count()
    
    metrics = {'table': table_name, 'total_records': total}
    
    if table_name == 'customers':
        metrics.update({
            'nulls_id': df.filter(col("customer_id").isNull()).count(),
            'unique_customers': df.select("customer_id").distinct().count(),
            'unknown_cities': df.filter(col("customer_city") == "unknown").count(),
        })
    elif table_name == 'orders':
        metrics.update({
            'nulls_id': df.filter(col("order_id").isNull()).count(),
            'unknown_status': df.filter(col("order_status") == "unknown").count(),
            'delivered': df.filter(col("order_status") == "delivered").count(),
        })
        if df.filter(col("delivery_delay_days").isNotNull()).count() > 0:
            delay = df.select(avg("delivery_delay_days")).collect()[0][0]
            metrics['avg_delay_days'] = round(delay, 2) if delay else 0
    elif table_name == 'order_items':
        metrics.update({
            'nulls_order_id': df.filter(col("order_id").isNull()).count(),
            'zero_price': df.filter(col("price") == 0).count(),
            'unique_products': df.select("product_id").distinct().count(),
            'unique_sellers': df.select("seller_id").distinct().count(),
        })
        price = df.select(avg("price"), f_min("price"), f_max("price"), f_sum("price")).collect()[0]
        metrics.update({
            'avg_price': round(price[0], 2) if price[0] else 0,
            'min_price': price[1],
            'max_price': price[2],
            'total_sales': round(price[3], 2) if price[3] else 0,
        })
    
    return metrics

def print_report(metrics_list):
    print(f"\n{'='*70}")
    print("DATA QUALITY REPORT - SILVER LAYER")
    print(f"{'='*70}\n")
    
    for metrics in metrics_list:
        print(f"📊 {metrics['table'].upper()}")
        print(f"   Total Records: {metrics['total_records']:,}")
        for k, v in metrics.items():
            if k not in ['table', 'total_records']:
                print(f"   {k}: {v}")
        print()

def main():
    spark = get_spark()
    silver_base = "dbfs:/mnt/silver"
    
    metrics = [
        validate_table(spark, f"{silver_base}/customers", "customers"),
        validate_table(spark, f"{silver_base}/orders", "orders"),
        validate_table(spark, f"{silver_base}/order_items", "order_items"),
    ]
    
    print_report(metrics)
    spark.stop()

if __name__ == "__main__":
    main()
