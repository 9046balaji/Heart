"""
Weekly Data Aggregation Service.

Aggregates health data from all sources for weekly summary.
As specified in medical.md Section 3.

Data Categories:
A. Health stats - Heart rate, steps, sleep, alerts
B. Food & calories - Daily calories, nutrition compliance
C. Medications - Name, dosage, taken/missed, compliance %
D. Exercise - Workouts, active minutes, goal %
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import mean, stdev
from enum import Enum

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    """Direction of health metric trends."""
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


@dataclass
class WeeklyHealthStats:
    """Aggregated health stats for the week (Category A)."""
    # Heart & Vitals
    avg_heart_rate: Optional[float] = None
    min_heart_rate: Optional[int] = None
    max_heart_rate: Optional[int] = None
    resting_heart_rate: Optional[int] = None
    resting_hr_trend: TrendDirection = TrendDirection.STABLE
    
    # Blood Pressure
    avg_systolic: Optional[int] = None
    avg_diastolic: Optional[int] = None
    bp_readings_count: int = 0
    
    # Activity
    total_steps: int = 0
    avg_steps_per_day: float = 0.0
    steps_goal_met_days: int = 0
    steps_trend_percent: float = 0.0  # vs previous week
    
    # Sleep (if available)
    avg_sleep_hours: Optional[float] = None
    sleep_quality_score: Optional[float] = None
    
    # Alerts
    high_hr_alerts: int = 0
    low_hr_alerts: int = 0
    irregular_rhythm_alerts: int = 0
    low_activity_alerts: int = 0
    abnormal_lab_alerts: int = 0


@dataclass
class WeeklyNutritionStats:
    """Aggregated nutrition stats for the week (Category B)."""
    avg_daily_calories: float = 0.0
    calorie_goal: int = 2000
    days_target_met: int = 0
    total_days: int = 7
    
    # Macros
    avg_protein_g: float = 0.0
    avg_carbs_g: float = 0.0
    avg_fat_g: float = 0.0
    
    # Foods
    top_foods: List[str] = field(default_factory=list)
    meals_logged: int = 0
    
    # Compliance
    compliance_percent: float = 0.0
    missed_targets: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class MedicationCompliance:
    """Compliance data for a single medication."""
    medication_name: str
    dosage: str
    frequency: str
    doses_scheduled: int
    doses_taken: int
    doses_missed: int
    compliance_percent: float
    missed_times: List[str] = field(default_factory=list)


@dataclass
class WeeklyMedicationStats:
    """Aggregated medication compliance for the week (Category C)."""
    medications: List[MedicationCompliance] = field(default_factory=list)
    overall_compliance_percent: float = 0.0
    total_doses_scheduled: int = 0
    total_doses_taken: int = 0
    total_doses_missed: int = 0
    reminders_sent: int = 0
    perfect_compliance_days: int = 0


@dataclass
class WeeklyExerciseStats:
    """Aggregated exercise stats for the week (Category D)."""
    workouts_completed: int = 0
    workouts_planned: int = 0
    total_active_minutes: int = 0
    active_minutes_goal: int = 150  # WHO recommendation
    goal_completion_percent: float = 0.0
    workout_types: List[str] = field(default_factory=list)
    calories_burned: int = 0
    avg_workout_duration: float = 0.0
    longest_workout: int = 0


@dataclass
class WeeklyDocumentStats:
    """Stats from scanned documents this week."""
    new_documents: int = 0
    new_lab_results: List[Dict[str, Any]] = field(default_factory=list)
    new_prescriptions: List[Dict[str, Any]] = field(default_factory=list)
    abnormal_findings: List[str] = field(default_factory=list)


@dataclass
class WeeklySummary:
    """Complete weekly health summary."""
    user_id: str
    week_start: datetime
    week_end: datetime
    
    health_stats: WeeklyHealthStats
    nutrition: WeeklyNutritionStats
    medications: WeeklyMedicationStats
    exercise: WeeklyExerciseStats
    documents: WeeklyDocumentStats
    
    # Risk assessment
    latest_risk_score: Optional[float] = None
    risk_category: Optional[str] = None
    risk_trend: TrendDirection = TrendDirection.STABLE
    
    # AI-generated
    personalized_tip: str = ""
    highlights: List[str] = field(default_factory=list)
    areas_for_improvement: List[str] = field(default_factory=list)
    
    # Metadata
    generated_at: datetime = field(default_factory=datetime.utcnow)


class WeeklyAggregationService:
    """
    Aggregates all health data sources for weekly summary.
    
    Data Sources (as per medical.md):
    A. Health stats - Heart rate, steps, sleep, alerts
    B. Food & calories - Daily calories, nutrition compliance
    C. Medications - Name, dosage, taken/missed, compliance %
    D. Exercise - Workouts, active minutes, goal %
    
    + Scanned document data
    + Prediction results
    """
    
    # Default goals
    DEFAULT_STEPS_GOAL = 10000
    DEFAULT_CALORIE_GOAL = 2000
    DEFAULT_ACTIVE_MINUTES_GOAL = 150
    DEFAULT_SLEEP_GOAL = 7.0
    
    def __init__(
        self,
        timeline_service=None,
        prediction_service=None,
        vitals_db=None,
        nutrition_db=None,
        medication_db=None,
        exercise_db=None
    ):
        """
        Initialize weekly aggregation service.
        
        Args:
            timeline_service: Patient timeline for document data
            prediction_service: Prediction service for risk scores
            vitals_db: Database/API for vital signs
            nutrition_db: Database/API for nutrition data
            medication_db: Database/API for medication tracking
            exercise_db: Database/API for exercise data
        """
        self.timeline = timeline_service
        self.prediction = prediction_service
        self.vitals_db = vitals_db
        self.nutrition_db = nutrition_db
        self.medication_db = medication_db
        self.exercise_db = exercise_db
        
        # Cache for previous weeks (for trend calculation)
        self._previous_summaries: Dict[str, WeeklySummary] = {}
        
        logger.info("WeeklyAggregationService initialized")
    
    def generate_weekly_summary(
        self,
        user_id: str,
        week_end: Optional[datetime] = None
    ) -> WeeklySummary:
        """
        Generate comprehensive weekly health summary.
        
        Args:
            user_id: User ID
            week_end: End of the week (defaults to now)
        
        Returns:
            WeeklySummary with all aggregated data
        """
        # Calculate week boundaries
        end = week_end or datetime.utcnow()
        # Go back to start of current day, then back 6 more days
        end_date = end.replace(hour=23, minute=59, second=59)
        start_date = (end_date - timedelta(days=6)).replace(hour=0, minute=0, second=0)
        
        logger.info(f"Generating weekly summary for {user_id}: {start_date} to {end_date}")
        
        # Aggregate each category
        health_stats = self._aggregate_health_stats(user_id, start_date, end_date)
        nutrition = self._aggregate_nutrition(user_id, start_date, end_date)
        medications = self._aggregate_medications(user_id, start_date, end_date)
        exercise = self._aggregate_exercise(user_id, start_date, end_date)
        documents = self._aggregate_documents(user_id, start_date, end_date)
        
        # Get risk assessment
        risk_score, risk_category = self._get_latest_risk(user_id)
        
        # Generate insights
        tip = self._generate_personalized_tip(
            health_stats, nutrition, medications, exercise
        )
        highlights = self._generate_highlights(
            health_stats, nutrition, medications, exercise, documents
        )
        improvements = self._generate_improvement_areas(
            health_stats, nutrition, medications, exercise
        )
        
        summary = WeeklySummary(
            user_id=user_id,
            week_start=start_date,
            week_end=end_date,
            health_stats=health_stats,
            nutrition=nutrition,
            medications=medications,
            exercise=exercise,
            documents=documents,
            latest_risk_score=risk_score,
            risk_category=risk_category,
            personalized_tip=tip,
            highlights=highlights,
            areas_for_improvement=improvements
        )
        
        # Cache for trend calculation
        self._previous_summaries[user_id] = summary
        
        return summary
    
    def _aggregate_health_stats(
        self,
        user_id: str,
        start: datetime,
        end: datetime
    ) -> WeeklyHealthStats:
        """Aggregate health vitals for the week."""
        stats = WeeklyHealthStats()
        
        # Get data from timeline if available
        if self.timeline:
            from .timeline_service import TimelineEventType
            
            events = self.timeline.get_timeline(
                user_id,
                start_date=start,
                end_date=end,
                event_types=[TimelineEventType.VITAL_READING, TimelineEventType.ALERT],
                limit=1000
            )
            
            heart_rates = []
            systolics = []
            diastolics = []
            steps_by_day: Dict[str, int] = {}
            
            for event in events:
                if event.event_type == TimelineEventType.VITAL_READING:
                    vital_type = event.data.get("vital_type", "")
                    value = event.data.get("value")
                    
                    if vital_type == "heart_rate" and value:
                        heart_rates.append(float(value))
                    elif vital_type == "blood_pressure_systolic" and value:
                        systolics.append(int(value))
                    elif vital_type == "blood_pressure_diastolic" and value:
                        diastolics.append(int(value))
                    elif vital_type == "steps" and value:
                        day = event.timestamp.strftime("%Y-%m-%d")
                        steps_by_day[day] = steps_by_day.get(day, 0) + int(value)
                
                elif event.event_type == TimelineEventType.ALERT:
                    alert_type = event.data.get("alert_type", "")
                    if "high_hr" in alert_type:
                        stats.high_hr_alerts += 1
                    elif "low_hr" in alert_type:
                        stats.low_hr_alerts += 1
            
            # Calculate stats
            if heart_rates:
                stats.avg_heart_rate = round(mean(heart_rates), 1)
                stats.min_heart_rate = int(min(heart_rates))
                stats.max_heart_rate = int(max(heart_rates))
            
            if systolics:
                stats.avg_systolic = int(mean(systolics))
                stats.bp_readings_count = len(systolics)
            
            if diastolics:
                stats.avg_diastolic = int(mean(diastolics))
            
            if steps_by_day:
                stats.total_steps = sum(steps_by_day.values())
                stats.avg_steps_per_day = round(stats.total_steps / len(steps_by_day), 0)
                stats.steps_goal_met_days = sum(
                    1 for steps in steps_by_day.values() 
                    if steps >= self.DEFAULT_STEPS_GOAL
                )
        
        return stats
    
    def _aggregate_nutrition(
        self,
        user_id: str,
        start: datetime,
        end: datetime
    ) -> WeeklyNutritionStats:
        """Aggregate nutrition data for the week."""
        stats = WeeklyNutritionStats()
        stats.calorie_goal = self.DEFAULT_CALORIE_GOAL
        
        # In production, this would query the nutrition database
        # For now, return default/mock data
        if self.nutrition_db:
            # Query nutrition database
            pass
        
        # Calculate compliance
        if stats.avg_daily_calories > 0:
            deviation = abs(stats.avg_daily_calories - stats.calorie_goal)
            tolerance = stats.calorie_goal * 0.1  # 10% tolerance
            stats.compliance_percent = max(0, 100 - (deviation / tolerance * 100))
        
        return stats
    
    def _aggregate_medications(
        self,
        user_id: str,
        start: datetime,
        end: datetime
    ) -> WeeklyMedicationStats:
        """Aggregate medication compliance for the week."""
        stats = WeeklyMedicationStats()
        
        # Get prescriptions from timeline
        if self.timeline:
            from .timeline_service import TimelineEventType
            
            events = self.timeline.get_timeline(
                user_id,
                start_date=start,
                end_date=end,
                event_types=[
                    TimelineEventType.PRESCRIPTION,
                    TimelineEventType.MEDICATION_TAKEN,
                    TimelineEventType.MEDICATION_MISSED
                ],
                limit=500
            )
            
            # Track medications
            med_compliance: Dict[str, Dict[str, Any]] = {}
            
            for event in events:
                if event.event_type == TimelineEventType.PRESCRIPTION:
                    med_name = event.data.get("medication_name", "Unknown")
                    if med_name not in med_compliance:
                        med_compliance[med_name] = {
                            "dosage": event.data.get("dosage", ""),
                            "frequency": event.data.get("frequency", ""),
                            "taken": 0,
                            "missed": 0
                        }
                
                elif event.event_type == TimelineEventType.MEDICATION_TAKEN:
                    med_name = event.data.get("medication_name", "Unknown")
                    if med_name in med_compliance:
                        med_compliance[med_name]["taken"] += 1
                    stats.total_doses_taken += 1
                
                elif event.event_type == TimelineEventType.MEDICATION_MISSED:
                    med_name = event.data.get("medication_name", "Unknown")
                    if med_name in med_compliance:
                        med_compliance[med_name]["missed"] += 1
                    stats.total_doses_missed += 1
            
            # Build medication list
            for med_name, data in med_compliance.items():
                total = data["taken"] + data["missed"]
                compliance = (data["taken"] / total * 100) if total > 0 else 0
                
                stats.medications.append(MedicationCompliance(
                    medication_name=med_name,
                    dosage=data["dosage"],
                    frequency=data["frequency"],
                    doses_scheduled=total,
                    doses_taken=data["taken"],
                    doses_missed=data["missed"],
                    compliance_percent=round(compliance, 1)
                ))
            
            # Calculate overall compliance
            stats.total_doses_scheduled = stats.total_doses_taken + stats.total_doses_missed
            if stats.total_doses_scheduled > 0:
                stats.overall_compliance_percent = round(
                    stats.total_doses_taken / stats.total_doses_scheduled * 100, 1
                )
        
        return stats
    
    def _aggregate_exercise(
        self,
        user_id: str,
        start: datetime,
        end: datetime
    ) -> WeeklyExerciseStats:
        """Aggregate exercise data for the week."""
        stats = WeeklyExerciseStats()
        stats.active_minutes_goal = self.DEFAULT_ACTIVE_MINUTES_GOAL
        
        # Get exercise events from timeline
        if self.timeline:
            from .timeline_service import TimelineEventType
            
            events = self.timeline.get_timeline(
                user_id,
                start_date=start,
                end_date=end,
                event_types=[TimelineEventType.EXERCISE],
                limit=100
            )
            
            workout_durations = []
            workout_types = set()
            
            for event in events:
                stats.workouts_completed += 1
                
                duration = event.data.get("duration_minutes", 0)
                if duration:
                    workout_durations.append(duration)
                    stats.total_active_minutes += duration
                
                workout_type = event.data.get("workout_type")
                if workout_type:
                    workout_types.add(workout_type)
                
                calories = event.data.get("calories_burned", 0)
                stats.calories_burned += calories
            
            stats.workout_types = list(workout_types)
            
            if workout_durations:
                stats.avg_workout_duration = round(mean(workout_durations), 1)
                stats.longest_workout = max(workout_durations)
            
            # Calculate goal completion
            stats.goal_completion_percent = round(
                min(100, stats.total_active_minutes / stats.active_minutes_goal * 100), 1
            )
        
        return stats
    
    def _aggregate_documents(
        self,
        user_id: str,
        start: datetime,
        end: datetime
    ) -> WeeklyDocumentStats:
        """Aggregate document data from timeline."""
        stats = WeeklyDocumentStats()
        
        if self.timeline:
            from .timeline_service import TimelineEventType, EventImportance
            
            events = self.timeline.get_timeline(
                user_id,
                start_date=start,
                end_date=end,
                event_types=[
                    TimelineEventType.DOCUMENT_UPLOADED,
                    TimelineEventType.LAB_RESULT,
                    TimelineEventType.PRESCRIPTION
                ],
                limit=100
            )
            
            for event in events:
                if event.event_type == TimelineEventType.DOCUMENT_UPLOADED:
                    stats.new_documents += 1
                
                elif event.event_type == TimelineEventType.LAB_RESULT:
                    stats.new_lab_results.append({
                        "date": event.timestamp.isoformat(),
                        "title": event.title,
                        "test_count": event.data.get("test_count", 0)
                    })
                    
                    # Check for abnormal findings
                    if event.importance in [EventImportance.HIGH, EventImportance.CRITICAL]:
                        stats.abnormal_findings.append(event.description)
                
                elif event.event_type == TimelineEventType.PRESCRIPTION:
                    stats.new_prescriptions.append({
                        "date": event.timestamp.isoformat(),
                        "medication": event.data.get("medication_name"),
                        "dosage": event.data.get("dosage")
                    })
        
        return stats
    
    def _get_latest_risk(self, user_id: str) -> tuple:
        """Get latest risk assessment."""
        if self.timeline:
            from .timeline_service import TimelineEventType
            
            events = self.timeline.get_timeline(
                user_id,
                event_types=[TimelineEventType.PREDICTION_RUN],
                limit=1
            )
            
            if events:
                return (
                    events[0].data.get("risk_score"),
                    events[0].data.get("risk_category")
                )
        
        return (None, None)
    
    def _generate_personalized_tip(
        self,
        health: WeeklyHealthStats,
        nutrition: WeeklyNutritionStats,
        medications: WeeklyMedicationStats,
        exercise: WeeklyExerciseStats
    ) -> str:
        """Generate personalized health tip based on data."""
        tips = []
        
        # Exercise tips
        if exercise.goal_completion_percent < 50:
            tips.append(
                "Try adding a 10-minute walk after meals to boost your active minutes! 🚶‍♂️"
            )
        elif exercise.goal_completion_percent >= 100:
            tips.append(
                "Amazing job hitting your exercise goal! Keep up the great work! 💪"
            )
        
        # Medication tips
        if medications.overall_compliance_percent < 80:
            tips.append(
                "Setting medication reminders can help improve compliance. "
                "Try linking it to a daily habit like brushing teeth! 💊"
            )
        elif medications.overall_compliance_percent >= 95:
            tips.append(
                "Excellent medication adherence this week! "
                "Consistency is key to your health. ⭐"
            )
        
        # Activity tips
        if health.avg_steps_per_day and health.avg_steps_per_day < 5000:
            tips.append(
                "Small changes add up! Try taking the stairs or parking farther away. 🎯"
            )
        
        # Heart rate tips
        if health.high_hr_alerts > 3:
            tips.append(
                "Consider practicing deep breathing exercises to help manage stress. 🧘"
            )
        
        # Default tip
        if not tips:
            tips.append(
                "Keep up the great work on your health journey! 🌟"
            )
        
        return tips[0]
    
    def _generate_highlights(
        self,
        health: WeeklyHealthStats,
        nutrition: WeeklyNutritionStats,
        medications: WeeklyMedicationStats,
        exercise: WeeklyExerciseStats,
        documents: WeeklyDocumentStats
    ) -> List[str]:
        """Generate positive highlights from the week."""
        highlights = []
        
        if health.steps_goal_met_days >= 5:
            highlights.append(
                f"🏆 Hit your step goal {health.steps_goal_met_days} days this week!"
            )
        
        if exercise.workouts_completed >= 3:
            highlights.append(
                f"💪 Completed {exercise.workouts_completed} workouts this week!"
            )
        
        if medications.overall_compliance_percent >= 90:
            highlights.append(
                f"💊 {medications.overall_compliance_percent:.0f}% medication compliance!"
            )
        
        if documents.new_documents > 0:
            highlights.append(
                f"📄 Added {documents.new_documents} new health document(s) to your record"
            )
        
        return highlights[:5]  # Limit to 5 highlights
    
    def _generate_improvement_areas(
        self,
        health: WeeklyHealthStats,
        nutrition: WeeklyNutritionStats,
        medications: WeeklyMedicationStats,
        exercise: WeeklyExerciseStats
    ) -> List[str]:
        """Identify areas for improvement."""
        areas = []
        
        if health.avg_steps_per_day and health.avg_steps_per_day < 7000:
            areas.append("Daily step count")
        
        if exercise.goal_completion_percent < 80:
            areas.append("Weekly active minutes")
        
        if medications.overall_compliance_percent < 90:
            areas.append("Medication adherence")
        
        if health.high_hr_alerts > 5:
            areas.append("Heart rate management")
        
        return areas[:3]  # Limit to 3 areas


# Global instance
_aggregation_service: Optional[WeeklyAggregationService] = None


def get_aggregation_service() -> WeeklyAggregationService:
    """Get or create the global aggregation service instance."""
    global _aggregation_service
    if _aggregation_service is None:
        _aggregation_service = WeeklyAggregationService()
    return _aggregation_service
