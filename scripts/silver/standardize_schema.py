"""Common schema rules for the silver layer."""

from pyspark.sql.functions import col, regexp_replace, to_timestamp, trim, when


COLUMN_RENAMES = {
    "product_name_lenght": "product_name_length",
    "product_description_lenght": "product_description_length",
}

TIMESTAMP_COLUMNS = {
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
    "shipping_limit_date",
    "review_creation_date",
    "review_answer_timestamp",
}

INTEGER_COLUMNS = {
    "order_item_id",
    "payment_sequential",
    "payment_installments",
    "review_score",
    "product_name_length",
    "product_description_length",
    "product_photos_qty",
    "product_weight_g",
    "product_length_cm",
    "product_height_cm",
    "product_width_cm",
}

DOUBLE_COLUMNS = {
    "geolocation_lat",
    "geolocation_lng",
    "price",
    "freight_value",
    "payment_value",
}

ZIP_COLUMNS = {
    "customer_zip_code_prefix",
    "geolocation_zip_code_prefix",
    "seller_zip_code_prefix",
}


def normalize_column_name(name):
    name = name.replace("\ufeff", "").strip().lower()
    name = name.replace(" ", "_").replace("-", "_")
    return COLUMN_RENAMES.get(name, name)


def normalize_columns(df):
    for old_name in df.columns:
        new_name = normalize_column_name(old_name)
        if old_name != new_name:
            df = df.withColumnRenamed(old_name, new_name)
    return df


def cast_columns(df):
    for column_name, dtype in df.dtypes:
        if dtype == "string":
            df = df.withColumn(
                column_name,
                when(trim(col(column_name)) == "", None).otherwise(trim(col(column_name))),
            )

    for column_name in TIMESTAMP_COLUMNS & set(df.columns):
        df = df.withColumn(column_name, to_timestamp(col(column_name)))

    for column_name in INTEGER_COLUMNS & set(df.columns):
        df = df.withColumn(column_name, col(column_name).cast("int"))

    for column_name in DOUBLE_COLUMNS & set(df.columns):
        df = df.withColumn(column_name, col(column_name).cast("double"))

    for column_name in ZIP_COLUMNS & set(df.columns):
        digits = regexp_replace(col(column_name).cast("string"), r"\D", "")
        df = df.withColumn(column_name, when(digits != "", digits))

    return df


def standardize_schema(df):
    return cast_columns(normalize_columns(df))
