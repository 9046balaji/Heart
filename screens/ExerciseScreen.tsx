
import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { workoutData } from '../data/workouts';
import { statsData, personalBestsData } from '../data/stats';
import { trophies } from '../data/gamification';
import { ExercisePlan, PlanDay, Workout } from '../types';
import { apiClient } from '../services/apiClient';
import { AreaChart, Area, BarChart, Bar, XAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import CommunityScreen from './CommunityScreen';
import StatsScreen from './StatsScreen';
import CoachScreen from './CoachScreen';

const daysOfWeek = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

// --- Template Data Mock ---
const TEMPLATE_CATEGORIES = ['Full Body', 'Core', 'Upper Body', 'Lower Body', 'Cardio', 'Flexibility'];

const TEMPLATES: Record<string, { id: string, name: string, desc: string, days: number, exercises: string[] }[]> = {
    'Full Body': [
        { id: 't_fb_1', name: 'Total Body Tone', desc: 'A balanced mix of strength and cardio for general fitness.', days: 3, exercises: ['w_strength_25_full_body_bw', 'w_cardio_20_jumping_jacks', 'w_flexibility_10_full_body'] },
        { id: 't_fb_2', name: 'Advanced Strength', desc: 'Heavy dumbbell work targeting all muscle groups.', days: 4, exercises: ['w_dumbbell_20_full_body', 'w_strength_30_full_body_db', 'w_core_05_quick', 'w_stretch_07_post_workout'] }
    ],
    'Core': [
        { id: 't_core_1', name: 'Core Crusher', desc: 'Intense focus on abs and lower back stability.', days: 3, exercises: ['w_strength_10_core', 'w_strength_10_abs_hips', 'w_pilates_10_core'] },
        { id: 't_core_2', name: 'Pilates Power', desc: 'Mat-based pilates for a strong core.', days: 2, exercises: ['w_pilates_15_mat', 'w_balance_10_dynamic'] }
    ],
    'Upper Body': [
        { id: 't_up_1', name: 'Arm Sculpt', desc: 'Tone arms and shoulders with light weights.', days: 2, exercises: ['w_strength_10_arms', 'w_strength_12_upper_body'] },
        { id: 't_up_2', name: 'Band Upper Body', desc: 'Resistance band focus for upper body strength.', days: 3, exercises: ['w_band_10_pull_aparts', 'w_strength_15_upper_bands', 'w_stretch_05_standing'] }
    ],
    'Lower Body': [
        { id: 't_low_1', name: 'Leg Day Essentials', desc: 'Squats and lunges to build leg strength.', days: 2, exercises: ['w_bodyweight_10_squats', 'w_strength_15_lower_body_bw'] },
        { id: 't_low_2', name: 'Glute Focus', desc: 'Targeted glute activation and strength.', days: 3, exercises: ['w_glute_08_bridges', 'w_strength_10_bands_lower', 'w_hip_10_openers'] }
    ],
    'Cardio': [
        { id: 't_cardio_1', name: 'Cardio Blast', desc: 'High energy routine to burn calories.', days: 4, exercises: ['w_cardio_10_hiit_beginner', 'w_cardio_20_jumping_jacks', 'w_cardio_15_low_impact', 'w_walk_20_intervals'] },
        { id: 't_cardio_2', name: 'Dance Party', desc: 'Fun dance-based cardio workouts.', days: 3, exercises: ['w_dance_15_cardio', 'w_cardio_10_dance', 'w_cardio_10_step_touch'] }
    ],
    'Flexibility': [
        { id: 't_flex_1', name: 'Daily Stretch', desc: 'Improve mobility and reduce stiffness.', days: 7, exercises: ['w_stretch_05_standing', 'w_mobility_15_morning', 'w_stretch_05_sleep', 'w_yoga_10_gentle'] },
        { id: 't_flex_2', name: 'Yoga Flow', desc: 'Vinyasa and Hatha flows for flexibility.', days: 3, exercises: ['w_yoga_15_flow', 'w_hatha_20_flow', 'w_yoga_25_restorative'] }
    ]
};

// --- Sub-Components ---

const MiniAudioPlayer: React.FC<{ workout: Workout, onClose: () => void }> = ({ workout, onClose }) => {
    const [isPlaying, setIsPlaying] = useState(false);
    const [progress, setProgress] = useState(0);
    const [caption, setCaption] = useState("Coach: Ready to start? Let's warm up.");
    const [elapsed, setElapsed] = useState(0);

    useEffect(() => {
        setIsPlaying(true);
        const interval = setInterval(() => {
            if (isPlaying) {
                setElapsed(prev => prev + 1);
                setProgress(prev => Math.min(100, prev + 0.1));

                // Simulated script
                if (elapsed === 5) setCaption("Coach: Keep a steady pace.");
                if (elapsed === 15) setCaption("Coach: You're doing great! Check your posture.");
                if (elapsed === 30) setCaption("Coach: We're approaching the first kilometer.");
            }
        }, 1000);
        return () => clearInterval(interval);
    }, [isPlaying, elapsed]);

    return (
        <div className="fixed bottom-24 left-4 right-4 bg-slate-900/90 backdrop-blur-xl border border-slate-700 p-4 rounded-2xl shadow-2xl z-50 animate-in slide-in-from-bottom-10 fade-in duration-300 flex items-center gap-4">
            <div className="w-12 h-12 bg-primary/20 rounded-full flex items-center justify-center shrink-0 relative">
                {isPlaying && <span className="absolute inset-0 rounded-full border-2 border-primary animate-ping opacity-50"></span>}
                <span className="material-symbols-outlined text-primary">{workout.intensity === 'high' ? 'directions_run' : 'headphones'}</span>
            </div>
            <div className="flex-1 min-w-0">
                <p className="text-xs text-primary font-bold uppercase tracking-wider mb-0.5">Audio Guide Active</p>
                <p className="text-white text-sm font-medium truncate">{workout.title}</p>
                <p className="text-slate-400 text-xs mt-1 italic truncate">"{caption}"</p>
                <div className="w-full bg-slate-700 h-1 rounded-full mt-2 overflow-hidden">
                    <div className="bg-primary h-full transition-all duration-1000" style={{ width: `${progress}%` }}></div>
                </div>
            </div>
            <div className="flex items-center gap-2">
                <button onClick={() => setIsPlaying(!isPlaying)} className="w-10 h-10 bg-white text-slate-900 rounded-full flex items-center justify-center hover:bg-slate-200 transition-colors">
                    <span className="material-symbols-outlined filled">{isPlaying ? 'pause' : 'play_arrow'}</span>
                </button>
                <button onClick={onClose} className="w-8 h-8 text-slate-400 hover:text-white rounded-full flex items-center justify-center transition-colors">
                    <span className="material-symbols-outlined">close</span>
                </button>
            </div>
        </div>
    );
};

interface WorkoutCardProps {
  workout: Workout;
  onClick: () => void;
  onAudioClick?: () => void;
}

const WorkoutCard: React.FC<WorkoutCardProps> = ({ workout, onClick, onAudioClick }) => {
    const [isHovered, setIsHovered] = useState(false);
    const videoRef = useRef<HTMLVideoElement>(null);

    // Only attempt preview for MP4s (mostly Pexels in data)
    const canPreview = workout.videoUrl && !workout.videoUrl.includes('youtube');

    useEffect(() => {
        if (isHovered && canPreview && videoRef.current) {
            videoRef.current.play().catch(() => {});
        } else if (!isHovered && videoRef.current) {
            videoRef.current.pause();
            videoRef.current.currentTime = 0;
        }
    }, [isHovered, canPreview]);

    const getImageUrl = (url: string, seed: string) => {
        if (url.startsWith('/images/')) {
            return `https://picsum.photos/seed/${seed}/800/600`;
        }
        return url;
    };

    return (
        <div
            onClick={onClick}
            className="flex flex-col gap-2 cursor-pointer group relative"
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
        >
            <div className="relative w-full aspect-[4/3] rounded-xl overflow-hidden bg-slate-200 dark:bg-slate-800 transition-transform duration-300 group-hover:scale-[1.02] shadow-sm group-hover:shadow-lg">
                {/* Static Image */}
                <div
                    className={`absolute inset-0 bg-cover bg-center transition-opacity duration-300 ${isHovered && canPreview ? 'opacity-0' : 'opacity-100'}`}
                    style={{backgroundImage: `url(${getImageUrl(workout.image, workout.id)})`}}
                ></div>

                {/* Video Preview */}
                {canPreview && (
                    <video
                        ref={videoRef}
                        src={workout.videoUrl}
                        muted
                        loop
                        playsInline
                        className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-300 ${isHovered ? 'opacity-100' : 'opacity-0'}`}
                    />
                )}

                {/* Overlay Badge */}
                {isHovered && canPreview && (
                    <div className="absolute top-2 left-2 bg-black/60 backdrop-blur-sm px-2 py-1 rounded-md text-[10px] font-bold text-white flex items-center gap-1">
                        <span className="material-symbols-outlined text-[10px] animate-pulse text-red-500">videocam</span> Preview
                    </div>
                )}

                {/* Audio Guide Button (if applicable) */}
                {(workout.category === 'Cardio' && workout.accessibility.includes('outdoor')) && (
                    <button
                        onClick={(e) => { e.stopPropagation(); if (onAudioClick) onAudioClick(); }}
                        className="absolute bottom-2 right-2 w-8 h-8 bg-black/60 backdrop-blur-sm rounded-full flex items-center justify-center text-white hover:bg-primary hover:text-slate-900 transition-colors z-20"
                        title="Start Audio Guide"
                    >
                        <span className="material-symbols-outlined text-sm">headphones</span>
                    </button>
                )}

                <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"></div>
                <button className="absolute top-2 right-2 w-8 h-8 flex items-center justify-center rounded-full bg-black/30 backdrop-blur-sm text-white hover:bg-black/50 transition-colors">
                    <span className="material-symbols-outlined text-lg">add</span>
                </button>
            </div>
            <div>
                <p className="text-base font-medium leading-normal text-slate-900 dark:text-white truncate group-hover:text-primary transition-colors">
                    {workout.title}
                </p>
                <p className="text-sm font-normal leading-normal text-slate-500 dark:text-slate-400 truncate">
                    {workout.category}, {workout.equipment[0] === 'none' ? 'Bodyweight' : workout.equipment[0].replace(/-/g, ' ')}
                </p>
            </div>
        </div>
    );
};

const RemindersOverlay: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const [enabled, setEnabled] = useState(true);
  return <div className="fixed inset-0 bg-black/50 z-50" onClick={onClose}></div>;
};

const ExerciseScreen: React.FC = () => {
  const navigate = useNavigate();
  const [view, setView] = useState<'dashboard' | 'wizard'>('dashboard');
  const [activeTab, setActiveTab] = useState<'plan' | 'stats' | 'community' | 'coach'>('plan');
  const [showReminders, setShowReminders] = useState(false);
  const [plan, setPlan] = useState<ExercisePlan | null>(null);
  const [activeAudioGuide, setActiveAudioGuide] = useState<Workout | null>(null);

  // Search & Filter State
  const [showFilters, setShowFilters] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterCategory, setFilterCategory] = useState('All');
  const [displayLimit, setDisplayLimit] = useState(8);

  // Readiness State
  const [readinessScore, setReadinessScore] = useState(85);

  useEffect(() => {
    const savedPlan = localStorage.getItem('user_exercise_plan');
    if (savedPlan) {
      setPlan(JSON.parse(savedPlan));
    }
  }, []);

  const savePlan = (newPlan: ExercisePlan) => {
    setPlan(newPlan);
    localStorage.setItem('user_exercise_plan', JSON.stringify(newPlan));
    setView('dashboard');
  };

  const getWorkoutById = (id: string): Workout | undefined => {
    return workoutData.find(w => w.id === id);
  };

  // --- Wizard View Implementation ---
  const WizardView = () => {
    const [path, setPath] = useState<'menu' | 'templates' | 'scratch'>('menu');
    const [isGenerating, setIsGenerating] = useState(false);

    // Scratch Builder State
    const [scratchStep, setScratchStep] = useState(1);
    const [scratchData, setScratchData] = useState({
        name: '',
        goal: '',
        frequency: 3,
        exercises: [] as string[]
    });
    const [scratchSearch, setScratchSearch] = useState('');
    const [showPreview, setShowPreview] = useState(false);

    // Template State
    const [selectedCategory, setSelectedCategory] = useState('Full Body');
    const [previewTemplate, setPreviewTemplate] = useState<any>(null);

    // AI Quick Start Logic
    const handleQuickStart = async () => {
        setIsGenerating(true);
        try {
            setTimeout(() => {
                const newPlan: ExercisePlan = {
                    id: `plan_${Date.now()}`,
                    name: "AI Personalized Plan",
                    days: [], // Populate
                    weeklyTargetMinutes: 150,
                    createdAt: new Date().toISOString(),
                    goal: 'Heart Health'
                };
                // Populate random days
                const days: PlanDay[] = [];
                for(let i=0; i<7; i++) days.push({ day: daysOfWeek[i], workoutId: i%2===0 ? workoutData[i].id : 'rest', completed: false });
                newPlan.days = days;
                savePlan(newPlan);
                setIsGenerating(false);
            }, 1500);
        } catch (e) { setIsGenerating(false); }
    };

    // --- Template Logic ---
    const handleSelectTemplate = (t: any) => {
        const days: PlanDay[] = [];
        let exIndex = 0;
        for (let i = 0; i < 7; i++) {
            const isWorkoutDay = i % 2 === 0 && exIndex < t.days;
            if (isWorkoutDay) {
                days.push({ day: daysOfWeek[i], workoutId: t.exercises[exIndex % t.exercises.length], completed: false });
                exIndex++;
            } else {
                days.push({ day: daysOfWeek[i], workoutId: 'rest', completed: false });
            }
        }
        const newPlan: ExercisePlan = {
            id: `plan_${Date.now()}`,
            name: t.name,
            goal: t.desc,
            days: days,
            weeklyTargetMinutes: days.reduce((acc, curr) => curr.workoutId !== 'rest' ? acc + 30 : acc, 0),
            createdAt: new Date().toISOString()
        };
        savePlan(newPlan);
    };

    // --- Scratch Logic ---
    const toggleExercise = (id: string) => {
        if (scratchData.exercises.includes(id)) {
            setScratchData(prev => ({ ...prev, exercises: prev.exercises.filter(e => e !== id) }));
        } else {
            setScratchData(prev => ({ ...prev, exercises: [...prev.exercises, id] }));
        }
    };

    const confirmScratchPlan = () => {
        const days: PlanDay[] = [];
        const exercises = scratchData.exercises;

        let exIndex = 0;
        for (let i = 0; i < 7; i++) {
            const shouldWorkout = (i < scratchData.frequency * 2) && (i % 2 === 0 || scratchData.frequency > 4);
            if (exercises.length > 0 && exIndex < scratchData.frequency) {
                 days.push({ day: daysOfWeek[i], workoutId: exercises[exIndex % exercises.length], completed: false });
                 exIndex++;
            } else if (days.length < 7) {
                 days.push({ day: daysOfWeek[i], workoutId: 'rest', completed: false });
            }
        }
        while (days.length < 7) days.push({ day: daysOfWeek[days.length], workoutId: 'rest', completed: false });

        const newPlan: ExercisePlan = {
            id: `plan_${Date.now()}`,
            name: scratchData.name || 'Custom Plan',
            goal: scratchData.goal,
            days: days,
            weeklyTargetMinutes: 100,
            createdAt: new Date().toISOString()
        };
        savePlan(newPlan);
    };

    const renderMenu = () => (
        <div className="space-y-4 p-6">
            <h3 className="text-2xl font-bold dark:text-white mb-4">How would you like to start?</h3>

            <button onClick={() => setPath('templates')} className="w-full bg-white dark:bg-card-dark p-5 rounded-2xl border border-slate-200 dark:border-slate-700 text-left hover:border-primary transition-all group shadow-sm">
                <div className="flex justify-between items-start mb-2">
                    <span className="material-symbols-outlined text-3xl text-purple-500">dashboard</span>
                    <span className="material-symbols-outlined text-slate-300 group-hover:text-primary transition-colors">arrow_forward</span>
                </div>
                <h4 className="font-bold text-xl dark:text-white">Popular Templates</h4>
                <p className="text-slate-500 text-sm mt-1">Browse ready-made plans for every goal.</p>
            </button>

            <button onClick={() => setPath('scratch')} className="w-full bg-white dark:bg-card-dark p-5 rounded-2xl border border-slate-200 dark:border-slate-700 text-left hover:border-primary transition-all group shadow-sm">
                <div className="flex justify-between items-start mb-2">
                    <span className="material-symbols-outlined text-3xl text-blue-500">build</span>
                    <span className="material-symbols-outlined text-slate-300 group-hover:text-primary transition-colors">arrow_forward</span>
                </div>
                <h4 className="font-bold text-xl dark:text-white">Build from Scratch</h4>
                <p className="text-slate-500 text-sm mt-1">Select exercises one-by-one to fit your needs.</p>
            </button>

            <button onClick={handleQuickStart} disabled={isGenerating} className="w-full bg-gradient-to-r from-green-500 to-emerald-600 p-5 rounded-2xl text-white text-left shadow-lg hover:shadow-xl transition-all">
                <div className="flex justify-between items-start mb-2">
                    {isGenerating ? <span className="w-8 h-8 border-4 border-white/30 border-t-white rounded-full animate-spin"></span> : <span className="material-symbols-outlined text-3xl">auto_awesome</span>}
                </div>
                <h4 className="font-bold text-xl">{isGenerating ? 'Designing Plan...' : 'AI Quick Start'}</h4>
                <p className="text-green-100 text-sm mt-1">Generate a plan instantly based on your profile.</p>
            </button>
        </div>
    );

    const renderTemplates = () => (
        <div className="flex flex-col h-full">
            <div className="px-6 py-4 overflow-x-auto no-scrollbar border-b border-slate-100 dark:border-slate-800">
                <div className="flex gap-2">
                    {TEMPLATE_CATEGORIES.map(cat => (
                        <button
                            key={cat}
                            onClick={() => setSelectedCategory(cat)}
                            className={`px-4 py-2 rounded-full text-sm font-bold whitespace-nowrap transition-colors ${selectedCategory === cat ? 'bg-primary text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'}`}
                        >
                            {cat}
                        </button>
                    ))}
                </div>
            </div>
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {TEMPLATES[selectedCategory]?.map(t => (
                    <div key={t.id} className="bg-white dark:bg-card-dark p-4 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm">
                        <div className="flex justify-between items-start mb-2">
                            <h4 className="font-bold text-lg dark:text-white">{t.name}</h4>
                            <span className="text-xs bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded text-slate-600 dark:text-slate-300">{t.days} Days/Week</span>
                        </div>
                        <p className="text-sm text-slate-500 mb-4">{t.desc}</p>
                        <div className="flex gap-2">
                            <button onClick={() => setPreviewTemplate(t)} className="flex-1 py-2 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-bold text-slate-600 dark:text-slate-300">Preview</button>
                            <button onClick={() => handleSelectTemplate(t)} className="flex-1 py-2 bg-primary text-white rounded-lg text-sm font-bold">Select</button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );

    const renderScratch = () => (
        <div className="flex flex-col h-full">
            {scratchStep === 1 && (
                <div className="p-6 space-y-6">
                    <h3 className="text-xl font-bold dark:text-white">Plan Details</h3>
                    <div className="space-y-4">
                        <div>
                            <label className="text-xs font-bold text-slate-500 uppercase">Plan Name</label>
                            <input
                                type="text" value={scratchData.name} onChange={e => setScratchData({...scratchData, name: e.target.value})}
                                placeholder="e.g. Morning Cardio"
                                className="w-full mt-1 p-3 bg-slate-100 dark:bg-slate-800 rounded-xl border-none outline-none dark:text-white focus:ring-2 focus:ring-primary"
                            />
                        </div>
                        <div>
                            <label className="text-xs font-bold text-slate-500 uppercase">Goal / Description</label>
                            <input
                                type="text" value={scratchData.goal} onChange={e => setScratchData({...scratchData, goal: e.target.value})}
                                placeholder="e.g. Lose weight, Build muscle"
                                className="w-full mt-1 p-3 bg-slate-100 dark:bg-slate-800 rounded-xl border-none outline-none dark:text-white focus:ring-2 focus:ring-primary"
                            />
                        </div>
                        <div>
                            <div className="flex justify-between">
                                <label className="text-xs font-bold text-slate-500 uppercase">Frequency</label>
                                <span className="text-sm font-bold text-primary">{scratchData.frequency} days/week</span>
                            </div>
                            <input
                                type="range" min="1" max="7" value={scratchData.frequency} onChange={e => setScratchData({...scratchData, frequency: parseInt(e.target.value)})}
                                className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-primary mt-2"
                            />
                        </div>
                    </div>
                    <button onClick={() => setScratchStep(2)} disabled={!scratchData.name} className="w-full py-3 bg-primary text-white rounded-xl font-bold disabled:opacity-50 mt-4">
                        Next: Add Exercises
                    </button>
                </div>
            )}

            {scratchStep === 2 && (
                <div className="flex flex-col h-full">
                    <div className="p-4 border-b border-slate-100 dark:border-slate-800">
                        <div className="relative">
                            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">search</span>
                            <input
                                type="text" placeholder="Search exercises..." value={scratchSearch} onChange={e => setScratchSearch(e.target.value)}
                                className="w-full pl-10 pr-4 py-2 bg-slate-100 dark:bg-slate-800 rounded-xl border-none outline-none dark:text-white"
                            />
                        </div>
                    </div>
                    <div className="flex-1 overflow-y-auto p-4 space-y-2">
                        {workoutData.filter(w => w.title.toLowerCase().includes(scratchSearch.toLowerCase())).map(w => {
                            const isSelected = scratchData.exercises.includes(w.id);
                            return (
                                <div key={w.id} onClick={() => toggleExercise(w.id)} className={`flex items-center p-3 rounded-xl border cursor-pointer transition-all ${isSelected ? 'border-primary bg-primary/5' : 'border-slate-100 dark:border-slate-800 bg-white dark:bg-card-dark'}`}>
                                    <div className={`w-5 h-5 rounded border flex items-center justify-center mr-3 ${isSelected ? 'bg-primary border-primary text-white' : 'border-slate-300 dark:border-slate-600'}`}>
                                        {isSelected && <span className="material-symbols-outlined text-sm">check</span>}
                                    </div>
                                    <div className="flex-1">
                                        <h4 className="font-bold text-sm dark:text-white">{w.title}</h4>
                                        <p className="text-xs text-slate-500">{w.category} • {w.duration_min} min</p>
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    {/* Live Preview / Action Bar */}
                    <div className="p-4 border-t border-slate-100 dark:border-slate-800 bg-white dark:bg-card-dark shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)] z-[60]">
                        <div
                            className="flex justify-between items-center mb-3 cursor-pointer"
                            onClick={() => setShowPreview(!showPreview)}
                        >
                            <div>
                                <p className="text-xs text-slate-500 font-bold uppercase">{scratchData.name || 'Plan'}</p>
                                <p className="text-sm font-bold text-primary">{scratchData.exercises.length} exercises selected</p>
                            </div>
                            <span className="material-symbols-outlined text-slate-400">{showPreview ? 'expand_more' : 'expand_less'}</span>
                        </div>

                        {showPreview && (
                            <div className="mb-4 max-h-40 overflow-y-auto space-y-1 border-t border-slate-100 dark:border-slate-700 pt-2">
                                {scratchData.exercises.map(id => {
                                    const w = getWorkoutById(id);
                                    return w ? <div key={id} className="text-xs dark:text-white flex justify-between"><span>{w.title}</span><button onClick={(e) => {e.stopPropagation(); toggleExercise(id);}} className="text-red-500">×</button></div> : null;
                                })}
                                {scratchData.exercises.length === 0 && <p className="text-xs text-slate-400 italic">No exercises added.</p>}
                            </div>
                        )}

                        <div className="flex gap-2">
                            <button onClick={() => setScratchStep(1)} className="px-4 py-3 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-bold rounded-xl">Back</button>
                            <button onClick={() => setScratchStep(3)} disabled={scratchData.exercises.length === 0} className="flex-1 py-3 bg-primary text-white font-bold rounded-xl disabled:opacity-50">Review</button>
                        </div>
                    </div>
                </div>
            )}

            {scratchStep === 3 && (
                <div className="p-6 flex flex-col h-full">
                    <h3 className="text-2xl font-bold dark:text-white mb-6">Review Plan</h3>

                    <div className="bg-white dark:bg-card-dark p-4 rounded-xl border border-slate-200 dark:border-slate-700 mb-6">
                        <h4 className="font-bold text-lg dark:text-white">{scratchData.name}</h4>
                        <p className="text-sm text-slate-500 mb-2">{scratchData.goal}</p>
                        <div className="flex gap-4 text-xs font-medium text-slate-600 dark:text-slate-400">
                            <span className="flex items-center gap-1"><span className="material-symbols-outlined text-sm">calendar_month</span> {scratchData.frequency} Days/Wk</span>
                            <span className="flex items-center gap-1"><span className="material-symbols-outlined text-sm">fitness_center</span> {scratchData.exercises.length} Exercises</span>
                        </div>
                    </div>

                    <h4 className="text-sm font-bold text-slate-500 uppercase mb-3">Exercises Included</h4>
                    <div className="flex-1 overflow-y-auto space-y-2 mb-6">
                        {scratchData.exercises.map((id, i) => {
                            const w = getWorkoutById(id);
                            return w ? (
                                <div key={i} className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                                    <span className="text-sm dark:text-white font-medium">{w.title}</span>
                                    <span className="text-xs text-slate-400">{w.duration_min}m</span>
                                </div>
                            ) : null;
                        })}
                    </div>

                    <div className="flex gap-3 mt-auto">
                        <button onClick={() => setScratchStep(2)} className="flex-1 py-3 border border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300 font-bold rounded-xl">Edit</button>
                        <button onClick={confirmScratchPlan} className="flex-[2] py-3 bg-primary text-white font-bold rounded-xl shadow-lg shadow-primary/20">Confirm & Save</button>
                    </div>
                </div>
            )}
        </div>
    );

    return (
        <div className="fixed top-0 bottom-0 left-1/2 w-full max-w-md -translate-x-1/2 z-[60] bg-background-light dark:bg-background-dark flex flex-col animate-in slide-in-from-bottom duration-300 shadow-2xl">
            <div className="flex items-center p-4 border-b border-slate-200 dark:border-slate-800">
                <button onClick={() => { if(path === 'menu') { setView('dashboard'); } else { setPath('menu'); setScratchStep(1); } }} className="p-2 -ml-2 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-900 dark:text-white transition-colors">
                    <span className="material-symbols-outlined">{path === 'menu' ? 'close' : 'arrow_back'}</span>
                </button>
                <h2 className="flex-1 text-center font-bold text-lg dark:text-white">
                    {path === 'menu' ? 'Create Plan' : path === 'templates' ? 'Templates' : 'Build Plan'}
                </h2>
                <div className="w-10"></div>
            </div>

            <div className="flex-1 overflow-hidden relative">
                {path === 'menu' && renderMenu()}
                {path === 'templates' && renderTemplates()}
                {path === 'scratch' && renderScratch()}
            </div>

            {/* Template Preview Modal */}
            {previewTemplate && (
                <div className="absolute inset-0 z-10 bg-black/60 backdrop-blur-sm flex items-end sm:items-center justify-center p-4 animate-in fade-in">
                    <div className="bg-white dark:bg-card-dark w-full max-w-sm rounded-2xl p-6 shadow-2xl animate-in slide-in-from-bottom-10">
                        <h3 className="text-xl font-bold dark:text-white mb-1">{previewTemplate.name}</h3>
                        <p className="text-sm text-slate-500 mb-4">{previewTemplate.desc}</p>

                        <div className="bg-slate-50 dark:bg-slate-800 p-3 rounded-lg mb-4">
                            <p className="text-xs font-bold text-slate-500 uppercase mb-2">Included Workouts</p>
                            <ul className="space-y-1">
                                {previewTemplate.exercises.map((eid: string) => (
                                    <li key={eid} className="text-sm dark:text-slate-200 flex items-center gap-2">
                                        <span className="w-1.5 h-1.5 rounded-full bg-primary"></span>
                                        {getWorkoutById(eid)?.title}
                                    </li>
                                ))}
                            </ul>
                        </div>

                        <div className="flex gap-3">
                            <button onClick={() => setPreviewTemplate(null)} className="flex-1 py-3 bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-white font-bold rounded-xl">Back</button>
                            <button onClick={() => handleSelectTemplate(previewTemplate)} className="flex-1 py-3 bg-primary text-white font-bold rounded-xl shadow-lg shadow-primary/20">Use This Plan</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
  };

  // Filter Logic:
  // If plan exists, collect unique exercises from plan.days
  const planWorkoutIds = plan
    ? Array.from(new Set(plan.days.map(d => d.workoutId).filter(id => id !== 'rest')))
    : [];

  // If plan exists, constrain source to plan exercises. Otherwise show all.
  const sourceWorkouts = (plan && planWorkoutIds.length > 0)
    ? workoutData.filter(w => planWorkoutIds.includes(w.id))
    : workoutData;

  const filteredWorkouts = sourceWorkouts.filter(w => w.title.toLowerCase().includes(searchQuery.toLowerCase()));

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark">
      {/* Header with Tabs */}
      <div className="sticky top-0 bg-background-light dark:bg-background-dark z-10">
          <div className="flex items-center justify-between p-4 pb-2 border-b border-slate-100 dark:border-slate-800/50">
             <button onClick={() => navigate('/dashboard')} className="p-2 -ml-2 rounded-full text-slate-800 dark:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
                <span className="material-symbols-outlined">arrow_back_ios_new</span>
             </button>
            <h2 className="font-bold text-lg dark:text-white">Fitness</h2>
            <button onClick={() => setShowReminders(true)} className="p-2 rounded-full text-slate-800 dark:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors relative">
               <span className="material-symbols-outlined">notifications</span>
            </button>
          </div>

          <div className="flex px-4 border-b border-slate-200 dark:border-slate-800 overflow-x-auto no-scrollbar">
            <button
                onClick={() => setActiveTab('plan')}
                className={`flex-1 py-3 text-sm font-bold border-b-[3px] transition-colors whitespace-nowrap px-3 ${activeTab === 'plan' ? 'border-primary text-slate-900 dark:text-white' : 'border-transparent text-slate-500 dark:text-slate-400'}`}
            >
                My Plan
            </button>
            <button
                onClick={() => setActiveTab('coach')}
                className={`flex-1 py-3 text-sm font-bold border-b-[3px] transition-colors whitespace-nowrap px-3 ${activeTab === 'coach' ? 'border-primary text-slate-900 dark:text-white' : 'border-transparent text-slate-500 dark:text-slate-400'}`}
            >
                AI Coach
            </button>
            <button
                onClick={() => setActiveTab('stats')}
                className={`flex-1 py-3 text-sm font-bold border-b-[3px] transition-colors whitespace-nowrap px-3 ${activeTab === 'stats' ? 'border-primary text-slate-900 dark:text-white' : 'border-transparent text-slate-500 dark:text-slate-400'}`}
            >
                Stats
            </button>
            <button
                onClick={() => setActiveTab('community')}
                className={`flex-1 py-3 text-sm font-bold border-b-[3px] transition-colors whitespace-nowrap px-3 ${activeTab === 'community' ? 'border-primary text-slate-900 dark:text-white' : 'border-transparent text-slate-500 dark:text-slate-400'}`}
            >
                Community
            </button>
          </div>
      </div>

      {view === 'dashboard' && (
          <>
            {activeTab === 'plan' && (
                <div className="px-4 space-y-6 pb-24 animate-in fade-in slide-in-from-bottom-4 duration-300">
                    {!plan && (
                        <div className="bg-gradient-to-br from-slate-900 to-slate-800 dark:from-slate-800 dark:to-slate-700 rounded-2xl p-6 text-white text-center shadow-xl">
                            <div className="w-16 h-16 bg-white/10 rounded-full flex items-center justify-center mx-auto mb-4">
                                <span className="material-symbols-outlined text-3xl">calendar_add_on</span>
                            </div>
                            <h2 className="text-xl font-bold mb-2">No Plan Active</h2>
                            <p className="text-slate-300 text-sm mb-6">Build a personalized routine to reach your heart health goals.</p>
                            <button onClick={() => setView('wizard')} className="bg-white text-slate-900 px-8 py-3 rounded-full font-bold hover:bg-slate-100 transition-colors w-full sm:w-auto">
                                Create Your Plan
                            </button>
                        </div>
                    )}

                    {plan && (
                        <>
                        {/* Plan Header */}
                        <div className="flex justify-between items-center pt-2">
                            <h2 className="text-2xl font-bold dark:text-white">{plan.name}</h2>
                            <button onClick={() => setView('wizard')} className="text-xs font-bold text-primary bg-primary/10 px-3 py-1 rounded-full">Change Plan</button>
                        </div>

                        {/* Readiness Widget (Simulated) */}
                        <div className="bg-white dark:bg-card-dark p-4 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-800 relative overflow-hidden">
                            <div className="flex justify-between items-start mb-2 relative z-10">
                                <div>
                                    <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                        Daily Readiness
                                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full bg-green-100 text-green-600`}>
                                            High
                                        </span>
                                    </h3>
                                    <p className="text-xs text-slate-500 mt-1">You are recovered and ready to train.</p>
                                </div>
                                <div className="w-10 h-10 rounded-full flex items-center justify-center relative">
                                    <span className="material-symbols-outlined text-green-500 text-2xl">battery_full</span>
                                </div>
                            </div>
                        </div>

                        {/* Today's Workout Card */}
                        {(() => {
                            const todayIndex = (new Date().getDay() + 6) % 7;
                            const todayPlan = plan.days[todayIndex];
                            const todayWorkout = todayPlan && todayPlan.workoutId !== 'rest' ? getWorkoutById(todayPlan.workoutId) : null;

                            return (
                                <div className="bg-white dark:bg-card-dark rounded-2xl p-5 shadow-sm border border-slate-100 dark:border-slate-800 relative overflow-hidden transition-all duration-300">
                                    {todayWorkout ? (
                                        <div className="relative z-10">
                                            <div className="flex justify-between items-start mb-4">
                                                <div>
                                                    <div className="flex gap-2 mb-2">
                                                        <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-md inline-block bg-blue-100 text-blue-600">
                                                            Today
                                                        </span>
                                                    </div>
                                                    <h3 className="text-xl font-bold dark:text-white leading-tight">{todayWorkout.title}</h3>
                                                    <p className="text-slate-500 text-sm mt-1">{todayWorkout.duration_min} min • {todayWorkout.equipment.join(', ')}</p>
                                                </div>
                                                <div className="w-16 h-16 rounded-xl bg-slate-200 bg-cover bg-center cursor-pointer" onClick={() => navigate(`/workout/${todayWorkout.id}`)} style={{backgroundImage: `url(${todayWorkout.image.startsWith('/images') ? 'https://picsum.photos/seed/'+todayWorkout.id+'/200' : todayWorkout.image})`}}></div>
                                            </div>

                                            <div className="flex flex-col gap-3">
                                                <button onClick={() => navigate(`/workout/${todayWorkout.id}`)} className="flex-1 bg-primary hover:bg-primary-dark text-slate-900 py-3 rounded-xl font-bold flex items-center justify-center gap-2 transition-colors shadow-lg shadow-primary/20">
                                                    <span className="material-symbols-outlined">play_arrow</span> Start
                                                </button>
                                            </div>
                                        </div>
                                    ) : (
                                         <div className="text-center py-6">
                                            <span className="material-symbols-outlined text-4xl text-slate-300 mb-2">spa</span>
                                            <h3 className="font-bold dark:text-white">Rest Day</h3>
                                            <p className="text-sm text-slate-500">Take it easy and recover today.</p>
                                         </div>
                                    )}
                                </div>
                            );
                        })()}

                        {/* Weekly Schedule */}
                        <div>
                            <h3 className="font-bold dark:text-white mb-3">Weekly Schedule</h3>
                            <div className="flex gap-2 overflow-x-auto no-scrollbar pb-2">
                                {plan.days.map((day, idx) => {
                                    const isRest = day.workoutId === 'rest';
                                    const w = getWorkoutById(day.workoutId);
                                    return (
                                        <div key={idx} className={`flex-shrink-0 w-24 flex flex-col items-center gap-2 bg-white dark:bg-card-dark p-2 rounded-xl border border-slate-100 dark:border-slate-800`}>
                                            <span className="text-xs font-bold text-slate-500">{day.day}</span>
                                            <div className="h-10 flex items-center justify-center">
                                                {isRest ? <span className="material-symbols-outlined text-slate-300">spa</span> : <span className="material-symbols-outlined text-primary">fitness_center</span>}
                                            </div>
                                            <p className="text-[10px] text-center line-clamp-1 w-full text-slate-600 dark:text-slate-300">{isRest ? 'Rest' : w?.title}</p>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                        </>
                    )}

                    <div className="pt-2">
                         <div className="flex justify-between items-center mb-4">
                            <h3 className="font-bold text-lg dark:text-white">{plan ? 'My Routine Exercises' : 'Browse Library'}</h3>
                            <span className="text-xs text-slate-500">{filteredWorkouts.length} workouts</span>
                         </div>
                         <div className="mb-4 flex gap-3">
                             <div className="relative flex-1">
                                <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">search</span>
                                <input type="text" placeholder="Search exercises..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="w-full pl-12 h-12 rounded-xl bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 outline-none dark:text-white" />
                             </div>
                             <button onClick={() => setShowFilters(true)} className={`h-12 w-12 rounded-xl border flex items-center justify-center transition-colors relative bg-white dark:bg-slate-800 text-slate-500 dark:text-slate-400 border-slate-100 dark:border-slate-700`}>
                                 <span className="material-symbols-outlined">tune</span>
                             </button>
                         </div>

                         <div className="grid grid-cols-2 gap-4">
                             {filteredWorkouts.slice(0, displayLimit).map(workout => (
                                 <WorkoutCard
                                    key={workout.id}
                                    workout={workout}
                                    onClick={() => navigate(`/workout/${workout.id}`)}
                                    onAudioClick={() => setActiveAudioGuide(workout)}
                                 />
                             ))}
                         </div>

                         {displayLimit < filteredWorkouts.length && (
                             <button
                                onClick={() => setDisplayLimit(prev => prev + 20)}
                                className="w-full py-3 mt-4 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-bold rounded-xl hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                             >
                                Load More Workouts ({filteredWorkouts.length - displayLimit} remaining)
                             </button>
                         )}
                    </div>
                </div>
            )}
            {activeTab === 'coach' && <CoachScreen />}
            {activeTab === 'stats' && <StatsScreen />}
            {activeTab === 'community' && <CommunityScreen />}
          </>
      )}

      {view === 'wizard' && <WizardView />}
      {showReminders && <RemindersOverlay onClose={() => setShowReminders(false)} />}

      {/* Filter Modal Placeholder */}
      {showFilters && (
        <div className="fixed inset-0 z-50 flex flex-col justify-end" onClick={() => setShowFilters(false)}>
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm"></div>
            <div className="relative bg-white dark:bg-card-dark rounded-t-3xl p-6" onClick={e => e.stopPropagation()}>
                <h3 className="text-xl font-bold dark:text-white mb-4">Filters</h3>
                <p className="text-slate-500 mb-6">Filter options go here...</p>
                <button onClick={() => setShowFilters(false)} className="w-full py-3 bg-primary text-slate-900 font-bold rounded-xl">Apply</button>
            </div>
        </div>
      )}

      {/* Mini Audio Player */}
      {activeAudioGuide && <MiniAudioPlayer workout={activeAudioGuide} onClose={() => setActiveAudioGuide(null)} />}
    </div>
  );
};

export default ExerciseScreen;
