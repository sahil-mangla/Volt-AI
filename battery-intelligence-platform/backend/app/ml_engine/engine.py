import numpy as np
from app.utils.logger import log_error

class ModelEngine:
    def __init__(self):
        self.available_models = [
            "physics_model",
            "linear_regression_model",
            "xgboost_model",
            "lstm_model"
        ]

    def predict(self, features: dict, model_name: str = "physics_model") -> dict:
        """
        Runs the specified model on the extracted features.
        Returns: health_score, failure_probability, remaining_cycles, remaining_days
        """
        if model_name not in self.available_models:
            model_name = "physics_model"
            
        try:
            return getattr(self, f"_{model_name}_inference")(features)
        except Exception as e:
            log_error(f"Inference Engine failed for {model_name}", str(e))
            return self._physics_model_inference(features)

    def _physics_model_inference(self, features: dict) -> dict:
        # Baseline degradation equation
        cap_fade = features.get('capacity_fade', 0.0)
        ir = features.get('internal_resistance', 0.05)
        
        health_score = max(0.0, min(100.0, 100.0 - (cap_fade * 50.0)))
        rul = max(0.0, 1000.0 * (health_score / 100.0))
        fail_prob = max(0.0, 1.0 - (health_score / 100.0))
        
        return {
            "health_score": round(health_score, 2),
            "failure_probability": round(fail_prob, 3),
            "remaining_cycles": round(rul, 2),
            "remaining_days": round(rul * 0.5, 2) # Assume 2 cycles per day
        }

    def _linear_regression_model_inference(self, features: dict) -> dict:
        v_var = features.get('voltage_variance', 0.0)
        t_var = features.get('temperature_variance', 0.0)
        cap_fade = features.get('capacity_fade', 0.0)
        
        health_score = max(0.0, min(100.0, 100.0 - (cap_fade * 45.0) - (v_var * 5.0) - (t_var * 2.0)))
        rul = max(0.0, 950.0 * (health_score / 100.0))
        fail_prob = max(0.0, 1.0 - (health_score / 100.0) + 0.05)
        
        return {
            "health_score": round(health_score, 2),
            "failure_probability": round(min(1.0, fail_prob), 3),
            "remaining_cycles": round(rul, 2),
            "remaining_days": round(rul * 0.55, 2) 
        }

    def _xgboost_model_inference(self, features: dict) -> dict:
        # Non-linear heuristic representing tree splits
        avg_temp = features.get('avg_temperature', 25.0)
        cap_fade = features.get('capacity_fade', 0.0)

        health_score = 100.0
        if avg_temp > 35:
            health_score -= 15
        elif avg_temp > 30:
            health_score -= 5
            
        if cap_fade > 0.2:
            health_score -= 20
        else:
            health_score -= cap_fade * 50
            
        health_score = max(0.0, health_score)
        rul = max(0.0, 1000.0 * (health_score / 100.0))
        fail_prob = 1.0 if health_score < 60 else max(0.0, 1.0 - (health_score / 100.0))

        return {
            "health_score": round(health_score, 2),
            "failure_probability": round(min(1.0, fail_prob), 3),
            "remaining_cycles": round(rul, 2),
            "remaining_days": round(rul * 0.48, 2)
        }

    def _lstm_model_inference(self, features: dict) -> dict:
        # Sequence heuristic based on cycle count trend estimation
        cycle = features.get('cycle_count', 1)
        cap_fade = features.get('capacity_fade', 0.0)
        # Logarithmic decay approximation
        decay = np.log1p(cycle) * 2.0 + (cap_fade * 30.0)
        
        health_score = max(0.0, min(100.0, 100.0 - decay))
        rul = max(0.0, 1100.0 * (health_score / 100.0)) # LSTM predicts slightly longer life
        fail_prob = max(0.0, 1.0 - (health_score / 100.0))
        if cycle > 500:
            fail_prob += 0.1
            
        return {
            "health_score": round(health_score, 2),
            "failure_probability": round(min(1.0, fail_prob), 3),
            "remaining_cycles": round(rul, 2),
            "remaining_days": round(rul * 0.5, 2)
        }

model_engine = ModelEngine()
