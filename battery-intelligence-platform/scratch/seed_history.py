import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ml_engine.data_loader import DataLoader
from ml_engine.features import FeatureEngineer

def seed_history():
    load_dotenv()
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("Error: DATABASE_URL not found")
        return

    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        print("📊 Clearing old fake linear history...")
        conn.execute(text("DELETE FROM battery_features"))
        conn.commit()
        
    print("📥 Loading real raw data from database...")
    df = DataLoader.load_from_db(db_url)
    if df is None or df.empty:
        print("❌ No data found in battery_cycles table!")
        return
        
    print("🧠 Computing real cycle features...")
    df_features = FeatureEngineer.compute_cycle_features(df)
    
    records = []
    batteries = df_features['battery_id'].unique()
    
    with engine.connect() as conn:
        print("📦 Ensuring batteries exist in main table...")
        for bid in batteries:
            conn.execute(text("""
                INSERT INTO batteries (id, capacity, model_type, status)
                VALUES (:bid, 2.0, 'Lithium-Ion', 'Active')
                ON CONFLICT (id) DO NOTHING
            """), {"bid": bid})
        conn.commit()

    print("🔄 Generating actual history records...")
    for _, row in df_features.iterrows():
        bid = row['battery_id']
        cycle_num = row['cycle']
        cap = row.get('capacity', 2.0)
        v_mean = row.get('voltage_mean', 3.8)
        t_mean = row.get('temperature_mean', 25.0)
        
        health = row.get('health_score', 100.0)
        fade = (100.0 - health) / 20.0
        
        records.append({
            "bid": bid,
            "cycle": int(cycle_num),
            "fade": float(fade),
            "cap": float(cap),
            "v_mean": float(v_mean),
            "t_mean": float(t_mean)
        })
        
    print(f"💾 Inserting {len(records)} actual cycle records to battery_features...")
    
    with engine.connect() as conn:
        for chunk in [records[i:i+500] for i in range(0, len(records), 500)]:
            for rec in chunk:
                conn.execute(text("""
                    INSERT INTO battery_features (battery_id, cycle, cycle_count, avg_voltage, avg_temperature, capacity_fade, capacity_ah)
                    VALUES (:bid, :cycle, :cycle, :v_mean, :t_mean, :fade, :cap)
                    ON CONFLICT DO NOTHING
                """), rec)
            conn.commit()
            
    print("✅ Full Real History Seeding Complete!")

if __name__ == "__main__":
    seed_history()
