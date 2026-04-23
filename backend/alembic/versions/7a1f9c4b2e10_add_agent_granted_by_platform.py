"""add agents.granted_by_platform

Splits the single `agents.is_enabled` install flag into two independent
permissions:

  * `granted_by_platform` — super admin's gate ("this agent is available to
    this org at all"). Must be true before the org admin can install.
  * `is_enabled`          — org admin's install flag (unchanged semantics).

Existing rows are backfilled to `granted_by_platform=true` so any already-
installed agents in bootstrapped orgs (e.g. Syngene from the dev seed) stay
working. From here on, new orgs start empty — super admin grants agents one
by one, and the org admin decides what to install.

Revision ID: 7a1f9c4b2e10
Revises: 95cef30ffe22
Create Date: 2026-04-22 20:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7a1f9c4b2e10"
down_revision: Union[str, Sequence[str], None] = "95cef30ffe22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add with server_default=true so existing rows are automatically granted.
    # After the column is in place we drop the default so the ORM controls it
    # (ORM default is False — new rows only become granted via the explicit
    # /platform/agents/grant endpoint).
    op.add_column(
        "agents",
        sa.Column(
            "granted_by_platform",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.alter_column("agents", "granted_by_platform", server_default=None)


def downgrade() -> None:
    op.drop_column("agents", "granted_by_platform")
