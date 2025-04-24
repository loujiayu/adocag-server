import os
import redis
import logging
from typing import Optional
from src.services.cache_implementations import CacheInterface, MemoryCache, RedisCache

class CacheManager:
    """
    Cache manager to handle cache initialization and provide a singleton instance
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CacheManager, cls).__new__(cls)
            cls._instance._initialize_cache()
        return cls._instance
    
    def _initialize_cache(self):
        """Initialize the appropriate cache implementation"""
        self.redis_client = None
        self.cache_type = "memory"  # Default to memory cache
        self.cache = None
        
        self.cache = MemoryCache()

        # try:
        #     if os.environ.get("REDIS_ENABLED", "false").lower() == "true":
        #         redis_host = os.environ.get("REDIS_HOST")
        #         redis_port = int(os.environ.get("REDIS_PORT", 6379))
        #         redis_password = os.environ.get("REDIS_PASSWORD")
        #         redis_ssl = os.environ.get("REDIS_SSL", "false").lower() == "true"
                
        #         if redis_host and redis_password:
        #             self.redis_client = redis.Redis(
        #                 host=redis_host,
        #                 port=redis_port,
        #                 password=redis_password,
        #                 ssl=redis_ssl
        #             )
        #             # Test connection
        #             if self.redis_client.ping():
        #                 logging.info("Redis connection successful, using Redis cache")
        #                 self.cache_type = "redis"
        #                 self.cache = RedisCache(self.redis_client)
        #             else:
        #                 logging.warning("Redis ping failed, falling back to memory cache")
        #                 self.redis_client = None
        #                 self.cache = MemoryCache()
        #         else:
        #             logging.warning("Redis config incomplete, falling back to memory cache")
        #             self.cache = MemoryCache()
        #     else:
        #         logging.info("Redis not enabled, using memory cache")
        #         self.cache = MemoryCache()
        # except Exception as e:
        #     logging.error(f"Error connecting to Redis: {str(e)}, falling back to memory cache")
        #     self.redis_client = None
        #     self.cache = MemoryCache()
    
    def get_cache(self) -> CacheInterface:
        """Get the configured cache implementation"""
        return self.cache
    
    def get_cache_type(self) -> str:
        """Get the type of cache being used"""
        return self.cache_type
    
    def get_redis_client(self) -> Optional[redis.Redis]:
        """Get the Redis client if available"""
        return self.redis_client