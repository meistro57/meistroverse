from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "mysql+pymysql://user:password@localhost/meistroverse"
    redis_url: str = "redis://localhost:6379/0"
    
    # AI/LLM
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    
    # Application
    debug: bool = False
    log_level: str = "INFO"
    secret_key: str = "your_secret_key_here"
    
    # External APIs
    printify_api_key: Optional[str] = None
    printify_shop_id: Optional[str] = None
    
    # Task Queue
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    
    # Web Server
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()