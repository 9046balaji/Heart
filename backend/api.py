import os
import joblib
import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from imblearn.pipeline import Pipeline as ImbPipeline
from contextlib import asynccontextmanager
from database import init_db
from document_routes import router as document_router

# Define the input data model
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

# Global variable to store the model
model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Database
    init_db()
    
    # Load the model on startup
    global model
    model_path = os.path.join(os.path.dirname(__file__), "Models", "stacking_heart_disease_model_v3.joblib")
    try:
        model = joblib.load(model_path)
        print(f"Model loaded successfully from {model_path}")
    except Exception as e:
        print(f"Failed to load model: {e}")
        print("WARNING: Heart Disease Prediction endpoint will be unavailable.")
        model = None
    yield
    # Clean up resources if needed
    model = None

app = FastAPI(title="Heart Disease Prediction API", lifespan=lifespan)

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
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        # Convert input to DataFrame (matching the model's expected feature names)
        # Note: The feature names must match EXACTLY what the model was trained on.
        # Based on heart.py and heart_statlog_cleveland_hungary_final.csv:
        # 'age','sex','chest pain type','resting bp s','cholesterol','fasting blood sugar','resting ecg','max heart rate','exercise angina','oldpeak','ST slope'
        
        # Mapping pydantic fields to CSV column names
        data = {
            'age': [input_data.age],
            'sex': [input_data.sex],
            'chest pain type': [input_data.chest_pain_type],
            'resting bp s': [input_data.resting_bp_s],
            'cholesterol': [input_data.cholesterol],
            'fasting blood sugar': [input_data.fasting_blood_sugar],
            'resting ecg': [input_data.resting_ecg],
            'max heart rate': [input_data.max_heart_rate],
            'exercise angina': [input_data.exercise_angina],
            'oldpeak': [input_data.oldpeak],
            'ST slope': [input_data.st_slope]
        }
        
        df = pd.DataFrame(data)
        
        # Make prediction
        prediction = model.predict(df)[0]
        # Some models support predict_proba
        try:
            probability = model.predict_proba(df)[0][1] # Probability of class 1 (Disease)
        except:
            probability = float(prediction) # Fallback if probability not available

        return {
            "prediction": int(prediction),
            "probability": float(probability),
            "risk_level": "High" if probability > 0.5 else "Low",
            "message": "High risk of heart disease detected." if prediction == 1 else "Low risk of heart disease."
        }

    except Exception as e:
        print(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)
