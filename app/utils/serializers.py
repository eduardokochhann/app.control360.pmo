"""
Funções de serialização otimizadas para diferentes contextos.
"""

from flask import current_app


def serialize_task_for_sprints(task):
    """Versão simplificada e robusta para o módulo de sprints."""
    if not task:
        return None
    
    try:
        # Dados básicos obrigatórios
        task_data = {
            'id': getattr(task, 'id', None),
            'title': getattr(task, 'title', 'Sem título') or 'Sem título',
            'description': getattr(task, 'description', '') or '',
            'priority': getattr(task, 'priority', 'Média') or 'Média',
            'estimated_effort': getattr(task, 'estimated_effort', 0) or 0,
            'logged_time': getattr(task, 'logged_time', 0) or 0,
            'position': getattr(task, 'position', 0) or 0,
            'sprint_id': getattr(task, 'sprint_id', None),
            'backlog_id': getattr(task, 'backlog_id', None),
            'column_id': getattr(task, 'column_id', None),
            'is_generic': getattr(task, 'is_generic', False) or False,
        }
        
        # Campos calculados
        estimated_effort = task_data['estimated_effort']
        logged_time = task_data['logged_time']
        task_data['remaining_hours'] = max(0, estimated_effort - logged_time) if estimated_effort else 0
        task_data['assigned_to'] = getattr(task, 'specialist_name', 'Não atribuído') or 'Não atribuído'
        task_data['specialist_name'] = task_data['assigned_to']  # Campo legado
        task_data['estimated_hours'] = task_data['estimated_effort']  # Campo legado
        
        # Status
        try:
            status = getattr(task, 'status', None)
            task_data['status'] = status.value if status else 'TODO'
        except:
            task_data['status'] = 'TODO'
        
        # Coluna
        try:
            column = getattr(task, 'column', None)
            if column and hasattr(column, 'name'):
                column_name = column.name
                task_data['column_name'] = column_name
                # Identificador simplificado
                name_lower = column_name.lower()
                if 'todo' in name_lower or 'fazer' in name_lower:
                    task_data['column_identifier'] = 'todo'
                elif 'progress' in name_lower or 'andamento' in name_lower:
                    task_data['column_identifier'] = 'in-progress'
                elif 'review' in name_lower or 'revisão' in name_lower:
                    task_data['column_identifier'] = 'review'
                elif 'done' in name_lower or 'feito' in name_lower or 'completo' in name_lower:
                    task_data['column_identifier'] = 'done'
                else:
                    task_data['column_identifier'] = 'default'
            else:
                task_data['column_name'] = 'Coluna Desconhecida'
                task_data['column_identifier'] = 'default'
        except:
            task_data['column_name'] = 'Coluna Desconhecida'
            task_data['column_identifier'] = 'default'
        
        # Backlog e projeto
        try:
            backlog = getattr(task, 'backlog', None)
            if backlog:
                task_data['project_id'] = getattr(backlog, 'project_id', None)
                task_data['backlog_name'] = getattr(backlog, 'name', 'Backlog Desconhecido')
                
                # Tenta obter o nome do projeto via MacroService (com cache)
                if task_data['project_id'] and not getattr(task, 'is_generic', False):
                    try:
                        from app.macro.services import MacroService
                        macro_service = MacroService()
                        project_details = macro_service.obter_detalhes_projeto(task_data['project_id'])
                        if project_details and 'Projeto' in project_details:
                            task_data['project_name'] = project_details['Projeto']
                        else:
                            task_data['project_name'] = f'Projeto {task_data["project_id"]}'
                    except:
                        # Fallback silencioso
                        task_data['project_name'] = f'Projeto {task_data["project_id"]}'
                else:
                    task_data['project_name'] = f'Projeto {task_data["project_id"]}' if task_data['project_id'] else 'Nome Indisponível'
            else:
                task_data['project_id'] = None
                task_data['project_name'] = 'Nome Indisponível'
                task_data['backlog_name'] = 'Backlog Desconhecido'
        except:
            task_data['project_id'] = None
            task_data['project_name'] = 'Nome Indisponível'
            task_data['backlog_name'] = 'Backlog Desconhecido'
        
        # Segments count (opcional)
        try:
            segments = getattr(task, 'segments', None)
            task_data['segments_count'] = segments.count() if segments else 0
        except:
            task_data['segments_count'] = 0
        
        return task_data
        
    except Exception as e:
        # Log apenas em caso de erro crítico
        if current_app:
            current_app.logger.warning(f"Erro ao serializar tarefa {getattr(task, 'id', 'unknown')}: {str(e)}")
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