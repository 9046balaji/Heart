import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../services/apiClient';
import { useUserStore } from '../store/useUserStore';
import { useAuth } from '../hooks/useAuth';
import { DocumentDetails } from '../services/api.types';
import ScreenHeader from '../components/ScreenHeader';

// Use the shared type from api.types
type Document = DocumentDetails;

export default function DocumentScreen() {
    const navigate = useNavigate();
    const { user } = useAuth();
    const [loading, setLoading] = useState(false);
    const [documents, setDocuments] = useState<Document[]>([]);
    const [showUploadModal, setShowUploadModal] = useState(false);
    const [uploading, setUploading] = useState(false);

    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        loadDocuments();
    }, [user]);

    const loadDocuments = async () => {
        if (!user) return;
        setLoading(true);
        try {
            const docs = await apiClient.getDocuments();
            setDocuments(docs);
        } catch (error) {
            console.error('Failed to load documents:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file || !user) return;

        setUploading(true);
        try {
            await apiClient.uploadDocument(file); // Backend handles user and type for now
            await loadDocuments();
            setShowUploadModal(false);
        } catch (error) {
            console.error('Upload failed:', error);
            alert('Failed to upload document');
        } finally {
            setUploading(false);
        }
    };

    const getIconForType = (type: string) => {
        switch (type.toLowerCase()) {
            case 'lab report': return 'biotech';
            case 'prescription': return 'prescriptions';
            case 'imaging': return 'radiology';
            default: return 'description';
        }
    };

    return (
        <div className="min-h-screen bg-slate-50 dark:bg-background-dark pb-24 font-sans">
            <ScreenHeader
                title="Medical Records"
                subtitle="Secure Document Storage"
                rightIcon="add"
                onRightAction={() => setShowUploadModal(true)}
            />

            <div className="max-w-4xl mx-auto p-4 space-y-6">

                {/* Search / Filter (Placeholder for now) */}
                <div className="relative">
                    <span className="material-symbols-outlined absolute left-4 top-3.5 text-slate-400">search</span>
                    <input
                        type="text"
                        placeholder="Search records..."
                        className="w-full pl-12 pr-4 py-3 bg-white dark:bg-card-dark rounded-xl border-none shadow-sm focus:ring-2 focus:ring-primary/20 dark:text-white"
                    />
                </div>

                {loading ? (
                    <div className="flex justify-center py-12">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                    </div>
                ) : documents.length === 0 ? (
                    <div className="text-center py-16">
                        <div className="w-20 h-20 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-4">
                            <span className="material-symbols-outlined text-4xl text-slate-300">folder_off</span>
                        </div>
                        <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-1">No Documents Yet</h3>
                        <p className="text-slate-500 dark:text-slate-400 text-sm max-w-xs mx-auto mb-6">Upload your lab reports, prescriptions, or imaging results to keep them organized.</p>
                        <button
                            onClick={() => setShowUploadModal(true)}
                            className="bg-primary text-white px-6 py-3 rounded-xl font-bold hover:bg-primary-dark transition-colors shadow-lg shadow-primary/20"
                        >
                            Upload First Document
                        </button>
                    </div>
                ) : (
                    <div className="grid gap-4">
                        {documents.map((doc) => (
                            <div key={doc.document_id} className="bg-white dark:bg-card-dark p-4 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm flex items-center gap-4 hover:shadow-md transition-shadow group">
                                <div className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 ${doc.classification?.document_type === 'Lab Report' ? 'bg-blue-50 text-blue-600 dark:bg-blue-900/20' :
                                    doc.classification?.document_type === 'Prescription' ? 'bg-green-50 text-green-600 dark:bg-green-900/20' :
                                        'bg-indigo-50 text-indigo-600 dark:bg-indigo-900/20'
                                    }`}>
                                    <span className="material-symbols-outlined">{getIconForType(doc.classification?.document_type || 'default')}</span>
                                </div>

                                <div className="flex-1 min-w-0">
                                    <h4 className="font-bold text-slate-900 dark:text-white truncate">{doc.filename}</h4>
                                    <div className="flex items-center gap-2 mt-1">
                                        <span className="text-xs font-medium px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-500">
                                            {doc.classification?.document_type}
                                        </span>
                                        <span className="text-xs text-slate-400">
                                            {new Date(doc.created_at).toLocaleDateString()}
                                        </span>
                                    </div>
                                    {doc.classification?.category && (
                                        <p className="text-sm text-slate-500 dark:text-slate-400 mt-2 line-clamp-2">
                                            {doc.classification.category}
                                        </p>
                                    )}
                                </div>

                                <button className="p-2 text-slate-400 hover:text-primary hover:bg-slate-50 dark:hover:bg-slate-800 rounded-full transition-colors">
                                    <span className="material-symbols-outlined">download</span>
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Upload Modal */}
            {showUploadModal && (
                <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 sm:p-6 bg-slate-900/60 backdrop-blur-sm animate-in fade-in" onClick={() => setShowUploadModal(false)}>
                    <div className="bg-white dark:bg-slate-900 rounded-3xl w-full max-w-sm p-6 shadow-2xl animate-in slide-in-from-bottom-10" onClick={e => e.stopPropagation()}>
                        <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-6">Upload Document</h3>

                        <div
                            onClick={() => fileInputRef.current?.click()}
                            className="border-2 border-dashed border-slate-200 dark:border-slate-700 rounded-2xl p-8 text-center hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer"
                        >
                            {uploading ? (
                                <div className="py-4">
                                    <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                                    <p className="font-bold text-slate-900 dark:text-white">Uploading...</p>
                                </div>
                            ) : (
                                <>
                                    <span className="material-symbols-outlined text-4xl text-slate-400 mb-2">cloud_upload</span>
                                    <p className="font-bold text-slate-900 dark:text-white">Tap to Select File</p>
                                    <p className="text-xs text-slate-500 mt-1">PDF, JPG, PNG up to 10MB</p>
                                </>
                            )}
                        </div>
                        <input
                            type="file"
                            ref={fileInputRef}
                            className="hidden"
                            onChange={handleFileUpload}
                            accept=".pdf,.jpg,.jpeg,.png"
                        />

                        <button
                            onClick={() => setShowUploadModal(false)}
                            className="w-full mt-6 py-3.5 bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white font-bold rounded-xl hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                        >
                            Cancel
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
