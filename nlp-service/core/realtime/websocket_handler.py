"""
WebSocket Handler - Real-time bidirectional communication

This module provides WebSocket support for:
- Streaming chat responses
- Real-time status updates
- Live health data monitoring
- Session management

Usage:
    from realtime import websocket_router
    app.include_router(websocket_router)
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    Query,
    HTTPException,
    Depends,
)
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from jose import jwt, JWTError
import redis.asyncio as redis
import os

# JWT configuration
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "dev_secret_key")
JWT_ALGORITHM = "HS256"

security = HTTPBearer()

logger = logging.getLogger(__name__)


class WebSocketException(Exception):
    """Custom exception for WebSocket authentication errors."""

    def __init__(self, code: int, reason: str):
        self.code = code
        self.reason = reason
        super().__init__(reason)


async def validate_websocket_token(token: Optional[str] = Query(None)) -> str:
    """
    Validate JWT token and extract user_id.
    """
    if not token:
        # For backward compatibility/dev, allow anonymous if configured
        if os.getenv("ALLOW_ANONYMOUS_WS", "false").lower() == "true":
            return "anonymous"
        raise WebSocketException(code=1008, reason="Missing authentication token")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise WebSocketException(code=1008, reason="Invalid token: missing user_id")
        return user_id
    except JWTError as e:
        logger.warning(f"WebSocket JWT validation failed: {e}")
        raise WebSocketException(code=1008, reason="Invalid or expired token")

# ============================================================================
# Message Types
# ============================================================================


class MessageType(str, Enum):
    """Types of WebSocket messages."""

    # Client -> Server
    CHAT_MESSAGE = "chat_message"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    PING = "ping"

    # Server -> Client
    CHAT_RESPONSE = "chat_response"
    CHAT_TOKEN = "chat_token"  # Streaming tokens
    CHAT_COMPLETE = "chat_complete"
    STATUS_UPDATE = "status_update"
    ERROR = "error"
    PONG = "pong"
    CONNECTED = "connected"


class ChatMessage(BaseModel):
    """Incoming chat message from client."""

    message: str
    session_id: Optional[str] = None
    model: str = "gemini"
    include_memory: bool = True
    stream: bool = True


class WebSocketMessage(BaseModel):
    """Generic WebSocket message format."""

    type: MessageType
    data: Any
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    message_id: Optional[str] = None


# ============================================================================
# Connection Manager
# ============================================================================


@dataclass
class ClientConnection:
    """Represents a connected WebSocket client."""

    websocket: WebSocket
    user_id: str
    session_id: str
    connected_at: datetime = field(default_factory=datetime.now)
    subscriptions: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def connection_duration(self) -> float:
        """Duration of connection in seconds."""
        return (datetime.now() - self.connected_at).total_seconds()


class ConnectionManager:
    """
    Manages WebSocket connections for real-time communication.

    Features:
    - Connection tracking by user and session
    - Broadcast messaging
    - Subscription-based messaging
    - Connection health monitoring
    """

    def __init__(self, redis_url: Optional[str] = None):
        self._connections: Dict[str, ClientConnection] = {}  # session_id -> connection
        self._user_sessions: Dict[str, Set[str]] = {}  # user_id -> set of session_ids
        self._lock = asyncio.Lock()
        self._message_handlers: Dict[MessageType, List[Callable]] = {}

        # Redis Pub/Sub (cross-instance)
        self.redis_url = redis_url or os.getenv("REDIS_URL")
        self._redis: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._redis_enabled = False

        # Start Redis connection in background
        if self.redis_url:
            asyncio.create_task(self._init_redis())

    async def _init_redis(self):
        """Initialize Redis Pub/Sub connection."""
        try:
            self._redis = redis.from_url(
                self.redis_url, encoding="utf-8", decode_responses=True
            )
            await self._redis.ping()

            self._pubsub = self._redis.pubsub()
            await self._pubsub.subscribe("websocket_broadcast")

            self._redis_enabled = True
            logger.info("Redis Pub/Sub enabled for WebSocket scaling")

            # Start background listener
            asyncio.create_task(self._redis_listener())

        except Exception as e:
            logger.warning(f"Redis Pub/Sub unavailable: {e}. Using local-only mode.")
            self._redis_enabled = False

    async def _redis_listener(self):
        """Listen for messages from other instances."""
        try:
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])

                    # Deliver to local connections
                    session_id = data.get("session_id")
                    user_id = data.get("user_id")
                    
                    # Check if broadcast
                    if data.get("broadcast"):
                        msg = WebSocketMessage(**data["message"])
                        exclude = set(data.get("exclude", []))
                        # Local broadcast
                        for sid, conn in self._connections.items():
                            if sid not in exclude:
                                await self._send_message(conn, msg)
                        continue

                    msg = WebSocketMessage(**data["message"])

                    if session_id and session_id in self._connections:
                        await self._send_message(self._connections[session_id], msg)
                    elif user_id:
                        # Send to all local sessions for this user
                        if user_id in self._user_sessions:
                            for sid in self._user_sessions[user_id]:
                                await self._send_message(self._connections[sid], msg)

        except Exception as e:
            logger.error(f"Redis listener error: {e}")

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ClientConnection:
        """Accept a new WebSocket connection."""
        await websocket.accept()

        async with self._lock:
            connection = ClientConnection(
                websocket=websocket,
                user_id=user_id,
                session_id=session_id,
                metadata=metadata or {},
            )

            self._connections[session_id] = connection

            if user_id not in self._user_sessions:
                self._user_sessions[user_id] = set()
            self._user_sessions[user_id].add(session_id)

            logger.info(f"WebSocket connected: user={user_id}, session={session_id}")

            # Send connected confirmation
            await self._send_message(
                connection,
                WebSocketMessage(
                    type=MessageType.CONNECTED,
                    data={
                        "session_id": session_id,
                        "user_id": user_id,
                        "message": "Connected to Cardio AI real-time service",
                    },
                ),
            )

            return connection

    async def disconnect(self, session_id: str):
        """Handle WebSocket disconnection."""
        async with self._lock:
            if session_id in self._connections:
                connection = self._connections.pop(session_id)
                user_id = connection.user_id

                if user_id in self._user_sessions:
                    self._user_sessions[user_id].discard(session_id)
                    if not self._user_sessions[user_id]:
                        del self._user_sessions[user_id]

                logger.info(
                    f"WebSocket disconnected: user={user_id}, session={session_id}, duration={connection.connection_duration:.1f}s"
                )

    async def _send_message(
        self, connection: ClientConnection, message: WebSocketMessage
    ):
        """Send a message to a specific connection."""
        try:
            await connection.websocket.send_json(message.model_dump())
        except Exception as e:
            logger.error(f"Failed to send message to {connection.session_id}: {e}")
            raise

    async def send_to_session(self, session_id: str, message: WebSocketMessage):
        """Send a message to a specific session."""
        if session_id in self._connections:
            await self._send_message(self._connections[session_id], message)

    async def send_to_user(self, user_id: str, message: WebSocketMessage):
        """Send a message to all sessions of a user."""
        # Send to local connections
        if user_id in self._user_sessions:
            for session_id in self._user_sessions[user_id]:
                await self.send_to_session(session_id, message)

        # Publish to Redis for other instances
        if self._redis_enabled:
            try:
                await self._redis.publish(
                    "websocket_broadcast",
                    json.dumps(
                        {"user_id": user_id, "message": message.model_dump()}
                    ),
                )
            except Exception as e:
                logger.warning(f"Redis publish failed: {e}")

    async def broadcast(
        self, message: WebSocketMessage, exclude: Optional[Set[str]] = None
    ):
        """Broadcast a message to all connected clients."""
        exclude = exclude or set()
        
        # Broadcast locally
        for session_id, connection in self._connections.items():
            if session_id not in exclude:
                try:
                    await self._send_message(connection, message)
                except Exception as e:
                    logger.warning(f"Broadcast failed for {session_id}: {e}")

        # Publish to Redis for other instances
        if self._redis_enabled:
            try:
                await self._redis.publish(
                    "websocket_broadcast",
                    json.dumps(
                        {
                            "broadcast": True,
                            "message": message.model_dump(),
                            "exclude": list(exclude),
                        }
                    ),
                )
            except Exception as e:
                logger.warning(f"Redis broadcast publish failed: {e}")

    async def stream_tokens(self, session_id: str, token_generator, message_id: str):
        """Stream tokens from a generator to a client."""
        if session_id not in self._connections:
            logger.warning(f"Cannot stream to disconnected session: {session_id}")
            return

        connection = self._connections[session_id]
        full_response = ""

        try:
            async for token in token_generator:
                full_response += token
                await self._send_message(
                    connection,
                    WebSocketMessage(
                        type=MessageType.CHAT_TOKEN,
                        data={"token": token, "accumulated": full_response},
                        message_id=message_id,
                    ),
                )

            # Send completion message
            await self._send_message(
                connection,
                WebSocketMessage(
                    type=MessageType.CHAT_COMPLETE,
                    data={"full_response": full_response},
                    message_id=message_id,
                ),
            )

        except Exception as e:
            logger.error(f"Token streaming error: {e}")
            await self._send_message(
                connection,
                WebSocketMessage(
                    type=MessageType.ERROR,
                    data={"error": str(e), "code": "STREAM_ERROR"},
                    message_id=message_id,
                ),
            )

    def get_connection(self, session_id: str) -> Optional[ClientConnection]:
        """Get connection by session ID."""
        return self._connections.get(session_id)

    def get_user_sessions(self, user_id: str) -> Set[str]:
        """Get all session IDs for a user."""
        return self._user_sessions.get(user_id, set())

    @property
    def active_connections(self) -> int:
        """Number of active connections."""
        return len(self._connections)

    @property
    def active_users(self) -> int:
        """Number of unique connected users."""
        return len(self._user_sessions)

    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "active_connections": self.active_connections,
            "active_users": self.active_users,
            "sessions": list(self._connections.keys()),
        }


# Global connection manager instance
_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager


# ============================================================================
# WebSocket Router
# ============================================================================

websocket_router = APIRouter(prefix="/ws", tags=["websocket"])


@websocket_router.websocket("/chat/{session_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = Query(None),
):
    """
    Secured WebSocket endpoint for real-time chat.
    Requires JWT token in query parameter: ?token=...
    """
    manager = get_connection_manager()

    try:
        # Step 1: Validate token BEFORE accepting connection
        user_id = await validate_websocket_token(token)
        
        # Step 2: Accept connection only after authentication
        connection = await manager.connect(websocket, user_id, session_id)


        while True:
            # Receive message from client
            try:
                data = await websocket.receive_json()
            except json.JSONDecodeError:
                await manager.send_to_session(
                    session_id,
                    WebSocketMessage(
                        type=MessageType.ERROR,
                        data={"error": "Invalid JSON", "code": "INVALID_JSON"},
                    ),
                )
                continue

            msg_type = data.get("type", "")
            msg_data = data.get("data", {})
            msg_id = data.get("message_id", str(datetime.now().timestamp()))

            # Handle different message types
            if msg_type == MessageType.PING:
                await manager.send_to_session(
                    session_id,
                    WebSocketMessage(
                        type=MessageType.PONG,
                        data={"timestamp": datetime.now().isoformat()},
                    ),
                )

            elif msg_type == MessageType.CHAT_MESSAGE:
                await handle_chat_message(
                    manager=manager,
                    session_id=session_id,
                    user_id=user_id,
                    message_data=msg_data,
                    message_id=msg_id,
                )

            elif msg_type == MessageType.SUBSCRIBE:
                topic = msg_data.get("topic")
                if topic:
                    connection.subscriptions.add(topic)
                    await manager.send_to_session(
                        session_id,
                        WebSocketMessage(
                            type=MessageType.STATUS_UPDATE, data={"subscribed": topic}
                        ),
                    )

            elif msg_type == MessageType.UNSUBSCRIBE:
                topic = msg_data.get("topic")
                if topic:
                    connection.subscriptions.discard(topic)
                    await manager.send_to_session(
                        session_id,
                        WebSocketMessage(
                            type=MessageType.STATUS_UPDATE, data={"unsubscribed": topic}
                        ),
                    )

            else:
                await manager.send_to_session(
                    session_id,
                    WebSocketMessage(
                        type=MessageType.ERROR,
                        data={
                            "error": f"Unknown message type: {msg_type}",
                            "code": "UNKNOWN_TYPE",
                        },
                    ),
                )

    except WebSocketException as e:
        # Authentication failed - close connection immediately
        logger.warning(f"WebSocket authentication failed: {e.reason}")
        await websocket.close(code=e.code, reason=e.reason)

    except WebSocketDisconnect:
        await manager.disconnect(session_id)
    except Exception as e:
        logger.exception(f"WebSocket error for session {session_id}")
        await manager.disconnect(session_id)


async def handle_chat_message(
    manager: ConnectionManager,
    session_id: str,
    user_id: str,
    message_data: Dict[str, Any],
    message_id: str,
):
    """Handle incoming chat message and generate response."""
    try:
        message = message_data.get("message", "")
        model = message_data.get("model", "gemini")
        stream = message_data.get("stream", True)

        if not message:
            await manager.send_to_session(
                session_id,
                WebSocketMessage(
                    type=MessageType.ERROR,
                    data={"error": "Empty message", "code": "EMPTY_MESSAGE"},
                    message_id=message_id,
                ),
            )
            return

        # Send processing status
        await manager.send_to_session(
            session_id,
            WebSocketMessage(
                type=MessageType.STATUS_UPDATE,
                data={"status": "processing", "message": "Generating response..."},
                message_id=message_id,
            ),
        )

        if stream:
            # Stream response tokens
            async def generate_response():
                """Simulate streaming response - integrate with actual LLM."""
                # TODO: Integrate with OllamaGenerator or Gemini API
                response = f"This is a placeholder response to: {message}"
                for word in response.split():
                    yield word + " "
                    await asyncio.sleep(0.05)  # Simulate token generation delay

            await manager.stream_tokens(session_id, generate_response(), message_id)

        else:
            # Send complete response
            response = f"This is a placeholder response to: {message}"
            await manager.send_to_session(
                session_id,
                WebSocketMessage(
                    type=MessageType.CHAT_RESPONSE,
                    data={"response": response},
                    message_id=message_id,
                ),
            )

    except Exception as e:
        logger.exception(f"Error handling chat message: {e}")
        await manager.send_to_session(
            session_id,
            WebSocketMessage(
                type=MessageType.ERROR,
                data={"error": str(e), "code": "PROCESSING_ERROR"},
                message_id=message_id,
            ),
        )


@websocket_router.get("/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics."""
    manager = get_connection_manager()
    return manager.get_stats()


# ============================================================================
# Health Monitoring WebSocket
# ============================================================================


@websocket_router.websocket("/health-monitor/{user_id}")
async def websocket_health_monitor(
    websocket: WebSocket,
    user_id: str,
):
    """
    WebSocket endpoint for real-time health monitoring.

    Sends updates when:
    - Vital signs are logged
    - Medication reminders are due
    - Appointment reminders
    - Health alerts
    """
    manager = get_connection_manager()
    session_id = f"health-{user_id}-{datetime.now().timestamp()}"

    try:
        connection = await manager.connect(
            websocket, user_id, session_id, {"type": "health_monitor"}
        )

        # Subscribe to health-related topics
        connection.subscriptions.update(
            [
                f"vitals:{user_id}",
                f"medications:{user_id}",
                f"appointments:{user_id}",
                f"alerts:{user_id}",
            ]
        )

        # Keep connection alive
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(), timeout=30.0  # Send ping every 30 seconds
                )

                # Handle incoming messages
                msg_type = data.get("type", "")
                if msg_type == MessageType.PING:
                    await manager.send_to_session(
                        session_id,
                        WebSocketMessage(
                            type=MessageType.PONG,
                            data={"timestamp": datetime.now().isoformat()},
                        ),
                    )

            except asyncio.TimeoutError:
                # Send heartbeat
                await manager.send_to_session(
                    session_id,
                    WebSocketMessage(
                        type=MessageType.STATUS_UPDATE,
                        data={
                            "heartbeat": True,
                            "timestamp": datetime.now().isoformat(),
                        },
                    ),
                )

    except WebSocketDisconnect:
        await manager.disconnect(session_id)
    except Exception as e:
        logger.exception(f"Health monitor WebSocket error: {e}")
        await manager.disconnect(session_id)
