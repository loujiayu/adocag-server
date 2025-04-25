import json
import time
import random
from typing import Optional, Any
import redis.asyncio

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
        if ttl > 0:
            jitter = random.uniform(-0.1, 0.1) * ttl  # ±10% jitter
            ttl = max(1, int(ttl + jitter))  # Ensure TTL is at least 1 second
        
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