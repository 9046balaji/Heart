import React, { useState } from 'react';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    TextInput,
    ScrollView,
    ActivityIndicator,
    Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { apiClient } from '../services/apiClient';

export default function KnowledgeGraphScreen({ navigation }: any) {
    const [query, setQuery] = useState('');
    const [loading, setLoading] = useState(false);
    const [results, setResults] = useState<any>(null);
    const [mode, setMode] = useState<'search' | 'rag'>('search');
    const [ragAnswer, setRagAnswer] = useState<any>(null);

    const handleSearch = async () => {
        if (!query.trim()) return;

        setLoading(true);
        try {
            if (mode === 'search') {
                const response = await apiClient.searchGraph(query);
                setResults(response);
                setRagAnswer(null);
            } else {
                const response = await apiClient.ragQuery(query);
                setRagAnswer(response);
                setResults(null);
            }
        } catch (error) {
            console.error('Search error:', error);
            Alert.alert('Error', `Failed to ${mode === 'search' ? 'search' : 'query'} knowledge graph`);
        } finally {
            setLoading(false);
        }
    };

    const renderNode = (node: any, index: number) => (
        <View key={index} style={styles.nodeCard}>
            <View style={[styles.nodeIcon, { backgroundColor: getNodeColor(node.label) }]}>
                <Text style={styles.nodeIconText}>{node.label[0]}</Text>
            </View>
            <View style={styles.nodeInfo}>
                <Text style={styles.nodeTitle}>{node.properties.name || node.id}</Text>
                <Text style={styles.nodeType}>{node.label}</Text>
                {Object.entries(node.properties).map(([key, value]: [string, any], i) => (
                    key !== 'name' && (
                        <Text key={i} style={styles.nodeProp}>
                            {key}: {String(value)}
                        </Text>
                    )
                ))}
            </View>
        </View>
    );

    const getNodeColor = (label: string) => {
        switch (label.toLowerCase()) {
            case 'condition': return '#e91e63';
            case 'symptom': return '#ff9800';
            case 'medication': return '#2196f3';
            case 'treatment': return '#4caf50';
            default: return '#9c27b0';
        }
    };

    return (
        <SafeAreaView style={styles.container}>
            <LinearGradient colors={['#1a1a2e', '#16213e']} style={styles.header}>
                <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color="#fff" />
                </TouchableOpacity>
                <Text style={styles.headerTitle}>Knowledge Graph</Text>
                <View style={{ width: 24 }} />
            </LinearGradient>

            <View style={styles.searchSection}>
                <View style={styles.searchBar}>
                    <Ionicons name="search" size={20} color="#666" />
                    <TextInput
                        style={styles.input}
                        placeholder="Search medical knowledge..."
                        value={query}
                        onChangeText={setQuery}
                        onSubmitEditing={handleSearch}
                        returnKeyType="search"
                    />
                    {query.length > 0 && (
                        <TouchableOpacity onPress={() => setQuery('')}>
                            <Ionicons name="close-circle" size={20} color="#ccc" />
                        </TouchableOpacity>
                    )}
                </View>
                <View style={styles.modeToggle}>
                    <TouchableOpacity
                        style={[styles.modeButton, mode === 'search' && styles.modeButtonActive]}
                        onPress={() => setMode('search')}
                    >
                        <Text style={[styles.modeText, mode === 'search' && styles.modeTextActive]}>Search</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                        style={[styles.modeButton, mode === 'rag' && styles.modeButtonActive]}
                        onPress={() => setMode('rag')}
                    >
                        <Text style={[styles.modeText, mode === 'rag' && styles.modeTextActive]}>RAG Query</Text>
                    </TouchableOpacity>
                </View>
            </View>

            <ScrollView style={styles.content}>
                {loading ? (
                    <ActivityIndicator size="large" color="#4e54c8" style={{ marginTop: 50 }} />
                ) : results ? (
                    <View>
                        <Text style={styles.resultCount}>
                            Found {results.nodes.length} nodes and {results.relationships.length} relationships
                        </Text>

                        <Text style={styles.sectionTitle}>Nodes</Text>
                        {results.nodes.map((node: any, index: number) => renderNode(node, index))}

                        {results.relationships.length > 0 && (
                            <>
                                <Text style={[styles.sectionTitle, { marginTop: 20 }]}>Relationships</Text>
                                {results.relationships.map((rel: any, index: number) => (
                                    <View key={index} style={styles.relCard}>
                                        <Text style={styles.relText}>
                                            {rel.from} <Ionicons name="arrow-forward" size={14} /> {rel.type} <Ionicons name="arrow-forward" size={14} /> {rel.to}
                                        </Text>
                                    </View>
                                ))}
                            </>
                        )}
                    </View>
                ) : ragAnswer ? (
                    <View>
                        <View style={styles.answerCard}>
                            <View style={styles.answerHeader}>
                                <Ionicons name="bulb" size={20} color="#4e54c8" />
                                <Text style={styles.answerTitle}>Answer</Text>
                            </View>
                            <Text style={styles.answerText}>{ragAnswer.answer}</Text>
                        </View>
                        {ragAnswer.context && ragAnswer.context.length > 0 && (
                            <>
                                <Text style={styles.sectionTitle}>Context Sources</Text>
                                {ragAnswer.context.map((ctx: any, index: number) => (
                                    <View key={index} style={styles.contextCard}>
                                        <Text style={styles.contextText}>{ctx.text || ctx.content || JSON.stringify(ctx)}</Text>
                                    </View>
                                ))}
                            </>
                        )}
                    </View>
                ) : (
                    <View style={styles.emptyState}>
                        <Ionicons name="share-social-outline" size={64} color="#ddd" />
                        <Text style={styles.emptyText}>
                            {mode === 'search'
                                ? 'Explore connections between symptoms, conditions, and treatments'
                                : 'Ask questions and get contextual answers from the knowledge graph'}
                        </Text>
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
    searchSection: {
        padding: 15,
        backgroundColor: '#fff',
        elevation: 2,
    },
    searchBar: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: '#f5f5f5',
        borderRadius: 10,
        paddingHorizontal: 15,
        height: 45,
    },
    input: {
        flex: 1,
        marginLeft: 10,
        fontSize: 16,
        color: '#333',
    },
    content: {
        flex: 1,
        padding: 20,
    },
    resultCount: {
        fontSize: 14,
        color: '#666',
        marginBottom: 15,
    },
    sectionTitle: {
        fontSize: 18,
        fontWeight: 'bold',
        color: '#333',
        marginBottom: 10,
    },
    nodeCard: {
        flexDirection: 'row',
        backgroundColor: '#fff',
        padding: 15,
        borderRadius: 12,
        marginBottom: 10,
        elevation: 1,
    },
    nodeIcon: {
        width: 40,
        height: 40,
        borderRadius: 20,
        alignItems: 'center',
        justifyContent: 'center',
        marginRight: 15,
    },
    nodeIconText: {
        color: '#fff',
        fontSize: 18,
        fontWeight: 'bold',
    },
    nodeInfo: {
        flex: 1,
    },
    nodeTitle: {
        fontSize: 16,
        fontWeight: '600',
        color: '#333',
        marginBottom: 2,
    },
    nodeType: {
        fontSize: 12,
        color: '#666',
        marginBottom: 5,
        textTransform: 'uppercase',
        fontWeight: '500',
    },
    nodeProp: {
        fontSize: 12,
        color: '#888',
    },
    relCard: {
        backgroundColor: '#fff',
        padding: 12,
        borderRadius: 8,
        marginBottom: 8,
        borderLeftWidth: 3,
        borderLeftColor: '#4e54c8',
    },
    relText: {
        fontSize: 14,
        color: '#555',
    },
    emptyState: {
        alignItems: 'center',
        justifyContent: 'center',
        marginTop: 80,
        padding: 40,
    },
    emptyText: {
        marginTop: 20,
        textAlign: 'center',
        color: '#999',
        fontSize: 16,
        lineHeight: 24,
    },
    modeToggle: {
        flexDirection: 'row',
        marginTop: 10,
        borderRadius: 8,
        backgroundColor: '#f0f0f0',
        padding: 3,
    },
    modeButton: {
        flex: 1,
        paddingVertical: 8,
        alignItems: 'center',
        borderRadius: 6,
    },
    modeButtonActive: {
        backgroundColor: '#4e54c8',
    },
    modeText: {
        fontSize: 14,
        color: '#666',
        fontWeight: '600',
    },
    modeTextActive: {
        color: '#fff',
    },
    answerCard: {
        backgroundColor: '#fff',
        padding: 20,
        borderRadius: 12,
        marginBottom: 20,
        elevation: 2,
        borderLeftWidth: 4,
        borderLeftColor: '#4e54c8',
    },
    answerHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: 12,
    },
    answerTitle: {
        fontSize: 16,
        fontWeight: 'bold',
        color: '#333',
        marginLeft: 8,
    },
    answerText: {
        fontSize: 15,
        color: '#444',
        lineHeight: 22,
    },
    contextCard: {
        backgroundColor: '#f9f9f9',
        padding: 12,
        borderRadius: 8,
        marginBottom: 10,
        borderLeftWidth: 2,
        borderLeftColor: '#ddd',
    },
    contextText: {
        fontSize: 13,
        color: '#666',
        lineHeight: 18,
    },
});
