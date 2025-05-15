"""initial migration

Revision ID: initial_migration
Revises: 
Create Date: 2024-05-14 20:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = 'initial_migration'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    # Cria a tabela de tags se não existir
    if 'tags' not in tables:
        op.create_table('tags',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=50), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )

    # Cria a tabela de notas se não existir
    if 'notes' not in tables:
        op.create_table('notes',
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

        # Cria índices para melhor performance
        op.create_index('ix_notes_project_id', 'notes', ['project_id'])
        op.create_index('ix_notes_task_id', 'notes', ['task_id'])
        op.create_index('ix_notes_created_at', 'notes', ['created_at'])
        op.create_index('ix_notes_report_date', 'notes', ['report_date'])

    # Cria a tabela de associação entre notas e tags se não existir
    if 'note_tags' not in tables:
        op.create_table('note_tags',
            sa.Column('note_id', sa.Integer(), nullable=False),
            sa.Column('tag_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['note_id'], ['notes.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('note_id', 'tag_id')
        )

def downgrade():
    # Remove as tabelas na ordem correta
    op.drop_table('note_tags')
    op.drop_table('notes')
    op.drop_table('tags') 