import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load env variables
load_dotenv()

def verify_database():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not found!")
        return

    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM battery_cycles"))
            count = result.scalar()
            print(f"Total rows in 'battery_cycles': {count}")
            
            # Check a sample
            result = conn.execute(text("SELECT * FROM battery_cycles LIMIT 1"))
            row = result.fetchone()
            print(f"Sample row: {row}")
            
    except Exception as e:
        print(f"Verification failed: {e}")

if __name__ == "__main__":
    verify_database()
