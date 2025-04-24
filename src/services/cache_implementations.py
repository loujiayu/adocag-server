import json
import time
from typing import Optional, Any

# Abstract cache interface
class CacheInterface:
    """Abstract interface for cache implementations"""
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache by key"""
        raise NotImplementedError("Subclasses must implement get()")
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with optional TTL in seconds"""
        raise NotImplementedError("Subclasses must implement set()")
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        raise NotImplementedError("Subclasses must implement delete()")
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        raise NotImplementedError("Subclasses must implement exists()")

# Memory cache implementation
class MemoryCache(CacheInterface):
    """In-memory cache implementation"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MemoryCache, cls).__new__(cls)
            cls._instance._cache = {}  # {key: (value, expiry_time)}
        return cls._instance
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache, return None if expired or not found"""
        if key in self._cache:
            value, expiry = self._cache[key]
            if expiry == 0 or expiry > time.time():  # 0 means no expiry
                return value
            # Remove expired item
            del self._cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL in seconds"""
        expiry = 0 if ttl <= 0 else time.time() + ttl
        self._cache[key] = (value, expiry)
        return True
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache and is not expired"""
        if key in self._cache:
            _, expiry = self._cache[key]
            if expiry == 0 or expiry > time.time():
                return True
            # Remove expired item
            del self._cache[key]
        return False

# Redis cache implementation
class RedisCache(CacheInterface):
    """Redis-based cache implementation"""
    
    _instance = None
    
    def __new__(cls, redis_client=None):
        if cls._instance is None:
            cls._instance = super(RedisCache, cls).__new__(cls)
            cls._instance.redis = redis_client
        return cls._instance
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache"""
        value = self.redis.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value.decode('utf-8') if isinstance(value, bytes) else value
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in Redis cache with TTL in seconds"""
        try:
            serialized = json.dumps(value)
            return self.redis.set(key, serialized, ex=ttl)
        except (TypeError, ValueError):
            # Fall back to string representation for non-serializable objects
            return self.redis.set(key, str(value), ex=ttl)
    
    def delete(self, key: str) -> bool:
        """Delete key from Redis cache"""
        return self.redis.delete(key) > 0
    
    def exists(self, key: str) -> bool:
        """Check if key exists in Redis cache"""
        return self.redis.exists(key) > 0