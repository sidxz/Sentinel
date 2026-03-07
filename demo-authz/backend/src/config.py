from pydantic_settings import BaseSettings, SettingsConfigDict

from sentinel_auth import Sentinel


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    sentinel_url: str = "http://localhost:9003"
    service_name: str = "team-notes"
    service_api_key: str = ""
    idp_jwks_url: str = "https://www.googleapis.com/oauth2/v3/certs"
    host: str = "0.0.0.0"
    port: int = 9200
    frontend_url: str = "http://localhost:9201"


settings = Settings()

sentinel = Sentinel(
    base_url=settings.sentinel_url,
    service_name=settings.service_name,
    service_key=settings.service_api_key,
    mode="authz",
    idp_jwks_url=settings.idp_jwks_url,
    actions=[
        {"action": "notes:export", "description": "Export notes as JSON"},
        {"action": "notes:bulk-delete", "description": "Bulk delete notes"},
    ],
)
