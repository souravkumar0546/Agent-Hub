"""add cacm tables — CACM (Continuous Audit & Continuous Monitoring) agent.

Adds the three tables that persist run metadata, progress events, and
flagged exceptions for the new CACM agent. Design spec:
docs/superpowers/specs/2026-05-07-cacm-design.md.

Revision ID: fcfc43cd930e
Revises: 9b2e7f4a0c11
Create Date: 2026-05-07 15:45:44.681991

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fcfc43cd930e'
down_revision: Union[str, Sequence[str], None] = '9b2e7f4a0c11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cacm_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kpi_type", sa.String(80), nullable=False),
        sa.Column("process", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_records", sa.Integer, nullable=True),
        sa.Column("total_exceptions", sa.Integer, nullable=True),
        sa.Column("exception_pct", sa.Float, nullable=True),
        sa.Column("summary_json", sa.JSON, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index(op.f("ix_cacm_runs_org_id"), "cacm_runs", ["org_id"], unique=False)
    op.create_index(op.f("ix_cacm_runs_kpi_type"), "cacm_runs", ["kpi_type"], unique=False)

    op.create_table(
        "cacm_run_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("cacm_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("stage", sa.String(40), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("payload_json", sa.JSON, nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "seq", name="uq_cacm_event_run_seq"),
    )
    op.create_index(op.f("ix_cacm_run_events_run_id"), "cacm_run_events", ["run_id"], unique=False)

    op.create_table(
        "cacm_exceptions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("cacm_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exception_no", sa.String(40), nullable=False),
        sa.Column("risk", sa.String(10), nullable=False),
        sa.Column("payload_json", sa.JSON, nullable=False),
    )
    op.create_index(op.f("ix_cacm_exceptions_run_id"), "cacm_exceptions", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_cacm_exceptions_run_id"), table_name="cacm_exceptions")
    op.drop_table("cacm_exceptions")
    op.drop_index(op.f("ix_cacm_run_events_run_id"), table_name="cacm_run_events")
    op.drop_table("cacm_run_events")
    op.drop_index(op.f("ix_cacm_runs_kpi_type"), table_name="cacm_runs")
    op.drop_index(op.f("ix_cacm_runs_org_id"), table_name="cacm_runs")
    op.drop_table("cacm_runs")
