import React, { useState, useEffect } from 'react';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    ScrollView,
    ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { apiClient } from '../services/apiClient';

export default function SmartWatchScreen({ navigation }: any) {
    const [loading, setLoading] = useState(false);
    const [vitals, setVitals] = useState<any>(null);
    const [deviceStatus, setDeviceStatus] = useState('Connected');
    const [isLive, setIsLive] = useState(false);

    useEffect(() => {
        loadVitals();

        // WebSocket connection
        const wsUrl = apiClient.getWebSocketUrl('/api/smartwatch/stream/mock_device_id');
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log('Connected to smartwatch stream');
            setIsLive(true);
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'vitals') {
                    setVitals((prev: any) => ({
                        ...prev,
                        ...data.payload
                    }));
                }
            } catch (e) {
                console.error('WS parse error:', e);
            }
        };

        ws.onclose = () => {
            setIsLive(false);
        };

        return () => {
            ws.close();
        };
    }, []);

    const loadVitals = async () => {
        setLoading(true);
        try {
            // Get device ID from storage
            const devicesRaw = localStorage.getItem('connected_devices');
            let deviceId = 'mock_device_id';

            if (devicesRaw) {
                const devices = JSON.parse(devicesRaw);
                const activeWatch = devices.find((d: any) => d.status === 'connected' && d.type === 'watch');
                if (activeWatch) {
                    deviceId = activeWatch.id;
                    setDeviceStatus('Connected');
                } else {
                    setDeviceStatus('Disconnected');
                    // We can still try to load data or return early
                }
            }

            // Fetch metrics in parallel
            const [hrData, stepsData, spo2Data] = await Promise.all([
                apiClient.getAggregatedVitals(deviceId, 'hr', 'day'),
                apiClient.getAggregatedVitals(deviceId, 'steps', 'day'),
                apiClient.getAggregatedVitals(deviceId, 'spo2', 'day'),
            ]);

            // Helper to get latest value
            const getValue = (data: any) => {
                if (data && data.data && data.data.length > 0) {
                    return data.data[data.data.length - 1].value;
                }
                return 0;
            };

            setVitals({
                heart_rate: Math.round(getValue(hrData)),
                steps: Math.round(getValue(stepsData)),
                calories: 0, // Not supported by backend yet
                sleep: '0h 0m', // Not supported by backend yet
                spo2: Math.round(getValue(spo2Data)),
            });
        } catch (error) {
            console.error('Load vitals error:', error);
            // Keep empty state on error
            setVitals(null);
        } finally {
            setLoading(false);
        }
    };

    const renderVitalCard = (icon: any, title: string, value: string, unit: string, color: string) => (
        <View style={styles.vitalCard}>
            <View style={[styles.iconContainer, { backgroundColor: color + '20' }]}>
                <Ionicons name={icon} size={24} color={color} />
            </View>
            <View style={styles.vitalInfo}>
                <Text style={styles.vitalTitle}>{title}</Text>
                <View style={styles.valueContainer}>
                    <Text style={styles.vitalValue}>{value}</Text>
                    <Text style={styles.vitalUnit}>{unit}</Text>
                </View>
            </View>
        </View>
    );

    return (
        <SafeAreaView style={styles.container}>
            <LinearGradient colors={['#1a1a2e', '#16213e']} style={styles.header}>
                <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color="#fff" />
                </TouchableOpacity>
                <Text style={styles.headerTitle}>Smart Watch</Text>
                <View style={styles.statusContainer}>
                    <View style={[styles.statusDot, { backgroundColor: isLive ? '#4caf50' : '#888' }]} />
                    <Text style={styles.statusText}>{isLive ? 'Live Stream' : deviceStatus}</Text>
                </View>
            </LinearGradient>

            <ScrollView style={styles.content}>
                <View style={styles.deviceCard}>
                    <LinearGradient
                        colors={['#2c3e50', '#3498db']}
                        style={styles.deviceGradient}
                    >
                        <View>
                            <Text style={styles.deviceName}>Apple Watch Series 8</Text>
                            <Text style={styles.deviceBattery}>Battery: 78%</Text>
                        </View>
                        <Ionicons name="watch" size={48} color="rgba(255,255,255,0.8)" />
                    </LinearGradient>
                </View>

                <Text style={styles.sectionTitle}>Today's Vitals</Text>

                {loading ? (
                    <ActivityIndicator size="large" color="#4e54c8" style={{ marginTop: 50 }} />
                ) : vitals ? (
                    <View style={styles.grid}>
                        {renderVitalCard('heart', 'Heart Rate', vitals.heart_rate, 'BPM', '#e91e63')}
                        {renderVitalCard('walk', 'Steps', vitals.steps.toLocaleString(), 'steps', '#2196f3')}
                        {renderVitalCard('flame', 'Calories', vitals.calories, 'kcal', '#ff9800')}
                        {renderVitalCard('moon', 'Sleep', vitals.sleep, '', '#673ab7')}
                        {renderVitalCard('water', 'SpO2', vitals.spo2, '%', '#00bcd4')}
                    </View>
                ) : (
                    <View style={styles.emptyState}>
                        <Text style={styles.emptyText}>No data available</Text>
                    </View>
                )}

                <TouchableOpacity style={styles.syncButton} onPress={loadVitals}>
                    <Text style={styles.syncButtonText}>Sync Now</Text>
                </TouchableOpacity>
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
    statusContainer: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: 'rgba(255,255,255,0.1)',
        paddingHorizontal: 10,
        paddingVertical: 5,
        borderRadius: 15,
    },
    statusDot: {
        width: 8,
        height: 8,
        borderRadius: 4,
        marginRight: 6,
    },
    statusText: {
        color: '#fff',
        fontSize: 12,
        fontWeight: '500',
    },
    content: {
        flex: 1,
        padding: 20,
    },
    deviceCard: {
        borderRadius: 15,
        overflow: 'hidden',
        marginBottom: 25,
        elevation: 4,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.2,
        shadowRadius: 4,
    },
    deviceGradient: {
        padding: 20,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
    },
    deviceName: {
        color: '#fff',
        fontSize: 18,
        fontWeight: 'bold',
        marginBottom: 5,
    },
    deviceBattery: {
        color: 'rgba(255,255,255,0.9)',
        fontSize: 14,
    },
    sectionTitle: {
        fontSize: 18,
        fontWeight: 'bold',
        color: '#333',
        marginBottom: 15,
    },
    grid: {
        gap: 15,
    },
    vitalCard: {
        flexDirection: 'row',
        backgroundColor: '#fff',
        padding: 15,
        borderRadius: 12,
        alignItems: 'center',
        elevation: 2,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.1,
        shadowRadius: 2,
    },
    iconContainer: {
        width: 50,
        height: 50,
        borderRadius: 25,
        alignItems: 'center',
        justifyContent: 'center',
        marginRight: 15,
    },
    vitalInfo: {
        flex: 1,
    },
    vitalTitle: {
        fontSize: 14,
        color: '#666',
        marginBottom: 4,
    },
    valueContainer: {
        flexDirection: 'row',
        alignItems: 'baseline',
    },
    vitalValue: {
        fontSize: 24,
        fontWeight: 'bold',
        color: '#333',
        marginRight: 5,
    },
    vitalUnit: {
        fontSize: 14,
        color: '#888',
    },
    emptyState: {
        alignItems: 'center',
        padding: 30,
    },
    emptyText: {
        color: '#999',
        fontSize: 16,
    },
    syncButton: {
        marginTop: 30,
        backgroundColor: '#fff',
        padding: 15,
        borderRadius: 10,
        alignItems: 'center',
        borderWidth: 1,
        borderColor: '#ddd',
    },
    syncButtonText: {
        color: '#333',
        fontWeight: '600',
        fontSize: 16,
    },
});
