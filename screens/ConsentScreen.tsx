import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Switch, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { apiClient } from '../services/apiClient';
import { useToast } from '../components/Toast';
import { useConfirm } from '../components/ConfirmDialog';

export default function ConsentScreen() {
    const navigate = useNavigate();
    const { showToast } = useToast();
    const confirm = useConfirm();
    const [loading, setLoading] = useState(true);
    const [consents, setConsents] = useState<any>({});
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadConsents();
    }, []);

    const loadConsents = async () => {
        try {
            setLoading(true);
            const data = await apiClient.getConsent('current_user');
            setConsents(data);
            setError(null);
        } catch (err) {
            console.error('Failed to load consents:', err);
            setError('Failed to load consent settings.');
        } finally {
            setLoading(false);
        }
    };

    const handleConsentToggle = async (consentType: string, value: boolean) => {
        try {
            const updated = { ...consents, [consentType]: value };
            await apiClient.updateConsent('current_user', updated);
            setConsents(updated);
            showToast('Consent preferences updated', 'success');
        } catch (err) {
            console.error('Failed to update consent:', err);
            showToast('Failed to update consent. Please try again.', 'error');
        }
    };

    const consentItems = [
        {
            key: 'data_processing',
            title: 'Data Processing',
            description: 'Allow processing of your health data for personalized insights and recommendations',
            icon: 'server' as const,
            required: true,
        },
        {
            key: 'ai_analysis',
            title: 'AI Analysis',
            description: 'Enable AI-powered analysis of your health records and vitals',
            icon: 'sparkles' as const,
            required: false,
        },
        {
            key: 'data_sharing',
            title: 'Data Sharing',
            description: 'Share anonymized data for research and improving healthcare AI',
            icon: 'share-social' as const,
            required: false,
        },
        {
            key: 'marketing',
            title: 'Marketing Communications',
            description: 'Receive health tips, updates, and promotional content',
            icon: 'mail' as const,
            required: false,
        },
        {
            key: 'analytics',
            title: 'Usage Analytics',
            description: 'Allow collection of app usage data to improve user experience',
            icon: 'analytics' as const,
            required: false,
        },
        {
            key: 'third_party',
            title: 'Third-Party Integration',
            description: 'Enable integration with third-party health apps and devices',
            icon: 'link' as const,
            required: false,
        },
    ];

    return (
        <SafeAreaView style={styles.container}>
            <LinearGradient colors={['#1a1a2e', '#16213e']} style={styles.header}>
                <TouchableOpacity onPress={() => navigate(-1)} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color="#fff" />
                </TouchableOpacity>
                <Text style={styles.headerTitle}>Privacy & Consent</Text>
                <View style={{ width: 24 }} />
            </LinearGradient>

            <ScrollView style={styles.content}>
                {loading ? (
                    <View style={styles.centerContainer}>
                        <ActivityIndicator size="large" color="#4e54c8" />
                        <Text style={styles.loadingText}>Loading consents...</Text>
                    </View>
                ) : error ? (
                    <View style={styles.centerContainer}>
                        <Ionicons name="alert-circle" size={48} color="#EA4335" />
                        <Text style={styles.errorText}>{error}</Text>
                        <TouchableOpacity style={styles.retryButton} onPress={loadConsents}>
                            <Text style={styles.retryText}>Retry</Text>
                        </TouchableOpacity>
                    </View>
                ) : (
                    <View>
                        <View style={styles.infoCard}>
                            <Ionicons name="shield-checkmark" size={32} color="#4e54c8" />
                            <Text style={styles.infoTitle}>Your Data, Your Control</Text>
                            <Text style={styles.infoText}>
                                We respect your privacy. Manage your consent preferences below. You can change these settings at any time.
                            </Text>
                        </View>

                        <Text style={styles.sectionTitle}>Consent Preferences</Text>

                        {consentItems.map((item) => (
                            <View key={item.key} style={styles.consentCard}>
                                <View style={styles.consentHeader}>
                                    <View style={[styles.iconBox, { backgroundColor: consents[item.key] ? '#4e54c820' : '#f0f0f0' }]}>
                                        <Ionicons
                                            name={item.icon}
                                            size={20}
                                            color={consents[item.key] ? '#4e54c8' : '#999'}
                                        />
                                    </View>
                                    <View style={styles.consentInfo}>
                                        <View style={styles.titleRow}>
                                            <Text style={styles.consentTitle}>{item.title}</Text>
                                            {item.required && (
                                                <View style={styles.requiredBadge}>
                                                    <Text style={styles.requiredText}>Required</Text>
                                                </View>
                                            )}
                                        </View>
                                        <Text style={styles.consentDescription}>{item.description}</Text>
                                    </View>
                                    <Switch
                                        value={consents[item.key] || false}
                                        onValueChange={(value) => handleConsentToggle(item.key, value)}
                                        disabled={item.required}
                                        trackColor={{ false: '#ccc', true: '#4e54c8' }}
                                        thumbColor={consents[item.key] ? '#fff' : '#f4f3f4'}
                                    />
                                </View>
                            </View>
                        ))}

                        <View style={styles.gdprInfo}>
                            <Ionicons name="information-circle" size={20} color="#666" />
                            <Text style={styles.gdprText}>
                                In compliance with GDPR and HIPAA regulations. Your data is encrypted and securely stored.
                            </Text>
                        </View>

                        <TouchableOpacity
                            style={styles.revokeButton}
                            onPress={async () => {
                                const confirmed = await confirm({
                                    title: 'Revoke All Consents',
                                    message: 'This will disable all optional features. Are you sure?',
                                    confirmText: 'Revoke',
                                    variant: 'danger',
                                });
                                if (confirmed) {
                                    const updated = { ...consents };
                                    consentItems.filter(i => !i.required).forEach(i => {
                                        updated[i.key] = false;
                                    });
                                    await apiClient.updateConsent('current_user', updated);
                                    setConsents(updated);
                                }
                            }}
                        >
                            <Ionicons name="close-circle" size={20} color="#EA4335" />
                            <Text style={styles.revokeText}>Revoke All Optional Consents</Text>
                        </TouchableOpacity>
                    </View>
                )}
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
    content: {
        flex: 1,
        padding: 15,
    },
    centerContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        paddingTop: 60,
    },
    loadingText: {
        marginTop: 10,
        color: '#666',
    },
    errorText: {
        marginTop: 10,
        color: '#EA4335',
        marginBottom: 20,
    },
    retryButton: {
        paddingHorizontal: 20,
        paddingVertical: 10,
        backgroundColor: '#4e54c8',
        borderRadius: 8,
    },
    retryText: {
        color: '#fff',
        fontWeight: 'bold',
    },
    infoCard: {
        backgroundColor: '#E8EAF6',
        borderRadius: 12,
        padding: 20,
        alignItems: 'center',
        marginBottom: 20,
    },
    infoTitle: {
        fontSize: 18,
        fontWeight: 'bold',
        color: '#333',
        marginTop: 10,
        marginBottom: 8,
    },
    infoText: {
        fontSize: 14,
        color: '#555',
        textAlign: 'center',
        lineHeight: 20,
    },
    sectionTitle: {
        fontSize: 18,
        fontWeight: 'bold',
        color: '#333',
        marginTop: 10,
        marginBottom: 15,
    },
    consentCard: {
        backgroundColor: '#fff',
        borderRadius: 12,
        padding: 15,
        marginBottom: 12,
        elevation: 1,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.1,
        shadowRadius: 2,
    },
    consentHeader: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    iconBox: {
        width: 40,
        height: 40,
        borderRadius: 20,
        alignItems: 'center',
        justifyContent: 'center',
        marginRight: 12,
    },
    consentInfo: {
        flex: 1,
        marginRight: 10,
    },
    titleRow: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: 4,
    },
    consentTitle: {
        fontSize: 15,
        fontWeight: '600',
        color: '#333',
    },
    requiredBadge: {
        backgroundColor: '#FFF3E0',
        paddingHorizontal: 8,
        paddingVertical: 2,
        borderRadius: 10,
        marginLeft: 8,
    },
    requiredText: {
        fontSize: 10,
        color: '#F9A825',
        fontWeight: 'bold',
    },
    consentDescription: {
        fontSize: 13,
        color: '#666',
        lineHeight: 18,
    },
    gdprInfo: {
        flexDirection: 'row',
        alignItems: 'flex-start',
        backgroundColor: '#fff',
        borderRadius: 8,
        padding: 12,
        marginTop: 20,
        gap: 10,
    },
    gdprText: {
        flex: 1,
        fontSize: 12,
        color: '#666',
        lineHeight: 18,
    },
    revokeButton: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#fff',
        borderWidth: 1,
        borderColor: '#EA4335',
        borderRadius: 8,
        padding: 12,
        marginTop: 15,
        marginBottom: 20,
        gap: 8,
    },
    revokeText: {
        color: '#EA4335',
        fontWeight: '600',
        fontSize: 14,
    },
});
