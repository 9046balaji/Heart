
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
        <div className="fixed bottom-24 left-4 z-40 flex flex-col gap-3 no-print">
            {/* Hands Free Toggle (Mini) */}
            <button
                onClick={toggleHandsFreeMode}
                className="w-10 h-10 rounded-full bg-slate-700 text-white shadow-lg flex items-center justify-center hover:bg-slate-600 transition-colors"
                title="Enter Hands-Free Mode"
            >
                <span className="material-symbols-outlined text-lg">accessibility_new</span>
            </button>

            {/* Main Mic FAB */}
            <button
                onMouseDown={toggleListen} // Desktop hold
                onClick={toggleListen} // Mobile tap toggle
                className={`w-14 h-14 rounded-full shadow-xl flex items-center justify-center transition-all duration-300 border-2 border-slate-700/50 ${
                    isListening
                    ? 'bg-red-600 text-white scale-110 animate-pulse ring-4 ring-red-500/30'
                    : 'bg-slate-800 text-white hover:bg-slate-700'
                }`}
                title="Voice Control"
            >
                <span className="material-symbols-outlined text-2xl">{isListening ? 'mic' : 'mic_none'}</span>
            </button>
        </div>

        {/* Simple Toast */}
        {showToast && !isHandsFree && (
            <div className="fixed bottom-40 left-6 z-50 bg-black/80 text-white px-4 py-3 rounded-xl text-sm backdrop-blur-md animate-in slide-in-from-left fade-in duration-300 flex items-center gap-3 shadow-2xl max-w-[200px]">
                <span className="material-symbols-outlined text-sm text-green-400">graphic_eq</span>
                <span className="truncate">"{transcript}"</span>
            </div>
        )}

        {/* Full Screen Hands-Free Overlay */}
        {isHandsFree && (
            <div className="fixed inset-0 z-[100] bg-slate-950 flex flex-col items-center justify-between p-8 animate-in fade-in duration-300">

                {/* Header */}
                <div className="w-full flex justify-between items-center">
                    <div className="flex items-center gap-2 text-white/50">
                        <span className="material-symbols-outlined">accessibility_new</span>
                        <span className="text-sm font-bold uppercase tracking-widest">Hands-Free Mode</span>
                    </div>
                    <button
                        onClick={toggleHandsFreeMode}
                        className="px-4 py-2 bg-white/10 hover:bg-white/20 rounded-full text-white font-bold text-sm transition-colors"
                    >
                        Exit
                    </button>
                </div>

                {/* Central Visualizer */}
                <div className="flex flex-col items-center justify-center flex-1 w-full text-center">

                    {/* Status Text */}
                    <h2 className="text-2xl font-medium text-slate-400 mb-8 h-8">
                        {aiState === 'listening' ? "Listening..." : aiState === 'processing' ? "Thinking..." : "Speaking..."}
                    </h2>

                    {/* Orb */}
                    <div className="relative mb-12">
                        <div className={`w-48 h-48 rounded-full blur-3xl absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 transition-colors duration-500 ${
                            aiState === 'listening' ? 'bg-red-600/40' :
                            aiState === 'processing' ? 'bg-purple-600/40' : 'bg-blue-600/40'
                        }`}></div>
                        <div className={`w-32 h-32 rounded-full border-4 flex items-center justify-center relative z-10 transition-all duration-300 ${
                            aiState === 'listening' ? 'border-red-500 shadow-[0_0_50px_rgba(239,68,68,0.5)] scale-110' :
                            aiState === 'processing' ? 'border-purple-500 animate-pulse' : 'border-blue-500'
                        }`}>
                            <span className="material-symbols-outlined text-6xl text-white">
                                {aiState === 'listening' ? 'mic' : aiState === 'processing' ? 'smart_toy' : 'volume_up'}
                            </span>
                        </div>
                    </div>

                    {/* Transcripts */}
                    <div className="space-y-6 max-w-lg w-full">
                        <div className="min-h-[60px]">
                            <p className="text-3xl font-bold text-white leading-tight">
                                "{transcript || "..."}"
                            </p>
                        </div>

                        {aiResponse && (
                            <div className="bg-white/10 rounded-2xl p-6 border border-white/10">
                                <p className="text-xl text-blue-200">
                                    {aiResponse}
                                </p>
                            </div>
                        )}
                    </div>
                </div>

                {/* Footer Controls */}
                <div className="w-full flex flex-col gap-4">
                    <div className="grid grid-cols-2 gap-4">
                        <button
                            onClick={() => speak("I'm stopping.")}
                            className="py-6 bg-slate-800 rounded-2xl text-white font-bold text-lg flex items-center justify-center gap-2 hover:bg-slate-700 transition-colors"
                        >
                            <span className="material-symbols-outlined">stop_circle</span> Stop
                        </button>
                        <button
                            onClick={() => { setTranscript(''); startListening(); }}
                            className="py-6 bg-slate-800 rounded-2xl text-white font-bold text-lg flex items-center justify-center gap-2 hover:bg-slate-700 transition-colors"
                        >
                            <span className="material-symbols-outlined">refresh</span> Retry
                        </button>
                    </div>

                    <a
                        href="tel:911"
                        className="w-full py-6 bg-red-600 rounded-2xl text-white font-black text-2xl uppercase tracking-widest flex items-center justify-center gap-3 hover:bg-red-700 transition-colors shadow-lg shadow-red-900/50"
                    >
                        <span className="material-symbols-outlined text-3xl">emergency</span>
                        Emergency SOS
                    </a>
                </div>

            </div>
        )}
    </>
  );
};

export default VoiceControl;
