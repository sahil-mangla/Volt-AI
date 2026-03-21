import pandas as pd
import numpy as np
import os
import joblib
from app.config import settings
from app.utils.logger import log_error

class MLService:
    def __init__(self):
        self.model = None
        self._load_model()

    def _load_model(self):
        # Attempt to load model from path configured in env
        try:
            if os.path.exists(settings.model_path):
                self.model = joblib.load(settings.model_path)
            else:
                pass # Model will fallback to heuristics if file is missing
        except Exception as e:
            log_error("Model Load", str(e))

    def perform_feature_engineering(self, cycle_data: dict) -> dict:
        """
        Extracts summary features from raw time-series cycle data arrays.
        """
        try:
            time = np.array(cycle_data['time'])
            voltage = np.array(cycle_data['voltage'])
            current = np.array(cycle_data['current'])
            temp = np.array(cycle_data['temperature'])

            # Simple features
            v_mean = np.mean(voltage) if len(voltage) > 0 else 3.7
            t_mean = np.mean(temp) if len(temp) > 0 else 25.0
            
            # Simple capacity proxy (Coulomb counting approximation)
            capacity = 2.0
            if len(time) > 1:
                capacity = np.mean(np.abs(current)) * (time[-1] - time[0]) / 3600.0
                
            return {
                "voltage_mean": float(v_mean),
                "temperature_mean": float(t_mean),
                "capacity": float(capacity)
            }
        except Exception as e:
            log_error("Feature Engineering", str(e))
            return {"voltage_mean": 3.7, "temperature_mean": 25.0, "capacity": 2.0}

    def predict_health_and_rul(self, features: dict) -> dict:
        """
        Predicts RUL, Health, and Failure Risk based on engineered features.
        """
        try:
            cap = features.get('capacity', 2.0)
            initial_cap = 2.0 # Assume 2.0Ah nominal for calculation
            
            # SOH / Health
            soh = (cap / initial_cap) * 100.0
            health_score = max(0.0, min(100.0, soh))
            
            # Predict RUL (Heuristic or ML)
            rul = 1000.0
            if self.model:
                seq = np.array([[features['voltage_mean'], features['temperature_mean'], cap]])
                try:
                    rul_pred = self.model.predict(seq.reshape(1, -1))[0]
                    rul = float(rul_pred)
                except:
                    # ML Inference failed, fallback
                    pass
            else:
                # Heuristic baseline
                if health_score < 100:
                    rul = max(0.0, (health_score - 70) / 0.1) # Simple assumed degradation rate
            
            # Calculate failure risk (0.0 to 1.0)
            failure_risk = 0.0
            if health_score < 70:
                failure_risk = 0.95
            elif health_score < 80:
                failure_risk = 0.70
            elif health_score < 90:
                failure_risk = 0.30
                
            return {
                "health_score": round(health_score, 1),
                "rul_cycles": round(rul, 0),
                "failure_risk": round(failure_risk, 2)
            }
            
        except Exception as e:
            log_error("Prediction Logic", str(e))
            return {"health_score": 100.0, "rul_cycles": 1000.0, "failure_risk": 0.0}

ml_service = MLService()
