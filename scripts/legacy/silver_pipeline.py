"""⚠️  LEGACY - Use scripts/py/pipeline_orchestration.py instead"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../spark_jobs'))

from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, avg, sum as spark_sum
from spark_jobs.stream_silver_customers import clean_customers
from spark_jobs.stream_silver_orders import clean_orders
from spark_jobs.stream_silver_order_items import clean_order_items
from datetime import datetime

def load_seed_to_bronze(spark, seed_dir="../../db/seed", bronze_dir="../../data/bronze"):
    """Load seed CSV files to bronze layer"""
    print("\n📥 Loading seed CSV files to bronze layer...\n")
    os.makedirs(bronze_dir, exist_ok=True)
    
    datasets = [
        ("olist_customers_dataset", "Customers"),
        ("olist_orders_dataset", "Orders"),
        ("olist_order_items_dataset", "Order Items")
    ]
    
    for file_name, label in datasets:
        print(f"  Reading: {file_name}.csv ({label})")
        df = spark.read.csv(f"{seed_dir}/{file_name}.csv", header=True, inferSchema=True)
        df = df.withColumn("_processing_timestamp", current_timestamp())
        df.write.format("parquet").mode("overwrite").save(f"{bronze_dir}/{file_name}")
        print(f"    ✓ Saved {df.count():,} records")
    print()

def run_silver_cleaning(spark, bronze_base="../../data/bronze", silver_base="../../data/silver"):
    """Run silver layer cleaning jobs"""
    print("✨ Running silver layer cleaning...\n")
    
    jobs = [
        ("Customers", lambda: clean_customers(spark, f"{bronze_base}/olist_customers_dataset", 
                                              f"{silver_base}/customers")),
        ("Orders", lambda: clean_orders(spark, f"{bronze_base}/olist_orders_dataset", 
                                        f"{silver_base}/orders")),
        ("Order Items", lambda: clean_order_items(spark, f"{bronze_base}/olist_order_items_dataset", 
                                                 f"{silver_base}/order_items"))
    ]
    
    results = {}
    for label, job_func in jobs:
        try:
            job_func()
            results[label] = '✓'
        except Exception as e:
            results[label] = f'✗ {str(e)[:40]}'
    
    return results

def show_stats(spark, silver_base="../../data/silver"):
    """Display silver layer statistics"""
    print("\n📊 SILVER LAYER STATISTICS:\n")
    
    try:
        cust = spark.read.parquet(f"{silver_base}/customers")
        print(f"✓ CUSTOMERS: {cust.count():,} records")
    except Exception as e:
        print(f"✗ CUSTOMERS: {e}")
    
    try:
        ord = spark.read.parquet(f"{silver_base}/orders")
        print(f"✓ ORDERS: {ord.count():,} records")
    except Exception as e:
        print(f"✗ ORDERS: {e}")
    
    try:
        items = spark.read.parquet(f"{silver_base}/order_items")
        print(f"✓ ORDER ITEMS: {items.count():,} records")
    except Exception as e:
        print(f"✗ ORDER ITEMS: {e}")

def main():
    spark = SparkSession.builder.appName("SilverPipeline").master("local[*]").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    start = datetime.now()
    
    print(f"\n{'='*60}")
    print("SILVER LAYER PIPELINE [LEGACY]")
    print(f"{'='*60}")
    
    try:
        load_seed_to_bronze(spark)
        results = run_silver_cleaning(spark)
        show_stats(spark)
        
        elapsed = (datetime.now() - start).total_seconds()
        success = all(v == '✓' for v in results.values())
        
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        for task, status in results.items():
            print(f"  {status} {task}")
        print(f"  ⏱  Total time: {elapsed:.2f}s")
        print(f"{'='*60}\n")
        
        return success
    
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        spark.stop()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
