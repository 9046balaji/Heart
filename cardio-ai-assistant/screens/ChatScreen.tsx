
import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { apiClient } from '../services/apiClient';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Message, HealthAssessment, Medication, Appointment } from '../types';
import { memoryService } from '../services/memoryService';
import { ChatMessageMarkdown } from '../components/MarkdownRenderer';
import { useChatStore, ChatSession, chatActions } from '../store/useChatStore';

// --- Audio Helpers ---
function base64ToUint8Array(base64: string) {
  const binaryString = atob(base64);
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes;
}

async function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      if (typeof reader.result === 'string') {
        const base64 = reader.result.split(',')[1];
        resolve(base64);
      } else {
        reject(new Error('Failed to convert blob to base64'));
      }
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

// --- Tool Definitions ---
const toolsDefinition = [
  {
    functionDeclarations: [
      {
        name: "logBiometrics",
        description: "Log the user's biometric data such as blood pressure and heart rate.",
        parameters: {
          type: "OBJECT",
          properties: {
            systolic: { type: "NUMBER", description: "Systolic blood pressure (top number)" },
            diastolic: { type: "NUMBER", description: "Diastolic blood pressure (bottom number)" },
            heartRate: { type: "NUMBER", description: "Heart rate in beats per minute" }
          },
          required: ["systolic", "diastolic"]
        }
      },
      {
        name: "addMedication",
        description: "Add a new medication to the user's schedule/cabinet.",
        parameters: {
          type: "OBJECT",
          properties: {
            name: { type: "STRING", description: "Name of the medication" },
            dosage: { type: "STRING", description: "Dosage (e.g., 10mg)" },
            frequency: { type: "STRING", description: "Frequency (e.g., Daily, Twice a day)" },
            time: { type: "STRING", description: "Time to take (e.g., 08:00)" }
          },
          required: ["name", "dosage"]
        }
      },
      {
        name: "scheduleAppointment",
        description: "Schedule a doctor's appointment.",
        parameters: {
          type: "OBJECT",
          properties: {
            doctorName: { type: "STRING", description: "Name of the doctor" },
            date: { type: "STRING", description: "Date (YYYY-MM-DD) or relative like 'tomorrow'" },
            time: { type: "STRING", description: "Time (HH:MM)" },
            specialty: { type: "STRING", description: "Doctor's specialty" }
          },
          required: ["doctorName", "date"]
        }
      },
      {
        name: "navigate",
        description: "Navigate the user to a specific screen in the application.",
        parameters: {
          type: "OBJECT",
          properties: {
            screen: {
              type: "STRING",
              description: "The screen to navigate to. Valid values: dashboard, nutrition, exercise, assessment, medications, profile, settings, chat"
            }
          },
          required: ["screen"]
        }
      },
      {
        name: "showWidget",
        description: "Display a visual widget in the chat stream. Use this for charts, recipes, or lists.",
        parameters: {
          type: "OBJECT",
          properties: {
            type: { type: "STRING", description: "Type of widget: 'heartRateChart', 'bloodPressureChart', 'recipeCard'" },
            title: { type: "STRING", description: "Title of the widget" },
            data: { type: "STRING", description: "JSON stringified data. For charts: [{'day': 'Mon', 'value': 72}, ...]. For recipes: {'id': '...', 'title': '...', 'calories': 300, 'image': '...'}" }
          },
          required: ["type", "data"]
        }
      }
    ]
  }
];

// --- Extended Message Type for UI ---
interface ExtendedMessage extends Message {
  type?: 'text' | 'action_request' | 'action_result' | 'widget';
  actionData?: any;
  widgetData?: {
    type: string;
    title: string;
    data: any;
  };
  ragContext?: boolean; // Indicator if RAG was used
  image?: string; // Base64 image string for visual context
  sources?: Array<{ // RAG citation sources
    title: string;
    category?: string;
    relevance?: number;
  }>;
  groundingMetadata?: {
    groundingChunks?: Array<{
      web?: {
        uri?: string;
        title?: string;
      };
    }>;
  };
}

const ChatScreen: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [input, setInput] = useState('');
  const [attachment, setAttachment] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [userLocation, setUserLocation] = useState<{ lat: number, lng: number } | null>(null);

  // UI State
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false);

  // Feature States
  const [isRecording, setIsRecording] = useState(false);
  const [isPlayingId, setIsPlayingId] = useState<string | null>(null);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  // Refs
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const activeSourceNodeRef = useRef<AudioBufferSourceNode | null>(null);

  // Chat Store
  const {
    messages,
    sessions,
    currentSessionId,
    isLoading,
    isStreaming,
    isSearchingMemories,
    selectedModel,
    createSession,
    loadSession,
    deleteSession,
    loadSessions,
    updateSessionTitle,
    setSelectedModel,
    setMessages
  } = useChatStore();

  // Load sessions on mount
  useEffect(() => {
    const userId = localStorage.getItem('user_id') || 'user_123';
    loadSessions(userId);

    // Create a new session if none exists
    if (!currentSessionId && sessions.length === 0) {
      createSession();
    }
  }, [loadSessions, createSession, currentSessionId, sessions.length]);

  // Init Memory Service & Handle Voice Commands
  useEffect(() => {
    // Memory service will work with backend API
    memoryService.syncContext();

    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setUserLocation({
            lat: position.coords.latitude,
            lng: position.coords.longitude
          });
        },
        (error) => {
          console.debug("Error getting location", error);
        }
      );
    }

    // Check for auto-send message from voice control
    if (location.state?.autoSend) {
      handleSend(location.state.autoSend);
      // Clear state to prevent re-send on refresh
      window.history.replaceState({}, document.title);
    }

    return () => {
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, [location.state]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading, attachment]);

  // --- Tool Execution Logic (Placeholder for future implementation) ---
  // Tools are currently handled by the backend agent, but we keep these for reference
  // or client-side specific actions if needed.

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setAttachment(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const removeAttachment = () => {
    setAttachment(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // --- Main Chat Logic ---
  const handleSend = async (textInput?: string) => {
    const messageText = textInput || input;

    // Allow sending if there's text OR an attachment
    if ((!messageText.trim() && !attachment) || isLoading) return;

    // Clear input immediately
    setInput('');
    setAttachment(null);
    if (fileInputRef.current) fileInputRef.current.value = '';

    // Send to store
    await chatActions.sendMessage(messageText, selectedModel);
  };

  // --- Audio Recording & Transcription ---
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        await transcribeAudio(audioBlob);
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error("Error accessing microphone:", err);
      alert("Could not access microphone. Please check permissions.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const transcribeAudio = async (audioBlob: Blob) => {
    // In a real app, we would use setLoading(true) here
    // But since we are just setting input, we don't strictly need to block UI
    try {
      const base64Audio = await blobToBase64(audioBlob);
      // For now, use a simple transcription placeholder
      setInput("Audio message received. Please type your response.");
    } catch (error) {
      console.error("Transcription error:", error);
      alert("Failed to transcribe audio.");
    }
  };

  const playTTS = async (text: string, messageId: string) => {
    if (activeSourceNodeRef.current) {
      activeSourceNodeRef.current.stop();
      activeSourceNodeRef.current = null;
      setIsPlayingId(null);
      if (messageId === isPlayingId) return;
    }

    setIsPlayingId(messageId);

    try {
      console.log("Text-to-speech requested for:", text);
      alert("Text-to-speech feature is currently disabled.");
      setIsPlayingId(null);
    } catch (error) {
      console.error("TTS Error:", error);
      setIsPlayingId(null);
    }
  };

  const copyMessage = async (text: string, messageId: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedMessageId(messageId);
      setTimeout(() => setCopiedMessageId(null), 2000);
    } catch (error) {
      console.error("Copy failed:", error);
    }
  };

  const handleRenameSession = async (sessionId: string) => {
    if (editTitle.trim()) {
      await updateSessionTitle(sessionId, editTitle);
    }
    setEditingSessionId(null);
  };

  // Regenerate an AI response
  const [regeneratingId, setRegeneratingId] = useState<string | null>(null);

  const regenerateMessage = async (messageId: string) => {
    setRegeneratingId(messageId);
    try {
      await chatActions.regenerateLastResponse();
    } finally {
      setRegeneratingId(null);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const menuItems = [
    { icon: 'search', label: 'Search' },
    { icon: 'history', label: 'How is my BP trending?' },
    { icon: 'monitor_heart', label: 'Analyze my workouts' },
    { icon: 'restaurant_menu', label: 'Review my sodium intake' },
    { icon: 'support_agent', label: 'County Assistant' },
  ];

  return (
    <div className="flex flex-col h-screen bg-[#101922] relative overflow-hidden font-sans" role="main" aria-label="Cardio AI Chat">

      {/* --- Sidebar Overlay --- */}
      {isMenuOpen && (
        <>
          <div
            className="fixed inset-0 bg-black/60 z-40 backdrop-blur-sm animate-in fade-in duration-200"
            onClick={() => setIsMenuOpen(false)}
            aria-hidden="true"
          ></div>
          <nav className="fixed top-0 left-0 bottom-0 w-72 bg-[#192633] z-50 shadow-2xl animate-in slide-in-from-left duration-300 flex flex-col" role="navigation" aria-label="Main menu">
            <div className="p-6">
              {/* New Chat Button */}
              <button
                onClick={() => {
                  createSession();
                  setMessages([{
                    id: Date.now().toString(),
                    role: 'assistant',
                    content: 'I am ready to help. You can ask me to log your vitals, add medications, book appointments, or analyze your trends.',
                    timestamp: new Date().toISOString(),
                    type: 'text'
                  }]);
                  setIsMenuOpen(false);
                }}
                className="w-full flex items-center justify-center gap-2 p-3 mb-4 bg-[#D32F2F] hover:bg-red-700 text-white rounded-lg transition-colors font-medium"
              >
                <span className="material-symbols-outlined text-xl">add</span>
                <span>New Chat</span>
              </button>

              <div className="relative mb-4">
                <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">search</span>
                <input
                  type="text"
                  placeholder="Search"
                  className="w-full bg-[#101922] border border-slate-700 rounded-lg py-2 pl-10 pr-4 text-slate-200 text-sm focus:outline-none focus:border-red-500"
                  aria-label="Search conversations"
                />
              </div>

              {/* Conversation History */}
              {sessions.length > 0 && (
                <div className="mb-4">
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 px-1">Recent Chats</h3>
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {sessions.slice(0, 5).map((session: ChatSession) => (
                      <div
                        key={session.id}
                        className="group flex items-center gap-2 p-2 text-slate-300 hover:bg-[#101922] hover:text-white rounded-lg transition-colors cursor-pointer"
                        onClick={() => {
                          if (editingSessionId === session.id) return;
                          loadSession(session.id);
                          setIsMenuOpen(false);
                        }}
                      >
                        <span className="material-symbols-outlined text-sm text-slate-500">chat_bubble</span>

                        {editingSessionId === session.id ? (
                          <input
                            type="text"
                            value={editTitle}
                            onChange={(e) => setEditTitle(e.target.value)}
                            onBlur={() => handleRenameSession(session.id)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleRenameSession(session.id);
                            }}
                            autoFocus
                            className="flex-1 bg-transparent border-b border-blue-500 text-sm focus:outline-none text-white"
                            onClick={(e) => e.stopPropagation()}
                          />
                        ) : (
                          <div className="flex-1 min-w-0">
                            <p className="text-sm truncate">{session.title}</p>
                            <p className="text-xs text-slate-500 truncate">
                              {session.lastMessage || `${session.messageCount} messages`}
                            </p>
                          </div>
                        )}

                        <div className="flex opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditingSessionId(session.id);
                              setEditTitle(session.title);
                            }}
                            className="p-1 text-slate-500 hover:text-blue-400 transition-all"
                            aria-label="Rename conversation"
                          >
                            <span className="material-symbols-outlined text-sm">edit</span>
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteSession(session.id);
                            }}
                            className="p-1 text-slate-500 hover:text-red-400 transition-all"
                            aria-label="Delete conversation"
                          >
                            <span className="material-symbols-outlined text-sm">delete</span>
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Quick Actions */}
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 px-1">Quick Actions</h3>
              <div className="space-y-1">
                {menuItems.slice(1).map((item) => (
                  <button
                    key={item.label}
                    onClick={() => { setIsMenuOpen(false); handleSend(item.label); }}
                    className="w-full flex items-center gap-4 p-3 text-slate-300 hover:bg-[#101922] hover:text-white rounded-lg transition-colors text-left"
                  >
                    <span className="material-symbols-outlined text-xl">{item.icon}</span>
                    <span className="text-sm font-medium">{item.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-auto p-4 border-t border-slate-800">
              <button
                onClick={() => { setIsMenuOpen(false); navigate('/settings'); }}
                className="w-full flex items-center gap-4 p-3 text-slate-300 hover:bg-[#101922] hover:text-white rounded-lg transition-colors text-left"
              >
                <span className="material-symbols-outlined text-xl text-red-400">settings</span>
                <span className="text-sm font-medium text-red-400">Settings</span>
              </button>
            </div>
          </nav>
        </>
      )}

      {/* --- Header --- */}
      <div className="flex items-center justify-between p-4 z-10 bg-[#101922] border-b border-slate-800/50">
        <button onClick={() => setIsMenuOpen(true)} className="p-2 -ml-2 text-slate-300 hover:text-white transition-colors">
          <span className="material-symbols-outlined text-2xl">menu</span>
        </button>
        <div className="flex flex-col items-center">
          <h1 className="font-bold text-lg text-white">Cardio AI Agent</h1>

          {/* Model Selector Dropdown */}
          <div className="relative mt-1">
            <button
              onClick={() => setIsModelDropdownOpen(!isModelDropdownOpen)}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 rounded transition-colors"
            >
              <span className="material-symbols-outlined text-sm">
                {selectedModel === 'ollama' ? 'memory' : 'auto_awesome'}
              </span>
              <span className="font-medium">
                {selectedModel === 'ollama' ? 'Ollama (Local)' : 'Gemini'}
              </span>
              <span className="material-symbols-outlined text-sm">
                {isModelDropdownOpen ? 'expand_less' : 'expand_more'}
              </span>
            </button>

            {/* Dropdown Menu */}
            {isModelDropdownOpen && (
              <div className="absolute top-full mt-1 left-1/2 -translate-x-1/2 bg-[#192633] border border-slate-700 rounded-lg shadow-lg z-50 min-w-48">
                <button
                  onClick={() => {
                    setSelectedModel('gemini');
                    setIsModelDropdownOpen(false);
                  }}
                  className={`w-full flex items-center gap-2 px-4 py-2 text-left text-sm transition-colors ${selectedModel === 'gemini'
                    ? 'bg-slate-700 text-white'
                    : 'text-slate-300 hover:bg-slate-800'
                    }`}
                >
                  <span className="material-symbols-outlined text-base">auto_awesome</span>
                  <div className="flex-1">
                    <div className="font-medium">Gemini</div>
                    <div className="text-xs text-slate-500">Google's advanced AI model</div>
                  </div>
                </button>

                <button
                  onClick={() => {
                    setSelectedModel('ollama');
                    setIsModelDropdownOpen(false);
                  }}
                  className={`w-full flex items-center gap-2 px-4 py-2 text-left text-sm transition-colors border-t border-slate-700 ${selectedModel === 'ollama'
                    ? 'bg-slate-700 text-white'
                    : 'text-slate-300 hover:bg-slate-800'
                    }`}
                >
                  <span className="material-symbols-outlined text-base">memory</span>
                  <div className="flex-1">
                    <div className="font-medium">Ollama (Local)</div>
                    <div className="text-xs text-slate-500">Run locally on your machine</div>
                  </div>
                </button>
              </div>
            )}
          </div>

          {isSearchingMemories ? (
            <span className="text-[10px] text-blue-400 flex items-center gap-1 mt-1">
              <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse"></span>
              Searching memories...
            </span>
          ) : (
            <span className="text-[10px] text-green-500 flex items-center gap-1 mt-1">
              <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></span>
              Memory Active
            </span>
          )}
        </div>
        <button onClick={() => navigate('/profile')} className="w-9 h-9 rounded-full bg-slate-700 overflow-hidden border border-slate-600">
          <img src="https://randomuser.me/api/portraits/women/44.jpg" alt="Profile" className="w-full h-full object-cover" />
        </button>
      </div>

      {/* --- Messages --- */}
      <div
        className="flex-1 overflow-y-auto p-4 space-y-6"
        role="log"
        aria-label="Chat messages"
        aria-live="polite"
      >
        <AnimatePresence initial={false}>
          {messages.map((msg) => {
            // Render Action Requests (e.g. "Processing: logBiometrics")
            if (msg.type === 'action_request') {
              return (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.2 }}
                  className="flex justify-center w-full my-2"
                >
                  <div className="flex items-center gap-2 px-4 py-2 bg-[#192633] rounded-full border border-slate-700 shadow-sm animate-pulse">
                    <span className="material-symbols-outlined text-yellow-500 text-sm">settings</span>
                    <span className="text-xs text-slate-300 italic">{msg.content}</span>
                  </div>
                </motion.div>
              );
            }

            // Render Action Results (Standard)
            if (msg.type === 'action_result') {
              const { name } = msg.actionData;
              let icon = 'check_circle';
              let color = 'text-green-500';

              if (name === 'logBiometrics') { icon = 'monitor_heart'; color = 'text-red-500'; }
              if (name === 'addMedication') { icon = 'pill'; color = 'text-blue-500'; }
              if (name === 'scheduleAppointment') { icon = 'calendar_today'; color = 'text-purple-500'; }

              return (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ duration: 0.2 }}
                  className="flex justify-center w-full my-2"
                >
                  <div className="flex flex-col items-center p-3 bg-[#1F2937] rounded-xl border border-slate-700 shadow-sm w-3/4 max-w-sm">
                    <div className={`w-8 h-8 rounded-full bg-opacity-20 ${color.replace('text', 'bg')} flex items-center justify-center mb-2`}>
                      <span className={`material-symbols-outlined ${color}`}>{icon}</span>
                    </div>
                    <p className="text-xs font-bold text-white mb-1">{msg.content.split(':')[0]}</p>
                    <p className="text-[10px] text-slate-400 text-center">{msg.content.split(':')[1]}</p>
                  </div>
                </motion.div>
              );
            }

            // Render Widgets (Generative UI)
            if (msg.type === 'widget' && msg.widgetData) {
              const { type, title, data } = msg.widgetData;

              return (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  className="flex justify-start w-full my-2"
                >
                  <div className="w-full max-w-sm bg-[#192633] rounded-2xl border border-slate-700 overflow-hidden shadow-md">
                    <div className="bg-[#1F2937] p-3 border-b border-slate-700 flex justify-between items-center">
                      <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">{title}</span>
                      <span className="material-symbols-outlined text-slate-400 text-sm">
                        {type === 'recipeCard' ? 'restaurant_menu' : 'show_chart'}
                      </span>
                    </div>

                    <div className="p-4">
                      {type.includes('Chart') && (
                        <div className="h-40 w-full min-w-0 min-h-0 relative">
                          <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0} debounce={50}>
                            <AreaChart data={data}>
                              <defs>
                                <linearGradient id={`grad${msg.id}`} x1="0" y1="0" x2="0" y2="1">
                                  <stop offset="5%" stopColor="#137fec" stopOpacity={0.3} />
                                  <stop offset="95%" stopColor="#137fec" stopOpacity={0} />
                                </linearGradient>
                              </defs>
                              <Tooltip
                                contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px', fontSize: '10px' }}
                                itemStyle={{ color: '#fff' }}
                              />
                              <Area
                                type="monotone"
                                dataKey="value"
                                stroke="#137fec"
                                strokeWidth={2}
                                fillOpacity={1}
                                fill={`url(#grad${msg.id})`}
                              />
                              <XAxis dataKey="day" hide />
                              <YAxis hide domain={['auto', 'auto']} />
                            </AreaChart>
                          </ResponsiveContainer>
                          <div className="flex justify-between text-[10px] text-slate-500 mt-1 px-2">
                            {data.length > 0 && <span>{data[0].day}</span>}
                            {data.length > 0 && <span>{data[data.length - 1].day}</span>}
                          </div>
                        </div>
                      )}

                      {type === 'recipeCard' && (
                        <div className="flex flex-col gap-3">
                          {data.image && (
                            <div className="w-full h-32 rounded-lg bg-cover bg-center" style={{ backgroundImage: `url('${data.image}')` }}></div>
                          )}
                          <div>
                            <h4 className="font-bold text-white text-sm">{data.title}</h4>
                            <div className="flex gap-2 text-xs text-slate-400 mt-1">
                              <span>{data.calories} kcal</span> • <span>{data.time || '15 min'}</span>
                            </div>
                          </div>
                          <button
                            onClick={() => navigate(`/nutrition`)}
                            className="w-full py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-xs font-bold transition-colors"
                          >
                            View Recipe
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              );
            }

            // Standard Text Message
            return (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, x: msg.role === 'user' ? 20 : -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className={`flex w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div className={`flex flex-col max-w-[85%] ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>

                  <div className="flex items-center gap-2 mb-1 px-1">
                    <span className="text-xs text-slate-400">{msg.role === 'user' ? 'You' : 'Cardio AI'}</span>
                    {msg.ragContext && msg.role === 'assistant' && (
                      <span className="text-[10px] text-blue-400 bg-blue-900/30 px-1 rounded flex items-center gap-0.5" title="Used your past data">
                        <span className="material-symbols-outlined text-[10px]">history</span> History
                      </span>
                    )}
                  </div>

                  <div className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                    {/* Avatar */}
                    <div className="shrink-0 mt-1">
                      {msg.role === 'assistant' ? (
                        <div className="w-8 h-8 rounded-full overflow-hidden border border-slate-600">
                          <img src="https://img.freepik.com/free-photo/portrait-young-doctor-hospital_23-2148365287.jpg?t=st=1730000000~exp=1730003600~hmac=fakehash" alt="AI" className="w-full h-full object-cover" />
                        </div>
                      ) : (
                        <div className="w-8 h-8 rounded-full bg-slate-600 flex items-center justify-center">
                          <span className="material-symbols-outlined text-sm text-white">person</span>
                        </div>
                      )}
                    </div>

                    {/* Bubble */}
                    <div className={`p-4 rounded-2xl text-sm leading-relaxed shadow-sm relative group ${msg.role === 'assistant'
                      ? 'bg-[#192633] text-slate-100 rounded-tl-none border border-slate-800'
                      : 'bg-[#4B5563] text-white rounded-tr-none'
                      }`}>
                      {msg.image && (
                        <div className="mb-2 rounded-lg overflow-hidden border border-white/20">
                          <img src={msg.image} alt="Uploaded content" className="max-w-full h-auto max-h-48 object-cover" />
                        </div>
                      )}

                      {/* Use ChatMessageMarkdown for model responses, plain text for user */}
                      {msg.role === 'assistant' ? (
                        <ChatMessageMarkdown
                          content={msg.content}
                          sources={msg.sources}
                          showHealthAlerts={true}
                        />
                      ) : (
                        <span>{msg.content}</span>
                      )}

                      {/* Message Actions (TTS, Copy & Regenerate) */}
                      {msg.role === 'assistant' && (
                        <div className="absolute -right-10 bottom-0 flex flex-col gap-1">
                          <button
                            onClick={() => regenerateMessage(msg.id)}
                            disabled={regeneratingId === msg.id || isLoading}
                            className={`p-1.5 rounded-full hover:bg-slate-800 transition-colors ${regeneratingId === msg.id ? 'text-blue-400 animate-spin' : 'text-slate-500'
                              } disabled:opacity-50`}
                            title="Regenerate response"
                            aria-label="Regenerate AI response"
                          >
                            <span className="material-symbols-outlined text-lg">
                              refresh
                            </span>
                          </button>
                          <button
                            onClick={() => copyMessage(msg.content, msg.id)}
                            className={`p-1.5 rounded-full hover:bg-slate-800 transition-colors ${copiedMessageId === msg.id ? 'text-green-400' : 'text-slate-500'
                              }`}
                            title={copiedMessageId === msg.id ? 'Copied!' : 'Copy message'}
                          >
                            <span className="material-symbols-outlined text-lg">
                              {copiedMessageId === msg.id ? 'check' : 'content_copy'}
                            </span>
                          </button>
                          <button
                            onClick={() => playTTS(msg.content, msg.id)}
                            className={`p-1.5 rounded-full hover:bg-slate-800 transition-colors ${isPlayingId === msg.id ? 'text-red-400' : 'text-slate-500'
                              }`}
                            title={isPlayingId === msg.id ? 'Stop' : 'Read aloud'}
                          >
                            <span className="material-symbols-outlined text-lg">
                              {isPlayingId === msg.id ? 'stop_circle' : 'volume_up'}
                            </span>
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Grounding Data */}
                  {msg.groundingMetadata?.groundingChunks && (
                    <div className="mt-2 ml-11 flex flex-wrap gap-2">
                      {msg.groundingMetadata.groundingChunks.map((chunk: any, i: number) => (
                        <a
                          key={i}
                          href={chunk.web?.uri || chunk.maps?.source?.uri}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center gap-1 bg-[#192633] border border-slate-700 px-2 py-1 rounded text-xs text-blue-400 hover:text-blue-300"
                        >
                          <span className="material-symbols-outlined text-[10px]">link</span>
                          {chunk.web?.title || "Source"}
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>

        {isLoading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex justify-start w-full"
          >
            <div className="flex flex-col items-start gap-1 max-w-[85%]">
              <span className="text-xs text-slate-400 px-1">Cardio AI Agent</span>
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full overflow-hidden border border-slate-600">
                  <img src="https://img.freepik.com/free-photo/portrait-young-doctor-hospital_23-2148365287.jpg?t=st=1730000000~exp=1730003600~hmac=fakehash" alt="AI" className="w-full h-full object-cover" />
                </div>
                <div className="p-4 bg-[#192633] border border-slate-800 rounded-2xl rounded-tl-none flex items-center gap-1.5">
                  <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce"></span>
                  <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce [animation-delay:0.2s]"></span>
                  <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce [animation-delay:0.4s]"></span>
                </div>
              </div>
            </div>
          </motion.div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* --- Input Area --- */}
      <div className="p-4 bg-[#101922] relative">

        {/* Attachment Preview */}
        {attachment && (
          <div className="absolute bottom-full left-4 mb-2 bg-[#192633] border border-slate-700 p-2 rounded-xl flex items-center gap-3 animate-in slide-in-from-bottom-2 fade-in">
            <div className="w-12 h-12 rounded-lg bg-cover bg-center border border-slate-600" style={{ backgroundImage: `url('${attachment}')` }}></div>
            <button
              onClick={removeAttachment}
              className="w-6 h-6 rounded-full bg-slate-800 text-slate-400 hover:bg-red-900/50 hover:text-red-400 flex items-center justify-center transition-colors"
            >
              <span className="material-symbols-outlined text-sm">close</span>
            </button>
          </div>
        )}

        {/* Quick Actions */}
        {!isLoading && messages.length < 3 && !attachment && (
          <div className="flex gap-3 mb-4 overflow-x-auto no-scrollbar">
            <button
              onClick={() => handleSend("Log my blood pressure as 120 over 80 and heart rate 72")}
              className="flex-shrink-0 px-4 py-2 bg-[#3C1F1F] text-[#FCA5A5] text-xs font-semibold rounded-full border border-red-900/50 hover:bg-[#4a2626] transition-colors"
            >
              + Log BP 120/80
            </button>
            <button
              onClick={() => handleSend("Show my heart rate trend for this week")}
              className="flex-shrink-0 px-4 py-2 bg-[#1E293B] text-[#93C5FD] text-xs font-semibold rounded-full border border-blue-900/50 hover:bg-[#2b3a55] transition-colors"
            >
              + Show HR Trend
            </button>
            <button
              onClick={() => handleSend("Book Dr. Smith for next Monday")}
              className="flex-shrink-0 px-4 py-2 bg-[#2E1065] text-[#D8B4FE] text-xs font-semibold rounded-full border border-purple-900/50 hover:bg-[#431c8a] transition-colors"
            >
              + Book Appt
            </button>
          </div>
        )}

        <div className="flex items-center gap-3">
          {/* Attachment Button */}
          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            accept="image/*"
            onChange={handleFileSelect}
            aria-label="Upload an image"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className={`flex items-center justify-center w-12 h-12 rounded-full shadow-lg transition-colors shrink-0 ${attachment ? 'bg-green-600 text-white' : 'bg-[#D32F2F] text-white hover:bg-red-700'}`}
            aria-label={attachment ? 'Image attached - click to change' : 'Attach an image'}
            title={attachment ? 'Change attachment' : 'Attach image'}
          >
            <span className="material-symbols-outlined rotate-45">attach_file</span>
          </button>

          {/* Text Input */}
          <div className="flex-1 relative h-12" role="search">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder={attachment ? "Ask about this image..." : "Type or say 'Show me a healthy recipe'..."}
              className="w-full h-full bg-[#1F2937] border border-slate-700 rounded-full pl-5 pr-12 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-slate-500 transition-colors"
              aria-label="Type your message to Cardio AI"
              autoComplete="off"
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() && !attachment}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-slate-400 hover:text-white transition-colors disabled:opacity-30"
              aria-label="Send message"
              title="Send"
            >
              <span className="material-symbols-outlined">send</span>
            </button>
          </div>

          {/* Mic Button */}
          <button
            onMouseDown={startRecording}
            onMouseUp={stopRecording}
            onTouchStart={startRecording}
            onTouchEnd={stopRecording}
            className={`flex items-center justify-center w-12 h-12 rounded-full bg-[#D32F2F] text-white shadow-lg hover:bg-red-700 transition-all shrink-0 ${isRecording ? 'animate-pulse scale-110' : ''}`}
            aria-label={isRecording ? 'Recording... Release to stop' : 'Hold to record voice message'}
            title={isRecording ? 'Release to send' : 'Voice input'}
          >
            <span className="material-symbols-outlined">{isRecording ? 'mic_off' : 'mic'}</span>
          </button>
        </div>

        <p className="text-center text-[10px] text-slate-500 mt-3">
          Agent can perform actions, display charts, and analyze images.
        </p>
      </div>

    </div>
  );
};

export default ChatScreen;
