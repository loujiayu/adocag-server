import json
import time
import random
from typing import Optional, Any
import redis.asyncio
from collections import OrderedDict

# Abstract cache interface
class CacheInterface:
    """Abstract interface for cache implementations"""
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache by key"""
        raise NotImplementedError("Subclasses must implement get()")
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with optional TTL in seconds"""
        raise NotImplementedError("Subclasses must implement set()")
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        raise NotImplementedError("Subclasses must implement delete()")
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        raise NotImplementedError("Subclasses must implement exists()")

# Memory cache implementation
class MemoryCache():
    """In-memory cache implementation with item count limit"""
    
    _instance = None
    DEFAULT_MAX_ITEMS = 30000  # Default maximum number of items to store
    
    def __new__(cls, max_items=None):
        if cls._instance is None:
            cls._instance = super(MemoryCache, cls).__new__(cls)
            cls._instance._cache = OrderedDict()  # {key: (value, expiry_time)}
            cls._instance.max_items = max_items or cls.DEFAULT_MAX_ITEMS
        return cls._instance
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache, return None if expired or not found"""
        if key in self._cache:
            value, expiry = self._cache[key]
            if expiry == 0 or expiry > time.time():  # 0 means no expiry
                # Move to end to mark as recently used (LRU behavior)
                self._cache.move_to_end(key)
                return value
            # Remove expired item
            del self._cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL in seconds, evicting oldest items if needed"""
        # If key already exists, just update it
        if key in self._cache:
            expiry = 0 if ttl <= 0 else time.time() + ttl
            self._cache[key] = (value, expiry)
            # Move to end to mark as recently used
            self._cache.move_to_end(key)
            return True
            
        # If we've reached max items, remove the oldest item (first in OrderedDict)
        if len(self._cache) >= self.max_items:
            # Remove least recently used item (first item in OrderedDict)
            try:
                self._cache.popitem(last=False)
            except KeyError:
                pass  # Dict was empty somehow
            
        # Add new item
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
                # Move to end to mark as recently used
                self._cache.move_to_end(key)
                return True
            # Remove expired item
            del self._cache[key]
        return False
        
    def clear(self) -> None:
        """Clear all items from cache"""
        self._cache.clear()
        
    def get_size(self) -> int:
        """Get the current number of items in the cache"""
        return len(self._cache)

# Redis cache implementation
class RedisCache(CacheInterface):
    """Redis-based cache implementation using async methods"""
    
    _instance = None
    
    def __new__(cls, redis_client=None):
        if cls._instance is None:
            cls._instance = super(RedisCache, cls).__new__(cls)
            cls._instance.redis: redis.asyncio.Redis = redis_client
        return cls._instance
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache asynchronously"""
        value = await self.redis.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value.decode('utf-8') if isinstance(value, bytes) else value
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """
        Set value in Redis cache with TTL in seconds plus random jitter (asynchronous)
        
        Args:
            key: Cache key
            value: Value to store (will be JSON serialized)
            ttl: Time-to-live in seconds
            
        Returns:
            True if set was successful, False otherwise
        """
        # Add random jitter (±10%) to TTL to prevent cache stampede

        try:
            serialized = json.dumps(value)
            return await self.redis.set(key, serialized, ex=ttl)
        except (TypeError, ValueError):
            # Fall back to string representation for non-serializable objects
            return await self.redis.set(key, str(value), ex=ttl)
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis cache asynchronously"""
        result = await self.redis.delete(key)
        return result > 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis cache asynchronously"""
        result = await self.redis.exists(key)
        return result > 0

# Tiered cache implementation (local memory + Redis)
class TieredCache(CacheInterface):
    """Two-tier cache implementation that checks memory first, then Redis"""
    
    _instance = None
    
    def __new__(cls, redis_client=None):
        if cls._instance is None:
            cls._instance = super(TieredCache, cls).__new__(cls)
            cls._instance.memory_cache = MemoryCache()
            cls._instance.redis_cache = RedisCache(redis_client) if redis_client else None
        return cls._instance
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache, checking memory first then Redis"""
        # Try local memory cache first (fast)
        local_result = self.memory_cache.get(key)
        if local_result is not None:
            return local_result
            
        # If not in local cache and Redis is available, try Redis
        if self.redis_cache:
            redis_result = await self.redis_cache.get(key)
            if redis_result is not None:
                # Store in local cache for future fast access
                self.memory_cache.set(key, redis_result)
                return redis_result
                
        # Not found in any cache
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in both memory and Redis caches"""
        # Always set in local memory cache
        if ttl > 0:
            jitter = random.uniform(-0.1, 0.1) * ttl  # ±10% jitter
            ttl = max(1, int(ttl + jitter))  # Ensure TTL is at least 1 second
        
        local_success = self.memory_cache.set(key, value, ttl)
        
        # If Redis is available, also set there for persistence
        redis_success = True
        if self.redis_cache:
            redis_success = await self.redis_cache.set(key, value, ttl)
            
        return local_success and redis_success
    
    async def delete(self, key: str) -> bool:
        """Delete key from both memory and Redis caches"""
        # Always delete from local memory cache
        local_success = self.memory_cache.delete(key)
        
        # If Redis is available, also delete there
        redis_success = True
        if self.redis_cache:
            redis_success = await self.redis_cache.delete(key)
            
        return local_success or redis_success  # Return true if deletion succeeded in either cache
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in either memory or Redis cache"""
        # Check local memory cache first
        if self.memory_cache.exists(key):
            return True
            
        # If not in local cache and Redis is available, check Redis
        if self.redis_cache:
            return await self.redis_cache.exists(key)
            
        return False