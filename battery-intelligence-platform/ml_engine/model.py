
import pandas as pd
import numpy as np
import pickle
import logging
import os
from typing import Dict, Any, Optional
from .features import FeatureEngineer

logger = logging.getLogger(__name__)

class BatteryPredictor:
    """
    Production-ready wrapper for the Battery RUL Prediction Model.
    Designed to be swapped with an XGBoost/LSTM model in the future.
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.lstm = None
        self.model_type = "Heuristic"
        
        # Try Loading LSTM
        try:
            from .lstm_model import LSTMRegressor
            lstm_path = os.path.join(os.path.dirname(__file__), 'lstm_model.h5')
            if os.path.exists(lstm_path):
                self.lstm = LSTMRegressor(sequence_length=30, n_features=3)
                if self.lstm.load(lstm_path):
                    self.model_type = "LSTM (Deep Learning)"
                    logger.info("LSTM Model Loaded Successfully!")
        except Exception as e:
            logger.warning(f"Could not load LSTM model: {e}")

    def predict(self, df_cycle_raw: pd.DataFrame) -> Dict[str, Any]:
        """
        Ingests raw cycle data for a single battery and returns prediction.
        """
        try:
            # 1. Feature Engineering
            df_features = FeatureEngineer.compute_cycle_features(df_cycle_raw)
            if df_features.empty:
                return {"error": "No features extraction possible"}
            
            # Get latest cycle data
            latest = df_features.iloc[-1]
            
            # 2. Heuristic Prediction (Baseline)
            rul = latest.get('rul', -1)
            health = latest.get('health_score', 100)
            soh = latest.get('soh', 100)
            
            # 3. LSTM Prediction Override
            if self.lstm:
                cols = ['voltage_mean', 'temperature_mean', 'capacity']
                hist_len = len(df_features)
                if hist_len >= 30:
                    try:
                        # Extract sequence
                        seq = df_features[cols].iloc[-30:].values
                        predicted_rul = self.lstm.predict(seq)
                        rul = float(predicted_rul)
                        logger.info(f"LSTM Predicted RUL: {rul}")
                    except Exception as e:
                        logger.error(f"LSTM Prediction Error: {e}")

            # 4. Criticality Logic
            if health < 70 or rul < 20:
                is_critical = True
                status = "CRITICAL"
                recommendation = "Schedule immediate replacement."
            elif health < 85 or rul < 50:
                is_critical = False
                status = "WARNING"
                recommendation = "Plan maintenance check within 30 days."
            else:
                is_critical = False
                status = "HEALTHY"
                recommendation = "Normal operation."
                
            return {
                "battery_id": latest['battery_id'],
                "cycle": int(latest['cycle']),
                "health_score": float(health),
                "rul_cycles": float(rul),
                "soh": float(soh),
                "status": status,
                "is_critical": is_critical,
                "recommendation": recommendation,
                "prediction_model": self.model_type
            }
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return {"error": str(e)}

    def predict_batch(self, df_features: pd.DataFrame) -> Dict[str, float]:
        """
        Batch predicts RUL for all batteries in the features DataFrame using LSTM.
        Returns: {battery_id: rul_val}
        """
        results = {}
        if not self.lstm:
            return results
            
        cols = ['voltage_mean', 'temperature_mean', 'capacity']
        
        for bid in df_features['battery_id'].unique():
            batt_df = df_features[df_features['battery_id'] == bid].sort_values('cycle')
            if len(batt_df) >= 30:
                try:
                    seq = batt_df[cols].iloc[-30:].values
                    pred = self.lstm.predict(seq)
                    results[bid] = float(pred)
                    # Cap prediction for sanity
                    if results[bid] < 0: results[bid] = 0
                except Exception as e:
                    logger.warning(f"Batch predict failed for {bid}: {e}")
                    
        return results

    def save_model(self, path: str):
        # pickle self if needed, or just config
        with open(path, 'wb') as f:
            pickle.dump(self, f)

    def load_model(self, path: str):
        with open(path, 'rb') as f:
            self = pickle.load(f)
