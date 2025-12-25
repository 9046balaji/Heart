import asyncio
import redis.asyncio as aioredis
from typing import Optional
from contextlib import asynccontextmanager
import uuid
import time
import logging

logger = logging.getLogger(__name__)

class RedisLock:
    """
    Distributed mutex lock using Redis.
    
    Prevents race conditions in appointment booking.
    """
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis: Optional[aioredis.Redis] = None
    
    async def get_redis(self) -> aioredis.Redis:
        """Get Redis client."""
        if self.redis is None:
            self.redis = await aioredis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)
        return self.redis
    
    @asynccontextmanager
    async def acquire(
        self,
        lock_name: str,
        timeout: int = 10,  # Max time to hold lock
        blocking_timeout: int = 5  # Max time to wait to acquire
    ):
        """
        Acquire distributed lock.
        
        Usage:
            async with lock.acquire("booking:slot_123"):
                # Only one process can execute this block at a time
                await book_appointment()
        
        Args:
            lock_name: Unique lock identifier
            timeout: How long lock is valid (seconds)
            blocking_timeout: How long to wait if lock is held
        """
        redis = await self.get_redis()
        
        # Generate unique token for this lock acquisition
        # (Prevents releasing someone else's lock)
        lock_token = str(uuid.uuid4())
        lock_key = f"lock:{lock_name}"
        
        # Try to acquire lock
        acquired = False
        start_time = time.time()
        
        while not acquired and (time.time() - start_time) < blocking_timeout:
            # SET with NX (only if not exists) and EX (expiration)
            acquired = await redis.set(
                lock_key,
                lock_token,
                ex=timeout,
                nx=True  # Only set if key doesn't exist
            )
            
            if not acquired:
                # Lock is held by someone else, wait a bit
                await asyncio.sleep(0.1)
        
        if not acquired:
            raise TimeoutError(
                f"Could not acquire lock '{lock_name}' within {blocking_timeout}s"
            )
        
        try:
            # Lock acquired, yield to caller
            yield
        finally:
            # Release lock (only if we still own it)
            # Use Lua script for atomic check-and-delete
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            
            await redis.eval(lua_script, 1, lock_key, lock_token)
