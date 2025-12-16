import os
import logging
import datetime
import asyncio
from contextlib import asynccontextmanager
from typing import List, Literal, Optional, Dict
from dataclasses import asdict

import asyncpg
import pandas as pd
from dateutil import parser as dt_parser
from fastapi import FastAPI, Header, HTTPException, BackgroundTasks, Request, status, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field, validator

# ML Imports
from ml import HealthExplainer, AlertChannel

# --------- Configuration ----------
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/healthdb")
# In production, use a secure secret manager or env vars
DEVICE_API_KEYS = os.getenv("DEVICE_API_KEYS", "device_key_example").split(",")
MAX_SAMPLES_PER_REQUEST = int(os.getenv("MAX_SAMPLES_PER_REQUEST", "1000"))

# --------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("health-api")

# --------- Global State ----------
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

# --------- Pydantic Models for ML Endpoints ----------
class HealthAnalyzeRequest(BaseModel):
    device_id: str = Field(..., description="Device identifier")
    hr: float = Field(..., description="Heart rate in BPM")
    spo2: float = Field(98.0, description="Blood oxygen percentage")
    steps: int = Field(0, description="Step count")

class HealthQuestionRequest(BaseModel):
    question: str = Field(..., description="Health question to ask")
    include_vitals: bool = Field(True, description="Include vitals in context")

# --------- Database & Lifespan ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global db_pool, health_explainer
    logger.info("Initializing database pool...")
    try:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
        logger.info("Database pool created.")
        
        # Initialize Health Explainer
        logger.info("Initializing health explainer...")
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
        
        yield
    except Exception as e:
        logger.error(f"Failed to connect to DB: {e}")
        raise
    finally:
        # Shutdown
        if db_pool:
            await db_pool.close()
            logger.info("Database pool closed.")

app = FastAPI(title="Health Super-App Backend", version="1.0.0", lifespan=lifespan)

# Add GZIP compression for bandwidth optimization
app.add_middleware(GZipMiddleware, minimum_size=1000)

# --------- WebSocket Connections ----------
active_connections: Dict[str, WebSocket] = {}

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
    if not db_pool:
        logger.error("DB pool not available for background task.")
        return

    insert_sql = """
    INSERT INTO device_timeseries (device_id, metric_type, value, ts, idempotency_key)
    VALUES ($1, $2, $3, $4, $5)
    ON CONFLICT DO NOTHING
    """

    # Prepare data as list of tuples for asyncpg
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

@app.post("/api/v1/ingest/timeseries", status_code=201)
async def ingest_timeseries_data(
    payload: TimeSeriesPayload,
    background: BackgroundTasks,
    authorized: bool = Depends(verify_device_api_key),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    """
    Accepts high-frequency data from devices and offloads writing to background.
    """
    # Log intake
    logger.info(f"Received {len(payload.samples)} samples from {payload.device_id}")

    # Offload to background task
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

    # 1. Load data into DataFrame
    # Explicit dict construction is faster/safer than raw Record objects
    data = [{"ts": r["ts"], "value": r["value"]} for r in rows]
    df = pd.DataFrame(data)

    # 2. Setup Index
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df = df.set_index("ts")

    # 3. Resample
    rule = INTERVAL_MAP.get(interval, "H")
    agg = df["value"].resample(rule).agg(["mean", "min", "max", "count"])
    agg = agg.rename(columns={"mean": "avg", "count": "samples"})

    # 4. Format Output
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

@app.get("/api/v1/health/{device_id}/aggregate")
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
    # 1. Parse Dates
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    try:
        end_dt = dt_parser.isoparse(end).astimezone(datetime.timezone.utc) if end else now_utc
        start_dt = dt_parser.isoparse(start).astimezone(datetime.timezone.utc) if start else end_dt - datetime.timedelta(hours=24)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid timestamp format")

    if start_dt >= end_dt:
        raise HTTPException(status_code=400, detail="start time must be before end time")

    # 2. DB Fetch (IO-bound)
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    query = """
        SELECT ts, value FROM device_timeseries
        WHERE device_id = $1 AND metric_type = $2 AND ts >= $3 AND ts <= $4
        ORDER BY ts ASC
    """
    
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, device_id, metric_type, start_dt, end_dt)

    # 3. Process Data (CPU-bound -> Offload to thread)
    buckets = await asyncio.to_thread(_calculate_aggregates, rows, interval)

    return {
        "device_id": device_id,
        "metric_type": metric_type,
        "interval": interval,
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat(),
        "buckets": buckets,
    }

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Health Super-App Backend API v1"}


# --------- WebSocket: Real-Time Streaming ----------
@app.websocket("/ws/health/{device_id}")
async def websocket_health_stream(websocket: WebSocket, device_id: str):
    """
    Real-time WebSocket endpoint for streaming health data to frontend.
    Connect from React: new WebSocket('ws://localhost:8000/ws/health/device_123')
    """
    await websocket.accept()
    active_connections[device_id] = websocket
    logger.info(f"WebSocket connected: {device_id}")
    
    try:
        while True:
            # Keep connection alive, receive any commands from frontend
            data = await websocket.receive_text()
            logger.debug(f"Received from {device_id}: {data}")
    except WebSocketDisconnect:
        if device_id in active_connections:
            del active_connections[device_id]
        logger.info(f"WebSocket disconnected: {device_id}")


async def broadcast_to_device(device_id: str, data: dict):
    """Helper to push real-time data to connected WebSocket clients."""
    if device_id in active_connections:
        try:
            await active_connections[device_id].send_json(data)
        except Exception as e:
            logger.error(f"Failed to broadcast to {device_id}: {e}")


# --------- FHIR Export (Healthcare Interoperability) ----------
@app.get("/api/v1/health/{device_id}/fhir/observation")
async def export_fhir_observations(
    device_id: str,
    limit: int = Query(50, le=500, description="Max records to export"),
    authorized: bool = Depends(verify_device_api_key)
):
    """
    Exports health data in HL7 FHIR R4 format for EHR integration.
    Use this endpoint to share data with hospitals and medical systems.
    """
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    query = """
        SELECT metric_type, value, ts 
        FROM device_timeseries 
        WHERE device_id = $1 
        ORDER BY ts DESC 
        LIMIT $2
    """
    
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, device_id, limit)

    # LOINC codes for medical interoperability
    LOINC_CODES = {
        "hr": ("8867-4", "Heart rate", "beats/min", "/min"),
        "spo2": ("2708-6", "Oxygen saturation", "%", "%"),
        "steps": ("55423-8", "Number of steps", "steps", "{steps}"),
        "ppg": ("76536-4", "PPG waveform", "arbitrary", "1"),
    }

    fhir_bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "total": len(rows),
        "entry": []
    }

    for row in rows:
        metric = row["metric_type"]
        loinc = LOINC_CODES.get(metric, ("unknown", metric, "unit", "unit"))
        
        observation = {
            "resourceType": "Observation",
            "status": "final",
            "code": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": loinc[0],
                    "display": loinc[1]
                }]
            },
            "subject": {"reference": f"Device/{device_id}"},
            "effectiveDateTime": row["ts"].isoformat(),
            "valueQuantity": {
                "value": row["value"],
                "unit": loinc[2],
                "system": "http://unitsofmeasure.org",
                "code": loinc[3]
            }
        }
        fhir_bundle["entry"].append({"resource": observation})

    return fhir_bundle


# --------- Latest Reading (Quick Access) ----------
@app.get("/api/v1/health/{device_id}/latest")
async def get_latest_readings(
    device_id: str,
    authorized: bool = Depends(verify_device_api_key)
):
    """
    Returns the most recent reading for each metric type.
    Useful for dashboard widgets showing current status.
    """
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not initialized")

    query = """
        SELECT DISTINCT ON (metric_type) 
            metric_type, value, ts
        FROM device_timeseries 
        WHERE device_id = $1 
        ORDER BY metric_type, ts DESC
    """
    
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, device_id)

    return {
        "device_id": device_id,
        "readings": [
            {
                "metric_type": row["metric_type"],
                "value": row["value"],
                "timestamp": row["ts"].isoformat()
            }
            for row in rows
        ]
    }


# =====================================================================
# ML-POWERED HEALTH ANALYSIS ENDPOINTS
# =====================================================================

@app.post("/api/v1/health/analyze")
async def analyze_health_data(
    request: HealthAnalyzeRequest,
    authorized: bool = Depends(verify_device_api_key)
):
    """
    Analyze health data with ML prediction and chatbot explanation.
    
    This endpoint combines:
    - Rule-based threshold detection
    - ML anomaly detection (Isolation Forest)
    - Natural language explanations (Gemini/Ollama)
    
    Returns prediction, alert (if any), and natural language explanation.
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


@app.post("/api/v1/health/ask")
async def ask_health_question(
    request: HealthQuestionRequest,
    authorized: bool = Depends(verify_device_api_key)
):
    """
    Ask the health chatbot a question.
    
    Uses Gemini (or Ollama fallback) to answer health-related questions.
    Can optionally include current vitals context for personalized answers.
    """
    if not health_explainer:
        raise HTTPException(status_code=503, detail="Health analyzer not initialized")
    
    response = await health_explainer.ask_question(
        question=request.question, 
        include_vitals=request.include_vitals
    )
    
    return {"response": response}


@app.get("/api/v1/health/system/status")
async def get_system_status():
    """
    Get health analysis system status.
    
    Returns information about:
    - ML detector status
    - Chatbot availability
    - Alert statistics
    """
    if not health_explainer:
        return {"status": "not_initialized"}
    
    return health_explainer.get_status()


@app.get("/api/v1/health/alerts")
async def get_recent_alerts(
    limit: int = Query(10, le=100, description="Maximum alerts to return"),
    authorized: bool = Depends(verify_device_api_key)
):
    """
    Get recent health alerts.
    
    Returns the most recent alerts with their explanations and status.
    """
    if not health_explainer:
        raise HTTPException(status_code=503, detail="Health analyzer not initialized")
    
    alerts = health_explainer.get_recent_alerts(limit)
    return {"alerts": alerts, "count": len(alerts)}


@app.post("/api/v1/health/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    authorized: bool = Depends(verify_device_api_key)
):
    """
    Acknowledge a health alert.
    
    Marks the alert as acknowledged so it won't be shown again.
    """
    if not health_explainer:
        raise HTTPException(status_code=503, detail="Health analyzer not initialized")
    
    success = health_explainer.acknowledge_alert(alert_id)
    if success:
        return {"status": "acknowledged", "alert_id": alert_id}
    else:
        raise HTTPException(status_code=404, detail="Alert not found")