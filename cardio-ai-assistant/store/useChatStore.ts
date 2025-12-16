/**
 * Chat Store - Zustand slice for chat state management
 * 
 * Centralizes all chat-related state:
 * - Messages
 * - Sessions
 * - Loading states
 * - Model selection
 * - UI preferences
 */

import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';

// ============================================================================
// Types
// ============================================================================

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  
  // Extended fields
  isError?: boolean;
  isStreaming?: boolean;
  thinkingContent?: string;
  metadata?: {
    model?: string;
    processingTime?: number;
    tokens?: number;
    memoryContext?: string[];
    citations?: Citation[];
  };
}

export interface Citation {
  id: string;
  source: string;
  title: string;
  snippet: string;
  relevance: number;
}

export interface ChatSession {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
  lastMessage?: string;
  model?: 'gemini' | 'ollama';
}

export type ModelType = 'gemini' | 'ollama';

export interface ChatState {
  // Messages
  messages: Message[];
  currentSessionId: string | null;
  sessions: ChatSession[];
  
  // UI State
  isLoading: boolean;
  isStreaming: boolean;
  isSearchingMemories: boolean;
  error: string | null;
  
  // Preferences
  selectedModel: ModelType;
  isThinkingEnabled: boolean;
  autoSaveEnabled: boolean;
  
  // Voice
  isRecording: boolean;
  isPlayingId: string | null;
  
  // Actions
  setMessages: (messages: Message[]) => void;
  addMessage: (message: Message) => void;
  updateMessage: (id: string, updates: Partial<Message>) => void;
  removeMessage: (id: string) => void;
  clearMessages: () => void;
  
  // Session actions
  createSession: (title?: string) => string;
  loadSession: (sessionId: string) => void;
  deleteSession: (sessionId: string) => void;
  updateSessionTitle: (sessionId: string, title: string) => void;
  
  // State setters
  setLoading: (loading: boolean) => void;
  setStreaming: (streaming: boolean) => void;
  setSearchingMemories: (searching: boolean) => void;
  setError: (error: string | null) => void;
  
  // Preference setters
  setSelectedModel: (model: ModelType) => void;
  setThinkingEnabled: (enabled: boolean) => void;
  
  // Voice actions
  setRecording: (recording: boolean) => void;
  setPlayingId: (id: string | null) => void;
  
  // Computed
  getCurrentSession: () => ChatSession | null;
  getSessionMessages: (sessionId: string) => Message[];
}

// ============================================================================
// Initial State
// ============================================================================

const generateId = () => `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
const generateSessionId = () => `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

const defaultMessage: Message = {
  id: 'welcome',
  role: 'assistant',
  content: "Hello! I'm your AI health assistant. How can I help you today with your cardiovascular health?",
  timestamp: new Date().toISOString(),
};

const initialState = {
  messages: [defaultMessage],
  currentSessionId: null,
  sessions: [],
  isLoading: false,
  isStreaming: false,
  isSearchingMemories: false,
  error: null,
  selectedModel: 'gemini' as ModelType,
  isThinkingEnabled: false,
  autoSaveEnabled: true,
  isRecording: false,
  isPlayingId: null,
};

// ============================================================================
// Store
// ============================================================================

export const useChatStore = create<ChatState>()(
  devtools(
    persist(
      immer((set, get) => ({
        ...initialState,

        // Message actions
        setMessages: (messages) => set({ messages }),
        
        addMessage: (message) => set((state) => {
          state.messages.push({
            ...message,
            id: message.id || generateId(),
            timestamp: message.timestamp || new Date().toISOString(),
          });
          
          // Update session
          if (state.currentSessionId) {
            const session = state.sessions.find(s => s.id === state.currentSessionId);
            if (session) {
              session.updatedAt = new Date().toISOString();
              session.messageCount = state.messages.length;
              session.lastMessage = message.content.slice(0, 100);
            }
          }
        }),
        
        updateMessage: (id, updates) => set((state) => {
          const index = state.messages.findIndex(m => m.id === id);
          if (index !== -1) {
            state.messages[index] = { ...state.messages[index], ...updates };
          }
        }),
        
        removeMessage: (id) => set((state) => {
          state.messages = state.messages.filter(m => m.id !== id);
        }),
        
        clearMessages: () => set((state) => {
          state.messages = [defaultMessage];
        }),

        // Session actions
        createSession: (title) => {
          const sessionId = generateSessionId();
          const now = new Date().toISOString();
          
          set((state) => {
            state.sessions.unshift({
              id: sessionId,
              title: title || `Chat ${state.sessions.length + 1}`,
              createdAt: now,
              updatedAt: now,
              messageCount: 1,
              model: state.selectedModel,
            });
            state.currentSessionId = sessionId;
            state.messages = [defaultMessage];
          });
          
          return sessionId;
        },
        
        loadSession: (sessionId) => set((state) => {
          // In real implementation, would load from backend/storage
          const session = state.sessions.find(s => s.id === sessionId);
          if (session) {
            state.currentSessionId = sessionId;
            // Messages would be loaded from persistent storage
          }
        }),
        
        deleteSession: (sessionId) => set((state) => {
          state.sessions = state.sessions.filter(s => s.id !== sessionId);
          if (state.currentSessionId === sessionId) {
            state.currentSessionId = null;
            state.messages = [defaultMessage];
          }
        }),
        
        updateSessionTitle: (sessionId, title) => set((state) => {
          const session = state.sessions.find(s => s.id === sessionId);
          if (session) {
            session.title = title;
          }
        }),

        // State setters
        setLoading: (loading) => set({ isLoading: loading }),
        setStreaming: (streaming) => set({ isStreaming: streaming }),
        setSearchingMemories: (searching) => set({ isSearchingMemories: searching }),
        setError: (error) => set({ error }),

        // Preference setters
        setSelectedModel: (model) => set({ selectedModel: model }),
        setThinkingEnabled: (enabled) => set({ isThinkingEnabled: enabled }),

        // Voice actions
        setRecording: (recording) => set({ isRecording: recording }),
        setPlayingId: (id) => set({ isPlayingId: id }),

        // Computed
        getCurrentSession: () => {
          const state = get();
          return state.sessions.find(s => s.id === state.currentSessionId) || null;
        },
        
        getSessionMessages: (sessionId) => {
          // In real implementation, would fetch from storage
          const state = get();
          return state.currentSessionId === sessionId ? state.messages : [];
        },
      })),
      {
        name: 'chat-store',
        partialize: (state) => ({
          sessions: state.sessions,
          selectedModel: state.selectedModel,
          isThinkingEnabled: state.isThinkingEnabled,
          autoSaveEnabled: state.autoSaveEnabled,
        }),
      }
    ),
    { name: 'ChatStore' }
  )
);

// ============================================================================
// Selectors (for performance optimization)
// ============================================================================

export const selectMessages = (state: ChatState) => state.messages;
export const selectIsLoading = (state: ChatState) => state.isLoading;
export const selectIsStreaming = (state: ChatState) => state.isStreaming;
export const selectSelectedModel = (state: ChatState) => state.selectedModel;
export const selectSessions = (state: ChatState) => state.sessions;
export const selectCurrentSession = (state: ChatState) => 
  state.sessions.find(s => s.id === state.currentSessionId);

// ============================================================================
// Actions (standalone for use outside components)
// ============================================================================

export const chatActions = {
  sendMessage: async (content: string, model?: ModelType) => {
    const store = useChatStore.getState();
    
    // Add user message
    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };
    store.addMessage(userMessage);
    store.setLoading(true);
    store.setError(null);
    
    try {
      const selectedModel = model || store.selectedModel;
      
      // Create assistant message placeholder
      const assistantId = generateId();
      store.addMessage({
        id: assistantId,
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
        isStreaming: true,
      });
      
      store.setStreaming(true);
      
      // API call would go here
      // For now, simulate response
      const response = await simulateApiCall(content, selectedModel);
      
      // Update assistant message with response
      store.updateMessage(assistantId, {
        content: response.content,
        isStreaming: false,
        metadata: response.metadata,
      });
      
    } catch (error) {
      store.setError(error instanceof Error ? error.message : 'Failed to send message');
    } finally {
      store.setLoading(false);
      store.setStreaming(false);
    }
  },
  
  regenerateLastResponse: async () => {
    const store = useChatStore.getState();
    const messages = store.messages;
    
    // Find last user message
    const lastUserMsgIndex = [...messages].reverse().findIndex(m => m.role === 'user');
    if (lastUserMsgIndex === -1) return;
    
    const lastUserMsg = messages[messages.length - 1 - lastUserMsgIndex];
    
    // Remove last assistant message
    const lastMsg = messages[messages.length - 1];
    if (lastMsg.role === 'assistant') {
      store.removeMessage(lastMsg.id);
    }
    
    // Resend
    await chatActions.sendMessage(lastUserMsg.content);
  },
};

// Simulate API call (replace with actual implementation)
async function simulateApiCall(
  content: string, 
  model: ModelType
): Promise<{ content: string; metadata: Message['metadata'] }> {
  await new Promise(r => setTimeout(r, 1000));
  return {
    content: `[Simulated ${model} response] You asked: "${content.slice(0, 50)}..."`,
    metadata: {
      model,
      processingTime: 1000,
      tokens: content.length + 50,
    },
  };
}
