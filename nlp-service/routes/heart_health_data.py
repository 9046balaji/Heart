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
        row = await db.execute_query(
            """
                SELECT user_id, name, date_of_birth, gender, blood_type,
                       weight_kg, height_cm, known_conditions, medications, allergies
                FROM users
                WHERE user_id = %s
            """,
            (user_id,),
            operation="read",
            fetch_one=True
        )
        
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "user_id": row["user_id"],
            "name": row["name"],
            "date_of_birth": row["date_of_birth"],
            "gender": row["gender"],
            "blood_type": row["blood_type"],
            "weight_kg": float(row["weight_kg"]) if row["weight_kg"] else None,
            "height_cm": float(row["height_cm"]) if row["height_cm"] else None,
            "known_conditions": json_parse(row["known_conditions"]),
            "medications": json_parse(row["medications"]),
            "allergies": json_parse(row["allergies"])
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
        
        result = await db.execute_query(f"""
            UPDATE users
            SET {', '.join(fields)}
            WHERE user_id = %s
        """, tuple(values), operation="write")
        
        if result == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
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
        
        rows = await db.execute_query(
            """
                SELECT metric_type, value, unit, recorded_at, device_id
                FROM vitals
                WHERE user_id = %s AND recorded_at >= %s
                ORDER BY recorded_at DESC
                LIMIT %s
            """,
            (user_id, cutoff, limit),
            operation="read",
            fetch_all=True
        )
        
        return [
            {
                "metric_type": row["metric_type"],
                "value": float(row["value"]),
                "unit": row["unit"],
                "recorded_at": row["recorded_at"],
                "device_id": row["device_id"]
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
        for reading in readings:
            await db.execute_query(
                """
                    INSERT INTO vitals (user_id, device_id, metric_type, value, unit, recorded_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id, 
                    reading.device_id, 
                    reading.metric_type, 
                    reading.value, 
                    reading.unit, 
                    reading.recorded_at
                ),
                operation="write"
            )
            
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
        rows = await db.execute_query(
            """
                SELECT id, alert_type, severity, message, created_at, is_resolved
                FROM health_alerts
                WHERE user_id = %s AND is_resolved = %s
                ORDER BY created_at DESC
            """,
            (user_id, resolved),
            operation="read",
            fetch_all=True
        )
        
        return [
            {
                "id": row["id"],
                "alert_type": row["alert_type"],
                "severity": row["severity"],
                "message": row["message"],
                "created_at": row["created_at"],
                "is_resolved": bool(row["is_resolved"])
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
        
        rows = await db.execute_query(
            """
                SELECT metric_type, value, recorded_at
                FROM vitals
                WHERE user_id = %s
                  AND metric_type IN ('heart_rate', 'spo2', 'steps')
                  AND recorded_at >= %s
                ORDER BY recorded_at ASC
            """,
            (user_id, cutoff),
            operation="read",
            fetch_all=True
        )
        
        if not rows:
            return {"status": "NO_DATA", "message": "No recent data available"}
        
        # Initialize FeatureExtractor
        extractor = FeatureExtractor(window_size=len(rows) + 10)
        
        # Feed data
        samples = {}
        for row in rows:
            metric = row["metric_type"]
            value = float(row["value"])
            ts = row["recorded_at"]
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
