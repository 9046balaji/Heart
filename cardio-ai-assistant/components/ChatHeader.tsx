import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

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
    const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false);

    return (
        <div className="flex items-center justify-between p-4 z-10 bg-[#101922] border-b border-slate-800/50">
            <button onClick={onMenuClick} className="p-2 -ml-2 text-slate-300 hover:text-white transition-colors">
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
                                    onModelSelect('gemini');
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
                                    onModelSelect('ollama');
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

            <div className="flex items-center gap-2">
                <button
                    onClick={() => navigate('/agent-settings')}
                    className="p-2 text-slate-400 hover:text-white transition-colors"
                    title="Agent Settings"
                >
                    <span className="material-symbols-outlined">settings</span>
                </button>
                <button onClick={() => navigate('/profile')} className="w-9 h-9 rounded-full bg-slate-700 overflow-hidden border border-slate-600">
                    <img src="https://randomuser.me/api/portraits/women/44.jpg" alt="Profile" className="w-full h-full object-cover" />
                </button>
            </div>
        </div>
    );
};
