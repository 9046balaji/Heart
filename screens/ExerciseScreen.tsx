
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
        { id: 't_fb_1', name: 'Total Body Tone', desc: 'A balanced mix of strength and cardio for general fitness.', days: 3, exercises: ['gym_57', 'gym_908', 'gym_56'] },
        { id: 't_fb_2', name: 'Advanced Strength', desc: 'Heavy dumbbell work targeting all muscle groups.', days: 4, exercises: ['gym_822', 'gym_1022', 'gym_980', 'gym_805'] }
    ],
    'Core': [
        { id: 't_core_1', name: 'Core Crusher', desc: 'Intense focus on abs and lower back stability.', days: 3, exercises: ['gym_56', 'gym_980', 'gym_958'] },
        { id: 't_core_2', name: 'Pilates Power', desc: 'Mat-based pilates for a strong core.', days: 2, exercises: ['gym_960', 'gym_976'] }
    ],
    'Upper Body': [
        { id: 't_up_1', name: 'Arm Sculpt', desc: 'Tone arms and shoulders with light weights.', days: 2, exercises: ['gym_31', 'gym_805'] },
        { id: 't_up_2', name: 'Band Upper Body', desc: 'Resistance band focus for upper body strength.', days: 3, exercises: ['gym_820', 'gym_804', 'gym_822'] }
    ],
    'Lower Body': [
        { id: 't_low_1', name: 'Leg Day Essentials', desc: 'Squats and lunges to build leg strength.', days: 2, exercises: ['gym_12', 'gym_981'] },
        { id: 't_low_2', name: 'Glute Focus', desc: 'Targeted glute activation and strength.', days: 3, exercises: ['gym_46', 'gym_802', 'gym_43'] }
    ],
    'Cardio': [
        { id: 't_cardio_1', name: 'Cardio Blast', desc: 'High energy routine to burn calories.', days: 4, exercises: ['gym_908', 'gym_961', 'gym_962', 'gym_927'] },
        { id: 't_cardio_2', name: 'Dance Party', desc: 'Fun dance-based cardio workouts.', days: 3, exercises: ['gym_907', 'gym_923', 'gym_927'] }
    ],
    'Flexibility': [
        { id: 't_flex_1', name: 'Daily Stretch', desc: 'Improve mobility and reduce stiffness.', days: 7, exercises: ['gym_909', 'gym_912', 'gym_924', 'gym_992'] },
        { id: 't_flex_2', name: 'Yoga Flow', desc: 'Vinyasa and Hatha flows for flexibility.', days: 3, exercises: ['gym_993', 'gym_959', 'gym_979'] }
    ]
};

// --- Sub-Components ---

const MiniAudioPlayer: React.FC<{ workout: Workout, onClose: () => void }> = ({ workout, onClose }) => {
    const [isPlaying, setIsPlaying] = useState(true);
    const [progress, setProgress] = useState(0);
    const [caption, setCaption] = useState("Coach: Ready to start? Let's warm up.");
    const [elapsed, setElapsed] = useState(0);

    useEffect(() => {
        if (!isPlaying) return;

        const interval = setInterval(() => {
            setElapsed(prev => {
                const next = prev + 1;
                // Simulated coaching script
                if (next === 5) setCaption("Coach: Keep a steady pace.");
                if (next === 15) setCaption("Coach: You're doing great! Check your posture.");
                if (next === 30) setCaption("Coach: We're approaching the first kilometer.");
                return next;
            });
            setProgress(prev => Math.min(100, prev + 0.1));
        }, 1000);

        return () => clearInterval(interval);
    }, [isPlaying]);

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
            videoRef.current.play().catch(() => { });
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
                    style={{ backgroundImage: `url(${getImageUrl(workout.image, workout.id)})` }}
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
                {(workout.category === 'Cardio' && workout.accessibility?.includes('outdoor')) && (
                    <button
                        onClick={(e) => { e.stopPropagation(); if (onAudioClick) onAudioClick(); }}
                        className="absolute bottom-2 right-2 w-8 h-8 bg-black/60 backdrop-blur-sm rounded-full flex items-center justify-center text-white hover:bg-primary hover:text-slate-900 transition-colors z-20"
                        title="Start Audio Guide"
                    >
                        <span className="material-symbols-outlined text-sm">headphones</span>
                    </button>
                )}

                <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"></div>
                <button
                    onClick={(e) => { e.stopPropagation(); onClick(); }}
                    className="absolute top-2 right-2 w-8 h-8 flex items-center justify-center rounded-full bg-black/30 backdrop-blur-sm text-white hover:bg-black/50 transition-colors z-20"
                    title="View workout"
                >
                    <span className="material-symbols-outlined text-lg">add</span>
                </button>
            </div>
            <div>
                <p className="text-base font-medium leading-normal text-slate-900 dark:text-white truncate group-hover:text-primary transition-colors">
                    {workout.title}
                </p>
                <p className="text-sm font-normal leading-normal text-slate-500 dark:text-slate-400 truncate">
                    {workout.category}, {(workout.equipment && workout.equipment[0]) ? (workout.equipment[0] === 'none' ? 'Bodyweight' : workout.equipment[0].replace(/-/g, ' ')) : 'No Equipment'}
                </p>
            </div>
        </div>
    );
};

const RemindersOverlay: React.FC<{ onClose: () => void }> = ({ onClose }) => {
    const [enabled, setEnabled] = useState(true);
    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center p-4" onClick={onClose}>
            <div className="bg-white dark:bg-card-dark w-full max-w-sm rounded-2xl p-6 shadow-2xl animate-in slide-in-from-bottom-10 duration-300" onClick={e => e.stopPropagation()}>
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-xl font-bold dark:text-white">Workout Reminders</h3>
                    <button onClick={onClose} className="p-1 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800">
                        <span className="material-symbols-outlined text-slate-400">close</span>
                    </button>
                </div>
                <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 rounded-xl mb-4">
                    <div>
                        <p className="font-bold dark:text-white text-sm">Daily Reminders</p>
                        <p className="text-xs text-slate-500">Get notified about your workout schedule</p>
                    </div>
                    <button
                        onClick={() => setEnabled(!enabled)}
                        className={`w-12 h-7 rounded-full transition-colors relative ${enabled ? 'bg-primary' : 'bg-slate-300 dark:bg-slate-600'}`}
                    >
                        <div className={`w-5 h-5 bg-white rounded-full absolute top-1 transition-transform shadow-sm ${enabled ? 'translate-x-6' : 'translate-x-1'}`}></div>
                    </button>
                </div>
                <p className="text-xs text-slate-400 text-center">
                    {enabled ? 'You will receive reminders for scheduled workouts.' : 'Reminders are turned off.'}
                </p>
            </div>
        </div>
    );
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
    const [sortBy, setSortBy] = useState<'name' | 'duration' | 'intensity'>('name');
    const [displayLimit, setDisplayLimit] = useState(8);

    // Normalize data to handle inconsistent formats
    const normalizedWorkouts = React.useMemo(() => {
        return workoutData.map((w: any) => ({
            ...w,
            id: w.id || `w_${Math.random().toString(36).substr(2, 9)}`,
            title: w.title || w.name || 'Untitled Workout',
            category: w.category || w.area || 'General',
            duration_min: w.duration_min || 15,
            intensity: w.intensity || 'medium',
            equipment: (w.equipment && w.equipment.length > 0) ? w.equipment : ['none'],
            accessibility: w.accessibility || [],
            goal: w.goal || ['General Fitness'],
            image: w.image || w.image_url || '',
            steps: w.steps || (w.process ? [w.process] : ['Follow the video instructions.']),
            videoUrl: w.videoUrl || w.youtube || '',
            all_images: w.all_images || [],
            target_muscles: w.target_muscles || [],
            secondary_muscles: w.secondary_muscles || [],
            process: w.process || ''
        })) as Workout[];
    }, []);

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
        return normalizedWorkouts.find(w => w.id === id);
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
        const [scratchFilterCat, setScratchFilterCat] = useState('All');
        const [detailExercise, setDetailExercise] = useState<Workout | null>(null);

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
                    for (let i = 0; i < 7; i++) days.push({ day: daysOfWeek[i], workoutId: i % 2 === 0 ? normalizedWorkouts[i].id : 'rest', completed: false });
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

        const getImgUrl = (url: string, seed: string) => {
            if (!url || url.startsWith('/images/')) return `https://picsum.photos/seed/${seed}/800/600`;
            return url;
        };

        const SCRATCH_CATEGORIES = ['All', 'Chest', 'Back', 'Arms', 'Shoulders', 'Legs', 'Abs', 'Cardio'];

        const scratchFiltered = normalizedWorkouts.filter(w => {
            const matchesSearch = w.title.toLowerCase().includes(scratchSearch.toLowerCase());
            const matchesCat = scratchFilterCat === 'All' || w.category === scratchFilterCat;
            return matchesSearch && matchesCat;
        });

        const renderStepIndicator = () => (
            <div className="px-6 pt-4 pb-2">
                <div className="flex items-center justify-between relative">
                    {/* Progress Line */}
                    <div className="absolute top-4 left-[calc(16.67%)] right-[calc(16.67%)] h-0.5 bg-slate-200 dark:bg-slate-700">
                        <div
                            className="h-full bg-primary transition-all duration-500 ease-out"
                            style={{ width: scratchStep === 1 ? '0%' : scratchStep === 2 ? '50%' : '100%' }}
                        />
                    </div>
                    {[
                        { num: 1, label: 'Details', icon: 'edit_note' },
                        { num: 2, label: 'Exercises', icon: 'fitness_center' },
                        { num: 3, label: 'Review', icon: 'checklist' }
                    ].map(step => {
                        const isActive = scratchStep === step.num;
                        const isComplete = scratchStep > step.num;
                        return (
                            <div key={step.num} className="flex flex-col items-center gap-1 relative z-10 flex-1">
                                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300 ${isActive
                                    ? 'bg-primary text-white scale-110 shadow-lg shadow-primary/30'
                                    : isComplete
                                        ? 'bg-green-500 text-white'
                                        : 'bg-slate-200 dark:bg-slate-700 text-slate-400 dark:text-slate-500'
                                    }`}>
                                    {isComplete
                                        ? <span className="material-symbols-outlined text-sm">check</span>
                                        : <span className="material-symbols-outlined text-sm">{step.icon}</span>
                                    }
                                </div>
                                <span className={`text-[10px] font-bold transition-colors ${isActive ? 'text-primary' : isComplete ? 'text-green-500' : 'text-slate-400'}`}>
                                    {step.label}
                                </span>
                            </div>
                        );
                    })}
                </div>
            </div>
        );

        const renderScratch = () => (
            <div className="flex flex-col h-full">
                {renderStepIndicator()}

                {/* ─── STEP 1: Plan Details ─── */}
                {scratchStep === 1 && (
                    <div className="flex-1 overflow-y-auto px-6 pt-2 pb-6">
                        <div className="mb-6">
                            <h3 className="text-2xl font-bold dark:text-white">Plan Details</h3>
                            <p className="text-sm text-slate-500 mt-1">Give your plan a name and set your preferences.</p>
                        </div>

                        <div className="space-y-5">
                            {/* Plan Name */}
                            <div className="bg-white dark:bg-card-dark rounded-2xl p-4 border border-slate-100 dark:border-slate-800 shadow-sm">
                                <div className="flex items-center gap-3 mb-3">
                                    <div className="w-10 h-10 rounded-xl bg-blue-50 dark:bg-blue-500/10 flex items-center justify-center">
                                        <span className="material-symbols-outlined text-blue-500">badge</span>
                                    </div>
                                    <label className="text-sm font-bold dark:text-white">Plan Name</label>
                                </div>
                                <input
                                    type="text" value={scratchData.name} onChange={e => setScratchData({ ...scratchData, name: e.target.value })}
                                    placeholder="e.g. Morning Strength Routine"
                                    className="w-full p-3.5 bg-slate-50 dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 outline-none dark:text-white focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all text-sm"
                                />
                            </div>

                            {/* Goal */}
                            <div className="bg-white dark:bg-card-dark rounded-2xl p-4 border border-slate-100 dark:border-slate-800 shadow-sm">
                                <div className="flex items-center gap-3 mb-3">
                                    <div className="w-10 h-10 rounded-xl bg-purple-50 dark:bg-purple-500/10 flex items-center justify-center">
                                        <span className="material-symbols-outlined text-purple-500">flag</span>
                                    </div>
                                    <label className="text-sm font-bold dark:text-white">Goal / Description</label>
                                </div>
                                <input
                                    type="text" value={scratchData.goal} onChange={e => setScratchData({ ...scratchData, goal: e.target.value })}
                                    placeholder="e.g. Build muscle, Lose weight"
                                    className="w-full p-3.5 bg-slate-50 dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 outline-none dark:text-white focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all text-sm"
                                />
                            </div>

                            {/* Frequency */}
                            <div className="bg-white dark:bg-card-dark rounded-2xl p-4 border border-slate-100 dark:border-slate-800 shadow-sm">
                                <div className="flex items-center gap-3 mb-3">
                                    <div className="w-10 h-10 rounded-xl bg-green-50 dark:bg-green-500/10 flex items-center justify-center">
                                        <span className="material-symbols-outlined text-green-500">calendar_month</span>
                                    </div>
                                    <label className="text-sm font-bold dark:text-white">Training Frequency</label>
                                </div>
                                {/* Day selector buttons */}
                                <div className="flex justify-between gap-1.5 mb-3">
                                    {[1, 2, 3, 4, 5, 6, 7].map(d => (
                                        <button
                                            key={d}
                                            onClick={() => setScratchData({ ...scratchData, frequency: d })}
                                            className={`flex-1 py-2.5 rounded-xl text-sm font-bold transition-all ${d <= scratchData.frequency
                                                ? 'bg-primary text-white shadow-sm'
                                                : 'bg-slate-100 dark:bg-slate-800 text-slate-400'
                                                }`}
                                        >
                                            {d}
                                        </button>
                                    ))}
                                </div>
                                <p className="text-center text-sm text-primary font-bold">
                                    {scratchData.frequency} {scratchData.frequency === 1 ? 'day' : 'days'} per week
                                </p>
                            </div>
                        </div>

                        <button
                            onClick={() => setScratchStep(2)}
                            disabled={!scratchData.name}
                            className="w-full py-3.5 bg-primary text-white rounded-xl font-bold disabled:opacity-40 mt-6 flex items-center justify-center gap-2 shadow-lg shadow-primary/20 transition-all hover:shadow-xl"
                        >
                            Next: Add Exercises
                            <span className="material-symbols-outlined text-lg">arrow_forward</span>
                        </button>
                    </div>
                )}

                {/* ─── STEP 2: Exercise Selection ─── */}
                {scratchStep === 2 && (
                    <div className="flex flex-col flex-1 overflow-hidden">
                        {/* Search + Category Filters */}
                        <div className="px-4 pt-3 pb-2 space-y-3 border-b border-slate-100 dark:border-slate-800">
                            <div className="relative">
                                <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xl">search</span>
                                <input
                                    type="text" placeholder="Search exercises..." value={scratchSearch} onChange={e => setScratchSearch(e.target.value)}
                                    className="w-full pl-10 pr-4 py-2.5 bg-slate-100 dark:bg-slate-800 rounded-xl border-none outline-none dark:text-white text-sm focus:ring-2 focus:ring-primary/50"
                                />
                                {scratchSearch && (
                                    <button onClick={() => setScratchSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2">
                                        <span className="material-symbols-outlined text-slate-400 text-lg">close</span>
                                    </button>
                                )}
                            </div>
                            <div className="flex gap-1.5 overflow-x-auto no-scrollbar pb-1">
                                {SCRATCH_CATEGORIES.map(cat => (
                                    <button
                                        key={cat}
                                        onClick={() => setScratchFilterCat(cat)}
                                        className={`px-3 py-1.5 rounded-full text-xs font-bold whitespace-nowrap transition-all ${scratchFilterCat === cat
                                            ? 'bg-primary text-white shadow-sm'
                                            : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400'
                                            }`}
                                    >
                                        {cat}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Exercise Cards */}
                        <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
                            {scratchFiltered.length === 0 && (
                                <div className="text-center py-12">
                                    <span className="material-symbols-outlined text-4xl text-slate-300 mb-2">search_off</span>
                                    <p className="text-slate-400 text-sm">No exercises found.</p>
                                </div>
                            )}
                            {scratchFiltered.map(w => {
                                const isSelected = scratchData.exercises.includes(w.id);
                                return (
                                    <div
                                        key={w.id}
                                        onClick={() => toggleExercise(w.id)}
                                        className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${isSelected
                                            ? 'border-primary bg-primary/5 dark:bg-primary/10 shadow-sm'
                                            : 'border-slate-100 dark:border-slate-800 bg-white dark:bg-card-dark hover:border-slate-300 dark:hover:border-slate-600'
                                            }`}
                                    >
                                        {/* Thumbnail */}
                                        <div
                                            className="w-14 h-14 rounded-lg bg-slate-200 dark:bg-slate-700 bg-cover bg-center flex-shrink-0 relative overflow-hidden"
                                            style={{ backgroundImage: `url(${getImgUrl(w.image, w.id)})` }}
                                        >
                                            {isSelected && (
                                                <div className="absolute inset-0 bg-primary/60 flex items-center justify-center">
                                                    <span className="material-symbols-outlined text-white text-lg">check</span>
                                                </div>
                                            )}
                                        </div>

                                        {/* Info */}
                                        <div className="flex-1 min-w-0">
                                            <h4 className="font-bold text-sm dark:text-white truncate">{w.title}</h4>
                                            <p className="text-xs text-slate-500 mt-0.5">{w.category} • {w.duration_min} min</p>
                                            {w.target_muscles && w.target_muscles.length > 0 && (
                                                <div className="flex gap-1 mt-1 flex-wrap">
                                                    {w.target_muscles.slice(0, 2).map((m, i) => (
                                                        <span key={i} className="text-[10px] px-1.5 py-0.5 bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 rounded">
                                                            {m}
                                                        </span>
                                                    ))}
                                                    {w.target_muscles.length > 2 && (
                                                        <span className="text-[10px] px-1.5 py-0.5 text-slate-400">+{w.target_muscles.length - 2}</span>
                                                    )}
                                                </div>
                                            )}
                                        </div>

                                        {/* Checkbox */}
                                        <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-all ${isSelected
                                            ? 'bg-primary border-primary text-white scale-110'
                                            : 'border-slate-300 dark:border-slate-600'
                                            }`}>
                                            {isSelected && <span className="material-symbols-outlined text-sm">check</span>}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>

                        {/* Bottom Action Bar */}
                        <div className="p-4 border-t border-slate-100 dark:border-slate-800 bg-white dark:bg-card-dark shadow-[0_-4px_12px_-4px_rgba(0,0,0,0.1)] z-[60]">
                            <div
                                className="flex justify-between items-center mb-3 cursor-pointer"
                                onClick={() => setShowPreview(!showPreview)}
                            >
                                <div>
                                    <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">{scratchData.name || 'Your Plan'}</p>
                                    <p className="text-sm font-bold text-primary">{scratchData.exercises.length} exercise{scratchData.exercises.length !== 1 ? 's' : ''} selected</p>
                                </div>
                                <span className="material-symbols-outlined text-slate-400 transition-transform"
                                    style={{ transform: showPreview ? 'rotate(180deg)' : 'rotate(0deg)' }}
                                >expand_less</span>
                            </div>

                            {showPreview && (
                                <div className="mb-3 max-h-36 overflow-y-auto space-y-1.5 border-t border-slate-100 dark:border-slate-700 pt-2">
                                    {scratchData.exercises.map(id => {
                                        const w = getWorkoutById(id);
                                        return w ? (
                                            <div key={id} className="flex items-center justify-between bg-slate-50 dark:bg-slate-800 rounded-lg px-3 py-1.5">
                                                <span className="text-xs dark:text-white font-medium truncate flex-1">{w.title}</span>
                                                <button onClick={(e) => { e.stopPropagation(); toggleExercise(id); }} className="text-red-400 hover:text-red-500 ml-2">
                                                    <span className="material-symbols-outlined text-sm">remove_circle</span>
                                                </button>
                                            </div>
                                        ) : null;
                                    })}
                                    {scratchData.exercises.length === 0 && <p className="text-xs text-slate-400 italic text-center py-2">Tap exercises above to add them.</p>}
                                </div>
                            )}

                            <div className="flex gap-2">
                                <button onClick={() => setScratchStep(1)} className="px-5 py-3 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-bold rounded-xl transition-colors hover:bg-slate-200 dark:hover:bg-slate-700">
                                    <span className="material-symbols-outlined text-lg">arrow_back</span>
                                </button>
                                <button
                                    onClick={() => setScratchStep(3)}
                                    disabled={scratchData.exercises.length === 0}
                                    className="flex-1 py-3 bg-primary text-white font-bold rounded-xl disabled:opacity-40 flex items-center justify-center gap-2 shadow-lg shadow-primary/20"
                                >
                                    Review Plan
                                    <span className="material-symbols-outlined text-lg">arrow_forward</span>
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {/* ─── STEP 3: Review ─── */}
                {scratchStep === 3 && (
                    <div className="flex flex-col flex-1 overflow-hidden">
                        <div className="flex-1 overflow-y-auto px-6 pt-2 pb-4">
                            <div className="mb-5">
                                <h3 className="text-2xl font-bold dark:text-white">Review Your Plan</h3>
                                <p className="text-sm text-slate-500 mt-1">Tap any exercise to see full details.</p>
                            </div>

                            {/* Plan Summary Card */}
                            <div className="bg-gradient-to-br from-primary/10 to-blue-500/5 dark:from-primary/20 dark:to-blue-500/10 p-5 rounded-2xl border border-primary/20 mb-5">
                                <div className="flex items-start justify-between mb-3">
                                    <div>
                                        <h4 className="font-bold text-lg dark:text-white">{scratchData.name}</h4>
                                        {scratchData.goal && <p className="text-sm text-slate-500 mt-0.5">{scratchData.goal}</p>}
                                    </div>
                                    <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
                                        <span className="material-symbols-outlined text-primary">sports_martial_arts</span>
                                    </div>
                                </div>
                                <div className="flex gap-4">
                                    <div className="flex items-center gap-1.5 text-xs font-medium text-slate-600 dark:text-slate-400">
                                        <span className="material-symbols-outlined text-sm text-primary">calendar_month</span>
                                        {scratchData.frequency} Days/Week
                                    </div>
                                    <div className="flex items-center gap-1.5 text-xs font-medium text-slate-600 dark:text-slate-400">
                                        <span className="material-symbols-outlined text-sm text-primary">fitness_center</span>
                                        {scratchData.exercises.length} Exercises
                                    </div>
                                    <div className="flex items-center gap-1.5 text-xs font-medium text-slate-600 dark:text-slate-400">
                                        <span className="material-symbols-outlined text-sm text-primary">timer</span>
                                        ~{scratchData.exercises.reduce((acc, id) => acc + (getWorkoutById(id)?.duration_min || 15), 0)} min
                                    </div>
                                </div>
                            </div>

                            {/* Exercises List with Images */}
                            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Exercises Included</h4>
                            <div className="space-y-3">
                                {scratchData.exercises.map((id, i) => {
                                    const w = getWorkoutById(id);
                                    if (!w) return null;
                                    return (
                                        <div
                                            key={id}
                                            onClick={() => setDetailExercise(w)}
                                            className="flex items-center gap-3 p-3 bg-white dark:bg-card-dark rounded-xl border border-slate-100 dark:border-slate-800 cursor-pointer hover:border-primary/50 hover:shadow-md transition-all group"
                                        >
                                            {/* Numbering */}
                                            <div className="w-7 h-7 rounded-full bg-slate-100 dark:bg-slate-700 flex items-center justify-center flex-shrink-0">
                                                <span className="text-xs font-bold text-slate-500 dark:text-slate-400">{i + 1}</span>
                                            </div>

                                            {/* Image */}
                                            <div
                                                className="w-16 h-16 rounded-xl bg-slate-200 dark:bg-slate-700 bg-cover bg-center flex-shrink-0 shadow-sm"
                                                style={{ backgroundImage: `url(${getImgUrl(w.image, w.id)})` }}
                                            />

                                            {/* Info */}
                                            <div className="flex-1 min-w-0">
                                                <h4 className="font-bold text-sm dark:text-white truncate group-hover:text-primary transition-colors">{w.title}</h4>
                                                <p className="text-xs text-slate-500 mt-0.5">{w.category} • {w.duration_min} min</p>
                                                {w.target_muscles && w.target_muscles.length > 0 && (
                                                    <p className="text-[10px] text-slate-400 mt-1 truncate">
                                                        {w.target_muscles.slice(0, 3).join(', ')}
                                                    </p>
                                                )}
                                            </div>

                                            {/* Expand arrow */}
                                            <span className="material-symbols-outlined text-slate-300 dark:text-slate-600 group-hover:text-primary transition-colors flex-shrink-0">
                                                chevron_right
                                            </span>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Bottom Action Buttons */}
                        <div className="p-4 border-t border-slate-100 dark:border-slate-800 bg-white dark:bg-card-dark shadow-[0_-4px_12px_-4px_rgba(0,0,0,0.1)]">
                            <div className="flex gap-3">
                                <button onClick={() => setScratchStep(2)} className="flex-1 py-3 border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 font-bold rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors flex items-center justify-center gap-2">
                                    <span className="material-symbols-outlined text-lg">edit</span>
                                    Edit
                                </button>
                                <button onClick={confirmScratchPlan} className="flex-[2] py-3 bg-primary text-white font-bold rounded-xl shadow-lg shadow-primary/20 hover:shadow-xl transition-all flex items-center justify-center gap-2">
                                    <span className="material-symbols-outlined text-lg">check_circle</span>
                                    Confirm & Save
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {/* ─── Exercise Detail Modal ─── */}
                {detailExercise && (
                    <div className="absolute inset-0 z-20 bg-black/60 backdrop-blur-sm flex items-end sm:items-center justify-center animate-in fade-in duration-200" onClick={() => setDetailExercise(null)}>
                        <div className="bg-white dark:bg-card-dark w-full max-w-md rounded-t-3xl sm:rounded-2xl max-h-[85vh] overflow-hidden flex flex-col shadow-2xl animate-in slide-in-from-bottom-10 duration-300" onClick={e => e.stopPropagation()}>
                            {/* Hero Image */}
                            <div className="relative w-full h-48 bg-slate-200 dark:bg-slate-700 bg-cover bg-center flex-shrink-0"
                                style={{ backgroundImage: `url(${getImgUrl(detailExercise.image, detailExercise.id)})` }}
                            >
                                <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent" />
                                <button onClick={() => setDetailExercise(null)} className="absolute top-3 right-3 w-8 h-8 bg-black/40 backdrop-blur-sm rounded-full flex items-center justify-center text-white hover:bg-black/60 transition-colors">
                                    <span className="material-symbols-outlined text-lg">close</span>
                                </button>
                                <div className="absolute bottom-4 left-4 right-4">
                                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-md bg-primary/80 text-white mb-2 inline-block">{detailExercise.category}</span>
                                    <h3 className="text-xl font-bold text-white leading-tight">{detailExercise.title}</h3>
                                </div>
                            </div>

                            {/* Scrollable Content */}
                            <div className="flex-1 overflow-y-auto p-5 space-y-4">
                                {/* Quick Stats */}
                                <div className="flex gap-3">
                                    <div className="flex-1 bg-slate-50 dark:bg-slate-800 rounded-xl p-3 text-center">
                                        <span className="material-symbols-outlined text-primary text-lg">timer</span>
                                        <p className="text-xs font-bold dark:text-white mt-1">{detailExercise.duration_min} min</p>
                                        <p className="text-[10px] text-slate-400">Duration</p>
                                    </div>
                                    <div className="flex-1 bg-slate-50 dark:bg-slate-800 rounded-xl p-3 text-center">
                                        <span className="material-symbols-outlined text-orange-500 text-lg">local_fire_department</span>
                                        <p className="text-xs font-bold dark:text-white mt-1">{detailExercise.intensity}</p>
                                        <p className="text-[10px] text-slate-400">Intensity</p>
                                    </div>
                                    <div className="flex-1 bg-slate-50 dark:bg-slate-800 rounded-xl p-3 text-center">
                                        <span className="material-symbols-outlined text-blue-500 text-lg">fitness_center</span>
                                        <p className="text-xs font-bold dark:text-white mt-1">{(detailExercise.equipment?.[0] || 'none') === 'none' ? 'Body' : 'Equip'}</p>
                                        <p className="text-[10px] text-slate-400">Equipment</p>
                                    </div>
                                </div>

                                {/* Target Muscles */}
                                {detailExercise.target_muscles && detailExercise.target_muscles.length > 0 && (
                                    <div>
                                        <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Target Muscles</h4>
                                        <div className="flex flex-wrap gap-1.5">
                                            {detailExercise.target_muscles.map((m, i) => (
                                                <span key={i} className="text-xs px-2.5 py-1 bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 rounded-full font-medium">{m}</span>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {detailExercise.secondary_muscles && detailExercise.secondary_muscles.length > 0 && (
                                    <div>
                                        <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Secondary Muscles</h4>
                                        <div className="flex flex-wrap gap-1.5">
                                            {detailExercise.secondary_muscles.map((m, i) => (
                                                <span key={i} className="text-xs px-2.5 py-1 bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 rounded-full font-medium">{m}</span>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Equipment */}
                                {detailExercise.equipment && detailExercise.equipment.length > 0 && detailExercise.equipment[0] !== 'none' && (
                                    <div>
                                        <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Equipment Needed</h4>
                                        <div className="flex flex-wrap gap-1.5">
                                            {detailExercise.equipment.map((e, i) => (
                                                <span key={i} className="text-xs px-2.5 py-1 bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 rounded-full font-medium">{e.replace(/-/g, ' ')}</span>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Instructions / Process */}
                                {detailExercise.process && (
                                    <div>
                                        <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Instructions</h4>
                                        <div className="bg-slate-50 dark:bg-slate-800 rounded-xl p-4 text-sm text-slate-700 dark:text-slate-300 leading-relaxed prose prose-sm dark:prose-invert max-w-none"
                                            dangerouslySetInnerHTML={{ __html: detailExercise.process }}
                                        />
                                    </div>
                                )}

                                {/* All Images Gallery */}
                                {detailExercise.all_images && detailExercise.all_images.length > 1 && (
                                    <div>
                                        <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Exercise Images</h4>
                                        <div className="flex gap-2 overflow-x-auto no-scrollbar pb-1">
                                            {detailExercise.all_images.map((img, i) => (
                                                <div key={i} className="w-32 h-32 rounded-xl bg-slate-200 dark:bg-slate-700 bg-cover bg-center flex-shrink-0 shadow-sm"
                                                    style={{ backgroundImage: `url(${img})` }}
                                                />
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* YouTube Link */}
                                {detailExercise.videoUrl && detailExercise.videoUrl.includes('youtube') && (
                                    <a
                                        href={detailExercise.videoUrl}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="flex items-center gap-3 p-3 bg-red-50 dark:bg-red-500/10 rounded-xl hover:bg-red-100 dark:hover:bg-red-500/20 transition-colors"
                                    >
                                        <div className="w-10 h-10 rounded-full bg-red-500 flex items-center justify-center flex-shrink-0">
                                            <span className="material-symbols-outlined text-white">play_arrow</span>
                                        </div>
                                        <div>
                                            <p className="text-sm font-bold text-red-600 dark:text-red-400">Watch on YouTube</p>
                                            <p className="text-xs text-slate-500">See the exercise in action</p>
                                        </div>
                                    </a>
                                )}
                            </div>

                            {/* Close Button */}
                            <div className="p-4 border-t border-slate-100 dark:border-slate-800">
                                <button onClick={() => setDetailExercise(null)} className="w-full py-3 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-bold rounded-xl hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors">
                                    Close
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        );

        return (
            <div className="fixed top-0 bottom-0 left-1/2 w-full max-w-md -translate-x-1/2 z-[60] bg-background-light dark:bg-background-dark flex flex-col animate-in slide-in-from-bottom duration-300 shadow-2xl">
                <div className="flex items-center p-4 border-b border-slate-200 dark:border-slate-800">
                    <button onClick={() => {
                        if (detailExercise) {
                            setDetailExercise(null);
                        } else if (path === 'menu') {
                            setView('dashboard');
                        } else if (path === 'scratch' && scratchStep > 1) {
                            setScratchStep(scratchStep - 1);
                        } else {
                            setPath('menu');
                            setScratchStep(1);
                        }
                    }} className="p-2 -ml-2 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-900 dark:text-white transition-colors">
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
        ? normalizedWorkouts.filter(w => planWorkoutIds.includes(w.id))
        : normalizedWorkouts;

    const filteredWorkouts = sourceWorkouts
        .filter(w => {
            const matchesSearch = w.title.toLowerCase().includes(searchQuery.toLowerCase());
            const matchesCategory = filterCategory === 'All' || w.category === filterCategory;
            return matchesSearch && matchesCategory;
        })
        .sort((a, b) => {
            if (sortBy === 'duration') return a.duration_min - b.duration_min;
            if (sortBy === 'intensity') {
                const intensityOrder = { 'low': 1, 'low-moderate': 2, 'moderate': 3, 'moderate-high': 4, 'high': 5 };
                const aVal = intensityOrder[a.intensity as keyof typeof intensityOrder] || 3;
                const bVal = intensityOrder[b.intensity as keyof typeof intensityOrder] || 3;
                return aVal - bVal;
            }
            return a.title.localeCompare(b.title);
        });

    // Reset pagination when filters change
    useEffect(() => {
        setDisplayLimit(8);
    }, [searchQuery, filterCategory, sortBy]);

    return (
        <div className="min-h-screen bg-background-light dark:bg-background-dark overflow-x-hidden">
            {/* Header with Tabs */}
            <div className="sticky top-0 bg-background-light dark:bg-background-dark z-10">
                <div className="flex items-center justify-between p-4 pb-2 border-b border-slate-100 dark:border-slate-800/50">
                    <button onClick={() => navigate(-1)} className="p-2 -ml-2 rounded-full text-slate-800 dark:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
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
                                                            <div className="w-16 h-16 rounded-xl bg-slate-200 bg-cover bg-center cursor-pointer" onClick={() => navigate(`/workout/${todayWorkout.id}`)} style={{ backgroundImage: `url(${todayWorkout.image.startsWith('/images') ? 'https://picsum.photos/seed/' + todayWorkout.id + '/200' : todayWorkout.image})` }}></div>
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
                                {/* Search & Filter Controls */}
                                <div className="mb-4 space-y-3">
                                    <div className="flex gap-2">
                                        <div className="relative flex-1">
                                            <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">search</span>
                                            <input
                                                type="text"
                                                placeholder="Search exercises..."
                                                value={searchQuery}
                                                onChange={(e) => setSearchQuery(e.target.value)}
                                                className="w-full pl-12 h-12 rounded-xl bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 outline-none dark:text-white focus:ring-2 focus:ring-primary/50"
                                            />
                                        </div>
                                    </div>

                                    <div className="flex gap-2 overflow-x-auto no-scrollbar">
                                        <select
                                            value={filterCategory}
                                            onChange={(e) => setFilterCategory(e.target.value)}
                                            className="px-4 py-2 bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 rounded-lg text-sm font-medium dark:text-white focus:outline-none focus:ring-2 focus:ring-primary/50"
                                        >
                                            <option value="All">All Categories</option>
                                            <option value="Cardio">Cardio</option>
                                            <option value="Chest">Chest</option>
                                            <option value="Back">Back</option>
                                            <option value="Arms">Arms</option>
                                            <option value="Shoulders">Shoulders</option>
                                            <option value="Legs">Legs</option>
                                            <option value="Abs">Abs</option>
                                        </select>

                                        <select
                                            value={sortBy}
                                            onChange={(e) => setSortBy(e.target.value as any)}
                                            className="px-4 py-2 bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 rounded-lg text-sm font-medium dark:text-white focus:outline-none focus:ring-2 focus:ring-primary/50"
                                        >
                                            <option value="name">Sort: A-Z</option>
                                            <option value="duration">Sort: Duration</option>
                                            <option value="intensity">Sort: Intensity</option>
                                        </select>
                                    </div>
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
