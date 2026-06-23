"""Every configured rate-limit tier must be a string the `limits` library accepts.
Guards against typos like "10/min" (valid format is "10/minute") that would
otherwise blow up at request time inside slowapi.
"""

from limits import parse

from src.config import settings

TIERS = [
    "rate_limit_default",
    "rate_limit_aggregate",
    "rate_limit_auth",
    "rate_limit_auth_admin",
    "rate_limit_authz_resolve",
    "rate_limit_read",
    "rate_limit_admin_write",
    "rate_limit_sensitive",
]


def test_all_tiers_exist_and_parse():
    for name in TIERS:
        value = getattr(settings, name)
        assert isinstance(value, str), name
        if value:  # "" is the explicit "disable this tier" sentinel
            parse(value)  # raises ValueError on a malformed limit string
