from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/smartfarm"
    
    # JWT
    secret_key: str = "your-super-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 525600 * 10  # ~10 years (no expiry)
    refresh_token_expire_days: int = 3650  # ~10 years (no expiry)
    
    # Application
    app_name: str = "SmartFarm API"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    # Sub-path prefix when running behind reverse proxy, e.g. /api
    # Leave empty for local dev. Set ROOT_PATH=/api in cPanel env vars.
    root_path: str = ""
    
    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:8080,https://broilabs.ukirbin.com"

    # IoT Device Authentication
    iot_api_key: str = "changeme-iot-secret-key"

    # Fonnte WhatsApp Gateway (https://fonnte.com)
    # Isi token dari dashboard Fonnte: https://app.fonnte.com/devices
    fonnte_token: str = ""
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
