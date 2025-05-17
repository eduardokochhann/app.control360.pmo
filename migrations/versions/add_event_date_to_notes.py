"""Adiciona campo event_date à tabela notes

Revision ID: add_event_date_to_notes
Create Date: 2024-05-17 04:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic
revision = 'add_event_date_to_notes'
down_revision = 'cac58624e363'  # Apontando para a última migração
branch_labels = None
depends_on = None

def upgrade():
    # Adiciona a coluna event_date
    op.add_column('notes', 
        sa.Column('event_date', sa.DateTime(), nullable=True)
    )
    
    # Cria um índice para melhor performance
    op.create_index('ix_notes_event_date', 'notes', ['event_date'])
    
    # Atualiza os registros existentes usando created_at como valor inicial
    conn = op.get_bind()
    conn.execute("""
        UPDATE notes 
        SET event_date = created_at 
        WHERE event_date IS NULL
    """)

def downgrade():
    # Remove o índice
    op.drop_index('ix_notes_event_date', 'notes')
    
    # Remove a coluna
    op.drop_column('notes', 'event_date') 