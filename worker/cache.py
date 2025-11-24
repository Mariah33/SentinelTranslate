import hashlib
import os

import redis

# Redis DB 2 for caching (separate from broker/backend)
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_CACHE_DB = int(os.environ.get("REDIS_CACHE_DB", "2"))
CACHE_TTL = int(os.environ.get("CACHE_TTL", "86400"))  # 24 hours default

# Global Redis connection for caching
cache_client = redis.Redis(
    host=REDIS_HOST, port=REDIS_PORT, db=REDIS_CACHE_DB, decode_responses=True
)


def _make_cache_key(text: str, src_lang: str, tgt_lang: str) -> str:
    """Generate cache key: {src}-{tgt}:{hash}"""
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"{src_lang}-{tgt_lang}:{text_hash}"


def get_cached_translation(text: str, src_lang: str, tgt_lang: str) -> str | None:
    """
    Get cached translation from Redis.

    Returns:
        Cached translation string, or None if not found
    """
    key = _make_cache_key(text, src_lang, tgt_lang)
    return cache_client.get(key)


def set_cached_translation(text: str, src_lang: str, tgt_lang: str, translation: str) -> None:
    """
    Store translation in Redis cache.

    Args:
        text: Source text
        src_lang: Source language code
        tgt_lang: Target language code
        translation: Translated text to cache
    """
    key = _make_cache_key(text, src_lang, tgt_lang)
    cache_client.setex(key, CACHE_TTL, translation)
