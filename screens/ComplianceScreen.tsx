import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { apiClient, AuditLogEntry } from '../services/apiClient';

export default function ComplianceScreen({ navigation }: any) {
    const [logs, setLogs] = useState<AuditLogEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadAuditLogs();
    }, []);

    const loadAuditLogs = async () => {
        try {
            setLoading(true);
            // In a real app, we would get the current user ID from context
            const data = await apiClient.getAuditLog('current_user', 50);
            setLogs(data);
            setError(null);
        } catch (err) {
            console.error('Failed to load audit logs:', err);
            setError('Failed to load audit logs. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const getActionColor = (action: string) => {
        switch (action) {
            case 'read': return '#4e54c8';
            case 'write': return '#25D366';
            case 'delete': return '#EA4335';
            case 'export': return '#F9A825';
            default: return '#888';
        }
    };

    const formatDate = (dateString: string) => {
        return new Date(dateString).toLocaleString();
    };

    return (
        <SafeAreaView style={styles.container}>
            <LinearGradient colors={['#1a1a2e', '#16213e']} style={styles.header}>
                <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color="#fff" />
                </TouchableOpacity>
                <Text style={styles.headerTitle}>Compliance Audit Log</Text>
                <View style={{ width: 24 }} />
            </LinearGradient>

            <View style={styles.content}>
                {loading ? (
                    <View style={styles.centerContainer}>
                        <ActivityIndicator size="large" color="#4e54c8" />
                        <Text style={styles.loadingText}>Loading audit records...</Text>
                    </View>
                ) : error ? (
                    <View style={styles.centerContainer}>
                        <Ionicons name="alert-circle" size={48} color="#EA4335" />
                        <Text style={styles.errorText}>{error}</Text>
                        <TouchableOpacity style={styles.retryButton} onPress={loadAuditLogs}>
                            <Text style={styles.retryText}>Retry</Text>
                        </TouchableOpacity>
                    </View>
                ) : (
                    <ScrollView style={styles.logList}>
                        <View style={styles.tableHeader}>
                            <Text style={[styles.headerCell, { flex: 2 }]}>Timestamp</Text>
                            <Text style={[styles.headerCell, { flex: 1 }]}>Action</Text>
                            <Text style={[styles.headerCell, { flex: 2 }]}>Resource</Text>
                        </View>

                        {logs.length === 0 ? (
                            <View style={styles.emptyContainer}>
                                <Text style={styles.emptyText}>No audit records found.</Text>
                            </View>
                        ) : (
                            logs.map((log) => (
                                <View key={log.id} style={styles.logRow}>
                                    <View style={styles.rowMain}>
                                        <Text style={[styles.cellText, { flex: 2, fontSize: 12, color: '#666' }]}>
                                            {formatDate(log.timestamp)}
                                        </Text>
                                        <View style={{ flex: 1 }}>
                                            <View style={[styles.badge, { backgroundColor: getActionColor(log.action) + '20' }]}>
                                                <Text style={[styles.badgeText, { color: getActionColor(log.action) }]}>
                                                    {log.action.toUpperCase()}
                                                </Text>
                                            </View>
                                        </View>
                                        <Text style={[styles.cellText, { flex: 2, fontWeight: '500' }]}>
                                            {log.resource_type}
                                        </Text>
                                    </View>
                                    {log.details && (
                                        <View style={styles.detailsContainer}>
                                            <Text style={styles.detailsText}>
                                                {JSON.stringify(log.details)}
                                            </Text>
                                        </View>
                                    )}
                                </View>
                            ))
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
    content: {
        flex: 1,
        padding: 15,
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
    logList: {
        flex: 1,
    },
    tableHeader: {
        flexDirection: 'row',
        paddingVertical: 10,
        borderBottomWidth: 1,
        borderBottomColor: '#ddd',
        marginBottom: 10,
    },
    headerCell: {
        fontWeight: 'bold',
        color: '#444',
    },
    logRow: {
        backgroundColor: '#fff',
        borderRadius: 8,
        padding: 12,
        marginBottom: 10,
        elevation: 1,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.1,
        shadowRadius: 1,
    },
    rowMain: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: 5,
    },
    cellText: {
        color: '#333',
    },
    badge: {
        paddingHorizontal: 8,
        paddingVertical: 2,
        borderRadius: 4,
        alignSelf: 'flex-start',
    },
    badgeText: {
        fontSize: 10,
        fontWeight: 'bold',
    },
    detailsContainer: {
        marginTop: 5,
        paddingTop: 5,
        borderTopWidth: 1,
        borderTopColor: '#eee',
    },
    detailsText: {
        fontSize: 11,
        color: '#888',
        fontFamily: 'monospace',
    },
    emptyContainer: {
        padding: 20,
        alignItems: 'center',
    },
    emptyText: {
        color: '#888',
        fontStyle: 'italic',
    },
});
