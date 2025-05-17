"""add available_for_sprint to backlog

Revision ID: add_available_for_sprint
Revises: b6d91184c086
Create Date: 2025-05-17 00:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_available_for_sprint'
down_revision = 'b6d91184c086'
branch_labels = None
depends_on = None

def upgrade():
    # Adiciona a coluna available_for_sprint com valor padrão True
    op.add_column('backlog', sa.Column('available_for_sprint', sa.Boolean(), nullable=False, server_default='1'))

def downgrade():
    # Remove a coluna available_for_sprint
    op.drop_column('backlog', 'available_for_sprint') 