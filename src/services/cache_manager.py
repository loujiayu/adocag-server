import os
import redis.asyncio
import logging
from typing import Optional
from src.services.cache_implementations import CacheInterface, MemoryCache, RedisCache, TieredCache

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
        self.cache = None
        
        try:
            redis_host = os.environ.get("REDIS_HOST", "adocagf.redis.cache.windows.net")
            redis_port = int(os.environ.get("REDIS_PORT", 6380))
            redis_password = os.environ.get("REDIS_PASSWORD")
            
            # Check if Redis configuration is available
            if redis_host and redis_password:
                # Try to initialize Redis client
                try:
                    # Use asyncio Redis client
                    self.redis_client = redis.asyncio.Redis(
                        host=redis_host,
                        port=redis_port,
                        password=redis_password,
                        ssl=True
                    )
                    
                    # Initialize the tiered cache with Redis
                    self.cache = TieredCache(self.redis_client)
                    self.cache_type = "tiered"
                    logging.info("Tiered cache initialized with Redis backend")
                except Exception as e:
                    logging.error(f"Error initializing Redis: {str(e)}, falling back to memory cache")
                    self.redis_client = None
                    self.cache = MemoryCache()
                    self.cache_type = "memory"
            else:
                logging.warning("Redis config incomplete, using memory cache only")
                self.cache = MemoryCache()
                self.cache_type = "memory"
        except Exception as e:
            logging.error(f"Error in cache initialization: {str(e)}, falling back to memory cache")
            self.redis_client = None
            self.cache = MemoryCache()
            self.cache_type = "memory"
    
    def get_cache(self) -> CacheInterface:
        """Get the configured cache implementation"""
        return self.cache
    
    def get_cache_type(self) -> str:
        """Get the type of cache being used"""
        return self.cache_type
    
    def get_redis_client(self) -> Optional[redis.asyncio.Redis]:
        """Get the Redis client if available"""
        return self.redis_client