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

import { handleError, retryWithBackoff, ErrorType } from '../utils/errorHandling';
import { authService } from './authService';
import { HeartDiseasePredictionRequest, HeartDiseasePredictionResponse, DocumentDetails } from './api.types';

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  headers?: Record<string, string>;
  body?: any;
  timeout?: number;
  skipAuth?: boolean; // Skip authentication for login/register endpoints
  skipDedup?: boolean; // Skip request deduplication
  retries?: number; // Number of retries for failed requests
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

// ============================================================================
// Request Deduplication
// ============================================================================

// In-flight requests map for deduplication
const inFlightRequests = new Map<string, Promise<any>>();

/**
 * Generate a cache key for request deduplication
 */
function getRequestKey(endpoint: string, options: RequestOptions): string {
  return `${options.method || 'GET'}:${endpoint}:${JSON.stringify(options.body || {})}`;
}

// ============================================================================
// Request/Response Interceptors
// ============================================================================

type RequestInterceptor = (endpoint: string, options: RequestOptions) => RequestOptions;
type ResponseInterceptor = <T>(response: T, endpoint: string) => T;

const requestInterceptors: RequestInterceptor[] = [];
const responseInterceptors: ResponseInterceptor[] = [];

/**
 * Add a request interceptor
 */
export function addRequestInterceptor(interceptor: RequestInterceptor): void {
  requestInterceptors.push(interceptor);
}

/**
 * Add a response interceptor
 */
export function addResponseInterceptor(interceptor: ResponseInterceptor): void {
  responseInterceptors.push(interceptor);
}

/**
 * Clear all interceptors
 */
export function clearInterceptors(): void {
  requestInterceptors.length = 0;
  responseInterceptors.length = 0;
}

// ============================================================================
// Centralized Error Handler
// ============================================================================

/**
 * Process API errors with user-friendly messages
 */
function processApiError(error: unknown): APIError {
  if (error instanceof APIError) {
    return error;
  }

  if (error instanceof TypeError && error.message === 'Failed to fetch') {
    return new APIError(0, 'Network error. Please check your connection.', { type: ErrorType.NETWORK });
  }

  if (error instanceof DOMException && error.name === 'AbortError') {
    return new APIError(0, 'Request timeout. Please try again.', { type: ErrorType.TIMEOUT });
  }

  return new APIError(
    0,
    error instanceof Error ? error.message : 'Unknown error occurred',
    error
  );
}

async function apiCall<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  // Apply request interceptors
  let processedOptions = { ...options };
  for (const interceptor of requestInterceptors) {
    processedOptions = interceptor(endpoint, processedOptions);
  }

  const {
    method = 'GET',
    headers = {},
    body,
    timeout = 30000,
    skipAuth = false,
    skipDedup = false,
    retries = 0,
  } = processedOptions;

  // Request deduplication for GET requests
  const requestKey = getRequestKey(endpoint, processedOptions);
  if (method === 'GET' && !skipDedup) {
    const existingRequest = inFlightRequests.get(requestKey);
    if (existingRequest) {
      console.log(`[API] Deduplicating request: ${requestKey}`);
      return existingRequest;
    }
  }

  // Check for offline status before making request
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    throw new APIError(
      0,
      'Device is offline',
      { type: ErrorType.OFFLINE }
    );
  }

  // Inject auth header if available and not skipped
  const authHeaders: Record<string, string> = {};
  if (!skipAuth) {
    const authHeader = authService.getAuthHeader();
    if (authHeader) {
      authHeaders['Authorization'] = authHeader;
    }
  }

  const url = `${API_BASE_URL}${endpoint}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders,
        ...headers,
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    // Handle 401 Unauthorized - token expired or invalid
    if (response.status === 401 && !skipAuth) {
      // Try to refresh token
      const refreshed = await handleTokenRefresh();
      if (refreshed) {
        // Retry request with new token
        return apiCall<T>(endpoint, options);
      } else {
        // Refresh failed, clear auth
        authService.clearAuth();
        // Redirect to login if in browser (window defined)
        if (typeof window !== 'undefined') {
          window.location.hash = '#/login';
        }
        throw new APIError(401, 'Session expired. Please log in again.');
      }
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new APIError(
        response.status,
        errorData.error || `HTTP ${response.status}`,
        errorData
      );
    }

    let result = (await response.json()) as T;

    // Apply response interceptors
    for (const interceptor of responseInterceptors) {
      result = interceptor(result, endpoint);
    }

    // Clear from in-flight on success
    inFlightRequests.delete(requestKey);

    return result;
  } catch (error) {
    clearTimeout(timeoutId);

    // Clear from in-flight on error
    inFlightRequests.delete(requestKey);

    // Retry logic for transient errors
    if (retries > 0 && error instanceof APIError) {
      // Retry on network errors or 5xx errors
      if (error.status === 0 || error.status >= 500) {
        console.log(`[API] Retrying request (${retries} attempts left): ${endpoint}`);
        await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1 second
        return apiCall<T>(endpoint, { ...processedOptions, retries: retries - 1 });
      }
    }

    throw processApiError(error);
  }
}

// ============================================================================
// Token Refresh Helper
// ============================================================================

/**
 * Attempt to refresh the access token using the refresh token
 * Returns true if successful, false otherwise
 */
async function handleTokenRefresh(): Promise<boolean> {
  try {
    const refreshToken = authService.getRefreshToken();
    if (!refreshToken) {
      console.log('[Auth] No refresh token available');
      return false;
    }

    console.log('[Auth] Attempting token refresh...');
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      console.log('[Auth] Token refresh failed:', response.status);
      return false;
    }

    const data = await response.json();

    // Store new tokens
    authService.setToken(data.token);
    if (data.refresh_token) {
      authService.setRefreshToken(data.refresh_token);
    }

    console.log('[Auth] Token refreshed successfully');
    return true;
  } catch (error) {
    console.error('[Auth] Token refresh error:', error);
    return false;
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
  // ==========================================================================
  // HEART DISEASE API
  // ==========================================================================

  /**
   * Predict Heart Disease Risk
   */
  predictHeartDisease: async (data: HeartDiseasePredictionRequest) => {
    return apiCall<HeartDiseasePredictionResponse>('/api/predict-heart-disease', {
      method: 'POST',
      body: data
    });
  },

  // ==========================================================================
  // AUTHENTICATION API
  // ==========================================================================

  /**
   * Login with email and password
   */
  login: async (email: string, password: string) => {
    return apiCall<{
      user: {
        id: string;
        email: string;
        name: string;
        role: string;
      };
      token: string;
      refresh_token?: string;
    }>('/auth/login', {
      method: 'POST',
      body: { email, password },
      skipAuth: true,
    });
  },

  /**
   * Register new user
   */
  register: async (data: {
    email: string;
    password: string;
    name: string;
  }) => {
    return apiCall<{
      user: {
        id: string;
        email: string;
        name: string;
      };
      token: string;
      refresh_token?: string;
    }>('/auth/register', {
      method: 'POST',
      body: data,
      skipAuth: true,
    });
  },

  /**
   * Logout current user
   */
  logout: async () => {
    return apiCall<{ message: string }>('/auth/logout', {
      method: 'POST',
    });
  },

  /**
   * Get current authenticated user
   */
  me: async () => {
    return apiCall<{
      id: string;
      email: string;
      name: string;
      role: string;
    }>('/auth/me');
  },

  /**
   * Refresh authentication token
   */
  refreshToken: async (refreshToken: string) => {
    return apiCall<{
      token: string;
      refresh_token?: string;
    }>('/auth/refresh', {
      method: 'POST',
      body: { refresh_token: refreshToken },
      skipAuth: true,
    });
  },

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
      disclaimer?: string;
      context_used?: string[];
      provider?: string;
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
      allergen_warnings?: string[];
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
      allergies_considered?: string[];
      provider?: string;
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
    // Check for offline status before making request
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      yield { type: 'error', data: { error: 'You are currently offline. Please check your internet connection.' } };
      return;
    }

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

  // ==========================================================================
  // DOCUMENT API
  // ==========================================================================

  uploadDocument: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiCall<DocumentUploadResponse>('/api/documents/upload', {
      method: 'POST',
      body: formData,
    });
  },

  processDocument: async (documentId: string) => {
    return apiCall<DocumentProcessingResult>(`/api/documents/process/${documentId}`, {
      method: 'POST',
    });
  },

  getDocument: async (documentId: string) => {
    return apiCall<DocumentResponse>(`/api/documents/${documentId}`);
  },

  getDocuments: async () => {
    return apiCall<DocumentDetails[]>('/api/documents');
  },

  // ==========================================================================
  // VISION API
  // ==========================================================================

  analyzeECG: async (file: File, context?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    if (context) formData.append('patient_context', context);
    return apiCall<ECGAnalysisResponse>('/api/vision/ecg/analyze', {
      method: 'POST',
      body: formData,
    });
  },

  recognizeFood: async (file: File, estimatePortions: boolean = true) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('estimate_portions', String(estimatePortions));
    return apiCall<FoodAnalysisResponse>('/api/vision/food/recognize', {
      method: 'POST',
      body: formData,
    });
  },

  logMeal: async (userId: string, file: File, mealType: string, notes?: string) => {
    const formData = new FormData();
    formData.append('user_id', userId);
    formData.append('file', file);
    formData.append('meal_type', mealType);
    if (notes) formData.append('notes', notes);
    return apiCall<any>('/api/vision/food/log-meal', {
      method: 'POST',
      body: formData,
    });
  },

  // ==========================================================================
  // CALENDAR API
  // ==========================================================================

  storeCalendarCredentials: async (userId: string, credentials: any) => {
    return apiCall<any>(`/api/calendar/${userId}/credentials`, {
      method: 'POST',
      body: credentials,
    });
  },

  syncCalendar: async (userId: string, options: any) => {
    return apiCall<SyncResponse>(`/api/calendar/${userId}/sync`, {
      method: 'POST',
      body: options,
    });
  },

  getCalendarEvents: async (userId: string, start?: string, end?: string) => {
    const params = new URLSearchParams();
    if (start) params.append('start_date', start);
    if (end) params.append('end_date', end);
    return apiCall<CalendarEventResponse[]>(`/api/calendar/${userId}/events?${params.toString()}`);
  },

  scheduleReminder: async (userId: string, reminder: any) => {
    return apiCall<ReminderResponse>(`/api/calendar/${userId}/reminder`, {
      method: 'POST',
      body: reminder,
    });
  },

  // ==========================================================================
  // NOTIFICATIONS API
  // ==========================================================================

  sendWhatsApp: async (request: any) => {
    return apiCall<any>('/api/notifications/whatsapp', {
      method: 'POST',
      body: request,
    });
  },

  sendEmail: async (request: any) => {
    return apiCall<any>('/api/notifications/email', {
      method: 'POST',
      body: request,
    });
  },

  registerDevice: async (userId: string, token: string, platform: string) => {
    return apiCall<any>('/api/notifications/register-device', {
      method: 'POST',
      body: { user_id: userId, device_token: token, platform },
    });
  },

  sendPushNotification: async (request: {
    user_id: string;
    title: string;
    body: string;
    data?: any;
  }) => {
    return apiCall<any>('/api/notifications/push', {
      method: 'POST',
      body: request,
    });
  },

  // ==========================================================================
  // SMARTWATCH API
  // ==========================================================================

  registerSmartwatch: async (device: any) => {
    return apiCall<any>('/api/smartwatch/register', {
      method: 'POST',
      body: device,
    });
  },

  ingestVitals: async (payload: any) => {
    return apiCall<any>('/api/smartwatch/vitals/ingest', {
      method: 'POST',
      body: payload,
    });
  },

  getAggregatedVitals: async (deviceId: string, metric: string, interval: string) => {
    return apiCall<any>(`/api/smartwatch/vitals/${deviceId}/aggregated?metric_type=${metric}&interval=${interval}`);
  },

  analyzeHealth: async (data: any) => {
    return apiCall<any>('/api/smartwatch/analyze', {
      method: 'POST',
      body: data,
    });
  },

  // ==========================================================================
  // MEDICATIONS API
  // ==========================================================================

  /**
   * Get all medications for a user
   */
  getMedications: async (userId: string) => {
    return apiCall<Array<{
      id: string;
      name: string;
      dosage: string;
      schedule: string[];
      frequency: string;
      startDate?: string;
      endDate?: string;
      notes?: string;
    }>>(`/api/users/${userId}/medications`);
  },

  /**
   * Add a new medication for a user
   */
  addMedication: async (userId: string, medication: {
    name: string;
    dosage: string;
    schedule: string[];
    frequency: string;
    startDate?: string;
    endDate?: string;
    notes?: string;
  }) => {
    return apiCall<{
      id: string;
      name: string;
      dosage: string;
      schedule: string[];
      frequency: string;
      startDate?: string;
      endDate?: string;
      notes?: string;
    }>(`/api/users/${userId}/medications`, {
      method: 'POST',
      body: medication,
    });
  },

  /**
   * Update an existing medication
   */
  updateMedication: async (userId: string, medicationId: string, medication: Partial<{
    name: string;
    dosage: string;
    schedule: string[];
    frequency: string;
    startDate?: string;
    endDate?: string;
    notes?: string;
  }>) => {
    return apiCall<{
      id: string;
      name: string;
      dosage: string;
      schedule: string[];
      frequency: string;
      startDate?: string;
      endDate?: string;
      notes?: string;
    }>(`/api/users/${userId}/medications/${medicationId}`, {
      method: 'PUT',
      body: medication,
    });
  },

  /**
   * Delete a medication
   */
  deleteMedication: async (userId: string, medicationId: string) => {
    return apiCall<{ message: string }>(`/api/users/${userId}/medications/${medicationId}`, {
      method: 'DELETE',
    });
  },

  // ==========================================================================
  // KNOWLEDGE GRAPH API
  // ==========================================================================

  searchGraph: async (query: string, nodeTypes?: string[]) => {
    return apiCall<GraphSearchResponse>('/api/knowledge-graph/search', {
      method: 'POST',
      body: { query, node_types: nodeTypes },
    });
  },

  createNode: async (node: any) => {
    return apiCall<any>('/api/knowledge-graph/node', {
      method: 'POST',
      body: node,
    });
  },

  ragQuery: async (query: string) => {
    return apiCall<{ answer: string; context: any[] }>('/api/knowledge-graph/rag-query', {
      method: 'POST',
      body: { query },
    });
  },

  // ==========================================================================
  // INTEGRATIONS API
  // ==========================================================================

  getPatientTimeline: async (userId: string, days: number = 30) => {
    return apiCall<TimelineEvent[]>(`/api/integrations/timeline/${userId}?days=${days}`);
  },

  getWeeklySummary: async (userId: string) => {
    return apiCall<any>(`/api/integrations/weekly-summary/${userId}`);
  },

  predictFromDocument: async (documentId: string, userId: string, patientProfile: any = {}) => {
    return apiCall<any>('/api/integrations/predict-from-document', {
      method: 'POST',
      body: { document_id: documentId, user_id: userId, patient_profile: patientProfile },
    });
  },

  triggerWeeklySummary: async (userId: string) => {
    return apiCall<any>('/api/weekly-summary/trigger', {
      method: 'POST',
      body: { user_id: userId },
    });
  },

  // ==========================================================================
  // MEDICAL AI API
  // ==========================================================================

  extractMedicalEntities: async (text: string) => {
    return apiCall<any>('/api/medical-ai/extract-entities', {
      method: 'POST',
      body: { text },
    });
  },

  getPatientSummary: async (userId: string) => {
    return apiCall<any>('/api/medical-ai/patient-summary', {
      method: 'POST',
      body: { user_id: userId },
    });
  },

  expandTerminology: async (term: string) => {
    return apiCall<any>('/api/medical-ai/terminology', {
      method: 'POST',
      body: { term },
    });
  },

  // ==========================================================================
  // TOOLS API
  // ==========================================================================

  recordBloodPressure: async (systolic: number, diastolic: number, userId: string) => {
    return apiCall<any>('/api/tools/blood-pressure', {
      method: 'POST',
      body: { systolic, diastolic, user_id: userId, timestamp: new Date().toISOString() },
    });
  },

  recordHeartRate: async (bpm: number, userId: string) => {
    return apiCall<any>('/api/tools/heart-rate', {
      method: 'POST',
      body: { bpm, user_id: userId, timestamp: new Date().toISOString() },
    });
  },

  checkDrugInteractions: async (medications: string[]) => {
    return apiCall<any>('/api/tools/drug-interactions', {
      method: 'POST',
      body: { medications },
    });
  },

  symptomTriage: async (symptoms: string[], userId: string) => {
    return apiCall<any>('/api/tools/symptom-triage', {
      method: 'POST',
      body: { symptoms, user_id: userId },
    });
  },

  // ==========================================================================
  // COMPLIANCE API
  // ==========================================================================

  getDisclaimer: async (type: string) => {
    return apiCall<any>(`/api/compliance/disclaimer/${type}`);
  },

  encryptPHI: async (data: any) => {
    return apiCall<any>('/api/compliance/encrypt-phi', {
      method: 'POST',
      body: { data },
    });
  },

  getVerificationQueue: async () => {
    return apiCall<any>('/api/compliance/verification/pending');
  },

  submitVerification: async (itemId: string, verified: boolean, notes?: string) => {
    return apiCall<any>('/api/compliance/verification/submit', {
      method: 'POST',
      body: { item_id: itemId, verified, notes },
    });
  },

  // ==========================================================================
  // CONSENT MANAGEMENT API
  // ==========================================================================

  getConsent: async (userId: string) => {
    return apiCall<any>(`/api/consent/${userId}`);
  },

  updateConsent: async (userId: string, consents: any) => {
    return apiCall<any>(`/api/consent/${userId}`, {
      method: 'PUT',
      body: consents,
    });
  },

  revokeConsent: async (userId: string, consentType: string) => {
    return apiCall<any>(`/api/consent/${userId}/${consentType}`, {
      method: 'DELETE',
    });
  },

  // ==========================================================================
  // SMARTWATCH ADDITIONAL APIs
  // ==========================================================================

  // Removed duplicate analyzeHealth function to fix TS1117 error

  // ==========================================================================
  // EVALUATION APIs (Admin/Developer)
  // ==========================================================================

  evaluateRAG: async (queries: string[], groundTruth?: any[]) => {
    return apiCall<any>('/api/evaluation/rag', {
      method: 'POST',
      body: { queries, ground_truth: groundTruth },
    });
  },

  getWebSocketUrl: (endpoint: string) => {
    const wsBase = API_BASE_URL.replace('http', 'ws');
    return `${wsBase}${endpoint}`;
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

export interface TimelineEvent {
  id: string;
  event_type: string;
  timestamp: string;
  title: string;
  description: string;
  source: string;
  importance: string;
  verified: boolean;
  data: Record<string, any>;
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

// ============================================================================
// DOCUMENT TYPES
// ============================================================================

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  status: string;
}

export interface DocumentProcessingResult {
  text: string;
  metadata: Record<string, any>;
  entities: any[];
}

export interface DocumentResponse {
  id: string;
  content: string;
  processed_at: string;
}

// ============================================================================
// VISION TYPES
// ============================================================================

export interface ECGAnalysisResponse {
  rhythm: string;
  heart_rate_bpm?: number;
  abnormalities: string[];
  recommendations: string[];
  confidence: number;
}

export interface FoodAnalysisResponse {
  food_items: any[];
  total_calories?: number;
  macros: Record<string, number>;
  health_score?: number;
  recommendations: string[];
}

// ============================================================================
// CALENDAR TYPES
// ============================================================================

export interface SyncResponse {
  events_synced: number;
  reminders_created: number;
  sync_completed_at: string;
}

export interface CalendarEventResponse {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
  location?: string;
  description?: string;
}

export interface ReminderResponse {
  id: string;
  appointment_id: string;
  scheduled_for: string;
  status: string;
}

// ============================================================================
// KNOWLEDGE GRAPH TYPES
// ============================================================================

export interface GraphSearchResponse {
  query: string;
  nodes: any[];
  relationships: any[];
  paths: string[][];
  total_results: number;
}

export { APIError };
