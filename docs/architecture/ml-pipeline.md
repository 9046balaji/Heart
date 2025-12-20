# 🤖 ML Pipeline Architecture

## Overview

The ML pipeline provides intelligent anomaly detection for smartwatch health data with natural language explanations and chatbot integration.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ML Anomaly Detection Pipeline                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Smartwatch Data                                                         │
│       │                                                                  │
│       ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                   Feature Extractor                              │    │
│  │   - Statistical features (mean, std, min, max, percentiles)     │    │
│  │   - Time-based patterns                                          │    │
│  │   - Trend analysis                                               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│       │                                                                  │
│       ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                   Anomaly Detector                               │    │
│  │   - Isolation Forest (sklearn)                                   │    │
│  │   - Configurable contamination threshold                         │    │
│  │   - Anomaly scores (-1 to 1)                                     │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│       │                                                                  │
│       ├───────────────────────────┐                                     │
│       ▼                           ▼                                     │
│  ┌─────────────┐           ┌─────────────┐                              │
│  │    Rule     │           │   Health    │                              │
│  │   Engine    │           │  Explainer  │                              │
│  │ (thresholds)│           │ (NL output) │                              │
│  └─────────────┘           └─────────────┘                              │
│       │                           │                                     │
│       └───────────┬───────────────┘                                     │
│                   ▼                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                   Alert Pipeline                                 │    │
│  │   - Priority classification (CRITICAL, HIGH, MEDIUM, LOW)       │    │
│  │   - Recommendation generation                                    │    │
│  │   - Action suggestions                                           │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│       │                                                                  │
│       ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                   Chatbot Connector                              │    │
│  │   - Gemini/Ollama integration                                    │    │
│  │   - Context-aware responses                                      │    │
│  │   - Prompt templates                                             │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Feature Extractor (`feature_extractor.py`)

Extracts meaningful features from raw smartwatch time-series data:

```python
class WatchDataFeatureExtractor:
    def extract_features(self, data: WatchData) -> Dict[str, float]:
        return {
            'heart_rate_mean': ...,
            'heart_rate_std': ...,
            'heart_rate_min': ...,
            'heart_rate_max': ...,
            'steps_total': ...,
            'sleep_quality_score': ...,
            'activity_variance': ...,
        }
```

**Features Extracted:**
- Heart rate statistics (mean, std, min, max, percentiles)
- Step count patterns
- Sleep quality metrics
- Activity level indicators
- HRV (Heart Rate Variability) if available

### 2. Anomaly Detector (`anomaly_detector.py`)

Uses Isolation Forest for unsupervised anomaly detection:

```python
class AnomalyDetector:
    def __init__(self, contamination: float = 0.1):
        self.model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100
        )

    def detect(self, features: np.ndarray) -> AnomalyResult:
        score = self.model.decision_function(features)
        is_anomaly = self.model.predict(features) == -1
        return AnomalyResult(is_anomaly=is_anomaly, score=score)
```

**Key Parameters:**
- `contamination`: Expected proportion of anomalies (default: 0.1)
- `n_estimators`: Number of trees in the forest (default: 100)

### 3. Rule Engine (`rule_engine.py`)

Clinical threshold-based rules for health metrics:

```python
HEALTH_RULES = {
    'heart_rate': {
        'critical_low': 40,
        'low': 50,
        'normal_low': 60,
        'normal_high': 100,
        'high': 120,
        'critical_high': 150
    },
    'blood_pressure_systolic': {
        'critical_low': 70,
        'low': 90,
        'normal_high': 120,
        'elevated': 130,
        'high': 140,
        'critical_high': 180
    }
}
```

### 4. Health Explainer (`health_explainer.py`)

Generates natural language explanations for anomalies:

```python
class HealthExplainer:
    def explain(self, anomaly: AnomalyResult, features: Dict) -> str:
        """
        Returns: "Your heart rate of 145 bpm is elevated.
                  This could indicate physical exertion or stress.
                  Consider resting and monitoring."
        """
```

### 5. Alert Pipeline (`alert_pipeline.py`)

Coordinates detection, explanation, and notification:

```python
class AlertPipeline:
    def process(self, watch_data: WatchData) -> Alert:
        features = self.feature_extractor.extract(watch_data)
        anomaly = self.detector.detect(features)
        explanation = self.explainer.explain(anomaly, features)
        priority = self.classify_priority(anomaly)
        recommendations = self.generate_recommendations(anomaly)

        return Alert(
            priority=priority,
            explanation=explanation,
            recommendations=recommendations,
            raw_data=watch_data
        )
```

**Priority Levels:**
| Priority | Criteria | Response Time |
|----------|----------|---------------|
| CRITICAL | Life-threatening values | Immediate |
| HIGH | Significant deviation | Within 1 hour |
| MEDIUM | Notable change | Within 24 hours |
| LOW | Minor variation | Informational |

### 6. Chatbot Connector (`chatbot_connector.py`)

Integrates with AI providers for contextual responses:

```python
class ChatbotConnector:
    def __init__(self, provider: str = "gemini"):
        self.provider = provider  # "gemini" or "ollama"

    async def get_response(self, alert: Alert, user_query: str) -> str:
        prompt = self.build_prompt(alert, user_query)
        return await self.call_ai(prompt)
```

### 7. Prompt Templates (`prompt_templates.py`)

Healthcare-specific prompt engineering:

```python
ALERT_PROMPT = """
You are a healthcare AI assistant analyzing smartwatch data.

Alert Information:
- Priority: {priority}
- Anomaly Type: {anomaly_type}
- Affected Metrics: {metrics}

Patient Query: {query}

Provide a helpful, medically-informed response that:
1. Acknowledges the concern
2. Explains the data in simple terms
3. Suggests appropriate actions
4. Recommends when to seek medical help
"""
```

## Model Files

Located in `cardio-ai-assistant/backend/models/`:

| File | Purpose |
|------|---------|
| `stacking_ensemble_model.joblib` | Heart disease prediction |
| `stacking_heart_disease_model.joblib` | Alternative ensemble |
| `fitted_mlp_model.joblib` | Neural network model |

## Usage Example

```python
from ml.alert_pipeline import AlertPipeline
from ml.chatbot_connector import ChatbotConnector

# Initialize pipeline
pipeline = AlertPipeline()
connector = ChatbotConnector(provider="gemini")

# Process smartwatch data
watch_data = WatchData(
    heart_rate=[72, 75, 145, 142, 78],  # Spike detected
    steps=[1000, 1200, 500, 800],
    timestamp=datetime.now()
)

# Get alert
alert = pipeline.process(watch_data)
# Alert: HIGH priority - Heart rate spike detected

# Get AI response
response = await connector.get_response(
    alert=alert,
    user_query="Why did my heart rate spike?"
)
# Response: "Your heart rate increased from ~75 to 145 bpm..."
```

## Configuration

```python
# ml/__init__.py
ML_CONFIG = {
    'anomaly_detector': {
        'contamination': 0.1,
        'n_estimators': 100
    },
    'rule_engine': {
        'use_custom_thresholds': True,
        'threshold_file': 'config/thresholds.json'
    },
    'chatbot': {
        'default_provider': 'gemini',
        'fallback_provider': 'ollama',
        'timeout': 30
    }
}
```

## Testing

```bash
cd cardio-ai-assistant/backend
python test_ml.py
```

Test coverage:
- Feature extraction accuracy
- Anomaly detection precision/recall
- Rule engine threshold validation
- Explanation quality
- Chatbot integration
