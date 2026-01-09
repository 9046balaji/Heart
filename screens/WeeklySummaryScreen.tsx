import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { apiClient } from '../services/apiClient';

export default function WeeklySummaryScreen({ navigation }: any) {
    const [loading, setLoading] = useState(true);
    const [summary, setSummary] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadSummary();
    }, []);

    const loadSummary = async () => {
        try {
            setLoading(true);
            const data = await apiClient.getWeeklySummary('current_user');
            setSummary(data);
            setError(null);
        } catch (err) {
            console.error('Failed to load weekly summary:', err);
            setError('Failed to load weekly summary. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const formatDate = (dateString: string) => {
        return new Date(dateString).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    };

    const renderStatCard = (icon: any, title: string, value: string | number, subtitle?: string, color: string = '#4e54c8') => (
        <View style={styles.statCard}>
            <View style={[styles.statIcon, { backgroundColor: color + '20' }]}>
                <Ionicons name={icon} size={24} color={color} />
            </View>
            <View style={styles.statInfo}>
                <Text style={styles.statTitle}>{title}</Text>
                <Text style={styles.statValue}>{value}</Text>
                {subtitle && <Text style={styles.statSubtitle}>{subtitle}</Text>}
            </View>
        </View>
    );

    return (
        <SafeAreaView style={styles.container}>
            <LinearGradient colors={['#1a1a2e', '#16213e']} style={styles.header}>
                <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color="#fff" />
                </TouchableOpacity>
                <Text style={styles.headerTitle}>Weekly Summary</Text>
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
                        <View style={styles.periodCard}>
                            <Text style={styles.periodTitle}>Summary Period</Text>
                            <Text style={styles.periodText}>
                                {formatDate(summary.week_start)} - {formatDate(summary.week_end)}
                            </Text>
                        </View>

                        {summary.personalized_tip && (
                            <View style={styles.tipCard}>
                                <View style={styles.tipHeader}>
                                    <Ionicons name="bulb" size={20} color="#F9A825" />
                                    <Text style={styles.tipTitle}>Personalized Tip</Text>
                                </View>
                                <Text style={styles.tipText}>{summary.personalized_tip}</Text>
                            </View>
                        )}

                        <Text style={styles.sectionTitle}>Health Stats</Text>
                        <View style={styles.statsGrid}>
                            {renderStatCard('heart', 'Avg Heart Rate', `${summary.health_stats?.avg_heart_rate || 0} BPM`, undefined, '#e91e63')}
                            {renderStatCard('walk', 'Total Steps', (summary.health_stats?.total_steps || 0).toLocaleString(),
                                `${summary.health_stats?.avg_steps_per_day || 0}/day avg`, '#2196f3')}
                            {renderStatCard('trophy', 'Goal Met', `${summary.health_stats?.steps_goal_met_days || 0} days`, undefined, '#4caf50')}
                        </View>

                        <Text style={styles.sectionTitle}>Nutrition</Text>
                        <View style={styles.statsGrid}>
                            {renderStatCard('restaurant', 'Daily Calories', Math.round(summary.nutrition?.avg_daily_calories || 0), undefined, '#ff9800')}
                            {renderStatCard('checkmark-circle', 'Target Met', `${summary.nutrition?.days_target_met || 0} days`,
                                `${Math.round(summary.nutrition?.compliance_percent || 0)}% compliance`, '#4caf50')}
                        </View>

                        <Text style={styles.sectionTitle}>Exercise</Text>
                        <View style={styles.statsGrid}>
                            {renderStatCard('fitness', 'Workouts', summary.exercise?.workouts_completed || 0, undefined, '#673ab7')}
                            {renderStatCard('time', 'Active Minutes', summary.exercise?.total_active_minutes || 0,
                                `${Math.round(summary.exercise?.goal_completion_percent || 0)}% of goal`, '#3f51b5')}
                            {renderStatCard('flame', 'Calories Burned', summary.exercise?.calories_burned || 0, undefined, '#ff5722')}
                        </View>

                        <Text style={styles.sectionTitle}>Medications</Text>
                        <View style={styles.medicationCard}>
                            <View style={styles.medicationHeader}>
                                <Text style={styles.medicationTitle}>Overall Compliance</Text>
                                <Text style={[styles.compliancePercent, {
                                    color: (summary.medications?.overall_compliance_percent || 0) >= 80 ? '#4caf50' : '#ff9800'
                                }]}>
                                    {Math.round(summary.medications?.overall_compliance_percent || 0)}%
                                </Text>
                            </View>
                            <Text style={styles.medicationStat}>
                                {summary.medications?.total_doses_taken || 0} taken, {summary.medications?.total_doses_missed || 0} missed
                            </Text>
                        </View>

                        {summary.highlights && summary.highlights.length > 0 && (
                            <>
                                <Text style={styles.sectionTitle}>Highlights</Text>
                                {summary.highlights.map((highlight: string, index: number) => (
                                    <View key={index} style={styles.listItem}>
                                        <Ionicons name="checkmark-circle" size={16} color="#4caf50" />
                                        <Text style={styles.listText}>{highlight}</Text>
                                    </View>
                                ))}
                            </>
                        )}

                        {summary.areas_for_improvement && summary.areas_for_improvement.length > 0 && (
                            <>
                                <Text style={styles.sectionTitle}>Areas for Improvement</Text>
                                {summary.areas_for_improvement.map((area: string, index: number) => (
                                    <View key={index} style={styles.listItem}>
                                        <Ionicons name="arrow-up-circle" size={16} color="#ff9800" />
                                        <Text style={styles.listText}>{area}</Text>
                                    </View>
                                ))}
                            </>
                        )}
                    </View>
                ) : (
                    <View style={styles.centerContainer}>
                        <Text style={styles.emptyText}>No summary data available</Text>
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
    periodCard: {
        backgroundColor: '#fff',
        borderRadius: 12,
        padding: 15,
        marginBottom: 15,
        borderLeftWidth: 4,
        borderLeftColor: '#4e54c8',
    },
    periodTitle: {
        fontSize: 12,
        color: '#666',
        textTransform: 'uppercase',
        fontWeight: '600',
        marginBottom: 5,
    },
    periodText: {
        fontSize: 16,
        color: '#333',
        fontWeight: '500',
    },
    tipCard: {
        backgroundColor: '#FFF9E6',
        borderRadius: 12,
        padding: 15,
        marginBottom: 20,
        borderLeftWidth: 4,
        borderLeftColor: '#F9A825',
    },
    tipHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: 8,
    },
    tipTitle: {
        fontSize: 14,
        fontWeight: 'bold',
        color: '#333',
        marginLeft: 8,
    },
    tipText: {
        fontSize: 14,
        color: '#555',
        lineHeight: 20,
    },
    sectionTitle: {
        fontSize: 18,
        fontWeight: 'bold',
        color: '#333',
        marginTop: 15,
        marginBottom: 10,
    },
    statsGrid: {
        gap: 10,
        marginBottom: 5,
    },
    statCard: {
        flexDirection: 'row',
        backgroundColor: '#fff',
        borderRadius: 12,
        padding: 15,
        alignItems: 'center',
    },
    statIcon: {
        width: 50,
        height: 50,
        borderRadius: 25,
        alignItems: 'center',
        justifyContent: 'center',
        marginRight: 15,
    },
    statInfo: {
        flex: 1,
    },
    statTitle: {
        fontSize: 13,
        color: '#666',
        marginBottom: 2,
    },
    statValue: {
        fontSize: 20,
        fontWeight: 'bold',
        color: '#333',
    },
    statSubtitle: {
        fontSize: 11,
        color: '#888',
        marginTop: 2,
    },
    medicationCard: {
        backgroundColor: '#fff',
        borderRadius: 12,
        padding: 15,
        marginBottom: 5,
    },
    medicationHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 8,
    },
    medicationTitle: {
        fontSize: 14,
        fontWeight: '600',
        color: '#333',
    },
    compliancePercent: {
        fontSize: 24,
        fontWeight: 'bold',
    },
    medicationStat: {
        fontSize: 13,
        color: '#666',
    },
    listItem: {
        flexDirection: 'row',
        alignItems: 'flex-start',
        backgroundColor: '#fff',
        borderRadius: 8,
        padding: 12,
        marginBottom: 8,
    },
    listText: {
        fontSize: 14,
        color: '#555',
        marginLeft: 10,
        flex: 1,
        lineHeight: 20,
    },
    emptyText: {
        color: '#888',
        fontSize: 16,
        fontStyle: 'italic',
    },
});
