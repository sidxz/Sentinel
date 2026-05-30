import uuid

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from src.config import Settings


def _write_keypair(tmp_path, name):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    priv_path = tmp_path / f"{name}_priv.pem"
    pub_path = tmp_path / f"{name}_pub.pem"
    priv_path.write_bytes(priv)
    pub_path.write_bytes(pub)
    return priv_path, pub_path


@pytest.fixture
def two_keys(tmp_path, monkeypatch):
    from src.auth import key_provider
    from src.config import settings

    cur_priv, cur_pub = _write_keypair(tmp_path, "cur")
    _old_priv, old_pub = _write_keypair(tmp_path, "old")
    monkeypatch.setattr(settings, "jwt_private_key_path", cur_priv)
    monkeypatch.setattr(settings, "jwt_public_key_path", cur_pub)
    monkeypatch.setattr(settings, "jwt_previous_public_key_paths", str(old_pub))
    key_provider.reset_cache()
    yield {"cur_pub": cur_pub.read_text(), "old_pub": old_pub.read_text()}
    key_provider.reset_cache()


def test_signing_key_returns_private_and_kid(two_keys):
    from src.auth import key_provider

    private_pem, kid = key_provider.signing_key()
    assert "PRIVATE KEY" in private_pem
    assert kid == key_provider.thumbprint_kid(two_keys["cur_pub"])


def test_verification_keys_include_current_and_previous(two_keys):
    from src.auth import key_provider

    keys = key_provider.verification_keys()
    cur_kid = key_provider.thumbprint_kid(two_keys["cur_pub"])
    old_kid = key_provider.thumbprint_kid(two_keys["old_pub"])
    assert set(keys) == {cur_kid, old_kid}
    assert keys[cur_kid] == two_keys["cur_pub"]


def test_previous_public_key_paths_parses_csv():
    s = Settings(jwt_previous_public_key_paths="keys/old1.pem, keys/old2.pem")
    assert s.jwt_previous_public_key_paths_list == ["keys/old1.pem", "keys/old2.pem"]


def test_previous_public_key_paths_empty_default():
    s = Settings()
    assert s.jwt_previous_public_key_paths_list == []
