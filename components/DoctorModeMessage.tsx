/**
 * DoctorModeMessage Component
 * 
 * Specialized message component for MedGemma (Doctor) agent responses.
 * Features a distinctive blue medical theme with structured data rendering.
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
        <div className={`doctor-mode-message flex flex-col max-w-[90%] items-start`}>
            {/* Agent Badge Header */}
            <div className="flex items-center gap-2 mb-1 px-1">
                <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${isDoctor
                        ? 'bg-blue-900/50 text-blue-300 border border-blue-700'
                        : 'bg-green-900/50 text-green-300 border border-green-700'
                    }`}>
                    <span className="material-symbols-outlined text-sm">
                        {isDoctor ? 'stethoscope' : 'support_agent'}
                    </span>
                    <span>{isDoctor ? 'Medical Expert' : 'Health Assistant'}</span>
                </div>

                {message.routingReason && (
                    <span className="text-[10px] text-slate-500 italic">
                        {message.routingReason}
                    </span>
                )}

                {message.ragContext && (
                    <span className="text-[10px] text-blue-400 bg-blue-900/30 px-1 rounded flex items-center gap-0.5" title="Used medical knowledge base">
                        <span className="material-symbols-outlined text-[10px]">database</span>
                        RAG
                    </span>
                )}
            </div>

            <div className="flex gap-3 flex-row">
                {/* Avatar */}
                <div className="shrink-0 mt-1">
                    <div className={`w-10 h-10 rounded-full overflow-hidden border-2 flex items-center justify-center ${isDoctor
                            ? 'border-blue-500 bg-blue-900/50'
                            : 'border-green-500 bg-green-900/50'
                        }`}>
                        <span className={`material-symbols-outlined text-xl ${isDoctor ? 'text-blue-400' : 'text-green-400'
                            }`}>
                            {isDoctor ? 'medical_services' : 'smart_toy'}
                        </span>
                    </div>
                </div>

                {/* Message Content */}
                <div className={`flex-1 p-4 rounded-2xl rounded-tl-none text-sm leading-relaxed shadow-lg relative group ${isDoctor
                        ? 'bg-gradient-to-br from-blue-950/80 to-slate-900 text-slate-100 border border-blue-800/50'
                        : 'bg-gradient-to-br from-green-950/80 to-slate-900 text-slate-100 border border-green-800/50'
                    }`}>
                    {/* Emergency Warning */}
                    {message.metadata?.is_emergency && (
                        <div className="flex items-center gap-2 p-2 mb-3 bg-red-900/50 rounded-lg border border-red-700">
                            <span className="material-symbols-outlined text-red-400 animate-pulse">emergency</span>
                            <span className="text-sm font-medium text-red-300">
                                Emergency detected - Please seek immediate medical attention if needed
                            </span>
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
                        <div className="mt-4 pt-4 border-t border-slate-700">
                            <StructuredDataRenderer data={message.structuredData} />
                        </div>
                    )}

                    {/* Action Buttons */}
                    <div className="flex items-center gap-2 mt-3 pt-2 border-t border-slate-700/50 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                            onClick={() => onCopy?.(message.content, message.id)}
                            className="flex items-center gap-1 px-2 py-1 text-xs text-slate-400 hover:text-white hover:bg-slate-700 rounded transition-colors"
                            title="Copy message"
                        >
                            <span className="material-symbols-outlined text-sm">
                                {copiedMessageId === message.id ? 'check' : 'content_copy'}
                            </span>
                            {copiedMessageId === message.id ? 'Copied!' : 'Copy'}
                        </button>

                        <button
                            onClick={() => onPlayTTS?.(message.content, message.id)}
                            className="flex items-center gap-1 px-2 py-1 text-xs text-slate-400 hover:text-white hover:bg-slate-700 rounded transition-colors"
                            title="Read aloud"
                        >
                            <span className="material-symbols-outlined text-sm">
                                {isPlayingId === message.id ? 'stop' : 'volume_up'}
                            </span>
                            {isPlayingId === message.id ? 'Stop' : 'Listen'}
                        </button>

                        {message.complexityScore !== undefined && (
                            <span className="ml-auto text-[10px] text-slate-500">
                                Complexity: {Math.round(message.complexityScore * 100)}%
                            </span>
                        )}
                    </div>
                </div>
            </div>

            {/* Grounding/Citation Sources */}
            {message.groundingMetadata?.groundingChunks && message.groundingMetadata.groundingChunks.length > 0 && (
                <div className="mt-2 ml-13 text-xs text-slate-500">
                    <span className="material-symbols-outlined text-xs mr-1">link</span>
                    References:
                    {message.groundingMetadata.groundingChunks.slice(0, 3).map((chunk, idx) => (
                        <a
                            key={idx}
                            href={chunk.web?.uri}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="ml-2 text-blue-400 hover:underline"
                        >
                            {chunk.web?.title || 'Source'}
                        </a>
                    ))}
                </div>
            )}
        </div>
    );
};

export default DoctorModeMessage;
