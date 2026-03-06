# Testing

This guide covers the testing approach for the Sentinel Auth, including how to run tests, write new ones, and work with fixtures.

## Running Tests

From the service directory:

```bash
cd service && uv run pytest
```

With verbose output:

```bash
cd service && uv run pytest -v
```

Run a specific test file:

```bash
cd service && uv run pytest tests/test_permissions.py
```

Run a specific test function:

```bash
cd service && uv run pytest tests/test_permissions.py::test_check_permission -v
```

## Test Structure

Tests mirror the source directory structure:

```
service/
├── src/
│   ├── api/
│   │   ├── auth_routes.py
│   │   ├── user_routes.py
│   │   └── permission_routes.py
│   └── services/
│       ├── auth_service.py
│       └── permission_service.py
└── tests/
    ├── conftest.py              # Shared fixtures
    ├── test_auth.py             # Auth route tests
    ├── test_users.py            # User route tests
    └── test_permissions.py      # Permission route tests
```

## Fixtures

### Database Session

The `conftest.py` file provides a test database session that uses transactions rolled back after each test, ensuring test isolation without requiring a separate test database:

```python
@pytest.fixture
async def db_session():
    async with async_session() as session:
        async with session.begin():
            yield session
            await session.rollback()
```

### Test Client

An async test client for making HTTP requests against the FastAPI application:

```python
from httpx import AsyncClient, ASGITransport

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

### Authenticated User

A fixture that provides a pre-authenticated user context, bypassing the JWT validation middleware:

```python
@pytest.fixture
def auth_headers(test_user):
    """Headers with a valid JWT for test_user."""
    token = create_access_token(
        user_id=str(test_user.id),
        email=test_user.email,
        workspace_roles={"test-workspace": "owner"},
    )
    return {"Authorization": f"Bearer {token}"}
```

## Testing Patterns

### Testing API Routes

Use the async test client to make requests and assert on responses:

```python
@pytest.mark.asyncio
async def test_get_current_user(client, auth_headers):
    response = await client.get("/users/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
```

### Testing with Mocked JWT

For tests that need to verify behavior with different user contexts, create tokens with specific claims:

```python
@pytest.mark.asyncio
async def test_viewer_cannot_delete(client):
    token = create_access_token(
        user_id="user-uuid",
        email="viewer@example.com",
        workspace_roles={"my-workspace": "viewer"},
    )
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete(
        "/workspaces/my-workspace",
        headers=headers,
    )
    assert response.status_code == 403
```

### Testing Permission Checks

Permission tests typically involve registering a resource, setting visibility or shares, and then verifying access:

```python
@pytest.mark.asyncio
async def test_permission_check_owner_has_access(client, auth_headers, service_headers):
    # Register a resource
    await client.post(
        "/permissions/register",
        json={
            "resource_type": "document",
            "resource_id": "doc-uuid",
            "workspace_id": "ws-uuid",
            "owner_id": "user-uuid",
        },
        headers=service_headers,
    )

    # Check access
    response = await client.post(
        "/permissions/check",
        json={
            "resource_type": "document",
            "resource_id": "doc-uuid",
            "permission": "edit",
        },
        headers={**auth_headers, **service_headers},
    )
    assert response.status_code == 200
    assert response.json()["allowed"] is True
```

### Testing Service-Key Authentication

For endpoints that require service-key authentication:

```python
@pytest.fixture
def service_headers():
    return {"X-Service-Key": "test-service-key"}
```

Service keys are always validated against the database. For integration tests, create a service app via the admin API or use test fixtures that seed a service app into the database.

## Security / Penetration Testing

The `pentest/` directory contains a standalone security testing suite that runs against a live instance of the service. It combines industry tools (OWASP ZAP, Nuclei, Nikto, jwt_tool) with ~110 custom tests.

### Setup

```bash
# Install external tools
make pentest-setup
```

### Running

```bash
# Full suite (external tools + custom scripts)
make pentest

# Custom scripts only (faster, no tool dependencies)
make pentest-custom

# Individual tool
cd pentest && python run_all.py --zap
cd pentest && python run_all.py --nuclei
cd pentest && python run_all.py --nikto
cd pentest && python run_all.py --jwt
```

!!! note
    The custom suite pauses 62 seconds between test modules to respect the global rate limit (30 req/min). A full custom run takes ~10 minutes.

### Adding Custom Tests

Custom scripts live in `pentest/custom/`. Each script follows the pattern:

```python
from config import BASE_URL, forge_access_token, print_result, print_section

def test_my_security_check():
    r = httpx.get(f"{BASE_URL}/some/endpoint", ...)
    passed = r.status_code == 401
    print_result("My check description", passed, f"Status: {r.status_code}")
    return passed

def main():
    print_section("MY TEST SUITE")
    test_my_security_check()

if __name__ == "__main__":
    main()
```

Add the module to `SUITES` in `pentest/custom/runner.py` to include it in the full run. Reports are written to `pentest/reports/`.

---

## Best Practices

- **Use `pytest.mark.asyncio`** on all async test functions.
- **Isolate tests.** Each test should set up its own data and not depend on state from other tests.
- **Test both success and failure paths.** Verify that unauthorized requests return 401/403 and that invalid inputs return 422.
- **Use descriptive test names.** The function name should describe the scenario, e.g., `test_viewer_cannot_delete_workspace`.
- **Keep fixtures focused.** Create specific fixtures rather than one large setup that covers everything.
