import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    ScrollView,
    ActivityIndicator,
    Alert,
    FlatList,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { apiClient } from '../services/apiClient';
import { useAuth } from '../hooks/useAuth';

export default function CalendarScreen() {
    const navigate = useNavigate();
    const { user } = useAuth();
    const [loading, setLoading] = useState(false);
    const [events, setEvents] = useState<any[]>([]);
    const [syncing, setSyncing] = useState(false);

    useEffect(() => {
        loadEvents();
    }, []);

    const loadEvents = async () => {
        if (!user) return;

        setLoading(true);
        try {
            const data = await apiClient.getCalendarEvents(user.id);
            setEvents(data);
        } catch (error) {
            console.error('Load events error:', error);
            Alert.alert('Error', 'Failed to load calendar events');
            setEvents([]);
        } finally {
            setLoading(false);
        }
    };

    const handleSync = async () => {
        if (!user) return;

        setSyncing(true);
        try {
            await apiClient.syncCalendar(user.id, { provider: 'google' });
            Alert.alert('Success', 'Calendar synced successfully');
            loadEvents();
        } catch (error) {
            console.error('Sync error:', error);
            Alert.alert('Error', 'Failed to sync calendar');
        } finally {
            setSyncing(false);
        }
    };

    const renderEvent = ({ item }: { item: any }) => (
        <View style={styles.eventCard}>
            <View style={styles.eventTime}>
                <Text style={styles.timeText}>
                    {new Date(item.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </Text>
                <Text style={styles.dateText}>
                    {new Date(item.start_time).toLocaleDateString()}
                </Text>
            </View>
            <View style={styles.eventDetails}>
                <Text style={styles.eventTitle}>{item.title}</Text>
                {item.location && (
                    <View style={styles.locationContainer}>
                        <Ionicons name="location-outline" size={14} color="#666" />
                        <Text style={styles.locationText}>{item.location}</Text>
                    </View>
                )}
            </View>
        </View>
    );

    return (
        <SafeAreaView style={styles.container}>
            <LinearGradient colors={['#1a1a2e', '#16213e']} style={styles.header}>
                <TouchableOpacity onPress={() => navigate(-1)} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color="#fff" />
                </TouchableOpacity>
                <Text style={styles.headerTitle}>Calendar</Text>
                <TouchableOpacity onPress={handleSync} disabled={syncing}>
                    {syncing ? (
                        <ActivityIndicator color="#fff" size="small" />
                    ) : (
                        <Ionicons name="sync" size={24} color="#fff" />
                    )}
                </TouchableOpacity>
            </LinearGradient>

            <View style={styles.content}>
                <View style={styles.summaryCard}>
                    <LinearGradient
                        colors={['#4e54c8', '#8f94fb']}
                        style={styles.summaryGradient}
                    >
                        <View>
                            <Text style={styles.summaryTitle}>Upcoming Events</Text>
                            <Text style={styles.summaryCount}>{events.length} events this week</Text>
                        </View>
                        <Ionicons name="calendar" size={40} color="rgba(255,255,255,0.8)" />
                    </LinearGradient>
                </View>

                <Text style={styles.sectionTitle}>Schedule</Text>

                {loading ? (
                    <ActivityIndicator size="large" color="#4e54c8" style={{ marginTop: 50 }} />
                ) : (
                    <FlatList
                        data={events}
                        renderItem={renderEvent}
                        keyExtractor={item => item.id}
                        contentContainerStyle={styles.listContent}
                        ListEmptyComponent={
                            <View style={styles.emptyState}>
                                <Text style={styles.emptyText}>No upcoming events</Text>
                            </View>
                        }
                    />
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
    content: {
        flex: 1,
        padding: 20,
    },
    summaryCard: {
        borderRadius: 15,
        overflow: 'hidden',
        marginBottom: 25,
        elevation: 4,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.2,
        shadowRadius: 4,
    },
    summaryGradient: {
        padding: 20,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
    },
    summaryTitle: {
        color: '#fff',
        fontSize: 18,
        fontWeight: 'bold',
        marginBottom: 5,
    },
    summaryCount: {
        color: 'rgba(255,255,255,0.9)',
        fontSize: 14,
    },
    sectionTitle: {
        fontSize: 18,
        fontWeight: 'bold',
        color: '#333',
        marginBottom: 15,
    },
    listContent: {
        paddingBottom: 20,
    },
    eventCard: {
        flexDirection: 'row',
        backgroundColor: '#fff',
        borderRadius: 12,
        marginBottom: 12,
        padding: 15,
        elevation: 2,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.1,
        shadowRadius: 2,
    },
    eventTime: {
        borderRightWidth: 1,
        borderRightColor: '#eee',
        paddingRight: 15,
        marginRight: 15,
        alignItems: 'center',
        justifyContent: 'center',
        minWidth: 70,
    },
    timeText: {
        fontSize: 16,
        fontWeight: 'bold',
        color: '#333',
    },
    dateText: {
        fontSize: 12,
        color: '#888',
        marginTop: 4,
    },
    eventDetails: {
        flex: 1,
        justifyContent: 'center',
    },
    eventTitle: {
        fontSize: 16,
        fontWeight: '600',
        color: '#333',
        marginBottom: 4,
    },
    locationContainer: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    locationText: {
        fontSize: 13,
        color: '#666',
        marginLeft: 4,
    },
    emptyState: {
        alignItems: 'center',
        marginTop: 50,
    },
    emptyText: {
        color: '#999',
        fontSize: 16,
    },
});
