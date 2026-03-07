# Code Style

This page documents the coding conventions and architectural decisions used throughout the Sentinel Auth.

## Async Everywhere

The entire service is async. This applies to:

- **FastAPI route handlers** -- all use `async def`
- **SQLAlchemy** -- uses the 2.0 async API (`AsyncSession`, `async_sessionmaker`)
- **HTTP clients** -- uses `httpx.AsyncClient` for outbound requests
- **Redis** -- uses `aioredis` (via the `redis` package's async interface)

Do not introduce synchronous blocking calls. If you need to call a synchronous library, wrap it with `asyncio.to_thread()`.

```python
# Correct
async def get_user(db: AsyncSession, user_id: UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

# Incorrect -- blocks the event loop
def get_user(db: Session, user_id: UUID) -> User | None:
    return db.query(User).filter(User.id == user_id).first()
```

## Pydantic v2

All request and response schemas use Pydantic v2 with `model_config`:

```python
from pydantic import BaseModel, ConfigDict

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str
    is_active: bool
```

Key conventions:

- Use `from_attributes=True` on response models so they can be constructed directly from SQLAlchemy model instances.
- Use `Field()` for validation constraints and descriptions.
- Request bodies use separate schema classes from responses (do not reuse the same model for both).

## Type Hints

All public functions must have complete type annotations, including return types:

```python
async def create_workspace(
    db: AsyncSession,
    name: str,
    slug: str,
    created_by: UUID,
) -> Workspace:
    ...
```

Use modern Python 3.12 syntax:

- `str | None` instead of `Optional[str]`
- `list[str]` instead of `List[str]`
- `dict[str, Any]` instead of `Dict[str, Any]`

## Docstrings

Use Google-style docstrings on all public classes and functions:

```python
async def check_permission(
    db: AsyncSession,
    user_id: UUID,
    resource_type: str,
    resource_id: UUID,
    permission: str,
) -> bool:
    """Check if a user has a specific permission on a resource.

    Evaluates access in order: ownership, visibility, direct shares,
    and group shares.

    Args:
        db: Async database session.
        user_id: The ID of the user to check.
        resource_type: The type of resource (e.g., "document").
        resource_id: The unique ID of the resource.
        permission: The required permission level ("view" or "edit").

    Returns:
        True if the user has the requested permission, False otherwise.

    Raises:
        ValueError: If permission is not "view" or "edit".
    """
```

This format is parsed by mkdocstrings to generate the [SDK Reference](../reference/index.md).

## Logging

Use `structlog` for structured logging:

```python
import structlog

logger = structlog.get_logger()

async def handle_callback(provider: str, code: str):
    logger.info("oauth_callback", provider=provider)
    try:
        user = await process_oauth(provider, code)
        logger.info("user_authenticated", user_id=str(user.id), provider=provider)
    except OAuthError as e:
        logger.error("oauth_failed", provider=provider, error=str(e))
        raise
```

Guidelines:

- Use snake_case event names (first positional argument).
- Pass structured key-value pairs, not formatted strings.
- Log at appropriate levels: `debug` for development details, `info` for normal operations, `warning` for recoverable issues, `error` for failures.

## Dependency Management

The project uses [uv](https://docs.astral.sh/uv/) for dependency management with a workspace layout:

```bash
# Add a dependency to the service
cd service && uv add package-name

# Add a dependency to the SDK
cd sdk && uv add package-name

# Sync all workspace dependencies
uv sync
```

The root `uv.lock` file locks all dependencies across the workspace. Always commit `uv.lock` changes.

## No Local User Management

This is a fundamental architectural decision: Sentinel never stores passwords or manages user credentials directly. All authentication flows go through external identity providers (Google, GitHub, Microsoft Entra ID) via OAuth2/OIDC.

User records are created automatically on first login. The `social_accounts` table links users to their provider identities, allowing a single user to log in through multiple providers.

Do not add:

- Password fields to the `User` model
- Registration endpoints that accept email/password
- Password reset flows
- Local authentication middleware

## SQLAlchemy Patterns

Use the `mapped_column` declarative style (SQLAlchemy 2.0):

```python
class Group(Base):
    __tablename__ = "groups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
```

For queries, use the `select()` construct:

```python
# Correct -- SQLAlchemy 2.0 style
stmt = select(User).where(User.email == email)
result = await db.execute(stmt)
user = result.scalar_one_or_none()

# Incorrect -- legacy 1.x style
user = db.query(User).filter_by(email=email).first()
```

## Error Handling

Use FastAPI's `HTTPException` for API errors:

```python
from fastapi import HTTPException, status

async def get_workspace_or_404(db: AsyncSession, slug: str) -> Workspace:
    workspace = await get_workspace_by_slug(db, slug)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{slug}' not found",
        )
    return workspace
```

Use specific HTTP status codes:

- `400` for invalid input that passes Pydantic validation but fails business rules
- `401` for missing or invalid authentication
- `403` for authenticated users without sufficient permissions
- `404` for resources that do not exist
- `409` for conflicts (e.g., duplicate workspace slugs)
- `422` is returned automatically by FastAPI for Pydantic validation failures
