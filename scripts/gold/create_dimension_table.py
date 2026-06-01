"""Create Gold dimensions from the S3 Silver layer."""

import argparse
import os
from pathlib import Path

try:
    from business_mapping import CONFIG, build_spark, get_nested, run_dimensions
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.gold.business_mapping import CONFIG, build_spark, get_nested, run_dimensions


def parse_args():
    parser = argparse.ArgumentParser(description="Build Gold dimensions from Silver parquet.")
    parser.add_argument(
        "--silver-path",
        default=os.environ.get("SILVER_PATH", get_nested(CONFIG, "s3", "silver_uri", default="data/silver")),
    )
    parser.add_argument(
        "--gold-path",
        default=os.environ.get("GOLD_PATH", get_nested(CONFIG, "s3", "gold_uri", default="data/gold")),
    )
    parser.add_argument("--mode", choices=["overwrite", "append"], default="overwrite")
    return parser.parse_args()


def main():
    args = parse_args()
    spark = build_spark("OlistGoldDimensions", args.silver_path, args.gold_path)
    try:
        run_dimensions(spark, args.silver_path, args.gold_path, args.mode)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
