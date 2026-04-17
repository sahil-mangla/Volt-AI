
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
import random

def seed_variety():
    load_dotenv()
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("Error: DATABASE_URL not found")
        return

    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        print("🌱 Seeding status variety and model-specific RULs...")
        
        # 1. Get all batteries
        result = conn.execute(text("SELECT battery_id, last_cycle FROM battery_predictions"))
        rows = result.fetchall()
        
        for bid, last_cycle in rows:
            # Randomly pick 3 batteries to be "CRITICAL" (Health 60-69)
            if random.random() < 0.2:
                final_health = random.uniform(62.0, 69.5)
            # Randomly pick some to be "WARNING" (Health 70-79)
            elif random.random() < 0.3:
                final_health = random.uniform(71.0, 79.5)
            else:
                final_health = random.uniform(85.0, 99.0)
                
            # Differentiate RULs
            # Linear: Constant decay
            rul_linear = int((final_health - 60) / 0.15) if final_health > 60 else 0
            
            # LSTM: More optimistic/curved
            rul_lstm = int((final_health - 60) / 0.08) if final_health > 60 else 10
            
            # Update
            conn.execute(text("""
                UPDATE battery_predictions 
                SET health_score = :health, 
                    rul_linear = :rul_lin, 
                    rul_lstm = :rul_lstm 
                WHERE battery_id = :bid
            """), {"health": final_health, "rul_lin": rul_linear, "rul_lstm": rul_lstm, "bid": bid})
            print(f"  - Updated {bid}: Health={final_health:.1f}, Linear={rul_linear}, LSTM={rul_lstm}")
            
        conn.commit()
    print("✅ Database seeding complete.")

if __name__ == "__main__":
    seed_variety()
