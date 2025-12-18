"""
Smart Watch Router Module
Handles device integration, vitals ingestion, and ML-powered health analysis.
"""

import os
import logging
import datetime
import asyncio
from typing import List, Literal, Optional, Dict, Any
from contextlib import asynccontextmanager

import asyncpg
import pandas as pd
from dateutil import parser as dt_parser
from fastapi import APIRouter, Header, HTTPException, BackgroundTasks, Request, status, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, validator

# Import configuration
from config import (
    DATABASE_URL,
    LOG_LEVEL
)

# Import dependencies
# Note: We'll need to ensure these dependencies exist or create them
# from core.dependencies import get_current_user  # Example dependency

# Import ML components (will be moved to this package)
from .anomaly_detector import AnomalyDetector
from .health_explainer import HealthExplainer, AlertChannel
# from .feature_extractor import FeatureExtractor # If needed directly
# from .rule_engine import RuleEngine # If needed directly

# Configure logging
logger = logging.getLogger("nlp-service.smart-watch")

# Create Router
router = APIRouter(prefix="/api/smartwatch", tags=["Smart Watch"])

# --------- Configuration Constants ----------
# These should ideally move to config.py
DEVICE_API_KEYS = os.getenv("DEVICE_API_KEYS", "device_key_example").split(",")
MAX_SAMPLES_PER_REQUEST = int(os.getenv("MAX_SAMPLES_PER_REQUEST", "1000"))

# --------- Global State ----------
# In a router, we rely on the main app's lifespan or dependency injection for DB pools.
# For now, we'll keep a local pool reference but it should ideally be injected.
db_pool: Optional[asyncpg.pool.Pool] = None
health_explainer: Optional[HealthExplainer] = None

# --------- Pydantic Models ----------
class TimeSeriesDataPoint(BaseModel):
    metric_type: Literal["hr", "ppg", "steps", "spo2"] = Field(..., description="Metric type")
    value: float = Field(..., description="Metric value")
    timestamp: datetime.datetime = Field(..., description="UTC timestamp when recorded")

    @validator("timestamp")
    def ensure_timezone_aware(cls, v: datetime.datetime):
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("timestamp must be timezone-aware (e.g. include +00:00). Use UTC.")
        return v

class TimeSeriesPayload(BaseModel):
    device_id: str = Field(..., description="Unique identifier for the device")
    samples: List[TimeSeriesDataPoint]

    @validator("samples")
    def samples_limit(cls, v):
        if not v:
            raise ValueError("samples must not be empty")
        if len(v) > MAX_SAMPLES_PER_REQUEST:
            raise ValueError(f"too many samples: limit is {MAX_SAMPLES_PER_REQUEST}")
        return v

class HealthAnalyzeRequest(BaseModel):
    device_id: str = Field(..., description="Device identifier")
    hr: float = Field(..., description="Heart rate in BPM")
    spo2: float = Field(98.0, description="Blood oxygen percentage")
    steps: int = Field(0, description="Step count")

class HealthQuestionRequest(BaseModel):
    question: str = Field(..., description="Health question to ask")
    include_vitals: bool = Field(True, description="Include vitals in context")

# --------- Dependencies ----------
def verify_device_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Dependency to enforce API Key auth on routes."""
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key")
    if x_api_key not in DEVICE_API_KEYS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return True

# --------- Core Logic: Ingestion (Write) ----------
async def _persist_samples(device_id: str, samples: List[TimeSeriesDataPoint], idempotency_key: Optional[str]):
    """
    Background task: Bulk insert samples into PostgreSQL using efficient executemany.
    """
    # We need to access the DB pool. In a router, this is tricky without DI.
    # For this refactor, we will assume a global pool is available or passed.
    # TODO: Refactor to use dependency injection for DB connection
    if not db_pool:
        logger.error("DB pool not available for background task.")
        return

    insert_sql = """
    INSERT INTO device_timeseries (device_id, metric_type, value, ts, idempotency_key)
    VALUES ($1, $2, $3, $4, $5)
    ON CONFLICT DO NOTHING
    """

    data_tuples = [
        (device_id, s.metric_type, s.value, s.timestamp, idempotency_key)
        for s in samples
    ]

    async with db_pool.acquire() as conn:
        try:
            await conn.executemany(insert_sql, data_tuples)
            logger.info(f"Persisted {len(samples)} samples for {device_id}")
        except Exception as e:
            logger.exception(f"Failed to persist samples: {e}")

@router.post("/vitals", status_code=201)
async def ingest_timeseries_data(
    payload: TimeSeriesPayload,
    background: BackgroundTasks,
    authorized: bool = Depends(verify_device_api_key),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    """
    Accepts high-frequency data from devices and offloads writing to background.
    """
    logger.info(f"Received {len(payload.samples)} samples from {payload.device_id}")
    background.add_task(_persist_samples, payload.device_id, payload.samples, x_idempotency_key)
    return {
        "status": "accepted",
        "device_id": payload.device_id,
        "count": len(payload.samples)
    }

# --------- Core Logic: Aggregation (Read) ----------
INTERVAL_MAP = {
    "1min": "T", "5min": "5T", "15min": "15T", "30min": "30T", "hour": "H", "day": "D",
}

def _calculate_aggregates(rows, interval: str):
    """
    CPU-bound function run in a separate thread.
    Uses Pandas to resample and aggregate time-series data.
    """
    if not rows:
        return []

    data = [{"ts": r["ts"], "value": r["value"]} for r in rows]
    df = pd.DataFrame(data)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df = df.set_index("ts")

    rule = INTERVAL_MAP.get(interval, "H")
    agg = df["value"].resample(rule).agg(["mean", "min", "max", "count"])
    agg = agg.rename(columns={"mean": "avg", "count": "samples"})

    buckets = []
    for ts, row in agg.iterrows():
        if row["samples"] == 0:
            continue
        buckets.append({
            "bucket_start": ts.isoformat(),
            "samples": int(row["samples"]),
            "avg": row["avg"] if not pd.isna(row["avg"]) else None,
            "min": row["min"] if not pd.isna(row["min"]) else None,
            "max": row["max"] if not pd.isna(row["max"]) else None,
        })
    return buckets

@router.get("/{device_id}/aggregate")
async def aggregate_device_timeseries(
    device_id: str,
    metric_type: str = Query("hr", description="Metric (hr, ppg, steps, spo2)"),
    start: Optional[str] = Query(None, description="Start time (ISO8601)"),
    end: Optional[str] = Query(None, description="End time (ISO8601)"),
    interval: Literal["1min", "5min", "15min", "30min", "hour", "day"] = Query("hour"),
    authorized: bool = Depends(verify_device_api_key),
):
    """
    Returns aggregated metrics. Uses asyncio.to_thread to prevent blocking.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    try:
        end_dt = dt_parser.isoparse(end).astimezone(datetime.timezone.utc) if end else now_utc
        start_dt = dt_parser.isoparse(start).astimezone(datetime.timezone.utc) if start else end_dt - datetime.timedelta(hours=24)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid timestamp format")

    if start_dt >= end_dt:
        raise HTTPException(status_code=400, detail="start time must be before end time")

    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    query = """
        SELECT ts, value FROM device_timeseries
        WHERE device_id = $1 AND metric_type = $2 AND ts >= $3 AND ts <= $4
        ORDER BY ts ASC
    """
    
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, device_id, metric_type, start_dt, end_dt)

    buckets = await asyncio.to_thread(_calculate_aggregates, rows, interval)

    return {
        "device_id": device_id,
        "metric_type": metric_type,
        "interval": interval,
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat(),
        "buckets": buckets,
    }

# --------- WebSocket: Real-Time Streaming ----------
active_connections: Dict[str, WebSocket] = {}

@router.websocket("/ws/{device_id}")
async def websocket_health_stream(websocket: WebSocket, device_id: str):
    """
    Real-time WebSocket endpoint for streaming health data to frontend.
    """
    await websocket.accept()
    active_connections[device_id] = websocket
    logger.info(f"WebSocket connected: {device_id}")
    
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Received from {device_id}: {data}")
    except WebSocketDisconnect:
        if device_id in active_connections:
            del active_connections[device_id]
        logger.info(f"WebSocket disconnected: {device_id}")


# =====================================================================
# ML-POWERED HEALTH ANALYSIS ENDPOINTS
# =====================================================================

@router.post("/analyze")
async def analyze_health_data(
    request: HealthAnalyzeRequest,
    authorized: bool = Depends(verify_device_api_key)
):
    """
    Analyze health data with ML prediction and chatbot explanation.
    """
    if not health_explainer:
        raise HTTPException(status_code=503, detail="Health analyzer not initialized")
    
    result = await health_explainer.analyze(
        device_id=request.device_id,
        hr=request.hr,
        spo2=request.spo2,
        steps=request.steps
    )
    
    return {
        "status": result.status,
        "explanation": result.explanation,
        "alert": result.alert,
        "prediction": result.prediction,
        "processing_time_ms": result.processing_time_ms
    }


@router.post("/ask")
async def ask_health_question(
    request: HealthQuestionRequest,
    authorized: bool = Depends(verify_device_api_key)
):
    """
    Ask the health chatbot a question.
    """
    if not health_explainer:
        raise HTTPException(status_code=503, detail="Health analyzer not initialized")
    
    response = await health_explainer.ask_question(
        question=request.question, 
        include_vitals=request.include_vitals
    )
    
    return {"response": response}


@router.get("/system/status")
async def get_system_status():
    """
    Get health analysis system status.
    """
    if not health_explainer:
        return {"status": "not_initialized"}
    
    return health_explainer.get_status()


@router.get("/alerts")
async def get_recent_alerts(
    limit: int = Query(10, le=100, description="Maximum alerts to return"),
    authorized: bool = Depends(verify_device_api_key)
):
    """
    Get recent health alerts.
    """
    if not health_explainer:
        raise HTTPException(status_code=503, detail="Health analyzer not initialized")
    
    alerts = health_explainer.get_recent_alerts(limit)
    return {"alerts": alerts, "count": len(alerts)}


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    authorized: bool = Depends(verify_device_api_key)
):
    """
    Acknowledge a health alert.
    """
    if not health_explainer:
        raise HTTPException(status_code=503, detail="Health analyzer not initialized")
    
    success = health_explainer.acknowledge_alert(alert_id)
    if success:
        return {"status": "acknowledged", "alert_id": alert_id}
    else:
        raise HTTPException(status_code=404, detail="Alert not found")

# --------- Startup/Shutdown Logic for Router ----------
# Routers don't have lifespan, so we need a way to initialize the DB pool.
# We can expose an init function to be called by main.py's lifespan.

async def init_smartwatch_module():
    """Initialize resources for the smart watch module."""
    global db_pool
    logger.info("Initializing Smart Watch module...")
    try:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
        logger.info("Smart Watch DB pool created.")
    except Exception as e:
        logger.error(f"Failed to connect to DB: {e}")
        # Don't raise, allow partial startup? Or raise?
        # For now, log error.
    
    # Initialize Health Explainer
    global health_explainer
    logger.info("Initializing health explainer...")
    try:
        health_explainer = HealthExplainer(
            user_profile={'name': 'User'},  # Default profile
            enable_chatbot=True
        )
        
        # Register WebSocket handler for real-time alerts
        async def websocket_alert_handler(alert):
            """Send alerts to connected WebSocket clients."""
            for device_id, ws in active_connections.items():
                try:
                    alert_data = {
                        'id': alert.id,
                        'timestamp': alert.timestamp,
                        'anomaly_type': alert.anomaly_type,
                        'severity': alert.severity,
                        'title': alert.title,
                        'message': alert.message,
                        'recommendation': alert.recommendation,
                        'chatbot_explanation': alert.chatbot_explanation,
                        'channels': [c.value for c in alert.channels]
                    }
                    await ws.send_json({
                        "type": "health_alert",
                        "alert": alert_data
                    })
                except Exception as e:
                    logger.error(f"Failed to send alert to {device_id}: {e}")
        
        health_explainer.register_alert_handler(AlertChannel.WEBSOCKET, websocket_alert_handler)
        logger.info("Health explainer initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Health Explainer: {e}")

async def shutdown_smartwatch_module():
    """Cleanup resources."""
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("Smart Watch DB pool closed.")

