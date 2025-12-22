# 🏗️ System Architecture Overview

> **Document Version:** 1.1  
> **Last Updated:** December 22, 2025  
> **Purpose:** High-level technical overview for developers and stakeholders

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Cardio AI Assistant (HeartGuard)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────┐     ┌──────────────────────┐                      │
│  │   React Frontend     │     │   Flask Backend      │                      │
│  │   (Vite + TypeScript)│────▶│   (aip_service.py)   │                      │
│  │   Port: 5173         │     │   Port: 5000         │                      │
│  └──────────────────────┘     └──────────┬───────────┘                      │
│                                          │                                   │
│                                          ▼                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        FastAPI NLP Service                            │   │
│  │                        Port: 5001 (16 API Route Groups)               │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │                    Core NLP Engines                              │ │   │
│  │  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐│ │   │
│  │  │  │   Intent    │ │  Sentiment  │ │   Entity    │ │    Risk     ││ │   │
│  │  │  │ Recognizer  │ │  Analyzer   │ │  Extractor  │ │  Assessor   ││ │   │
│  │  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘│ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │                    Memory System (Memori)                        │ │   │
│  │  │  - Context Retrieval    - User Preferences    - Chat History    │ │   │
│  │  │  - Prompt Building      - Session Management  - Memory Agents   │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │                    RAG & Knowledge Systems                       │ │   │
│  │  │  - Embedding Service    - Vector Store        - Knowledge Base  │ │   │
│  │  │  - Semantic Search      - Knowledge Graph     - Neo4j Queries   │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │                    AI Agents System                              │ │   │
│  │  │  - Health Agent         - Cardio Specialist   - Task Executor   │ │   │
│  │  │  - Orchestrator         - Planner             - Base Agent      │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                       │   │
│  │  ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐   │   │
│  │  │  Document Scanning│ │   Medical AI      │ │   Compliance      │   │   │
│  │  │  - OCR Engine     │ │   - MedGemma      │ │   - Audit Logger  │   │   │
│  │  │  - Classifier     │ │   - Terminology   │ │   - Consent Mgmt  │   │   │
│  │  │  - Ingestion      │ │   - Multimodal    │ │   - Encryption    │   │   │
│  │  └───────────────────┘ └───────────────────┘ └───────────────────┘   │   │
│  │                                                                       │   │
│  │  ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐   │   │
│  │  │  Vision Analysis  │ │   Health Tools    │ │  Calendar Sync    │   │   │
│  │  │  - ECG Analyzer   │ │   - BP Calculator │ │   - Google Cal    │   │   │
│  │  │  - Food Recog     │ │   - BMI/HR Zones  │ │   - Outlook       │   │   │
│  │  │  - Image AI       │ │   - Function Call │ │   - Reminders     │   │   │
│  │  └───────────────────┘ └───────────────────┘ └───────────────────┘   │   │
│  │                                                                       │   │
│  │  ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐   │   │
│  │  │  Real-time WS     │ │   Notifications   │ │   Weekly Summary  │   │   │
│  │  │  - Event Bus      │ │   - WhatsApp      │ │   - Aggregation   │   │   │
│  │  │  - WebSocket      │ │   - Email/Push    │ │   - Reports       │   │   │
│  │  └───────────────────┘ └───────────────────┘ └───────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    ML Anomaly Detection Pipeline                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │  Feature    │  │  Anomaly    │  │   Rule      │  │   Alert     │  │   │
│  │  │  Extractor  │  │  Detector   │  │   Engine    │  │  Pipeline   │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  │                                                                       │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                   │   │
│  │  │   Chatbot   │  │   Health    │  │   Prompt    │                   │   │
│  │  │  Connector  │  │  Explainer  │  │  Templates  │                   │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────┐     ┌──────────────────────┐                      │
│  │   External Services  │     │   AI Providers       │                      │
│  │   - Google Calendar  │     │   - Google Gemini    │                      │
│  │   - Outlook Calendar │     │   - Ollama (local)   │                      │
│  │   - Twilio WhatsApp  │     │   - Neo4j (graphs)   │                      │
│  │   - SendGrid Email   │     │   - MedGemma         │                      │
│  └──────────────────────┘     └──────────────────────┘                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Overview

### Frontend Layer
- **Technology:** React + TypeScript + Vite
- **Port:** 5173
- **Key Features:**
  - Dashboard with health metrics visualization
  - Chat interface with AI assistant
  - Medication tracking and reminders
  - Appointment management
  - Nutrition and exercise tracking
  - Analytics dashboard
  - Community features
  - Multi-language support

### Flask Backend
- **File:** `cardio-ai-assistant/backend/aip_service.py`
- **Port:** 5000
- **Responsibilities:**
  - Google Gemini API integration
  - Recipe and workout analysis
  - Meal plan generation
  - Health assessments
  - Medication insights
  - NLP service proxy

### FastAPI NLP Service
- **Location:** `nlp-service/`
- **Port:** 5001
- **Core Engines (located in `engines/`):**
  - Intent recognition (TF-IDF + keyword matching)
  - Sentiment analysis (VADER-based)
  - Entity extraction (SpaCy PhraseMatcher)
  - Risk assessment (Framingham + ML models)

### Memory System (Memori)
- **Location:** `nlp-service/memori/`
- **Features:**
  - Patient-specific memory isolation
  - Context retrieval with relevance scoring
  - Session management
  - LRU caching with TTL
  - HIPAA-compliant data handling

### RAG Pipeline
- **Location:** `nlp-service/rag/`
- **Components:**
  - `embedding_service.py` - Text embedding generation
  - `embedding_onnx.py` - ONNX-optimized embeddings
  - `vector_store.py` - Vector similarity search
  - `rag_pipeline.py` - Query orchestration
  - `knowledge_base/` - Medical knowledge documents

### AI Agents System
- **Location:** `nlp-service/agents/`
- **Agents:**
  - `health_agent.py` - General health assistant
  - `cardio_specialist.py` - Cardiovascular specialist
  - `orchestrator.py` - Multi-agent coordination
  - `planner.py` - Task planning
  - `task_executor.py` - Task execution

### Document Scanning
- **Location:** `nlp-service/document_scanning/`
- **Components:**
  - `ocr_engine.py` - OCR processing
  - `classifier.py` - Document classification
  - `ingestion.py` - Document ingestion pipeline

### Medical AI
- **Location:** `nlp-service/medical_ai/`
- **Components:**
  - `medgemma_service.py` - MedGemma integration
  - `multimodal_processor.py` - Image + text processing
  - `terminology_normalizer.py` - Medical terminology standardization

### Compliance
- **Location:** `nlp-service/compliance/`
- **Components:**
  - `audit_logger.py` - HIPAA audit logging
  - `consent_manager.py` - Patient consent tracking
  - `data_retention.py` - Data retention policies
  - `encryption_service.py` - Data encryption
  - `disclaimer_service.py` - Medical disclaimers

### Real-time Communication
- **Location:** `nlp-service/realtime/`
- **Components:**
  - `websocket_handler.py` - WebSocket connections
  - `event_bus.py` - Event publishing/subscription

### Integrations
- **Location:** `nlp-service/integrations/`
- **Components:**
  - `timeline_service.py` - Health timeline
  - `prediction_integration.py` - Risk predictions
  - `weekly_aggregation.py` - Weekly summaries
  - `doctor_dashboard.py` - Provider dashboard data

### Calendar Integration
- **Location:** `nlp-service/calendar_integration/`
- **Components:**
  - `google_calendar.py` - Google Calendar OAuth & sync
  - `outlook_calendar.py` - Outlook/Microsoft 365 integration
  - `appointment_sync.py` - Bidirectional appointment sync
  - `calendar_service.py` - Unified calendar abstraction
- **Features:**
  - OAuth 2.0 credential management
  - Event sync with external calendars
  - Health appointment reminders
  - Medication schedule integration

### Knowledge Graph
- **Location:** `nlp-service/knowledge_graph/`
- **Components:**
  - `graph_store.py` - Neo4j connection management
  - `entity_manager.py` - Medical entity CRUD operations
  - `relationship_mapper.py` - Entity relationship management
  - `query_engine.py` - Cypher query execution
- **Features:**
  - Medical entity relationships (symptoms → conditions)
  - Semantic relationship traversal
  - Graph-based knowledge retrieval
  - Patient health entity mapping

### Notifications
- **Location:** `nlp-service/notifications/`
- **Components:**
  - `whatsapp_service.py` - Twilio WhatsApp integration
  - `email_service.py` - SMTP/SendGrid email notifications
  - `push_service.py` - FCM push notifications
  - `notification_manager.py` - Unified notification orchestration
- **Features:**
  - Multi-channel delivery (WhatsApp, Email, Push)
  - Notification templates
  - Delivery status tracking
  - User preference management
  - Quiet hours enforcement

### Health Tools
- **Location:** `nlp-service/tools/`
- **Components:**
  - `tool_registry.py` - LLM tool registration system
  - `blood_pressure_calculator.py` - BP category classification
  - `bmi_calculator.py` - BMI calculation and ranges
  - `heart_rate_zones.py` - Training zone calculation
  - `function_calling.py` - AI function execution
- **Features:**
  - Health metric calculators
  - LLM function calling support
  - Extensible tool registry
  - Parameter validation

### Vision Analysis
- **Location:** `nlp-service/vision/`
- **Components:**
  - `ecg_analyzer.py` - ECG image analysis
  - `food_recognizer.py` - Food image recognition
  - `skin_analyzer.py` - Skin condition detection
  - `vision_service.py` - Unified vision interface
- **Features:**
  - ECG rhythm detection
  - Food nutrition estimation
  - Image-based health analysis
  - Multi-model support

### ML Anomaly Detection & Smart Watch
- **Location:** `nlp-service/medical_ai/smart_watch/`
- **Features:**
  - Isolation Forest anomaly detection
  - Rule-based alert engine with clinical thresholds
  - Natural language health explanations
  - Chatbot integration via Health Explainer
  - Real-time WebSocket streaming
  - MySQL/PostgreSQL support for time-series data

## Data Flow

```
User Input → Frontend → Flask Backend → NLP Service
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │                       │                       │
                    ▼                       ▼                       ▼
             Intent Recognition      Entity Extraction       Sentiment Analysis
                    │                       │                       │
                    └───────────────────────┼───────────────────────┘
                                            │
                              ┌─────────────┴─────────────┐
                              │                           │
                              ▼                           ▼
                       Memory Retrieval            RAG Context
                              │                           │
                              └─────────────┬─────────────┘
                                            │
                                            ▼
                                    AI Response Generation
                                            │
                                            ▼
                                    Response to User
```

## Database Architecture

| Database | Technology | Purpose |
|----------|------------|---------|
| Chat History | SQLite | Conversation storage |
| User Preferences | SQLite | Settings, preferences |
| Health Data | SQLite / MySQL (XAMPP) | Vitals, metrics, assessments |
| Appointments | SQLite (`appointments.db`) | Scheduling data |
| Device Time-Series | MySQL (XAMPP) / PostgreSQL | High-frequency smartwatch data |
| NLP Cache | SQLite (`nlp_cache.db`) | Response caching |

## External Integrations

### AI Providers
- **Google Gemini:** Primary AI model (gemini-1.5-flash)
- **Ollama:** Local inference (gemma3:1b default model)

### Calendar Services
- **Google Calendar:** OAuth 2.0 integration for event sync
- **Microsoft Outlook:** Office 365 calendar integration

### Notification Channels
- **Twilio WhatsApp:** Business messaging API
- **SendGrid/SMTP:** Email notifications
- **Firebase Cloud Messaging:** Push notifications

### Knowledge Stores
- **Neo4j:** Knowledge graph database (optional)

### Planned Integrations
- Smartwatch APIs (Fitbit, Apple Health, Google Fit)
- FHIR/HL7 medical systems
