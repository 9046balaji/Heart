
import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { HealthAssessment } from '../types';
import { apiClient } from '../services/apiClient';

// --- Utility Functions ---

// 1) Categorize Systolic Blood Pressure (AHA categories)
function categorizeBP(systolic: number, diastolic: number) {
  if (!systolic || !diastolic) return { category: 'N/A', level: 'unknown', description: 'Enter both SBP and DBP for category.' };
  if (systolic > 180 || diastolic > 120) return { category: 'Hypertensive Crisis', level: 'emergency', description: 'Seek urgent care immediately.' };
  if (systolic >= 140 || diastolic >= 90) return { category: 'Stage 2 Hypertension', level: 'high', description: 'See your doctor for evaluation.' };
  if (systolic >= 130 || diastolic >= 80) return { category: 'Stage 1 Hypertension', level: 'moderate', description: 'Lifestyle changes recommended.' };
  if (systolic >= 120 && diastolic < 80) return { category: 'Elevated', level: 'notice', description: 'Lifestyle changes recommended.' };
  return { category: 'Normal', level: 'ok', description: 'Maintain healthy lifestyle.' };
}

// 2) Client-side Preliminary ASCVD Risk Indicator (Simplified Heuristic)
function calculatePreliminaryASCVDIndicator(data: any) {
  const { age, gender, race, totalCholesterol, hdlCholesterol, systolic, onBPMeds, isSmoker, hasDiabetes } = data;

  if (!age || !gender || !race || !totalCholesterol || !hdlCholesterol || !systolic) {
    return { level: 'incomplete', description: 'Please fill all fields for a preliminary estimate.' };
  }

  const ageNum = parseFloat(age);
  const sysNum = parseFloat(systolic);
  const cholNum = parseFloat(totalCholesterol);
  const hdlNum = parseFloat(hdlCholesterol);

  let riskFactors = 0;

  // Age (non-modifiable)
  if (ageNum >= 40 && ageNum <= 79) {
    if (ageNum >= 60) riskFactors += 1;
  } else if (ageNum > 79) {
      return { level: 'high', description: 'High risk due to age. Consult your doctor.' };
  } else if (ageNum < 40) {
      return { level: 'low', description: 'Low immediate risk due to age. Focus on prevention.' };
  }

  // Modifiable factors
  if (sysNum >= 130) riskFactors += 1;
  if (onBPMeds) riskFactors += 1;
  if (cholNum > 200) riskFactors += 1;
  if (hdlNum < (gender.toLowerCase() === 'female' ? 50 : 40)) riskFactors += 1;
  if (isSmoker) riskFactors += 2;
  if (hasDiabetes) riskFactors += 2;

  if (riskFactors >= 4) return { level: 'high', description: 'High estimated 10-year ASCVD risk. Consult your doctor immediately.' };
  if (riskFactors >= 2) return { level: 'intermediate', description: 'Intermediate estimated 10-year ASCVD risk. Discuss lifestyle changes.' };
  if (riskFactors >= 1) return { level: 'borderline', description: 'Borderline estimated 10-year ASCVD risk. Focus on prevention.' };
  return { level: 'low', description: 'Low estimated 10-year ASCVD risk. Maintain a heart-healthy lifestyle.' };
}

// --- ECG Simulation Helper ---
function getECGValue(t: number) {
    // Basic P-QRS-T wave simulation
    // t is time in seconds. Period is 1s (60bpm)
    const period = 1.0;
    const x = t % period;

    // Baseline
    let y = 0.0;

    // P Wave (0.1 to 0.2)
    if (x > 0.1 && x < 0.2) {
        y += 0.15 * Math.sin((x - 0.1) * 10 * Math.PI);
    }

    // QRS Complex (0.35 to 0.45)
    // Q
    if (x > 0.35 && x < 0.38) {
        y -= 0.15 * Math.sin((x - 0.35) * 33 * Math.PI);
    }
    // R
    if (x >= 0.38 && x < 0.42) {
        y += 1.0 * Math.sin((x - 0.38) * 25 * Math.PI);
    }
    // S
    if (x >= 0.42 && x < 0.45) {
        y -= 0.25 * Math.sin((x - 0.42) * 33 * Math.PI);
    }

    // T Wave (0.6 to 0.8)
    if (x > 0.6 && x < 0.8) {
        y += 0.25 * Math.sin((x - 0.6) * 5 * Math.PI);
    }

    // Add some noise
    y += (Math.random() - 0.5) * 0.05;

    return y;
}

const ECGRecorder = () => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [isRecording, setIsRecording] = useState(false);
    const [analysis, setAnalysis] = useState<string | null>(null);
    const [progress, setProgress] = useState(0);
    const requestRef = useRef<number>(0);
    const startTimeRef = useRef<number>(0);
    const dataPointsRef = useRef<number[]>([]);

    const startECG = () => {
        setIsRecording(true);
        setAnalysis(null);
        setProgress(0);
        dataPointsRef.current = [];
        startTimeRef.current = performance.now();
        requestRef.current = requestAnimationFrame(animate);
    };

    const animate = (time: number) => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const duration = 5000; // 5 seconds recording
        const elapsed = time - startTimeRef.current;
        const width = canvas.width;
        const height = canvas.height;
        const centerY = height / 2;
        const scaleY = height * 0.4;

        // Clear only if starting or drawing full refresh (simple sweep)
        // Here we simulate a moving window or just redraw all points for simplicity
        ctx.fillStyle = '#000000';
        ctx.fillRect(0, 0, width, height);

        // Draw Grid
        ctx.strokeStyle = '#003300';
        ctx.lineWidth = 1;
        ctx.beginPath();
        for(let i=0; i<width; i+=20) { ctx.moveTo(i,0); ctx.lineTo(i,height); }
        for(let i=0; i<height; i+=20) { ctx.moveTo(0,i); ctx.lineTo(width,i); }
        ctx.stroke();

        // Calculate Data
        const totalSeconds = elapsed / 1000;
        const currentVal = getECGValue(totalSeconds);
        dataPointsRef.current.push(currentVal);

        // Draw Waveform
        ctx.strokeStyle = '#00ff00';
        ctx.lineWidth = 2;
        ctx.beginPath();

        // We draw the last 2 seconds of data to keep it moving
        const windowSize = 3; // seconds visible
        const pointsToDraw = Math.floor(60 * windowSize); // 60fps * 3s
        const startIndex = Math.max(0, dataPointsRef.current.length - pointsToDraw);

        for (let i = startIndex; i < dataPointsRef.current.length; i++) {
            const point = dataPointsRef.current[i];
            // X position relative to window
            const x = ((i - startIndex) / pointsToDraw) * width;
            const y = centerY - (point * scaleY);
            if (i === startIndex) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();

        // Update Progress
        const p = Math.min(100, (elapsed / duration) * 100);
        setProgress(p);

        if (elapsed < duration) {
            requestRef.current = requestAnimationFrame(animate);
        } else {
            setIsRecording(false);
            analyzeECG();
        }
    };

    const analyzeECG = async () => {
        setAnalysis("Processing rhythm data with backend API...");
        try {
            const result = await apiClient.generateInsight({
                user_name: 'Patient',
                vitals: {}
            });

            setAnalysis(result.insight || "Analysis complete.");

        } catch (error) {
            console.error("ECG Analysis Error", error);
            setAnalysis("Error analyzing data. Please try again.");
        }
    };

    useEffect(() => {
        return () => {
            if (requestRef.current) cancelAnimationFrame(requestRef.current);
        };
    }, []);

    return (
        <div className="bg-black rounded-xl overflow-hidden border border-slate-700 shadow-2xl relative">
            {/* Header / Info */}
            <div className="absolute top-0 left-0 right-0 p-4 flex justify-between items-center z-10 bg-gradient-to-b from-black/80 to-transparent">
                <div className="flex items-center gap-2">
                    <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
                    <span className="text-xs font-mono text-green-500 uppercase tracking-widest">Live Lead I</span>
                </div>
                <span className="text-xs font-mono text-green-500">25mm/s</span>
            </div>

            <canvas
                ref={canvasRef}
                width={350}
                height={200}
                className="w-full h-48 md:h-64 cursor-crosshair bg-black"
            ></canvas>

            {/* Overlay Controls */}
            {!isRecording && !analysis && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/60 backdrop-blur-sm">
                    <button
                        onClick={startECG}
                        className="bg-red-600 hover:bg-red-700 text-white rounded-full w-16 h-16 flex items-center justify-center shadow-lg shadow-red-600/30 transition-transform hover:scale-110"
                    >
                        <div className="w-6 h-6 bg-white rounded-full"></div>
                    </button>
                </div>
            )}

            {/* Analysis Overlay */}
            {analysis && !isRecording && (
                <div className="p-4 bg-slate-900 border-t border-slate-800">
                    <div className="flex items-start gap-3">
                        <span className="material-symbols-outlined text-green-500 text-xl mt-1">monitor_heart</span>
                        <div>
                            <h4 className="text-green-500 font-bold text-sm uppercase mb-1">AI Rhythm Analysis</h4>
                            <p className="text-slate-300 text-xs leading-relaxed">{analysis}</p>
                        </div>
                    </div>
                    <button
                        onClick={startECG}
                        className="w-full mt-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold rounded-lg transition-colors"
                    >
                        Record Again
                    </button>
                </div>
            )}

            {/* Progress Bar */}
            {isRecording && (
                <div className="absolute bottom-0 left-0 h-1 bg-green-500 transition-all duration-100 ease-linear" style={{width: `${progress}%`}}></div>
            )}
        </div>
    );
};

const AssessmentScreen: React.FC = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'Questionnaire' | 'ECG'>('Questionnaire');
  const [view, setView] = useState<'form' | 'report'>('form');
  const [step, setStep] = useState(1);
  const [assessment, setAssessment] = useState<HealthAssessment | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Expanded Form State
  const [formData, setFormData] = useState({
    // Step 1: Personal & Vitals
    age: '',
    gender: '',
    race: '',
    systolic: '',
    diastolic: '',
    totalCholesterol: '',
    hdlCholesterol: '',
    isSmoker: false,
    hasDiabetes: false,
    onBPMeds: false,
    // Step 2: Medical History
    historyHeartAttack: false,
    historyFamily: false,
    historyKidney: false,
    historyAfib: false,
    medications: '',
    allergies: '',
    // Step 3: Lifestyle (Detailed)
    fruitVegIntake: 'Some days',
    processedFoodIntake: 'Weekly',
    exerciseDays: 2,
    exerciseIntensity: 'Moderate',
    stressLevel: 'Moderate',
    sleepHours: '6-8 hours',
    alcoholConsumption: 'Socially'
  });

  const [isEmergencyModalVisible, setIsEmergencyModalVisible] = useState(false);
  const [showRiskSummary, setShowRiskSummary] = useState(false);

  // AI Analysis State
  const [aiAnalysis, setAiAnalysis] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isProcessingFile, setIsProcessingFile] = useState(false);
  const [uploadSummary, setUploadSummary] = useState<string | null>(null);

  // Derived Values
  const bpCategory = categorizeBP(parseFloat(formData.systolic), parseFloat(formData.diastolic));
  const riskIndicator = calculatePreliminaryASCVDIndicator(formData);

  useEffect(() => {
    const saved = localStorage.getItem('last_assessment');
    if (saved) {
      setAssessment(JSON.parse(saved));
      // Uncomment to start in report view if saved
      // setView('report');
    }
  }, []);

  // Monitor BP for Emergency
  useEffect(() => {
    if (bpCategory.level === 'emergency') {
      setIsEmergencyModalVisible(true);
    } else {
      setIsEmergencyModalVisible(false);
    }
  }, [bpCategory.level]);

  // Monitor fields for Risk Summary Visibility
  useEffect(() => {
    const { age, gender, race, systolic, totalCholesterol, hdlCholesterol } = formData;
    const allFilled = age && gender && race && systolic && totalCholesterol && hdlCholesterol;

    if (allFilled && bpCategory.level !== 'emergency') {
      setShowRiskSummary(true);
    } else {
      setShowRiskSummary(false);
    }
  }, [formData, bpCategory.level]);


  const handleChange = (field: string, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleContinue = () => {
    if (bpCategory.level === 'emergency') {
        setIsEmergencyModalVisible(true);
        return;
    }

    if (step === 3) {
        calculateFinalRisk();
    } else {
        setStep(step + 1);
        window.scrollTo(0, 0);
    }
  };

  const handleBack = () => {
    if (step > 1) {
        setStep(step - 1);
        window.scrollTo(0, 0);
    } else {
        navigate('/dashboard');
    }
  };

  const calculateFinalRisk = () => {
    const age = parseInt(formData.age) || 40;
    const systolic = parseInt(formData.systolic) || 120;
    const cholesterol = parseInt(formData.totalCholesterol) || 200;

    let score = 100;

    // 1. Vitals Penalties
    if (age > 50) score -= 5;
    if (age > 70) score -= 10;
    if (systolic > 120) score -= 5;
    if (systolic > 130) score -= 10;
    if (systolic > 140) score -= 15;
    if (cholesterol > 200) score -= 5;
    if (cholesterol > 240) score -= 10;

    // 2. Risk Factors Penalties
    if (formData.isSmoker) score -= 15;
    if (formData.hasDiabetes) score -= 15;
    if (formData.historyHeartAttack) score -= 20;
    if (formData.historyFamily) score -= 5;
    if (formData.historyAfib) score -= 10;

    // 3. Lifestyle Penalties/Bonuses
    // Diet
    if (formData.fruitVegIntake === 'Rarely') score -= 5;
    else if (formData.fruitVegIntake === 'Daily') score += 5;

    if (formData.processedFoodIntake === 'Daily') score -= 10;
    else if (formData.processedFoodIntake === 'Rarely') score += 5;

    // Exercise
    if (formData.exerciseDays === 0) score -= 10;
    else if (formData.exerciseDays >= 4) score += 5;

    // Stress & Sleep
    if (formData.stressLevel === 'High' || formData.stressLevel === 'Severe') score -= 10;
    if (formData.sleepHours === '< 5 hrs') score -= 5;

    // Alcohol
    if (formData.alcoholConsumption === 'Heavy') score -= 10;

    score = Math.max(0, Math.min(100, score));

    let risk = 'Low Risk';
    if (score < 80) risk = 'Moderate Risk';
    if (score < 50) risk = 'High Risk';

    let details = "Your vitals are within a healthy range. Keep up the good work!";
    if (risk === 'Moderate Risk') details = "Your indicators suggest some elevated risks. Consider improving diet and exercise.";
    if (risk === 'High Risk') details = "Your indicators suggest a higher risk. Please consult with a cardiologist for a full evaluation.";

    const newAssessment: HealthAssessment = {
        date: new Date().toISOString(),
        score,
        risk,
        details,
        vitals: {
            systolic,
            cholesterol
        }
    };

    localStorage.setItem('last_assessment', JSON.stringify(newAssessment));
    setAssessment(newAssessment);
    setAiAnalysis(null); // Reset AI analysis on new calculation
    setView('report');
    window.scrollTo(0, 0);
  };

  const generateAIAnalysis = async () => {
      setIsAnalyzing(true);
      try {
          const result = await apiClient.generateInsight({
              user_name: 'Patient',
              vitals: {}
          });

          setAiAnalysis(result.insight || "Could not generate analysis.");
      } catch (error) {
          console.error("Analysis Error:", error);
          setAiAnalysis("Sorry, I encountered an error while analyzing your data. Please try again.");
      } finally {
          setIsAnalyzing(false);
      }
  };

  // --- File Upload Logic ---
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files[0]) {
          const file = e.target.files[0];
          const reader = new FileReader();
          reader.onloadend = async () => {
              const base64String = reader.result as string;
              processMedicalReport(base64String.split(',')[1]);
          };
          reader.readAsDataURL(file);
      }
  };

  const processMedicalReport = async (base64Data: string) => {
      setIsProcessingFile(true);
      setUploadSummary(null);
      try {
          // Simplified file processing - would integrate with backend API in production
          setUploadSummary("Medical report upload feature is available. Please configure the backend API to process document analysis.");
      } catch (error) {
          console.error("Report Processing Error:", error);
          alert("Could not process the report. Please try a clearer image.");
      } finally {
          setIsProcessingFile(false);
      }
  };

  // --- Render Components ---

  const ToggleSwitch = ({ label, checked, onChange, infoText }: { label: string, checked: boolean, onChange: (checked: boolean) => void, infoText?: string }) => (
    <div className="flex items-center justify-between bg-white dark:bg-slate-800/50 p-4 rounded-xl border border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-2 pr-4">
            <span className="text-sm font-medium dark:text-slate-200">{label}</span>
            {infoText && (
                <button
                    onClick={() => window.alert(infoText)}
                    className="text-slate-400 hover:text-primary transition-colors flex items-center justify-center"
                    title="More info"
                >
                    <span className="material-symbols-outlined text-base">info</span>
                </button>
            )}
        </div>
        <label className="relative inline-flex items-center cursor-pointer shrink-0">
            <input
                type="checkbox"
                className="sr-only peer"
                checked={checked}
                onChange={(e) => onChange(e.target.checked)}
            />
            <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer dark:bg-slate-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-slate-600 peer-checked:bg-primary"></div>
        </label>
    </div>
  );

  const SelectionGroup = ({ label, options, value, onChange }: { label: string, options: string[], value: string, onChange: (val: string) => void }) => (
    <div className="space-y-2">
        <label className="text-sm font-medium dark:text-slate-200">{label}</label>
        <div className="grid grid-cols-2 gap-2">
            {options.map((option) => (
                <button
                    key={option}
                    onClick={() => onChange(option)}
                    className={`p-3 rounded-lg text-sm font-medium border transition-all ${
                        value === option
                        ? 'bg-primary/10 border-primary text-primary'
                        : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600'
                    }`}
                >
                    {option}
                </button>
            ))}
        </div>
    </div>
  );

  // --- Report View Render ---
  if (view === 'report' && assessment) {
    return (
        <div className="min-h-screen bg-background-light dark:bg-background-dark flex flex-col animate-in fade-in duration-300">
            <div className="flex items-center p-4 bg-background-light dark:bg-background-dark sticky top-0 z-10 no-print">
                <button onClick={() => navigate('/dashboard')} className="p-2 -ml-2 rounded-full hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-slate-900 dark:text-white">
                    <span className="material-symbols-outlined">arrow_back</span>
                </button>
                <h2 className="flex-1 text-center font-bold text-lg dark:text-white">Assessment Report</h2>
                <div className="w-10"></div>
            </div>

            <div className="flex-1 p-6 flex flex-col items-center">
                {/* Score Circle */}
                <div className={`w-32 h-32 rounded-full flex items-center justify-center border-8 mb-6 ${
                    assessment.score >= 80 ? 'border-green-100 bg-green-50 text-green-600 dark:border-green-900/30 dark:bg-green-900/10 dark:text-green-500' :
                    assessment.score >= 50 ? 'border-yellow-100 bg-yellow-50 text-yellow-600 dark:border-yellow-900/30 dark:bg-yellow-900/10 dark:text-yellow-500' :
                    'border-red-100 bg-red-50 text-red-600 dark:border-red-900/30 dark:bg-red-900/10 dark:text-red-500'
                }`}>
                    <div className="text-center">
                        <span className="block text-4xl font-bold">{assessment.score}</span>
                        <span className="text-xs font-medium uppercase tracking-wider">Score</span>
                    </div>
                </div>

                <h2 className={`text-2xl font-bold mb-2 ${
                     assessment.score >= 80 ? 'text-green-600 dark:text-green-500' :
                     assessment.score >= 50 ? 'text-yellow-600 dark:text-yellow-500' :
                     'text-red-600 dark:text-red-500'
                }`}>
                    {assessment.risk}
                </h2>

                <p className="text-center text-slate-600 dark:text-slate-300 mb-8 max-w-sm">
                    {assessment.details}
                </p>

                {/* AI Analysis Section */}
                {!aiAnalysis ? (
                    <button
                        onClick={generateAIAnalysis}
                        disabled={isAnalyzing}
                        className="w-full mb-6 p-4 rounded-xl bg-gradient-to-r from-blue-500 to-indigo-600 text-white font-bold shadow-lg shadow-blue-500/30 flex items-center justify-center gap-2 hover:scale-[1.02] transition-transform no-print"
                    >
                        {isAnalyzing ? (
                            <>
                                <span className="w-4 h-4 border-2 border-white/50 border-t-white rounded-full animate-spin"></span>
                                Analyzing...
                            </>
                        ) : (
                            <>
                                <span className="material-symbols-outlined">psychology</span>
                                Get Comprehensive AI Analysis
                            </>
                        )}
                    </button>
                ) : (
                    <div className="w-full bg-white dark:bg-card-dark rounded-xl p-5 shadow-md border border-indigo-100 dark:border-indigo-900/30 mb-6 animate-in slide-in-from-bottom-4 duration-500">
                        <div className="flex items-center gap-2 mb-3 text-indigo-600 dark:text-indigo-400">
                            <span className="material-symbols-outlined">auto_awesome</span>
                            <h3 className="font-bold">AI Health Analysis</h3>
                        </div>
                        <div className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-wrap">
                            {aiAnalysis}
                        </div>
                    </div>
                )}

                <div className="w-full bg-white dark:bg-card-dark rounded-xl p-4 shadow-sm border border-slate-100 dark:border-slate-800 space-y-4 mb-6">
                    <h3 className="font-bold dark:text-white border-b border-slate-100 dark:border-slate-800 pb-2">Your Vitals</h3>
                    <div className="flex justify-between items-center">
                        <span className="text-slate-500">Blood Pressure</span>
                        <span className="font-medium dark:text-white">{assessment.vitals.systolic} mmHg (Sys)</span>
                    </div>
                    <div className="flex justify-between items-center">
                        <span className="text-slate-500">Cholesterol</span>
                        <span className="font-medium dark:text-white">{assessment.vitals.cholesterol} mg/dL</span>
                    </div>
                    <div className="flex justify-between items-center">
                        <span className="text-slate-500">Date</span>
                        <span className="font-medium dark:text-white">{new Date(assessment.date).toLocaleDateString()}</span>
                    </div>
                </div>

                <div className="flex gap-3 w-full no-print">
                    <button
                        onClick={() => window.print()}
                        className="flex-1 py-4 bg-white dark:bg-card-dark border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-white rounded-xl font-bold flex items-center justify-center gap-2 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                    >
                        <span className="material-symbols-outlined">print</span>
                        Export PDF
                    </button>
                    <button
                        onClick={() => { setView('form'); setStep(1); }}
                        className="flex-1 py-4 bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-white rounded-xl font-bold hover:bg-slate-300 dark:hover:bg-slate-700 transition-colors"
                    >
                        Retake
                    </button>
                </div>
            </div>
        </div>
    );
  }

  // --- Form View Render ---
  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark flex flex-col relative">
      {/* Header */}
      <div className="flex items-center p-4 bg-background-light dark:bg-background-dark sticky top-0 z-10">
        <button onClick={handleBack} className="p-2 -ml-2 rounded-full hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-slate-900 dark:text-white">
          <span className="material-symbols-outlined">arrow_back</span>
        </button>
        <h2 className="flex-1 text-center font-bold text-lg dark:text-white">Health Monitoring</h2>
        <div className="w-10"></div>
      </div>

      {/* Feature Tabs */}
      <div className="px-6 mb-4">
          <div className="bg-slate-200 dark:bg-slate-800 p-1 rounded-xl flex">
              <button
                onClick={() => setActiveTab('Questionnaire')}
                className={`flex-1 py-2 text-sm font-bold rounded-lg transition-colors ${activeTab === 'Questionnaire' ? 'bg-white dark:bg-card-dark shadow text-primary' : 'text-slate-500'}`}
              >
                  Risk Assessment
              </button>
              <button
                onClick={() => setActiveTab('ECG')}
                className={`flex-1 py-2 text-sm font-bold rounded-lg transition-colors ${activeTab === 'ECG' ? 'bg-white dark:bg-card-dark shadow text-primary' : 'text-slate-500'}`}
              >
                  ECG Monitor
              </button>
          </div>
      </div>

      {/* Content Area */}
      {activeTab === 'ECG' ? (
          <div className="flex-1 px-6 pb-24 animate-in fade-in slide-in-from-right duration-300">
              <div className="mb-4 text-center">
                  <span className="material-symbols-outlined text-4xl text-red-500 mb-2">monitor_heart</span>
                  <h3 className="text-xl font-bold dark:text-white">ECG Rhythm Monitor</h3>
                  <p className="text-slate-500 text-sm mt-1">Record your heart rhythm using the sensor or camera simulation.</p>
              </div>

              <ECGRecorder />

              <div className="mt-6 p-4 bg-yellow-50 dark:bg-yellow-900/10 border border-yellow-200 dark:border-yellow-800 rounded-xl">
                  <div className="flex items-start gap-3">
                      <span className="material-symbols-outlined text-yellow-600 text-xl">info</span>
                      <div>
                          <h4 className="text-yellow-700 dark:text-yellow-500 font-bold text-sm">Medical Disclaimer</h4>
                          <p className="text-xs text-yellow-800/80 dark:text-yellow-200/70 mt-1 leading-relaxed">
                              This feature uses simulated data for demonstration purposes. It does not replace a clinical ECG or medical advice. If you feel unwell, contact emergency services.
                          </p>
                      </div>
                  </div>
              </div>
          </div>
      ) : (
          <>
            {/* Stepper for Questionnaire */}
            <div className="px-6 py-2 mb-2">
                <div className="flex items-center justify-between relative">
                <div className="absolute top-4 left-0 right-0 h-0.5 bg-slate-200 dark:bg-slate-700 -z-0 transform translate-y-[-50%]"></div>

                {[1, 2, 3].map((s) => (
                    <div key={s} className="relative z-10 flex flex-col items-center gap-1 bg-background-light dark:bg-background-dark px-2">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-colors duration-300 ${
                        step >= s
                        ? 'bg-primary text-white shadow-lg shadow-primary/30'
                        : 'bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 text-slate-400'
                    }`}>
                        {s}
                    </div>
                    <span className={`text-xs font-medium ${step >= s ? 'text-primary' : 'text-slate-400'}`}>
                        {s === 1 ? 'Personal' : s === 2 ? 'Medical' : 'Lifestyle'}
                    </span>
                    </div>
                ))}
                </div>
            </div>

            {/* Form Content */}
            <div className="flex-1 px-6 pt-4 pb-24">
                {step === 1 && (
                    <div className="space-y-6 animate-in slide-in-from-right duration-300">

                        {/* AI Auto-Fill Section */}
                        <div className="bg-gradient-to-r from-blue-600 to-indigo-600 rounded-xl p-4 text-white shadow-lg">
                            <div className="flex justify-between items-start mb-2">
                                <div className="flex items-center gap-2">
                                    <span className="material-symbols-outlined">description</span>
                                    <span className="font-bold text-sm">Have a Lab Report?</span>
                                </div>
                                {isProcessingFile && <span className="w-4 h-4 border-2 border-white/50 border-t-white rounded-full animate-spin"></span>}
                            </div>
                            <p className="text-xs text-blue-100 mb-3">Upload a photo of your results and we'll fill in the details for you.</p>
                            <button
                                onClick={() => fileInputRef.current?.click()}
                                disabled={isProcessingFile}
                                className="w-full py-2 bg-white text-blue-600 rounded-lg text-xs font-bold flex items-center justify-center gap-2 hover:bg-blue-50 transition-colors disabled:opacity-70"
                            >
                                {isProcessingFile ? "Analyzing..." : "Auto-fill from Report"}
                            </button>
                            <input
                                type="file"
                                ref={fileInputRef}
                                className="hidden"
                                accept="image/*"
                                onChange={handleFileUpload}
                            />
                        </div>

                        {uploadSummary && (
                            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 p-3 rounded-xl flex items-start gap-2 relative">
                                <span className="material-symbols-outlined text-blue-600 dark:text-blue-400 text-sm mt-0.5">info</span>
                                <div className="flex-1">
                                    <p className="text-xs font-bold text-blue-700 dark:text-blue-300 mb-1">Medical Summary</p>
                                    <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">{uploadSummary}</p>
                                </div>
                                <button onClick={() => setUploadSummary(null)} className="text-slate-400 hover:text-slate-600"><span className="material-symbols-outlined text-sm">close</span></button>
                            </div>
                        )}

                        <div>
                            <h1 className="text-2xl font-bold mb-2 dark:text-white">Personal & Risk Factors</h1>
                            <p className="text-slate-500">Please provide accurate information for a preliminary heart health indication.</p>
                        </div>

                        <div className="space-y-2">
                            <label className="text-sm font-medium dark:text-slate-200">Age</label>
                            <input
                            type="number"
                            placeholder="e.g., 52"
                            className="w-full p-4 rounded-xl bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 focus:ring-2 focus:ring-primary outline-none dark:text-white"
                            value={formData.age}
                            onChange={(e) => handleChange('age', e.target.value)}
                            />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium dark:text-slate-200">Gender</label>
                                <div className="relative">
                                    <select
                                        className="w-full p-4 rounded-xl bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 focus:ring-2 focus:ring-primary outline-none appearance-none dark:text-white"
                                        value={formData.gender}
                                        onChange={(e) => handleChange('gender', e.target.value)}
                                    >
                                        <option value="" disabled>Select</option>
                                        <option value="Male">Male</option>
                                        <option value="Female">Female</option>
                                        <option value="Other">Other</option>
                                    </select>
                                    <span className="material-symbols-outlined absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none">expand_more</span>
                                </div>
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium dark:text-slate-200">Race</label>
                                <div className="relative">
                                    <select
                                        className="w-full p-4 rounded-xl bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 focus:ring-2 focus:ring-primary outline-none appearance-none dark:text-white"
                                        value={formData.race}
                                        onChange={(e) => handleChange('race', e.target.value)}
                                    >
                                        <option value="" disabled>Select</option>
                                        <option value="White">White</option>
                                        <option value="Black">Black</option>
                                        <option value="Asian">Asian</option>
                                        <option value="Hispanic">Hispanic</option>
                                        <option value="Other">Other</option>
                                    </select>
                                    <span className="material-symbols-outlined absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none">expand_more</span>
                                </div>
                            </div>
                        </div>

                        {/* Blood Pressure Section */}
                        <div className="p-4 bg-slate-50 dark:bg-slate-800/30 rounded-2xl border border-slate-100 dark:border-slate-700">
                            <div className="flex items-center gap-2 mb-4">
                                <span className="material-symbols-outlined text-red-500">favorite</span>
                                <h3 className="font-bold dark:text-white">Blood Pressure</h3>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <label className="text-xs font-medium dark:text-slate-300">Systolic (Top)</label>
                                    <input
                                        type="number"
                                        placeholder="120"
                                        className="w-full p-3 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 focus:ring-2 focus:ring-primary outline-none dark:text-white"
                                        value={formData.systolic}
                                        onChange={(e) => handleChange('systolic', e.target.value)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-medium dark:text-slate-300">Diastolic (Bottom)</label>
                                    <input
                                        type="number"
                                        placeholder="80"
                                        className="w-full p-3 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 focus:ring-2 focus:ring-primary outline-none dark:text-white"
                                        value={formData.diastolic}
                                        onChange={(e) => handleChange('diastolic', e.target.value)}
                                    />
                                </div>
                            </div>

                            {/* Inline BP Feedback Badge */}
                            {(formData.systolic || formData.diastolic) && bpCategory.level !== 'unknown' && (
                                <div className={`mt-3 p-3 rounded-xl flex items-start gap-3 ${
                                    bpCategory.level === 'emergency' ? 'bg-red-500 text-white' :
                                    bpCategory.level === 'high' ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300' :
                                    bpCategory.level === 'moderate' ? 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300' :
                                    bpCategory.level === 'notice' ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300' :
                                    'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                                }`}>
                                    <span className="material-symbols-outlined text-lg mt-0.5">
                                        {bpCategory.level === 'ok' ? 'check_circle' : 'warning'}
                                    </span>
                                    <div>
                                        <p className="font-bold text-sm">{bpCategory.category}</p>
                                        <p className="text-xs opacity-90 mt-0.5">{bpCategory.description}</p>
                                    </div>
                                </div>
                            )}
                        </div>

                        <ToggleSwitch
                            label="Are you on BP medication?"
                            checked={formData.onBPMeds}
                            onChange={(val) => handleChange('onBPMeds', val)}
                            infoText="Indicates history of hypertension which is a risk factor."
                        />

                        {/* Cholesterol Section */}
                        <div className="p-4 bg-slate-50 dark:bg-slate-800/30 rounded-2xl border border-slate-100 dark:border-slate-700">
                            <div className="flex items-center gap-2 mb-4">
                                <span className="material-symbols-outlined text-blue-500">water_drop</span>
                                <h3 className="font-bold dark:text-white">Cholesterol</h3>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <label className="text-xs font-medium dark:text-slate-300">Total (mg/dL)</label>
                                    <input
                                        type="number"
                                        placeholder="200"
                                        className="w-full p-3 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 focus:ring-2 focus:ring-primary outline-none dark:text-white"
                                        value={formData.totalCholesterol}
                                        onChange={(e) => handleChange('totalCholesterol', e.target.value)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-medium dark:text-slate-300">HDL (mg/dL)</label>
                                    <input
                                        type="number"
                                        placeholder="50"
                                        className="w-full p-3 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 focus:ring-2 focus:ring-primary outline-none dark:text-white"
                                        value={formData.hdlCholesterol}
                                        onChange={(e) => handleChange('hdlCholesterol', e.target.value)}
                                    />
                                </div>
                            </div>
                        </div>

                        <ToggleSwitch
                            label="Do you smoke?"
                            checked={formData.isSmoker}
                            onChange={(val) => handleChange('isSmoker', val)}
                            infoText="Smoking significantly increases the risk of heart disease and stroke."
                        />

                        <ToggleSwitch
                            label="Do you have diabetes?"
                            checked={formData.hasDiabetes}
                            onChange={(val) => handleChange('hasDiabetes', val)}
                            infoText="Diabetes doubles the risk of heart disease. Managing blood sugar is crucial."
                        />

                        {/* Risk Summary Card */}
                        {showRiskSummary && (
                            <div className={`p-5 rounded-xl border-l-4 shadow-sm animate-in fade-in slide-in-from-bottom-4 duration-500 ${
                                riskIndicator.level === 'high' ? 'bg-red-50 dark:bg-red-900/10 border-red-500' :
                                riskIndicator.level === 'intermediate' ? 'bg-orange-50 dark:bg-orange-900/10 border-orange-500' :
                                riskIndicator.level === 'borderline' ? 'bg-yellow-50 dark:bg-yellow-900/10 border-yellow-500' :
                                'bg-green-50 dark:bg-green-900/10 border-green-500'
                            }`}>
                                <h4 className="text-sm font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2">Preliminary 10-Year ASCVD Risk Indicator</h4>
                                <div className="flex items-center gap-2 mb-2">
                                    <h3 className={`text-2xl font-bold ${
                                        riskIndicator.level === 'high' ? 'text-red-600 dark:text-red-400' :
                                        riskIndicator.level === 'intermediate' ? 'text-orange-600 dark:text-orange-400' :
                                        riskIndicator.level === 'borderline' ? 'text-yellow-600 dark:text-yellow-400' :
                                        'text-green-600 dark:text-green-400'
                                    }`}>
                                        {riskIndicator.level.toUpperCase()} RISK
                                    </h3>
                                </div>
                                <p className="text-slate-700 dark:text-slate-300 text-sm mb-4 leading-relaxed">{riskIndicator.description}</p>
                                <p className="text-xs text-slate-400 italic">
                                    *This is a simplified heuristic for informational purposes only. It does not replace a clinical assessment.
                                </p>
                            </div>
                        )}
                    </div>
                )}

                {step === 2 && (
                    <div className="space-y-6 animate-in slide-in-from-right duration-300">
                        <div>
                            <h1 className="text-2xl font-bold mb-2 dark:text-white">Medical History</h1>
                            <p className="text-slate-500">Tell us about your medical background to help us assess your risk.</p>
                        </div>

                        <div className="bg-white dark:bg-card-dark rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
                            <div className="p-4 border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
                                <h3 className="font-bold dark:text-white text-sm uppercase tracking-wide">Existing Conditions</h3>
                            </div>
                            <div className="p-4 space-y-2">
                                <ToggleSwitch
                                    label="History of Heart Attack or Stroke"
                                    checked={formData.historyHeartAttack}
                                    onChange={(val) => handleChange('historyHeartAttack', val)}
                                />
                                <ToggleSwitch
                                    label="Family History of Heart Disease"
                                    checked={formData.historyFamily}
                                    onChange={(val) => handleChange('historyFamily', val)}
                                    infoText="Immediate family (parents/siblings) diagnosed before age 55 (men) or 65 (women)."
                                />
                                <ToggleSwitch
                                    label="Chronic Kidney Disease"
                                    checked={formData.historyKidney}
                                    onChange={(val) => handleChange('historyKidney', val)}
                                />
                                <ToggleSwitch
                                    label="Atrial Fibrillation"
                                    checked={formData.historyAfib}
                                    onChange={(val) => handleChange('historyAfib', val)}
                                    infoText="Irregular, often rapid heart rate that can increase risk of stroke."
                                />
                            </div>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <label className="text-sm font-medium dark:text-slate-200 mb-2 block">Current Medications (Optional)</label>
                                <textarea
                                    rows={3}
                                    placeholder="e.g. Lisinopril, Atorvastatin, Metformin..."
                                    className="w-full p-4 rounded-xl bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 focus:ring-2 focus:ring-primary outline-none dark:text-white resize-none"
                                    value={formData.medications}
                                    onChange={(e) => handleChange('medications', e.target.value)}
                                />
                            </div>
                            <div>
                                <label className="text-sm font-medium dark:text-slate-200 mb-2 block">Allergies (Optional)</label>
                                <input
                                    type="text"
                                    placeholder="e.g. Penicillin, Shellfish"
                                    className="w-full p-4 rounded-xl bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 focus:ring-2 focus:ring-primary outline-none dark:text-white"
                                    value={formData.allergies}
                                    onChange={(e) => handleChange('allergies', e.target.value)}
                                />
                            </div>
                        </div>
                    </div>
                )}

                {step === 3 && (
                    <div className="space-y-6 animate-in slide-in-from-right duration-300">
                        <div>
                            <h1 className="text-2xl font-bold mb-2 dark:text-white">Lifestyle Factors</h1>
                            <p className="text-slate-500">Help us understand your daily habits to personalize your recommendations.</p>
                        </div>

                        {/* Diet Section */}
                        <div className="bg-white dark:bg-card-dark rounded-xl border border-slate-200 dark:border-slate-700 p-4 space-y-4">
                            <div className="flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-2">
                                <span className="material-symbols-outlined text-green-500">restaurant</span>
                                <h3 className="font-bold dark:text-white">Diet & Nutrition</h3>
                            </div>

                            <SelectionGroup
                                label="How often do you eat fruits & vegetables?"
                                options={['Rarely', '1-2 days/week', 'Some days', 'Daily']}
                                value={formData.fruitVegIntake}
                                onChange={(val) => handleChange('fruitVegIntake', val)}
                            />

                            <SelectionGroup
                                label="How often do you eat processed/fast food?"
                                options={['Rarely', 'Weekly', 'Multiple/week', 'Daily']}
                                value={formData.processedFoodIntake}
                                onChange={(val) => handleChange('processedFoodIntake', val)}
                            />
                        </div>

                        {/* Activity Section */}
                        <div className="bg-white dark:bg-card-dark rounded-xl border border-slate-200 dark:border-slate-700 p-4 space-y-4">
                            <div className="flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-2">
                                <span className="material-symbols-outlined text-blue-500">directions_run</span>
                                <h3 className="font-bold dark:text-white">Physical Activity</h3>
                            </div>

                            <div className="space-y-3">
                                <div className="flex justify-between items-end">
                                    <label className="text-sm font-medium dark:text-slate-200">Days per week (30+ mins)</label>
                                    <span className="text-2xl font-bold text-primary">{formData.exerciseDays}</span>
                                </div>
                                <input
                                    type="range"
                                    min="0"
                                    max="7"
                                    value={formData.exerciseDays}
                                    onChange={(e) => handleChange('exerciseDays', parseInt(e.target.value))}
                                    className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-primary"
                                />
                                <div className="flex justify-between text-xs text-slate-400">
                                    <span>0 days</span>
                                    <span>Every day</span>
                                </div>
                            </div>

                            {formData.exerciseDays > 0 && (
                                <SelectionGroup
                                    label="Typical Intensity"
                                    options={['Low (Walk)', 'Moderate (Jog)', 'High (Run/HIIT)']}
                                    value={formData.exerciseIntensity}
                                    onChange={(val) => handleChange('exerciseIntensity', val)}
                                />
                            )}
                        </div>

                        {/* Wellbeing Section */}
                        <div className="bg-white dark:bg-card-dark rounded-xl border border-slate-200 dark:border-slate-700 p-4 space-y-4">
                            <div className="flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-2">
                                <span className="material-symbols-outlined text-purple-500">psychology</span>
                                <h3 className="font-bold dark:text-white">Wellbeing & Habits</h3>
                            </div>

                            <SelectionGroup
                                label="Average Sleep per Night"
                                options={['< 5 hrs', '5-6 hrs', '6-8 hrs', '9+ hrs']}
                                value={formData.sleepHours}
                                onChange={(val) => handleChange('sleepHours', val)}
                            />

                            <SelectionGroup
                                label="Daily Stress Level"
                                options={['Low', 'Moderate', 'High', 'Severe']}
                                value={formData.stressLevel}
                                onChange={(val) => handleChange('stressLevel', val)}
                            />

                            <SelectionGroup
                                label="Alcohol Consumption"
                                options={['None', 'Socially', 'Moderate', 'Heavy']}
                                value={formData.alcoholConsumption}
                                onChange={(val) => handleChange('alcoholConsumption', val)}
                            />
                        </div>
                    </div>
                )}

                {/* Sticky Footer for Questionnaire */}
                <div className="fixed bottom-0 left-0 right-0 p-4 bg-white dark:bg-background-dark border-t border-slate-100 dark:border-slate-800 z-20">
                    <div className="max-w-md mx-auto">
                        <button
                            onClick={handleContinue}
                            className="w-full h-14 bg-primary hover:bg-primary-dark text-white rounded-xl font-bold flex items-center justify-center gap-2 transition-colors shadow-lg shadow-primary/30"
                        >
                            <span>{step === 3 ? 'View Final Report' : 'Continue'}</span>
                            <span className="material-symbols-outlined">arrow_forward</span>
                        </button>
                        <p className="text-center text-xs text-slate-400 mt-3 flex items-center justify-center gap-1">
                            <span className="material-symbols-outlined text-xs">lock</span>
                            Your data is secure.
                        </p>
                    </div>
                </div>
            </div>
          </>
      )}

      {/* Emergency Modal */}
      {isEmergencyModalVisible && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-in fade-in duration-300"></div>
            <div className="relative bg-white dark:bg-card-dark rounded-2xl p-6 w-full max-w-sm shadow-2xl animate-in zoom-in-95 duration-300">
                <div className="flex flex-col items-center text-center">
                    <div className="w-20 h-20 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center mb-4 animate-pulse">
                        <span className="material-symbols-outlined text-red-600 text-5xl">warning</span>
                    </div>
                    <h2 className="text-2xl font-bold text-red-600 dark:text-red-500 mb-2">Hypertensive Crisis!</h2>
                    <p className="text-slate-600 dark:text-slate-300 mb-6 leading-relaxed">
                        Your blood pressure readings ({formData.systolic}/{formData.diastolic}) indicate a critical condition. This is a medical emergency.
                    </p>

                    <button className="w-full py-3 bg-red-600 hover:bg-red-700 text-white rounded-xl font-bold flex items-center justify-center gap-2 mb-3 transition-colors shadow-lg shadow-red-600/30">
                        <span className="material-symbols-outlined">call</span>
                        Call Emergency Services
                    </button>

                    <button className="w-full py-3 bg-slate-100 dark:bg-slate-800 text-blue-600 dark:text-blue-400 rounded-xl font-bold flex items-center justify-center gap-2 mb-6 transition-colors">
                        <span className="material-symbols-outlined">near_me</span>
                        Find Nearest Clinic
                    </button>

                    <button
                        onClick={() => setIsEmergencyModalVisible(false)}
                        className="text-sm text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 underline"
                    >
                        I understand the risk (Dismiss)
                    </button>
                </div>
            </div>
        </div>
      )}

    </div>
  );
};

export default AssessmentScreen;
