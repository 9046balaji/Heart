
import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import formattedRecipeData from '../data/formattedRecipes';
import { Recipe, FlexibleRecipe } from '../types/recipeTypes';
import { apiClient, APIError } from '../services/apiClient';
import { useToast } from '../components/Toast';

// --- Helper: Parse time from string ---
// Returns seconds if found, else 0
const extractDuration = (text: string): number => {
    const regex = /(\d+)\s*(min|minute|sec|second)/i;
    const match = text.match(regex);
    if (match) {
        const val = parseInt(match[1]);
        const unit = match[2].toLowerCase();
        if (unit.startsWith('min')) return val * 60;
        return val;
    }
    return 0;
};

// --- Helper: Highlight Techniques ---
const HighlightedInstruction = ({ text, onTermClick }: { text: string, onTermClick: (term: string) => void }) => {
    const techniques = ['boil', 'simmer', 'sauté', 'saute', 'fry', 'bake', 'roast', 'grill', 'steam', 'poach', 'blanch', 'braise', 'stew', 'broil', 'marinate', 'whisk', 'fold', 'knead', 'julienne', 'dice', 'mince', 'chop', 'slice', 'peel', 'grate', 'zest', 'sear', 'mix', 'blend', 'mash', 'crush'];

    // Split by regex, keeping the delimiter
    const regex = new RegExp(`\\b(${techniques.join('|')})\\b`, 'gi');
    const parts = text.split(regex);

    return (
        <span>
            {parts.map((part, i) => {
                if (techniques.some(t => t.toLowerCase() === part.toLowerCase())) {
                    return (
                        <span
                            key={i}
                            onClick={(e) => { e.stopPropagation(); onTermClick(part); }}
                            className="text-primary font-bold cursor-pointer border-b-2 border-dotted border-primary/50 hover:text-primary-dark hover:border-primary transition-colors"
                            title="Tap for explanation"
                        >
                            {part}
                        </span>
                    );
                }
                return <span key={i}>{part}</span>;
            })}
        </span>
    );
};

const CookingModeOverlay = ({
    recipe,
    onClose,
    onComplete
}: {
    recipe: any,
    onClose: () => void,
    onComplete: () => void
}) => {
    const [stepIndex, setStepIndex] = useState(0);
    const [timerActive, setTimerActive] = useState(false);
    const [timeLeft, setTimeLeft] = useState(0);
    const [initialTime, setInitialTime] = useState(0);
    const timerRef = useRef<any>(null);

    const currentStep = recipe.steps[stepIndex];
    const detectedDuration = extractDuration(currentStep);

    useEffect(() => {
        // Reset timer when changing steps
        setTimerActive(false);
        if (timerRef.current) clearInterval(timerRef.current);
        setTimeLeft(0);
        setInitialTime(0);
    }, [stepIndex]);

    useEffect(() => {
        if (timerActive && timeLeft > 0) {
            timerRef.current = setInterval(() => {
                setTimeLeft((prev) => {
                    if (prev <= 1) {
                        clearInterval(timerRef.current);
                        setTimerActive(false);
                        // Play beep
                        const audio = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg');
                        audio.play();
                        return 0;
                    }
                    return prev - 1;
                });
            }, 1000);
        }
        return () => clearInterval(timerRef.current);
    }, [timerActive]);

    const startTimer = (duration: number) => {
        setInitialTime(duration);
        setTimeLeft(duration);
        setTimerActive(true);
    };

    const formatTime = (seconds: number) => {
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return `${m}:${s < 10 ? '0' : ''}${s}`;
    };

    const speakText = (text: string) => {
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel(); // Stop current
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = 0.9;
            window.speechSynthesis.speak(utterance);
        }
    };

    const handleNext = () => {
        if (stepIndex < recipe.steps.length - 1) {
            setStepIndex(stepIndex + 1);
        } else {
            onComplete();
        }
    };

    const handlePrev = () => {
        if (stepIndex > 0) {
            setStepIndex(stepIndex - 1);
        }
    };

    return (
        <div className="fixed inset-0 z-50 bg-slate-900 text-white flex flex-col animate-in slide-in-from-bottom duration-300">
            {/* Top Bar */}
            <div className="flex items-center justify-between p-4 pb-2">
                <button onClick={onClose} className="p-2 rounded-full hover:bg-white/10 transition-colors">
                    <span className="material-symbols-outlined text-2xl">close</span>
                </button>
                <div className="flex-1 mx-4">
                    <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-green-500 transition-all duration-300"
                            style={{ width: `${((stepIndex + 1) / recipe.steps.length) * 100}%` }}
                        ></div>
                    </div>
                    <p className="text-center text-xs text-slate-400 mt-1">Step {stepIndex + 1} of {recipe.steps.length}</p>
                </div>
                <button onClick={() => speakText(currentStep)} className="p-2 rounded-full hover:bg-white/10 transition-colors text-primary">
                    <span className="material-symbols-outlined text-2xl">volume_up</span>
                </button>
            </div>

            {/* Main Content */}
            <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
                <div className="mb-8">
                    <div className="w-16 h-16 bg-primary/20 text-primary rounded-full flex items-center justify-center mx-auto mb-6 text-2xl font-bold border-2 border-primary">
                        {stepIndex + 1}
                    </div>
                    <h2 className="text-2xl md:text-3xl font-bold leading-relaxed">{currentStep}</h2>
                </div>

                {/* Smart Timer UI - Priority 2 */}
                {detectedDuration > 0 && (
                    <div className="mt-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                        {!timerActive && timeLeft === 0 ? (
                            <button
                                onClick={() => startTimer(detectedDuration)}
                                className="flex items-center gap-2 px-6 py-3 bg-slate-800 border border-slate-600 rounded-full hover:bg-slate-700 transition-colors text-lg font-medium text-orange-400 shadow-lg shadow-orange-500/10"
                            >
                                <span className="material-symbols-outlined filled">timer</span>
                                Start Timer ({Math.round(detectedDuration / 60)}m)
                            </button>
                        ) : (
                            <div className="flex flex-col items-center gap-4 animate-in fade-in zoom-in">
                                <div className="relative">
                                    <svg className="w-48 h-48 transform -rotate-90">
                                        <circle cx="96" cy="96" r="90" stroke="currentColor" strokeWidth="8" fill="transparent" className="text-slate-800" />
                                        <circle
                                            cx="96" cy="96" r="90"
                                            stroke="currentColor" strokeWidth="8" fill="transparent"
                                            className="text-orange-500 transition-all duration-1000 linear"
                                            strokeDasharray={565.48}
                                            strokeDashoffset={565.48 - ((timeLeft / initialTime) * 565.48)}
                                        />
                                    </svg>
                                    <div className="absolute inset-0 flex items-center justify-center">
                                        <span className="text-4xl font-mono font-bold text-white">{formatTime(timeLeft)}</span>
                                    </div>
                                </div>
                                <button
                                    onClick={() => setTimerActive(!timerActive)}
                                    className="px-6 py-2 bg-white/10 rounded-full text-sm font-bold hover:bg-white/20 transition-colors"
                                >
                                    {timerActive ? 'Pause' : 'Resume'}
                                </button>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Controls */}
            <div className="p-6 pb-8 flex gap-4">
                <button
                    onClick={handlePrev}
                    disabled={stepIndex === 0}
                    className="flex-1 py-4 rounded-2xl font-bold text-lg bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed hover:bg-slate-700 transition-colors"
                >
                    Back
                </button>
                <button
                    onClick={handleNext}
                    className="flex-[2] py-4 rounded-2xl font-bold text-lg bg-primary text-white hover:bg-primary-dark transition-colors shadow-lg shadow-primary/20"
                >
                    {stepIndex === recipe.steps.length - 1 ? 'Finish Cooking' : 'Next Step'}
                </button>
            </div>
        </div>
    );
};

const RecipeDetailScreen: React.FC = () => {
    const navigate = useNavigate();
    const { id } = useParams();
    const { showToast } = useToast();
    const [activeTab, setActiveTab] = useState<'Ingredients' | 'Instructions'>('Ingredients');
    const [isFavorite, setIsFavorite] = useState(false);
    const [servings, setServings] = useState(1);
    const [isCooking, setIsCooking] = useState(false);
    const [recipe, setRecipe] = useState<any>(null);

    // AI Modal States
    const [showSubModal, setShowSubModal] = useState(false);
    const [subModalData, setSubModalData] = useState<{ ingredient: string, result: string | null, loading: boolean }>({ ingredient: '', result: null, loading: false });

    const [showTechModal, setShowTechModal] = useState(false);
    const [techModalData, setTechModalData] = useState<{ term: string, result: string | null, loading: boolean }>({ term: '', result: null, loading: false });

    useEffect(() => {
        // Check static data first - now accessing directly without .recipe
        const staticItem = formattedRecipeData.find(recipe => recipe.id === id);
        if (staticItem) {
            setRecipe(staticItem);
        } else {
            // Check custom/generated recipes in local storage
            const customRecipes = JSON.parse(localStorage.getItem('custom_recipes') || '[]');
            const customItem = customRecipes.find((r: any) => r.id === id);
            if (customItem) {
                setRecipe(customItem);
            }
        }
    }, [id]);

    useEffect(() => {
        window.scrollTo(0, 0);
        if (recipe) {
            setServings(recipe.servings);
        }
    }, [recipe]);

    useEffect(() => {
        if (id) {
            const saved = JSON.parse(localStorage.getItem('saved_recipes') || '[]');
            setIsFavorite(saved.includes(id));
        }
    }, [id]);

    const toggleFavorite = () => {
        if (!id) return;
        const saved = JSON.parse(localStorage.getItem('saved_recipes') || '[]');
        let newSaved;
        if (isFavorite) {
            newSaved = saved.filter((savedId: string) => savedId !== id);
        } else {
            newSaved = [...saved, id];
        }
        localStorage.setItem('saved_recipes', JSON.stringify(newSaved));
        setIsFavorite(!isFavorite);
    };

    const handleCookingComplete = () => {
        setIsCooking(false);
        if (recipe) {
            const logItem = {
                id: `cooked_${Date.now()}`,
                name: recipe.title,
                calories: recipe.calories,
                protein: recipe.macros.protein_g,
                carbs: recipe.macros.carbs_g,
                fat: recipe.macros.fat_g || recipe.macros.fats_g,
                sodium: 0,
                image: recipe.image,
                time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            };
            const currentLog = JSON.parse(localStorage.getItem('daily_food_log') || '[]');
            localStorage.setItem('daily_food_log', JSON.stringify([logItem, ...currentLog]));
            showToast("Recipe completed and logged to your daily nutrition!", 'success');
            navigate('/nutrition');
        }
    };

    const getImageUrl = (img: string) => {
        if (!img) return `https://picsum.photos/seed/${id}/800/600`;
        if (img.startsWith('/images/')) {
            return `https://picsum.photos/seed/${recipe?.id}/800/600`;
        }
        return img;
    };

    const getIngredientDisplay = (item: any) => {
        const originalServings = recipe?.servings || 1;
        const ratio = servings / originalServings;

        // Safely get the amount value regardless of format
        const amountValue = item.amount !== undefined ? item.amount : (item.measure || 'As needed');

        // Handle New Data Format (Number amount + Unit string) e.g., { amount: 2, unit: "cups" }
        if (typeof amountValue === 'number') {
            const scaled = amountValue * ratio;
            // Format to remove unnecessary decimals (e.g., 2.00 -> 2)
            const formatted = Number.isInteger(scaled) ? scaled : parseFloat(scaled.toFixed(2));
            return `${formatted} ${item.unit || ''}`;
        }

        // Handle Old Data Format (String amount e.g. "300g" or "1 cup")
        const amountStr = String(amountValue);
        const numericMatch = amountStr.match(/^(\d+(\.\d+)?)/); // Matches number at start

        if (numericMatch) {
            const baseVal = parseFloat(numericMatch[0]);
            if (!isNaN(baseVal)) {
                const scaled = baseVal * ratio;
                const formatted = Number.isInteger(scaled) ? scaled : parseFloat(scaled.toFixed(1));
                // Replace the original number in the string with the scaled one
                return amountStr.replace(numericMatch[0], String(formatted));
            }
        }

        // Fallback: just return the string if scaling fails
        return amountStr;
    };

    // --- AI Feature: Ingredient Substitution ---
    const handleGetSubstitute = async (ingredient: string) => {
        setSubModalData({ ingredient, result: null, loading: true });
        setShowSubModal(true);

        try {
            // Call backend API proxy
            setSubModalData(prev => ({
                ...prev,
                result: `Healthy substitutes for ${ingredient}:\n• Option 1\n• Option 2\n• Option 3`,
                loading: false
            }));
        } catch (e) {
            setSubModalData(prev => ({ ...prev, result: "Could not load suggestions.", loading: false }));
        }
    };

    // --- AI Feature: Technique Explainer ---
    const handleExplainTechnique = async (term: string) => {
        setTechModalData({ term, result: null, loading: true });
        setShowTechModal(true);

        try {
            // Call backend API proxy
            setTechModalData(prev => ({
                ...prev,
                result: `${term} is a cooking method used to prepare food properly. It involves careful technique and timing.`,
                loading: false
            }));
        } catch (e) {
            setTechModalData(prev => ({ ...prev, result: "Could not load explanation.", loading: false }));
        }
    };

    if (!recipe) return <div className="p-8 text-center">Loading recipe...</div>;

    return (
        <div className="min-h-screen bg-white dark:bg-background-dark pb-24 relative overflow-x-hidden">
            {/* Hero Image */}
            <div className="w-full h-[40vh] relative">
                <img src={getImageUrl(recipe.image)} alt={recipe.title} className="w-full h-full object-cover" />
                <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-transparent to-black/60"></div>

                <div className="absolute top-0 left-0 right-0 p-4 flex justify-between items-center z-10">
                    <button onClick={() => navigate(-1)} className="w-10 h-10 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center text-white hover:bg-white/30 transition-colors">
                        <span className="material-symbols-outlined">arrow_back</span>
                    </button>
                    <button onClick={toggleFavorite} className="w-10 h-10 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center text-white hover:bg-white/30 transition-colors">
                        <span className={`material-symbols-outlined ${isFavorite ? 'filled text-red-500' : ''}`}>favorite</span>
                    </button>
                </div>
            </div>

            {/* Content Sheet */}
            <div className="relative -mt-10 bg-white dark:bg-card-dark rounded-t-[32px] px-6 pt-8 pb-8 min-h-[70vh] shadow-2xl">
                <div className="w-12 h-1 bg-slate-200 dark:bg-slate-700 rounded-full mx-auto mb-6"></div>

                <div className="mb-6">
                    <div className="flex gap-2 mb-3 flex-wrap">
                        {recipe.tags && recipe.tags.slice(0, 4).map((tag: string) => (
                            <span key={tag} className="bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400 text-[10px] font-bold px-2 py-1 rounded-md uppercase tracking-wide">
                                {tag}
                            </span>
                        ))}
                    </div>
                    <h1 className="text-2xl font-bold dark:text-white mb-2 leading-tight">{recipe.title}</h1>
                    <div className="flex items-center gap-6 text-slate-500 dark:text-slate-400 text-sm flex-wrap">
                        {recipe.ratings && (
                            <div className="flex items-center gap-1">
                                <span className="material-symbols-outlined text-yellow-400 filled text-lg">star</span>
                                <span className="font-bold dark:text-white">{recipe.ratings.avg}</span>
                                <span className="text-xs">({recipe.ratings.count})</span>
                            </div>
                        )}
                        <div className="flex items-center gap-1">
                            <span className="material-symbols-outlined text-lg">schedule</span>
                            <span>{(recipe.prep_time_min || 0) + (recipe.cook_time_min || 0)} min</span>
                        </div>
                        <div className="flex items-center gap-1">
                            <span className="material-symbols-outlined text-lg">local_fire_department</span>
                            <span>{recipe.calories} kcal</span>
                        </div>
                        <div className="flex items-center gap-1">
                            <span className="material-symbols-outlined text-lg">barbell</span>
                            <span className="capitalize">{recipe.difficulty}</span>
                        </div>
                    </div>
                </div>

                {/* Nutrition Grid */}
                <div className="grid grid-cols-3 gap-3 mb-8">
                    <div className="bg-slate-50 dark:bg-slate-800 rounded-xl p-3 text-center border border-slate-100 dark:border-slate-700/50">
                        <span className="block text-[10px] text-slate-400 uppercase font-bold tracking-wider mb-1">Protein</span>
                        <span className="block text-lg font-bold dark:text-white text-primary">{(recipe.macros?.protein_g || recipe.protein || 0)}g</span>
                    </div>
                    <div className="bg-slate-50 dark:bg-slate-800 rounded-xl p-3 text-center border border-slate-100 dark:border-slate-700/50">
                        <span className="block text-[10px] text-slate-400 uppercase font-bold tracking-wider mb-1">Carbs</span>
                        <span className="block text-lg font-bold dark:text-white text-orange-500">{(recipe.macros?.carbs_g || recipe.carbs || 0)}g</span>
                    </div>
                    <div className="bg-slate-50 dark:bg-slate-800 rounded-xl p-3 text-center border border-slate-100 dark:border-slate-700/50">
                        <span className="block text-[10px] text-slate-400 uppercase font-bold tracking-wider mb-1">Fats</span>
                        <span className="block text-lg font-bold dark:text-white text-yellow-500">
                            {(recipe.macros?.fat_g || recipe.macros?.fats_g || recipe.fat || recipe.fats || 0)}g
                        </span>
                    </div>
                </div>

                <p className="text-slate-600 dark:text-slate-300 text-sm leading-relaxed mb-8">
                    {recipe.description}
                </p>

                {/* YouTube Video Section */}
                {recipe.youtube && (
                    <div className="mb-8">
                        <h3 className="text-lg font-bold dark:text-white mb-4 flex items-center gap-2">
                            <span className="material-symbols-outlined text-red-500">play_circle</span>
                            Video Tutorial
                        </h3>
                        <div className="relative w-full pt-[56.25%] rounded-xl overflow-hidden shadow-lg bg-black">
                            <iframe
                                className="absolute top-0 left-0 w-full h-full"
                                src={`https://www.youtube.com/embed/${recipe.youtube.split('v=')[1]?.split('&')[0]}`}
                                title="Recipe Video"
                                frameBorder="0"
                                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                allowFullScreen
                            ></iframe>
                        </div>
                    </div>
                )}

                {/* Servings Control */}
                <div className="flex items-center justify-between mb-6 bg-slate-50 dark:bg-slate-800/50 p-3 rounded-xl">
                    <span className="text-sm font-bold dark:text-white">Servings</span>
                    <div className="flex items-center gap-4">
                        <button
                            onClick={() => setServings(Math.max(1, servings - 1))}
                            className="w-8 h-8 rounded-full bg-white dark:bg-slate-700 shadow-sm flex items-center justify-center text-slate-600 dark:text-white"
                        >
                            <span className="material-symbols-outlined text-sm">remove</span>
                        </button>
                        <span className="font-bold w-4 text-center dark:text-white">{servings}</span>
                        <button
                            onClick={() => setServings(servings + 1)}
                            className="w-8 h-8 rounded-full bg-white dark:bg-slate-700 shadow-sm flex items-center justify-center text-slate-600 dark:text-white"
                        >
                            <span className="material-symbols-outlined text-sm">add</span>
                        </button>
                    </div>
                </div>

                {/* Tab Switcher */}
                <div className="flex p-1 bg-slate-100 dark:bg-slate-800 rounded-xl mb-6">
                    {['Ingredients', 'Instructions'].map((tab) => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab as any)}
                            className={`flex-1 py-3 text-sm font-bold rounded-lg transition-all ${activeTab === tab
                                ? 'bg-white dark:bg-card-dark shadow-sm text-slate-900 dark:text-white'
                                : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300'
                                }`}
                        >
                            {tab}
                        </button>
                    ))}
                </div>

                {/* Tab Content */}
                <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
                    {activeTab === 'Ingredients' ? (
                        <ul className="space-y-3">
                            {recipe.ingredients.map((item: any, i: number) => (
                                <li key={i} className="flex items-center gap-4 p-3 rounded-xl border border-slate-50 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors group">
                                    <div className="w-2 h-2 rounded-full bg-green-500 flex-shrink-0"></div>
                                    <div className="flex-1 flex justify-between items-center">
                                        <span className="text-slate-700 dark:text-slate-200 text-sm font-medium">{item.name}</span>
                                        <div className="flex items-center gap-3">
                                            <span className="text-slate-500 dark:text-slate-400 text-sm">{getIngredientDisplay(item)}</span>
                                            {/* Priority 3: Substitution Button */}
                                            <button
                                                onClick={(e) => { e.stopPropagation(); handleGetSubstitute(item.name); }}
                                                className="w-6 h-6 rounded-full bg-blue-50 dark:bg-blue-900/30 text-blue-500 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                                                title="Find Substitutes"
                                            >
                                                <span className="material-symbols-outlined text-[14px]">swap_horiz</span>
                                            </button>
                                        </div>
                                    </div>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <div className="space-y-8 relative pl-2">
                            <div className="absolute left-[19px] top-4 bottom-8 w-0.5 bg-slate-200 dark:bg-slate-700"></div>

                            {recipe.steps.map((step: string, i: number) => (
                                <div key={i} className="flex gap-6 relative z-10 group">
                                    <div className="w-10 h-10 rounded-full bg-white dark:bg-slate-800 border-2 border-green-500 text-green-500 flex items-center justify-center text-sm font-bold flex-shrink-0 group-hover:bg-green-500 group-hover:text-white transition-colors">
                                        {i + 1}
                                    </div>
                                    <div className="pt-2 pb-4">
                                        <p className="text-slate-700 dark:text-slate-200 text-sm leading-relaxed">
                                            {/* Priority 4: Technique Highlighting */}
                                            <HighlightedInstruction text={step} onTermClick={handleExplainTechnique} />
                                        </p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            <div className="fixed bottom-6 left-6 right-6 z-20">
                <button
                    onClick={() => setIsCooking(true)}
                    className="w-full py-4 bg-primary hover:bg-primary-dark text-white rounded-2xl font-bold shadow-xl shadow-primary/30 flex items-center justify-center gap-2 transition-transform hover:scale-[1.02]"
                >
                    <span className="material-symbols-outlined">play_circle</span>
                    Start Cooking Mode
                </button>
            </div>

            {isCooking && (
                <CookingModeOverlay
                    recipe={recipe}
                    onClose={() => setIsCooking(false)}
                    onComplete={handleCookingComplete}
                />
            )}

            {/* Ingredient Substitute Modal */}
            {showSubModal && (
                <div className="fixed inset-0 z-[60] flex items-end justify-center p-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowSubModal(false)}>
                    <div className="bg-white dark:bg-card-dark w-full max-w-md rounded-t-3xl p-6 animate-in slide-in-from-bottom duration-300" onClick={e => e.stopPropagation()}>
                        <div className="w-12 h-1 bg-slate-200 dark:bg-slate-700 rounded-full mx-auto mb-6"></div>
                        <h3 className="text-lg font-bold dark:text-white mb-4 flex items-center gap-2">
                            <span className="material-symbols-outlined text-blue-500">swap_horiz</span>
                            Substitutes for "{subModalData.ingredient}"
                        </h3>

                        {subModalData.loading ? (
                            <div className="flex flex-col items-center py-8">
                                <span className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4"></span>
                                <p className="text-slate-500 text-sm">Asking Gemini for ideas...</p>
                            </div>
                        ) : (
                            <div className="text-slate-700 dark:text-slate-300 text-sm leading-relaxed whitespace-pre-line bg-slate-50 dark:bg-slate-800/50 p-4 rounded-xl">
                                {subModalData.result}
                            </div>
                        )}
                        <button onClick={() => setShowSubModal(false)} className="w-full mt-6 py-3 bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white font-bold rounded-xl">Close</button>
                    </div>
                </div>
            )}

            {/* Technique Explainer Modal */}
            {showTechModal && (
                <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={() => setShowTechModal(false)}>
                    <div className="bg-white dark:bg-card-dark w-full max-w-sm rounded-2xl p-6 animate-in zoom-in-95 duration-200 relative" onClick={e => e.stopPropagation()}>
                        <button onClick={() => setShowTechModal(false)} className="absolute top-4 right-4 text-slate-400 hover:text-slate-600"><span className="material-symbols-outlined">close</span></button>
                        <h3 className="text-lg font-bold dark:text-white mb-2 capitalize">{techModalData.term}</h3>
                        <div className="h-0.5 w-10 bg-primary mb-4"></div>

                        {techModalData.loading ? (
                            <div className="flex items-center gap-3 text-slate-500 text-sm">
                                <span className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin"></span>
                                Explaining...
                            </div>
                        ) : (
                            <p className="text-slate-600 dark:text-slate-300 text-sm leading-relaxed">
                                {techModalData.result}
                            </p>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default RecipeDetailScreen;
