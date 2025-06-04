"""
Funções de serialização otimizadas para diferentes contextos.
"""

from flask import current_app


def serialize_task_for_sprints(task):
    """Versão otimizada de serialize_task específica para o módulo de sprints - SEM LOGS DEBUG."""
    if not task:
        return None
    
    try:
        # Calcula horas restantes de forma otimizada
        remaining_hours = None
        if task.estimated_effort is not None:
            logged = task.logged_time or 0
            remaining_hours = task.estimated_effort - logged

        # Otimização: acesso direto às propriedades sem logs
        column_identifier = 'default'
        column_full_name = 'Coluna Desconhecida'
        if task.column:
            column_full_name = task.column.name
            name_lower = column_full_name.lower()
            if 'todo' in name_lower or 'fazer' in name_lower:
                column_identifier = 'todo'
            elif 'progress' in name_lower or 'andamento' in name_lower:
                column_identifier = 'in-progress'
            elif 'review' in name_lower or 'revisão' in name_lower:
                column_identifier = 'review'
            elif 'done' in name_lower or 'feito' in name_lower or 'completo' in name_lower:
                column_identifier = 'done'

        # Otimização: project details cacheados ou fallback
        project_name = 'Nome Indisponível'
        if task.backlog and task.backlog.project_id:
            try:
                # Cache básico para project details - evita chamadas repetitivas ao MacroService
                cache_key = f"project_{task.backlog.project_id}"
                if not hasattr(current_app, '_project_cache'):
                    current_app._project_cache = {}
                
                if cache_key in current_app._project_cache:
                    project_details = current_app._project_cache[cache_key]
                else:
                    from app.macro.services import MacroService
                    macro_service = MacroService()
                    project_details = macro_service.obter_detalhes_projeto(task.backlog.project_id)
                    current_app._project_cache[cache_key] = project_details
                
                if project_details:
                    project_name = project_details.get('Projeto', 'Nome Indisponível')
            except Exception:
                # OTIMIZAÇÃO: Sem logs de erro para não impactar performance
                pass

        return {
            'id': task.id,
            'title': task.title or 'Sem título',
            'description': task.description or '',
            'priority': task.priority or 'Média',
            'estimated_effort': task.estimated_effort,
            'logged_time': task.logged_time or 0,
            'remaining_hours': remaining_hours,
            'assigned_to': task.assigned_to or task.specialist_name or 'Não atribuído',
            'specialist_name': task.specialist_name or 'Não atribuído',  # Campo legado
            'estimated_hours': task.estimated_effort,  # Campo legado
            'position': task.position or 0,
            'sprint_id': task.sprint_id,
            'backlog_id': task.backlog_id,
            'column_id': task.column_id,
            'column_name': column_full_name,
            'column_identifier': column_identifier,
            'project_name': project_name,
            'backlog_name': task.backlog.name if task.backlog else 'Backlog Desconhecido',
            'is_generic': task.is_generic or False,
            'status': task.status.value if task.status else 'TODO',
            'segments_count': len(task.segments) if task.segments else 0,
        }
        
    except Exception as e:
        # OTIMIZAÇÃO: Fallback silencioso em caso de erro
        return {
            'id': getattr(task, 'id', 'N/A'),
            'title': 'Erro ao carregar tarefa',
            'description': '',
            'priority': 'Média',
            'estimated_effort': 0,
            'logged_time': 0,
            'remaining_hours': 0,
            'assigned_to': 'N/A',
            'specialist_name': 'N/A',
            'estimated_hours': 0,
            'position': 0,
            'sprint_id': getattr(task, 'sprint_id', None),
            'backlog_id': getattr(task, 'backlog_id', None),
            'column_id': getattr(task, 'column_id', None),
            'column_name': 'Erro',
            'column_identifier': 'default',
            'project_name': 'Erro',
            'backlog_name': 'Erro',
            'is_generic': False,
            'status': 'TODO',
            'segments_count': 0,
        } 