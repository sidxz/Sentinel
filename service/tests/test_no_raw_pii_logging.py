import pathlib

SRC = pathlib.Path(__file__).resolve().parents[1] / "src"


def test_authz_routes_log_no_raw_email():
    text = (SRC / "api" / "authz_routes.py").read_text()
    # The two known leaks (email_conflict ~:259, inactive_user ~:267) must be gone.
    assert "email=idp_claims" not in text
    assert "email=user.email" not in text
