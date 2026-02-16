"""
Create battery_predictions table in Neon database.
This table stores pre-computed LSTM predictions to avoid running ML models on Vercel.
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_predictions_table():
    """Creates the battery_predictions table if it doesn't exist."""
    
    # Load environment variables
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        logger.error("DATABASE_URL not found in environment variables")
        sys.exit(1)
    
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Create table
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS battery_predictions (
                id SERIAL PRIMARY KEY,
                battery_id VARCHAR(50) NOT NULL,
                rul_lstm INTEGER NOT NULL,
                health_score FLOAT NOT NULL,
                last_cycle INTEGER NOT NULL,
                computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(battery_id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_battery_predictions_battery_id 
            ON battery_predictions(battery_id);
            """
            
            conn.execute(text(create_table_sql))
            conn.commit()
            
            logger.info("✅ battery_predictions table created successfully")
            
    except Exception as e:
        logger.error(f"❌ Error creating table: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_predictions_table()
