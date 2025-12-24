"""
Chart Generator for Weekly Health Reports.

Generates professional matplotlib charts as base64-encoded PNG images
for embedding in PDF reports.
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server use
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
import base64
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ChartGenerator:
    """
    Professional chart generator for health metrics.
    
    Features:
    - Heart rate trend lines
    - Activity bar charts
    - Blood pressure dual-axis charts
    - Medication adherence gauges
    
    All charts use consistent Heart Health branding colors.
    """
    
    # Brand colors
    COLORS = {
        'primary': '#FF4B4B',      # Red for heart rate
        'success': '#4CAF50',      # Green for goals met
        'warning': '#FFC107',      # Yellow for warnings
        'info': '#2196F3',         # Blue for informational
        'danger': '#F44336',       # Red for alerts
        'neutral': '#9E9E9E',      # Gray for baselines
    }
    
    def __init__(self, dpi: int = 100, figsize: Tuple[int, int] = (6, 3)):
        """
        Initialize chart generator.
        
        Args:
            dpi: Image resolution (100 = web, 150 = print quality)
            figsize: Figure size in inches (width, height)
        """
        self.dpi = dpi
        self.figsize = figsize
        plt.style.use('seaborn-v0_8-whitegrid')
    
    def generate_heart_rate_chart(
        self, 
        dates: List[str], 
        values: List[int],
        resting_hr: Optional[int] = None
    ) -> str:
        """
        Generate heart rate trend chart.
        
        Args:
            dates: List of date strings (YYYY-MM-DD)
            values: Heart rate values (BPM)
            resting_hr: Optional resting heart rate baseline
            
        Returns:
            Base64-encoded PNG image
        """
        try:
            fig, ax = plt.subplots(figsize=self.figsize)
            
            # Convert dates to datetime objects
            date_objects = [datetime.strptime(d, '%Y-%m-%d') for d in dates]
            
            # Plot heart rate line
            ax.plot(
                date_objects, 
                values, 
                color=self.COLORS['primary'],
                marker='o',
                linewidth=2,
                markersize=6,
                label='Heart Rate'
            )
            
            # Add resting heart rate baseline
            if resting_hr:
                ax.axhline(
                    y=resting_hr, 
                    color=self.COLORS['neutral'],
                    linestyle='--', 
                    alpha=0.5,
                    label=f'Resting HR: {resting_hr} BPM'
                )
            
            # Formatting
            ax.set_title('Heart Rate Trend (Last 7 Days)', fontsize=12, fontweight='bold')
            ax.set_xlabel('Date', fontsize=10)
            ax.set_ylabel('Heart Rate (BPM)', fontsize=10)
            ax.legend(loc='upper right', fontsize=8)
            ax.grid(True, alpha=0.3)
            
            # Format x-axis dates
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            plt.xticks(rotation=45, ha='right')
            
            plt.tight_layout()
            
            return self._to_base64(fig)
            
        except Exception as e:
            logger.error(f"Heart rate chart generation failed: {e}")
            return ""
    
    def generate_activity_bar_chart(
        self, 
        days: List[str], 
        steps: List[int],
        goal: int = 10000
    ) -> str:
        """
        Generate daily steps bar chart.
        
        Args:
            days: Day labels (e.g., ['Mon', 'Tue', ...])
            steps: Daily step counts
            goal: Daily step goal
            
        Returns:
            Base64-encoded PNG image
        """
        try:
            fig, ax = plt.subplots(figsize=self.figsize)
            
            # Color bars based on goal achievement
            colors = [
                self.COLORS['success'] if s >= goal else self.COLORS['warning'] 
                for s in steps
            ]
            
            bars = ax.bar(days, steps, color=colors, alpha=0.8, edgecolor='black', linewidth=0.5)
            
            # Add goal line
            ax.axhline(
                y=goal, 
                color=self.COLORS['neutral'],
                linestyle='--', 
                alpha=0.5,
                label=f'Goal: {goal:,} steps'
            )
            
            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2., 
                    height,
                    f'{int(height):,}',
                    ha='center', 
                    va='bottom',
                    fontsize=8
                )
            
            # Formatting
            ax.set_title('Daily Steps', fontsize=12, fontweight='bold')
            ax.set_xlabel('Day', fontsize=10)
            ax.set_ylabel('Steps', fontsize=10)
            ax.legend(loc='upper right', fontsize=8)
            ax.grid(True, alpha=0.3, axis='y')
            
            # Format y-axis with comma separators
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
            
            plt.tight_layout()
            
            return self._to_base64(fig)
            
        except Exception as e:
            logger.error(f"Activity chart generation failed: {e}")
            return ""
    
    def generate_blood_pressure_chart(
        self,
        dates: List[str],
        systolic: List[int],
        diastolic: List[int]
    ) -> str:
        """
        Generate blood pressure dual-line chart.
        
        Args:
            dates: Date strings (YYYY-MM-DD)
            systolic: Systolic pressure values
            diastolic: Diastolic pressure values
            
        Returns:
            Base64-encoded PNG image
        """
        try:
            fig, ax = plt.subplots(figsize=self.figsize)
            
            date_objects = [datetime.strptime(d, '%Y-%m-%d') for d in dates]
            
            # Plot both lines
            ax.plot(
                date_objects, 
                systolic, 
                color=self.COLORS['danger'],
                marker='o',
                linewidth=2,
                label='Systolic'
            )
            ax.plot(
                date_objects, 
                diastolic, 
                color=self.COLORS['info'],
                marker='s',
                linewidth=2,
                label='Diastolic'
            )
            
            # Add reference zones
            ax.axhspan(120, 130, alpha=0.1, color='yellow', label='Elevated')
            ax.axhspan(130, 180, alpha=0.1, color='red', label='High')
            
            # Formatting
            ax.set_title('Blood Pressure Trend', fontsize=12, fontweight='bold')
            ax.set_xlabel('Date', fontsize=10)
            ax.set_ylabel('mmHg', fontsize=10)
            ax.legend(loc='upper right', fontsize=8)
            ax.grid(True, alpha=0.3)
            
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            plt.xticks(rotation=45, ha='right')
            
            plt.tight_layout()
            
            return self._to_base64(fig)
            
        except Exception as e:
            logger.error(f"Blood pressure chart generation failed: {e}")
            return ""
    
    def generate_medication_gauge(
        self,
        adherence_percent: float,
        total_doses: int,
        taken_doses: int
    ) -> str:
        """
        Generate medication adherence gauge chart.
        
        Args:
            adherence_percent: Adherence percentage (0-100)
            total_doses: Total scheduled doses
            taken_doses: Doses taken
            
        Returns:
            Base64-encoded PNG image
        """
        try:
            fig, ax = plt.subplots(figsize=(4, 4), subplot_kw={'projection': 'polar'})
            
            # Gauge parameters
            theta = (adherence_percent / 100) * 180  # Half circle
            
            # Draw gauge arc
            angles = [0, theta, 180]
            colors = ['green' if adherence_percent >= 80 else 'yellow' if adherence_percent >= 60 else 'red']
            
            ax.barh(
                0, 
                theta * (3.14159 / 180),
                left=0,
                height=0.3,
                color=colors[0],
                alpha=0.7
            )
            
            # Add percentage text
            ax.text(
                0, 0, 
                f'{adherence_percent:.0f}%',
                ha='center', 
                va='center',
                fontsize=24,
                fontweight='bold'
            )
            
            ax.text(
                0, -0.5,
                f'{taken_doses}/{total_doses} doses',
                ha='center',
                fontsize=10
            )
            
            ax.set_ylim(-1, 1)
            ax.set_theta_zero_location('W')
            ax.set_theta_direction(1)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.spines['polar'].set_visible(False)
            
            plt.title('Medication Adherence', fontsize=12, fontweight='bold', pad=20)
            plt.tight_layout()
            
            return self._to_base64(fig)
            
        except Exception as e:
            logger.error(f"Medication gauge generation failed: {e}")
            return ""
    
    def _to_base64(self, fig) -> str:
        """
        Convert matplotlib figure to base64 string.
        
        Args:
            fig: Matplotlib figure object
            
        Returns:
            Base64-encoded PNG
        """
        try:
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=self.dpi, bbox_inches='tight')
            plt.close(fig)  # Free memory
            buf.seek(0)
            return base64.b64encode(buf.getvalue()).decode('utf-8')
        except Exception as e:
            logger.error(f"Base64 conversion failed: {e}")
            return ""


# Singleton instance
_chart_generator: Optional[ChartGenerator] = None

def get_chart_generator() -> ChartGenerator:
    """Get singleton chart generator."""
    global _chart_generator
    if _chart_generator is None:
        _chart_generator = ChartGenerator()
    return _chart_generator