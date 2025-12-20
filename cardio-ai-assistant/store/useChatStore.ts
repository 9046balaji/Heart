import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';
import { memoryService } from '../services/memoryService';
import { apiClient } from '../services/apiClient';
import { Message, Citation } from '../types';

// ============================================================================
// Types
// ============================================================================





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
  updateSessionTitle: (sessionId: string, title: string) => Promise<void>;
  loadSessions: (userId: string) => Promise<void>;

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

// ... (keep existing initial state)

export const useChatStore = create<ChatState>()(
  devtools(
    persist(
      immer((set, get) => ({
        ...initialState,

        // ... (keep existing message actions)

        setMessages: (messages) => set({ messages }),

        addMessage: (message) => set((state) => {
          state.messages.push({
            ...message,
            id: message.id || generateId(),
            timestamp: message.timestamp || new Date().toISOString(),
          });

          // Update session locally (backend updates on its own)
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
        loadSessions: async (userId: string) => {
          try {
            const sessions = await memoryService.getSessions(userId);
            set((state) => {
              state.sessions = sessions.map(s => ({
                id: s.sessionId,
                title: `Chat ${new Date(s.createdAt || Date.now()).toLocaleDateString()}`, // Backend might not return title
                createdAt: s.createdAt || new Date().toISOString(),
                updatedAt: s.lastActivity || new Date().toISOString(),
                messageCount: s.messageCount,
                model: 'gemini' // Default
              }));
            });
          } catch (error) {
            console.error('Failed to load sessions:', error);
          }
        },

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

        loadSession: async (sessionId) => {
          set({ isLoading: true });
          try {
            const { messages } = await memoryService.getSessionHistory(sessionId);
            set((state) => {
              state.currentSessionId = sessionId;
              state.messages = messages.map(m => ({
                id: generateId(), // Backend might not return IDs for all
                role: m.role,
                content: m.content,
                timestamp: m.timestamp || new Date().toISOString(),
                metadata: m.metadata
              }));
            });
          } catch (error) {
            console.error('Failed to load session history:', error);
            // Fallback to local if needed or just error
          } finally {
            set({ isLoading: false });
          }
        },

        deleteSession: async (sessionId) => {
          try {
            await memoryService.deleteSession(sessionId);
            set((state) => {
              state.sessions = state.sessions.filter(s => s.id !== sessionId);
              if (state.currentSessionId === sessionId) {
                state.currentSessionId = null;
                state.messages = [defaultMessage];
              }
            });
          } catch (error) {
            console.error('Failed to delete session:', error);
          }
        },

        updateSessionTitle: async (sessionId, title) => {
          try {
            await memoryService.updateSession(sessionId, { title });
            set((state) => {
              const session = state.sessions.find(s => s.id === sessionId);
              if (session) {
                session.title = title;
              }
            });
          } catch (error) {
            console.error('Failed to update session title:', error);
          }
        },

        // ... (keep state setters)
        setLoading: (loading) => set({ isLoading: loading }),
        setStreaming: (streaming) => set({ isStreaming: streaming }),
        setSearchingMemories: (searching) => set({ isSearchingMemories: searching }),
        setError: (error) => set({ error }),

        setSelectedModel: (model) => set({ selectedModel: model }),
        setThinkingEnabled: (enabled) => set({ isThinkingEnabled: enabled }),

        setRecording: (recording) => set({ isRecording: recording }),
        setPlayingId: (id) => set({ isPlayingId: id }),

        getCurrentSession: () => {
          const state = get();
          return state.sessions.find(s => s.id === state.currentSessionId) || null;
        },

        getSessionMessages: (sessionId) => {
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

// ... (keep selectors)

export const chatActions = {
  sendMessage: async (content: string, model?: ModelType) => {
    const store = useChatStore.getState();
    const userId = localStorage.getItem('user_id') || 'user_123'; // Get real user ID
    const sessionId = store.currentSessionId || store.createSession();

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

      if (selectedModel === 'ollama') {
        // Streaming with Ollama
        const generator = apiClient.streamOllamaResponse({
          message: content,
          model: 'llama3', // Or config
          conversation_history: store.messages.map(m => ({ role: m.role, content: m.content })),
        });

        let fullContent = '';
        for await (const chunk of generator) {
          if (chunk.type === 'token') {
            fullContent += chunk.data;
            store.updateMessage(assistantId, {
              content: fullContent,
            });
          } else if (chunk.type === 'error') {
            throw new Error(chunk.data.error);
          }
        }

        store.updateMessage(assistantId, {
          isStreaming: false,
        });

      } else {
        // Standard query (Gemini/Agent)
        const response = await memoryService.aiQuery(userId, sessionId, content, {
          aiProvider: 'gemini',
          patientName: 'User', // TODO: Get from profile
        });

        if (response.success) {
          store.updateMessage(assistantId, {
            content: response.response,
            isStreaming: false,
            metadata: {
              model: 'gemini',
              processingTime: response.metadata.processingTimeMs,
              tokens: response.metadata.tokensEstimated,
              memoryContext: response.contextUsed.map(c => c.source),
            },
          });
        } else {
          throw new Error(response.error || 'AI query failed');
        }
      }

    } catch (error) {
      store.setError(error instanceof Error ? error.message : 'Failed to send message');
      store.updateMessage(store.messages[store.messages.length - 1].id, {
        content: 'Sorry, I encountered an error processing your request.',
        isError: true,
        isStreaming: false
      });
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
