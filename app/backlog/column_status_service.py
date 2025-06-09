"""
Serviço para mapeamento consistente entre colunas do Kanban e status de tarefas.
Centraliza a lógica de conversão para evitar inconsistências.
"""

from typing import Optional, Dict, List
from ..models import TaskStatus, Column
from flask import current_app


class ColumnStatusService:
    """Serviço para gerenciar mapeamento entre colunas e status de tarefas"""
    
    # Mapeamento padrão de nomes de coluna para status
    # Chave: padrão de texto (lowercase), Valor: TaskStatus enum
    COLUMN_STATUS_MAPPING = {
        # A Fazer / To Do
        'a fazer': TaskStatus.TODO,
        'afazer': TaskStatus.TODO,
        'todo': TaskStatus.TODO,
        'to do': TaskStatus.TODO,
        'pendente': TaskStatus.TODO,
        'backlog': TaskStatus.TODO,
        
        # Em Andamento / In Progress  
        'em andamento': TaskStatus.IN_PROGRESS,
        'andamento': TaskStatus.IN_PROGRESS,
        'in progress': TaskStatus.IN_PROGRESS,
        'inprogress': TaskStatus.IN_PROGRESS,
        'progresso': TaskStatus.IN_PROGRESS,
        'fazendo': TaskStatus.IN_PROGRESS,
        'desenvolvimento': TaskStatus.IN_PROGRESS,
        
        # Revisão / Review
        'revisão': TaskStatus.REVIEW,
        'revisao': TaskStatus.REVIEW,
        'review': TaskStatus.REVIEW,
        'em revisão': TaskStatus.REVIEW,
        'em revisao': TaskStatus.REVIEW,
        'validação': TaskStatus.REVIEW,
        'validacao': TaskStatus.REVIEW,
        'teste': TaskStatus.REVIEW,
        
        # Concluído / Done
        'concluído': TaskStatus.DONE,
        'concluido': TaskStatus.DONE,
        'done': TaskStatus.DONE,
        'finalizado': TaskStatus.DONE,
        'completo': TaskStatus.DONE,
        'entregue': TaskStatus.DONE,
        'pronto': TaskStatus.DONE,
        
        # Arquivado
        'arquivado': TaskStatus.ARCHIVED,
        'archived': TaskStatus.ARCHIVED,
        'cancelado': TaskStatus.ARCHIVED,
        'cancelled': TaskStatus.ARCHIVED,
    }
    
    # Mapeamento reverso: status para identificador de coluna preferido
    STATUS_COLUMN_MAPPING = {
        TaskStatus.TODO: 'afazer',
        TaskStatus.IN_PROGRESS: 'andamento', 
        TaskStatus.REVIEW: 'revisao',
        TaskStatus.DONE: 'concluido',
        TaskStatus.ARCHIVED: 'arquivado'
    }
    
    @classmethod
    def get_status_from_column_name(cls, column_name: str) -> Optional[TaskStatus]:
        """
        Converte nome da coluna para TaskStatus correspondente.
        
        Args:
            column_name: Nome da coluna do Kanban
            
        Returns:
            TaskStatus correspondente ou None se não encontrar
        """
        if not column_name:
            return None
            
        # Normaliza o nome (lowercase, sem espaços extras)
        normalized_name = column_name.lower().strip()
        
        # Busca correspondência direta
        status = cls.COLUMN_STATUS_MAPPING.get(normalized_name)
        if status:
            return status
            
        # Busca por correspondência parcial (fallback)
        for pattern, task_status in cls.COLUMN_STATUS_MAPPING.items():
            if pattern in normalized_name or normalized_name in pattern:
                current_app.logger.info(f"[ColumnStatus] Mapeamento parcial: '{column_name}' -> {task_status.value}")
                return task_status
                
        # Log se não encontrou mapeamento
        current_app.logger.warning(f"[ColumnStatus] Nenhum mapeamento encontrado para coluna: '{column_name}'")
        return None
    
    @classmethod
    def get_column_identifier_from_status(cls, status: TaskStatus) -> str:
        """
        Converte TaskStatus para identificador de coluna.
        
        Args:
            status: TaskStatus enum
            
        Returns:
            String identificador da coluna
        """
        return cls.STATUS_COLUMN_MAPPING.get(status, 'default')
    
    @classmethod
    def is_status_transition_valid(cls, from_status: TaskStatus, to_status: TaskStatus) -> bool:
        """
        Verifica se uma transição de status é válida.
        
        Args:
            from_status: Status atual
            to_status: Status desejado
            
        Returns:
            True se a transição é válida
        """
        # Definir transições válidas
        valid_transitions = {
            TaskStatus.TODO: [TaskStatus.IN_PROGRESS, TaskStatus.ARCHIVED],
            TaskStatus.IN_PROGRESS: [TaskStatus.TODO, TaskStatus.REVIEW, TaskStatus.DONE, TaskStatus.ARCHIVED],
            TaskStatus.REVIEW: [TaskStatus.IN_PROGRESS, TaskStatus.DONE, TaskStatus.ARCHIVED],
            TaskStatus.DONE: [TaskStatus.REVIEW, TaskStatus.ARCHIVED],  # Permitir reabrir
            TaskStatus.ARCHIVED: [TaskStatus.TODO]  # Permitir desarquivar
        }
        
        if from_status == to_status:
            return True  # Mesma posição é válida
            
        allowed_transitions = valid_transitions.get(from_status, [])
        return to_status in allowed_transitions
    
    @classmethod
    def get_default_status_for_new_task(cls) -> TaskStatus:
        """Retorna o status padrão para novas tarefas"""
        return TaskStatus.TODO
    
    @classmethod
    def get_completion_indicators(cls) -> List[str]:
        """Retorna lista de indicadores que sugerem que tarefa está concluída"""
        return [
            'concluído', 'concluido', 'done', 'finalizado', 
            'completo', 'entregue', 'pronto'
        ]
    
    @classmethod
    def get_progress_indicators(cls) -> List[str]:
        """Retorna lista de indicadores que sugerem que tarefa está em progresso"""
        return [
            'em andamento', 'andamento', 'in progress', 'inprogress',
            'progresso', 'fazendo', 'desenvolvimento'
        ]
    
    @classmethod
    def log_status_change(cls, task_id: int, old_status: TaskStatus, new_status: TaskStatus, 
                         column_name: str, reason: str = "column_move"):
        """
        Loga mudanças de status para auditoria.
        
        Args:
            task_id: ID da tarefa
            old_status: Status anterior  
            new_status: Novo status
            column_name: Nome da coluna de destino
            reason: Motivo da mudança
        """
        current_app.logger.info(
            f"[StatusChange] Tarefa {task_id}: {old_status.value} -> {new_status.value} "
            f"(Coluna: '{column_name}', Motivo: {reason})"
        ) 