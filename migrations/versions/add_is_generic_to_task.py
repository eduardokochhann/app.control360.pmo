"""add is_generic to task

Revision ID: add_is_generic_to_task
Revises: # será preenchido automaticamente
Create Date: 2024-03-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_is_generic_to_task'
down_revision = None  # será preenchido automaticamente
branch_labels = None
depends_on = None

def upgrade():
    # Adiciona a coluna is_generic com valor padrão False
    op.add_column('task', sa.Column('is_generic', sa.Boolean(), nullable=False, server_default='0'))
    op.create_index(op.f('ix_task_is_generic'), 'task', ['is_generic'], unique=False)

def downgrade():
    # Remove a coluna is_generic
    op.drop_index(op.f('ix_task_is_generic'), table_name='task')
    op.drop_column('task', 'is_generic') 