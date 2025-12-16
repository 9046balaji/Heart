# 🫀 Cardio AI Assistant (HeartGuard)

An AI-powered cardiovascular health assistant built with React, TypeScript, and Google Gemini AI.

<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

## Overview

Cardio AI Assistant is a comprehensive health management application that helps users monitor their cardiovascular health through AI-powered insights, personalized recommendations, and interactive features.

## Features

### 🏠 Dashboard
- Real-time health metrics visualization
- Daily health insights from AI
- Quick access to all features

### 💬 AI Chat
- Conversational AI assistant for health queries
- Intent recognition and sentiment analysis
- Context-aware responses with medical knowledge

### 💊 Medications
- Medication tracking and reminders
- AI-powered medication insights
- Interaction warnings

### 📅 Appointments
- Schedule and manage appointments
- Provider information
- Appointment reminders

### 🥗 Nutrition
- Meal planning with AI
- Recipe analysis
- Heart-healthy recommendations

### 🏃 Exercise
- Workout tracking
- AI-powered workout analysis
- Personalized exercise recommendations

### 📊 Analytics
- Health trends and patterns
- Risk assessments
- Progress tracking

### 👥 Community
- Connect with others
- Share experiences
- Support groups

## Tech Stack

- **Frontend**: React 18 + TypeScript
- **Build Tool**: Vite
- **Styling**: CSS Modules
- **State Management**: Zustand
- **API Client**: Axios
- **Charts**: Recharts

## Project Structure

```
cardio-ai-assistant/
├── App.tsx                 # Main application component
├── index.tsx               # Entry point
├── package.json            # Dependencies
├── vite.config.ts          # Vite configuration
├── backend/                # Flask backend service
│   ├── aip_service.py      # Main Flask app (port 5000)
│   ├── smart_watch.py      # Smartwatch integration
│   └── ml/                 # ML anomaly detection pipeline
│       ├── alert_pipeline.py
│       ├── anomaly_detector.py
│       ├── chatbot_connector.py
│       ├── feature_extractor.py
│       ├── health_explainer.py
│       ├── prompt_templates.py
│       └── rule_engine.py
├── components/             # Reusable UI components
│   ├── BottomNav.tsx
│   ├── LoadingSpinner.tsx
│   ├── MarkdownRenderer.tsx
│   └── ...
├── screens/                # Page components
│   ├── DashboardScreen.tsx
│   ├── ChatScreen.tsx
│   ├── MedicationScreen.tsx
│   ├── NutritionScreen.tsx
│   ├── ExerciseScreen.tsx
│   ├── AnalyticsDashboard.tsx
│   └── ...
├── services/               # API and external services
│   ├── apiClient.ts        # HTTP client
│   ├── memoryService.ts    # Memory system integration
│   └── ...
├── store/                  # State management (Zustand)
│   ├── useHealthStore.ts
│   ├── useChatStore.ts
│   └── ...
├── contexts/               # React contexts
│   └── LanguageContext.tsx
├── hooks/                  # Custom React hooks
│   ├── useVitals.ts
│   ├── useAppointments.ts
│   └── ...
└── data/                   # Static data and translations
    ├── translations.ts
    ├── recipes.ts
    └── workouts.ts
```

## Run Locally

### Prerequisites
- Node.js 18+
- npm or yarn
- Python 3.10+ (for backend)

### Setup

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Configure environment**:
   Set the `GEMINI_API_KEY` in [.env.local](.env.local):
   ```env
   VITE_API_URL=http://localhost:5000
   VITE_NLP_URL=http://localhost:5001
   GEMINI_API_KEY=your-api-key-here
   ```

3. **Run the frontend**:
   ```bash
   npm run dev
   # Opens at http://localhost:5173
   ```

4. **Run the backend** (in a separate terminal):
   ```bash
   cd backend
   pip install -r requirements.txt
   python aip_service.py
   # Runs at http://localhost:5000
   ```

## Backend Endpoints

The Flask backend (`aip_service.py`) provides:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/generate-insight` | POST | Generate daily health insight |
| `/api/analyze-recipe` | POST | Analyze recipe nutrition |
| `/api/analyze-workout` | POST | Analyze workout performance |
| `/api/generate-meal-plan` | POST | Generate personalized meal plan |
| `/api/health-assessment` | POST | Comprehensive health assessment |
| `/api/medication-insights` | POST | Medication management insights |
| `/api/nlp/process` | POST | Proxy to NLP service |
| `/api/nlp/health` | GET | NLP service health check |

## ML Pipeline

The ML anomaly detection system (`backend/ml/`) processes smartwatch data:

- **Feature Extraction**: Statistical features from time-series data
- **Anomaly Detection**: Isolation Forest algorithm
- **Rule Engine**: Clinical threshold-based rules
- **Alert Pipeline**: Priority classification and recommendations
- **Health Explainer**: Natural language explanations
- **Chatbot Connector**: AI-powered contextual responses

## Integration with NLP Service

The frontend communicates with the NLP service (port 5001) through:
- Direct API calls for NLP processing
- Memory service for context management
- Real-time WebSocket for live updates

## Development

### Available Scripts

```bash
npm run dev      # Start development server
npm run build    # Build for production
npm run preview  # Preview production build
npm run lint     # Run ESLint
```

### Adding New Screens

1. Create component in `screens/`
2. Add route in `App.tsx`
3. Update navigation in `BottomNav.tsx`

### Adding API Endpoints

1. Add endpoint in `backend/aip_service.py`
2. Create service method in `services/apiClient.ts`
3. Use in components via hooks or stores

## Related Services

- **NLP Service**: `../nlp-service/` - Natural language processing
- **Documentation**: `../docs/` - Full project documentation

## License

Part of the HeartGuard project.
