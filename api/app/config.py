from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    postgres_db: str = "jobpilot"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    
    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/jobpilot")
    redis_url: str = Field(default="redis://localhost:6379/0")
    
    gemini_api_key: str = ""
    claude_api_key: str = ""
    encryption_key: str = ""
    
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
