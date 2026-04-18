
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
import random

def seed_history():
    load_dotenv()
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("Error: DATABASE_URL not found")
        return

    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        print("📊 Seeding historical features for graphing...")
        
        # 1. Get current batteries
        result = conn.execute(text("SELECT battery_id, last_cycle, health_score FROM battery_predictions"))
        rows = result.fetchall()
        
        for bid, last_cycle, health in rows:
            print(f"  - Generating history for {bid} (up to cycle {last_cycle})")
            
            # Ensure battery exists in 'batteries' table to satisfy FK
            conn.execute(text("""
                INSERT INTO batteries (id, capacity, model_type, status)
                VALUES (:bid, 2.0, 'Lithium-Ion', 'Active')
                ON CONFLICT (id) DO NOTHING
            """), {"bid": bid})
            
            # Create 15 historical cycles
            for i in range(1, 16):
                cycle_num = max(1, last_cycle - (16 - i) * 5)
                # Health starts high and trends down to the current health
                hist_health = 100 - (100 - health) * (i / 15.0)
                # Map health back to capacity_fade (inverse)
                capacity_fade = (100 - hist_health) / 20.0
                
                conn.execute(text("""
                    INSERT INTO battery_features (battery_id, cycle, cycle_count, avg_voltage, avg_temperature, capacity_fade, capacity_ah)
                    VALUES (:bid, :cycle, :cycle, 3.8, 25.0, :fade, :cap)
                    ON CONFLICT DO NOTHING
                """), {
                    "bid": bid, 
                    "cycle": cycle_num, 
                    "fade": capacity_fade,
                    "cap": 2.0 - capacity_fade
                })
        
        conn.commit()
    print("✅ History seeding complete.")

if __name__ == "__main__":
    seed_history()
