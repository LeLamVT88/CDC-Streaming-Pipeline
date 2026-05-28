import os
import time
import boto3
import pandas as pd
from io import BytesIO
import argparse

try:
    from scripts.common.config import get_nested, load_yaml, project_path
except ImportError:
    from pathlib import Path
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from scripts.common.config import get_nested, load_yaml, project_path

CONFIG = load_yaml()
DEFAULT_SEED_DIR = project_path(get_nested(CONFIG, "paths", "seed", default="db/seed"))
DEFAULT_S3_BUCKET = get_nested(CONFIG, "aws", "bucket", default=None)
DEFAULT_S3_PREFIX = get_nested(CONFIG, "s3", "bronze_prefix", default="bronze")

s3 = boto3.client("s3")


def upload_dataframe_to_s3(df: pd.DataFrame, bucket: str, key: str) -> None:
    """Ghi DataFrame thành Parquet rồi upload lên S3 (in-memory, không tạo file tạm)."""
    buffer = BytesIO()
    df.to_parquet(buffer, index=False, engine="pyarrow")
    buffer.seek(0)
    s3.put_object(Bucket=bucket, Key=key, Body=buffer.getvalue())


def upload_seed_data(
    seed_dir: str,
    bucket: str,
    prefix: str = DEFAULT_S3_PREFIX,
) -> None:
    if not os.path.exists(seed_dir):
        print(f"Error: {seed_dir} not found")
        return

    csv_files = [f for f in os.listdir(seed_dir) if f.endswith(".csv")]
    if not csv_files:
        print(f"No CSV files in {seed_dir}")
        return

    print(f"Found {len(csv_files)} CSV files  →  s3://{bucket}/{prefix}/\n")

    for file in csv_files:
        file_path  = os.path.join(seed_dir, file)
        table_name = os.path.splitext(file)[0]
        print(f"{file} → {prefix}/{table_name}/")
        start = time.time()
        total_rows = 0

        try:
            chunks = list(pd.read_csv(file_path, chunksize=50_000))
            for i, chunk in enumerate(chunks):
                # Mỗi chunk → 1 object Parquet riêng để tránh overwrite
                # Key pattern: bronze/<table>/part_<i>.parquet
                key = f"{prefix}/{table_name}/part_{i:04d}.parquet"
                upload_dataframe_to_s3(chunk, bucket, key)
                total_rows += len(chunk)
                print(f"  part_{i:04d}: {len(chunk):,} rows  →  s3://{bucket}/{key}")

            elapsed = time.time() - start
            print(f"  ✓ Done — {total_rows:,} rows total in {elapsed:.1f}s\n")

        except Exception as e:
            print(f"  ✗ Error: {str(e)[:80]}\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Upload seed CSV files to the S3 bronze layer as parquet.")
    parser.add_argument("--seed-dir", default=os.environ.get("SEED_DIR", DEFAULT_SEED_DIR))
    parser.add_argument(
        "--bucket",
        default=os.environ.get("S3_BUCKET", DEFAULT_S3_BUCKET),
        required=os.environ.get("S3_BUCKET", DEFAULT_S3_BUCKET) is None,
    )
    parser.add_argument("--prefix", default=os.environ.get("BRONZE_PREFIX", DEFAULT_S3_PREFIX))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print("Uploading seed CSVs to S3 Bronze layer...\n")
    upload_seed_data(args.seed_dir, args.bucket, args.prefix)
    print("All done!")
