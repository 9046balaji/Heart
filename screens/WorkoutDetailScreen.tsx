
import React, { useEffect, useState, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { workoutData } from '../data/workouts';
import { apiClient, APIError } from '../services/apiClient';
import { memoryService } from '../services/memoryService';

// --- Custom Video Player Component ---
const CustomVideoPlayer = ({ src, poster, isExpanded, toggleExpand }: { src: string, poster?: string, isExpanded: boolean, toggleExpand: () => void }) => {
    const videoRef = useRef<HTMLVideoElement>(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [progress, setProgress] = useState(0);
    const [duration, setDuration] = useState(0);
    const [currentTime, setCurrentTime] = useState(0);
    const [volume, setVolume] = useState(1);
    const [isMuted, setIsMuted] = useState(false);
    const [showControls, setShowControls] = useState(true);

    const togglePlay = () => {
        if (!videoRef.current) return;
        if (isPlaying) {
            videoRef.current.pause();
        } else {
            videoRef.current.play();
        }
        setIsPlaying(!isPlaying);
    };

    const handleTimeUpdate = () => {
        if (!videoRef.current) return;
        const current = videoRef.current.currentTime;
        const dur = videoRef.current.duration;
        setCurrentTime(current);
        if (dur) setProgress((current / dur) * 100);
    };

    const handleLoadedMetadata = () => {
        if (!videoRef.current) return;
        setDuration(videoRef.current.duration);
    };

    const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!videoRef.current) return;
        const seekTime = (parseFloat(e.target.value) / 100) * duration;
        videoRef.current.currentTime = seekTime;
        setProgress(parseFloat(e.target.value));
    };

    const toggleMute = () => {
        if (!videoRef.current) return;
        videoRef.current.muted = !isMuted;
        setIsMuted(!isMuted);
    };

    const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!videoRef.current) return;
        const vol = parseFloat(e.target.value);
        videoRef.current.volume = vol;
        setVolume(vol);
        setIsMuted(vol === 0);
    };

    const formatTime = (time: number) => {
        const minutes = Math.floor(time / 60);
        const seconds = Math.floor(time % 60);
        return `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
    };

    return (
        <div
            className={`relative group bg-black rounded-2xl overflow-hidden shadow-md transition-all duration-300 ${isExpanded ? 'fixed inset-0 z-[100] rounded-none' : 'w-full h-full'
                }`}
            onMouseEnter={() => setShowControls(true)}
            onMouseLeave={() => isPlaying && setShowControls(false)}
        >
            {/* Close Button (Expanded Mode) */}
            {isExpanded && (
                <button
                    onClick={toggleExpand}
                    className="absolute top-6 right-6 w-10 h-10 bg-white/20 hover:bg-white/30 rounded-full flex items-center justify-center text-white backdrop-blur-md z-50"
                >
                    <span className="material-symbols-outlined">close</span>
                </button>
            )}

            <div className={`w-full h-full flex items-center justify-center ${isExpanded ? 'max-w-7xl mx-auto' : ''}`}>
                <video
                    ref={videoRef}
                    src={src}
                    poster={poster}
                    className="w-full h-full object-contain"
                    onClick={togglePlay}
                    onTimeUpdate={handleTimeUpdate}
                    onLoadedMetadata={handleLoadedMetadata}
                    onEnded={() => setIsPlaying(false)}
                />
            </div>

            {/* Controls Overlay */}
            <div className={`absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-4 transition-opacity duration-300 ${showControls ? 'opacity-100' : 'opacity-0'}`}>
                {/* Progress Bar */}
                <input
                    type="range"
                    min="0"
                    max="100"
                    value={progress}
                    onChange={handleSeek}
                    className="w-full h-1 bg-white/30 rounded-lg appearance-none cursor-pointer accent-primary mb-3 hover:h-2 transition-all"
                />

                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <button onClick={togglePlay} className="text-white hover:text-primary transition-colors">
                            <span className="material-symbols-outlined text-3xl filled">
                                {isPlaying ? 'pause_circle' : 'play_circle'}
                            </span>
                        </button>

                        <div className="flex items-center gap-2 group/vol">
                            <button onClick={toggleMute} className="text-white hover:text-primary transition-colors">
                                <span className="material-symbols-outlined text-2xl">
                                    {isMuted || volume === 0 ? 'volume_off' : volume < 0.5 ? 'volume_down' : 'volume_up'}
                                </span>
                            </button>
                            <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.1"
                                value={isMuted ? 0 : volume}
                                onChange={handleVolumeChange}
                                className="w-0 overflow-hidden group-hover/vol:w-20 transition-all h-1 bg-white/30 accent-white rounded-lg appearance-none cursor-pointer"
                            />
                        </div>

                        <span className="text-xs text-white font-medium font-mono">
                            {formatTime(currentTime)} / {formatTime(duration)}
                        </span>
                    </div>

                    <button
                        onClick={toggleExpand}
                        className="text-white hover:text-primary transition-colors"
                        title={isExpanded ? "Collapse" : "Expand"}
                    >
                        <span className="material-symbols-outlined text-2xl">
                            {isExpanded ? 'close_fullscreen' : 'open_in_full'}
                        </span>
                    </button>
                </div>
            </div>

            {/* Centered Play Button (Initial/Paused) */}
            {!isPlaying && (
                <div
                    className="absolute inset-0 flex items-center justify-center pointer-events-none"
                    onClick={togglePlay} // Allow clicking center to play
                >
                    <div className="w-16 h-16 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center pointer-events-auto cursor-pointer hover:bg-white/30 hover:scale-110 transition-all">
                        <span className="material-symbols-outlined text-white text-4xl filled">play_arrow</span>
                    </div>
                </div>
            )}
        </div>
    );
};

// --- Live API Audio Helpers ---
function decode(base64: string) {
    const binaryString = atob(base64);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes;
}

function encode(bytes: Uint8Array) {
    let binary = '';
    const len = bytes.byteLength;
    for (let i = 0; i < len; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
}

async function decodeAudioData(
    data: Uint8Array,
    ctx: AudioContext,
    sampleRate: number,
    numChannels: number,
): Promise<AudioBuffer> {
    const dataInt16 = new Int16Array(data.buffer);
    const frameCount = dataInt16.length / numChannels;
    const buffer = ctx.createBuffer(numChannels, frameCount, sampleRate);

    for (let channel = 0; channel < numChannels; channel++) {
        const channelData = buffer.getChannelData(channel);
        for (let i = 0; i < frameCount; i++) {
            channelData[i] = dataInt16[i * numChannels + channel] / 32768.0;
        }
    }
    return buffer;
}

function createBlob(data: Float32Array): any {
    const l = data.length;
    const int16 = new Int16Array(l);
    for (let i = 0; i < l; i++) {
        int16[i] = data[i] * 32768;
    }
    return {
        data: encode(new Uint8Array(int16.buffer)),
        mimeType: 'audio/pcm;rate=16000',
    };
}

const WorkoutDetailScreen: React.FC = () => {
    const navigate = useNavigate();
    const { id } = useParams();
    const [isVideoExpanded, setIsVideoExpanded] = useState(false);

    // Timer State
    const [isActive, setIsActive] = useState(false);
    const [seconds, setSeconds] = useState(0);
    const timerRef = useRef<any>(null);

    // Live Coach State
    const [isLiveCoachActive, setIsLiveCoachActive] = useState(false);
    const [isCoachSpeaking, setIsCoachSpeaking] = useState(false);

    // Bio-Feedback State (Heart Rate)
    const [heartRate, setHeartRate] = useState<number>(0);
    const [isBlueToothConnected, setIsBlueToothConnected] = useState(false);
    const lastSentHRRef = useRef<number>(0);

    // Dynamic Music State
    const [isMusicEnabled, setIsMusicEnabled] = useState(false);
    const audioRef = useRef<HTMLAudioElement | null>(null);

    // Phase 2: Pre-Check & RPE State
    const [showPreCheck, setShowPreCheck] = useState(false);
    const [showRPE, setShowRPE] = useState(false);
    const [vitals, setVitals] = useState({ systolic: '', diastolic: '', hr: '' });
    const [isSafetyLocked, setIsSafetyLocked] = useState(false);
    const [rpe, setRpe] = useState(5);
    const [workoutNotes, setWorkoutNotes] = useState('');

    // Refs for Live API
    const liveSessionRef = useRef<any>(null);
    const inputAudioCtxRef = useRef<AudioContext | null>(null);
    const outputAudioCtxRef = useRef<AudioContext | null>(null);
    const sourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());
    const nextStartTimeRef = useRef<number>(0);

    // Scroll to top when route/ID changes
    useEffect(() => {
        window.scrollTo(0, 0);
    }, [id]);

    const rawWorkout = workoutData.find(w => w.id === id);

    const workout = React.useMemo(() => {
        if (!rawWorkout) return null;
        const w = rawWorkout as any;
        return {
            ...w,
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
            estimated_calories_per_min: w.estimated_calories_per_min || 5
        } as any; // Cast to any to avoid strict type checks on the component usage
    }, [rawWorkout]);

    const getImageUrl = (url: string, seed: string) => {
        if (!url) return `https://picsum.photos/seed/${seed}/800/600`;
        if (url.startsWith('/images/')) {
            return `https://picsum.photos/seed/${seed}/800/600`;
        }
        return url;
    };

    // Timer Effect
    useEffect(() => {
        if (isActive) {
            timerRef.current = setInterval(() => {
                setSeconds(s => s + 1);
            }, 1000);

            // Start music if enabled
            if (isMusicEnabled && audioRef.current && audioRef.current.paused) {
                audioRef.current.play().catch(e => console.log("Audio play failed", e));
            }

        } else if (!isActive && timerRef.current) {
            clearInterval(timerRef.current);

            // Pause music
            if (audioRef.current && !audioRef.current.paused) {
                audioRef.current.pause();
            }
        }
        return () => clearInterval(timerRef.current);
    }, [isActive, isMusicEnabled]);

    // Cleanup Live API and Audio on unmount
    useEffect(() => {
        return () => {
            stopLiveCoach();
            if (audioRef.current) {
                audioRef.current.pause();
                audioRef.current = null;
            }
        };
    }, []);

    // Heart Rate Context Injection Logic
    useEffect(() => {
        if (isLiveCoachActive && heartRate > 0 && liveSessionRef.current) {
            const now = Date.now();
            // Send update every 15 seconds to avoid flooding
            if (now - lastSentHRRef.current > 15000) {
                // We use send() to push a text turn. This simulates the user stating their HR or the system injecting it.
                try {
                    liveSessionRef.current.send({
                        clientContent: {
                            turns: [{
                                role: 'user',
                                parts: [{ text: `[SYSTEM ALERT] User Heart Rate is currently: ${heartRate} bpm.` }]
                            }],
                            turnComplete: true
                        }
                    });
                    lastSentHRRef.current = now;
                } catch (e) {
                    console.debug("Failed to inject HR context", e);
                }
            }
        }
    }, [heartRate, isLiveCoachActive]);

    // --- Dynamic Music Manager ---
    useEffect(() => {
        if (workout && !audioRef.current) {
            // Select track based on intensity
            let trackUrl = "";
            // Using copyright-free tracks from Pixabay (placeholders)
            if (workout.intensity === 'high') {
                trackUrl = "https://cdn.pixabay.com/audio/2022/01/18/audio_d0a13f69d2.mp3"; // Upbeat
            } else if (workout.intensity === 'low') {
                trackUrl = "https://cdn.pixabay.com/audio/2022/05/27/audio_1808fbf07a.mp3"; // Chill
            } else {
                trackUrl = "https://cdn.pixabay.com/audio/2022/03/10/audio_5b58f3e478.mp3"; // Moderate
            }

            const audio = new Audio(trackUrl);
            audio.loop = true;
            audio.volume = 0.3; // Background level
            audioRef.current = audio;
        }
    }, [workout]);

    const toggleMusic = () => {
        if (isMusicEnabled) {
            audioRef.current?.pause();
        } else if (isActive) {
            audioRef.current?.play();
        }
        setIsMusicEnabled(!isMusicEnabled);
    };

    // --- Bluetooth Heart Rate Logic ---
    const connectHeartRate = async () => {
        try {
            // Request Device
            const device = await (navigator as any).bluetooth.requestDevice({
                filters: [{ services: ['heart_rate'] }]
            });

            // Connect to GATT
            const server = await device.gatt.connect();
            const service = await server.getPrimaryService('heart_rate');
            const characteristic = await service.getCharacteristic('heart_rate_measurement');

            // Start Notifications
            await characteristic.startNotifications();
            characteristic.addEventListener('characteristicvaluechanged', handleHeartRateChanged);

            setIsBlueToothConnected(true);

            // Disconnect listener
            device.addEventListener('gattserverdisconnected', () => {
                setIsBlueToothConnected(false);
                setHeartRate(0);
            });

        } catch (e) {
            console.error("Bluetooth connection failed", e);
            alert("Could not connect to Heart Rate Monitor. Make sure it's paired and active.");
            // Simulator for Demo if bluetooth fails or not present
            if (!isBlueToothConnected) {
                alert("Simulating Heart Rate Monitor for Demo.");
                setIsBlueToothConnected(true);
                const interval = setInterval(() => {
                    setHeartRate(prev => {
                        if (!isBlueToothConnected) { clearInterval(interval); return 0; }
                        // Simulate HR rising during workout
                        return Math.min(185, Math.max(60, (prev || 70) + (isActive ? Math.floor(Math.random() * 5) : -2)));
                    });
                }, 2000);
            }
        }
    };

    const handleHeartRateChanged = (event: any) => {
        const value = event.target.value;
        // Parse standard Heart Rate Measurement
        // First byte: flags.
        const flags = value.getUint8(0);
        const rate16Bits = flags & 0x1;
        let hr;
        if (rate16Bits) {
            hr = value.getUint16(1, true); // Little endian
        } else {
            hr = value.getUint8(1);
        }
        setHeartRate(hr);
    };

    // --- Live Coach Logic ---
    const startLiveCoach = async () => {
        if (!workout) return;

        setIsLiveCoachActive(true);

        try {
            // For now, just show a simple message instead of complex real-time audio
            alert("Live Coach feature coming soon! Your workout coach will guide you with voice commands.");
            setIsLiveCoachActive(false);

        } catch (error) {
            console.error("Live Coach Error:", error);
            alert("Could not start Live Coach.");
            setIsLiveCoachActive(false);
        }
    };

    const stopLiveCoach = () => {
        if (liveSessionRef.current) {
            liveSessionRef.current.then((session: any) => session.close());
            liveSessionRef.current = null;
        }
        if (inputAudioCtxRef.current) {
            inputAudioCtxRef.current.close();
            inputAudioCtxRef.current = null;
        }
        if (outputAudioCtxRef.current) {
            outputAudioCtxRef.current.close();
            outputAudioCtxRef.current = null;
        }
        setIsLiveCoachActive(false);
        setIsCoachSpeaking(false);
    };

    // --- Pre-Workout Check Logic ---
    const handleStartRequest = () => {
        // If High Intensity, trigger safety check
        if (workout?.intensity === 'high' || workout?.intensity === 'medium-high') {
            // Pre-fill HR if device connected
            if (heartRate > 0) {
                setVitals(v => ({ ...v, hr: heartRate.toString() }));
            }
            setShowPreCheck(true);
        } else {
            startWorkout();
        }
    };

    const checkVitals = () => {
        const sys = parseInt(vitals.systolic);
        const dia = parseInt(vitals.diastolic);

        // Safety Thresholds
        if (sys > 160 || dia > 100) {
            setIsSafetyLocked(true);
        } else {
            setShowPreCheck(false);
            startWorkout();
        }
    };

    const startWorkout = () => {
        setIsActive(true);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    // --- Post-Workout & RPE Logic ---
    const handleFinishRequest = () => {
        setIsActive(false);
        stopLiveCoach();
        setShowRPE(true);
    };

    const handleShare = async () => {
        if (!workout) return;
        const shareData = {
            title: 'Cardio AI Workout',
            text: `I just completed a ${workout.duration_min} min ${workout.title} with Cardio AI!`,
            url: window.location.origin
        };

        try {
            if (navigator.share) {
                await navigator.share(shareData);
            } else {
                await navigator.clipboard.writeText(`${shareData.title}\n${shareData.text}`);
                alert("Workout stats copied to clipboard!");
            }
        } catch (err) {
            console.error("Share failed", err);
        }
    };

    const submitRPE = async () => {
        if (!workout) return;

        const caloriesBurned = Math.round((seconds / 60) * workout.estimated_calories_per_min);
        const dateStr = new Date().toISOString();

        // Save to local storage
        const history = JSON.parse(localStorage.getItem('workout_history') || '[]');
        history.push({
            id: workout.id,
            title: workout.title,
            date: dateStr,
            duration: seconds,
            calories: caloriesBurned,
            rpe: rpe,
            notes: workoutNotes
        });
        localStorage.setItem('workout_history', JSON.stringify(history));

        // AI Memory Injection (backend will handle this)
        // await memoryService.init(); // Will be moved to backend

        // Adaptive Logic Check (Client-side simulation)
        if (workout.intensity === 'medium' && rpe >= 9) {
            alert("Noted! That seemed harder than expected. We'll adjust future recommendations to be slightly lighter.");
            localStorage.setItem('adaptive_adjustment', 'decrease_difficulty');
        }

        setShowRPE(false);
        setSeconds(0);
        navigate('/exercise');
    };

    const formatTimer = (totalSeconds: number) => {
        const m = Math.floor(totalSeconds / 60);
        const s = totalSeconds % 60;
        return `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;
    };

    const getProgressPercentage = () => {
        if (!workout) return 0;
        const totalSeconds = workout.duration_min * 60;
        return Math.min(100, (seconds / totalSeconds) * 100);
    };

    if (!workout) {
        return (
            <div className="min-h-screen flex flex-col items-center justify-center bg-background-light dark:bg-background-dark p-6 text-center">
                <span className="material-symbols-outlined text-6xl text-slate-300 mb-4">fitness_center</span>
                <h2 className="text-xl font-bold dark:text-white mb-2">Workout Not Found</h2>
                <p className="text-slate-500 mb-6">The exercise you are looking for doesn't exist.</p>
                <button onClick={() => navigate('/exercise')} className="px-6 py-3 bg-primary text-white rounded-xl font-bold">
                    Back to Exercise
                </button>
            </div>
        );
    }

    const categoryColor = {
        'Cardio': 'text-red-500 bg-red-50 dark:bg-red-900/20',
        'Strength': 'text-orange-500 bg-orange-50 dark:bg-orange-900/20',
        'Flexibility': 'text-purple-500 bg-purple-50 dark:bg-purple-900/20',
        'Balance': 'text-blue-500 bg-blue-50 dark:bg-blue-900/20',
        'Recovery': 'text-green-500 bg-green-50 dark:bg-green-900/20',
    }[workout.category] || 'text-slate-500 bg-slate-50 dark:bg-slate-900/20';

    let videoSrc = workout.videoUrl || "https://www.youtube.com/embed/ml6cT4AZdqI";

    // Convert standard YouTube watch URLs to embed URLs
    if (videoSrc.includes('youtube.com/watch?v=')) {
        const videoId = videoSrc.split('v=')[1]?.split('&')[0];
        if (videoId) videoSrc = `https://www.youtube.com/embed/${videoId}`;
    } else if (videoSrc.includes('youtu.be/')) {
        const videoId = videoSrc.split('youtu.be/')[1]?.split('?')[0];
        if (videoId) videoSrc = `https://www.youtube.com/embed/${videoId}`;
    }

    const isYouTube = videoSrc.includes('youtube.com/embed') || videoSrc.includes('youtube.com') || videoSrc.includes('youtu.be');

    return (
        <div className="min-h-screen bg-white dark:bg-background-dark pb-24 relative">
            {/* Hero Image */}
            <div className="w-full h-[40vh] relative">
                <img src={getImageUrl(workout.image, workout.id)} alt={workout.title} className="w-full h-full object-cover" />
                <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-transparent to-black/60"></div>

                <div className="absolute top-0 left-0 right-0 p-4 flex justify-between items-center z-10">
                    <button onClick={() => navigate(-1)} className="w-10 h-10 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center text-white hover:bg-white/30 transition-colors">
                        <span className="material-symbols-outlined">arrow_back</span>
                    </button>

                    {/* New Controls for DJ & Bluetooth */}
                    <div className="flex gap-3">
                        <button
                            onClick={toggleMusic}
                            className={`h-10 px-3 rounded-full backdrop-blur-md flex items-center justify-center gap-1 text-xs font-bold transition-colors ${isMusicEnabled ? 'bg-green-500/80 text-white' : 'bg-white/20 text-white hover:bg-white/30'}`}
                        >
                            <span className="material-symbols-outlined text-sm">{isMusicEnabled ? 'music_note' : 'music_off'}</span>
                            AI DJ
                        </button>

                        <button
                            onClick={connectHeartRate}
                            className={`h-10 px-3 rounded-full backdrop-blur-md flex items-center justify-center gap-1 text-xs font-bold transition-colors ${isBlueToothConnected ? 'bg-red-500/80 text-white' : 'bg-white/20 text-white hover:bg-white/30'}`}
                        >
                            <span className={`material-symbols-outlined text-sm ${isBlueToothConnected ? 'animate-pulse' : ''}`}>favorite</span>
                            {heartRate > 0 ? `${heartRate} bpm` : 'Connect HR'}
                        </button>
                    </div>
                </div>
            </div>

            {/* Content Sheet */}
            <div className="relative -mt-10 bg-white dark:bg-card-dark rounded-t-[32px] px-6 pt-8 pb-8 min-h-[70vh] shadow-2xl animate-in slide-in-from-bottom duration-300">
                <div className="w-12 h-1 bg-slate-200 dark:bg-slate-700 rounded-full mx-auto mb-6"></div>

                <div className="mb-6">
                    <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-1 rounded-md ${categoryColor} mb-2 inline-block`}>
                        {workout.category}
                    </span>
                    <h1 className="text-2xl font-bold dark:text-white mb-2 leading-tight">{workout.title}</h1>
                    <p className="text-slate-500 dark:text-slate-400 text-sm leading-relaxed">{workout.description}</p>
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-3 gap-3 mb-8">
                    <div className="bg-slate-50 dark:bg-slate-800 rounded-xl p-3 text-center border border-slate-100 dark:border-slate-700/50">
                        <span className="material-symbols-outlined text-primary mb-1 text-xl">timer</span>
                        <span className="block text-sm font-bold dark:text-white">{workout.duration_min} min</span>
                        <span className="text-[10px] text-slate-400">Duration</span>
                    </div>
                    <div className="bg-slate-50 dark:bg-slate-800 rounded-xl p-3 text-center border border-slate-100 dark:border-slate-700/50">
                        <span className="material-symbols-outlined text-orange-500 mb-1 text-xl">local_fire_department</span>
                        <span className="block text-sm font-bold dark:text-white">{workout.estimated_calories_per_min * workout.duration_min} Cal</span>
                        <span className="text-[10px] text-slate-400">{workout.estimated_calories_per_min} cal/min</span>
                    </div>
                    <div className="bg-slate-50 dark:bg-slate-800 rounded-xl p-3 text-center border border-slate-100 dark:border-slate-700/50">
                        <span className="material-symbols-outlined text-green-500 mb-1 text-xl">barbell</span>
                        <span className="block text-sm font-bold dark:text-white capitalize">{workout.intensity}</span>
                        <span className="text-[10px] text-slate-400">Intensity</span>
                    </div>
                </div>

                <div className="mb-8 relative z-50">
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="font-bold text-lg dark:text-white">Video Demonstration</h3>
                        {isYouTube && (
                            <button
                                onClick={() => setIsVideoExpanded(!isVideoExpanded)}
                                className="text-xs text-primary font-bold flex items-center gap-1 hover:underline"
                            >
                                <span className="material-symbols-outlined text-sm">
                                    {isVideoExpanded ? 'close_fullscreen' : 'open_in_full'}
                                </span>
                                {isVideoExpanded ? 'Collapse' : 'Expand'}
                            </button>
                        )}
                    </div>

                    <div
                        className={`transition-all duration-300 ease-in-out ${isVideoExpanded
                            ? 'fixed inset-0 z-[100] bg-black flex items-center justify-center p-4'
                            : 'rounded-2xl overflow-hidden bg-black aspect-video shadow-md relative group'
                            }`}
                    >
                        {isYouTube ? (
                            <>
                                {isVideoExpanded && (
                                    <button
                                        onClick={() => setIsVideoExpanded(false)}
                                        className="absolute top-6 right-6 w-10 h-10 bg-white/20 hover:bg-white/30 rounded-full flex items-center justify-center text-white backdrop-blur-md z-50"
                                    >
                                        <span className="material-symbols-outlined">close</span>
                                    </button>
                                )}
                                <div className={`relative w-full ${isVideoExpanded ? 'h-full max-w-5xl max-h-[80vh]' : 'h-full'}`}>
                                    <iframe
                                        width="100%"
                                        height="100%"
                                        src={videoSrc}
                                        title="Workout Demonstration"
                                        frameBorder="0"
                                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                                        allowFullScreen
                                        className="w-full h-full"
                                    ></iframe>
                                </div>
                            </>
                        ) : (
                            <CustomVideoPlayer
                                src={videoSrc}
                                poster={getImageUrl(workout.image, workout.id)}
                                isExpanded={isVideoExpanded}
                                toggleExpand={() => setIsVideoExpanded(!isVideoExpanded)}
                            />
                        )}
                    </div>
                </div>

                <div className="mb-8">
                    <h3 className="font-bold text-lg dark:text-white mb-4">Instructions</h3>
                    <div className="space-y-6 relative pl-2">
                        <div className="absolute left-[19px] top-4 bottom-8 w-0.5 bg-slate-200 dark:bg-slate-700"></div>
                        {workout.steps.map((step, i) => (
                            <div key={i} className="flex gap-6 relative z-10 group">
                                <div className="w-10 h-10 rounded-full bg-white dark:bg-slate-800 border-2 border-primary text-primary flex items-center justify-center text-sm font-bold flex-shrink-0 group-hover:bg-primary group-hover:text-white transition-colors shadow-sm">
                                    {i + 1}
                                </div>
                                <div className="pt-2 pb-4">
                                    <p className="text-slate-700 dark:text-slate-200 text-sm leading-relaxed">{step}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Floating Action Bar */}
            <div className="fixed bottom-0 left-0 right-0 z-20 w-full px-4 pb-6 pt-4 bg-gradient-to-t from-background-light dark:from-background-dark via-background-light/90 dark:via-background-dark/90 to-transparent">
                {!isActive ? (
                    <button
                        onClick={handleStartRequest}
                        className="w-full py-4 bg-primary hover:bg-primary-dark text-white rounded-2xl font-bold shadow-xl shadow-primary/30 flex items-center justify-center gap-2 transition-transform hover:scale-[1.02]"
                    >
                        <span className="material-symbols-outlined">play_circle</span>
                        Start Workout
                    </button>
                ) : (
                    <div className="flex gap-3 items-end">
                        {/* Live Coach Toggle */}
                        <button
                            onClick={isLiveCoachActive ? stopLiveCoach : startLiveCoach}
                            className={`h-14 w-14 rounded-2xl flex items-center justify-center transition-all shadow-lg shrink-0 ${isLiveCoachActive
                                ? 'bg-red-500 text-white shadow-red-500/20'
                                : 'bg-slate-800 text-slate-400'
                                }`}
                        >
                            {isCoachSpeaking && (
                                <span className="absolute w-14 h-14 rounded-2xl border-2 border-red-500 animate-ping opacity-50"></span>
                            )}
                            <span className="material-symbols-outlined relative z-10">{isLiveCoachActive ? 'mic_off' : 'mic'}</span>
                        </button>

                        {/* Active Workout Card */}
                        <div className="flex-1 bg-slate-900 text-white rounded-2xl p-4 shadow-2xl border border-slate-700 animate-in slide-in-from-bottom duration-300 relative overflow-hidden">
                            {/* Progress Bar Background */}
                            <div className="absolute top-0 left-0 bottom-0 bg-white/5 pointer-events-none transition-all duration-1000 linear" style={{ width: `${getProgressPercentage()}%` }}></div>

                            <div className="relative z-10 flex justify-between items-center mb-2">
                                <div className="flex items-center gap-2">
                                    <span className="material-symbols-outlined text-green-400 animate-pulse text-sm">fiber_manual_record</span>
                                    <span className="text-xs font-bold uppercase tracking-wider text-green-400">Live</span>
                                </div>
                                <div className="text-right">
                                    <span className="text-xs text-slate-400">Target: {workout.duration_min}m</span>
                                </div>
                            </div>

                            <div className="relative z-10 flex justify-between items-end">
                                <div>
                                    <p className="font-mono text-3xl font-bold leading-none tracking-tight">{formatTimer(seconds)}</p>
                                </div>
                                <button
                                    onClick={handleFinishRequest}
                                    className="px-5 py-2 bg-primary hover:bg-primary-dark text-slate-900 rounded-xl font-bold text-sm flex items-center gap-1 transition-colors shadow-lg shadow-primary/20"
                                >
                                    <span className="material-symbols-outlined text-lg">flag</span>
                                    Finish
                                </button>
                            </div>

                            {/* Thin visual progress line at bottom */}
                            <div className="absolute bottom-0 left-0 right-0 h-1 bg-slate-800">
                                <div className="h-full bg-primary transition-all duration-1000 linear" style={{ width: `${getProgressPercentage()}%` }}></div>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Pre-Workout Safety Check Modal */}
            {showPreCheck && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
                    <div className="bg-white dark:bg-card-dark rounded-2xl p-6 w-full max-w-sm shadow-2xl">
                        {!isSafetyLocked ? (
                            <>
                                <div className="flex items-center gap-3 mb-4 text-primary">
                                    <span className="material-symbols-outlined text-3xl">medical_services</span>
                                    <h3 className="text-xl font-bold dark:text-white">Pre-Workout Check</h3>
                                </div>
                                <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
                                    This is a high-intensity workout. Please verify your vitals are safe to proceed.
                                </p>
                                <div className="space-y-4 mb-6">
                                    <div className="grid grid-cols-2 gap-3">
                                        <div>
                                            <label className="text-xs font-bold text-slate-500">Systolic</label>
                                            <input
                                                type="number"
                                                value={vitals.systolic}
                                                onChange={e => setVitals({ ...vitals, systolic: e.target.value })}
                                                placeholder="120"
                                                className="w-full p-3 rounded-xl bg-slate-100 dark:bg-slate-800 border-none dark:text-white text-center font-bold"
                                            />
                                        </div>
                                        <div>
                                            <label className="text-xs font-bold text-slate-500">Diastolic</label>
                                            <input
                                                type="number"
                                                value={vitals.diastolic}
                                                onChange={e => setVitals({ ...vitals, diastolic: e.target.value })}
                                                placeholder="80"
                                                className="w-full p-3 rounded-xl bg-slate-100 dark:bg-slate-800 border-none dark:text-white text-center font-bold"
                                            />
                                        </div>
                                    </div>
                                    <div>
                                        <label className="text-xs font-bold text-slate-500">Heart Rate</label>
                                        <div className="flex gap-2">
                                            <input
                                                type="number"
                                                value={vitals.hr}
                                                onChange={e => setVitals({ ...vitals, hr: e.target.value })}
                                                placeholder="72"
                                                className="w-full p-3 rounded-xl bg-slate-100 dark:bg-slate-800 border-none dark:text-white text-center font-bold"
                                            />
                                            <button onClick={() => setVitals({ ...vitals, hr: heartRate.toString() })} className="bg-primary/20 text-primary px-3 rounded-xl font-bold text-xs whitespace-nowrap">
                                                Read Device
                                            </button>
                                        </div>
                                    </div>
                                </div>
                                <div className="flex gap-3">
                                    <button onClick={() => setShowPreCheck(false)} className="flex-1 py-3 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-bold rounded-xl">Cancel</button>
                                    <button onClick={checkVitals} disabled={!vitals.systolic || !vitals.diastolic} className="flex-1 py-3 bg-primary text-white font-bold rounded-xl disabled:opacity-50">Proceed</button>
                                </div>
                            </>
                        ) : (
                            <div className="text-center">
                                <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4 text-red-600 animate-pulse">
                                    <span className="material-symbols-outlined text-4xl">warning</span>
                                </div>
                                <h3 className="text-xl font-bold text-red-600 mb-2">Hypertensive Crisis Risk</h3>
                                <p className="text-slate-600 dark:text-slate-300 mb-6 text-sm">
                                    Your blood pressure is too high for intense exercise. We recommend a recovery session or consulting a doctor.
                                </p>
                                <button onClick={() => navigate('/workout/w_breathing_07_calm')} className="w-full py-3 bg-green-500 text-white font-bold rounded-xl mb-3 flex items-center justify-center gap-2">
                                    <span className="material-symbols-outlined">self_improvement</span> Switch to Breathing Exercise
                                </button>
                                <button onClick={() => setShowPreCheck(false)} className="text-slate-400 text-sm underline">Cancel</button>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Post-Workout RPE Modal */}
            {showRPE && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
                    <div className="bg-white dark:bg-card-dark w-full max-w-md rounded-2xl p-6 animate-in zoom-in-95 duration-200 overflow-y-auto max-h-[90vh]">
                        <div className="w-16 h-16 bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400 rounded-full flex items-center justify-center mx-auto mb-4">
                            <span className="material-symbols-outlined text-3xl filled">check_circle</span>
                        </div>
                        <h3 className="text-2xl font-bold dark:text-white text-center mb-1">Great Job!</h3>
                        <p className="text-slate-500 dark:text-slate-400 text-center text-sm mb-6">Workout Completed</p>

                        <div className="mb-6">
                            <p className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-3">Rate Exertion (RPE)</p>
                            <div className="flex justify-between mb-4 text-3xl transition-all">
                                <span className={`filter ${rpe <= 3 ? 'grayscale-0 scale-125' : 'grayscale opacity-50'}`}>🙂</span>
                                <span className={`filter ${rpe > 3 && rpe <= 7 ? 'grayscale-0 scale-125' : 'grayscale opacity-50'}`}>😐</span>
                                <span className={`filter ${rpe > 7 ? 'grayscale-0 scale-125' : 'grayscale opacity-50'}`}>🥵</span>
                            </div>
                            <input
                                type="range"
                                min="1"
                                max="10"
                                value={rpe}
                                onChange={e => setRpe(parseInt(e.target.value))}
                                className="w-full h-3 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-primary"
                            />
                            <div className="flex justify-between mt-2 text-xs font-bold text-slate-400 uppercase tracking-wider">
                                <span>Easy</span>
                                <span>Moderate</span>
                                <span>Max Effort</span>
                            </div>
                            <div className="text-center mt-2 font-bold text-primary text-xl">{rpe} / 10</div>
                        </div>

                        <div className="mb-6">
                            <p className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-2">Notes</p>
                            <textarea
                                className="w-full p-3 bg-slate-100 dark:bg-slate-800 rounded-xl border-none outline-none dark:text-white resize-none h-24 focus:ring-2 focus:ring-primary"
                                placeholder="How did you feel? Any pain?"
                                value={workoutNotes}
                                onChange={(e) => setWorkoutNotes(e.target.value)}
                            ></textarea>
                        </div>

                        <div className="flex gap-3">
                            <button
                                onClick={handleShare}
                                className="flex-1 py-3 bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-900 dark:text-white font-bold rounded-xl flex items-center justify-center gap-2 transition-colors"
                            >
                                <span className="material-symbols-outlined text-sm">share</span> Share
                            </button>
                            <button onClick={submitRPE} className="flex-[2] py-3 bg-primary hover:bg-primary-dark text-white font-bold rounded-xl shadow-lg shadow-primary/20 transition-colors">
                                Save & Finish
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default WorkoutDetailScreen;
