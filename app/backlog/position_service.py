"""
Serviço para gestão unificada de posições das tarefas no Kanban.
Centraliza todas as operações de reordenação, movimentação e cálculo de posições.
"""

from typing import List, Optional, Tuple
from sqlalchemy import and_, func
from ..models import Task, Column, db
from flask import current_app


class PositionService:
    """Serviço para gerenciar posições de tarefas no Kanban"""
    
    POSITION_INCREMENT = 100  # Incremento padrão entre posições
    
    @classmethod
    def get_next_position_in_column(cls, column_id: int, backlog_id: int) -> int:
        """
        Calcula a próxima posição disponível em uma coluna.
        
        Args:
            column_id: ID da coluna
            backlog_id: ID do backlog
            
        Returns:
            Próxima posição disponível
        """
        try:
            max_position = db.session.query(func.max(Task.position)).filter(
                and_(
                    Task.column_id == column_id,
                    Task.backlog_id == backlog_id,
                    Task.position.isnot(None)
                )
            ).scalar()
            
            if max_position is None:
                return cls.POSITION_INCREMENT
                
            return max_position + cls.POSITION_INCREMENT
            
        except Exception as e:
            current_app.logger.error(f"[PositionService] Erro ao calcular próxima posição: {e}")
            return cls.POSITION_INCREMENT
    
    @classmethod
    def calculate_position_between(cls, previous_position: Optional[int], 
                                 next_position: Optional[int]) -> int:
        """
        Calcula uma posição entre duas posições existentes.
        
        Args:
            previous_position: Posição da tarefa anterior (None se for a primeira)
            next_position: Posição da próxima tarefa (None se for a última)
            
        Returns:
            Nova posição calculada
        """
        if previous_position is None and next_position is None:
            return cls.POSITION_INCREMENT
            
        if previous_position is None:
            # Inserindo no início
            return max(1, next_position - cls.POSITION_INCREMENT)
            
        if next_position is None:
            # Inserindo no final
            return previous_position + cls.POSITION_INCREMENT
            
        # Inserindo no meio
        gap = next_position - previous_position
        if gap <= 1:
            # Posições muito próximas, precisa reordenar
            return cls._trigger_reorder_and_get_position(previous_position, next_position)
            
        return previous_position + (gap // 2)
    
    @classmethod
    def _trigger_reorder_and_get_position(cls, previous_position: int, next_position: int) -> int:
        """
        Reorganiza posições quando o gap fica muito pequeno.
        
        Args:
            previous_position: Posição anterior
            next_position: Próxima posição
            
        Returns:
            Nova posição após reorganização
        """
        current_app.logger.info(f"[PositionService] Reorganizando posições devido a gap pequeno entre {previous_position} e {next_position}")
        
        # Por simplicidade, retorna uma posição intermediária
        # Em produção, poderia implementar uma reorganização mais sofisticada
        return previous_position + 50
    
    @classmethod
    def move_task_to_position(cls, task: Task, target_column_id: int, 
                            target_position: Optional[int] = None) -> bool:
        """
        Move uma tarefa para uma nova coluna e posição.
        
        Args:
            task: Tarefa a ser movida
            target_column_id: ID da coluna de destino
            target_position: Posição específica (opcional, será calculada se None)
            
        Returns:
            True se a movimentação foi bem-sucedida
        """
        try:
            old_column_id = task.column_id
            old_position = task.position
            
            # Atualiza coluna
            task.column_id = target_column_id
            
            # Calcula nova posição se não especificada
            if target_position is None:
                target_position = cls.get_next_position_in_column(target_column_id, task.backlog_id)
            
            task.position = target_position
            
            current_app.logger.info(
                f"[PositionService] Tarefa {task.id} movida: "
                f"Coluna {old_column_id}->{target_column_id}, "
                f"Posição {old_position}->{target_position}"
            )
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"[PositionService] Erro ao mover tarefa {task.id}: {e}")
            return False
    
    @classmethod
    def reorder_tasks_in_column(cls, column_id: int, backlog_id: int, 
                              task_ids_ordered: List[int]) -> bool:
        """
        Reordena tarefas em uma coluna baseado em uma lista ordenada de IDs.
        
        Args:
            column_id: ID da coluna
            backlog_id: ID do backlog
            task_ids_ordered: Lista de IDs das tarefas na ordem desejada
            
        Returns:
            True se a reordenação foi bem-sucedida
        """
        try:
            # Busca todas as tarefas da coluna
            tasks = Task.query.filter(
                and_(
                    Task.column_id == column_id,
                    Task.backlog_id == backlog_id,
                    Task.id.in_(task_ids_ordered)
                )
            ).all()
            
            if not tasks:
                return True  # Nada para reordenar
            
            # Cria mapeamento task_id -> task
            tasks_dict = {task.id: task for task in tasks}
            
            # Atualiza posições baseado na ordem fornecida
            for index, task_id in enumerate(task_ids_ordered):
                if task_id in tasks_dict:
                    new_position = (index + 1) * cls.POSITION_INCREMENT
                    tasks_dict[task_id].position = new_position
                    
                    current_app.logger.info(
                        f"[PositionService] Tarefa {task_id} reordenada para posição {new_position}"
                    )
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"[PositionService] Erro ao reordenar tarefas: {e}")
            return False
    
    @classmethod
    def get_tasks_ordered_by_position(cls, column_id: int, backlog_id: int) -> List[Task]:
        """
        Retorna tarefas de uma coluna ordenadas por posição.
        
        Args:
            column_id: ID da coluna
            backlog_id: ID do backlog
            
        Returns:
            Lista de tarefas ordenadas por posição
        """
        try:
            return Task.query.filter(
                and_(
                    Task.column_id == column_id,
                    Task.backlog_id == backlog_id
                )
            ).order_by(Task.position.asc(), Task.created_at.asc()).all()
            
        except Exception as e:
            current_app.logger.error(f"[PositionService] Erro ao buscar tarefas ordenadas: {e}")
            return []
    
    @classmethod
    def fix_position_gaps(cls, column_id: int, backlog_id: int) -> bool:
        """
        Corrige gaps nas posições de uma coluna, reorganizando sequencialmente.
        
        Args:
            column_id: ID da coluna
            backlog_id: ID do backlog
            
        Returns:
            True se a correção foi bem-sucedida
        """
        try:
            tasks = cls.get_tasks_ordered_by_position(column_id, backlog_id)
            
            for index, task in enumerate(tasks):
                new_position = (index + 1) * cls.POSITION_INCREMENT
                if task.position != new_position:
                    old_position = task.position
                    task.position = new_position
                    current_app.logger.info(
                        f"[PositionService] Corrigindo posição da tarefa {task.id}: {old_position} -> {new_position}"
                    )
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"[PositionService] Erro ao corrigir gaps de posição: {e}")
            return False
    
    @classmethod
    def validate_positions_consistency(cls, column_id: int, backlog_id: int) -> Tuple[bool, List[str]]:
        """
        Valida se as posições em uma coluna estão consistentes.
        
        Args:
            column_id: ID da coluna
            backlog_id: ID do backlog
            
        Returns:
            Tupla (is_valid, list_of_issues)
        """
        issues = []
        
        try:
            tasks = cls.get_tasks_ordered_by_position(column_id, backlog_id)
            
            if not tasks:
                return True, []
            
            # Verifica se há posições None
            none_positions = [task.id for task in tasks if task.position is None]
            if none_positions:
                issues.append(f"Tarefas com posição None: {none_positions}")
            
            # Verifica posições duplicadas
            positions = [task.position for task in tasks if task.position is not None]
            duplicates = [pos for pos in set(positions) if positions.count(pos) > 1]
            if duplicates:
                issues.append(f"Posições duplicadas: {duplicates}")
            
            # Verifica gaps muito pequenos
            for i in range(len(tasks) - 1):
                if tasks[i].position and tasks[i+1].position:
                    gap = tasks[i+1].position - tasks[i].position
                    if gap <= 1:
                        issues.append(f"Gap muito pequeno entre tarefas {tasks[i].id} e {tasks[i+1].id}: {gap}")
            
            return len(issues) == 0, issues
            
        except Exception as e:
            issues.append(f"Erro ao validar consistência: {e}")
            return False, issues 