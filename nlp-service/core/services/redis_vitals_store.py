import redis
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict

class RedisVitalsStore:
    """
    Redis-backed storage for patient vitals history.
    Uses Sorted Sets (ZSET) where score = timestamp.
    """
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.client = redis.from_url(self.redis_url, decode_responses=True)
        self.window_minutes = 30  # Keep last 30 mins of data
        
    def add_reading(self, device_id: str, reading: Dict) -> None:
        """Add a new reading and trim old data."""
        key = f"vitals:{device_id}"
        timestamp = datetime.utcnow().timestamp()
        
        # Add to ZSET
        self.client.zadd(key, {json.dumps(reading): timestamp})
        
        # Trim data older than window
        cutoff = timestamp - (self.window_minutes * 60)
        self.client.zremrangebyscore(key, 0, cutoff)
        
    def get_history(self, device_id: str) -> List[Dict]:
        """Get all readings in the current window."""
        key = f"vitals:{device_id}"
        # Get all items in set (already sorted by time)
        items = self.client.zrange(key, 0, -1)
        return [json.loads(item) for item in items]