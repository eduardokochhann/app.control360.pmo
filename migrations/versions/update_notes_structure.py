"""Atualiza estrutura da tabela notes e copia dados de notes_new

Revision ID: update_notes_structure
Create Date: 2024-05-13 05:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from datetime import datetime

# revision identifiers, used by Alembic
revision = 'update_notes_structure'
down_revision = 'add_notes_tables'  # Ajuste para o ID da sua última migração
branch_labels = None
depends_on = None

def upgrade():
    # 1. Criar tabela temporária com a estrutura correta
    op.create_table(
        'notes_temp',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('note_type', sa.String(20), nullable=False),
        sa.Column('category', sa.String(20), server_default='general', nullable=False),
        sa.Column('priority', sa.String(20), server_default='medium', nullable=False),
        sa.Column('report_status', sa.String(20), server_default='draft', nullable=False),
        sa.Column('project_id', sa.String(50), nullable=False),
        sa.Column('backlog_id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('report_date', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['task_id'], ['task.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['backlog_id'], ['backlog.id'], ondelete='CASCADE'),
        sa.CheckConstraint("note_type IN ('project', 'task')", name='ck_note_type'),
        sa.CheckConstraint(
            "category IN ('decision', 'risk', 'impediment', 'status_update', 'general')", 
            name='ck_note_category'
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high')", 
            name='ck_note_priority'
        ),
        sa.CheckConstraint(
            "report_status IN ('draft', 'ready_for_report', 'reported')", 
            name='ck_note_report_status'
        )
    )

    # 2. Criar índices na tabela temporária
    op.create_index('ix_notes_temp_project_id', 'notes_temp', ['project_id'])
    op.create_index('ix_notes_temp_task_id', 'notes_temp', ['task_id'])
    op.create_index('ix_notes_temp_created_at', 'notes_temp', ['created_at'])
    op.create_index('ix_notes_temp_report_date', 'notes_temp', ['report_date'])

    # 3. Copiar dados de notes_new para notes_temp com valores padrão
    conn = op.get_bind()
    conn.execute("""
        INSERT INTO notes_temp (
            id, content, note_type, category, priority, report_status,
            project_id, backlog_id, task_id, created_at, updated_at, report_date
        )
        SELECT 
            id, 
            content,
            'project' as note_type,  -- valor padrão
            'general' as category,    -- valor padrão
            'medium' as priority,     -- valor padrão
            'draft' as report_status, -- valor padrão
            '10237' as project_id,    -- valor do projeto atual
            4 as backlog_id,          -- valor do backlog atual
            NULL as task_id,          -- sem tarefa associada
            CURRENT_TIMESTAMP as created_at,
            CURRENT_TIMESTAMP as updated_at,
            NULL as report_date
        FROM notes_new
    """)

    # 4. Dropar a tabela notes original
    op.drop_table('notes')

    # 5. Renomear notes_temp para notes
    op.rename_table('notes_temp', 'notes')

def downgrade():
    # Não implementamos downgrade pois é uma migração de dados
    pass 