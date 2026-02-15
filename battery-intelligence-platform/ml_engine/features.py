
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

class FeatureEngineer:
    """
    Transforms raw time-series cycle data into cycle-level features.
    """
    
    @staticmethod
    def compute_cycle_features(df_raw: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregates raw sensor data into per-cycle statistics.
        Input: Raw DataFrame with ['battery_id', 'cycle', 'voltage_measured', 'current_measured', 'temperature_measured']
        Output: DataFrame with one row per (battery_id, cycle) containing features like 'voltage_mean', 'capacity', etc.
        """
        features_list = []
        
        # Group by battery_id
        for battery_id in df_raw['battery_id'].unique():
            battery_data = df_raw[df_raw['battery_id'] == battery_id]
            
            # Process each cycle
            for cycle in battery_data['cycle'].unique():
                cycle_data = battery_data[battery_data['cycle'] == cycle]
                
                if len(cycle_data) < 10:
                    continue
                
                stats = {
                    'battery_id': battery_id,
                    'cycle': cycle,
                    'data_points': len(cycle_data)
                }
                
                # 1. Voltage Features
                if 'voltage_measured' in cycle_data.columns:
                    stats.update({
                        'voltage_mean': cycle_data['voltage_measured'].mean(),
                        'voltage_min': cycle_data['voltage_measured'].min(),
                        'voltage_max': cycle_data['voltage_measured'].max(),
                        'voltage_std': cycle_data['voltage_measured'].std()
                    })
                
                # 2. Temperature Features
                if 'temperature_measured' in cycle_data.columns:
                    stats.update({
                        'temperature_mean': cycle_data['temperature_measured'].mean(),
                        'temperature_max': cycle_data['temperature_measured'].max(),
                        'temperature_std': cycle_data['temperature_measured'].std()
                    })
                
                # 3. Capacity (Integration of Current over Time)
                # If ground truth capacity is provided in synthetic data, use it.
                # Otherwise, calculate it.
                if 'capacity' in cycle_data.columns:
                    stats['capacity'] = cycle_data['capacity'].mean()
                elif 'current_measured' in cycle_data.columns and 'time' in cycle_data.columns:
                    # Simple Coulomb Counting
                    try:
                        time_diff = np.diff(cycle_data['time'])
                        current_avg = (cycle_data['current_measured'].values[:-1] + cycle_data['current_measured'].values[1:]) / 2
                        # Ah = Sum(AvgCurrent * TimeDiff) / 3600
                        # capacity = np.sum(np.abs(current_avg) * time_diff) / 3600
                        # Note: Simple robust estimation for now
                        stats['capacity'] = np.abs(cycle_data['current_measured']).mean() * (cycle_data['time'].max() - cycle_data['time'].min()) / 3600
                    except:
                        stats['capacity'] = np.nan

                features_list.append(stats)
        
        df_features = pd.DataFrame(features_list)
        if df_features.empty:
            logger.warning("Feature engineering resulted in empty DataFrame")
            return df_features

        # Post-Processing: Calculate Derivatives (SOH, Fade Rate)
        df_final = FeatureEngineer._calculate_derivatives(df_features)
        
        return df_final

    @staticmethod
    def _calculate_derivatives(df: pd.DataFrame) -> pd.DataFrame:
        """
        Adds SOH, Health Score, and RUL estimates based on historical trends.
        """
        df = df.sort_values(['battery_id', 'cycle'])
        
        processed_batteries = []
        for battery_id in df['battery_id'].unique():
            batt_df = df[df['battery_id'] == battery_id].copy()
            
            # SOH (State of Health)
            initial_capacity = 2.0 # Default nominal
            if 'capacity' in batt_df.columns:
                # Robust Baseline: Look at first 10 cycles, filter out noise/partial cycles (< 0.5 Ah)
                # Use the MAX (assuming specific capacity) or Median to avoid low outliers.
                early_cycles = batt_df['capacity'].iloc[:10]
                valid_cycles = early_cycles[early_cycles > 0.5]
                
                if not valid_cycles.empty:
                    initial_capacity = valid_cycles.max()
                elif not early_cycles.empty:
                     initial_capacity = early_cycles.max() # Fallback if all are low
                
                if initial_capacity > 0:
                    batt_df['soh'] = (batt_df['capacity'] / initial_capacity) * 100
                else:
                    batt_df['soh'] = 100
            
            # Clamp SOH for display logic (prevent 164% or millions)
            batt_df['soh'] = batt_df['soh'].clip(upper=110)

            # Health Score (Composite)
            # Simplified for robustness:
            soh_score = batt_df.get('soh', pd.Series([100]*len(batt_df))).fillna(100)
            batt_df['health_score'] = soh_score  # Baseline
            
            # RUL (Remaining Useful Life) - Linear Extrapolation
            # Find when SOH hits 70%
            # Use rolling trend
            batt_df['rul'] = FeatureEngineer._estimate_rul(batt_df)
            
            processed_batteries.append(batt_df)
            
        return pd.concat(processed_batteries)

    @staticmethod
    def _estimate_rul(df_battery: pd.DataFrame) -> pd.Series:
        """
        Estimates RUL for a single battery history dataframe.
        """
        rul_series = []
        # Simple heuristic: If SOH drops 0.1% per cycle, and we are at 90%, 
        # we have (90-70)/0.1 = 200 cycles left.
        
        for i in range(len(df_battery)):
            current_cycle = df_battery['cycle'].iloc[i]
            current_soh = df_battery['health_score'].iloc[i]
            
            if i < 10:
                rul_series.append(1000) # Placeholder for start
                continue
                
            # Calulcate degradation rate over last 20 cycles (increased from 10 to smooth out noise)
            recent_window = 20
            if i < recent_window:
                rul_series.append(1000)
                continue

            recent_df = df_battery.iloc[max(0, i-recent_window):i+1]
            try:
                # fit linear regression: soh = m * cycle + c
                coeffs = np.polyfit(recent_df['cycle'], recent_df['health_score'], 1)
                slope = coeffs[0]
                
                # If slope is negative, standard calc
                if slope < -0.001: # Significant degradation
                    cycles_remaining = (current_soh - 70) / abs(slope)
                    rul_series.append(int(min(2000, max(0, cycles_remaining))))
                
                # If slope is positive/flat BUT battery is already dying (SOH < 80%), 
                # do NOT say 1000. Panic and say "Unknown/Low" or assume worst case.
                elif current_soh < 80:
                    # Fallback: Assume average degradation rate of 0.5% per cycle if unclear
                    cycles_remaining = (current_soh - 70) / 0.5
                    rul_series.append(int(max(0, cycles_remaining)))
                
                else:
                    rul_series.append(1000) # Not degrading significantly yet
            except:
                rul_series.append(1000)
                
        return pd.Series(rul_series, index=df_battery.index)
