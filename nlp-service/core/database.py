"""
Production-grade database layer with connection pooling, resilience, and monitoring.

Features:
- Connection pooling with configurable strategies
- **Adaptive pool sizing based on load** (NEW)
- **Enhanced pool monitoring with metrics** (NEW)
- Automatic retry logic for transient failures
- Health checks and monitoring
- Session lifecycle management
- Environment-aware configuration
"""

import logging
import os
import threading
import time
from contextlib import contextmanager, asynccontextmanager
from typing import Generator, Optional, Dict, Any, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque

from sqlalchemy import create_engine, event, Engine, text
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.exc import SQLAlchemyError, OperationalError, DisconnectionError
from sqlalchemy.pool import QueuePool, NullPool, StaticPool
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)


# ============================================================================
# POOL MONITORING
# ============================================================================

@dataclass
class PoolSnapshot:
    """Point-in-time snapshot of connection pool state."""
    timestamp: datetime
    checked_out: int
    overflow: int
    pool_size: int
    max_overflow: int
    utilization_pct: float
    wait_queue_size: int = 0
    
    @property
    def total_available(self) -> int:
        return self.pool_size + self.max_overflow - self.checked_out - self.overflow


class PoolMetricsCollector:
    """Collects and analyzes connection pool metrics over time."""
    
    def __init__(self, max_snapshots: int = 1000):
        self.snapshots: deque = deque(maxlen=max_snapshots)
        self.connection_wait_times: deque = deque(maxlen=5000)
        self.query_durations: deque = deque(maxlen=5000)
        self._lock = threading.Lock()
        
        # Counters
        self.total_connections = 0
        self.total_timeouts = 0
        self.total_queries = 0
        self.peak_checked_out = 0
    
    def record_snapshot(self, snapshot: PoolSnapshot) -> None:
        """Record a pool snapshot."""
        with self._lock:
            self.snapshots.append(snapshot)
            self.peak_checked_out = max(self.peak_checked_out, snapshot.checked_out)
    
    def record_connection_wait(self, wait_time_ms: float) -> None:
        """Record time spent waiting for a connection."""
        with self._lock:
            self.connection_wait_times.append(wait_time_ms)
            self.total_connections += 1
    
    def record_query_duration(self, duration_ms: float) -> None:
        """Record query execution time."""
        with self._lock:
            self.query_durations.append(duration_ms)
            self.total_queries += 1
    
    def record_timeout(self) -> None:
        """Record a connection timeout."""
        with self._lock:
            self.total_timeouts += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get aggregated pool metrics."""
        with self._lock:
            if not self.snapshots:
                return {"status": "no_data"}
            
            recent_snapshots = list(self.snapshots)[-100:]
            recent_waits = list(self.connection_wait_times)[-1000:]
            recent_queries = list(self.query_durations)[-1000:]
            
            # Calculate utilization statistics
            utilizations = [s.utilization_pct for s in recent_snapshots]
            avg_utilization = sum(utilizations) / len(utilizations) if utilizations else 0
            
            return {
                "snapshot_count": len(self.snapshots),
                "total_connections": self.total_connections,
                "total_timeouts": self.total_timeouts,
                "total_queries": self.total_queries,
                "peak_checked_out": self.peak_checked_out,
                "utilization": {
                    "current": recent_snapshots[-1].utilization_pct if recent_snapshots else 0,
                    "avg_recent": round(avg_utilization, 2),
                    "max_recent": max(utilizations) if utilizations else 0,
                },
                "connection_wait_ms": {
                    "avg": round(sum(recent_waits) / len(recent_waits), 2) if recent_waits else 0,
                    "p95": self._percentile(recent_waits, 95) if recent_waits else 0,
                    "max": max(recent_waits) if recent_waits else 0,
                },
                "query_duration_ms": {
                    "avg": round(sum(recent_queries) / len(recent_queries), 2) if recent_queries else 0,
                    "p95": self._percentile(recent_queries, 95) if recent_queries else 0,
                },
                "timeout_rate": round(self.total_timeouts / max(self.total_connections, 1) * 100, 2),
            }
    
    @staticmethod
    def _percentile(data: List[float], pct: int) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0
        sorted_data = sorted(data)
        idx = int(len(sorted_data) * pct / 100)
        return round(sorted_data[min(idx, len(sorted_data) - 1)], 2)


# ============================================================================
# ADAPTIVE POOL SIZING
# ============================================================================

@dataclass
class PoolSizeConfig:
    """Configuration for adaptive pool sizing."""
    min_size: int = 5
    max_size: int = 50
    initial_size: int = 10
    scale_up_threshold: float = 0.80  # Scale up when >80% utilized
    scale_down_threshold: float = 0.30  # Scale down when <30% utilized
    scale_factor: float = 1.5  # Multiply by this when scaling up
    cooldown_seconds: int = 60  # Wait between resize operations
    check_interval_seconds: int = 10  # How often to check utilization


class AdaptivePoolManager:
    """
    Manages dynamic connection pool sizing based on load.
    
    Features:
    - Automatically scales pool size up when utilization is high
    - Scales down when utilization drops to save resources
    - Respects min/max size boundaries
    - Cooldown period prevents thrashing
    - Thread-safe operation
    """
    
    def __init__(
        self,
        config: PoolSizeConfig = None,
        metrics_collector: PoolMetricsCollector = None,
    ):
        self.config = config or PoolSizeConfig()
        self.metrics = metrics_collector or PoolMetricsCollector()
        
        self.current_size = self.config.initial_size
        self.current_overflow = self.config.max_size - self.config.initial_size
        
        self._last_resize_time: Optional[datetime] = None
        self._resize_history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._monitoring_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        
        # Callbacks for resize events
        self._resize_callbacks: List[Callable[[int, int], None]] = []
    
    def register_resize_callback(self, callback: Callable[[int, int], None]) -> None:
        """Register callback for pool resize events.
        
        Args:
            callback: Function(old_size, new_size) called on resize
        """
        self._resize_callbacks.append(callback)
    
    def evaluate_and_resize(self, current_utilization: float) -> Optional[int]:
        """
        Evaluate current utilization and resize pool if needed.
        
        Args:
            current_utilization: Current pool utilization (0.0 - 1.0)
            
        Returns:
            New pool size if resized, None if no change
        """
        with self._lock:
            now = datetime.now()
            
            # Check cooldown
            if self._last_resize_time:
                elapsed = (now - self._last_resize_time).total_seconds()
                if elapsed < self.config.cooldown_seconds:
                    return None
            
            old_size = self.current_size
            new_size = None
            reason = ""
            
            # Scale UP if utilization is high
            if current_utilization > self.config.scale_up_threshold:
                proposed_size = int(self.current_size * self.config.scale_factor)
                new_size = min(proposed_size, self.config.max_size)
                reason = f"high_utilization ({current_utilization:.1%})"
            
            # Scale DOWN if utilization is low
            elif current_utilization < self.config.scale_down_threshold:
                proposed_size = int(self.current_size / self.config.scale_factor)
                new_size = max(proposed_size, self.config.min_size)
                reason = f"low_utilization ({current_utilization:.1%})"
            
            # Apply resize if changed
            if new_size and new_size != old_size:
                self.current_size = new_size
                self.current_overflow = max(0, self.config.max_size - new_size)
                self._last_resize_time = now
                
                self._resize_history.append({
                    "timestamp": now.isoformat(),
                    "old_size": old_size,
                    "new_size": new_size,
                    "utilization": current_utilization,
                    "reason": reason,
                })
                
                # Keep history bounded
                if len(self._resize_history) > 100:
                    self._resize_history = self._resize_history[-50:]
                
                logger.info(
                    f"Pool resized: {old_size} -> {new_size} "
                    f"(reason: {reason})"
                )
                
                # Notify callbacks
                for callback in self._resize_callbacks:
                    try:
                        callback(old_size, new_size)
                    except Exception as e:
                        logger.error(f"Resize callback error: {e}")
                
                return new_size
            
            return None
    
    def get_recommended_size(self) -> Dict[str, int]:
        """Get current recommended pool configuration."""
        return {
            "pool_size": self.current_size,
            "max_overflow": self.current_overflow,
        }
    
    def get_resize_history(self) -> List[Dict[str, Any]]:
        """Get history of resize operations."""
        with self._lock:
            return list(self._resize_history)
    
    def get_status(self) -> Dict[str, Any]:
        """Get adaptive pool manager status."""
        return {
            "current_size": self.current_size,
            "current_overflow": self.current_overflow,
            "config": {
                "min_size": self.config.min_size,
                "max_size": self.config.max_size,
                "scale_up_threshold": self.config.scale_up_threshold,
                "scale_down_threshold": self.config.scale_down_threshold,
            },
            "last_resize": self._last_resize_time.isoformat() if self._last_resize_time else None,
            "resize_count": len(self._resize_history),
            "monitoring_active": self._monitoring_thread is not None and self._monitoring_thread.is_alive(),
        }


class DatabaseConfig:
    """Database configuration for different environments."""
    
    # Determine environment
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
    
    # Connection pooling strategy based on environment
    POOL_STRATEGIES = {
        "production": QueuePool,      # Thread-safe, connection queueing
        "staging": QueuePool,
        "development": StaticPool,    # Single shared connection (for SQLite)
        "testing": NullPool,          # New connection each time (isolation)
    }
    
    # Pool parameters (tuned for healthcare workloads)
    POOL_PARAMS = {
        "pool_size": 10,              # Default connections in pool
        "max_overflow": 20,           # Additional connections if needed
        "pool_timeout": 30,           # Wait 30s for available connection
        "pool_recycle": 3600,         # Recycle connections every hour
        "pool_pre_ping": True,        # Test connections before use (detect stale)
        "echo": False,                # Log SQL statements (set True in debug)
    }
    
    # Query timeout (healthcare apps need predictable performance)
    QUERY_TIMEOUT = 30  # seconds
    
    # Connection retry strategy
    RETRY_CONFIG = {
        "stop": stop_after_attempt(3),
        "wait": wait_exponential(multiplier=1, min=2, max=10),
        "retry": retry_if_exception_type((OperationalError, DisconnectionError)),
    }


class DatabaseConnection:
    """Manages database connection lifecycle with resilience and adaptive sizing."""
    
    def __init__(
        self,
        database_url: str,
        environment: str = None,
        pool_size: int = None,
        max_overflow: int = None,
        enable_adaptive_sizing: bool = True,
    ):
        """Initialize database connection with appropriate pooling strategy.
        
        Args:
            database_url: SQLAlchemy database URL
            environment: Environment name (production, staging, development, testing)
            pool_size: Initial pool size (default from config)
            max_overflow: Max overflow connections (default from config)
            enable_adaptive_sizing: Enable dynamic pool sizing based on load
        """
        
        self.database_url = database_url
        self.environment = environment or DatabaseConfig.ENVIRONMENT
        
        # Use provided values or defaults
        self.pool_size = pool_size or DatabaseConfig.POOL_PARAMS["pool_size"]
        self.max_overflow = max_overflow or DatabaseConfig.POOL_PARAMS["max_overflow"]
        
        # Initialize metrics collector
        self.metrics_collector = PoolMetricsCollector()
        
        # Initialize adaptive pool manager if enabled
        self.enable_adaptive_sizing = enable_adaptive_sizing
        self.adaptive_manager: Optional[AdaptivePoolManager] = None
        if enable_adaptive_sizing and self.environment in ("production", "staging"):
            self.adaptive_manager = AdaptivePoolManager(
                config=PoolSizeConfig(
                    min_size=5,
                    max_size=self.pool_size + self.max_overflow,
                    initial_size=self.pool_size,
                ),
                metrics_collector=self.metrics_collector,
            )
            # Update initial sizes from adaptive manager
            recommended = self.adaptive_manager.get_recommended_size()
            self.pool_size = recommended["pool_size"]
            self.max_overflow = recommended["max_overflow"]
        
        # Select pooling strategy
        pool_class = DatabaseConfig.POOL_STRATEGIES.get(
            self.environment,
            QueuePool
        )
        
        # Create engine with resilience parameters
        self.engine: Engine = self._create_engine(pool_class)
        
        # Create session factory with scoped sessions (thread-safe)
        self.SessionFactory = scoped_session(
            sessionmaker(
                bind=self.engine,
                expire_on_commit=False,  # Prevent lazy loading after commit
                autoflush=True,
                autocommit=False,
            )
        )
        
        # Setup event listeners for monitoring
        self._setup_event_listeners()
        
        # Connection metrics
        self.connection_metrics = {
            "acquired": 0,
            "released": 0,
            "failures": 0,
        }
        
        logger.info(
            f"Database initialized: environment={self.environment} | "
            f"pool_class={pool_class.__name__} | "
            f"pool_size={self.pool_size} | "
            f"adaptive_sizing={'enabled' if self.adaptive_manager else 'disabled'} | "
            f"url={self._mask_url(database_url)}"
        )
    
    def _create_engine(self, pool_class):
        """Create SQLAlchemy engine with production parameters."""
        
        # Adjust pool parameters based on environment
        pool_params = DatabaseConfig.POOL_PARAMS.copy()
        pool_params["pool_size"] = self.pool_size
        pool_params["max_overflow"] = self.max_overflow
        
        # SQLite doesn't use connection pooling
        if "sqlite" in self.database_url:
            pool_class = StaticPool
            pool_params = {
                "echo": pool_params["echo"],
            }
            logger.info("Using StaticPool for SQLite (single connection)")
        
        return create_engine(
            self.database_url,
            poolclass=pool_class,
            **pool_params,
            # Connection string parameters
            connect_args={
                "timeout": DatabaseConfig.QUERY_TIMEOUT,
                "check_same_thread": False,  # For SQLite in tests
            } if "sqlite" in self.database_url else {}
        )
    
    def _setup_event_listeners(self):
        """Setup SQLAlchemy event listeners for monitoring."""
        
        @event.listens_for(Engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            """Log connection acquisition."""
            self.connection_metrics["acquired"] += 1
            logger.debug(f"Database connection acquired: {id(dbapi_conn)}")
        
        @event.listens_for(Engine, "close")
        def receive_close(dbapi_conn, connection_record):
            """Log connection release."""
            self.connection_metrics["released"] += 1
            logger.debug(f"Database connection released: {id(dbapi_conn)}")
        
        @event.listens_for(Engine, "close")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            """SQLite-specific optimizations (only for SQLite)."""
            if "sqlite" in self.database_url:
                try:
                    cursor = dbapi_conn.cursor()
                    cursor.execute("PRAGMA foreign_keys=ON")  # Enable FK constraints
                    cursor.execute("PRAGMA journal_mode=WAL")  # Write-ahead logging
                    cursor.close()
                except Exception as e:
                    logger.warning(f"Failed to set SQLite pragmas: {e}")
        
        # Enhanced monitoring: record pool snapshots periodically
        @event.listens_for(Engine, "checkout")
        def on_checkout(dbapi_conn, connection_record, connection_proxy):
            """Track connection checkout for adaptive sizing."""
            connection_record.info["checkout_time"] = time.time()
            self._record_pool_snapshot()
        
        @event.listens_for(Engine, "checkin")
        def on_checkin(dbapi_conn, connection_record):
            """Track connection checkin and wait time."""
            checkout_time = connection_record.info.get("checkout_time")
            if checkout_time:
                duration_ms = (time.time() - checkout_time) * 1000
                self.metrics_collector.record_query_duration(duration_ms)
    
    def get_session(self) -> Session:
        """Get a thread-safe database session."""
        return self.SessionFactory()
    
    def close_session(self):
        """Close current thread's session."""
        self.SessionFactory.remove()
    
    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Context manager for session lifecycle management.
        
        Ensures proper cleanup and error handling:
        - Automatic commit on success
        - Automatic rollback on exception
        - Guaranteed cleanup regardless of outcome
        
        Usage:
            with db.session_scope() as session:
                user = session.query(User).first()
                
        Raises:
            SQLAlchemyError: If database operation fails
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            self.connection_metrics["failures"] += 1
            logger.error(f"Database transaction failed: {e}", exc_info=True)
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Unexpected error in database transaction: {e}", exc_info=True)
            raise
        finally:
            session.close()
    
    @retry(**DatabaseConfig.RETRY_CONFIG)
    def execute_with_retry(self, query_func, *args, **kwargs):
        """Execute query with automatic retry on transient failures.
        
        Handles:
        - Network timeouts
        - Connection pool exhaustion (temporary)
        - Temporary database unavailability
        - Connection stale errors
        
        Args:
            query_func: Callable that takes session as first arg
            *args: Positional arguments for query_func
            **kwargs: Keyword arguments for query_func
        
        Returns:
            Result from query_func
        
        Raises:
            OperationalError: If max retries exceeded
        
        Example:
            def get_user(session, user_id):
                return session.query(User).filter(User.id == user_id).first()
            
            user = db.execute_with_retry(get_user, user_id=123)
        """
        with self.session_scope() as session:
            return query_func(session, *args, **kwargs)
    
    def health_check(self) -> bool:
        """Check database connectivity and health.
        
        Returns:
            True if database is healthy, False otherwise
        """
        try:
            with self.session_scope() as session:
                # Execute simple query
                session.execute(text("SELECT 1"))
            logger.info("Database health check: PASSED")
            return True
        except Exception as e:
            logger.error(f"Database health check: FAILED - {e}")
            return False
    
    def get_connection_pool_stats(self) -> Dict[str, Any]:
        """Return connection pool statistics for monitoring.
        
        Returns:
            Dictionary with pool statistics or empty dict for unsupported pools
        """
        pool = self.engine.pool
        
        try:
            if hasattr(pool, "checkedout"):
                return {
                    "type": "QueuePool",
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                    "pool_size": self.pool_size,
                    "max_overflow": self.max_overflow,
                }
            elif hasattr(pool, "_conn"):
                return {
                    "type": "StaticPool",
                    "status": "single_connection",
                }
            else:
                return {
                    "type": type(pool).__name__,
                    "status": "unknown",
                }
        except Exception as e:
            logger.warning(f"Failed to get pool stats: {e}")
            return {"type": type(pool).__name__, "status": "error", "error": str(e)}
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get connection metrics for observability."""
        metrics = {
            "connections_acquired": self.connection_metrics["acquired"],
            "connections_released": self.connection_metrics["released"],
            "connection_failures": self.connection_metrics["failures"],
            "pool_stats": self.get_connection_pool_stats(),
            "detailed_metrics": self.metrics_collector.get_metrics(),
        }
        
        # Add adaptive sizing info if enabled
        if self.adaptive_manager:
            metrics["adaptive_sizing"] = self.adaptive_manager.get_status()
        
        return metrics
    
    def _record_pool_snapshot(self) -> None:
        """Record current pool state for monitoring."""
        try:
            pool = self.engine.pool
            if hasattr(pool, "checkedout"):
                checked_out = pool.checkedout()
                overflow = pool.overflow()
                total_capacity = self.pool_size + self.max_overflow
                utilization = checked_out / total_capacity if total_capacity > 0 else 0
                
                snapshot = PoolSnapshot(
                    timestamp=datetime.now(),
                    checked_out=checked_out,
                    overflow=overflow,
                    pool_size=self.pool_size,
                    max_overflow=self.max_overflow,
                    utilization_pct=round(utilization * 100, 2),
                )
                self.metrics_collector.record_snapshot(snapshot)
                
                # Trigger adaptive sizing evaluation
                if self.adaptive_manager:
                    self.adaptive_manager.evaluate_and_resize(utilization)
        except Exception as e:
            logger.debug(f"Failed to record pool snapshot: {e}")
    
    def get_adaptive_sizing_status(self) -> Dict[str, Any]:
        """Get adaptive pool sizing status and history."""
        if not self.adaptive_manager:
            return {"enabled": False, "reason": "Not enabled for this environment"}
        
        return {
            "enabled": True,
            "status": self.adaptive_manager.get_status(),
            "resize_history": self.adaptive_manager.get_resize_history()[-10:],  # Last 10
        }
    
    def force_pool_resize(self, new_size: int) -> bool:
        """Manually resize the connection pool.
        
        Note: This requires engine recreation and should be used carefully.
        For most cases, let the adaptive manager handle resizing.
        
        Args:
            new_size: New pool size
            
        Returns:
            True if resize was requested, False if not supported
        """
        if not self.adaptive_manager:
            logger.warning("Manual resize not available without adaptive manager")
            return False
        
        # Update adaptive manager
        with self.adaptive_manager._lock:
            old_size = self.adaptive_manager.current_size
            self.adaptive_manager.current_size = new_size
            self.adaptive_manager._resize_history.append({
                "timestamp": datetime.now().isoformat(),
                "old_size": old_size,
                "new_size": new_size,
                "reason": "manual_resize",
            })
        
        logger.info(f"Manual pool resize requested: {old_size} -> {new_size}")
        return True
    
    def dispose(self):
        """Close all connections in the pool.
        
        Use during graceful shutdown to ensure all resources are cleaned up.
        """
        try:
            self.SessionFactory.remove()
            self.engine.dispose()
            logger.info("Database connections disposed successfully")
        except Exception as e:
            logger.error(f"Error disposing database connections: {e}")
    
    @staticmethod
    def _mask_url(url: str) -> str:
        """Mask credentials in URL for safe logging."""
        if "@" in url:
            scheme_and_creds, host = url.split("@", 1)
            return scheme_and_creds.rsplit("://", 1)[0] + "://***@" + host
        return url


# ============================================================================
# GLOBAL DATABASE INSTANCE
# ============================================================================

# Import database URL from config
from config import DATABASE_URL

db = DatabaseConnection(
    database_url=DATABASE_URL,
    environment=DatabaseConfig.ENVIRONMENT
)

# Backward compatibility for existing code
SessionLocal = db.SessionFactory
engine = db.engine


# ============================================================================
# MIDDLEWARE FOR SESSION CLEANUP (FastAPI integration)
# ============================================================================

async def cleanup_database_session():
    """Cleanup database session after request.
    
    Can be used with:
    - @app.middleware("http")
    - Dependencies in route handlers
    """
    try:
        yield
    finally:
        db.close_session()


# ============================================================================
# HELPER FUNCTIONS FOR COMMON PATTERNS
# ============================================================================

def transactional_operation(func):
    """Decorator for transactional database operations.
    
    Usage:
        @transactional_operation
        def create_user(session, name: str):
            user = User(name=name)
            session.add(user)
            return user  # Automatic commit
    """
    def wrapper(*args, **kwargs):
        with db.session_scope() as session:
            return func(session, *args, **kwargs)
    return wrapper
