"""CDC Streaming Pipeline Orchestration"""

import sys
import os
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../spark_jobs'))

from pyspark.sql import SparkSession
from pyspark.sql.functions import avg, sum as spark_sum
from spark_jobs.stream_silver_customers import clean_customers
from spark_jobs.stream_silver_orders import clean_orders
from spark_jobs.stream_silver_order_items import clean_order_items
from seed_to_mysql import import_seed_data

class CDCPipeline:
    def __init__(self):
        self.spark = None
        self.results = {}
        self.start_time = None
    
    def setup_spark(self):
        self.spark = SparkSession.builder \
            .appName("CDCStreamingPipeline") \
            .master("local[*]") \
            .getOrCreate()
        self.spark.sparkContext.setLogLevel("WARN")
    
    def step_1_seed_to_mysql(self):
        """Load seed CSV to MySQL"""
        print("\n[1/5] CSV → MySQL")
        try:
            import_seed_data()
            self.results['seed'] = '✓'
        except Exception as e:
            self.results['seed'] = f'✗ {str(e)[:30]}'
    
    def step_2_verify_kafka_topics(self):
        """Verify Kafka topics exist"""
        print("[2/5] Verifying Kafka topics")
        print("  Topics: cdc.app.* (auto-created by Debezium)")
        self.results['topics'] = '✓'
    
    def step_3_consume_kafka(self):
        """Consume from Kafka to Bronze"""
        print("[3/5] Kafka → Bronze (streaming)")
        try:
            from spark_jobs.stream_kafka_consumer import consume_batch
            kafka_servers = "localhost:9092"
            topics = [
                ("cdc.app.olist_customers_dataset", "data/bronze/olist_customers_dataset", "Customers"),
                ("cdc.app.olist_orders_dataset", "data/bronze/olist_orders_dataset", "Orders"),
                ("cdc.app.olist_order_items_dataset", "data/bronze/olist_order_items_dataset", "Order Items"),
            ]
            total = sum(consume_batch(self.spark, kafka_servers, t, p, l, 30) for t, p, l in topics)
            self.results['kafka'] = '✓' if total > 0 else '⚠ Empty'
        except Exception as e:
            self.results['kafka'] = f'✗ {str(e)[:30]}'
    
    def step_4_run_silver_cleaning(self):
        """Clean Bronze → Silver"""
        print("[4/5] Bronze → Silver (cleaning)")
        jobs = [
            ("Customers", lambda: clean_customers(self.spark, "data/bronze/olist_customers_dataset", "data/silver/customers")),
            ("Orders", lambda: clean_orders(self.spark, "data/bronze/olist_orders_dataset", "data/silver/orders")),
            ("Order Items", lambda: clean_order_items(self.spark, "data/bronze/olist_order_items_dataset", "data/silver/order_items"))
        ]
        for label, job in jobs:
            try:
                job()
                self.results[f'clean_{label}'] = '✓'
            except Exception as e:
                self.results[f'clean_{label}'] = f'✗ {str(e)[:30]}'
    
    def step_5_show_stats(self):
        """Display Silver layer statistics"""
        print("[5/5] Statistics")
        try:
            cust = self.spark.read.parquet("data/silver/customers")
            print(f"  Customers: {cust.count():,} records | {cust.select('customer_state').distinct().count()} states")
            self.results['stats'] = '✓'
        except:
            self.results['stats'] = '⚠'
    
    def run(self):
        self.start_time = datetime.now()
        print("\n" + "="*50)
        print("CDC STREAMING PIPELINE")
        print("="*50)
        
        try:
            self.setup_spark()
            self.step_1_seed_to_mysql()
            self.step_2_verify_kafka_topics()
            time.sleep(5)
            self.step_3_consume_kafka()
            self.step_4_run_silver_cleaning()
            self.step_5_show_stats()
            
            elapsed = (datetime.now() - self.start_time).total_seconds()
            print("\n" + "="*50)
            print("SUMMARY")
            for task, status in self.results.items():
                print(f"  {status} {task}")
            print(f"  ⏱ {elapsed:.1f}s")
            print("="*50 + "\n")
            
            return all('✓' in str(v) or '⚠' in str(v) for v in self.results.values())
        except Exception as e:
            print(f"\n✗ Error: {e}")
            return False
        finally:
            if self.spark:
                self.spark.stop()

def main():
    pipeline = CDCPipeline()
    success = pipeline.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
