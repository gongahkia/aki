"""
Configuration management for Jikai application.
Uses Pydantic Settings for type-safe configuration with environment variable support.
"""

from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""

    chroma_host: str = Field(default="localhost", env="CHROMA_HOST")
    chroma_port: int = Field(default=8000, env="CHROMA_PORT")
    chroma_collection_name: str = Field(
        default="tort_hypotheticals", env="CHROMA_COLLECTION"
    )

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

    host: str = Field(default="127.0.0.1", env="API_HOST")
    port: int = Field(default=8000, env="API_PORT")
    debug: bool = Field(default=False, env="API_DEBUG")
    cors_origins: List[str] = Field(default=["*"], env="API_CORS_ORIGINS")
    rate_limit: int = Field(default=100, env="API_RATE_LIMIT")
    rate_limiter_max_buckets: int = Field(
        default=10000, env="API_RATE_LIMITER_MAX_BUCKETS"
    )
    rate_limiter_bucket_ttl_seconds: int = Field(
        default=600, env="API_RATE_LIMITER_BUCKET_TTL_SECONDS"
    )
    rate_limiter_cleanup_interval_seconds: int = Field(
        default=60, env="API_RATE_LIMITER_CLEANUP_INTERVAL_SECONDS"
    )

    @field_validator(
        "rate_limiter_max_buckets",
        "rate_limiter_bucket_ttl_seconds",
        "rate_limiter_cleanup_interval_seconds",
    )
    @classmethod
    def validate_rate_limiter_values(cls, v):
        if int(v) < 1:
            raise ValueError("Rate limiter values must be >= 1")
        return int(v)

    class Config:
        env_prefix = "API_"


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""

    level: str = Field(default="INFO", env="LOG_LEVEL")
    format: str = Field(default="json", env="LOG_FORMAT")
    file_path: Optional[str] = Field(default=None, env="LOG_FILE_PATH")

    @field_validator("level")
    @classmethod
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()

    class Config:
        env_prefix = "LOG_"


class TortLawSettings(BaseSettings):
    """Tort law specific configuration."""

    law_domain: str = Field(default="tort", env="LAW_DOMAIN")
    default_topics: List[str] = Field(
        default=[
            "negligence",
            "duty of care",
            "standard of care",
            "causation",
            "remoteness",
            "battery",
            "assault",
            "false imprisonment",
            "defamation",
            "private nuisance",
            "trespass to land",
            "vicarious liability",
            "strict liability",
            "harassment",
            "occupiers_liability",
            "product_liability",
            "contributory_negligence",
            "economic_loss",
            "psychiatric_harm",
            "employers_liability",
            "breach_of_statutory_duty",
            "rylands_v_fletcher",
            "consent_defence",
            "illegality_defence",
            "limitation_periods",
            "res_ipsa_loquitur",
            "novus_actus_interveniens",
            "volenti_non_fit_injuria",
        ],
        env="DEFAULT_TOPICS",
    )
    max_parties: int = Field(default=5, env="MAX_PARTIES")
    min_parties: int = Field(default=2, env="MIN_PARTIES")

    class Config:
        env_prefix = "TORT_"


class LLMProviderSettings(BaseSettings):
    """LLM provider API keys and hosts."""

    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    google_api_key: Optional[str] = Field(default=None, env="GOOGLE_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    ollama_host: str = Field(default="http://localhost:11434", env="OLLAMA_HOST")
    local_llm_host: Optional[str] = Field(default=None, env="LOCAL_LLM_HOST")
    default_provider: str = Field(default="ollama", env="DEFAULT_PROVIDER")
    default_model: str = Field(default="llama2:7b", env="DEFAULT_MODEL")

    class Config:
        env_prefix = ""


class MLSettings(BaseSettings):
    """ML pipeline configuration."""

    models_dir: str = Field(default="models", env="ML_MODELS_DIR")
    training_data_path: str = Field(
        default="corpus/labelled/sample.csv", env="ML_TRAINING_DATA"
    )
    default_n_clusters: int = Field(default=5, env="ML_N_CLUSTERS")

    class Config:
        env_prefix = "ML_"


class TUISettings(BaseSettings):
    """TUI configuration."""

    theme: str = Field(default="dark", env="TUI_THEME")
    keybindings: str = Field(default="default", env="TUI_KEYBINDINGS")

    class Config:
        env_prefix = "TUI_"


class Settings(BaseSettings):
    """Main application settings combining all configuration sections."""

    app_name: str = Field(default="Jikai", env="APP_NAME")
    app_version: str = Field(default="2.0.0", env="APP_VERSION")
    environment: str = Field(default="development", env="ENVIRONMENT")
    allowed_law_domains: List[str] = Field(
        default=["tort"], env="ALLOWED_LAW_DOMAINS"
    )
    corpus_path: str = Field(default="corpus/clean/tort/corpus.json", env="CORPUS_PATH")
    database_path: str = Field(default="data/jikai.db", env="DATABASE_PATH")
    retention_enabled: bool = Field(default=True, env="RETENTION_ENABLED")
    retention_generations: int = Field(default=2000, env="RETENTION_GENERATIONS")
    retention_reports: int = Field(default=4000, env="RETENTION_REPORTS")
    retention_cleanup_interval_minutes: int = Field(
        default=60, env="RETENTION_CLEANUP_INTERVAL_MINUTES"
    )
    local_response_cache_enabled: bool = Field(
        default=True, env="LOCAL_RESPONSE_CACHE_ENABLED"
    )
    local_response_cache_ttl_seconds: int = Field(
        default=120, env="LOCAL_RESPONSE_CACHE_TTL_SECONDS"
    )
    local_response_cache_max_entries: int = Field(
        default=128, env="LOCAL_RESPONSE_CACHE_MAX_ENTRIES"
    )
    embedding_model: str = Field(default="all-MiniLM-L6-v2", env="EMBEDDING_MODEL")

    # Sub-configurations
    database: DatabaseSettings = DatabaseSettings()
    llm: LLMSettings = LLMSettings()
    aws: AWSSettings = AWSSettings()
    api: APISettings = APISettings()
    logging: LoggingSettings = LoggingSettings()
    tort_law: TortLawSettings = TortLawSettings()
    llm_providers: LLMProviderSettings = LLMProviderSettings()
    ml: MLSettings = MLSettings()
    tui: TUISettings = TUISettings()

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        valid_envs = ["development", "staging", "production"]
        if v.lower() not in valid_envs:
            raise ValueError(f"Environment must be one of {valid_envs}")
        return v.lower()

    @field_validator("allowed_law_domains", mode="before")
    @classmethod
    def validate_allowed_law_domains(cls, v):
        if isinstance(v, str):
            parsed = [domain.strip().lower() for domain in v.split(",") if domain.strip()]
            return parsed or ["tort"]
        if isinstance(v, list):
            parsed = [str(domain).strip().lower() for domain in v if str(domain).strip()]
            return parsed or ["tort"]
        return ["tort"]

    @field_validator(
        "retention_generations",
        "retention_reports",
        "retention_cleanup_interval_minutes",
        "local_response_cache_ttl_seconds",
        "local_response_cache_max_entries",
    )
    @classmethod
    def validate_retention_values(cls, v):
        if int(v) < 1:
            raise ValueError("Configured values must be >= 1")
        return int(v)

    @property
    def anthropic_api_key(self):
        return self.llm_providers.anthropic_api_key

    @property
    def google_api_key(self):
        return self.llm_providers.google_api_key

    @property
    def openai_api_key(self):
        return self.llm_providers.openai_api_key

    @property
    def local_llm_host(self):
        return self.llm_providers.local_llm_host

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
