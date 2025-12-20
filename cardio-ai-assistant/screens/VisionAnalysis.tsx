/**
 * VisionAnalysis Screen
 *
 * AI-powered vision analysis for ECG images and food recognition.
 *
 * Features:
 * - ECG Analysis Tab: Upload ECG strip images for rhythm analysis
 * - Food Recognition Tab: Upload meal photos for nutritional analysis
 * - Prominent medical disclaimers
 * - Confidence indicators
 * - Healthcare-grade error handling
 */

import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { visionService, VisionServiceError } from '../services/visionService';
import { ECGAnalysisResponse, FoodAnalysisResponse } from '../services/api.types';

type Tab = 'ecg' | 'food';
type AnalysisState = 'idle' | 'analyzing' | 'complete' | 'error';

interface ECGState {
    status: AnalysisState;
    result: ECGAnalysisResponse | null;
    error: string | null;
}

interface FoodState {
    status: AnalysisState;
    result: FoodAnalysisResponse | null;
    error: string | null;
    mealLogged: boolean;
}

/**
 * Convert service errors to user-friendly messages
 */
function getUserFriendlyError(error: unknown): string {
    if (error instanceof VisionServiceError) {
        return error.userMessage;
    }
    if (error instanceof Error) {
        console.error('[VisionAnalysis] Error:', error);
        return 'Could not analyze this image. Please try a clearer photo.';
    }
    return 'Something went wrong. Please try again.';
}

/**
 * Get confidence badge styling
 */
function getConfidenceBadge(confidence: number): { class: string; label: string } {
    if (confidence >= 0.8) {
        return { class: 'bg-green-100 text-green-700', label: 'High' };
    } else if (confidence >= 0.6) {
        return { class: 'bg-yellow-100 text-yellow-700', label: 'Medium' };
    }
    return { class: 'bg-orange-100 text-orange-700', label: 'Low' };
}

const VisionAnalysis: React.FC = () => {
    const navigate = useNavigate();
    const ecgFileRef = useRef<HTMLInputElement>(null);
    const foodFileRef = useRef<HTMLInputElement>(null);

    const [activeTab, setActiveTab] = useState<Tab>('ecg');
    const [patientContext, setPatientContext] = useState('');
    const [mealType, setMealType] = useState<'breakfast' | 'lunch' | 'dinner' | 'snack'>('lunch');

    const [ecgState, setECGState] = useState<ECGState>({
        status: 'idle',
        result: null,
        error: null,
    });

    const [foodState, setFoodState] = useState<FoodState>({
        status: 'idle',
        result: null,
        error: null,
        mealLogged: false,
    });

    const USER_ID = 'demo_user_123';

    // ============================================================================
    // ECG Analysis
    // ============================================================================

    const handleECGFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files || !e.target.files[0]) return;
        const file = e.target.files[0];

        setECGState({ status: 'analyzing', result: null, error: null });

        try {
            const result = await visionService.analyzeECG(file, patientContext || undefined);
            setECGState({ status: 'complete', result, error: null });
        } catch (error) {
            setECGState({ status: 'error', result: null, error: getUserFriendlyError(error) });
        }
    };

    const resetECG = () => {
        setECGState({ status: 'idle', result: null, error: null });
        setPatientContext('');
        if (ecgFileRef.current) ecgFileRef.current.value = '';
    };

    // ============================================================================
    // Food Recognition
    // ============================================================================

    const handleFoodFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files || !e.target.files[0]) return;
        const file = e.target.files[0];

        setFoodState({ status: 'analyzing', result: null, error: null, mealLogged: false });

        try {
            const result = await visionService.recognizeFood(file, true);
            setFoodState({ status: 'complete', result, error: null, mealLogged: false });
        } catch (error) {
            setFoodState({ status: 'error', result: null, error: getUserFriendlyError(error), mealLogged: false });
        }
    };

    const handleLogMeal = async () => {
        if (!foodFileRef.current?.files?.[0] || !foodState.result) return;

        try {
            await visionService.logMeal(USER_ID, foodFileRef.current.files[0], mealType);
            setFoodState(prev => ({ ...prev, mealLogged: true }));
        } catch (error) {
            setFoodState(prev => ({ ...prev, error: getUserFriendlyError(error) }));
        }
    };

    const resetFood = () => {
        setFoodState({ status: 'idle', result: null, error: null, mealLogged: false });
        if (foodFileRef.current) foodFileRef.current.value = '';
    };

    // ============================================================================
    // Render
    // ============================================================================

    return (
        <div className="min-h-screen bg-background-light dark:bg-background-dark pb-24 relative">
            {/* Header */}
            <div className="flex items-center p-4 bg-white dark:bg-card-dark sticky top-0 z-10 border-b border-slate-100 dark:border-slate-800 shadow-sm">
                <button
                    onClick={() => navigate(-1)}
                    className="p-2 -ml-2 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-900 dark:text-white transition-colors"
                >
                    <span className="material-symbols-outlined">arrow_back</span>
                </button>
                <h2 className="flex-1 text-center font-bold text-lg dark:text-white">Vision Analysis</h2>
                <div className="w-10"></div>
            </div>

            {/* Tab Navigation */}
            <div className="p-4 pb-0">
                <div className="flex bg-slate-100 dark:bg-slate-800 rounded-xl p-1">
                    <button
                        onClick={() => setActiveTab('ecg')}
                        className={`flex-1 py-3 rounded-lg flex items-center justify-center gap-2 font-medium transition-colors ${activeTab === 'ecg'
                                ? 'bg-white dark:bg-slate-700 text-primary shadow-sm'
                                : 'text-slate-500 dark:text-slate-400'
                            }`}
                    >
                        <span className="material-symbols-outlined text-xl">monitor_heart</span>
                        ECG Analysis
                    </button>
                    <button
                        onClick={() => setActiveTab('food')}
                        className={`flex-1 py-3 rounded-lg flex items-center justify-center gap-2 font-medium transition-colors ${activeTab === 'food'
                                ? 'bg-white dark:bg-slate-700 text-primary shadow-sm'
                                : 'text-slate-500 dark:text-slate-400'
                            }`}
                    >
                        <span className="material-symbols-outlined text-xl">restaurant</span>
                        Food Recognition
                    </button>
                </div>
            </div>

            <div className="p-4 space-y-4">
                {/* ============== ECG TAB ============== */}
                {activeTab === 'ecg' && (
                    <>
                        {/* Medical Disclaimer - Always Visible */}
                        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-4">
                            <div className="flex items-start gap-2">
                                <span className="material-symbols-outlined text-red-600 mt-0.5">warning</span>
                                <div>
                                    <p className="font-medium text-red-800 dark:text-red-400 text-sm">Medical Disclaimer</p>
                                    <p className="text-xs text-red-700 dark:text-red-400 mt-1">
                                        {visionService.ECG_DISCLAIMER}
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* ECG Idle State */}
                        {ecgState.status === 'idle' && (
                            <>
                                {/* Info Card */}
                                <div className="bg-gradient-to-r from-rose-600 to-pink-600 rounded-2xl p-5 text-white shadow-lg">
                                    <div className="flex items-start gap-4">
                                        <div className="w-12 h-12 bg-white/20 rounded-full flex items-center justify-center shrink-0">
                                            <span className="material-symbols-outlined text-2xl">monitor_heart</span>
                                        </div>
                                        <div>
                                            <h3 className="font-bold text-lg">ECG Strip Analysis</h3>
                                            <p className="text-rose-100 text-sm mt-1">
                                                Upload a photo of your ECG strip for AI rhythm analysis.
                                            </p>
                                        </div>
                                    </div>
                                </div>

                                {/* Patient Context Input */}
                                <div className="bg-white dark:bg-card-dark rounded-xl p-4 border border-slate-100 dark:border-slate-800">
                                    <label className="text-xs font-bold text-slate-500 uppercase">
                                        Patient Context (Optional)
                                    </label>
                                    <input
                                        type="text"
                                        className="w-full mt-2 p-3 rounded-xl bg-slate-100 dark:bg-slate-800 border-none outline-none dark:text-white focus:ring-2 focus:ring-primary"
                                        placeholder="e.g., History of palpitations, on beta blockers"
                                        value={patientContext}
                                        onChange={(e) => setPatientContext(e.target.value)}
                                    />
                                </div>

                                {/* Upload Button */}
                                <button
                                    onClick={() => ecgFileRef.current?.click()}
                                    className="w-full py-4 bg-primary text-white rounded-xl font-medium flex items-center justify-center gap-2 shadow-lg shadow-primary/30 hover:bg-primary-dark transition-colors"
                                >
                                    <span className="material-symbols-outlined">upload</span>
                                    Upload ECG Image
                                </button>

                                <input
                                    ref={ecgFileRef}
                                    type="file"
                                    accept="image/*"
                                    capture="environment"
                                    className="hidden"
                                    onChange={handleECGFileSelect}
                                />
                            </>
                        )}

                        {/* ECG Analyzing State */}
                        {ecgState.status === 'analyzing' && (
                            <div className="bg-white dark:bg-card-dark rounded-2xl p-8 shadow-lg border border-slate-100 dark:border-slate-800">
                                <div className="flex flex-col items-center gap-4">
                                    <div className="w-16 h-16 rounded-full bg-rose-100 dark:bg-rose-900/30 flex items-center justify-center">
                                        <span className="material-symbols-outlined text-rose-600 text-3xl animate-pulse">
                                            monitor_heart
                                        </span>
                                    </div>
                                    <div className="text-center">
                                        <p className="font-medium text-slate-700 dark:text-white">Analyzing ECG...</p>
                                        <p className="text-sm text-slate-500 mt-1">Detecting rhythm patterns</p>
                                    </div>
                                    <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-2 overflow-hidden">
                                        <div className="h-full bg-primary rounded-full animate-pulse w-2/3"></div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* ECG Error State */}
                        {ecgState.status === 'error' && ecgState.error && (
                            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl p-5">
                                <div className="flex items-start gap-3">
                                    <span className="material-symbols-outlined text-red-500 mt-0.5">error</span>
                                    <div className="flex-1">
                                        <h4 className="font-medium text-red-800 dark:text-red-400">Analysis Failed</h4>
                                        <p className="text-red-700 dark:text-red-400 text-sm mt-1">{ecgState.error}</p>
                                        <button
                                            onClick={resetECG}
                                            className="mt-3 px-4 py-2 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 rounded-lg text-sm font-medium"
                                        >
                                            Try Again
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* ECG Results */}
                        {ecgState.status === 'complete' && ecgState.result && (
                            <div className="space-y-4">
                                {/* Rhythm Card */}
                                <div className="bg-white dark:bg-card-dark rounded-xl border border-slate-100 dark:border-slate-800 overflow-hidden">
                                    <div className="p-4 bg-slate-50 dark:bg-slate-800/50 border-b border-slate-100 dark:border-slate-700 flex items-center justify-between">
                                        <h4 className="font-medium text-slate-700 dark:text-white flex items-center gap-2">
                                            <span className="material-symbols-outlined text-rose-500">favorite</span>
                                            Rhythm Analysis
                                        </h4>
                                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getConfidenceBadge(ecgState.result.confidence).class}`}>
                                            {Math.round(ecgState.result.confidence * 100)}% confidence
                                        </span>
                                    </div>
                                    <div className="p-4">
                                        <div className="flex items-center gap-4">
                                            <div className="w-16 h-16 rounded-full bg-rose-100 dark:bg-rose-900/30 flex items-center justify-center">
                                                <span className="material-symbols-outlined text-rose-600 text-2xl">monitor_heart</span>
                                            </div>
                                            <div>
                                                <p className="text-2xl font-bold text-slate-800 dark:text-white">
                                                    {ecgState.result.rhythm}
                                                </p>
                                                {ecgState.result.heart_rate_bpm && (
                                                    <p className="text-slate-500">
                                                        Estimated HR: <span className="font-medium">{ecgState.result.heart_rate_bpm} bpm</span>
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Requires Review Warning */}
                                {ecgState.result.requires_review && (
                                    <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4 flex items-start gap-3">
                                        <span className="material-symbols-outlined text-amber-600">priority_high</span>
                                        <div>
                                            <p className="font-medium text-amber-800 dark:text-amber-400">Professional Review Recommended</p>
                                            <p className="text-sm text-amber-700 dark:text-amber-400 mt-1">
                                                This ECG should be reviewed by a healthcare provider.
                                            </p>
                                        </div>
                                    </div>
                                )}

                                {/* Abnormalities */}
                                {ecgState.result.abnormalities.length > 0 && (
                                    <div className="bg-white dark:bg-card-dark rounded-xl border border-slate-100 dark:border-slate-800 overflow-hidden">
                                        <div className="p-4 bg-slate-50 dark:bg-slate-800/50 border-b border-slate-100 dark:border-slate-700">
                                            <h4 className="font-medium text-slate-700 dark:text-white flex items-center gap-2">
                                                <span className="material-symbols-outlined text-amber-500">warning</span>
                                                Detected Abnormalities
                                            </h4>
                                        </div>
                                        <ul className="divide-y divide-slate-100 dark:divide-slate-700">
                                            {ecgState.result.abnormalities.map((abnormality, i) => (
                                                <li key={i} className="p-4 flex items-center gap-3">
                                                    <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                                                    <span className="text-slate-700 dark:text-slate-300">{abnormality}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}

                                {/* Recommendations */}
                                {ecgState.result.recommendations.length > 0 && (
                                    <div className="bg-white dark:bg-card-dark rounded-xl border border-slate-100 dark:border-slate-800 overflow-hidden">
                                        <div className="p-4 bg-slate-50 dark:bg-slate-800/50 border-b border-slate-100 dark:border-slate-700">
                                            <h4 className="font-medium text-slate-700 dark:text-white flex items-center gap-2">
                                                <span className="material-symbols-outlined text-blue-500">lightbulb</span>
                                                Recommendations
                                            </h4>
                                        </div>
                                        <ul className="divide-y divide-slate-100 dark:divide-slate-700">
                                            {ecgState.result.recommendations.map((rec, i) => (
                                                <li key={i} className="p-4 flex items-start gap-3">
                                                    <span className="material-symbols-outlined text-blue-500 text-sm mt-0.5">check_circle</span>
                                                    <span className="text-slate-700 dark:text-slate-300">{rec}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}

                                {/* Analyze Another Button */}
                                <button
                                    onClick={resetECG}
                                    className="w-full py-4 bg-primary text-white rounded-xl font-medium flex items-center justify-center gap-2 shadow-lg shadow-primary/30"
                                >
                                    <span className="material-symbols-outlined">monitor_heart</span>
                                    Analyze Another ECG
                                </button>
                            </div>
                        )}
                    </>
                )}

                {/* ============== FOOD TAB ============== */}
                {activeTab === 'food' && (
                    <>
                        {/* Food Idle State */}
                        {foodState.status === 'idle' && (
                            <>
                                {/* Info Card */}
                                <div className="bg-gradient-to-r from-green-600 to-emerald-600 rounded-2xl p-5 text-white shadow-lg">
                                    <div className="flex items-start gap-4">
                                        <div className="w-12 h-12 bg-white/20 rounded-full flex items-center justify-center shrink-0">
                                            <span className="material-symbols-outlined text-2xl">restaurant</span>
                                        </div>
                                        <div>
                                            <h3 className="font-bold text-lg">Meal Recognition</h3>
                                            <p className="text-green-100 text-sm mt-1">
                                                Take a photo of your meal for instant nutritional analysis.
                                            </p>
                                        </div>
                                    </div>
                                </div>

                                {/* Meal Type Selector */}
                                <div className="bg-white dark:bg-card-dark rounded-xl p-4 border border-slate-100 dark:border-slate-800">
                                    <label className="text-xs font-bold text-slate-500 uppercase">Meal Type</label>
                                    <div className="grid grid-cols-4 gap-2 mt-2">
                                        {(['breakfast', 'lunch', 'dinner', 'snack'] as const).map((type) => (
                                            <button
                                                key={type}
                                                onClick={() => setMealType(type)}
                                                className={`py-2 px-3 rounded-lg text-sm font-medium capitalize transition-colors ${mealType === type
                                                        ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                                                        : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                                                    }`}
                                            >
                                                {type}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                {/* Upload Button */}
                                <button
                                    onClick={() => foodFileRef.current?.click()}
                                    className="w-full py-4 bg-green-600 text-white rounded-xl font-medium flex items-center justify-center gap-2 shadow-lg shadow-green-600/30 hover:bg-green-700 transition-colors"
                                >
                                    <span className="material-symbols-outlined">photo_camera</span>
                                    Take Meal Photo
                                </button>

                                <input
                                    ref={foodFileRef}
                                    type="file"
                                    accept="image/*"
                                    capture="environment"
                                    className="hidden"
                                    onChange={handleFoodFileSelect}
                                />
                            </>
                        )}

                        {/* Food Analyzing State */}
                        {foodState.status === 'analyzing' && (
                            <div className="bg-white dark:bg-card-dark rounded-2xl p-8 shadow-lg border border-slate-100 dark:border-slate-800">
                                <div className="flex flex-col items-center gap-4">
                                    <div className="w-16 h-16 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                                        <span className="material-symbols-outlined text-green-600 text-3xl animate-pulse">
                                            restaurant
                                        </span>
                                    </div>
                                    <div className="text-center">
                                        <p className="font-medium text-slate-700 dark:text-white">Analyzing Meal...</p>
                                        <p className="text-sm text-slate-500 mt-1">Identifying food items</p>
                                    </div>
                                    <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-2 overflow-hidden">
                                        <div className="h-full bg-green-500 rounded-full animate-pulse w-2/3"></div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Food Error State */}
                        {foodState.status === 'error' && foodState.error && (
                            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl p-5">
                                <div className="flex items-start gap-3">
                                    <span className="material-symbols-outlined text-red-500 mt-0.5">error</span>
                                    <div className="flex-1">
                                        <h4 className="font-medium text-red-800 dark:text-red-400">Analysis Failed</h4>
                                        <p className="text-red-700 dark:text-red-400 text-sm mt-1">{foodState.error}</p>
                                        <button
                                            onClick={resetFood}
                                            className="mt-3 px-4 py-2 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 rounded-lg text-sm font-medium"
                                        >
                                            Try Again
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Food Results */}
                        {foodState.status === 'complete' && foodState.result && (
                            <div className="space-y-4">
                                {/* Logged Success Banner */}
                                {foodState.mealLogged && (
                                    <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl p-4 flex items-center gap-3">
                                        <span className="material-symbols-outlined text-green-600">check_circle</span>
                                        <p className="font-medium text-green-800 dark:text-green-400">
                                            Meal logged successfully!
                                        </p>
                                    </div>
                                )}

                                {/* Calories Card */}
                                <div className="bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl p-5 text-white shadow-lg">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="text-green-100 text-sm">Estimated Calories</p>
                                            <p className="text-4xl font-bold mt-1">
                                                {foodState.result.total_calories?.toFixed(0) || '--'}
                                            </p>
                                            <p className="text-green-100 text-sm">kcal</p>
                                        </div>
                                        {foodState.result.health_score && (
                                            <div className="text-center">
                                                <div className="w-16 h-16 rounded-full bg-white/20 flex items-center justify-center">
                                                    <span className="text-2xl font-bold">{foodState.result.health_score}</span>
                                                </div>
                                                <p className="text-xs text-green-100 mt-1">Health Score</p>
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* Macros */}
                                <div className="bg-white dark:bg-card-dark rounded-xl border border-slate-100 dark:border-slate-800 p-4">
                                    <h4 className="font-medium text-slate-700 dark:text-white mb-3">Macronutrients</h4>
                                    <div className="grid grid-cols-3 gap-4">
                                        <div className="text-center">
                                            <div className="w-12 h-12 mx-auto rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mb-2">
                                                <span className="font-bold text-blue-600">{foodState.result.macros.protein?.toFixed(0) || 0}g</span>
                                            </div>
                                            <p className="text-xs text-slate-500">Protein</p>
                                        </div>
                                        <div className="text-center">
                                            <div className="w-12 h-12 mx-auto rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center mb-2">
                                                <span className="font-bold text-amber-600">{foodState.result.macros.carbs?.toFixed(0) || 0}g</span>
                                            </div>
                                            <p className="text-xs text-slate-500">Carbs</p>
                                        </div>
                                        <div className="text-center">
                                            <div className="w-12 h-12 mx-auto rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-2">
                                                <span className="font-bold text-red-600">{foodState.result.macros.fat?.toFixed(0) || 0}g</span>
                                            </div>
                                            <p className="text-xs text-slate-500">Fat</p>
                                        </div>
                                    </div>
                                </div>

                                {/* Food Items */}
                                {foodState.result.food_items.length > 0 && (
                                    <div className="bg-white dark:bg-card-dark rounded-xl border border-slate-100 dark:border-slate-800 overflow-hidden">
                                        <div className="p-4 bg-slate-50 dark:bg-slate-800/50 border-b border-slate-100 dark:border-slate-700">
                                            <h4 className="font-medium text-slate-700 dark:text-white">
                                                Detected Items ({foodState.result.food_items.length})
                                            </h4>
                                        </div>
                                        <ul className="divide-y divide-slate-100 dark:divide-slate-700">
                                            {foodState.result.food_items.map((item, i) => (
                                                <li key={i} className="p-4 flex items-center justify-between">
                                                    <div className="flex items-center gap-3">
                                                        <span className="material-symbols-outlined text-slate-400">restaurant</span>
                                                        <span className="font-medium text-slate-700 dark:text-white">{item.name}</span>
                                                    </div>
                                                    <div className="text-right">
                                                        <span className="font-medium text-slate-700 dark:text-white">
                                                            {item.calories} kcal
                                                        </span>
                                                        <span className={`ml-2 px-2 py-0.5 rounded-full text-xs ${getConfidenceBadge(item.confidence).class}`}>
                                                            {Math.round(item.confidence * 100)}%
                                                        </span>
                                                    </div>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}

                                {/* Recommendations */}
                                {foodState.result.recommendations.length > 0 && (
                                    <div className="bg-white dark:bg-card-dark rounded-xl border border-slate-100 dark:border-slate-800 overflow-hidden">
                                        <div className="p-4 bg-slate-50 dark:bg-slate-800/50 border-b border-slate-100 dark:border-slate-700">
                                            <h4 className="font-medium text-slate-700 dark:text-white flex items-center gap-2">
                                                <span className="material-symbols-outlined text-green-500">lightbulb</span>
                                                Heart-Healthy Tips
                                            </h4>
                                        </div>
                                        <ul className="divide-y divide-slate-100 dark:divide-slate-700">
                                            {foodState.result.recommendations.map((rec, i) => (
                                                <li key={i} className="p-4 flex items-start gap-3">
                                                    <span className="material-symbols-outlined text-green-500 text-sm mt-0.5">check_circle</span>
                                                    <span className="text-slate-700 dark:text-slate-300">{rec}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}

                                {/* Action Buttons */}
                                <div className="flex gap-3">
                                    {!foodState.mealLogged && (
                                        <button
                                            onClick={handleLogMeal}
                                            className="flex-1 py-4 bg-green-600 text-white rounded-xl font-medium flex items-center justify-center gap-2 shadow-lg shadow-green-600/30"
                                        >
                                            <span className="material-symbols-outlined">add_circle</span>
                                            Log This Meal
                                        </button>
                                    )}
                                    <button
                                        onClick={resetFood}
                                        className={`${foodState.mealLogged ? 'flex-1' : ''} py-4 px-6 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-xl font-medium flex items-center justify-center gap-2`}
                                    >
                                        <span className="material-symbols-outlined">photo_camera</span>
                                        {foodState.mealLogged ? 'Log Another' : 'Retake'}
                                    </button>
                                </div>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
};

export default VisionAnalysis;
