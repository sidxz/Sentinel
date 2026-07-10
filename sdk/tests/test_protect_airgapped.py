"""Sentinel.protect() must accept the air-gapped authz config (idp_public_key only).

Regression: AuthzMiddleware's constructor precondition only consulted
sentinel_instance.idp_jwks_url, so protect() (which forwards no explicit keys)
raised ValueError at startup even when the Sentinel instance held a valid
idp_public_key.
"""

from starlette.applications import Starlette
from starlette.testclient import TestClient

from sentinel_auth import Sentinel


def test_protect_with_idp_public_key_only(rsa_keypair):
    _, public_pem = rsa_keypair
    s = Sentinel(
        base_url="https://sentinel.test",
        service_name="reports",
        service_key="svc-key",
        idp_public_key=public_pem,
        idp_audience="my-client-id",
    )
    app = Starlette(routes=[])
    s.protect(app)
    # The middleware constructor runs when the stack is built (first request).
    # Before the fix this raised ValueError despite the valid idp_public_key.
    with TestClient(app) as client:
        resp = client.get("/health")  # excluded path; 404 means the stack built
        assert resp.status_code == 404
