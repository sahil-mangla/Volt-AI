
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import joblib
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LSTMRegressor:
    """
    Wrapper for RandomForest (acting as a robust ML model when Tensorflow is unavailable).
    Implements same interface as the LSTM class.
    """
    
    def __init__(self, sequence_length=30, n_features=3):
        self.sequence_length = sequence_length
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.scaler = StandardScaler()
        
    def train(self, X, y, epochs=None, batch_size=None):
        """
        X shape: (n_samples, sequence_length, n_features) -> flatten to (n_samples, seq_len*n_features)
        """
        # Flatten sequence input for RF
        n_samples = X.shape[0]
        X_flat = X.reshape(n_samples, -1)
        
        logger.info(f"Training RandomForest (Fallback) on {n_samples} samples...")
        self.model.fit(X_flat, y)
        
    def predict(self, sequence):
        """
        Input shape: (1, sequence_length, n_features)
        """
        if sequence.ndim == 2:
            sequence = sequence.reshape(1, *sequence.shape)
            
        X_flat = sequence.reshape(1, -1)
        return self.model.predict(X_flat)[0]
        
    def save(self, path):
        # Save both model and config
        joblib.dump(self.model, path)
        logger.info(f"Model saved to {path}")
        
    def load(self, path):
        if os.path.exists(path):
            try:
                self.model = joblib.load(path)
                logger.info(f"Model loaded from {path}")
                return True
            except:
                logger.error(f"Failed to load sklearn model from {path}")
                return False
        return False
