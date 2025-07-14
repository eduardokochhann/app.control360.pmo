# -*- coding: utf-8 -*-
from . import db  # Importa a instância db de app/__init__.py
from datetime import datetime
import enum
import pytz

# Define o fuso horário brasileiro
br_timezone = pytz.timezone('America/Sao_Paulo')

def get_brasilia_now():
    """Retorna datetime atual no fuso horário de Brasília."""
    return datetime.now(br_timezone)

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

# --- NOVOS ENUMS PARA FASES DE PROJETOS ---
class ProjectType(enum.Enum):
    WATERFALL = 'waterfall'
    AGILE = 'agile'

class PhaseStatus(enum.Enum):
    NOT_STARTED = 'Não Iniciada'
    IN_PROGRESS = 'Em Andamento'
    COMPLETED = 'Concluída'
    SKIPPED = 'Pulada'
# --- FIM NOVOS ENUMS FASES ---

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
    
    # Campos de arquivamento
    is_archived = db.Column(db.Boolean, nullable=False, default=False, server_default='0')
    archived_at = db.Column(db.DateTime, nullable=True)
    archived_by = db.Column(db.String(150), nullable=True)
    
    # Se tarefas pertencem a uma única sprint:
    tasks = db.relationship('Task', backref='sprint', lazy='dynamic', order_by='Task.position') # Ordena por posição

    def __repr__(self):
        return f'<Sprint {self.name}>'

    def to_dict(self):
        """Serializa a sprint para dicionário sem importação circular."""
        sprint_data = {
            'id': self.id,
            'name': self.name,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'goal': self.goal,
            'criticality': self.criticality,
            'is_archived': self.is_archived,
            'archived_at': self.archived_at.isoformat() if self.archived_at else None,
            'archived_by': self.archived_by,
            'tasks': [] # Inicializa com lista vazia
        }
        
        try:
            # Usa o serializer otimizado para evitar importação circular
            from app.utils.serializers import serialize_task_for_sprints
            # .all() é necessário porque 'tasks' é lazy='dynamic'
            tasks_for_sprint = self.tasks.all() 
            sprint_data['tasks'] = [serialize_task_for_sprints(task) for task in tasks_for_sprint]
        except Exception as e:
            # Log do erro de forma segura
            from flask import current_app
            if current_app:
                current_app.logger.error(f"Erro ao serializar tarefas para a sprint {self.id}: {e}")
            sprint_data['tasks'] = []
            sprint_data['error_serializing_tasks'] = str(e)

        return sprint_data

class Backlog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Vincula ao ID do projeto externo (armazenado em JSON/Excel)
    # Usamos String assumindo que o ID do projeto pode não ser numérico. Ajuste se necessário.
    project_id = db.Column(db.String, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False, default='Backlog Principal') # Ex: Backlog do Projeto X
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=get_brasilia_now)
    available_for_sprint = db.Column(db.Boolean, nullable=False, server_default='1') # Adicionado
    tasks = db.relationship('Task', backref='backlog', lazy=True, order_by='Task.position') # Tarefas neste backlog

    # --- NOVOS CAMPOS PARA GESTÃO DE FASES ---
    project_type = db.Column(db.Enum(ProjectType), nullable=True, default=None) # waterfall ou agile
    current_phase = db.Column(db.Integer, nullable=False, default=1, server_default='1') # Fase atual (1-N)
    phases_config = db.Column(db.Text, nullable=True) # JSON com configuração das fases
    phase_started_at = db.Column(db.DateTime, nullable=True) # Quando a fase atual começou
    # --- FIM NOVOS CAMPOS FASES ---

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
    created_at = db.Column(db.DateTime, default=get_brasilia_now)
    updated_at = db.Column(db.DateTime, default=get_brasilia_now, onupdate=get_brasilia_now)
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
    created_at = db.Column(db.DateTime, default=get_brasilia_now)
    updated_at = db.Column(db.DateTime, default=get_brasilia_now, onupdate=get_brasilia_now)
    
    # --- NOVO CAMPO PARA DATA DE INÍCIO ---
    started_at = db.Column(db.DateTime, nullable=True) # Quando o marco foi colocado em andamento
    # --- FIM NOVO CAMPO ---

    # --- NOVOS CAMPOS PARA GATILHOS DE FASE ---
    triggers_next_phase = db.Column(db.Boolean, default=False, nullable=False, server_default='0') # Se marco dispara próxima fase
    phase_order = db.Column(db.Integer, nullable=True) # Ordem do marco na sequência de fases
    auto_created = db.Column(db.Boolean, default=False, nullable=False, server_default='0') # Se foi criado automaticamente
    # --- FIM NOVOS CAMPOS GATILHOS ---

    # Chave Estrangeira para Backlog
    backlog_id = db.Column(db.Integer, db.ForeignKey('backlog.id'), nullable=False)

    # Propriedade para verificar se está atrasado
    @property
    def is_delayed(self):
        # Está atrasado se a data planejada passou, não tem data real e não está concluído
        return (self.planned_date < get_brasilia_now().date() and 
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
            'started_at': self.started_at.strftime('%Y-%m-%d %H:%M:%S') if self.started_at else None,
            'status': {'key': self.status.name, 'value': self.status.value},
            'criticality': {'key': self.criticality.name, 'value': self.criticality.value},
            'is_checkpoint': self.is_checkpoint,
            'is_delayed': self.is_delayed,
            'backlog_id': self.backlog_id,
            'triggers_next_phase': self.triggers_next_phase,
            'phase_order': self.phase_order,
            'auto_created': self.auto_created
        }

    def __repr__(self):
        return f'<ProjectMilestone {self.id}: {self.name}>'
# --- FIM NOVO MODELO MARCOS ---

# --- NOVO MODELO PARA CONFIGURAÇÃO DE FASES ---
class ProjectPhaseConfiguration(db.Model):
    """Modelo para configurar fases de projetos (Waterfall/Ágil)"""
    __tablename__ = 'project_phase_configuration'
    
    id = db.Column(db.Integer, primary_key=True)
    project_type = db.Column(db.Enum(ProjectType), nullable=False) # waterfall ou agile
    phase_number = db.Column(db.Integer, nullable=False) # Número da fase (1, 2, 3, ...)
    phase_name = db.Column(db.String(100), nullable=False) # Nome da fase (ex: "Planejamento")
    phase_description = db.Column(db.Text, nullable=True) # Descrição da fase
    phase_color = db.Column(db.String(20), nullable=True, default='#E8F5E8') # Cor para exibição
    milestone_names = db.Column(db.Text, nullable=True) # JSON com nomes dos marcos desta fase
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default='1')
    created_at = db.Column(db.DateTime, default=get_brasilia_now)
    updated_at = db.Column(db.DateTime, default=get_brasilia_now, onupdate=get_brasilia_now)
    
    # Índice único para evitar fases duplicadas
    __table_args__ = (
        db.UniqueConstraint('project_type', 'phase_number', name='uq_project_type_phase'),
    )

    def get_milestone_names(self):
        """Retorna lista de nomes dos marcos desta fase"""
        if not self.milestone_names:
            return []
        try:
            import json
            return json.loads(self.milestone_names)
        except:
            return []

    def set_milestone_names(self, names_list):
        """Define lista de nomes dos marcos desta fase"""
        import json
        self.milestone_names = json.dumps(names_list) if names_list else None

    def to_dict(self):
        """Serializa configuração de fase para dicionário"""
        return {
            'id': self.id,
            'project_type': self.project_type.value if self.project_type else None,
            'phase_number': self.phase_number,
            'phase_name': self.phase_name,
            'phase_description': self.phase_description,
            'phase_color': self.phase_color,
            'milestone_names': self.get_milestone_names(),
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f'<ProjectPhaseConfiguration {self.project_type.value if self.project_type else "None"} - Fase {self.phase_number}: {self.phase_name}>'

    @staticmethod
    def get_phases_for_type(project_type):
        """Retorna todas as fases configuradas para um tipo de projeto"""
        return ProjectPhaseConfiguration.query.filter_by(
            project_type=project_type, 
            is_active=True
        ).order_by(ProjectPhaseConfiguration.phase_number).all()

    @staticmethod
    def initialize_default_phases():
        """Inicializa configurações padrão de fases se não existirem"""
        from flask import current_app
        from .. import db
        
        # Configurações padrão Waterfall
        waterfall_phases = [
            {'phase_number': 1, 'phase_name': 'Planejamento', 'phase_color': '#E8F5E8', 'milestone_names': ['Milestone Start']},
            {'phase_number': 2, 'phase_name': 'Execução', 'phase_color': '#E8F0FF', 'milestone_names': ['Milestone Setup']},
            {'phase_number': 3, 'phase_name': 'CutOver', 'phase_color': '#FFF8E1', 'milestone_names': ['Milestone CutOver']},
            {'phase_number': 4, 'phase_name': 'GoLive', 'phase_color': '#E8FFE8', 'milestone_names': ['Milestone Finish Project']}
        ]
        
        # Configurações padrão Ágil
        agile_phases = [
            {'phase_number': 1, 'phase_name': 'Planejamento', 'phase_color': '#E8F5E8', 'milestone_names': ['Milestone Start']},
            {'phase_number': 2, 'phase_name': 'Sprint Planning', 'phase_color': '#F0F8FF', 'milestone_names': ['Milestone Setup']},
            {'phase_number': 3, 'phase_name': 'Desenvolvimento', 'phase_color': '#E8F0FF', 'milestone_names': ['Milestone Developer']},
            {'phase_number': 4, 'phase_name': 'CutOver', 'phase_color': '#FFF8E1', 'milestone_names': ['Milestone CutOver']},
            {'phase_number': 5, 'phase_name': 'GoLive', 'phase_color': '#E8FFE8', 'milestone_names': ['Milestone Finish Project']}
        ]
        
        try:
            # Verifica se já existem configurações
            if ProjectPhaseConfiguration.query.count() == 0:
                import json
                
                # Criar fases Waterfall
                for phase_config in waterfall_phases:
                    phase = ProjectPhaseConfiguration(
                        project_type=ProjectType.WATERFALL,
                        phase_number=phase_config['phase_number'],
                        phase_name=phase_config['phase_name'],
                        phase_color=phase_config['phase_color'],
                        milestone_names=json.dumps(phase_config['milestone_names'])
                    )
                    db.session.add(phase)
                
                # Criar fases Ágil
                for phase_config in agile_phases:
                    phase = ProjectPhaseConfiguration(
                        project_type=ProjectType.AGILE,
                        phase_number=phase_config['phase_number'],
                        phase_name=phase_config['phase_name'],
                        phase_color=phase_config['phase_color'],
                        milestone_names=json.dumps(phase_config['milestone_names'])
                    )
                    db.session.add(phase)
                
                db.session.commit()
                if current_app:
                    current_app.logger.info("Configurações padrão de fases de projeto inicializadas com sucesso")
                    
        except Exception as e:
            db.session.rollback()
            if current_app:
                current_app.logger.error(f"Erro ao inicializar configurações padrão de fases: {e}")
# --- FIM NOVO MODELO CONFIGURAÇÃO FASES ---

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
    identified_date = db.Column(db.DateTime, default=get_brasilia_now, nullable=False)
    resolved_date = db.Column(db.DateTime, nullable=True)
    mitigation_plan = db.Column(db.Text)
    contingency_plan = db.Column(db.Text)
    responsible = db.Column(db.String(150))
    trend = db.Column(db.String(50), default='Estável') # Ex: Aumentando, Diminuindo, Estável
    created_at = db.Column(db.DateTime, default=get_brasilia_now)
    updated_at = db.Column(db.DateTime, default=get_brasilia_now, onupdate=get_brasilia_now)

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
    created_at = db.Column(db.DateTime, default=get_brasilia_now)

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
    created_at = db.Column(db.DateTime, default=get_brasilia_now)
    updated_at = db.Column(db.DateTime, default=get_brasilia_now, onupdate=get_brasilia_now)
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

# --- SISTEMA DE COMPLEXIDADE DE PROJETOS ---

class ComplexityCategory(enum.Enum):
    BAIXA = 'Baixa'
    MÉDIA = 'Média'
    ALTA = 'Alta'

class ComplexityCriteria(db.Model):
    __tablename__ = 'complexity_criteria'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=get_brasilia_now)
    criteria_order = db.Column(db.Integer, default=0)
    
    options = db.relationship('ComplexityCriteriaOption', backref='criteria', lazy=True, order_by='ComplexityCriteriaOption.option_order')

    def __repr__(self):
        return f'<ComplexityCriteria {self.name}>'

class ComplexityCriteriaOption(db.Model):
    __tablename__ = 'complexity_criteria_option'
    id = db.Column(db.Integer, primary_key=True)
    criteria_id = db.Column(db.Integer, db.ForeignKey('complexity_criteria.id'), nullable=False)
    option_name = db.Column(db.String(100), nullable=False)
    points = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    option_label = db.Column(db.String(100))
    option_order = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<ComplexityCriteriaOption {self.option_name} ({self.points}pts)>'

class ProjectComplexityAssessment(db.Model):
    __tablename__ = 'project_complexity_assessment'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(50), nullable=False, index=True)
    backlog_id = db.Column(db.Integer, nullable=False, index=True)
    total_score = db.Column(db.Integer, nullable=False)
    complexity_category = db.Column(db.String(20), nullable=False)
    assessed_by = db.Column(db.String(150), nullable=False)
    assessment_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=get_brasilia_now)
    updated_at = db.Column(db.DateTime, default=get_brasilia_now)
    category = db.Column(db.String(20))
    notes = db.Column(db.Text)

    details = db.relationship('ProjectComplexityAssessmentDetail', backref='assessment', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<ProjectComplexityAssessment Project:{self.project_id} Score:{self.total_score} Category:{self.complexity_category}>'

class ProjectComplexityAssessmentDetail(db.Model):
    __tablename__ = 'project_complexity_assessment_detail'
    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('project_complexity_assessment.id'), nullable=False)
    criteria_id = db.Column(db.Integer, nullable=False)
    selected_option_id = db.Column(db.Integer, nullable=False)
    points_awarded = db.Column(db.Integer, nullable=False)
    option_id = db.Column(db.Integer)
    score = db.Column(db.Integer)

    def __repr__(self):
        return f'<AssessmentDetail criteria:{self.criteria_id} option:{self.selected_option_id} ({self.points_awarded}pts)>'

class ComplexityThreshold(db.Model):
    __tablename__ = 'complexity_threshold'
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.Enum(ComplexityCategory), nullable=False, unique=True)
    min_score = db.Column(db.Integer, nullable=False)
    max_score = db.Column(db.Integer, nullable=True)  # NULL para categoria mais alta
    
    def __repr__(self):
        return f'<ComplexityThreshold {self.category.value}: {self.min_score}-{self.max_score or "∞"}>'

# --- FIM SISTEMA DE COMPLEXIDADE ---

# Tabela de associação para tags das notas (many-to-many)

# --- NOVO MODELO PARA CONFIGURAÇÕES DE ESPECIALISTAS ---
class SpecialistConfiguration(db.Model):
    """Configurações individuais por especialista para cálculo de datas e capacidade."""
    __tablename__ = 'specialist_configuration'
    
    id = db.Column(db.Integer, primary_key=True)
    specialist_name = db.Column(db.String(150), nullable=False, unique=True, index=True)
    
    # Configurações de jornada de trabalho
    daily_work_hours = db.Column(db.Float, nullable=False, default=8.0, server_default='8.0')  # Horas por dia
    weekly_work_days = db.Column(db.Integer, nullable=False, default=5, server_default='5')    # Dias por semana
    
    # Configurações de dias úteis (JSON para flexibilidade)
    # Formato: {"monday": true, "tuesday": true, ..., "sunday": false}
    work_days_config = db.Column(db.Text, nullable=False, 
                                default='{"monday": true, "tuesday": true, "wednesday": true, "thursday": true, "friday": true, "saturday": false, "sunday": false}')
    
    # Configurações de feriados e exceções
    consider_holidays = db.Column(db.Boolean, nullable=False, default=True, server_default='1')
    custom_holidays = db.Column(db.Text, nullable=True)  # JSON com feriados específicos
    
    # Configurações de buffer e margem
    buffer_percentage = db.Column(db.Float, nullable=False, default=10.0, server_default='10.0')  # % de buffer nas estimativas
    
    # Configurações de timezone (se necessário)
    timezone = db.Column(db.String(50), nullable=False, default='America/Sao_Paulo', server_default='America/Sao_Paulo')
    
    # Campos de controle
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default='1')
    created_at = db.Column(db.DateTime, default=get_brasilia_now)
    updated_at = db.Column(db.DateTime, default=get_brasilia_now, onupdate=get_brasilia_now)
    
    def __repr__(self):
        return f'<SpecialistConfiguration {self.specialist_name}>'
    
    def get_work_days_config(self):
        """Retorna configuração de dias úteis como dict."""
        import json
        try:
            return json.loads(self.work_days_config)
        except:
            # Fallback para configuração padrão
            return {
                "monday": True, "tuesday": True, "wednesday": True, 
                "thursday": True, "friday": True, "saturday": False, "sunday": False
            }
    
    def set_work_days_config(self, config_dict):
        """Define configuração de dias úteis a partir de dict."""
        import json
        self.work_days_config = json.dumps(config_dict)
    
    def get_custom_holidays(self):
        """Retorna feriados personalizados como lista."""
        import json
        try:
            return json.loads(self.custom_holidays) if self.custom_holidays else []
        except:
            return []
    
    def set_custom_holidays(self, holidays_list):
        """Define feriados personalizados a partir de lista."""
        import json
        self.custom_holidays = json.dumps(holidays_list)
    
    def to_dict(self):
        """Serializa configuração para dict."""
        return {
            'id': self.id,
            'specialist_name': self.specialist_name,
            'daily_work_hours': self.daily_work_hours,
            'weekly_work_days': self.weekly_work_days,
            'work_days_config': self.get_work_days_config(),
            'consider_holidays': self.consider_holidays,
            'custom_holidays': self.get_custom_holidays(),
            'buffer_percentage': self.buffer_percentage,
            'timezone': self.timezone,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @staticmethod
    def get_or_create_config(specialist_name):
        """Obtém configuração existente ou cria uma padrão."""
        config = SpecialistConfiguration.query.filter_by(specialist_name=specialist_name).first()
        if not config:
            config = SpecialistConfiguration(specialist_name=specialist_name)
            db.session.add(config)
            db.session.commit()
        return config
# --- FIM CONFIGURAÇÕES DE ESPECIALISTAS ---

# --- SISTEMA DE CONFIGURAÇÃO DE MÓDULOS ---
class ModuleType(enum.Enum):
    MODULE = 'module'        # Módulo completo
    FEATURE = 'feature'      # Funcionalidade específica
    DASHBOARD = 'dashboard'  # Dashboard/relatório

class ModuleConfiguration(db.Model):
    """Configurações de módulos e funcionalidades do sistema."""
    __tablename__ = 'module_configuration'
    
    id = db.Column(db.Integer, primary_key=True)
    module_key = db.Column(db.String(100), nullable=False, unique=True, index=True)  # Ex: 'gerencial', 'macro.status_report'
    display_name = db.Column(db.String(150), nullable=False)  # Nome para exibição
    description = db.Column(db.Text)  # Descrição do módulo/funcionalidade
    module_type = db.Column(db.Enum(ModuleType), nullable=False, default=ModuleType.MODULE)
    
    # Configurações de habilitação
    is_enabled = db.Column(db.Boolean, nullable=False, default=True, server_default='1')
    requires_authentication = db.Column(db.Boolean, nullable=False, default=True, server_default='1')
    
    # Hierarquia e dependências
    parent_module = db.Column(db.String(100), nullable=True)  # Módulo pai (se for sub-funcionalidade)
    dependencies = db.Column(db.Text, nullable=True)  # JSON com dependências de outros módulos
    
    # Informações de exibição
    icon = db.Column(db.String(100), nullable=True)  # Ícone do FontAwesome
    color = db.Column(db.String(20), nullable=True)  # Cor do card/botão
    display_order = db.Column(db.Integer, nullable=False, default=0)  # Ordem de exibição
    
    # Configurações de acesso
    allowed_roles = db.Column(db.Text, nullable=True)  # JSON com roles permitidos
    maintenance_mode = db.Column(db.Boolean, nullable=False, default=False, server_default='0')
    maintenance_message = db.Column(db.Text, nullable=True)
    
    # Campos de controle
    created_at = db.Column(db.DateTime, default=get_brasilia_now)
    updated_at = db.Column(db.DateTime, default=get_brasilia_now, onupdate=get_brasilia_now)
    created_by = db.Column(db.String(150), nullable=True)
    updated_by = db.Column(db.String(150), nullable=True)
    
    def __repr__(self):
        return f'<ModuleConfiguration {self.module_key}: {self.display_name}>'
    
    def get_dependencies(self):
        """Retorna lista de dependências."""
        import json
        try:
            return json.loads(self.dependencies) if self.dependencies else []
        except:
            return []
    
    def set_dependencies(self, deps_list):
        """Define dependências a partir de lista."""
        import json
        self.dependencies = json.dumps(deps_list)
    
    def get_allowed_roles(self):
        """Retorna lista de roles permitidos."""
        import json
        try:
            return json.loads(self.allowed_roles) if self.allowed_roles else ['admin', 'user']
        except:
            return ['admin', 'user']
    
    def set_allowed_roles(self, roles_list):
        """Define roles permitidos a partir de lista."""
        import json
        self.allowed_roles = json.dumps(roles_list)
    
    @property
    def is_available(self):
        """Verifica se o módulo está disponível (habilitado e não em manutenção)."""
        if not self.is_enabled:
            return False
        
        # Se tem dependências, verifica se todas estão habilitadas
        dependencies = self.get_dependencies()
        if dependencies:
            for dep in dependencies:
                dep_config = ModuleConfiguration.query.filter_by(module_key=dep).first()
                if not dep_config or not dep_config.is_enabled:
                    return False
        
        return True
    
    def to_dict(self):
        """Serializa configuração para dict."""
        return {
            'id': self.id,
            'module_key': self.module_key,
            'display_name': self.display_name,
            'description': self.description,
            'module_type': self.module_type.value,
            'is_enabled': self.is_enabled,
            'requires_authentication': self.requires_authentication,
            'parent_module': self.parent_module,
            'dependencies': self.get_dependencies(),
            'icon': self.icon,
            'color': self.color,
            'display_order': self.display_order,
            'allowed_roles': self.get_allowed_roles(),
            'maintenance_mode': self.maintenance_mode,
            'maintenance_message': self.maintenance_message,
            'is_available': self.is_available,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'updated_by': self.updated_by
        }
    
    @staticmethod
    def get_enabled_modules():
        """Retorna apenas módulos habilitados ordenados por display_order."""
        return ModuleConfiguration.query.filter_by(
            is_enabled=True, 
            module_type=ModuleType.MODULE
        ).order_by(ModuleConfiguration.display_order).all()
    
    @staticmethod
    def is_module_enabled(module_key):
        """Verifica se um módulo específico está habilitado."""
        config = ModuleConfiguration.query.filter_by(module_key=module_key).first()
        return config.is_available if config else False
    
    @staticmethod
    def get_module_config(module_key):
        """Obtém configuração de um módulo específico."""
        return ModuleConfiguration.query.filter_by(module_key=module_key).first()

# --- FIM SISTEMA DE CONFIGURAÇÃO DE MÓDULOS ---

# <<< FIM: MODELO COMPLETO >>> 