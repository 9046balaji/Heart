# HeartGuard NLP Microservice

Advanced Natural Language Processing service for the HeartGuard chatbot, built with Python FastAPI.

## Overview

This microservice provides enterprise-grade NLP capabilities for the HeartGuard chatbot:

- **Intent Recognition**: 10+ predefined medical intents with context awareness
- **Sentiment Analysis**: Detect user emotional state (positive, neutral, negative, distressed, urgent)
- **Entity Extraction**: Identify symptoms, medications, foods, measurements, and time references
- **Risk Assessment**: Framingham Risk Score algorithm for cardiovascular disease risk
- **Emergency Detection**: Immediate identification of critical situations
- **RAG Pipeline**: Semantic search over medical knowledge base
- **Memory System**: Patient-specific context management (Memori)
- **AI Agents**: Orchestrated health and cardiology specialist agents
- **Real-time WebSocket**: Live communication support
- **Compliance**: HIPAA-compliant audit logging and consent management
- **Document Scanning**: OCR-based medical document processing
- **Calendar Integration**: Google Calendar & Outlook sync
- **Knowledge Graph**: Neo4j-powered medical entity relationships
- **Notifications**: WhatsApp, Email, and Push notification delivery
- **Health Tools**: LLM function calling with health calculators
- **Vision Analysis**: ECG analysis and food recognition

## Architecture

```
NLP Service (Python FastAPI) - Port 5001
├── Core Engines (engines/)
│   ├── Intent Recognizer (TF-IDF + keyword matching)
│   ├── Sentiment Analyzer (VADER-based)
│   ├── Entity Extractor (SpaCy PhraseMatcher)
│   └── Risk Assessor (Framingham + ML models)
├── Memory System (memori/)
│   ├── Context Retrieval
│   ├── User Preferences
│   ├── Chat History
│   └── Session Management
├── RAG Pipeline (rag/)
│   ├── Embedding Service
│   ├── Vector Store
│   └── Knowledge Base
├── AI Agents (agents/)
│   ├── Health Agent
│   ├── Cardio Specialist
│   ├── Orchestrator
│   └── Task Executor
├── Medical AI (medical_ai/)
│   ├── MedGemma Service
│   ├── Multimodal Processor
│   └── Terminology Normalizer
├── Document Scanning (document_scanning/)
│   ├── OCR Engine
│   ├── Classifier
│   └── Ingestion Pipeline
├── Compliance (compliance/)
│   ├── Audit Logger
│   ├── Consent Manager
│   └── Encryption Service
├── Real-time (realtime/)
│   ├── WebSocket Handler
│   └── Event Bus
├── Calendar Integration (calendar_integration/)
│   ├── Google Calendar
│   ├── Outlook Calendar
│   └── Appointment Sync
├── Knowledge Graph (knowledge_graph/)
│   ├── Graph Store (Neo4j)
│   ├── Entity Manager
│   └── Query Engine
├── Notifications (notifications/)
│   ├── WhatsApp Service
│   ├── Email Service
│   └── Push Service
├── Health Tools (tools/)
│   ├── Tool Registry
│   ├── BP Calculator
│   ├── BMI Calculator
│   └── Heart Rate Zones
├── Vision Analysis (vision/)
│   ├── ECG Analyzer
│   ├── Food Recognizer
│   └── Vision Service
└── Integrations (integrations/)
    ├── Timeline Service
    ├── Weekly Aggregation
    └── Doctor Dashboard
```

## Tech Stack

- **Framework**: FastAPI (Python 3.10+)
- **NLP**: VADER, spaCy
- **AI**: Google Gemini, Ollama (local)
- **Data Validation**: Pydantic
- **Server**: Uvicorn
- **Rate Limiting**: SlowAPI
- **Containerization**: Docker & Docker Compose

## Installation

### Prerequisites

- Python 3.10+ (3.11 recommended)
- pip (Python package manager)
- (Optional) Docker and Docker Compose
- (Optional) Ollama for local AI inference

### Local Setup

1. **Navigate to nlp-service directory**:
```bash
cd nlp-service
```

2. **Create virtual environment**:
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

3. **Copy environment file**:
```bash
cp .env.example .env
```

4. **Install dependencies**:
```bash
pip install -r requirements.txt
```

5. **Download spaCy model**:
```bash
python -m spacy download en_core_web_sm
```

6. **Run the service**:
```bash
python main.py
```

The service will be available at `http://localhost:5001`

### Docker Setup

1. **Build and run with Docker Compose**:
```bash
docker-compose up -d
```

2. **View logs**:
```bash
docker-compose logs -f nlp-service
```

3. **Stop service**:
```bash
docker-compose down
```

## API Route Groups

The NLP service mounts multiple routers, each conditionally loaded based on available dependencies:

| Route Group | Prefix | Status | Description |
|-------------|--------|--------|-------------|
| Core | `/` | Always On | Health, cache, analytics, NLP process |
| RAG | `/api/rag` | Conditional | Semantic search, knowledge base |
| Memory | `/api/memory` | Conditional | User preferences, context retrieval |
| Agents | `/api/agents` | Conditional | ADK agent orchestration |
| Documents | `/api/documents` | Conditional | Document scanning, OCR |
| Medical AI | `/api/medical-ai` | Conditional | MedGemma integration |
| Weekly Summary | `/api/weekly-summary` | Conditional | Health summaries |
| Consent | `/api/consent` | Conditional | Consent management |
| Webhooks | `/api/webhooks` | Conditional | Twilio, SendGrid |
| Integrations | `/api/integrations` | Conditional | External system integrations |
| Compliance | `/api/compliance` | Conditional | Audit, verification |
| Calendar | `/api/calendar` | Conditional | Google/Outlook calendar sync |
| Knowledge Graph | `/api/knowledge-graph` | Conditional | Neo4j graph queries |
| Notifications | `/api/notifications` | Conditional | WhatsApp, Email, Push |
| Tools | `/api/tools` | Conditional | LLM function calling |
| Vision | `/api/vision` | Conditional | ECG, food recognition |
| WebSocket | `/ws` | Conditional | Real-time communication |
| Ollama | `/ollama-*` | Always On | Local LLM generation |
| Structured Outputs | `/api/structured-outputs` | Conditional | Schema-guided responses |

## API Endpoints

### 1. Health Check
```
GET /health
```
**Response**: Service status and loaded models

### 2. Cache Statistics
```
GET /cache/stats
```
**Response**: Cache hit/miss statistics and memory usage

### 3. Analytics Endpoints
```
GET /analytics/summary
```
**Response**: Comprehensive analytics summary

```
GET /analytics/intents
```
**Response**: Intent distribution statistics

```
GET /analytics/sentiments
```
**Response**: Sentiment distribution statistics

```
GET /analytics/entities
```
**Response**: Entity type distribution statistics

```
GET /analytics/top-intents
```
**Response**: Most common intents

```
GET /analytics/top-entities
```
**Response**: Most common entity types

### 4. Model Management Endpoints
```
GET /models/versions
```
**Response**: Current versions of all models

```
GET /models/history/{model_name}
```
**Response**: Version history for a specific model

```
POST /models/version/{model_name}?version={version}
```
**Response**: Set the version of a specific model

```
POST /models/rollback/{model_name}
```
**Response**: Rollback to the previous version of a specific model

```
GET /models/list
```
**Response**: List all available models and their versions

```
POST /models/ab-test/{model_name}?version_a={version_a}&version_b={version_b}&split_ratio={split_ratio}
```
**Response**: Enable A/B testing between two versions of a model

### 2. Process NLP
```
POST /api/nlp/process
```

**Request**:
```json
{
  "message": "I'm experiencing severe chest pain",
  "session_id": "session-123",
  "user_id": "user-456",
  "context": {
    "previous_symptoms": ["fatigue"]
  }
}
```

**Response**:
```json
{
  "intent": "symptom_check",
  "intent_confidence": 0.95,
  "sentiment": "distressed",
  "sentiment_score": -0.85,
  "entities": [
    {
      "type": "symptom",
      "value": "chest pain",
      "start_index": 24,
      "end_index": 34,
      "confidence": 0.95
    }
  ],
  "keywords_matched": ["pain", "symptom"],
  "suggested_response": "I'm concerned...",
  "requires_escalation": true,
  "confidence_overall": 0.92
}
```

### 3. Assess Risk
```
POST /api/risk/assess
```

**Request**:
```json
{
  "metrics": {
    "age": 55,
    "gender": "M",
    "blood_pressure_systolic": 140,
    "blood_pressure_diastolic": 90,
    "cholesterol_total": 250,
    "smoking_status": "former",
    "diabetes": false,
    "family_history_heart_disease": true,
    "physical_activity_minutes_per_week": 120
  },
  "user_id": "user-456"
}
```

**Response**:
```json
{
  "risk_level": "MODERATE",
  "risk_score": 18.5,
  "risk_interpretation": "Your cardiovascular risk is moderate...",
  "recommendations": [
    "Reduce sodium intake to less than 2,300mg per day",
    "Follow a heart-healthy diet...",
    "Schedule consultation with cardiologist..."
  ],
  "consultation_urgency": "RECOMMENDED_WITHIN_MONTH"
}
```

### 4. Extract Entities
```
POST /api/entities/extract
```

**Request**:
```json
{
  "text": "I take aspirin 100mg daily and I'm experiencing shortness of breath",
  "entity_types": ["medication", "symptom"]
}
```

**Response**:
```json
{
  "entities": [
    {
      "type": "medication",
      "value": "aspirin",
      "start_index": 7,
      "end_index": 14
    },
    {
      "type": "symptom",
      "value": "shortness of breath",
      "start_index": 47,
      "end_index": 66
    }
  ]
}
```

## Intents Supported

| Intent | Keywords | Context |
|--------|----------|---------|
| `greeting` | hello, hi, hey | User greeting |
| `emergency` | help, 911, severe | Critical situation |
| `symptom_check` | pain, feel, hurt | Medical symptoms |
| `medication_reminder` | medication, pill, dose | Medication management |
| `risk_assessment` | risk, heart disease | Risk calculation |
| `nutrition_advice` | eat, food, meal | Dietary guidance |
| `exercise_coaching` | exercise, workout, fitness | Physical activity |
| `health_goal` | goal, target, achieve | Goal setting |
| `health_education` | learn, teach, information | Education request |
| `appointment_booking` | appointment, doctor, schedule | Appointment request |

## Entity Types

| Type | Examples | Pattern |
|------|----------|---------|
| `symptom` | chest pain, shortness of breath | Keyword matching |
| `medication` | aspirin, lisinopril | Drug database |
| `food` | olive oil, salmon, nuts | Healthy food list |
| `measurement` | 140/90 mmHg, 180 lbs | Regex patterns |
| `duration` | 2 days, 3 weeks | Time expressions |
| `time_reference` | today, tomorrow, Monday | Temporal markers |

## Sentiment Types

| Sentiment | Score Range | Intensity | Use Case |
|-----------|------------|-----------|----------|
| `positive` | 0.6 to 1.0 | mild, moderate, strong, very_strong | Good health news |
| `neutral` | -0.4 to 0.6 | moderate | Factual questions |
| `negative` | -1.0 to -0.4 | mild, moderate, strong, very_strong | Health concerns |
| `distressed` | ≤ -0.7 | severe | Emotional distress |
| `urgent` | ≥ 0.8 | severe | Critical situation |

## Risk Assessment

### Algorithm

Uses the **Framingham Risk Score** as the base calculation:

1. **Age Factor** (strongest predictor): 0-20 points
2. **Blood Pressure**: 0-15 points
3. **Cholesterol**: 0-10 points
4. **LDL/HDL Ratio**: 0-10 points
5. **Smoking Status**: 0-15 points (current smokers)
6. **Diabetes**: 0-15 points
7. **Family History**: 0-10 points
8. **Physical Activity**: -10 points (protective)

### Risk Levels

- **LOW** (< 10%): Normal annual checkups
- **MODERATE** (10-20%): Lifestyle modifications
- **HIGH** (> 20%): Immediate medical consultation

## Configuration

Edit `.env` file to customize:

```env
# Service
NLP_SERVICE_PORT=5000
LOG_LEVEL=INFO

# Models
SPACY_MODEL=en_core_web_sm
USE_GPU=false

# Transformer Models
USE_TRANSFORMER_MODELS=false
TRANSFORMER_MODEL_NAME=bert-base-uncased

# ML Models
USE_ML_RISK_MODELS=false
ML_RISK_MODEL_TYPE=random_forest

# Thresholds
INTENT_CONFIDENCE_THRESHOLD=0.5
SENTIMENT_THRESHOLD_POSITIVE=0.6
SENTIMENT_THRESHOLD_URGENT=0.8
```

## Integration with TypeScript Backend

See `../chatbot/backend/services/nlpService.ts` for integration example.

### Quick Integration

```typescript
const nlpResult = await axios.post('http://nlp-service:5000/api/nlp/process', {
  message: userInput,
  session_id: sessionId,
  context: chatContext
});

const { intent, sentiment, entities, suggests_escalation } = nlpResult.data;
```

## ML Risk Models

The NLP service supports ML-based models for enhanced risk assessment:

- **Scikit-learn Integration**: Use Random Forest, Gradient Boosting, and Logistic Regression models
- **Configurable Models**: Switch between different ML algorithms
- **Fallback Mechanism**: Automatically fall back to Framingham Risk Score if ML models fail
- **Environment Configuration**: Control ML usage via `USE_ML_RISK_MODELS` environment variable

## Transformer Models

The NLP service supports transformer-based models for improved intent recognition:

- **BERT/RoBERTa Integration**: Use state-of-the-art transformer models for intent classification
- **Configurable Models**: Switch between different transformer architectures
- **Fallback Mechanism**: Automatically fall back to keyword-based recognition if transformers fail
- **Environment Configuration**: Control transformer usage via `USE_TRANSFORMER_MODELS` environment variable

## Model Versioning

The NLP service supports model versioning for all components:

- **Version Management**: Track and control versions of all NLP models
- **A/B Testing**: Compare different model versions with configurable traffic splitting
- **Rollback Capability**: Revert to previous model versions when needed
- **Version History**: Maintain complete history of model version changes
- **API Endpoints**: Manage models via `/models/*` endpoints

## Analytics

The NLP service tracks usage patterns and performance metrics:

- **Intent Distribution**: Tracks frequency of different intent types
- **Sentiment Analysis**: Monitors user sentiment patterns
- **Entity Extraction**: Records entity type frequencies
- **Performance Metrics**: Measures processing times and request rates
- **Session Tracking**: Follows user session patterns
- **API Endpoints**: Access analytics data via `/analytics/*` endpoints

## Caching

The NLP service implements an in-memory caching layer to improve performance for repeated requests:

- **Entity Extraction**: Cached for 1 hour
- **Intent Recognition**: Cached for 1 hour
- **LRU Eviction**: Automatically removes least recently used items
- **Cache Statistics**: Available via `/cache/stats` endpoint

## Performance

- **Intent Recognition**: < 100ms
- **Sentiment Analysis**: < 50ms
- **Entity Extraction**: < 150ms
- **Risk Assessment**: < 100ms
- **Total NLP Processing**: < 400ms
- **Cached Requests**: < 10ms

## Testing

### Unit Tests

Run unit tests for all components:

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all unit tests
python -m pytest tests/ -v

# Run specific test module
python -m pytest tests/test_intent_recognizer.py -v

# Run tests with coverage report
python -m pytest tests/ --cov=. --cov-report=html --cov-report=term
```

Test categories include:
- Intent recognition accuracy
- Sentiment analysis correctness
- Entity extraction completeness
- Risk assessment calculations
- Performance benchmarks

### Integration Tests

Integration tests verify the API endpoints (requires service to be running):

```bash
# Start the service first
python main.py

# In another terminal, run integration tests
python -m pytest tests/test_api_endpoints.py -v
```

### Test Documentation

See [tests/README.md](tests/README.md) for detailed information about:
- Test structure and organization
- Running tests with different options
- Adding new tests
- Continuous integration setup

## Logging

Logs are written to:
- Console (INFO and above)
- `nlp_service.log` file

Adjust log level in `.env`:
```env
LOG_LEVEL=DEBUG    # More verbose
LOG_LEVEL=WARNING  # Less verbose
```

## Production Deployment

### Using Docker Compose (Recommended)

```bash
# Build production image
docker-compose -f docker-compose.yml build --no-cache

# Run services
docker-compose up -d

# Monitor
docker-compose logs -f nlp-service
```

### Environment Variables for Production

```env
NLP_SERVICE_PORT=5000
NLP_SERVICE_HOST=0.0.0.0
LOG_LEVEL=INFO
USE_GPU=false
CORS_ORIGINS=https://chatbot.example.com,https://api.example.com
```

## Troubleshooting

### Issue: ModuleNotFoundError for dependencies

**Solution**:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Issue: spaCy model not found

**Solution**:
```bash
python -m spacy download en_core_web_sm
```

### Issue: Port 5000 already in use

**Solution**:
```bash
# Change port in .env
NLP_SERVICE_PORT=5001
```

## Future Enhancements

1. **Advanced Transformer Models**: Fine-tune BERT/RoBERTa models on medical domain data
2. **Enhanced ML Risk Models**: Add more sophisticated ML algorithms and feature engineering
3. **Advanced Caching Layer**: Redis for distributed caching in production environments
4. **Enhanced Model Versioning**: Add model registry and deployment automation
5. **A/B Testing**: Compare different NLP configurations
6. **Advanced Analytics**: Add data visualization and export capabilities
7. **Custom Training**: Fine-tune models on domain-specific data

## Contributing

Guidelines for contributing improvements:

1. Create feature branch
2. Add tests for new features
3. Update documentation
4. Submit pull request

## License

Part of HeartGuard Chatbot project.

## Support

For issues or questions:
- Check documentation in `/docs`
- Review integration examples
- Check logs for error details

## Version History

- **v1.0.0** (2024): Initial release
  - Intent recognition
  - Sentiment analysis
  - Entity extraction
  - Risk assessment
