"""PySpark integration for ICU microservice.

This module provides a production-ready PySpark integration for the ICU microservice,
enabling distributed text processing with ICU transformations in Spark pipelines.

Key Features:
- HTTP client with connection pooling and retry logic
- Pandas UDFs for common ICU operations (transliteration, normalization, case mapping)
- Iterator-based UDFs for memory-efficient processing of large datasets
- Graceful error handling with fallback to original text
- Environment-based configuration

Quick Start:
    from pyspark.sql import SparkSession
    from pyspark.sql.functions import col
    from pyspark_integration import transliterate_latin_ascii, normalize_nfc

    spark = SparkSession.builder.appName("ICU-Example").getOrCreate()
    df = spark.createDataFrame([("Café",)], ["text"])
    df = df.withColumn("ascii", transliterate_latin_ascii(col("text")))
    df.show()

Environment Variables:
    ICU_SERVICE_URL: ICU microservice endpoint (default: http://icu-service:8083)
    ICU_REQUEST_TIMEOUT: Request timeout in seconds (default: 30)
    ICU_BATCH_SIZE: Batch size for iterator UDFs (default: 500)
"""

from .client import ICUServiceClient
from .udfs import (
    case_mapping_upper_turkish,
    normalize_nfc,
    normalize_nfkc,
    transliterate_any_latin,
    transliterate_cyrillic_latin,
    transliterate_latin_ascii,
    transliterate_latin_ascii_iter,
)

__version__ = "1.0.0"

__all__ = [
    "ICUServiceClient",
    "transliterate_latin_ascii",
    "transliterate_latin_ascii_iter",
    "transliterate_any_latin",
    "transliterate_cyrillic_latin",
    "normalize_nfc",
    "normalize_nfkc",
    "case_mapping_upper_turkish",
]
