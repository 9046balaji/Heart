
import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { apiClient } from '../services/apiClient';
import { useToast } from './Toast';

const VoiceControl: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { showToast: showNotification } = useToast();

  // Basic State
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [showToast, setShowToast] = useState(false);

  // Hands-Free Mode State
  const [isHandsFree, setIsHandsFree] = useState(false);
  const [aiState, setAiState] = useState<'idle' | 'listening' | 'processing' | 'speaking'>('idle');
  const [aiResponse, setAiResponse] = useState("I'm listening...");
  const [permissionError, setPermissionError] = useState(false);

  // Refs
  const recognitionRef = useRef<any>(null);
  const synthesisRef = useRef<SpeechSynthesis>(window.speechSynthesis);
  const silenceTimerRef = useRef<any>(null);

  useEffect(() => {
    // Initialize Web Speech API
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false; // We handle the loop manually for better control
      recognitionRef.current.interimResults = true;
      recognitionRef.current.lang = 'en-US';

      recognitionRef.current.onstart = () => {
        setIsListening(true);
        if (isHandsFree) setAiState('listening');
      };

      recognitionRef.current.onresult = (event: any) => {
        const currentTranscript = Array.from(event.results)
          .map((result: any) => result[0].transcript)
          .join('');

        setTranscript(currentTranscript);
        if (!isHandsFree) setShowToast(true);

        // Debounce final processing
        if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = setTimeout(() => {
            if (event.results[0].isFinal || currentTranscript.length > 0) {
                if (isHandsFree) {
                    processHandsFreeCommand(currentTranscript);
                } else {
                    processSimpleCommand(currentTranscript);
                    setShowToast(false);
                }
            }
        }, 1500); // Wait 1.5s of silence before processing
      };

      recognitionRef.current.onerror = (event: any) => {
        // Handle specific errors
        if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
            setIsListening(false);
            setPermissionError(true);
            if (isHandsFree) {
                setIsHandsFree(false);
                setAiState('idle');
                    showNotification("Microphone permission denied. Please allow access in settings.", "error");
            }
            return;
        }

        if (event.error === 'no-speech') {
            // Just silence, not an error per se
            if (!isHandsFree) setIsListening(false);
            return;
        }

        console.debug("Speech recognition error", event.error);
        if (isHandsFree) {
             // Retry if hands-free is active and it wasn't a fatal error
             setTimeout(() => {
                 if (aiState !== 'speaking' && !permissionError) startListening();
             }, 1000);
        } else {
            setIsListening(false);
        }
      };

      recognitionRef.current.onend = () => {
        setIsListening(false);
        // In Hands-Free mode, we restart listening automatically unless we are processing or speaking
        if (isHandsFree && aiState === 'listening' && !permissionError) {
            setTimeout(() => startListening(), 500);
        }
      };
    }

    return () => {
        if (recognitionRef.current) recognitionRef.current.abort();
        if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
        synthesisRef.current.cancel();
    };
  }, [isHandsFree, aiState, permissionError]);

  const startListening = () => {
      if (permissionError) {
          showNotification("Microphone access is blocked.", "error");
          return;
      }
      try {
          recognitionRef.current?.start();
      } catch (e) {
          // Already started or error
      }
  };

  const stopListening = () => {
      try {
        recognitionRef.current?.stop();
      } catch (e) {
        // Ignore
      }
  };

  const toggleListen = () => {
    if (!recognitionRef.current) {
        showNotification("Voice control not supported in this browser.", "warning");
        return;
    }

    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  const toggleHandsFreeMode = () => {
      if (permissionError) {
          showNotification("Cannot enter Hands-Free mode without microphone access.", "error");
          return;
      }
      const newState = !isHandsFree;
      setIsHandsFree(newState);
      if (newState) {
          setAiState('listening');
          speak("Hands free mode active. I'm listening.");
      } else {
          stopListening();
          synthesisRef.current.cancel();
          setAiState('idle');
      }
  };

  // --- TTS ---
  const speak = (text: string) => {
      if (!text) return;

      stopListening();
      setAiState('speaking');
      setAiResponse(text);

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;

      utterance.onend = () => {
          if (isHandsFree) {
              setAiState('listening');
              setTranscript('');
              startListening();
          } else {
              setAiState('idle');
          }
      };

      synthesisRef.current.speak(utterance);
  };

  // --- Logic ---

  const processSimpleCommand = (cmd: string) => {
    const lowerCmd = cmd.toLowerCase();

    // Data Logging Commands -> Send to Chat Agent
    if (lowerCmd.startsWith('log') || lowerCmd.startsWith('record') || lowerCmd.startsWith('add') || lowerCmd.includes('blood pressure') || lowerCmd.includes('weight')) {
        navigate('/chat', { state: { autoSend: cmd } });
        return;
    }

    // Navigation Commands
    if (lowerCmd.includes('home') || lowerCmd.includes('dashboard')) navigate('/dashboard');
    else if (lowerCmd.includes('exercise') || lowerCmd.includes('workout')) navigate('/exercise');
    else if (lowerCmd.includes('diet') || lowerCmd.includes('food')) navigate('/nutrition');
    else if (lowerCmd.includes('assessment') || lowerCmd.includes('health')) navigate('/assessment');
    else if (lowerCmd.includes('medicine') || lowerCmd.includes('medication')) navigate('/medications');
    else if (lowerCmd.includes('chat')) navigate('/chat');
    else if (lowerCmd.includes('profile')) navigate('/profile');
  };

  const processHandsFreeCommand = async (cmd: string) => {
      if (!cmd.trim()) return;
      stopListening();
      setAiState('processing');

      // Local quick checks
      if (cmd.toLowerCase().includes('exit') || cmd.toLowerCase().includes('stop')) {
          toggleHandsFreeMode();
          return;
      }

      if (cmd.toLowerCase().includes('help') || cmd.toLowerCase().includes('emergency') || cmd.toLowerCase().includes('911')) {
          speak("I am displaying emergency options. Please tap the red button to call 911.");
          return;
      }

      try {
          // Use backend API for voice command processing
          const prompt = `You are a voice assistant for a cardiac patient. They are using "Hands-Free Mode" possibly because they feel weak.
User said: "${cmd}"

Determine the intent:
1. NAVIGATION: Go to a screen (dashboard, exercise, nutrition, assessment, medications, chat, profile).
2. LOG_DATA: User wants to log BP, weight, or food.
3. ADVICE: User feels unwell or asks a question.
4. UNKNOWN: Cannot determine.

Return JSON ONLY:
{
    "intent": "NAVIGATION" | "LOG_DATA" | "ADVICE" | "UNKNOWN",
    "action_value": "string (e.g., '/dashboard' or '120/80')",
    "speech_response": "string (Short, comforting, max 1 sentence)"
}`;

          const result = await apiClient.generateInsight({
              user_name: 'VoiceUser',
              vitals: {}
          });

          try {
              const parsed = JSON.parse(result.insight);

              if (parsed.intent === 'NAVIGATION') {
                  navigate(parsed.action_value);
              }
              else if (parsed.intent === 'LOG_DATA') {
                  navigate('/chat', { state: { autoSend: `Log this data: ${cmd}` } });
              }

              speak(parsed.speech_response || "Command processed.");
          } catch {
              speak("I didn't quite catch that. Can you repeat?");
          }

      } catch (error) {
          console.error("AI Error", error);
          speak("I'm having trouble connecting. Trying basic command.");
          processSimpleCommand(cmd);
      }
  };

  // Don't show on login/signup screens
  if (['/login', '/signup', '/'].includes(location.pathname)) return null;

  return (
    <>
        {/* Standard FAB */}
        <div className="fixed bottom-24 left-4 z-40 flex flex-col gap-2.5 no-print">
            {/* Hands Free Toggle */}
            <button
                onClick={toggleHandsFreeMode}
                className={`w-10 h-10 rounded-xl shadow-lg flex items-center justify-center transition-all duration-200 active:scale-90 border ${
                    isHandsFree
                        ? 'bg-blue-600 text-white border-blue-500/50 shadow-blue-900/30'
                        : 'bg-white dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-50 dark:hover:bg-slate-700 border-slate-200 dark:border-slate-700/50'
                }`}
                title="Enter Hands-Free Mode"
            >
                <span className="material-symbols-outlined text-lg">accessibility_new</span>
            </button>

            {/* Main Mic FAB */}
            <button
                onMouseDown={toggleListen}
                onClick={toggleListen}
                className={`w-12 h-12 rounded-xl shadow-xl flex items-center justify-center transition-all duration-300 border ${
                    isListening
                    ? 'bg-red-600 text-white scale-105 voice-orb-active border-red-500/50'
                    : 'bg-white dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-50 dark:hover:bg-slate-700 border-slate-200 dark:border-slate-700/50'
                }`}
                title="Voice Control"
            >
                <span className="material-symbols-outlined text-xl">{isListening ? 'mic' : 'mic_none'}</span>
            </button>
        </div>

        {/* Simple Toast */}
        {showToast && !isHandsFree && (
            <div className="fixed bottom-40 left-6 z-50 bg-white/95 dark:bg-[#131d28]/95 text-slate-900 dark:text-white px-4 py-3 rounded-xl text-sm backdrop-blur-md animate-scaleIn shadow-2xl shadow-black/10 dark:shadow-black/40 max-w-[220px] border border-slate-200 dark:border-slate-700/40">
                <div className="flex items-center gap-2.5">
                    <div className="flex items-center gap-0.5 h-4 flex-shrink-0">
                        {[...Array(3)].map((_, i) => (
                            <div key={i} className="w-0.5 bg-emerald-400 rounded-full waveform-bar" style={{ animationDelay: `${i * 0.12}s` }}></div>
                        ))}
                    </div>
                    <span className="truncate text-xs text-slate-700 dark:text-slate-200">"{transcript}"</span>
                </div>
            </div>
        )}

        {/* Full Screen Hands-Free Overlay */}
        {isHandsFree && (
            <div className="fixed inset-0 z-[100] bg-slate-50 dark:bg-[#0a1118] flex flex-col items-center justify-between p-6 animate-fadeIn">

                {/* Header */}
                <div className="w-full flex justify-between items-center">
                    <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center border border-slate-200 dark:border-slate-700/50">
                            <span className="material-symbols-outlined text-slate-500 dark:text-slate-400 text-lg">accessibility_new</span>
                        </div>
                        <div>
                            <span className="text-xs font-bold text-slate-900/70 dark:text-white/70 uppercase tracking-widest block">Hands-Free Mode</span>
                            <span className="text-[10px] text-slate-500">Voice-activated cardiac assistant</span>
                        </div>
                    </div>
                    <button
                        onClick={toggleHandsFreeMode}
                        className="px-4 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-xl text-slate-900 dark:text-white font-medium text-sm transition-all duration-200 border border-slate-200 dark:border-slate-700/50 active:scale-95"
                    >
                        Exit
                    </button>
                </div>

                {/* Central Visualizer */}
                <div className="flex flex-col items-center justify-center flex-1 w-full text-center">

                    {/* Status Text */}
                    <div className="mb-8">
                        <h2 className={`text-xl font-semibold mb-1 transition-colors duration-300 ${
                            aiState === 'listening' ? 'text-red-600 dark:text-red-400' :
                            aiState === 'processing' ? 'text-purple-600 dark:text-purple-400' : 'text-blue-600 dark:text-blue-400'
                        }`}>
                            {aiState === 'listening' ? "Listening..." : aiState === 'processing' ? "Processing..." : "Speaking..."}
                        </h2>
                        <p className="text-xs text-slate-500">
                            {aiState === 'listening' ? 'Speak clearly — I\'m ready' :
                             aiState === 'processing' ? 'Analyzing your request' : 'Please wait...'}
                        </p>
                    </div>

                    {/* Orb with waveform */}
                    <div className="relative mb-10">
                        {/* Glow background */}
                        <div className={`w-52 h-52 rounded-full blur-[60px] absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 transition-all duration-700 ${
                            aiState === 'listening' ? 'bg-red-600/15 dark:bg-red-600/25' :
                            aiState === 'processing' ? 'bg-purple-600/15 dark:bg-purple-600/25' : 'bg-blue-600/15 dark:bg-blue-600/25'
                        }`}></div>

                        {/* Main orb */}
                        <div className={`w-36 h-36 rounded-full border-2 flex flex-col items-center justify-center relative z-10 transition-all duration-500 bg-white/80 dark:bg-transparent ${
                            aiState === 'listening' ? 'border-red-500/60 shadow-[0_0_40px_rgba(239,68,68,0.2)] dark:shadow-[0_0_40px_rgba(239,68,68,0.3)] scale-110' :
                            aiState === 'processing' ? 'border-purple-500/60 shadow-[0_0_40px_rgba(168,85,247,0.2)] dark:shadow-[0_0_40px_rgba(168,85,247,0.3)]' :
                            'border-blue-500/60 shadow-[0_0_40px_rgba(59,130,246,0.2)] dark:shadow-[0_0_40px_rgba(59,130,246,0.3)]'
                        }`}>
                            <span className="material-symbols-outlined text-5xl text-slate-700 dark:text-white mb-1">
                                {aiState === 'listening' ? 'mic' : aiState === 'processing' ? 'smart_toy' : 'volume_up'}
                            </span>

                            {/* Waveform inside orb */}
                            {aiState === 'listening' && (
                                <div className="flex items-center gap-0.5 h-5">
                                    {[...Array(5)].map((_, i) => (
                                        <div key={i} className="w-0.5 bg-red-400 rounded-full waveform-bar" style={{ animationDelay: `${i * 0.1}s` }}></div>
                                    ))}
                                </div>
                            )}

                            {aiState === 'processing' && (
                                <div className="flex items-center gap-1 mt-1">
                                    <div className="w-1.5 h-1.5 bg-purple-400 rounded-full typing-dot"></div>
                                    <div className="w-1.5 h-1.5 bg-purple-400 rounded-full typing-dot"></div>
                                    <div className="w-1.5 h-1.5 bg-purple-400 rounded-full typing-dot"></div>
                                </div>
                            )}
                        </div>

                        {/* Pulse ring */}
                        {aiState === 'listening' && (
                            <div className="absolute inset-0 w-36 h-36 rounded-full border border-red-500/20 animate-ping z-0"></div>
                        )}
                    </div>

                    {/* Transcripts */}
                    <div className="space-y-4 max-w-md w-full">
                        <div className="min-h-[50px]">
                            <p className="text-2xl font-bold text-slate-900 dark:text-white leading-tight">
                                "{transcript || "..."}"
                            </p>
                        </div>

                        {aiResponse && (
                            <div className="glass-surface rounded-2xl p-5 border border-slate-200 dark:border-slate-700/40 shadow-lg">
                                <p className="text-lg text-blue-700 dark:text-blue-200 leading-relaxed">
                                    {aiResponse}
                                </p>
                            </div>
                        )}
                    </div>
                </div>

                {/* Footer Controls */}
                <div className="w-full flex flex-col gap-3">
                    <div className="grid grid-cols-2 gap-3">
                        <button
                            onClick={() => speak("I'm stopping.")}
                            className="py-5 bg-slate-100 dark:bg-slate-800 rounded-2xl text-slate-900 dark:text-white font-bold text-base flex items-center justify-center gap-2 hover:bg-slate-200 dark:hover:bg-slate-700 transition-all duration-200 border border-slate-200 dark:border-slate-700/50 active:scale-[0.98]"
                        >
                            <span className="material-symbols-outlined">stop_circle</span> Stop
                        </button>
                        <button
                            onClick={() => { setTranscript(''); startListening(); }}
                            className="py-5 bg-slate-100 dark:bg-slate-800 rounded-2xl text-slate-900 dark:text-white font-bold text-base flex items-center justify-center gap-2 hover:bg-slate-200 dark:hover:bg-slate-700 transition-all duration-200 border border-slate-200 dark:border-slate-700/50 active:scale-[0.98]"
                        >
                            <span className="material-symbols-outlined">refresh</span> Retry
                        </button>
                    </div>

                    <a
                        href="tel:911"
                        className="w-full py-5 bg-gradient-to-r from-red-600 to-red-700 rounded-2xl text-white font-black text-xl uppercase tracking-widest flex items-center justify-center gap-3 hover:from-red-700 hover:to-red-800 transition-all duration-200 shadow-xl shadow-red-900/40 active:scale-[0.98]"
                    >
                        <span className="material-symbols-outlined text-2xl animate-heartbeat">emergency</span>
                        Emergency SOS
                    </a>
                </div>

            </div>
        )}
    </>
  );
};

export default VoiceControl;
