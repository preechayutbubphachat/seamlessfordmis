from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Hospital Group Treatment History Filter"
    app_env: str = "development"
    app_edition: str = Field(default="lan_server", alias="APP_EDITION")
    database_engine: str = Field(default="", alias="DATABASE_ENGINE")
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/hospital_group_history",
        alias="DATABASE_URL",
    )
    cors_origins: str = Field(default="http://127.0.0.1:3020,http://localhost:3020", alias="CORS_ORIGINS")
    data_dir: Path = Field(default=Path("../data"), alias="DATA_DIR")
    source_data_dir: Path = Field(default=Path("../data"), alias="SOURCE_DATA_DIR")
    upload_dir: Path = Field(default=Path("../uploads/target_groups"), alias="UPLOAD_DIR")
    parsed_cache_dir: Path = Field(default=Path("../uploads/parsed_cache"), alias="PARSED_CACHE_DIR")
    reports_dir: Path = Field(default=Path("../backend/reports"), alias="REPORTS_DIR")
    exports_dir: Path = Field(default=Path("../data/exports"), alias="EXPORTS_DIR")
    backup_dir: Path = Field(default=Path("../data/backups"), alias="BACKUP_DIR")
    logs_dir: Path = Field(default=Path("../logs"), validation_alias=AliasChoices("LOG_DIR", "LOGS_DIR"))

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def include_error_details(self) -> bool:
        return self.app_env.lower() != "production"

    @property
    def effective_database_engine(self) -> str:
        configured = self.database_engine.strip().lower()
        if configured:
            return configured
        if self.database_url.strip().lower().startswith("sqlite"):
            return "sqlite"
        return "postgres"

    @property
    def is_desktop_local(self) -> bool:
        return self.app_edition.strip().lower() == "desktop_local"

    @property
    def is_sqlite(self) -> bool:
        return self.effective_database_engine == "sqlite"

    def resolve_local_path(self, value: Path) -> Path:
        if value.is_absolute():
            return value
        return value.resolve()


settings = Settings()
