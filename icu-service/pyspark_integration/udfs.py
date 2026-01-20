"""Pandas UDFs for ICU microservice integration with PySpark.

This module provides production-ready Pandas UDFs for common ICU text transformations.
Each UDF includes graceful error handling, logging, and falls back to the original text on errors.

Key Features:
- Standard Pandas UDFs for small-to-medium datasets
- Iterator-based UDFs for memory-efficient processing of large datasets
- Automatic batching for optimal HTTP request sizes
- Graceful error handling with fallback to original text
- Comprehensive logging for debugging and monitoring

Environment Variables:
    ICU_SERVICE_URL: ICU microservice endpoint (default: http://icu-service:8083)
    ICU_REQUEST_TIMEOUT: Request timeout in seconds (default: 30)
    ICU_BATCH_SIZE: Batch size for iterator UDFs (default: 500)

Example:
    from pyspark.sql import SparkSession
    from pyspark.sql.functions import col
    from pyspark_integration.udfs import transliterate_latin_ascii, normalize_nfc

    spark = SparkSession.builder.appName("ICU-Example").getOrCreate()
    df = spark.createDataFrame([("Café",), ("naïve",)], ["text"])

    # Apply transliteration
    df = df.withColumn("ascii", transliterate_latin_ascii(col("text")))
    df.show()
    # +-----+-----+
    # | text|ascii|
    # +-----+-----+
    # | Café| Cafe|
    # |naïve|naive|
    # +-----+-----+
"""

import logging
import os
from collections.abc import Iterator

import pandas as pd
from pyspark.sql.functions import pandas_udf
from pyspark.sql.types import StringType

from .client import ICUServiceClient

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Environment configuration
ICU_SERVICE_URL = os.getenv("ICU_SERVICE_URL", "http://icu-service:8083")
ICU_REQUEST_TIMEOUT = int(os.getenv("ICU_REQUEST_TIMEOUT", "30"))
ICU_BATCH_SIZE = int(os.getenv("ICU_BATCH_SIZE", "500"))

# Module-level client (shared across UDF calls for connection pooling)
_client = ICUServiceClient(base_url=ICU_SERVICE_URL, timeout=ICU_REQUEST_TIMEOUT)

logger.info(f"Initialized ICU UDFs: service={ICU_SERVICE_URL}, timeout={ICU_REQUEST_TIMEOUT}s, batch_size={ICU_BATCH_SIZE}")


# ==============================================================================
# Standard Pandas UDFs
# ==============================================================================


@pandas_udf(StringType())
def transliterate_latin_ascii(texts: pd.Series) -> pd.Series:
    """Transliterate Latin text to ASCII (remove diacritics).

    This UDF removes diacritics and accents from Latin-script text, converting
    characters like é, ñ, ü to their ASCII equivalents (e, n, u).

    Args:
        texts: Series of text strings to transliterate

    Returns:
        Series of ASCII-transliterated texts

    Example:
        >>> from pyspark.sql.functions import col
        >>> df = spark.createDataFrame([
        ...     ("Café au lait",),
        ...     ("naïve résumé",),
        ...     ("Zürich",),
        ... ], ["text"])
        >>> df = df.withColumn("ascii", transliterate_latin_ascii(col("text")))
        >>> df.show()
        +-------------+-------------+
        |         text|        ascii|
        +-------------+-------------+
        | Café au lait| Cafe au lait|
        |naïve résumé|naive resume|
        |      Zürich|      Zurich|
        +-------------+-------------+

    Note:
        On error, returns original text and logs warning. No exceptions raised.
    """
    texts_list = texts.tolist()
    try:
        results = _client.transliterate(texts_list, transform_id="Latin-ASCII", reverse=False)
        return pd.Series(results)
    except Exception as e:
        logger.warning(f"ICU service error in transliterate_latin_ascii: {e}. Returning original texts.")
        return texts


@pandas_udf(StringType())
def transliterate_any_latin(texts: pd.Series) -> pd.Series:
    """Transliterate any script to Latin.

    This UDF transliterates text from any script (Cyrillic, Greek, Arabic, etc.)
    to Latin script using ICU's Any-Latin transform.

    Args:
        texts: Series of text strings to transliterate

    Returns:
        Series of Latin-transliterated texts

    Example:
        >>> from pyspark.sql.functions import col
        >>> df = spark.createDataFrame([
        ...     ("Москва",),      # Russian
        ...     ("Αθήνα",),       # Greek
        ...     ("القاهرة",),     # Arabic
        ...     ("東京",),         # Japanese
        ... ], ["text"])
        >>> df = df.withColumn("latin", transliterate_any_latin(col("text")))
        >>> df.show()
        +------+--------+
        |  text|   latin|
        +------+--------+
        |Москва| Moskva|
        | Αθήνα|  Athína|
        |القاهرة|alqāhrẗ|
        |   東京|  dōngjīng|
        +------+--------+

    Note:
        On error, returns original text and logs warning. No exceptions raised.
    """
    texts_list = texts.tolist()
    try:
        results = _client.transliterate(texts_list, transform_id="Any-Latin", reverse=False)
        return pd.Series(results)
    except Exception as e:
        logger.warning(f"ICU service error in transliterate_any_latin: {e}. Returning original texts.")
        return texts


@pandas_udf(StringType())
def transliterate_cyrillic_latin(texts: pd.Series) -> pd.Series:
    """Transliterate Cyrillic text to Latin.

    This UDF specifically handles Cyrillic-to-Latin transliteration using
    ICU's Cyrillic-Latin transform.

    Args:
        texts: Series of text strings to transliterate

    Returns:
        Series of Latin-transliterated texts

    Example:
        >>> from pyspark.sql.functions import col
        >>> df = spark.createDataFrame([
        ...     ("Москва",),
        ...     ("Санкт-Петербург",),
        ...     ("Владивосток",),
        ... ], ["text"])
        >>> df = df.withColumn("latin", transliterate_cyrillic_latin(col("text")))
        >>> df.show()
        +---------------+-----------------+
        |           text|            latin|
        +---------------+-----------------+
        |         Москва|           Moskva|
        |Санкт-Петербург|Sankt-Peterburg|
        |    Владивосток|     Vladivostok|
        +---------------+-----------------+

    Note:
        On error, returns original text and logs warning. No exceptions raised.
    """
    texts_list = texts.tolist()
    try:
        results = _client.transliterate(texts_list, transform_id="Cyrillic-Latin", reverse=False)
        return pd.Series(results)
    except Exception as e:
        logger.warning(f"ICU service error in transliterate_cyrillic_latin: {e}. Returning original texts.")
        return texts


@pandas_udf(StringType())
def normalize_nfc(texts: pd.Series) -> pd.Series:
    """Normalize text to NFC (Canonical Decomposition followed by Canonical Composition).

    NFC is the recommended normalization form for most applications. It converts
    combining character sequences to precomposed characters when possible.

    Args:
        texts: Series of text strings to normalize

    Returns:
        Series of NFC-normalized texts

    Example:
        >>> from pyspark.sql.functions import col
        >>> # Text with combining characters
        >>> df = spark.createDataFrame([
        ...     ("e\u0301",),  # e + combining acute accent
        ...     ("café",),      # already NFC
        ... ], ["text"])
        >>> df = df.withColumn("normalized", normalize_nfc(col("text")))
        >>> df.show()
        +----+----------+
        |text|normalized|
        +----+----------+
        |   é|         é|  # Now precomposed
        |café|      café|  # Unchanged
        +----+----------+

    Note:
        On error, returns original text and logs warning. No exceptions raised.
    """
    texts_list = texts.tolist()
    try:
        results = _client.normalize(texts_list, form="NFC")
        return pd.Series(results)
    except Exception as e:
        logger.warning(f"ICU service error in normalize_nfc: {e}. Returning original texts.")
        return texts


@pandas_udf(StringType())
def normalize_nfkc(texts: pd.Series) -> pd.Series:
    """Normalize text to NFKC (Compatibility Decomposition followed by Canonical Composition).

    NFKC applies compatibility decomposition (e.g., ﬁ → fi, ² → 2) before
    canonical composition. Useful for search and matching applications.

    Args:
        texts: Series of text strings to normalize

    Returns:
        Series of NFKC-normalized texts

    Example:
        >>> from pyspark.sql.functions import col
        >>> df = spark.createDataFrame([
        ...     ("ﬁle",),      # ligature fi
        ...     ("x²",),       # superscript 2
        ...     ("①②③",),     # circled numbers
        ... ], ["text"])
        >>> df = df.withColumn("normalized", normalize_nfkc(col("text")))
        >>> df.show()
        +----+----------+
        |text|normalized|
        +----+----------+
        |ﬁle|      file|  # Ligature expanded
        |  x²|        x2|  # Superscript normalized
        | ①②③|       123|  # Circled numbers normalized
        +----+----------+

    Note:
        On error, returns original text and logs warning. No exceptions raised.
    """
    texts_list = texts.tolist()
    try:
        results = _client.normalize(texts_list, form="NFKC")
        return pd.Series(results)
    except Exception as e:
        logger.warning(f"ICU service error in normalize_nfkc: {e}. Returning original texts.")
        return texts


@pandas_udf(StringType())
def case_mapping_upper_turkish(texts: pd.Series) -> pd.Series:
    """Apply Turkish uppercase transformation.

    Turkish has special casing rules: 'i' uppercases to 'İ' (dotted I),
    not 'I' (dotless I). This UDF uses locale-aware case mapping.

    Args:
        texts: Series of text strings to uppercase

    Returns:
        Series of Turkish-uppercased texts

    Example:
        >>> from pyspark.sql.functions import col
        >>> df = spark.createDataFrame([
        ...     ("istanbul",),
        ...     ("İzmir",),
        ... ], ["text"])
        >>> df = df.withColumn("upper", case_mapping_upper_turkish(col("text")))
        >>> df.show()
        +--------+--------+
        |    text|   upper|
        +--------+--------+
        |istanbul|İSTANBUL|  # Note: İ not I
        |   İzmir|   İZMİR|  # Preserves dotted I
        +--------+--------+

    Note:
        On error, returns original text and logs warning. No exceptions raised.
    """
    texts_list = texts.tolist()
    try:
        results = _client.case_mapping(texts_list, operation="upper", locale="tr")
        return pd.Series(results)
    except Exception as e:
        logger.warning(f"ICU service error in case_mapping_upper_turkish: {e}. Returning original texts.")
        return texts


# ==============================================================================
# Iterator-based UDFs for Large Datasets
# ==============================================================================


@pandas_udf(StringType())
def transliterate_latin_ascii_iter(iterator: Iterator[pd.Series]) -> Iterator[pd.Series]:
    """Iterator-based UDF for Latin-ASCII transliteration (memory-efficient).

    This UDF processes data in batches to avoid loading the entire partition into memory.
    Recommended for large datasets or when memory is constrained.

    The batch size is controlled by the ICU_BATCH_SIZE environment variable (default: 500).

    Args:
        iterator: Iterator of Series containing text strings

    Yields:
        Series of ASCII-transliterated texts

    Example:
        >>> from pyspark.sql.functions import col
        >>> # For large datasets, use iterator UDF
        >>> df = spark.read.parquet("s3://large-dataset/texts.parquet")
        >>> df = df.withColumn("ascii", transliterate_latin_ascii_iter(col("text")))
        >>> df.write.parquet("s3://output/processed.parquet")

    Environment Variables:
        ICU_BATCH_SIZE: Batch size for processing (default: 500)

    Note:
        - Processes data in configurable batches to limit memory usage
        - On error, returns original text for failed batch and logs warning
        - Connection is reused across batches for efficiency
    """
    batch_size = ICU_BATCH_SIZE

    for texts_series in iterator:
        texts = texts_series.tolist()
        results = []

        # Process in smaller batches to avoid overwhelming the service
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                batch_results = _client.transliterate(batch, transform_id="Latin-ASCII", reverse=False)
                results.extend(batch_results)
            except Exception as e:
                logger.warning(f"ICU service error in batch {i}-{i + batch_size}: {e}. Returning original texts.")
                results.extend(batch)

        yield pd.Series(results)


@pandas_udf(StringType())
def transliterate_any_latin_iter(iterator: Iterator[pd.Series]) -> Iterator[pd.Series]:
    """Iterator-based UDF for Any-Latin transliteration (memory-efficient).

    This UDF processes data in batches to avoid loading the entire partition into memory.
    Recommended for large datasets or when memory is constrained.

    Args:
        iterator: Iterator of Series containing text strings

    Yields:
        Series of Latin-transliterated texts

    Example:
        >>> from pyspark.sql.functions import col
        >>> df = spark.read.parquet("s3://large-dataset/multilingual.parquet")
        >>> df = df.withColumn("latin", transliterate_any_latin_iter(col("text")))

    Note:
        Processes data in configurable batches (ICU_BATCH_SIZE env var).
    """
    batch_size = ICU_BATCH_SIZE

    for texts_series in iterator:
        texts = texts_series.tolist()
        results = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                batch_results = _client.transliterate(batch, transform_id="Any-Latin", reverse=False)
                results.extend(batch_results)
            except Exception as e:
                logger.warning(f"ICU service error in batch {i}-{i + batch_size}: {e}. Returning original texts.")
                results.extend(batch)

        yield pd.Series(results)


@pandas_udf(StringType())
def normalize_nfc_iter(iterator: Iterator[pd.Series]) -> Iterator[pd.Series]:
    """Iterator-based UDF for NFC normalization (memory-efficient).

    This UDF processes data in batches to avoid loading the entire partition into memory.
    Recommended for large datasets or when memory is constrained.

    Args:
        iterator: Iterator of Series containing text strings

    Yields:
        Series of NFC-normalized texts

    Example:
        >>> from pyspark.sql.functions import col
        >>> df = spark.read.parquet("s3://large-dataset/texts.parquet")
        >>> df = df.withColumn("normalized", normalize_nfc_iter(col("text")))

    Note:
        Processes data in configurable batches (ICU_BATCH_SIZE env var).
    """
    batch_size = ICU_BATCH_SIZE

    for texts_series in iterator:
        texts = texts_series.tolist()
        results = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                batch_results = _client.normalize(batch, form="NFC")
                results.extend(batch_results)
            except Exception as e:
                logger.warning(f"ICU service error in batch {i}-{i + batch_size}: {e}. Returning original texts.")
                results.extend(batch)

        yield pd.Series(results)
