"""Adiciona backlog_id e atualiza project_id na tabela notes

Revision ID: update_notes_add_backlog_id
Create Date: 2024-05-13 05:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision = 'update_notes_add_backlog_id'
down_revision = 'add_notes_tables'  # Ajuste para o ID da sua última migração
branch_labels = None
depends_on = None

def upgrade():
    # Criamos uma tabela temporária com a nova estrutura
    op.create_table('notes_new',
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
        sa.ForeignKeyConstraint(['backlog_id'], ['backlog.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['task.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
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

    # Copiamos os dados da tabela antiga para a nova, atualizando project_id
    conn = op.get_bind()
    conn.execute("""
        INSERT INTO notes_new (
            id, content, note_type, category, priority, report_status,
            project_id, backlog_id, task_id, created_at, updated_at, report_date
        )
        SELECT 
            n.id, n.content, n.note_type, n.category, n.priority, n.report_status,
            b.project_id, -- Pega o project_id do backlog
            CAST(n.project_id AS INTEGER), -- O atual project_id vira backlog_id
            n.task_id, n.created_at, n.updated_at, n.report_date
        FROM notes n
        LEFT JOIN backlog b ON b.id = CAST(n.project_id AS INTEGER)
    """)

    # Removemos a tabela antiga
    op.drop_table('notes')

    # Renomeamos a nova tabela
    op.rename_table('notes_new', 'notes')

def downgrade():
    # Para reverter, precisamos fazer o processo inverso
    op.create_table('notes_old',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('note_type', sa.String(20), nullable=False),
        sa.Column('category', sa.String(20), server_default='general', nullable=False),
        sa.Column('priority', sa.String(20), server_default='medium', nullable=False),
        sa.Column('report_status', sa.String(20), server_default='draft', nullable=False),
        sa.Column('project_id', sa.String(50), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('report_date', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['task.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
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

    # Copiamos os dados de volta, usando backlog_id como project_id
    conn = op.get_bind()
    conn.execute("""
        INSERT INTO notes_old (
            id, content, note_type, category, priority, report_status,
            project_id, task_id, created_at, updated_at, report_date
        )
        SELECT 
            id, content, note_type, category, priority, report_status,
            backlog_id, -- backlog_id volta a ser project_id
            task_id, created_at, updated_at, report_date
        FROM notes
    """)

    # Removemos a tabela nova
    op.drop_table('notes')

    # Renomeamos a tabela antiga
    op.rename_table('notes_old', 'notes') 