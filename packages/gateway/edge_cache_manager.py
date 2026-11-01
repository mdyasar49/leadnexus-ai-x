"""
LeadNexus AI X — Phase 37: Edge Cache Manager & ETag Engine
Provides deterministic ETag generation, 304 Not Modified validation,
TTL eviction, and tag-based cache invalidation.
"""

import time
import hashlib
import json
from typing import Dict, Any, List, Optional, Tuple


class EdgeCacheManager:
    """In-memory high performance edge response cache."""

    # Key -> {"data": Any, "etag": str, "expires_at": float, "tags": List[str]}
    _cache: Dict[str, Dict[str, Any]] = {}
    # Tag -> Set of keys
    _tag_index: Dict[str, set] = {}

    @classmethod
    def compute_etag(cls, data: Any) -> str:
        """Computes a deterministic strong ETag from data serialization."""
        if isinstance(data, (dict, list)):
            serialized = json.dumps(data, sort_keys=True, separators=(',', ':'))
        else:
            serialized = str(data)
        digest = hashlib.sha256(serialized.encode('utf-8')).hexdigest()[:32]
        return f'"{digest}"'

    @classmethod
    def get(
        cls,
        cache_key: str,
        if_none_match: Optional[str] = None
    ) -> Tuple[Optional[Any], bool, Optional[str]]:
        """
        Retrieves cached response.
        Returns (data, is_not_modified, etag).
        If if_none_match matches cached ETag, is_not_modified is True.
        """
        entry = cls._cache.get(cache_key)
        if not entry:
            return None, False, None

        # Check expiration
        now = time.time()
        if entry["expires_at"] < now:
            cls.delete(cache_key)
            return None, False, None

        etag = entry["etag"]

        if if_none_match and if_none_match.strip() == etag:
            return None, True, etag  # HTTP 304 Not Modified

        return entry["data"], False, etag

    @classmethod
    def set(
        cls,
        cache_key: str,
        data: Any,
        ttl_seconds: int = 60,
        tags: Optional[List[str]] = None
    ) -> str:
        """Stores response in cache with ETag and tagging."""
        etag = cls.compute_etag(data)
        expires_at = time.time() + ttl_seconds
        assigned_tags = tags or []

        cls._cache[cache_key] = {
            "data": data,
            "etag": etag,
            "expires_at": expires_at,
            "tags": assigned_tags,
        }

        for tag in assigned_tags:
            if tag not in cls._tag_index:
                cls._tag_index[tag] = set()
            cls._tag_index[tag].add(cache_key)

        return etag

    @classmethod
    def delete(cls, cache_key: str) -> None:
        """Deletes a single cache entry."""
        if cache_key in cls._cache:
            entry = cls._cache.pop(cache_key)
            for tag in entry.get("tags", []):
                if tag in cls._tag_index and cache_key in cls._tag_index[tag]:
                    cls._tag_index[tag].remove(cache_key)

    @classmethod
    def invalidate_tags(cls, tags: List[str]) -> int:
        """Invalidates all cache entries matching specified tags."""
        invalidated_count = 0
        keys_to_delete = set()
        for tag in tags:
            if tag in cls._tag_index:
                keys_to_delete.update(cls._tag_index[tag])

        for key in keys_to_delete:
            if key in cls._cache:
                cls.delete(key)
                invalidated_count += 1

        return invalidated_count

    @classmethod
    def clear(cls) -> None:
        """Clears all cached entries and tag indexes."""
        cls._cache.clear()
        cls._tag_index.clear()

