import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AppError, ErrorType, getErrorIcon, getErrorColor } from '../utils/errorHandling';

interface ErrorDisplayProps {
    error: AppError | string;
    onRetry?: () => void;
    compact?: boolean;
}

/**
 * Reusable Error Display Component
 * Shows error messages with appropriate icons and retry buttons
 */
export default function ErrorDisplay({ error, onRetry, compact = false }: ErrorDisplayProps) {
    const appError = typeof error === 'string'
        ? {
            type: ErrorType.UNKNOWN,
            message: error,
            userMessage: error,
            retryable: !!onRetry
        }
        : error;

    const icon = getErrorIcon(appError.type);
    const color = getErrorColor(appError.type);

    if (compact) {
        return (
            <View style={styles.compactContainer}>
                <Ionicons name={icon as any} size={20} color={color} />
                <Text style={styles.compactText}>{appError.userMessage}</Text>
                {appError.retryable && onRetry && (
                    <TouchableOpacity onPress={onRetry} style={styles.compactRetry}>
                        <Ionicons name="refresh" size={16} color="#4e54c8" />
                    </TouchableOpacity>
                )}
            </View>
        );
    }

    return (
        <View style={styles.container}>
            <View style={[styles.iconCircle, { backgroundColor: color + '20' }]}>
                <Ionicons name={icon as any} size={48} color={color} />
            </View>
            <Text style={styles.message}>{appError.userMessage}</Text>
            {appError.retryable && onRetry && (
                <TouchableOpacity style={styles.retryButton} onPress={onRetry}>
                    <Ionicons name="refresh" size={20} color="#fff" style={styles.retryIcon} />
                    <Text style={styles.retryText}>Try Again</Text>
                </TouchableOpacity>
            )}
            {__DEV__ && appError.message !== appError.userMessage && (
                <Text style={styles.debugText}>Debug: {appError.message}</Text>
            )}
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        padding: 30,
    },
    iconCircle: {
        width: 100,
        height: 100,
        borderRadius: 50,
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: 20,
    },
    message: {
        fontSize: 16,
        color: '#666',
        textAlign: 'center',
        marginBottom: 20,
        lineHeight: 24,
        maxWidth: 300,
    },
    retryButton: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: '#4e54c8',
        paddingHorizontal: 24,
        paddingVertical: 12,
        borderRadius: 8,
        gap: 8,
    },
    retryIcon: {
        marginRight: 4,
    },
    retryText: {
        color: '#fff',
        fontSize: 16,
        fontWeight: '600',
    },
    debugText: {
        marginTop: 20,
        fontSize: 12,
        color: '#EA4335',
        fontFamily: 'monospace',
    },
    compactContainer: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: '#fff',
        padding: 12,
        borderRadius: 8,
        borderLeftWidth: 3,
        borderLeftColor: '#EA4335',
        gap: 10,
    },
    compactText: {
        flex: 1,
        fontSize: 14,
        color: '#666',
    },
    compactRetry: {
        padding: 4,
    },
});
