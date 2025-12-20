import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { apiClient } from '../services/apiClient';

export default function PatientSummaryScreen({ navigation }: any) {
    const [loading, setLoading] = useState(true);
    const [summary, setSummary] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadSummary();
    }, []);

    const loadSummary = async () => {
        try {
            setLoading(true);
            const data = await apiClient.getPatientSummary('current_user');
            setSummary(data);
            setError(null);
        } catch (err) {
            console.error('Failed to load patient summary:', err);
            setError('Failed to load patient summary. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const renderConditionCard = (condition: any, index: number) => (
        <View key={index} style={styles.conditionCard}>
            <View style={styles.conditionHeader}>
                <Ionicons name="medical" size={20} color="#e91e63" />
                <Text style={styles.conditionName}>{condition.name || condition.condition}</Text>
            </View>
            {condition.diagnosed_date && (
                <Text style={styles.conditionDetail}>Diagnosed: {new Date(condition.diagnosed_date).toLocaleDateString()}</Text>
            )}
            {condition.severity && (
                <View style={[styles.severityBadge, { backgroundColor: getSeverityColor(condition.severity) + '20' }]}>
                    <Text style={[styles.severityText, { color: getSeverityColor(condition.severity) }]}>
                        {condition.severity}
                    </Text>
                </View>
            )}
        </View>
    );

    const renderMedicationCard = (medication: any, index: number) => (
        <View key={index} style={styles.medicationCard}>
            <View style={styles.medicationHeader}>
                <Ionicons name="medkit" size={20} color="#2196f3" />
                <Text style={styles.medicationName}>{medication.name}</Text>
            </View>
            <Text style={styles.medicationDetail}>
                {medication.dosage} - {medication.frequency || 'As needed'}
            </Text>
            {medication.prescriber && (
                <Text style={styles.medicationPrescriber}>Prescribed by: {medication.prescriber}</Text>
            )}
        </View>
    );

    const getSeverityColor = (severity: string) => {
        switch (severity?.toLowerCase()) {
            case 'critical': return '#EA4335';
            case 'high': return '#ff9800';
            case 'moderate': return '#F9A825';
            case 'low': return '#4caf50';
            default: return '#666';
        }
    };

    return (
        <SafeAreaView style={styles.container}>
            <LinearGradient colors={['#1a1a2e', '#16213e']} style={styles.header}>
                <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color="#fff" />
                </TouchableOpacity>
                <Text style={styles.headerTitle}>Patient Summary</Text>
                <TouchableOpacity onPress={loadSummary}>
                    <Ionicons name="refresh" size={24} color="#fff" />
                </TouchableOpacity>
            </LinearGradient>

            <ScrollView style={styles.content}>
                {loading ? (
                    <View style={styles.centerContainer}>
                        <ActivityIndicator size="large" color="#4e54c8" />
                        <Text style={styles.loadingText}>Loading summary...</Text>
                    </View>
                ) : error ? (
                    <View style={styles.centerContainer}>
                        <Ionicons name="alert-circle" size={48} color="#EA4335" />
                        <Text style={styles.errorText}>{error}</Text>
                        <TouchableOpacity style={styles.retryButton} onPress={loadSummary}>
                            <Text style={styles.retryText}>Retry</Text>
                        </TouchableOpacity>
                    </View>
                ) : summary ? (
                    <View>
                        {summary.ai_summary && (
                            <View style={styles.summaryCard}>
                                <View style={styles.summaryHeader}>
                                    <Ionicons name="sparkles" size={20} color="#4e54c8" />
                                    <Text style={styles.summaryTitle}>AI-Generated Summary</Text>
                                </View>
                                <Text style={styles.summaryText}>{summary.ai_summary}</Text>
                            </View>
                        )}

                        {summary.demographics && (
                            <>
                                <Text style={styles.sectionTitle}>Demographics</Text>
                                <View style={styles.infoCard}>
                                    <View style={styles.infoRow}>
                                        <Text style={styles.infoLabel}>Age:</Text>
                                        <Text style={styles.infoValue}>{summary.demographics.age}</Text>
                                    </View>
                                    <View style={styles.infoRow}>
                                        <Text style={styles.infoLabel}>Gender:</Text>
                                        <Text style={styles.infoValue}>{summary.demographics.gender}</Text>
                                    </View>
                                    {summary.demographics.blood_type && (
                                        <View style={styles.infoRow}>
                                            <Text style={styles.infoLabel}>Blood Type:</Text>
                                            <Text style={styles.infoValue}>{summary.demographics.blood_type}</Text>
                                        </View>
                                    )}
                                </View>
                            </>
                        )}

                        {summary.conditions && summary.conditions.length > 0 && (
                            <>
                                <Text style={styles.sectionTitle}>Medical Conditions</Text>
                                {summary.conditions.map((condition: any, index: number) =>
                                    renderConditionCard(condition, index)
                                )}
                            </>
                        )}

                        {summary.medications && summary.medications.length > 0 && (
                            <>
                                <Text style={styles.sectionTitle}>Current Medications</Text>
                                {summary.medications.map((medication: any, index: number) =>
                                    renderMedicationCard(medication, index)
                                )}
                            </>
                        )}

                        {summary.allergies && summary.allergies.length > 0 && (
                            <>
                                <Text style={styles.sectionTitle}>Allergies</Text>
                                <View style={styles.allergiesContainer}>
                                    {summary.allergies.map((allergy: string, index: number) => (
                                        <View key={index} style={styles.allergyBadge}>
                                            <Ionicons name="warning" size={14} color="#EA4335" />
                                            <Text style={styles.allergyText}>{allergy}</Text>
                                        </View>
                                    ))}
                                </View>
                            </>
                        )}

                        {summary.risk_factors && summary.risk_factors.length > 0 && (
                            <>
                                <Text style={styles.sectionTitle}>Risk Factors</Text>
                                {summary.risk_factors.map((factor: string, index: number) => (
                                    <View key={index} style={styles.riskFactorItem}>
                                        <Ionicons name="alert-circle" size={16} color="#ff9800" />
                                        <Text style={styles.riskFactorText}>{factor}</Text>
                                    </View>
                                ))}
                            </>
                        )}
                    </View>
                ) : (
                    <View style={styles.centerContainer}>
                        <Text style={styles.emptyText}>No patient data available</Text>
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
    summaryCard: {
        backgroundColor: '#E8EAF6',
        borderRadius: 12,
        padding: 15,
        marginBottom: 20,
        borderLeftWidth: 4,
        borderLeftColor: '#4e54c8',
    },
    summaryHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: 10,
    },
    summaryTitle: {
        fontSize: 16,
        fontWeight: 'bold',
        color: '#333',
        marginLeft: 8,
    },
    summaryText: {
        fontSize: 14,
        color: '#555',
        lineHeight: 22,
    },
    sectionTitle: {
        fontSize: 18,
        fontWeight: 'bold',
        color: '#333',
        marginTop: 15,
        marginBottom: 10,
    },
    infoCard: {
        backgroundColor: '#fff',
        borderRadius: 12,
        padding: 15,
        marginBottom: 10,
    },
    infoRow: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        paddingVertical: 8,
        borderBottomWidth: 1,
        borderBottomColor: '#f0f0f0',
    },
    infoLabel: {
        fontSize: 14,
        color: '#666',
        fontWeight: '500',
    },
    infoValue: {
        fontSize: 14,
        color: '#333',
        fontWeight: '600',
    },
    conditionCard: {
        backgroundColor: '#fff',
        borderRadius: 12,
        padding: 15,
        marginBottom: 10,
        borderLeftWidth: 3,
        borderLeftColor: '#e91e63',
    },
    conditionHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: 8,
    },
    conditionName: {
        fontSize: 16,
        fontWeight: '600',
        color: '#333',
        marginLeft: 10,
        flex: 1,
    },
    conditionDetail: {
        fontSize: 13,
        color: '#666',
        marginBottom: 5,
    },
    severityBadge: {
        alignSelf: 'flex-start',
        paddingHorizontal: 10,
        paddingVertical: 4,
        borderRadius: 12,
        marginTop: 5,
    },
    severityText: {
        fontSize: 11,
        fontWeight: 'bold',
        textTransform: 'uppercase',
    },
    medicationCard: {
        backgroundColor: '#fff',
        borderRadius: 12,
        padding: 15,
        marginBottom: 10,
        borderLeftWidth: 3,
        borderLeftColor: '#2196f3',
    },
    medicationHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: 8,
    },
    medicationName: {
        fontSize: 16,
        fontWeight: '600',
        color: '#333',
        marginLeft: 10,
    },
    medicationDetail: {
        fontSize: 14,
        color: '#555',
        marginBottom: 5,
    },
    medicationPrescriber: {
        fontSize: 12,
        color: '#888',
    },
    allergiesContainer: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: 10,
    },
    allergyBadge: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: '#FFEBEE',
        paddingHorizontal: 12,
        paddingVertical: 8,
        borderRadius: 20,
        gap: 6,
    },
    allergyText: {
        fontSize: 13,
        color: '#EA4335',
        fontWeight: '500',
    },
    riskFactorItem: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: '#fff',
        borderRadius: 8,
        padding: 12,
        marginBottom: 8,
        gap: 10,
    },
    riskFactorText: {
        fontSize: 14,
        color: '#555',
        flex: 1,
    },
    emptyText: {
        color: '#888',
        fontSize: 16,
        fontStyle: 'italic',
    },
});
