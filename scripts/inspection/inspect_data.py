#!/usr/bin/env python3
"""Công cụ kiểm tra dữ liệu - Check Data Across Layers"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from pyspark.sql import SparkSession
import pymysql
from sqlalchemy import create_engine

def get_spark():
    return SparkSession.builder.appName("DataInspector").getOrCreate()

def show_mysql_data():
    """Hiển thị dữ liệu từ MySQL"""
    print("\n" + "="*70)
    print("📊 MySQL DATABASE (app)")
    print("="*70)
    
    try:
        engine = create_engine("mysql+pymysql://root:root@localhost:3306/app")
        conn = engine.connect()
        
        # Lấy danh sách bảng
        tables_query = "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='app' ORDER BY TABLE_NAME"
        result = conn.execute(tables_query)
        tables = [row[0] for row in result]
        
        print(f"\n📌 Tổng số bảng: {len(tables)}\n")
        
        for table in tables:
            count_query = f"SELECT COUNT(*) FROM {table}"
            count = conn.execute(count_query).fetchone()[0]
            print(f"  • {table}: {count:,} rows")
        
        conn.close()
    except Exception as e:
        print(f"❌ Lỗi kết nối MySQL: {e}")

def show_bronze_data():
    """Hiển thị dữ liệu từ Bronze Layer"""
    print("\n" + "="*70)
    print("🥉 BRONZE LAYER (data/bronze/)")
    print("="*70)
    
    spark = get_spark()
    spark.sparkContext.setLogLevel("ERROR")
    
    tables = [
        ("Customers", "data/bronze/customers"),
        ("Orders", "data/bronze/orders"),
        ("Order Items", "data/bronze/order_items"),
    ]
    
    for name, path in tables:
        try:
            df = spark.read.parquet(path)
            count = df.count()
            cols = len(df.columns)
            print(f"\n  📄 {name}")
            print(f"     • Rows: {count:,}")
            print(f"     • Columns: {cols}")
            print(f"     • Path: {path}")
            print(f"     • Columns: {', '.join(df.columns[:5])}{'...' if cols > 5 else ''}")
        except Exception as e:
            print(f"  ❌ {name}: {str(e)[:50]}")

def show_silver_data():
    """Hiển thị dữ liệu từ Silver Layer"""
    print("\n" + "="*70)
    print("🥈 SILVER LAYER (data/silver/) - CLEANED DATA")
    print("="*70)
    
    spark = get_spark()
    spark.sparkContext.setLogLevel("ERROR")
    
    tables = [
        ("Customers", "data/silver/customers"),
        ("Orders", "data/silver/orders"),
        ("Order Items", "data/silver/order_items"),
    ]
    
    for name, path in tables:
        try:
            df = spark.read.parquet(path)
            count = df.count()
            cols = len(df.columns)
            print(f"\n  📄 {name}")
            print(f"     • Rows: {count:,}")
            print(f"     • Columns: {cols}")
            print(f"     • Path: {path}")
            print(f"     • Columns: {', '.join(df.columns[:5])}{'...' if cols > 5 else ''}")
        except Exception as e:
            print(f"  ❌ {name}: {str(e)[:50]}")

def show_sample_data(table_name, layer, path, limit=5):
    """Hiển thị sample dữ liệu"""
    print("\n" + "="*70)
    print(f"📋 SAMPLE DATA - {layer} / {table_name}")
    print("="*70)
    
    spark = get_spark()
    spark.sparkContext.setLogLevel("ERROR")
    
    try:
        df = spark.read.parquet(path)
        print(f"\nShowing {min(limit, df.count())} rows:\n")
        df.limit(limit).show(truncate=False, vertical=False)
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    print("\n🔍 CDC PIPELINE - DATA INSPECTION TOOL")
    
    show_mysql_data()
    show_bronze_data()
    show_silver_data()
    
    # Sample data
    show_sample_data("Customers", "Silver", "data/silver/customers", 3)

if __name__ == "__main__":
    main()
