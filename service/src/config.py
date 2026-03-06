from pathlib import Path
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    database_url: str = (
        "postgresql+asyncpg://identity:identity_dev@localhost:9001/identity"
    )

    # Redis
    redis_url: str = "redis://localhost:9002/0"

    # JWT
    jwt_private_key_path: Path = Path("keys/private.pem")
    jwt_public_key_path: Path = Path("keys/public.pem")
    jwt_algorithm: str = "RS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    admin_token_expire_minutes: int = 60

    # OAuth2 providers
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    entra_client_id: str = ""
    entra_client_secret: str = ""
    entra_tenant_id: str = ""

    # Service
    service_host: str = "0.0.0.0"
    service_port: int = 9003
    base_url: str = "http://localhost:9003"
    frontend_url: str = "http://localhost:3000"

    # Session (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
    session_secret_key: str = "dev-only-change-me-in-production"

    # CORS (comma-separated in .env)
    cors_origins: str = "http://localhost:3000,http://localhost:9101"

    # Security
    cookie_secure: bool = False  # Set True in production (requires HTTPS)
    allowed_hosts: str = ""  # comma-separated override; empty = derived from BASE_URL
    debug: bool = True  # Set False in production (disables /docs, /redoc)

    # Admin
    admin_emails: str = ""
    admin_url: str = "http://localhost:9004"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def admin_email_list(self) -> list[str]:
        if not self.admin_emails:
            return []
        return [e.strip() for e in self.admin_emails.split(",") if e.strip()]

    @property
    def allowed_hosts_list(self) -> list[str]:
        if self.allowed_hosts:
            return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]
        # Derive from BASE_URL + ADMIN_URL
        hosts = set()
        for url in [self.base_url, self.admin_url]:
            parsed = urlparse(url)
            if parsed.hostname:
                hosts.add(parsed.hostname)
        return list(hosts) if hosts else ["*"]



settings = Settings()
