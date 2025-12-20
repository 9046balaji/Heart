"""
Weekly Summary Message Generator.

Generates WhatsApp-friendly formatted health summaries.
"""

from typing import Optional
from dataclasses import dataclass
from datetime import datetime
import logging

from .data_aggregator import WeeklyHealthData

logger = logging.getLogger(__name__)


@dataclass
class GeneratedSummary:
    """Generated summary message."""

    user_id: str
    message: str
    message_type: str  # "whatsapp", "email", "sms"
    character_count: int
    week_start: datetime
    week_end: datetime
    generated_at: datetime

    # WhatsApp has 65536 character limit, but we aim for readable lengths
    is_within_limit: bool = True


class WeeklySummaryMessageGenerator:
    """
    Generates formatted health summary messages.

    Optimized for WhatsApp delivery with:
    - Emoji indicators for quick scanning
    - Structured sections
    - Actionable insights
    - Character limit awareness

    Example:
        generator = WeeklySummaryMessageGenerator()
        summary = generator.generate_whatsapp_message(weekly_data)
        print(summary.message)
    """

    # WhatsApp formatting
    WHATSAPP_MAX_LENGTH = 4096  # Practical limit for readability

    # Emoji indicators
    EMOJI_HEART = "❤️"
    EMOJI_STEPS = "👣"
    EMOJI_SLEEP = "😴"
    EMOJI_FOOD = "🍎"
    EMOJI_PILL = "💊"
    EMOJI_EXERCISE = "🏃"
    EMOJI_CHECK = "✅"
    EMOJI_WARNING = "⚠️"
    EMOJI_UP = "📈"
    EMOJI_DOWN = "📉"
    EMOJI_STABLE = "➡️"
    EMOJI_STAR = "⭐"
    EMOJI_CALENDAR = "📅"
    EMOJI_CHART = "📊"

    def __init__(self, user_name: Optional[str] = None):
        """Initialize generator with optional user name."""
        self.user_name = user_name

    def generate_whatsapp_message(
        self,
        data: WeeklyHealthData,
        include_detailed_nutrition: bool = True,
        include_medication_details: bool = True,
    ) -> GeneratedSummary:
        """
        Generate a WhatsApp-formatted weekly summary.

        Args:
            data: Aggregated weekly health data
            include_detailed_nutrition: Include nutrition breakdown
            include_medication_details: Include medication names

        Returns:
            GeneratedSummary with formatted message
        """
        sections = []

        # Header
        sections.append(self._generate_header(data))

        # Vitals section
        vitals_section = self._generate_vitals_section(data)
        if vitals_section:
            sections.append(vitals_section)

        # Nutrition section
        nutrition_section = self._generate_nutrition_section(
            data, include_detailed_nutrition
        )
        if nutrition_section:
            sections.append(nutrition_section)

        # Medication section
        medication_section = self._generate_medication_section(
            data, include_medication_details
        )
        if medication_section:
            sections.append(medication_section)

        # Exercise section
        exercise_section = self._generate_exercise_section(data)
        if exercise_section:
            sections.append(exercise_section)

        # Alerts section
        alerts_section = self._generate_alerts_section(data)
        if alerts_section:
            sections.append(alerts_section)

        # Footer
        sections.append(self._generate_footer(data))

        # Combine all sections
        message = "\n\n".join(sections)

        return GeneratedSummary(
            user_id=data.user_id,
            message=message,
            message_type="whatsapp",
            character_count=len(message),
            week_start=data.week_start,
            week_end=data.week_end,
            generated_at=datetime.utcnow(),
            is_within_limit=len(message) <= self.WHATSAPP_MAX_LENGTH,
        )

    def _generate_header(self, data: WeeklyHealthData) -> str:
        """Generate message header."""
        greeting = f"Hi {self.user_name}" if self.user_name else "Hello"
        week_str = f"{data.week_start.strftime('%b %d')} - {data.week_end.strftime('%b %d, %Y')}"

        return f"""{self.EMOJI_CALENDAR} *Weekly Health Summary*
{greeting}! Here's your health report for {week_str}:"""

    def _generate_vitals_section(self, data: WeeklyHealthData) -> Optional[str]:
        """Generate vitals section."""
        vitals = data.vitals
        lines = [f"{self.EMOJI_CHART} *VITALS OVERVIEW*"]

        has_data = False

        # Heart rate
        if vitals.avg_heart_rate:
            has_data = True
            trend_emoji = self._get_trend_emoji(vitals.hr_trend)
            lines.append(
                f"{self.EMOJI_HEART} Heart Rate: {vitals.avg_heart_rate:.0f} bpm avg {trend_emoji}"
            )
            if vitals.min_heart_rate and vitals.max_heart_rate:
                lines.append(
                    f"   Range: {vitals.min_heart_rate} - {vitals.max_heart_rate} bpm"
                )

        # Steps
        if vitals.avg_steps:
            has_data = True
            trend_emoji = self._get_trend_emoji(vitals.steps_trend)
            lines.append(
                f"{self.EMOJI_STEPS} Daily Steps: {vitals.avg_steps:,.0f} avg {trend_emoji}"
            )
            if vitals.total_steps:
                lines.append(f"   Total: {vitals.total_steps:,} steps this week")

        # Sleep
        if vitals.avg_sleep_hours:
            has_data = True
            sleep_quality = self._get_sleep_quality_indicator(vitals.avg_sleep_hours)
            lines.append(
                f"{self.EMOJI_SLEEP} Sleep: {vitals.avg_sleep_hours:.1f} hrs/night {sleep_quality}"
            )

        # Blood pressure
        if vitals.avg_blood_pressure_systolic and vitals.avg_blood_pressure_diastolic:
            has_data = True
            bp_indicator = self._get_bp_indicator(
                vitals.avg_blood_pressure_systolic, vitals.avg_blood_pressure_diastolic
            )
            lines.append(
                f"🩺 Blood Pressure: {vitals.avg_blood_pressure_systolic:.0f}/"
                f"{vitals.avg_blood_pressure_diastolic:.0f} mmHg {bp_indicator}"
            )

        return "\n".join(lines) if has_data else None

    def _generate_nutrition_section(
        self, data: WeeklyHealthData, detailed: bool
    ) -> Optional[str]:
        """Generate nutrition section."""
        nutrition = data.nutrition
        lines = [f"{self.EMOJI_FOOD} *NUTRITION*"]

        has_data = False

        if nutrition.avg_daily_calories:
            has_data = True
            lines.append(f"Avg Daily Calories: {nutrition.avg_daily_calories:,.0f}")
            lines.append(
                f"Balanced Days: {nutrition.balanced_days}/{nutrition.total_days}"
            )

        if detailed and has_data:
            if nutrition.avg_sodium_mg:
                sodium_status = (
                    self.EMOJI_WARNING
                    if nutrition.avg_sodium_mg > 2300
                    else self.EMOJI_CHECK
                )
                lines.append(
                    f"Sodium: {nutrition.avg_sodium_mg:.0f} mg/day {sodium_status}"
                )
            if nutrition.avg_sugar_g:
                sugar_status = (
                    self.EMOJI_WARNING
                    if nutrition.avg_sugar_g > 50
                    else self.EMOJI_CHECK
                )
                lines.append(f"Sugar: {nutrition.avg_sugar_g:.0f} g/day {sugar_status}")
            if nutrition.avg_protein_g:
                lines.append(f"Protein: {nutrition.avg_protein_g:.0f} g/day")

        # Suggestions
        if nutrition.suggestions:
            lines.append("")
            lines.append("_Tips:_")
            for suggestion in nutrition.suggestions[:2]:  # Limit to 2 suggestions
                lines.append(f"• {suggestion}")

        return "\n".join(lines) if has_data else None

    def _generate_medication_section(
        self, data: WeeklyHealthData, include_details: bool
    ) -> Optional[str]:
        """Generate medication section."""
        meds = data.medications

        if meds.total_medications == 0:
            return None

        lines = [f"{self.EMOJI_PILL} *MEDICATIONS*"]

        # Compliance percentage with visual indicator
        compliance_emoji = self._get_compliance_emoji(meds.compliance_percentage)
        lines.append(
            f"Compliance: {meds.compliance_percentage:.0f}% {compliance_emoji}"
        )
        lines.append(f"Taken: {meds.taken_count}/{meds.total_medications}")

        # Missed medications warning
        if meds.missed_medications and include_details:
            lines.append(f"\n{self.EMOJI_WARNING} _Missed:_")
            for med in meds.missed_medications[:3]:  # Limit to 3
                lines.append(f"• {med}")

        return "\n".join(lines)

    def _generate_exercise_section(self, data: WeeklyHealthData) -> Optional[str]:
        """Generate exercise section."""
        exercise = data.exercise

        if exercise.workouts_completed == 0 and exercise.total_active_minutes == 0:
            return f"{self.EMOJI_EXERCISE} *EXERCISE*\nNo workouts logged this week. Try to stay active!"

        lines = [f"{self.EMOJI_EXERCISE} *EXERCISE*"]

        lines.append(f"Workouts: {exercise.workouts_completed}")
        lines.append(f"Active Minutes: {exercise.total_active_minutes} min")

        # Goal progress bar
        goal_bar = self._generate_progress_bar(exercise.goal_completion_percentage)
        lines.append(
            f"Weekly Goal: {goal_bar} {exercise.goal_completion_percentage:.0f}%"
        )

        if exercise.calories_burned > 0:
            lines.append(f"Calories Burned: {exercise.calories_burned:,}")

        if exercise.workout_types:
            lines.append(f"Activities: {', '.join(exercise.workout_types[:3])}")

        return "\n".join(lines)

    def _generate_alerts_section(self, data: WeeklyHealthData) -> Optional[str]:
        """Generate alerts section if there are any."""
        alerts = data.vitals.alerts.copy()

        # Add medication compliance alert
        if (
            data.medications.compliance_percentage < 80
            and data.medications.total_medications > 0
        ):
            alerts.append("Medication compliance below 80%. Please stay on schedule.")

        # Add exercise alert
        if data.exercise.goal_completion_percentage < 50:
            alerts.append("Exercise goal below 50%. Try adding more activity.")

        if not alerts:
            return None

        lines = [f"{self.EMOJI_WARNING} *ATTENTION NEEDED*"]
        for alert in alerts[:4]:  # Limit to 4 alerts
            lines.append(f"• {alert}")

        return "\n".join(lines)

    def _generate_footer(self, data: WeeklyHealthData) -> str:
        """Generate message footer."""
        completeness_str = f"{data.data_completeness * 100:.0f}%"

        return f"""---
_Data completeness: {completeness_str}_
_Reply STOP to unsubscribe • HELP for support_
{self.EMOJI_STAR} Stay healthy!"""

    def _get_trend_emoji(self, trend: Optional[str]) -> str:
        """Get emoji for trend direction."""
        if trend == "up":
            return self.EMOJI_UP
        elif trend == "down":
            return self.EMOJI_DOWN
        else:
            return self.EMOJI_STABLE

    def _get_sleep_quality_indicator(self, hours: float) -> str:
        """Get sleep quality indicator."""
        if hours >= 7:
            return self.EMOJI_CHECK
        elif hours >= 6:
            return "😐"
        else:
            return self.EMOJI_WARNING

    def _get_bp_indicator(self, systolic: float, diastolic: float) -> str:
        """Get blood pressure indicator."""
        if systolic < 120 and diastolic < 80:
            return self.EMOJI_CHECK  # Normal
        elif systolic < 130 and diastolic < 80:
            return "🟡"  # Elevated
        else:
            return self.EMOJI_WARNING  # High

    def _get_compliance_emoji(self, percentage: float) -> str:
        """Get medication compliance indicator."""
        if percentage >= 90:
            return self.EMOJI_STAR
        elif percentage >= 75:
            return self.EMOJI_CHECK
        elif percentage >= 50:
            return "🟡"
        else:
            return self.EMOJI_WARNING

    def _generate_progress_bar(self, percentage: float, length: int = 10) -> str:
        """Generate a text-based progress bar."""
        filled = int(percentage / 100 * length)
        empty = length - filled
        return f"[{'█' * filled}{'░' * empty}]"

    def generate_email_message(
        self, data: WeeklyHealthData, include_charts: bool = False
    ) -> GeneratedSummary:
        """
        Generate an email-formatted weekly summary.

        More detailed than WhatsApp, can include charts/graphs.

        Args:
            data: Aggregated weekly health data
            include_charts: Whether to include chart placeholders

        Returns:
            GeneratedSummary with HTML email content
        """
        # Email can be more detailed
        whatsapp_summary = self.generate_whatsapp_message(data)

        # Convert to HTML-friendly format
        html_message = self._convert_to_html(whatsapp_summary.message)

        return GeneratedSummary(
            user_id=data.user_id,
            message=html_message,
            message_type="email",
            character_count=len(html_message),
            week_start=data.week_start,
            week_end=data.week_end,
            generated_at=datetime.utcnow(),
        )

    def _convert_to_html(self, text: str) -> str:
        """Convert WhatsApp formatting to HTML."""
        # Replace WhatsApp bold (*text*) with HTML bold
        import re

        html = text
        html = re.sub(r"\*([^*]+)\*", r"<strong>\1</strong>", html)
        html = re.sub(r"_([^_]+)_", r"<em>\1</em>", html)
        html = html.replace("\n", "<br>\n")

        return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; }}
        .summary {{ max-width: 600px; margin: 0 auto; }}
    </style>
</head>
<body>
    <div class="summary">
        {html}
    </div>
</body>
</html>
"""

    def generate_sms_message(self, data: WeeklyHealthData) -> GeneratedSummary:
        """
        Generate a condensed SMS summary (160 char limit awareness).

        Args:
            data: Aggregated weekly health data

        Returns:
            GeneratedSummary with SMS-optimized content
        """
        # Very condensed summary
        vitals = data.vitals
        meds = data.medications

        parts = ["Weekly Health:"]

        if vitals.avg_heart_rate:
            parts.append(f"HR:{vitals.avg_heart_rate:.0f}")
        if vitals.avg_steps:
            parts.append(f"Steps:{vitals.avg_steps/1000:.1f}k")
        if meds.total_medications > 0:
            parts.append(f"Meds:{meds.compliance_percentage:.0f}%")

        message = " ".join(parts)

        return GeneratedSummary(
            user_id=data.user_id,
            message=message,
            message_type="sms",
            character_count=len(message),
            week_start=data.week_start,
            week_end=data.week_end,
            generated_at=datetime.utcnow(),
            is_within_limit=len(message) <= 160,
        )
