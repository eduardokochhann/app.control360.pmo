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

# --- NOVOS ENUMS PARA MARCOS ---
class MilestoneStatus(enum.Enum):
    PENDING = 'Pendente'
    IN_PROGRESS = 'Em Andamento'
    COMPLETED = 'Concluído'
    DELAYED = 'Atrasado'

class MilestoneCriticality(enum.Enum):
    LOW = 'Baixa'
    MEDIUM = 'Média'
    HIGH = 'Alta'
    CRITICAL = 'Crítica'
# --- FIM NOVOS ENUMS ---

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

    # --- NOVO RELACIONAMENTO PARA MARCOS E RISCOS ---
    milestones = db.relationship('ProjectMilestone', backref='backlog', lazy=True, cascade="all, delete-orphan")
    risks = db.relationship('ProjectRisk', backref='backlog', lazy=True, cascade="all, delete-orphan")
    # --- FIM NOVO RELACIONAMENTO ---

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

# --- NOVO MODELO PARA MARCOS DO PROJETO ---
class ProjectMilestone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    planned_date = db.Column(db.Date, nullable=False)
    actual_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.Enum(MilestoneStatus), default=MilestoneStatus.PENDING, nullable=False)
    criticality = db.Column(db.Enum(MilestoneCriticality), default=MilestoneCriticality.MEDIUM, nullable=False)
    is_checkpoint = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Chave Estrangeira para Backlog
    backlog_id = db.Column(db.Integer, db.ForeignKey('backlog.id'), nullable=False)

    # Propriedade para verificar se está atrasado
    @property
    def is_delayed(self):
        # Está atrasado se a data planejada passou, não tem data real e não está concluído
        return (self.planned_date < datetime.utcnow().date() and 
                self.actual_date is None and 
                self.status != MilestoneStatus.COMPLETED)

    def to_dict(self):
        """Serializa o objeto Milestone para um dicionário."""
        current_status = self.status.value
        if self.is_delayed and self.status != MilestoneStatus.DELAYED:
            current_status = MilestoneStatus.DELAYED.value
        elif not self.is_delayed and self.status == MilestoneStatus.DELAYED:
            current_status = MilestoneStatus.PENDING.value

        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'planned_date': self.planned_date.strftime('%Y-%m-%d') if self.planned_date else None,
            'actual_date': self.actual_date.strftime('%Y-%m-%d') if self.actual_date else None,
            'status': current_status,
            'criticality': self.criticality.value,
            'is_checkpoint': self.is_checkpoint,
            'is_delayed': self.is_delayed,
            'backlog_id': self.backlog_id
        }

    def __repr__(self):
        return f'<ProjectMilestone {self.id}: {self.name}>'
# --- FIM NOVO MODELO MARCOS ---

# --- NOVO MODELO PARA RISCOS DO PROJETO (Estrutura básica) ---
# Enums para Riscos (se ainda não existirem)
class RiskStatus(enum.Enum):
    ACTIVE = 'Ativo'
    MITIGATED = 'Mitigado'
    RESOLVED = 'Resolvido'

class RiskImpact(enum.Enum):
    LOW = 'Baixo'
    MEDIUM = 'Médio'
    HIGH = 'Alto'

class RiskProbability(enum.Enum):
    LOW = 'Baixa'
    MEDIUM = 'Média'
    HIGH = 'Alta'

class ProjectRisk(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.Text, nullable=False)
    impact = db.Column(db.Enum(RiskImpact), default=RiskImpact.MEDIUM, nullable=False)
    probability = db.Column(db.Enum(RiskProbability), default=RiskProbability.MEDIUM, nullable=False)
    status = db.Column(db.Enum(RiskStatus), default=RiskStatus.ACTIVE, nullable=False)
    identified_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resolved_date = db.Column(db.DateTime, nullable=True)
    mitigation_plan = db.Column(db.Text)
    contingency_plan = db.Column(db.Text)
    responsible = db.Column(db.String(150))
    trend = db.Column(db.String(50), default='Estável') # Ex: Aumentando, Diminuindo, Estável
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Chave Estrangeira para Backlog
    backlog_id = db.Column(db.Integer, db.ForeignKey('backlog.id'), nullable=False)

    # Propriedade para calcular Severidade (exemplo)
    @property
    def severity(self):
        impact_map = {RiskImpact.LOW: 1, RiskImpact.MEDIUM: 2, RiskImpact.HIGH: 3}
        prob_map = {RiskProbability.LOW: 1, RiskProbability.MEDIUM: 2, RiskProbability.HIGH: 3}
        score = impact_map.get(self.impact, 0) * prob_map.get(self.probability, 0)
        if score >= 6:
            return 'Crítico'
        elif score >= 4:
            return 'Alto'
        elif score >= 2:
            return 'Médio'
        else:
            return 'Baixo'

    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'impact': self.impact.value,
            'probability': self.probability.value,
            'status': self.status.value,
            'identified_date': self.identified_date.strftime('%Y-%m-%d') if self.identified_date else None,
            'resolved_date': self.resolved_date.strftime('%Y-%m-%d') if self.resolved_date else None,
            'mitigation_plan': self.mitigation_plan,
            'contingency_plan': self.contingency_plan,
            'responsible': self.responsible,
            'trend': self.trend,
            'severity': self.severity, # Usa a propriedade
            'backlog_id': self.backlog_id
        }

    def __repr__(self):
        return f'<ProjectRisk {self.id}: {self.description[:30]}...>'
# --- FIM NOVO MODELO RISCOS --- 