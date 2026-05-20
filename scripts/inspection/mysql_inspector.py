#!/usr/bin/env python3
"""MySQL Data Inspector - Công cụ kiểm tra dữ liệu MySQL"""

import sys
import pymysql
from datetime import datetime

def connect_mysql():
    """Kết nối MySQL"""
    try:
        conn = pymysql.connect(
            host='localhost',
            user='root',
            password='root',
            database='app'
        )
        return conn
    except Exception as e:
        print(f"❌ Lỗi kết nối MySQL: {e}")
        sys.exit(1)

def run_query(conn, query, description=""):
    """Chạy SQL query"""
    try:
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if description:
            print(f"\n📋 {description}")
            print("-" * 70)
        
        if rows:
            # Print headers
            if isinstance(rows[0], dict):
                headers = list(rows[0].keys())
                print(" | ".join(f"{h:30}" for h in headers))
                print("-" * 70)
                # Print rows
                for row in rows:
                    print(" | ".join(f"{str(row[h]):30}" for h in headers))
            else:
                for row in rows:
                    print(row)
        else:
            print("(Không có dữ liệu)")
        
        cursor.close()
        return rows
    except Exception as e:
        print(f"❌ Lỗi SQL: {e}")
        return None

def main():
    conn = connect_mysql()
    
    print("\n" + "="*70)
    print("🗄️  MYSQL DATABASE INSPECTOR (app)")
    print("="*70)
    
    # 1. Overview
    run_query(conn, """
        SELECT TABLE_NAME, TABLE_ROWS 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_SCHEMA='app' 
        ORDER BY TABLE_ROWS DESC
    """, "📊 1. Tổng Quan Các Bảng")
    
    # 2. Customers
    run_query(conn, """
        SELECT COUNT(*) as 'Total Rows', 
               COUNT(DISTINCT customer_id) as 'Unique Customers',
               COUNT(DISTINCT customer_state) as 'States'
        FROM olist_customers_dataset
    """, "👥 2. Customers Statistics")
    
    # 3. Sample Customers
    run_query(conn, """
        SELECT customer_id, customer_city, customer_state 
        FROM olist_customers_dataset 
        LIMIT 5
    """, "👥 3. Sample Customers")
    
    # 4. Orders
    run_query(conn, """
        SELECT COUNT(*) as 'Total Orders',
               COUNT(DISTINCT customer_id) as 'Unique Customers',
               COUNT(DISTINCT order_status) as 'Order Statuses'
        FROM olist_orders_dataset
    """, "📦 4. Orders Statistics")
    
    # 5. Order Status Distribution
    run_query(conn, """
        SELECT order_status, COUNT(*) as count
        FROM olist_orders_dataset
        GROUP BY order_status
        ORDER BY count DESC
    """, "📦 5. Order Status Distribution")
    
    # 6. Sample Orders
    run_query(conn, """
        SELECT order_id, order_status, order_purchase_timestamp, order_delivered_customer_date
        FROM olist_orders_dataset 
        LIMIT 5
    """, "📦 6. Sample Orders")
    
    # 7. Order Items
    run_query(conn, """
        SELECT COUNT(*) as 'Total Items',
               COUNT(DISTINCT order_id) as 'Orders with Items',
               ROUND(SUM(price), 2) as 'Total Revenue',
               ROUND(AVG(price), 2) as 'Avg Price'
        FROM olist_order_items_dataset
    """, "🛒 7. Order Items Statistics")
    
    # 8. Sample Order Items
    run_query(conn, """
        SELECT order_id, order_item_id, product_id, price, freight_value
        FROM olist_order_items_dataset 
        LIMIT 5
    """, "🛒 8. Sample Order Items")
    
    # 9. Revenue Analysis
    run_query(conn, """
        SELECT 
            COUNT(DISTINCT o.order_id) as 'Total Orders',
            COUNT(DISTINCT o.customer_id) as 'Customers',
            ROUND(SUM(oi.price), 2) as 'Total Revenue',
            ROUND(AVG(oi.price), 2) as 'Avg Item Price',
            ROUND(SUM(oi.freight_value), 2) as 'Total Freight'
        FROM olist_orders_dataset o
        LEFT JOIN olist_order_items_dataset oi ON o.order_id = oi.order_id
    """, "💰 9. Revenue Summary")
    
    print("\n" + "="*70)
    print("✅ Kiểm tra hoàn tất")
    print("="*70)
    
    conn.close()

if __name__ == "__main__":
    main()
