"""
Longitudinal Patient Timeline Service.

Aggregates all patient health events into a chronological timeline.

From medical.md Section 5:
"Once structured, the data can feed: Longitudinal patient history"
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class TimelineEventType(Enum):
    """Types of events in patient timeline."""
    # Document events
    LAB_RESULT = "lab_result"
    PRESCRIPTION = "prescription"
    DISCHARGE = "discharge"
    MEDICAL_BILL = "medical_bill"
    DOCUMENT_UPLOADED = "document_uploaded"
    
    # Health events
    VITAL_READING = "vital_reading"
    SYMPTOM = "symptom"
    ALERT = "alert"
    
    # Activity events
    MEDICATION_TAKEN = "medication_taken"
    MEDICATION_MISSED = "medication_missed"
    EXERCISE = "exercise"
    MEAL_LOGGED = "meal_logged"
    
    # Clinical events
    APPOINTMENT = "appointment"
    CONSULTATION = "consultation"
    PROCEDURE = "procedure"
    
    # AI events
    PREDICTION_RUN = "prediction_run"
    AI_EXTRACTION = "ai_extraction"
    SUMMARY_GENERATED = "summary_generated"


class EventImportance(Enum):
    """Importance levels for timeline events."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TimelineEvent:
    """A single event in the patient timeline."""
    id: str
    event_type: TimelineEventType
    timestamp: datetime
    title: str
    description: str
    source: str  # "document", "manual", "smartwatch", "prediction", "system"
    source_id: Optional[str] = None  # Reference to source document/record
    data: Dict[str, Any] = field(default_factory=dict)
    importance: EventImportance = EventImportance.NORMAL
    verified: bool = False
    tags: List[str] = field(default_factory=list)


@dataclass
class TimelinePeriod:
    """A period of time in the timeline with aggregated data."""
    start_date: date
    end_date: date
    events: List[TimelineEvent]
    event_count: int
    summary: Dict[str, Any]


@dataclass
class TimelineSummary:
    """Summary statistics for a timeline."""
    total_events: int
    events_by_type: Dict[str, int]
    date_range: Dict[str, Optional[date]]
    critical_events: int
    unverified_events: int
    sources: List[str]


class PatientTimelineService:
    """
    Builds and manages longitudinal patient history.
    
    Aggregates data from:
    - Scanned medical documents
    - Manual entries
    - Smartwatch/device data
    - Medication logs
    - Exercise records
    - Predictions and alerts
    """
    
    def __init__(
        self, 
        db_session=None,
        audit_service=None
    ):
        """
        Initialize timeline service.
        
        Args:
            db_session: Database session for persistence
            audit_service: Audit service for logging
        """
        self.db_session = db_session
        self.audit_service = audit_service
        
        # In-memory storage (replace with DB in production)
        self._timelines: Dict[str, List[TimelineEvent]] = {}
        
        logger.info("PatientTimelineService initialized")
    
    def add_document_events(
        self,
        user_id: str,
        document_id: str,
        document_type: str,
        extracted_data: Dict[str, Any],
        document_date: Optional[datetime] = None
    ) -> List[TimelineEvent]:
        """
        Add events from a processed document to the timeline.
        
        Args:
            user_id: User ID
            document_id: Source document ID
            document_type: Type of document
            extracted_data: Data extracted from document
            document_date: Date of the document (if known)
        
        Returns:
            List of created timeline events
        """
        events = []
        event_date = document_date or datetime.utcnow()
        
        # Create main document event
        doc_event = TimelineEvent(
            id=str(uuid.uuid4()),
            event_type=TimelineEventType.DOCUMENT_UPLOADED,
            timestamp=datetime.utcnow(),
            title=f"{document_type.replace('_', ' ').title()} Uploaded",
            description=f"Medical document processed and added to record",
            source="document",
            source_id=document_id,
            data={"document_type": document_type},
            importance=EventImportance.NORMAL,
            tags=["document", document_type]
        )
        events.append(doc_event)
        
        # Create specific events based on document type
        if document_type == "lab_report":
            events.extend(self._create_lab_events(
                user_id, document_id, extracted_data, event_date
            ))
        elif document_type == "prescription":
            events.extend(self._create_prescription_events(
                user_id, document_id, extracted_data, event_date
            ))
        elif document_type == "discharge_summary":
            events.extend(self._create_discharge_events(
                user_id, document_id, extracted_data, event_date
            ))
        
        # Store events
        if user_id not in self._timelines:
            self._timelines[user_id] = []
        self._timelines[user_id].extend(events)
        
        logger.info(f"Added {len(events)} timeline events for user {user_id}")
        return events
    
    def _create_lab_events(
        self,
        user_id: str,
        document_id: str,
        extracted_data: Dict[str, Any],
        event_date: datetime
    ) -> List[TimelineEvent]:
        """Create timeline events from lab report."""
        events = []
        
        # Main lab result event
        lab_event = TimelineEvent(
            id=str(uuid.uuid4()),
            event_type=TimelineEventType.LAB_RESULT,
            timestamp=event_date,
            title="Lab Results Received",
            description=extracted_data.get("test_panel", "Laboratory tests completed"),
            source="document",
            source_id=document_id,
            importance=EventImportance.HIGH,
            tags=["lab", "results"]
        )
        
        # Add test results as data
        test_results = extracted_data.get("test_results", [])
        lab_event.data = {
            "test_count": len(test_results),
            "results_summary": []
        }
        
        # Check for abnormal results
        abnormal_count = 0
        for test in test_results:
            is_abnormal = self._check_abnormal(test)
            if is_abnormal:
                abnormal_count += 1
            lab_event.data["results_summary"].append({
                "name": test.get("test_name"),
                "value": test.get("value"),
                "unit": test.get("unit"),
                "abnormal": is_abnormal
            })
        
        if abnormal_count > 0:
            lab_event.importance = EventImportance.CRITICAL
            lab_event.description = f"Lab results with {abnormal_count} abnormal value(s)"
            lab_event.tags.append("abnormal")
        
        events.append(lab_event)
        return events
    
    def _create_prescription_events(
        self,
        user_id: str,
        document_id: str,
        extracted_data: Dict[str, Any],
        event_date: datetime
    ) -> List[TimelineEvent]:
        """Create timeline events from prescription."""
        events = []
        
        medications = extracted_data.get("medications", [])
        
        for med in medications:
            med_event = TimelineEvent(
                id=str(uuid.uuid4()),
                event_type=TimelineEventType.PRESCRIPTION,
                timestamp=event_date,
                title=f"New Prescription: {med.get('name', 'Unknown')}",
                description=(
                    f"{med.get('dosage', '')} - {med.get('frequency', '')} "
                    f"for {med.get('duration', 'as directed')}"
                ),
                source="document",
                source_id=document_id,
                data={
                    "medication_name": med.get("name"),
                    "dosage": med.get("dosage"),
                    "frequency": med.get("frequency"),
                    "duration": med.get("duration"),
                    "prescriber": extracted_data.get("prescriber_name")
                },
                importance=EventImportance.HIGH,
                tags=["prescription", "medication"]
            )
            events.append(med_event)
        
        return events
    
    def _create_discharge_events(
        self,
        user_id: str,
        document_id: str,
        extracted_data: Dict[str, Any],
        event_date: datetime
    ) -> List[TimelineEvent]:
        """Create timeline events from discharge summary."""
        events = []
        
        discharge_event = TimelineEvent(
            id=str(uuid.uuid4()),
            event_type=TimelineEventType.DISCHARGE,
            timestamp=event_date,
            title="Hospital Discharge",
            description=extracted_data.get("discharge_diagnosis", "Discharged from hospital"),
            source="document",
            source_id=document_id,
            data={
                "admission_date": extracted_data.get("admission_date"),
                "discharge_date": extracted_data.get("discharge_date"),
                "diagnosis": extracted_data.get("discharge_diagnosis"),
                "procedures": extracted_data.get("procedures", []),
                "follow_up": extracted_data.get("follow_up_instructions")
            },
            importance=EventImportance.CRITICAL,
            tags=["discharge", "hospital", "inpatient"]
        )
        events.append(discharge_event)
        
        return events
    
    def add_vital_reading(
        self,
        user_id: str,
        vital_type: str,
        value: float,
        unit: str,
        timestamp: Optional[datetime] = None,
        source: str = "smartwatch"
    ) -> TimelineEvent:
        """
        Add a vital reading to the timeline.
        
        Args:
            user_id: User ID
            vital_type: Type of vital (heart_rate, blood_pressure, etc.)
            value: Vital value
            unit: Unit of measurement
            timestamp: When the reading was taken
            source: Source of the reading
        
        Returns:
            Created timeline event
        """
        event = TimelineEvent(
            id=str(uuid.uuid4()),
            event_type=TimelineEventType.VITAL_READING,
            timestamp=timestamp or datetime.utcnow(),
            title=f"{vital_type.replace('_', ' ').title()} Reading",
            description=f"{value} {unit}",
            source=source,
            data={
                "vital_type": vital_type,
                "value": value,
                "unit": unit
            },
            importance=self._assess_vital_importance(vital_type, value),
            tags=["vital", vital_type]
        )
        
        if user_id not in self._timelines:
            self._timelines[user_id] = []
        self._timelines[user_id].append(event)
        
        return event
    
    def add_prediction_event(
        self,
        user_id: str,
        risk_score: float,
        risk_category: str,
        document_id: Optional[str],
        features_used: List[str]
    ) -> TimelineEvent:
        """
        Add a prediction run to the timeline.
        
        Args:
            user_id: User ID
            risk_score: Prediction risk score
            risk_category: Risk category (low, moderate, high, etc.)
            document_id: Source document if applicable
            features_used: Features used in prediction
        
        Returns:
            Created timeline event
        """
        importance = EventImportance.NORMAL
        if risk_category in ["high", "very_high"]:
            importance = EventImportance.CRITICAL
        elif risk_category == "moderate":
            importance = EventImportance.HIGH
        
        event = TimelineEvent(
            id=str(uuid.uuid4()),
            event_type=TimelineEventType.PREDICTION_RUN,
            timestamp=datetime.utcnow(),
            title="Heart Disease Risk Assessment",
            description=f"Risk Score: {risk_score:.1%} ({risk_category.replace('_', ' ').title()})",
            source="prediction",
            source_id=document_id,
            data={
                "risk_score": risk_score,
                "risk_category": risk_category,
                "features_used": features_used,
                "feature_count": len(features_used)
            },
            importance=importance,
            tags=["prediction", "risk", risk_category]
        )
        
        if user_id not in self._timelines:
            self._timelines[user_id] = []
        self._timelines[user_id].append(event)
        
        return event
    
    def get_timeline(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[TimelineEventType]] = None,
        importance: Optional[List[EventImportance]] = None,
        limit: int = 100
    ) -> List[TimelineEvent]:
        """
        Get timeline events for a user.
        
        Args:
            user_id: User ID
            start_date: Filter events after this date
            end_date: Filter events before this date
            event_types: Filter by event types
            importance: Filter by importance levels
            limit: Maximum events to return
        
        Returns:
            List of timeline events, sorted by timestamp (newest first)
        """
        events = self._timelines.get(user_id, [])
        
        # Apply filters
        if start_date:
            events = [e for e in events if e.timestamp >= start_date]
        if end_date:
            events = [e for e in events if e.timestamp <= end_date]
        if event_types:
            events = [e for e in events if e.event_type in event_types]
        if importance:
            events = [e for e in events if e.importance in importance]
        
        # Sort by timestamp (newest first)
        events = sorted(events, key=lambda e: e.timestamp, reverse=True)
        
        return events[:limit]
    
    def get_timeline_summary(
        self,
        user_id: str,
        days: int = 7
    ) -> TimelineSummary:
        """
        Get summary statistics for a user's timeline.
        
        Args:
            user_id: User ID
            days: Number of days to summarize
        
        Returns:
            Timeline summary statistics
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        events = self.get_timeline(user_id, start_date=cutoff, limit=1000)
        
        # Count by type
        events_by_type: Dict[str, int] = {}
        sources = set()
        critical_count = 0
        unverified_count = 0
        
        for event in events:
            type_name = event.event_type.value
            events_by_type[type_name] = events_by_type.get(type_name, 0) + 1
            sources.add(event.source)
            
            if event.importance == EventImportance.CRITICAL:
                critical_count += 1
            if not event.verified:
                unverified_count += 1
        
        # Get date range
        dates = [e.timestamp.date() for e in events]
        
        return TimelineSummary(
            total_events=len(events),
            events_by_type=events_by_type,
            date_range={
                "start": min(dates) if dates else None,
                "end": max(dates) if dates else None
            },
            critical_events=critical_count,
            unverified_events=unverified_count,
            sources=list(sources)
        )
    
    def get_recent_critical_events(
        self,
        user_id: str,
        days: int = 30,
        limit: int = 10
    ) -> List[TimelineEvent]:
        """Get recent critical/high importance events."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        return self.get_timeline(
            user_id,
            start_date=cutoff,
            importance=[EventImportance.CRITICAL, EventImportance.HIGH],
            limit=limit
        )
    
    def _check_abnormal(self, test: Dict[str, Any]) -> bool:
        """Check if a test result is outside reference range."""
        reference_range = test.get("reference_range", "")
        value = test.get("value")
        
        if not reference_range or value is None:
            return False
        
        try:
            value_num = float(value)
            
            # Parse reference range (e.g., "70-100", "<200", ">40")
            if "-" in reference_range:
                parts = reference_range.replace(" ", "").split("-")
                low = float(parts[0])
                high = float(parts[1])
                return value_num < low or value_num > high
            elif reference_range.startswith("<"):
                limit = float(reference_range[1:].strip())
                return value_num >= limit
            elif reference_range.startswith(">"):
                limit = float(reference_range[1:].strip())
                return value_num <= limit
        except (ValueError, IndexError):
            pass
        
        return False
    
    def _assess_vital_importance(self, vital_type: str, value: float) -> EventImportance:
        """Assess importance of a vital reading."""
        # Define critical thresholds
        thresholds = {
            "heart_rate": {"low": 50, "high": 120, "critical_low": 40, "critical_high": 150},
            "blood_pressure_systolic": {"low": 90, "high": 140, "critical_low": 80, "critical_high": 180},
            "blood_pressure_diastolic": {"low": 60, "high": 90, "critical_low": 50, "critical_high": 120},
            "oxygen_saturation": {"low": 95, "critical_low": 90},
            "temperature": {"low": 36.1, "high": 37.8, "critical_low": 35, "critical_high": 39.5}
        }
        
        vital_type_lower = vital_type.lower().replace(" ", "_")
        
        if vital_type_lower in thresholds:
            limits = thresholds[vital_type_lower]
            
            if value <= limits.get("critical_low", float("-inf")) or \
               value >= limits.get("critical_high", float("inf")):
                return EventImportance.CRITICAL
            elif value < limits.get("low", float("-inf")) or \
                 value > limits.get("high", float("inf")):
                return EventImportance.HIGH
        
        return EventImportance.NORMAL


# Global instance
_timeline_service: Optional[PatientTimelineService] = None


def get_timeline_service() -> PatientTimelineService:
    """Get or create the global timeline service instance."""
    global _timeline_service
    if _timeline_service is None:
        _timeline_service = PatientTimelineService()
    return _timeline_service
