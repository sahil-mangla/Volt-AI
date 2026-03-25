import time
import sys
import os

# Ensure the backend root is in the python path for absolute imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database.session import SessionLocal
from app.api.router import recompute_ml_internal

def run_recompute():
    """
    Standalone runner to process the entire battery fleet's ML predictions.
    Connects to the database currently configured in .env (e.g., Neon PostgreSQL).
    """
    db = SessionLocal()
    try:
        print("Starting local ML recompute...")
        
        while True:
            # processes one batch of 50 batteries at a time
            result = recompute_ml_internal(db, batch_size=50)
            
            remaining = result.get("remaining", 0)
            processed = result.get("batteries_processed_this_batch", 0)
            
            print(f"Processed {processed} batteries. Remaining: {remaining}")
            
            if remaining == 0:
                print("Recompute completed!")
                break
                
            # Throttle to prevent database connection exhaustion
            time.sleep(1)
            
    except Exception as e:
        print(f"Fatal error during recompute: {e}")
    finally:
        db.close()
        print("Database session closed.")

if __name__ == "__main__":
    run_recompute()
