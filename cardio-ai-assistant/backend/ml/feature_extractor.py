"""
Feature Extractor for Watch Data
Converts raw sensor readings into ML-ready features.

This module maintains a rolling window of health data and extracts
statistical features that can be used by the ML model for anomaly detection.
"""

import numpy as np
from typing import List, Optional
from dataclasses import dataclass
from collections import deque
import statistics


@dataclass
class HealthFeatures:
    """Extracted features from raw health data."""
    # Heart Rate Features
    hr_current: float
    hr_mean_5min: float
    hr_std_5min: float
    hr_min_5min: float
    hr_max_5min: float
    hr_trend: float  # positive = increasing, negative = decreasing
    
    # Heart Rate Variability (HRV)
    hrv_sdnn: float  # Standard deviation of NN intervals
    hrv_rmssd: float  # Root mean square of successive differences
    
    # Blood Oxygen Features
    spo2_current: float
    spo2_mean_5min: float
    spo2_min_5min: float
    
    # Activity Context
    steps_last_5min: int
    is_resting: bool  # True if steps < 10 in last 5 min
    
    # Derived Features
    hr_spo2_ratio: float  # HR / SpO2 (higher = more stress)
    anomaly_score: float = 0.0  # Filled by model


class FeatureExtractor:
    """
    Maintains a rolling window of health data and extracts features.
    
    The extractor buffers incoming sensor readings and computes statistical
    features over the window when requested. This enables the ML model to
    detect patterns over time, not just instant threshold violations.
    
    Attributes:
        window_size: Number of samples to keep in the rolling buffer
        hr_buffer: Rolling buffer for heart rate values
        spo2_buffer: Rolling buffer for blood oxygen values
        steps_buffer: Rolling buffer for step count values
        ibi_buffer: Rolling buffer for inter-beat interval values
    
    Example:
        extractor = FeatureExtractor(window_size=300)  # 5 min at 1 sample/sec
        
        # Add samples as they come in
        extractor.add_sample(hr=72, spo2=98, steps=0)
        extractor.add_sample(hr=75, spo2=97, steps=5)
        
        # Extract features when you have enough data
        features = extractor.extract_features()
        if features:
            print(f"Current HR: {features.hr_current}")
            print(f"Is resting: {features.is_resting}")
    """
    
    def __init__(self, window_size: int = 300):  # 5 minutes at 1 sample/sec
        """
        Initialize the feature extractor.
        
        Args:
            window_size: Number of samples to keep in the rolling window.
                        Default is 300 (5 minutes at 1 sample per second).
        """
        self.window_size = window_size
        
        # Rolling buffers using deque for O(1) append and auto-truncation
        self.hr_buffer: deque = deque(maxlen=window_size)
        self.spo2_buffer: deque = deque(maxlen=window_size)
        self.steps_buffer: deque = deque(maxlen=window_size)
        self.ibi_buffer: deque = deque(maxlen=window_size)  # Inter-beat intervals
        
    def add_sample(
        self, 
        hr: float, 
        spo2: float = 98.0, 
        steps: int = 0, 
        ibi: float = None
    ) -> None:
        """
        Add a new sample to the rolling window.
        
        Args:
            hr: Heart rate in beats per minute
            spo2: Blood oxygen saturation percentage (default: 98.0)
            steps: Step count in this sample period (default: 0)
            ibi: Inter-beat interval in milliseconds (optional).
                 If not provided, it will be estimated from HR.
        """
        self.hr_buffer.append(hr)
        self.spo2_buffer.append(spo2)
        self.steps_buffer.append(steps)
        
        if ibi is not None:
            self.ibi_buffer.append(ibi)
        elif hr > 0:
            # Estimate IBI from HR if not provided
            # IBI (ms) = 60000 / HR (bpm)
            self.ibi_buffer.append(60000 / hr)
    
    def extract_features(self) -> Optional[HealthFeatures]:
        """
        Extract features from the current buffer.
        
        Returns:
            HealthFeatures object if we have enough data (at least 30 samples),
            None otherwise.
        """
        if len(self.hr_buffer) < 30:  # Need at least 30 seconds
            return None
        
        hr_list = list(self.hr_buffer)
        spo2_list = list(self.spo2_buffer)
        steps_list = list(self.steps_buffer)
        ibi_list = list(self.ibi_buffer)
        
        # Heart Rate Features
        hr_current = hr_list[-1]
        hr_mean = statistics.mean(hr_list)
        hr_std = statistics.stdev(hr_list) if len(hr_list) > 1 else 0
        hr_min = min(hr_list)
        hr_max = max(hr_list)
        
        # HR Trend (linear regression slope over last minute)
        hr_trend = self._calculate_trend(hr_list[-60:])
        
        # HRV Features (if we have IBI data)
        hrv_sdnn = 0.0
        hrv_rmssd = 0.0
        if len(ibi_list) > 10:
            hrv_sdnn = statistics.stdev(ibi_list)
            # RMSSD: Root Mean Square of Successive Differences
            successive_diffs = [
                abs(ibi_list[i+1] - ibi_list[i]) 
                for i in range(len(ibi_list)-1)
            ]
            if successive_diffs:
                hrv_rmssd = np.sqrt(np.mean(np.square(successive_diffs)))
        
        # SpO2 Features
        spo2_current = spo2_list[-1]
        spo2_mean = statistics.mean(spo2_list)
        spo2_min = min(spo2_list)
        
        # Activity Features
        steps_5min = sum(steps_list)
        is_resting = steps_5min < 10
        
        # Derived Features
        hr_spo2_ratio = hr_current / spo2_current if spo2_current > 0 else 0
        
        return HealthFeatures(
            hr_current=hr_current,
            hr_mean_5min=hr_mean,
            hr_std_5min=hr_std,
            hr_min_5min=hr_min,
            hr_max_5min=hr_max,
            hr_trend=hr_trend,
            hrv_sdnn=hrv_sdnn,
            hrv_rmssd=hrv_rmssd,
            spo2_current=spo2_current,
            spo2_mean_5min=spo2_mean,
            spo2_min_5min=spo2_min,
            steps_last_5min=steps_5min,
            is_resting=is_resting,
            hr_spo2_ratio=hr_spo2_ratio
        )
    
    def _calculate_trend(self, values: List[float]) -> float:
        """
        Calculate linear trend (slope) of values.
        
        Uses simple linear regression to compute the slope of the values
        over the given window. Positive slope means increasing, negative
        means decreasing.
        
        Args:
            values: List of numeric values to analyze
            
        Returns:
            Slope of the linear fit (units per sample)
        """
        if len(values) < 2:
            return 0.0
        
        x = np.arange(len(values))
        y = np.array(values)
        
        # Simple linear regression using numpy polyfit
        slope = np.polyfit(x, y, 1)[0]
        return float(slope)
    
    def to_model_input(self, features: HealthFeatures) -> np.ndarray:
        """
        Convert features to numpy array for ML model.
        
        The ML model expects a specific order of features. This method
        ensures the features are in the correct format.
        
        Args:
            features: HealthFeatures object to convert
            
        Returns:
            Numpy array of shape (1, 14) ready for model prediction
        """
        return np.array([
            features.hr_current,
            features.hr_mean_5min,
            features.hr_std_5min,
            features.hr_min_5min,
            features.hr_max_5min,
            features.hr_trend,
            features.hrv_sdnn,
            features.hrv_rmssd,
            features.spo2_current,
            features.spo2_mean_5min,
            features.spo2_min_5min,
            features.steps_last_5min,
            1.0 if features.is_resting else 0.0,
            features.hr_spo2_ratio
        ]).reshape(1, -1)
    
    def clear(self) -> None:
        """Clear all buffers."""
        self.hr_buffer.clear()
        self.spo2_buffer.clear()
        self.steps_buffer.clear()
        self.ibi_buffer.clear()
    
    def get_buffer_size(self) -> int:
        """Get the current number of samples in the buffer."""
        return len(self.hr_buffer)
    
    def is_ready(self) -> bool:
        """Check if we have enough samples for feature extraction."""
        return len(self.hr_buffer) >= 30
