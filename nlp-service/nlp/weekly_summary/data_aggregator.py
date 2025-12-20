"""
Weekly Health Data Aggregation Service.

Collects and aggregates 7-day health data for summary generation.
"""

from typing import Dict, Any, List, Optional, Protocol
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging
import statistics

logger = logging.getLogger(__name__)


# Repository Protocols for dependency injection
class VitalsRepository(Protocol):
    """Protocol for vitals data repository."""

    def get_heart_rate_range(
        self, user_id: str, start: datetime, end: datetime
    ) -> List[int]: ...

    def get_daily_steps_range(
        self, user_id: str, start: datetime, end: datetime
    ) -> List[int]: ...

    def get_sleep_data_range(
        self, user_id: str, start: datetime, end: datetime
    ) -> List[Dict]: ...

    def get_blood_pressure_range(
        self, user_id: str, start: datetime, end: datetime
    ) -> List[Dict]: ...


class NutritionRepository(Protocol):
    """Protocol for nutrition data repository."""

    def get_daily_calories_range(
        self, user_id: str, start: datetime, end: datetime
    ) -> List[int]: ...

    def get_nutrition_details_range(
        self, user_id: str, start: datetime, end: datetime
    ) -> List[Dict]: ...


class MedicationRepository(Protocol):
    """Protocol for medication data repository."""

    def get_compliance_range(
        self, user_id: str, start: datetime, end: datetime
    ) -> Dict[str, Any]: ...


class ExerciseRepository(Protocol):
    """Protocol for exercise data repository."""

    def get_workouts_range(
        self, user_id: str, start: datetime, end: datetime
    ) -> List[Dict]: ...


@dataclass
class VitalsAggregate:
    """Aggregated vital signs data."""

    avg_heart_rate: Optional[float] = None
    min_heart_rate: Optional[int] = None
    max_heart_rate: Optional[int] = None
    resting_heart_rate: Optional[float] = None
    hr_trend: Optional[str] = None  # "up", "down", "stable"
    hr_trend_percent: Optional[float] = None

    avg_steps: Optional[float] = None
    total_steps: Optional[int] = None
    steps_trend: Optional[str] = None
    steps_trend_percent: Optional[float] = None

    avg_sleep_hours: Optional[float] = None
    sleep_quality_avg: Optional[str] = None

    avg_blood_pressure_systolic: Optional[float] = None
    avg_blood_pressure_diastolic: Optional[float] = None

    alerts: List[str] = field(default_factory=list)


@dataclass
class NutritionAggregate:
    """Aggregated nutrition data."""

    avg_daily_calories: Optional[float] = None
    total_calories: Optional[int] = None
    balanced_days: int = 0
    total_days: int = 7

    avg_sodium_mg: Optional[float] = None
    avg_sugar_g: Optional[float] = None
    avg_protein_g: Optional[float] = None
    avg_carbs_g: Optional[float] = None
    avg_fat_g: Optional[float] = None

    suggestions: List[str] = field(default_factory=list)


@dataclass
class MedicationAggregate:
    """Aggregated medication compliance data."""

    total_medications: int = 0
    taken_count: int = 0
    missed_count: int = 0
    compliance_percentage: float = 0.0

    medications_detail: List[Dict[str, Any]] = field(default_factory=list)
    missed_medications: List[str] = field(default_factory=list)


@dataclass
class ExerciseAggregate:
    """Aggregated exercise data."""

    workouts_completed: int = 0
    total_active_minutes: int = 0
    calories_burned: int = 0
    goal_completion_percentage: float = 0.0
    target_minutes: int = 150  # WHO recommendation

    workout_types: List[str] = field(default_factory=list)
    workout_days: int = 0


@dataclass
class WeeklyHealthData:
    """Complete weekly health data aggregate."""

    user_id: str
    week_start: datetime
    week_end: datetime

    vitals: VitalsAggregate
    nutrition: NutritionAggregate
    medications: MedicationAggregate
    exercise: ExerciseAggregate

    generated_at: datetime = field(default_factory=datetime.utcnow)
    data_completeness: float = 0.0  # 0-1 indicating how much data was available


class WeeklyDataAggregator:
    """
    Aggregates 7-day health data for weekly summary.

    Collects data from multiple sources:
    - Vital signs database
    - Nutrition/food log
    - Medication tracker
    - Exercise/workout log

    Example:
        aggregator = WeeklyDataAggregator(
            vitals_repository=vitals_repo,
            nutrition_repository=nutrition_repo,
            medication_repository=med_repo,
            exercise_repository=exercise_repo
        )
        data = aggregator.aggregate_weekly_data("user123")
    """

    def __init__(
        self,
        vitals_repository: Optional[VitalsRepository] = None,
        nutrition_repository: Optional[NutritionRepository] = None,
        medication_repository: Optional[MedicationRepository] = None,
        exercise_repository: Optional[ExerciseRepository] = None,
    ):
        """
        Initialize aggregator with data repositories.

        Args:
            vitals_repository: Repository for vital signs data
            nutrition_repository: Repository for nutrition data
            medication_repository: Repository for medication data
            exercise_repository: Repository for exercise data
        """
        self.vitals_repo = vitals_repository
        self.nutrition_repo = nutrition_repository
        self.medication_repo = medication_repository
        self.exercise_repo = exercise_repository

    def aggregate_weekly_data(
        self, user_id: str, week_end: Optional[datetime] = None
    ) -> WeeklyHealthData:
        """
        Aggregate all health data for the past 7 days.

        Args:
            user_id: User to aggregate data for
            week_end: End date of the week (default: now)

        Returns:
            WeeklyHealthData with all aggregates
        """
        if week_end is None:
            week_end = datetime.utcnow()

        week_start = week_end - timedelta(days=7)

        logger.info(
            f"Aggregating weekly data for user {user_id}: {week_start} to {week_end}"
        )

        # Aggregate each category
        vitals = self._aggregate_vitals(user_id, week_start, week_end)
        nutrition = self._aggregate_nutrition(user_id, week_start, week_end)
        medications = self._aggregate_medications(user_id, week_start, week_end)
        exercise = self._aggregate_exercise(user_id, week_start, week_end)

        # Calculate data completeness
        completeness = self._calculate_completeness(
            vitals, nutrition, medications, exercise
        )

        return WeeklyHealthData(
            user_id=user_id,
            week_start=week_start,
            week_end=week_end,
            vitals=vitals,
            nutrition=nutrition,
            medications=medications,
            exercise=exercise,
            data_completeness=completeness,
        )

    def _aggregate_vitals(
        self, user_id: str, start: datetime, end: datetime
    ) -> VitalsAggregate:
        """Aggregate vital signs data."""
        vitals = VitalsAggregate()

        if not self.vitals_repo:
            return vitals

        try:
            # Get heart rate data
            hr_data = self.vitals_repo.get_heart_rate_range(user_id, start, end)
            if hr_data:
                vitals.avg_heart_rate = round(statistics.mean(hr_data), 1)
                vitals.min_heart_rate = min(hr_data)
                vitals.max_heart_rate = max(hr_data)

                # Calculate trend (compare first half to second half)
                mid = len(hr_data) // 2
                if mid > 0:
                    first_half_avg = statistics.mean(hr_data[:mid])
                    second_half_avg = statistics.mean(hr_data[mid:])
                    diff = second_half_avg - first_half_avg
                    percent_change = (
                        (diff / first_half_avg * 100) if first_half_avg > 0 else 0
                    )

                    if diff > 3:
                        vitals.hr_trend = "up"
                    elif diff < -3:
                        vitals.hr_trend = "down"
                    else:
                        vitals.hr_trend = "stable"
                    vitals.hr_trend_percent = round(percent_change, 1)

            # Get steps data
            steps_data = self.vitals_repo.get_daily_steps_range(user_id, start, end)
            if steps_data:
                vitals.total_steps = sum(steps_data)
                vitals.avg_steps = round(statistics.mean(steps_data), 0)

                # Steps trend
                mid = len(steps_data) // 2
                if mid > 0:
                    first_half_avg = statistics.mean(steps_data[:mid])
                    second_half_avg = statistics.mean(steps_data[mid:])
                    diff = second_half_avg - first_half_avg
                    percent_change = (
                        (diff / first_half_avg * 100) if first_half_avg > 0 else 0
                    )

                    if percent_change > 10:
                        vitals.steps_trend = "up"
                    elif percent_change < -10:
                        vitals.steps_trend = "down"
                    else:
                        vitals.steps_trend = "stable"
                    vitals.steps_trend_percent = round(percent_change, 1)

            # Get sleep data
            sleep_data = self.vitals_repo.get_sleep_data_range(user_id, start, end)
            if sleep_data:
                hours = [s.get("hours", 0) for s in sleep_data if s.get("hours")]
                if hours:
                    vitals.avg_sleep_hours = round(statistics.mean(hours), 1)

            # Get blood pressure data
            bp_data = self.vitals_repo.get_blood_pressure_range(user_id, start, end)
            if bp_data:
                systolic = [bp.get("systolic") for bp in bp_data if bp.get("systolic")]
                diastolic = [
                    bp.get("diastolic") for bp in bp_data if bp.get("diastolic")
                ]
                if systolic:
                    vitals.avg_blood_pressure_systolic = round(
                        statistics.mean(systolic), 0
                    )
                if diastolic:
                    vitals.avg_blood_pressure_diastolic = round(
                        statistics.mean(diastolic), 0
                    )

            # Check for alerts
            if vitals.max_heart_rate and vitals.max_heart_rate > 120:
                vitals.alerts.append(
                    f"High heart rate detected: {vitals.max_heart_rate} bpm"
                )

            if vitals.avg_steps and vitals.avg_steps < 3000:
                vitals.alerts.append("Low activity: Consider increasing daily steps")

            if vitals.avg_sleep_hours and vitals.avg_sleep_hours < 6:
                vitals.alerts.append(
                    f"Low sleep: Averaging {vitals.avg_sleep_hours:.1f} hours/night"
                )

            if (
                vitals.avg_blood_pressure_systolic
                and vitals.avg_blood_pressure_systolic > 140
            ):
                vitals.alerts.append("Elevated blood pressure readings")

        except Exception as e:
            logger.error(f"Error aggregating vitals: {e}")

        return vitals

    def _aggregate_nutrition(
        self, user_id: str, start: datetime, end: datetime
    ) -> NutritionAggregate:
        """Aggregate nutrition data."""
        nutrition = NutritionAggregate()

        if not self.nutrition_repo:
            return nutrition

        try:
            # Get daily calorie data
            calorie_data = self.nutrition_repo.get_daily_calories_range(
                user_id, start, end
            )
            if calorie_data:
                nutrition.total_calories = sum(calorie_data)
                nutrition.avg_daily_calories = round(statistics.mean(calorie_data), 0)
                nutrition.total_days = len(calorie_data)

                # Count "balanced" days (1800-2200 calories as example)
                nutrition.balanced_days = sum(
                    1 for c in calorie_data if 1800 <= c <= 2200
                )

                # Generate suggestions
                if nutrition.avg_daily_calories > 2500:
                    nutrition.suggestions.append("Consider reducing portion sizes")
                elif nutrition.avg_daily_calories < 1500:
                    nutrition.suggestions.append(
                        "You may need more calories for energy"
                    )

            # Get detailed nutrition
            details = self.nutrition_repo.get_nutrition_details_range(
                user_id, start, end
            )
            if details:
                sodium = [d.get("sodium_mg", 0) for d in details if d.get("sodium_mg")]
                sugar = [d.get("sugar_g", 0) for d in details if d.get("sugar_g")]
                protein = [d.get("protein_g", 0) for d in details if d.get("protein_g")]

                if sodium:
                    nutrition.avg_sodium_mg = round(statistics.mean(sodium), 0)
                    if nutrition.avg_sodium_mg > 2300:
                        nutrition.suggestions.append(
                            "Sodium intake is above recommended limit"
                        )

                if sugar:
                    nutrition.avg_sugar_g = round(statistics.mean(sugar), 0)
                    if nutrition.avg_sugar_g > 50:
                        nutrition.suggestions.append("Consider reducing sugar intake")

                if protein:
                    nutrition.avg_protein_g = round(statistics.mean(protein), 0)

        except Exception as e:
            logger.error(f"Error aggregating nutrition: {e}")

        return nutrition

    def _aggregate_medications(
        self, user_id: str, start: datetime, end: datetime
    ) -> MedicationAggregate:
        """Aggregate medication compliance data."""
        medications = MedicationAggregate()

        if not self.medication_repo:
            return medications

        try:
            # Get medication tracking data
            med_data = self.medication_repo.get_compliance_range(user_id, start, end)
            if med_data:
                medications.total_medications = med_data.get("total_scheduled", 0)
                medications.taken_count = med_data.get("taken", 0)
                medications.missed_count = med_data.get("missed", 0)

                if medications.total_medications > 0:
                    medications.compliance_percentage = round(
                        medications.taken_count / medications.total_medications * 100, 1
                    )

                medications.medications_detail = med_data.get("details", [])
                medications.missed_medications = med_data.get("missed_names", [])

        except Exception as e:
            logger.error(f"Error aggregating medications: {e}")

        return medications

    def _aggregate_exercise(
        self, user_id: str, start: datetime, end: datetime
    ) -> ExerciseAggregate:
        """Aggregate exercise data."""
        exercise = ExerciseAggregate()

        if not self.exercise_repo:
            return exercise

        try:
            # Get workout data
            workout_data = self.exercise_repo.get_workouts_range(user_id, start, end)
            if workout_data:
                exercise.workouts_completed = len(workout_data)
                exercise.total_active_minutes = sum(
                    w.get("duration_minutes", 0) for w in workout_data
                )
                exercise.calories_burned = sum(
                    w.get("calories", 0) for w in workout_data
                )
                exercise.workout_types = list(
                    set(w.get("type", "Unknown") for w in workout_data)
                )

                # Count unique workout days
                workout_dates = set(
                    w.get("date", "").split("T")[0]
                    for w in workout_data
                    if w.get("date")
                )
                exercise.workout_days = len(workout_dates)

                # Goal completion (WHO: 150 minutes/week moderate activity)
                exercise.goal_completion_percentage = min(
                    round(
                        exercise.total_active_minutes / exercise.target_minutes * 100, 1
                    ),
                    100,
                )

        except Exception as e:
            logger.error(f"Error aggregating exercise: {e}")

        return exercise

    def _calculate_completeness(
        self,
        vitals: VitalsAggregate,
        nutrition: NutritionAggregate,
        medications: MedicationAggregate,
        exercise: ExerciseAggregate,
    ) -> float:
        """Calculate how complete the weekly data is."""
        scores = []

        # Vitals completeness
        vitals_score = 0
        if vitals.avg_heart_rate:
            vitals_score += 0.25
        if vitals.avg_steps:
            vitals_score += 0.25
        if vitals.avg_sleep_hours:
            vitals_score += 0.25
        if vitals.avg_blood_pressure_systolic:
            vitals_score += 0.25
        scores.append(vitals_score)

        # Nutrition completeness
        nutrition_score = (
            min(nutrition.total_days / 7, 1.0) if nutrition.total_days else 0
        )
        scores.append(nutrition_score)

        # Medication completeness
        med_score = 1.0 if medications.total_medications > 0 else 0
        scores.append(med_score)

        # Exercise completeness
        exercise_score = 1.0 if exercise.workouts_completed > 0 else 0
        scores.append(exercise_score)

        return round(statistics.mean(scores), 2)
