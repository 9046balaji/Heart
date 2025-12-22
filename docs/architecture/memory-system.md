# 🧠 Memory System Architecture

> **Document Version:** 1.1  
> **Last Updated:** December 22, 2025  
> **Component:** NLP Service Memory Module

---

## Executive Summary

The Memory System enables **context-aware, personalized healthcare conversations** by maintaining patient-specific memory isolation, intelligent context retrieval, and HIPAA-compliant data handling. It integrates with the AI service layer to provide relevant historical context for every interaction.

---

## Overview

The Cardio AI Assistant implements a sophisticated memory system based on the **Memori** architecture principles. This enables context-aware, personalized healthcare conversations with patient data isolation.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Memory System                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                   Integrated AI Service                          │    │
│  │   - Orchestrates Store → Retrieve → Build → Call → Store flow   │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              │                                           │
│         ┌────────────────────┼────────────────────┐                     │
│         │                    │                    │                     │
│         ▼                    ▼                    ▼                     │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐             │
│  │   Context   │      │   Prompt    │      │    User     │             │
│  │  Retriever  │      │   Builder   │      │ Preferences │             │
│  └─────────────┘      └─────────────┘      └─────────────┘             │
│         │                    │                    │                     │
│         └────────────────────┼────────────────────┘                     │
│                              │                                           │
│                              ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    Memori Integration                            │    │
│  │   - Patient-specific memory isolation                           │    │
│  │   - LRU caching with TTL                                        │    │
│  │   - SQLite/PostgreSQL persistence                               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Context Retriever (`context_retrieval.py`)

**Purpose:** Query-aware context retrieval with keyword analysis

**Features:**
- 9 Context Types: CHAT_HISTORY, HEALTH_METRICS, MEDICATIONS, etc.
- Parallel data fetching
- Relevance scoring (0.0 - 1.0)
- Token budget management
- LRU caching

```python
# Example usage
retriever = ContextRetriever(patient_id="patient_123")
contexts = await retriever.retrieve_for_query(
    query="What about my blood pressure medication?",
    max_tokens=2000
)
```

### 2. Prompt Builder (`prompt_builder.py`)

**Purpose:** Healthcare-specific prompt templates with context sections

**Features:**
- 5 communication styles: PROFESSIONAL, EMPATHETIC, CASUAL, CLINICAL, ENCOURAGING
- Emergency mode detection
- Auto section cleanup (removes empty sections)
- Token estimation

```python
# Example usage
builder = HealthcarePromptBuilder()
prompt = builder.build_prompt(
    query="How's my heart health?",
    contexts=contexts,
    style=CommunicationStyle.EMPATHETIC
)
```

### 3. User Preferences (`user_preferences.py`)

**Purpose:** SQLAlchemy-based preference storage

**Features:**
- Type-safe storage (string, int, float, bool, json)
- PHI sensitivity flags
- Audit logging
- GDPR compliance (export, delete)

```python
# Example usage
prefs = UserPreferencesManager(patient_id="patient_123")
await prefs.set_preference("communication_style", "empathetic")
style = await prefs.get_preference("communication_style")
```

### 4. Integrated AI Service (`integrated_ai_service.py`)

**Purpose:** Full orchestration tying all components together

**Flow:**
1. **Store** user message to history
2. **Retrieve** relevant context
3. **Build** healthcare prompt
4. **Call** AI provider (Gemini/Ollama)
5. **Store** assistant response

```python
# Example usage
service = IntegratedHealthAIService(patient_id="patient_123")
response = await service.process_query(
    query="I'm feeling dizzy today",
    session_id="session_456"
)
```

## Memory-Aware Agents (`memory_aware_agents.py`)

The agent orchestration layer that combines:
- Intent recognition
- Sentiment analysis
- Entity extraction
- Risk assessment
- Memory retrieval

```python
# Conversation flow
agent = MemoryAwareHealthAgent(patient_id="patient_123")
response = await agent.process_message(
    message="I have chest pain",
    session_id="session_456"
)
# Returns: emergency flag, intent, sentiment, entities, risk, AI response
```

## API Endpoints (`routes/memory.py`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/memory/preferences` | GET/POST/DELETE | User preferences CRUD |
| `/memory/sessions` | GET/POST/DELETE | Session management |
| `/memory/context/preview` | POST | Context retrieval preview |
| `/memory/gdpr/export` | GET | GDPR data export |
| `/memory/gdpr/delete` | DELETE | GDPR data deletion |

## Frontend Integration (`memoryService.ts`)

The TypeScript service provides:
- Full API integration
- Local caching
- Session tracking
- Type-safe interfaces

```typescript
// Example usage
const memoryService = MemoryServiceImpl.getInstance();
await memoryService.savePreference({ key: 'theme', value: 'dark' });
const context = await memoryService.getContextPreview('my symptoms');
```

## Data Isolation

### HIPAA Compliance
- Patient data is isolated by `patient_id`
- No cross-patient data access
- Audit logging for all operations
- Encryption at rest (configurable)

### Multi-tenancy
```python
# Each patient gets isolated memory
patient_1_memory = MemoryManager.get_patient_memory("patient_1")
patient_2_memory = MemoryManager.get_patient_memory("patient_2")
# Completely separate data stores
```

## Performance Optimizations

| Optimization | Impact |
|--------------|--------|
| LRU caching | O(1) memory lookups |
| Parallel fetching | 3-5x faster context retrieval |
| Token budgeting | Prevents context overflow |
| Database indexing | O(log n) searches |

## Configuration

Environment variables:
```env
MEMORY_ENABLED=true
MEMORY_DATABASE_URL=sqlite:///memory.db
MEMORY_CACHE_SIZE=100
MEMORY_DEFAULT_STYLE=empathetic
```
