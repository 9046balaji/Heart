import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient, APIError } from '../services/apiClient';
import { Medication } from '../types';

const MedicationScreen: React.FC = () => {
  const navigate = useNavigate();
  const [medications, setMedications] = useState<Medication[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [analysisResult, setAnalysisResult] = useState<string | null>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Form State
  const [newMed, setNewMed] = useState({
    name: '',
    dosage: '',
    frequency: 'Daily',
    time: '08:00',
    instructions: '',
    quantity: '30' // Default quantity
  });

  const USER_ID = 'demo_user_123'; 

  useEffect(() => {
    fetchMedications();
  }, []);

  // Sync state to local storage whenever it changes to support Chat RAG context
  useEffect(() => {
    if (medications.length > 0) {
        localStorage.setItem('user_medications', JSON.stringify(medications));
    }
  }, [medications]);

  const fetchMedications = async () => {
    setIsLoading(true);
    // Simulate async load
    await new Promise(resolve => setTimeout(resolve, 300));
    
    const saved = localStorage.getItem('user_medications');
    if (saved) {
      setMedications(JSON.parse(saved));
    }
    setIsLoading(false);
  };

  const handleAddMedication = async () => {
    if (!newMed.name || !newMed.dosage) return;
    
    const medData: Medication = {
      id: `med_${Date.now()}`,
      name: newMed.name,
      dosage: newMed.dosage,
      frequency: newMed.frequency,
      times: [newMed.time],
      takenToday: [false],
      instructions: newMed.instructions,
      quantity: parseInt(newMed.quantity) || 30,
      // userId not needed for local type but kept for structure consistency if needed
    } as any; // Cast to avoid strict type check on extra fields

    setMedications(prev => [...prev, medData]);
    setShowAddModal(false);
    setNewMed({ name: '', dosage: '', frequency: 'Daily', time: '08:00', instructions: '', quantity: '30' });
  };

  const toggleTaken = async (medId: string, timeIndex: number) => {
    const medIndex = medications.findIndex(m => m.id === medId);
    if (medIndex === -1) return;

    const med = medications[medIndex];
    const isTaking = !med.takenToday[timeIndex]; 
    const newTaken = [...med.takenToday];
    newTaken[timeIndex] = isTaking;
    
    let newQuantity = med.quantity || 0;
    if (isTaking && newQuantity > 0) newQuantity -= 1;
    else if (!isTaking) newQuantity += 1;

    const updatedMeds = [...medications];
    updatedMeds[medIndex] = { ...med, takenToday: newTaken, quantity: newQuantity };
    setMedications(updatedMeds);
  };

  const checkInteractions = async () => {
    if (medications.length < 2) {
        setAnalysisResult("Add at least two medications to check for interactions.");
        return;
    }

    setIsAnalyzing(true);
    setAnalysisResult(null);

    try {
        // Call backend API proxy
        const medList = medications.map(m => `${m.name} ${m.dosage}`).join(', ');
        
        const response = await apiClient.medicationInsights({
            medications: medications.map(m => ({ name: m.name, dosage: m.dosage })),
            supplements: [],
            recent_vitals: {}
        });

        setAnalysisResult(response.insights || "No interactions found.");

    } catch (error) {
        console.error("API Error:", error);
        if (error instanceof APIError) {
            setAnalysisResult(`Error: ${error.message}`);
        } else {
            setAnalysisResult("Failed to analyze interactions. Please try again.");
        }
    } finally {
        setIsAnalyzing(false);
    }
  };

  const deleteMed = async (id: string) => {
      if (confirm("Are you sure you want to delete this medication?")) {
        const newMeds = medications.filter(m => m.id !== id);
        setMedications(newMeds);
        // Force update local storage if array becomes empty (useEffect might skip empty array based on existing logic, so we do it manually here just in case)
        if (newMeds.length === 0) {
            localStorage.setItem('user_medications', JSON.stringify([]));
        }
      }
  };

  // --- AI Label Scanner Logic ---
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files[0]) {
          const file = e.target.files[0];
          const reader = new FileReader();
          reader.onloadend = async () => {
              const base64String = reader.result as string;
              scanLabel(base64String.split(',')[1]);
          };
          reader.readAsDataURL(file);
      }
  };

  const scanLabel = async (base64Data: string) => {
      setIsScanning(true);
      try {
          // For now, create a simple mock medication
          const mockMed: Medication = {
              id: `med_${Date.now()}`,
              name: 'Medication',
              dosage: '10mg',
              quantity: 30,
              frequency: 'Once daily',
              times: [],
              takenToday: []
          };

          const newMeds = [mockMed, ...medications];
          setMedications(newMeds);
          localStorage.setItem('user_medications', JSON.stringify(newMeds));

      } catch (error) {
          console.error("Scan Error:", error);
          alert("Could not read label. Please try again.");
      } finally {
          setIsScanning(false);
      }
  };

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark pb-24 relative">
      {/* Header */}
      <div className="flex items-center p-4 bg-white dark:bg-card-dark sticky top-0 z-10 border-b border-slate-100 dark:border-slate-800 shadow-sm">
        <button onClick={() => navigate('/dashboard')} className="p-2 -ml-2 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-900 dark:text-white transition-colors">
          <span className="material-symbols-outlined">arrow_back</span>
        </button>
        <h2 className="flex-1 text-center font-bold text-lg dark:text-white">Medicine Cabinet</h2>
        <div className="w-10"></div>
      </div>

      <div className="p-4 space-y-6">
        {/* Interaction Checker Card */}
        <div className="bg-gradient-to-r from-blue-600 to-indigo-600 rounded-2xl p-5 text-white shadow-lg">
            <div className="flex items-start gap-4">
                <div className="w-12 h-12 bg-white/20 rounded-full flex items-center justify-center shrink-0">
                    <span className="material-symbols-outlined text-2xl">medical_services</span>
                </div>
                <div className="flex-1">
                    <h3 className="font-bold text-lg">Safety Check</h3>
                    <p className="text-blue-100 text-sm mb-4">Use AI to scan your medication list for potential interactions.</p>
                    <button 
                        onClick={checkInteractions}
                        disabled={isAnalyzing}
                        className="bg-white text-blue-700 px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 hover:bg-blue-50 transition-colors disabled:opacity-70"
                    >
                        {isAnalyzing ? (
                            <>
                                <span className="w-3 h-3 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></span>
                                Analyzing...
                            </>
                        ) : (
                            <>
                                <span className="material-symbols-outlined text-sm">check_circle</span>
                                Check Interactions
                            </>
                        )}
                    </button>
                </div>
            </div>
            
            {analysisResult && (
                <div className="mt-4 bg-white/10 p-3 rounded-xl border border-white/20 animate-in fade-in slide-in-from-top-2">
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">{analysisResult}</p>
                </div>
            )}
        </div>

        {/* Medication List */}
        <div>
            <div className="flex justify-between items-center mb-4">
                <div className="flex items-center gap-2">
                    <h3 className="font-bold text-lg dark:text-white">Your Medications</h3>
                    {isLoading && <span className="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></span>}
                </div>
                <span className="text-xs text-slate-500">{medications.length} active</span>
            </div>

            {!isLoading && medications.length > 0 ? (
                <div className="space-y-3">
                    {medications.sort((a, b) => a.times[0].localeCompare(b.times[0])).map((med) => (
                        <div key={med.id} className="bg-white dark:bg-card-dark p-4 rounded-xl border border-slate-100 dark:border-slate-800 shadow-sm relative group">
                            <button 
                                onClick={() => deleteMed(med.id)}
                                className="absolute top-2 right-2 text-slate-300 hover:text-red-500 p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                                <span className="material-symbols-outlined text-sm">delete</span>
                            </button>
                            <div className="flex items-start gap-4">
                                <div className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 ${
                                    parseInt(med.times[0]) < 12 ? 'bg-orange-100 text-orange-600 dark:bg-orange-900/30 dark:text-orange-400' :
                                    parseInt(med.times[0]) < 18 ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400' :
                                    'bg-indigo-100 text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-400'
                                }`}>
                                    <span className="material-symbols-outlined">pill</span>
                                </div>
                                <div className="flex-1">
                                    <h4 className="font-bold text-slate-900 dark:text-white text-lg">{med.name}</h4>
                                    <div className="flex justify-between items-start">
                                        <div>
                                            <p className="text-sm text-slate-500 dark:text-slate-400">{med.dosage} • {med.frequency}</p>
                                            <p className="text-xs text-slate-400 mt-1 italic">{med.instructions || "No special instructions"}</p>
                                        </div>
                                        <div className="text-right">
                                            <span className={`text-xs font-bold px-2 py-1 rounded-full ${
                                                (med.quantity || 0) < 5 ? 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400' : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
                                            }`}>
                                                {(med.quantity || 0) < 5 ? 'Refill Needed' : `${med.quantity} left`}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex gap-2 overflow-x-auto">
                                {med.times.map((time, idx) => (
                                    <button
                                        key={idx}
                                        onClick={() => toggleTaken(med.id, idx)}
                                        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                                            med.takenToday[idx] 
                                            ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' 
                                            : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
                                        }`}
                                    >
                                        <span className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                                            med.takenToday[idx] ? 'border-green-600 bg-green-600 text-white' : 'border-slate-400'
                                        }`}>
                                            {med.takenToday[idx] && <span className="material-symbols-outlined text-[10px]">check</span>}
                                        </span>
                                        {time}
                                    </button>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            ) : !isLoading && (
                <div className="text-center py-10 bg-slate-50 dark:bg-slate-800/50 rounded-xl border-dashed border-2 border-slate-200 dark:border-slate-700">
                    <span className="material-symbols-outlined text-4xl text-slate-300 mb-2">medication</span>
                    <p className="text-slate-500 font-medium">Cabinet is empty</p>
                    <p className="text-slate-400 text-sm">Add your prescriptions to track them.</p>
                </div>
            )}
        </div>
      </div>

      {/* FAB */}
      <button 
        onClick={() => setShowAddModal(true)}
        className="fixed bottom-6 right-6 w-14 h-14 bg-primary hover:bg-primary-dark text-white rounded-full shadow-lg shadow-primary/30 flex items-center justify-center transition-transform hover:scale-105 z-20"
      >
        <span className="material-symbols-outlined text-3xl">add</span>
      </button>

      {/* Add Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200" onClick={() => setShowAddModal(false)}>
            <div className="bg-white dark:bg-card-dark rounded-2xl p-6 w-full max-w-sm shadow-2xl" onClick={e => e.stopPropagation()}>
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-xl font-bold dark:text-white">Add Medication</h3>
                    <button onClick={() => setShowAddModal(false)}><span className="material-symbols-outlined text-slate-400">close</span></button>
                </div>

                {/* AI Scan Button */}
                <div className="mb-4">
                    <button 
                        onClick={() => fileInputRef.current?.click()}
                        disabled={isScanning}
                        className="w-full py-3 bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400 rounded-xl border border-indigo-200 dark:border-indigo-800 border-dashed flex items-center justify-center gap-2 hover:bg-indigo-100 dark:hover:bg-indigo-900/30 transition-colors"
                    >
                        {isScanning ? (
                            <>
                                <span className="w-4 h-4 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin"></span>
                                Scanning Label...
                            </>
                        ) : (
                            <>
                                <span className="material-symbols-outlined">document_scanner</span>
                                Scan Pill Bottle
                            </>
                        )}
                    </button>
                    <input 
                        type="file" 
                        ref={fileInputRef} 
                        accept="image/*" 
                        className="hidden" 
                        onChange={handleFileChange} 
                    />
                </div>

                <div className="space-y-4">
                    <div>
                        <label className="text-xs font-bold text-slate-500 uppercase">Medication Name</label>
                        <input 
                            type="text" 
                            className="w-full mt-1 p-3 rounded-xl bg-slate-100 dark:bg-slate-800 border-none outline-none dark:text-white focus:ring-2 focus:ring-primary"
                            placeholder="e.g. Metoprolol"
                            value={newMed.name}
                            onChange={e => setNewMed({...newMed, name: e.target.value})}
                        />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="text-xs font-bold text-slate-500 uppercase">Dosage</label>
                            <input 
                                type="text" 
                                className="w-full mt-1 p-3 rounded-xl bg-slate-100 dark:bg-slate-800 border-none outline-none dark:text-white focus:ring-2 focus:ring-primary"
                                placeholder="e.g. 50mg"
                                value={newMed.dosage}
                                onChange={e => setNewMed({...newMed, dosage: e.target.value})}
                            />
                        </div>
                        <div>
                            <label className="text-xs font-bold text-slate-500 uppercase">Qty (Pills)</label>
                            <input 
                                type="number" 
                                className="w-full mt-1 p-3 rounded-xl bg-slate-100 dark:bg-slate-800 border-none outline-none dark:text-white focus:ring-2 focus:ring-primary"
                                placeholder="30"
                                value={newMed.quantity}
                                onChange={e => setNewMed({...newMed, quantity: e.target.value})}
                            />
                        </div>
                    </div>
                    <div>
                        <label className="text-xs font-bold text-slate-500 uppercase">Time</label>
                        <input 
                            type="time" 
                            className="w-full mt-1 p-3 rounded-xl bg-slate-100 dark:bg-slate-800 border-none outline-none dark:text-white focus:ring-2 focus:ring-primary"
                            value={newMed.time}
                            onChange={e => setNewMed({...newMed, time: e.target.value})}
                        />
                    </div>
                    <div>
                        <label className="text-xs font-bold text-slate-500 uppercase">Instructions (Optional)</label>
                        <input 
                            type="text" 
                            className="w-full mt-1 p-3 rounded-xl bg-slate-100 dark:bg-slate-800 border-none outline-none dark:text-white focus:ring-2 focus:ring-primary"
                            placeholder="e.g. Take with food"
                            value={newMed.instructions}
                            onChange={e => setNewMed({...newMed, instructions: e.target.value})}
                        />
                    </div>
                </div>
                <div className="flex gap-3 mt-6">
                    <button onClick={() => setShowAddModal(false)} className="flex-1 py-3 text-slate-500 font-bold hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors">Cancel</button>
                    <button onClick={handleAddMedication} className="flex-1 py-3 bg-primary text-white font-bold rounded-xl shadow-lg shadow-primary/30">Save</button>
                </div>
            </div>
        </div>
      )}
    </div>
  );
};

export default MedicationScreen;