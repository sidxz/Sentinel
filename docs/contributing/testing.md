# Testing

This guide covers the testing approach for the Sentinel Auth, including how to run tests, write new ones, and work with fixtures.

## Running Tests

### SDK Tests

The SDK (`sdk/`) has a full test suite. From the SDK directory:

```bash
cd sdk && uv run pytest
```

With verbose output:

```bash
cd sdk && uv run pytest -v
```

Run a specific test file:

```bash
cd sdk && uv run pytest tests/test_permissions.py
```

Run a specific test function:

```bash
cd sdk && uv run pytest tests/test_permissions.py::TestPermissionClient::test_can_allowed -v
```

### Service Tests

!!! warning "Not yet implemented"
    The service (`service/`) does not currently have its own test suite. Integration and API-level tests for the FastAPI service are planned but not yet in place. Contributions welcome.

## Test Structure

SDK tests live in `sdk/tests/` and cover each public module:

```
sdk/
├── src/sentinel_auth/
│   ├── types.py
│   ├── middleware.py
│   ├── dependencies.py
│   ├── permissions.py
│   ├── roles.py
│   └── sentinel.py
└── tests/
    ├── conftest.py              # Shared fixtures (RSA keypair, JWT helpers)
    ├── test_types.py            # AuthenticatedUser, WorkspaceContext
    ├── test_middleware.py       # JWTAuthMiddleware (Starlette TestClient)
    ├── test_dependencies.py     # FastAPI dependency helpers
    ├── test_permissions.py      # PermissionClient (httpx mocked via respx)
    └── test_roles.py            # RoleClient (httpx mocked via respx)
```

## Fixtures

Shared fixtures are defined in `sdk/tests/conftest.py`.

### RSA Keypair

A session-scoped RSA keypair used to sign and verify JWTs throughout the test suite:

```python
@pytest.fixture(scope="session")
def rsa_keypair():
    """Generate an RSA keypair for signing/verifying JWTs."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem
```

### JWT Payload and Token Factory

A standard JWT payload matching the middleware's expected claims, and a factory to encode it:

```python
@pytest.fixture()
def jwt_payload(user_id, workspace_id):
    """Standard JWT payload matching the middleware's expected claims."""
    return {
        "sub": str(user_id),
        "email": "alice@example.com",
        "name": "Alice",
        "wid": str(workspace_id),
        "wslug": "acme-corp",
        "wrole": "editor",
        "groups": [],
        "aud": "sentinel:access",
        "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
        "iat": datetime.datetime.now(datetime.UTC),
    }

@pytest.fixture()
def make_token(rsa_keypair):
    """Factory to encode a JWT payload with the test private key."""
    private_pem, _ = rsa_keypair
    def _make(payload: dict) -> str:
        return jwt.encode(payload, private_pem, algorithm="RS256")
    return _make
```

### Injecting a Fake User (Dependency Tests)

For testing FastAPI dependency helpers, a middleware injects an `AuthenticatedUser` into `request.state` to bypass JWT validation:

```python
def _inject_user(app: FastAPI, user: AuthenticatedUser):
    @app.middleware("http")
    async def _set_user(request: Request, call_next):
        request.state.user = user
        return await call_next(request)
```

## Testing Patterns

### Testing Middleware

Middleware tests build a minimal Starlette app, add `JWTAuthMiddleware`, and use `TestClient` to verify token validation:

```python
class TestJWTMiddleware:
    def test_valid_token(self, rsa_keypair, valid_token):
        _, pub = rsa_keypair
        client = TestClient(_make_app(pub))
        resp = client.get("/protected", headers={"Authorization": f"Bearer {valid_token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "alice@example.com"

    def test_expired_token(self, rsa_keypair, jwt_payload, make_token):
        _, pub = rsa_keypair
        jwt_payload["exp"] = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
        token = make_token(jwt_payload)
        client = TestClient(_make_app(pub))
        resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401
```

### Testing FastAPI Dependencies

Dependency tests use `FastAPI` + `TestClient` with the fake-user middleware to verify that `get_current_user`, `get_workspace_id`, `get_workspace_context`, and `require_role` work correctly:

```python
class TestRequireRole:
    def test_passes_when_role_sufficient(self, editor_user):
        app = FastAPI()
        _inject_user(app, editor_user)

        @app.get("/edit")
        def edit(user: AuthenticatedUser = Depends(require_role("editor"))):
            return {"ok": True}

        assert TestClient(app).get("/edit").status_code == 200

    def test_rejects_when_role_insufficient(self, editor_user):
        app = FastAPI()
        _inject_user(app, editor_user)

        @app.get("/admin")
        def admin(user: AuthenticatedUser = Depends(require_role("admin"))):
            return {"ok": True}

        resp = TestClient(app).get("/admin")
        assert resp.status_code == 403
```

### Testing HTTP Clients (PermissionClient / RoleClient)

The `PermissionClient` and `RoleClient` tests use [respx](https://lundberg.github.io/respx/) to mock `httpx` requests, so no live service is needed:

```python
class TestRoleClient:
    @respx.mock
    async def test_check_action_allowed(self, client):
        respx.post("https://auth.test/roles/check-action").mock(
            return_value=httpx.Response(200, json={"allowed": True})
        )
        assert await client.check_action("tok", "reports:export", WS_ID) is True
```

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
