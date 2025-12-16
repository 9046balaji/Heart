
import React, { useState, useEffect, useRef } from 'react';
import { apiClient } from '../services/apiClient';

interface ChatMessage {
  id: string;
  role: 'user' | 'model';
  text: string;
}

const CoachScreen: React.FC = () => {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'model',
      text: "Hi! I'm your AI Fitness Coach. How are you feeling today? Need a workout adjustment or recovery tips?"
    }
  ]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = async (textOverride?: string) => {
    const textToSend = textOverride || input;
    if (!textToSend.trim()) return;

    const userMsg: ChatMessage = { id: Date.now().toString(), role: 'user', text: textToSend };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
        // Context from LocalStorage
        const history = JSON.parse(localStorage.getItem('workout_history') || '[]').slice(-5);
        const plan = JSON.parse(localStorage.getItem('user_exercise_plan') || '{}');
        
        const result = await apiClient.generateInsight({
            user_name: 'User',
            vitals: {},
            activities: history
        });
        
        const reply = result.insight || "I'm focusing on my breathing... try again in a moment.";
        setMessages(prev => [...prev, { id: Date.now().toString(), role: 'model', text: reply }]);

    } catch (error) {
        console.error(error);
        setMessages(prev => [...prev, { id: Date.now().toString(), role: 'model', text: "Connection error. Please try again." }]);
    } finally {
        setIsLoading(false);
    }
  };

  const suggestions = [
      "I'm feeling sore today",
      "Suggest a 20min HIIT",
      "How's my consistency?",
      "Modify my plan for knees"
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] animate-in fade-in slide-in-from-bottom-4 duration-300">
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((msg) => (
                <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] p-4 rounded-2xl text-sm leading-relaxed shadow-sm ${
                        msg.role === 'user' 
                        ? 'bg-primary text-white rounded-br-none' 
                        : 'bg-white dark:bg-card-dark text-slate-700 dark:text-slate-200 rounded-bl-none border border-slate-100 dark:border-slate-800'
                    }`}>
                        {msg.text}
                    </div>
                </div>
            ))}
            {isLoading && (
                <div className="flex justify-start">
                    <div className="bg-white dark:bg-card-dark p-4 rounded-2xl rounded-bl-none border border-slate-100 dark:border-slate-800 flex gap-1">
                        <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></span>
                        <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce [animation-delay:0.2s]"></span>
                        <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce [animation-delay:0.4s]"></span>
                    </div>
                </div>
            )}
            <div ref={messagesEndRef} />
        </div>

        <div className="p-4 bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm border-t border-slate-200 dark:border-slate-800">
            {messages.length < 3 && (
                <div className="flex gap-2 overflow-x-auto no-scrollbar mb-3">
                    {suggestions.map((s, i) => (
                        <button 
                            key={i} 
                            onClick={() => handleSend(s)}
                            className="whitespace-nowrap px-3 py-1.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-full text-xs font-bold text-slate-600 dark:text-slate-300 hover:border-primary hover:text-primary transition-colors"
                        >
                            {s}
                        </button>
                    ))}
                </div>
            )}
            
            <div className="flex gap-2 relative">
                <input 
                    type="text" 
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                    placeholder="Ask your coach..." 
                    className="flex-1 bg-white dark:bg-card-dark border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-primary outline-none dark:text-white shadow-sm"
                />
                <button 
                    onClick={() => handleSend()}
                    disabled={!input.trim() || isLoading}
                    className="w-12 h-12 bg-primary text-white rounded-xl flex items-center justify-center shadow-lg shadow-primary/20 disabled:opacity-50 hover:bg-primary-dark transition-colors"
                >
                    <span className="material-symbols-outlined">send</span>
                </button>
            </div>
        </div>
    </div>
  );
};

export default CoachScreen;
