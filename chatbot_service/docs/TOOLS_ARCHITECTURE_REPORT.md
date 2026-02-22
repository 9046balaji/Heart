# Tools Architecture Report

## HeartGuard AI — Agent Tools & Integrations

> **Version:** 2.1.0  
> **Last Updated:** February 2026  
> **Author:** HeartGuard AI Team

---

## Table of Contents

1. [Overview](#overview)
2. [Tool Architecture](#tool-architecture)
3. [Core Medical Tools](#core-medical-tools)
4. [OpenFDA Integration](#openfda-integration)
5. [FHIR Integration](#fhir-integration)
6. [Medical Imaging Tools](#medical-imaging-tools)
7. [Medical Coding](#medical-coding)
8. [Web Search Tools](#web-search-tools)
9. [Data Files](#data-files)
10. [File Reference](#file-reference)

---

## Overview

**Tools** are callable functions that AI agents can use during conversation. When the LangGraph Orchestrator routes a query to a specialist agent, that agent uses its assigned tools to fetch real data — drug interactions, patient vitals, FDA reports, appointment availability, etc.

**Key Idea:** Tools connect the AI to real-world data sources, ensuring responses are based on actual patient records and verified medical databases — not just the LLM's training data.

---

## Tool Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       TOOL ECOSYSTEM                             │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                   CORE MEDICAL TOOLS                       │  │
│  │                                                            │  │
│  │  ┌────────────────┐  ┌─────────────────┐  ┌────────────┐  │  │
│  │  │  Drug          │  │  Symptom        │  │  Health    │  │  │
│  │  │  Interaction   │  │  Checker        │  │  Data      │  │  │
│  │  │  Checker       │  │                 │  │  Tool      │  │  │
│  │  │                │  │  NLP-based      │  │            │  │  │
│  │  │  PostgreSQL +  │  │  triage with    │  │  Unified   │  │  │
│  │  │  JSON fallback │  │  urgency        │  │  vitals,   │  │  │
│  │  │  severity      │  │  levels         │  │  meds,     │  │  │
│  │  │  scoring       │  │                 │  │  goals,    │  │  │
│  │  │                │  │                 │  │  alerts    │  │  │
│  │  └────────────────┘  └─────────────────┘  └────────────┘  │  │
│  │                                                            │  │
│  │  ┌────────────────┐  ┌─────────────────┐  ┌────────────┐  │  │
│  │  │  Medication    │  │  Appointment    │  │  Patient   │  │  │
│  │  │  Tool          │  │  Tool           │  │  Context   │  │  │
│  │  │                │  │                 │  │  Tool      │  │  │
│  │  │  Add/update/   │  │  Provider       │  │            │  │  │
│  │  │  delete/list   │  │  search, book,  │  │  Full      │  │  │
│  │  │  medications   │  │  cancel,        │  │  patient   │  │  │
│  │  │                │  │  reschedule     │  │  data for  │  │  │
│  │  │                │  │                 │  │  LLM       │  │  │
│  │  └────────────────┘  └─────────────────┘  └────────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                  EXTERNAL INTEGRATIONS                     │  │
│  │                                                            │  │
│  │  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐ │  │
│  │  │ OpenFDA  │  │   FHIR    │  │  DICOM   │  │ Medical  │ │  │
│  │  │ (5 tools)│  │   R4      │  │  Parser  │  │ Coding   │ │  │
│  │  │          │  │           │  │          │  │          │ │  │
│  │  │ Adverse  │  │ Patient   │  │ Pixel    │  │ ICD-10   │ │  │
│  │  │ Events   │  │ Observe   │  │ Extract  │  │ SNOMED   │ │  │
│  │  │ Recalls  │  │ MedReq    │  │ Metadata │  │ CPT      │ │  │
│  │  │ Labels   │  │           │  │ Anonymize│  │ LOINC    │ │  │
│  │  └──────────┘  └───────────┘  └──────────┘  └──────────┘ │  │
│  │                                                            │  │
│  │  ┌──────────────┐  ┌────────────────┐                     │  │
│  │  │  Pathology   │  │  Radiology     │                     │  │
│  │  │  WSI Analyzer│  │  Volume Viewer │                     │  │
│  │  │              │  │                │                     │  │
│  │  │  OpenSlide   │  │  NiBabel NIfTI │                     │  │
│  │  │  Tile extract│  │  MIP/Slice     │                     │  │
│  │  └──────────────┘  └────────────────┘                     │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                   SEARCH TOOLS                             │  │
│  │                                                            │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │  WebSearchTool                                       │  │  │
│  │  │  • DuckDuckGo (primary)                              │  │  │
│  │  │  • Tavily (backup)                                   │  │  │
│  │  │  • Medical site prioritization                       │  │  │
│  │  │    (WHO, CDC, NIH, FDA, PubMed)                      │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Core Medical Tools

### Drug Interaction Checker

```
┌──────────────────────────────────────────────────────┐
│         DRUG INTERACTION CHECKER                     │
│                                                      │
│  Input: Drug A + Drug B                              │
│                                                      │
│       ┌──────────────┐                               │
│       │  PostgreSQL   │  Primary data source          │
│       │  drug_inter-  │                               │
│       │  actions table│                               │
│       └──────┬───────┘                               │
│              │                                       │
│         Found? ──No──▶ ┌──────────────┐              │
│              │         │  JSON file    │  Fallback    │
│             Yes        │  interactions │              │
│              │         │  .json        │              │
│              ▼         └──────┬───────┘              │
│       ┌──────────────┐       │                       │
│       │ Severity     │◀──────┘                       │
│       │ Scoring      │                               │
│       │              │                               │
│       │ major        │ ──▶ High risk, avoid          │
│       │ moderate     │ ──▶ Monitor closely            │
│       │ minor        │ ──▶ Generally safe             │
│       └──────────────┘                               │
│                                                      │
│  Output: severity, mechanism, recommendation,        │
│          evidence_level, source (FDA/AHA/ESC)        │
└──────────────────────────────────────────────────────┘
```

### Symptom Checker

```
Input: List of symptoms ──▶ NLP Analysis ──▶ Triage Level

Urgency Levels:
┌──────────────┐
│  EMERGENCY   │ ──▶ "Call 911 immediately"
│  URGENT      │ ──▶ "Visit ER within hours"
│  MODERATE    │ ──▶ "Schedule doctor visit"
│  LOW         │ ──▶ "Monitor at home"
│  SELF-CARE   │ ──▶ "Home remedies sufficient"
└──────────────┘
```

### Health Data Tool

```
Query ──▶ HealthDataTool ──▶ Aggregates from multiple sources:
              │
              ├── Vitals (blood pressure, heart rate, SpO2)
              ├── Medications (current prescriptions)
              ├── Goals (weight loss, exercise, etc.)
              └── Alerts (pending health alerts)
```

### Medication Tool

```
CRUD operations on user medications:

ADD    → name, dosage, frequency, schedule, instructions
UPDATE → modify any field
DELETE → remove medication
LIST   → all current medications
MARK   → taken_today flag
```

### Appointment Tool

```
Provider Search ──▶ Filter by specialty, rating, insurance
Availability   ──▶ Check open time slots
Book           ──▶ Reserve appointment
Cancel         ──▶ Cancel with reason
Reschedule     ──▶ Move to different time
```

### Patient Context Tool

```
┌──────────────────────────────────────────┐
│  PATIENT CONTEXT TOOL                    │
│                                          │
│  Aggregates ALL patient data into a      │
│  single context block for the LLM:       │
│                                          │
│  ├── Demographics (age, sex)             │
│  ├── Current medications                 │
│  ├── Recent vitals                       │
│  ├── Known allergies                     │
│  ├── Medical history                     │
│  ├── Active health goals                 │
│  ├── Pending alerts                      │
│  └── Recent appointments                 │
│                                          │
│  Used by: ThinkingAgent, Supervisor      │
└──────────────────────────────────────────┘
```

---

## OpenFDA Integration

5 tools connected to the FDA's public API:

```
┌──────────────────────────────────────────────────────┐
│                    OPENFDA SUITE                     │
│                                                      │
│  Base: OpenFDABaseTool                               │
│  ├── HTTP client with rate limiting                  │
│  ├── Response parsing and normalization              │
│  └── Error handling and retry                        │
│                                                      │
│  ┌──────────────────────────────────────────┐        │
│  │  1. AdverseEventsTool                    │        │
│  │     FAERS database                       │        │
│  │     Search: drug name, reaction, date    │        │
│  │     Returns: reported adverse events     │        │
│  └──────────────────────────────────────────┘        │
│                                                      │
│  ┌──────────────────────────────────────────┐        │
│  │  2. DrugEnforcementTool                  │        │
│  │     Drug recall database                 │        │
│  │     Returns: recall reason, class, firm  │        │
│  └──────────────────────────────────────────┘        │
│                                                      │
│  ┌──────────────────────────────────────────┐        │
│  │  3. DrugLabelsTool                       │        │
│  │     FDA-approved drug labels             │        │
│  │     Returns: indications, warnings,      │        │
│  │     dosage, contraindications            │        │
│  └──────────────────────────────────────────┘        │
│                                                      │
│  ┌──────────────────────────────────────────┐        │
│  │  4. FoodEnforcementTool                  │        │
│  │     Food recall database                 │        │
│  │     Returns: food safety recalls         │        │
│  └──────────────────────────────────────────┘        │
│                                                      │
│  ┌──────────────────────────────────────────┐        │
│  │  5. FoodEventsTool                       │        │
│  │     CAERS database                       │        │
│  │     Returns: food adverse event reports  │        │
│  └──────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────┘
```

---

## FHIR Integration

Healthcare interoperability via FHIR R4 standard:

```
┌──────────────────────────────────────────────────────┐
│                  FHIR R4 CLIENT                      │
│                                                      │
│  ┌──────────────────────────────────────────┐        │
│  │  FHIRClient (AsyncFHIRClient wrapper)    │        │
│  │                                          │        │
│  │  Resource CRUD:                          │        │
│  │  • Patient — demographics, identifiers   │        │
│  │  • Observation — lab results, vitals     │        │
│  │  • MedicationRequest — prescriptions     │        │
│  │  • Bundle — batch resource operations    │        │
│  │                                          │        │
│  │  Used by: fhir_agent_tool in Orchestrator│        │
│  └──────────────────────────────────────────┘        │
│                                                      │
│  ┌──────────────────────────────────────────┐        │
│  │  FHIR Resources                          │        │
│  │                                          │        │
│  │  Mappers convert between:                │        │
│  │  HeartGuard models ◄──▶ FHIR R4 JSON     │        │
│  └──────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────┘
```

---

## Medical Imaging Tools

### DICOM Parser

```
┌──────────────────────────────────────────────────────┐
│                  DICOM PARSER                        │
│                                                      │
│  Input: DICOM file (.dcm)                            │
│                                                      │
│  Functions:                                          │
│  ├── Pixel extraction → numpy array → image          │
│  ├── Metadata extraction:                            │
│  │   patient name, study date, modality,             │
│  │   body part, institution                          │
│  ├── Anonymization:                                  │
│  │   Remove all patient-identifying fields           │
│  │   (HIPAA Safe Harbor method)                      │
│  └── Window/level adjustment for display             │
│                                                      │
│  Library: pydicom                                    │
└──────────────────────────────────────────────────────┘
```

### Pathology WSI Analyzer

```
┌──────────────────────────────────────────────────────┐
│             WSI (Whole-Slide Imaging)                 │
│                                                      │
│  Input: Whole-slide image file                       │
│                                                      │
│  Functions:                                          │
│  ├── Multi-resolution tile extraction                │
│  ├── Region-of-interest selection                    │
│  ├── Magnification levels (1x → 40x)                │
│  └── Batch tile processing for AI analysis           │
│                                                      │
│  Library: OpenSlide                                  │
└──────────────────────────────────────────────────────┘
```

### Radiology Volume Viewer

```
┌──────────────────────────────────────────────────────┐
│              VOLUME VIEWER                           │
│                                                      │
│  Input: NIfTI file (.nii.gz)                         │
│                                                      │
│  Functions:                                          │
│  ├── 3D volume loading                               │
│  ├── MIP (Maximum Intensity Projection)              │
│  ├── Axial/Coronal/Sagittal slice rendering          │
│  └── Windowing for CT/MRI contrast                   │
│                                                      │
│  Library: NiBabel                                    │
└──────────────────────────────────────────────────────┘
```

---

## Medical Coding

```
┌──────────────────────────────────────────────────────┐
│                 AUTO CODER                           │
│                                                      │
│  Input: Clinical text (notes, reports)               │
│                                                      │
│  Output: Suggested codes from 4 systems:             │
│                                                      │
│  ┌────────────┐  ┌────────────┐                      │
│  │  ICD-10    │  │ SNOMED-CT  │                      │
│  │            │  │            │                      │
│  │ Diagnoses  │  │ Clinical   │                      │
│  │ & conditions│ │ concepts   │                      │
│  └────────────┘  └────────────┘                      │
│                                                      │
│  ┌────────────┐  ┌────────────┐                      │
│  │   LOINC    │  │    CPT     │                      │
│  │            │  │            │                      │
│  │ Lab tests  │  │ Procedures │                      │
│  │ & results  │  │ & services │                      │
│  └────────────┘  └────────────┘                      │
│                                                      │
│  Method: NLP entity extraction → code matching       │
└──────────────────────────────────────────────────────┘
```

---

## Web Search Tools

```
┌──────────────────────────────────────────────────────┐
│               WEB SEARCH TOOL                        │
│                                                      │
│  ┌─────────────────────────────────────────────┐     │
│  │  Primary: DuckDuckGo                         │     │
│  │  Backup:  Tavily                             │     │
│  │                                             │     │
│  │  Medical site prioritization:               │     │
│  │  ├── WHO (who.int)                          │     │
│  │  ├── CDC (cdc.gov)                          │     │
│  │  ├── NIH (nih.gov)                          │     │
│  │  ├── FDA (fda.gov)                          │     │
│  │  ├── PubMed (pubmed.ncbi.nlm.nih.gov)      │     │
│  │  ├── Mayo Clinic                            │     │
│  │  └── Cleveland Clinic                       │     │
│  └─────────────────────────────────────────────┘     │
│                                                      │
│  Used by:                                            │
│  • CRAG fallback (when RAG confidence is low)        │
│  • Deep Research Agent                               │
│  • Researcher worker in Orchestrator                 │
└──────────────────────────────────────────────────────┘
```

---

## Data Files

Static knowledge bases used by tools:

### drugs.json

| Category | Count | Examples |
|----------|-------|---------|
| Cardiovascular | 62 | aspirin, atorvastatin, lisinopril, metoprolol |
| Diabetes | 21 | metformin, empagliflozin, semaglutide |
| Analgesics | 11 | acetaminophen, ibuprofen, morphine |
| Anticoagulants | 9 | warfarin, heparin, apixaban |
| Antiplatelets | 7 | aspirin, clopidogrel, ticagrelor |

### interactions.json

25 drug-drug interactions with severity, mechanism, recommendation, evidence level, and source (FDA, AHA/ACC, ESC).

Example:
```
warfarin + aspirin = MAJOR
  → "Increased risk of bleeding"
  → "Avoid combination or monitor INR closely"
  → Source: FDA
```

### symptoms.json

| Category | Count | Examples |
|----------|-------|---------|
| Cardiac | 35 | chest pain, palpitations, syncope |
| General | 34 | fatigue, fever, headache, nausea |
| Respiratory | 12 | shortness of breath, hemoptysis |
| Metabolic | 10 | polyuria, polydipsia, hyperglycemia |

---

## How Tools Connect to Agents

```
┌──────────────────────────┐
│   LangGraph Orchestrator │
│                          │
│   drug_expert_node ──────┼──▶ DrugInteractionChecker
│   data_analyst_node ─────┼──▶ HealthDataTool (SQL)
│   heart_analyst_node ────┼──▶ HeartDiseasePredictor
│   thinking_node ─────────┼──▶ All tools (dynamic)
│   fhir_query_node ───────┼──▶ FHIRClient
│   clinical_reasoning ────┼──▶ TriageSystem + DDx
│   researcher_node ───────┼──▶ WebSearchTool + Crawler
│   medical_analyst_node ──┼──▶ RAG Pipeline
└──────────────────────────┘
```

---

## File Reference

### Core Tools

| File | Purpose |
|------|---------|
| `tools/drug_interaction_checker.py` | Drug interaction analysis |
| `tools/symptom_checker.py` | Symptom triage |
| `tools/health_data_tool.py` | Unified health data query |
| `tools/medication_tool.py` | Medication CRUD |
| `tools/appointment_tool.py` | Appointment booking |
| `tools/web_search_tool.py` | Medical web search |
| `tools/patient_context_tool.py` | Full patient context |

### OpenFDA Tools

| File | Purpose |
|------|---------|
| `tools/openfda/base.py` | Base HTTP client |
| `tools/openfda/adverse_events.py` | FAERS database |
| `tools/openfda/drug_enforcement.py` | Drug recalls |
| `tools/openfda/drug_labels.py` | Drug labeling |
| `tools/openfda/food_enforcement.py` | Food recalls |
| `tools/openfda/food_events.py` | CAERS database |

### FHIR Tools

| File | Purpose |
|------|---------|
| `tools/fhir/client.py` | FHIR R4 async client |
| `tools/fhir/resources.py` | Resource mappers |

### Imaging Tools

| File | Purpose |
|------|---------|
| `tools/dicom/parser.py` | DICOM file parser |
| `tools/pathology/wsi_analyzer.py` | Whole-slide imaging |
| `tools/radiology/volume_viewer.py` | 3D volume rendering |

### Medical Coding

| File | Purpose |
|------|---------|
| `tools/medical_coding/auto_coder.py` | Auto ICD-10/SNOMED/CPT coding |

### Data Files

| File | Purpose |
|------|---------|
| `data/drugs.json` | 110+ categorized drug names |
| `data/interactions.json` | 25 drug interaction pairs |
| `data/symptoms.json` | 91 categorized symptoms |

---

*This document describes the Tools Architecture of HeartGuard AI v2.1.0*
