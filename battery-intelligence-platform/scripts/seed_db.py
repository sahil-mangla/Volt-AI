import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add parent directory to path to import ml_engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ml_engine.data_loader import DataLoader

def seed_database():
    """
    Reads the NASA dataset using DataLoader and uploads it to the Neon Postgres DB.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        # Try loading from .env manually if not in env
        try:
            from dotenv import load_dotenv
            load_dotenv()
            database_url = os.getenv("DATABASE_URL")
        except ImportError:
            pass
            
    if not database_url:
        logger.error("DATABASE_URL not found. Please set it in .env or environment variables.")
        return

    logger.info("Connecting to Database...")
    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection successful.")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return

    # Load Data locally
    # We use the existing DataLoader logic to parse the messy CSV structure
    local_data_path = os.path.join(os.path.dirname(__file__), '../data/raw/cleaned_dataset')
    
    logger.info(f"Loading data from {local_data_path}...")
    # Load ALL data (remove limit or set high)
    # NOTE: adjusting max_files to a reasonable number for initial seed.
    # Set to 1000 to catch everything in the folder.
    df = DataLoader.load_nasa_dataset(local_data_path, max_files=1000)
    
    if df is None or df.empty:
        logger.error("No data found to seed!")
        return

    logger.info(f"Loaded {len(df)} rows. Preparing to upload...")

    # Upload to DB
    table_name = 'battery_cycles'
    
    try:
        # write_to_sql chunksize is important for large datasets
        # 'replace' will drop the table if it exists and recreate it. 
        # Use 'append' if you want to add to it.
        df.to_sql(table_name, engine, if_exists='replace', index=False, chunksize=1000)
        
        # Create indices for performance
        with engine.connect() as conn:
            logger.info("Creating indices...")
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_battery_id ON {table_name} (battery_id)"))
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_battery_cycle ON {table_name} (battery_id, cycle)"))
            conn.commit()
            
        logger.info("Database seeding complete!")
        
    except Exception as e:
        logger.error(f"Failed to upload data: {e}")

if __name__ == "__main__":
    seed_database()
