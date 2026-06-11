import os
import time
import pandas as pd
from io import BytesIO
import argparse
from pathlib import Path

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
DEFAULT_BRONZE_PATH = os.environ.get("BRONZE_PATH", get_nested(CONFIG, "s3", "bronze_uri", default=None))


def is_s3_path(path: str | None) -> bool:
    return bool(path and path.startswith(("s3://", "s3a://")))


def s3_key_prefix(output_path: str | None, prefix: str) -> str:
    if not output_path:
        return prefix
    if not is_s3_path(output_path):
        return prefix
    without_scheme = output_path.replace("s3a://", "s3://", 1).removeprefix("s3://")
    parts = without_scheme.split("/", 1)
    return parts[1].strip("/") if len(parts) > 1 else prefix


def s3_bucket_name(output_path: str | None, bucket: str | None) -> str | None:
    if not is_s3_path(output_path):
        return bucket
    without_scheme = output_path.replace("s3a://", "s3://", 1).removeprefix("s3://")
    return without_scheme.split("/", 1)[0]


def upload_dataframe_to_s3(df: pd.DataFrame, bucket: str, key: str) -> None:
    """Ghi DataFrame thành Parquet rồi upload lên S3 (in-memory, không tạo file tạm)."""
    import boto3

    buffer = BytesIO()
    df.to_parquet(buffer, index=False, engine="pyarrow")
    buffer.seek(0)
    boto3.client("s3").put_object(Bucket=bucket, Key=key, Body=buffer.getvalue())


def write_dataframe_to_local(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False, engine="pyarrow")


def upload_seed_data(
    seed_dir: str,
    bucket: str | None,
    prefix: str = DEFAULT_S3_PREFIX,
    output_path: str | None = DEFAULT_BRONZE_PATH,
) -> None:
    if not os.path.exists(seed_dir):
        raise FileNotFoundError(f"{seed_dir} not found")

    csv_files = [f for f in os.listdir(seed_dir) if f.endswith(".csv")]
    if not csv_files:
        raise FileNotFoundError(f"No CSV files in {seed_dir}")

    use_s3 = is_s3_path(output_path)
    bucket = s3_bucket_name(output_path, bucket)
    prefix = s3_key_prefix(output_path, prefix)
    if use_s3 and not bucket:
        raise ValueError("S3 bucket is required when writing Bronze data to S3")

    destination = f"s3://{bucket}/{prefix}/" if use_s3 else str(Path(output_path or "data/bronze"))
    print(f"Found {len(csv_files)} CSV files -> {destination}\n")

    for file in csv_files:
        file_path  = os.path.join(seed_dir, file)
        table_name = os.path.splitext(file)[0]
        print(f"{file} -> {table_name}/")
        start = time.time()
        total_rows = 0

        chunks = pd.read_csv(file_path, chunksize=50_000)
        for i, chunk in enumerate(chunks):
            if use_s3:
                key = f"{prefix}/{table_name}/part_{i:04d}.parquet"
                upload_dataframe_to_s3(chunk, bucket, key)  # type: ignore[arg-type]
                print(f"  part_{i:04d}: {len(chunk):,} rows -> s3://{bucket}/{key}")
            else:
                part_path = Path(output_path or "data/bronze") / table_name / f"part_{i:04d}.parquet"
                write_dataframe_to_local(chunk, part_path)
                print(f"  part_{i:04d}: {len(chunk):,} rows -> {part_path}")
            total_rows += len(chunk)

        elapsed = time.time() - start
        print(f"  Done: {total_rows:,} rows total in {elapsed:.1f}s\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Upload seed CSV files to the S3 bronze layer as parquet.")
    parser.add_argument("--seed-dir", default=os.environ.get("SEED_DIR", DEFAULT_SEED_DIR))
    parser.add_argument(
        "--bucket",
        default=os.environ.get("S3_BUCKET", DEFAULT_S3_BUCKET),
        required=os.environ.get("S3_BUCKET", DEFAULT_S3_BUCKET) is None,
    )
    parser.add_argument("--prefix", default=os.environ.get("BRONZE_PREFIX", DEFAULT_S3_PREFIX))
    parser.add_argument("--output-path", default=DEFAULT_BRONZE_PATH)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print("Writing seed CSVs to Bronze layer...\n")
    upload_seed_data(args.seed_dir, args.bucket, args.prefix, args.output_path)
    print("All done!")
