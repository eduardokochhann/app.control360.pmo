"""Merge multiple heads

Revision ID: af3becab4425
Revises: add_event_date_to_notes, add_include_in_status_report_flag, remove_available_for_sprint
Create Date: 2025-06-03 18:40:21.224864

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'af3becab4425'
down_revision = ('add_event_date_to_notes', 'add_include_in_status_report_flag', 'remove_available_for_sprint')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
