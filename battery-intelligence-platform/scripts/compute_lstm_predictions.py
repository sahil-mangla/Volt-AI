"""
Compute LSTM predictions for all batteries and store in database.
This script should be run locally or via cron to update predictions periodically.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import logging

from ml_engine.data_loader import DataLoader
from ml_engine.features import FeatureEngineer
from ml_engine.model import BatteryPredictor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def compute_and_store_predictions():
    """
    Load data from database, compute LSTM predictions, and store results.
    """
    
    # Load environment variables
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        logger.error("DATABASE_URL not found in environment variables")
        sys.exit(1)
    
    try:
        # Connect to database
        engine = create_engine(database_url)
        logger.info("📊 Loading battery data from database...")
        
        # Load data
        df = DataLoader.load_from_db(database_url)
        
        if df is None or df.empty:
            logger.error("❌ No data found in database")
            sys.exit(1)
        
        logger.info(f"✅ Loaded {len(df)} rows")
        
        # Compute features
        logger.info("🔧 Computing features...")
        df_features = FeatureEngineer.compute_cycle_features(df)
        
        # Initialize predictor
        logger.info("🤖 Initializing LSTM predictor...")
        predictor = BatteryPredictor()
        
        # Compute predictions
        logger.info("🧮 Computing LSTM predictions...")
        lstm_predictions = predictor.predict_batch(df_features)
        
        # Prepare data for insertion
        predictions_data = []
        for battery_id in df_features['battery_id'].unique():
            batt_df = df_features[df_features['battery_id'] == battery_id].sort_values('cycle')
            latest = batt_df.iloc[-1]
            
            rul_lstm = int(lstm_predictions.get(battery_id, 0))
            
            predictions_data.append({
                'battery_id': battery_id,
                'rul_lstm': rul_lstm,
                'health_score': float(latest['health_score']),
                'last_cycle': int(latest['cycle'])
            })
        
        # Store in database
        logger.info(f"💾 Storing predictions for {len(predictions_data)} batteries...")
        
        with engine.connect() as conn:
            # Clear old predictions
            conn.execute(text("DELETE FROM battery_predictions"))
            
            # Insert new predictions
            for pred in predictions_data:
                insert_sql = """
                INSERT INTO battery_predictions (battery_id, rul_lstm, health_score, last_cycle)
                VALUES (:battery_id, :rul_lstm, :health_score, :last_cycle)
                """
                conn.execute(text(insert_sql), pred)
            
            conn.commit()
        
        logger.info("✅ Successfully stored predictions in database!")
        logger.info(f"📈 Predictions computed for: {[p['battery_id'] for p in predictions_data]}")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    compute_and_store_predictions()
