import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { apiClient } from '../services/apiClient';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Message } from '../types';
import { memoryService } from '../services/memoryService';
import { ChatMessageMarkdown } from '../components/MarkdownRenderer';
import { useChatStore, ChatSession, chatActions, groupSessionsByDate, ChatSettings, SearchMode } from '../store/useChatStore';
import { useAuth } from '../hooks/useAuth';
import { useOfflineStatus } from '../hooks/useOfflineStatus';
import { useProvider } from '../contexts/ProviderContext';
import { useToast } from '../components/Toast';

// Audio Helpers
function base64ToUint8Array(base64: string) {
  const bin = atob(base64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

async function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      if (typeof reader.result === 'string') {
        resolve(reader.result.split(',')[1]);
      } else {
        reject(new Error('Failed to convert blob to base64'));
      }
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

type SidebarPanel = 'history' | 'settings' | null;

function useAutoResize(value: string) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 160) + 'px';
    }
  }, [value]);
  return ref;
}

function formatTime(ts: string) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}

const searchModeLabel: Record<SearchMode, { icon: string; label: string; color: string }> = {
  default: { icon: '', label: '', color: '' },
  web_search: { icon: 'travel_explore', label: 'Web Search', color: 'text-blue-500 bg-blue-500/10 border-blue-200/40 dark:border-blue-500/20' },
  deep_search: { icon: 'psychology', label: 'Deep Analysis', color: 'text-purple-500 bg-purple-500/10 border-purple-200/40 dark:border-purple-500/20' },
  memory: { icon: 'history', label: 'Memory', color: 'text-amber-500 bg-amber-500/10 border-amber-200/40 dark:border-amber-500/20' },
};

const ChatScreen: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useToast();
  const { isOnline } = useOfflineStatus();
  const location = useLocation();

  const [input, setInput] = useState('');
  const [attachment, setAttachment] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useAutoResize(input);

  const [sidebarPanel, setSidebarPanel] = useState<SidebarPanel>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [contextMenuSession, setContextMenuSession] = useState<string | null>(null);

  const [isRecording, setIsRecording] = useState(false);
  const [isPlayingId, setIsPlayingId] = useState<string | null>(null);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const activeSourceNodeRef = useRef<AudioBufferSourceNode | null>(null);

  const [regeneratingId, setRegeneratingId] = useState<string | null>(null);

  // Search mode: what tools/context to use for the next message
  const [searchMode, setSearchMode] = useState<SearchMode>('default');
  const [activeSearchMode, setActiveSearchMode] = useState<SearchMode>('default');

  // Editing a user message
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);

  const {
    messages, sessions, currentSessionId,
    isLoading, isStreaming, isSearchingMemories,
    selectedModel, settings,
    createSession, loadSession, deleteSession,
    loadSessions, updateSessionTitle, setSelectedModel,
    setMessages, pinSession, archiveSession, deleteAllSessions,
    updateSettings,
  } = useChatStore();

  useEffect(() => {
    if (!user) return;
    loadSessions(user.id);
    if (!currentSessionId && sessions.length === 0) createSession();
  }, [user]);

  useEffect(() => {
    memoryService.syncContext();
    if (location.state?.autoSend) {
      handleSend(location.state.autoSend);
      window.history.replaceState({}, document.title);
    }
    return () => { audioContextRef.current?.close(); };
  }, [location.state]);

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    });
  }, []);

  useEffect(() => { scrollToBottom(); }, [messages, isLoading, attachment, scrollToBottom]);

  const activeSessions = useMemo(() => sessions.filter(s => !s.isArchived), [sessions]);
  const pinnedSessions = useMemo(() => activeSessions.filter(s => s.isPinned), [activeSessions]);
  const unpinnedSessions = useMemo(() => activeSessions.filter(s => !s.isPinned), [activeSessions]);
  const groupedSessions = useMemo(() => groupSessionsByDate(unpinnedSessions), [unpinnedSessions]);
  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return null;
    const q = searchQuery.toLowerCase();
    return activeSessions.filter(s =>
      s.title.toLowerCase().includes(q) ||
      s.lastMessage?.toLowerCase().includes(q) ||
      s.messages?.some(m => m.content.toLowerCase().includes(q))
    );
  }, [searchQuery, activeSessions]);
  const archivedSessions = useMemo(() => sessions.filter(s => s.isArchived), [sessions]);
  const [showArchived, setShowArchived] = useState(false);
  const dateGroupOrder = ['Today', 'Yesterday', 'Previous 7 Days', 'Previous 30 Days', 'Older'];

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => setAttachment(reader.result as string);
      reader.readAsDataURL(file);
    }
  };

  const removeAttachment = () => {
    setAttachment(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleSend = async (textInput?: string) => {
    const text = textInput || input;
    if ((!text.trim() && !attachment) || isLoading) return;
    if (!isOnline) { showToast('You are currently offline.', 'warning'); return; }
    const currentSearchMode = searchMode;
    setInput('');
    setAttachment(null);
    setActiveSearchMode(currentSearchMode); // Track mode during loading
    setSearchMode('default'); // Reset after send (Gemini-style)
    if (fileInputRef.current) fileInputRef.current.value = '';
    await chatActions.sendMessage(text, selectedModel, currentSearchMode);
    setActiveSearchMode('default');
  };

  const startRecording = async () => {
    if (!isOnline) { showToast('Voice recording requires internet.', 'warning'); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];
      recorder.ondataavailable = e => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
      recorder.onstop = async () => {
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        await transcribeAudio(blob);
        stream.getTracks().forEach(t => t.stop());
      };
      recorder.start();
      setIsRecording(true);
    } catch { showToast('Could not access microphone.', 'error'); }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) { mediaRecorderRef.current.stop(); setIsRecording(false); }
  };

  const transcribeAudio = async (blob: Blob) => {
    try {
      const b64 = await blobToBase64(blob);
      const res = await apiClient.transcribeAudio(b64);
      if (res.success) setInput(res.text);
      else showToast('Transcription failed: ' + res.error, 'error');
    } catch { showToast('Failed to transcribe audio.', 'error'); }
  };

  const playTTS = async (text: string, messageId: string) => {
    if (activeSourceNodeRef.current && isPlayingId === messageId) {
      activeSourceNodeRef.current.stop();
      activeSourceNodeRef.current = null;
      setIsPlayingId(null);
      return;
    }
    if (activeSourceNodeRef.current) { activeSourceNodeRef.current.stop(); activeSourceNodeRef.current = null; }
    setIsPlayingId(messageId);
    try {
      const response = await apiClient.synthesizeSpeech(text);
      if (response.success && response.audio) {
        const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
        audioContextRef.current = ctx;
        const data = base64ToUint8Array(response.audio);
        const buf = await ctx.decodeAudioData(data.buffer);
        const src = ctx.createBufferSource();
        src.buffer = buf;
        src.connect(ctx.destination);
        src.onended = () => { setIsPlayingId(null); activeSourceNodeRef.current = null; };
        src.start(0);
        activeSourceNodeRef.current = src;
      } else {
        const u = new SpeechSynthesisUtterance(text);
        u.onend = () => setIsPlayingId(null);
        window.speechSynthesis.speak(u);
      }
    } catch {
      setIsPlayingId(null);
      if ('speechSynthesis' in window) {
        const u = new SpeechSynthesisUtterance(text);
        u.onend = () => setIsPlayingId(null);
        window.speechSynthesis.speak(u);
      }
    }
  };

  const copyMessage = async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedMessageId(id);
      setTimeout(() => setCopiedMessageId(null), 2000);
    } catch {}
  };

  const handleRenameSession = async (sessionId: string) => {
    if (editTitle.trim()) await updateSessionTitle(sessionId, editTitle);
    setEditingSessionId(null);
  };

  const regenerateMessage = async (messageId: string) => {
    setRegeneratingId(messageId);
    try { await chatActions.regenerateLastResponse(); } finally { setRegeneratingId(null); }
  };

  // Edit a sent user message: load it into input and remove it + the assistant response that followed
  const editUserMessage = (messageId: string) => {
    const msgIndex = messages.findIndex(m => m.id === messageId);
    if (msgIndex === -1) return;
    const msg = messages[msgIndex];
    if (msg.role !== 'user') return;

    // Load content into input
    setInput(msg.content);
    setEditingMessageId(messageId);

    // Remove this user message and any assistant messages that follow it
    const store = useChatStore.getState();
    const idsToRemove: string[] = [messageId];
    for (let i = msgIndex + 1; i < messages.length; i++) {
      idsToRemove.push(messages[i].id);
    }
    idsToRemove.forEach(id => store.removeMessage(id));

    // Focus the textarea
    setTimeout(() => textareaRef.current?.focus(), 100);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  useEffect(() => {
    if (contextMenuSession) {
      const close = () => setContextMenuSession(null);
      const timer = setTimeout(() => document.addEventListener('click', close), 0);
      return () => { clearTimeout(timer); document.removeEventListener('click', close); };
    }
  }, [contextMenuSession]);

  // SettingsPanel
  const SettingsPanel = () => {
    const [localSettings, setLocalSettings] = useState<ChatSettings>({ ...settings });
    const handleSave = () => { updateSettings(localSettings); showToast('Settings saved', 'success'); };
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-700/50 flex-shrink-0">
          <div className="flex items-center gap-2">
            <button onClick={() => setSidebarPanel('history')} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500">
              <span className="material-symbols-outlined text-lg">arrow_back</span>
            </button>
            <h2 className="font-semibold text-slate-900 dark:text-white text-[15px]">Settings</h2>
          </div>
          <button onClick={() => setSidebarPanel(null)} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400">
            <span className="material-symbols-outlined text-lg">close</span>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          <div>
            <label className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2.5 block">AI Model</label>
            <div className="grid grid-cols-2 gap-2">
              {(['gemini', 'ollama'] as const).map(m => (
                <button key={m} onClick={() => setSelectedModel(m)}
                  className={`py-3 px-3 rounded-xl text-sm font-medium transition-all duration-200 flex items-center justify-center gap-2 ${
                    selectedModel === m
                      ? 'bg-gradient-to-r from-red-500 to-red-600 text-white shadow-lg shadow-red-500/25'
                      : 'bg-slate-100 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
                  }`}>
                  <span className="material-symbols-outlined text-base">{m === 'ollama' ? 'memory' : 'cloud'}</span>
                  {m === 'ollama' ? 'Ollama' : 'Gemini'}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2.5 block">
              Temperature <span className="text-slate-900 dark:text-white font-bold ml-1">{localSettings.temperature.toFixed(1)}</span>
            </label>
            <input type="range" min="0" max="1" step="0.1" value={localSettings.temperature}
              onChange={e => setLocalSettings({ ...localSettings, temperature: parseFloat(e.target.value) })}
              className="w-full accent-red-500 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full cursor-pointer" />
            <div className="flex justify-between text-[10px] text-slate-400 mt-1.5"><span>Precise</span><span>Creative</span></div>
          </div>
          <div>
            <label className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2.5 block">System Prompt</label>
            <textarea rows={4} value={localSettings.systemPrompt}
              onChange={e => setLocalSettings({ ...localSettings, systemPrompt: e.target.value })}
              className="w-full bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl px-3.5 py-3 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-500/40 resize-none transition-all" />
          </div>
          <div className="space-y-2.5">
            {[
              { key: 'streamResponses' as const, label: 'Stream Responses', desc: 'See tokens appear in real-time', icon: 'stream' },
              { key: 'autoGenerateTitle' as const, label: 'Auto-name Chats', desc: 'Generate title from first message', icon: 'title' },
            ].map(toggle => (
              <div key={toggle.key} className="flex items-center justify-between bg-slate-50 dark:bg-slate-800/60 rounded-xl px-4 py-3.5 border border-slate-100 dark:border-slate-700/30">
                <div className="flex items-center gap-3">
                  <span className="material-symbols-outlined text-base text-slate-400">{toggle.icon}</span>
                  <div>
                    <p className="text-sm text-slate-800 dark:text-white font-medium">{toggle.label}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">{toggle.desc}</p>
                  </div>
                </div>
                <button onClick={() => setLocalSettings({ ...localSettings, [toggle.key]: !localSettings[toggle.key] })}
                  className={`w-11 h-6 rounded-full transition-colors duration-200 relative flex-shrink-0 ${localSettings[toggle.key] ? 'bg-red-500' : 'bg-slate-300 dark:bg-slate-600'}`}>
                  <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-transform duration-200 ${localSettings[toggle.key] ? 'left-[22px]' : 'left-0.5'}`} />
                </button>
              </div>
            ))}
          </div>
          <div className="pt-2">
            <label className="text-[11px] font-semibold text-red-400 uppercase tracking-wider mb-2.5 block">Danger Zone</label>
            <button onClick={() => { deleteAllSessions(); showToast('All chats deleted', 'success'); setSidebarPanel(null); }}
              className="w-full py-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-sm font-medium hover:bg-red-500/20 transition-all flex items-center justify-center gap-2">
              <span className="material-symbols-outlined text-base">delete_forever</span>
              Delete All Conversations
            </button>
          </div>
        </div>
        <div className="px-5 py-4 border-t border-slate-200 dark:border-slate-700/50 flex-shrink-0">
          <button onClick={handleSave}
            className="w-full py-3 bg-gradient-to-r from-red-500 to-red-600 text-white rounded-xl text-sm font-semibold hover:from-red-600 hover:to-red-700 transition-all shadow-lg shadow-red-500/25 active:scale-[0.98]">
            Save Settings
          </button>
        </div>
      </div>
    );
  };

  // SessionItem
  const SessionItem = ({ session }: { session: ChatSession }) => {
    const isActive = session.id === currentSessionId;
    const isEditing = editingSessionId === session.id;
    const showMenu = contextMenuSession === session.id;
    return (
      <div
        className={`group relative flex items-center gap-2.5 px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-150 text-sm ${
          isActive
            ? 'bg-red-500/10 dark:bg-red-500/15 text-slate-900 dark:text-white ring-1 ring-red-500/20'
            : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60'
        }`}
        onClick={() => { if (!isEditing) { loadSession(session.id); setSidebarPanel(null); } }}
      >
        <span className={`material-symbols-outlined text-base flex-shrink-0 ${isActive ? 'text-red-500' : 'text-slate-400'}`}>
          {session.isPinned ? 'push_pin' : 'chat_bubble_outline'}
        </span>
        {isEditing ? (
          <input type="text" value={editTitle}
            onChange={e => setEditTitle(e.target.value)}
            onBlur={() => handleRenameSession(session.id)}
            onKeyDown={e => { if (e.key === 'Enter') handleRenameSession(session.id); if (e.key === 'Escape') setEditingSessionId(null); }}
            autoFocus
            className="flex-1 bg-transparent border-b-2 border-red-500 text-sm focus:outline-none text-slate-900 dark:text-white min-w-0 py-0.5"
            onClick={e => e.stopPropagation()} />
        ) : (
          <div className="flex-1 min-w-0">
            <p className="text-[13px] truncate font-medium leading-tight">{session.title}</p>
            <p className="text-[11px] text-slate-400 dark:text-slate-500 truncate mt-0.5">{session.lastMessage || `${session.messageCount} messages`}</p>
          </div>
        )}
        {!isEditing && (
          <button onClick={e => { e.stopPropagation(); setContextMenuSession(showMenu ? null : session.id); }}
            className="sm:opacity-0 sm:group-hover:opacity-100 p-1 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-400 transition-all flex-shrink-0">
            <span className="material-symbols-outlined text-base">more_horiz</span>
          </button>
        )}
        {showMenu && (
          <div className="absolute right-2 top-full mt-1 bg-white dark:bg-[#1a2737] border border-slate-200 dark:border-slate-700/60 rounded-xl shadow-xl z-[60] py-1.5 min-w-[160px] animate-scaleIn"
            onClick={e => e.stopPropagation()}>
            {[
              { icon: 'edit', label: 'Rename', action: () => { setEditingSessionId(session.id); setEditTitle(session.title); setContextMenuSession(null); } },
              { icon: session.isPinned ? 'push_pin' : 'push_pin', label: session.isPinned ? 'Unpin' : 'Pin', action: () => { pinSession(session.id); setContextMenuSession(null); } },
              { icon: 'archive', label: session.isArchived ? 'Unarchive' : 'Archive', action: () => { archiveSession(session.id); setContextMenuSession(null); } },
              { icon: 'delete', label: 'Delete', action: () => { deleteSession(session.id); setContextMenuSession(null); }, danger: true },
            ].map(item => (
              <button key={item.label} onClick={item.action}
                className={`w-full flex items-center gap-2.5 px-3.5 py-2.5 text-[12px] text-left transition-colors ${
                  (item as any).danger ? 'text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20' : 'text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/70'
                }`}>
                <span className="material-symbols-outlined text-sm">{item.icon}</span>
                {item.label}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full bg-slate-50 dark:bg-[#0f1923] relative overflow-hidden">
      {/* SIDEBAR */}
      <AnimatePresence>
        {sidebarPanel !== null && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="fixed inset-0 bg-black/50 z-40 backdrop-blur-[2px]"
              onClick={() => setSidebarPanel(null)} />
            <motion.nav
              initial={{ x: -300 }} animate={{ x: 0 }} exit={{ x: -300 }}
              transition={{ type: 'spring', damping: 30, stiffness: 400 }}
              className="fixed top-0 left-0 h-screen w-[300px] max-w-[85vw] bg-white dark:bg-[#151f2b] z-50 shadow-2xl flex flex-col overflow-hidden border-r border-slate-200/60 dark:border-slate-700/30">
              {sidebarPanel === 'settings' ? <SettingsPanel /> : (
                <>
                  <div className="px-4 pt-5 pb-3 flex-shrink-0">
                    <div className="flex items-center justify-between mb-4">
                      <h2 className="font-semibold text-slate-900 dark:text-white text-[15px]">Chats</h2>
                      <button onClick={() => setSidebarPanel(null)} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400">
                        <span className="material-symbols-outlined text-lg">close</span>
                      </button>
                    </div>
                    <button onClick={() => { createSession(); setSidebarPanel(null); }}
                      className="w-full flex items-center justify-center gap-2 py-2.5 mb-3 bg-gradient-to-r from-red-500 to-red-600 text-white rounded-xl font-medium text-sm shadow-lg shadow-red-500/20 active:scale-[0.98] transition-transform">
                      <span className="material-symbols-outlined text-lg">add</span>
                      New Chat
                    </button>
                    <div className="relative">
                      <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-base">search</span>
                      <input type="text" placeholder="Search chats..."
                        value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                        className="w-full bg-slate-100 dark:bg-[#0f1923] border border-slate-200 dark:border-slate-700/50 rounded-xl py-2.5 pl-10 pr-4 text-slate-700 dark:text-slate-200 text-xs focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-500/30 transition-all" />
                      {searchQuery && (
                        <button onClick={() => setSearchQuery('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                          <span className="material-symbols-outlined text-sm">close</span>
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-0.5 chat-messages">
                    {searchResults ? (
                      searchResults.length === 0 ? (
                        <div className="text-center py-10">
                          <span className="material-symbols-outlined text-3xl text-slate-300 dark:text-slate-600 mb-2 block">search_off</span>
                          <p className="text-xs text-slate-400">No results for "{searchQuery}"</p>
                        </div>
                      ) : (
                        <>
                          <p className="text-[10px] text-slate-400 uppercase tracking-wider px-2 py-2 font-semibold">
                            {searchResults.length} result{searchResults.length !== 1 ? 's' : ''}
                          </p>
                          {searchResults.map(s => <SessionItem key={s.id} session={s} />)}
                        </>
                      )
                    ) : (
                      <>
                        {pinnedSessions.length > 0 && (
                          <div className="mb-1">
                            <p className="text-[10px] text-slate-400 uppercase tracking-wider px-2 py-2 font-semibold flex items-center gap-1">
                              <span className="material-symbols-outlined text-[10px]">push_pin</span> Pinned
                            </p>
                            {pinnedSessions.map(s => <SessionItem key={s.id} session={s} />)}
                          </div>
                        )}
                        {dateGroupOrder.map(group =>
                          groupedSessions[group] ? (
                            <div key={group} className="mb-1">
                              <p className="text-[10px] text-slate-400 uppercase tracking-wider px-2 py-2 font-semibold">{group}</p>
                              {groupedSessions[group].map(s => <SessionItem key={s.id} session={s} />)}
                            </div>
                          ) : null
                        )}
                        {archivedSessions.length > 0 && (
                          <div className="mt-3">
                            <button onClick={() => setShowArchived(!showArchived)}
                              className="flex items-center gap-1.5 text-[10px] text-slate-400 uppercase tracking-wider px-2 py-2 font-semibold w-full hover:text-slate-300 transition-colors">
                              <span className="material-symbols-outlined text-xs transition-transform" style={{ transform: showArchived ? 'rotate(180deg)' : '' }}>expand_more</span>
                              Archived ({archivedSessions.length})
                            </button>
                            {showArchived && archivedSessions.map(s => <SessionItem key={s.id} session={s} />)}
                          </div>
                        )}
                        {activeSessions.length === 0 && (
                          <div className="text-center py-16">
                            <span className="material-symbols-outlined text-4xl text-slate-200 dark:text-slate-700 mb-3 block">forum</span>
                            <p className="text-sm text-slate-400 font-medium">No conversations yet</p>
                            <p className="text-[11px] text-slate-400/60 mt-1">Start a new chat to begin</p>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                  <div className="px-3 py-3 border-t border-slate-100 dark:border-slate-700/30 flex-shrink-0 space-y-0.5">
                    <button onClick={() => setSidebarPanel('settings')}
                      className="w-full flex items-center gap-3 px-3 py-2.5 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60 rounded-xl transition-colors text-sm">
                      <span className="material-symbols-outlined text-base text-slate-400">tune</span>
                      <span className="font-medium">Chat Settings</span>
                    </button>
                  </div>
                </>
              )}
            </motion.nav>
          </>
        )}
      </AnimatePresence>

      {/* HEADER */}
      <header className="flex items-center justify-between px-2 py-2 z-10 bg-white/80 dark:bg-[#151f2b]/80 backdrop-blur-xl border-b border-slate-200/60 dark:border-slate-700/30 flex-shrink-0">
        <div className="flex items-center gap-0.5">
          <button onClick={() => navigate(-1)} className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800/60 text-slate-500 dark:text-slate-400 active:scale-95 transition-all">
            <span className="material-symbols-outlined text-[22px]">arrow_back</span>
          </button>
          <button onClick={() => setSidebarPanel('history')} className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800/60 text-slate-500 dark:text-slate-400 active:scale-95 transition-all">
            <span className="material-symbols-outlined text-[22px]">menu</span>
          </button>
        </div>
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-red-500 to-red-700 flex items-center justify-center shadow-md shadow-red-900/20">
            <span className="material-symbols-outlined text-white text-base">cardiology</span>
          </div>
          <div className="flex flex-col">
            <h1 className="font-bold text-[15px] text-slate-900 dark:text-white leading-tight">Cardio AI</h1>
            <div className="flex items-center gap-1.5">
              {isOnline ? (
                <span className="flex items-center gap-1 text-[10px] text-emerald-500 font-medium">
                  <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-gentle-pulse" />
                  Online
                </span>
              ) : (
                <span className="flex items-center gap-1 text-[10px] text-amber-500 font-medium">
                  <span className="w-1.5 h-1.5 bg-amber-500 rounded-full" />
                  Offline
                </span>
              )}
              <span className="text-slate-300 dark:text-slate-600 text-[8px]">\u2022</span>
              <span className="text-[10px] text-slate-400 font-medium capitalize">{selectedModel}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-0.5">
          <button onClick={() => createSession()} className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800/60 text-slate-500 dark:text-slate-400 active:scale-95 transition-all" title="New chat">
            <span className="material-symbols-outlined text-[22px]">edit_square</span>
          </button>
        </div>
      </header>

      {/* MESSAGES AREA */}
      <div className="flex-1 overflow-y-auto px-4 chat-messages" style={{ minHeight: 0 }} role="log" aria-label="Chat messages" aria-live="polite">
        <div className="flex flex-col justify-end" style={{ minHeight: '100%' }}>
        {messages.length === 0 && !isLoading && (
          <div className="flex flex-col items-center justify-center py-8 animate-fadeIn" style={{ minHeight: '100%' }}>
            <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-red-500 to-red-700 flex items-center justify-center shadow-xl shadow-red-500/20 mb-6 animate-breathe">
              <span className="material-symbols-outlined text-white text-4xl">cardiology</span>
            </div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2 text-center">{getGreeting()}{user?.name?.trim() ? `, ${user.name.trim().split(' ')[0]}` : ''}</h2>
            <p className="text-sm text-slate-400 dark:text-slate-500 text-center max-w-[280px] mb-8 leading-relaxed">
              Ask me about heart health, log your vitals, or get personalized guidance.
            </p>
            <div className="grid grid-cols-2 gap-3 w-full max-w-sm px-2">
              {[
                { icon: 'monitor_heart', label: 'Log Blood Pressure', prompt: 'Log my blood pressure as 120 over 80 and heart rate 72', gradient: 'from-red-500/10 to-red-600/5 dark:from-red-500/20 dark:to-red-600/10', iconColor: 'text-red-500', border: 'border-red-200/60 dark:border-red-500/20' },
                { icon: 'show_chart', label: 'View HR Trend', prompt: 'Show my heart rate trend for this week', gradient: 'from-blue-500/10 to-blue-600/5 dark:from-blue-500/20 dark:to-blue-600/10', iconColor: 'text-blue-500', border: 'border-blue-200/60 dark:border-blue-500/20' },
                { icon: 'ecg_heart', label: 'Risk Assessment', prompt: 'Can you assess my cardiovascular risk based on my recent vitals?', gradient: 'from-emerald-500/10 to-emerald-600/5 dark:from-emerald-500/20 dark:to-emerald-600/10', iconColor: 'text-emerald-500', border: 'border-emerald-200/60 dark:border-emerald-500/20' },
                { icon: 'medication', label: 'Medication Info', prompt: 'What are the side effects of Metoprolol?', gradient: 'from-purple-500/10 to-purple-600/5 dark:from-purple-500/20 dark:to-purple-600/10', iconColor: 'text-purple-500', border: 'border-purple-200/60 dark:border-purple-500/20' },
              ].map((item, i) => (
                <button key={i} onClick={() => handleSend(item.prompt)}
                  style={{ animationDelay: `${i * 60}ms` }}
                  className={`flex flex-col items-center gap-2.5 p-4 rounded-2xl bg-gradient-to-br border transition-all duration-200 hover:scale-[1.02] active:scale-[0.97] animate-floatUp ${item.gradient} ${item.border}`}>
                  <div className="w-10 h-10 rounded-xl bg-white dark:bg-slate-800 flex items-center justify-center shadow-sm">
                    <span className={`material-symbols-outlined text-xl ${item.iconColor}`}>{item.icon}</span>
                  </div>
                  <span className="text-xs font-medium text-slate-700 dark:text-slate-300 text-center leading-tight">{item.label}</span>
                </button>
              ))}
            </div>
            <div className="flex items-center gap-1.5 mt-8 px-3 py-2 bg-slate-100 dark:bg-slate-800/40 rounded-full">
              <span className="material-symbols-outlined text-[11px] text-amber-500">shield</span>
              <span className="text-[10px] text-slate-400">Not a substitute for professional medical advice</span>
            </div>
          </div>
        )}

        <div className="space-y-4 py-3">
          <AnimatePresence initial={false}>
            {messages.map((msg, idx) => {
              const isUser = msg.role === 'user';
              const isLast = idx === messages.length - 1;

              if (msg.type === 'action_request') {
                return (
                  <motion.div key={msg.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                    transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                    className="flex justify-center my-1">
                    <div className="inline-flex items-center gap-2 px-4 py-2 bg-amber-50 dark:bg-amber-500/10 border border-amber-200/60 dark:border-amber-500/20 rounded-full">
                      <span className="material-symbols-outlined text-amber-500 text-sm animate-gentle-pulse">settings</span>
                      <span className="text-xs text-amber-700 dark:text-amber-300 italic">{msg.content}</span>
                    </div>
                  </motion.div>
                );
              }

              if (msg.type === 'action_result') {
                const { name } = msg.actionData;
                const config: Record<string, { icon: string; color: string; bg: string }> = {
                  logBiometrics: { icon: 'monitor_heart', color: 'text-red-500', bg: 'bg-red-50 dark:bg-red-500/10 border-red-200/60 dark:border-red-500/20' },
                  addMedication: { icon: 'pill', color: 'text-blue-500', bg: 'bg-blue-50 dark:bg-blue-500/10 border-blue-200/60 dark:border-blue-500/20' },
                  scheduleAppointment: { icon: 'calendar_today', color: 'text-purple-500', bg: 'bg-purple-50 dark:bg-purple-500/10 border-purple-200/60 dark:border-purple-500/20' },
                };
                const c = config[name] || { icon: 'check_circle', color: 'text-emerald-500', bg: 'bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200/60 dark:border-emerald-500/20' };
                return (
                  <motion.div key={msg.id} initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
                    transition={{ type: 'spring', damping: 25 }}
                    className="flex justify-center my-1">
                    <div className={`flex items-center gap-3 px-5 py-3 rounded-2xl border ${c.bg}`}>
                      <span className={`material-symbols-outlined text-xl ${c.color}`}>{c.icon}</span>
                      <div>
                        <p className="text-sm font-semibold text-slate-800 dark:text-white">{msg.content.split(':')[0]}</p>
                        {msg.content.split(':')[1] && <p className="text-[11px] text-slate-500 mt-0.5">{msg.content.split(':')[1]}</p>}
                      </div>
                    </div>
                  </motion.div>
                );
              }

              if (msg.type === 'widget' && msg.widgetData) {
                const { type, title, data } = msg.widgetData;
                return (
                  <motion.div key={msg.id} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                    transition={{ type: 'spring', damping: 25 }}
                    className="flex justify-start my-1">
                    <div className="w-full max-w-[340px] bg-white dark:bg-[#1a2737] rounded-2xl border border-slate-200 dark:border-slate-700/40 overflow-hidden shadow-sm">
                      <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-700/30 flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-700 dark:text-slate-200 uppercase tracking-wide">{title}</span>
                        <span className="material-symbols-outlined text-sm text-slate-400">show_chart</span>
                      </div>
                      <div className="p-4">
                        {type.includes('Chart') && (
                          <div className="h-36 w-full min-w-0 min-h-0">
                            <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0} debounce={50}>
                              <AreaChart data={data}>
                                <defs>
                                  <linearGradient id={`grad${msg.id}`} x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2} />
                                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                                  </linearGradient>
                                </defs>
                                <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px', fontSize: '10px', boxShadow: '0 4px 12px rgba(0,0,0,0.2)' }} itemStyle={{ color: '#fff' }} />
                                <Area type="monotone" dataKey="value" stroke="#ef4444" strokeWidth={2} fillOpacity={1} fill={`url(#grad${msg.id})`} />
                                <XAxis dataKey="day" hide />
                                <YAxis hide domain={['auto', 'auto']} />
                              </AreaChart>
                            </ResponsiveContainer>
                            <div className="flex justify-between text-[10px] text-slate-400 mt-1">
                              {data.length > 0 && <span>{data[0].day}</span>}
                              {data.length > 0 && <span>{data[data.length - 1].day}</span>}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </motion.div>
                );
              }

              return (
                <motion.div key={msg.id}
                  initial={{ opacity: 0, y: 10, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ type: 'spring', damping: 25, stiffness: 350, mass: 0.8 }}
                  className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                  <div className={`flex gap-2.5 ${isUser ? 'max-w-[88%] flex-row-reverse' : 'max-w-full w-full flex-row'}`}>
                    {!isUser && (
                      <div className="shrink-0 mt-0.5">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-red-500 to-red-700 flex items-center justify-center shadow-sm">
                          <span className="material-symbols-outlined text-white text-sm">cardiology</span>
                        </div>
                      </div>
                    )}
                    <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
                      <div className={`group relative text-sm leading-relaxed transition-all ${
                        isUser
                          ? 'px-4 py-3 bg-gradient-to-br from-red-500 to-red-600 text-white rounded-2xl rounded-br-md shadow-sm shadow-red-500/15'
                          : 'py-1 text-slate-800 dark:text-slate-100'
                      }`}>
                        {msg.image && (
                          <div className="mb-2.5 rounded-xl overflow-hidden">
                            <img src={msg.image} alt="Uploaded" className="max-w-full max-h-48 object-cover rounded-xl" />
                          </div>
                        )}
                        {!isUser ? (
                          <ChatMessageMarkdown content={msg.content} sources={msg.sources} showHealthAlerts={true} />
                        ) : (
                          <span className="leading-relaxed whitespace-pre-wrap">{msg.content}</span>
                        )}
                        {msg.isStreaming && (
                          <span className="inline-block w-0.5 h-4 bg-red-400 animate-gentle-pulse ml-0.5 rounded-full align-text-bottom" />
                        )}
                      </div>
                      <div className={`flex items-center gap-1.5 mt-1 px-1 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
                        <span className="text-[10px] text-slate-400/70 dark:text-slate-500/70 font-mono">
                          {formatTime(msg.timestamp)}
                        </span>
                        {isUser && !isLoading && (
                          <button onClick={() => editUserMessage(msg.id)}
                            className="p-1 rounded-lg text-slate-300 dark:text-slate-500 hover:text-slate-500 dark:hover:text-slate-300 hover:bg-white/20 dark:hover:bg-slate-800/50 transition-all duration-150 opacity-0 group-hover:opacity-100 focus:opacity-100"
                            title="Edit message">
                            <span className="material-symbols-outlined text-[13px]">edit</span>
                          </button>
                        )}
                        {msg.ragContext && !isUser && (
                          <span className="text-[9px] text-blue-500 bg-blue-500/10 px-1.5 py-0.5 rounded-full flex items-center gap-0.5 font-medium">
                            <span className="material-symbols-outlined text-[9px]">history</span> Memory
                          </span>
                        )}
                        {isUser && (msg as any).searchMode && (msg as any).searchMode !== 'default' && (() => {
                          const sm = searchModeLabel[(msg as any).searchMode as SearchMode];
                          return (
                            <span className={`text-[9px] px-1.5 py-0.5 rounded-full flex items-center gap-0.5 font-medium border ${sm.color}`}>
                              <span className="material-symbols-outlined text-[9px]">{sm.icon}</span> {sm.label}
                            </span>
                          );
                        })()}
                        {msg.metadata?.model && !isUser && (
                          <span className="text-[9px] text-slate-400 bg-slate-100 dark:bg-slate-800/50 px-1.5 py-0.5 rounded-full">
                            {String(msg.metadata.model)}
                          </span>
                        )}
                      </div>
                      {!isUser && !msg.isStreaming && msg.content && (
                        <div className="flex items-center gap-0.5 mt-1 pl-0.5">
                          {[
                            { action: () => regenerateMessage(msg.id), icon: regeneratingId === msg.id ? 'sync' : 'refresh', title: 'Regenerate', active: regeneratingId === msg.id, activeClass: 'animate-spin text-blue-500' },
                            { action: () => copyMessage(msg.content, msg.id), icon: copiedMessageId === msg.id ? 'check' : 'content_copy', title: copiedMessageId === msg.id ? 'Copied!' : 'Copy', active: copiedMessageId === msg.id, activeClass: 'text-emerald-500' },
                            { action: () => playTTS(msg.content, msg.id), icon: isPlayingId === msg.id ? 'stop_circle' : 'volume_up', title: isPlayingId === msg.id ? 'Stop' : 'Read aloud', active: isPlayingId === msg.id, activeClass: 'text-red-500' },
                          ].map((btn, i) => (
                            <button key={i} onClick={btn.action} disabled={btn.icon === 'refresh' && isLoading}
                              className={`p-1.5 rounded-lg transition-all duration-150 ${btn.active ? btn.activeClass : 'text-slate-300 dark:text-slate-600 hover:text-slate-500 dark:hover:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800/50'} disabled:opacity-30`}
                              title={btn.title}>
                              <span className="material-symbols-outlined text-[14px]">{btn.icon}</span>
                            </button>
                          ))}
                        </div>
                      )}
                      {msg.groundingMetadata?.groundingChunks && (
                        <div className="flex flex-wrap gap-1.5 mt-1.5">
                          {msg.groundingMetadata.groundingChunks.map((chunk: any, i: number) => (
                            <a key={i} href={chunk.web?.uri || chunk.maps?.source?.uri} target="_blank" rel="noreferrer"
                              className="flex items-center gap-1 bg-blue-50 dark:bg-blue-500/10 border border-blue-200/50 dark:border-blue-500/20 px-2 py-1 rounded-full text-[10px] text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-500/20 transition-colors">
                              <span className="material-symbols-outlined text-[10px]">link</span>
                              {chunk.web?.title || 'Source'}
                            </a>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>

          {isLoading && !messages.some(m => m.isStreaming) && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              transition={{ type: 'spring', damping: 25 }}
              className="flex justify-start">
              <div className="flex items-start gap-2.5">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-red-500 to-red-700 flex items-center justify-center shadow-sm animate-breathe">
                  <span className="material-symbols-outlined text-white text-sm">cardiology</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="px-4 py-3 bg-white dark:bg-[#1a2737] border border-slate-200/80 dark:border-slate-700/40 rounded-2xl rounded-bl-md shadow-sm">
                    <div className="flex items-center gap-1.5">
                      <div className="flex items-center gap-1">
                        <div className="w-1.5 h-1.5 bg-slate-400 dark:bg-slate-500 rounded-full typing-dot" />
                        <div className="w-1.5 h-1.5 bg-slate-400 dark:bg-slate-500 rounded-full typing-dot" />
                        <div className="w-1.5 h-1.5 bg-slate-400 dark:bg-slate-500 rounded-full typing-dot" />
                      </div>
                      <span className="text-[11px] text-slate-400 ml-1 font-medium">
                        {activeSearchMode === 'web_search' ? 'Searching the web...' : activeSearchMode === 'deep_search' ? 'Analyzing in depth...' : activeSearchMode === 'memory' ? 'Checking your history...' : 'Thinking...'}
                      </span>
                    </div>
                  </div>
                  <button onClick={() => chatActions.stopGeneration()}
                    className="p-1.5 rounded-full text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 transition-all"
                    title="Stop generating">
                    <span className="material-symbols-outlined text-[16px]">stop_circle</span>
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </div>
        <div ref={messagesEndRef} className="h-1 shrink-0" />
        </div>
      </div>

      {/* INPUT AREA */}
      <div className="px-3 pt-2 bg-white/80 dark:bg-[#151f2b]/80 backdrop-blur-xl border-t border-slate-200/50 dark:border-slate-700/30" style={{ flexShrink: 0, paddingBottom: 'max(12px, env(safe-area-inset-bottom))' }}>
        {attachment && (
          <div className="mb-2 bg-slate-50 dark:bg-[#1a2737] border border-slate-200 dark:border-slate-700/40 p-2 rounded-xl flex items-center gap-3 animate-scaleIn">
            <div className="w-12 h-12 rounded-lg bg-cover bg-center border border-slate-200 dark:border-slate-600/40 shadow-inner flex-shrink-0" style={{ backgroundImage: `url('${attachment}')` }} />
            <div className="flex-1 min-w-0">
              <p className="text-xs text-slate-700 dark:text-slate-300 font-medium">Image attached</p>
              <p className="text-[10px] text-slate-400 mt-0.5">Ask about this image</p>
            </div>
            <button onClick={removeAttachment} className="w-6 h-6 rounded-md bg-slate-200/60 dark:bg-slate-700 text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 flex items-center justify-center transition-colors flex-shrink-0">
              <span className="material-symbols-outlined text-sm">close</span>
            </button>
          </div>
        )}

        {!isLoading && messages.length > 0 && messages.length < 4 && !attachment && (
          <div className="flex gap-2 mb-2 overflow-x-auto no-scrollbar pb-0.5">
            {[
              { label: '\u2764\uFE0F Log BP', prompt: 'Log my blood pressure as 120 over 80 and heart rate 72' },
              { label: '\uD83D\uDCC8 HR Trend', prompt: 'Show my heart rate trend for this week' },
              { label: '\uD83D\uDC8A Medications', prompt: 'What medications am I currently taking?' },
            ].map((item, i) => (
              <button key={i} onClick={() => handleSend(item.prompt)}
                className="flex-shrink-0 px-3.5 py-1.5 bg-slate-100 dark:bg-slate-800/60 text-slate-600 dark:text-slate-300 text-[11px] font-medium rounded-full border border-slate-200/80 dark:border-slate-700/40 hover:bg-slate-200 dark:hover:bg-slate-700 hover:text-slate-900 dark:hover:text-white active:scale-95 transition-all">
                {item.label}
              </button>
            ))}
          </div>
        )}

        {/* Gemini-style input capsule */}
        <div className="rounded-[24px] border border-slate-200 dark:border-slate-700/50 bg-white dark:bg-[#1a2737] transition-all duration-200 input-glow">
          {/* Textarea */}
          <div className="px-5 pt-3.5 pb-1.5">
            <textarea ref={textareaRef}
              value={input} onChange={e => setInput(e.target.value)} onKeyDown={handleKeyPress}
              placeholder={attachment ? 'Ask about this image...' : 'Ask Cardio AI anything...'}
              rows={1}
              className="w-full bg-transparent text-slate-800 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none text-[15px] resize-none max-h-[140px] leading-relaxed rounded-xl"
              autoComplete="off" />
          </div>

          {/* Bottom toolbar inside capsule */}
          <div className="flex items-center justify-between px-2.5 pb-2.5 pt-0.5">
            {/* Left: tool buttons */}
            <div className="flex items-center gap-0.5">
              <input type="file" ref={fileInputRef} className="hidden" accept="image/*" onChange={handleFileSelect} />
              <button onClick={() => fileInputRef.current?.click()} title="Attach image"
                className={`p-2 rounded-full transition-all duration-150 active:scale-90 ${
                  attachment
                    ? 'text-emerald-500 bg-emerald-500/10'
                    : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700/50'
                }`}>
                <span className="material-symbols-outlined text-[20px]">{attachment ? 'check_circle' : 'add_photo_alternate'}</span>
              </button>
              <button onClick={() => (isRecording ? stopRecording() : startRecording())} title={isRecording ? 'Stop recording' : 'Voice input'}
                className={`p-2 rounded-full transition-all duration-150 active:scale-90 ${
                  isRecording
                    ? 'text-red-500 bg-red-500/10 animate-gentle-pulse'
                    : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700/50'
                }`}>
                <span className="material-symbols-outlined text-[20px]">{isRecording ? 'stop_circle' : 'mic'}</span>
              </button>

              {/* Separator */}
              <div className="w-px h-5 bg-slate-200 dark:bg-slate-700/50 mx-1" />

              {/* Search mode chips */}
              {([
                { mode: 'web_search' as SearchMode, icon: 'travel_explore', label: 'Search' },
                { mode: 'deep_search' as SearchMode, icon: 'psychology', label: 'Deep' },
                { mode: 'memory' as SearchMode, icon: 'history', label: 'Memory' },
              ]).map(chip => (
                <button key={chip.mode}
                  onClick={() => setSearchMode(searchMode === chip.mode ? 'default' : chip.mode)}
                  title={chip.label}
                  className={`flex items-center gap-1 px-2.5 py-1.5 rounded-full text-[11px] font-medium transition-all duration-200 active:scale-95 ${
                    searchMode === chip.mode
                      ? 'bg-red-500/10 dark:bg-red-500/20 text-red-600 dark:text-red-400 ring-1 ring-red-500/30'
                      : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700/50'
                  }`}>
                  <span className="material-symbols-outlined text-[14px]">{chip.icon}</span>
                  <span className="hidden sm:inline">{chip.label}</span>
                </button>
              ))}
            </div>

            {/* Right: send or stop button */}
            {isLoading || isStreaming ? (
              <button onClick={() => chatActions.stopGeneration()}
                className="p-2 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-red-100 dark:hover:bg-red-500/20 hover:text-red-600 dark:hover:text-red-400 transition-all duration-200 active:scale-90 shadow-sm"
                title="Stop generating">
                <span className="material-symbols-outlined text-[20px]">stop</span>
              </button>
            ) : (
              <button onClick={() => handleSend()} disabled={!input.trim() && !attachment}
                className={`p-2 rounded-full transition-all duration-200 ${
                  input.trim() || attachment
                    ? 'bg-gradient-to-r from-red-500 to-red-600 text-white shadow-md shadow-red-500/20 hover:shadow-lg active:scale-90'
                    : 'bg-slate-100 dark:bg-slate-800/50 text-slate-300 dark:text-slate-600'
                } disabled:opacity-40 disabled:shadow-none disabled:cursor-not-allowed`}>
                <span className="material-symbols-outlined text-[20px]">arrow_upward</span>
              </button>
            )}
          </div>
        </div>

        {isRecording && (
          <div className="flex items-center justify-center gap-2 mt-2 animate-fadeIn">
            <div className="flex items-center gap-0.5 h-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="w-0.5 bg-red-400 rounded-full waveform-bar" style={{ animationDelay: `${i * 0.1}s` }} />
              ))}
            </div>
            <span className="text-[10px] text-red-400 font-medium">Recording... Tap stop when done</span>
          </div>
        )}

        {searchMode !== 'default' && (
          <div className="flex items-center justify-center gap-1.5 mt-1.5">
            <span className="material-symbols-outlined text-[12px] text-red-500">
              {searchMode === 'web_search' ? 'travel_explore' : searchMode === 'deep_search' ? 'psychology' : 'history'}
            </span>
            <span className="text-[10px] text-slate-500 dark:text-slate-400">
              {searchMode === 'web_search' && 'Web search enabled — responses include web results'}
              {searchMode === 'deep_search' && 'Deep analysis enabled — detailed, thorough responses'}
              {searchMode === 'memory' && 'Memory context — referencing your health history'}
            </span>
          </div>
        )}

        <p className="text-center text-[9px] text-slate-300 dark:text-slate-600 mt-1.5 select-none">
          AI assistant for guidance only — consult your doctor for medical decisions
        </p>
      </div>
    </div>
  );
};

export default ChatScreen;
