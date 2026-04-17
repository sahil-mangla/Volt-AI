
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

async def ensure_data_loaded():
    """
    Ensures BATTERY_STATS is populated. Uses lazy loading for serverless environments.
    """
    global NASA_DATA, BATTERY_STATS
    
    # If already loaded, return
    if BATTERY_STATS:
        return

    logger.info("📡 Lazy-loading fleet data...")
    try:
        is_vercel = os.environ.get('VERCEL') == '1'
        db_url = os.environ.get('DATABASE_URL')
        
        # Priority 1: Load pre-computed predictions (FASTEST)
        if db_url:
            try:
                from sqlalchemy import create_engine, text
                engine = create_engine(db_url)
                
                with engine.connect() as conn:
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
                                "rul_linear": rul_lstm,
                                "rul_lstm": rul_lstm,
                                "status": status,
                                "last_cycle": last_cycle,
                                "history": [] 
                            }
                        
                        BATTERY_STATS = new_stats
                        logger.info(f"✅ Loaded {len(BATTERY_STATS)} batteries from pre-computed predictions.")
                        return 
            except Exception as e:
                logger.warning(f"Failed to load pre-computed predictions: {e}. Falling back to cycle calculations.")

        # Priority 2: Fallback to computing from cycles
        if db_url:
            fetch_limit = 10000 if is_vercel else 50000
            NASA_DATA = DataLoader.load_from_db(db_url, limit=fetch_limit)
            
        if NASA_DATA is None or NASA_DATA.empty:
            base_path = os.path.join(os.path.dirname(__file__), '../../data/sample') if is_vercel else os.path.join(os.path.dirname(__file__), '../../data/raw/cleaned_dataset')
            limit = 10 if is_vercel else 1000
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
                    "last_cycle": int(latest['cycle']),
                    "history": batt_df.to_dict(orient='records')
                }
            
            BATTERY_STATS = new_stats
            logger.info("✅ Fleet initialization complete via cycle computation.")
            
    except Exception as e:
        logger.error(f"❌ Lazy Load Failed: {str(e)}")
        if not BATTERY_STATS: BATTERY_STATS = {}

@app.on_event("startup")
async def startup_event():
    # Still attempt loading on startup for non-serverless environments
    await ensure_data_loaded()

# Initialize Model
predictor = BatteryPredictor()

# Router for API endpoints
from fastapi import APIRouter
router = APIRouter()

@router.get("/batteries")
async def get_batteries(model_type: str = 'linear'):
    """Returns list of all monitored batteries and their current status."""
    await ensure_data_loaded()
    if not BATTERY_STATS:
        return []
    
    # Return summary list
    summary = []
    logger.info(f"Serving {len(BATTERY_STATS)} batteries with model {model_type}")
    
    for bid, data in BATTERY_STATS.items():
        # Select RUL based on model_type
        # We ensure we pick the specific field from our seeded DB
        rul_val = data.get("rul_lstm" if model_type.lower() == 'lstm' else "rul_linear", data["rul"])
        
        # Consistent drift calculation
        last_cycle = data.get("last_cycle", 0)
        display_rul = max(0, int(rul_val) - (last_cycle % 3))
        
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
    await ensure_data_loaded()
    if battery_id not in BATTERY_STATS:
        raise HTTPException(status_code=404, detail="Battery not found")
    
    data = BATTERY_STATS[battery_id].copy()
    
    # Update the top-level RUL to match requested model
    rul_val = data.get("rul_lstm" if model_type.lower() == 'lstm' else "rul_linear", data["rul"])
    last_cycle = data.get("last_cycle", 0)
    data["rul"] = max(0, int(rul_val) - (last_cycle % 3))
    
    # Load history from battery_features table (PRE-COMPUTED AGGREGATES)
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        try:
            logger.info(f"Fetching history from battery_features for {battery_id}...")
            from sqlalchemy import create_engine
            engine = create_engine(db_url)
            
            # Fetch last 20 cycles for this battery
            query = f"SELECT cycle, capacity_ah, avg_temperature as temperature, capacity_fade as health_score FROM battery_features WHERE battery_id = '{battery_id}' ORDER BY cycle ASC"
            df_hist = pd.read_sql(query, engine)
            
            if not df_hist.empty:
                # Map columns if necessary for frontend components
                # health_score here is normalized to 0-100 for the UI
                df_hist['health_score'] = df_hist['health_score'].apply(lambda x: max(0, min(100, 100 - (x * 20)))) 
                
                # Mock RUL trend for the graph to match the current prediction
                df_hist['rul'] = df_hist['cycle'].apply(lambda c: max(0, data["rul"] + (last_cycle - c)))
                
                data["history"] = df_hist.to_dict(orient='records')
                logger.info(f"Successfully loaded {len(data['history'])} history points.")
        except Exception as e:
            logger.error(f"Failed to load history from features table: {e}")

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
