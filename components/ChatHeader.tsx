import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProvider } from '../contexts/ProviderContext';

interface ChatHeaderProps {
    onMenuClick: () => void;
    selectedModel: string;
    onModelSelect: (model: string) => void;
    isSearchingMemories: boolean;
}

export const ChatHeader: React.FC<ChatHeaderProps> = ({
    onMenuClick,
    selectedModel,
    onModelSelect,
    isSearchingMemories
}) => {
    const navigate = useNavigate();
    const { selectedProvider, setSelectedProvider, providerStatus, availableProviders } = useProvider();
    const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    // Close dropdown on outside click
    useEffect(() => {
        if (!isModelDropdownOpen) return;
        const handler = (e: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
                setIsModelDropdownOpen(false);
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, [isModelDropdownOpen]);

    return (
        <div className="flex items-center justify-between px-3 py-2.5 z-10 glass-surface border-b border-slate-200/60 dark:border-slate-800/40">
            <div className="flex items-center gap-1">
                <button
                    onClick={() => navigate(-1)}
                    className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800/70 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-all duration-200 active:scale-95"
                >
                    <span className="material-symbols-outlined text-xl">arrow_back</span>
                </button>
                <button onClick={onMenuClick} className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800/70 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-all duration-200 active:scale-95">
                    <span className="material-symbols-outlined text-xl">menu</span>
                </button>
            </div>

            <div className="flex flex-col items-center">
                <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-red-500 to-red-700 flex items-center justify-center shadow-md shadow-red-900/30">
                        <span className="material-symbols-outlined text-white text-sm">cardiology</span>
                    </div>
                    <h1 className="font-bold text-base text-slate-900 dark:text-white tracking-tight">Cardio AI Agent</h1>
                </div>

                {/* Model Selector Dropdown */}
                <div className="relative mt-1" ref={dropdownRef}>
                    <button
                        onClick={() => setIsModelDropdownOpen(!isModelDropdownOpen)}
                        className="flex items-center gap-1.5 px-2.5 py-1 text-xs bg-slate-100 dark:bg-slate-800/70 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg transition-all duration-200 border border-slate-200 dark:border-slate-700/50"
                    >
                        <span className="material-symbols-outlined text-sm">
                            {selectedProvider === 'ollama' ? 'memory' : 'cloud'}
                        </span>
                        <span className="font-medium">
                            {selectedProvider === 'ollama' ? 'Ollama (Local)' : 'OpenRouter (Cloud)'}
                        </span>
                        <span className={`material-symbols-outlined text-sm transition-transform duration-200 ${isModelDropdownOpen ? 'rotate-180' : ''}`}>
                            expand_more
                        </span>
                    </button>

                    {/* Dropdown Menu */}
                    {isModelDropdownOpen && (
                        <div className="absolute top-full mt-1.5 left-1/2 -translate-x-1/2 bg-white dark:bg-[#131d28] border border-slate-200 dark:border-slate-700/60 rounded-xl shadow-2xl shadow-black/10 dark:shadow-black/40 z-50 min-w-60 overflow-hidden animate-slideDown">
                            {availableProviders.map((provider, index) => (
                                <button
                                    key={provider.name}
                                    onClick={async () => {
                                        await setSelectedProvider(provider.name as 'ollama' | 'openrouter');
                                        setIsModelDropdownOpen(false);
                                    }}
                                    disabled={!provider.available}
                                    className={`w-full flex items-center gap-3 px-4 py-3 text-left text-sm transition-all duration-150 ${selectedProvider === provider.name
                                            ? 'bg-red-50 dark:bg-red-900/20 text-slate-900 dark:text-white'
                                            : 'text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/70'
                                        } ${!provider.available ? 'opacity-40 cursor-not-allowed' : ''} ${index > 0 ? 'border-t border-slate-100 dark:border-slate-800/50' : ''
                                        }`}
                                >
                                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                                        selectedProvider === provider.name ? 'bg-red-100 dark:bg-red-900/30' : 'bg-slate-100 dark:bg-slate-800/50'
                                    }`}>
                                        <span className="material-symbols-outlined text-base">
                                            {provider.name === 'ollama' ? 'memory' : 'cloud'}
                                        </span>
                                    </div>
                                    <div className="flex-1">
                                        <div className="font-medium text-sm">{provider.label}</div>
                                        <div className="text-[11px] text-slate-500 leading-tight">{provider.description}</div>
                                    </div>
                                    {selectedProvider === provider.name && (
                                        <span className="material-symbols-outlined text-sm text-red-400">check_circle</span>
                                    )}
                                    {!provider.available && (
                                        <span className="text-[10px] text-amber-400 bg-amber-900/20 px-1.5 py-0.5 rounded">N/A</span>
                                    )}
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                {/* Status indicator */}
                <div className="flex items-center gap-2 mt-1">
                    {isSearchingMemories ? (
                        <span className="text-[10px] text-blue-400 flex items-center gap-1 font-medium">
                            <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse"></span>
                            Searching memories...
                        </span>
                    ) : (
                        <span className="text-[10px] text-emerald-400 flex items-center gap-1 font-medium">
                            <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-gentle-pulse"></span>
                            Online
                        </span>
                    )}
                </div>
            </div>

            <div className="flex items-center gap-1">
                <button
                    onClick={() => navigate('/agent-settings')}
                    className="p-2 rounded-xl text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800/70 transition-all duration-200 active:scale-95"
                    title="Agent Settings"
                >
                    <span className="material-symbols-outlined text-xl">settings</span>
                </button>
                <button onClick={() => navigate('/profile')} className="w-9 h-9 rounded-xl bg-slate-200 dark:bg-slate-700 overflow-hidden border border-slate-300/50 dark:border-slate-600/50 shadow-sm hover:ring-2 hover:ring-red-500/30 transition-all duration-200">
                    <img src="https://randomuser.me/api/portraits/women/44.jpg" alt="Profile" className="w-full h-full object-cover" />
                </button>
            </div>
        </div>
    );
};
