import numpy as np

def extract_features(cycle_data: dict, current_cycle_count: int = 1) -> dict:
    """
    Extracts statistical and physical battery features from time-series cycle telemetry.
    cycle_data should have 'time', 'voltage', 'current', 'temperature' arrays.
    """
    time = np.array(cycle_data.get('time', []))
    voltage = np.array(cycle_data.get('voltage', []))
    current = np.array(cycle_data.get('current', []))
    temperature = np.array(cycle_data.get('temperature', []))

    # Basic statistical descriptors
    avg_voltage = float(np.mean(voltage)) if len(voltage) > 0 else 3.7
    max_voltage = float(np.max(voltage)) if len(voltage) > 0 else 4.2
    min_voltage = float(np.min(voltage)) if len(voltage) > 0 else 3.0
    avg_current = float(np.mean(current)) if len(current) > 0 else 1.5
    avg_temp = float(np.mean(temperature)) if len(temperature) > 0 else 25.0
    
    # Variances
    v_var = float(np.var(voltage)) if len(voltage) > 0 else 0.01
    t_var = float(np.var(temperature)) if len(temperature) > 0 else 0.5
    c_var = float(np.var(current)) if len(current) > 0 else 0.2

    # Derived physics/energy features
    charge_time = 0.0
    discharge_time = 0.0
    capacity = 2.0
    if len(time) > 1:
        dt = np.diff(time, prepend=time[0])
        # Assume positive current is charging, negative is discharging
        charge_mask = current > 0
        discharge_mask = current < 0
        
        charge_time = float(np.sum(dt[charge_mask]))
        discharge_time = float(np.sum(dt[discharge_mask]))
        
        capacity = float(np.sum(np.abs(current) * dt) / 3600.0)
    else:
        # Fallbacks if only single point data is provided
        charge_time = 3600.0
        discharge_time = 3600.0

    capacity_fade = max(0.0, 2.0 - capacity)

    # Simplified Internal Resistance heuristic
    ir = 0.05

    # Simplified Energy Efficiency heuristic
    energy_eff = 0.95

    return {
        "cycle_count": current_cycle_count,
        "average_voltage": avg_voltage,
        "max_voltage": max_voltage,
        "min_voltage": min_voltage,
        "average_current": avg_current,
        "average_temperature": avg_temp,
        "capacity_fade": capacity_fade,
        "internal_resistance": ir,
        "charge_time": charge_time,
        "discharge_time": discharge_time,
        "energy_efficiency": energy_eff,
        "voltage_variance": v_var,
        "temperature_variance": t_var,
        "current_variance": c_var,
        # Keep capacity calculated for reference in backwards compatibility
        "capacity": capacity,
        "energy_throughput": capacity # using capacity as proxy for throughput (Amp-hours)
    }
