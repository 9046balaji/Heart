"""
Weekly Summary Service Package.

Provides weekly health summary generation and delivery:
- 7-day data aggregation
- Summary message generation
- WhatsApp/Email/SMS delivery
- Scheduled job execution

Usage:
    from weekly_summary import WeeklyDataAggregator, WeeklySummaryMessageGenerator

    aggregator = WeeklyDataAggregator(...)
    data = aggregator.aggregate_weekly_data(user_id)

    generator = WeeklySummaryMessageGenerator()
    summary = generator.generate_summary(data)
"""

from .data_aggregator import (
    WeeklyDataAggregator,
    WeeklyHealthData,
    VitalsAggregate,
    NutritionAggregate,
    MedicationAggregate,
    ExerciseAggregate,
)

from .message_generator import WeeklySummaryMessageGenerator, GeneratedSummary

from .scheduler_job import WeeklySummaryJob, DeliveryResult, register_weekly_summary_job

from .chart_generator import ChartGenerator, get_chart_generator

__all__ = [
    # Data Aggregation
    "WeeklyDataAggregator",
    "WeeklyHealthData",
    "VitalsAggregate",
    "NutritionAggregate",
    "MedicationAggregate",
    "ExerciseAggregate",
    # Message Generation
    "WeeklySummaryMessageGenerator",
    "GeneratedSummary",
    # Scheduler
    "WeeklySummaryJob",
    "DeliveryResult",
    "register_weekly_summary_job",
    # Chart Generation
    "ChartGenerator",
    "get_chart_generator",
]
