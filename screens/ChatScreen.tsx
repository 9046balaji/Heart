
import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { apiClient } from '../services/apiClient';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Message } from '../types';
import { memoryService } from '../services/memoryService';
import { ChatMessageMarkdown } from '../components/MarkdownRenderer';
import { useChatStore, ChatSession, chatActions, groupSessionsByDate, ChatSettings } from '../store/useChatStore';
import { useAuth } from '../hooks/useAuth';
import { useOfflineStatus } from '../hooks/useOfflineStatus';
import { useProvider } from '../contexts/ProviderContext';
import { useToast } from '../components/Toast';

// --- Audio Helpers ---
function base64ToUint8Array(base64: string) {
  const binaryString = atob(base64);
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) bytes[i] = binaryString.charCodeAt(i);
  return bytes;
}

async function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      if (typeof reader.result === 'string') resolve(reader.result.split(',')[1]);
      else reject(new Error('Failed to convert blob to base64'));
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

// --- Sidebar Panel Type ---
type SidebarPanel = 'history' | 'settings' | null;

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

  // Sidebar
  const [sidebarPanel, setSidebarPanel] = useState<SidebarPanel>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Editing
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  // Context menu
  const [contextMenuSession, setContextMenuSession] = useState<string | null>(null);

  // Audio
  const [isRecording, setIsRecording] = useState(false);
  const [isPlayingId, setIsPlayingId] = useState<string | null>(null);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const activeSourceNodeRef = useRef<AudioBufferSourceNode | null>(null);

  // Regenerate
  const [regeneratingId, setRegeneratingId] = useState<string | null>(null);

  // Chat Store
  const {
    messages, sessions, currentSessionId,
    isLoading, isStreaming, isSearchingMemories,
    selectedModel, settings,
    createSession, loadSession, deleteSession,
    loadSessions, updateSessionTitle, setSelectedModel,
    setMessages, pinSession, archiveSession, deleteAllSessions,
    updateSettings,
  } = useChatStore();

  // ── Session management ──
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
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => { scrollToBottom(); }, [messages, isLoading, attachment, scrollToBottom]);

  // ── Grouped sessions for sidebar ──
  const activeSessions = useMemo(
    () => sessions.filter((s) => !s.isArchived),
    [sessions]
  );
  const pinnedSessions = useMemo(
    () => activeSessions.filter((s) => s.isPinned),
    [activeSessions]
  );
  const unpinnedSessions = useMemo(
    () => activeSessions.filter((s) => !s.isPinned),
    [activeSessions]
  );
  const groupedSessions = useMemo(
    () => groupSessionsByDate(unpinnedSessions),
    [unpinnedSessions]
  );
  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return null;
    const q = searchQuery.toLowerCase();
    return activeSessions.filter(
      (s) =>
        s.title.toLowerCase().includes(q) ||
        s.lastMessage?.toLowerCase().includes(q) ||
        s.messages?.some((m) => m.content.toLowerCase().includes(q))
    );
  }, [searchQuery, activeSessions]);
  const archivedSessions = useMemo(
    () => sessions.filter((s) => s.isArchived),
    [sessions]
  );
  const [showArchived, setShowArchived] = useState(false);

  const dateGroupOrder = ['Today', 'Yesterday', 'Previous 7 Days', 'Previous 30 Days', 'Older'];

  // ── File / Audio handlers (kept from original) ──
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
    const messageText = textInput || input;
    if ((!messageText.trim() && !attachment) || isLoading) return;
    if (!isOnline) { showToast('You are currently offline.', 'warning'); return; }
    setInput('');
    setAttachment(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
    await chatActions.sendMessage(messageText, selectedModel);
  };

  const startRecording = async () => {
    if (!isOnline) { showToast('Voice recording requires internet.', 'warning'); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];
      mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
      mediaRecorder.onstop = async () => {
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        await transcribeAudio(blob);
        stream.getTracks().forEach((t) => t.stop());
      };
      mediaRecorder.start();
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
      activeSourceNodeRef.current.stop(); activeSourceNodeRef.current = null; setIsPlayingId(null); return;
    }
    if (activeSourceNodeRef.current) { activeSourceNodeRef.current.stop(); activeSourceNodeRef.current = null; }
    setIsPlayingId(messageId);
    try {
      const response = await apiClient.synthesizeSpeech(text);
      if (response.success && response.audio) {
        const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
        audioContextRef.current = ctx;
        const audioData = base64ToUint8Array(response.audio);
        const audioBuffer = await ctx.decodeAudioData(audioData.buffer);
        const source = ctx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(ctx.destination);
        source.onended = () => { setIsPlayingId(null); activeSourceNodeRef.current = null; };
        source.start(0);
        activeSourceNodeRef.current = source;
      } else {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.onend = () => setIsPlayingId(null);
        window.speechSynthesis.speak(utterance);
      }
    } catch {
      setIsPlayingId(null);
      if ('speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.onend = () => setIsPlayingId(null);
        window.speechSynthesis.speak(utterance);
      }
    }
  };

  const copyMessage = async (text: string, messageId: string) => {
    try { await navigator.clipboard.writeText(text); setCopiedMessageId(messageId); setTimeout(() => setCopiedMessageId(null), 2000); } catch {}
  };

  const handleRenameSession = async (sessionId: string) => {
    if (editTitle.trim()) await updateSessionTitle(sessionId, editTitle);
    setEditingSessionId(null);
  };

  const regenerateMessage = async (messageId: string) => {
    setRegeneratingId(messageId);
    try { await chatActions.regenerateLastResponse(); } finally { setRegeneratingId(null); }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  // ── Settings Panel Component ──
  const SettingsPanel = () => {
    const [localSettings, setLocalSettings] = useState<ChatSettings>({ ...settings });

    const handleSave = () => {
      updateSettings(localSettings);
      showToast('Settings saved', 'success');
    };

    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800 flex-shrink-0">
          <h2 className="font-bold text-slate-900 dark:text-white text-base">Chat Settings</h2>
          <button onClick={() => setSidebarPanel(null)} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 transition-colors">
            <span className="material-symbols-outlined text-lg">close</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {/* Model */}
          <div>
            <label className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2 block">AI Model</label>
            <div className="grid grid-cols-2 gap-2">
              {(['gemini', 'ollama'] as const).map((m) => (
                <button key={m} onClick={() => setSelectedModel(m)}
                  className={`py-2.5 px-3 rounded-xl text-sm font-medium transition-all ${
                    selectedModel === m
                      ? 'bg-[#D32F2F] text-white shadow-lg shadow-red-900/30'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
                  }`}>
                  <span className="material-symbols-outlined text-sm mr-1 align-middle">{m === 'ollama' ? 'memory' : 'cloud'}</span>
                  {m === 'ollama' ? 'Ollama' : 'Gemini'}
                </button>
              ))}
            </div>
          </div>

          {/* Temperature */}
          <div>
            <label className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2 block">
              Temperature <span className="text-slate-900 dark:text-white ml-1">{localSettings.temperature.toFixed(1)}</span>
            </label>
            <input type="range" min="0" max="1" step="0.1"
              value={localSettings.temperature}
              onChange={(e) => setLocalSettings({ ...localSettings, temperature: parseFloat(e.target.value) })}
              className="w-full accent-[#D32F2F] h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full"
            />
            <div className="flex justify-between text-[10px] text-slate-500 mt-1"><span>Precise</span><span>Creative</span></div>
          </div>

          {/* System Prompt */}
          <div>
            <label className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2 block">System Prompt</label>
            <textarea rows={4}
              value={localSettings.systemPrompt}
              onChange={(e) => setLocalSettings({ ...localSettings, systemPrompt: e.target.value })}
              className="w-full bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-800 dark:text-slate-200 focus:outline-none focus:border-[#D32F2F] resize-none"
            />
          </div>

          {/* Toggles */}
          <div className="space-y-3">
            {[
              { key: 'streamResponses' as const, label: 'Stream Responses', desc: 'See tokens appear in real-time' },
              { key: 'autoGenerateTitle' as const, label: 'Auto-name Chats', desc: 'Generate title from first message' },
            ].map((toggle) => (
              <div key={toggle.key} className="flex items-center justify-between bg-slate-50 dark:bg-slate-800 rounded-xl px-4 py-3">
                <div>
                  <p className="text-sm text-slate-900 dark:text-white font-medium">{toggle.label}</p>
                  <p className="text-[10px] text-slate-500">{toggle.desc}</p>
                </div>
                <button onClick={() => setLocalSettings({ ...localSettings, [toggle.key]: !localSettings[toggle.key] })}
                  className={`w-10 h-6 rounded-full transition-colors relative ${localSettings[toggle.key] ? 'bg-[#D32F2F]' : 'bg-slate-600'}`}>
                  <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${localSettings[toggle.key] ? 'left-[18px]' : 'left-0.5'}`}></span>
                </button>
              </div>
            ))}
          </div>

          {/* Danger Zone */}
          <div>
            <label className="text-xs font-bold text-red-500 dark:text-red-400 uppercase tracking-wider mb-2 block">Danger Zone</label>
            <button onClick={() => { deleteAllSessions(); showToast('All chats deleted', 'success'); setSidebarPanel(null); }}
              className="w-full py-3 bg-red-900/20 border border-red-900/40 text-red-400 rounded-xl text-sm font-medium hover:bg-red-900/30 transition-colors flex items-center justify-center gap-2">
              <span className="material-symbols-outlined text-sm">delete_forever</span>
              Delete All Conversations
            </button>
          </div>
        </div>

        <div className="px-5 py-4 border-t border-slate-200 dark:border-slate-800 flex-shrink-0">
          <button onClick={handleSave}
            className="w-full py-3 bg-[#D32F2F] text-white rounded-xl text-sm font-bold hover:bg-red-700 transition-colors shadow-lg shadow-red-900/30">
            Save Settings
          </button>
        </div>
      </div>
    );
  };

  // ── Session Item Component ──
  const SessionItem = ({ session }: { session: ChatSession }) => {
    const isActive = session.id === currentSessionId;
    const isEditing = editingSessionId === session.id;
    const showMenu = contextMenuSession === session.id;

    return (
      <div
        className={`group relative flex items-center gap-2 px-3 py-2.5 rounded-xl cursor-pointer transition-all text-sm ${
          isActive ? 'bg-[#D32F2F]/15 text-slate-900 dark:text-white' : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60'
        }`}
        onClick={() => { if (!isEditing) { loadSession(session.id); setSidebarPanel(null); } }}
      >
        <span className="material-symbols-outlined text-sm text-slate-500 flex-shrink-0">
          {session.isPinned ? 'push_pin' : 'chat_bubble_outline'}
        </span>

        {isEditing ? (
          <input type="text" value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            onBlur={() => handleRenameSession(session.id)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleRenameSession(session.id); if (e.key === 'Escape') setEditingSessionId(null); }}
            autoFocus
            className="flex-1 bg-transparent border-b border-[#D32F2F] text-sm focus:outline-none text-slate-900 dark:text-white min-w-0"
            onClick={(e) => e.stopPropagation()}
          />
        ) : (
          <div className="flex-1 min-w-0">
            <p className="text-sm truncate font-medium">{session.title}</p>
            <p className="text-[10px] text-slate-500 truncate">{session.lastMessage || `${session.messageCount} messages`}</p>
          </div>
        )}

        {/* Hover actions */}
        {!isEditing && (
          <button onClick={(e) => { e.stopPropagation(); setContextMenuSession(showMenu ? null : session.id); }}
            className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-400 transition-all flex-shrink-0">
            <span className="material-symbols-outlined text-sm">more_horiz</span>
          </button>
        )}

        {/* Context menu */}
        {showMenu && (
          <div className="absolute right-0 top-full mt-1 bg-white dark:bg-[#131d28] border border-slate-200 dark:border-slate-700/60 rounded-xl shadow-2xl shadow-black/10 dark:shadow-black/40 z-50 py-1 min-w-[160px] animate-scaleIn"
            onClick={(e) => e.stopPropagation()}>
            {[
              { icon: 'edit', label: 'Rename', action: () => { setEditingSessionId(session.id); setEditTitle(session.title); setContextMenuSession(null); } },
              { icon: session.isPinned ? 'push_pin' : 'push_pin', label: session.isPinned ? 'Unpin' : 'Pin', action: () => { pinSession(session.id); setContextMenuSession(null); } },
              { icon: 'archive', label: session.isArchived ? 'Unarchive' : 'Archive', action: () => { archiveSession(session.id); setContextMenuSession(null); } },
              { icon: 'delete', label: 'Delete', action: () => { deleteSession(session.id); setContextMenuSession(null); }, danger: true },
            ].map((item) => (
              <button key={item.label} onClick={item.action}
                className={`w-full flex items-center gap-2.5 px-3 py-2 text-xs text-left transition-all duration-150 ${
                  (item as any).danger ? 'text-red-500 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20' : 'text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/70'
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

  // ── Close context menu on outside click ──
  useEffect(() => {
    if (contextMenuSession) {
      const close = () => setContextMenuSession(null);
      const timer = setTimeout(() => document.addEventListener('click', close), 0);
      return () => { clearTimeout(timer); document.removeEventListener('click', close); };
    }
  }, [contextMenuSession]);

  return (
    <div className="flex flex-col h-screen bg-slate-50 dark:bg-[#101922] relative overflow-hidden font-sans">

      {/* ══════════ SIDEBAR ══════════ */}
      <AnimatePresence>
        {sidebarPanel !== null && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 bg-black/60 z-40 backdrop-blur-sm"
              onClick={() => setSidebarPanel(null)}
            />
            <motion.nav
              initial={{ x: -320 }} animate={{ x: 0 }} exit={{ x: -320 }}
              transition={{ type: 'spring', damping: 28, stiffness: 350 }}
              className="fixed top-0 left-0 h-screen w-80 max-w-[85vw] bg-white dark:bg-[#131d28] z-50 shadow-2xl shadow-black/10 dark:shadow-black/50 flex flex-col overflow-hidden border-r border-slate-200/50 dark:border-slate-800/30"
            >
              {sidebarPanel === 'settings' ? (
                <SettingsPanel />
              ) : (
                <>
                  {/* Header */}
                  <div className="px-4 pt-5 pb-3 flex-shrink-0">
                    <div className="flex items-center justify-between mb-4">
                      <h2 className="font-bold text-slate-900 dark:text-white text-base">Conversations</h2>
                      <button onClick={() => setSidebarPanel(null)} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 transition-colors">
                        <span className="material-symbols-outlined text-lg">close</span>
                      </button>
                    </div>

                    {/* New Chat */}
                    <button onClick={() => { createSession(); setSidebarPanel(null); }}
                      className="w-full flex items-center justify-center gap-2 py-2.5 mb-3 bg-gradient-to-r from-[#D32F2F] to-[#B71C1C] hover:from-red-600 hover:to-red-800 text-white rounded-xl transition-all duration-200 font-medium text-sm shadow-lg shadow-red-900/25 active:scale-[0.98]">
                      <span className="material-symbols-outlined text-lg">add</span>
                      New Chat
                    </button>

                    {/* Search */}
                    <div className="relative">
                      <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">search</span>
                      <input type="text" placeholder="Search conversations..."
                        value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full bg-slate-100 dark:bg-[#101922] border border-slate-200 dark:border-slate-700 rounded-xl py-2.5 pl-9 pr-4 text-slate-800 dark:text-slate-200 text-xs focus:outline-none focus:border-[#D32F2F] transition-colors"
                      />
                      {searchQuery && (
                        <button onClick={() => setSearchQuery('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
                          <span className="material-symbols-outlined text-sm">close</span>
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Session List */}
                  <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-1">
                    {searchResults ? (
                      /* Search Results */
                      searchResults.length === 0 ? (
                        <div className="text-center py-8">
                          <span className="material-symbols-outlined text-3xl text-slate-600 mb-2 block">search_off</span>
                          <p className="text-xs text-slate-500">No results for "{searchQuery}"</p>
                        </div>
                      ) : (
                        <>
                          <p className="text-[10px] text-slate-500 uppercase tracking-wider px-2 py-1.5 font-bold">
                            {searchResults.length} result{searchResults.length !== 1 ? 's' : ''}
                          </p>
                          {searchResults.map((s) => <SessionItem key={s.id} session={s} />)}
                        </>
                      )
                    ) : (
                      <>
                        {/* Pinned */}
                        {pinnedSessions.length > 0 && (
                          <div className="mb-2">
                            <p className="text-[10px] text-slate-500 uppercase tracking-wider px-2 py-1.5 font-bold flex items-center gap-1">
                              <span className="material-symbols-outlined text-[10px]">push_pin</span> Pinned
                            </p>
                            {pinnedSessions.map((s) => <SessionItem key={s.id} session={s} />)}
                          </div>
                        )}

                        {/* Date groups */}
                        {dateGroupOrder.map((group) =>
                          groupedSessions[group] ? (
                            <div key={group} className="mb-2">
                              <p className="text-[10px] text-slate-500 uppercase tracking-wider px-2 py-1.5 font-bold">{group}</p>
                              {groupedSessions[group].map((s) => <SessionItem key={s.id} session={s} />)}
                            </div>
                          ) : null
                        )}

                        {/* Archived */}
                        {archivedSessions.length > 0 && (
                          <div className="mt-4">
                            <button onClick={() => setShowArchived(!showArchived)}
                              className="flex items-center gap-2 text-[10px] text-slate-500 uppercase tracking-wider px-2 py-1.5 font-bold w-full hover:text-slate-400 transition-colors">
                              <span className="material-symbols-outlined text-xs">{showArchived ? 'expand_less' : 'expand_more'}</span>
                              Archived ({archivedSessions.length})
                            </button>
                            {showArchived && archivedSessions.map((s) => <SessionItem key={s.id} session={s} />)}
                          </div>
                        )}

                        {activeSessions.length === 0 && (
                          <div className="text-center py-12">
                            <span className="material-symbols-outlined text-4xl text-slate-700 mb-2 block">forum</span>
                            <p className="text-sm text-slate-500">No conversations yet</p>
                            <p className="text-[10px] text-slate-600 mt-1">Start a new chat to begin</p>
                          </div>
                        )}
                      </>
                    )}
                  </div>

                  {/* Bottom: Settings */}
                  <div className="px-4 py-3 border-t border-slate-200 dark:border-slate-800 flex-shrink-0 space-y-1">
                    <button onClick={() => setSidebarPanel('settings')}
                      className="w-full flex items-center gap-3 px-3 py-2.5 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white rounded-xl transition-colors text-sm">
                      <span className="material-symbols-outlined text-lg text-slate-500 dark:text-slate-400">tune</span>
                      <span className="font-medium">Chat Settings</span>
                    </button>
                    <button onClick={() => { setSidebarPanel(null); navigate('/settings'); }}
                      className="w-full flex items-center gap-3 px-3 py-2.5 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white rounded-xl transition-colors text-sm">
                      <span className="material-symbols-outlined text-lg text-slate-500 dark:text-slate-400">settings</span>
                      <span className="font-medium">App Settings</span>
                    </button>
                  </div>
                </>
              )}
            </motion.nav>
          </>
        )}
      </AnimatePresence>

      {/* ══════════ HEADER ══════════ */}
      <div className="flex items-center justify-between px-3 py-2.5 z-10 glass-surface border-b border-slate-200/60 dark:border-slate-800/40 flex-shrink-0">
        <div className="flex items-center gap-0.5">
          <button onClick={() => navigate(-1)} className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800/70 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-all duration-200 active:scale-95">
            <span className="material-symbols-outlined text-xl">arrow_back</span>
          </button>
          <button onClick={() => setSidebarPanel('history')} className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800/70 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-all duration-200 active:scale-95">
            <span className="material-symbols-outlined text-xl">menu</span>
          </button>
        </div>

        <div className="flex flex-col items-center">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-red-500 to-red-700 flex items-center justify-center shadow-md shadow-red-900/30">
              <span className="material-symbols-outlined text-white text-sm">cardiology</span>
            </div>
            <h1 className="font-bold text-base text-slate-900 dark:text-white tracking-tight">Cardio AI</h1>
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            {isOnline ? (
              <span className="flex items-center gap-1 text-[10px] text-emerald-400 font-medium">
                <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-gentle-pulse"></span>
                Online
              </span>
            ) : (
              <span className="flex items-center gap-1 text-[10px] text-amber-400 font-medium">
                <span className="w-1.5 h-1.5 bg-amber-400 rounded-full"></span>
                Offline
              </span>
            )}
            <span className="text-slate-300 dark:text-slate-700">•</span>
            <span className="flex items-center gap-1 text-[10px] text-slate-500 font-medium">
              <span className="material-symbols-outlined text-[10px]">{selectedModel === 'ollama' ? 'memory' : 'cloud'}</span>
              {selectedModel === 'ollama' ? 'Local' : 'Cloud'}
            </span>
            {isSearchingMemories && (
              <>
                <span className="text-slate-300 dark:text-slate-700">•</span>
                <span className="text-[10px] text-blue-400 flex items-center gap-0.5 font-medium">
                  <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse"></span> Memory
                </span>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center gap-0.5">
          <button onClick={() => createSession()} className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800/70 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-all duration-200 active:scale-95" title="New chat">
            <span className="material-symbols-outlined text-xl">edit_square</span>
          </button>
          <button onClick={() => setSidebarPanel('settings')} className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800/70 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-all duration-200 active:scale-95" title="Settings">
            <span className="material-symbols-outlined text-xl">tune</span>
          </button>
        </div>
      </div>

      {/* ══════════ MESSAGES ══════════ */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5 chat-messages" role="log" aria-label="Chat messages" aria-live="polite">
        {/* Welcome screen when no messages */}
        {messages.length === 0 && !isLoading && (
          <div className="flex flex-col items-center justify-center h-full py-12 animate-fadeIn">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-red-500 to-red-700 flex items-center justify-center shadow-xl shadow-red-900/30 mb-5 animate-breathe">
              <span className="material-symbols-outlined text-white text-3xl">cardiology</span>
            </div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-1.5">Welcome to Cardio AI</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 text-center max-w-xs mb-2">
              Your intelligent cardiac health assistant. Ask me anything about heart health, log vitals, or get personalized guidance.
            </p>
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 dark:bg-slate-800/50 rounded-full mt-1 mb-8">
              <span className="material-symbols-outlined text-xs text-amber-400">shield</span>
              <span className="text-[10px] text-slate-500">Medical AI — Not a substitute for professional care</span>
            </div>

            <div className="grid grid-cols-2 gap-2.5 w-full max-w-sm">
              {[
                { icon: 'monitor_heart', label: 'Log Blood Pressure', prompt: 'Log my blood pressure as 120 over 80 and heart rate 72', color: 'from-red-50 to-red-100/50 dark:from-red-900/40 dark:to-red-950/20 border-red-200 dark:border-red-800/30 text-red-600 dark:text-red-300' },
                { icon: 'show_chart', label: 'View HR Trend', prompt: 'Show my heart rate trend for this week', color: 'from-blue-50 to-blue-100/50 dark:from-blue-900/40 dark:to-blue-950/20 border-blue-200 dark:border-blue-800/30 text-blue-600 dark:text-blue-300' },
                { icon: 'restaurant', label: 'Heart-Healthy Meal', prompt: 'Suggest a heart-healthy meal plan for today', color: 'from-emerald-50 to-emerald-100/50 dark:from-emerald-900/40 dark:to-emerald-950/20 border-emerald-200 dark:border-emerald-800/30 text-emerald-600 dark:text-emerald-300' },
                { icon: 'calendar_today', label: 'Book Appointment', prompt: 'Book Dr. Smith for next Monday', color: 'from-purple-50 to-purple-100/50 dark:from-purple-900/40 dark:to-purple-950/20 border-purple-200 dark:border-purple-800/30 text-purple-600 dark:text-purple-300' },
              ].map((item, i) => (
                <button key={i} onClick={() => handleSend(item.prompt)}
                  style={{ animationDelay: `${i * 80}ms` }}
                  className={`flex flex-col items-center gap-2 p-4 rounded-2xl bg-gradient-to-br border transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] animate-floatUp ${item.color}`}>
                  <span className="material-symbols-outlined text-xl">{item.icon}</span>
                  <span className="text-xs font-medium text-center leading-tight">{item.label}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        <AnimatePresence initial={false}>
          {messages.map((msg) => {
            // Action Requests
            if (msg.type === 'action_request') {
              return (
                <motion.div key={msg.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                  transition={{ type: 'spring', damping: 20, stiffness: 300 }}
                  className="flex justify-center w-full my-2">
                  <div className="flex items-center gap-2.5 px-4 py-2.5 glass-surface rounded-full border border-slate-200 dark:border-slate-700/50 shadow-sm">
                    <span className="material-symbols-outlined text-amber-500 dark:text-amber-400 text-sm animate-gentle-pulse">settings</span>
                    <span className="text-xs text-slate-600 dark:text-slate-300 italic">{msg.content}</span>
                  </div>
                </motion.div>
              );
            }

            // Action Results
            if (msg.type === 'action_result') {
              const { name } = msg.actionData;
              let icon = 'check_circle', color = 'text-emerald-400', bgColor = 'bg-emerald-500/10 border-emerald-500/20';
              if (name === 'logBiometrics') { icon = 'monitor_heart'; color = 'text-red-400'; bgColor = 'bg-red-500/10 border-red-500/20'; }
              if (name === 'addMedication') { icon = 'pill'; color = 'text-blue-400'; bgColor = 'bg-blue-500/10 border-blue-500/20'; }
              if (name === 'scheduleAppointment') { icon = 'calendar_today'; color = 'text-purple-400'; bgColor = 'bg-purple-500/10 border-purple-500/20'; }
              return (
                <motion.div key={msg.id} initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
                  transition={{ type: 'spring', damping: 20, stiffness: 300 }}
                  className="flex justify-center w-full my-2">
                  <div className={`flex flex-col items-center p-4 rounded-2xl border w-3/4 max-w-sm ${bgColor}`}>
                    <div className={`w-10 h-10 rounded-xl ${bgColor} flex items-center justify-center mb-2.5`}>
                      <span className={`material-symbols-outlined text-xl ${color}`}>{icon}</span>
                    </div>
                    <p className="text-sm font-semibold text-slate-900 dark:text-white mb-0.5">{msg.content.split(':')[0]}</p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 text-center leading-relaxed">{msg.content.split(':')[1]}</p>
                  </div>
                </motion.div>
              );
            }

            // Widgets
            if (msg.type === 'widget' && msg.widgetData) {
              const { type, title, data } = msg.widgetData;
              return (
                <motion.div key={msg.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                  transition={{ type: 'spring', damping: 20, stiffness: 300 }}
                  className="flex justify-start w-full my-2">
                  <div className="w-full max-w-sm bg-white dark:bg-[#192633] rounded-2xl border border-slate-200 dark:border-slate-700/60 overflow-hidden shadow-lg">
                    <div className="bg-gradient-to-r from-slate-100/80 to-slate-100/40 dark:from-slate-800/80 dark:to-slate-800/40 px-4 py-3 border-b border-slate-200/60 dark:border-slate-700/40 flex justify-between items-center">
                      <span className="text-xs font-bold text-slate-700 dark:text-slate-200 uppercase tracking-wider">{title}</span>
                      <div className="w-7 h-7 rounded-lg bg-slate-200/70 dark:bg-slate-700/50 flex items-center justify-center">
                        <span className="material-symbols-outlined text-slate-500 dark:text-slate-400 text-sm">
                          {type === 'recipeCard' ? 'restaurant_menu' : 'show_chart'}
                        </span>
                      </div>
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
                              <Tooltip contentStyle={{ backgroundColor: 'var(--tooltip-bg, #1e293b)', border: 'none', borderRadius: '8px', fontSize: '10px' }} itemStyle={{ color: '#fff' }} />
                              <Area type="monotone" dataKey="value" stroke="#137fec" strokeWidth={2} fillOpacity={1} fill={`url(#grad${msg.id})`} />
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
                          {data.image && <div className="w-full h-32 rounded-lg bg-cover bg-center" style={{ backgroundImage: `url('${data.image}')` }} />}
                          <div>
                            <h4 className="font-bold text-slate-900 dark:text-white text-sm">{data.title}</h4>
                            <div className="flex gap-2 text-xs text-slate-500 dark:text-slate-400 mt-1"><span>{data.calories} kcal</span> • <span>{data.time || '15 min'}</span></div>
                          </div>
                          <button onClick={() => navigate('/nutrition')} className="w-full py-2.5 bg-gradient-to-r from-slate-200 to-slate-300 dark:from-slate-700 dark:to-slate-600 hover:from-slate-300 hover:to-slate-400 dark:hover:from-slate-600 dark:hover:to-slate-500 text-slate-800 dark:text-white rounded-xl text-xs font-bold transition-all duration-200 active:scale-[0.98]">View Recipe</button>
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              );
            }

            // Standard Text Message
            return (
              <motion.div key={msg.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                transition={{ type: 'spring', damping: 22, stiffness: 300, mass: 0.8 }}
                className={`flex w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`flex flex-col max-w-[85%] ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                  {/* Sender Label + Badges */}
                  <div className="flex items-center gap-2 mb-1 px-1">
                    <span className="text-[11px] text-slate-500 font-medium">{msg.role === 'user' ? 'You' : 'Cardio AI'}</span>
                    {msg.ragContext && msg.role === 'assistant' && (
                      <span className="text-[10px] text-blue-400 bg-blue-900/30 px-1.5 py-0.5 rounded-full flex items-center gap-0.5 font-medium" title="Used your past data">
                        <span className="material-symbols-outlined text-[10px]">history</span> Memory
                      </span>
                    )}
                    {msg.metadata?.model && msg.role === 'assistant' && (
                      <span className="text-[9px] text-slate-500 dark:text-slate-600 bg-slate-100 dark:bg-slate-800/50 px-1.5 py-0.5 rounded-full">
                        {String(msg.metadata.model)}
                      </span>
                    )}
                  </div>

                  <div className={`flex gap-2.5 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                    {/* Avatar */}
                    <div className="shrink-0 mt-1">
                      {msg.role === 'assistant' ? (
                        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-red-500 to-red-700 flex items-center justify-center shadow-lg shadow-red-900/25 ring-1 ring-red-500/20">
                          <span className="material-symbols-outlined text-white text-sm">cardiology</span>
                        </div>
                      ) : (
                        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-slate-500 to-slate-600 flex items-center justify-center ring-1 ring-slate-500/20">
                          <span className="material-symbols-outlined text-sm text-white">person</span>
                        </div>
                      )}
                    </div>

                    {/* Bubble */}
                    <div className={`p-3.5 rounded-2xl text-sm leading-relaxed relative group transition-all duration-200 ${
                      msg.role === 'assistant'
                        ? 'bg-white dark:bg-[#192633] text-slate-800 dark:text-slate-100 rounded-tl-md border border-slate-200/80 dark:border-slate-800/60 shadow-md shadow-slate-200/50 dark:shadow-black/10'
                        : 'bg-gradient-to-br from-[#D32F2F] to-[#B71C1C] text-white rounded-tr-md shadow-md shadow-red-900/20'
                    }`}>
                      {/* Image attachment */}
                      {msg.image && (
                        <div className="mb-3 rounded-xl overflow-hidden border border-white/10 shadow-inner">
                          <img src={msg.image} alt="Uploaded" className="max-w-full h-auto max-h-48 object-cover" />
                        </div>
                      )}

                      {msg.role === 'assistant' ? (
                        <ChatMessageMarkdown content={msg.content} sources={msg.sources} showHealthAlerts={true} />
                      ) : (
                        <span className="leading-relaxed">{msg.content}</span>
                      )}

                      {/* Streaming cursor */}
                      {msg.isStreaming && (
                        <span className="inline-block w-0.5 h-4 bg-red-400 animate-gentle-pulse ml-0.5 rounded-full align-text-bottom"></span>
                      )}

                      {/* Message Actions — assistant only */}
                      {msg.role === 'assistant' && !msg.isStreaming && msg.content && (
                        <div className="flex items-center gap-0.5 mt-2.5 pt-2 border-t border-slate-100 dark:border-slate-800/40 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                          <button onClick={() => regenerateMessage(msg.id)} disabled={regeneratingId === msg.id || isLoading}
                            className={`p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800/70 transition-all duration-200 ${regeneratingId === msg.id ? 'text-blue-500 dark:text-blue-400 animate-spin' : 'text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300'} disabled:opacity-40`} title="Regenerate">
                            <span className="material-symbols-outlined text-[15px]">refresh</span>
                          </button>
                          <button onClick={() => copyMessage(msg.content, msg.id)}
                            className={`p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800/70 transition-all duration-200 ${copiedMessageId === msg.id ? 'text-emerald-500 dark:text-emerald-400' : 'text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300'}`}
                            title={copiedMessageId === msg.id ? 'Copied!' : 'Copy'}>
                            <span className="material-symbols-outlined text-[15px]">{copiedMessageId === msg.id ? 'check' : 'content_copy'}</span>
                          </button>
                          <button onClick={() => playTTS(msg.content, msg.id)}
                            className={`p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800/70 transition-all duration-200 ${isPlayingId === msg.id ? 'text-red-500 dark:text-red-400' : 'text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300'}`}
                            title={isPlayingId === msg.id ? 'Stop' : 'Read aloud'}>
                            <span className="material-symbols-outlined text-[15px]">{isPlayingId === msg.id ? 'stop_circle' : 'volume_up'}</span>
                          </button>
                          {/* Timestamp on hover */}
                          <span className="ml-auto text-[9px] text-slate-600 font-mono">
                            {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                      )}

                      {/* User message timestamp */}
                      {msg.role === 'user' && (
                        <div className="flex justify-end mt-1.5 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                          <span className="text-[9px] text-white/40 font-mono">
                            {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Grounding Sources */}
                  {msg.groundingMetadata?.groundingChunks && (
                    <div className="mt-2 ml-11 flex flex-wrap gap-1.5">
                      {msg.groundingMetadata.groundingChunks.map((chunk: any, i: number) => (
                        <a key={i} href={chunk.web?.uri || chunk.maps?.source?.uri} target="_blank" rel="noreferrer"
                          className="flex items-center gap-1 bg-blue-900/20 border border-blue-800/30 px-2 py-1 rounded-full text-[10px] text-blue-400 hover:text-blue-300 hover:bg-blue-900/30 transition-all duration-200">
                          <span className="material-symbols-outlined text-[10px]">link</span>
                          {chunk.web?.title || 'Source'}
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>

        {/* Professional typing indicator */}
        {isLoading && !messages.some((m) => m.isStreaming) && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', damping: 20, stiffness: 300 }}
            className="flex justify-start w-full">
            <div className="flex items-start gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-red-500 to-red-700 flex items-center justify-center shadow-lg shadow-red-900/25 ring-1 ring-red-500/20 animate-breathe">
                <span className="material-symbols-outlined text-white text-sm">cardiology</span>
              </div>
              <div className="px-4 py-3.5 bg-white dark:bg-[#192633] border border-slate-200/80 dark:border-slate-800/60 rounded-2xl rounded-tl-md shadow-md shadow-slate-200/50 dark:shadow-black/10">
                <div className="flex items-center gap-1">
                  <div className="w-2 h-2 bg-slate-400 rounded-full typing-dot"></div>
                  <div className="w-2 h-2 bg-slate-400 rounded-full typing-dot"></div>
                  <div className="w-2 h-2 bg-slate-400 rounded-full typing-dot"></div>
                </div>
              </div>
            </div>
          </motion.div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* ══════════ INPUT ══════════ */}
      <div className="px-3 pb-3 pt-2 glass-surface border-t border-slate-200/50 dark:border-slate-800/30 relative flex-shrink-0">
        {/* Attachment preview */}
        {attachment && (
          <div className="mb-2 bg-white dark:bg-[#192633] border border-slate-200 dark:border-slate-700/50 p-2.5 rounded-xl flex items-center gap-3 animate-scaleIn">
            <div className="w-14 h-14 rounded-xl bg-cover bg-center border border-slate-200 dark:border-slate-600/50 shadow-inner" style={{ backgroundImage: `url('${attachment}')` }} />
            <div className="flex-1 min-w-0">
              <p className="text-xs text-slate-700 dark:text-slate-300 font-medium">Image attached</p>
              <p className="text-[10px] text-slate-500">Ask about this image</p>
            </div>
            <button onClick={removeAttachment} className="w-7 h-7 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:bg-red-50 dark:hover:bg-red-900/50 hover:text-red-500 dark:hover:text-red-400 flex items-center justify-center transition-colors">
              <span className="material-symbols-outlined text-sm">close</span>
            </button>
          </div>
        )}

        {/* Inline quick actions (only when conversation is short, no welcome screen) */}
        {!isLoading && messages.length > 0 && messages.length < 3 && !attachment && (
          <div className="flex gap-2 mb-2.5 overflow-x-auto no-scrollbar pb-0.5">
            {[
              { label: '💓 Log BP', prompt: 'Log my blood pressure as 120 over 80 and heart rate 72' },
              { label: '📈 HR Trend', prompt: 'Show my heart rate trend for this week' },
              { label: '📅 Book Appt', prompt: 'Book Dr. Smith for next Monday' },
            ].map((item, i) => (
              <button key={i} onClick={() => handleSend(item.prompt)}
                className="flex-shrink-0 px-3.5 py-1.5 bg-slate-100 dark:bg-slate-800/70 text-slate-600 dark:text-slate-300 text-xs font-medium rounded-full border border-slate-200 dark:border-slate-700/50 hover:bg-slate-200 dark:hover:bg-slate-700 hover:text-slate-900 dark:hover:text-white transition-all duration-200 active:scale-95">
                {item.label}
              </button>
            ))}
          </div>
        )}

        <div className="flex items-end gap-2">
          <input type="file" ref={fileInputRef} className="hidden" accept="image/*" onChange={handleFileSelect} />
          <button onClick={() => fileInputRef.current?.click()}
            className={`flex items-center justify-center w-10 h-10 rounded-xl shadow-md transition-all duration-200 shrink-0 active:scale-90 ${
              attachment ? 'bg-emerald-600 text-white shadow-emerald-900/30' : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700/50'
            }`}>
            <span className="material-symbols-outlined text-lg">{attachment ? 'check' : 'attach_file'}</span>
          </button>

          <div className="flex-1 relative input-glow rounded-2xl border border-slate-200 dark:border-slate-700/60 bg-white dark:bg-[#1a2737] transition-all duration-200">
            <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyPress}
              placeholder={attachment ? 'Ask about this image...' : 'Message Cardio AI...'}
              rows={1}
              className="chat-textarea w-full bg-transparent pl-4 pr-11 py-2.5 text-slate-800 dark:text-slate-200 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none text-sm"
              autoComplete="off"
            />
            <button onClick={() => handleSend()} disabled={!input.trim() && !attachment}
              className={`absolute right-1.5 bottom-1.5 p-1.5 rounded-lg transition-all duration-200 ${
                input.trim() || attachment
                  ? 'bg-[#D32F2F] text-white shadow-md shadow-red-900/30 hover:bg-red-700 active:scale-90'
                  : 'text-slate-600'
              } disabled:opacity-30 disabled:shadow-none`}>
              <span className="material-symbols-outlined text-lg">send</span>
            </button>
          </div>

          <button onClick={() => (isRecording ? stopRecording() : startRecording())}
            className={`flex items-center justify-center w-10 h-10 rounded-xl shadow-md transition-all duration-200 shrink-0 active:scale-90 ${
              isRecording
                ? 'bg-red-600 text-white scale-105 voice-orb-active border border-red-500/50'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700/50'
            }`}>
            <span className="material-symbols-outlined text-lg">{isRecording ? 'stop' : 'mic'}</span>
          </button>
        </div>

        {/* Recording indicator */}
        {isRecording && (
          <div className="flex items-center justify-center gap-2 mt-2 animate-fadeIn">
            <div className="flex items-center gap-0.5 h-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="w-0.5 bg-red-400 rounded-full waveform-bar" style={{ animationDelay: `${i * 0.1}s` }}></div>
              ))}
            </div>
            <span className="text-[10px] text-red-400 font-medium">Recording...</span>
          </div>
        )}

        <p className="text-center text-[10px] text-slate-400 dark:text-slate-600 mt-2 select-none">
          <span className="material-symbols-outlined text-[10px] align-middle mr-0.5">info</span>
          AI assistant for guidance only — not a substitute for professional medical advice
        </p>
      </div>
    </div>
  );
};

export default ChatScreen;
