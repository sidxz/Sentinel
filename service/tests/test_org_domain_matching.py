"""Organization model shape + pure domain-matching logic."""

import uuid


def test_organization_models_have_expected_shape():
    from src.models.organization import (
        Organization,
        OrganizationDomain,
        WorkspaceAllowedOrganization,
    )

    assert Organization.__tablename__ == "organizations"
    for col in ("id", "slug", "name", "is_public", "enabled", "created_by"):
        assert col in Organization.__table__.columns
    # At most one public org — the partial unique index must exist.
    assert any(
        idx.name == "uq_one_public_org" for idx in Organization.__table__.indexes
    )

    assert OrganizationDomain.__tablename__ == "organization_domains"
    for col in ("id", "organization_id", "domain", "include_subdomains"):
        assert col in OrganizationDomain.__table__.columns
    # Domain must be globally unique (a domain cannot belong to two orgs).
    assert any(
        c.name == "uq_org_domain"
        for c in OrganizationDomain.__table__.constraints
    )

    assert WorkspaceAllowedOrganization.__tablename__ == "workspace_allowed_organizations"
    for col in ("id", "workspace_id", "organization_id"):
        assert col in WorkspaceAllowedOrganization.__table__.columns


def test_models_registered_for_metadata():
    import src.models as m

    assert "Organization" in m.__all__
    assert "OrganizationDomain" in m.__all__
    assert "WorkspaceAllowedOrganization" in m.__all__


def test_user_has_organization_id_column():
    from src.models.user import User

    assert "organization_id" in User.__table__.columns
    assert User.__table__.columns["organization_id"].nullable is True
