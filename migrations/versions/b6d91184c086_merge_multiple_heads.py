"""merge multiple heads

Revision ID: b6d91184c086
Revises: add_is_generic_to_task, bfd33be84b7e, initial_migration
Create Date: 2025-05-17 00:40:07.681710

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b6d91184c086'
down_revision = ('add_is_generic_to_task', 'bfd33be84b7e', 'initial_migration')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
