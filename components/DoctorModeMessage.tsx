/**
 * DoctorModeMessage Component
 * 
 * Specialized message component for MedGemma (Doctor) agent responses.
 * Features a distinctive blue medical theme with structured data rendering
 * and professional healthcare-appropriate styling.
 */

import React from 'react';
import { Message } from '../types';
import { ChatMessageMarkdown } from './MarkdownRenderer';
import { StructuredDataRenderer } from './StructuredDataRenderer';

interface DoctorModeMessageProps {
    message: Message;
    onCopy?: (text: string, id: string) => void;
    onPlayTTS?: (text: string, id: string) => void;
    isPlayingId?: string | null;
    copiedMessageId?: string | null;
}

export const DoctorModeMessage: React.FC<DoctorModeMessageProps> = ({
    message,
    onCopy,
    onPlayTTS,
    isPlayingId,
    copiedMessageId,
}) => {
    const isDoctor = message.agentType === 'doctor';
    const hasStructuredData = message.structuredData && (
        (message.structuredData.medications?.length ?? 0) > 0 ||
        (message.structuredData.lab_values?.length ?? 0) > 0 ||
        (message.structuredData.diagnoses?.length ?? 0) > 0 ||
        message.structuredData.vitals_summary
    );

    return (
        <div className={`doctor-mode-message flex flex-col max-w-[90%] items-start animate-message-left`}>
            {/* Agent Badge Header */}
            <div className="flex items-center gap-2 mb-1.5 px-1">
                <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold shadow-sm ${isDoctor
                        ? 'bg-blue-50 dark:bg-blue-900/40 text-blue-600 dark:text-blue-300 border border-blue-200 dark:border-blue-700/50'
                        : 'bg-emerald-50 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-700/50'
                    }`}>
                    <span className="material-symbols-outlined text-sm">
                        {isDoctor ? 'stethoscope' : 'support_agent'}
                    </span>
                    <span>{isDoctor ? 'Medical Expert' : 'Health Assistant'}</span>
                </div>

                {message.routingReason && (
                    <span className="text-[10px] text-slate-500 italic bg-slate-100 dark:bg-slate-800/40 px-1.5 py-0.5 rounded">
                        {message.routingReason}
                    </span>
                )}

                {message.ragContext && (
                    <span className="text-[10px] text-blue-400 bg-blue-900/30 px-1.5 py-0.5 rounded-lg flex items-center gap-0.5 font-medium" title="Used medical knowledge base">
                        <span className="material-symbols-outlined text-[10px]">database</span>
                        RAG
                    </span>
                )}
            </div>

            <div className="flex gap-3 flex-row">
                {/* Avatar */}
                <div className="shrink-0 mt-1">
                    <div className={`w-10 h-10 rounded-xl overflow-hidden border-2 flex items-center justify-center shadow-lg ${isDoctor
                            ? 'border-blue-400/50 dark:border-blue-500/50 bg-gradient-to-br from-blue-500 to-blue-700 dark:from-blue-800 dark:to-blue-950 shadow-blue-500/20 dark:shadow-blue-900/30'
                            : 'border-emerald-400/50 dark:border-emerald-500/50 bg-gradient-to-br from-emerald-500 to-emerald-700 dark:from-emerald-800 dark:to-emerald-950 shadow-emerald-500/20 dark:shadow-emerald-900/30'
                        }`}>
                        <span className={`material-symbols-outlined text-xl text-white ${isDoctor ? '' : ''
                            }`}>
                            {isDoctor ? 'medical_services' : 'smart_toy'}
                        </span>
                    </div>
                </div>

                {/* Message Content */}
                <div className={`flex-1 p-4 rounded-2xl rounded-tl-md text-sm leading-relaxed shadow-lg relative group transition-all duration-200 ${isDoctor
                        ? 'bg-gradient-to-br from-blue-50/80 to-white dark:from-blue-950/70 dark:to-[#0f1923] text-slate-800 dark:text-slate-100 border border-blue-200/60 dark:border-blue-800/40'
                        : 'bg-gradient-to-br from-emerald-50/80 to-white dark:from-emerald-950/70 dark:to-[#0f1923] text-slate-800 dark:text-slate-100 border border-emerald-200/60 dark:border-emerald-800/40'
                    }`}>

                    {/* Medical Disclaimer Ribbon */}
                    {isDoctor && (
                        <div className="flex items-center gap-1.5 px-2.5 py-1.5 mb-3 bg-slate-100/70 dark:bg-slate-800/40 rounded-lg border border-slate-200/50 dark:border-slate-700/30 text-[10px] text-slate-500 dark:text-slate-400">
                            <span className="material-symbols-outlined text-xs text-amber-400/70">info</span>
                            <span>AI-generated medical information — verify with your healthcare provider</span>
                        </div>
                    )}

                    {/* Emergency Warning */}
                    {message.metadata?.is_emergency && (
                        <div className="flex items-center gap-2.5 p-3 mb-3 bg-red-50 dark:bg-red-900/40 rounded-xl border border-red-200 dark:border-red-700/50 shadow-md shadow-red-100/30 dark:shadow-red-900/20">
                            <div className="w-8 h-8 rounded-lg bg-red-100 dark:bg-red-800/50 flex items-center justify-center flex-shrink-0">
                                <span className="material-symbols-outlined text-red-500 dark:text-red-400 animate-heartbeat">emergency</span>
                            </div>
                            <div>
                                <p className="text-sm font-semibold text-red-600 dark:text-red-300">Emergency Detected</p>
                                <p className="text-[11px] text-red-500/80 dark:text-red-400/80">Please seek immediate medical attention if needed</p>
                            </div>
                        </div>
                    )}

                    {/* Message Text */}
                    <ChatMessageMarkdown
                        content={message.content}
                        sources={message.sources}
                        showHealthAlerts={true}
                    />

                    {/* Structured Data Rendering */}
                    {hasStructuredData && message.structuredData && (
                        <div className="mt-4 pt-4 border-t border-slate-200/40 dark:border-slate-700/40">
                            <StructuredDataRenderer data={message.structuredData} />
                        </div>
                    )}

                    {/* Confidence Score */}
                    {message.complexityScore !== undefined && (
                        <div className="mt-3 pt-2 border-t border-slate-200/30 dark:border-slate-700/30">
                            <div className="flex items-center gap-2">
                                <span className="text-[10px] text-slate-500 font-medium">Confidence</span>
                                <div className="flex-1 h-1 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
                                    <div
                                        className={`h-full rounded-full transition-all duration-500 ${
                                            message.complexityScore > 0.7 ? 'bg-emerald-500' :
                                            message.complexityScore > 0.4 ? 'bg-amber-500' : 'bg-red-500'
                                        }`}
                                        style={{ width: `${Math.round(message.complexityScore * 100)}%` }}
                                    />
                                </div>
                                <span className="text-[10px] text-slate-500 font-mono">{Math.round(message.complexityScore * 100)}%</span>
                            </div>
                        </div>
                    )}

                    {/* Action Buttons */}
                    <div className="flex items-center gap-1 mt-3 pt-2.5 border-t border-slate-200/40 dark:border-slate-700/40 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                        <button
                            onClick={() => onCopy?.(message.content, message.id)}
                            className="flex items-center gap-1 px-2.5 py-1.5 text-xs text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-700/50 rounded-lg transition-all duration-200"
                            title="Copy message"
                        >
                            <span className="material-symbols-outlined text-sm">
                                {copiedMessageId === message.id ? 'check' : 'content_copy'}
                            </span>
                            {copiedMessageId === message.id ? 'Copied!' : 'Copy'}
                        </button>

                        <button
                            onClick={() => onPlayTTS?.(message.content, message.id)}
                            className="flex items-center gap-1 px-2.5 py-1.5 text-xs text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-700/50 rounded-lg transition-all duration-200"
                            title="Read aloud"
                        >
                            <span className="material-symbols-outlined text-sm">
                                {isPlayingId === message.id ? 'stop' : 'volume_up'}
                            </span>
                            {isPlayingId === message.id ? 'Stop' : 'Listen'}
                        </button>

                        {/* Timestamp */}
                        <span className="ml-auto text-[9px] text-slate-600 font-mono">
                            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                    </div>
                </div>
            </div>

            {/* Grounding/Citation Sources */}
            {message.groundingMetadata?.groundingChunks && message.groundingMetadata.groundingChunks.length > 0 && (
                <div className="mt-2 ml-13 flex flex-wrap gap-1.5">
                    <span className="text-[10px] text-slate-500 flex items-center gap-1 mr-1">
                        <span className="material-symbols-outlined text-[10px]">link</span>
                        Sources:
                    </span>
                    {message.groundingMetadata.groundingChunks.slice(0, 3).map((chunk, idx) => (
                        <a
                            key={idx}
                            href={chunk.web?.uri}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[10px] text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/25 px-2 py-0.5 rounded-full hover:bg-blue-100 dark:hover:bg-blue-900/40 hover:text-blue-700 dark:hover:text-blue-300 transition-all duration-200 border border-blue-200 dark:border-blue-800/30"
                        >
                            {chunk.web?.title || `Source ${idx + 1}`}
                        </a>
                    ))}
                </div>
            )}
        </div>
    );
};

export default DoctorModeMessage;
