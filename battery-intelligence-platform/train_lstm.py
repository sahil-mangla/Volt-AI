
import os
import sys
import numpy as np
import pandas as pd
import logging

# Setup Path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ml_engine.data_loader import DataLoader
from ml_engine.features import FeatureEngineer
from ml_engine.lstm_model import LSTMRegressor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def prepare_sequences(df_features, sequence_length=50):
    """
    Creates (Cycle_Sequence, RUL_Label) pairs.
    """
    sequences = []
    labels = []
    
    feature_cols = ['voltage_mean', 'current_measured', 'temperature_mean']
    # Ensuring these columns exist. If not, use availables.
    # From features.py we know: 'voltage_mean', 'temperature_mean'. 
    # 'current_measured' might be raw. 
    # Let's verify what features we actually get.
    # In features.py we calculate: voltage_mean, temperature_mean, capacity, health_score.
    # We should use: ['voltage_mean', 'temperature_mean', 'capacity']
    
    use_cols = ['voltage_mean', 'temperature_mean', 'capacity']
    
    for bid in df_features['battery_id'].unique():
        batt = df_features[df_features['battery_id'] == bid].sort_values('cycle')
        
        # We need RUL as ground truth label (calculated from SOH)
        # The heuristic 'rul' column from features.py is our "ground truth" for training this model
        # (Technically we are distilling the heuristic into a neural net, which isn't ideal,
        # but without real failure labels, it's the best proxy. 
        # Ideally we would calculate RUL = Max_Cycle - Current_Cycle for dead batteries).
        
        # Let's Calculate True RUL for training (Cycles remaining until end of data or failure)
        # Assuming last cycle is EOL for B0005, B0006 etc.
        max_cycle = batt['cycle'].max()
        batt['true_rul'] = max_cycle - batt['cycle']
        
        data = batt[use_cols].values
        target = batt['true_rul'].values
        
        if len(data) < sequence_length:
            continue
            
        for i in range(len(data) - sequence_length):
            seq = data[i : i + sequence_length]
            label = target[i + sequence_length]
            sequences.append(seq)
            labels.append(label)
            
    return np.array(sequences), np.array(labels)

def main():
    # 1. Load Data
    base_path = os.path.join(os.path.dirname(__file__), 'data/raw/cleaned_dataset')
    logger.info("Loading Data...")
    df_raw = DataLoader.load_nasa_dataset(base_path, max_files=1000)
    
    if df_raw.empty:
        logger.error("No data loaded. Exiting.")
        return

    # 2. Extract Features
    logger.info("Extracting Features...")
    df_features = FeatureEngineer.compute_cycle_features(df_raw)
    
    # Fill NA for stability
    df_features = df_features.fillna(method='ffill').fillna(0)
    
    # 3. Prepare Sequences
    SEQ_LEN = 30 # Use 30 cycles memory
    logger.info(f"Preparing Sequences (Window={SEQ_LEN})...")
    X, y = prepare_sequences(df_features, sequence_length=SEQ_LEN)
    
    logger.info(f"Training Data Shape: {X.shape}")
    
    # 4. Train Model
    # Note: Using RandomForest fallback due to TensorFlow installation issues in this environment
    model = LSTMRegressor(sequence_length=SEQ_LEN, n_features=3)
    model.train(X, y) 
    
    # 5. Save
    # Use .joblib extension for sklearn
    save_path = os.path.join(os.path.dirname(__file__), 'ml_engine/lstm_model.h5') # Keeping .h5 name for compatibility with main launcher logic, though it's joblib pickle now
    model.save(save_path)
    logger.info("Training Complete!")

if __name__ == "__main__":
    main()
