"""Regression test: ``email_verified`` must be strictly the boolean ``True``.

Vulnerability: the proxy-mode callbacks in ``auth_routes.py`` used
``if not userinfo.get("email_verified", False):``, which accepts any truthy
value — including the *string* ``"false"``. An IdP that emits a stringified
boolean (a known quirk of some configurations) could therefore slip an
unverified-email sign-in past the check. V13 fixed this in
``idp_validator.py`` (authz-mode) but the proxy-mode paths used a separate
inline check that was missed. The shared helper below closes the scope gap.
"""

from __future__ import annotations

import pytest

from src.services.auth_service import is_email_verified_claim


class TestIsEmailVerifiedClaim:
    def test_boolean_true_accepted(self):
        assert is_email_verified_claim({"email_verified": True}) is True

    def test_boolean_false_rejected(self):
        assert is_email_verified_claim({"email_verified": False}) is False

    @pytest.mark.parametrize("truthy_string", ["true", "True", "TRUE", "1", "yes"])
    def test_truthy_strings_rejected(self, truthy_string):
        assert is_email_verified_claim({"email_verified": truthy_string}) is False

    @pytest.mark.parametrize("falsy_string", ["false", "False", "0", "no", ""])
    def test_any_string_rejected(self, falsy_string):
        """Even a 'false' string is a non-boolean — reject strictly."""
        assert is_email_verified_claim({"email_verified": falsy_string}) is False

    def test_integer_one_rejected(self):
        assert is_email_verified_claim({"email_verified": 1}) is False

    def test_missing_rejected(self):
        assert is_email_verified_claim({}) is False

    def test_none_rejected(self):
        assert is_email_verified_claim({"email_verified": None}) is False
