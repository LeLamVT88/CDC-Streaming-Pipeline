import os
import pandas as pd
from sqlalchemy import create_engine
import time

def import_seed_data():
    db_user = 'root'
    db_password = 'root'
    db_host = 'localhost'
    db_port = '3306'
    db_name = 'app'

    engine = create_engine(f'mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}')
    seed_dir = os.path.join(os.path.dirname(__file__), '../../db/seed')
    
    if not os.path.exists(seed_dir):
        print(f"Error: {seed_dir} not found")
        return

    csv_files = [f for f in os.listdir(seed_dir) if f.endswith('.csv')]
    if not csv_files:
        print(f"No CSV files in {seed_dir}")
        return

    print(f"Found {len(csv_files)} CSV files")

    for file in csv_files:
        file_path = os.path.join(seed_dir, file)
        table_name = os.path.splitext(file)[0]
        
        print(f"\n{file} → {table_name}")
        start_time = time.time()
        
        try:
            for i, chunk in enumerate(pd.read_csv(file_path, chunksize=50000)):
                if i == 0:
                    chunk.to_sql(name=table_name, con=engine, if_exists='replace', index=False)
                    print(f"  Created: {len(chunk)} rows")
                else:
                    chunk.to_sql(name=table_name, con=engine, if_exists='append', index=False)
                    print(f"  Appended: {len(chunk)} rows")
                    
            elapsed = time.time() - start_time
            print(f"  ✓ Done in {elapsed:.1f}s")
            
        except Exception as e:
            print(f"  ✗ Error: {str(e)[:50]}")

if __name__ == "__main__":
    print("Seeding MySQL...")
    import_seed_data()
    print("\nAll done!")
