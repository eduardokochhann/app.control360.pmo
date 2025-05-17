"""remove available_for_sprint from backlog

Revision ID: remove_available_for_sprint
Revises: add_available_for_sprint
Create Date: 2025-05-17 02:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'remove_available_for_sprint'
down_revision = 'add_available_for_sprint'
branch_labels = None
depends_on = None

def upgrade():
    # Remove a coluna available_for_sprint
    op.drop_column('backlog', 'available_for_sprint')

def downgrade():
    # Adiciona a coluna available_for_sprint de volta com valor padrão True
    op.add_column('backlog', sa.Column('available_for_sprint', sa.Boolean(), nullable=False, server_default='1')) 