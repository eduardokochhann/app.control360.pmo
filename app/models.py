from . import db  # Importa a instância db de app/__init__.py
from datetime import datetime
import enum

# Enum para Status da Tarefa (pode ser útil)
class TaskStatus(enum.Enum):
    TODO = 'A Fazer'
    IN_PROGRESS = 'Em Andamento'
    REVIEW = 'Revisão'
    DONE = 'Concluído'
    ARCHIVED = 'Arquivado'

# Tabela de Associação para Many-to-Many entre Tarefas e Sprints (se necessário)
# Se uma tarefa puder pertencer a múltiplas sprints (menos comum), usaríamos isso.
# Por simplicidade inicial, vamos assumir que uma tarefa pertence a uma sprint (ForeignKey em Task)

class Column(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    position = db.Column(db.Integer, nullable=False, default=0) # Para ordenar as colunas no board
    tasks = db.relationship('Task', backref='column', lazy=True, order_by='Task.position') # Tarefas nesta coluna

    def __repr__(self):
        return f'<Column {self.name}>'

class Sprint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    goal = db.Column(db.Text) # Objetivo da Sprint
    criticality = db.Column(db.String(50), nullable=False, server_default='Normal') # Usa server_default
    # Se tarefas pertencem a uma única sprint:
    tasks = db.relationship('Task', backref='sprint', lazy='dynamic', order_by='Task.position') # Ordena por posição

    def __repr__(self):
        return f'<Sprint {self.name}>'

class Backlog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Vincula ao ID do projeto externo (armazenado em JSON/Excel)
    # Usamos String assumindo que o ID do projeto pode não ser numérico. Ajuste se necessário.
    project_id = db.Column(db.String, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False, default='Backlog Principal') # Ex: Backlog do Projeto X
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tasks = db.relationship('Task', backref='backlog', lazy=True, order_by='Task.position') # Tarefas neste backlog

    def __repr__(self):
        return f'<Backlog {self.name} (Project: {self.project_id})>'

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.Enum(TaskStatus), default=TaskStatus.TODO, nullable=False)
    priority = db.Column(db.String(50), nullable=True, default='Média') # <<< NOVO CAMPO PRIORIDADE
    estimated_effort = db.Column(db.Float, nullable=True) # Esforço em horas, por exemplo
    position = db.Column(db.Integer, nullable=False, default=0) # Ordem da tarefa dentro da coluna/backlog
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    start_date = db.Column(db.DateTime, nullable=True) # Data de início planejada/real
    due_date = db.Column(db.DateTime, nullable=True) # Prazo (já existia)
    completed_at = db.Column(db.DateTime, nullable=True) # Data de conclusão real
    logged_time = db.Column(db.Float, nullable=True, default=0.0) # Tempo trabalhado registrado

    # <<< INÍCIO: Adicionar campo para especialista >>>
    specialist_name = db.Column(db.String(150), nullable=True, index=True) # Nome do especialista responsável
    # <<< FIM: Adicionar campo para especialista >>>

    # Chaves Estrangeiras
    backlog_id = db.Column(db.Integer, db.ForeignKey('backlog.id'), nullable=False)
    column_id = db.Column(db.Integer, db.ForeignKey('column.id'), nullable=False)
    sprint_id = db.Column(db.Integer, db.ForeignKey('sprint.id'), nullable=True) # Tarefa pode não estar em uma sprint

    # Relacionamentos já definidos via backref em Column, Sprint, Backlog

    def __repr__(self):
        return f'<Task {self.id}: {self.title}>'

# Você pode adicionar mais modelos ou campos conforme necessário (ex: Usuários, Comentários, Labels, etc.) 