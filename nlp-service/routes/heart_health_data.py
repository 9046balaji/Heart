"""
Heart Health Data API Routes

Provides endpoints for retrieving and managing heart health data,
including vitals, alerts, and user medical profiles.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel, Field

from core.database.xampp_db import get_database, XAMPPDatabase
from medical_ai.smart_watch.feature_extractor import FeatureExtractor
from medical_ai.smart_watch.rule_engine import RuleEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/heart-health", tags=["Heart Health Data"])

# ============================================================================
# DATA MODELS
# ============================================================================

class VitalReading(BaseModel):
    metric_type: str = Field(..., description="Type of metric (heart_rate, spo2, steps)")
    value: float = Field(..., description="Value of the reading")
    unit: str = Field(..., description="Unit of measurement (bpm, %, count)")
    recorded_at: Optional[datetime] = Field(default_factory=datetime.now)
    device_id: Optional[str] = "manual"

class UserProfileUpdate(BaseModel):
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    known_conditions: Optional[List[str]] = None
    medications: Optional[List[str]] = None
    allergies: Optional[List[str]] = None

class HealthAlert(BaseModel):
    id: int
    alert_type: str
    severity: str
    message: str
    created_at: datetime
    is_resolved: bool

# ============================================================================
# DEPENDENCIES
# ============================================================================

async def get_db():
    db = await get_database()
    if not db or not db.initialized:
        raise HTTPException(status_code=503, detail="Database not available")
    return db

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/profile/{user_id}")
async def get_user_profile(user_id: str, db: XAMPPDatabase = Depends(get_db)):
    """Get user's medical profile."""
    try:
        async with db.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT user_id, name, date_of_birth, gender, blood_type,
                           weight_kg, height_cm, known_conditions, medications, allergies
                    FROM users
                    WHERE user_id = %s
                """, (user_id,))
                
                row = await cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="User not found")
                
                return {
                    "user_id": row[0],
                    "name": row[1],
                    "date_of_birth": row[2],
                    "gender": row[3],
                    "blood_type": row[4],
                    "weight_kg": float(row[5]) if row[5] else None,
                    "height_cm": float(row[6]) if row[6] else None,
                    "known_conditions": json_parse(row[7]),
                    "medications": json_parse(row[8]),
                    "allergies": json_parse(row[9])
                }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/profile/{user_id}")
async def update_user_profile(
    user_id: str, 
    update: UserProfileUpdate, 
    db: XAMPPDatabase = Depends(get_db)
):
    """Update user's medical profile."""
    try:
        import json
        
        fields = []
        values = []
        
        if update.weight_kg is not None:
            fields.append("weight_kg = %s")
            values.append(update.weight_kg)
        if update.height_cm is not None:
            fields.append("height_cm = %s")
            values.append(update.height_cm)
        if update.known_conditions is not None:
            fields.append("known_conditions = %s")
            values.append(json.dumps(update.known_conditions))
        if update.medications is not None:
            fields.append("medications = %s")
            values.append(json.dumps(update.medications))
        if update.allergies is not None:
            fields.append("allergies = %s")
            values.append(json.dumps(update.allergies))
            
        if not fields:
            return {"message": "No changes provided"}
            
        values.append(user_id)
        
        async with db.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f"""
                    UPDATE users
                    SET {', '.join(fields)}
                    WHERE user_id = %s
                """, tuple(values))
                
                if cursor.rowcount == 0:
                    raise HTTPException(status_code=404, detail="User not found")
                
                await conn.commit()
                
        return {"message": "Profile updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/vitals/{user_id}")
async def get_recent_vitals(
    user_id: str, 
    hours: int = 24, 
    limit: int = 100,
    db: XAMPPDatabase = Depends(get_db)
):

    """Get recent vitals history."""
    try:
        cutoff = datetime.now() - timedelta(hours=hours)
        
        async with db.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT metric_type, value, unit, recorded_at, device_id
                    FROM vitals
                    WHERE user_id = %s AND recorded_at >= %s
                    ORDER BY recorded_at DESC
                    LIMIT %s
                """, (user_id, cutoff, limit))
                
                rows = await cursor.fetchall()
                
                return [
                    {
                        "metric_type": row[0],
                        "value": float(row[1]),
                        "unit": row[2],
                        "recorded_at": row[3],
                        "device_id": row[4]
                    }
                    for row in rows
                ]
    except Exception as e:
        logger.error(f"Error fetching vitals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/vitals/{user_id}")
async def record_vitals(
    user_id: str, 
    readings: List[VitalReading], 
    db: XAMPPDatabase = Depends(get_db)
):
    """Record new vital readings."""
    try:
        async with db.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                for reading in readings:
                    await cursor.execute("""
                        INSERT INTO vitals (user_id, device_id, metric_type, value, unit, recorded_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        user_id, 
                        reading.device_id, 
                        reading.metric_type, 
                        reading.value, 
                        reading.unit, 
                        reading.recorded_at
                    ))
                await conn.commit()
                
        return {"message": f"Recorded {len(readings)} readings"}
    except Exception as e:
        logger.error(f"Error recording vitals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts/{user_id}")
async def get_active_alerts(
    user_id: str, 
    resolved: bool = False,
    db: XAMPPDatabase = Depends(get_db)
):
    """Get health alerts for a user."""
    try:
        async with db.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT id, alert_type, severity, message, created_at, is_resolved
                    FROM health_alerts
                    WHERE user_id = %s AND is_resolved = %s
                    ORDER BY created_at DESC
                """, (user_id, resolved))
                
                rows = await cursor.fetchall()
                
                return [
                    {
                        "id": row[0],
                        "alert_type": row[1],
                        "severity": row[2],
                        "message": row[3],
                        "created_at": row[4],
                        "is_resolved": bool(row[5])
                    }
                    for row in rows
                ]
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analysis/{user_id}")
async def analyze_current_health(user_id: str, db: XAMPPDatabase = Depends(get_db)):
    """
    Run on-demand analysis of recent vitals using the Rule Engine.
    Returns current health status and any detected anomalies.
    """
    try:
        # Fetch last 1 hour of data
        cutoff = datetime.now() - timedelta(hours=1)
        
        async with db.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT metric_type, value, recorded_at
                    FROM vitals
                    WHERE user_id = %s
                      AND metric_type IN ('heart_rate', 'spo2', 'steps')
                      AND recorded_at >= %s
                    ORDER BY recorded_at ASC
                """, (user_id, cutoff))
                
                rows = await cursor.fetchall()
                
                if not rows:
                    return {"status": "NO_DATA", "message": "No recent data available"}
                
                # Initialize FeatureExtractor
                extractor = FeatureExtractor(window_size=len(rows) + 10)
                
                # Feed data
                samples = {}
                for row in rows:
                    metric = row[0]
                    value = float(row[1])
                    ts = row[2]
                    key = ts.strftime("%Y-%m-%d %H:%M")
                    
                    if key not in samples:
                        samples[key] = {"hr": 0, "spo2": 98, "steps": 0}
                    
                    if metric == 'heart_rate':
                        samples[key]["hr"] = value
                    elif metric == 'spo2':
                        samples[key]["spo2"] = value
                    elif metric == 'steps':
                        samples[key]["steps"] = int(value)
                
                for key in sorted(samples.keys()):
                    s = samples[key]
                    if s["hr"] > 0:
                        extractor.add_sample(hr=s["hr"], spo2=s["spo2"], steps=s["steps"])
                
                # Extract features
                features = extractor.extract_features()
                
                if not features:
                    return {"status": "INSUFFICIENT_DATA", "message": "Need more data points for analysis"}
                
                # Run Rule Engine
                rule_engine = RuleEngine() # Could fetch user profile here for personalization
                anomalies = rule_engine.analyze(features)
                status = rule_engine.get_overall_status(anomalies)
                
                return {
                    "timestamp": datetime.utcnow(),
                    "status": status,
                    "features": {
                        "hr_current": features.hr_current,
                        "hr_mean_5min": features.hr_mean_5min,
                        "spo2_current": features.spo2_current,
                        "is_resting": features.is_resting
                    },
                    "anomalies": [
                        {
                            "type": a.anomaly_type.value,
                            "message": a.message,
                            "severity": a.severity.name,
                            "recommendation": a.recommendation
                        } for a in anomalies
                    ]
                }
                
    except Exception as e:
        logger.error(f"Error running analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def json_parse(value):
    """Helper to parse JSON fields safely."""
    if not value:
        return None
    if isinstance(value, str):
        try:
            import json
            return json.loads(value)
        except:
            return value
    return value
