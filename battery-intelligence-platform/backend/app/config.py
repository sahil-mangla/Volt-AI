from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    database_url: Optional[str] = None
    azure_storage_connection_string: Optional[str] = None
    azure_sql_connection_string: Optional[str] = None
    model_path: Optional[str] = "app/ml/lstm_model.h5"
    secret_key: Optional[str] = "super-secret-key"

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()
