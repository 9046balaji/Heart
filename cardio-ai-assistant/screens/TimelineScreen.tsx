import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { apiClient, TimelineEvent } from '../services/apiClient';

export default function TimelineScreen({ navigation }: any) {
    const [events, setEvents] = useState<TimelineEvent[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [days, setDays] = useState(30);

    useEffect(() => {
        loadTimeline();
    }, [days]);

    const loadTimeline = async () => {
        try {
            setLoading(true);
            const data = await apiClient.getPatientTimeline('current_user', days);
            setEvents(data);
            setError(null);
        } catch (err) {
            console.error('Failed to load timeline:', err);
            setError('Failed to load timeline. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const getEventIcon = (type: string) => {
        switch (type) {
            case 'lab_result': return 'flask';
            case 'prescription': return 'medkit';
            case 'vital': return 'heart';
            case 'appointment': return 'calendar';
            case 'alert': return 'warning';
            default: return 'ellipse';
        }
    };

    const getEventColor = (type: string) => {
        switch (type) {
            case 'lab_result': return '#4e54c8';
            case 'prescription': return '#25D366';
            case 'vital': return '#EA4335';
            case 'appointment': return '#F9A825';
            case 'alert': return '#FF5722';
            default: return '#888';
        }
    };

    const formatDate = (dateString: string) => {
        const date = new Date(dateString);
        return {
            day: date.getDate(),
            month: date.toLocaleString('default', { month: 'short' }),
            time: date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
    };

    return (
        <SafeAreaView style={styles.container}>
            <LinearGradient colors={['#1a1a2e', '#16213e']} style={styles.header}>
                <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color="#fff" />
                </TouchableOpacity>
                <Text style={styles.headerTitle}>Patient Timeline</Text>
                <View style={{ width: 24 }} />
            </LinearGradient>

            <View style={styles.filterContainer}>
                {[7, 30, 90].map((d) => (
                    <TouchableOpacity
                        key={d}
                        style={[styles.filterButton, days === d && styles.filterButtonActive]}
                        onPress={() => setDays(d)}
                    >
                        <Text style={[styles.filterText, days === d && styles.filterTextActive]}>
                            {d} Days
                        </Text>
                    </TouchableOpacity>
                ))}
            </View>

            <View style={styles.content}>
                {loading ? (
                    <View style={styles.centerContainer}>
                        <ActivityIndicator size="large" color="#4e54c8" />
                        <Text style={styles.loadingText}>Loading timeline...</Text>
                    </View>
                ) : error ? (
                    <View style={styles.centerContainer}>
                        <Ionicons name="alert-circle" size={48} color="#EA4335" />
                        <Text style={styles.errorText}>{error}</Text>
                        <TouchableOpacity style={styles.retryButton} onPress={loadTimeline}>
                            <Text style={styles.retryText}>Retry</Text>
                        </TouchableOpacity>
                    </View>
                ) : (
                    <ScrollView style={styles.timelineList}>
                        {events.length === 0 ? (
                            <View style={styles.emptyContainer}>
                                <Text style={styles.emptyText}>No events found in this period.</Text>
                            </View>
                        ) : (
                            events.map((event, index) => {
                                const { day, month, time } = formatDate(event.timestamp);
                                const isLast = index === events.length - 1;
                                const color = getEventColor(event.event_type);

                                return (
                                    <View key={event.id} style={styles.timelineItem}>
                                        <View style={styles.dateColumn}>
                                            <Text style={styles.dateDay}>{day}</Text>
                                            <Text style={styles.dateMonth}>{month}</Text>
                                            <Text style={styles.dateTime}>{time}</Text>
                                        </View>

                                        <View style={styles.lineColumn}>
                                            <View style={[styles.dot, { backgroundColor: color }]} />
                                            {!isLast && <View style={styles.line} />}
                                        </View>

                                        <View style={styles.cardColumn}>
                                            <View style={styles.card}>
                                                <View style={styles.cardHeader}>
                                                    <View style={[styles.iconBox, { backgroundColor: color + '20' }]}>
                                                        <Ionicons name={getEventIcon(event.event_type) as any} size={16} color={color} />
                                                    </View>
                                                    <Text style={styles.cardTitle}>{event.title}</Text>
                                                </View>
                                                <Text style={styles.cardDescription}>{event.description}</Text>
                                                <View style={styles.cardFooter}>
                                                    <Text style={styles.sourceText}>Source: {event.source}</Text>
                                                    {event.verified && (
                                                        <View style={styles.verifiedBadge}>
                                                            <Ionicons name="checkmark-circle" size={12} color="#25D366" />
                                                            <Text style={styles.verifiedText}>Verified</Text>
                                                        </View>
                                                    )}
                                                </View>
                                            </View>
                                        </View>
                                    </View>
                                );
                            })
                        )}
                    </ScrollView>
                )}
            </View>
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
    filterContainer: {
        flexDirection: 'row',
        justifyContent: 'center',
        paddingVertical: 15,
        backgroundColor: '#fff',
        borderBottomWidth: 1,
        borderBottomColor: '#eee',
    },
    filterButton: {
        paddingHorizontal: 20,
        paddingVertical: 8,
        borderRadius: 20,
        marginHorizontal: 5,
        backgroundColor: '#f0f0f0',
    },
    filterButtonActive: {
        backgroundColor: '#4e54c8',
    },
    filterText: {
        color: '#666',
        fontWeight: '600',
    },
    filterTextActive: {
        color: '#fff',
    },
    content: {
        flex: 1,
    },
    centerContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
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
    timelineList: {
        padding: 20,
    },
    timelineItem: {
        flexDirection: 'row',
        marginBottom: 20,
    },
    dateColumn: {
        width: 50,
        alignItems: 'center',
        paddingTop: 5,
    },
    dateDay: {
        fontSize: 18,
        fontWeight: 'bold',
        color: '#333',
    },
    dateMonth: {
        fontSize: 12,
        color: '#666',
        textTransform: 'uppercase',
    },
    dateTime: {
        fontSize: 10,
        color: '#888',
        marginTop: 2,
    },
    lineColumn: {
        width: 30,
        alignItems: 'center',
    },
    dot: {
        width: 12,
        height: 12,
        borderRadius: 6,
        marginTop: 8,
        zIndex: 1,
    },
    line: {
        width: 2,
        flex: 1,
        backgroundColor: '#ddd',
        marginTop: -2,
    },
    cardColumn: {
        flex: 1,
    },
    card: {
        backgroundColor: '#fff',
        borderRadius: 12,
        padding: 15,
        elevation: 2,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.1,
        shadowRadius: 2,
    },
    cardHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: 8,
    },
    iconBox: {
        width: 28,
        height: 28,
        borderRadius: 14,
        alignItems: 'center',
        justifyContent: 'center',
        marginRight: 10,
    },
    cardTitle: {
        fontSize: 16,
        fontWeight: '600',
        color: '#333',
        flex: 1,
    },
    cardDescription: {
        fontSize: 14,
        color: '#555',
        marginBottom: 10,
        lineHeight: 20,
    },
    cardFooter: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderTopWidth: 1,
        borderTopColor: '#f0f0f0',
        paddingTop: 8,
    },
    sourceText: {
        fontSize: 11,
        color: '#888',
    },
    verifiedBadge: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 4,
    },
    verifiedText: {
        fontSize: 11,
        color: '#25D366',
        fontWeight: '500',
    },
    emptyContainer: {
        padding: 40,
        alignItems: 'center',
    },
    emptyText: {
        color: '#888',
        fontStyle: 'italic',
    },
});
