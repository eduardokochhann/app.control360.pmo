"""empty message

Revision ID: bfd33be84b7e
Revises: add_generic_tasks_support, update_notes_add_backlog_id, update_notes_structure
Create Date: 2025-05-13 10:19:12.792183

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bfd33be84b7e'
down_revision = ('add_generic_tasks_support', 'update_notes_add_backlog_id', 'update_notes_structure')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
