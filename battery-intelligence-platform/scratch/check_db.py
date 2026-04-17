import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_url = os.environ.get('DATABASE_URL')
if not db_url:
    print("DATABASE_URL not found")
    exit(1)

engine = create_engine(db_url)
try:
    with engine.connect() as conn:
        result = conn.execute(text('SELECT battery_id, rul_lstm, health_score FROM battery_predictions LIMIT 5'))
        rows = result.fetchall()
        print(f"Predictions from DB: {rows}")
        
        result = conn.execute(text('SELECT battery_id, COUNT(*) FROM battery_cycles GROUP BY battery_id'))
        rows = result.fetchall()
        print(f"Cycle counts from DB: {rows}")
except Exception as e:
    print(f"Error: {e}")
