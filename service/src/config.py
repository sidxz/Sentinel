from pathlib import Path
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    database_url: str = (
        "postgresql+asyncpg://identity:identity_dev@localhost:9001/identity?ssl=require"
    )

    # Redis
    redis_url: str = "rediss://:sentinel_dev@localhost:9002/0"
    redis_tls_ca_cert: str = ""  # Path to CA cert for Redis TLS (e.g. keys/tls/ca.crt)
    redis_tls_verify: str = "none"  # "none" | "required" — set "required" in production

    # JWT
    jwt_private_key_path: Path = Path("keys/private.pem")
    jwt_public_key_path: Path = Path("keys/public.pem")
    jwt_algorithm: str = "RS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    admin_token_expire_minutes: int = 60
    authz_token_expire_minutes: int = 5
    jwt_previous_public_key_paths: str = (
        ""  # comma-separated retired public key paths (verify-only)
    )

    # OAuth2 providers
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    entra_client_id: str = ""
    entra_client_secret: str = ""
    entra_tenant_id: str = ""
    # Dex (self-hosted OIDC) — config-gated; consumed by the Layer-2 isolation prover.
    dex_client_id: str = ""
    dex_client_secret: str = ""
    dex_server_metadata_url: str = ""

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
    debug: bool = False  # Set True for local development (enables /docs, /redoc)
    rate_limit_rpm: int = 30  # Global rate limit (requests per minute per IP)
    rate_limit_enabled: bool = (
        True  # master switch; False only on ephemeral test targets
    )
    behind_proxy: bool = (
        False  # Set True when behind a reverse proxy (nginx, ALB, etc.)
    )
    trusted_proxy_count: int = (
        1  # Number of trusted reverse proxies between Sentinel and the internet.
        # The client IP is read from the Nth-from-right X-Forwarded-For entry, so
        # client-controlled (leftmost) values cannot spoof the rate-limit bucket.
    )

    # Admin
    admin_emails: str = ""
    admin_url: str = "http://localhost:9004"

    @property
    def redis_ssl_kwargs(self) -> dict:
        """Extra kwargs for redis.from_url() when using rediss:// scheme."""
        if not self.redis_url.startswith("rediss://"):
            return {}
        import ssl as _ssl

        kwargs: dict = {}
        if self.redis_tls_ca_cert:
            kwargs["ssl_ca_certs"] = self.redis_tls_ca_cert
        kwargs["ssl_cert_reqs"] = (
            _ssl.CERT_REQUIRED
            if self.redis_tls_verify == "required"
            else _ssl.CERT_NONE
        )
        return kwargs

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def jwt_previous_public_key_paths_list(self) -> list[str]:
        if not self.jwt_previous_public_key_paths:
            return []
        return [
            p.strip()
            for p in self.jwt_previous_public_key_paths.split(",")
            if p.strip()
        ]

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
        if not hosts:
            # No hosts derived — allow all in dev, but startup check
            # will reject this in production (DEBUG=False)
            return ["*"]
        return list(hosts)


settings = Settings()
