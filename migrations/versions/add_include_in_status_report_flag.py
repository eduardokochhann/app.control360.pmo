"""Add include_in_status_report flag to Note model

Revision ID: add_include_in_status_report_flag
Revises: update_notes_add_backlog_id
Create Date: 2025-06-03 18:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_include_in_status_report_flag'
down_revision = 'update_notes_add_backlog_id'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar coluna include_in_status_report com valor padrão True
    # Por padrão, todas as notas são incluídas no Status Report (opt-out)
    op.add_column('notes', sa.Column('include_in_status_report', sa.Boolean(), 
                                    nullable=False, server_default='1'))
    
    # Atualizar todas as notas existentes:
    # - Notas de projeto: manter True (incluir)
    # - Notas de task: definir como False (não incluir) para manter comportamento atual
    op.execute("""
        UPDATE notes 
        SET include_in_status_report = CASE 
            WHEN note_type = 'project' THEN 1 
            WHEN note_type = 'task' THEN 0 
            ELSE 1 
        END
    """)


def downgrade():
    # Remover a coluna include_in_status_report
    op.drop_column('notes', 'include_in_status_report') 