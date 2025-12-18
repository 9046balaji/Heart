/**
 * API Client Service
 * All frontend API calls go through this service to the backend
 * NO API KEYS are stored in the frontend
 */

// Use empty string for API_BASE_URL when using Vite proxy (VITE_API_URL is empty or '/')
// When VITE_API_URL is empty, endpoints will be relative like /api/...
// When using proxy, /api paths are automatically forwarded to backend
// Updated to point to the new NLP service instead of Flask backend
const API_BASE_URL = (import.meta as any).env.VITE_NLP_SERVICE_URL && (import.meta as any).env.VITE_NLP_SERVICE_URL !== '/' 
  ? (import.meta as any).env.VITE_NLP_SERVICE_URL 
  : 'http://localhost:5001';

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  headers?: Record<string, string>;
  body?: any;
  timeout?: number;
}

class APIError extends Error {
  constructor(
    public status: number,
    public message: string,
    public data?: any
  ) {
    super(message);
    this.name = 'APIError';
  }
}

async function apiCall<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const {
    method = 'GET',
    headers = {},
    body,
    timeout = 30000,
  } = options;

  const url = `${API_BASE_URL}${endpoint}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new APIError(
        response.status,
        errorData.error || `HTTP ${response.status}`,
        errorData
      );
    }

    return (await response.json()) as T;
  } catch (error) {
    clearTimeout(timeoutId);

    if (error instanceof APIError) {
      throw error;
    }

    if (error instanceof TypeError && error.message === 'Failed to fetch') {
      throw new APIError(
        0,
        'Network error. Please check your connection.',
        error
      );
    }

    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new APIError(
        0,
        'Request timeout. Please try again.',
        error
      );
    }

    throw new APIError(
      0,
      error instanceof Error ? error.message : 'Unknown error occurred',
      error
    );
  }
}

// ============================================================================
// Retry Logic
// ============================================================================

const RETRY_STATUS_CODES = [408, 429, 500, 502, 503, 504];
const MAX_RETRIES = 3;
const INITIAL_DELAY_MS = 1000;

interface RetryOptions extends RequestOptions {
  maxRetries?: number;
  retryDelay?: number;
}

/**
 * API call with automatic retry for transient failures
 * Uses exponential backoff between retries
 */
async function apiCallWithRetry<T>(
  endpoint: string,
  options: RetryOptions = {}
): Promise<T> {
  const { maxRetries = MAX_RETRIES, retryDelay = INITIAL_DELAY_MS, ...requestOptions } = options;
  let lastError: APIError | null = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await apiCall<T>(endpoint, requestOptions);
    } catch (error) {
      if (!(error instanceof APIError)) {
        throw error;
      }

      lastError = error;

      // Don't retry client errors (4xx) except for specific ones
      const isRetryableStatus = RETRY_STATUS_CODES.includes(error.status);
      const isNetworkError = error.status === 0;
      
      if (!isRetryableStatus && !isNetworkError) {
        throw error;
      }

      // Don't retry on last attempt
      if (attempt === maxRetries) {
        break;
      }

      // Exponential backoff with jitter
      const delay = retryDelay * Math.pow(2, attempt) + Math.random() * 100;
      console.log(`[API] Retry ${attempt + 1}/${maxRetries} after ${Math.round(delay)}ms for ${endpoint}`);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }

  throw lastError!;
}

// ============================================================================
// API ENDPOINTS
// ============================================================================

export const apiClient = {
  /**
   * Generate daily health insight
   */
  generateInsight: async (params: {
    user_name: string;
    vitals: {
      heart_rate?: number;
      blood_pressure?: string;
      blood_glucose?: number;
    };
    activities?: string[];
    medications?: string[];
  }) => {
    return apiCall<{
      insight: string;
      timestamp: string;
    }>('/api/generate-insight', {
      method: 'POST',
      body: params,
    });
  },

  /**
   * Analyze recipe for nutritional insights
   */
  analyzeRecipe: async (params: {
    recipe_name: string;
    ingredients: string[];
    servings?: number;
    user_preferences?: string[];
  }) => {
    return apiCall<{
      analysis: string;
      recipe: string;
      timestamp: string;
    }>('/api/analyze-recipe', {
      method: 'POST',
      body: params,
    });
  },

  /**
   * Analyze workout for performance insights
   */
  analyzeWorkout: async (params: {
    workout_type: string;
    duration_minutes: number;
    intensity?: string;
    heart_rate_data?: number[];
    user_goals?: string[];
  }) => {
    return apiCall<{
      analysis: string;
      workout_type: string;
      timestamp: string;
    }>('/api/analyze-workout', {
      method: 'POST',
      body: params,
    });
  },

  /**
   * Generate personalized meal plan
   */
  generateMealPlan: async (params: {
    dietary_preferences: string[];
    calorie_target?: number;
    days?: number;
    allergies?: string[];
  }) => {
    return apiCall<{
      meal_plan: string;
      days: number;
      timestamp: string;
    }>('/api/generate-meal-plan', {
      method: 'POST',
      body: params,
    });
  },

  /**
   * Perform comprehensive health assessment
   */
  healthAssessment: async (params: {
    user_name: string;
    age?: number;
    vitals: Record<string, any>;
    health_history?: string[];
    lifestyle?: Record<string, any>;
  }) => {
    return apiCall<{
      assessment: string;
      user: string;
      timestamp: string;
    }>('/api/health-assessment', {
      method: 'POST',
      body: params,
    });
  },

  /**
   * Get medication-related insights
   */
  medicationInsights: async (params: {
    medications: Array<{ name: string; dosage: string }>;
    supplements?: string[];
    recent_vitals?: Record<string, any>;
  }) => {
    return apiCall<{
      insights: string;
      medication_count: number;
      timestamp: string;
    }>('/api/medication-insights', {
      method: 'POST',
      body: params,
    });
  },

  /**
   * Health check
   */
  healthCheck: async () => {
    return apiCall<{
      status: string;
      service: string;
    }>('/api/health');
  },

  /**
   * Process text with NLP service
   */
  processNLP: async (params: {
    message: string;
    session_id?: string;
    user_id?: string;
    context?: any;
    model?: 'gemini' | 'ollama';
  }) => {
    return apiCall<{
      intent: string;
      sentiment: string;
      entities: any[];
      suggested_response?: string;
      requires_escalation?: boolean;
    }>('/api/nlp/process', {
      method: 'POST',
      body: params,
    });
  },

  /**
   * Stream response from Ollama (Server-Sent Events)
   * Returns an async generator that yields tokens as they arrive
   */
  streamOllamaResponse: async function* (params: {
    message: string;
    model?: string;
    conversation_history?: Array<{ role: string; content: string }>;
    temperature?: number;
  }): AsyncGenerator<{ type: 'token' | 'done' | 'error'; data: string | any }> {
    const url = `${API_BASE_URL}/api/chat/stream`;
    
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(params),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            
            if (data.startsWith('[DONE]')) {
              const metadata = JSON.parse(data.slice(6));
              yield { type: 'done', data: metadata };
            } else if (data.startsWith('[ERROR]')) {
              const error = JSON.parse(data.slice(7));
              yield { type: 'error', data: error };
            } else {
              yield { type: 'token', data: data };
            }
          }
        }
      }
    } catch (error) {
      yield { type: 'error', data: { error: error instanceof Error ? error.message : 'Unknown error' } };
    }
  },

  // ============================================================================
  // STRUCTURED OUTPUT ENDPOINTS
  // These endpoints return LLM responses that match predefined JSON schemas
  // ============================================================================

  /**
   * Check if structured outputs feature is available
   */
  getStructuredOutputsStatus: async () => {
    return apiCall<StructuredOutputsStatus>('/api/structured-outputs/status');
  },

  /**
   * Get the JSON schema for a specific output type
   */
  getStructuredSchema: async (schemaName: StructuredSchemaName) => {
    return apiCall<{
      schema_name: string;
      json_schema: Record<string, any>;
      description: string;
    }>(`/api/structured-outputs/schema/${schemaName}`);
  },

  /**
   * Generate a structured health analysis from user message
   * Returns comprehensive health analysis with intent, sentiment, entities, recommendations
   */
  structuredHealthAnalysis: async (params: StructuredHealthAnalysisRequest) => {
    return apiCall<StructuredResponse<CardioHealthAnalysis>>(
      '/api/structured-outputs/health-analysis',
      {
        method: 'POST',
        body: params,
      }
    );
  },

  /**
   * Generate a quick intent analysis
   * Lightweight classification of user intent
   */
  structuredIntentAnalysis: async (params: { message: string }) => {
    return apiCall<StructuredResponse<SimpleIntentAnalysis>>(
      '/api/structured-outputs/intent',
      {
        method: 'POST',
        body: params,
      }
    );
  },

  /**
   * Generate a structured conversation response
   */
  structuredConversation: async (params: StructuredConversationRequest) => {
    return apiCall<StructuredResponse<ConversationResponse>>(
      '/api/structured-outputs/conversation',
      {
        method: 'POST',
        body: params,
      }
    );
  },

  // ==========================================================================
  // USER PREFERENCES API
  // ==========================================================================

  /**
   * Get all user preferences
   */
  getPreferences: async (userId: string): Promise<UserPreferences> => {
    return apiCall<UserPreferences>(`/api/memory/preferences/${userId}`);
  },

  /**
   * Get a specific user preference
   */
  getPreference: async (userId: string, key: string): Promise<{ key: string; value: unknown }> => {
    return apiCall<{ key: string; value: unknown }>(`/api/memory/preferences/${userId}/${key}`);
  },

  /**
   * Update user preferences
   */
  updatePreferences: async (userId: string, preferences: Partial<UserPreferences>): Promise<void> => {
    return apiCall<void>(`/api/memory/preferences/${userId}`, {
      method: 'PUT',
      body: preferences,
    });
  },

  /**
   * Bulk update user preferences
   */
  bulkUpdatePreferences: async (userId: string, preferences: Record<string, unknown>): Promise<void> => {
    return apiCall<void>(`/api/memory/preferences/${userId}/bulk`, {
      method: 'PUT',
      body: { preferences },
    });
  },

  /**
   * Delete a specific user preference
   */
  deletePreference: async (userId: string, key: string): Promise<void> => {
    return apiCall<void>(`/api/memory/preferences/${userId}/${key}`, {
      method: 'DELETE',
    });
  },

  // ==========================================================================
  // GDPR COMPLIANCE API
  // ==========================================================================

  /**
   * Export all user data for GDPR compliance
   * Returns all stored data associated with the user
   */
  exportUserData: async (userId: string): Promise<GDPRExportData> => {
    return apiCall<GDPRExportData>(`/api/memory/gdpr/export/${userId}`, {
      method: 'POST',
      timeout: 60000, // Longer timeout for data export
    });
  },

  /**
   * Delete all user data for GDPR compliance (Right to be Forgotten)
   * This is irreversible - use with caution
   */
  deleteUserData: async (userId: string): Promise<GDPRDeleteResponse> => {
    return apiCall<GDPRDeleteResponse>(`/api/memory/gdpr/delete/${userId}`, {
      method: 'DELETE',
      timeout: 60000, // Longer timeout for data deletion
    });
  },

  /**
   * Get audit log for user data access
   */
  getAuditLog: async (userId: string, limit?: number): Promise<AuditLogEntry[]> => {
    const params = limit ? `?limit=${limit}` : '';
    return apiCall<AuditLogEntry[]>(`/api/memory/audit/${userId}${params}`);
  },

  // ==========================================================================
  // ANALYTICS API
  // ==========================================================================

  /**
   * Get analytics summary for the application
   */
  getAnalyticsSummary: async (): Promise<AnalyticsSummary> => {
    return apiCall<AnalyticsSummary>('/api/analytics/summary');
  },

  /**
   * Get intent distribution analytics
   */
  getIntentAnalytics: async (): Promise<IntentAnalytics> => {
    return apiCall<IntentAnalytics>('/api/analytics/intents');
  },

  /**
   * Get sentiment distribution analytics
   */
  getSentimentAnalytics: async (): Promise<SentimentAnalytics> => {
    return apiCall<SentimentAnalytics>('/api/analytics/sentiments');
  },

  /**
   * Get entity extraction analytics
   */
  getEntityAnalytics: async (): Promise<EntityAnalytics> => {
    return apiCall<EntityAnalytics>('/api/analytics/entities');
  },

  /**
   * Get top intents by frequency
   */
  getTopIntents: async (limit?: number): Promise<TopIntentsResponse> => {
    const params = limit ? `?limit=${limit}` : '';
    return apiCall<TopIntentsResponse>(`/api/analytics/top-intents${params}`);
  },

  /**
   * Get top entities by frequency
   */
  getTopEntities: async (limit?: number): Promise<TopEntitiesResponse> => {
    const params = limit ? `?limit=${limit}` : '';
    return apiCall<TopEntitiesResponse>(`/api/analytics/top-entities${params}`);
  },

  // ==========================================================================
  // MODEL MANAGEMENT API
  // ==========================================================================

  /**
   * Get all model versions
   */
  getModelVersions: async (): Promise<ModelVersionsResponse> => {
    return apiCall<ModelVersionsResponse>('/api/models/versions');
  },

  /**
   * Get version history for a specific model
   */
  getModelHistory: async (modelName: string): Promise<ModelHistoryResponse> => {
    return apiCall<ModelHistoryResponse>(`/api/models/history/${modelName}`);
  },

  /**
   * List all available models
   */
  listModels: async (): Promise<ModelsListResponse> => {
    return apiCall<ModelsListResponse>('/api/models/list');
  },
};

// ============================================================================
// STRUCTURED OUTPUT TYPE DEFINITIONS
// These types match the Pydantic schemas in the backend
// ============================================================================

/** Confidence levels for LLM responses */
export type ResponseConfidence = 'high' | 'medium' | 'low' | 'uncertain';

/** Healthcare-specific intents */
export type HealthIntent = 
  | 'symptom_report'
  | 'medication_question'
  | 'lifestyle_advice'
  | 'emergency'
  | 'appointment'
  | 'general_health'
  | 'vital_signs'
  | 'diet_nutrition'
  | 'exercise'
  | 'mental_health'
  | 'unknown';

/** Urgency classification for health queries */
export type UrgencyLevel = 
  | 'critical'   // Requires immediate attention
  | 'high'       // Should see doctor soon
  | 'moderate'   // Can wait for regular appointment
  | 'low'        // General information/advice
  | 'informational';  // Just seeking knowledge

/** Available schema names */
export type StructuredSchemaName = 
  | 'CardioHealthAnalysis'
  | 'SimpleIntentAnalysis'
  | 'ConversationResponse'
  | 'VitalSignsAnalysis'
  | 'MedicationInfo';

/** Entity extracted from user input */
export interface ExtractedEntity {
  entity_type: string;
  value: string;
  confidence: number;
  context?: string;
}

/** Suggested follow-up question */
export interface FollowUpQuestion {
  question: string;
  priority: number;
  reason?: string;
}

/** Health recommendation */
export interface HealthRecommendation {
  recommendation: string;
  category: string;
  urgency: UrgencyLevel;
  evidence_based: boolean;
}

/** 
 * Main structured output for cardiovascular health analysis
 * This is the primary schema for health-related queries
 */
export interface CardioHealthAnalysis {
  intent: HealthIntent;
  intent_confidence: number;
  sentiment: string;
  urgency: UrgencyLevel;
  entities: ExtractedEntity[];
  response: string;
  explanation?: string;
  recommendations: HealthRecommendation[];
  follow_up_questions: FollowUpQuestion[];
  requires_professional: boolean;
  disclaimer?: string;
  confidence: ResponseConfidence;
}

/** Lightweight intent analysis */
export interface SimpleIntentAnalysis {
  intent: string;
  confidence: number;
  keywords: string[];
  summary: string;
}

/** Structured conversation response */
export interface ConversationResponse {
  response: string;
  tone: string;
  topics: string[];
  action_items: string[];
  needs_clarification: boolean;
}

/** Vital signs interpretation */
export interface VitalSignsAnalysis {
  metric_type: string;
  value: number;
  unit: string;
  status: string;
  interpretation: string;
  recommendations: string[];
  reference_range?: string;
}

/** Medication information */
export interface MedicationInfo {
  medication_name: string;
  purpose: string;
  common_side_effects: string[];
  interactions_warning?: string;
  dosage_reminder?: string;
  important_notes: string[];
  consult_doctor: boolean;
}

/** Status of structured outputs feature */
export interface StructuredOutputsStatus {
  enabled: boolean;
  message: string;
  available_schemas: string[];
  endpoints?: string[];
}

/** Request for structured health analysis */
export interface StructuredHealthAnalysisRequest {
  message: string;
  session_id?: string;
  patient_context?: Record<string, any>;
  model?: string;
}

/** Request for structured conversation */
export interface StructuredConversationRequest {
  message: string;
  conversation_history?: Array<{ role: string; content: string }>;
  session_id?: string;
}

/** Generic structured response wrapper */
export interface StructuredResponse<T> {
  success: boolean;
  data: T;
  metadata: {
    generation_time_ms: number;
    model?: string;
    schema: string;
  };
}

// ============================================================================
// USER PREFERENCES TYPES
// ============================================================================

/** User preferences structure */
export interface UserPreferences {
  user_id: string;
  theme?: 'light' | 'dark' | 'system';
  language?: string;
  notifications_enabled?: boolean;
  email_notifications?: boolean;
  reminder_time?: string;
  health_goals?: {
    steps?: number;
    water_intake?: number;
    exercise_minutes?: number;
  };
  privacy_settings?: {
    share_with_doctors?: boolean;
    share_with_family?: boolean;
    anonymous_analytics?: boolean;
  };
  accessibility?: {
    font_size?: 'small' | 'medium' | 'large';
    high_contrast?: boolean;
    reduce_motion?: boolean;
  };
  created_at?: string;
  updated_at?: string;
}

// ============================================================================
// GDPR TYPES
// ============================================================================

/** GDPR data export response */
export interface GDPRExportData {
  user_id: string;
  export_date: string;
  data: {
    profile: Record<string, unknown>;
    preferences: UserPreferences;
    conversations: Array<{
      session_id: string;
      messages: Array<{ role: string; content: string; timestamp: string }>;
    }>;
    health_data: Array<{
      type: string;
      data: Record<string, unknown>;
      timestamp: string;
    }>;
    audit_log: AuditLogEntry[];
  };
  format_version: string;
}

/** GDPR delete response */
export interface GDPRDeleteResponse {
  success: boolean;
  user_id: string;
  deleted_items: {
    profile: boolean;
    preferences: boolean;
    conversations: number;
    health_data: number;
    audit_entries: number;
  };
  deletion_date: string;
  confirmation_id: string;
}

/** Audit log entry for data access tracking */
export interface AuditLogEntry {
  id: string;
  user_id: string;
  action: 'read' | 'write' | 'delete' | 'export';
  resource_type: string;
  resource_id?: string;
  timestamp: string;
  ip_address?: string;
  user_agent?: string;
  details?: Record<string, unknown>;
}

// ============================================================================
// ANALYTICS TYPES
// ============================================================================

/** Analytics summary response */
export interface AnalyticsSummary {
  total_requests: number;
  total_users: number;
  average_response_time_ms: number;
  error_rate: number;
  top_intents: Array<{ intent: string; count: number }>;
  sentiment_distribution: {
    positive: number;
    negative: number;
    neutral: number;
  };
  period: {
    start: string;
    end: string;
  };
}

/** Intent analytics response */
export interface IntentAnalytics {
  total_classified: number;
  intents: Array<{
    intent: string;
    count: number;
    percentage: number;
    average_confidence: number;
  }>;
  unclassified_count: number;
  period: {
    start: string;
    end: string;
  };
}

/** Sentiment analytics response */
export interface SentimentAnalytics {
  total_analyzed: number;
  distribution: {
    positive: { count: number; percentage: number };
    negative: { count: number; percentage: number };
    neutral: { count: number; percentage: number };
  };
  average_confidence: number;
  trend: Array<{
    date: string;
    positive: number;
    negative: number;
    neutral: number;
  }>;
}

/** Entity analytics response */
export interface EntityAnalytics {
  total_extracted: number;
  entity_types: Array<{
    type: string;
    count: number;
    percentage: number;
    examples: string[];
  }>;
  extraction_rate: number;
}

/** Top intents response */
export interface TopIntentsResponse {
  intents: Array<{
    intent: string;
    count: number;
    percentage: number;
    trend: 'up' | 'down' | 'stable';
  }>;
  total_requests: number;
  period: string;
}

/** Top entities response */
export interface TopEntitiesResponse {
  entities: Array<{
    entity: string;
    type: string;
    count: number;
    percentage: number;
  }>;
  total_entities: number;
  period: string;
}

// ============================================================================
// MODEL MANAGEMENT TYPES
// ============================================================================

/** Model versions response */
export interface ModelVersionsResponse {
  models: Array<{
    name: string;
    current_version: string;
    versions: string[];
    last_updated: string;
  }>;
}

/** Model history response */
export interface ModelHistoryResponse {
  model_name: string;
  history: Array<{
    version: string;
    deployed_at: string;
    metrics?: {
      accuracy?: number;
      latency_ms?: number;
    };
    notes?: string;
  }>;
}

/** Models list response */
export interface ModelsListResponse {
  models: Array<{
    name: string;
    type: string;
    status: 'active' | 'deprecated' | 'testing';
    description?: string;
  }>;
}

export { APIError };
