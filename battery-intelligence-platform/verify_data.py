
import sys
import os
import logging

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from ml_engine.data_loader import DataLoader

logging.basicConfig(level=logging.INFO)

def verify_loader():
    print("="*50)
    print("🧪 TESTING DATA LOADER WITH REAL NASA DATASET")
    print("="*50)
    
    base_path = "data/raw/cleaned_dataset"
    print(f"Loading data from: {base_path}")
    
    # Load up to 100 files to test
    df = DataLoader.load_nasa_dataset(base_path, max_files=100)
    
    if df is not None and not df.empty:
        print("\n✅ Data Loaded Successfully!")
        print(f"Total Rows: {len(df)}")
        print(f"Columns: {list(df.columns)}")
        print(f"Batteries Found: {df['battery_id'].unique()}")
        print(f"Max Cycle: {df['cycle'].max()}")
        print("\nSample Data:")
        print(df[['battery_id', 'cycle', 'voltage_measured', 'temperature_measured', 'capacity']].head())
    else:
        print("\n❌ Failed to load data.")

if __name__ == "__main__":
    verify_loader()
