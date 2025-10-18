"""
Configuration management for Jikai application.
Uses Pydantic Settings for type-safe configuration with environment variable support.
"""

from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
import os


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    chroma_host: str = Field(default="localhost", env="CHROMA_HOST")
    chroma_port: int = Field(default=8000, env="CHROMA_PORT")
    chroma_collection_name: str = Field(default="tort_hypotheticals", env="CHROMA_COLLECTION")
    
    class Config:
        env_prefix = "DB_"


class LLMSettings(BaseSettings):
    """LLM provider configuration settings."""
    
    provider: str = Field(default="ollama", env="LLM_PROVIDER")
    model_name: str = Field(default="llama2:7b", env="LLM_MODEL")
    temperature: float = Field(default=0.7, env="LLM_TEMPERATURE")
    max_tokens: int = Field(default=2048, env="LLM_MAX_TOKENS")
    timeout: int = Field(default=30, env="LLM_TIMEOUT")
    
    # Ollama specific settings
    ollama_host: str = Field(default="http://localhost:11434", env="OLLAMA_HOST")
    
    class Config:
        env_prefix = "LLM_"


class AWSSettings(BaseSettings):
    """AWS configuration settings."""
    
    access_key_id: Optional[str] = Field(default=None, env="AWS_ACCESS_KEY_ID")
    secret_access_key: Optional[str] = Field(default=None, env="AWS_SECRET_ACCESS_KEY")
    region: str = Field(default="us-east-1", env="AWS_REGION")
    s3_bucket: str = Field(default="jikai-corpus", env="AWS_S3_BUCKET")
    
    class Config:
        env_prefix = "AWS_"


class APISettings(BaseSettings):
    """API configuration settings."""
    
    host: str = Field(default="0.0.0.0", env="API_HOST")
    port: int = Field(default=8000, env="API_PORT")
    debug: bool = Field(default=False, env="API_DEBUG")
    cors_origins: List[str] = Field(default=["*"], env="API_CORS_ORIGINS")
    rate_limit: int = Field(default=100, env="API_RATE_LIMIT")
    
    class Config:
        env_prefix = "API_"


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""
    
    level: str = Field(default="INFO", env="LOG_LEVEL")
    format: str = Field(default="json", env="LOG_FORMAT")
    file_path: Optional[str] = Field(default=None, env="LOG_FILE_PATH")
    
    @field_validator('level')
    @classmethod
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'Log level must be one of {valid_levels}')
        return v.upper()
    
    class Config:
        env_prefix = "LOG_"


class TortLawSettings(BaseSettings):
    """Tort law specific configuration."""
    
    law_domain: str = Field(default="tort", env="LAW_DOMAIN")
    default_topics: List[str] = Field(
        default=[
            "negligence", "duty of care", "standard of care", "causation", 
            "remoteness", "battery", "assault", "false imprisonment",
            "defamation", "private nuisance", "trespass to land", 
            "vicarious liability", "strict liability", "harassment"
        ],
        env="DEFAULT_TOPICS"
    )
    max_parties: int = Field(default=5, env="MAX_PARTIES")
    min_parties: int = Field(default=2, env="MIN_PARTIES")
    
    class Config:
        env_prefix = "TORT_"


class Settings(BaseSettings):
    """Main application settings combining all configuration sections."""
    
    app_name: str = Field(default="Jikai", env="APP_NAME")
    app_version: str = Field(default="2.0.0", env="APP_VERSION")
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    # Sub-configurations
    database: DatabaseSettings = DatabaseSettings()
    llm: LLMSettings = LLMSettings()
    aws: AWSSettings = AWSSettings()
    api: APISettings = APISettings()
    logging: LoggingSettings = LoggingSettings()
    tort_law: TortLawSettings = TortLawSettings()
    
    @field_validator('environment')
    @classmethod
    def validate_environment(cls, v):
        valid_envs = ['development', 'staging', 'production']
        if v.lower() not in valid_envs:
            raise ValueError(f'Environment must be one of {valid_envs}')
        return v.lower()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
