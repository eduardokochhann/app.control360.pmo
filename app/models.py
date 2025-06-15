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

    def to_dict(self):
        # Importar serialize_task aqui para evitar importação circular no nível do módulo,
        # assumindo que serialize_task pode depender de modelos definidos neste arquivo.
        # Uma melhor prática seria ter serialize_task em um arquivo de utils ou helpers.
        from app.backlog.routes import serialize_task 

        sprint_data = {
            'id': self.id,
            'name': self.name,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'goal': self.goal,
            'criticality': self.criticality,
            'tasks': [] # Inicializa com lista vazia
        }
        try:
            # .all() é necessário porque 'tasks' é lazy='dynamic'
            tasks_for_sprint = self.tasks.all() 
            sprint_data['tasks'] = [serialize_task(task) for task in tasks_for_sprint]
        except Exception as e:
            # Logar o erro seria ideal aqui.
            # Por enquanto, se houver erro na serialização das tarefas, 
            # retornamos a sprint com uma lista de tarefas vazia e um campo de erro.
            # Isso permite que o frontend ainda mostre a sprint, mesmo com erro nas tarefas.
            print(f"Erro ao serializar tarefas para a sprint {self.id}: {e}") # Log no servidor
            sprint_data['tasks'] = []
            sprint_data['error_serializing_tasks'] = str(e) # Adiciona um campo de erro

        return sprint_data

class Backlog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Vincula ao ID do projeto externo (armazenado em JSON/Excel)
    # Usamos String assumindo que o ID do projeto pode não ser numérico. Ajuste se necessário.
    project_id = db.Column(db.String, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False, default='Backlog Principal') # Ex: Backlog do Projeto X
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    available_for_sprint = db.Column(db.Boolean, nullable=False, server_default='1') # Adicionado
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
    priority = db.Column(db.String(50), nullable=True, default='Média')
    estimated_effort = db.Column(db.Float, nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    start_date = db.Column(db.DateTime, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    logged_time = db.Column(db.Float, nullable=True, default=0.0)
    actually_started_at = db.Column(db.DateTime, nullable=True)
    specialist_name = db.Column(db.String(150), nullable=True, index=True)
    is_generic = db.Column(db.Boolean, default=False, nullable=False, server_default='0')  # Campo para identificar tarefas genéricas
    is_unplanned = db.Column(db.Boolean, nullable=False, default=False, server_default='0') # NOVO CAMPO: Tarefa não programada

    # Chaves Estrangeiras
    backlog_id = db.Column(db.Integer, db.ForeignKey('backlog.id'), nullable=False)
    column_id = db.Column(db.Integer, db.ForeignKey('column.id'), nullable=False)
    sprint_id = db.Column(db.Integer, db.ForeignKey('sprint.id'), nullable=True)

    # Relacionamentos já definidos via backref em Column, Sprint, Backlog

    def __repr__(self):
        return f'<Task {self.id}: {self.title}>'

# <<< INÍCIO: NOVO MODELO TASKSEGMENT >>>
class TaskSegment(db.Model):
    __tablename__ = 'task_segment'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False, index=True)
    segment_start_datetime = db.Column(db.DateTime, nullable=False)
    segment_end_datetime = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    # order = db.Column(db.Integer, nullable=True) # Campo 'order' opcional, podemos adicionar depois se necessário

    # Relacionamento para que TaskSegment.task aponte para a Task pai
    # O backref 'segments' em Task permitirá Task.segments para acessar todos os segmentos
    task = db.relationship('Task', backref=db.backref('segments', lazy='dynamic', cascade="all, delete-orphan"))

    def __repr__(self):
        return f'<TaskSegment {self.id} for Task {self.task_id} from {self.segment_start_datetime} to {self.segment_end_datetime}>'

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'segment_start_datetime': self.segment_start_datetime.isoformat() if self.segment_start_datetime else None,
            'segment_end_datetime': self.segment_end_datetime.isoformat() if self.segment_end_datetime else None,
            'description': self.description
            # Adicionar 'order' se o campo for incluído
        }
# <<< FIM: NOVO MODELO TASKSEGMENT >>>

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
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'planned_date': self.planned_date.strftime('%Y-%m-%d') if self.planned_date else None,
            'actual_date': self.actual_date.strftime('%Y-%m-%d') if self.actual_date else None,
            'status': self.status.value,
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
    IDENTIFIED = 'Identificado'
    MITIGATED = 'Mitigado'
    RESOLVED = 'Resolvido'
    ACCEPTED = 'Aceito'

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
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    impact = db.Column(db.Enum(RiskImpact), default=RiskImpact.MEDIUM, nullable=False)
    probability = db.Column(db.Enum(RiskProbability), default=RiskProbability.MEDIUM, nullable=False)
    status = db.Column(db.Enum(RiskStatus), default=RiskStatus.IDENTIFIED, nullable=False)
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
            'title': self.title,
            'description': self.description,
            'impact': {'key': self.impact.name, 'value': self.impact.value},
            'probability': {'key': self.probability.name, 'value': self.probability.value},
            'status': {'key': self.status.name, 'value': self.status.value},
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
        return f'<ProjectRisk {self.id}: {self.title[:30]}...>'
# --- FIM NOVO MODELO RISCOS ---

# Enums para o sistema de notas
class NoteType(enum.Enum):
    PROJECT = 'project'
    TASK = 'task'

class NoteCategory(enum.Enum):
    DECISION = 'decision'
    RISK = 'risk'
    IMPEDIMENT = 'impediment'
    STATUS_UPDATE = 'status_update'
    GENERAL = 'general'

class NotePriority(enum.Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'

class NoteReportStatus(enum.Enum):
    DRAFT = 'draft'
    READY_FOR_REPORT = 'ready_for_report'
    REPORTED = 'reported'

# Tabela de associação para tags
note_tags = db.Table('note_tags',
    db.Column('note_id', db.Integer, db.ForeignKey('notes.id', ondelete='CASCADE'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True)
)

class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Tag {self.name}>'

class Note(db.Model):
    __tablename__ = 'notes'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    note_type = db.Column(db.String(20), nullable=False)  # 'project' ou 'task'
    category = db.Column(db.String(20), nullable=False, server_default='general')  # 'decision', 'risk', etc.
    priority = db.Column(db.String(20), nullable=False, server_default='medium')  # 'low', 'medium', 'high'
    report_status = db.Column(db.String(20), nullable=False, server_default='draft')  # 'draft', 'ready_for_report', 'reported'
    
    # NOVO: Flag para controlar se a nota aparece no Status Report
    # Por padrão True (opt-out) - todas as notas aparecem a menos que marcadas como False
    include_in_status_report = db.Column(db.Boolean, nullable=False, server_default='1')
    
    # Relacionamentos
    project_id = db.Column(db.String(50), nullable=False)  # ID do projeto (ex: 10237)
    backlog_id = db.Column(db.Integer, db.ForeignKey('backlog.id', ondelete='CASCADE'), nullable=False)  # ID do backlog
    task_id = db.Column(db.Integer, db.ForeignKey('task.id', ondelete='CASCADE'), nullable=True)
    
    # Campos de controle
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    report_date = db.Column(db.DateTime, nullable=True)
    event_date = db.Column(db.Date, nullable=True)
    
    # Relacionamentos
    tags = db.relationship('Tag', secondary=note_tags, lazy='subquery',
                         backref=db.backref('notes', lazy=True))
    task = db.relationship('Task', backref=db.backref('notes', lazy=True, cascade="all, delete-orphan"))
    backlog = db.relationship('Backlog', backref=db.backref('notes', lazy=True, cascade="all, delete-orphan"))

    # Validações via CheckConstraint
    __table_args__ = (
        db.CheckConstraint("note_type IN ('project', 'task')", name='ck_note_type'),
        db.CheckConstraint(
            "category IN ('decision', 'risk', 'impediment', 'status_update', 'general')", 
            name='ck_note_category'
        ),
        db.CheckConstraint(
            "priority IN ('low', 'medium', 'high')", 
            name='ck_note_priority'
        ),
        db.CheckConstraint(
            "report_status IN ('draft', 'ready_for_report', 'reported')", 
            name='ck_note_report_status'
        )
    )

    def __repr__(self):
        return f'<Note {self.id}: {self.note_type}>'

    def to_dict(self):
        """Converte a nota para um dicionário."""
        return {
            'id': self.id,
            'content': self.content,
            'note_type': self.note_type,
            'category': self.category,
            'priority': self.priority,
            'report_status': self.report_status,
            'include_in_status_report': self.include_in_status_report,
            'project_id': self.project_id,
            'backlog_id': self.backlog_id,
            'task_id': self.task_id,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'updated_at': self.updated_at.isoformat() + 'Z' if self.updated_at else None,
            'report_date': self.report_date.isoformat() if self.report_date else None,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'tags': [tag.name for tag in self.tags],
            'task_title': self.task.title if self.task else None
        } 