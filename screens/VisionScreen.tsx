import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    ScrollView,
    Image,
    ActivityIndicator,
    Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import * as ImagePicker from 'expo-image-picker';
import { apiClient } from '../services/apiClient';

type Tab = 'ecg' | 'food';

export default function VisionScreen() {
    const navigate = useNavigate();
    const [activeTab, setActiveTab] = useState<Tab>('ecg');
    const [loading, setLoading] = useState(false);
    const [image, setImage] = useState<string | null>(null);
    const [result, setResult] = useState<any>(null);

    const pickImage = async () => {
        const result = await ImagePicker.launchImageLibraryAsync({
            mediaTypes: ImagePicker.MediaTypeOptions.Images,
            allowsEditing: true,
            aspect: [4, 3],
            quality: 1,
        });

        if (!result.canceled) {
            setImage(result.assets[0].uri);
            setResult(null);
        }
    };

    const analyzeImage = async () => {
        if (!image) return;

        setLoading(true);
        try {
            // Create file object
            const filename = image.split('/').pop() || 'image.jpg';
            const match = /\.(\w+)$/.exec(filename);
            const type = match ? `image/${match[1]}` : 'image/jpeg';

            const file = {
                uri: image,
                name: filename,
                type,
            } as any;

            let response;
            if (activeTab === 'ecg') {
                response = await apiClient.analyzeECG(file);
            } else {
                response = await apiClient.recognizeFood(file);
            }

            setResult(response);
        } catch (error) {
            console.error('Analysis error:', error);
            Alert.alert('Error', 'Failed to analyze image');
        } finally {
            setLoading(false);
        }
    };

    const renderECGResult = () => {
        if (!result) return null;
        return (
            <View style={styles.resultContainer}>
                <Text style={styles.resultTitle}>ECG Analysis</Text>
                <View style={styles.resultRow}>
                    <Text style={styles.label}>Rhythm:</Text>
                    <Text style={styles.value}>{result.rhythm}</Text>
                </View>
                <View style={styles.resultRow}>
                    <Text style={styles.label}>Heart Rate:</Text>
                    <Text style={styles.value}>{result.heart_rate_bpm} BPM</Text>
                </View>
                <Text style={styles.subTitle}>Abnormalities:</Text>
                {result.abnormalities.map((item: string, index: number) => (
                    <Text key={index} style={styles.listItem}>• {item}</Text>
                ))}
            </View>
        );
    };

    const renderFoodResult = () => {
        if (!result) return null;
        return (
            <View style={styles.resultContainer}>
                <Text style={styles.resultTitle}>Food Analysis</Text>
                <View style={styles.resultRow}>
                    <Text style={styles.label}>Calories:</Text>
                    <Text style={styles.value}>{result.total_calories} kcal</Text>
                </View>
                <Text style={styles.subTitle}>Items:</Text>
                {result.food_items.map((item: any, index: number) => (
                    <Text key={index} style={styles.listItem}>
                        • {item.name} ({item.calories} kcal)
                    </Text>
                ))}
            </View>
        );
    };

    return (
        <SafeAreaView style={styles.container}>
            <LinearGradient colors={['#1a1a2e', '#16213e']} style={styles.header}>
                <TouchableOpacity onPress={() => navigate(-1)} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color="#fff" />
                </TouchableOpacity>
                <Text style={styles.headerTitle}>Vision Analysis</Text>
                <View style={{ width: 24 }} />
            </LinearGradient>

            <View style={styles.tabs}>
                <TouchableOpacity
                    style={[styles.tab, activeTab === 'ecg' && styles.activeTab]}
                    onPress={() => { setActiveTab('ecg'); setImage(null); setResult(null); }}
                >
                    <Text style={[styles.tabText, activeTab === 'ecg' && styles.activeTabText]}>ECG</Text>
                </TouchableOpacity>
                <TouchableOpacity
                    style={[styles.tab, activeTab === 'food' && styles.activeTab]}
                    onPress={() => { setActiveTab('food'); setImage(null); setResult(null); }}
                >
                    <Text style={[styles.tabText, activeTab === 'food' && styles.activeTabText]}>Food</Text>
                </TouchableOpacity>
            </View>

            <ScrollView style={styles.content}>
                <View style={styles.uploadArea}>
                    {image ? (
                        <Image source={{ uri: image }} style={styles.previewImage} />
                    ) : (
                        <TouchableOpacity style={styles.placeholder} onPress={pickImage}>
                            <Ionicons name="camera" size={48} color="#ccc" />
                            <Text style={styles.placeholderText}>Tap to select image</Text>
                        </TouchableOpacity>
                    )}
                </View>

                {image && (
                    <TouchableOpacity
                        style={styles.analyzeButton}
                        onPress={analyzeImage}
                        disabled={loading}
                    >
                        <LinearGradient
                            colors={['#4e54c8', '#8f94fb']}
                            style={styles.gradientButton}
                        >
                            {loading ? (
                                <ActivityIndicator color="#fff" />
                            ) : (
                                <Text style={styles.buttonText}>Analyze {activeTab.toUpperCase()}</Text>
                            )}
                        </LinearGradient>
                    </TouchableOpacity>
                )}

                {activeTab === 'ecg' ? renderECGResult() : renderFoodResult()}
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
    tabs: {
        flexDirection: 'row',
        backgroundColor: '#fff',
        padding: 5,
        margin: 15,
        borderRadius: 10,
        elevation: 2,
    },
    tab: {
        flex: 1,
        paddingVertical: 12,
        alignItems: 'center',
        borderRadius: 8,
    },
    activeTab: {
        backgroundColor: '#e8f5e9',
    },
    tabText: {
        fontSize: 16,
        color: '#666',
        fontWeight: '500',
    },
    activeTabText: {
        color: '#2e7d32',
        fontWeight: 'bold',
    },
    content: {
        flex: 1,
        padding: 20,
    },
    uploadArea: {
        height: 250,
        backgroundColor: '#fff',
        borderRadius: 15,
        overflow: 'hidden',
        marginBottom: 20,
        elevation: 2,
    },
    previewImage: {
        width: '100%',
        height: '100%',
        resizeMode: 'cover',
    },
    placeholder: {
        flex: 1,
        alignItems: 'center',
        justifyContent: 'center',
        borderStyle: 'dashed',
        borderWidth: 2,
        borderColor: '#ddd',
        margin: 10,
        borderRadius: 10,
    },
    placeholderText: {
        marginTop: 10,
        color: '#999',
        fontSize: 16,
    },
    analyzeButton: {
        borderRadius: 15,
        overflow: 'hidden',
        marginBottom: 20,
        elevation: 5,
    },
    gradientButton: {
        padding: 18,
        alignItems: 'center',
    },
    buttonText: {
        color: '#fff',
        fontSize: 18,
        fontWeight: 'bold',
    },
    resultContainer: {
        backgroundColor: '#fff',
        padding: 20,
        borderRadius: 15,
        elevation: 2,
        marginBottom: 30,
    },
    resultTitle: {
        fontSize: 20,
        fontWeight: 'bold',
        color: '#333',
        marginBottom: 15,
    },
    resultRow: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        marginBottom: 10,
        paddingBottom: 10,
        borderBottomWidth: 1,
        borderBottomColor: '#f0f0f0',
    },
    label: {
        fontSize: 16,
        color: '#666',
    },
    value: {
        fontSize: 16,
        fontWeight: '600',
        color: '#333',
    },
    subTitle: {
        fontSize: 16,
        fontWeight: '600',
        color: '#333',
        marginTop: 10,
        marginBottom: 5,
    },
    listItem: {
        fontSize: 15,
        color: '#555',
        marginBottom: 5,
        paddingLeft: 10,
    },
});
