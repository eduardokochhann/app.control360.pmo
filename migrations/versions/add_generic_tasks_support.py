"""add_generic_tasks_support

Revision ID: add_generic_tasks_support
Revises: None
Create Date: 2024-05-13 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = 'add_generic_tasks_support'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Verifica se a coluna is_generic já existe
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    columns = [col['name'] for col in inspector.get_columns('task')]
    
    if 'is_generic' not in columns:
        # Adiciona a coluna is_generic apenas se ela não existir
        op.add_column('task', sa.Column('is_generic', sa.Boolean(), nullable=False, server_default='false'))
    
    # Para SQLite, precisamos recriar a tabela para alterar as constraints
    # 1. Criar tabela temporária
    op.execute('''
        CREATE TABLE task_temp (
            id INTEGER NOT NULL PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            status VARCHAR(50) NOT NULL,
            priority VARCHAR(50),
            estimated_effort FLOAT,
            position INTEGER NOT NULL,
            created_at DATETIME,
            updated_at DATETIME,
            start_date DATETIME,
            due_date DATETIME,
            completed_at DATETIME,
            logged_time FLOAT,
            actually_started_at DATETIME,
            specialist_name VARCHAR(150),
            is_generic BOOLEAN NOT NULL DEFAULT false,
            backlog_id INTEGER,
            column_id INTEGER,
            sprint_id INTEGER,
            FOREIGN KEY(backlog_id) REFERENCES backlog (id),
            FOREIGN KEY(column_id) REFERENCES column (id),
            FOREIGN KEY(sprint_id) REFERENCES sprint (id)
        )
    ''')
    
    # 2. Copiar dados
    op.execute('''
        INSERT INTO task_temp 
        SELECT id, title, description, status, priority, estimated_effort, position,
               created_at, updated_at, start_date, due_date, completed_at, logged_time,
               actually_started_at, specialist_name, is_generic, backlog_id, column_id, sprint_id
        FROM task
    ''')
    
    # 3. Dropar tabela antiga
    op.execute('DROP TABLE task')
    
    # 4. Renomear tabela temporária
    op.execute('ALTER TABLE task_temp RENAME TO task')

def downgrade():
    # Para SQLite, precisamos recriar a tabela para reverter as alterações
    # 1. Criar tabela temporária com constraints originais
    op.execute('''
        CREATE TABLE task_temp (
            id INTEGER NOT NULL PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            status VARCHAR(50) NOT NULL,
            priority VARCHAR(50),
            estimated_effort FLOAT,
            position INTEGER NOT NULL,
            created_at DATETIME,
            updated_at DATETIME,
            start_date DATETIME,
            due_date DATETIME,
            completed_at DATETIME,
            logged_time FLOAT,
            actually_started_at DATETIME,
            specialist_name VARCHAR(150),
            backlog_id INTEGER NOT NULL,
            column_id INTEGER NOT NULL,
            sprint_id INTEGER,
            FOREIGN KEY(backlog_id) REFERENCES backlog (id),
            FOREIGN KEY(column_id) REFERENCES column (id),
            FOREIGN KEY(sprint_id) REFERENCES sprint (id)
        )
    ''')
    
    # 2. Copiar dados (ignorando is_generic)
    op.execute('''
        INSERT INTO task_temp 
        SELECT id, title, description, status, priority, estimated_effort, position,
               created_at, updated_at, start_date, due_date, completed_at, logged_time,
               actually_started_at, specialist_name, backlog_id, column_id, sprint_id
        FROM task
    ''')
    
    # 3. Dropar tabela antiga
    op.execute('DROP TABLE task')
    
    # 4. Renomear tabela temporária
    op.execute('ALTER TABLE task_temp RENAME TO task') 