"""Example PySpark pipeline using ICU microservice.

This script demonstrates how to integrate the ICU microservice into a PySpark
data processing pipeline for text preprocessing and normalization.

Use Cases:
    - Multilingual text preprocessing for machine learning
    - Search index normalization
    - Text standardization for analytics
    - Data cleaning for translation pipelines

Usage:
    # Local execution
    spark-submit --master local[4] example_pipeline.py

    # Cluster execution
    spark-submit \
        --master yarn \
        --num-executors 10 \
        --executor-cores 4 \
        --executor-memory 8g \
        --conf spark.sql.execution.arrow.pyspark.enabled=true \
        --conf spark.sql.execution.arrow.maxRecordsPerBatch=500 \
        example_pipeline.py

Environment Variables:
    ICU_SERVICE_URL: ICU microservice endpoint (default: http://icu-service:8083)
    ICU_REQUEST_TIMEOUT: Request timeout in seconds (default: 30)
    ICU_BATCH_SIZE: Batch size for iterator UDFs (default: 500)
"""

import sys

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import avg, col, length, when

# Import ICU UDFs
try:
    from pyspark_integration import (
        ICUServiceClient,
        normalize_nfc,
        normalize_nfkc,
        transliterate_any_latin,
        transliterate_latin_ascii,
    )
except ImportError:
    print("Error: Could not import pyspark_integration module.")
    print("Make sure the pyspark_integration directory is in your PYTHONPATH:")
    print("  export PYTHONPATH=/path/to/icu-service:$PYTHONPATH")
    sys.exit(1)


def create_spark_session() -> SparkSession:
    """Create and configure Spark session for ICU processing.

    Returns:
        Configured SparkSession with Arrow optimization enabled
    """
    return (
        SparkSession.builder.appName("ICU-Text-Preprocessing")
        # Enable Apache Arrow for faster Pandas UDF execution
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        # Batch size for Arrow conversion (tune based on data size)
        .config("spark.sql.execution.arrow.maxRecordsPerBatch", "500")
        # Optimize shuffle partitions for small datasets
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )


def check_icu_service_health(client: ICUServiceClient) -> bool:
    """Verify ICU service is healthy before processing.

    Args:
        client: ICUServiceClient instance

    Returns:
        True if service is healthy, False otherwise
    """
    try:
        health = client.health_check()
        print(f"✓ ICU service healthy: {health}")
        return health.get("status") == "healthy"
    except Exception as e:
        print(f"✗ ICU service unavailable: {e}")
        return False


def create_sample_data(spark: SparkSession) -> DataFrame:
    """Create sample multilingual dataset for demonstration.

    Args:
        spark: SparkSession instance

    Returns:
        DataFrame with multilingual text samples
    """
    data = [
        ("1", "Café au lait", "French", "Food & Drink"),
        ("2", "naïve résumé", "French", "Documents"),
        ("3", "Zürich", "German", "Cities"),
        ("4", "Москва", "Russian", "Cities"),
        ("5", "東京", "Japanese", "Cities"),
        ("6", "Αθήνα", "Greek", "Cities"),
        ("7", "São Paulo", "Portuguese", "Cities"),
        ("8", "Björk Guðmundsdóttir", "Icelandic", "Names"),
        ("9", "Dvořák", "Czech", "Names"),
        ("10", "①②③ ½ ¼ ¾", "Symbols", "Numbers"),
    ]

    return spark.createDataFrame(data, ["id", "text", "language", "category"])


def preprocess_text(df: DataFrame) -> DataFrame:
    """Apply ICU transformations for text preprocessing.

    This function demonstrates a typical text preprocessing pipeline:
        1. Unicode normalization (NFC) - canonical form
        2. Compatibility normalization (NFKC) - for search/matching
        3. Transliteration to Latin script
        4. ASCII transliteration (remove diacritics)

    Args:
        df: Input DataFrame with 'text' column

    Returns:
        DataFrame with additional preprocessed columns
    """
    return (
        df
        # Step 1: Normalize to NFC (canonical composition)
        .withColumn("normalized_nfc", normalize_nfc(col("text")))
        # Step 2: Normalize to NFKC (compatibility decomposition + canonical composition)
        .withColumn("normalized_nfkc", normalize_nfkc(col("text")))
        # Step 3: Transliterate any script to Latin
        .withColumn("latin", transliterate_any_latin(col("normalized_nfc")))
        # Step 4: Remove diacritics for ASCII-only text
        .withColumn("ascii", transliterate_latin_ascii(col("latin")))
        # Step 5: Add text length for analysis
        .withColumn("original_length", length(col("text")))
        .withColumn("ascii_length", length(col("ascii")))
        # Step 6: Flag if transliteration changed the text
        .withColumn("was_transliterated", when(col("text") != col("ascii"), True).otherwise(False))
    )


def display_results(df: DataFrame, title: str) -> None:
    """Display DataFrame results in a formatted table.

    Args:
        df: DataFrame to display
        title: Title for the output section
    """
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80 + "\n")
    df.show(truncate=False)


def analyze_text_statistics(df: DataFrame) -> None:
    """Analyze and display text processing statistics.

    Args:
        df: DataFrame with preprocessing results
    """
    print("\n" + "=" * 80)
    print(" Text Processing Statistics")
    print("=" * 80 + "\n")

    # Count by category
    print("→ Records by Category:")
    df.groupBy("category").count().orderBy("category").show()

    # Transliteration statistics
    print("→ Transliteration Statistics:")
    df.groupBy("was_transliterated").count().show()

    # Average text lengths
    print("→ Average Text Lengths:")
    df.select(
        avg("original_length").alias("avg_original_length"),
        avg("ascii_length").alias("avg_ascii_length"),
    ).show()


def main() -> int:
    """Main pipeline execution.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    print("\n" + "=" * 80)
    print(" ICU Text Preprocessing Pipeline - Example")
    print("=" * 80 + "\n")

    # Step 1: Initialize Spark session
    print("→ Initializing Spark session...")
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")  # Reduce Spark logging verbosity

    try:
        # Step 2: Health check
        print("→ Checking ICU service health...")
        client = ICUServiceClient()
        if not check_icu_service_health(client):
            print("\n✗ Pipeline aborted: ICU service is not available")
            return 1

        # Step 3: Create sample data
        print("→ Creating sample dataset...")
        df_input = create_sample_data(spark)
        display_results(df_input.select("id", "text", "language", "category"), "Input Data")

        # Step 4: Apply ICU preprocessing
        print("→ Applying ICU transformations...")
        df_processed = preprocess_text(df_input)

        # Step 5: Display results
        display_results(
            df_processed.select("id", "text", "latin", "ascii", "was_transliterated"),
            "Preprocessing Results",
        )

        display_results(
            df_processed.select("id", "text", "normalized_nfc", "normalized_nfkc"),
            "Normalization Results",
        )

        # Step 6: Analyze statistics
        # Import avg function for statistics

        analyze_text_statistics(df_processed)

        # Step 7: Example - Save results to Parquet
        # Uncomment to save results
        # output_path = "s3://my-bucket/processed-texts/"
        # print(f"→ Saving results to {output_path}...")
        # df_processed.write.mode("overwrite").parquet(output_path)

        print("\n" + "=" * 80)
        print(" ✓ Pipeline completed successfully!")
        print("=" * 80 + "\n")

        return 0

    except Exception as e:
        print(f"\n✗ Pipeline failed: {e}")
        import traceback

        traceback.print_exc()
        return 1

    finally:
        # Step 8: Cleanup
        print("→ Stopping Spark session...")
        spark.stop()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
