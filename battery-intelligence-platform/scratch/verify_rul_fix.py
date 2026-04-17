
import sys
import os
import pandas as pd
import numpy as np

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from ml_engine.features import FeatureEngineer

def verify_rul():
    print("🧪 Verifying RUL Fix...")
    
    # Create fake data for a healthy battery at cycle 50
    data = {
        'battery_id': ['B0005'] * 60,
        'cycle': list(range(1, 61)),
        'health_score': [100 - (i * 0.01) for i in range(60)], # Very slow degradation
        'voltage_measured': [4.0] * 60,
        'temperature_measured': [25.0] * 60,
        'capacity': [2.0] * 60
    }
    df = pd.DataFrame(data)
    
    # Compute RUL
    df_result = FeatureEngineer._calculate_derivatives(df)
    
    latest_rul = df_result.iloc[-1]['rul']
    print(f"Latest Battery Health: {df_result.iloc[-1]['health_score']}%")
    print(f"Latest Cycle: {df_result.iloc[-1]['cycle']}")
    print(f"Computed RUL: {latest_rul}")
    
    # Check if it's still 1000
    if latest_rul == 1000:
        print("❌ FAILED: RUL is still stuck at 1000")
    elif latest_rul < 800:
        print(f"✅ SUCCESS: RUL is {latest_rul} (Expected around 800 - 60 = 740)")
    else:
        print(f"❓ UNKNOWN: RUL is {latest_rul}")

if __name__ == "__main__":
    verify_rul()
