from flask import current_app
from datetime import datetime, timedelta, date
import pytz # Embora br_timezone não seja usado diretamente por serialize_task, pode ser útil manter aqui se outras utils o usarem.

# Importa os modelos necessários diretamente. Ajuste se for mais específico.
from ..models import Task, Column, Backlog, Sprint, TaskStatus, TaskSegment 

# Define o fuso horário de Brasília - pode ser removido se não usado por outras utils aqui
br_timezone = pytz.timezone('America/Sao_Paulo')

# Função auxiliar para serializar uma tarefa
def serialize_task(task):
    try:
        # Calcula horas restantes (se possível)
        remaining_hours = None
        if task.estimated_effort is not None:
            # Assume 0 se logged_time for None para cálculo
            logged = task.logged_time or 0
            remaining_hours = task.estimated_effort - logged

        # Encontra o nome da coluna e gera um prefixo/identificador
        column_identifier = 'default' # Identificador padrão
        column_full_name = 'Coluna Desconhecida'
        if task.column:
            column_full_name = task.column.name
            # Gera um identificador simplificado baseado no nome da coluna para usar na classe CSS
            name_lower = column_full_name.lower()
            if 'a fazer' in name_lower:
                column_identifier = 'afazer'
            elif 'andamento' in name_lower:
                column_identifier = 'andamento'
            elif 'revis' in name_lower: # Pega \"Revisão\"
                column_identifier = 'revisao'
            elif 'concluído' in name_lower or 'concluido' in name_lower:
                column_identifier = 'concluido'
            # Adicionar mais elifs se houver outras colunas padrão

        # Protege contra erros se o relacionamento backlog ou sprint não existir
        backlog_rel = task.backlog if hasattr(task, 'backlog') and task.backlog is not None else None
        sprint_rel = task.sprint if hasattr(task, 'sprint') and task.sprint is not None else None
        
        # Prepara os timestamps com tratamento de erros
        created_at = task.created_at.isoformat() if hasattr(task, 'created_at') and task.created_at else None
        updated_at = task.updated_at.isoformat() if hasattr(task, 'updated_at') and task.updated_at else None
        start_date_iso = task.start_date.isoformat() if hasattr(task, 'start_date') and task.start_date else None
        due_date_iso = task.due_date.isoformat() if hasattr(task, 'due_date') and task.due_date else None
        completed_at_iso = task.completed_at.isoformat() if hasattr(task, 'completed_at') and task.completed_at else None
        actually_started_at_iso = task.actually_started_at.isoformat() if hasattr(task, 'actually_started_at') and task.actually_started_at else None


        # Coleta dos dados principais da tarefa
        task_data = {
            'id': task.id,
            'name': task.title, # Mantendo 'name' para consistência com o que o frontend pode esperar às vezes
            'title': task.title if hasattr(task, 'title') else "Sem título",
            'description': task.description if hasattr(task, 'description') else "",
            'status': task.status.value if hasattr(task, 'status') and task.status else None,
            'priority': task.priority if hasattr(task, 'priority') else "Média",
            'estimated_hours': task.estimated_effort if hasattr(task, 'estimated_effort') else None,
            'logged_time': task.logged_time if hasattr(task, 'logged_time') else 0,
            'remaining_hours': remaining_hours,
            'position': task.position if hasattr(task, 'position') else 0,
            'created_at': created_at,
            'updated_at': updated_at,
            'start_date': start_date_iso,
            'due_date': due_date_iso,
            'completed_at': completed_at_iso,
            'actually_started_at': actually_started_at_iso, # Adicionado
            'backlog_id': task.backlog_id if hasattr(task, 'backlog_id') else None,
            'column_id': task.column_id if hasattr(task, 'column_id') else None,
            'column_name': column_full_name,
            'column_identifier': column_identifier,
            'sprint_id': task.sprint_id if hasattr(task, 'sprint_id') else None,
            'project_id': backlog_rel.project_id if backlog_rel else None,
            'sprint_name': sprint_rel.name if sprint_rel else None,
            'specialist_name': task.specialist_name if hasattr(task, 'specialist_name') else None,
            'is_generic': task.is_generic if hasattr(task, 'is_generic') else False # Adicionado
        }

        # --- INÍCIO: Adicionar resumo dos segmentos da tarefa ---
        task_segments_summary = []
        if hasattr(task, 'segments'):
            try:
                segments = task.segments # Não precisa de .all() se for uma relação lazy='dynamic' ou já carregada
                                         # Se for dynamic e precisar de ordenação, seria task.segments.order_by(...)
                for segment in segments:
                    segment_summary = {
                        'id': segment.id,
                        'start': segment.segment_start_datetime.isoformat() if segment.segment_start_datetime else None,
                        'end': segment.segment_end_datetime.isoformat() if segment.segment_end_datetime else None,
                        'description': (segment.description[:75] + '...') if segment.description and len(segment.description) > 75 else segment.description
                    }
                    task_segments_summary.append(segment_summary)
            except Exception as seg_ex:
                current_app.logger.error(f"Erro ao serializar segmentos para tarefa {task.id}: {str(seg_ex)}")
        
        task_data['task_segments_summary'] = task_segments_summary
        # --- FIM: Adicionar resumo dos segmentos da tarefa ---\

        return task_data
    except Exception as e:
        current_app.logger.error(f"[Erro ao serializar tarefa {getattr(task, 'id', 'ID_DESCONHECIDO')}]: {str(e)}", exc_info=True)
        return {
            'id': getattr(task, 'id', None), # Tenta pegar o ID mesmo em erro
            'title': "Erro ao carregar tarefa",
            'error': str(e),
            # Fornece valores padrão para chaves que o frontend pode esperar para evitar TypeErrors
            'name': "Erro", 
            'description': "",
            'status': None,
            'priority': "Média",
            'estimated_hours': None,
            'logged_time': 0,
            'remaining_hours': None,
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
            'sprint_name': None,
            'specialist_name': None,
            'is_generic': False,
            'task_segments_summary': []
        } 