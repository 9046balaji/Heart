import React, { useState, useEffect } from 'react';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    ScrollView,
    ActivityIndicator,
    Alert,
    RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../services/apiClient';
import { useUserStore } from '../store/useUserStore';
import { DocumentUploadResponse } from '../services/api.types';

interface Document {
    id: string;
    name: string;
    status: string;
    date: string;
    file_size?: number;
    content_type?: string;
}

export default function DocumentScreen() {
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    const [refreshing, setRefreshing] = useState(false);
    const [documents, setDocuments] = useState<Document[]>([]);
    const [uploadProgress, setUploadProgress] = useState<number | null>(null);
    const user = useUserStore(state => state.user);

    useEffect(() => {
        loadDocuments();
    }, []);

    const loadDocuments = async () => {
        try {
            // In a real implementation, you would fetch documents from the backend
            // For now, we'll just refresh the local state
        } catch (error) {
            console.error('Error loading documents:', error);
            Alert.alert('Error', 'Failed to load documents');
        }
    };

    const onRefresh = async () => {
        setRefreshing(true);
        await loadDocuments();
        setRefreshing(false);
    };

    const handleUpload = async () => {
        // Since expo-document-picker is not available, we'll simulate the upload
        Alert.alert(
            'Feature Not Available',
            'Document upload functionality requires additional setup. This would normally open a file picker.',
            [{ text: 'OK' }]
        );

        // Simulate adding a document for UI demonstration
        if (documents.length === 0) {
            setDocuments([{
                id: 'doc_' + Date.now(),
                name: 'sample_medical_report.pdf',
                status: 'processed',
                date: new Date().toISOString(),
                file_size: 1024000,
                content_type: 'application/pdf'
            }]);
        }
    };

    const handleDocumentPress = (document: Document) => {
        // Navigate to document detail screen
        navigate(`/scan-document?docId=${document.id}`);
    };

    const formatFileSize = (bytes?: number): string => {
        if (!bytes) return '';
        if (bytes < 1024) return bytes + ' bytes';
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / 1048576).toFixed(1) + ' MB';
    };

    return (
        <SafeAreaView style={styles.container}>
            <LinearGradient
                colors={['#1a1a2e', '#16213e']}
                style={styles.header}
            >
                <TouchableOpacity onPress={() => navigate(-1)} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color="#fff" />
                </TouchableOpacity>
                <Text style={styles.headerTitle}>Documents</Text>
                <TouchableOpacity style={styles.headerButton} onPress={loadDocuments}>
                    <Ionicons name="refresh" size={24} color="#fff" />
                </TouchableOpacity>
            </LinearGradient>

            <ScrollView
                style={styles.content}
                refreshControl={
                    <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
                }
            >
                <View style={styles.uploadSection}>
                    <TouchableOpacity
                        style={styles.uploadButton}
                        onPress={handleUpload}
                        disabled={loading}
                    >
                        <LinearGradient
                            colors={['#4e54c8', '#8f94fb']}
                            style={styles.gradientButton}
                        >
                            {loading ? (
                                <>
                                    <ActivityIndicator color="#fff" />
                                    {uploadProgress !== null && (
                                        <Text style={styles.progressText}>{uploadProgress}%</Text>
                                    )}
                                </>
                            ) : (
                                <>
                                    <Ionicons name="cloud-upload" size={24} color="#fff" />
                                    <Text style={styles.buttonText}>Upload Document</Text>
                                </>
                            )}
                        </LinearGradient>
                    </TouchableOpacity>

                    <Text style={styles.supportedText}>
                        Supports PDF, JPG, PNG files up to 10MB
                    </Text>
                </View>

                <View style={styles.listSection}>
                    <View style={styles.sectionHeader}>
                        <Text style={styles.sectionTitle}>Recent Documents</Text>
                        <Text style={styles.documentCount}>{documents.length} items</Text>
                    </View>

                    {documents.length === 0 ? (
                        <View style={styles.emptyState}>
                            <Ionicons name="document-text-outline" size={48} color="#666" />
                            <Text style={styles.emptyText}>No documents uploaded yet</Text>
                            <Text style={styles.emptySubtext}>Upload your medical documents, prescriptions, or reports</Text>
                        </View>
                    ) : (
                        documents.map((doc) => (
                            <TouchableOpacity
                                key={doc.id}
                                style={styles.documentCard}
                                onPress={() => handleDocumentPress(doc)}
                                disabled={doc.status !== 'processed'}
                            >
                                <View style={styles.docIcon}>
                                    <Ionicons
                                        name={
                                            doc.content_type?.includes('pdf') ? 'document-text' :
                                                doc.content_type?.includes('image') ? 'image' :
                                                    'document'
                                        }
                                        size={24}
                                        color="#4e54c8"
                                    />
                                </View>
                                <View style={styles.docInfo}>
                                    <Text style={styles.docName} numberOfLines={1}>{doc.name}</Text>
                                    <Text style={styles.docDate}>
                                        {new Date(doc.date).toLocaleDateString()}
                                        {doc.file_size ? ` • ${formatFileSize(doc.file_size)}` : ''}
                                    </Text>
                                </View>
                                <View style={[
                                    styles.docStatus,
                                    doc.status === 'processed' ? styles.statusProcessed :
                                        doc.status === 'processing' ? styles.statusProcessing :
                                            doc.status === 'failed' ? styles.statusFailed :
                                                styles.statusUploaded
                                ]}>
                                    <Text style={styles.statusText}>
                                        {doc.status.charAt(0).toUpperCase() + doc.status.slice(1)}
                                    </Text>
                                </View>
                                <Ionicons name="chevron-forward" size={20} color="#ccc" />
                            </TouchableOpacity>
                        ))
                    )}
                </View>
            </ScrollView>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#f5f5f5',
    },
    header: {
        padding: 20,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
    },
    backButton: {
        padding: 5,
    },
    headerTitle: {
        fontSize: 20,
        fontWeight: 'bold',
        color: '#fff',
    },
    headerButton: {
        padding: 5,
    },
    content: {
        flex: 1,
        padding: 20,
    },
    uploadSection: {
        marginBottom: 30,
    },
    uploadButton: {
        borderRadius: 15,
        overflow: 'hidden',
        elevation: 5,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.25,
        shadowRadius: 3.84,
    },
    gradientButton: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
        gap: 10,
    },
    buttonText: {
        color: '#fff',
        fontSize: 18,
        fontWeight: '600',
    },
    progressText: {
        color: '#fff',
        fontSize: 16,
        fontWeight: '600',
    },
    supportedText: {
        textAlign: 'center',
        marginTop: 10,
        color: '#666',
        fontSize: 14,
    },
    listSection: {
        flex: 1,
    },
    sectionHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 15,
    },
    sectionTitle: {
        fontSize: 18,
        fontWeight: 'bold',
        color: '#333',
    },
    documentCount: {
        fontSize: 14,
        color: '#666',
    },
    emptyState: {
        alignItems: 'center',
        justifyContent: 'center',
        padding: 40,
        backgroundColor: '#fff',
        borderRadius: 15,
        borderStyle: 'dashed',
        borderWidth: 2,
        borderColor: '#ddd',
    },
    emptyText: {
        marginTop: 10,
        color: '#666',
        fontSize: 16,
        fontWeight: '600',
    },
    emptySubtext: {
        marginTop: 5,
        color: '#999',
        fontSize: 14,
        textAlign: 'center',
    },
    documentCard: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: '#fff',
        padding: 15,
        borderRadius: 12,
        marginBottom: 10,
        elevation: 2,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.1,
        shadowRadius: 2,
    },
    docIcon: {
        width: 40,
        height: 40,
        borderRadius: 20,
        backgroundColor: '#f0f0f5',
        alignItems: 'center',
        justifyContent: 'center',
        marginRight: 15,
    },
    docInfo: {
        flex: 1,
        marginRight: 10,
    },
    docName: {
        fontSize: 16,
        fontWeight: '600',
        color: '#333',
        marginBottom: 4,
    },
    docDate: {
        fontSize: 12,
        color: '#888',
    },
    docStatus: {
        paddingHorizontal: 10,
        paddingVertical: 4,
        borderRadius: 10,
        marginRight: 10,
    },
    statusUploaded: {
        backgroundColor: '#e3f2fd',
    },
    statusProcessing: {
        backgroundColor: '#fff3e0',
    },
    statusProcessed: {
        backgroundColor: '#e8f5e9',
    },
    statusFailed: {
        backgroundColor: '#ffebee',
    },
    statusText: {
        fontSize: 12,
        fontWeight: '500',
    },
});
