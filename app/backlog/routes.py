from flask import render_template, jsonify, request, abort, current_app, redirect, url_for, Response, send_file
from . import backlog_bp # Importa o blueprint
from .. import db # Importa a instância do banco de dados
from ..models import Backlog, Task, Column, Sprint, TaskStatus, ProjectMilestone, ProjectRisk, MilestoneStatus, MilestoneCriticality, RiskImpact, RiskProbability, RiskStatus, TaskSegment, Note, Tag # Importa os modelos
from ..macro.services import MacroService # Importa o serviço Macro
import pandas as pd
from datetime import datetime, timedelta, date
import pytz # <<< ADICIONADO
from sqlalchemy import and_
from sqlalchemy.orm import joinedload
from io import BytesIO
import time

# Define o fuso horário de Brasília
br_timezone = pytz.timezone('America/Sao_Paulo') # <<< ADICIONADO

# Importa a versão otimizada da função de serialização
from ..utils.serializers import serialize_task_for_sprints

# Função auxiliar para serializar uma tarefa
def serialize_task(task):
    """Converte um objeto Task em um dicionário serializável."""
    if not task:
        return None
    
    # OTIMIZAÇÃO: Removido log excessivo que estava causando lentidão
    # current_app.logger.info(f"[serialize_task] Serializando tarefa ID: {task.id}, Título: {task.title}, is_generic: {task.is_generic}")

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
            elif 'revis' in name_lower: # Pega "Revisão"
                column_identifier = 'revisao'
            elif 'concluído' in name_lower or 'concluido' in name_lower:
                column_identifier = 'concluido'
            # Adicionar mais elifs se houver outras colunas padrão

        # Protege contra erros se o relacionamento backlog ou sprint não existir
        backlog = task.backlog if hasattr(task, 'backlog') and task.backlog is not None else None
        sprint = task.sprint if hasattr(task, 'sprint') and task.sprint is not None else None
        
        # Prepara os timestamps com tratamento de erros
        created_at = task.created_at.isoformat() if hasattr(task, 'created_at') and task.created_at else None
        updated_at = task.updated_at.isoformat() if hasattr(task, 'updated_at') and task.updated_at else None
        start_date = task.start_date.isoformat() if hasattr(task, 'start_date') and task.start_date else None
        due_date = task.due_date.isoformat() if hasattr(task, 'due_date') and task.due_date else None
        completed_at = task.completed_at.isoformat() if hasattr(task, 'completed_at') and task.completed_at else None

        # Coleta dos dados principais da tarefa
        task_data = {
            'id': task.id,
            'name': task.title, # Mantendo 'name' para consistência com o que o frontend pode esperar às vezes
            'title': task.title if hasattr(task, 'title') else "Sem título",
            'description': task.description if hasattr(task, 'description') else "",
            'status': task.status.value if hasattr(task, 'status') and task.status else None,
            'priority': task.priority if hasattr(task, 'priority') else "Média",
            'estimated_effort': task.estimated_effort if hasattr(task, 'estimated_effort') else None,
            'logged_time': task.logged_time if hasattr(task, 'logged_time') else 0,
            'remaining_hours': remaining_hours,
            'position': task.position if hasattr(task, 'position') else 0,
            'created_at': created_at,
            'updated_at': updated_at,
            'start_date': start_date,
            'due_date': due_date,
            'completed_at': completed_at,
            'backlog_id': task.backlog_id if hasattr(task, 'backlog_id') else None,
            'column_id': task.column_id if hasattr(task, 'column_id') else None,
            'column_name': column_full_name,
            'column_identifier': column_identifier,
            'sprint_id': task.sprint_id if hasattr(task, 'sprint_id') else None,
            'project_id': backlog.project_id if backlog else None,
            'sprint_name': sprint.name if sprint else None,
            'specialist_name': task.specialist_name if hasattr(task, 'specialist_name') else None,
            'is_generic': task.is_generic if hasattr(task, 'is_generic') else False, # Adicionado para is_generic
            'is_unplanned': task.is_unplanned if hasattr(task, 'is_unplanned') else False # NOVO CAMPO
        }

        # NOVO: Busca o nome do projeto se não for tarefa genérica e tiver project_id
        if not (task.is_generic if hasattr(task, 'is_generic') else False) and backlog and backlog.project_id:
            try:
                from ..macro.services import MacroService
                macro_service = MacroService()
                project_details = macro_service.obter_detalhes_projeto(backlog.project_id)
                if project_details:
                    # As chaves são normalizadas (minúsculas), então usa 'projeto' em vez de 'Projeto'
                    task_data['project_name'] = project_details.get('projeto', project_details.get('Projeto', 'Projeto Desconhecido'))
                else:
                    task_data['project_name'] = 'Projeto Desconhecido'
            except Exception as proj_ex:
                current_app.logger.warning(f"Erro ao buscar nome do projeto {backlog.project_id}: {proj_ex}")
                task_data['project_name'] = 'Projeto Desconhecido'
        else:
            task_data['project_name'] = None

        # --- INÍCIO: Adicionar resumo dos segmentos da tarefa ---
        task_segments_summary = []
        if hasattr(task, 'segments'):
            try:
                # Ordenar segmentos por data de início, se desejado (opcional)
                # segments = task.segments.order_by(TaskSegment.segment_start_datetime).all()
                segments = task.segments.all() # Pega todos os segmentos
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
                # Não impede a serialização da tarefa principal se os segmentos falharem
        
        task_data['task_segments_summary'] = task_segments_summary
        # --- FIM: Adicionar resumo dos segmentos da tarefa ---

        return task_data
    except Exception as e:
        current_app.logger.error(f"[Erro ao serializar tarefa {getattr(task, 'id', 'ID_DESCONHECIDO')}]: {str(e)}", exc_info=True)
        # Retorna um objeto mínimo em caso de erro
        return {
            'id': task.id,
            'title': "Erro ao carregar tarefa",
            'error': str(e)
        }

# Rota principal - AGORA REDIRECIONA PARA A SELEÇÃO
@backlog_bp.route('/')
def index():
    # Redireciona para a nova página de seleção de projetos
    return redirect(url_for('.project_selection'))

# NOVA ROTA - Página de Seleção de Projetos
@backlog_bp.route('/projetos')
def project_selection():
    try:
        macro_service = MacroService()
        grouping_mode = request.args.get('group_by', 'squad') # Pega parâmetro ou default 'squad'
        dados_df = macro_service.carregar_dados()
        if dados_df.empty:
            current_app.logger.warning("Seleção de Projetos: DataFrame vazio ou não carregado.")
            projects = []
        else:
            projects = macro_service.obter_projetos_ativos(dados_df)
            projects.sort(key=lambda x: x.get('projeto', ''))

        current_app.logger.info(f"Processando {len(projects)} projetos para seleção.")
        projects_for_template = []
        squads = set() # Para popular o filtro de Squads
        statuses = set() # Para popular o filtro de Status
        specialists = set() # Para popular o filtro de Especialistas
        
        for p_dict in projects:
            project_id_str = str(p_dict.get('numero')) # Garante que é string
            task_count = 0
            backlog_exists = False
            try:
                # Busca o backlog para este project_id
                backlog = Backlog.query.filter_by(project_id=project_id_str).first()
                if backlog:
                    backlog_exists = True
                    # Conta as tarefas associadas a este backlog
                    # Usar count() é mais eficiente que carregar todas as tarefas
                    task_count = db.session.query(Task.id).filter(Task.backlog_id == backlog.id).count() 
                    current_app.logger.debug(f"Projeto {project_id_str}: Backlog ID {backlog.id}, Tarefas: {task_count}")
                else:
                     current_app.logger.debug(f"Projeto {project_id_str}: Nenhum backlog encontrado.")

            except Exception as db_error:
                 current_app.logger.error(f"Erro ao buscar backlog/tarefas para projeto {project_id_str}: {db_error}")
                 # Continua mesmo com erro, task_count será 0

            project_data = {
                'id': project_id_str, # Usa a string consistente
                'name': p_dict.get('projeto'),
                'squad': p_dict.get('squad'),
                'specialist': p_dict.get('especialista'),
                'status': p_dict.get('status'),
                'task_count': task_count, # <<< Adiciona a contagem
                'backlog_exists': backlog_exists # <<< Indica se backlog existe
            }
            projects_for_template.append(project_data)
            
            # Coleta squads, status e specialist para filtros (ignorando None ou vazios)
            if project_data['squad']:
                squads.add(project_data['squad'])
            if project_data['status']:
                statuses.add(project_data['status'])
            if project_data['specialist']:
                specialists.add(project_data['specialist'])

        # --- Ordenação Condicional --- 
        if grouping_mode == 'specialist':
            # Ordena por Especialista (None/vazio por último), depois por Nome
            projects_for_template.sort(key=lambda x: (x.get('specialist', '') or 'ZZZ', x.get('name', '')))
            current_app.logger.info("Ordenando projetos por Especialista.")
        else: # Default para Squad
            # Ordena por Squad (None/vazio por último), depois por Nome
            projects_for_template.sort(key=lambda x: (x.get('squad', '') or 'ZZZ', x.get('name', '')))
            current_app.logger.info("Ordenando projetos por Squad.")
        # ---------------------------
        
        # Ordena as opções dos dropdowns
        sorted_squads = sorted(list(squads))
        sorted_statuses = sorted(list(statuses))
        sorted_specialists = sorted(list(specialists))

        current_app.logger.info(f"Renderizando seleção com {len(projects_for_template)} projetos. Squads: {len(sorted_squads)}, Status: {len(sorted_statuses)}, Especialistas: {len(sorted_specialists)}")
        return render_template(
            'backlog/project_selection.html', 
            projects=projects_for_template,
            squad_options=sorted_squads, # Passa squads para o filtro
            status_options=sorted_statuses, # Passa status para o filtro
            specialist_options=sorted_specialists, # Passa especialistas para o filtro
            current_grouping=grouping_mode # <<< Passa modo de agrupamento atual
        )
            
    except Exception as e:
        current_app.logger.error(f"Erro ao carregar página de seleção de projetos: {e}", exc_info=True)
        # Renderiza a página com erro ou redireciona para uma página de erro
        return render_template('backlog/project_selection.html', projects=[], error="Erro ao carregar projetos.")

# NOVA ROTA - Quadro Kanban para um Projeto Específico
@backlog_bp.route('/board/<string:project_id>')
def board_by_project(project_id):
    try:
        # Log detalhado para depuração
        current_app.logger.info(f"[DEBUG] Iniciando carregamento do quadro para project_id: {project_id}")
        
        # 1. Busca detalhes do projeto (para cabeçalho)
        current_app.logger.info(f"[DEBUG] Buscando detalhes do projeto {project_id}")
        macro_service = MacroService()
        project_details = macro_service.obter_detalhes_projeto(project_id)
        current_app.logger.info(f"[DEBUG] Resultado da busca de detalhes: {project_details}")
        
        if not project_details:
            current_app.logger.warning(f"[DEBUG] Detalhes não encontrados para projeto {project_id}. Redirecionando para seleção.")
            # TODO: Adicionar flash message informando erro?
            return redirect(url_for('.project_selection'))
            
        # 2. Busca o backlog associado
        current_app.logger.info(f"[DEBUG] Buscando backlog para o projeto {project_id}")
        current_backlog = Backlog.query.filter_by(project_id=project_id).first()
        backlog_id = current_backlog.id if current_backlog else None
        backlog_name = current_backlog.name if current_backlog else "Backlog não criado"
        current_app.logger.info(f"[DEBUG] Backlog encontrado: ID={backlog_id}, Nome={backlog_name}")
        
        # 3. Busca as tarefas do backlog (se existir)
        tasks_list = []
        if backlog_id:
            current_app.logger.info(f"[DEBUG] Buscando tarefas para o backlog {backlog_id}")
            tasks = Task.query.filter_by(backlog_id=backlog_id).order_by(Task.position).all()
            tasks_list = [serialize_task(t) for t in tasks]
            current_app.logger.info(f"[DEBUG] Encontradas {len(tasks_list)} tarefas para o backlog {backlog_id}.")
        else:
            current_app.logger.info(f"[DEBUG] Nenhum backlog encontrado para o projeto {project_id}.")
            # O template board.html precisa lidar com backlog_id=None (ex: mostrar botão criar)
        
        # 4. Busca colunas (necessário para estrutura do quadro)
        current_app.logger.info(f"[DEBUG] Buscando colunas para o quadro")
        columns = Column.query.order_by(Column.position).all()
        current_app.logger.info(f"[DEBUG] Encontradas {len(columns)} colunas")
        
        # Serializa as colunas para evitar erro de JSON
        columns_list = [{'id': c.id, 'name': c.name, 'position': c.position} for c in columns]
        
        # Serializa os dados do projeto para evitar problemas de JSON
        project_data = {
            'id': str(project_details.get('Numero', project_id)),
            'name': project_details.get('Projeto', 'Projeto Desconhecido'),
            'squad': project_details.get('Squad', ''),
            'status': project_details.get('Status', ''),
            'specialist': project_details.get('Especialista', ''),
            'hours': project_details.get('Horas', 0),
            'worked_hours': project_details.get('HorasTrabalhadas', 0),
            'completion': project_details.get('Conclusao', 0),
            'account_manager': project_details.get('Account Manager', ''),
            'start_date': project_details.get('DataInicio').isoformat() if project_details.get('DataInicio') and not pd.isna(project_details.get('DataInicio')) else None,
            'due_date': project_details.get('VencimentoEm').isoformat() if project_details.get('VencimentoEm') and not pd.isna(project_details.get('VencimentoEm')) else None,
            'billing': project_details.get('Faturamento', ''),
            'remaining_hours': project_details.get('HorasRestantes', 0)
        }
        
        # Serializa o backlog
        backlog_data = {
            'id': current_backlog.id,
            'name': current_backlog.name,
            'project_id': current_backlog.project_id
        }
        
        # 5. Renderiza o template do quadro passando os dados específicos
        current_app.logger.info(f"[DEBUG] Renderizando template board.html")
        return render_template(
            'backlog/board.html', 
            columns=columns_list,  # Passa lista serializada ao invés de objetos
            tasks_json=jsonify(tasks_list).get_data(as_text=True), 
            current_project=project_data,  # Passa dados serializados
            current_backlog_id=backlog_id, 
            current_backlog_name=backlog_name,
            backlog=backlog_data  # Passa dados serializados
        )

    except Exception as e:
        current_app.logger.error(f"[DEBUG] Erro ao carregar quadro para projeto {project_id}: {str(e)}", exc_info=True)
        # TODO: Adicionar flash message?
        return redirect(url_for('.project_selection'))

# --- API Endpoints --- 

# --- Task Segment API Endpoints ---

@backlog_bp.route('/api/tasks/<int:task_id>/segments', methods=['GET'])
def get_task_segments(task_id):
    task = Task.query.get_or_404(task_id)
    segments = task.segments.order_by(TaskSegment.segment_start_datetime).all() # Ordena por data de início
    return jsonify([segment.to_dict() for segment in segments])

@backlog_bp.route('/api/tasks/<int:task_id>/segments', methods=['POST'])
def manage_task_segments(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.json
    segments_data = data.get('segments', [])

    current_app.logger.info(f"Recebido para gerenciar segmentos da tarefa {task_id}: {segments_data}")

    # Estratégia: Remover todos os segmentos existentes e recriá-los
    # Isso simplifica a lógica de identificar novos, atualizados ou removidos.
    # Se performance for um problema para muitas atualizações, pode ser otimizado depois.
    TaskSegment.query.filter_by(task_id=task_id).delete()
    
    new_segments_list = []
    for segment_item in segments_data:
        try:
            start_date_str = segment_item.get('start_date')
            start_time_str = segment_item.get('start_time')
            due_date_str = segment_item.get('due_date')
            due_time_str = segment_item.get('due_time')
            description = segment_item.get('description')

            if not all([start_date_str, start_time_str, due_date_str, due_time_str]):
                current_app.logger.warning(f"Item de segmento inválido (datas/horas faltando): {segment_item}")
                continue # Pula este item

            # Combina data e hora e converte para datetime
            # Assume que as strings de data estão no formato YYYY-MM-DD e hora HH:MM
            segment_start_datetime = datetime.strptime(f"{start_date_str} {start_time_str}", "%Y-%m-%d %H:%M")
            segment_end_datetime = datetime.strptime(f"{due_date_str} {due_time_str}", "%Y-%m-%d %H:%M")
            
            if segment_end_datetime <= segment_start_datetime:
                current_app.logger.warning(f"Item de segmento inválido (fim antes ou igual ao início): {segment_item}")
                continue # Pula este item

            new_segment = TaskSegment(
                task_id=task_id,
                segment_start_datetime=segment_start_datetime,
                segment_end_datetime=segment_end_datetime,
                description=description
            )
            db.session.add(new_segment)
            new_segments_list.append(new_segment) # Adiciona à lista para retorno posterior (antes do commit)

        except ValueError as ve:
            current_app.logger.error(f"Erro de valor ao processar segmento {segment_item}: {ve}")
            # Pode-se optar por abortar ou continuar com os próximos segmentos
            continue 
        except Exception as e:
            current_app.logger.error(f"Erro inesperado ao processar segmento {segment_item}: {e}")
            db.session.rollback() # Desfaz a transação parcial se um erro geral ocorrer
            return jsonify({'message': 'Erro interno ao processar segmentos'}), 500

    try:
        db.session.commit()
        current_app.logger.info(f"Segmentos para tarefa {task_id} atualizados com sucesso. {len(new_segments_list)} segmentos processados.")
        
        # Busca os segmentos recém-criados/atualizados do banco para garantir que temos IDs e dados consistentes
        # É importante fazer isso APÓS o commit.
        updated_segments = TaskSegment.query.filter_by(task_id=task_id).order_by(TaskSegment.segment_start_datetime).all()
        return jsonify([s.to_dict() for s in updated_segments]), 200 # 200 OK pois substituímos
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao commitar segmentos para tarefa {task_id}: {e}")
        return jsonify({'message': 'Erro ao salvar segmentos no banco de dados'}), 500

# --- Fim Task Segment API Endpoints ---

# API para obter a lista de projetos ativos (usada pela página de seleção agora)
@backlog_bp.route('/api/projects')
def get_active_projects():
    try:
        macro_service = MacroService()
        dados_df = macro_service.carregar_dados()
        # Verifica se o DataFrame inicial está vazio
        if dados_df.empty:
            current_app.logger.info("DataFrame inicial vazio ou não carregado.")
            return jsonify([])
            
        # Chama obter_projetos_ativos, que agora retorna a lista completa de dicionários
        ativos_list = macro_service.obter_projetos_ativos(dados_df)
        
        # Verifica se a LISTA está vazia
        if not ativos_list:
             current_app.logger.info("Nenhum projeto ativo encontrado pelo MacroService.")
             return jsonify([])

        # --- SIMPLIFICAÇÃO: Retorna a lista como recebida do service --- 
        # A formatação, tratamento de nulos e seleção de colunas 
        # já foram feitos em obter_projetos_ativos.
        
        # Opcional: Ordenar aqui se não for feito no service
        ativos_list.sort(key=lambda x: x.get('projeto', '')) 
        
        # Renomeia as chaves para o frontend esperar (se necessário)
        # Ou ajusta o frontend para esperar 'numero', 'projeto', 'squad', etc.
        # Vamos manter as chaves do service por enquanto: 'numero', 'projeto', 'squad', 'especialista', 'status'
        # Apenas mapeamos 'numero' para 'id' e 'projeto' para 'name' para compatibilidade mínima
        projetos_final = []
        for p_dict in ativos_list:
            projetos_final.append({
                'id': p_dict.get('numero'), 
                'name': p_dict.get('projeto'),
                'squad': p_dict.get('squad'),
                'specialist': p_dict.get('especialista'),
                'status': p_dict.get('status')
            })
            
        current_app.logger.info(f"Retornando {len(projetos_final)} projetos ativos com detalhes para API.")
        return jsonify(projetos_final)
        # ---------------------------------------------------------------
        
    except Exception as e:
        # Log do erro completo
        current_app.logger.error(f"Erro ao buscar projetos ativos: {e}", exc_info=True)
        abort(500, description="Erro interno ao buscar projetos ativos.")

# API para obter colunas
@backlog_bp.route('/api/columns')
def get_columns():
    columns = Column.query.order_by(Column.position).all()
    columns_list = [{'id': c.id, 'name': c.name, 'position': c.position} for c in columns]
    return jsonify(columns_list)

# API para obter tarefas (Agora pode ser chamada pelo board_by_project ou pelo JS)
# Vamos manter o filtro por backlog_id
@backlog_bp.route('/api/tasks')
def get_tasks():
    backlog_id_filter = request.args.get('backlog_id', type=int)
    query = Task.query
    if backlog_id_filter:
        query = query.filter_by(backlog_id=backlog_id_filter)
    
    tasks = query.order_by(Task.position).all()
    tasks_list = [serialize_task(t) for t in tasks]
    return jsonify(tasks_list)

# API para obter detalhes de uma tarefa específica
@backlog_bp.route('/api/tasks/<int:task_id>', methods=['GET'])
def get_task_details(task_id):
    task = Task.query.get_or_404(task_id)
    return jsonify(task.to_dict())

# API para atualizar detalhes de uma tarefa existente
@backlog_bp.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task_details(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    data = request.get_json()
    current_app.logger.info(f"Atualizando tarefa {task_id} com dados: {data}")

    # Mapeamento de status ID para nome para validação
    status_map = {col.id: col.name for col in Column.query.all()}
    
    # Validação e atualização dos campos
    if 'title' in data:
        task.title = data['title']
    if 'description' in data:
        task.description = data['description']
    if 'priority' in data:
        task.priority = data['priority']
    
    if 'estimated_hours' in data:
        try:
            # Permite valor nulo ou string vazia para limpar o campo
            if data.get('estimated_hours') and str(data['estimated_hours']).strip():
                task.estimated_effort = float(data['estimated_hours'])
            else:
                task.estimated_effort = None
        except (ValueError, TypeError):
            current_app.logger.warning(f"Valor inválido para estimated_hours: {data.get('estimated_hours')}")
            task.estimated_effort = None

    if 'specialist_name' in data:
        # Permite "Não atribuído" ou nulo para limpar o campo
        specialist = data['specialist_name']
        if specialist and specialist.lower() != 'não atribuído':
            task.specialist_name = specialist
        else:
            task.specialist_name = None
    
    # Novos campos adicionais
    if 'start_date' in data:
        if data['start_date']:
            try:
                task.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
            except ValueError:
                current_app.logger.warning(f"Formato inválido para start_date: {data['start_date']}")
        else:
            task.start_date = None
    
    if 'due_date' in data:
        if data['due_date']:
            try:
                task.due_date = datetime.strptime(data['due_date'], '%Y-%m-%d')
            except ValueError:
                current_app.logger.warning(f"Formato inválido para due_date: {data['due_date']}")
        else:
            task.due_date = None
    
    if 'logged_time' in data:
        try:
            if data.get('logged_time') is not None and str(data['logged_time']).strip():
                task.logged_time = float(data['logged_time'])
            else:
                task.logged_time = None
        except (ValueError, TypeError):
            current_app.logger.warning(f"Valor inválido para logged_time: {data.get('logged_time')}")
            task.logged_time = None
    
    if 'is_unplanned' in data:
        task.is_unplanned = bool(data['is_unplanned'])
    
    # 🎯 NOVOS CAMPOS: actually_started_at e completed_at editáveis
    if 'actually_started_at' in data:
        if data['actually_started_at']:
            try:
                task.actually_started_at = datetime.fromisoformat(data['actually_started_at'].replace('Z', '+00:00'))
            except ValueError:
                current_app.logger.warning(f"Formato inválido para actually_started_at: {data['actually_started_at']}")
        else:
            task.actually_started_at = None
    
    if 'completed_at' in data:
        if data['completed_at']:
            try:
                task.completed_at = datetime.fromisoformat(data['completed_at'].replace('Z', '+00:00'))
            except ValueError:
                current_app.logger.warning(f"Formato inválido para completed_at: {data['completed_at']}")
        else:
            task.completed_at = None
    
    if 'status' in data:
        try:
            status_id = int(data['status'])
            if status_id in status_map:
                # O ID da coluna é o próprio status_id no novo modelo
                task.column_id = status_id
            else:
                current_app.logger.error(f"Status ID '{status_id}' inválido recebido.")
                return jsonify({'error': f"Status inválido: {data['status']}"}), 400
        except (ValueError, TypeError):
            current_app.logger.error(f"Valor de status inválido recebido: {data['status']}. Esperado um ID numérico.")
            return jsonify({'error': f"Valor de status inválido: {data['status']}"}), 400

    db.session.commit()
    current_app.logger.info(f"Tarefa {task_id} atualizada com sucesso.")
    
    # Usar serialize_task em vez de task.to_dict()
    return jsonify(serialize_task(task))

# API para excluir uma tarefa (VERSÃO OTIMIZADA)
@backlog_bp.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    try:
        # OTIMIZAÇÃO: Captura informações antes da exclusão
        old_column_id = task.column_id
        old_position = task.position
        old_sprint_id = task.sprint_id
        
        # OTIMIZAÇÃO: Executa updates em batch sem logs excessivos
        if old_sprint_id:
            # Para tarefas em sprints, ajusta posições apenas dentro da sprint
            Task.query.filter(
                Task.sprint_id == old_sprint_id,
                Task.position > old_position
            ).update({Task.position: Task.position - 1}, synchronize_session=False)
        else:
            # Para tarefas fora de sprints, ajusta posições na coluna
            Task.query.filter(
                Task.column_id == old_column_id,
                Task.position > old_position
            ).update({Task.position: Task.position - 1}, synchronize_session=False)
        
        # OTIMIZAÇÃO: Exclusão da tarefa sem logs desnecessários
        db.session.delete(task)
        db.session.commit()
        
        # OTIMIZAÇÃO: Log mínimo apenas
        return '', 204 
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao excluir tarefa {task_id}: {str(e)}")
        abort(500, description="Erro interno ao excluir a tarefa.")

# API para criar uma nova tarefa em um backlog específico
@backlog_bp.route('/api/backlogs/<int:backlog_id>/tasks', methods=['POST'])
def create_task(backlog_id):
    backlog = Backlog.query.get_or_404(backlog_id)
    data = request.get_json()

    # <<< INÍCIO: Obter especialista padrão do projeto >>>
    default_specialist = None
    try:
        macro_service = MacroService()
        project_details = macro_service.obter_detalhes_projeto(backlog.project_id)
        if project_details and project_details.get('specialist'):
            default_specialist = project_details['specialist']
            current_app.logger.info(f"Especialista padrão para projeto {backlog.project_id}: {default_specialist}")
        else:
            current_app.logger.warning(f"Não foi possível obter especialista padrão para projeto {backlog.project_id}.")
    except Exception as e:
        current_app.logger.error(f"Erro ao buscar detalhes do projeto {backlog.project_id} para obter especialista padrão: {e}", exc_info=True)
        # Continua a criação da tarefa mesmo se não encontrar o especialista padrão
    # <<< FIM: Obter especialista padrão do projeto >>>

    # Encontra a primeira coluna (ex: 'A Fazer') por posição
    first_column = Column.query.order_by(Column.position).first()
    if not first_column:
        abort(500, description="Nenhuma coluna encontrada no sistema. Crie colunas primeiro.")

    # Calcula a posição da nova tarefa (no final da primeira coluna)
    max_pos = db.session.query(db.func.max(Task.position)).filter_by(column_id=first_column.id).scalar()
    new_position = (max_pos or -1) + 1

    # Processa campos opcionais
    start_date_obj = None # Inicializa fora do try
    if data.get('start_date'):
        try:
            start_date_obj = datetime.strptime(data['start_date'], '%Y-%m-%d')
        except ValueError:
            abort(400, description="Formato inválido para 'start_date'. Use YYYY-MM-DD.")

    estimated_effort_val = None # Inicializa fora do try
    # --- CORREÇÃO: Espera 'estimated_hours' vindo do frontend --- 
    if data.get('estimated_hours') is not None and data['estimated_hours'] != '':
        try:
            estimated_effort_val = float(data['estimated_hours'])
            if estimated_effort_val < 0:
                abort(400, description="'estimated_hours' não pode ser negativo.")
        except ValueError:
            abort(400, description="Valor inválido para 'estimated_hours'. Use um número.")

    due_date_obj = None # Inicializa fora do try
    if data.get('due_date'):
        try:
            due_date_obj = datetime.strptime(data['due_date'], '%Y-%m-%d') # Valida o formato
        except ValueError:
            abort(400, description="Formato inválido para 'due_date'. Use YYYY-MM-DD.")
    
    logged_time_val = None # Inicializa fora do try
    if data.get('logged_time') is not None and data['logged_time'] != '':
        try:
            logged_time_val = float(data['logged_time'])
            if logged_time_val < 0:
                abort(400, description="'logged_time' não pode ser negativo.")
        except ValueError:
            abort(400, description="Valor inválido para 'logged_time'. Use um número.")

    new_task = Task(
        title=data.get('title', 'Nova Tarefa').strip(),
        description=data.get('description'),
        status=TaskStatus.TODO, # Status inicial sempre TODO
        priority=data.get('priority', 'Média'), # Adiciona prioridade
        estimated_effort=estimated_effort_val, # <<< Usa a variável processada
        logged_time=logged_time_val, # <<< NOVO CAMPO >>>
        position=new_position,
        start_date=start_date_obj, # <<< Usa a variável processada
        due_date=due_date_obj, # <<< CORREÇÃO: Usa o objeto datetime validado
        backlog_id=backlog.id,
        column_id=first_column.id, # Atribui à primeira coluna
        specialist_name=data.get('specialist_name') or default_specialist, # Usa o do payload ou o padrão
        is_unplanned=data.get('is_unplanned', False) # <<< NOVO CAMPO >>>
    )
    db.session.add(new_task)
    db.session.commit()
    
    # Recarrega a tarefa para obter relacionamentos (como task.column)
    db.session.refresh(new_task)

    return jsonify(serialize_task(new_task)), 201 # Retorna a tarefa criada

# API para mover/atualizar uma tarefa (coluna, posição, etc.)
@backlog_bp.route('/api/tasks/<int:task_id>/move', methods=['PUT'])
def move_task(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.get_json()

    if not data:
        abort(400, description="Nenhum dado fornecido para atualização.")

    new_column_id = data.get('column_id')
    new_position = data.get('position', 0) # Posição padrão se não fornecida

    if new_column_id is None:
        abort(400, description="'column_id' é obrigatório para mover.")

    target_column = Column.query.get(new_column_id)
    if not target_column:
        abort(400, description=f"Coluna de destino com id {new_column_id} não encontrada.")

    old_column_id = task.column_id
    old_position = task.position
    is_moving_to_done = target_column.name.upper() == 'CONCLUÍDO' # Verifica se está movendo para Concluído
    was_in_done = task.column.name.upper() == 'CONCLUÍDO' if task.column else False
    
    # Verifica se está movendo para Em Andamento
    is_moving_to_progress = target_column.name.upper() == 'EM ANDAMENTO'
    was_in_progress = task.column.name.upper() == 'EM ANDAMENTO' if task.column else False

    # Lógica para reordenar as tarefas nas colunas afetadas
    # Se moveu para uma coluna diferente
    if old_column_id != new_column_id:
        # Decrementa posição das tarefas na coluna antiga que estavam depois da tarefa movida
        Task.query.filter(
            Task.column_id == old_column_id,
            Task.position > old_position
        ).update({Task.position: Task.position - 1}, synchronize_session='fetch')
        
        # Incrementa posição das tarefas na coluna nova que estão na nova posição ou depois
        Task.query.filter(
            Task.column_id == new_column_id,
            Task.position >= new_position
        ).update({Task.position: Task.position + 1}, synchronize_session='fetch')
    else:
        # Moveu dentro da mesma coluna
        if new_position > old_position:
            # Moveu para baixo: decrementa os entre old_pos+1 e new_pos
            Task.query.filter(
                Task.column_id == new_column_id,
                Task.position > old_position,
                Task.position <= new_position
            ).update({Task.position: Task.position - 1}, synchronize_session='fetch')
        elif new_position < old_position:
            # Moveu para cima: incrementa os entre new_pos e old_pos-1
            Task.query.filter(
                Task.column_id == new_column_id,
                Task.position >= new_position,
                Task.position < old_position
            ).update({Task.position: Task.position + 1}, synchronize_session='fetch')

    # Atualiza a tarefa movida
    task.column_id = new_column_id
    task.position = new_position

    # 🎯 NOVA LÓGICA: Define data de início real quando sai de "A Fazer"
    # Verifica se está saindo de "A Fazer" para qualquer status que não seja "Concluído"
    is_leaving_todo = task.column.name.upper() == 'A FAZER' if task.column else False
    is_moving_to_review = target_column.name.upper() == 'REVISÃO'
    
    # Preenche actually_started_at quando:
    # 1. Move para "Em Andamento" OU
    # 2. Move diretamente de "A Fazer" para "Revisão" OU  
    # 3. Move diretamente de "A Fazer" para "Concluído"
    # 4. Ainda não tem data de início real
    should_set_start_time = (
        is_moving_to_progress or 
        (is_leaving_todo and is_moving_to_review) or
        (is_leaving_todo and is_moving_to_done)
    )
    
    if not task.actually_started_at and should_set_start_time:
        task.actually_started_at = datetime.now(br_timezone)
        if is_moving_to_progress:
            action_desc = "Em Andamento"
        elif is_moving_to_review:
            action_desc = "Revisão (início direto)"
        else:
            action_desc = "Concluído (início direto)"
        current_app.logger.info(f"[Task Moved] Tarefa {task.id} movida para {action_desc}, data de INÍCIO REAL definida para {task.actually_started_at} (usando br_timezone)")

    # Atualiza data de início planejada (LEGADO - manter por enquanto se houver dependências)
    # if is_moving_to_progress and not was_in_progress:
    #     if not task.start_date:  # Define apenas na primeira vez que entra em EM ANDAMENTO
    #         task.start_date = datetime.utcnow()
    #         current_app.logger.info(f"[Task Moved] Tarefa {task.id} movida para Em Andamento, data de início definida")

    # Atualiza status e data de conclusão
    if is_moving_to_done:
        task.status = TaskStatus.DONE
        if not task.completed_at: # Define apenas se NÃO houver data de conclusão prévia
            task.completed_at = datetime.utcnow()
            current_app.logger.info(f"[Task Moved] Tarefa {task.id} movida para Concluído, data de conclusão definida.")
        else:
            current_app.logger.info(f"[Task Moved] Tarefa {task.id} movida para Concluído, data de conclusão existente mantida: {task.completed_at}")
    else:
        # Se saiu de DONE, NÃO limpa mais a data de conclusão automaticamente.
        # A data de conclusão (se existir) é mantida para fins de histórico.
        # O status da tarefa é atualizado com base na nova coluna.
        
        # Tenta mapear nome da coluna para status comparando com os valores do Enum
        found_status = False
        for status_member in TaskStatus:
            # Compara o valor do enum (ex: 'A Fazer') com o nome da coluna do BD
            if status_member.value.upper() == target_column.name.upper():
                task.status = status_member
                found_status = True
                current_app.logger.info(f"[Task Moved] Tarefa {task.id} movida para coluna '{target_column.name}', status definido para '{task.status.value}'.")
                break 
        
        if not found_status: 
            # Fallback se o nome da coluna não corresponder diretamente a um TaskStatus.value
            if task.status == TaskStatus.DONE: # Só muda se ESTAVA em DONE e não encontrou novo status válido
                 task.status = TaskStatus.TODO # Ou TaskStatus.IN_PROGRESS, dependendo da regra de negócio
                 current_app.logger.info(f"[Task Moved] Tarefa {task.id} saiu de 'Concluído' para coluna '{target_column.name}', status revertido para '{task.status.value}' (fallback)." )
            # else: # Se não estava em DONE e não achou match, o status atual é mantido (pode ser TODO, IN_PROGRESS etc)
            #    current_app.logger.info(f"[Task Moved] Tarefa {task.id} movida para coluna '{target_column.name}', status MANTIDO como '{task.status.value}' pois não estava em 'Concluído' e não houve match de coluna para novo status.")

    db.session.commit()
    
    # Recarrega a tarefa para obter relacionamentos atualizados
    db.session.refresh(task)

    return jsonify(serialize_task(task))

# API para obter ou criar backlog para um projeto específico
@backlog_bp.route('/api/projects/<string:project_id>/backlog', methods=['GET', 'POST'])
def project_backlog(project_id):
    if request.method == 'GET':
        backlog = Backlog.query.filter_by(project_id=project_id).first()
        if backlog:
            return jsonify({'id': backlog.id, 'name': backlog.name, 'project_id': backlog.project_id})
        else:
            # Retorna 404 se o backlog não existe (o frontend pode oferecer criar)
            return jsonify({'message': 'Backlog não encontrado para este projeto'}), 404
            
    elif request.method == 'POST':
        # Verifica se já existe
        existing_backlog = Backlog.query.filter_by(project_id=project_id).first()
        if existing_backlog:
            return jsonify({'message': 'Backlog já existe para este projeto', 'id': existing_backlog.id}), 409 # Conflict
        
        # TODO: Validar se project_id realmente existe nos dados do MacroService?
        # (Opcional, mas recomendado)
        
        # Cria o novo backlog
        data = request.get_json() or {}
        backlog_name = data.get('name', f'Backlog Projeto {project_id}') # Nome padrão
        
        new_backlog = Backlog(project_id=project_id, name=backlog_name)
        db.session.add(new_backlog)
        db.session.commit()
        
        return jsonify({'id': new_backlog.id, 'name': new_backlog.name, 'project_id': new_backlog.project_id}), 201

# --- ADICIONAR ROTA PARA DETALHES DO PROJETO --- 
@backlog_bp.route('/api/projects/<string:project_id>/details', methods=['GET'])
def get_project_details(project_id):
    try:
        # --- USA O MÉTODO REAL DO MacroService --- 
        macro_service = MacroService()
        project_details = macro_service.obter_detalhes_projeto(project_id)
        # -----------------------------------------
        
        if not project_details: 
             # O método do serviço já logou o warning/erro
             return jsonify({'message': 'Detalhes do projeto não encontrados'}), 404
        
        # Adiciona informações do backlog se existir
        backlog = Backlog.query.filter_by(project_id=project_id).first()
        if backlog:
            project_details['backlog'] = {
                'id': backlog.id,
                'name': backlog.name,
                'available_for_sprint': backlog.available_for_sprint,
                'created_at': backlog.created_at.isoformat() if backlog.created_at else None
            }
        else:
            project_details['backlog'] = None
             
        return jsonify(project_details)
        
    except Exception as e:
        current_app.logger.error(f"Erro ao buscar detalhes do projeto {project_id}: {e}", exc_info=True)
        abort(500, description="Erro interno ao buscar detalhes do projeto.")
# ------------------------------------------------

# --- NOVA ROTA PARA DADOS DO CABEÇALHO ---
@backlog_bp.route('/api/projects/<string:project_id>/header-details', methods=['GET'])
def get_project_header_details(project_id):
    """
    Retorna dados formatados para o cabeçalho do projeto no quadro Kanban.
    """
    current_app.logger.info(f"Buscando dados de cabeçalho para o projeto {project_id}")
    macro_service = MacroService()
    details = macro_service.obter_detalhes_projeto(project_id)

    if not details:
        current_app.logger.warning(f"Nenhum detalhe encontrado para o projeto {project_id} no MacroService.")
        return jsonify({
            'project_name': 'Projeto não encontrado',
            'specialist': 'N/A',
            'status': 'N/A',
            'estimated_hours': '-',
            'remaining_hours': '-',
            'account_manager': 'N/A'
        }), 404

    # O serviço já deve retornar chaves minúsculas, mas garantimos aqui.
    details = {str(k).lower(): v for k, v in details.items()}

    # Formata os dados para o frontend, tratando valores nulos ou vazios
    estimated_hours = details.get('horas', 0)
    remaining_hours = details.get('horasrestantes', 0)

    header_data = {
        'project_name': details.get('projeto', 'Nome não disponível'),
        'specialist': details.get('especialista', 'Não atribuído'),
        'status': details.get('status', 'Status não definido'),
        'estimated_hours': f"{estimated_hours:.0f}h" if pd.notna(estimated_hours) and estimated_hours > 0 else "-",
        'remaining_hours': f"{remaining_hours:.0f}h" if pd.notna(remaining_hours) and remaining_hours > 0 else "-",
        'account_manager': details.get('account_manager', 'N/A')
    }
    
    # Adiciona informação de complexidade se existir
    try:
        from ..models import ProjectComplexityAssessment
        latest_assessment = ProjectComplexityAssessment.query.filter_by(project_id=project_id).order_by(ProjectComplexityAssessment.created_at.desc()).first()
        
        if latest_assessment:
            complexity_info = {
                "score": latest_assessment.total_score,
                "category": latest_assessment.complexity_category,  # Este campo é string, não enum
                "category_label": latest_assessment.complexity_category  # Usa o mesmo valor para label
            }
            header_data['complexity'] = complexity_info
        else:
            header_data['complexity'] = None
            
    except Exception as e:
        current_app.logger.warning(f"Erro ao buscar complexidade para o cabeçalho do projeto {project_id}: {e}")
        header_data['complexity'] = None
    
    current_app.logger.info(f"Dados do cabeçalho para o projeto {project_id}: {header_data}")
    return jsonify(header_data)
# --- FIM DA NOVA ROTA ---

# Adicionar rotas para CRUD de Sprints se necessário... 

# API para obter tarefas não alocadas a sprints, agrupadas por backlog/projeto
# ✅ CACHE OTIMIZADO: Cache global para projetos ativos (reduz logs MacroService)
import time
_ACTIVE_PROJECTS_CACHE = {
    'data': None,
    'timestamp': None,
    'ttl_seconds': 300  # 5 minutos de cache para projetos ativos
}

def _get_cached_active_projects():
    """Retorna projetos ativos do cache se válido."""
    if (_ACTIVE_PROJECTS_CACHE['data'] is not None and 
        _ACTIVE_PROJECTS_CACHE['timestamp'] is not None):
        elapsed = time.time() - _ACTIVE_PROJECTS_CACHE['timestamp']
        if elapsed < _ACTIVE_PROJECTS_CACHE['ttl_seconds']:
            return _ACTIVE_PROJECTS_CACHE['data']
    return None

def _set_cached_active_projects(project_ids):
    """Cacheia IDs de projetos ativos."""
    _ACTIVE_PROJECTS_CACHE['data'] = project_ids
    _ACTIVE_PROJECTS_CACHE['timestamp'] = time.time()

@backlog_bp.route('/api/backlogs/unassigned-tasks')
def get_unassigned_tasks():
    macro_service = MacroService() # Re-adiciona instância do serviço
    try:
        # 1. Busca todas as tarefas sem sprint_id E QUE NÃO SÃO GENÉRICAS,
        #    APENAS de backlogs disponíveis para sprint,
        #    ordenadas por backlog e posição
        unassigned_tasks = Task.query.filter(
                                        Task.sprint_id == None,
                                        Task.is_generic == False # Simplifica a condição
                                      )\
                                      .join(Backlog)\
                                      .filter(Backlog.available_for_sprint == True)\
                                      .order_by(Task.backlog_id, Task.position).all()

        # 2. Agrupa as tarefas por backlog_id
        tasks_by_backlog = {}
        for task in unassigned_tasks:
            if task.backlog_id not in tasks_by_backlog:
                tasks_by_backlog[task.backlog_id] = []
            tasks_by_backlog[task.backlog_id].append(serialize_task(task))

        # 3. Formata a resposta final
        result = []
        if tasks_by_backlog:
            # Busca os detalhes dos backlogs que têm tarefas não alocadas
            backlog_ids = list(tasks_by_backlog.keys())
            backlogs = Backlog.query.filter(Backlog.id.in_(backlog_ids)).all()
            backlog_details_map = {b.id: b for b in backlogs}

            # Re-adiciona busca de detalhes dos projetos
            project_ids = list(set(b.project_id for b in backlogs)) # Evita buscar o mesmo ID várias vezes
            
            # ✅ OTIMIZAÇÃO AGRESSIVA: Usar cache para projetos ativos (reduz logs drasticamente)
            active_project_ids = _get_cached_active_projects()
            
            if active_project_ids is None and project_ids:
                try:
                    # Cache miss - buscar projetos ativos (RARO após implementação)
                    dados_df = macro_service.carregar_dados()
                    if not dados_df.empty:
                        projects_data = macro_service.obter_projetos_ativos(dados_df)
                        if projects_data:
                            active_project_ids = set(str(p.get('numero', '')) for p in projects_data if p.get('numero'))
                            # Cacheia resultado para próximas 5 minutos
                            _set_cached_active_projects(active_project_ids)
                            current_app.logger.info(f"[Unassigned Tasks] Cache miss: {len(active_project_ids)} projetos ativos carregados e cacheados por 5min")
                        else:
                            active_project_ids = set()
                            _set_cached_active_projects(active_project_ids)
                    else:
                        current_app.logger.warning("DataFrame vazio ao carregar dados para filtrar projetos ativos")
                        active_project_ids = set(project_ids)
                        _set_cached_active_projects(active_project_ids)
                except Exception as e:
                    current_app.logger.warning(f"Erro ao buscar projetos ativos: {e}")
                    # Se falhar, considera todos os projetos como ativos
                    active_project_ids = set(project_ids)
                    _set_cached_active_projects(active_project_ids)
            elif active_project_ids is not None:
                # ✅ Cache hit - ZERO logs para evitar spam (operação mais comum)
                pass
            
            # OTIMIZAÇÃO: Instanciar macro_service uma vez e usar cache interno
            if project_ids:
                macro_service = MacroService()
                # Cache otimizado: O MacroService agora usa cache interno de 30-60 segundos
                # Isso elimina os 155 logs por projeto e melhora drasticamente a performance
                project_details_map = {}
                for pid in project_ids:
                    try:
                        # OTIMIZAÇÃO: obter_detalhes_projeto agora usa cache e logs mínimos
                        details = macro_service.obter_detalhes_projeto(pid)
                        project_details_map[pid] = details
                    except Exception as e:
                        # Log apenas em caso de erro real
                        current_app.logger.warning(f"Erro ao buscar detalhes do projeto {pid}: {e}")
                        project_details_map[pid] = None
            else:
                project_details_map = {}

            for backlog_id, tasks in tasks_by_backlog.items():
                backlog = backlog_details_map.get(backlog_id)
                if backlog:
                    # NOVO: Verifica se o projeto está ativo
                    if backlog.project_id not in active_project_ids:
                        current_app.logger.debug(f"[Unassigned Tasks] Projeto {backlog.project_id} não está ativo, ignorando backlog")
                        continue
                    
                    project_details = project_details_map.get(backlog.project_id)
                    
                    # OTIMIZAÇÃO: Removido log excessivo de project details
                    # Pega o NOME DO PROJETO, usa 'Nome Indisponível' se não encontrar
                    # CORREÇÃO: A função _normalize_key converte 'Projeto' para 'projeto'
                    project_name = project_details.get('projeto', 'Nome Indisponível') if project_details else 'Nome Indisponível'

                    result.append({
                        'backlog_id': backlog.id,
                        'backlog_name': backlog.name, # Nome do Backlog (Ex: Backlog Principal)
                        'project_id': backlog.project_id, # ID do Projeto associado
                        'project_name': project_name, # << NOME DO PROJETO CORRIGIDO
                        'tasks': tasks,
                        'available_for_sprint': backlog.available_for_sprint  # NOVO: Inclui flag de disponibilidade
                    })
                else:
                    # OTIMIZAÇÃO: Log apenas em WARNING para casos raros
                    current_app.logger.warning(f"Tarefas órfãs encontradas para backlog_id {backlog_id}")

        # Opcional: Ordenar a lista de backlogs/projetos resultantes
        result.sort(key=lambda x: (x.get('project_id', '')))

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Erro ao buscar tarefas não alocadas: {e}", exc_info=True)
        return jsonify({"message": "Erro interno ao buscar tarefas não alocadas."}), 500

# API para atualizar disponibilidade de backlog para sprints
@backlog_bp.route('/api/backlogs/<int:backlog_id>/sprint-availability', methods=['PUT'])
def update_backlog_sprint_availability(backlog_id):
    """
    Atualiza se um backlog deve aparecer no módulo de sprints
    """
    try:
        backlog = Backlog.query.get_or_404(backlog_id)
        data = request.get_json()
        
        if 'available_for_sprint' not in data:
            return jsonify({'error': 'Campo available_for_sprint é obrigatório'}), 400
        
        old_value = backlog.available_for_sprint
        new_value = bool(data['available_for_sprint'])
        
        backlog.available_for_sprint = new_value
        db.session.commit()
        
        action = "habilitado" if new_value else "desabilitado"
        current_app.logger.info(f"Backlog {backlog_id} (Projeto {backlog.project_id}) {action} para sprints")
        
        return jsonify({
            'message': f'Backlog {action} para sprints com sucesso',
            'backlog_id': backlog.id,
            'project_id': backlog.project_id,
            'available_for_sprint': backlog.available_for_sprint,
            'changed': old_value != new_value
        })
        
    except Exception as e:
        current_app.logger.error(f"Erro ao atualizar disponibilidade do backlog {backlog_id}: {e}", exc_info=True)
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500 

# API para associar/desassociar uma tarefa a uma Sprint
@backlog_bp.route('/api/tasks/<int:task_id>/assign', methods=['PUT'])
def assign_task_to_sprint(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.get_json()

    if data is None:
        abort(400, description="Corpo da requisição ausente ou inválido.")

    new_sprint_id = data.get('sprint_id')
    new_position = data.get('position')
    
    if new_position is None or not isinstance(new_position, int) or new_position < 0:
        abort(400, description="Campo 'position' ausente ou inválido. Deve ser um inteiro não negativo.")

    if new_sprint_id is not None:
        try:
            new_sprint_id = int(new_sprint_id)
            target_sprint = Sprint.query.get(new_sprint_id)
            if not target_sprint:
                abort(400, description=f"Sprint com ID {new_sprint_id} não encontrada.")
        except (ValueError, TypeError):
             abort(400, description="Valor inválido para 'sprint_id'. Deve ser um número ou null.")

    old_sprint_id = task.sprint_id
    old_position = task.position

    # OTIMIZAÇÃO: Log mínimo apenas para debugging crítico se necessário
    # current_app.logger.info(f"[AssignTask] Iniciando. TaskID: {task_id}, OldSprint: {old_sprint_id}, OldPos: {old_position}, NewSprint: {new_sprint_id}, NewPos: {new_position}")

    try:
        # 1. Ajusta posições na lista de ORIGEM (se diferente da destino)
        if old_sprint_id != new_sprint_id:
            if old_sprint_id is None:
                if task.is_generic:
                    # Para tarefas genéricas, ajusta posições apenas entre tarefas genéricas
                    Task.query.filter(
                        Task.is_generic == True,
                        Task.sprint_id == None,
                        Task.position > old_position
                    ).update({Task.position: Task.position - 1}, synchronize_session=False)
                else:
                    # Para tarefas do backlog, mantém o comportamento original
                    Task.query.filter(
                        Task.backlog_id == task.backlog_id,
                        Task.sprint_id == None,
                        Task.position > old_position
                    ).update({Task.position: Task.position - 1}, synchronize_session=False)
            else:
                Task.query.filter(
                    Task.sprint_id == old_sprint_id,
                    Task.position > old_position
                ).update({Task.position: Task.position - 1}, synchronize_session=False)
        
        # 2. Ajusta posições na lista de DESTINO
        if old_sprint_id != new_sprint_id:
            if new_sprint_id is None:
                if task.is_generic:
                    # Para tarefas genéricas, ajusta posições apenas entre tarefas genéricas
                    Task.query.filter(
                        Task.is_generic == True,
                        Task.sprint_id == None,
                        Task.position >= new_position
                    ).update({Task.position: Task.position + 1}, synchronize_session=False)
                else:
                    # Para tarefas do backlog, mantém o comportamento original
                    Task.query.filter(
                        Task.backlog_id == task.backlog_id,
                        Task.sprint_id == None,
                        Task.position >= new_position
                    ).update({Task.position: Task.position + 1}, synchronize_session=False)
            else:
                Task.query.filter(
                    Task.sprint_id == new_sprint_id,
                    Task.position >= new_position
                ).update({Task.position: Task.position + 1}, synchronize_session=False)
        else:
            if new_position > old_position:
                if new_sprint_id is not None:
                    Task.query.filter(
                        Task.sprint_id == new_sprint_id,
                        Task.position > old_position,
                        Task.position <= new_position
                    ).update({Task.position: Task.position - 1}, synchronize_session=False)
                else:
                    if task.is_generic:
                        Task.query.filter(
                            Task.is_generic == True,
                            Task.sprint_id == None,
                            Task.position > old_position,
                            Task.position <= new_position
                        ).update({Task.position: Task.position - 1}, synchronize_session=False)
                    else:
                        Task.query.filter(
                            Task.backlog_id == task.backlog_id,
                            Task.sprint_id == None,
                            Task.position > old_position,
                            Task.position <= new_position
                        ).update({Task.position: Task.position - 1}, synchronize_session=False)
            elif new_position < old_position:
                if new_sprint_id is not None:
                    Task.query.filter(
                        Task.sprint_id == new_sprint_id,
                        Task.position >= new_position,
                        Task.position < old_position
                    ).update({Task.position: Task.position + 1}, synchronize_session=False)
                else:
                    if task.is_generic:
                        Task.query.filter(
                            Task.is_generic == True,
                            Task.sprint_id == None,
                            Task.position >= new_position,
                            Task.position < old_position
                        ).update({Task.position: Task.position + 1}, synchronize_session=False)
                    else:
                        Task.query.filter(
                            Task.backlog_id == task.backlog_id,
                            Task.sprint_id == None,
                            Task.position >= new_position,
                            Task.position < old_position
                        ).update({Task.position: Task.position + 1}, synchronize_session=False)

        # 3. Atualiza sprint_id e position
        task.sprint_id = new_sprint_id
        task.position = new_position

        # 🎯 NOVA LÓGICA: Atualiza datas quando atribui à sprint
        if new_sprint_id is not None and target_sprint:
            # SEMPRE SOBRESCREVE as datas com as datas da sprint
            task.start_date = target_sprint.start_date  # Data início planejada = início da sprint
            task.due_date = target_sprint.end_date      # Data vencimento = fim da sprint
            current_app.logger.info(f"[AssignTask] Tarefa {task_id} atribuída à sprint {new_sprint_id}. Datas atualizadas: início={target_sprint.start_date}, fim={target_sprint.end_date}")
        elif new_sprint_id is None:
            # Quando remove da sprint, mantém as datas (não limpa automaticamente)
            # Permite que o usuário edite manualmente se necessário
            current_app.logger.info(f"[AssignTask] Tarefa {task_id} removida da sprint. Datas planejadas mantidas para referência.")

        db.session.commit()
        db.session.refresh(task)
        
        # OTIMIZAÇÃO: Usar função otimizada se a tarefa está em uma sprint
        if new_sprint_id:
            return jsonify(serialize_task_for_sprints(task))
        else:
            return jsonify(serialize_task(task))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao reordenar/associar tarefa {task_id} à sprint {new_sprint_id}: {e}", exc_info=True)
        abort(500, description="Erro interno ao atualizar posição/associação da sprint.")

# <<< INÍCIO: Nova API para listar especialistas disponíveis >>>
@backlog_bp.route('/api/available-specialists')
def get_available_specialists():
    """Retorna a lista de nomes de especialistas únicos do MacroService."""
    try:
        macro_service = MacroService()
        specialist_list = macro_service.get_specialist_list()
        return jsonify(specialist_list)
    except Exception as e:
        current_app.logger.error(f"Erro ao buscar lista de especialistas disponíveis: {e}", exc_info=True)
        # Retorna lista vazia em caso de erro grave
        return jsonify([]), 500
# <<< FIM: Nova API para listar especialistas disponíveis >>> 

# --- API para Marcos do Projeto --- 
@backlog_bp.route('/api/backlogs/<int:backlog_id>/milestones', methods=['GET'])
def get_milestones(backlog_id):
    """Retorna os marcos do projeto associado ao backlog."""
    try:
        # Verifica se o backlog existe
        backlog = Backlog.query.get_or_404(backlog_id)
        milestones = ProjectMilestone.query.filter_by(backlog_id=backlog_id).order_by(ProjectMilestone.planned_date).all()
        milestones_list = [m.to_dict() for m in milestones]
        return jsonify(milestones_list)
    except Exception as e:
        current_app.logger.error(f"Erro ao buscar marcos para backlog {backlog_id}: {e}", exc_info=True)
        abort(500, description="Erro interno ao buscar marcos do projeto.")

@backlog_bp.route('/api/milestones/<int:milestone_id>', methods=['GET'])
def get_milestone_details(milestone_id):
    """Retorna os detalhes de um marco específico."""
    milestone = ProjectMilestone.query.get_or_404(milestone_id)
    return jsonify(milestone.to_dict())

@backlog_bp.route('/api/milestones/<int:milestone_id>', methods=['PUT'])
def update_milestone(milestone_id):
    """Atualiza um marco existente."""
    milestone = ProjectMilestone.query.get_or_404(milestone_id)
    data = request.get_json()

    if not data:
        abort(400, description="Nenhum dado fornecido para atualização.")

    try:
        # Atualiza campos permitidos
        if 'name' in data:
            name = data['name'].strip()
            if not name:
                 abort(400, description="Nome não pode ser vazio.")
            milestone.name = name
            
        if 'description' in data:
            milestone.description = data.get('description', '') # Permite limpar a descrição
            
        if 'planned_date' in data:
            milestone.planned_date = datetime.strptime(data['planned_date'], '%Y-%m-%d').date()
            
        if 'actual_date' in data:
            actual_date_str = data['actual_date']
            milestone.actual_date = datetime.strptime(actual_date_str, '%Y-%m-%d').date() if actual_date_str else None
            
        if 'status' in data:
            status_key = data['status']
            if not status_key or status_key.strip() == '':
                status_key = 'PENDING'
            
            try:
                milestone.status = MilestoneStatus[status_key]
                if milestone.status == MilestoneStatus.COMPLETED and not milestone.actual_date:
                    milestone.actual_date = datetime.utcnow().date()
            except KeyError:
                valid_statuses = [s.name for s in MilestoneStatus]
                abort(400, description=f"Chave de Status inválida '{status_key}'. Válidas: {valid_statuses}")

        if 'criticality' in data:
            criticality_key = data['criticality']
            if not criticality_key or criticality_key.strip() == '':
                criticality_key = 'MEDIUM'
                
            try:
                milestone.criticality = MilestoneCriticality[criticality_key]
            except KeyError:
                valid_criticalities = [c.name for c in MilestoneCriticality]
                abort(400, description=f"Chave de Criticidade inválida '{criticality_key}'. Válidas: {valid_criticalities}")
        
        if 'is_checkpoint' in data:
            milestone.is_checkpoint = bool(data['is_checkpoint'])
        
        # Atualiza timestamp
        milestone.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Retorna o marco atualizado usando to_dict
        return jsonify(milestone.to_dict())
        
    except ValueError as ve:
        db.session.rollback()
        abort(400, description=str(ve))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao atualizar marco {milestone_id}: {e}", exc_info=True)
        abort(500, description="Erro interno ao atualizar marco do projeto.")

@backlog_bp.route('/api/milestones/<int:milestone_id>', methods=['DELETE'])
def delete_milestone(milestone_id):
    """Exclui um marco."""
    milestone = ProjectMilestone.query.get_or_404(milestone_id)
    try:
        db.session.delete(milestone)
        db.session.commit()
        current_app.logger.info(f"Marco ID {milestone_id} excluído com sucesso.")
        return '', 204 # Retorna 204 No Content para DELETE bem-sucedido
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao excluir marco {milestone_id}: {e}", exc_info=True)
        abort(500, description="Erro interno ao excluir marco do projeto.")

# --- API para Riscos e Impedimentos --- 
# (A implementação dos Riscos virá depois) 

# --- API para Riscos e Impedimentos ---

@backlog_bp.route('/api/backlogs/<int:backlog_id>/risks', methods=['GET'])
def get_backlog_risks(backlog_id):
    """Retorna todos os riscos associados a um backlog específico."""
    current_app.logger.info(f"[API GET RISKS] Buscando riscos para o backlog ID: {backlog_id}")
    backlog = Backlog.query.get_or_404(backlog_id) # Garante que o backlog existe
    
    risks = ProjectRisk.query.filter_by(backlog_id=backlog.id).order_by(ProjectRisk.created_at.desc()).all()
    current_app.logger.info(f"[API GET RISKS] {len(risks)} riscos encontrados para o backlog {backlog_id}")
    
    return jsonify([risk.to_dict() for risk in risks])

@backlog_bp.route('/api/risks/<int:risk_id>', methods=['GET'])
def get_risk_details(risk_id):
    """Retorna os detalhes de um risco específico."""
    risk = ProjectRisk.query.get_or_404(risk_id)
    return jsonify(risk.to_dict())

@backlog_bp.route('/api/risks', methods=['POST'])
def create_risk():
    """Cria um novo risco para o projeto (backlog_id vem no corpo)."""
    data = request.get_json()
    if not data:
        abort(400, description="Nenhum dado fornecido.")

    backlog_id = data.get('backlog_id')
    title = data.get('title')
    description = data.get('description')
    # --- CORREÇÃO: Usar .name para o padrão e esperar a CHAVE do frontend ---
    impact_str = data.get('impact', RiskImpact.MEDIUM.name)
    probability_str = data.get('probability', RiskProbability.MEDIUM.name)
    status_str = data.get('status', RiskStatus.IDENTIFIED.name)
    responsible = data.get('responsible')
    mitigation_plan = data.get('mitigation_plan')
    contingency_plan = data.get('contingency_plan')
    trend = data.get('trend',
                     'Estável')

    if not backlog_id or not title:
        abort(400, description="'backlog_id' e 'title' são obrigatórios.")

    backlog = Backlog.query.get_or_404(backlog_id)

    try:
        # Validar e converter enums com tratamento de valores vazios
        if not impact_str or impact_str.strip() == '':
            impact_str = RiskImpact.MEDIUM.name
        if not probability_str or probability_str.strip() == '':
            probability_str = RiskProbability.MEDIUM.name
        if not status_str or status_str.strip() == '':
            status_str = RiskStatus.IDENTIFIED.name
            
        # --- CORREÇÃO: Acessar Enum pela chave (ex: RiskStatus['IDENTIFIED']) ---
        impact = RiskImpact[impact_str]
        probability = RiskProbability[probability_str]
        status = RiskStatus[status_str]
    except KeyError as e:
        # Erro mais específico se a chave do Enum não for encontrada
        valid_impacts = [r.name for r in RiskImpact]
        valid_probabilities = [r.name for r in RiskProbability]
        valid_statuses = [r.name for r in RiskStatus]
        abort(400, description=f"Valores de chave inválidos para Enums. Chave não encontrada: {e}. Válidas: Impacto={valid_impacts}, Probabilidade={valid_probabilities}, Status={valid_statuses}")
    except ValueError as e:
        valid_impacts = [r.name for r in RiskImpact]
        valid_probabilities = [r.name for r in RiskProbability]
        valid_statuses = [r.name for r in RiskStatus]
        abort(400, description=f"Valores inválidos. Impacto='{impact_str}' (válidos: {valid_impacts}), Probabilidade='{probability_str}' (válidos: {valid_probabilities}), Status='{status_str}' (válidos: {valid_statuses})")

    new_risk = ProjectRisk(
        title=title,
        description=description,
        impact=impact,
        probability=probability,
        status=status,
        responsible=responsible,
        mitigation_plan=mitigation_plan,
        contingency_plan=contingency_plan,
        trend=trend,
        backlog_id=backlog.id,
        identified_date=datetime.utcnow() # Data de identificação é agora
    )

    try:
        db.session.add(new_risk)
        db.session.commit()
        current_app.logger.info(f"[API CREATE RISK] Risco ID {new_risk.id} criado para backlog {backlog.id}")
        return jsonify(new_risk.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[API CREATE RISK] Erro ao salvar risco no DB: {e}", exc_info=True)
        abort(500, description="Erro interno ao salvar o risco no banco de dados.")

@backlog_bp.route('/api/risks/<int:risk_id>', methods=['PUT'])
def update_risk(risk_id):
    """Atualiza um risco existente."""
    risk = ProjectRisk.query.get_or_404(risk_id)
    data = request.get_json()

    if not data:
        abort(400, description="Nenhum dado fornecido para atualização.")

    # Atualiza os campos (com validação para Enums)
    try:
        if 'title' in data:
            risk.title = data['title']
        if 'description' in data:
            risk.description = data['description']
        if 'impact' in data:
            impact_value = data['impact']
            if not impact_value or impact_value.strip() == '':
                impact_value = RiskImpact.MEDIUM.name
            risk.impact = RiskImpact[impact_value]  # Alterado para buscar pela chave
        if 'probability' in data:
            probability_value = data['probability']
            if not probability_value or probability_value.strip() == '':
                probability_value = RiskProbability.MEDIUM.name
            risk.probability = RiskProbability[probability_value]  # Alterado para buscar pela chave
        if 'status' in data:
            status_value = data['status']
            if not status_value or status_value.strip() == '':
                status_value = RiskStatus.IDENTIFIED.name
            risk.status = RiskStatus[status_value]  # Alterado para buscar pela chave
        if 'responsible' in data:
            risk.responsible = data.get('responsible')
        if 'mitigation_plan' in data:
            risk.mitigation_plan = data.get('mitigation_plan')
        if 'contingency_plan' in data:
            risk.contingency_plan = data.get('contingency_plan')
        if 'trend' in data:
            risk.trend = data.get('trend')
        if 'resolved_date' in data:
            resolved_date_str = data.get('resolved_date')
            risk.resolved_date = datetime.strptime(resolved_date_str, '%Y-%m-%d') if resolved_date_str else None
        
        risk.updated_at = datetime.utcnow() # Atualiza a data de modificação

    except KeyError as e:
        # Captura erro se alguma CHAVE de Enum for inválida
        valid_impacts = [r.name for r in RiskImpact]
        valid_probabilities = [r.name for r in RiskProbability]
        valid_statuses = [r.name for r in RiskStatus]
        abort(400, description=f"Chave de Enum inválida: {e}. Chaves válidas: Impacto={valid_impacts}, Probabilidade={valid_probabilities}, Status={valid_statuses}")
    except ValueError as e:
        # Captura erro se algum valor de Enum for inválido
        valid_impacts = [r.name for r in RiskImpact]
        valid_probabilities = [r.name for r in RiskProbability]
        valid_statuses = [r.name for r in RiskStatus]
        abort(400, description=f"Valores inválidos para enums. Detalhes: {str(e)}. Válidos: Impacto={valid_impacts}, Probabilidade={valid_probabilities}, Status={valid_statuses}")
    except Exception as e: # Outros erros de conversão, como data
        db.session.rollback()
        current_app.logger.error(f"[API UPDATE RISK] Erro de conversão de dados para risco {risk_id}: {e}", exc_info=True)
        abort(400, description=f"Erro na conversão de dados: {str(e)}")

    try:
        db.session.commit()
        current_app.logger.info(f"[API UPDATE RISK] Risco ID {risk.id} atualizado.")
        return jsonify(risk.to_dict())
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[API UPDATE RISK] Erro ao salvar atualizações do risco {risk_id} no DB: {e}", exc_info=True)
        abort(500, description="Erro interno ao atualizar o risco no banco de dados.")

@backlog_bp.route('/api/risks/<int:risk_id>', methods=['DELETE'])
def delete_risk_from_api(risk_id):
    """Exclui um risco específico."""
    current_app.logger.info(f"[API DELETE RISK] Recebida requisição para excluir Risco ID: {risk_id}")
    risk = ProjectRisk.query.get_or_404(risk_id)
    try:
        db.session.delete(risk)
        db.session.commit()
        current_app.logger.info(f"[API DELETE RISK] Risco ID: {risk_id} excluído do DB com sucesso.")
        # Retorna uma resposta vazia com status 204 No Content, que é comum para DELETE bem-sucedido
        return '', 204
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[API DELETE RISK] Erro ao excluir Risco ID: {risk_id} do DB: {e}", exc_info=True)
        abort(500, description="Erro interno ao excluir o risco do banco de dados.")

# NOVA API - Timeline de tarefas
@backlog_bp.route('/api/backlogs/<int:backlog_id>/timeline-tasks', methods=['GET'])
def get_timeline_tasks(backlog_id):
    """
    Retorna tarefas para exibição na linha do tempo, organizadas em três categorias:
    1. Recentemente concluídas (last_days) 
    2. Próximas no prazo (next_days)
    3. Recentemente iniciadas (last_days)
    
    Query params:
    - last_days: int (dias para trás, padrão: 7)
    - next_days: int (dias para frente, padrão: 7)
    """
    try:
        last_days_param = request.args.get('last_days', 7, type=int)
        next_days_param = request.args.get('next_days', 7, type=int)

        current_app.logger.info(f"[Timeline API] Buscando tarefas para backlog {backlog_id} com last_days={last_days_param}, next_days={next_days_param} (BRT Based)")

        backlog = Backlog.query.get_or_404(backlog_id)
        
        now_brt = datetime.now(br_timezone) # <<< USA BR_TIMEZONE
        today_brt_date = now_brt.date() # <<< Data de hoje em BRT

        # Define o início e o fim do dia de hoje em BRT (timezone-aware)
        start_of_today_brt = br_timezone.localize(datetime.combine(today_brt_date, datetime.min.time()))
        end_of_today_brt = br_timezone.localize(datetime.combine(today_brt_date, datetime.max.time()))
        
        # Data limite para "recentemente concluídas" (X dias atrás, início do dia em BRT)
        recent_past_limit_date_completed_brt = today_brt_date - timedelta(days=last_days_param)
        recent_past_limit_datetime_start_completed_brt = br_timezone.localize(datetime.combine(recent_past_limit_date_completed_brt, datetime.min.time()))

        # Data limite para "próximas tarefas" (Y dias à frente, fim do dia em BRT)
        upcoming_future_limit_date_brt = today_brt_date + timedelta(days=next_days_param)
        upcoming_future_limit_datetime_end_brt = br_timezone.localize(datetime.combine(upcoming_future_limit_date_brt, datetime.max.time()))

        # Data limite para "Tarefas Iniciadas Recentemente" (5 dias para trás, início do dia em BRT)
        days_for_recently_started = 5 
        recent_past_limit_date_started_brt = today_brt_date - timedelta(days=days_for_recently_started)
        recent_past_limit_datetime_start_started_brt = br_timezone.localize(datetime.combine(recent_past_limit_date_started_brt, datetime.min.time()))

        # 1. Tarefas Concluídas (todas, sem limite de data)
        all_completed_tasks_q = Task.query.filter(
            Task.backlog_id == backlog_id,
            Task.completed_at != None
        ).order_by(Task.completed_at.desc()).all()
        all_completed_tasks = [serialize_task(t) for t in all_completed_tasks_q]
        current_app.logger.info(f"[Timeline API] Encontradas {len(all_completed_tasks)} tarefas concluídas (todas).")

        # 2. Próximas Tarefas (com start_date nos próximos Y dias, NÃO Concluídas e NÃO Em Andamento)
        # start_date é Date, não DateTime. Comparação com today_brt_date e upcoming_future_limit_date_brt é direta.
        upcoming_tasks_q = Task.query.join(Column, Task.column_id == Column.id).filter(
            Task.backlog_id == backlog_id,
            Task.start_date != None,
            Task.start_date >= today_brt_date, 
            Task.start_date <= upcoming_future_limit_date_brt, 
            Column.name != 'Concluído', 
            Column.name != 'Em Andamento' 
        ).order_by(Task.start_date.asc()).all()
        upcoming_tasks = [serialize_task(t) for t in upcoming_tasks_q]
        current_app.logger.info(f"[Timeline API] Encontradas {len(upcoming_tasks)} próximas tarefas (BRT Based).")

        # 3. Tarefas Iniciadas Recentemente (actually_started_at nos últimos X dias E na coluna Em Andamento)
        # actually_started_at agora é BRT-aware.
        recently_started_tasks_q = Task.query.join(Column, Task.column_id == Column.id).filter(
            Task.backlog_id == backlog_id,
            Task.actually_started_at != None,
            Task.actually_started_at >= recent_past_limit_datetime_start_started_brt, 
            Task.actually_started_at <= end_of_today_brt, 
            Column.name == 'Em Andamento' 
        ).order_by(Task.actually_started_at.desc()).all()
        recently_started_tasks = [serialize_task(t) for t in recently_started_tasks_q]
        current_app.logger.info(f"[Timeline API] Encontradas {len(recently_started_tasks)} tarefas iniciadas recentemente (BRT Based, usando actually_started_at).")
        
        return jsonify({
            'all_completed': all_completed_tasks, # CHAVE RENOMEADA
            'upcoming_tasks': upcoming_tasks,
            'recently_started': recently_started_tasks
        })
            
    except Exception as e:
        current_app.logger.error(f"[Timeline API] Erro ao buscar tarefas da timeline para backlog {backlog_id}: {str(e)}", exc_info=True)
        return jsonify({
            'error': f"Erro ao buscar tarefas da timeline: {str(e)}",
            'all_completed': [], # CHAVE RENOMEADA
            'upcoming_tasks': [],
            'recently_started': []
        }), 500 

 

# ROTA PARA A AGENDA TÉCNICA
@backlog_bp.route('/agenda')
def technical_agenda():
    try:
        # Inicialmente, não estamos ligando a agenda a um projeto específico,
        # então current_project e current_project_id_for_link podem ser None ou ter valores padrão.
        # Se você decidir filtrar por projeto no futuro, precisará buscar esses dados.
        # Ex: project_id = request.args.get('project_id')
        # current_project = MacroService().obter_detalhes_projeto(project_id) if project_id else None
        # current_project_id_for_link = project_id
        
        current_app.logger.info("Acessando a Agenda Técnica.")
        return render_template(
            'backlog/agenda_tec.html',
            title="Agenda Técnica Consolidada", 
            current_project=None, # Ou detalhes de um projeto padrão/geral se aplicável
            current_project_id_for_link=None # ID para o link "Voltar ao Quadro"
        )
    except Exception as e:
        current_app.logger.error(f"Erro ao carregar a Agenda Técnica: {e}", exc_info=True)
        # Você pode redirecionar para uma página de erro ou retornar um erro 500
        abort(500) # Ou render_template('error.html', error=str(e))

# NOVA API PARA TAREFAS DA AGENDA TÉCNICA
@backlog_bp.route('/api/agenda/tasks', methods=['GET'])
def get_agenda_tasks():
    try:
        # Modificado para buscar TaskSegments e fazer join com Task para acessar os campos da tarefa pai
        # Filtra segmentos que têm uma data de início definida.
        task_segments = TaskSegment.query.join(Task, TaskSegment.task_id == Task.id)\
                                       .filter(TaskSegment.segment_start_datetime.isnot(None))\
                                       .all()
        
        current_app.logger.info(f"API /api/agenda/tasks: Encontrados {len(task_segments)} segmentos de tarefas com data de início.")
        
        events = []
        for segment in task_segments:
            task_pai = segment.task # Acessa a tarefa pai através do relacionamento

            start_datetime_str = None
            if segment.segment_start_datetime:
                start_datetime_str = segment.segment_start_datetime.strftime('%Y-%m-%dT%H:%M:%S')

            end_datetime_str = None
            if segment.segment_end_datetime:
                end_datetime_str = segment.segment_end_datetime.strftime('%Y-%m-%dT%H:%M:%S')
            
            specialist_name_cleaned = None
            if task_pai.specialist_name and task_pai.specialist_name.strip():
                specialist_name_cleaned = task_pai.specialist_name.strip()

            # Monta o título do evento. Se o segmento tiver descrição, concatena.
            event_title = task_pai.title
            if segment.description and segment.description.strip():
                event_title = f"{task_pai.title} - {segment.description.strip()}"

            event = {
                'id': str(segment.id), # ID do segmento é o ID do evento
                'title': event_title,
                'body': task_pai.description or '', # Descrição da tarefa pai como corpo principal
                'start': start_datetime_str,
                'end': end_datetime_str,
                'category': 'time', 
                'isAllDay': False, # Assumindo que segmentos sempre têm hora
                'calendarId': specialist_name_cleaned,
                'raw': { 
                    'taskId': task_pai.id,
                    'segmentId': segment.id,
                    'taskStatus': task_pai.status.value if task_pai.status else None,
                    'specialistName': task_pai.specialist_name,
                    'projectName': task_pai.backlog.project_id if task_pai.backlog else "N/A",
                    'projectId': task_pai.backlog.project_id if task_pai.backlog else None, 
                    'backlogName': task_pai.backlog.name if task_pai.backlog else None,
                    'backlogId': task_pai.backlog_id,
                    'segmentDescription': segment.description # Adiciona a descrição do segmento também no raw data
                }
            }
            events.append(event)
        
        current_app.logger.info(f"API /api/agenda/tasks: Retornando {len(events)} eventos de segmentos.")
        return jsonify(events)
    except Exception as e:
        current_app.logger.error(f"Erro em /api/agenda/tasks: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# --- FIM ROTAS AGENDA ---

# API para Notas movida para note_routes.py
# As funções abaixo estão comentadas e foram substituídas pelas novas implementações em note_routes.py
# @backlog_bp.route('/api/notes', methods=['GET'])
# def get_notes():
#     """Retorna todas as notas de um projeto ou tarefa específica."""
#     # Implementação movida para note_routes.py
#     pass

# @backlog_bp.route('/api/notes/<int:note_id>', methods=['GET'])
# def get_note(note_id):
#     """Retorna uma nota específica."""
#     # Implementação movida para note_routes.py
#     pass 

# @backlog_bp.route('/api/notes', methods=['POST'])
# def create_note():
#     """Cria uma nova nota."""
#     # Implementação movida para note_routes.py
#     pass

# @backlog_bp.route('/api/notes/<int:note_id>', methods=['PUT'])
# def update_note(note_id):
#     """Atualiza uma nota existente."""
#     # Implementação movida para note_routes.py
#     pass

# @backlog_bp.route('/api/notes/<int:note_id>', methods=['DELETE'])
# def delete_note(note_id):
#     """Exclui uma nota."""
#     # Implementação movida para note_routes.py
#     pass

# @backlog_bp.route('/api/tags', methods=['GET'])
# def get_tags():
#     """Retorna todas as tags disponíveis."""
#     # Implementação movida para note_routes.py
#     pass

# Rota de disponibilidade para sprint removida

# --- NOVA ROTA PARA IMPORTAR TAREFAS DO EXCEL --- (Coloque antes de qualquer função utilitária solta no final, se houver)
@backlog_bp.route('/api/backlogs/<int:backlog_id>/import-tasks', methods=['POST'])
def import_tasks_from_excel(backlog_id):
    current_app.logger.info(f"[Import Excel API] Requisição recebida para backlog ID: {backlog_id}")

    backlog = Backlog.query.get_or_404(backlog_id)
    if not backlog:
        current_app.logger.error(f"[Import Excel API] Backlog ID {backlog_id} não encontrado.")
        return jsonify({'message': 'Backlog não encontrado.'}), 404

    # Obter detalhes do projeto para pegar o especialista padrão
    macro_service = MacroService()
    project_details = macro_service.obter_detalhes_projeto(str(backlog.project_id))
    default_specialist = project_details.get('especialista') if project_details else None
    current_app.logger.info(f"[Import Excel API] Projeto ID: {backlog.project_id}, Especialista Padrão do Projeto: {default_specialist}")

    if 'excel_file' not in request.files:
        current_app.logger.warning("[Import Excel API] Nenhum arquivo enviado na requisição.")
        return jsonify({'message': 'Nenhum arquivo excel enviado.'}), 400

    file = request.files['excel_file']

    if file.filename == '':
        current_app.logger.warning("[Import Excel API] Nome do arquivo vazio.")
        return jsonify({'message': 'Nenhum arquivo selecionado.'}), 400

    if file and file.filename.endswith('.xlsx'):
        try:
            current_app.logger.info(f"[Import Excel API] Lendo arquivo Excel: {file.filename}")
            df = pd.read_excel(file, engine='openpyxl')
            current_app.logger.debug(f"[Import Excel API] DataFrame lido. Colunas: {df.columns.tolist()}")

            expected_columns = { # Colunas esperadas e se são obrigatórias
                'Titulo': True,
                'HorasEstimadas': False,
                'DataInicio': False,
                'DataFim': False,
                'ColunaKanban': True
            }
            
            missing_required_columns = [col for col, req in expected_columns.items() if req and col not in df.columns]
            if missing_required_columns:
                msg = f"Colunas obrigatórias faltando na planilha: {', '.join(missing_required_columns)}."
                current_app.logger.error(f"[Import Excel API] {msg}")
                return jsonify({'message': msg}), 400

            imported_count = 0
            errors = []
            newly_created_tasks_ids = []

            kanban_columns_db = Column.query.all()
            # Mapa dos nomes canônicos (do BD, em minúsculas) para IDs
            db_column_name_to_id_map = {str(col.name).strip().lower(): col.id for col in kanban_columns_db}
            current_app.logger.debug(f"[Import Excel API] Mapa de colunas Kanban do DB: {db_column_name_to_id_map}")

            # Dicionário de aliases para nomes de colunas do Excel (chave: minúscula, valor: nome canônico minúsculo do BD)
            excel_column_name_aliases = {
                # Para "A Fazer" (Supondo que 'A Fazer' é o nome no BD)
                'to do': 'a fazer',
                'todo': 'a fazer',
                'a fazer': 'a fazer',
                'a_fazer': 'a fazer',
                'fazer': 'a fazer',
                # Para "Em Andamento" (Supondo que 'Em Andamento' é o nome no BD)
                'in progress': 'em andamento',
                'inprogress': 'em andamento',
                'em andamento': 'em andamento',
                'em_andamento': 'em andamento',
                'andamento': 'em andamento',
                # Para "Revisão" (Supondo que 'Revisão' é o nome no BD)
                'review': 'revisão',
                'revisao': 'revisão', # Sem acento
                'revisão': 'revisão',
                'em revisão': 'revisão',
                'em revisao': 'revisão',
                # Para "Concluído" (Supondo que 'Concluído' é o nome no BD)
                'done': 'concluído',
                'concluido': 'concluído', # Sem acento
                'concluído': 'concluído',
                'completed': 'concluído',
            }
            # Nomes canônicos válidos (em minúsculas, como estão no BD) para referência
            valid_canonical_column_names = list(db_column_name_to_id_map.keys())

            for index, row in df.iterrows():
                try:
                    titulo = row.get('Titulo')
                    coluna_kanban_name_excel = row.get('ColunaKanban') # Nome como está no Excel

                    if not titulo or pd.isna(titulo):
                        errors.append(f"Linha {index + 2}: Título da tarefa está vazio.")
                        continue 
                    if not coluna_kanban_name_excel or pd.isna(coluna_kanban_name_excel):
                        errors.append(f"Linha {index + 2}: Nome da Coluna Kanban está vazio para a tarefa '{str(titulo)[:50]}'.")
                        continue
                    
                    titulo_str = str(titulo).strip()
                    
                    # Normaliza o nome da coluna do Excel para busca (minúsculas, sem espaços extras)
                    normalized_excel_col_name = str(coluna_kanban_name_excel).strip().lower()

                    # Tenta encontrar um nome canônico correspondente usando o mapa de aliases
                    canonical_name_target = excel_column_name_aliases.get(normalized_excel_col_name)
                    
                    target_column_id = None
                    if canonical_name_target:
                        # Se encontrou no alias, busca o ID usando o nome canônico
                        target_column_id = db_column_name_to_id_map.get(canonical_name_target)
                    else:
                        # Se não encontrou no alias, tenta a correspondência direta com o nome normalizado do Excel
                        target_column_id = db_column_name_to_id_map.get(normalized_excel_col_name)

                    if not target_column_id:
                        errors.append(f"Linha {index + 2}: Coluna Kanban '{coluna_kanban_name_excel}' não reconhecida ou mapeada. Válidas (ou aliases para): {', '.join(valid_canonical_column_names)}")
                        continue

                    # Processamento de horas estimadas com suporte a sufixos
                    horas_estimadas_raw = row.get('HorasEstimadas')
                    horas_estimadas = None # Garante que se houver erro ou valor vazio, será None
                    if horas_estimadas_raw and not pd.isna(horas_estimadas_raw):
                        valor_processar = str(horas_estimadas_raw).strip()
                        
                        # Remove 'hrs', 'hr', 'h' (case-insensitive) e espaços ao redor
                        for sufixo in ['hrs', 'hr', 'h']:
                            if valor_processar.lower().endswith(sufixo):
                                valor_processar = valor_processar[:-len(sufixo)].strip()
                                break
                        
                        # Substitui vírgula por ponto para aceitar decimais como 7,5
                        valor_processar = valor_processar.replace(',', '.')
                        
                        if valor_processar: # Verifica se sobrou algo para converter
                            try:
                                horas_convertidas = float(valor_processar)
                                if horas_convertidas >= 0:
                                    horas_estimadas = horas_convertidas
                                else:
                                    errors.append(f"Linha {index + 2}: HorasEstimadas ('{horas_estimadas_raw}') resultou em valor negativo ({horas_convertidas}) para '{titulo_str}'. Será importado sem horas.")
                            except ValueError:
                                errors.append(f"Linha {index + 2}: HorasEstimadas ('{horas_estimadas_raw}') não pôde ser convertido para número para '{titulo_str}'. Será importado sem horas.")

                    def parse_date_from_excel(date_input, field_name):
                        if date_input is None or pd.isna(date_input): return None
                        if isinstance(date_input, datetime): return date_input.date()
                        
                        full_str = str(date_input).strip()
                        
                        # Se a data já está no formato datetime, converte diretamente
                        if isinstance(date_input, (datetime, date)):
                            return date_input if isinstance(date_input, date) else date_input.date()
                        
                        # Remove qualquer prefixo de dia da semana (ex: "Qua 28/05/25" -> "28/05/25")
                        # Procura pelo último espaço e pega tudo depois dele se houver uma data válida
                        if ' ' in full_str:
                            parts = full_str.split()
                            # Pega a última parte que deve ser a data
                            date_str_to_parse = parts[-1]
                        else:
                            date_str_to_parse = full_str

                        # Lista de formatos de data aceitos
                        date_formats = [
                            '%Y-%m-%d',    # YYYY-MM-DD
                            '%d/%m/%Y',    # DD/MM/YYYY
                            '%d/%m/%y',    # DD/MM/YY
                            '%Y/%m/%d',    # YYYY/MM/DD
                            '%d-%m-%Y',    # DD-MM-YYYY
                            '%d-%m-%y'     # DD-MM-YY
                        ]

                        for date_format in date_formats:
                            try:
                                return datetime.strptime(date_str_to_parse, date_format).date()
                            except ValueError:
                                continue

                        errors.append(f"Linha {index + 2}: Formato de {field_name} ('{date_input}') inválido para '{titulo_str}'. Use YYYY-MM-DD ou dd/mm/aa(aaaa).")
                        return None

                    data_inicio = parse_date_from_excel(row.get('DataInicio'), 'DataInicio')
                    if data_inicio == 'PARSE_ERROR': continue
                    data_fim = parse_date_from_excel(row.get('DataFim'), 'DataFim')
                    if data_fim == 'PARSE_ERROR': continue
                    
                    # Define a posição inicial como 0 (topo da coluna)
                    next_position = 0

                    new_task = Task(
                        title=titulo_str,
                        backlog_id=backlog.id,
                        column_id=target_column_id,
                        priority='Média', 
                        specialist_name=default_specialist,
                        estimated_effort=horas_estimadas,
                        start_date=data_inicio,
                        due_date=data_fim,
                        position=next_position,
                        status=TaskStatus.TODO # Default inicial
                    )
                    
                    target_column_obj = next((col for col in kanban_columns_db if col.id == target_column_id), None)
                    if target_column_obj:
                        col_name_lower = target_column_obj.name.lower()
                        if 'andamento' in col_name_lower:
                            new_task.status = TaskStatus.IN_PROGRESS
                            if not new_task.start_date: new_task.actually_started_at = datetime.utcnow()
                        elif 'revis' in col_name_lower:
                            new_task.status = TaskStatus.REVIEW
                        elif 'concluído' in col_name_lower or 'concluido' in col_name_lower:
                            new_task.status = TaskStatus.DONE
                            if not new_task.completed_at: new_task.completed_at = datetime.utcnow()
                        
                    db.session.add(new_task)
                    db.session.flush() # Para obter o ID da new_task
                    newly_created_tasks_ids.append(new_task.id)
                    imported_count += 1
                    current_app.logger.debug(f"[Import Excel API] Tarefa '{titulo_str}' (ID futuro: {new_task.id}) preparada.")

                except Exception as e_row:
                    current_app.logger.error(f"[Import Excel API] Erro ao processar linha {index + 2}: {str(e_row)}", exc_info=True)
                    errors.append(f"Linha {index + 2}: Erro inesperado - {str(e_row)}")
            
            if errors and imported_count > 0:
                 db.session.commit()
                 current_app.logger.info(f"[Import Excel API] {imported_count} tarefas importadas. {len(errors)} erros.")
                 return jsonify({
                    'message': f"{imported_count} tarefas importadas com {len(errors)} erros. Verifique os detalhes.",
                    'imported_count': imported_count,
                    'created_task_ids': newly_created_tasks_ids,
                    'errors': errors
                }), 207
            elif errors: 
                db.session.rollback()
                current_app.logger.warning(f"[Import Excel API] Nenhuma tarefa importada. {len(errors)} erros.")
                return jsonify({'message': 'Nenhuma tarefa importada devido a erros.', 'errors': errors}), 422
            else: 
                db.session.commit()
                current_app.logger.info(f"[Import Excel API] {imported_count} tarefas importadas com sucesso.")
                return jsonify({
                    'message': f'{imported_count} tarefas importadas com sucesso!',
                    'imported_count': imported_count,
                    'created_task_ids': newly_created_tasks_ids
                }), 201
                
        except pd.errors.EmptyDataError:
            current_app.logger.error("[Import Excel API] Planilha vazia.")
            return jsonify({'message': 'A planilha enviada está vazia.'}), 400
        except Exception as e_general:
            db.session.rollback()
            current_app.logger.error(f"[Import Excel API] Erro geral: {str(e_general)}", exc_info=True)
            return jsonify({'message': f'Erro geral ao processar o arquivo: {str(e_general)}'}), 500
    else:
        current_app.logger.warning("[Import Excel API] Tipo de arquivo inválido.")
        return jsonify({'message': 'Tipo de arquivo inválido. Apenas .xlsx.'}), 400

# Certifique-se que esta é a última parte adicionada ou que está em uma seção lógica de rotas.

# --- INÍCIO: APIs para Sprint Semanal do Especialista ---

@backlog_bp.route('/api/specialists/<path:specialist_name>/weekly-segments', methods=['GET'])
def get_specialist_weekly_segments(specialist_name):
    """
    Retorna os segmentos de tarefas de um especialista para uma semana específica.
    Query params:
    - week: Data de referência da semana (YYYY-MM-DD), padrão é semana atual
    - view: 'current' (só semana atual) ou 'extended' (atual + 2 próximas)
    """
    try:
        from urllib.parse import unquote
        from datetime import datetime, timedelta
        
        # Decodifica o nome do especialista
        specialist_name = unquote(specialist_name)
        current_app.logger.info(f"[Sprint Semanal] Buscando segmentos para especialista: {specialist_name}")
        
        # **BUSCA ROBUSTA DO ESPECIALISTA (igual ao debug)**
        specialist_trimmed = specialist_name.strip()
        
        # Busca híbrida (trim + case-insensitive)
        tasks_for_specialist = Task.query.filter(
            db.func.lower(db.func.trim(Task.specialist_name)) == specialist_trimmed.lower()
        ).all()
        
        # Se não encontrou com busca híbrida, tenta case-insensitive
        if not tasks_for_specialist:
            tasks_for_specialist = Task.query.filter(
                Task.specialist_name.ilike(f"%{specialist_name}%")
            ).all()
        
        # Se ainda não encontrou, tenta busca exata
        if not tasks_for_specialist:
            tasks_for_specialist = Task.query.filter_by(specialist_name=specialist_name).all()
        
        current_app.logger.info(f"[Sprint Semanal] Encontradas {len(tasks_for_specialist)} tarefas para o especialista")
        
        # Parâmetros da requisição
        week_param = request.args.get('week')
        view_mode = request.args.get('view', 'current')  # 'current' ou 'extended'
        
        # Define a data de referência da semana
        if week_param:
            try:
                reference_date = datetime.strptime(week_param, '%Y-%m-%d').date()
                current_app.logger.info(f"[Sprint Semanal] Usando data de referência fornecida: {reference_date}")
            except ValueError:
                current_app.logger.error(f"[Sprint Semanal] Formato de data inválido: {week_param}")
                return jsonify({'error': 'Formato de data inválido. Use YYYY-MM-DD'}), 400
        else:
            reference_date = datetime.now().date()
            current_app.logger.info(f"[Sprint Semanal] Usando data atual como referência: {reference_date}")
        
        # Calcula o início da semana (segunda-feira)
        days_since_monday = reference_date.weekday()
        week_start = reference_date - timedelta(days=days_since_monday)
        
        # Define quantas semanas buscar
        weeks_to_fetch = 3 if view_mode == 'extended' else 1
        current_app.logger.info(f"[Sprint Semanal] Buscando {weeks_to_fetch} semanas a partir de {week_start}")
        
        # Busca segmentos para as semanas
        all_weeks_data = []
        
        for week_offset in range(weeks_to_fetch):
            current_week_start = week_start + timedelta(weeks=week_offset)
            current_week_end = current_week_start + timedelta(days=4)  # Sexta-feira
            
            # Converte para datetime para comparação
            week_start_datetime = datetime.combine(current_week_start, datetime.min.time())
            week_end_datetime = datetime.combine(current_week_end, datetime.max.time())
            
            current_app.logger.info(f"[Sprint Semanal] Semana {week_offset + 1}: {week_start_datetime} - {week_end_datetime}")
            
            # **BUSCA SEGMENTOS USANDO AS TAREFAS ENCONTRADAS**
            task_ids = [task.id for task in tasks_for_specialist]
            
            if not task_ids:
                current_app.logger.info(f"[Sprint Semanal] Nenhuma tarefa encontrada para o especialista, pulando semana")
                continue
            
            # Busca segmentos da semana atual filtrando pelos IDs das tarefas
            segments = TaskSegment.query.filter(
                TaskSegment.task_id.in_(task_ids),
                TaskSegment.segment_start_datetime >= week_start_datetime,
                TaskSegment.segment_start_datetime <= week_end_datetime
            )\
            .order_by(TaskSegment.segment_start_datetime)\
            .all()
            
            current_app.logger.info(f"[Sprint Semanal] Encontrados {len(segments)} segmentos brutos para semana {week_offset + 1}")
            
            # Filtra apenas projetos ativos usando MacroService
            macro_service = MacroService()
            active_projects_data = macro_service.carregar_dados()
            active_project_ids = []
            project_names = {}  # Mapeamento ID -> Nome
            
            if not active_projects_data.empty:
                active_projects = macro_service.obter_projetos_ativos(active_projects_data)
                active_project_ids = [str(p.get('numero', '')) for p in active_projects]
                
                # Cria mapeamento de ID para nome do projeto
                for project in active_projects:
                    project_id = str(project.get('numero', ''))
                    project_name = project.get('projeto', f'Projeto {project_id}')
                    project_names[project_id] = project_name
                    
                current_app.logger.info(f"[Sprint Semanal] {len(active_project_ids)} projetos ativos encontrados")
            else:
                current_app.logger.warning("[Sprint Semanal] Nenhum projeto ativo encontrado no MacroService")
            
            # Serializa segmentos da semana
            week_segments = []
            for segment in segments:
                task = segment.task
                backlog = task.backlog
                
                # Verifica se o projeto está ativo
                if backlog.project_id not in active_project_ids:
                    current_app.logger.debug(f"[Sprint Semanal] Projeto {backlog.project_id} não está ativo, ignorando segmento")
                    continue
                
                # Busca o nome real do projeto
                project_name = project_names.get(backlog.project_id, f"Projeto {backlog.project_id}")
                
                segment_data = {
                    'id': segment.id,
                    'task_id': task.id,
                    'task_title': task.title,
                    'task_description': task.description,
                    'project_id': backlog.project_id,
                    'project_name': project_name,  # Agora usa o nome real
                    'start_datetime': segment.segment_start_datetime.isoformat(),
                    'end_datetime': segment.segment_end_datetime.isoformat(),
                    'segment_description': segment.description,
                    'estimated_hours': task.estimated_effort or 0,
                    'logged_time': task.logged_time or 0,
                    'priority': task.priority,
                    'status': task.status.value,
                    'column_id': task.column_id,
                    'column_name': task.column.name if task.column else None,
                    'is_completed': task.status == TaskStatus.DONE,
                    'backlog_id': backlog.id
                }
                week_segments.append(segment_data)
            
            current_app.logger.info(f"[Sprint Semanal] {len(week_segments)} segmentos válidos após filtro de projetos ativos")
            
            # Dados da semana (formato PT-BR para exibição)
            week_data = {
                'week_start': current_week_start.strftime('%Y-%m-%d'),
                'week_end': current_week_end.strftime('%Y-%m-%d'),
                'week_label': f"{current_week_start.strftime('%d/%m')} - {current_week_end.strftime('%d/%m')}",
                'week_label_full': f"{current_week_start.strftime('%d/%m/%Y')} - {current_week_end.strftime('%d/%m/%Y')}",
                'is_current_week': week_offset == 0,
                'segments': week_segments,
                'total_hours': sum(s.get('estimated_hours', 0) for s in week_segments)
            }
            all_weeks_data.append(week_data)
        
        total_segments = sum(len(w['segments']) for w in all_weeks_data)
        current_app.logger.info(f"[Sprint Semanal] RESULTADO FINAL: {total_segments} segmentos para {specialist_name}")
        
        return jsonify({
            'specialist_name': specialist_name,
            'view_mode': view_mode,
            'reference_date': reference_date.strftime('%Y-%m-%d'),
            'weeks': all_weeks_data,
            'debug_info': {
                'total_segments_found': total_segments,
                'total_tasks_found': len(tasks_for_specialist),
                'active_projects_count': len(active_project_ids) if active_project_ids else 0,
                'weeks_searched': weeks_to_fetch
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"[Sprint Semanal] Erro ao buscar segmentos: {str(e)}", exc_info=True)
        return jsonify({'error': f'Erro interno do servidor: {str(e)}'}), 500

@backlog_bp.route('/api/tasks/<int:task_id>/auto-segment', methods=['POST'])
def auto_segment_task(task_id):
    """
    Cria segmentos automáticos para uma tarefa baseado no limite de 10h por segmento.
    """
    try:
        task = Task.query.get_or_404(task_id)
        data = request.get_json()
        
        max_hours_per_segment = data.get('max_hours_per_segment', 10)
        start_date = data.get('start_date')  # YYYY-MM-DD
        start_time = data.get('start_time', '09:00')  # HH:MM
        daily_hours = data.get('daily_hours', 7.2)  # Horas por dia de trabalho (36h/semana ÷ 5 dias)
        
        if not start_date:
            return jsonify({'error': 'Data de início é obrigatória'}), 400
        
        if not task.estimated_effort or task.estimated_effort <= 0:
            return jsonify({'error': 'Tarefa deve ter esforço estimado maior que zero'}), 400
        
        # Remove segmentos existentes
        TaskSegment.query.filter_by(task_id=task_id).delete()
        
        # Calcula quantos segmentos são necessários
        total_hours = task.estimated_effort
        segments_needed = int((total_hours + max_hours_per_segment - 1) // max_hours_per_segment)  # Ceiling division
        
        start_datetime = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
        current_datetime = start_datetime
        
        segments_created = []
        remaining_hours = total_hours
        
        for segment_num in range(segments_needed):
            # Calcula horas deste segmento
            segment_hours = min(max_hours_per_segment, remaining_hours)
            remaining_hours -= segment_hours
            
            # Calcula data/hora fim do segmento
            end_datetime = current_datetime + timedelta(hours=segment_hours)
            
            # Cria descrição do segmento
            if segments_needed > 1:
                description = f"Etapa {segment_num + 1}/{segments_needed} - {segment_hours}h"
            else:
                description = f"Execução completa - {segment_hours}h"
            
            # Cria o segmento
            segment = TaskSegment(
                task_id=task_id,
                segment_start_datetime=current_datetime,
                segment_end_datetime=end_datetime,
                description=description
            )
            db.session.add(segment)
            segments_created.append(segment)
            
            # Próximo segmento começa após um intervalo (pode ser customizado)
            # Por simplicidade, vamos começar no próximo dia útil
            current_datetime = current_datetime.replace(hour=9, minute=0, second=0, microsecond=0)
            current_datetime += timedelta(days=1)
            
            # Pula fins de semana (sábado=5, domingo=6)
            while current_datetime.weekday() >= 5:
                current_datetime += timedelta(days=1)
        
        db.session.commit()
        
        # Retorna os segmentos criados
        created_segments = [s.to_dict() for s in segments_created]
        
        current_app.logger.info(f"[Auto Segmento] Criados {len(created_segments)} segmentos para tarefa {task_id}")
        
        return jsonify({
            'message': f'{len(created_segments)} segmentos criados automaticamente',
            'segments': created_segments,
            'total_hours': total_hours,
            'max_hours_per_segment': max_hours_per_segment
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[Auto Segmento] Erro: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erro ao criar segmentos automáticos'}), 500

@backlog_bp.route('/api/segments/<int:segment_id>/complete', methods=['PUT'])
def complete_segment(segment_id):
    """
    Marca um segmento como concluído e atualiza a tarefa se todos os segmentos estiverem concluídos.
    """
    try:
        segment = TaskSegment.query.get_or_404(segment_id)
        task = segment.task
        data = request.get_json()
        
        logged_hours = data.get('logged_hours', 0)
        completion_notes = data.get('completion_notes', '')
        
        # Atualiza a descrição do segmento para incluir as notas de conclusão
        if completion_notes:
            segment.description = f"{segment.description} - CONCLUÍDO: {completion_notes}"
        else:
            segment.description = f"{segment.description} - CONCLUÍDO"
        
        # Adiciona horas trabalhadas à tarefa
        if logged_hours > 0:
            task.logged_time = (task.logged_time or 0) + logged_hours
        
        # Verifica se todos os segmentos da tarefa estão concluídos
        all_segments = TaskSegment.query.filter_by(task_id=task.id).all()
        completed_segments = [s for s in all_segments if 'CONCLUÍDO' in (s.description or '')]
        
        # Se todos os segmentos estão concluídos, marca a tarefa como concluída
        if len(completed_segments) == len(all_segments):
            task.status = TaskStatus.DONE
            task.completed_at = datetime.utcnow()
            
            # Move para coluna "Concluído" se existir
            done_column = Column.query.filter_by(name='Concluído').first()
            if done_column:
                task.column_id = done_column.id
        
        db.session.commit()
        
        current_app.logger.info(f"[Segmento] Segmento {segment_id} marcado como concluído")
        
        return jsonify({
            'message': 'Segmento marcado como concluído',
            'task_completed': task.status == TaskStatus.DONE,
            'segment': segment.to_dict(),
            'task_logged_time': task.logged_time
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[Segmento] Erro ao concluir segmento: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erro ao concluir segmento'}), 500

@backlog_bp.route('/api/segments/<int:segment_id>/move-week', methods=['PUT'])
def move_segment_to_week(segment_id):
    """
    Move um segmento para uma semana diferente.
    """
    try:
        segment = TaskSegment.query.get_or_404(segment_id)
        data = request.get_json()
        
        new_week_start = data.get('new_week_start')  # YYYY-MM-DD
        new_start_time = data.get('new_start_time', '09:00')  # HH:MM
        
        if not new_week_start:
            return jsonify({'error': 'Nova semana é obrigatória'}), 400
        
        # Calcula a duração original do segmento
        original_duration = segment.segment_end_datetime - segment.segment_start_datetime
        
        # Calcula a nova data/hora de início
        new_start_date = datetime.strptime(new_week_start, '%Y-%m-%d').date()
        new_start_datetime = datetime.combine(new_start_date, datetime.strptime(new_start_time, '%H:%M').time())
        
        # Atualiza o segmento
        segment.segment_start_datetime = new_start_datetime
        segment.segment_end_datetime = new_start_datetime + original_duration
        
        db.session.commit()
        
        current_app.logger.info(f"[Segmento] Segmento {segment_id} movido para semana {new_week_start}")
        
        return jsonify({
            'message': 'Segmento movido com sucesso',
            'segment': segment.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[Segmento] Erro ao mover segmento: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erro ao mover segmento'}), 500

# --- FIM: APIs para Sprint Semanal do Especialista ---

# --- INÍCIO: Debug Sprint Semanal ---
# --- SPRINT SEMANAL: Função de debug removida para produção ---

@backlog_bp.route('/api/specialists/<path:specialist_name>/redistribute-workload', methods=['POST'])
def redistribute_specialist_workload(specialist_name):
    """
    Redistribui a carga de trabalho de um especialista quando há sobrecarga.
    Analisa semanas futuras e redistribui tarefas automaticamente.
    """
    try:
        from urllib.parse import unquote
        from datetime import datetime, timedelta
        
        specialist_name = unquote(specialist_name)
        data = request.get_json()
        
        max_hours_per_week = data.get('max_hours_per_week', 40)
        weeks_to_analyze = data.get('weeks_to_analyze', 4)
        
        current_app.logger.info(f"[Redistribuir] Iniciando redistribuição para {specialist_name}")
        
        # Busca tarefas do especialista
        tasks_for_specialist = Task.query.filter(
            db.func.lower(db.func.trim(Task.specialist_name)) == specialist_name.strip().lower()
        ).all()
        
        if not tasks_for_specialist:
            return jsonify({'error': 'Nenhuma tarefa encontrada para este especialista'}), 404
        
        # Analisa carga por semana nas próximas semanas
        hoje = datetime.now().date()
        semana_atual = hoje - timedelta(days=hoje.weekday())
        
        semanas_carga = []
        task_ids = [task.id for task in tasks_for_specialist]
        
        for week_offset in range(weeks_to_analyze):
            week_start = semana_atual + timedelta(weeks=week_offset)
            week_end = week_start + timedelta(days=4)
            
            week_start_dt = datetime.combine(week_start, datetime.min.time())
            week_end_dt = datetime.combine(week_end, datetime.max.time())
            
            # Busca segmentos da semana
            segments = TaskSegment.query.filter(
                TaskSegment.task_id.in_(task_ids),
                TaskSegment.segment_start_datetime >= week_start_dt,
                TaskSegment.segment_start_datetime <= week_end_dt
            ).all()
            
            total_hours = sum(s.task.estimated_effort or 0 for s in segments)
            
            semana_info = {
                'week_offset': week_offset,
                'week_start': week_start.strftime('%Y-%m-%d'),
                'week_label': f"{week_start.strftime('%d/%m')} - {week_end.strftime('%d/%m')}",
                'segments': segments,
                'total_hours': total_hours,
                'is_overloaded': total_hours > max_hours_per_week,
                'overload_hours': max(0, total_hours - max_hours_per_week)
            }
            
            semanas_carga.append(semana_info)
        
        # Identifica semanas sobrecarregadas
        semanas_sobrecarregadas = [s for s in semanas_carga if s['is_overloaded']]
        
        if not semanas_sobrecarregadas:
            return jsonify({
                'message': 'Nenhuma sobrecarga detectada',
                'specialist_name': specialist_name,
                'weeks_analyzed': semanas_carga,
                'redistributions': []
            })
        
        # Executa redistribuição
        redistribuicoes = []
        
        for semana_sobrecarregada in semanas_sobrecarregadas:
            horas_excesso = semana_sobrecarregada['overload_hours']
            segments_para_mover = []
            
            # Seleciona segmentos para mover (começando pelos menores)
            segments_ordenados = sorted(semana_sobrecarregada['segments'], 
                                      key=lambda s: s.task.estimated_effort or 0)
            
            horas_acumuladas = 0
            for segment in segments_ordenados:
                if horas_acumuladas >= horas_excesso:
                    break
                    
                segments_para_mover.append(segment)
                horas_acumuladas += segment.task.estimated_effort or 0
            
            # Encontra semana de destino (com menor carga)
            semanas_destino = [s for s in semanas_carga 
                             if s['week_offset'] > semana_sobrecarregada['week_offset'] 
                             and not s['is_overloaded']]
            
            if not semanas_destino:
                # Cria nova semana se necessário
                nova_semana_offset = semanas_carga[-1]['week_offset'] + 1
                nova_week_start = semana_atual + timedelta(weeks=nova_semana_offset)
                
                semanas_destino = [{
                    'week_offset': nova_semana_offset,
                    'week_start': nova_week_start.strftime('%Y-%m-%d'),
                    'total_hours': 0
                }]
            
            semana_destino = min(semanas_destino, key=lambda s: s['total_hours'])
            
            # Move os segmentos
            for segment in segments_para_mover:
                # Calcula nova data (segunda-feira da semana destino + hora original)
                nova_data = datetime.strptime(semana_destino['week_start'], '%Y-%m-%d')
                hora_original = segment.segment_start_datetime.time()
                nova_datetime = datetime.combine(nova_data.date(), hora_original)
                
                # Atualiza o segmento
                segment.segment_start_datetime = nova_datetime
                # Mantém a duração original
                duracao = segment.segment_end_datetime - segment.segment_start_datetime
                segment.segment_end_datetime = nova_datetime + duracao
                
                redistribuicoes.append({
                    'segment_id': segment.id,
                    'task_title': segment.task.title,
                    'hours': segment.task.estimated_effort or 0,
                    'from_week': semana_sobrecarregada['week_label'],
                    'to_week': f"{nova_data.strftime('%d/%m')} - {(nova_data + timedelta(days=4)).strftime('%d/%m')}",
                    'new_start_date': nova_datetime.strftime('%Y-%m-%d %H:%M')
                })
        
        # Salva as mudanças
        if redistribuicoes:
            db.session.commit()
            current_app.logger.info(f"[Redistribuir] {len(redistribuicoes)} segmentos redistribuídos para {specialist_name}")
        
        return jsonify({
            'message': f'{len(redistribuicoes)} tarefas redistribuídas com sucesso',
            'specialist_name': specialist_name,
            'max_hours_per_week': max_hours_per_week,
            'weeks_analyzed': len(semanas_carga),
            'overloaded_weeks': len(semanas_sobrecarregadas),
            'redistributions': redistribuicoes,
            'summary': {
                'total_redistributed_hours': sum(r['hours'] for r in redistribuicoes),
                'weeks_affected': len(set(r['from_week'] for r in redistribuicoes))
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"[Redistribuir] Erro: {str(e)}", exc_info=True)
        return jsonify({'error': f'Erro interno do servidor: {str(e)}'}), 500

# --- FIM: APIs para Sprint Semanal do Especialista ---

# ===================================
# ROTAS PARA GERENCIAMENTO DE CAPACIDADE
# ===================================

@backlog_bp.route('/api/specialists/<path:specialist_name>/capacity', methods=['GET'])
def get_specialist_capacity(specialist_name):
    """
    API para obter informações de capacidade de um especialista
    
    Args:
        specialist_name: Nome do especialista
        week: Data de início da semana (opcional, formato YYYY-MM-DD)
        weeks: Número de semanas futuras para analisar (opcional, padrão: 3)
    """
    try:
        from .capacity_service import CapacityService
        
        week_param = request.args.get('week')
        weeks_param = int(request.args.get('weeks', 3))
        
        capacity_service = CapacityService()
        
        # Define data de referência
        if week_param:
            reference_date = datetime.strptime(week_param, '%Y-%m-%d')
        else:
            reference_date = datetime.now()
        
        # Calcula início da semana (segunda-feira)
        days_since_monday = reference_date.weekday()
        week_start = reference_date - timedelta(days=days_since_monday)
        
        # Calcula capacidade para múltiplas semanas
        weeks_capacity = []
        for week_offset in range(weeks_param):
            current_week_start = week_start + timedelta(weeks=week_offset)
            capacity = capacity_service.calcular_capacidade_semana(specialist_name, current_week_start)
            
            # Adiciona informações extras para a interface
            capacity['week_offset'] = week_offset
            capacity['is_current_week'] = week_offset == 0
            capacity['week_label'] = f"{current_week_start.strftime('%d/%m')} - {(current_week_start + timedelta(days=4)).strftime('%d/%m')}"
            
            weeks_capacity.append(capacity)
        
        current_app.logger.info(f"[Capacity] Capacidade calculada para {specialist_name}: {len(weeks_capacity)} semanas")
        
        return jsonify({
            'specialist_name': specialist_name,
            'reference_date': reference_date.strftime('%Y-%m-%d'),
            'weeks': weeks_capacity,
            'summary': {
                'total_weeks_analyzed': len(weeks_capacity),
                'overloaded_weeks': sum(1 for w in weeks_capacity if w['resumo']['status_semana'] == 'sobrecarga'),
                'total_hours_all_weeks': sum(w['resumo']['total_horas_semana'] for w in weeks_capacity),
                'average_weekly_utilization': round(
                    sum(w['resumo']['percentual_ocupacao_semana'] for w in weeks_capacity) / len(weeks_capacity), 1
                ) if weeks_capacity else 0
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"[Capacity] Erro ao obter capacidade: {str(e)}", exc_info=True)
        return jsonify({'error': f'Erro interno do servidor: {str(e)}'}), 500

@backlog_bp.route('/api/specialists/<path:specialist_name>/capacity/conflicts', methods=['POST'])
def check_capacity_conflicts(specialist_name):
    """
    API para verificar conflitos de capacidade ao adicionar uma tarefa
    
    Body JSON:
        task_hours: Horas da tarefa
        target_date: Data alvo (formato YYYY-MM-DD)
    """
    try:
        from .capacity_service import CapacityService
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Dados JSON obrigatórios'}), 400
        
        task_hours = float(data.get('task_hours', 0))
        target_date_str = data.get('target_date')
        
        if not target_date_str:
            return jsonify({'error': 'target_date é obrigatório'}), 400
        
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d')
        capacity_service = CapacityService()
        
        conflicts = capacity_service.verificar_conflitos_capacidade(
            specialist_name, task_hours, target_date
        )
        
        current_app.logger.info(f"[Capacity] Conflitos verificados para {specialist_name}: {conflicts.get('tem_conflito', False)}")
        
        return jsonify(conflicts)
        
    except Exception as e:
        current_app.logger.error(f"[Capacity] Erro ao verificar conflitos: {str(e)}", exc_info=True)
        return jsonify({'error': f'Erro interno do servidor: {str(e)}'}), 500

@backlog_bp.route('/api/specialists/<path:specialist_name>/capacity/suggestions', methods=['POST'])
def get_capacity_suggestions(specialist_name):
    """
    API para obter sugestões de horários baseadas na capacidade
    
    Body JSON:
        task_hours: Horas da tarefa
        weeks_ahead: Semanas futuras para considerar (opcional, padrão: 4)
    """
    try:
        from .capacity_service import CapacityService
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Dados JSON obrigatórios'}), 400
        
        task_hours = float(data.get('task_hours', 0))
        weeks_ahead = int(data.get('weeks_ahead', 4))
        
        capacity_service = CapacityService()
        suggestions = capacity_service.sugerir_melhor_horario(
            specialist_name, task_hours, weeks_ahead
        )
        
        current_app.logger.info(f"[Capacity] {len(suggestions)} sugestões geradas para {specialist_name}")
        
        return jsonify({
            'specialist_name': specialist_name,
            'task_hours': task_hours,
            'weeks_analyzed': weeks_ahead,
            'suggestions': suggestions,
            'total_suggestions': len(suggestions)
        })
        
    except Exception as e:
        current_app.logger.error(f"[Capacity] Erro ao gerar sugestões: {str(e)}", exc_info=True)
        return jsonify({'error': f'Erro interno do servidor: {str(e)}'}), 500

@backlog_bp.route('/api/specialists/<path:specialist_name>/capacity/auto-balance', methods=['POST'])
def auto_balance_capacity(specialist_name):
    """
    API para balanceamento automático de capacidade
    
    Body JSON:
        max_hours_per_day: Máximo de horas por dia (opcional, padrão: 8)
        weeks_to_balance: Semanas para balancear (opcional, padrão: 4)
    """
    try:
        from .capacity_service import CapacityService
        
        data = request.get_json() or {}
        max_hours_per_day = float(data.get('max_hours_per_day', 8.0))
        weeks_to_balance = int(data.get('weeks_to_balance', 4))
        
        capacity_service = CapacityService()
        
        # Primeiro verifica a capacidade atual
        hoje = datetime.now()
        week_start = hoje - timedelta(days=hoje.weekday())
        
        balancing_results = []
        total_moved_hours = 0
        total_moved_tasks = 0
        
        for week_offset in range(weeks_to_balance):
            current_week_start = week_start + timedelta(weeks=week_offset)
            capacity = capacity_service.calcular_capacidade_semana(specialist_name, current_week_start)
            
            # Verifica se há dias sobrecarregados
            overloaded_days = [
                (day, info) for day, info in capacity['capacidade_por_dia'].items()
                if info['horas_alocadas'] > max_hours_per_day
            ]
            
            if overloaded_days:
                # Simula redistribuição (aqui você implementaria a lógica real)
                for day_name, day_info in overloaded_days:
                    excess_hours = day_info['horas_alocadas'] - max_hours_per_day
                    
                    balancing_results.append({
                        'week_start': current_week_start.strftime('%Y-%m-%d'),
                        'day': day_name,
                        'original_hours': day_info['horas_alocadas'],
                        'excess_hours': round(excess_hours, 1),
                        'action': 'move_to_next_available_day',
                        'status': 'simulated'  # Em produção seria 'executed'
                    })
                    
                    total_moved_hours += excess_hours
                    total_moved_tasks += 1  # Simplificado
        
        current_app.logger.info(f"[Capacity] Balanceamento simulado para {specialist_name}: {total_moved_hours}h movidas")
        
        return jsonify({
            'specialist_name': specialist_name,
            'weeks_analyzed': weeks_to_balance,
            'max_hours_per_day': max_hours_per_day,
            'balancing_results': balancing_results,
            'summary': {
                'total_moved_hours': round(total_moved_hours, 1),
                'total_moved_tasks': total_moved_tasks,
                'weeks_affected': len(set(r['week_start'] for r in balancing_results)),
                'status': 'simulation_complete'
            },
            'note': 'Esta é uma simulação. Para executar o balanceamento real, use o parâmetro execute=true'
        })
        
    except Exception as e:
        current_app.logger.error(f"[Capacity] Erro no balanceamento: {str(e)}", exc_info=True)
        return jsonify({'error': f'Erro interno do servidor: {str(e)}'}), 500

@backlog_bp.route('/api/sprints/<int:sprint_id>/capacity', methods=['GET'])
def get_sprint_capacity(sprint_id):
    """
    API para obter informações de capacidade de uma sprint baseada na sua duração
    
    Args:
        sprint_id: ID da sprint
        specialist: Nome do especialista (opcional, via query param)
    """
    try:
        from .capacity_service import CapacityService
        
        specialist_name = request.args.get('specialist')
        capacity_service = CapacityService()
        
        capacity_data = capacity_service.calcular_capacidade_sprint(sprint_id, specialist_name)
        
        if 'erro' in capacity_data:
            return jsonify({'error': capacity_data['erro']}), 404
        
        return jsonify(capacity_data)
        
    except Exception as e:
        logger.error(f"Erro ao calcular capacidade da sprint {sprint_id}: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

# ===================================
# ROTAS PARA ANÁLISES E RELATÓRIOS
# ===================================

@backlog_bp.route('/api/analytics/specialist/<path:specialist_name>/report', methods=['GET'])
def get_specialist_analytics_report(specialist_name):
    """
    API para gerar relatório completo de análise de um especialista
    
    Args:
        specialist_name: Nome do especialista
        weeks_back: Semanas passadas para análise (opcional, padrão: 4)
    """
    try:
        from .analytics_service import AnalyticsService
        
        weeks_back = int(request.args.get('weeks_back', 4))
        
        analytics_service = AnalyticsService()
        relatorio = analytics_service.gerar_relatorio_especialista(specialist_name, weeks_back)
        
        current_app.logger.info(f"[Analytics] Relatório gerado para {specialist_name}: {weeks_back} semanas")
        
        return jsonify(relatorio)
        
    except Exception as e:
        current_app.logger.error(f"[Analytics] Erro ao gerar relatório: {str(e)}", exc_info=True)
        return jsonify({'error': f'Erro interno do servidor: {str(e)}'}), 500

@backlog_bp.route('/api/analytics/team/dashboard', methods=['GET'])
def get_team_dashboard():
    """
    API para gerar dashboard consolidado da equipe
    
    Args:
        weeks_back: Semanas passadas para análise (opcional, padrão: 4)
    """
    try:
        from .analytics_service import AnalyticsService
        
        weeks_back = int(request.args.get('weeks_back', 4))
        
        analytics_service = AnalyticsService()
        dashboard = analytics_service.gerar_dashboard_equipe(weeks_back)
        
        current_app.logger.info(f"[Analytics] Dashboard da equipe gerado: {weeks_back} semanas")
        
        return jsonify(dashboard)
        
    except Exception as e:
        current_app.logger.error(f"[Analytics] Erro ao gerar dashboard: {str(e)}", exc_info=True)
        return jsonify({'error': f'Erro interno do servidor: {str(e)}'}), 500

@backlog_bp.route('/api/analytics/sprint-optimization', methods=['POST'])
def analyze_sprint_optimization():
    """
    API para análise de otimização de sprints da equipe
    
    Body JSON:
        team_members: Lista de nomes dos membros da equipe
        weeks_ahead: Semanas futuras para análise (opcional, padrão: 4)
    """
    try:
        from .analytics_service import AnalyticsService
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Dados JSON obrigatórios'}), 400
        
        team_members = data.get('team_members', [])
        weeks_ahead = int(data.get('weeks_ahead', 4))
        
        if not team_members:
            return jsonify({'error': 'Lista de membros da equipe é obrigatória'}), 400
        
        analytics_service = AnalyticsService()
        otimizacoes = analytics_service.analisar_otimizacao_sprints(team_members, weeks_ahead)
        
        current_app.logger.info(f"[Analytics] Otimização analisada para {len(team_members)} membros")
        
        return jsonify(otimizacoes)
        
    except Exception as e:
        current_app.logger.error(f"[Analytics] Erro na análise de otimização: {str(e)}", exc_info=True)
        return jsonify({'error': f'Erro interno do servidor: {str(e)}'}), 500

@backlog_bp.route('/api/analytics/export/<path:specialist_name>', methods=['GET'])
def export_specialist_data(specialist_name):
    """
    API para exportar dados de um especialista em diferentes formatos
    
    Args:
        specialist_name: Nome do especialista
        format: Formato de exportação (json, csv, excel) - padrão: json
        weeks_back: Semanas para exportar (opcional, padrão: 4)
    """
    try:
        from .analytics_service import AnalyticsService
        import csv
        import io
        
        formato = request.args.get('format', 'json').lower()
        weeks_back = int(request.args.get('weeks_back', 4))
        
        analytics_service = AnalyticsService()
        relatorio = analytics_service.gerar_relatorio_especialista(specialist_name, weeks_back)
        
        if formato == 'json':
            return jsonify(relatorio)
        
        elif formato == 'csv':
            # Cria CSV com dados resumidos
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow(['Métrica', 'Valor'])
            
            # Dados das métricas
            metricas = relatorio.get('metricas_produtividade', {})
            for key, value in metricas.items():
                writer.writerow([key.replace('_', ' ').title(), value])
            
            # Adiciona linha em branco
            writer.writerow([])
            
            # Dados de capacidade
            capacidade = relatorio.get('capacidade_historica', {})
            writer.writerow(['CAPACIDADE HISTÓRICA', ''])
            for key, value in capacidade.items():
                writer.writerow([key.replace('_', ' ').title(), value])
            
            # Recomendações
            writer.writerow([])
            writer.writerow(['RECOMENDAÇÕES', ''])
            for i, recomendacao in enumerate(relatorio.get('recomendacoes', []), 1):
                writer.writerow([f'Recomendação {i}', recomendacao])
            
            output.seek(0)
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment;filename={specialist_name}_relatorio.csv'}
            )
        
        else:
            return jsonify({'error': 'Formato não suportado. Use: json, csv'}), 400
        
    except Exception as e:
        current_app.logger.error(f"[Analytics] Erro na exportação: {str(e)}", exc_info=True)
        return jsonify({'error': f'Erro interno do servidor: {str(e)}'}), 500

@backlog_bp.route('/api/analytics/predictions/<path:specialist_name>', methods=['GET'])
def get_specialist_predictions(specialist_name):
    """
    API para obter predições de performance de um especialista
    
    Args:
        specialist_name: Nome do especialista
        prediction_weeks: Semanas futuras para predição (opcional, padrão: 2)
    """
    try:
        from .analytics_service import AnalyticsService
        
        prediction_weeks = int(request.args.get('prediction_weeks', 2))
        
        analytics_service = AnalyticsService()
        
        # Primeiro gera o relatório para ter dados históricos
        relatorio = analytics_service.gerar_relatorio_especialista(specialist_name, 4)
        
        if 'error' in relatorio:
            return jsonify(relatorio), 500
        
        # Extrai predições e expande com mais detalhes
        predicoes = relatorio.get('predicoes', {})
        metricas = relatorio.get('metricas_produtividade', {})
        tendencias = relatorio.get('tendencias', {})
        
        # Calcula predições mais detalhadas
        predictions_detail = {
            'specialist_name': specialist_name,
            'prediction_weeks': prediction_weeks,
            'base_data': {
                'current_productivity': metricas.get('percentual_conclusao', 0),
                'current_velocity': metricas.get('velocidade_semanal', 0),
                'trend': tendencias.get('tendencia_produtividade', 'estavel')
            },
            'predictions': [],
            'confidence_factors': {
                'data_consistency': min(100, len(tendencias.get('metricas_semanais', [])) * 25),
                'trend_stability': 75,  # Simulado
                'external_factors': 80   # Simulado
            },
            'recommendations': predicoes.get('recomendacao_carga', 'normal'),
            'risk_assessment': _assess_prediction_risks(metricas, tendencias)
        }
        
        # Gera predições para cada semana
        base_productivity = metricas.get('percentual_conclusao', 0)
        trend_variation = tendencias.get('variacao', 0)
        
        for week in range(1, prediction_weeks + 1):
            # Aplica tendência com decay
            predicted_productivity = base_productivity + (trend_variation * week * 0.8)
            predicted_productivity = max(0, min(100, predicted_productivity))
            
            # Calcula variabilidade
            confidence = max(50, 95 - (week * 10))  # Confiança diminui com o tempo
            
            predictions_detail['predictions'].append({
                'week': week,
                'predicted_productivity': round(predicted_productivity, 1),
                'confidence_level': confidence,
                'expected_velocity': round(metricas.get('velocidade_semanal', 0) * (predicted_productivity / 100), 1),
                'risk_level': 'baixo' if predicted_productivity > 70 else 'medio' if predicted_productivity > 50 else 'alto'
            })
        
        current_app.logger.info(f"[Analytics] Predições geradas para {specialist_name}: {prediction_weeks} semanas")
        
        return jsonify(predictions_detail)
        
    except Exception as e:
        current_app.logger.error(f"[Analytics] Erro nas predições: {str(e)}", exc_info=True)
        return jsonify({'error': f'Erro interno do servidor: {str(e)}'}), 500

@backlog_bp.route('/api/analytics/team/optimization-score', methods=['POST'])
def calculate_team_optimization_score():
    """
    API para calcular score de otimização da equipe
    
    Body JSON:
        team_members: Lista de nomes dos membros
        target_utilization: Utilização alvo (opcional, padrão: 80)
    """
    try:
        from .analytics_service import AnalyticsService
        from .capacity_service import CapacityService
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Dados JSON obrigatórios'}), 400
        
        team_members = data.get('team_members', [])
        target_utilization = float(data.get('target_utilization', 80.0))
        
        if not team_members:
            return jsonify({'error': 'Lista de membros da equipe é obrigatória'}), 400
        
        capacity_service = CapacityService()
        analytics_service = AnalyticsService()
        
        hoje = datetime.now()
        week_start = hoje - timedelta(days=hoje.weekday())
        
        # Calcula métricas de otimização
        utilizacoes = []
        sobrecargas = 0
        total_capacity = 0
        
        for member in team_members:
            capacity = capacity_service.calcular_capacidade_semana(member, week_start)
            utilization = capacity['resumo']['percentual_ocupacao_semana']
            utilizacoes.append(utilization)
            
            if capacity['resumo']['dias_sobrecarregados'] > 0:
                sobrecargas += 1
            
            total_capacity += capacity['resumo']['total_horas_semana']
        
        # Calcula score baseado em diferentes fatores
        score_components = {}
        
        # 1. Utilização média vs. target
        avg_utilization = sum(utilizacoes) / len(utilizacoes) if utilizacoes else 0
        utilization_score = max(0, 100 - abs(avg_utilization - target_utilization))
        score_components['utilization_alignment'] = round(utilization_score, 1)
        
        # 2. Distribuição equilibrada (baixo desvio padrão)
        import statistics
        std_dev = statistics.stdev(utilizacoes) if len(utilizacoes) > 1 else 0
        balance_score = max(0, 100 - (std_dev * 2))
        score_components['workload_balance'] = round(balance_score, 1)
        
        # 3. Ausência de sobrecargas
        overload_score = max(0, 100 - (sobrecargas * 20))
        score_components['overload_prevention'] = round(overload_score, 1)
        
        # 4. Eficiência de capacidade
        max_possible_capacity = len(team_members) * 36  # 36h por semana por pessoa
        capacity_efficiency = (total_capacity / max_possible_capacity) * 100 if max_possible_capacity > 0 else 0
        score_components['capacity_efficiency'] = round(capacity_efficiency, 1)
        
        # Score final ponderado
        final_score = (
            utilization_score * 0.3 +
            balance_score * 0.25 +
            overload_score * 0.25 +
            capacity_efficiency * 0.2
        )
        
        # Classificação do score
        if final_score >= 85:
            classification = 'Excelente'
            recommendations = ['Manter configuração atual', 'Monitorar tendências']
        elif final_score >= 70:
            classification = 'Boa'
            recommendations = ['Pequenos ajustes podem melhorar eficiência', 'Revisar distribuição em caso de sobrecarga']
        elif final_score >= 50:
            classification = 'Aceitável'
            recommendations = ['Redistribuir carga de trabalho', 'Revisar planejamento de capacidade']
        else:
            classification = 'Necessita Atenção'
            recommendations = ['Urgente: redistribuir tarefas', 'Revisar processo de alocação', 'Considerar recursos adicionais']
        
        result = {
            'team_members': team_members,
            'target_utilization': target_utilization,
            'optimization_score': round(final_score, 1),
            'classification': classification,
            'score_components': score_components,
            'team_metrics': {
                'average_utilization': round(avg_utilization, 1),
                'utilization_std_dev': round(std_dev, 1),
                'overloaded_members': sobrecargas,
                'total_team_capacity': round(total_capacity, 1),
                'capacity_efficiency': round(capacity_efficiency, 1)
            },
            'member_utilizations': [
                {'member': member, 'utilization': util}
                for member, util in zip(team_members, utilizacoes)
            ],
            'recommendations': recommendations
        }
        
        current_app.logger.info(f"[Analytics] Score de otimização calculado: {final_score:.1f} para {len(team_members)} membros")
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"[Analytics] Erro no cálculo do score: {str(e)}", exc_info=True)
        return jsonify({'error': f'Erro interno do servidor: {str(e)}'}), 500

def _assess_prediction_risks(metricas: dict, tendencias: dict) -> dict:
    """Avalia riscos nas predições"""
    risks = []
    
    if metricas.get('percentual_conclusao', 0) < 60:
        risks.append('Baixa produtividade histórica pode afetar predições')
    
    if tendencias.get('tendencia_produtividade') == 'declinio':
        risks.append('Tendência de declínio pode continuar')
    
    if len(tendencias.get('metricas_semanais', [])) < 3:
        risks.append('Poucos dados históricos reduzem confiabilidade')
    
    return {
        'level': 'alto' if len(risks) > 2 else 'medio' if len(risks) > 0 else 'baixo',
        'factors': risks
    }

# Rota modificada para POST (sem backlog_id na URL)
@backlog_bp.route('/api/milestones', methods=['POST'])
def create_milestone():
    """Cria um novo marco (milestone) para o projeto."""
    current_app.logger.info("!!! ROTA POST /api/milestones ACESSADA !!!")
    data = request.get_json()
    if not data:
        abort(400, description="Nenhum dado fornecido.")

    # Extração e validação de dados
    backlog_id = data.get('backlog_id')
    name = data.get('name', '').strip()
    planned_date_str = data.get('planned_date')

    if not all([backlog_id, name, planned_date_str]):
        abort(400, description="'backlog_id', 'name', e 'planned_date' são obrigatórios.")

    backlog = Backlog.query.get_or_404(backlog_id)
    
    try:
        planned_date = datetime.strptime(planned_date_str, '%Y-%m-%d').date()
        
        # --- CORREÇÃO: Usar chaves de Enum ---
        status_key = data.get('status', 'PENDING').strip()
        criticality_key = data.get('criticality', 'MEDIUM').strip()
        
        if not status_key: status_key = 'PENDING'
        if not criticality_key: criticality_key = 'MEDIUM'

        status = MilestoneStatus[status_key]
        criticality = MilestoneCriticality[criticality_key]
        # --- FIM CORREÇÃO ---

        actual_date = None
        if data.get('actual_date'):
            actual_date = datetime.strptime(data['actual_date'], '%Y-%m-%d').date()

        new_milestone = ProjectMilestone(
            name=name,
            description=data.get('description'),
            planned_date=planned_date,
            actual_date=actual_date,
            status=status,
            criticality=criticality,
            is_checkpoint=data.get('is_checkpoint', False),
            backlog_id=backlog.id
        )

        db.session.add(new_milestone)
        db.session.commit()
        current_app.logger.info(f"Marco '{name}' (ID: {new_milestone.id}) criado com sucesso para backlog {backlog_id}.")
        return jsonify(new_milestone.to_dict()), 201

    except (ValueError, KeyError) as e:
        db.session.rollback()
        # Log mais detalhado
        error_msg = f"Erro de valor ou chave de enum inválida: {str(e)}"
        current_app.logger.error(f"Erro ao criar marco para backlog {backlog_id}: {error_msg}", exc_info=True)
        # Fornece uma mensagem de erro mais útil ao cliente
        if isinstance(e, KeyError):
            valid_statuses = [s.name for s in MilestoneStatus]
            valid_criticalities = [c.name for c in MilestoneCriticality]
            abort(400, description=f"Chave de enum inválida. Status válidos: {valid_statuses}. Criticidades válidas: {valid_criticalities}.")
        else:
            abort(400, description="Formato de data inválido. Use YYYY-MM-DD.")
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro inesperado ao criar marco para backlog {backlog_id}: {e}", exc_info=True)
        abort(500, description="Erro interno ao criar o marco.")

# =====================================================
# APIs DO SISTEMA DE COMPLEXIDADE DE PROJETOS
# =====================================================

@backlog_bp.route('/api/complexity/criteria', methods=['GET'])
def get_complexity_criteria():
    try:
        from ..models import ComplexityCriteria, ComplexityCriteriaOption
        
        criteria = ComplexityCriteria.query.filter_by(is_active=True).order_by(ComplexityCriteria.criteria_order).all()
        
        result = []
        for criterion in criteria:
            options = ComplexityCriteriaOption.query.filter_by(criteria_id=criterion.id, is_active=True).order_by(ComplexityCriteriaOption.option_order).all()
            
            criterion_data = {
                'id': criterion.id,
                'name': criterion.name,
                'description': criterion.description,
                'order': criterion.criteria_order,
                'options': [
                    {
                        'id': opt.id,
                        'label': opt.option_label or opt.option_name,
                        'description': opt.description,
                        'score': opt.points,
                        'order': opt.option_order
                    } for opt in options
                ]
            }
            result.append(criterion_data)
        
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Erro ao buscar critérios de complexidade: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erro interno do servidor'}), 500

@backlog_bp.route('/api/complexity/thresholds', methods=['GET'])
def get_complexity_thresholds():
    """Retorna os thresholds de complexidade."""
    try:
        from ..models import ComplexityThreshold
        
        thresholds = ComplexityThreshold.query.order_by(ComplexityThreshold.min_score).all()
        
        result = []
        for threshold in thresholds:
            result.append({
                'category': threshold.category.name,  # Usa .name para obter o nome do enum
                'category_label': threshold.category.value,  # Usa .value para obter o valor/label do enum
                'min_score': threshold.min_score,
                'max_score': threshold.max_score
            })
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Erro ao buscar thresholds de complexidade: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erro interno do servidor'}), 500

@backlog_bp.route('/api/projects/<string:project_id>/complexity/assessment', methods=['GET'])
def get_project_complexity_assessment(project_id):
    try:
        from ..models import ProjectComplexityAssessment, ComplexityCriteria, ComplexityCriteriaOption
        
        assessment = ProjectComplexityAssessment.query.filter_by(project_id=project_id).order_by(ProjectComplexityAssessment.created_at.desc()).first()
        
        if not assessment:
            return jsonify({'assessment': None})
        
        details_data = []
        for detail in assessment.details:
            criteria = ComplexityCriteria.query.get(detail.criteria_id)
            option = ComplexityCriteriaOption.query.get(detail.selected_option_id)
            
            details_data.append({
                'criteria_id': detail.criteria_id,
                'option_id': detail.selected_option_id,
                'criteria_name': criteria.name if criteria else 'N/A',
                'option_label': option.option_label or option.option_name if option else 'N/A',
                'score': detail.points_awarded
            })
        
        response_data = {
            'assessment': {
                'id': assessment.id,
                'project_id': assessment.project_id,
                'total_score': assessment.total_score,
                'category': assessment.complexity_category,
                'category_label': assessment.complexity_category,
                'notes': assessment.notes or assessment.assessment_notes,
                'assessed_by': assessment.assessed_by,
                'created_at': assessment.created_at.isoformat(),
                'details': details_data
            }
        }
        
        return jsonify(response_data)
    except Exception as e:
        current_app.logger.error(f"Erro ao buscar avaliação de complexidade para projeto {project_id}: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erro interno do servidor'}), 500

@backlog_bp.route('/api/projects/<string:project_id>/complexity/assessment', methods=['POST'])
def create_project_complexity_assessment(project_id):
    try:
        from ..models import ProjectComplexityAssessment, ProjectComplexityAssessmentDetail, ComplexityCriteriaOption, ComplexityThreshold
        
        data = request.get_json()
        if not data or 'criteria' not in data:
            return jsonify({'error': 'Dados de critérios são obrigatórios'}), 400
        
        notes = data.get('notes', '')
        assessed_by = data.get('assessed_by', 'Sistema')
        
        # Busca o backlog do projeto
        from ..models import Backlog
        backlog = Backlog.query.filter_by(project_id=project_id).first()
        if not backlog:
            return jsonify({'error': 'Backlog não encontrado para este projeto'}), 404
        
        # Valida as opções e calcula o score
        total_score = 0
        assessment_details_data = []
        
        for criteria_id_str, option_id_str in data['criteria'].items():
            criteria_id = int(criteria_id_str)
            option_id = int(option_id_str)
            
            option = ComplexityCriteriaOption.query.get(option_id)
            if not option or option.criteria_id != criteria_id:
                return jsonify({'error': f'Opção inválida {option_id} para o critério {criteria_id_str}'}), 400

            total_score += option.points
            assessment_details_data.append({
                'criteria_id': criteria_id,
                'selected_option_id': option_id,
                'points_awarded': option.points
            })
        
        # Determina a categoria baseada nos thresholds
        thresholds = ComplexityThreshold.query.order_by(ComplexityThreshold.min_score).all()
        category = 'ALTA'  # Default para categoria mais alta
        
        for threshold in thresholds:
            if total_score >= threshold.min_score and (threshold.max_score is None or total_score <= threshold.max_score):
                category = threshold.category.name  # Usa .name para obter o valor string do enum
                break
        
        # Cria a avaliação
        assessment = ProjectComplexityAssessment(
            project_id=project_id,
            backlog_id=backlog.id,
            total_score=total_score,
            complexity_category=category,
            category=category,  # Preenche ambos os campos
            notes=notes,
            assessment_notes=notes,  # Preenche ambos os campos
            assessed_by=assessed_by
        )
        db.session.add(assessment)
        db.session.flush()

        # Cria os detalhes
        for detail_data in assessment_details_data:
            detail = ProjectComplexityAssessmentDetail(
                assessment_id=assessment.id,
                criteria_id=detail_data['criteria_id'],
                selected_option_id=detail_data['selected_option_id'],
                points_awarded=detail_data['points_awarded'],
                option_id=detail_data['selected_option_id'],  # Preenche ambos os campos
                score=detail_data['points_awarded']  # Preenche ambos os campos
            )
            db.session.add(detail)

        db.session.commit()

        return jsonify({
            'id': assessment.id,
            'project_id': assessment.project_id,
            'total_score': assessment.total_score,
            'category': assessment.complexity_category,
            'category_label': assessment.complexity_category,
            'notes': assessment.notes,
            'assessed_by': assessment.assessed_by,
            'created_at': assessment.created_at.isoformat()
        }), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao criar avaliação de complexidade para projeto {project_id}: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erro interno do servidor'}), 500

@backlog_bp.route('/api/projects/<string:project_id>/complexity/history', methods=['GET'])
def get_project_complexity_history(project_id):
    try:
        from ..models import ProjectComplexityAssessment
        
        assessments = ProjectComplexityAssessment.query.filter_by(project_id=project_id).order_by(ProjectComplexityAssessment.created_at.desc()).all()
        
        result = []
        for assessment in assessments:
            result.append({
                'id': assessment.id,
                'total_score': assessment.total_score,
                'category': assessment.complexity_category,
                'category_label': assessment.complexity_category,
                'notes': assessment.notes or assessment.assessment_notes,
                'assessed_by': assessment.assessed_by,
                'created_at': assessment.created_at.isoformat()
            })
        
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Erro ao buscar histórico de complexidade para projeto {project_id}: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erro interno do servidor'}), 500

# ========================================
# APIS WBS - WORK BREAKDOWN STRUCTURE
# ========================================

@backlog_bp.route('/api/projects/<string:project_id>/tasks', methods=['GET'])
def get_project_tasks_for_wbs(project_id):
    """
    Retorna todas as tarefas de um projeto para geração da WBS
    """
    try:
        from ..models import ProjectComplexityAssessment
        
        current_app.logger.info(f"[WBS API] Buscando tarefas do projeto: {project_id}")
        
        # Busca o backlog do projeto
        backlog = Backlog.query.filter_by(project_id=project_id).first()
        if not backlog:
            return jsonify({'error': 'Projeto não encontrado'}), 404

        # Busca todas as tarefas do projeto
        tasks = Task.query.filter_by(backlog_id=backlog.id).all()
        
        tasks_data = []
        for task in tasks:
            # Busca complexidade se existir
            complexity_assessment = ProjectComplexityAssessment.query.filter_by(
                project_id=project_id
            ).order_by(ProjectComplexityAssessment.created_at.desc()).first()
            
            complexity_level = None
            if complexity_assessment and complexity_assessment.complexity_category:
                complexity_level = complexity_assessment.complexity_category

            tasks_data.append({
                'id': task.id,
                'title': task.title,
                'name': task.title,  # Alias para compatibilidade
                'description': task.description or '',
                'status': task.status.value if task.status else 'TODO',
                'priority': task.priority or 'MEDIUM',
                'assigned_to': task.specialist_name or 'Não atribuído',
                'estimated_effort': task.estimated_effort,
                'start_date': task.start_date.isoformat() if task.start_date else None,
                'due_date': task.due_date.isoformat() if task.due_date else None,
                'complexity': complexity_level,
                'column_name': task.column.name if task.column else 'A Fazer',
                'created_at': task.created_at.isoformat() if task.created_at else None
            })

        current_app.logger.info(f"[WBS API] Retornando {len(tasks_data)} tarefas")
        return jsonify(tasks_data)

    except Exception as e:
        current_app.logger.error(f"[WBS API] Erro ao buscar tarefas: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500


@backlog_bp.route('/api/projects/<string:project_id>/milestones', methods=['GET'])
def get_project_milestones_for_wbs(project_id):
    """
    Retorna todos os marcos de um projeto para geração da WBS
    """
    try:
        from ..models import ProjectMilestone
        
        current_app.logger.info(f"[WBS API] Buscando marcos do projeto: {project_id}")
        
        # Busca o backlog do projeto
        backlog = Backlog.query.filter_by(project_id=project_id).first()
        if not backlog:
            return jsonify({'error': 'Projeto não encontrado'}), 404

        # Busca todos os marcos do projeto
        milestones = ProjectMilestone.query.filter_by(backlog_id=backlog.id).all()
        
        milestones_data = []
        for milestone in milestones:
            milestones_data.append({
                'id': milestone.id,
                'name': milestone.name,
                'description': milestone.description or '',
                'planned_date': milestone.planned_date.isoformat() if milestone.planned_date else None,
                'actual_date': milestone.actual_date.isoformat() if milestone.actual_date else None,
                'status': milestone.status.value if milestone.status else 'PENDING',
                'criticality': milestone.criticality.value if milestone.criticality else 'MEDIUM',
                'is_checkpoint': milestone.is_checkpoint or False,
                'created_at': milestone.created_at.isoformat() if milestone.created_at else None
            })

        current_app.logger.info(f"[WBS API] Retornando {len(milestones_data)} marcos")
        return jsonify(milestones_data)

    except Exception as e:
        current_app.logger.error(f"[WBS API] Erro ao buscar marcos: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500


@backlog_bp.route('/api/wbs/export', methods=['POST'])
def export_wbs_to_excel():
    """
    Exporta a WBS para um arquivo Excel
    """
    try:
        import pandas as pd
        from io import BytesIO
        from flask import send_file
        
        data = request.get_json()
        project_id = data.get('project_id')
        wbs_data = data.get('wbs_data', [])
        
        current_app.logger.info(f"[WBS Export] Exportando WBS do projeto {project_id} com {len(wbs_data)} itens")
        
        if not wbs_data:
            return jsonify({'error': 'Nenhum dado para exportar'}), 400

        # Cria DataFrame com os dados da WBS
        df = pd.DataFrame(wbs_data)
        
        # Renomeia colunas para português
        column_mapping = {
            'WBS_ID': 'ID WBS',
            'Tipo': 'Tipo',
            'ID_Tarefa': 'ID da Tarefa',
            'Tarefa': 'Tarefa/Marco',
            'Descrição': 'Descrição',
            'Data_Inicio': 'Data de Início',
            'Data_Prevista_Fim': 'Data Prevista para Fim',
            'Intervalo_Dias': 'Intervalo (Dias)',
            'Especialista': 'Especialista',
            'Status': 'Status',
            'Prioridade': 'Prioridade',
            'Coluna': 'Coluna Kanban'
        }
        
        df = df.rename(columns=column_mapping)
        
        # Cria arquivo Excel em memória
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Escreve a planilha principal
            df.to_excel(writer, sheet_name='WBS - Estrutura Analítica', index=False)
            
            # Adiciona planilha de resumo
            summary_data = {
                'Métrica': [
                    'Total de Itens',
                    'Total de Tarefas', 
                    'Total de Marcos',
                    'Duração Total Estimada (dias)',
                    'Especialistas Envolvidos'
                ],
                'Valor': [
                    len(wbs_data),
                    len([item for item in wbs_data if item.get('Tipo') == 'Tarefa']),
                    len([item for item in wbs_data if item.get('Tipo') == 'Marco']),
                    sum([item.get('Intervalo_Dias', 0) for item in wbs_data if item.get('Tipo') == 'Tarefa']),
                    len(set([item.get('Especialista') for item in wbs_data if item.get('Especialista') and item.get('Especialista') != 'Marco do Projeto']))
                ]
            }
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Resumo do Projeto', index=False)
            
            # Formatar planilhas
            workbook = writer.book
            
            # Formata planilha WBS
            wbs_sheet = writer.sheets['WBS - Estrutura Analítica']
            
            # Define larguras das colunas
            column_widths = {
                'A': 10,  # ID WBS
                'B': 8,   # Tipo
                'C': 12,  # ID da Tarefa
                'D': 40,  # Tarefa/Marco
                'E': 50,  # Descrição
                'F': 15,  # Data de Início
                'G': 20,  # Data Prevista para Fim
                'H': 15,  # Intervalo (Dias)
                'I': 20,  # Especialista
                'J': 12,  # Status
                'K': 12,  # Prioridade
                'L': 15   # Coluna Kanban
            }
            
            for col, width in column_widths.items():
                wbs_sheet.column_dimensions[col].width = width
            
            # Formata cabeçalho
            from openpyxl.styles import Font, PatternFill, Alignment
            
            header_font = Font(bold=True, color='FFFFFF')
            header_fill = PatternFill(start_color='07304F', end_color='07304F', fill_type='solid')
            center_alignment = Alignment(horizontal='center', vertical='center')
            
            for cell in wbs_sheet[1]:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = center_alignment
            
            # Formata planilha de resumo
            summary_sheet = writer.sheets['Resumo do Projeto']
            summary_sheet.column_dimensions['A'].width = 30
            summary_sheet.column_dimensions['B'].width = 20
            
            for cell in summary_sheet[1]:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = center_alignment

        output.seek(0)
        
        # Nome do arquivo
        filename = f"WBS_Projeto_{project_id}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        current_app.logger.info(f"[WBS Export] Arquivo {filename} gerado com sucesso")
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )

    except ImportError as e:
        current_app.logger.error(f"[WBS Export] Biblioteca não encontrada: {str(e)}")
        return jsonify({'error': 'Bibliotecas necessárias não instaladas (pandas, openpyxl)'}), 500
    except Exception as e:
        current_app.logger.error(f"[WBS Export] Erro ao exportar: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

# ✅ CACHE OTIMIZADO: Cache global para projetos ativos (reduz logs MacroService)
_ACTIVE_PROJECTS_CACHE = {
    'data': None,
    'timestamp': None,
    'ttl_seconds': 300  # 5 minutos de cache para projetos ativos
}

def _get_cached_active_projects():
    """Retorna projetos ativos do cache se válido."""
    if (_ACTIVE_PROJECTS_CACHE['data'] is not None and 
        _ACTIVE_PROJECTS_CACHE['timestamp'] is not None):
        elapsed = time.time() - _ACTIVE_PROJECTS_CACHE['timestamp']
        if elapsed < _ACTIVE_PROJECTS_CACHE['ttl_seconds']:
            return _ACTIVE_PROJECTS_CACHE['data']
    return None

def _set_cached_active_projects(project_ids):
    """Cacheia IDs de projetos ativos."""
    _ACTIVE_PROJECTS_CACHE['data'] = project_ids
    _ACTIVE_PROJECTS_CACHE['timestamp'] = time.time()

# 🎯 ENDPOINT PARA SALVAR NOVA ORDEM DA WBS
@backlog_bp.route('/api/wbs/update-order', methods=['POST'])
def update_wbs_task_order():
    """
    Atualiza a ordem/posição das tarefas na WBS
    """
    try:
        data = request.get_json()
        
        if not data:
            abort(400, description="Dados não fornecidos")
        
        project_id = data.get('project_id')
        task_orders = data.get('task_orders', [])
        
        if not project_id:
            abort(400, description="project_id é obrigatório")
        
        if not task_orders:
            abort(400, description="task_orders é obrigatório")
        
        current_app.logger.info(f"🔄 Atualizando ordem WBS para projeto {project_id} - {len(task_orders)} tarefas")
        
        # Atualiza a posição de cada tarefa
        updated_tasks = []
        for task_order in task_orders:
            task_id = task_order.get('task_id')
            new_position = task_order.get('new_position')
            
            if not task_id or new_position is None:
                current_app.logger.warning(f"Dados incompletos para tarefa: {task_order}")
                continue
            
            # Busca a tarefa
            task = Task.query.get(task_id)
            if not task:
                current_app.logger.warning(f"Tarefa {task_id} não encontrada")
                continue
            
            # Verifica se a tarefa pertence ao projeto correto
            if task.backlog and str(task.backlog.project_id) != str(project_id):
                current_app.logger.warning(f"Tarefa {task_id} não pertence ao projeto {project_id}")
                continue
            
            # Atualiza a posição
            old_position = task.position
            task.position = new_position
            task.updated_at = datetime.now(br_timezone)
            
            updated_tasks.append({
                'task_id': task_id,
                'title': task.title,
                'old_position': old_position,
                'new_position': new_position
            })
            
            current_app.logger.debug(f"📋 Tarefa {task_id} ({task.title}): posição {old_position} → {new_position}")
        
        # Salva todas as alterações
        db.session.commit()
        
        current_app.logger.info(f"✅ Ordem WBS atualizada com sucesso! {len(updated_tasks)} tarefas modificadas")
        
        return jsonify({
            'success': True,
            'message': f'Ordem das tarefas atualizada com sucesso',
            'updated_tasks_count': len(updated_tasks),
            'updated_tasks': updated_tasks
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Erro ao atualizar ordem WBS: {str(e)}", exc_info=True)
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500