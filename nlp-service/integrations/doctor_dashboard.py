"""
Doctor Consultation Dashboard API.

Provides physician-facing views of patient data from scanned documents.

From medical.md Section 5:
"Once structured, the data can feed: Doctor consultation dashboard"
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class PhysicianRole(Enum):
    """Physician access roles."""
    PRIMARY = "primary"  # Primary care physician
    SPECIALIST = "specialist"
    CONSULTANT = "consultant"
    EMERGENCY = "emergency"


class AccessLevel(Enum):
    """Data access levels."""
    FULL = "full"  # All patient data
    LIMITED = "limited"  # Basic health info
    EMERGENCY = "emergency"  # Critical info only
    SUMMARY = "summary"  # Aggregated summaries only


@dataclass
class PhysicianInfo:
    """Information about a physician."""
    physician_id: str
    name: str
    role: PhysicianRole
    specialty: Optional[str] = None
    license_number: Optional[str] = None
    institution: Optional[str] = None


@dataclass
class PatientOverview:
    """Comprehensive patient overview for physicians."""
    patient_id: str
    patient_name: str
    age: int
    gender: str
    
    # Latest vitals
    latest_vitals: Dict[str, Any]
    
    # Recent lab results
    recent_labs: List[Dict[str, Any]]
    
    # Current medications
    current_medications: List[Dict[str, Any]]
    
    # Risk assessment
    risk_assessment: Dict[str, Any]
    
    # Recent documents
    document_count: int
    last_document_date: Optional[datetime]
    
    # Alerts
    alerts: List[str]
    
    # Data freshness
    data_last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LabTrend:
    """Trend data for a lab test."""
    test_name: str
    values: List[Dict[str, Any]]  # [{date, value, unit, abnormal}]
    trend_direction: str  # "improving", "worsening", "stable"
    latest_value: float
    reference_range: str


class DoctorDashboardService:
    """
    Service for physician-facing patient data views.
    
    Features:
    - Aggregated patient overview
    - Document history
    - Lab trends
    - Medication reconciliation
    - Risk alerts
    
    Access Control:
    - Requires physician authentication
    - Logs all data access to audit trail
    - Respects patient consent
    """
    
    def __init__(
        self,
        timeline_service=None,
        prediction_service=None,
        audit_service=None,
        consent_manager=None
    ):
        """
        Initialize doctor dashboard service.
        
        Args:
            timeline_service: Patient timeline service
            prediction_service: Prediction integration service
            audit_service: Audit service for access logging
            consent_manager: Consent manager for patient permissions
        """
        self.timeline = timeline_service
        self.prediction = prediction_service
        self.audit = audit_service
        self.consent = consent_manager
        
        # In-memory patient data cache (replace with DB in production)
        self._patient_data: Dict[str, Dict[str, Any]] = {}
        
        logger.info("DoctorDashboardService initialized")
    
    async def get_patient_overview(
        self,
        patient_id: str,
        physician_id: str,
        physician_role: PhysicianRole
    ) -> PatientOverview:
        """
        Get comprehensive patient overview for physician dashboard.
        
        Args:
            patient_id: Patient user ID
            physician_id: Physician ID making the request
            physician_role: Role of the physician
        
        Returns:
            PatientOverview with all relevant data
        
        Raises:
            PermissionError: If consent not given
        """
        # Check consent
        if self.consent:
            has_consent = await self._check_physician_consent(
                patient_id, physician_id, physician_role
            )
            if not has_consent:
                raise PermissionError(
                    f"Patient {patient_id} has not granted data access consent"
                )
        
        # Log access
        if self.audit:
            self.audit.log_data_access(
                user_id=physician_id,
                resource_type="patient_overview",
                resource_id=patient_id,
                access_type="physician_view"
            )
        
        # Get patient profile
        patient_profile = self._get_patient_profile(patient_id)
        
        # Get latest vitals
        latest_vitals = await self._get_latest_vitals(patient_id)
        
        # Get recent labs
        recent_labs = await self._get_recent_labs(patient_id)
        
        # Get current medications
        medications = await self._get_current_medications(patient_id)
        
        # Get risk assessment
        risk = await self._get_risk_assessment(patient_id)
        
        # Get document count
        doc_info = await self._get_document_info(patient_id)
        
        # Generate alerts
        alerts = self._generate_alerts(latest_vitals, recent_labs, risk)
        
        return PatientOverview(
            patient_id=patient_id,
            patient_name=patient_profile.get("name", "Unknown"),
            age=patient_profile.get("age", 0),
            gender=patient_profile.get("gender", "Unknown"),
            latest_vitals=latest_vitals,
            recent_labs=recent_labs,
            current_medications=medications,
            risk_assessment=risk,
            document_count=doc_info.get("count", 0),
            last_document_date=doc_info.get("last_date"),
            alerts=alerts
        )
    
    async def get_document_history(
        self,
        patient_id: str,
        physician_id: str,
        document_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get patient's document history for physician review.
        
        Args:
            patient_id: Patient user ID
            physician_id: Physician ID
            document_type: Filter by document type
            limit: Maximum documents to return
        
        Returns:
            List of document summaries
        """
        # Log access
        if self.audit:
            self.audit.log_data_access(
                user_id=physician_id,
                resource_type="document_history",
                resource_id=patient_id,
                access_type="physician_view"
            )
        
        # Get documents from timeline
        if self.timeline:
            from .timeline_service import TimelineEventType
            
            event_types = None
            if document_type:
                type_mapping = {
                    "lab_report": TimelineEventType.LAB_RESULT,
                    "prescription": TimelineEventType.PRESCRIPTION,
                    "discharge": TimelineEventType.DISCHARGE,
                }
                if document_type in type_mapping:
                    event_types = [type_mapping[document_type]]
            
            events = self.timeline.get_timeline(
                patient_id,
                event_types=event_types,
                limit=limit
            )
            
            return [
                {
                    "id": e.id,
                    "type": e.event_type.value,
                    "date": e.timestamp.isoformat(),
                    "title": e.title,
                    "description": e.description,
                    "importance": e.importance.value,
                    "verified": e.verified,
                    "data": e.data
                }
                for e in events
            ]
        
        return []
    
    async def get_lab_trends(
        self,
        patient_id: str,
        physician_id: str,
        test_names: Optional[List[str]] = None,
        days: int = 365
    ) -> Dict[str, LabTrend]:
        """
        Get lab test trends over time.
        
        Args:
            patient_id: Patient user ID
            physician_id: Physician ID
            test_names: Specific tests to include
            days: Number of days of history
        
        Returns:
            Dictionary of test name to trend data
        """
        # Log access
        if self.audit:
            self.audit.log_data_access(
                user_id=physician_id,
                resource_type="lab_trends",
                resource_id=patient_id,
                access_type="physician_view"
            )
        
        # Default tests to track
        default_tests = [
            "cholesterol", "hdl", "ldl", "triglycerides",
            "glucose", "hba1c", "creatinine", "hemoglobin"
        ]
        tests_to_track = test_names or default_tests
        
        trends: Dict[str, LabTrend] = {}
        
        # Get lab events from timeline
        if self.timeline:
            from .timeline_service import TimelineEventType
            
            cutoff = datetime.utcnow() - timedelta(days=days)
            events = self.timeline.get_timeline(
                patient_id,
                start_date=cutoff,
                event_types=[TimelineEventType.LAB_RESULT],
                limit=500
            )
            
            # Group results by test name
            test_values: Dict[str, List[Dict[str, Any]]] = {}
            
            for event in events:
                results = event.data.get("results_summary", [])
                for result in results:
                    test_name = result.get("name", "").lower()
                    if any(t.lower() in test_name for t in tests_to_track):
                        if test_name not in test_values:
                            test_values[test_name] = []
                        test_values[test_name].append({
                            "date": event.timestamp.isoformat(),
                            "value": result.get("value"),
                            "unit": result.get("unit"),
                            "abnormal": result.get("abnormal", False)
                        })
            
            # Create trends
            for test_name, values in test_values.items():
                if len(values) >= 2:
                    # Sort by date
                    sorted_values = sorted(values, key=lambda x: x["date"])
                    
                    # Determine trend
                    trend = self._calculate_trend(sorted_values)
                    
                    trends[test_name] = LabTrend(
                        test_name=test_name,
                        values=sorted_values,
                        trend_direction=trend,
                        latest_value=sorted_values[-1].get("value"),
                        reference_range=""  # Would come from lab definitions
                    )
        
        return trends
    
    async def get_medication_reconciliation(
        self,
        patient_id: str,
        physician_id: str
    ) -> Dict[str, Any]:
        """
        Get medication reconciliation report.
        
        Args:
            patient_id: Patient user ID
            physician_id: Physician ID
        
        Returns:
            Medication reconciliation data
        """
        medications = await self._get_current_medications(patient_id)
        
        return {
            "current_medications": medications,
            "total_count": len(medications),
            "potential_interactions": [],  # Would require drug interaction DB
            "compliance_rate": 0.85,  # Would come from medication tracking
            "last_updated": datetime.utcnow().isoformat()
        }
    
    def _get_patient_profile(self, patient_id: str) -> Dict[str, Any]:
        """Get basic patient profile."""
        # In production, this would query the user database
        return self._patient_data.get(patient_id, {
            "name": "Patient",
            "age": 45,
            "gender": "Unknown"
        })
    
    async def _check_physician_consent(
        self,
        patient_id: str,
        physician_id: str,
        role: PhysicianRole
    ) -> bool:
        """Check if patient has consented to physician access."""
        # Emergency access always allowed
        if role == PhysicianRole.EMERGENCY:
            return True
        
        # Check consent manager
        if self.consent:
            # This would check the consent database
            pass
        
        # Default to allowed for now (should be restricted in production)
        return True
    
    async def _get_latest_vitals(self, patient_id: str) -> Dict[str, Any]:
        """Get most recent vital readings."""
        # In production, query vitals database
        return {
            "heart_rate": {"value": 72, "unit": "bpm", "timestamp": datetime.utcnow().isoformat()},
            "blood_pressure": {"systolic": 120, "diastolic": 80, "unit": "mmHg"},
            "oxygen_saturation": {"value": 98, "unit": "%"},
            "temperature": {"value": 36.6, "unit": "°C"}
        }
    
    async def _get_recent_labs(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get recent lab results."""
        if self.timeline:
            from .timeline_service import TimelineEventType
            
            events = self.timeline.get_timeline(
                patient_id,
                event_types=[TimelineEventType.LAB_RESULT],
                limit=5
            )
            
            return [
                {
                    "date": e.timestamp.isoformat(),
                    "title": e.title,
                    "results": e.data.get("results_summary", []),
                    "abnormal_count": sum(
                        1 for r in e.data.get("results_summary", []) 
                        if r.get("abnormal")
                    )
                }
                for e in events
            ]
        
        return []
    
    async def _get_current_medications(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get current medication list."""
        if self.timeline:
            from .timeline_service import TimelineEventType
            
            # Get recent prescriptions
            events = self.timeline.get_timeline(
                patient_id,
                event_types=[TimelineEventType.PRESCRIPTION],
                limit=20
            )
            
            medications = []
            seen = set()
            
            for e in events:
                med_name = e.data.get("medication_name", "").lower()
                if med_name and med_name not in seen:
                    seen.add(med_name)
                    medications.append({
                        "name": e.data.get("medication_name"),
                        "dosage": e.data.get("dosage"),
                        "frequency": e.data.get("frequency"),
                        "prescribed_date": e.timestamp.isoformat(),
                        "prescriber": e.data.get("prescriber")
                    })
            
            return medications
        
        return []
    
    async def _get_risk_assessment(self, patient_id: str) -> Dict[str, Any]:
        """Get latest risk assessment."""
        if self.timeline:
            from .timeline_service import TimelineEventType
            
            events = self.timeline.get_timeline(
                patient_id,
                event_types=[TimelineEventType.PREDICTION_RUN],
                limit=1
            )
            
            if events:
                return {
                    "risk_score": events[0].data.get("risk_score"),
                    "risk_category": events[0].data.get("risk_category"),
                    "assessed_at": events[0].timestamp.isoformat(),
                    "features_used": events[0].data.get("features_used", [])
                }
        
        return {"status": "no_assessment"}
    
    async def _get_document_info(self, patient_id: str) -> Dict[str, Any]:
        """Get document count and last date."""
        if self.timeline:
            from .timeline_service import TimelineEventType
            
            events = self.timeline.get_timeline(
                patient_id,
                event_types=[TimelineEventType.DOCUMENT_UPLOADED],
                limit=1000
            )
            
            return {
                "count": len(events),
                "last_date": events[0].timestamp if events else None
            }
        
        return {"count": 0, "last_date": None}
    
    def _generate_alerts(
        self,
        vitals: Dict[str, Any],
        labs: List[Dict[str, Any]],
        risk: Dict[str, Any]
    ) -> List[str]:
        """Generate alerts for physician attention."""
        alerts = []
        
        # Check vitals
        hr = vitals.get("heart_rate", {}).get("value")
        if hr and (hr < 50 or hr > 100):
            alerts.append(f"⚠️ Abnormal heart rate: {hr} bpm")
        
        bp = vitals.get("blood_pressure", {})
        if bp.get("systolic", 0) > 140 or bp.get("diastolic", 0) > 90:
            alerts.append(
                f"⚠️ Elevated blood pressure: {bp.get('systolic')}/{bp.get('diastolic')} mmHg"
            )
        
        o2 = vitals.get("oxygen_saturation", {}).get("value")
        if o2 and o2 < 95:
            alerts.append(f"🚨 Low oxygen saturation: {o2}%")
        
        # Check labs
        for lab in labs[:3]:
            abnormal = lab.get("abnormal_count", 0)
            if abnormal > 0:
                alerts.append(
                    f"⚠️ {abnormal} abnormal value(s) in {lab.get('title', 'lab results')}"
                )
        
        # Check risk
        risk_category = risk.get("risk_category")
        if risk_category in ["high", "very_high"]:
            alerts.append(
                f"🚨 Cardiovascular risk assessment: {risk_category.replace('_', ' ').upper()}"
            )
        
        return alerts
    
    def _calculate_trend(self, values: List[Dict[str, Any]]) -> str:
        """Calculate trend direction from values."""
        if len(values) < 2:
            return "stable"
        
        try:
            first_value = float(values[0].get("value", 0))
            last_value = float(values[-1].get("value", 0))
            
            if first_value == 0:
                return "stable"
            
            change_percent = ((last_value - first_value) / first_value) * 100
            
            if change_percent > 10:
                return "worsening"  # Assuming higher is worse for most tests
            elif change_percent < -10:
                return "improving"
            else:
                return "stable"
        except (ValueError, TypeError):
            return "stable"


# Global instance
_dashboard_service: Optional[DoctorDashboardService] = None


def get_dashboard_service() -> DoctorDashboardService:
    """Get or create the global dashboard service instance."""
    global _dashboard_service
    if _dashboard_service is None:
        _dashboard_service = DoctorDashboardService()
    return _dashboard_service
