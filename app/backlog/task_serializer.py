"""
Serviço unificado para serialização de tarefas do Backlog.
Centraliza toda a lógica de conversão de objetos Task para dicionários/JSON.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from flask import current_app
from ..models import Task, TaskStatus


class TaskSerializer:
    """Serviço para serialização unificada e consistente de tarefas"""
    
    # Campos padrão que sempre devem estar presentes na serialização
    DEFAULT_FIELDS = [
        'id', 'title', 'name', 'description', 'status', 'priority',
        'estimated_effort', 'estimated_hours', 'logged_time', 'remaining_hours',
        'position', 'created_at', 'updated_at', 'start_date', 'due_date',
        'completed_at', 'actually_started_at', 'backlog_id', 'column_id',
        'column_name', 'column_identifier', 'sprint_id', 'project_id',
        'project_name', 'specialist_name', 'milestone_id', 'is_generic'
    ]
    
    @classmethod
    def serialize_task(cls, task: Task, include_relations: bool = True, 
                      fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Serializa uma tarefa para dicionário.
        
        Args:
            task: Objeto Task a ser serializado
            include_relations: Se deve incluir dados relacionados (coluna, projeto, etc.)
            fields: Lista específica de campos a incluir (None = todos os padrão)
            
        Returns:
            Dicionário com dados serializados da tarefa
        """
        if not task:
            return cls._get_error_task_data("Tarefa inválida ou None")
            
        try:
            # Campos obrigatórios básicos
            task_data = {
                'id': task.id,
                'name': task.title,  # Alias para compatibilidade
                'title': task.title or "Sem título",
                'description': task.description or "",
                'status': task.status.value if task.status else None,
                'priority': task.priority or "Média",
                'position': task.position or 0,
                'created_at': cls._format_datetime(task.created_at),
                'updated_at': cls._format_datetime(task.updated_at),
                'backlog_id': task.backlog_id,
                'is_generic': task.is_generic or False
            }
            
            # Campos de esforço e tempo
            task_data.update(cls._serialize_effort_fields(task))
            
            # Campos de datas
            task_data.update(cls._serialize_date_fields(task))
            
            # Dados relacionados (se solicitado)
            if include_relations:
                task_data.update(cls._serialize_related_data(task))
            
            # Filtrar campos específicos se solicitado
            if fields:
                task_data = {k: v for k, v in task_data.items() if k in fields}
            
            return task_data
            
        except Exception as e:
            current_app.logger.error(f"[TaskSerializer] Erro ao serializar tarefa {getattr(task, 'id', 'unknown')}: {e}")
            return cls._get_error_task_data(f"Erro na serialização: {str(e)}")
    
    @classmethod
    def _serialize_effort_fields(cls, task: Task) -> Dict[str, Any]:
        """Serializa campos relacionados a esforço e tempo"""
        try:
            # Calcula horas restantes baseado no esforço estimado e tempo logado
            estimated_effort = task.estimated_effort or 0
            logged_time = task.logged_time or 0
            remaining_hours = max(0, estimated_effort - logged_time)
            
            return {
                'estimated_effort': estimated_effort,
                'estimated_hours': estimated_effort,  # Alias para compatibilidade  
                'logged_time': logged_time,
                'remaining_hours': remaining_hours
            }
        except Exception as e:
            current_app.logger.warning(f"[TaskSerializer] Erro ao calcular campos de esforço: {e}")
            return {
                'estimated_effort': 0,
                'estimated_hours': 0,
                'logged_time': 0,
                'remaining_hours': 0
            }
    
    @classmethod
    def _serialize_date_fields(cls, task: Task) -> Dict[str, Any]:
        """Serializa campos de datas"""
        return {
            'start_date': cls._format_datetime(task.start_date),
            'due_date': cls._format_datetime(task.due_date),
            'completed_at': cls._format_datetime(task.completed_at),
            'actually_started_at': cls._format_datetime(task.actually_started_at)
        }
    
    @classmethod
    def _serialize_related_data(cls, task: Task) -> Dict[str, Any]:
        """Serializa dados relacionados (coluna, projeto, especialista, etc.)"""
        related_data = {
            'column_id': task.column_id,
            'column_name': None,
            'column_identifier': None,
            'sprint_id': task.sprint_id,
            'project_id': None,
            'project_name': None,
            'specialist_name': task.specialist_name,
            'milestone_id': task.milestone_id
        }
        
        try:
            # Dados da coluna
            if task.column:
                related_data['column_name'] = task.column.name
                related_data['column_identifier'] = task.column.identifier
            
            # Dados do projeto (via backlog)
            if task.backlog:
                related_data['project_id'] = task.backlog.project_id
                # O project_name pode ser buscado via MacroService se necessário
                # Por performance, não busca aqui, mas pode ser adicionado conforme necessidade
                
        except Exception as e:
            current_app.logger.warning(f"[TaskSerializer] Erro ao serializar dados relacionados: {e}")
        
        return related_data
    
    @classmethod
    def serialize_task_list(cls, tasks: List[Task], include_relations: bool = True) -> List[Dict[str, Any]]:
        """
        Serializa uma lista de tarefas.
        
        Args:
            tasks: Lista de objetos Task
            include_relations: Se deve incluir dados relacionados
            
        Returns:
            Lista de dicionários serializados
        """
        if not tasks:
            return []
            
        try:
            return [cls.serialize_task(task, include_relations) for task in tasks]
        except Exception as e:
            current_app.logger.error(f"[TaskSerializer] Erro ao serializar lista de tarefas: {e}")
            return []
    
    @classmethod
    def serialize_task_summary(cls, task: Task) -> Dict[str, Any]:
        """
        Serializa resumo básico da tarefa (para listas, sem dados relacionados pesados).
        
        Args:
            task: Objeto Task
            
        Returns:
            Dicionário com dados resumidos
        """
        summary_fields = [
            'id', 'title', 'name', 'status', 'priority', 'estimated_effort',
            'logged_time', 'remaining_hours', 'position', 'specialist_name',
            'column_name', 'due_date'
        ]
        
        return cls.serialize_task(task, include_relations=True, fields=summary_fields)
    
    @classmethod
    def _format_datetime(cls, dt: Optional[datetime]) -> Optional[str]:
        """
        Formata datetime para string ISO ou retorna None.
        
        Args:
            dt: Objeto datetime ou None
            
        Returns:
            String ISO formatada ou None
        """
        if dt is None:
            return None
        try:
            return dt.isoformat()
        except Exception as e:
            current_app.logger.warning(f"[TaskSerializer] Erro ao formatar datetime {dt}: {e}")
            return None
    
    @classmethod
    def _get_error_task_data(cls, error_message: str) -> Dict[str, Any]:
        """
        Retorna estrutura de tarefa para casos de erro.
        
        Args:
            error_message: Mensagem de erro
            
        Returns:
            Dicionário com estrutura de erro padrão
        """
        return {
            'id': None,
            'name': "Erro ao carregar tarefa",
            'title': "Erro ao carregar tarefa",
            'description': "",
            'status': None,
            'priority': "Média",
            'estimated_effort': 0,
            'estimated_hours': 0,
            'logged_time': 0,
            'remaining_hours': 0,
            'position': 0,
            'created_at': None,
            'updated_at': None,
            'start_date': None,
            'due_date': None,
            'completed_at': None,
            'actually_started_at': None,
            'backlog_id': None,
            'column_id': None,
            'column_name': 'Erro',
            'column_identifier': 'error',
            'sprint_id': None,
            'project_id': None,
            'project_name': None,
            'specialist_name': None,
            'milestone_id': None,
            'is_generic': False,
            'error': error_message
        }
    
    @classmethod
    def validate_task_data(cls, task_data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Valida se os dados serializados estão consistentes.
        
        Args:
            task_data: Dicionário com dados da tarefa
            
        Returns:
            Tupla (is_valid, list_of_issues)
        """
        issues = []
        
        # Validações básicas
        if not task_data.get('id'):
            issues.append("ID da tarefa não informado")
            
        if not task_data.get('title'):
            issues.append("Título da tarefa não informado")
            
        # Validações de esforço
        estimated_effort = task_data.get('estimated_effort', 0)
        estimated_hours = task_data.get('estimated_hours', 0)
        
        if estimated_effort != estimated_hours:
            issues.append(f"Inconsistência entre estimated_effort ({estimated_effort}) e estimated_hours ({estimated_hours})")
        
        # Validações de tempo
        logged_time = task_data.get('logged_time', 0)
        remaining_hours = task_data.get('remaining_hours', 0)
        
        if estimated_effort > 0:
            expected_remaining = max(0, estimated_effort - logged_time)
            if remaining_hours != expected_remaining:
                issues.append(f"Horas restantes inconsistentes: esperado {expected_remaining}, atual {remaining_hours}")
        
        return len(issues) == 0, issues 