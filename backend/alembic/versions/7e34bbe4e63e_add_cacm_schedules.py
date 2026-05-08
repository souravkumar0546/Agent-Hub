"""add cacm schedules

Adds the cacm_schedules table that backs the per-KRI scheduling feature
(see docs/superpowers/specs/2026-05-08-cacm-kri-scheduling-design.md).
One row per (org, process_key, kri_name); upsert semantics on save.

Revision ID: 7e34bbe4e63e
Revises: fcfc43cd930e
Create Date: 2026-05-08 08:07:09.354493

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7e34bbe4e63e"
down_revision: Union[str, Sequence[str], None] = "fcfc43cd930e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cacm_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "org_id", sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("process_key", sa.String(length=64), nullable=False),
        sa.Column("kri_name", sa.String(length=255), nullable=False),
        sa.Column("kpi_type", sa.String(length=80), nullable=False),
        sa.Column("frequency", sa.String(length=16), nullable=False),
        sa.Column("time_of_day", sa.String(length=5), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_run_id", sa.Integer(),
            sa.ForeignKey("cacm_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "is_active", sa.Boolean(),
            nullable=False, server_default=sa.true(),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "org_id", "process_key", "kri_name",
            name="uq_cacm_schedule_org_process_kri",
        ),
    )
    op.create_index(
        "ix_cacm_schedules_active_due",
        "cacm_schedules",
        ["is_active", "next_run_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_cacm_schedules_active_due", table_name="cacm_schedules")
    op.drop_table("cacm_schedules")
