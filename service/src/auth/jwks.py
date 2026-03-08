"""JWKS (JSON Web Key Set) builder for Sentinel's RSA signing key."""

import base64
import hashlib
import json
import time

from cryptography.hazmat.primitives.serialization import load_pem_public_key
from jwt.algorithms import RSAAlgorithm

from src.auth.jwt import get_public_key

_jwks_cache: dict | None = None
_jwks_cache_time: float = 0
_JWKS_CACHE_TTL = 3600  # 1 hour — rebuild after key rotation + restart


def build_jwks() -> dict:
    """Build a JWKS response from the configured RSA public key.

    Result is cached with a TTL to support key rotation without full restart.
    """
    global _jwks_cache, _jwks_cache_time
    if (
        _jwks_cache is not None
        and (time.monotonic() - _jwks_cache_time) < _JWKS_CACHE_TTL
    ):
        return _jwks_cache

    pub_key = load_pem_public_key(get_public_key().encode())
    jwk = json.loads(RSAAlgorithm.to_jwk(pub_key))
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"

    # RFC 7638 thumbprint for kid — no mainstream Python lib provides this
    thumbprint_input = json.dumps(
        {"e": jwk["e"], "kty": "RSA", "n": jwk["n"]},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    jwk["kid"] = (
        base64.urlsafe_b64encode(hashlib.sha256(thumbprint_input).digest())
        .rstrip(b"=")
        .decode("ascii")
    )

    _jwks_cache = {"keys": [jwk]}
    _jwks_cache_time = time.monotonic()
    return _jwks_cache
