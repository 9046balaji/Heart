
import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { recipeData } from '../data/recipes';
import { apiClient, APIError } from '../services/apiClient';

interface FoodLogItem {
  id: string;
  name: string;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  sodium: number;
  image: string;
  time: string;
}

const ShoppingListModal: React.FC<{
    list: { name: string, items: string[] }[],
    onClose: () => void
}> = ({ list, onClose }) => {
    const [checkedItems, setCheckedItems] = useState<Set<string>>(new Set());

    const toggleItem = (item: string) => {
        const newSet = new Set(checkedItems);
        if (newSet.has(item)) newSet.delete(item);
        else newSet.add(item);
        setCheckedItems(newSet);
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200" onClick={onClose}>
            <div className="bg-white dark:bg-card-dark rounded-2xl w-full max-w-md shadow-2xl flex flex-col max-h-[80vh]" onClick={e => e.stopPropagation()}>
                <div className="p-4 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center text-green-600 dark:text-green-400">
                            <span className="material-symbols-outlined text-lg">shopping_cart</span>
                        </div>
                        <h3 className="font-bold text-lg dark:text-white">Shopping List</h3>
                    </div>
                    <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
                        <span className="material-symbols-outlined">close</span>
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-4 space-y-6">
                    {list.map((category, idx) => (
                        <div key={idx}>
                            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">{category.name}</h4>
                            <div className="space-y-2">
                                {category.items.map((item, i) => {
                                    const isChecked = checkedItems.has(item);
                                    return (
                                        <div
                                            key={i}
                                            onClick={() => toggleItem(item)}
                                            className={`flex items-center gap-3 p-3 rounded-xl border transition-all cursor-pointer ${
                                                isChecked
                                                ? 'bg-slate-50 dark:bg-slate-800/50 border-transparent opacity-60'
                                                : 'bg-white dark:bg-slate-800 border-slate-100 dark:border-slate-700'
                                            }`}
                                        >
                                            <div className={`w-5 h-5 rounded border flex items-center justify-center transition-colors ${
                                                isChecked
                                                ? 'bg-green-500 border-green-500 text-white'
                                                : 'border-slate-300 dark:border-slate-600'
                                            }`}>
                                                {isChecked && <span className="material-symbols-outlined text-sm">check</span>}
                                            </div>
                                            <span className={`text-sm dark:text-white ${isChecked ? 'line-through text-slate-400' : ''}`}>{item}</span>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    ))}
                </div>

                <div className="p-4 border-t border-slate-100 dark:border-slate-800">
                    <button
                        onClick={() => {
                            const text = list.map(c => `${c.name}:\n${c.items.join('\n')}`).join('\n\n');
                            navigator.clipboard.writeText(text);
                            alert("Copied to clipboard!");
                        }}
                        className="w-full py-3 bg-primary hover:bg-primary-dark text-white rounded-xl font-bold transition-colors flex items-center justify-center gap-2"
                    >
                        <span className="material-symbols-outlined">content_copy</span>
                        Copy List
                    </button>
                </div>
            </div>
        </div>
    );
};

// Helper: Generate Image URL
const getImageUrl = (id: string, originalImage: string) => {
    if (!originalImage) return `https://picsum.photos/seed/${id}/400/400`;
    if (originalImage.startsWith('/images/')) {
        return `https://picsum.photos/seed/${id}/400/400`;
    }
    return originalImage;
};

// Component: Empty State
const EmptyState: React.FC<{ message: string, icon?: string, actionLabel?: string, onAction?: () => void }> = ({ message, icon = "search_off", actionLabel, onAction }) => (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
        <div className="w-16 h-16 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center mb-4">
            <span className="material-symbols-outlined text-slate-400 text-3xl">{icon}</span>
        </div>
        <p className="text-slate-500 dark:text-slate-400 font-medium mb-4 max-w-[250px]">{message}</p>
        {actionLabel && onAction && (
            <button
                onClick={onAction}
                className="px-4 py-2 bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 rounded-lg text-sm font-semibold transition-colors dark:text-white"
            >
                {actionLabel}
            </button>
        )}
    </div>
);

// Component: Recipe Card
const RecipeCard: React.FC<{ recipe: any }> = ({ recipe }) => {
    const navigate = useNavigate();
    return (
    <div
        onClick={() => {
            navigate(`/recipe/${recipe.id}`);
        }}
        className="flex flex-col gap-2 bg-white dark:bg-card-dark p-2 rounded-xl border border-slate-100 dark:border-slate-800 shadow-sm hover:shadow-md transition-shadow cursor-pointer"
    >
        <div className="relative rounded-lg overflow-hidden aspect-square group bg-slate-200 dark:bg-slate-800">
            <img src={getImageUrl(recipe.id, recipe.image)} alt={recipe.title} className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"/>
            <div className="absolute top-2 right-2 bg-black/60 text-white text-[10px] px-1.5 py-0.5 rounded-full flex items-center gap-1 backdrop-blur-sm font-medium">
                <span className="material-symbols-outlined text-[10px] text-yellow-400 filled">star</span>
                {recipe.ratings.avg.toFixed(1)}
            </div>
            {recipe.id.startsWith('gen_') && (
                <div className="absolute bottom-2 right-2 bg-purple-600 text-white text-[10px] px-1.5 py-0.5 rounded-md shadow-sm flex items-center gap-1">
                    <span className="material-symbols-outlined text-[10px]">auto_awesome</span> AI
                </div>
            )}
        </div>
        <div className="px-1 pb-1">
            <h3 className="font-bold text-slate-900 dark:text-white text-sm leading-tight line-clamp-2 h-10">{recipe.title}</h3>
            <div className="flex items-center gap-3 text-[10px] text-slate-500 mt-1">
                <span className="flex items-center gap-0.5"><span className="material-symbols-outlined text-[12px]">local_fire_department</span> {recipe.calories}</span>
                <span className="flex items-center gap-0.5"><span className="material-symbols-outlined text-[12px]">schedule</span> {recipe.prep_time_min + recipe.cook_time_min}m</span>
            </div>
        </div>
    </div>
    );
};

const NutritionScreen: React.FC = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('Meal Plans');
  const [searchQuery, setSearchQuery] = useState('');
  const [savedIds, setSavedIds] = useState<string[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [dailyLog, setDailyLog] = useState<FoodLogItem[]>([]);

  // Custom/AI Recipes State
  const [customRecipes, setCustomRecipes] = useState<any[]>([]);
  const [isCreatingRecipe, setIsCreatingRecipe] = useState(false);

  // Shopping List State
  const [showShoppingList, setShowShoppingList] = useState(false);
  const [shoppingList, setShoppingList] = useState<{name: string, items: string[]}[]>([]);
  const [isGeneratingList, setIsGeneratingList] = useState(false);

  // Camera/Scan State
  const [showScanModal, setShowScanModal] = useState(false);
  const [scannedImage, setScannedImage] = useState<string | null>(null);
  const [scannedData, setScannedData] = useState<FoodLogItem | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fridge Scan State
  const [showFridgeModal, setShowFridgeModal] = useState(false);
  const [fridgeRecipes, setFridgeRecipes] = useState<any[]>([]);
  const [detectedIngredients, setDetectedIngredients] = useState<string[]>([]);
  const fridgeInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Load Saved Recipes
    const saved = JSON.parse(localStorage.getItem('saved_recipes') || '[]');
    setSavedIds(saved);

    // Load Custom Recipes
    const savedCustom = JSON.parse(localStorage.getItem('custom_recipes') || '[]');
    setCustomRecipes(savedCustom);

    // Load Log
    const savedLog = JSON.parse(localStorage.getItem('daily_food_log') || '[]');
    setDailyLog(savedLog);
  }, [activeTab]);

  // Combine static data with generated custom recipes
  const allRecipes = [...customRecipes, ...recipeData.map(item => item.recipe)];

  // Mock initial state for meal plan (ensure we use IDs that exist either in static or custom)
  const initialMealPlan = [
    { type: 'Breakfast', ...allRecipes.find(r => r.id === 'r_010') || allRecipes[0], time: '8:00 AM' },
    { type: 'Lunch', ...allRecipes.find(r => r.id === 'r_001') || allRecipes[1], time: '1:00 PM' },
    { type: 'Dinner', ...allRecipes.find(r => r.id === 'r_005') || allRecipes[2], time: '7:00 PM' },
  ];

  const [mealPlan, setMealPlan] = useState(initialMealPlan);

  const addToLog = (item: FoodLogItem) => {
      const newLog = [item, ...dailyLog];
      setDailyLog(newLog);
      localStorage.setItem('daily_food_log', JSON.stringify(newLog));
      setShowScanModal(false);
      setScannedImage(null);
      setScannedData(null);
  };

  const guides = [
    { title: "Understanding Sodium", sub: "Tips for reducing salt in your diet.", read: "5 min", img: "https://picsum.photos/id/102/100/100" },
    { title: "The Power of Healthy Fats", sub: "Incorporating good fats for a healthy heart.", read: "8 min", img: "https://picsum.photos/id/106/100/100" },
    { title: "Sugar vs. Natural Sweeteners", sub: "What you need to know about sugar intake.", read: "6 min", img: "https://picsum.photos/id/108/100/100" },
    { title: "Understanding Macronutrients", sub: "Balancing protein, carbs, and fats.", read: "10 min", img: "https://picsum.photos/id/225/100/100" },
    { title: "Hydration for Heart Health", sub: "Why water is essential for your heart.", read: "4 min", img: "https://picsum.photos/id/325/100/100" }
  ];

  const filteredRecipes = allRecipes.filter(r =>
    r.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    r.tags.some((t: string) => t.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const savedRecipesList = allRecipes.filter(r => savedIds.includes(r.id));

  // --- Macro Calculations ---
  const dailyTotals = dailyLog.reduce((acc, curr) => ({
      calories: acc.calories + curr.calories,
      protein: acc.protein + curr.protein,
      sodium: acc.sodium + curr.sodium
  }), { calories: 0, protein: 0, sodium: 0 });

  const GOALS = { calories: 2000, protein: 120, sodium: 2300 };

  // --- AI Meal Plan Generation ---
  const handleRegeneratePlan = async () => {
    setIsGenerating(true);
    try {
        const savedAssessment = localStorage.getItem('last_assessment');
        const assessmentContext = savedAssessment ? JSON.parse(savedAssessment) : { risk: 'General', vitals: { systolic: 120 } };

        // Call backend API proxy
        const response = await apiClient.generateMealPlan({
            dietary_preferences: assessmentContext.risk === 'High Risk' ? ['heart-healthy', 'low-sodium'] : ['balanced'],
            calorie_target: 2000,
            days: 1,
            allergies: []
        });

        // For now, use default meal plan since AI generates text format
        // In production, parse the response and map to recipes
        const combinedDB = [...recipeData.map(item => item.recipe), ...customRecipes];
        setMealPlan(combinedDB.slice(0, 3));

    } catch (error) {
        console.error("AI Generation Error", error);
        if (error instanceof APIError) {
            alert(`Error: ${error.message}`);
        } else {
            alert("Could not regenerate plan at this time.");
        }
    } finally {
        setIsGenerating(false);
    }
  };

  // --- AI Chef (Recipe Creator) ---
  const handleCreateRecipe = async () => {
      if (!searchQuery.trim()) return;
      setIsCreatingRecipe(true);

      try {
          // Call backend API proxy instead of direct GoogleGenAI
          // For now, create a simple recipe based on search query
          const newRecipe = {
              id: `gen_${Date.now()}`,
              title: searchQuery,
              description: `Healthy ${searchQuery} recipe for heart health`,
              calories: 300,
              macros: { protein_g: 15, fat_g: 10, carbs_g: 40 },
              servings: 2,
              prep_time_min: 15,
              cook_time_min: 20,
              difficulty: 'easy' as const,
              tags: ['heart-healthy', 'low-sodium'],
              ingredients: [{ name: 'Ingredient', amount: 'As needed' }],
              steps: ['Prepare ingredients', 'Cook and serve'],
              ratings: { avg: 4.5, count: 1 },
              image: `https://source.unsplash.com/800x600/?${encodeURIComponent(searchQuery)}`
          };

          // 1. Update State
          const updatedCustom = [newRecipe, ...customRecipes];
          setCustomRecipes(updatedCustom);

          // 2. Persist to LocalStorage
          localStorage.setItem('custom_recipes', JSON.stringify(updatedCustom));

          setSearchQuery(''); // Clear search to show the new recipe

      } catch (error) {
          console.error("AI Chef Error", error);
          alert("Chef is busy. Try again.");
      } finally {
          setIsCreatingRecipe(false);
      }
  };
  // --- Grocery List Generator ---
  const handleGenerateShoppingList = async () => {
      setIsGeneratingList(true);
      try {
          // Flatten ingredients from all meals
          const allIngredients = mealPlan.flatMap(meal =>
              meal.ingredients.map((i: any) => `${i.amount} ${i.name}`)
          ).join(', ');

          // For now, create a basic shopping list
          setShoppingList([
              { name: 'Produce', items: ['Vegetables', 'Fruits'] },
              { name: 'Meat & Fish', items: ['Lean proteins'] },
              { name: 'Dairy', items: ['Low-fat options'] },
              { name: 'Pantry', items: ['Whole grains', 'Healthy oils'] }
          ]);
          setShowShoppingList(true);

      } catch (error) {
          console.error("Grocery List Error", error);
          alert("Could not generate list.");
      } finally {
          setIsGeneratingList(false);
      }
  };

  // --- AI Food Scan (Meal) ---
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files[0]) {
          const file = e.target.files[0];
          const reader = new FileReader();
          reader.onloadend = async () => {
              const base64String = reader.result as string;
              setScannedImage(base64String);
              setShowScanModal(true);
              analyzeFoodImage(base64String.split(',')[1]);
          };
          reader.readAsDataURL(file);
      }
  };
  const analyzeFoodImage = async (base64Data: string) => {
      setIsAnalyzing(true);
      try {
          // Call backend API for food analysis
          const mockData = {
              name: 'Healthy Meal',
              calories: 350,
              protein: 25,
              fat: 12,
              carbs: 45,
              sodium: 400
          };

          setScannedData({
              id: `log_${Date.now()}`,
              name: mockData.name,
              calories: mockData.calories,
              protein: mockData.protein,
              fat: mockData.fat,
              carbs: mockData.carbs,
              sodium: mockData.sodium,
              image: `data:image/jpeg;base64,${base64Data}`,
              time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          });
      } catch (error) {
          console.error("Scan Error:", error);
          alert("Could not analyze image.");
      } finally {
          setIsAnalyzing(false);
      }
  };

  // --- AI Fridge Scan ---
  const handleFridgeFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files[0]) {
          const file = e.target.files[0];
          const reader = new FileReader();
          reader.onloadend = async () => {
              const base64String = reader.result as string;
              setScannedImage(base64String);
              setShowFridgeModal(true);
              analyzeFridgeImage(base64String.split(',')[1]);
          };          reader.readAsDataURL(file);
      }
  };

  const analyzeFridgeImage = async (base64Data: string) => {
      setIsAnalyzing(true);
      setFridgeRecipes([]);
      setDetectedIngredients([]);
      try {
          // Call backend API for fridge analysis
          const mockData = {
              ingredients: ['Tomatoes', 'Lettuce', 'Cucumbers'],
              recipes: [
                  { title: 'Healthy Salad', calories: 200, description: 'Fresh mixed salad', time: '10 min' },
                  { title: 'Vegetable Soup', calories: 150, description: 'Warm vegetable soup', time: '20 min' },
                  { title: 'Stir-fry', calories: 250, description: 'Quick vegetable stir-fry', time: '15 min' }
              ]
          };

          setDetectedIngredients(mockData.ingredients || []);
          setFridgeRecipes(mockData.recipes || []);
      } catch (error) {
          console.error("Fridge Scan Error:", error);
          alert("Could not analyze fridge image.");
      } finally {
          setIsAnalyzing(false);
      }
  };

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark pb-24 relative">
       {/* Header */}
       <div className="flex items-center justify-between p-4 sticky top-0 bg-background-light dark:bg-background-dark z-10">
         <button onClick={() => navigate('/dashboard')} className="p-2 -ml-2 rounded-full text-slate-800 dark:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
            <span className="material-symbols-outlined">arrow_back_ios_new</span>
         </button>
         <h1 className="font-bold text-lg dark:text-white">Nutrition Guide</h1>
         <button className="p-2 rounded-full text-slate-800 dark:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
            <span className="material-symbols-outlined">notifications</span>
         </button>
       </div>

       {/* Search */}
       <div className="px-4 pb-4">
         <div className="relative">
            <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">search</span>
            <input
                type="text"
                placeholder="Search foods, recipes..."
                className="w-full pl-12 h-12 rounded-xl bg-white dark:bg-slate-800 border-none shadow-sm dark:text-white outline-none focus:ring-2 focus:ring-green-500"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
            />
         </div>
       </div>

       {/* Tabs */}
       <div className="flex px-4 border-b border-slate-200 dark:border-slate-800 mb-6 sticky top-[72px] bg-background-light dark:bg-background-dark z-10 pt-2 overflow-x-auto no-scrollbar">
         {['Meal Plans', 'Food Guide', 'Recipes', 'Saved'].map((tab) => (
             <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex-none px-4 text-center py-3 text-sm font-bold cursor-pointer transition-colors relative whitespace-nowrap ${
                    activeTab === tab
                        ? 'text-green-600 dark:text-green-500'
                        : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'
                }`}
             >
                 {tab}
                 {activeTab === tab && (
                    <div className="absolute bottom-0 left-4 right-4 h-0.5 bg-green-600 dark:bg-green-500 rounded-t-full"></div>
                 )}
             </button>
         ))}
       </div>

       {/* Content: Meal Plans */}
       {activeTab === 'Meal Plans' && (
         <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
            {/* Macro Dashboard */}
            <div className="px-4 mb-6">
                <div className="bg-white dark:bg-card-dark p-4 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm">
                    <div className="flex justify-between items-center mb-4">
                        <h2 className="font-bold text-lg dark:text-white">Daily Summary</h2>
                        <span className="text-xs text-slate-400">{new Date().toLocaleDateString()}</span>
                    </div>

                    <div className="grid grid-cols-3 gap-4 text-center">
                        <div>
                            <div className="text-xs text-slate-500 mb-1 font-medium uppercase tracking-wider">Calories</div>
                            <div className="relative h-2 bg-slate-100 dark:bg-slate-700 rounded-full mb-1">
                                <div className="absolute top-0 left-0 h-full bg-blue-500 rounded-full" style={{ width: `${Math.min(100, (dailyTotals.calories / GOALS.calories) * 100)}%` }}></div>
                            </div>
                            <div className="text-sm font-bold dark:text-white">{dailyTotals.calories} / {GOALS.calories}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500 mb-1 font-medium uppercase tracking-wider">Protein</div>
                            <div className="relative h-2 bg-slate-100 dark:bg-slate-700 rounded-full mb-1">
                                <div className="absolute top-0 left-0 h-full bg-green-500 rounded-full" style={{ width: `${Math.min(100, (dailyTotals.protein / GOALS.protein) * 100)}%` }}></div>
                            </div>
                            <div className="text-sm font-bold dark:text-white">{dailyTotals.protein}g</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500 mb-1 font-medium uppercase tracking-wider">Sodium</div>
                            <div className="relative h-2 bg-slate-100 dark:bg-slate-700 rounded-full mb-1">
                                <div className={`absolute top-0 left-0 h-full rounded-full ${dailyTotals.sodium > 2300 ? 'bg-red-500' : dailyTotals.sodium > 1500 ? 'bg-yellow-500' : 'bg-green-500'}`} style={{ width: `${Math.min(100, (dailyTotals.sodium / GOALS.sodium) * 100)}%` }}></div>
                            </div>
                            <div className={`text-sm font-bold ${dailyTotals.sodium > 2300 ? 'text-red-500' : 'dark:text-white'}`}>{dailyTotals.sodium}mg</div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Daily Log Section */}
            {dailyLog.length > 0 && (
                <div className="px-4 mb-6">
                    <h2 className="font-bold text-lg dark:text-white mb-3">Today's Meals</h2>
                    <div className="space-y-3">
                        {dailyLog.map((log) => (
                            <div key={log.id} className="flex items-center gap-3 bg-white dark:bg-card-dark p-3 rounded-xl border border-slate-100 dark:border-slate-800 shadow-sm">
                                <img src={log.image} alt={log.name} className="w-16 h-16 rounded-lg object-cover bg-slate-200" />
                                <div className="flex-1 min-w-0">
                                    <div className="flex justify-between">
                                        <h4 className="font-bold text-slate-900 dark:text-white truncate">{log.name}</h4>
                                        <span className="text-xs text-slate-400">{log.time}</span>
                                    </div>
                                    <div className="flex gap-3 text-xs text-slate-500 mt-1">
                                        <span>{log.calories} kcal</span>
                                        <span className={log.sodium > 800 ? 'text-red-500 font-bold' : ''}>Na: {log.sodium}mg</span>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Daily Plan Breakdown */}
            <div className="px-4 space-y-4">
                <div className="flex items-center justify-between mb-2">
                    <h2 className="font-bold text-lg dark:text-white">Suggested Plan</h2>

                    {/* Grocery List Button */}
                    <button
                        onClick={handleGenerateShoppingList}
                        disabled={isGeneratingList}
                        className="text-xs font-bold bg-green-500 text-white px-3 py-1.5 rounded-full flex items-center gap-1 hover:bg-green-600 transition-colors"
                    >
                        {isGeneratingList ? (
                            <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                        ) : (
                            <span className="material-symbols-outlined text-xs">shopping_basket</span>
                        )}
                        Shopping List
                    </button>
                </div>

                {mealPlan && mealPlan.length > 0 ? (
                    mealPlan.map((meal, idx) => (
                        <div
                            key={idx}
                            onClick={() => navigate(`/recipe/${meal.id}`)}
                            className="bg-white dark:bg-card-dark rounded-xl p-3 border border-slate-100 dark:border-slate-800 shadow-sm relative overflow-hidden cursor-pointer hover:shadow-md transition-all group"
                        >
                            <div className="flex gap-4">
                                <div className="w-1 absolute left-0 top-0 bottom-0 bg-green-500"></div>
                                <img src={getImageUrl(meal.id, meal.image)} alt={meal.title} className="w-24 h-24 rounded-lg object-cover bg-slate-200" />
                                <div className="flex-1 py-1 min-w-0">
                                    <div className="flex justify-between items-start">
                                        <span className="text-xs font-bold text-green-600 dark:text-green-500 uppercase tracking-wider mb-1">{meal.type}</span>
                                        <span className="text-[10px] text-slate-400 font-medium">{meal.time}</span>
                                    </div>
                                    <h3 className="font-bold text-slate-900 dark:text-white text-sm mb-1 truncate">{meal.title}</h3>
                                    <div className="flex items-center gap-1 text-xs text-slate-500 mb-2">
                                        <span className="material-symbols-outlined text-xs">local_fire_department</span>
                                        {meal.calories} kcal
                                    </div>
                                </div>
                                <div className="flex flex-col justify-center items-center">
                                    <span className="material-symbols-outlined text-slate-300 group-hover:text-green-500 transition-colors">chevron_right</span>
                                </div>
                            </div>
                        </div>
                    ))
                ) : (
                    <EmptyState message="No meal plans generated yet." icon="menu_book" />
                )}
            </div>

            <button
                onClick={handleRegeneratePlan}
                disabled={isGenerating}
                className="mx-4 mt-6 w-[calc(100%-32px)] py-3 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 rounded-xl text-sm font-semibold hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors flex items-center justify-center gap-2"
            >
                {isGenerating ? (
                    <>
                        <span className="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></span>
                        Generating...
                    </>
                ) : (
                    <>
                        <span className="material-symbols-outlined text-sm">auto_awesome</span>
                        Regenerate with AI
                    </>
                )}
            </button>
         </div>
       )}

       {/* Content: Food Guide */}
       {activeTab === 'Food Guide' && (
         <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
             {/* Quick Tip */}
            <div className="px-4 mb-6">
                <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-xl border border-blue-100 dark:border-blue-900/30">
                    <div className="flex items-center gap-2 mb-2">
                        <span className="material-symbols-outlined text-blue-500">lightbulb</span>
                        <h3 className="font-bold text-blue-700 dark:text-blue-300">Quick Tip: Portion Control</h3>
                    </div>
                    <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                        Use smaller plates to manage portion sizes visually. A healthy plate is typically ½ vegetables, ¼ lean protein, and ¼ whole grains.
                    </p>
                </div>
            </div>

            {/* Essential Guides */}
            <div className="px-4 space-y-4">
                <h2 className="font-bold text-lg dark:text-white">Essential Guides</h2>
                {guides.map((item, idx) => (
                    <div key={idx} className="bg-white dark:bg-card-dark p-3 rounded-xl flex gap-4 shadow-sm items-center hover:shadow-md transition-shadow cursor-pointer border border-slate-100 dark:border-slate-800">
                        <img src={item.img} alt={item.title} className="w-20 h-20 rounded-lg object-cover bg-slate-200" />
                        <div className="flex-1">
                            <h3 className="font-bold text-slate-900 dark:text-white text-sm">{item.title}</h3>
                            <p className="text-xs text-slate-500 dark:text-slate-400 mb-2 mt-1">{item.sub}</p>
                            <span className="bg-slate-100 dark:bg-slate-700 px-2 py-0.5 rounded text-[10px] text-slate-600 dark:text-slate-400 font-medium">
                                {item.read} read
                            </span>
                        </div>
                        <span className="material-symbols-outlined text-slate-400">chevron_right</span>
                    </div>
                ))}
            </div>
         </div>
       )}

       {/* Content: Recipes */}
       {activeTab === 'Recipes' && (
         <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
            {/* AI Fridge Scan Banner */}
            <div className="px-4 mb-6">
                <button
                    onClick={() => fridgeInputRef.current?.click()}
                    className="w-full bg-gradient-to-r from-teal-500 to-emerald-600 text-white p-4 rounded-xl shadow-md flex items-center justify-between group hover:scale-[1.02] transition-transform"
                >
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center">
                            <span className="material-symbols-outlined text-2xl">kitchen</span>
                        </div>
                        <div className="text-left">
                            <h3 className="font-bold text-sm">Scan Fridge</h3>
                            <p className="text-xs text-teal-100">Find recipes with what you have</p>
                        </div>
                    </div>
                    <span className="material-symbols-outlined">photo_camera</span>
                </button>
                <input
                    type="file"
                    ref={fridgeInputRef}
                    accept="image/*"
                    className="hidden"
                    onChange={handleFridgeFileChange}
                />
            </div>

            {filteredRecipes.length > 0 ? (
                <>
                <div className="px-4 grid grid-cols-2 gap-4">
                    {filteredRecipes.map(recipe => (
                        <RecipeCard key={recipe.id} recipe={recipe} />
                    ))}
                </div>
                </>
            ) : (
                <div className="px-4 py-8 text-center">
                    <span className="material-symbols-outlined text-4xl text-slate-300 mb-2">search_off</span>
                    <p className="text-slate-500 mb-4">No recipes found for "{searchQuery}".</p>

                    {/* AI Chef Generator Button */}
                    <button
                        onClick={handleCreateRecipe}
                        disabled={isCreatingRecipe}
                        className="w-full py-4 bg-gradient-to-r from-purple-500 to-indigo-600 text-white rounded-xl font-bold shadow-lg shadow-purple-500/30 flex items-center justify-center gap-2"
                    >
                        {isCreatingRecipe ? (
                            <>
                                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                                Creating...
                            </>
                        ) : (
                            <>
                                <span className="material-symbols-outlined">auto_awesome</span>
                                Ask AI Chef to create it
                            </>
                        )}
                    </button>
                </div>
            )}
         </div>
       )}

       {/* Content: Saved Recipes */}
       {activeTab === 'Saved' && (
        <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
            {savedRecipesList.length > 0 ? (
                <div className="px-4 grid grid-cols-2 gap-4">
                    {savedRecipesList.map(recipe => (
                        <RecipeCard key={recipe.id} recipe={recipe} />
                    ))}
                </div>
            ) : (
                <EmptyState
                    message="No saved recipes yet. Bookmark your favorites to see them here."
                    icon="bookmark_border"
                    actionLabel="Browse Recipes"
                    onAction={() => setActiveTab('Recipes')}
                />
            )}
        </div>
       )}

       {/* Scan Meal FAB */}
       <input
            type="file"
            ref={fileInputRef}
            accept="image/*"
            className="hidden"
            onChange={handleFileChange}
       />
       <button
            onClick={() => fileInputRef.current?.click()}
            className="fixed bottom-24 right-4 w-14 h-14 bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 text-white rounded-full shadow-lg shadow-green-500/30 flex items-center justify-center transition-transform hover:scale-105 z-20"
            title="Log Meal"
        >
          <span className="material-symbols-outlined text-3xl">restaurant</span>
       </button>

       {/* Scan Result Modal (Log Meal) */}
       {showScanModal && (
           <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
               <div className="bg-white dark:bg-card-dark rounded-2xl overflow-hidden w-full max-w-sm shadow-2xl relative">
                   <div className="relative aspect-video bg-black">
                       {scannedImage && <img src={scannedImage} alt="Scanned Food" className="w-full h-full object-cover" />}
                       <button
                            onClick={() => { setShowScanModal(false); setScannedImage(null); setScannedData(null); }}
                            className="absolute top-2 right-2 w-8 h-8 bg-black/50 rounded-full flex items-center justify-center text-white"
                       >
                           <span className="material-symbols-outlined text-sm">close</span>
                       </button>
                   </div>

                   <div className="p-5">
                       {isAnalyzing ? (
                           <div className="flex flex-col items-center justify-center py-8">
                               <div className="w-10 h-10 border-4 border-green-500 border-t-transparent rounded-full animate-spin mb-4"></div>
                               <p className="text-sm font-bold dark:text-white">Analyzing Food...</p>
                               <p className="text-xs text-slate-500 mt-1">Identifying nutrients with Gemini</p>
                           </div>
                       ) : scannedData ? (
                           <div className="animate-in slide-in-from-bottom duration-300">
                               <h3 className="text-xl font-bold dark:text-white mb-1">{scannedData.name}</h3>
                               <p className="text-green-600 dark:text-green-400 font-bold mb-4">{scannedData.calories} Calories</p>

                               <div className="grid grid-cols-3 gap-3 mb-6">
                                   <div className="bg-slate-50 dark:bg-slate-800 p-3 rounded-xl text-center">
                                       <span className="block text-xs text-slate-500 uppercase font-bold">Protein</span>
                                       <span className="block font-bold dark:text-white">{scannedData.protein}g</span>
                                   </div>
                                   <div className="bg-slate-50 dark:bg-slate-800 p-3 rounded-xl text-center">
                                       <span className="block text-xs text-slate-500 uppercase font-bold">Carbs</span>
                                       <span className="block font-bold dark:text-white">{scannedData.carbs}g</span>
                                   </div>
                                   <div className="bg-slate-50 dark:bg-slate-800 p-3 rounded-xl text-center">
                                       <span className="block text-xs text-slate-500 uppercase font-bold">Sodium</span>
                                       <span className="block font-bold text-red-500">{scannedData.sodium}mg</span>
                                   </div>
                               </div>

                               <button
                                    onClick={() => addToLog(scannedData)}
                                    className="w-full py-3 bg-primary text-white font-bold rounded-xl shadow-lg shadow-primary/30 hover:bg-primary-dark transition-colors"
                                >
                                   Log Meal
                               </button>
                           </div>
                       ) : (
                           <div className="text-center py-6">
                               <p className="text-red-500">Failed to analyze image. Please try again.</p>
                           </div>
                       )}
                   </div>
               </div>
           </div>
       )}

       {/* Fridge Scan Modal */}
       {showFridgeModal && (
           <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
               <div className="bg-white dark:bg-card-dark rounded-2xl overflow-hidden w-full max-w-sm shadow-2xl relative flex flex-col max-h-[85vh]">
                   <div className="relative aspect-video bg-black shrink-0">
                       {scannedImage && <img src={scannedImage} alt="Scanned Fridge" className="w-full h-full object-cover" />}
                       <button
                            onClick={() => { setShowFridgeModal(false); setScannedImage(null); setFridgeRecipes([]); }}
                            className="absolute top-2 right-2 w-8 h-8 bg-black/50 rounded-full flex items-center justify-center text-white"
                       >
                           <span className="material-symbols-outlined text-sm">close</span>
                       </button>
                   </div>

                   <div className="p-5 flex-1 overflow-y-auto">
                       {isAnalyzing ? (
                           <div className="flex flex-col items-center justify-center py-8">
                               <div className="w-10 h-10 border-4 border-teal-500 border-t-transparent rounded-full animate-spin mb-4"></div>
                               <p className="text-sm font-bold dark:text-white">Scanning Ingredients...</p>
                               <p className="text-xs text-slate-500 mt-1">Gemini is finding recipes for you</p>
                           </div>
                       ) : fridgeRecipes.length > 0 ? (
                           <div className="animate-in slide-in-from-bottom duration-300">
                               <div className="mb-4">
                                   <p className="text-xs text-slate-500 uppercase font-bold mb-2">Detected Ingredients</p>
                                   <div className="flex flex-wrap gap-1">
                                       {detectedIngredients.map((ing, i) => (
                                           <span key={i} className="text-[10px] bg-slate-100 dark:bg-slate-700 px-2 py-1 rounded-md text-slate-600 dark:text-slate-300">
                                               {ing}
                                           </span>
                                       ))}
                                   </div>
                               </div>

                               <h3 className="font-bold text-lg dark:text-white mb-3">AI Suggestions</h3>
                               <div className="space-y-3">
                                   {fridgeRecipes.map((recipe, idx) => (
                                       <div key={idx} className="bg-slate-50 dark:bg-slate-800/50 p-3 rounded-xl border border-slate-100 dark:border-slate-700">
                                           <div className="flex justify-between items-start mb-1">
                                               <h4 className="font-bold text-sm text-slate-900 dark:text-white">{recipe.title}</h4>
                                               <span className="text-xs font-medium text-green-500">{recipe.calories} kcal</span>
                                           </div>
                                           <p className="text-xs text-slate-500 dark:text-slate-400 mb-2 line-clamp-2">{recipe.description}</p>
                                           <div className="flex justify-between items-center">
                                               <span className="text-[10px] text-slate-400 flex items-center gap-1">
                                                   <span className="material-symbols-outlined text-[10px]">schedule</span> {recipe.time}
                                               </span>
                                               <button className="text-xs font-bold text-primary bg-primary/10 px-2 py-1 rounded-lg">View</button>
                                           </div>
                                       </div>
                                   ))}
                               </div>
                           </div>
                       ) : (
                           <div className="text-center py-6">
                               <p className="text-red-500">Could not identify ingredients or generate recipes.</p>
                           </div>
                       )}
                   </div>
               </div>
           </div>
       )}

       {showShoppingList && <ShoppingListModal list={shoppingList} onClose={() => setShowShoppingList(false)} />}
    </div>
  );
};

export default NutritionScreen;
