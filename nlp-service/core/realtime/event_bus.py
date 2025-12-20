"""
Event Bus - Pub/Sub messaging for real-time updates

This module provides an asynchronous event bus for publishing and
subscribing to events across the application.

Features:
- Async event handling
- Topic-based subscriptions
- Wildcard subscriptions
- Event history
- Middleware support

Usage:
    from realtime import get_event_bus, Event, EventType

    bus = get_event_bus()

    # Subscribe to events
    async def handler(event: Event):
        print(f"Received: {event.data}")

    bus.subscribe("vitals:*", handler)

    # Publish events
    await bus.publish(Event(
        type=EventType.VITAL_LOGGED,
        topic="vitals:user123",
        data={"systolic": 120, "diastolic": 80}
    ))
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from collections import deque

logger = logging.getLogger(__name__)


# ============================================================================
# Event Types
# ============================================================================


class EventType(str, Enum):
    """Types of events in the system."""

    # Health Events
    VITAL_LOGGED = "vital_logged"
    VITAL_ALERT = "vital_alert"
    MEDICATION_REMINDER = "medication_reminder"
    MEDICATION_TAKEN = "medication_taken"
    APPOINTMENT_REMINDER = "appointment_reminder"
    HEALTH_ALERT = "health_alert"

    # Chat Events
    CHAT_MESSAGE = "chat_message"
    CHAT_RESPONSE = "chat_response"
    CHAT_ERROR = "chat_error"

    # System Events
    USER_CONNECTED = "user_connected"
    USER_DISCONNECTED = "user_disconnected"
    SYSTEM_STATUS = "system_status"

    # Custom Events
    CUSTOM = "custom"


@dataclass
class Event:
    """Represents an event in the system."""

    type: EventType
    topic: str
    data: Any
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(datetime.now().timestamp()))

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "type": self.type.value if isinstance(self.type, EventType) else self.type,
            "topic": self.topic,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "metadata": self.metadata,
            "event_id": self.event_id,
        }


# Type alias for event handlers
EventHandler = Callable[[Event], Any]


# ============================================================================
# Event Bus
# ============================================================================


class EventBus:
    """
    Asynchronous event bus for pub/sub messaging.

    Supports:
    - Exact topic matching: "vitals:user123"
    - Wildcard matching: "vitals:*" matches "vitals:user123"
    - Double wildcard: "**" matches all events
    """

    def __init__(self, history_size: int = 100):
        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._lock = asyncio.Lock()
        self._history: deque = deque(maxlen=history_size)
        self._middlewares: List[Callable[[Event], Optional[Event]]] = []
        self._running = False
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the event bus worker."""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._process_events())
        logger.info("Event bus started")

    async def stop(self):
        """Stop the event bus worker."""
        if not self._running:
            return

        self._running = False

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        logger.info("Event bus stopped")

    async def _process_events(self):
        """Process events from the queue."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._dispatch_event(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error processing event: {e}")

    def subscribe(self, topic: str, handler: EventHandler) -> Callable[[], None]:
        """
        Subscribe to events on a topic.

        Args:
            topic: Topic pattern to subscribe to (supports wildcards)
            handler: Async or sync function to handle events

        Returns:
            Unsubscribe function
        """
        if topic not in self._subscribers:
            self._subscribers[topic] = []

        self._subscribers[topic].append(handler)
        logger.debug(f"Subscribed to topic: {topic}")

        def unsubscribe():
            if topic in self._subscribers:
                try:
                    self._subscribers[topic].remove(handler)
                    if not self._subscribers[topic]:
                        del self._subscribers[topic]
                except ValueError:
                    pass

        return unsubscribe

    async def publish(self, event: Event):
        """
        Publish an event to all matching subscribers.

        Args:
            event: Event to publish
        """
        # Apply middlewares
        for middleware in self._middlewares:
            try:
                result = middleware(event)
                if result is None:
                    logger.debug(f"Event filtered by middleware: {event.event_id}")
                    return
                event = result
            except Exception as e:
                logger.warning(f"Middleware error: {e}")

        # Add to history
        self._history.append(event)

        # Queue for processing
        await self._queue.put(event)

    def publish_sync(self, event: Event):
        """
        Publish an event synchronously (adds to queue).

        Use this from sync code when you can't await.
        """
        asyncio.create_task(self.publish(event))

    async def _dispatch_event(self, event: Event):
        """Dispatch event to all matching subscribers."""
        handlers = self._get_matching_handlers(event.topic)

        if not handlers:
            logger.debug(f"No handlers for event: {event.topic}")
            return

        # Execute handlers concurrently
        tasks = []
        for handler in handlers:
            if asyncio.iscoroutinefunction(handler):
                tasks.append(asyncio.create_task(self._safe_call_async(handler, event)))
            else:
                tasks.append(asyncio.create_task(self._safe_call_sync(handler, event)))

        await asyncio.gather(*tasks, return_exceptions=True)

    def _get_matching_handlers(self, topic: str) -> List[EventHandler]:
        """Get all handlers matching a topic."""
        handlers = []

        for pattern, subs in self._subscribers.items():
            if self._topic_matches(pattern, topic):
                handlers.extend(subs)

        return handlers

    @staticmethod
    def _topic_matches(pattern: str, topic: str) -> bool:
        """Check if a topic matches a pattern."""
        if pattern == "**":
            return True

        if pattern == topic:
            return True

        # Convert pattern to regex
        # * matches any single segment
        # ** matches any number of segments
        regex_pattern = (
            pattern.replace(".", r"\.").replace("**", ".*").replace("*", r"[^:]*")
        )
        regex_pattern = f"^{regex_pattern}$"

        return bool(re.match(regex_pattern, topic))

    async def _safe_call_async(self, handler: EventHandler, event: Event):
        """Safely call an async handler."""
        try:
            await handler(event)
        except Exception as e:
            logger.exception(f"Handler error: {e}")

    async def _safe_call_sync(self, handler: EventHandler, event: Event):
        """Safely call a sync handler."""
        try:
            await asyncio.get_event_loop().run_in_executor(None, handler, event)
        except Exception as e:
            logger.exception(f"Handler error: {e}")

    def add_middleware(self, middleware: Callable[[Event], Optional[Event]]):
        """
        Add a middleware to process events before dispatch.

        Middleware can:
        - Modify the event
        - Return None to filter/drop the event
        - Return the event (possibly modified) to continue
        """
        self._middlewares.append(middleware)

    def get_history(self, topic: Optional[str] = None, limit: int = 50) -> List[Event]:
        """
        Get recent event history.

        Args:
            topic: Optional topic filter
            limit: Maximum number of events to return
        """
        events = list(self._history)

        if topic:
            events = [e for e in events if self._topic_matches(topic, e.topic)]

        return events[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        return {
            "subscribers": {
                topic: len(handlers) for topic, handlers in self._subscribers.items()
            },
            "total_subscriptions": sum(len(h) for h in self._subscribers.values()),
            "history_size": len(self._history),
            "queue_size": self._queue.qsize(),
            "running": self._running,
        }


# ============================================================================
# Global Instance
# ============================================================================

_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


# ============================================================================
# Utility Functions
# ============================================================================


async def publish_vital_event(user_id: str, vital_type: str, value: float, **kwargs):
    """Convenience function to publish vital sign events."""
    bus = get_event_bus()
    await bus.publish(
        Event(
            type=EventType.VITAL_LOGGED,
            topic=f"vitals:{user_id}",
            data={"vital_type": vital_type, "value": value, **kwargs},
            source="vital_service",
        )
    )


async def publish_medication_reminder(
    user_id: str, medication_name: str, scheduled_time: str
):
    """Convenience function to publish medication reminders."""
    bus = get_event_bus()
    await bus.publish(
        Event(
            type=EventType.MEDICATION_REMINDER,
            topic=f"medications:{user_id}",
            data={"medication_name": medication_name, "scheduled_time": scheduled_time},
            source="medication_service",
        )
    )


async def publish_health_alert(
    user_id: str, alert_type: str, message: str, severity: str = "warning"
):
    """Convenience function to publish health alerts."""
    bus = get_event_bus()
    await bus.publish(
        Event(
            type=EventType.HEALTH_ALERT,
            topic=f"alerts:{user_id}",
            data={"alert_type": alert_type, "message": message, "severity": severity},
            source="health_monitor",
        )
    )
