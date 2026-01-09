import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLanguage } from '../contexts/LanguageContext';

interface AgentSettings {
    model: 'gemini-pro' | 'gpt-4' | 'claude-3';
    persona: 'medical' | 'friendly' | 'concise';
    responseLength: 'short' | 'medium' | 'long';
    voice: 'male' | 'female';
    temperature: number;
}

const AgentSettingsScreen: React.FC = () => {
    const navigate = useNavigate();
    const { t } = useLanguage();

    const [settings, setSettings] = useState<AgentSettings>(() => {
        const saved = localStorage.getItem('agent_settings');
        return saved ? JSON.parse(saved) : {
            model: 'gemini-pro',
            persona: 'medical',
            responseLength: 'medium',
            voice: 'female',
            temperature: 0.7
        };
    });

    const [saved, setSaved] = useState(false);

    useEffect(() => {
        localStorage.setItem('agent_settings', JSON.stringify(settings));
    }, [settings]);

    const handleSave = () => {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
    };

    return (
        <div className="min-h-screen bg-background-light dark:bg-background-dark pb-24">
            {/* Header */}
            <div className="flex items-center p-4 bg-white dark:bg-card-dark sticky top-0 z-10 border-b border-slate-100 dark:border-slate-800 shadow-sm">
                <button
                    onClick={() => navigate(-1)}
                    className="p-2 -ml-2 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-900 dark:text-white transition-colors"
                >
                    <span className="material-symbols-outlined">arrow_back</span>
                </button>
                <h2 className="flex-1 text-center font-bold text-lg dark:text-white">Agent Settings</h2>
                <div className="w-10"></div>
            </div>

            <div className="p-4 space-y-6">
                {/* Model Selection */}
                <div>
                    <h3 className="text-sm font-bold text-slate-500 uppercase mb-3">AI Model</h3>
                    <div className="bg-white dark:bg-card-dark rounded-2xl p-4 shadow-sm space-y-3">
                        {[
                            { id: 'gemini-pro', name: 'Gemini Pro', desc: 'Fast & capable (Recommended)' },
                            { id: 'gpt-4', name: 'GPT-4', desc: 'Most accurate, slower' },
                            { id: 'claude-3', name: 'Claude 3', desc: 'Natural conversation' }
                        ].map(model => (
                            <label key={model.id} className="flex items-center justify-between p-3 rounded-xl border border-slate-100 dark:border-slate-700 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                                <div className="flex items-center gap-3">
                                    <div className={`w-10 h-10 rounded-full flex items-center justify-center ${settings.model === model.id ? 'bg-primary/10 text-primary' : 'bg-slate-100 dark:bg-slate-800 text-slate-400'}`}>
                                        <span className="material-symbols-outlined">smart_toy</span>
                                    </div>
                                    <div>
                                        <p className="font-medium dark:text-white">{model.name}</p>
                                        <p className="text-xs text-slate-500">{model.desc}</p>
                                    </div>
                                </div>
                                <input
                                    type="radio"
                                    name="model"
                                    checked={settings.model === model.id}
                                    onChange={() => setSettings(prev => ({ ...prev, model: model.id as any }))}
                                    className="w-5 h-5 text-primary focus:ring-primary border-gray-300"
                                />
                            </label>
                        ))}
                    </div>
                </div>

                {/* Persona */}
                <div>
                    <h3 className="text-sm font-bold text-slate-500 uppercase mb-3">Persona</h3>
                    <div className="bg-white dark:bg-card-dark rounded-2xl p-4 shadow-sm">
                        <div className="grid grid-cols-3 gap-3">
                            {[
                                { id: 'medical', icon: 'stethoscope', label: 'Medical' },
                                { id: 'friendly', icon: 'sentiment_satisfied', label: 'Friendly' },
                                { id: 'concise', icon: 'bolt', label: 'Concise' }
                            ].map(persona => (
                                <button
                                    key={persona.id}
                                    onClick={() => setSettings(prev => ({ ...prev, persona: persona.id as any }))}
                                    className={`flex flex-col items-center justify-center p-3 rounded-xl border transition-all ${settings.persona === persona.id
                                            ? 'border-primary bg-primary/5 text-primary'
                                            : 'border-slate-100 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/50 text-slate-500'
                                        }`}
                                >
                                    <span className="material-symbols-outlined mb-1">{persona.icon}</span>
                                    <span className="text-xs font-medium">{persona.label}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Response Settings */}
                <div>
                    <h3 className="text-sm font-bold text-slate-500 uppercase mb-3">Response Settings</h3>
                    <div className="bg-white dark:bg-card-dark rounded-2xl p-4 shadow-sm space-y-6">
                        {/* Length */}
                        <div>
                            <div className="flex justify-between mb-2">
                                <label className="text-sm font-medium dark:text-white">Response Length</label>
                                <span className="text-xs text-slate-500 capitalize">{settings.responseLength}</span>
                            </div>
                            <input
                                type="range"
                                min="0"
                                max="2"
                                step="1"
                                value={settings.responseLength === 'short' ? 0 : settings.responseLength === 'medium' ? 1 : 2}
                                onChange={(e) => {
                                    const val = parseInt(e.target.value);
                                    setSettings(prev => ({
                                        ...prev,
                                        responseLength: val === 0 ? 'short' : val === 1 ? 'medium' : 'long'
                                    }));
                                }}
                                className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-primary"
                            />
                            <div className="flex justify-between mt-1 text-xs text-slate-400">
                                <span>Short</span>
                                <span>Medium</span>
                                <span>Long</span>
                            </div>
                        </div>

                        {/* Temperature */}
                        <div>
                            <div className="flex justify-between mb-2">
                                <label className="text-sm font-medium dark:text-white">Creativity (Temperature)</label>
                                <span className="text-xs text-slate-500">{settings.temperature}</span>
                            </div>
                            <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.1"
                                value={settings.temperature}
                                onChange={(e) => setSettings(prev => ({ ...prev, temperature: parseFloat(e.target.value) }))}
                                className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-primary"
                            />
                            <div className="flex justify-between mt-1 text-xs text-slate-400">
                                <span>Precise</span>
                                <span>Balanced</span>
                                <span>Creative</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Voice Settings */}
                <div>
                    <h3 className="text-sm font-bold text-slate-500 uppercase mb-3">Voice Output</h3>
                    <div className="bg-white dark:bg-card-dark rounded-2xl p-4 shadow-sm">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center text-purple-600">
                                    <span className="material-symbols-outlined">record_voice_over</span>
                                </div>
                                <div>
                                    <p className="font-medium dark:text-white">Voice Preference</p>
                                    <p className="text-xs text-slate-500">For text-to-speech</p>
                                </div>
                            </div>
                            <div className="flex bg-slate-100 dark:bg-slate-800 rounded-lg p-1">
                                <button
                                    onClick={() => setSettings(prev => ({ ...prev, voice: 'male' }))}
                                    className={`px-3 py-1 rounded-md text-sm font-medium transition-all ${settings.voice === 'male'
                                            ? 'bg-white dark:bg-slate-700 shadow-sm text-slate-900 dark:text-white'
                                            : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                                        }`}
                                >
                                    Male
                                </button>
                                <button
                                    onClick={() => setSettings(prev => ({ ...prev, voice: 'female' }))}
                                    className={`px-3 py-1 rounded-md text-sm font-medium transition-all ${settings.voice === 'female'
                                            ? 'bg-white dark:bg-slate-700 shadow-sm text-slate-900 dark:text-white'
                                            : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                                        }`}
                                >
                                    Female
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <button
                    onClick={handleSave}
                    className="w-full py-4 bg-primary text-white font-bold rounded-xl shadow-lg shadow-primary/30 flex items-center justify-center gap-2 hover:bg-primary-dark transition-colors"
                >
                    {saved ? (
                        <>
                            <span className="material-symbols-outlined">check</span>
                            Settings Saved
                        </>
                    ) : (
                        'Save Configuration'
                    )}
                </button>
            </div>
        </div>
    );
};

export default AgentSettingsScreen;
