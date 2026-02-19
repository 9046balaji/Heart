/**
 * StructuredDataRenderer Component
 * 
 * Renders structured medical data returned by the Doctor (MedGemma) agent.
 * Supports medications tables, lab values, vitals summaries, and diagnoses.
 */

import * as React from 'react';
import { StructuredMedicalData } from '../types';

interface StructuredDataRendererProps {
    data: StructuredMedicalData;
    className?: string;
}

export const StructuredDataRenderer = ({
    data,
    className = ''
}: StructuredDataRendererProps) => {
    const hasMedications = data.medications && data.medications.length > 0;
    const hasLabValues = data.lab_values && data.lab_values.length > 0;
    const hasDiagnoses = data.diagnoses && data.diagnoses.length > 0;
    const hasVitals = data.vitals_summary && (
        data.vitals_summary.heart_rate !== undefined ||
        data.vitals_summary.blood_pressure_systolic !== undefined ||
        data.vitals_summary.spo2 !== undefined ||
        data.vitals_summary.summary_text
    );
    const hasRagSources = data.rag_sources && data.rag_sources.length > 0;

    if (!hasMedications && !hasLabValues && !hasDiagnoses && !hasVitals) {
        return null;
    }

    // Helper function to get status color classes
    const getStatusColorClasses = (status: string | undefined): string => {
        if (!status) return 'bg-blue-900/50 text-blue-300';
        
        switch (status.toLowerCase()) {
            case 'normal':
                return 'bg-green-900/50 text-green-300';
            case 'critical':
                return 'bg-red-900/50 text-red-300';
            case 'warning':
            case 'abnormal':
                return 'bg-yellow-900/50 text-yellow-300';
            default:
                return 'bg-blue-900/50 text-blue-300';
        }
    };

    // Helper function to get confidence color classes
    const getConfidenceColorClasses = (confidence: number | undefined): string => {
        const conf = confidence || 0;
        if (conf >= 0.8) {
            return 'bg-green-900/50 text-green-300';
        } else if (conf >= 0.5) {
            return 'bg-yellow-900/50 text-yellow-300';
        } else {
            return 'bg-red-900/50 text-red-300';
        }
    };

    return (
        <div className={`structured-data-renderer space-y-4 ${className}`}>
            {/* Vitals Summary Card */}
            {hasVitals && data.vitals_summary && (
                <div className="bg-blue-950/30 rounded-xl p-4 border border-blue-800/50">
                    <div className="flex items-center gap-2 mb-3">
                        <span className="material-symbols-outlined text-blue-400">monitor_heart</span>
                        <h4 className="text-sm font-semibold text-blue-300 uppercase tracking-wider">
                            Vitals Analysis
                        </h4>
                        {data.vitals_summary.status && (
                            <span className={`ml-auto px-2 py-0.5 rounded-full text-xs font-medium ${getStatusColorClasses(data.vitals_summary.status)}`}>
                                {data.vitals_summary.status.toUpperCase()}
                            </span>
                        )}
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {data.vitals_summary.heart_rate !== undefined && (
                            <div className="bg-slate-800/50 rounded-lg p-3">
                                <div className="text-xs text-slate-400 mb-1">Heart Rate</div>
                                <div className="text-xl font-bold text-white">
                                    {data.vitals_summary.heart_rate}
                                    <span className="text-xs text-slate-400 ml-1">bpm</span>
                                </div>
                            </div>
                        )}
                        {data.vitals_summary.blood_pressure_systolic !== undefined && (
                            <div className="bg-slate-800/50 rounded-lg p-3">
                                <div className="text-xs text-slate-400 mb-1">Blood Pressure</div>
                                <div className="text-xl font-bold text-white">
                                    {data.vitals_summary.blood_pressure_systolic}/{data.vitals_summary.blood_pressure_diastolic || '--'}
                                    <span className="text-xs text-slate-400 ml-1">mmHg</span>
                                </div>
                            </div>
                        )}
                        {data.vitals_summary.spo2 !== undefined && (
                            <div className="bg-slate-800/50 rounded-lg p-3">
                                <div className="text-xs text-slate-400 mb-1">SpO2</div>
                                <div className="text-xl font-bold text-white">
                                    {data.vitals_summary.spo2}
                                    <span className="text-xs text-slate-400 ml-1">%</span>
                                </div>
                            </div>
                        )}
                    </div>

                    {data.vitals_summary.summary_text && (
                        <p className="text-sm text-slate-300 mt-3">
                            {data.vitals_summary.summary_text}
                        </p>
                    )}
                </div>
            )}

            {/* Medications Table */}
            {hasMedications && data.medications && (
                <div className="bg-blue-950/30 rounded-xl p-4 border border-blue-800/50">
                    <div className="flex items-center gap-2 mb-3">
                        <span className="material-symbols-outlined text-blue-400">pill</span>
                        <h4 className="text-sm font-semibold text-blue-300 uppercase tracking-wider">
                            Medications
                        </h4>
                    </div>

                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-slate-700">
                                    <th className="text-left py-2 px-3 text-slate-400 font-medium">Medication</th>
                                    <th className="text-left py-2 px-3 text-slate-400 font-medium">Dosage</th>
                                    <th className="text-left py-2 px-3 text-slate-400 font-medium">Frequency</th>
                                    <th className="text-right py-2 px-3 text-slate-400 font-medium">Confidence</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.medications.map((med, idx) => (
                                    <tr key={`${med.name}-${idx}`} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                                        <td className="py-2 px-3 text-white font-medium">{med.name}</td>
                                        <td className="py-2 px-3 text-slate-300">
                                            {med.dosage_value && med.dosage_unit ? (
                                                <>{med.dosage_value} {med.dosage_unit}</>
                                            ) : (
                                                'N/A'
                                            )}
                                        </td>
                                        <td className="py-2 px-3 text-slate-300">{med.frequency || 'N/A'}</td>
                                        <td className="py-2 px-3 text-right">
                                            <span className={`px-2 py-0.5 rounded text-xs ${getConfidenceColorClasses(med.confidence)}`}>
                                                {Math.round((med.confidence || 0) * 100)}%
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Lab Values Table */}
            {hasLabValues && data.lab_values && (
                <div className="bg-blue-950/30 rounded-xl p-4 border border-blue-800/50">
                    <div className="flex items-center gap-2 mb-3">
                        <span className="material-symbols-outlined text-blue-400">science</span>
                        <h4 className="text-sm font-semibold text-blue-300 uppercase tracking-wider">
                            Lab Results
                        </h4>
                    </div>

                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-slate-700">
                                    <th className="text-left py-2 px-3 text-slate-400 font-medium">Test</th>
                                    <th className="text-right py-2 px-3 text-slate-400 font-medium">Value</th>
                                    <th className="text-left py-2 px-3 text-slate-400 font-medium">Reference</th>
                                    <th className="text-center py-2 px-3 text-slate-400 font-medium">Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.lab_values.map((lab, idx) => (
                                    <tr key={`${lab.test_name}-${idx}`} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                                        <td className="py-2 px-3 text-white font-medium">{lab.test_name}</td>
                                        <td className="py-2 px-3 text-right text-slate-300">
                                            {lab.value} <span className="text-slate-500">{lab.unit}</span>
                                        </td>
                                        <td className="py-2 px-3 text-slate-400 text-xs">
                                            {lab.reference_min !== undefined && lab.reference_max !== undefined
                                                ? `${lab.reference_min} - ${lab.reference_max}`
                                                : 'N/A'}
                                        </td>
                                        <td className="py-2 px-3 text-center">
                                            {lab.is_abnormal ? (
                                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-red-900/50 text-red-300 text-xs">
                                                    <span className="material-symbols-outlined text-xs">warning</span>
                                                    Abnormal
                                                </span>
                                            ) : (
                                                <span className="px-2 py-0.5 rounded bg-green-900/50 text-green-300 text-xs">
                                                    Normal
                                                </span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Diagnoses List */}
            {hasDiagnoses && data.diagnoses && (
                <div className="bg-blue-950/30 rounded-xl p-4 border border-blue-800/50">
                    <div className="flex items-center gap-2 mb-3">
                        <span className="material-symbols-outlined text-blue-400">medical_information</span>
                        <h4 className="text-sm font-semibold text-blue-300 uppercase tracking-wider">
                            Conditions Mentioned
                        </h4>
                    </div>

                    <div className="flex flex-wrap gap-2">
                        {data.diagnoses.map((diagnosis, idx) => (
                            <span
                                key={idx}
                                className="px-3 py-1.5 bg-slate-800/50 rounded-full text-sm text-slate-200 border border-slate-700"
                            >
                                {diagnosis}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* RAG Sources */}
            {hasRagSources && data.rag_sources && (
                <div className="flex items-center gap-2 text-xs text-slate-500">
                    <span className="material-symbols-outlined text-xs">source</span>
                    <span>Sources: {data.rag_sources.join(', ')}</span>
                </div>
            )}
        </div>
    );
};

export default StructuredDataRenderer;