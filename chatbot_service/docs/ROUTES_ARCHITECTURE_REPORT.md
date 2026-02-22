# Routes Architecture Report

## HeartGuard AI — API Routes & Endpoints

> **Version:** 2.1.0  
> **Last Updated:** February 2026  
> **Author:** HeartGuard AI Team

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Core Routes](#core-routes)
4. [Health Routes](#health-routes)
5. [Admin Routes](#admin-routes)
6. [Request Flow](#request-flow)
7. [Authentication](#authentication)
8. [File Reference](#file-reference)

---

## Overview

HeartGuard AI exposes **32 route files** organized into three groups: **Core** (user-facing), **Health** (medical features), and **Admin** (system management). All routes are built with **FastAPI** and registered in `main.py`.

**Base URL:** `http://localhost:5001` (development) or `http://localhost:8000` (production Docker)

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                     FASTAPI APPLICATION                       │
│                        (main.py)                              │
│                                                              │
│  Middleware:                                                 │
│  ├── CORS (configurable origins)                             │
│  ├── RequestTimeoutMiddleware (300s)                         │
│  └── MemoryContextInjector (Memori)                          │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                  CORE ROUTES                           │  │
│  │                                                        │  │
│  │  /auth       Authentication (login, register, JWT)     │  │
│  │  /chat       AI Chat (async + sync + history)          │  │
│  │  /users      User profiles & family                    │  │
│  │  /medications Medication tracking & interactions       │  │
│  │  /vitals     Vital sign measurements                   │  │
│  │  /documents  Document upload & parsing                 │  │
│  │  /health-goals Goal tracking & milestones              │  │
│  │  /appointments Doctor booking system                   │  │
│  │  /notifications Push notification management           │  │
│  │  /preferences User settings (HIPAA audit)              │  │
│  │  /consent    GDPR/HIPAA consent management             │  │
│  │  /calendar   Google Calendar integration               │  │
│  │  /memory     Patient memory CRUD & search              │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                  HEALTH ROUTES                         │  │
│  │                                                        │  │
│  │  /devices         IoT/wearable device management       │  │
│  │  /health-alerts   Health alert engine                   │  │
│  │  /predict         Heart disease ML prediction          │  │
│  │  /drug-interaction Drug interaction database           │  │
│  │  /symptom-checker  Symptom analysis & triage           │  │
│  │  /medical-images  Medical imaging analysis             │  │
│  │  /fhir           FHIR R4 interoperability              │  │
│  │  /openfda        FDA adverse events & recalls          │  │
│  │  /medical-coding ICD-10/SNOMED/CPT coding              │  │
│  │  /rag            RAG pipeline direct access            │  │
│  │  /embeddings     Embedding generation service          │  │
│  │  /research       Deep research agent                   │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                  ADMIN ROUTES                          │  │
│  │                                                        │  │
│  │  /admin          System health & stats                 │  │
│  │  /compliance     HIPAA audit log & reports             │  │
│  │  /monitoring     Prometheus metrics & circuit breakers │  │
│  │  /safety         Content safety dashboard              │  │
│  │  /data-export    GDPR data export/download             │  │
│  │  /emergency      Emergency data access (break-glass)   │  │
│  │  /performance    Performance reports & cache stats     │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## Core Routes

### Authentication (`/auth`)

```
POST /auth/register    ──▶ Create user account
POST /auth/login       ──▶ Get JWT token (Argon2 hash verify)
POST /auth/logout      ──▶ Invalidate token (Redis blocklist)
POST /auth/refresh     ──▶ Refresh expired JWT token
```

### Chat (`/chat`)

```
┌──────────────────────────────────────────────────────┐
│                   CHAT FLOW                          │
│                                                      │
│  Async (recommended):                                │
│  POST /chat/send ──▶ ARQ Job Queue ──▶ Background    │
│       │                                processing   │
│       ▼                                    │         │
│  Returns: { job_id }                       │         │
│       │                                    │         │
│       ▼                                    ▼         │
│  GET /chat/result/{job_id} ◄──── LangGraph result   │
│                                                      │
│  Sync (simple):                                      │
│  POST /chat/sync ──▶ Direct LangGraph ──▶ Response  │
│                                                      │
│  History:                                            │
│  GET  /chat/history        ──▶ Past conversations   │
│  POST /chat/session/archive ──▶ Archive old session │
└──────────────────────────────────────────────────────┘
```

### Medications (`/medications`)

```
GET    /medications              ──▶ List user medications
POST   /medications              ──▶ Add new medication
PUT    /medications/{id}         ──▶ Update medication
DELETE /medications/{id}         ──▶ Remove medication
POST   /medications/check-interactions ──▶ Check drug interactions
PATCH  /medications/{id}/taken-today   ──▶ Mark as taken
```

### Vitals (`/vitals`)

```
POST /vitals            ──▶ Record new vital measurement
GET  /vitals            ──▶ Get latest vitals
GET  /vitals/history    ──▶ Historical readings (date range)
GET  /vitals/statistics ──▶ Averages, trends, min/max
```

### Documents (`/documents`)

```
POST /documents/upload       ──▶ Upload & parse (MinerU/Docling)
GET  /documents/{doc_id}     ──▶ Retrieve parsed document
POST /documents/batch-upload ──▶ Multiple file upload
```

### Health Goals (`/health-goals`)

```
GET  /goals               ──▶ List active goals
POST /goals               ──▶ Create new goal
PUT  /goals/{id}          ──▶ Update goal
POST /goals/{id}/progress ──▶ Log progress
GET  /goals/{id}/milestones ──▶ View milestones
```

### Appointments (`/appointments`)

```
GET  /appointments/providers     ──▶ Search doctors
GET  /appointments/availability  ──▶ Available time slots
POST /appointments/book          ──▶ Book appointment
PUT  /appointments/{id}/status   ──▶ Confirm/cancel/complete
POST /appointments/intake        ──▶ Submit pre-visit intake form
```

### Notifications (`/notifications`)

```
POST /notifications/register-device ──▶ Register push token
POST /notifications/send            ──▶ Send notification
GET  /notifications/history         ──▶ Notification history
POST /notifications/schedule        ──▶ Schedule future notification
```

### Other Core Routes

| Route | Purpose |
|-------|---------|
| `GET/PUT /preferences` | User settings with HIPAA audit |
| `GET/POST /consents` | GDPR/HIPAA consent management |
| `DELETE /consents/revoke` | Revoke data consent |
| `GET /calendar/auth-url` | Google Calendar OAuth |
| `POST /calendar/callback` | OAuth callback handler |
| `GET /calendar/events` | Calendar events |
| `POST /calendar/sync-appointments` | Sync appointments to calendar |
| `GET/POST/DELETE /memories` | Patient memory CRUD |
| `POST /memories/search` | Semantic memory search |
| `GET /memories/context` | Get memory context for chat |
| `GET/PUT /users/profile` | User profile management |
| `PUT /users/password` | Change password |
| `GET /users/family` | Family member access |
| `DELETE /users/account` | Delete account (GDPR) |

---

## Health Routes

### Heart Disease Prediction (`/predict`)

```
POST /predict         ──▶ Submit patient data ──▶ ML Risk Score
GET  /predict/history ──▶ Past prediction results
GET  /predict/model-info ──▶ Model version & accuracy
```

### Drug Interaction Check (`/drug-interaction`)

```
POST /drug-interaction/check     ──▶ Check drug pair
GET  /drug-interaction/drug/{name} ──▶ All interactions for a drug
```

### Symptom Checker (`/symptom-checker`)

```
POST /symptom-checker/analyze ──▶ Symptoms ──▶ Triage + Differentials
GET  /symptom-checker/common  ──▶ Common symptom list
```

### Medical Imaging (`/medical-images`)

```
POST /medical-images/upload  ──▶ Upload medical image
POST /medical-images/analyze ──▶ AI analysis (X-ray, ECG, etc.)
                                  Supports: DICOM, pathology, radiology
```

### IoT Devices (`/devices`)

```
POST /devices/register   ──▶ Register wearable device
POST /devices/data        ──▶ Submit device readings
GET  /devices             ──▶ List connected devices
GET  /devices/timeseries  ──▶ Historical device data
```

### FHIR Interoperability (`/fhir`)

```
GET  /fhir/patient/{id}    ──▶ FHIR R4 Patient resource
GET  /fhir/observations    ──▶ FHIR Observations
POST /fhir/bundle          ──▶ Submit FHIR Bundle
```

### OpenFDA (`/openfda`)

```
GET /openfda/adverse-events ──▶ FAERS adverse event reports
GET /openfda/recalls        ──▶ Drug/food recall data
GET /openfda/labels         ──▶ FDA-approved drug labels
GET /openfda/food-events    ──▶ CAERS food adverse events
```

### Other Health Routes

| Route | Purpose |
|-------|---------|
| `POST /medical-coding/auto-code` | Auto-assign ICD-10/SNOMED/CPT codes |
| `GET /medical-coding/lookup/{system}/{code}` | Code lookup |
| `POST /rag/query` | Direct RAG pipeline query |
| `POST /rag/ingest` | Ingest new documents into RAG |
| `GET /rag/collections` | List vector store collections |
| `POST /rag/rerank` | Rerank search results |
| `POST /embeddings/generate` | Generate embeddings |
| `POST /embeddings/batch` | Batch embedding generation |
| `POST /research/start` | Start deep research job |
| `GET /research/status/{id}` | Research job status |
| `GET /research/result/{id}` | Research results |

---

## Admin Routes

### System Administration (`/admin`)

```
GET  /admin/health       ──▶ System health check
GET  /admin/stats        ──▶ System statistics
POST /admin/cache/clear  ──▶ Clear all caches
GET  /admin/config       ──▶ Current configuration (sanitized)
```

### Compliance (`/compliance`)

```
GET  /compliance/audit-log      ──▶ HIPAA audit log
POST /compliance/verify-content ──▶ Content safety check
GET  /compliance/report         ──▶ Compliance report
```

### Monitoring (`/monitoring`)

```
GET /monitoring/metrics          ──▶ Prometheus metrics (text format)
GET /monitoring/health/detailed  ──▶ Per-service health status
GET /monitoring/circuit-breakers ──▶ Circuit breaker states
```

### Safety Dashboard (`/safety`)

```
GET  /safety/dashboard        ──▶ Content safety overview
GET  /safety/flagged-content  ──▶ Flagged responses
POST /safety/review           ──▶ Review flagged content
```

### Data Export (`/data-export`)

```
POST /data-export/export      ──▶ Request GDPR data export
GET  /data-export/status/{id} ──▶ Export job status
GET  /data-export/download/{id} ──▶ Download exported data
```

### Emergency Access (`/emergency`)

```
GET /emergency/patient/{id}/emergency ──▶ Emergency data access
                                         (break-glass with audit trail)
```

### Performance (`/performance`)

```
GET /performance/report       ──▶ Performance metrics report
GET /performance/slow-queries ──▶ Slow query analysis
GET /performance/cache-stats  ──▶ Cache hit/miss rates
```

---

## Request Flow

```
Client Request
      │
      ▼
┌──────────────┐
│    CORS      │  Check allowed origins
│  Middleware  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Timeout    │  300s max request time
│  Middleware  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   JWT Auth   │  Verify Bearer token
│   (if needed)│  Rate limit check
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Memory     │  Inject patient memory
│  Context     │  context (if available)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Route      │  Process request
│   Handler    │  (business logic)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Response   │  Pydantic v2 validation
│  Validation  │  HTML sanitization
└──────┬───────┘
       │
       ▼
   JSON Response
```

---

## Authentication

Protected routes require a JWT Bearer token:

```
Authorization: Bearer <jwt_token>

Token payload:
{
  "sub": "user_id",
  "exp": 1740000000,  // expiry timestamp
  "iat": 1739900000   // issued at
}

Token flow:
1. POST /auth/login → { access_token, refresh_token }
2. Attach to requests: Authorization: Bearer <access_token>
3. On 401 → POST /auth/refresh with refresh_token
4. POST /auth/logout → token added to Redis blocklist
```

---

## File Reference

### Core Routes

| File | Purpose |
|------|---------|
| `routes/auth.py` | JWT authentication |
| `routes/chat.py` | AI chat (async/sync) |
| `routes/users.py` | User profiles |
| `routes/medications.py` | Medication CRUD |
| `routes/vitals.py` | Vital signs |
| `routes/documents.py` | Document upload |
| `routes/health_goals.py` | Goal tracking |
| `routes/appointments.py` | Appointment booking |
| `routes/notifications.py` | Push notifications |
| `routes/preferences.py` | User preferences |
| `routes/consent.py` | GDPR/HIPAA consent |
| `routes/calendar_integration.py` | Google Calendar |
| `routes/memory.py` | Patient memory |

### Health Routes

| File | Purpose |
|------|---------|
| `routes/predict.py` | Heart disease prediction |
| `routes/drug_interaction.py` | Drug interactions |
| `routes/symptom_checker.py` | Symptom analysis |
| `routes/medical_images.py` | Medical imaging |
| `routes/devices.py` | IoT devices |
| `routes/health_alerts.py` | Health alerts |
| `routes/fhir.py` | FHIR R4 |
| `routes/openfda.py` | OpenFDA |
| `routes/medical_coding.py` | Medical coding |
| `routes/rag.py` | RAG pipeline |
| `routes/embeddings.py` | Embedding service |
| `routes/research.py` | Deep research |

### Admin Routes

| File | Purpose |
|------|---------|
| `routes/admin.py` | System admin |
| `routes/compliance.py` | HIPAA compliance |
| `routes/monitoring.py` | Observability |
| `routes/safety_dashboard.py` | Content safety |
| `routes/data_export.py` | GDPR export |
| `routes/emergency_data.py` | Emergency access |
| `routes/performance.py` | Performance metrics |

---

*This document describes the Routes Architecture of HeartGuard AI v2.1.0*
