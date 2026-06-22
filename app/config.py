from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Seamless for DMIS"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = Field(alias="DATABASE_URL")
    source_data_dir: Path = Path("./data")
    source_data_pattern: str = "*.xlsx"
    upload_dir: Path = Path("./data/uploads")
    export_dir: Path = Path("./data/exports")
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    default_source_filename: str = "main_history.xlsx"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
