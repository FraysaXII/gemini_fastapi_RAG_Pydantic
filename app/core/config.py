from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    GEMINI_API_KEY: str = Field(..., description="Your Google Gemini API key")
    LOGFIRE_TOKEN: str | None = Field(None, description="Your Logfire token (optional)")
    LOG_LEVEL: str = Field("INFO", description="Logging level (e.g., DEBUG, INFO, WARNING)")
    APP_NAME: str = Field("GeminiFastAPI", description="Application name")

    # OpenTelemetry Resource Attributes
    OTEL_SERVICE_NAME: str = Field("gemini-fastapi-dev", description="OpenTelemetry service name")
    OTEL_SERVICE_VERSION: str = Field("0.1.0", description="OpenTelemetry service version")
    OTEL_DEPLOYMENT_ENVIRONMENT: str = Field("development", description="OpenTelemetry deployment environment (e.g., development, staging, production)")

    # Supabase Settings
    SUPABASE_URL: str | None = Field(None, description="Supabase project URL")
    SUPABASE_KEY: str | None = Field(None, description="Supabase anon or service role key")
    SUPABASE_DB_SCHEMA: str = Field("gemini_fastapi", description="Database schema for chat sessions")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')

settings = Settings() 