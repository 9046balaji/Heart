
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { apiClient } from '../services/apiClient';

interface ChatMessage {
  id: string;
  role: 'user' | 'model';
  text: string;
  isStreaming?: boolean;
}

const COACH_SYSTEM_CONTEXT = `You are a friendly, motivational AI Fitness Coach inside a cardio health app. 
You help users with workout advice, recovery tips, form corrections, plan adjustments, and general fitness questions.
Keep answers concise (2-4 sentences unless detail is needed). Use encouraging language and emojis sparingly.
If the user shares symptoms of injury or pain, advise them to consult a medical professional.`;

const CoachScreen: React.FC = () => {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'model',
      text: "Hi! 👋 I'm your AI Fitness Coach. I can help with workout plans, recovery tips, form advice, and more.\n\nHow are you feeling today?"
    }
  ]);
  const [retryMessage, setRetryMessage] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading, scrollToBottom]);

  // Build conversation history for the API
  const buildConversationHistory = useCallback(() => {
    return messages
      .filter(m => m.id !== 'welcome') // skip the initial greeting
      .map(m => ({
        role: m.role === 'user' ? 'user' : 'assistant',
        content: m.text
      }));
  }, [messages]);

  const handleSend = async (textOverride?: string) => {
    const textToSend = textOverride || input;
    if (!textToSend.trim() || isLoading) return;

    const userMsg: ChatMessage = { id: `user_${Date.now()}`, role: 'user', text: textToSend };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setRetryMessage(null);
    setIsLoading(true);

    const assistantMsgId = `model_${Date.now()}`;

    try {
      // Get workout context from localStorage
      const history = JSON.parse(localStorage.getItem('workout_history') || '[]').slice(-3);
      const plan = JSON.parse(localStorage.getItem('user_exercise_plan') || '{}');

      const contextParts: string[] = [COACH_SYSTEM_CONTEXT];
      if (plan?.name) contextParts.push(`User's current plan: "${plan.name}" (${plan.days?.length || 0} days/week)`);
      if (history.length > 0) contextParts.push(`Recent workouts: ${history.map((h: any) => h.name || h.title || 'workout').join(', ')}`);

      const conversationHistory = buildConversationHistory();
      // Add system context as the first message
      const fullHistory = [
        { role: 'system', content: contextParts.join('\n') },
        ...conversationHistory,
        { role: 'user', content: textToSend }
      ];

      // Add empty streaming message
      setMessages(prev => [...prev, { id: assistantMsgId, role: 'model', text: '', isStreaming: true }]);

      let fullText = '';
      let gotResponse = false;

      for await (const chunk of apiClient.streamOllamaResponse({
        message: textToSend,
        conversation_history: fullHistory,
        temperature: 0.7
      })) {
        if (chunk.type === 'token') {
          gotResponse = true;
          fullText += chunk.data;
          setMessages(prev => prev.map(m => m.id === assistantMsgId ? { ...m, text: fullText } : m));
        } else if (chunk.type === 'done') {
          setMessages(prev => prev.map(m => m.id === assistantMsgId ? { ...m, isStreaming: false } : m));
        } else if (chunk.type === 'error') {
          throw new Error(chunk.data?.error || 'Stream error');
        }
      }

      // If no tokens received, mark as done with fallback
      if (!gotResponse) {
        setMessages(prev => prev.map(m => m.id === assistantMsgId
          ? { ...m, text: "I'm having trouble connecting right now. Please try again in a moment.", isStreaming: false }
          : m
        ));
      } else {
        // Mark streaming done
        setMessages(prev => prev.map(m => m.id === assistantMsgId ? { ...m, isStreaming: false } : m));
      }

    } catch (error) {
      console.error('Coach error:', error);
      const errorText = error instanceof Error && error.message.includes('offline')
        ? "You appear to be offline. Please check your connection and try again."
        : "I'm having trouble connecting. Please try again.";

      // Remove empty streaming msg if present, add error
      setMessages(prev => {
        const filtered = prev.filter(m => m.id !== assistantMsgId || m.text.length > 0);
        if (filtered.find(m => m.id === assistantMsgId)) {
          return filtered.map(m => m.id === assistantMsgId ? { ...m, isStreaming: false } : m);
        }
        return [...filtered, { id: assistantMsgId, role: 'model', text: errorText, isStreaming: false }];
      });
      setRetryMessage(textToSend);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRetry = () => {
    if (retryMessage) {
      // Remove the last error message
      setMessages(prev => prev.slice(0, -1));
      handleSend(retryMessage);
    }
  };

  const handleClear = () => {
    setMessages([{
      id: 'welcome',
      role: 'model',
      text: "Hi! 👋 I'm your AI Fitness Coach. I can help with workout plans, recovery tips, form advice, and more.\n\nHow are you feeling today?"
    }]);
    setRetryMessage(null);
  };

  const suggestions = [
    { icon: 'sentiment_dissatisfied', text: "I'm feeling sore today" },
    { icon: 'timer', text: "Suggest a 20min HIIT" },
    { icon: 'trending_up', text: "How's my consistency?" },
    { icon: 'healing', text: "Modify plan for bad knees" },
    { icon: 'restaurant', text: "Post-workout nutrition tips" },
    { icon: 'hotel', text: "How much rest between sets?" }
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] animate-in fade-in slide-in-from-bottom-4 duration-300">
      {/* Coach Header */}
      <div className="px-4 pt-3 pb-2 flex items-center justify-between border-b border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-green-400 to-emerald-600 flex items-center justify-center shadow-lg shadow-green-500/20">
            <span className="material-symbols-outlined text-white text-lg">smart_toy</span>
          </div>
          <div>
            <h3 className="font-bold text-sm dark:text-white leading-tight">AI Fitness Coach</h3>
            <div className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
              <span className="text-[10px] text-green-600 dark:text-green-400 font-medium">Online</span>
            </div>
          </div>
        </div>
        {messages.length > 1 && (
          <button
            onClick={handleClear}
            className="text-xs text-slate-400 hover:text-red-500 flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
          >
            <span className="material-symbols-outlined text-sm">delete_sweep</span>
            Clear
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-200`}>
            {msg.role === 'model' && (
              <div className="w-7 h-7 rounded-full bg-gradient-to-br from-green-400 to-emerald-600 flex items-center justify-center mr-2 mt-1 flex-shrink-0">
                <span className="material-symbols-outlined text-white text-xs">smart_toy</span>
              </div>
            )}
            <div className={`max-w-[80%] p-4 rounded-2xl text-sm leading-relaxed shadow-sm ${
              msg.role === 'user'
                ? 'bg-primary text-white rounded-br-sm'
                : 'bg-white dark:bg-card-dark text-slate-700 dark:text-slate-200 rounded-bl-sm border border-slate-100 dark:border-slate-800'
            }`}>
              {/* Render text with basic markdown-like formatting */}
              {msg.text.split('\n').map((line, i) => (
                <p key={i} className={`${i > 0 ? 'mt-2' : ''} ${!line.trim() ? 'h-2' : ''}`}>
                  {line.startsWith('- ') ? (
                    <span className="flex items-start gap-2">
                      <span className="text-primary mt-0.5">•</span>
                      <span>{line.slice(2)}</span>
                    </span>
                  ) : (
                    line
                  )}
                </p>
              ))}
              {msg.isStreaming && (
                <span className="inline-block w-1.5 h-4 bg-primary/60 animate-pulse ml-0.5 rounded-sm align-text-bottom"></span>
              )}
            </div>
          </div>
        ))}

        {isLoading && !messages.some(m => m.isStreaming) && (
          <div className="flex justify-start">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-green-400 to-emerald-600 flex items-center justify-center mr-2 flex-shrink-0">
              <span className="material-symbols-outlined text-white text-xs">smart_toy</span>
            </div>
            <div className="bg-white dark:bg-card-dark p-4 rounded-2xl rounded-bl-sm border border-slate-100 dark:border-slate-800 flex gap-1.5">
              <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></span>
              <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce [animation-delay:0.15s]"></span>
              <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce [animation-delay:0.3s]"></span>
            </div>
          </div>
        )}

        {/* Retry Button */}
        {retryMessage && !isLoading && (
          <div className="flex justify-center">
            <button
              onClick={handleRetry}
              className="flex items-center gap-2 px-4 py-2 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-full text-xs font-bold hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors"
            >
              <span className="material-symbols-outlined text-sm">refresh</span>
              Tap to retry
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-t border-slate-200 dark:border-slate-800">
        {/* Suggestions - only show early in conversation */}
        {messages.length < 3 && (
          <div className="flex gap-2 overflow-x-auto no-scrollbar mb-3 -mx-1 px-1">
            {suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => handleSend(s.text)}
                className="whitespace-nowrap px-3 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-xs font-bold text-slate-600 dark:text-slate-300 hover:border-primary hover:text-primary transition-colors flex items-center gap-1.5 shadow-sm"
              >
                <span className="material-symbols-outlined text-sm text-primary">{s.icon}</span>
                {s.text}
              </button>
            ))}
          </div>
        )}

        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask your coach anything..."
            disabled={isLoading}
            className="flex-1 bg-slate-100 dark:bg-card-dark border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-primary/50 outline-none dark:text-white shadow-sm disabled:opacity-60 transition-all"
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || isLoading}
            className="w-12 h-12 bg-primary text-white rounded-xl flex items-center justify-center shadow-lg shadow-primary/20 disabled:opacity-40 hover:bg-primary/90 active:scale-95 transition-all"
          >
            <span className="material-symbols-outlined">send</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default CoachScreen;
