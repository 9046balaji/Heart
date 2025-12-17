# HeartGuard / Cardio AI Super-App

## System Architecture

```
┌────────────────────┐    ┌────────────────────┐
│   React Frontend   │    │   NLP Service      │
│   (Vite + React)   │◄──►│   (FastAPI)        │
│   Port: 5173       │    │   Port: 5001       │
└────────────────────┘    └────────────────────┘
                                 ▲
                                 │
                       ┌─────────┴──────────┐
                       │   Ollama/Gemini    │
                       │   (LLM Providers)  │
                       └────────────────────┘
```

## Services

| Service | Tech Stack | Port | Description |
|---------|------------|------|-------------|
| Frontend | React + Vite | 5173 | User Interface |
| NLP Service | FastAPI + Python | 5001 | AI Orchestration Layer |

---

## Project Overview

### What the System Does

Cardio AI Assistant is a comprehensive healthcare platform designed to assist users in monitoring and understanding their cardiovascular health. The system provides:

- Conversational AI for health-related queries with medical context awareness
- Cardiovascular risk assessment using the Framingham Risk Score algorithm and machine learning models
- Real-time health data processing from smartwatch devices
- Medical document scanning and analysis using OCR and AI
- Personalized health recommendations based on user data and preferences
- Appointment scheduling with calendar integration
- Multi-channel notifications (WhatsApp, Email, Push)

### Why It Exists

Cardiovascular disease remains a leading cause of mortality worldwide. Early detection and continuous monitoring can significantly improve outcomes. This platform aims to:

- Provide accessible cardiovascular health education
- Enable early identification of potential health concerns through AI-powered analysis
- Support healthcare providers with patient timeline and summary tools
- Maintain patient privacy through local processing options and HIPAA-compliant design

### Target Users

- **Patients**: Individuals seeking to monitor and understand their cardiovascular health
- **Healthcare Providers**: Doctors who need patient dashboards, health timelines, and summary reports
- **Caregivers**: Family members monitoring health metrics for others

---

## Key Features

### Implemented Features

#### AI and Natural Language Processing
- Intent recognition with 10+ predefined medical intents
- Sentiment analysis for emotional state detection (positive, neutral, negative, distressed, urgent)
- Entity extraction for symptoms, medications, foods, measurements, and time references
- Emergency detection for critical situations requiring immediate escalation
- Context-aware responses using patient memory and conversation history

#### Machine Learning and Risk Assessment
- Framingham Risk Score calculation for cardiovascular disease risk
- Isolation Forest anomaly detection for smartwatch health data
- Rule-based alert engine with clinical thresholds
- Natural language explanations for detected anomalies
- Heart disease prediction using ensemble ML models (Stacking, MLP)

#### Medical AI Integration
- MedGemma service for medical entity extraction (Cloud API mode)
- Medical terminology normalization and abbreviation expansion
- Patient-friendly summarization of medical reports
- Vision analysis for ECG images and food recognition

#### Document Processing
- OCR engine supporting Tesseract, Google Cloud Vision, and AWS Textract
- Medical document classification
- Document ingestion pipeline with confidence scoring

#### Memory and Context Management
- Patient-specific memory isolation
- Context retrieval with relevance scoring
- Session management and chat history
- LRU caching with configurable TTL
- User preferences storage with GDPR export/delete support

#### RAG (Retrieval-Augmented Generation)
- Semantic search over medical knowledge base
- Vector store for embedding-based retrieval
- Knowledge graph integration with Neo4j (optional)

#### Frontend Features
- Dashboard with health metrics visualization
- AI chat interface with markdown rendering
- Medication tracking and reminders
- Appointment management
- Nutrition planning with recipe analysis
- Exercise tracking with workout analysis
- Analytics dashboard with health trends
- Multi-language support

#### Notifications and Calendar
- WhatsApp Business API integration via Twilio
- Email notifications via SendGrid/SMTP
- Push notifications via Firebase Cloud Messaging
- Google Calendar and Outlook calendar synchronization
- Appointment reminders and medication schedule integration

#### Compliance
- HIPAA-compliant audit logging
- Patient consent management
- Data retention policies
- PHI encryption service

### Partially Implemented Features

- **Appointments Module**: Functional via agents but lacks dedicated REST endpoints
- **Memori Advanced Features**: Core memory works; advanced agents, security, and tools have limited API exposure

### Planned Features (Documented)

- Local MedGemma 4B inference using quantized GGUF models for privacy-focused deployments
- Smartwatch API integrations (Fitbit, Apple Health, Google Fit)
- FHIR/HL7 medical system integration
- Advanced transformer models fine-tuned on medical domain data

---

## System Architecture

### High-Level Overview

The system consists of three main services:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Cardio AI Assistant                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────┐     ┌──────────────────────┐                  │
│  │   React Frontend     │     │   Flask Backend      │                  │
│  │   (Vite + TypeScript)│────>│   (aip_service.py)   │                  │
│  │   Port: 5173         │     │   Port: 5000         │                  │
│  └──────────────────────┘     └──────────┬───────────┘                  │
│                                          │                               │
│                                          v                               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    FastAPI NLP Service                            │   │
│  │                    Port: 5001 (16 API Route Groups)               │   │
│  │                                                                   │   │
│  │  Core NLP Engines | Memory System | RAG Pipeline | AI Agents     │   │
│  │  Document Scanning | Medical AI | Compliance | Vision Analysis   │   │
│  │  Calendar Integration | Notifications | Knowledge Graph | Tools  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                          │                               │
│  ┌──────────────────────┐     ┌──────────────────────┐                  │
│  │   External Services  │     │   AI Providers       │                  │
│  │   - Google Calendar  │     │   - Google Gemini    │                  │
│  │   - Outlook Calendar │     │   - Ollama (local)   │                  │
│  │   - Twilio WhatsApp  │     │   - Neo4j (optional) │                  │
│  │   - SendGrid Email   │     │   - MedGemma (cloud) │                  │
│  └──────────────────────┘     └──────────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Interactions

1. **Frontend (React)**: Handles user interface, health dashboards, and chat interactions
2. **Flask Backend**: Proxies requests, integrates Google Gemini for recipe/workout analysis, and manages ML models
3. **NLP Service (FastAPI)**: Processes all natural language, manages memory, handles document scanning, and orchestrates AI agents

For detailed architecture documentation, see:
- [System Overview](docs/architecture/overview.md)
- [Memory System](docs/architecture/memory-system.md)
- [ML Pipeline](docs/architecture/ml-pipeline.md)

---

## AI and ML Components

### Intent Recognition
- TF-IDF vectorization combined with keyword matching
- Supports transformer models (optional, configurable)
- 10+ healthcare-specific intents including symptom check, medication reminder, risk assessment, emergency

### Sentiment Analysis
- VADER-based sentiment analysis
- Detects positive, neutral, negative, distressed, and urgent states
- Intensity levels: mild, moderate, strong, very strong

### Entity Extraction
- SpaCy PhraseMatcher for named entity recognition
- Extracts: symptoms, medications, foods, measurements, duration, time references
- Configurable entity types and patterns

### Risk Assessment
- **Framingham Risk Score**: Age, blood pressure, cholesterol, smoking status, diabetes, family history
- **ML Models**: Random Forest, Gradient Boosting, Logistic Regression (configurable)
- Risk levels: LOW (<10%), MODERATE (10-20%), HIGH (>20%)

### Anomaly Detection (ML Pipeline)
- **Feature Extractor**: Statistical features from smartwatch time-series data
- **Anomaly Detector**: Isolation Forest algorithm
- **Rule Engine**: Clinical threshold-based rules for heart rate, blood pressure
- **Health Explainer**: Natural language explanations for anomalies
- **Alert Pipeline**: Priority classification (CRITICAL, HIGH, MEDIUM, LOW)

### MedGemma Integration
- Medical entity extraction from clinical documents
- Patient-friendly summarization
- Terminology normalization
- Multimodal processing (text + images)
- Currently operates in Cloud API mode; local GGUF mode planned

### Vision Analysis
- ECG image analysis for rhythm detection
- Food recognition with nutrition estimation
- General medical image analysis via Gemini Vision

### AI Agents
- Health Agent: General health queries
- Cardio Specialist: Cardiovascular-specific expertise
- Orchestrator: Multi-agent coordination
- Planner and Task Executor: Complex task handling

---

## Data Flow

### Step-by-Step Processing

```
1. User Input
   └─> Frontend (React)
       └─> HTTP Request to Flask Backend (Port 5000)
           └─> Proxy to NLP Service (Port 5001)

2. NLP Processing
   └─> Intent Recognition
   └─> Sentiment Analysis
   └─> Entity Extraction
   └─> Emergency Detection Check

3. Context Retrieval
   └─> Memory System (patient-specific context)
   └─> RAG Pipeline (medical knowledge base)
   └─> User Preferences

4. AI Response Generation
   └─> Prompt Builder (healthcare-specific templates)
   └─> AI Provider (Gemini/Ollama)
   └─> Response with recommendations

5. Response Delivery
   └─> Store in Chat History
   └─> Return to Flask Backend
   └─> Return to Frontend
   └─> Optional: Trigger Notifications (WhatsApp/Email/Push)
```

### Health Data Processing (Smartwatch)

```
1. Smartwatch Data Received
   └─> Feature Extraction (heart rate, steps, sleep)
   └─> Anomaly Detection (Isolation Forest)
   └─> Rule Engine (clinical thresholds)

2. Alert Generation
   └─> Priority Classification
   └─> Natural Language Explanation
   └─> Recommendations

3. Notification
   └─> Push to Frontend
   └─> Optional: WhatsApp/Email alerts for critical priority
```

---

## Technology Stack

### Frontend
| Technology | Purpose |
|------------|---------|
| React 19 | UI framework |
| TypeScript | Type-safe JavaScript |
| Vite | Build tool and dev server |
| Zustand | State management |
| Recharts | Data visualization |
| React Router | Navigation |
| Tailwind CSS | Styling |
| Framer Motion | Animations |

### Backend (Flask)
| Technology | Purpose |
|------------|---------|
| Flask 3.0 | Web framework |
| Flask-CORS | Cross-origin resource sharing |
| Google Generative AI | Gemini API integration |
| scikit-learn | ML model inference |
| joblib | Model serialization |

### NLP Service (FastAPI)
| Technology | Purpose |
|------------|---------|
| FastAPI | High-performance API framework |
| Uvicorn | ASGI server |
| Pydantic | Data validation |
| VADER Sentiment | Sentiment analysis |
| scikit-learn | ML models |
| Sentence Transformers | Text embeddings |
| SQLAlchemy | Database ORM |
| Ollama | Local LLM inference |
| Google ADK | Agent Development Kit |

### Databases
| Database | Purpose |
|----------|---------|
| SQLite | Chat history, preferences, health data, appointments, cache |
| Neo4j (optional) | Knowledge graph |
| ChromaDB (optional) | Vector embeddings |

### External APIs and Services
| Service | Purpose |
|---------|---------|
| Google Gemini | Primary AI model |
| Ollama | Local AI inference (gemma3:1b) |
| Twilio | WhatsApp notifications |
| SendGrid | Email notifications |
| Firebase | Push notifications |
| Google Calendar API | Calendar sync |
| Microsoft Graph API | Outlook calendar sync |
| Google Cloud Vision | OCR (optional) |
| AWS Textract | OCR (optional) |
| Tesseract | Local OCR |

---

## Installation and Setup

### Prerequisites

- Python 3.10 or higher (3.11 recommended)
- Node.js 18 or higher
- npm or yarn
- Git
- Ollama (optional, for local AI inference)
- Tesseract OCR (optional, for local document scanning)

### Step 1: Clone Repository

```bash
cd "your-preferred-directory"
git clone <repository-url>
cd project
```

### Step 2: NLP Service Setup

```bash
cd nlp-service

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm

# Copy environment file
cp .env.example .env
# Edit .env with your configuration
```

### Step 3: Flask Backend Setup

```bash
cd cardio-ai-assistant/backend

# Create virtual environment (or use the same one)
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your configuration
```

### Step 4: Frontend Setup

```bash
cd cardio-ai-assistant

# Install dependencies
npm install

# Copy environment file
cp .env.example .env.local
# Edit .env.local with your configuration
```

### Step 5: Start Services

**Option A: Using the Service Runner (Recommended)**

```bash
cd project
python run_services.py
```

**Option B: Manual Start**

Terminal 1 - NLP Service:
```bash
cd nlp-service
python main.py
# Runs on http://localhost:5001
```

Terminal 2 - Frontend:
```bash
cd cardio-ai-assistant
npm run dev
# Runs on http://localhost:5173
```

### Step 6: Verify Installation

1. Open browser to http://localhost:5173
2. Test NLP health: `curl http://localhost:5001/health`

### Common Setup Issues

| Issue | Solution |
|-------|----------|
| spaCy model not found | Run `python -m spacy download en_core_web_sm` |
| Port already in use | Change port in respective `.env` file |
| Module not found | Verify virtual environment is activated and dependencies installed |
| API key errors | Ensure environment variables are properly set |

---

## Configuration

### Environment Variables

#### NLP Service (nlp-service/.env)

```env
# AI Providers
GOOGLE_API_KEY=your-gemini-api-key
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gemma3:1b

# Service Configuration
NLP_SERVICE_PORT=5001
NLP_SERVICE_HOST=0.0.0.0
LOG_LEVEL=INFO

# Memory System
MEMORY_ENABLED=true
MEMORY_DATABASE_URL=sqlite:///memory.db
MEMORY_CACHE_SIZE=100
MEMORY_DEFAULT_STYLE=empathetic

# Feature Toggles
RAG_ENABLED=true
MEDICAL_ROUTES_ENABLED=true
AGENTS_ROUTES_ENABLED=true
CALENDAR_ROUTES_ENABLED=true
NOTIFICATIONS_ROUTES_ENABLED=true
VISION_ROUTES_ENABLED=true

# Optional: Transformer Models
USE_TRANSFORMER_MODELS=false
USE_ML_RISK_MODELS=false
```

#### Frontend (cardio-ai-assistant/.env.local)

```env
VITE_NLP_URL=http://localhost:5001
```

### Feature Toggles

The NLP service supports conditional loading of feature modules. Each module can be enabled/disabled via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| RAG_ENABLED | true | Semantic search and knowledge base |
| MEMORY_ROUTES_ENABLED | true | User preferences and context |
| MEDICAL_ROUTES_ENABLED | true | Document scanning and MedGemma |
| AGENTS_ROUTES_ENABLED | true | ADK agent orchestration |
| CALENDAR_ROUTES_ENABLED | true | Google/Outlook sync |
| NOTIFICATIONS_ROUTES_ENABLED | true | WhatsApp, Email, Push |
| VISION_ROUTES_ENABLED | true | ECG and food recognition |

---

## Security and Privacy

### Data Handling Principles

1. **Patient Data Isolation**: All patient data is isolated by `patient_id` with no cross-patient data access
2. **Local Processing Option**: Ollama enables local AI inference without sending data to cloud providers
3. **Encryption**: PHI encryption service available for sensitive data at rest
4. **Audit Logging**: All data access operations are logged for compliance

### AI Safety Boundaries

1. **Medical Disclaimers**: All AI responses include appropriate medical disclaimers
2. **Emergency Escalation**: System detects emergency keywords and recommends immediate professional help
3. **Confidence Scoring**: Responses include confidence levels to indicate certainty
4. **No Diagnostic Claims**: System explicitly avoids making medical diagnoses

### Human-in-the-Loop Design

1. **Verification Queue**: High-risk recommendations can be queued for human review
2. **Provider Dashboard**: Healthcare providers can review patient data and AI suggestions
3. **Consent Management**: Patient consent is tracked and respected
4. **Override Capability**: All AI recommendations can be overridden by healthcare professionals

### Compliance Considerations

- HIPAA-compliant design patterns
- GDPR data export and deletion support
- Audit trail for all PHI access
- Configurable data retention policies

### Credential Security

- All credentials stored in environment variables
- `.env` files are gitignored
- See [SECURITY.md](SECURITY.md) for credential rotation procedures

---

## Usage Guide

### Typical User Flow

1. **Dashboard**: View current health metrics, daily insights, and quick access to features
2. **Chat**: Ask health questions, report symptoms, or request information
3. **Medications**: Track medications, set reminders, get interaction warnings
4. **Appointments**: Schedule appointments, sync with external calendars
5. **Nutrition**: Get meal plans, analyze recipes, track food intake
6. **Exercise**: Log workouts, get personalized recommendations
7. **Analytics**: View health trends, risk assessments, progress over time

### Example Scenarios

**Symptom Inquiry**:
```
User: "I've been having chest pain for the past 2 days"
System: Detects symptom entity, assesses urgency, provides recommendations, 
        may escalate if emergency keywords detected
```

**Risk Assessment**:
```
User: Provides age, blood pressure, cholesterol levels
System: Calculates Framingham Risk Score, provides interpretation and 
        personalized recommendations
```

**Document Upload**:
```
User: Uploads medical document (lab report, prescription)
System: OCR extracts text, classifies document type, extracts entities,
        provides patient-friendly summary
```

### What the System Does NOT Do

- Does NOT provide medical diagnoses
- Does NOT replace professional medical advice
- Does NOT prescribe medications or treatments
- Does NOT have access to external medical records unless explicitly uploaded
- Does NOT guarantee accuracy of AI-generated content
- Does NOT provide emergency medical services

---

## Project Status and Roadmap

### Current Maturity

| Component | Status | Stability |
|-----------|--------|-----------|
| Frontend UI | Production | Stable |
| Flask Backend | Production | Stable |
| NLP Core Engines | Production | Stable |
| Memory System | Production | Stable |
| RAG Pipeline | Production | Stable |
| AI Agents | Production | Stable |
| Document Scanning | Production | Stable |
| Calendar Integration | Production | Stable |
| Notifications | Production | Stable |
| MedGemma (Cloud) | Production | Stable |
| Vision Analysis | Production | Stable |
| ML Anomaly Detection | Production | Stable |

### Under Development

- Enhanced memori API exposure
- Dedicated appointments REST endpoints
- Advanced A/B testing for NLP models

### Future Enhancements (Documented)

- **Local MedGemma**: GGUF quantized model for on-device inference (6GB VRAM target)
- **Smartwatch Integration**: Direct APIs for Fitbit, Apple Health, Google Fit
- **FHIR/HL7 Support**: Medical system interoperability
- **Advanced ML Models**: Fine-tuned transformers for medical domain
- **Redis Caching**: Distributed caching for production scale
- **Model Registry**: Automated model deployment and versioning

---

## Folder Structure Overview

```
project/
├── README.md                 # This file
├── SECURITY.md               # Security guidelines and credential management
├── INTEGRATION_AUDIT.md      # Module integration status report
├── MEDGEMMA_IMPLEMENTATION_REPORT.md  # MedGemma technical documentation
├── run_services.py           # Service orchestrator script
│
├── cardio-ai-assistant/      # Frontend and Flask backend
│   ├── App.tsx               # Main React application
│   ├── package.json          # Frontend dependencies
│   ├── vite.config.ts        # Vite build configuration
│   ├── backend/              # Flask backend service
│   │   ├── aip_service.py    # Main Flask application
│   │   ├── smart_watch.py    # Smartwatch data processing
│   │   └── ml/               # ML anomaly detection pipeline
│   ├── components/           # Reusable UI components
│   ├── screens/              # Page components
│   ├── services/             # API client and external services
│   ├── store/                # State management (Zustand)
│   └── contexts/             # React contexts
│
├── nlp-service/              # FastAPI NLP microservice
│   ├── main.py               # FastAPI application entry point
│   ├── config.py             # Configuration management
│   ├── agents/               # ADK agent implementations
│   ├── calendar_integration/ # Google/Outlook calendar sync
│   ├── compliance/           # HIPAA audit, consent, encryption
│   ├── document_scanning/    # OCR and document processing
│   ├── engines/              # NLP processing engines
│   ├── integrations/         # External system integrations
│   ├── knowledge_graph/      # Neo4j graph operations
│   ├── medical_ai/           # MedGemma and medical AI
│   ├── memori/               # Memory management system
│   ├── middleware/           # Request processing middleware
│   ├── notifications/        # WhatsApp, Email, Push
│   ├── rag/                  # Retrieval-augmented generation
│   ├── realtime/             # WebSocket handlers
│   ├── routes/               # API route definitions
│   ├── services/             # Core service layer
│   ├── tools/                # LLM function calling tools
│   ├── vision/               # Image analysis services
│   └── weekly_summary/       # Health summary generation
│
├── docs/                     # Documentation
│   ├── architecture/         # System architecture docs
│   ├── guides/               # Developer guides
│   └── api/                  # API reference
│
├── files/                    # Additional documentation and reports
│   ├── STRUCTURED_OUTPUTS_GUIDE.md
│   ├── watch.md              # Smartwatch integration guide
│   └── ...
│
└── scripts/                  # Utility scripts
    ├── cleanup.ps1
    └── test_*.py             # Test scripts
```

---

## Documentation Index

### Architecture Documents
| Document | Description |
|----------|-------------|
| [docs/architecture/overview.md](docs/architecture/overview.md) | High-level system architecture and component overview |
| [docs/architecture/memory-system.md](docs/architecture/memory-system.md) | Memory system design and implementation |
| [docs/architecture/ml-pipeline.md](docs/architecture/ml-pipeline.md) | ML anomaly detection pipeline architecture |

### Developer Guides
| Document | Description |
|----------|-------------|
| [docs/guides/getting-started.md](docs/guides/getting-started.md) | Quick start guide for development setup |
| [docs/guides/deployment.md](docs/guides/deployment.md) | Production deployment instructions |
| [docs/guides/troubleshooting.md](docs/guides/troubleshooting.md) | Common issues and solutions |

### API Documentation
| Document | Description |
|----------|-------------|
| [docs/api/endpoints.md](docs/api/endpoints.md) | REST API endpoint reference |
| [nlp-service/README.md](nlp-service/README.md) | NLP service detailed documentation |

### Implementation Reports
| Document | Description |
|----------|-------------|
| [MEDGEMMA_IMPLEMENTATION_REPORT.md](MEDGEMMA_IMPLEMENTATION_REPORT.md) | MedGemma 4B integration technical blueprint |
| [INTEGRATION_AUDIT.md](INTEGRATION_AUDIT.md) | Module integration status audit |
| [SECURITY.md](SECURITY.md) | Security policy and credential management |

### Feature Documentation
| Document | Description |
|----------|-------------|
| [files/STRUCTURED_OUTPUTS_GUIDE.md](files/STRUCTURED_OUTPUTS_GUIDE.md) | LLM structured output implementation |
| [files/watch.md](files/watch.md) | Samsung smartwatch integration guide |

---

## Disclaimer

**IMPORTANT: READ BEFORE USE**

This software is provided for **educational and informational purposes only**.

1. **Not Medical Advice**: This system does not provide medical advice, diagnosis, or treatment recommendations. All information provided by this application is for general educational purposes only.

2. **Not a Substitute for Professional Care**: This application is not intended to replace consultation with qualified healthcare professionals. Always seek the advice of your physician or other qualified health provider with any questions you may have regarding a medical condition.

3. **No Emergency Services**: This application does not provide emergency medical services. If you are experiencing a medical emergency, call your local emergency services immediately.

4. **AI Limitations**: The AI-generated content may contain errors or inaccuracies. AI responses should not be relied upon for making health decisions.

5. **No Warranty**: This software is provided "as is" without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement.

6. **User Responsibility**: Users are solely responsible for how they use the information provided by this application.

By using this software, you acknowledge that you have read, understood, and agree to this disclaimer.

---

## License

This project is part of the HeartGuard educational initiative.

---

## Support

For issues or questions:
- Review the [Troubleshooting Guide](docs/guides/troubleshooting.md)
- Check existing documentation in the `/docs` folder
- Review service-specific READMEs in `nlp-service/` and `cardio-ai-assistant/`
