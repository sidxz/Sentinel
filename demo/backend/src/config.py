from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    sentinel_url: str = "http://localhost:9003"
    service_name: str = "team-notes"
    service_api_key: str = ""
    allowed_workspaces: list[str] = []
    host: str = "0.0.0.0"
    port: int = 9100
    frontend_url: str = "http://localhost:9101"


settings = Settings()
