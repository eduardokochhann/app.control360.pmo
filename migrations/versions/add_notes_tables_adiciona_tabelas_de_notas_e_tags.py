"""Adiciona tabelas de notas e tags

Revision ID: add_notes_tables
Revises: 
Create Date: 2024-05-13 00:17:34.611

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_notes_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Cria a tabela de tags
    op.create_table('tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Cria a tabela de notas
    op.create_table('notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('note_type', sa.String(length=20), nullable=False),
        sa.Column('category', sa.String(length=20), server_default='general', nullable=False),
        sa.Column('priority', sa.String(length=20), server_default='medium', nullable=False),
        sa.Column('report_status', sa.String(length=20), server_default='draft', nullable=False),
        sa.Column('project_id', sa.String(length=50), nullable=False),
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

    # Cria a tabela de associação entre notas e tags
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
