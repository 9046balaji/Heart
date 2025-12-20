"""
Audit log shipping to external SIEM.

Provides integration with popular SIEM solutions like Datadog, Splunk, and AWS CloudWatch.
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class LogShipper(ABC):
    """Abstract base class for log shippers."""

    @abstractmethod
    async def ship(self, log_entry: Dict[str, Any]) -> bool:
        """
        Ship log entry to SIEM.

        Args:
            log_entry: Log entry to ship

        Returns:
            True if successful, False otherwise
        """


class DatadogShipper(LogShipper):
    """Datadog integration for log shipping."""

    def __init__(self):
        """Initialize Datadog shipper."""
        self.api_key = os.getenv("DATADOG_API_KEY")
        self.endpoint = "https://http-intake.logs.datadoghq.com/api/v2/logs"

        if not self.api_key:
            raise ValueError("DATADOG_API_KEY environment variable not set")

        try:
            import httpx

            self.http_client = httpx.AsyncClient()
            logger.info("Datadog shipper initialized")
        except ImportError:
            raise ImportError(
                "httpx required for Datadog integration. Install with: pip install httpx"
            )

    async def ship(self, log_entry: Dict[str, Any]) -> bool:
        """
        Ship log entry to Datadog.

        Args:
            log_entry: Log entry to ship

        Returns:
            True if successful, False otherwise
        """
        try:
            # Add Datadog-specific fields
            datadog_entry = {
                "ddsource": "heartguard",
                "service": "nlp-service",
                "timestamp": log_entry.get("timestamp"),
                **log_entry,
            }

            response = await self.http_client.post(
                self.endpoint,
                json=datadog_entry,
                headers={
                    "DD-API-KEY": self.api_key,
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 202:
                logger.debug("Log entry shipped to Datadog successfully")
                return True
            else:
                logger.error(
                    f"Failed to ship log to Datadog: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Error shipping log to Datadog: {e}")
            return False


class SplunkShipper(LogShipper):
    """Splunk HEC (HTTP Event Collector) integration."""

    def __init__(self):
        """Initialize Splunk shipper."""
        self.hec_url = os.getenv("SPLUNK_HEC_URL")
        self.hec_token = os.getenv("SPLUNK_HEC_TOKEN")

        if not self.hec_url:
            raise ValueError("SPLUNK_HEC_URL environment variable not set")

        if not self.hec_token:
            raise ValueError("SPLUNK_HEC_TOKEN environment variable not set")

        try:
            import httpx

            self.http_client = httpx.AsyncClient()
            logger.info("Splunk shipper initialized")
        except ImportError:
            raise ImportError(
                "httpx required for Splunk integration. Install with: pip install httpx"
            )

    async def ship(self, log_entry: Dict[str, Any]) -> bool:
        """
        Ship log entry to Splunk.

        Args:
            log_entry: Log entry to ship

        Returns:
            True if successful, False otherwise
        """
        try:
            # Format for Splunk HEC
            splunk_entry = {
                "time": datetime.fromisoformat(
                    log_entry.get("timestamp", datetime.utcnow().isoformat())
                ).timestamp(),
                "host": os.getenv("HOSTNAME", "heartguard-nlp-service"),
                "source": "heartguard-audit",
                "sourcetype": "nlp-service:audit",
                "event": log_entry,
            }

            response = await self.http_client.post(
                self.hec_url,
                json=splunk_entry,
                headers={
                    "Authorization": f"Splunk {self.hec_token}",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code in [200, 201]:
                logger.debug("Log entry shipped to Splunk successfully")
                return True
            else:
                logger.error(
                    f"Failed to ship log to Splunk: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Error shipping log to Splunk: {e}")
            return False


class CloudWatchShipper(LogShipper):
    """AWS CloudWatch Logs integration."""

    def __init__(self):
        """Initialize CloudWatch shipper."""
        try:
            import boto3

            self.client = boto3.client("logs")
            self.log_group = os.getenv("AWS_LOG_GROUP", "/heartguard/audit")
            self.log_stream = os.getenv("AWS_LOG_STREAM", "nlp-service")
            logger.info("CloudWatch shipper initialized")
        except ImportError:
            raise ImportError(
                "boto3 required for AWS CloudWatch. Install with: pip install boto3"
            )
        except Exception as e:
            logger.error(f"Failed to initialize CloudWatch shipper: {e}")
            raise

    async def ship(self, log_entry: Dict[str, Any]) -> bool:
        """
        Ship log entry to CloudWatch.

        Args:
            log_entry: Log entry to ship

        Returns:
            True if successful, False otherwise
        """
        try:
            # Format for CloudWatch
            cw_entry = {
                "timestamp": int(
                    datetime.fromisoformat(
                        log_entry.get("timestamp", datetime.utcnow().isoformat())
                    ).timestamp()
                    * 1000
                ),
                "message": json.dumps(log_entry),
            }

            response = self.client.put_log_events(
                logGroupName=self.log_group,
                logStreamName=self.log_stream,
                logEvents=[cw_entry],
            )

            logger.debug("Log entry shipped to CloudWatch successfully")
            return True

        except Exception as e:
            logger.error(f"Error shipping log to CloudWatch: {e}")
            return False


class ConsoleShipper(LogShipper):
    """Console output for development/testing."""

    async def ship(self, log_entry: Dict[str, Any]) -> bool:
        """
        Output log entry to console.

        Args:
            log_entry: Log entry to output

        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"[AUDIT] {json.dumps(log_entry)}")
            return True
        except Exception as e:
            logger.error(f"Error outputting log to console: {e}")
            return False


def get_log_shipper() -> Optional[LogShipper]:
    """
    Get configured log shipper based on environment variables.

    Returns:
        Configured log shipper instance or None if not configured
    """
    # Check for Datadog configuration
    if os.getenv("DATADOG_API_KEY"):
        try:
            return DatadogShipper()
        except Exception as e:
            logger.warning(f"Datadog configuration failed: {e}")

    # Check for Splunk configuration
    if os.getenv("SPLUNK_HEC_URL") and os.getenv("SPLUNK_HEC_TOKEN"):
        try:
            return SplunkShipper()
        except Exception as e:
            logger.warning(f"Splunk configuration failed: {e}")

    # Check for CloudWatch configuration
    if os.getenv("AWS_LOG_GROUP") or os.getenv("AWS_ACCESS_KEY_ID"):
        try:
            return CloudWatchShipper()
        except Exception as e:
            logger.warning(f"CloudWatch configuration failed: {e}")

    # Fallback to console for development
    logger.info("Using console shipper for development")
    return ConsoleShipper()
