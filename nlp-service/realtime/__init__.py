"""
Real-time Communication Module

Provides WebSocket support for bidirectional real-time communication
between frontend and backend.
"""

from .websocket_handler import (
    websocket_router,
    ConnectionManager,
    get_connection_manager,
)
from .event_bus import (
    EventBus,
    Event,
    EventType,
    get_event_bus,
)

__all__ = [
    # WebSocket
    'websocket_router',
    'ConnectionManager', 
    'get_connection_manager',
    # Event Bus
    'EventBus',
    'Event',
    'EventType',
    'get_event_bus',
]
