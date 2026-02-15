import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../services/apiClient';
import { HeartDiseasePredictionRequest, HeartDiseasePredictionResponse } from '../services/api.types';
import ScreenHeader from '../components/ScreenHeader';

const AssessmentScreen: React.FC = () => {
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<HeartDiseasePredictionResponse | null>(null);
    const [error, setError] = useState<string | null>(null);

    const [formData, setFormData] = useState<HeartDiseasePredictionRequest>({
        age: 50,
        sex: 1, // Male
        chest_pain_type: 1, // Typical Angina
        resting_bp_s: 120,
        cholesterol: 200,
        fasting_blood_sugar: 0, // < 120 mg/dl
        resting_ecg: 0, // Normal
        max_heart_rate: 150,
        exercise_angina: 0, // No
        oldpeak: 0.0,
        st_slope: 1 // Up
    });

    const handleChange = (field: keyof HeartDiseasePredictionRequest, value: string | number) => {
        setFormData(prev => ({
            ...prev,
            [field]: Number(value)
        }));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        setResult(null);

        // Smooth scroll to results
        setTimeout(() => {
            window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
        }, 100);

        try {
            const data = await apiClient.predictHeartDisease(formData);
            setResult(data);
        } catch (err: any) {
            setError(err.message || 'Failed to get prediction. Ensure the backend is running.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-50 dark:bg-background-dark pb-24 font-sans">
            <ScreenHeader
                title="Heart Risk Assessment"
                subtitle="AI Clinical Prediction Model"
            />

            <div className="max-w-4xl mx-auto p-4 space-y-6">

                {/* Info Card */}
                <div className="bg-gradient-to-br from-blue-600 to-indigo-700 dark:from-blue-700 dark:to-indigo-800 text-white rounded-3xl p-6 shadow-xl shadow-blue-500/20 relative overflow-hidden group">
                    <div className="absolute top-0 right-0 w-40 h-40 bg-white/10 rounded-full blur-3xl -mr-10 -mt-10 group-hover:scale-110 transition-transform duration-700"></div>
                    <div className="relative z-10 flex items-start gap-4">
                        <div className="p-3 bg-white/20 backdrop-blur-sm rounded-xl">
                            <span className="material-symbols-outlined text-2xl">cardiology</span>
                        </div>
                        <div>
                            <h3 className="font-bold text-lg mb-1">Clinical Assessment</h3>
                            <p className="text-blue-100 text-sm leading-relaxed">
                                This tool uses a machine learning model trained on the Cleveland Heart Disease dataset to estimate risk factors.
                                <span className="block mt-2 font-medium opacity-90">Please fill out all vitals accurately.</span>
                            </p>
                        </div>
                    </div>
                </div>

                <form onSubmit={handleSubmit} className="space-y-6">

                    {/* Section 1: Vitals */}
                    <section className="bg-white dark:bg-card-dark rounded-3xl p-6 shadow-sm border border-slate-100 dark:border-slate-800 hover:shadow-md transition-shadow duration-300">
                        <div className="flex items-center gap-3 mb-6 pb-4 border-b border-slate-50 dark:border-slate-800">
                            <div className="w-10 h-10 rounded-xl bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 flex items-center justify-center">
                                <span className="material-symbols-outlined">vital_signs</span>
                            </div>
                            <h3 className="font-bold text-lg text-slate-800 dark:text-white">Patient Vitals</h3>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            {/* Age & Sex Row */}
                            <div className="space-y-2">
                                <label className="text-xs font-bold text-slate-500 uppercase tracking-wide">Age</label>
                                <input
                                    type="number"
                                    value={formData.age}
                                    onChange={(e) => handleChange('age', e.target.value)}
                                    className="w-full p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800 border-2 border-transparent focus:border-primary/20 outline-none focus:ring-4 focus:ring-primary/10 dark:text-white font-medium transition-all"
                                    required
                                />
                            </div>

                            <div className="space-y-2">
                                <label className="text-xs font-bold text-slate-500 uppercase tracking-wide">Sex</label>
                                <div className="flex bg-slate-50 dark:bg-slate-800 p-1.5 rounded-xl">
                                    {[
                                        { label: 'Male', value: 1, icon: 'male' },
                                        { label: 'Female', value: 0, icon: 'female' }
                                    ].map(opt => (
                                        <button
                                            key={opt.value}
                                            type="button"
                                            onClick={() => handleChange('sex', opt.value)}
                                            className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-bold transition-all ${formData.sex === opt.value
                                                ? 'bg-white dark:bg-slate-700 shadow-sm text-primary dark:text-white'
                                                : 'text-slate-500 hover:bg-white/50 dark:hover:bg-slate-700/50'
                                                }`}
                                        >
                                            <span className="material-symbols-outlined text-lg">{opt.icon}</span>
                                            {opt.label}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* BP & Cholesterol */}
                            <div className="space-y-2">
                                <label className="text-xs font-bold text-slate-500 uppercase tracking-wide">Resting BP (mm Hg)</label>
                                <div className="relative">
                                    <input
                                        type="number"
                                        value={formData.resting_bp_s}
                                        onChange={(e) => handleChange('resting_bp_s', e.target.value)}
                                        className="w-full p-3.5 pl-12 rounded-xl bg-slate-50 dark:bg-slate-800 border-2 border-transparent focus:border-primary/20 outline-none focus:ring-4 focus:ring-primary/10 dark:text-white font-medium transition-all"
                                        required
                                    />
                                    <span className="material-symbols-outlined absolute left-4 top-3.5 text-slate-400">blood_pressure</span>
                                </div>
                            </div>

                            <div className="space-y-2">
                                <label className="text-xs font-bold text-slate-500 uppercase tracking-wide">Cholesterol (mg/dl)</label>
                                <div className="relative">
                                    <input
                                        type="number"
                                        value={formData.cholesterol}
                                        onChange={(e) => handleChange('cholesterol', e.target.value)}
                                        className="w-full p-3.5 pl-12 rounded-xl bg-slate-50 dark:bg-slate-800 border-2 border-transparent focus:border-primary/20 outline-none focus:ring-4 focus:ring-primary/10 dark:text-white font-medium transition-all"
                                        required
                                    />
                                    <span className="material-symbols-outlined absolute left-4 top-3.5 text-slate-400">water_drop</span>
                                </div>
                            </div>

                            {/* Fasting BS & Max HR */}
                            <div className="space-y-2">
                                <label className="text-xs font-bold text-slate-500 uppercase tracking-wide">Fasting Blood Sugar</label>
                                <select
                                    value={formData.fasting_blood_sugar}
                                    onChange={(e) => handleChange('fasting_blood_sugar', e.target.value)}
                                    className="w-full p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800 border-2 border-transparent focus:border-primary/20 outline-none focus:ring-4 focus:ring-primary/10 dark:text-white font-medium appearance-none"
                                >
                                    <option value={0}>Normal (&lt; 120 mg/dl)</option>
                                    <option value={1}>High (&gt; 120 mg/dl)</option>
                                </select>
                            </div>

                            <div className="space-y-2">
                                <label className="text-xs font-bold text-slate-500 uppercase tracking-wide">Max Heart Rate</label>
                                <div className="relative">
                                    <input
                                        type="number"
                                        value={formData.max_heart_rate}
                                        onChange={(e) => handleChange('max_heart_rate', e.target.value)}
                                        className="w-full p-3.5 pl-12 rounded-xl bg-slate-50 dark:bg-slate-800 border-2 border-transparent focus:border-primary/20 outline-none focus:ring-4 focus:ring-primary/10 dark:text-white font-medium transition-all"
                                        required
                                    />
                                    <span className="material-symbols-outlined absolute left-4 top-3.5 text-slate-400">favorite</span>
                                </div>
                            </div>
                        </div>
                    </section>

                    {/* Section 2: Clinical Factors */}
                    <section className="bg-white dark:bg-card-dark rounded-3xl p-6 shadow-sm border border-slate-100 dark:border-slate-800 hover:shadow-md transition-shadow duration-300">
                        <div className="flex items-center gap-3 mb-6 pb-4 border-b border-slate-50 dark:border-slate-800">
                            <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400 flex items-center justify-center">
                                <span className="material-symbols-outlined">stethoscope</span>
                            </div>
                            <h3 className="font-bold text-lg text-slate-800 dark:text-white">Clinical Factors</h3>
                        </div>

                        <div className="space-y-6">
                            <div className="space-y-3">
                                <label className="text-xs font-bold text-slate-500 uppercase tracking-wide">Chest Pain Type</label>
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    {[
                                        { val: 1, label: 'Typical Angina', desc: 'Exertional chest pain' },
                                        { val: 2, label: 'Atypical Angina', desc: 'Non-specific pain' },
                                        { val: 3, label: 'Non-Anginal', desc: 'Not heart related' },
                                        { val: 4, label: 'Asymptomatic', desc: 'No pain present' }
                                    ].map(opt => (
                                        <button
                                            key={opt.val}
                                            type="button"
                                            onClick={() => handleChange('chest_pain_type', opt.val)}
                                            className={`p-4 rounded-xl border-2 text-left transition-all hover:shadow-md ${formData.chest_pain_type === opt.val
                                                ? 'bg-primary/5 border-primary shadow-sm'
                                                : 'bg-slate-50 dark:bg-slate-800 border-transparent hover:bg-white dark:hover:bg-slate-700'
                                                }`}
                                        >
                                            <div className="flex items-center justify-between mb-1">
                                                <span className={`font-bold ${formData.chest_pain_type === opt.val ? 'text-primary' : 'text-slate-700 dark:text-white'}`}>
                                                    {opt.label}
                                                </span>
                                                {formData.chest_pain_type === opt.val && (
                                                    <span className="material-symbols-outlined text-primary text-sm">check_circle</span>
                                                )}
                                            </div>
                                            <p className="text-xs text-slate-500 dark:text-slate-400">{opt.desc}</p>
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase tracking-wide">Resting ECG</label>
                                    <select
                                        value={formData.resting_ecg}
                                        onChange={(e) => handleChange('resting_ecg', e.target.value)}
                                        className="w-full p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800 border-2 border-transparent focus:border-primary/20 outline-none focus:ring-4 focus:ring-primary/10 dark:text-white font-medium"
                                    >
                                        <option value={0}>Normal</option>
                                        <option value={1}>ST-T Wave Abnormality</option>
                                        <option value={2}>Left Ventricular Hypertrophy</option>
                                    </select>
                                </div>

                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase tracking-wide">Exercise Angina?</label>
                                    <div className="flex bg-slate-50 dark:bg-slate-800 p-1.5 rounded-xl">
                                        {[
                                            { label: 'Yes', value: 1, color: 'text-red-500' },
                                            { label: 'No', value: 0, color: 'text-green-500' }
                                        ].map(opt => (
                                            <button
                                                key={opt.value}
                                                type="button"
                                                onClick={() => handleChange('exercise_angina', opt.value)}
                                                className={`flex-1 py-2.5 rounded-lg text-sm font-bold transition-all ${formData.exercise_angina === opt.value
                                                    ? `bg-white dark:bg-slate-700 shadow-sm ${opt.color}`
                                                    : 'text-slate-500'
                                                    }`}
                                            >
                                                {opt.label}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase tracking-wide">Oldpeak (ST Depression)</label>
                                    <input
                                        type="number"
                                        step="0.1"
                                        value={formData.oldpeak}
                                        onChange={(e) => handleChange('oldpeak', e.target.value)}
                                        className="w-full p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800 border-2 border-transparent focus:border-primary/20 outline-none focus:ring-4 focus:ring-primary/10 dark:text-white font-medium transition-all"
                                        required
                                    />
                                </div>

                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase tracking-wide">ST Slope</label>
                                    <select
                                        value={formData.st_slope}
                                        onChange={(e) => handleChange('st_slope', e.target.value)}
                                        className="w-full p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800 border-2 border-transparent focus:border-primary/20 outline-none focus:ring-4 focus:ring-primary/10 dark:text-white font-medium"
                                    >
                                        <option value={1}>Upsloping</option>
                                        <option value={2}>Flat</option>
                                        <option value={3}>Downsloping</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                    </section>

                    <div className="sticky bottom-6 pt-4">
                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full py-4 bg-primary hover:bg-primary-dark text-white rounded-2xl font-bold text-lg shadow-xl shadow-primary/30 transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-70 disabled:hover:scale-100 flex items-center justify-center gap-2"
                        >
                            {loading ? (
                                <>
                                    <span className="w-5 h-5 border-3 border-white/30 border-t-white rounded-full animate-spin"></span>
                                    <span>Analyzing Risk Profile...</span>
                                </>
                            ) : (
                                <>
                                    <span className="material-symbols-outlined">analytics</span>
                                    <span>Calculate Heart Risk</span>
                                </>
                            )}
                        </button>
                    </div>
                </form>

                {error && (
                    <div className="animate-in slide-in-from-bottom-5 fade-in p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl text-red-600 dark:text-red-300 flex items-center gap-3">
                        <span className="material-symbols-outlined rounded-full bg-red-100 dark:bg-red-900/50 p-1">error</span>
                        <p className="font-medium">{error}</p>
                    </div>
                )}

                {result && (
                    <div className="animate-in slide-in-from-bottom-10 fade-in duration-500 pb-10">
                        <div className={`rounded-3xl border-2 overflow-hidden shadow-2xl ${result.prediction === 1
                            ? 'bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-900/50'
                            : 'bg-green-50 dark:bg-green-950/20 border-green-200 dark:border-green-900/50'
                            }`}>
                            <div className="p-8 text-center relative">
                                <div className="absolute top-0 left-0 w-full h-full overflow-hidden opacity-10 pointer-events-none">
                                    <span className="material-symbols-outlined absolute top-4 left-4 text-6xl">ecg_heart</span>
                                    <span className="material-symbols-outlined absolute bottom-4 right-4 text-6xl">monitor_heart</span>
                                </div>

                                <div className={`inline-flex p-4 rounded-full mb-4 shadow-lg ${result.prediction === 1 ? 'bg-red-100 text-red-600' : 'bg-green-100 text-green-600'
                                    }`}>
                                    <span className="material-symbols-outlined text-4xl">
                                        {result.prediction === 1 ? 'warning' : 'verified'}
                                    </span>
                                </div>

                                <h2 className={`text-3xl font-black mb-2 ${result.prediction === 1 ? 'text-red-700 dark:text-red-400' : 'text-green-700 dark:text-green-400'
                                    }`}>
                                    {result.prediction === 1 ? 'High Probability' : 'Low Probability'}
                                </h2>

                                <p className="text-slate-600 dark:text-slate-300 text-lg mb-8 max-w-lg mx-auto leading-relaxed">
                                    {result.message}
                                </p>

                                <div className="grid grid-cols-2 gap-4 max-w-sm mx-auto mb-6">
                                    <div className="bg-white/60 dark:bg-black/20 backdrop-blur-sm p-4 rounded-2xl border border-white/50 dark:border-white/10">
                                        <p className="text-xs uppercase tracking-wide font-bold text-slate-500 mb-1">Probability</p>
                                        <p className={`text-2xl font-black ${result.prediction === 1 ? 'text-red-600' : 'text-green-600'}`}>
                                            {(result.probability * 100).toFixed(1)}%
                                        </p>
                                    </div>
                                    <div className="bg-white/60 dark:bg-black/20 backdrop-blur-sm p-4 rounded-2xl border border-white/50 dark:border-white/10">
                                        <p className="text-xs uppercase tracking-wide font-bold text-slate-500 mb-1">Risk Level</p>
                                        <p className={`text-2xl font-black ${result.prediction === 1 ? 'text-red-600' : 'text-green-600'}`}>
                                            {result.risk_level}
                                        </p>
                                    </div>
                                </div>

                                {result.prediction === 1 && (
                                    <div className="bg-red-100/50 dark:bg-red-900/30 p-4 rounded-xl border border-red-200 dark:border-red-800 mx-auto max-w-lg text-left flex items-start gap-3">
                                        <span className="material-symbols-outlined text-red-600 mt-0.5">medical_services</span>
                                        <div>
                                            <p className="font-bold text-red-800 dark:text-red-300 text-sm">Action Required</p>
                                            <p className="text-red-700 dark:text-red-400 text-sm">
                                                Please consult a cardiologist for better evaluation. This is an AI estimation, not a diagnosis.
                                            </p>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>

                        <p className="text-center text-xs text-slate-400 mt-6 mb-12 max-w-xl mx-auto">
                            *This AI model has an accuracy of ~85% based on the Statlog Heart Data Set. It should not replace professional medical advice.
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default AssessmentScreen;
