from functools import lru_cache
from typing import List

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Spheronix Hackathon Registration API"
    app_env: str = Field(default="development", alias="APP_ENV")
    app_base_url: str = Field(default="http://127.0.0.1:8000", alias="APP_BASE_URL")
    server_host: str = Field(default="0.0.0.0", alias="SERVER_HOST")
    server_port: int = Field(default=8000, alias="SERVER_PORT")

    mongodb_uri: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URI")
    mongodb_uri_legacy: str = Field(default="", alias="MONGO_URI")
    database_name: str = Field(default="hackathon_db", alias="DATABASE_NAME")
    database_name_legacy: str = Field(default="", alias="DB_NAME")
    global_db_name: str = Field(default="global_db", alias="GLOBAL_DB_NAME")

    cors_origins: str = Field(default="http://localhost:8000,http://127.0.0.1:8000", alias="CORS_ORIGINS")

    secret_key: str = Field(default="change-this-secret", alias="SECRET_KEY")
    admin_api_key: str = Field(default="change-this-admin-key", alias="ADMIN_API_KEY")

    google_client_id: str = Field(default="", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(default="", alias="GOOGLE_REDIRECT_URI")

    razorpay_key_id: str = Field(default="", alias="RAZORPAY_KEY_ID")
    razorpay_key_secret: str = Field(default="", alias="RAZORPAY_KEY_SECRET")
    razorpay_webhook_secret: str = Field(default="", alias="RAZORPAY_WEBHOOK_SECRET")

    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    mail_from: str = Field(default="", alias="MAIL_FROM")

    @field_validator("app_env")
    @classmethod
    def normalize_app_env(cls, value: str) -> str:
        return (value or "development").strip().lower()

    @field_validator("app_base_url")
    @classmethod
    def normalize_app_base_url(cls, value: str) -> str:
        # Strip inline comments (e.g. "http://...  # some comment")
        value = (value or "").split("#")[0].strip()
        # If someone accidentally set it to a comma-separated list, take the first entry
        if "," in value:
            value = value.split(",")[0].strip()
        return value.rstrip("/")



    @field_validator("cors_origins")
    @classmethod
    def normalize_cors_origins(cls, value: str) -> str:
        return ",".join(origin.strip() for origin in (value or "").split(",") if origin.strip())

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.is_production:
            if self.secret_key == "change-this-secret" or len(self.secret_key) < 24:
                raise ValueError("SECRET_KEY must be securely configured for production")
        return self

    @property
    def effective_mongodb_uri(self) -> str:
        return self.mongodb_uri_legacy or self.mongodb_uri

    @property
    def effective_database_name(self) -> str:
        return self.database_name_legacy or self.database_name

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
