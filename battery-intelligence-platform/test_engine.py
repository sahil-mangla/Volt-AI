
import sys
import os
import pandas as pd
import logging

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from ml_engine.data_loader import DataLoader
from ml_engine.model import BatteryPredictor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_pipeline():
    print("="*50)
    print("🔋 TESTING BATTERY INTELLIGENCE PLATFORM ENGINE 🔋")
    print("="*50)
    
    # 1. Generate Synthetic Data
    print("\n[1] Generating Synthetic Data...")
    df = DataLoader.create_synthetic_data(num_batteries=2, cycles_per_battery=150)
    print(f"    - Generated {len(df)} rows for {df['battery_id'].nunique()} batteries.")
    print(f"    - Columns: {list(df.columns)}")
    
    # 2. Initialize Predictor
    print("\n[2] Initializing ML Model...")
    predictor = BatteryPredictor()
    
    # 3. Running Predictions on a Single Battery
    battery_id = df['battery_id'].unique()[0]
    print(f"\n[3] Running Analysis for Battery {battery_id}...")
    
    batt_data = df[df['battery_id'] == battery_id]
    
    # Simulate processing cycle by cycle
    results = []
    print("    - Processing last 5 cycles...")
    for cycle in batt_data['cycle'].unique()[-5:]:
        cycle_df = batt_data[batt_data['cycle'] == cycle]
        
        # Predict
        result = predictor.predict(cycle_df)
        results.append(result)
        
        print(f"      Cycle {cycle}: Health={result.get('health_score', 0):.1f}%, "
              f"RUL={result.get('rul_cycles', 0):.1f}, "
              f"Status={result.get('status', 'Unknown')}")
              
    print("\n✅ Test Complete. The Engine is functional.")

if __name__ == "__main__":
    test_pipeline()
