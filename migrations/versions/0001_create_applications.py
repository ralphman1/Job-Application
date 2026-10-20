"""Create applications and their status history.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company", sa.String(200), nullable=False),
        sa.Column("position", sa.String(200), nullable=False),
        sa.Column("vacancy_url", sa.String(2048), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("applied_on", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("next_action", sa.String(500), nullable=True),
        sa.Column("follow_up_on", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("length(trim(company)) BETWEEN 1 AND 200", name="ck_company_length"),
        sa.CheckConstraint("length(trim(position)) BETWEEN 1 AND 200", name="ck_position_length"),
        sa.CheckConstraint(
            "status IN ('applied', 'interview', 'offer', 'accepted', 'rejected', 'withdrawn')",
            name="ck_application_status",
        ),
        sa.CheckConstraint(
            "vacancy_url IS NULL OR length(vacancy_url) <= 2048", name="ck_url_length"
        ),
        sa.CheckConstraint("notes IS NULL OR length(notes) <= 5000", name="ck_notes_length"),
        sa.CheckConstraint(
            "(next_action IS NULL AND follow_up_on IS NULL) OR "
            "(next_action IS NOT NULL AND follow_up_on IS NOT NULL "
            "AND length(trim(next_action)) BETWEEN 1 AND 500)",
            name="ck_next_action_pair",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_applications_updated", "applications", ["updated_at", "id"])
    op.create_index("ix_applications_follow_up", "applications", ["follow_up_on", "id"])
    op.create_table(
        "status_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('applied', 'interview', 'offer', 'accepted', 'rejected', 'withdrawn')",
            name="ck_history_from_status",
        ),
        sa.CheckConstraint(
            "to_status IN ('applied', 'interview', 'offer', 'accepted', 'rejected', 'withdrawn')",
            name="ck_history_to_status",
        ),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_history_application", "status_history", ["application_id", "changed_at", "id"]
    )


def downgrade() -> None:
    op.drop_index("ix_history_application", table_name="status_history")
    op.drop_table("status_history")
    op.drop_index("ix_applications_follow_up", table_name="applications")
    op.drop_index("ix_applications_updated", table_name="applications")
    op.drop_table("applications")
