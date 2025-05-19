from flask import render_template, jsonify, request, abort, current_app, redirect, url_for
from . import backlog_bp # Importa o blueprint
from .. import db # Importa a instância do banco de dados
from ..models import Backlog, Task, Column, Sprint, TaskStatus, ProjectMilestone, ProjectRisk, MilestoneStatus, MilestoneCriticality, RiskImpact, RiskProbability, RiskStatus, TaskSegment, Note, Tag # Importa os modelos
from ..macro.services import MacroService # Importa o serviço Macro
import pandas as pd
from datetime import datetime, timedelta, date
import pytz # <<< ADICIONADO

# Define o fuso horário de Brasília
br_timezone = pytz.timezone('America/Sao_Paulo') # <<< ADICIONADO

# Função auxiliar para serializar uma tarefa
def serialize_task(task):
    """Converte um objeto Task em um dicionário serializável."""
    if not task:
        return None
    
    # Adicionando log para depuração
    current_app.logger.info(f"[serialize_task] Serializando tarefa ID: {task.id}, Título: {task.title}, is_generic: {task.is_generic}")

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
            'estimated_hours': task.estimated_effort if hasattr(task, 'estimated_effort') else None,
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
        
        # 5. Renderiza o template do quadro passando os dados específicos
        current_app.logger.info(f"[DEBUG] Renderizando template board.html")
        return render_template(
            'backlog/board.html', 
            columns=columns, 
            # Passa a lista de tarefas serializadas diretamente para o JS consumir
            # O template não precisará mais agrupar por coluna aqui
            tasks_json=jsonify(tasks_list).get_data(as_text=True), 
            current_project=project_details, # Passa os detalhes do projeto atual
            current_backlog_id=backlog_id, 
            current_backlog_name=backlog_name,
            backlog=current_backlog # Adiciona o objeto backlog completo
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
    task = Task.query.get_or_404(task_id) # Busca a tarefa ou retorna 404 se não encontrar
    return jsonify(serialize_task(task)) # Retorna os dados serializados da tarefa

# API para atualizar detalhes de uma tarefa existente
@backlog_bp.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task_details(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Nenhum dado fornecido'}), 400

    current_app.logger.info(f"Atualizando tarefa {task_id} com dados: {data}")

    # Campos que podem ser atualizados diretamente
    simple_update_fields = {
        'title': 'title',
        'description': 'description',
        'priority': 'priority',
        'estimated_hours': 'estimated_effort', # Frontend envia 'estimated_hours', modelo usa 'estimated_effort'
        'logged_time': 'logged_time',
        'specialist_name': 'specialist_name'
        # 'is_generic' e 'is_unplanned' serão tratados abaixo
    }

    for front_key, model_key in simple_update_fields.items():
        if front_key in data:
            setattr(task, model_key, data[front_key])

    # Tratamento para 'status'
    if 'status' in data:
        try:
            status_enum = TaskStatus[data['status']]
            task.status = status_enum
        except KeyError:
            return jsonify({'error': f"Status inválido: {data['status']}"}), 400

    # Tratamento para 'is_generic'
    if 'is_generic' in data:
        if isinstance(data['is_generic'], bool):
            task.is_generic = data['is_generic']
        else:
            current_app.logger.warning(f"Valor inválido para is_generic: {data['is_generic']}. Esperado um booleano.")
            task.is_generic = str(data['is_generic']).lower() in ['true', '1', 'yes']

    # Tratamento para 'is_unplanned' - NOVO
    if 'is_unplanned' in data:
        if isinstance(data['is_unplanned'], bool):
            task.is_unplanned = data['is_unplanned']
        else:
            current_app.logger.warning(f"Valor inválido para is_unplanned: {data['is_unplanned']}. Esperado um booleano.")
            task.is_unplanned = str(data['is_unplanned']).lower() in ['true', '1', 'yes']

    # Tratamento para 'start_date'
    if 'start_date' in data and data['start_date']:
        try:
            task.start_date = datetime.fromisoformat(data['start_date'].replace('Z', '+00:00'))
        except ValueError:
            try: # Tentar parsear apenas data YYYY-MM-DD
                task.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
            except ValueError:
                 return jsonify({'error': f"Formato de start_date inválido: {data['start_date']}"}), 400
    elif 'start_date' in data and not data['start_date']: # Permitir limpar a data
        task.start_date = None

    # Tratamento para 'due_date'
    if 'due_date' in data and data['due_date']:
        try:
            task.due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
        except ValueError:
            try: # Tentar parsear apenas data YYYY-MM-DD
                task.due_date = datetime.strptime(data['due_date'], '%Y-%m-%d')
            except ValueError:
                return jsonify({'error': f"Formato de due_date inválido: {data['due_date']}"}), 400
    elif 'due_date' in data and not data['due_date']: # Permitir limpar a data
        task.due_date = None

    # Tratamento para 'completed_at'
    if 'completed_at' in data and data['completed_at']:
        try:
            task.completed_at = datetime.fromisoformat(data['completed_at'].replace('Z', '+00:00'))
            # Se a tarefa está sendo marcada como concluída, atualiza o status para DONE
            # a menos que já seja um status final (ex: ARCHIVED)
            if task.status not in [TaskStatus.DONE, TaskStatus.ARCHIVED]: # CORRIGIDO AQUI
                task.status = TaskStatus.DONE # CORRIGIDO AQUI
        except ValueError:
            try: # Tentar parsear apenas data YYYY-MM-DD
                dt_obj = datetime.strptime(data['completed_at'], '%Y-%m-%d')
                # Se apenas a data for fornecida, podemos definir a hora para o final do dia ou manter como meia-noite.
                # Para consistência, manter meia-noite UTC se nenhuma hora for dada.
                task.completed_at = dt_obj 
                if task.status not in [TaskStatus.DONE, TaskStatus.ARCHIVED]: # CORRIGIDO AQUI
                    task.status = TaskStatus.DONE # CORRIGIDO AQUI
            except ValueError:
                current_app.logger.error(f"Formato de data inválido para completed_at: {data['completed_at']}")
                
    elif 'completed_at' in data and not data['completed_at']:
        task.completed_at = None
        # Se a data de conclusão é removida, e o status era CONCLUIDO,
        # pode ser necessário reverter o status para um anterior (ex: EM_ANDAMENTO ou A_FAZER).
        # Isso depende da lógica de negócios. Por enquanto, apenas remove a data.
        # Poderíamos adicionar: if task.status == TaskStatus.DONE: task.status = TaskStatus.IN_PROGRESS # Ou A_FAZER # CORRIGIDO AQUI (exemplo)

    try:
        db.session.commit()
        # Log após o commit bem-sucedido
        current_app.logger.info(f"Tarefa {task_id} atualizada com sucesso. Novo status: {task.status}, Título: {task.title}")
        # Serializa a tarefa atualizada para retornar na resposta
        updated_task_data = serialize_task(task)
        if updated_task_data.get('error'): # Verifica se a serialização falhou
            current_app.logger.error(f"Erro ao serializar tarefa {task_id} após atualização: {updated_task_data.get('error')}")
            # Mesmo que a serialização falhe, a atualização no DB ocorreu.
            # Retornar uma mensagem genérica de sucesso ou tentar um fallback.
            return jsonify({'message': 'Tarefa atualizada, mas erro ao obter detalhes completos.'}), 200
        return jsonify(updated_task_data), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao atualizar tarefa {task_id}: {str(e)}", exc_info=True)
        return jsonify({'error': f'Erro ao salvar alterações: {str(e)}'}), 500

# API para excluir uma tarefa
@backlog_bp.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    try:
        # Lógica para reajustar posições na coluna da tarefa excluída
        old_column_id = task.column_id
        old_position = task.position
        
        # Decrementa posição das tarefas na coluna antiga que estavam depois da tarefa excluída
        Task.query.filter(
            Task.column_id == old_column_id,
            Task.position > old_position
        ).update({Task.position: Task.position - 1}, synchronize_session='fetch')
        
        # Exclui a tarefa
        db.session.delete(task)
        db.session.commit()
        current_app.logger.info(f"Tarefa {task_id} excluída com sucesso.")
        # Retorna 204 No Content, padrão para DELETE bem-sucedido sem corpo
        return '', 204 
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao excluir tarefa {task_id}: {e}", exc_info=True)
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

    new_task = Task(
        title=data['name'].strip(),
        description=data.get('description'),
        status=TaskStatus.TODO, # Status inicial sempre TODO
        priority=data.get('priority', 'Média'), # Adiciona prioridade
        estimated_effort=estimated_effort_val, # <<< Usa a variável processada
        position=new_position,
        start_date=start_date_obj, # <<< Usa a variável processada
        due_date=due_date_obj, # <<< CORREÇÃO: Usa o objeto datetime validado
        backlog_id=backlog.id,
        column_id=first_column.id, # Atribui à primeira coluna
        specialist_name=default_specialist, # <<< Define o especialista padrão >>>
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
    new_position = data.get('position') # A posição enviada pelo frontend (ex: 0, 1, 2...)

    if new_column_id is None or new_position is None:
        abort(400, description="'column_id' e 'position' são obrigatórios para mover.")

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

    # Define a data de início real APENAS se estiver movendo para "Em Andamento" 
    # e a tarefa ainda não tiver uma data de início real registrada.
    if is_moving_to_progress and not task.actually_started_at:
        task.actually_started_at = datetime.now(br_timezone) # <<< ALTERADO para usar br_timezone
        current_app.logger.info(f"[Task Moved] Tarefa {task.id} movida para Em Andamento, data de INÍCIO REAL definida para {task.actually_started_at} (usando br_timezone)")

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
             
        return jsonify(project_details)
        
    except Exception as e:
        current_app.logger.error(f"Erro ao buscar detalhes do projeto {project_id}: {e}", exc_info=True)
        abort(500, description="Erro interno ao buscar detalhes do projeto.")
# ------------------------------------------------

# Adicionar rotas para CRUD de Sprints se necessário... 

# API para obter tarefas não alocadas a sprints, agrupadas por backlog/projeto
@backlog_bp.route('/api/backlogs/unassigned-tasks')
def get_unassigned_tasks():
    macro_service = MacroService() # Re-adiciona instância do serviço
    try:
        # 1. Busca todas as tarefas sem sprint_id E QUE NÃO SÃO GENÉRICAS,
        #    ordenadas por backlog e posição
        unassigned_tasks = Task.query.filter(
                                        Task.sprint_id == None,
                                        Task.is_generic == False # Simplifica a condição
                                      )\
                                      .join(Backlog)\
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
            project_details_map = {pid: macro_service.obter_detalhes_projeto(pid) for pid in project_ids}

            for backlog_id, tasks in tasks_by_backlog.items():
                backlog = backlog_details_map.get(backlog_id)
                if backlog:
                    project_details = project_details_map.get(backlog.project_id)
                    # Pega o NOME DO PROJETO, usa 'Nome Indisponível' se não encontrar
                    project_name = project_details.get('name', 'Nome Indisponível') if project_details else 'Nome Indisponível'

                    result.append({
                        'backlog_id': backlog.id,
                        'backlog_name': backlog.name, # Nome do Backlog (Ex: Backlog Principal)
                        'project_id': backlog.project_id, # ID do Projeto associado
                        'project_name': project_name, # << NOME DO PROJETO
                        'tasks': tasks
                    })
                else:
                    # Caso raro: tarefas órfãs? Logar isso.
                    current_app.logger.warning(f"Tarefas encontradas para backlog_id {backlog_id} que não existe mais.")

        # Opcional: Ordenar a lista de backlogs/projetos resultantes
        result.sort(key=lambda x: (x.get('project_id', '')))

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Erro ao buscar tarefas não alocadas: {e}", exc_info=True)
        return jsonify({"message": "Erro interno ao buscar tarefas não alocadas."}), 500 

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

    current_app.logger.info(f"[AssignTask] Iniciando. TaskID: {task_id}, OldSprint: {old_sprint_id}, OldPos: {old_position}, NewSprint: {new_sprint_id}, NewPos: {new_position}")

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
                    ).update({Task.position: Task.position - 1}, synchronize_session='fetch')
                else:
                    # Para tarefas do backlog, mantém o comportamento original
                    Task.query.filter(
                        Task.backlog_id == task.backlog_id,
                        Task.sprint_id == None,
                        Task.position > old_position
                    ).update({Task.position: Task.position - 1}, synchronize_session='fetch')
            else:
                Task.query.filter(
                    Task.sprint_id == old_sprint_id,
                    Task.position > old_position
                ).update({Task.position: Task.position - 1}, synchronize_session='fetch')
        
        # 2. Ajusta posições na lista de DESTINO
        if old_sprint_id != new_sprint_id:
            if new_sprint_id is None:
                if task.is_generic:
                    # Para tarefas genéricas, ajusta posições apenas entre tarefas genéricas
                    Task.query.filter(
                        Task.is_generic == True,
                        Task.sprint_id == None,
                        Task.position >= new_position
                    ).update({Task.position: Task.position + 1}, synchronize_session='fetch')
                else:
                    # Para tarefas do backlog, mantém o comportamento original
                    Task.query.filter(
                        Task.backlog_id == task.backlog_id,
                        Task.sprint_id == None,
                        Task.position >= new_position
                    ).update({Task.position: Task.position + 1}, synchronize_session='fetch')
            else:
                Task.query.filter(
                    Task.sprint_id == new_sprint_id,
                    Task.position >= new_position
                ).update({Task.position: Task.position + 1}, synchronize_session='fetch')
        else:
            if new_position > old_position:
                if new_sprint_id is not None:
                    Task.query.filter(
                        Task.sprint_id == new_sprint_id,
                        Task.position > old_position,
                        Task.position <= new_position
                    ).update({Task.position: Task.position - 1}, synchronize_session='fetch')
                else:
                    if task.is_generic:
                        Task.query.filter(
                            Task.is_generic == True,
                            Task.sprint_id == None,
                            Task.position > old_position,
                            Task.position <= new_position
                        ).update({Task.position: Task.position - 1}, synchronize_session='fetch')
                    else:
                        Task.query.filter(
                            Task.backlog_id == task.backlog_id,
                            Task.sprint_id == None,
                            Task.position > old_position,
                            Task.position <= new_position
                        ).update({Task.position: Task.position - 1}, synchronize_session='fetch')
            elif new_position < old_position:
                if new_sprint_id is not None:
                    Task.query.filter(
                        Task.sprint_id == new_sprint_id,
                        Task.position >= new_position,
                        Task.position < old_position
                    ).update({Task.position: Task.position + 1}, synchronize_session='fetch')
                else:
                    if task.is_generic:
                        Task.query.filter(
                            Task.is_generic == True,
                            Task.sprint_id == None,
                            Task.position >= new_position,
                            Task.position < old_position
                        ).update({Task.position: Task.position + 1}, synchronize_session='fetch')
                    else:
                        Task.query.filter(
                            Task.backlog_id == task.backlog_id,
                            Task.sprint_id == None,
                            Task.position >= new_position,
                            Task.position < old_position
                        ).update({Task.position: Task.position + 1}, synchronize_session='fetch')

        task.sprint_id = new_sprint_id
        task.position = new_position

        db.session.commit()
        db.session.refresh(task)
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

# Rota modificada para POST (sem backlog_id na URL)
@backlog_bp.route('/api/milestones', methods=['POST'])
def create_milestone():
    """Cria um novo marco para o projeto associado ao backlog (ID do backlog vem no corpo)."""
    # <<< LOG DE DEBUG >>>
    current_app.logger.info("!!! ROTA POST /api/milestones ACESSADA !!!") 
    # <<< FIM LOG DE DEBUG >>>
    data = request.get_json()

    # <<< NOVO: Obter backlog_id do corpo da requisição >>>
    backlog_id = data.get('backlog_id')
    if not backlog_id:
        current_app.logger.error("Erro em create_milestone: backlog_id não encontrado no corpo JSON.")
        abort(400, description="ID do Backlog (backlog_id) é obrigatório no corpo da requisição.")
        
    # Verifica se o backlog existe
    try:
        backlog = Backlog.query.get_or_404(backlog_id)
    except Exception as e: # Captura erro se backlog_id não for um int válido para get_or_404
        current_app.logger.error(f"Erro ao buscar backlog ID {backlog_id}: {e}")
        abort(404, description=f"Backlog com ID {backlog_id} não encontrado.")
    # <<< FIM NOVO >>>

    if not data or not data.get('name') or not data.get('planned_date'):
        current_app.logger.error("Erro em create_milestone: Dados obrigatórios (name, planned_date) faltando.")
        abort(400, description="Nome e data planejada são obrigatórios.")

    try:
        # Processa dados obrigatórios
        planned_date = datetime.strptime(data['planned_date'], '%Y-%m-%d').date()
        name = data['name'].strip()
        if not name:
            abort(400, description="Nome não pode ser vazio.")
        
        # Processa dados opcionais
        description = data.get('description', '')
        actual_date_str = data.get('actual_date')
        actual_date = datetime.strptime(actual_date_str, '%Y-%m-%d').date() if actual_date_str else None
        
        status_str = data.get('status', MilestoneStatus.PENDING.value) # Default PENDING
        try:
            status = MilestoneStatus(status_str)
        except ValueError:
            valid_statuses = [s.value for s in MilestoneStatus]
            abort(400, description=f"Status inválido. Valores válidos: {valid_statuses}")

        criticality_str = data.get('criticality', MilestoneCriticality.MEDIUM.value) # Default MEDIUM
        try:
            criticality = MilestoneCriticality(criticality_str)
        except ValueError:
            valid_criticalities = [c.value for c in MilestoneCriticality]
            abort(400, description=f"Criticidade inválida. Valores válidos: {valid_criticalities}")
            
        is_checkpoint = data.get('is_checkpoint', False)

        # Cria o novo marco
        new_milestone = ProjectMilestone(
            name=name,
            description=description,
            planned_date=planned_date,
            actual_date=actual_date,
            status=status,
            criticality=criticality,
            is_checkpoint=is_checkpoint,
            backlog_id=backlog_id # Associa ao backlog (vindo do corpo agora)
        )
        
        db.session.add(new_milestone)
        db.session.commit()
        
        # Retorna o marco criado usando to_dict
        return jsonify(new_milestone.to_dict()), 201

    except ValueError as ve:
        # Erro específico de conversão de data ou enum
        db.session.rollback()
        abort(400, description=str(ve))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao criar marco para backlog {backlog_id}: {e}", exc_info=True)
        abort(500, description="Erro interno ao criar marco do projeto.")

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
            try:
                milestone.status = MilestoneStatus(data['status'])
                # Regra: Se marcar como concluído e não tiver data real, define data real
                if milestone.status == MilestoneStatus.COMPLETED and not milestone.actual_date:
                    milestone.actual_date = datetime.utcnow().date()
            except ValueError:
                valid_statuses = [s.value for s in MilestoneStatus]
                abort(400, description=f"Status inválido. Valores válidos: {valid_statuses}")
                
        if 'criticality' in data:
            try:
                milestone.criticality = MilestoneCriticality(data['criticality'])
            except ValueError:
                valid_criticalities = [c.value for c in MilestoneCriticality]
                abort(400, description=f"Criticidade inválida. Valores válidos: {valid_criticalities}")
        
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
    description = data.get('description')
    impact_str = data.get('impact', RiskImpact.MEDIUM.value) # Default MEDIUM
    probability_str = data.get('probability', RiskProbability.MEDIUM.value) # Default MEDIUM
    status_str = data.get('status', RiskStatus.ACTIVE.value) # Default ACTIVE
    responsible = data.get('responsible')
    mitigation_plan = data.get('mitigation_plan')
    contingency_plan = data.get('contingency_plan')
    trend = data.get('trend',
                     'Estável')

    if not backlog_id or not description:
        abort(400, description="'backlog_id' e 'description' são obrigatórios.")

    backlog = Backlog.query.get_or_404(backlog_id)

    try:
        impact = RiskImpact(impact_str)
        probability = RiskProbability(probability_str)
        status = RiskStatus(status_str)
    except ValueError:
        valid_impacts = [r.value for r in RiskImpact]
        valid_probabilities = [r.value for r in RiskProbability]
        valid_statuses = [r.value for r in RiskStatus]
        abort(400, description=f"Valores inválidos para impacto, probabilidade ou status. Válidos: Impacto={valid_impacts}, Probabilidade={valid_probabilities}, Status={valid_statuses}")

    new_risk = ProjectRisk(
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
        if 'description' in data:
            risk.description = data['description']
        if 'impact' in data:
            risk.impact = RiskImpact(data['impact'])
        if 'probability' in data:
            risk.probability = RiskProbability(data['probability'])
        if 'status' in data:
            risk.status = RiskStatus(data['status'])
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

    except ValueError:
        # Captura erro se algum valor de Enum for inválido
        valid_impacts = [r.value for r in RiskImpact]
        valid_probabilities = [r.value for r in RiskProbability]
        valid_statuses = [r.value for r in RiskStatus]
        abort(400, description=f"Valores inválidos para impacto, probabilidade ou status. Válidos: Impacto={valid_impacts}, Probabilidade={valid_probabilities}, Status={valid_statuses}")
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

@backlog_bp.route('/api/debug/timeline-tasks/<int:backlog_id>', methods=['GET'])
def debug_timeline_tasks(backlog_id):
    """
    Rota de diagnóstico para a linha do tempo
    """
    try:
        # Log para diagnóstico
        current_app.logger.info(f"[Timeline DEBUG] Iniciando diagnóstico para backlog_id: {backlog_id}")
        
        # Verificar se o backlog existe
        backlog = Backlog.query.get_or_404(backlog_id)
        current_app.logger.info(f"[Timeline DEBUG] Backlog encontrado: ID={backlog.id}, Projeto={backlog.project_id}")
        
        # Listar colunas
        columns = Column.query.all()
        columns_info = []
        for col in columns:
            columns_info.append({
                'id': col.id,
                'name': col.name,
                'position': col.position
            })
        
        # Listar tarefas do backlog
        tasks = Task.query.filter_by(backlog_id=backlog_id).all()
        current_app.logger.info(f"[Timeline DEBUG] Tarefas encontradas: {len(tasks)}")
        
        # Tentar serializar cada tarefa individualmente
        tasks_info = []
        for i, task in enumerate(tasks):
            try:
                task_data = serialize_task(task)
                tasks_info.append({
                    'id': task.id,
                    'title': task.title,
                    'serialized_ok': True
                })
            except Exception as e:
                current_app.logger.error(f"[Timeline DEBUG] Erro ao serializar tarefa {task.id}: {str(e)}")
                tasks_info.append({
                    'id': task.id,
                    'title': task.title if hasattr(task, 'title') else "Desconhecido",
                    'serialized_ok': False,
                    'error': str(e)
                })
        
        # Retornar informações de diagnóstico
        return jsonify({
            'backlog': {
                'id': backlog.id,
                'name': backlog.name,
                'project_id': backlog.project_id
            },
            'columns': columns_info,
            'tasks': tasks_info,
            'stats': {
                'total_tasks': len(tasks),
                'serialized_ok': sum(1 for t in tasks_info if t['serialized_ok'])
            }
        })
            
    except Exception as e:
        current_app.logger.error(f"[Timeline DEBUG] Erro ao realizar diagnóstico: {str(e)}", exc_info=True)
        return jsonify({
            'error': f"Erro durante diagnóstico: {str(e)}",
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
    # Assumindo que backlog.project_id é o ID que o macro_service espera
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
                # Adicione mais aliases conforme necessário para outras colunas
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
                        
                    horas_estimadas_raw = row.get('HorasEstimadas')
                    horas_estimadas = None # Garante que se houver erro ou valor vazio, será None
                    if horas_estimadas_raw and not pd.isna(horas_estimadas_raw):
                        valor_processar = str(horas_estimadas_raw).strip()
                        
                        # Remove 'hrs' ou 'hr' (case-insensitive) e espaços ao redor
                        if valor_processar.lower().endswith('hrs'):
                            valor_processar = valor_processar[:-3].strip()
                        elif valor_processar.lower().endswith('hr'):
                            valor_processar = valor_processar[:-2].strip()
                        
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
                        # Se valor_processar ficou vazio (ex: celula continha apenas 'hrs'), horas_estimadas permanece None
                                
                    def parse_date_from_excel(date_input, field_name):
                        if date_input is None or pd.isna(date_input): return None
                        if isinstance(date_input, datetime): return date_input.date()
                        
                        full_str = str(date_input).strip()
                        date_str_to_parse = full_str # Default to the full string
                        
                        # Verifica se há um prefixo textual antes da data (ex: "Qua 14/05/25")
                        # Se a string tiver um espaço, e a parte após o *último* espaço contiver '/' ou '-',
                        # é provável que seja o formato "TEXTO DATA"
                        last_space_index = full_str.rfind(' ')
                        if last_space_index != -1:
                            potential_date_candidate = full_str[last_space_index+1:]
                            # Verifica se o candidato realmente parece uma data
                            is_candidate_like_dd_mm_yy = '/' in potential_date_candidate
                            is_candidate_like_yyyy_mm_dd = potential_date_candidate.count('-') == 2
                            
                            if is_candidate_like_dd_mm_yy or is_candidate_like_yyyy_mm_dd:
                                date_str_to_parse = potential_date_candidate
                            else:
                                # Se a última parte não parece data (ex: "HH:MM:SS" de "YYYY-MM-DD HH:MM:SS"),
                                # ou o espaço não era para separar dia da semana.
                                # Nesse caso, a lógica de pegar a primeira parte antes do espaço é melhor.
                                date_str_to_parse = full_str.split(' ')[0]
                        else:
                            # Sem espaços, usa a string inteira (ex: "14/05/25" ou "2023-10-26")
                            # date_str_to_parse já é full_str, então não precisa de ação aqui.
                            pass

                        # Tenta formato YYYY-MM-DD primeiro
                        try:
                            return datetime.strptime(date_str_to_parse, '%Y-%m-%d').date()
                        except ValueError:
                            # Tenta formato dd/mm/yy ou dd/mm/yyyy
                            try:
                                # Tenta dd/mm/yyyy primeiro
                                return datetime.strptime(date_str_to_parse, '%d/%m/%Y').date()
                            except ValueError:
                                try:
                                    # Depois tenta dd/mm/yy
                                    dt_obj = datetime.strptime(date_str_to_parse, '%d/%m/%y')
                                    # Python's strptime %y handles 00-68 as 2000-2068 and 69-99 as 1969-1999.
                                    current_app.logger.debug(f"Data '{date_str_to_parse}' com formato '%d/%m/%y' resultou em ano {dt_obj.year}")
                                    return dt_obj.date()
                                except ValueError:
                                    errors.append(f"Linha {index + 2}: Formato de {field_name} ('{date_input}') inválido para '{titulo_str}'. Use YYYY-MM-DD ou dd/mm/aa(aaaa), opcionalmente precedido por dia da semana (ex: Qua dd/mm/aa).")
                                    return 'PARSE_ERROR'

                    data_inicio = parse_date_from_excel(row.get('DataInicio'), 'DataInicio')
                    if data_inicio == 'PARSE_ERROR': continue
                    data_fim = parse_date_from_excel(row.get('DataFim'), 'DataFim')
                    if data_fim == 'PARSE_ERROR': continue
                    
                    # Define a posição inicial como 0 (topo da coluna)
                    # Tarefas existentes serão deslocadas automaticamente pela lógica de `move_task` se essa API for chamada depois,
                    # ou se a ordenação no frontend/banco for baseada em `position`.
                    next_position = 0 

                    new_task = Task(
                        title=titulo_str,
                        backlog_id=backlog.id,
                        column_id=target_column_id,
                        # project_id=backlog.project_id, # Task não tem project_id direto, é via backlog
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