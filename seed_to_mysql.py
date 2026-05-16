import os
import pandas as pd
from sqlalchemy import create_engine
import time

def import_seed_data():
    # Database connection parameters
    db_user = 'root'
    db_password = 'root'
    db_host = 'localhost'
    db_port = '3306'
    db_name = 'app'

    # Create SQLAlchemy engine
    engine = create_engine(f'mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}')

    seed_dir = os.path.join(os.path.dirname(__file__), 'db', 'seed')
    
    if not os.path.exists(seed_dir):
        print(f"Error: Directory {seed_dir} not found.")
        return

    csv_files = [f for f in os.listdir(seed_dir) if f.endswith('.csv')]
    
    if not csv_files:
        print(f"No CSV files found in {seed_dir}")
        return

    print(f"Found {len(csv_files)} CSV files to import.")

    for file in csv_files:
        file_path = os.path.join(seed_dir, file)
        # Table name is the file name without extension
        table_name = os.path.splitext(file)[0]
        
        print(f"\nProcessing {file} -> Table: {table_name}")
        start_time = time.time()
        
        try:
            # Read CSV in chunks for better memory management with large files
            chunksize = 50000
            for i, chunk in enumerate(pd.read_csv(file_path, chunksize=chunksize)):
                # If first chunk, replace the table. Otherwise append.
                if i == 0:
                    chunk.to_sql(name=table_name, con=engine, if_exists='replace', index=False)
                    print(f"  Created table {table_name} and inserted first {len(chunk)} rows...")
                else:
                    chunk.to_sql(name=table_name, con=engine, if_exists='append', index=False)
                    print(f"  Appended next {len(chunk)} rows...")
                    
            elapsed_time = time.time() - start_time
            print(f"Successfully imported {file} in {elapsed_time:.2f} seconds.")
            
        except Exception as e:
            print(f"Error importing {file}: {str(e)}")

if __name__ == "__main__":
    print("Starting import process...")
    import_seed_data()
    print("\nAll done!")
