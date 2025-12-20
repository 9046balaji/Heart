"""
Cold storage pipeline for vitals data.

Moves hourly vitals from Redis to PostgreSQL for long-term storage and analysis.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# Database models
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

    # Indexes for common queries
    __table_args__ = (
        Index("idx_vital_device_metric", "device_id", "metric_type"),
        Index("idx_vital_timestamp", "timestamp"),
    )

    def __repr__(self):
        return f"<VitalReading(device_id='{self.device_id}', metric_type='{self.metric_type}', value={self.value}, timestamp='{self.timestamp}')>"


class VitalHourlySummary(Base):
    """SQLAlchemy model for hourly vital summaries."""

    __tablename__ = "vital_hourly_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(255), index=True, nullable=False)
    metric_type = Column(String(50), index=True, nullable=False)
    hour_start = Column(DateTime, index=True, nullable=False)
    avg_value = Column(Float)
    min_value = Column(Float)
    max_value = Column(Float)
    std_value = Column(Float)  # Standard deviation
    sample_count = Column(Integer)

    # Indexes for common queries
    __table_args__ = (
        Index("idx_summary_device_metric", "device_id", "metric_type"),
        Index("idx_summary_hour", "hour_start"),
    )

    def __repr__(self):
        return f"<VitalHourlySummary(device_id='{self.device_id}', metric_type='{self.metric_type}', hour_start='{self.hour_start}', avg_value={self.avg_value})>"


class VitalsColdStorage:
    """Cold storage pipeline for vitals data."""

    def __init__(
        self,
        redis_store: Any,  # RedisVitalsStore instance
        database_url: str = None,
        batch_size: int = 1000,
    ):
        """
        Initialize cold storage pipeline.

        Args:
            redis_store: RedisVitalsStore instance
            database_url: PostgreSQL database URL
            batch_size: Number of records to process in each batch
        """
        self.redis_store = redis_store
        self.batch_size = batch_size

        # Database setup
        self.database_url = (
            database_url or "postgresql://user:password@localhost/heartguard"
        )
        self.engine = create_engine(
            self.database_url, pool_size=10, max_overflow=20, pool_pre_ping=True
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

        logger.info("Vitals cold storage initialized")

    async def archive_hourly(self, device_id: str = None) -> Dict[str, Any]:
        """
        Archive hourly vitals data from Redis to PostgreSQL.

        Args:
            device_id: Specific device to archive (None for all devices)

        Returns:
            Archive statistics
        """
        try:
            # Get list of devices if not specified
            if device_id:
                devices = [device_id]
            else:
                devices = await self._get_active_devices()

            stats = {
                "devices_processed": 0,
                "readings_archived": 0,
                "summaries_created": 0,
                "errors": [],
            }

            for dev_id in devices:
                try:
                    device_stats = await self._archive_device_hourly(dev_id)
                    stats["devices_processed"] += 1
                    stats["readings_archived"] += device_stats["readings_count"]
                    stats["summaries_created"] += device_stats["summaries_count"]
                except Exception as e:
                    error_msg = f"Failed to archive device {dev_id}: {str(e)}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)

            logger.info(f"Hourly archive completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Hourly archive failed: {e}")
            raise

    async def _get_active_devices(self) -> List[str]:
        """
        Get list of active devices with recent vitals data.

        Returns:
            List of device IDs
        """
        # This would typically query a devices table or scan Redis keys
        # For now, we'll return a placeholder
        return ["device_001", "device_002"]

    async def _archive_device_hourly(self, device_id: str) -> Dict[str, Any]:
        """
        Archive hourly data for a specific device.

        Args:
            device_id: Device identifier

        Returns:
            Archive statistics for the device
        """
        stats = {"device_id": device_id, "readings_count": 0, "summaries_count": 0}

        try:
            # Get hourly data from Redis
            readings = self.redis_store.get_history(device_id)

            if not readings:
                logger.debug(f"No readings found for device {device_id}")
                return stats

            # Convert readings to database models
            db_readings = []
            hourly_data = {}

            for reading in readings:
                try:
                    # Parse reading data
                    timestamp = datetime.fromisoformat(reading.get("timestamp"))
                    heart_rate = reading.get("heart_rate")
                    bp_sys = reading.get("blood_pressure_systolic")
                    bp_dia = reading.get("blood_pressure_diastolic")
                    spo2 = reading.get("blood_oxygen")
                    temp = reading.get("temperature")

                    # Create database entries for each metric
                    if heart_rate is not None:
                        db_readings.append(
                            VitalReading(
                                device_id=device_id,
                                metric_type="hr",
                                value=float(heart_rate),
                                timestamp=timestamp,
                                unit="bpm",
                            )
                        )

                    if bp_sys is not None:
                        db_readings.append(
                            VitalReading(
                                device_id=device_id,
                                metric_type="bp_sys",
                                value=float(bp_sys),
                                timestamp=timestamp,
                                unit="mmHg",
                            )
                        )

                    if bp_dia is not None:
                        db_readings.append(
                            VitalReading(
                                device_id=device_id,
                                metric_type="bp_dia",
                                value=float(bp_dia),
                                timestamp=timestamp,
                                unit="mmHg",
                            )
                        )

                    if spo2 is not None:
                        db_readings.append(
                            VitalReading(
                                device_id=device_id,
                                metric_type="spo2",
                                value=float(spo2),
                                timestamp=timestamp,
                                unit="%",
                            )
                        )

                    if temp is not None:
                        db_readings.append(
                            VitalReading(
                                device_id=device_id,
                                metric_type="temp",
                                value=float(temp),
                                timestamp=timestamp,
                                unit="F",
                            )
                        )

                    # Group by hour for summary calculation
                    hour_key = timestamp.replace(minute=0, second=0, microsecond=0)
                    hour_str = hour_key.isoformat()

                    if hour_str not in hourly_data:
                        hourly_data[hour_str] = {
                            "timestamp": hour_key,
                            "hr_values": [],
                            "bp_sys_values": [],
                            "bp_dia_values": [],
                            "spo2_values": [],
                            "temp_values": [],
                        }

                    if heart_rate is not None:
                        hourly_data[hour_str]["hr_values"].append(float(heart_rate))
                    if bp_sys is not None:
                        hourly_data[hour_str]["bp_sys_values"].append(float(bp_sys))
                    if bp_dia is not None:
                        hourly_data[hour_str]["bp_dia_values"].append(float(bp_dia))
                    if spo2 is not None:
                        hourly_data[hour_str]["spo2_values"].append(float(spo2))
                    if temp is not None:
                        hourly_data[hour_str]["temp_values"].append(float(temp))

                except Exception as e:
                    logger.warning(
                        f"Failed to process reading for device {device_id}: {e}"
                    )
                    continue

            # Save readings to database in batches
            if db_readings:
                session = self.SessionLocal()
                try:
                    for i in range(0, len(db_readings), self.batch_size):
                        batch = db_readings[i : i + self.batch_size]
                        session.bulk_save_objects(batch)
                        session.commit()

                    stats["readings_count"] = len(db_readings)
                    logger.debug(
                        f"Archived {len(db_readings)} readings for device {device_id}"
                    )
                except Exception as e:
                    session.rollback()
                    raise e
                finally:
                    session.close()

            # Calculate and save hourly summaries
            db_summaries = []
            for hour_str, data in hourly_data.items():
                timestamp = data["timestamp"]

                # Create summaries for each metric type
                if data["hr_values"]:
                    db_summaries.append(
                        VitalHourlySummary(
                            device_id=device_id,
                            metric_type="hr",
                            hour_start=timestamp,
                            avg_value=sum(data["hr_values"]) / len(data["hr_values"]),
                            min_value=min(data["hr_values"]),
                            max_value=max(data["hr_values"]),
                            std_value=self._std_dev(data["hr_values"]),
                            sample_count=len(data["hr_values"]),
                        )
                    )

                if data["bp_sys_values"]:
                    db_summaries.append(
                        VitalHourlySummary(
                            device_id=device_id,
                            metric_type="bp_sys",
                            hour_start=timestamp,
                            avg_value=sum(data["bp_sys_values"])
                            / len(data["bp_sys_values"]),
                            min_value=min(data["bp_sys_values"]),
                            max_value=max(data["bp_sys_values"]),
                            std_value=self._std_dev(data["bp_sys_values"]),
                            sample_count=len(data["bp_sys_values"]),
                        )
                    )

                if data["bp_dia_values"]:
                    db_summaries.append(
                        VitalHourlySummary(
                            device_id=device_id,
                            metric_type="bp_dia",
                            hour_start=timestamp,
                            avg_value=sum(data["bp_dia_values"])
                            / len(data["bp_dia_values"]),
                            min_value=min(data["bp_dia_values"]),
                            max_value=max(data["bp_dia_values"]),
                            std_value=self._std_dev(data["bp_dia_values"]),
                            sample_count=len(data["bp_dia_values"]),
                        )
                    )

                if data["spo2_values"]:
                    db_summaries.append(
                        VitalHourlySummary(
                            device_id=device_id,
                            metric_type="spo2",
                            hour_start=timestamp,
                            avg_value=sum(data["spo2_values"])
                            / len(data["spo2_values"]),
                            min_value=min(data["spo2_values"]),
                            max_value=max(data["spo2_values"]),
                            std_value=self._std_dev(data["spo2_values"]),
                            sample_count=len(data["spo2_values"]),
                        )
                    )

                if data["temp_values"]:
                    db_summaries.append(
                        VitalHourlySummary(
                            device_id=device_id,
                            metric_type="temp",
                            hour_start=timestamp,
                            avg_value=sum(data["temp_values"])
                            / len(data["temp_values"]),
                            min_value=min(data["temp_values"]),
                            max_value=max(data["temp_values"]),
                            std_value=self._std_dev(data["temp_values"]),
                            sample_count=len(data["temp_values"]),
                        )
                    )

            # Save summaries to database in batches
            if db_summaries:
                session = self.SessionLocal()
                try:
                    for i in range(0, len(db_summaries), self.batch_size):
                        batch = db_summaries[i : i + self.batch_size]
                        session.bulk_save_objects(batch)
                        session.commit()

                    stats["summaries_count"] = len(db_summaries)
                    logger.debug(
                        f"Created {len(db_summaries)} summaries for device {device_id}"
                    )
                except Exception as e:
                    session.rollback()
                    raise e
                finally:
                    session.close()

            return stats

        except Exception as e:
            logger.error(f"Failed to archive device {device_id}: {e}")
            raise

    def _std_dev(self, values: List[float]) -> float:
        """
        Calculate standard deviation of a list of values.

        Args:
            values: List of numeric values

        Returns:
            Standard deviation
        """
        if len(values) < 2:
            return 0.0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance**0.5

    async def get_hourly_summary(
        self, device_id: str, metric_type: str, start_time: datetime, end_time: datetime
    ) -> List[VitalHourlySummary]:
        """
        Get hourly summaries for a device and metric type.

        Args:
            device_id: Device identifier
            metric_type: Metric type (e.g., "hr", "bp_sys")
            start_time: Start time
            end_time: End time

        Returns:
            List of hourly summaries
        """
        session = self.SessionLocal()
        try:
            summaries = (
                session.query(VitalHourlySummary)
                .filter(
                    VitalHourlySummary.device_id == device_id,
                    VitalHourlySummary.metric_type == metric_type,
                    VitalHourlySummary.hour_start >= start_time,
                    VitalHourlySummary.hour_start <= end_time,
                )
                .order_by(VitalHourlySummary.hour_start)
                .all()
            )

            return summaries
        finally:
            session.close()

    async def get_raw_readings(
        self,
        device_id: str,
        metric_type: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000,
    ) -> List[VitalReading]:
        """
        Get raw readings for a device and metric type.

        Args:
            device_id: Device identifier
            metric_type: Metric type (e.g., "hr", "bp_sys")
            start_time: Start time
            end_time: End time
            limit: Maximum number of readings to return

        Returns:
            List of raw readings
        """
        session = self.SessionLocal()
        try:
            readings = (
                session.query(VitalReading)
                .filter(
                    VitalReading.device_id == device_id,
                    VitalReading.metric_type == metric_type,
                    VitalReading.timestamp >= start_time,
                    VitalReading.timestamp <= end_time,
                )
                .order_by(VitalReading.timestamp)
                .limit(limit)
                .all()
            )

            return readings
        finally:
            session.close()


# Background archiving task
async def run_hourly_archive(
    cold_storage: VitalsColdStorage, interval_minutes: int = 60
):
    """
    Run hourly archive task in background.

    Args:
        cold_storage: VitalsColdStorage instance
        interval_minutes: Interval between archives
    """
    while True:
        try:
            logger.info("Starting hourly vitals archive")
            stats = await cold_storage.archive_hourly()
            logger.info(f"Hourly archive completed: {stats}")
        except Exception as e:
            logger.error(f"Hourly archive failed: {e}")

        # Wait for next interval
        await asyncio.sleep(interval_minutes * 60)
