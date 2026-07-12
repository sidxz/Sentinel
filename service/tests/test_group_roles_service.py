"""group_roles: groups as role assignees (spec 2026-07-12).

Model contract + service-layer tests in the repo's fake-session style.
The FK ondelete rules ARE the lifecycle design (group/role deletion cleans
bindings with zero purge code) — so they're asserted here, not assumed.
"""

from __future__ import annotations

from src.models.role import GroupRole


def test_group_role_table_contract():
    t = GroupRole.__table__
    assert t.name == "group_roles"
    fks = {fk.column.table.name: fk.ondelete for fk in t.foreign_keys}
    assert fks["groups"] == "CASCADE"
    assert fks["roles"] == "CASCADE"
    assert fks["users"] == "SET NULL"
    uniques = [
        c.name for c in t.constraints if c.__class__.__name__ == "UniqueConstraint"
    ]
    assert "uq_group_role" in uniques
