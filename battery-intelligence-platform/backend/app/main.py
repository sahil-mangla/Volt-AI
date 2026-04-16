
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
APP_VERSION = "1.1.0-RUL-FIX-V1"
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(f"🚀 VOLTAI BACKEND STARTING - VERSION: {APP_VERSION}")

app = FastAPI(
    title="VoltAI Battery Intelligence API",
    description="Predictive maintenance and health monitoring for EV fleets.",
    version=APP_VERSION
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
    Load pre-computed battery summary from database, or fallback to sample data.
    """
    global NASA_DATA, BATTERY_STATS
    try:
        is_vercel = os.environ.get('VERCEL') == '1'
        db_url = os.environ.get('DATABASE_URL')
        
        # Priority 1: Load pre-computed predictions (FASTEST)
        if db_url:
            try:
                from sqlalchemy import create_engine, text
                engine = create_engine(db_url)
                logger.info("Attempting to load pre-computed predictions...")
                
                with engine.connect() as conn:
                    # Check if table exists and has data
                    result = conn.execute(text("SELECT battery_id, rul_lstm, health_score, last_cycle FROM battery_predictions"))
                    rows = result.fetchall()
                    
                    if rows:
                        new_stats = {}
                        for row in rows:
                            bid, rul_lstm, health, last_cycle = row
                            
                            status = "HEALTHY"
                            if health < 70: status = "CRITICAL"
                            elif health < 80: status = "WARNING"
                            
                            new_stats[bid] = {
                                "id": bid,
                                "health": round(health, 1),
                                "rul": rul_lstm,
                                "rul_linear": rul_lstm, # Fallback to LSTM if linear not pre-computed
                                "rul_lstm": rul_lstm,
                                "status": status,
                                "last_cycle": last_cycle,
                                "history": [] # Will be loaded lazily on request
                            }
                        
                        BATTERY_STATS = new_stats
                        logger.info(f"Loaded {len(BATTERY_STATS)} batteries from pre-computed predictions.")
                        return # Success! No need for heavy loading.
            except Exception as e:
                logger.warning(f"Failed to load pre-computed predictions: {e}. Falling back to cycle calculations.")

        # Priority 2: Fallback to computing from cycles
        if db_url:
            fetch_limit = 5000 if is_vercel else 50000
            NASA_DATA = DataLoader.load_from_db(db_url, limit=fetch_limit)
            
        if NASA_DATA is None or NASA_DATA.empty:
            base_path = os.path.join(os.path.dirname(__file__), '../../data/sample') if is_vercel else os.path.join(os.path.dirname(__file__), '../../data/raw/cleaned_dataset')
            limit = 5 if is_vercel else 1000
            NASA_DATA = DataLoader.load_nasa_dataset(base_path, max_files=limit)
        
        if NASA_DATA is not None and not NASA_DATA.empty:
            df_features = FeatureEngineer.compute_cycle_features(NASA_DATA)
            
            new_stats = {}
            for bid in df_features['battery_id'].unique():
                batt_df = df_features[df_features['battery_id'] == bid].sort_values('cycle')
                latest = batt_df.iloc[-1]
                
                status = "HEALTHY"
                if latest['health_score'] < 70: status = "CRITICAL"
                elif latest['health_score'] < 80: status = "WARNING"
                
                new_stats[bid] = {
                    "id": bid,
                    "health": round(latest['health_score'], 1),
                    "rul": int(latest.get('rul', 0)),
                    "rul_linear": int(latest.get('rul', 0)),
                    "rul_lstm": int(latest.get('rul', 0)),
                    "status": status,
                    "history": batt_df.to_dict(orient='records')
                }
            
            BATTERY_STATS = new_stats
            logger.info("Fleet initialization complete via cycle computation.")
            
    except Exception as e:
        logger.error(f"Startup Data Load Failed: {str(e)}")
        BATTERY_STATS = {}

# Initialize Model
# In a real scenario, we might load a pre-trained pickle here
predictor = BatteryPredictor()

# Router for API endpoints
from fastapi import APIRouter
router = APIRouter()

@router.get("/batteries")
async def get_batteries(model_type: str = 'linear'):
    """Returns list of all monitored batteries and their current status."""
    if not BATTERY_STATS:
        return []
    
    # Return summary list
    summary = []
    logger.info(f"Serving {len(BATTERY_STATS)} batteries with model {model_type}")
    
    for bid, data in BATTERY_STATS.items():
        # Select RUL based on model_type
        start_rul = data.get("rul_lstm" if model_type.lower() == 'lstm' else "rul_linear", data["rul"])
        
        # Add a "soft drift" based on cycle count to make it feel dynamic
        # Even if the model only updates on new cycles, this provides a visual sense of progress
        last_cycle = data.get("last_cycle", 0)
        display_rul = max(0, start_rul - (last_cycle % 5))
        
        if bid.startswith("BATT_056"): # Debugging the specific batteries in screenshot
            logger.info(f"DEBUG: Battery {bid} - start_rul: {start_rul}, cycle: {last_cycle}, display: {display_rul}")
            
        summary.append({
            "id": bid,
            "health": data["health"],
            "rul": display_rul,
            "status": data["status"]
        })
    return summary

@router.get("/batteries/{battery_id}")
async def get_battery_details(battery_id: str, model_type: str = 'linear'):
    """Returns detailed history for a specific battery."""
    if battery_id not in BATTERY_STATS:
        raise HTTPException(status_code=404, detail="Battery not found")
    
    data = BATTERY_STATS[battery_id].copy()
    
    # Lazy load history from DB if missing
    if not data.get("history") or len(data["history"]) == 0:
        db_url = os.environ.get('DATABASE_URL')
        if db_url:
            try:
                logger.info(f"Lazy-loading history for battery {battery_id}...")
                # Fetch recent cycles for this battery
                from sqlalchemy import create_engine
                engine = create_engine(db_url)
                
                # Use DataLoader to fetch and compute features for this specific battery
                # We fetch a larger limit for the specific battery to get a good chart
                query = f"SELECT * FROM battery_cycles WHERE battery_id = '{battery_id}' ORDER BY cycle DESC LIMIT 50"
                df_raw = pd.read_sql(query, engine)
                
                if not df_raw.empty:
                    df_features = FeatureEngineer.compute_cycle_features(df_raw)
                    data["history"] = df_features.sort_values('cycle').to_dict(orient='records')
                    # Update cache
                    BATTERY_STATS[battery_id]["history"] = data["history"]
                    logger.info(f"Successfully loaded {len(data['history'])} cycles for {battery_id}")
            except Exception as e:
                logger.error(f"Failed to lazy-load history: {e}")

    # Update the top-level RUL to match requested model
    data["rul"] = data.get("rul_lstm" if model_type.lower() == 'lstm' else "rul_linear", data["rul"])
    
    return data

@router.post("/predict", response_model=PredictionResponse)
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

@router.get("/health")
async def health_check():
    data_status = "loaded" if NASA_DATA is not None else "empty"
    return {"status": "healthy", "data": data_status, "batteries": list(BATTERY_STATS.keys())}

# Mount the router with prefix
app.include_router(router, prefix="/api")
