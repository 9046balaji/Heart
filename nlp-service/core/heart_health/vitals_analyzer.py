# nlp-service/core/heart_health/vitals_analyzer.py

from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class VitalsAnalyzer:
    """
    Analyzes heart health vitals (BPM, SPO2) for anomalies and trends.
    """
    
    def __init__(self):
        self.thresholds = {
            "heart_rate": {"min": 50, "max": 100},  # Standard resting range
            "spo2": {"min": 95, "max": 100}         # Standard oxygen range
        }
    
    def analyze_readings(self, readings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyzes a list of vital readings.
        """
        if not readings:
            return {"status": "no_data", "anomalies": []}
            
        anomalies = []
        
        for reading in readings:
            metric = reading.get("metric_type")
            value = reading.get("value")
            
            if metric == "heart_rate":
                if value > self.thresholds["heart_rate"]["max"]:
                    anomalies.append(f"High Heart Rate: {value} BPM")
                elif value < self.thresholds["heart_rate"]["min"]:
                    anomalies.append(f"Low Heart Rate: {value} BPM")
                    
            elif metric == "spo2":
                if value < self.thresholds["spo2"]["min"]:
                    anomalies.append(f"Low Oxygen Saturation: {value}%")
        
        return {
            "status": "analyzed",
            "count": len(readings),
            "anomalies": anomalies,
            "has_concerns": len(anomalies) > 0
        }
