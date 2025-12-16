# 📚 Cardio AI Assistant Documentation

Welcome to the consolidated documentation for the Cardio AI Assistant (HeartGuard) project.

## 📂 Documentation Structure

```
docs/
├── README.md                    # This file - documentation index
├── architecture/                # System architecture docs
│   ├── overview.md              # High-level system architecture
│   ├── memory-system.md         # Memory/context management
│   └── ml-pipeline.md           # ML model architecture
├── guides/                      # Developer guides
│   ├── getting-started.md       # Quick start guide
│   ├── deployment.md            # Deployment instructions
│   └── troubleshooting.md       # Common issues & fixes
├── api/                         # API documentation
│   └── endpoints.md             # REST API reference
```

## 🏗️ Project Components

| Component | Location | Port | Technology |
|-----------|----------|------|------------|
| **Frontend** | `cardio-ai-assistant/` | 5173 | React + TypeScript + Vite |
| **Flask Backend** | `cardio-ai-assistant/backend/` | 5000 | Python Flask |
| **NLP Service** | `nlp-service/` | 5001 | Python FastAPI |
| **Service Runner** | `run_services.py` | - | Python orchestrator |

## 🚀 Quick Links

### Getting Started
- [Quick Start Guide](guides/getting-started.md)
- [Deployment Guide](guides/deployment.md)
- [Troubleshooting Guide](guides/troubleshooting.md)

### Architecture
- [System Overview](architecture/overview.md)
- [Memory System](architecture/memory-system.md)
- [ML Pipeline](architecture/ml-pipeline.md)

### API
- [API Endpoints](api/endpoints.md)

## ⚡ Quick Start

```bash
# Start all services with one command
python run_services.py

# Or start individually:
# Terminal 1 - NLP Service
cd nlp-service && python main.py

# Terminal 2 - Flask Backend
cd cardio-ai-assistant/backend && python aip_service.py

# Terminal 3 - Frontend
cd cardio-ai-assistant && npm run dev
```

## 🔧 NLP Service Features (16 API Route Groups)

The NLP Service provides a comprehensive healthcare AI platform with the following capabilities:

### Core NLP Processing
- **Intent Recognition** - 10+ healthcare intents with context awareness
- **Sentiment Analysis** - Emotional state detection (VADER-based)
- **Entity Extraction** - Symptoms, medications, measurements
- **Risk Assessment** - Framingham Risk Score algorithm

### AI & Knowledge Systems
- **RAG Pipeline** - Semantic search with medical knowledge base
- **Knowledge Graph** - Neo4j-powered medical entity relationships
- **AI Agents** - Orchestrated health agents with planning capabilities
- **Structured Outputs** - Schema-guided AI responses

### Memory & Context
- **Memory System** - Patient-specific context management (Memori)
- **User Preferences** - Personalization and settings storage
- **Chat History** - Conversation tracking and retrieval

### Medical Features
- **Document Scanning** - OCR-based medical document processing
- **Medical AI** - MedGemma integration for medical understanding
- **Vision Analysis** - ECG analysis, food recognition
- **Weekly Summaries** - Health trend reports

### Communication & Notifications
- **Real-time WebSocket** - Live bidirectional communication
- **Notifications** - WhatsApp, Email, Push notifications
- **Calendar Integration** - Google/Outlook calendar sync

### Compliance & Tools
- **HIPAA Compliance** - Audit logging and consent management
- **Health Tools** - Blood pressure, heart rate, BMI calculators
- **Function Calling** - LLM tool registry for automated actions

### Frontend Features
- Dashboard with health metrics visualization
- AI-powered chat assistant
- Medication tracking and reminders
- Appointment management
- Nutrition and exercise tracking
- Analytics dashboard
- Multi-language support

### Flask Backend Features
- Google Gemini AI integration
- Recipe and workout analysis
- Meal plan generation
- Health assessments
- NLP service proxy

## 📋 Environment Setup

Required environment files:
- `nlp-service/.env` - NLP service configuration
- `cardio-ai-assistant/backend/.env` - Flask backend configuration  
- `cardio-ai-assistant/.env.local` - Frontend configuration

## 📊 API Route Summary

| Route Group | Prefix | Description |
|-------------|--------|-------------|
| Core | `/` | Health, cache, analytics |
| NLP | `/api/nlp/*` | Intent, sentiment, entities |
| Risk | `/api/risk/*` | Cardiovascular risk assessment |
| RAG | `/api/rag/*` | Semantic search, knowledge base |
| Memory | `/api/memory/*` | User preferences, context |
| Agents | `/api/agents/*` | ADK agent orchestration |
| Documents | `/api/documents/*` | OCR, document processing |
| Medical AI | `/api/medical-ai/*` | MedGemma, terminology |
| Vision | `/api/vision/*` | ECG, food recognition |
| Calendar | `/api/calendar/*` | Google/Outlook sync |
| Notifications | `/api/notifications/*` | WhatsApp, Email, Push |
| Knowledge Graph | `/api/knowledge-graph/*` | Neo4j queries |
| Tools | `/api/tools/*` | Health calculators |
| Weekly Summary | `/api/weekly-summary/*` | Health reports |
| Compliance | `/api/compliance/*` | Audit, consent |
| WebSocket | `/ws/*` | Real-time events |

See [API Endpoints](api/endpoints.md) for complete documentation.

See [Getting Started Guide](guides/getting-started.md) for detailed setup instructions.
