"""
Redis client for distributed caching and throttling.
"""
import redis.asyncio as redis
from typing import Optional
from core.config import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()

class RedisClient:
    _instance: Optional[redis.Redis] = None
    
    @classmethod
    async def get_client(cls) -> redis.Redis:
        """Get or create Redis client singleton."""
        if cls._instance is None:
            try:
                cls._instance = await redis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True
                )
                logger.info("Connected to Redis successfully")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
        return cls._instance
    
    @classmethod
    async def close(cls):
        """Close Redis connection."""
        if cls._instance:
            await cls._instance.close()
            cls._instance = None
            logger.info("Redis connection closed")