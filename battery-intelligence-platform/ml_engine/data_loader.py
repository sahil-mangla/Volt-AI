
import pandas as pd
import numpy as np
import os
import glob
import re
from typing import List, Optional, Dict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataLoader:
    """
    Handles loading of NASA Battery Dataset or generation of synthetic data.
    """
    
    @staticmethod
    def load_nasa_dataset(base_path: str, max_files: int = 50) -> Optional[pd.DataFrame]:
        """
        Load CSV files from the NASA dataset directory structure using metadata.csv.
        
        Args:
            base_path: Path to the directory containing metadata.csv and the 'data' subdirectory.
            max_files: Maximum number of CSV files to load (to prevent memory issues during dev).
        """
        all_data = []
        try:
            metadata_path = os.path.join(base_path, "metadata.csv")
            if not os.path.exists(metadata_path):
                logger.warning(f"metadata.csv not found in {base_path}")
                return None

            # Load Metadata
            meta = pd.read_csv(metadata_path)
            
            # Filter for discharge cycles only (most relevant for degradation)
            # You can expand this to 'charge' or 'impedance' if needed.
            discharge_meta = meta[meta['type'] == 'discharge'].copy()
            
            # Sort by time to ensure cycles are in order
            # The 'start_time' is a string array, simplistically sorting by 'uid' usually works for order
            discharge_meta = discharge_meta.sort_values(by=['battery_id', 'uid'])
            
            # Limit grouping to specific batteries if desired, or load all until max_files
            batteries_to_load = discharge_meta['battery_id'].unique()
            files_loaded = 0
            
            logger.info(f"Found {len(discharge_meta)} discharge cycles for batteries: {batteries_to_load}")

            for battery_id in batteries_to_load:
                if files_loaded >= max_files:
                    break
                    
                batt_cycles = discharge_meta[discharge_meta['battery_id'] == battery_id]
                
                # Calculate cycle number based on order for this battery
                for cycle_num, (index, row) in enumerate(batt_cycles.iterrows(), start=1):
                    if files_loaded >= max_files:
                        break

                    filename = row['filename']
                    file_path = os.path.join(base_path, "data", filename)
                    
                    try:
                        df = pd.read_csv(file_path)
                        
                        # Standardize columns
                        df = DataLoader._standardize_columns(df)
                        
                        # Add metadata
                        df['battery_id'] = battery_id
                        df['cycle'] = cycle_num
                        df['filename'] = filename
                        
                        # Handle Capacity from metadata
                        try:
                            cap = float(row['Capacity']) if 'Capacity' in row and pd.notna(row['Capacity']) else np.nan
                        except:
                            cap = np.nan
                        df['capacity'] = cap
                        
                        all_data.append(df)
                        files_loaded += 1
                        
                    except Exception as e:
                        logger.error(f"Error loading {file_path}: {e}")
                        continue
            
            if all_data:
                logger.info(f"Successfully loaded {len(all_data)} cycles.")
                return pd.concat(all_data, ignore_index=True)
            return None

        except Exception as e:
            logger.error(f"Critical error in load_nasa_dataset: {e}")
            return None

    @staticmethod
    def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """
        Maps various column names to standard internal names.
        """
        column_mapping = {}
        for col in df.columns:
            col_lower = str(col).strip().lower()
            if 'voltage' in col_lower and 'load' not in col_lower:
                column_mapping[col] = 'voltage_measured'
            elif 'current' in col_lower and 'load' not in col_lower:
                column_mapping[col] = 'current_measured'
            elif 'temperature' in col_lower:
                column_mapping[col] = 'temperature_measured'
            elif 'current' in col_lower and 'load' in col_lower:
                column_mapping[col] = 'current_load'
            elif 'voltage' in col_lower and 'load' in col_lower:
                column_mapping[col] = 'voltage_load'
            elif 'time' in col_lower:
                column_mapping[col] = 'time'
        
        if column_mapping:
            df = df.rename(columns=column_mapping)
        
        # Ensure critical columns exist and are numeric
        expected_cols = ['voltage_measured', 'current_measured', 'temperature_measured', 'time', 'capacity']
        for col in expected_cols:
            if col not in df.columns:
                df[col] = np.nan
            else:
                # Force conversion to numeric, turning errors/strings into NaN
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        return df
        
    @staticmethod
    def load_from_db(connection_string: str, limit: Optional[int] = None) -> Optional[pd.DataFrame]:
        """
        Loads battery cycle data from the database.
        """
        try:
            from sqlalchemy import create_engine
            engine = create_engine(connection_string)
            
            query = "SELECT * FROM battery_cycles ORDER BY battery_id, cycle"
            if limit:
                query += f" LIMIT {limit}"
                
            logger.info(f"Fetching data from database (Limit: {limit})...")
            
            df = pd.read_sql(query, engine)
            
            if not df.empty:
                logger.info(f"Successfully loaded {len(df)} rows from DB.")
                return df
                
            return None
        except Exception as e:
            logger.error(f"Error loading from DB: {e}")
            return None

    @staticmethod
    def create_synthetic_data(num_batteries=4, cycles_per_battery=100) -> pd.DataFrame:
        """
        Generates synthetic battery data for testing/demo purposes.
        """
        np.random.seed(42)
        battery_ids = [f'B00{i:02d}' for i in range(5, 5+num_batteries)]
        all_cycles = []

        for battery_id in battery_ids:
            # Randomize degradation parameters per battery
            initial_capacity = np.random.uniform(1.8, 2.0)
            degradation_rate = np.random.uniform(0.003, 0.005)
            
            for cycle in range(1, cycles_per_battery + 1):
                n_samples = 100
                time = np.linspace(0, 100, n_samples)
                
                # Capacity Fade
                capacity = initial_capacity * np.exp(-degradation_rate * cycle)
                
                # Voltage & Current Profiles
                voltage = 3.7 + np.random.normal(0, 0.1, n_samples)
                current = 1.5 + np.random.normal(0, 0.2, n_samples)
                temp = 25 + (cycle * 0.05) + np.random.normal(0, 1, n_samples)
                
                df_cycle = pd.DataFrame({
                    'time': time,
                    'voltage_measured': voltage,
                    'current_measured': current,
                    'temperature_measured': temp,
                    'capacity': capacity, # Ground truth capacity for training
                    'battery_id': battery_id,
                    'cycle': cycle
                })
                all_cycles.append(df_cycle)
        
        return pd.concat(all_cycles, ignore_index=True)
