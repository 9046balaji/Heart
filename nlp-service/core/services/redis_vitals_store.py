import redis
import json
import os
from datetime import datetime
from typing import List, Dict
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database models for cold storage
Base = declarative_base()


class VitalReading(Base):
    """SQLAlchemy model for vital readings stored in cold storage."""

    __tablename__ = "vital_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(255), index=True, nullable=False)
    metric_type = Column(
        String(50), index=True, nullable=False
    )  # "hr", "bp_sys", "bp_dia", "spo2", etc.
    value = Column(Float, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)
    unit = Column(String(20))  # "bpm", "mmHg", "%", etc.


class RedisVitalsStore:
    """
    Redis-backed storage for patient vitals history with cold storage persistence.
    Uses Sorted Sets (ZSET) where score = timestamp.
    """

    def __init__(self, redis_url: str = None, database_url: str = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.client = redis.from_url(self.redis_url, decode_responses=True)
        self.window_minutes = 30  # Keep last 30 mins of data

        # Database setup for cold storage
        self.database_url = database_url or os.getenv(
            "DATABASE_URL", "sqlite:///./vitals_cold_storage.db"
        )
        self.engine = create_engine(self.database_url)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def add_reading(self, device_id: str, reading: Dict) -> None:
        """Add a new reading and trim old data."""
        key = f"vitals:{device_id}"
        timestamp = datetime.utcnow().timestamp()

        # Add to ZSET
        self.client.zadd(key, {json.dumps(reading): timestamp})

        # Trim data older than window
        cutoff = timestamp - (self.window_minutes * 60)
        self.client.zremrangebyscore(key, 0, cutoff)

        # Store in cold storage database
        self._store_in_cold_storage(device_id, reading, datetime.utcnow())

    def get_history(self, device_id: str) -> List[Dict]:
        """Get all readings in the current window."""
        key = f"vitals:{device_id}"
        # Get all items in set (already sorted by time)
        items = self.client.zrange(key, 0, -1)
        return [json.loads(item) for item in items]

    def _store_in_cold_storage(
        self, device_id: str, reading: Dict, timestamp: datetime
    ) -> None:
        """Store reading in cold storage database."""
        try:
            session = self.SessionLocal()

            # Extract metrics from reading
            metrics = []

            # Heart rate
            if "heart_rate" in reading:
                metrics.append(
                    VitalReading(
                        device_id=device_id,
                        metric_type="hr",
                        value=float(reading["heart_rate"]),
                        timestamp=timestamp,
                        unit="bpm",
                    )
                )

            # Blood pressure
            if "blood_pressure_systolic" in reading:
                metrics.append(
                    VitalReading(
                        device_id=device_id,
                        metric_type="bp_sys",
                        value=float(reading["blood_pressure_systolic"]),
                        timestamp=timestamp,
                        unit="mmHg",
                    )
                )

            if "blood_pressure_diastolic" in reading:
                metrics.append(
                    VitalReading(
                        device_id=device_id,
                        metric_type="bp_dia",
                        value=float(reading["blood_pressure_diastolic"]),
                        timestamp=timestamp,
                        unit="mmHg",
                    )
                )

            # Blood oxygen
            if "blood_oxygen" in reading:
                metrics.append(
                    VitalReading(
                        device_id=device_id,
                        metric_type="spo2",
                        value=float(reading["blood_oxygen"]),
                        timestamp=timestamp,
                        unit="%",
                    )
                )

            # Temperature
            if "temperature" in reading:
                metrics.append(
                    VitalReading(
                        device_id=device_id,
                        metric_type="temp",
                        value=float(reading["temperature"]),
                        timestamp=timestamp,
                        unit="F",
                    )
                )

            # Save metrics
            if metrics:
                session.add_all(metrics)
                session.commit()

        except Exception as e:
            # Log error but don't fail the main operation
            import logging

            logging.error(f"Failed to store vitals in cold storage: {e}")
        finally:
            if "session" in locals():
                session.close()
