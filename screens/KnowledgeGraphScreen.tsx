import React, { useState } from 'react';
import { apiClient } from '../services/apiClient';
import { useToast } from '../components/Toast';
import ScreenHeader from '../components/ScreenHeader';

export default function KnowledgeGraphScreen() {
    const { showToast } = useToast();
    const [query, setQuery] = useState('');
    const [loading, setLoading] = useState(false);
    const [results, setResults] = useState<any>(null);
    const [mode, setMode] = useState<'search' | 'rag'>('search');
    const [ragAnswer, setRagAnswer] = useState<any>(null);

    const handleSearch = async () => {
        if (!query.trim()) return;
        setLoading(true);
        try {
            if (mode === 'search') {
                const response = await apiClient.searchGraph(query);
                setResults(response);
                setRagAnswer(null);
            } else {
                const response = await apiClient.ragQuery(query);
                setRagAnswer(response);
                setResults(null);
            }
        } catch (error) {
            console.error('Search error:', error);
            showToast(`Failed to ${mode === 'search' ? 'search' : 'query'} knowledge graph`, 'error');
        } finally {
            setLoading(false);
        }
    };

    const getNodeColor = (label: string) => {
        switch (label.toLowerCase()) {
            case 'condition': return { bg: 'bg-pink-500', iconBg: 'bg-pink-100 dark:bg-pink-900/30', text: 'text-pink-600 dark:text-pink-400' };
            case 'symptom': return { bg: 'bg-orange-500', iconBg: 'bg-orange-100 dark:bg-orange-900/30', text: 'text-orange-600 dark:text-orange-400' };
            case 'medication': return { bg: 'bg-blue-500', iconBg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-600 dark:text-blue-400' };
            case 'treatment': return { bg: 'bg-emerald-500', iconBg: 'bg-emerald-100 dark:bg-emerald-900/30', text: 'text-emerald-600 dark:text-emerald-400' };
            default: return { bg: 'bg-purple-500', iconBg: 'bg-purple-100 dark:bg-purple-900/30', text: 'text-purple-600 dark:text-purple-400' };
        }
    };

    return (
        <div className="min-h-screen bg-slate-50 dark:bg-background-dark pb-24 font-sans overflow-x-hidden">
            <ScreenHeader title="Knowledge Graph" subtitle="Medical Knowledge Search" />

            {/* Search Section */}
            <div className="p-4 bg-white dark:bg-card-dark border-b border-slate-100 dark:border-slate-800 space-y-3">
                <div className="flex items-center gap-2 bg-slate-100 dark:bg-slate-800 rounded-xl px-4 h-11">
                    <span className="material-symbols-outlined text-lg text-slate-400">search</span>
                    <input
                        type="text"
                        placeholder="Search medical knowledge..."
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                        className="flex-1 bg-transparent border-none outline-none text-sm text-slate-800 dark:text-white placeholder-slate-400"
                    />
                    {query.length > 0 && (
                        <button onClick={() => setQuery('')} className="text-slate-300 hover:text-slate-500 transition-colors">
                            <span className="material-symbols-outlined text-lg">cancel</span>
                        </button>
                    )}
                    <button
                        onClick={handleSearch}
                        disabled={!query.trim() || loading}
                        className="w-9 h-9 bg-indigo-600 text-white rounded-lg flex items-center justify-center -mr-1 disabled:opacity-50 hover:bg-indigo-700 transition-colors"
                    >
                        <span className="material-symbols-outlined text-lg">arrow_forward</span>
                    </button>
                </div>

                {/* Mode Toggle */}
                <div className="flex bg-slate-100 dark:bg-slate-800 rounded-lg p-0.5">
                    <button
                        onClick={() => setMode('search')}
                        className={`flex-1 py-2 rounded-md text-sm font-semibold transition-colors ${
                            mode === 'search' ? 'bg-indigo-600 text-white shadow' : 'text-slate-500 dark:text-slate-400'
                        }`}
                    >
                        Search
                    </button>
                    <button
                        onClick={() => setMode('rag')}
                        className={`flex-1 py-2 rounded-md text-sm font-semibold transition-colors ${
                            mode === 'rag' ? 'bg-indigo-600 text-white shadow' : 'text-slate-500 dark:text-slate-400'
                        }`}
                    >
                        RAG Query
                    </button>
                </div>
            </div>

            <div className="p-4">
                {loading ? (
                    <div className="flex justify-center py-16">
                        <div className="w-8 h-8 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
                    </div>
                ) : results ? (
                    <div className="space-y-4">
                        <p className="text-sm text-slate-500 dark:text-slate-400">
                            Found {results.nodes.length} nodes and {results.relationships.length} relationships
                        </p>

                        <h2 className="text-lg font-bold text-slate-800 dark:text-white">Nodes</h2>
                        <div className="space-y-2.5">
                            {results.nodes.map((node: any, index: number) => {
                                const colors = getNodeColor(node.label);
                                return (
                                    <div key={index} className="flex gap-3 bg-white dark:bg-card-dark rounded-xl p-4 shadow-sm border border-slate-100 dark:border-slate-800">
                                        <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${colors.bg}`}>
                                            <span className="text-white text-lg font-bold">{node.label[0]}</span>
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <h4 className="text-sm font-semibold text-slate-800 dark:text-white">{node.properties.name || node.id}</h4>
                                            <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">{node.label}</span>
                                            {Object.entries(node.properties).map(([key, value]: [string, any], i) => (
                                                key !== 'name' && (
                                                    <p key={i} className="text-xs text-slate-400 dark:text-slate-500">
                                                        {key}: {String(value)}
                                                    </p>
                                                )
                                            ))}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>

                        {results.relationships.length > 0 && (
                            <>
                                <h2 className="text-lg font-bold text-slate-800 dark:text-white pt-2">Relationships</h2>
                                <div className="space-y-2">
                                    {results.relationships.map((rel: any, index: number) => (
                                        <div key={index} className="bg-white dark:bg-card-dark rounded-xl p-3 border-l-4 border-indigo-500 shadow-sm">
                                            <p className="text-sm text-slate-600 dark:text-slate-300 flex items-center gap-1 flex-wrap">
                                                <span className="font-medium">{rel.from}</span>
                                                <span className="material-symbols-outlined text-xs text-slate-400">arrow_forward</span>
                                                <span className="text-indigo-600 dark:text-indigo-400 font-semibold">{rel.type}</span>
                                                <span className="material-symbols-outlined text-xs text-slate-400">arrow_forward</span>
                                                <span className="font-medium">{rel.to}</span>
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            </>
                        )}
                    </div>
                ) : ragAnswer ? (
                    <div className="space-y-4">
                        {/* Answer Card */}
                        <div className="bg-white dark:bg-card-dark rounded-xl p-5 border-l-4 border-indigo-500 shadow-sm">
                            <div className="flex items-center gap-2 mb-3">
                                <span className="material-symbols-outlined text-lg text-indigo-600 dark:text-indigo-400">auto_awesome</span>
                                <h4 className="text-sm font-bold text-slate-800 dark:text-white">Answer</h4>
                            </div>
                            <p className="text-sm text-slate-700 dark:text-slate-200 leading-relaxed">{ragAnswer.answer}</p>
                        </div>

                        {ragAnswer.context && ragAnswer.context.length > 0 && (
                            <>
                                <h2 className="text-lg font-bold text-slate-800 dark:text-white">Context Sources</h2>
                                <div className="space-y-2">
                                    {ragAnswer.context.map((ctx: any, index: number) => (
                                        <div key={index} className="bg-slate-50 dark:bg-slate-800/50 rounded-xl p-3 border-l-2 border-slate-300 dark:border-slate-600">
                                            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                                                {ctx.text || ctx.content || JSON.stringify(ctx)}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            </>
                        )}
                    </div>
                ) : (
                    <div className="flex flex-col items-center justify-center py-20 text-slate-300 dark:text-slate-600">
                        <span className="material-symbols-outlined text-7xl mb-4">hub</span>
                        <p className="text-center text-base text-slate-400 dark:text-slate-500 leading-relaxed max-w-xs">
                            {mode === 'search'
                                ? 'Explore connections between symptoms, conditions, and treatments'
                                : 'Ask questions and get contextual answers from the knowledge graph'}
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
