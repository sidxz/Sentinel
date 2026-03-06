"""JWKS (JSON Web Key Set) builder for Sentinel's RSA signing key."""

import base64
import hashlib

from cryptography.hazmat.primitives.serialization import load_pem_public_key

from src.auth.jwt import get_public_key

_jwks_cache: dict | None = None


def _int_to_base64url(n: int) -> str:
    """Convert a positive integer to a Base64url-encoded string (no padding)."""
    byte_length = (n.bit_length() + 7) // 8
    raw = n.to_bytes(byte_length, byteorder="big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def build_jwks() -> dict:
    """Build a JWKS response from the configured RSA public key.

    Result is cached after first call.
    """
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    pem_data = get_public_key().encode()
    pub_key = load_pem_public_key(pem_data)
    numbers = pub_key.public_numbers()  # type: ignore[union-attr]

    n_b64 = _int_to_base64url(numbers.n)
    e_b64 = _int_to_base64url(numbers.e)

    # RFC 7638 thumbprint for kid: SHA-256 of canonical JSON {e, kty, n}
    import json

    thumbprint_input = json.dumps(
        {"e": e_b64, "kty": "RSA", "n": n_b64}, separators=(",", ":"), sort_keys=True
    ).encode()
    kid = base64.urlsafe_b64encode(hashlib.sha256(thumbprint_input).digest()).rstrip(b"=").decode("ascii")

    _jwks_cache = {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": kid,
                "n": n_b64,
                "e": e_b64,
            }
        ]
    }
    return _jwks_cache
