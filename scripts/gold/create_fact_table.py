"""Build the complete Gold layer from Silver parquet.

This is the main Silver -> Gold entry point. It writes dimensions, facts, and
business-facing marts so one command produces a consistent Gold snapshot.
"""

import argparse
import os
from pathlib import Path

try:
    from business_mapping import CONFIG, build_spark, get_nested, run_gold_pipeline
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.gold.business_mapping import CONFIG, build_spark, get_nested, run_gold_pipeline


def parse_args():
    parser = argparse.ArgumentParser(description="Build Gold dimensions, facts, and marts from Silver parquet.")
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
    spark = build_spark("OlistSilverToGold", args.silver_path, args.gold_path)
    try:
        results = run_gold_pipeline(spark, args.silver_path, args.gold_path, args.mode)
        print("\nGold layer completed:")
        for model_name, row_count in results.items():
            print(f"  {model_name}: {row_count:,} rows")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
