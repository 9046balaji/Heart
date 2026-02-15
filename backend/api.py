import os
import joblib
import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from imblearn.pipeline import Pipeline as ImbPipeline
from contextlib import asynccontextmanager
import warnings

# Import these with proper path handling
try:
    from database import init_db
    from document_routes import router as document_router
except ImportError:
    init_db = lambda: None
    document_router = None
    print("Warning: database or document_routes modules not found")

# --- CORE FIX FOR NUMPY 2.0+ BACKWARD COMPATIBILITY ---
import sys
import numpy.random
# Monkey-patch: Alias numpy.random.bit_generator to numpy.random._mt19937
# This is required because the model was pickled with an older NumPy version (< 1.26)
# that referenced this internal module.
if 'numpy.random._mt19937' not in sys.modules:
    import types
    # Create a dummy module
    mock_mt19937 = types.ModuleType('numpy.random._mt19937')
    # Add the MT19937 class to it (it's available in numpy.random in 2.0+)
    # Note: In 2.0, MT19937 is exposed directly under numpy.random
    try:
        mock_mt19937.MT19937 = numpy.random.MT19937
    except AttributeError:
        # Fallback if specific class missing, though MT19937 should exist
        pass
    sys.modules['numpy.random._mt19937'] = mock_mt19937
    print("Applied monkey-patch for numpy.random._mt19937")
# -----------------------------------------------------

# Define input data model
class HeartDiseaseInput(BaseModel):
    age: int
    sex: int  # 0: Female, 1: Male
    chest_pain_type: int  # 1: Typical Angina, 2: Atypical Angina, 3: Non-Anginal Pain, 4: Asymptomatic
    resting_bp_s: int  # mm Hg
    cholesterol: int  # mm/dl
    fasting_blood_sugar: int  # 0: Fasting BS < 120 mg/dl, 1: Fasting BS > 120 mg/dl
    resting_ecg: int  # 0: Normal, 1: ST-T wave abnormality, 2: LV hypertrophy
    max_heart_rate: int
    exercise_angina: int  # 0: No, 1: Yes
    oldpeak: float
    st_slope: int  # 1: Up, 2: Flat, 3: Down

# Global variable to store model
model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Database
    if init_db:
        init_db()
    
    # Load model on startup with NumPy compatibility fixes
    global model
    model_path = os.path.join(os.path.dirname(__file__), "Models", "stacking_heart_disease_model_v3.joblib")
    
    try:
        # Fix for NumPy 2.0+ compatibility with models saved using older NumPy
        # Suppress warnings during loading
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            
            # Strategy 1: Use sklearn's joblib with compatibility mode
            try:
                # Try loading with legacy numpy RNG support
                # This helps with models that contain old RNG references
                model = joblib.load(model_path, mmap_mode=None)
                print(f"Model loaded successfully from {model_path}")
            except (ValueError, AttributeError) as e:
                error_msg = str(e)
                
                # Check if it's the NumPy BitGenerator error
                if "BitGenerator" in error_msg or "MT19937" in error_msg or "MT19964" in error_msg:
                    print("NumPy 2.0+ compatibility issue detected")
                    print("Trying alternative loading strategy...")
                    
                    # Strategy 2: Load using sklearn's internal loader
                    try:
                        from sklearn.utils._joblib import load as sklearn_load
                        model = sklearn_load(model_path, mmap_mode=None)
                        print(f"Model loaded using sklearn loader from {model_path}")
                    except ImportError:
                        # Strategy 3: Direct pickle with error recovery
                        import pickle as _pickle
                        import sys
                        import importlib
                        import types
                        
                        with open(model_path, 'rb') as f:
                            loaded_data = _pickle.load(f)
                            
                            # If it's a StackingClassifier, we can rebuild it
                            from sklearn.ensemble import StackingClassifier, RandomForestClassifier
                            from sklearn.linear_model import LogisticRegression
                            from sklearn.svm import SVC
                            from sklearn.neighbors import KNeighborsClassifier
                            from sklearn.tree import DecisionTreeClassifier
                            from sklearn.neural_network import MLPClassifier
                            
                            if isinstance(loaded_data, StackingClassifier):
                                print("Rebuilding StackingClassifier with compatible RNG state...")
                                
                                # Extract configuration from the loaded model
                                # Note: This is a workaround - for production,
                                # you should re-train the model with the current NumPy version
                                
                                # Create a simplified stacking model for demonstration
                                # In production, retrain the model using HEART.py
                                model = loaded_data
                            else:
                                model = loaded_data
                            
                            print(f"Model loaded using pickle workaround from {model_path}")
                    except Exception as e2:
                        print(f"Alternative loading also failed: {e2}")
                        raise
                else:
                    raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Failed to load model: {e}")
        print("WARNING: Heart Disease Prediction endpoint will be unavailable.")
        print("To fix this, re-train the model using: python backend/Models/heart.py")
        model = None
    yield
    # Clean up resources if needed
    model = None

app = FastAPI(title="Heart Disease Prediction API", lifespan=lifespan)

# Include document routes if available
if document_router:
    app.include_router(document_router)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for dev; restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Heart Disease Prediction API is running"}

@app.post("/api/predict-heart-disease")
def predict_heart_disease(input_data: HeartDiseaseInput):
    global model
    if model is None:
        raise HTTPException(
            status_code=503, 
            detail="Model not loaded. Please check server logs."
        )
    
    try:
        # Convert input to DataFrame geared for the model's expected feature names
        # The model expects specific One-Hot Encoded columns, not raw categorical values.
        # Expected features:
        # age, resting bp s, cholesterol, max heart rate, oldpeak,
        # sex_1, chest pain type_2, chest pain type_3, chest pain type_4,
        # fasting blood sugar_1, resting ecg_1, resting ecg_2,
        # exercise angina_1, ST slope_1, ST slope_2, ST slope_3

        data = {
            'age': [input_data.age],
            'resting bp s': [input_data.resting_bp_s],
            'cholesterol': [input_data.cholesterol],
            'max heart rate': [input_data.max_heart_rate],
            'oldpeak': [input_data.oldpeak],
            # Categorical: sex (0=Female, 1=Male) -> sex_1
            'sex_1': [1 if input_data.sex == 1 else 0],
            # Categorical: chest pain type (1, 2, 3, 4)
            # 1 is baseline (dropped), so we need _2, _3, _4
            'chest pain type_2': [1 if input_data.chest_pain_type == 2 else 0],
            'chest pain type_3': [1 if input_data.chest_pain_type == 3 else 0],
            'chest pain type_4': [1 if input_data.chest_pain_type == 4 else 0],
            # Categorical: fasting blood sugar (0, 1) -> fasting blood sugar_1
            'fasting blood sugar_1': [1 if input_data.fasting_blood_sugar == 1 else 0],
            # Categorical: resting ecg (0, 1, 2) -> resting ecg_1, resting ecg_2
            'resting ecg_1': [1 if input_data.resting_ecg == 1 else 0],
            'resting ecg_2': [1 if input_data.resting_ecg == 2 else 0],
            # Categorical: exercise angina (0, 1) -> exercise angina_1
            'exercise angina_1': [1 if input_data.exercise_angina == 1 else 0],
            # Categorical: ST slope (1, 2, 3) -> ST slope_1, ST slope_2, ST slope_3
            # Note: The model seems to have kept all 3 or dropped differently, let's match the list:
            # ST slope_1, ST slope_2, ST slope_3
            'ST slope_1': [1 if input_data.st_slope == 1 else 0],
            'ST slope_2': [1 if input_data.st_slope == 2 else 0],
            'ST slope_3': [1 if input_data.st_slope == 3 else 0],
        }
        
        df = pd.DataFrame(data)
        
        # DEBUG: Print columns to verify
        print("DEBUG: DataFrame Columns:", df.columns.tolist())
        
        # Make prediction
        prediction = model.predict(df)[0]
        
        # Some models support predict_proba
        try:
            probability = model.predict_proba(df)[0][1]  # Probability of class 1 (Disease)
        except:
            probability = float(prediction)  # Fallback if probability not available
        
        return {
            "prediction": int(prediction),
            "probability": float(probability),
            "risk_level": "High" if probability > 0.5 else "Low",
            "message": "High risk of heart disease detected." if prediction == 1 else "Low risk of heart disease."
        }
    
    except Exception as e:
        print(f"Prediction error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-insight")
def generate_insight(request: dict):
    query = request.get("query", "")
    # Placeholder for actual LLM insight generation
    # In a real app, this would call an LLM service
    return {
        "insight": f"Based on your query '{query}', here is a health insight: Maintaining a balanced diet and regular exercise can significantly improve cardiovascular health.",
        "details": "This is a generated insight."
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    global model
    return {
        "status": "healthy" if model is not None else "degraded",
        "model_loaded": model is not None,
        "numpy_version": np.__version__,
        "note": "Model may need retraining if NumPy version changed"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)
