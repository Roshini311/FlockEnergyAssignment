"""
Application Configuration.

Loads environment variables and configuration settings for the API wrapper.
No default credentials are embedded for security compliance.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    URJA_BASE_URL: str = "https://urja-ops.flockenergy.tech"
    URJA_USERNAME: str = ""
    URJA_PASSWORD: str = ""
    REQUEST_TIMEOUT: float = 10.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
