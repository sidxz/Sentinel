from src.config import Settings


def test_previous_public_key_paths_parses_csv():
    s = Settings(jwt_previous_public_key_paths="keys/old1.pem, keys/old2.pem")
    assert s.jwt_previous_public_key_paths_list == ["keys/old1.pem", "keys/old2.pem"]


def test_previous_public_key_paths_empty_default():
    s = Settings()
    assert s.jwt_previous_public_key_paths_list == []
