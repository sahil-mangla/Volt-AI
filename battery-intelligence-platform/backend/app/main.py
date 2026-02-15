
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import logging
import sys
import os
from typing import List, Dict, Any

# Add project root to sys.path to import ml_engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from ml_engine.model import BatteryPredictor
from ml_engine.data_loader import DataLoader
from ml_engine.features import FeatureEngineer
from .schemas import CycleData, PredictionResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="VoltAI Battery Intelligence API",
    description="Predictive maintenance and health monitoring for EV fleets.",
    version="1.0.0"
)

# CORS (Allow frontend to connect)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Data Store
NASA_DATA = None
BATTERY_STATS = {}

@app.on_event("startup")
async def load_data():
    """
    Load NASA dataset on startup to simulate fleet data.
    """
    global NASA_DATA, BATTERY_STATS
    try:
        base_path = os.path.join(os.path.dirname(__file__), '../../data/raw/cleaned_dataset')
        # Check if running on Vercel (or other limited env)
        is_vercel = os.environ.get('VERCEL') == '1'
        limit = 10 if is_vercel else 1000
        
        logger.info(f"Loading NASA Metadata from: {base_path} (Limit: {limit})")
        
        # Load up to limit files
        NASA_DATA = DataLoader.load_nasa_dataset(base_path, max_files=limit)
        
        if NASA_DATA is not None and not NASA_DATA.empty:
            logger.info(f"Loaded {len(NASA_DATA)} rows of cycle data.")
            
            # Pre-compute features for fast API response
            logger.info("Pre-computing fleet statistics...")
            df_features = FeatureEngineer.compute_cycle_features(NASA_DATA)
            
            # Pre-compute LSTM predictions for fleet
            logger.info("Running LSTM Inference on fleet...")
            lstm_ruls = predictor.predict_batch(df_features)
            
            # Group by battery
            for bid in df_features['battery_id'].unique():
                batt_df = df_features[df_features['battery_id'] == bid].sort_values('cycle')
                
                # Get latest status
                latest = batt_df.iloc[-1]
                
                # RULs
                rul_linear = int(latest.get('rul', 0))
                rul_lstm = int(lstm_ruls.get(bid, rul_linear)) # Fallback to linear if no LSTM pred
                
                # Determine status based on LINEAR (standard) or allow override?
                # Let's stick to Health Score for status to be consistent.
                status = "HEALTHY"
                if latest['health_score'] < 70: status = "CRITICAL"
                elif latest['health_score'] < 80: status = "WARNING"
                
                BATTERY_STATS[bid] = {
                    "id": bid,
                    "health": round(latest['health_score'], 1),
                    "rul": rul_linear, # Default/Legacy
                    "rul_linear": rul_linear,
                    "rul_lstm": rul_lstm,
                    "status": status,
                    "history": batt_df.to_dict(orient='records')
                }
            logger.info(f"Fleet initialization complete for: {list(BATTERY_STATS.keys())}")
        else:
            logger.warning("No data loaded. Check data path.")
            
    except Exception as e:
        logger.error(f"Startup Data Load Failed: {e}")

# Initialize Model
# In a real scenario, we might load a pre-trained pickle here
predictor = BatteryPredictor()

@app.get("/")
async def root():
    return {"message": "VoltAI API is running. use /docs for API documentation."}

@app.get("/batteries")
async def get_batteries(model_type: str = 'linear'):
    """Returns list of all monitored batteries and their current status."""
    if not BATTERY_STATS:
        return []
    
    # Return summary list
    summary = []
    for bid, data in BATTERY_STATS.items():
        # Select RUL based on model_type
        start_rul = data.get("rul_lstm" if model_type.lower() == 'lstm' else "rul_linear", data["rul"])
        
        summary.append({
            "id": bid,
            "health": data["health"],
            "rul": start_rul,
            "status": data["status"]
        })
    return summary

@app.get("/batteries/{battery_id}")
async def get_battery_details(battery_id: str, model_type: str = 'linear'):
    """Returns detailed history for a specific battery."""
    if battery_id not in BATTERY_STATS:
        raise HTTPException(status_code=404, detail="Battery not found")
    
    data = BATTERY_STATS[battery_id].copy()
    
    # Update the top-level RUL to match requested model
    data["rul"] = data.get("rul_lstm" if model_type.lower() == 'lstm' else "rul_linear", data["rul"])
    
    # Note: We are NOT updating the history array RULs because that would require 
    # re-predicting history for every single point which is expensive.
    # The graph usually plots 'health_score', so RUL history isn't critical visually.
    
    return data

@app.post("/predict", response_model=PredictionResponse)
async def predict_battery_health(data: CycleData):
    """
    Analyzes a single charge/discharge cycle and returns health metrics + RUL.
    """
    try:
        # Convert Pydantic model to DataFrame
        # The ML engine expects a DataFrame with columns matching the CSVs
        # We need to map the input data (which might be clean/JSON) to that format.
        
        # Create a DataFrame for the cycle
        df = pd.DataFrame({
            "battery_id": [data.battery_id] * len(data.time),
            "cycle": [data.cycle_id] * len(data.time),
            "time": data.time,
            "voltage_measured": data.voltage,
            "current_measured": data.current,
            "temperature_measured": data.temperature
        })
        
        # Run Prediction
        # Note: The predictor expects a DataFrame that can compute features.
        result = predictor.predict(df)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
            
        return result
        
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    data_status = "loaded" if NASA_DATA is not None else "empty"
    return {"status": "healthy", "data": data_status, "batteries": list(BATTERY_STATS.keys())}
