from typing import Any

from pydantic import BaseModel, Field


class IdentifierQualitySummary(BaseModel):
    total_rows: int = 0
    non_null_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    missing_rows: int = 0
    looks_like_13_digit_rows: int = 0
    duplicate_normalized_identifier_rows: int = 0
    distinct_normalized_identifier_count: int = 0
    valid_percentage: float = 0.0
    invalid_percentage: float = 0.0
    missing_percentage: float = 0.0
    looks_like_13_digit_percentage: float = 0.0
    duplicate_rate_percentage: float = 0.0


class DateColumnProfile(BaseModel):
    column_name: str
    non_null_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    missing_rows: int = 0
    parseable_percentage: float = 0.0


class FileProfile(BaseModel):
    file_name: str
    file_type: str
    row_count: int
    available_columns: list[str] = Field(default_factory=list)
    important_non_null_counts: dict[str, int] = Field(default_factory=dict)
    date_profiles: list[DateColumnProfile] = Field(default_factory=list)
    service_type_samples: list[str] = Field(default_factory=list)
    identifier_quality: IdentifierQualitySummary
    anomalies: list[str] = Field(default_factory=list)


class ProfilingSummary(BaseModel):
    profile_type: str
    generated_at: str
    total_files: int
    total_rows: int
    available_columns: list[str] = Field(default_factory=list)
    important_non_null_counts: dict[str, int] = Field(default_factory=dict)
    date_profiles: list[DateColumnProfile] = Field(default_factory=list)
    service_type_samples: list[str] = Field(default_factory=list)
    identifier_quality: IdentifierQualitySummary
    files: list[FileProfile] = Field(default_factory=list)
    anomalies: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
