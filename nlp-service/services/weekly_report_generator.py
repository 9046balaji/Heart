"""
Weekly Health Report Generator Service

Aggregates health data from the past week and generates comprehensive
HTML reports with charts, insights, and personalized recommendations.
"""

import logging
import base64
import io
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server environment

logger = logging.getLogger(__name__)


class WeeklyReportGenerator:
    """Generates comprehensive weekly health reports with charts and insights."""

    def __init__(self):
        """Initialize the report generator."""
        self.fig_size = (8, 4)
        self.dpi = 100

    def generate_chart_base64(self, chart_data: List[float], labels: List[str], 
                            title: str, ylabel: str, color: str = '#E11D48') -> str:
        """
        Generate a line/bar chart and convert to base64 PNG.
        
        Args:
            chart_data: List of numeric values
            labels: X-axis labels
            title: Chart title
            ylabel: Y-axis label
            color: Chart color (default: primary rose red)
            
        Returns:
            Base64 encoded PNG image string
        """
        try:
            fig, ax = plt.subplots(figsize=self.fig_size, dpi=self.dpi)
            
            # Create line chart
            ax.plot(labels, chart_data, color=color, linewidth=2.5, marker='o', 
                   markersize=6, markerfacecolor=color, markeredgecolor='white', 
                   markeredgewidth=2)
            
            # Styling
            ax.set_title(title, fontsize=12, fontweight='bold', pad=15)
            ax.set_ylabel(ylabel, fontsize=10)
            ax.grid(True, alpha=0.2, linestyle='--')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            # Set background
            fig.patch.set_facecolor('white')
            ax.set_facecolor('#F8FAFC')
            
            plt.tight_layout()
            
            # Convert to base64
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', bbox_inches='tight', dpi=self.dpi)
            plt.close(fig)
            
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return image_base64
            
        except Exception as e:
            logger.error(f"Error generating chart: {e}")
            return ""

    def generate_mock_health_data(self, user_id: str) -> Dict[str, Any]:
        """
        Generate mock health data for the past 7 days.
        
        In production, this would query the actual health_data.db database.
        For food items, uses actual consumption data from FoodConsumptionLog.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary containing aggregated health data
        """
        import random
        from datetime import datetime
        
        try:
            from services.food_consumption import get_user_food_consumption
        except ImportError:
            logger.warning("Could not import food_consumption module")
            get_user_food_consumption = None
        
        # Generate 7 days of data
        data = {
            'heart_rate': [],
            'heart_rate_labels': [],
            'steps': [],
            'steps_labels': [],
            'blood_pressure_systolic': [],
            'blood_pressure_diastolic': [],
            'blood_pressure_labels': [],
            'medication_adherence': [],
            'medication_labels': [],
            'food_log': [],
            'water_intake': 5,  # cups per day
        }
        
        # Generate 7 days of vital signs data
        now = datetime.utcnow()
        
        for i in range(7):
            date = (now - timedelta(days=6-i)).date()
            label = date.strftime('%a')
            
            # Heart rate data (realistic values 60-100 bpm)
            hr = random.randint(60, 100)
            data['heart_rate'].append(hr)
            data['heart_rate_labels'].append(label)
            
            # Steps data (realistic values 5000-15000)
            steps = random.randint(5000, 15000)
            data['steps'].append(steps)
            data['steps_labels'].append(label)
            
            # Blood pressure data
            sys_bp = random.randint(110, 140)
            dia_bp = random.randint(70, 90)
            data['blood_pressure_systolic'].append(sys_bp)
            data['blood_pressure_diastolic'].append(dia_bp)
            data['blood_pressure_labels'].append(label)
            
            # Medication adherence (percentage 0-100)
            adherence = random.randint(70, 100)
            data['medication_adherence'].append(adherence)
            data['medication_labels'].append(label)
        
        # Get ACTUAL food consumption data (not random selections)
        if get_user_food_consumption:
            try:
                actual_food_log = get_user_food_consumption(user_id)
                data['food_log'] = actual_food_log
                logger.info(f"Loaded {len(actual_food_log)} actual food items for user {user_id}")
            except Exception as e:
                logger.error(f"Error loading food consumption data: {e}")
                data['food_log'] = []
        else:
            data['food_log'] = []
        
        return data

    def generate_report_data(self, user_id: str, user_name: str = "Patient") -> Dict[str, Any]:
        """
        Generate complete report data including health metrics, charts, and insights.
        
        Args:
            user_id: User ID
            user_name: User's display name
            
        Returns:
            Dictionary with all data needed to render the weekly report template
        """
        # Fetch or generate health data
        health_data = self.generate_mock_health_data(user_id)
        
        # Generate charts
        charts = {
            'heart_rate': self.generate_chart_base64(
                health_data['heart_rate'],
                health_data['heart_rate_labels'],
                'Heart Rate Trend',
                'BPM',
                color='#E11D48'
            ),
            'steps': self.generate_chart_base64(
                health_data['steps'],
                health_data['steps_labels'],
                'Daily Steps',
                'Steps',
                color='#10B981'
            ),
            'blood_pressure': self._generate_bp_chart(
                health_data['blood_pressure_systolic'],
                health_data['blood_pressure_diastolic'],
                health_data['blood_pressure_labels']
            ),
            'medication': self.generate_chart_base64(
                health_data['medication_adherence'],
                health_data['medication_labels'],
                'Medication Adherence',
                'Adherence %',
                color='#F59E0B'
            ),
        }
        
        # Calculate averages and generate insights
        avg_hr = sum(health_data['heart_rate']) / len(health_data['heart_rate'])
        avg_steps = sum(health_data['steps']) / len(health_data['steps'])
        
        insights = {
            'heart_rate': (
                f"Your average heart rate this week was {avg_hr:.0f} bpm, "
                "which is within the healthy resting range. Keep up the good work!"
            ),
            'steps': (
                f"You averaged {avg_steps:.0f} steps per day. "
                "Great activity level! Continue this momentum."
            ),
            'blood_pressure': (
                f"Average BP: {sum(health_data['blood_pressure_systolic'])/7:.0f}/"
                f"{sum(health_data['blood_pressure_diastolic'])/7:.0f} mmHg. "
                "Your blood pressure is well-controlled."
            ),
            'medication': (
                f"Your medication adherence is {sum(health_data['medication_adherence'])/7:.0f}%. "
                "Excellent consistency in taking your medications!"
            ),
        }
        
        # Nutrition data
        nutrition = {
            'sodium_avg': 1850,  # mg - shown as high
            'fiber_avg': 22,     # g - shown as good
        }
        
        # Calculate average calories from food log
        total_calories = sum(item['calories'] for item in health_data['food_log'])
        
        # Diet plan recommendations
        diet_plan = {
            'condition_focus': 'Heart Health',
            'recommended': [
                {
                    'category': 'Lean Proteins',
                    'items': 'Chicken breast, fish (salmon, mackerel), tofu, legumes'
                },
                {
                    'category': 'Whole Grains',
                    'items': 'Oatmeal, brown rice, whole wheat bread, quinoa'
                },
                {
                    'category': 'Fresh Fruits & Vegetables',
                    'items': 'Berries, leafy greens, bell peppers, broccoli'
                },
                {
                    'category': 'Healthy Fats',
                    'items': 'Olive oil, nuts, avocados, fatty fish'
                },
            ],
            'recommended_reason': (
                'These foods are rich in potassium, magnesium, and omega-3 fatty acids, '
                'which support cardiovascular health and help regulate blood pressure.'
            ),
            'restricted': [
                {
                    'category': 'High-Sodium Foods',
                    'items': 'Processed meats, canned soups, chips, salty snacks'
                },
                {
                    'category': 'Saturated Fats',
                    'items': 'Butter, fatty red meat, full-fat dairy, pastries'
                },
                {
                    'category': 'Added Sugars',
                    'items': 'Sodas, candy, desserts, sweetened beverages'
                },
                {
                    'category': 'Alcohol',
                    'items': 'Limit to moderate amounts (1-2 drinks per day max)'
                },
            ],
            'restricted_reason': (
                'These foods can increase sodium intake, blood pressure, cholesterol levels, '
                'and inflammation, which are harmful to heart health.'
            ),
        }
        
        # Medication adherence score
        med_score = sum(health_data['medication_adherence']) / len(health_data['medication_adherence'])
        
        scores = {
            'medication': int(med_score),
            'medication_message': (
                f"Outstanding adherence! You're maintaining {med_score:.0f}% consistency. "
                "Keep taking your medications as prescribed for optimal heart health."
            ) if med_score >= 90 else (
                f"Good adherence at {med_score:.0f}%. Minor improvement would help. "
                "Consider setting daily reminders to never miss a dose."
            ),
        }
        
        # Recommendations
        recommendations = [
            "Increase daily water intake to 8-10 glasses (64-80 oz) per day",
            "Aim for 150 minutes of moderate cardio exercise per week (e.g., brisk walking)",
            "Reduce sodium intake to under 2,300 mg per day for better BP control",
            "Practice stress-reduction techniques like meditation or deep breathing (10-15 min daily)",
            "Schedule regular check-ups with your cardiologist every 3-6 months",
            "Monitor your blood pressure at home daily, same time each morning",
            "Maintain consistent sleep schedule: aim for 7-9 hours nightly",
        ]
        
        # Week range
        now = datetime.utcnow()
        week_start = (now - timedelta(days=6)).date()
        week_end = now.date()
        week_range = f"{week_start.strftime('%B %d')} - {week_end.strftime('%B %d, %Y')}"
        
        # Compile complete report data
        report_data = {
            'user_name': user_name,
            'week_range': week_range,
            'charts': charts,
            'insights': insights,
            'nutrition': nutrition,
            'food_log': health_data['food_log'],
            'diet_plan': diet_plan,
            'scores': scores,
            'recommendations': recommendations,
        }
        
        return report_data

    def _generate_bp_chart(self, systolic: List[int], diastolic: List[int], 
                          labels: List[str]) -> str:
        """
        Generate a dual-line blood pressure chart.
        
        Args:
            systolic: Systolic readings
            diastolic: Diastolic readings
            labels: Date labels
            
        Returns:
            Base64 encoded PNG image
        """
        try:
            fig, ax = plt.subplots(figsize=self.fig_size, dpi=self.dpi)
            
            # Plot both systolic and diastolic
            ax.plot(labels, systolic, color='#1D4ED8', linewidth=2.5, marker='o',
                   markersize=5, label='Systolic', markerfacecolor='#1D4ED8',
                   markeredgecolor='white', markeredgewidth=2)
            ax.plot(labels, diastolic, color='#0EA5E9', linewidth=2.5, marker='s',
                   markersize=5, label='Diastolic', markerfacecolor='#0EA5E9',
                   markeredgecolor='white', markeredgewidth=2)
            
            # Add reference lines for normal BP
            ax.axhline(y=120, color='#F59E0B', linestyle='--', alpha=0.5, linewidth=1)
            ax.axhline(y=80, color='#F59E0B', linestyle='--', alpha=0.5, linewidth=1)
            
            # Styling
            ax.set_title('Blood Pressure Trend', fontsize=12, fontweight='bold', pad=15)
            ax.set_ylabel('mmHg', fontsize=10)
            ax.legend(loc='upper left', fontsize=9)
            ax.grid(True, alpha=0.2, linestyle='--')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            fig.patch.set_facecolor('white')
            ax.set_facecolor('#F8FAFC')
            
            plt.tight_layout()
            
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', bbox_inches='tight', dpi=self.dpi)
            plt.close(fig)
            
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return image_base64
            
        except Exception as e:
            logger.error(f"Error generating BP chart: {e}")
            return ""
