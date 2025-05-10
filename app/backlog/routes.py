from flask import render_template, jsonify, request, abort, current_app, redirect, url_for
from . import backlog_bp # Importa o blueprint
from .. import db # Importa a instância do banco de dados
from ..models import Backlog, Task, Column, Sprint, TaskStatus, ProjectMilestone, ProjectRisk, MilestoneStatus, MilestoneCriticality, RiskImpact, RiskProbability, RiskStatus # Importa os modelos
from ..macro.services import MacroService # Importa o serviço Macro
import pandas as pd
from datetime import datetime, timedelta, date

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

        return {
            'id': task.id,
            'name': task.title,
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
            'specialist_name': task.specialist_name if hasattr(task, 'specialist_name') else None
        }
    except Exception as e:
        current_app.logger.error(f"[Erro ao serializar tarefa {task.id}]: {str(e)}")
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
            current_backlog_name=backlog_name
        )

    except Exception as e:
        current_app.logger.error(f"[DEBUG] Erro ao carregar quadro para projeto {project_id}: {str(e)}", exc_info=True)
        # TODO: Adicionar flash message?
        return redirect(url_for('.project_selection'))

# --- API Endpoints --- 

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
        abort(400, description="Nenhum dado fornecido para atualização.")

    # Atualiza campos permitidos
    if 'name' in data:
        title = data['name'].strip()
        if not title:
            abort(400, description="Título (Nome) não pode ser vazio.")
        task.title = title
        
    if 'description' in data:
        task.description = data['description']
        
    if 'priority' in data:
        task.priority = data['priority']

    # --- Atualização das Horas --- 
    # Mapeia 'estimated_hours' do frontend para 'estimated_effort' do backend
    if 'estimated_hours' in data:
        try:
            # Permite None ou valor vazio para limpar a estimativa
            if data['estimated_hours'] is None or str(data['estimated_hours']).strip() == '':
                 task.estimated_effort = None
            else:
                estimated = float(data['estimated_hours'])
                if estimated < 0:
                    abort(400, description="Horas estimadas não podem ser negativas.")
                task.estimated_effort = estimated
        except (ValueError, TypeError):
             abort(400, description="Valor inválido para 'estimated_hours'. Use um número.")

    # Nota: 'remaining_hours' não é atualizado diretamente aqui.
    # Ele é calculado na função serialize_task com base em estimated_effort e logged_time.
    # Se precisarmos editar 'logged_time', um campo e lógica similar a 'estimated_hours' seriam necessários.
    # Por exemplo:
    # if 'logged_time' in data:
    #     try:
    #         if data['logged_time'] is None or str(data['logged_time']).strip() == '':
    #              task.logged_time = None
    #         else:
    #             logged = float(data['logged_time'])
    #             if logged < 0:
    #                 abort(400, description="Horas trabalhadas não podem ser negativas.")
    #             task.logged_time = logged
    #     except (ValueError, TypeError):
    #          abort(400, description="Valor inválido para 'logged_time'. Use um número.")
    # ------------------------------
        
    if 'start_date' in data:
        if data['start_date']: # Se não for vazio/null
            try:
                task.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
            except (ValueError, TypeError):
                abort(400, description="Formato inválido para 'start_date'. Use YYYY-MM-DD.")
        else: # Permite limpar a data
            task.start_date = None
            
    if 'due_date' in data: # <<< ADICIONADO PARA DUE_DATE
        if data['due_date']:
            try:
                task.due_date = datetime.strptime(data['due_date'], '%Y-%m-%d')
            except (ValueError, TypeError):
                abort(400, description="Formato inválido para 'due_date'. Use YYYY-MM-DD.")
        else:
            task.due_date = None
            
    if 'logged_time' in data: # <<< ADICIONADO PARA LOGGED_TIME
        if data['logged_time'] is not None and data['logged_time'] != '':
            try:
                logged = float(data['logged_time'])
                if logged < 0:
                    abort(400, description="'logged_time' não pode ser negativo.")
                task.logged_time = logged
            except (ValueError, TypeError):
                 abort(400, description="Valor inválido para 'logged_time'. Use um número.")
        else:
             # Permitir zerar o tempo logado? Ou apenas incrementar?
             # Por ora, permite definir/limpar.
             task.logged_time = None 
    
    # <<< INÍCIO: Atualizar especialista >>>
    if 'specialist_name' in data:
        # Permite string vazia ou None para limpar o especialista
        task.specialist_name = data['specialist_name'] if data['specialist_name'] else None
    # <<< FIM: Atualizar especialista >>>

    try:
        db.session.commit()
        db.session.refresh(task) 
        return jsonify(serialize_task(task))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao salvar alterações da tarefa {task_id}: {e}", exc_info=True)
        abort(500, description="Erro interno ao salvar alterações da tarefa.")

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
        # logged_time deve iniciar como 0 ou None (não vem do form de criação)
        # sprint_id também não vem do form de criação
        backlog_id=backlog.id,
        column_id=first_column.id, # Atribui à primeira coluna
        specialist_name=default_specialist, # <<< Define o especialista padrão >>>
        # sprint_id=data.get('sprint_id') # Remover se não for enviado
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

    # Atualiza data de início quando movida para Em Andamento
    if is_moving_to_progress and not was_in_progress:
        if not task.start_date:  # Define apenas na primeira vez que entra em EM ANDAMENTO
            task.start_date = datetime.utcnow()
            current_app.logger.info(f"[Task Moved] Tarefa {task.id} movida para Em Andamento, data de início definida")

    # Atualiza status e data de conclusão
    if is_moving_to_done:
        task.status = TaskStatus.DONE
        if not task.completed_at: # Define apenas na primeira vez que entra em DONE
            task.completed_at = datetime.utcnow()
            current_app.logger.info(f"[Task Moved] Tarefa {task.id} movida para Concluído, data de conclusão definida")
    else:
        # Se saiu de DONE, volta para um status apropriado e limpa data de conclusão
        if was_in_done:
             task.completed_at = None 
        # Tenta mapear nome da coluna para status comparando com os valores do Enum
        found_status = False
        for status_member in TaskStatus:
            if status_member.value.upper() == target_column.name.upper():
                task.status = status_member
                found_status = True
                break # Encontrou o status correspondente
        
        if not found_status and not is_moving_to_done: # Se não encontrou e não está indo para DONE
            task.status = TaskStatus.TODO # Mantém o fallback para TODO
            current_app.logger.warning(f"Não foi possível mapear o nome da coluna '{target_column.name}' para um TaskStatus.")
    
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
        # 1. Busca todas as tarefas sem sprint_id, ordenadas por backlog e posição
        unassigned_tasks = Task.query.filter(Task.sprint_id == None)\
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

    if data is None: # Verifica se o corpo da requisição é null ou vazio
        abort(400, description="Corpo da requisição ausente ou inválido.")

    # Espera um campo 'sprint_id' no corpo.
    # Pode ser um número (ID da sprint) ou null/None para desassociar.
    new_sprint_id = data.get('sprint_id')

    # Espera um campo 'position' no corpo.
    new_position = data.get('position')
    if new_position is None or not isinstance(new_position, int) or new_position < 0:
        abort(400, description="Campo 'position' ausente ou inválido. Deve ser um inteiro não negativo.")

    # Validação: Se for um ID, verifica se a Sprint existe
    if new_sprint_id is not None:
        try:
            # Converte para int se não for None
            new_sprint_id = int(new_sprint_id)
            target_sprint = Sprint.query.get(new_sprint_id)
            if not target_sprint:
                abort(400, description=f"Sprint com ID {new_sprint_id} não encontrada.")
        except (ValueError, TypeError):
             abort(400, description="Valor inválido para 'sprint_id'. Deve ser um número ou null.")

    # Guarda os valores antigos para lógica de reordenação
    old_sprint_id = task.sprint_id
    old_position = task.position

    current_app.logger.info(f"[AssignTask] Iniciando. TaskID: {task_id}, OldSprint: {old_sprint_id}, OldPos: {old_position}, NewSprint: {new_sprint_id}, NewPos: {new_position}")

    # --- Lógica de Reordenação --- 
    try:
        # 1. Ajusta posições na lista de ORIGEM (se diferente da destino)
        if old_sprint_id != new_sprint_id:
            if old_sprint_id is None: # Origem era o Backlog
                # Decrementa backlog tasks que estavam depois
                current_app.logger.debug(f"[AssignTask] Decrementando posições no Backlog ID {task.backlog_id} após pos {old_position}")
                Task.query.filter(
                    Task.backlog_id == task.backlog_id, 
                    Task.sprint_id == None, 
                    Task.position > old_position
                ).update({Task.position: Task.position - 1}, synchronize_session='fetch')
            else: # Origem era outra Sprint
                 # Decrementa sprint tasks que estavam depois
                current_app.logger.debug(f"[AssignTask] Decrementando posições na Sprint ID {old_sprint_id} após pos {old_position}")
                Task.query.filter(
                    Task.sprint_id == old_sprint_id, 
                    Task.position > old_position
                ).update({Task.position: Task.position - 1}, synchronize_session='fetch')
        
        # 2. Ajusta posições na lista de DESTINO
        if old_sprint_id != new_sprint_id: # Se moveu entre listas diferentes
             if new_sprint_id is None: # Destino é o Backlog
                # Incrementa backlog tasks a partir da nova posição
                current_app.logger.debug(f"[AssignTask] Incrementando posições no Backlog ID {task.backlog_id} a partir da pos {new_position}")
                Task.query.filter(
                    Task.backlog_id == task.backlog_id, 
                    Task.sprint_id == None, 
                    Task.position >= new_position
                ).update({Task.position: Task.position + 1}, synchronize_session='fetch')
             else: # Destino é uma Sprint
                # Incrementa sprint tasks a partir da nova posição
                current_app.logger.debug(f"[AssignTask] Incrementando posições na Sprint ID {new_sprint_id} a partir da pos {new_position}")
                Task.query.filter(
                    Task.sprint_id == new_sprint_id, 
                    Task.position >= new_position
                ).update({Task.position: Task.position + 1}, synchronize_session='fetch')
        else: # Movimento dentro da mesma lista (mesma sprint ou mesmo backlog)
            if new_position > old_position: # Moveu para baixo
                if new_sprint_id is not None: # Dentro da Sprint
                    Task.query.filter(
                        Task.sprint_id == new_sprint_id,
                        Task.position > old_position,
                        Task.position <= new_position
                    ).update({Task.position: Task.position - 1}, synchronize_session='fetch')
                else: # Dentro do Backlog
                     Task.query.filter(
                        Task.backlog_id == task.backlog_id,
                        Task.sprint_id == None,
                        Task.position > old_position,
                        Task.position <= new_position
                    ).update({Task.position: Task.position - 1}, synchronize_session='fetch')
            elif new_position < old_position: # Moveu para cima
                if new_sprint_id is not None: # Dentro da Sprint
                    Task.query.filter(
                        Task.sprint_id == new_sprint_id,
                        Task.position >= new_position,
                        Task.position < old_position
                    ).update({Task.position: Task.position + 1}, synchronize_session='fetch')
                else: # Dentro do Backlog
                    Task.query.filter(
                        Task.backlog_id == task.backlog_id,
                        Task.sprint_id == None,
                        Task.position >= new_position,
                        Task.position < old_position
                    ).update({Task.position: Task.position + 1}, synchronize_session='fetch')

        # 3. Atualiza a tarefa movida
        current_app.logger.debug(f"[AssignTask] Atualizando Task ID {task.id}: sprint_id={new_sprint_id}, position={new_position}")
        task.sprint_id = new_sprint_id
        task.position = new_position

        # 4. Commit das alterações
        current_app.logger.info(f"[AssignTask] Prestes a commitar alterações para Task ID {task.id}")
        db.session.commit()
        current_app.logger.info(f"[AssignTask] Commit bem-sucedido para Task ID {task.id}")
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
        # Log para diagnóstico
        current_app.logger.info(f"[Timeline DEBUG] Iniciando busca de tarefas para backlog_id: {backlog_id}")
        
        # Verificar se o backlog existe
        backlog = Backlog.query.get_or_404(backlog_id)
        current_app.logger.info(f"[Timeline DEBUG] Backlog encontrado: ID={backlog.id}, Projeto={backlog.project_id}")
        
        # Parâmetros de filtro
        last_days = request.args.get('last_days', default=7, type=int)
        next_days = request.args.get('next_days', default=7, type=int)
        current_app.logger.info(f"[Timeline DEBUG] Filtros: last_days={last_days}, next_days={next_days}")
        
        # Data atual como referência
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Calcula intervalos
        past_date = today - timedelta(days=last_days)
        future_date = today + timedelta(days=next_days)
        current_app.logger.info(f"[Timeline DEBUG] Intervalo de datas: passado={past_date}, futuro={future_date}")
        
        # Obter e verificar todas as colunas disponíveis
        current_app.logger.info("[Timeline DEBUG] Listando todas as colunas disponíveis:")
        all_columns = Column.query.all()
        
        # Ver quais coluna estão ou não disponíveis
        for col in all_columns:
            current_app.logger.info(f"\t- Coluna: ID={col.id}, Nome='{col.name}'")
        
        # Definir as listas iniciais como vazias
        recently_completed = []
        upcoming_tasks = []
        recently_started = []

        # Procurar as colunas pelo nome
        for col in all_columns:
            if col.name.upper() == 'A FAZER':
                a_fazer_column = col
                current_app.logger.info(f"[Timeline DEBUG] Coluna 'A Fazer' encontrada: ID={col.id}")
            elif col.name.upper() == 'EM ANDAMENTO':
                em_andamento_column = col
                current_app.logger.info(f"[Timeline DEBUG] Coluna 'Em Andamento' encontrada: ID={col.id}")
            elif col.name.upper() == 'CONCLUÍDO':
                concluido_column = col
                current_app.logger.info(f"[Timeline DEBUG] Coluna 'Concluído' encontrada: ID={col.id}")
            
        # 1. Tarefas concluídas recentemente (na coluna Concluído)
        try:
            if concluido_column:
                current_app.logger.info(f"[Timeline DEBUG] Buscando tarefas concluídas na coluna ID={concluido_column.id}")
                
                # IMPORTANTE: Buscamos APENAS por coluna, ignorando a data inicialmente
                recently_completed_query = Task.query.filter(
                    Task.backlog_id == backlog_id,
                    Task.column_id == concluido_column.id
                )
                
                # Opcional: Ordenar por completed_at se existir, senão por posição
                try:
                    recently_completed_query = recently_completed_query.order_by(Task.completed_at.desc().nullslast())
                    current_app.logger.info("[Timeline DEBUG] Ordenação por data de conclusão aplicada")
                except Exception as e:
                    current_app.logger.warning(f"[Timeline DEBUG] Falha ao ordenar por completed_at: {str(e)}")
                    recently_completed_query = recently_completed_query.order_by(Task.position)
                
                # Aplicar limite
                recently_completed = recently_completed_query.limit(10).all()
                current_app.logger.info(f"[Timeline DEBUG] Tarefas concluídas encontradas: {len(recently_completed)}")
                
                # Log detalhado de cada tarefa encontrada
                for task in recently_completed:
                    current_app.logger.info(f"[Timeline DEBUG] Tarefa concluída: ID={task.id}, Título={task.title}, Concluída em={task.completed_at}")
            else:
                current_app.logger.warning("[Timeline DEBUG] Coluna 'concluído' não encontrada, usando lista vazia para tarefas concluídas")
        except Exception as e:
            current_app.logger.error(f"[Timeline DEBUG] Erro ao buscar tarefas concluídas: {str(e)}")
            
        # 2. Próximas tarefas com prazo nos próximos X dias (e não concluídas)
        try:
            current_app.logger.info("[Timeline DEBUG] Buscando próximas tarefas")
            
            # IMPORTANTE: Buscar apenas tarefas que ainda vão começar (na coluna "A Fazer")
            # e que tenham uma data de início ou prazo nos próximos dias
            upcoming_query = Task.query.filter(
                Task.backlog_id == backlog_id,
                # Garantir que estamos pegando apenas tarefas da coluna "A Fazer"
                Task.column_id == a_fazer_column.id,
                db.or_(
                    # Tarefas com prazo (due_date) nos próximos dias
                    db.and_(
                        Task.due_date.isnot(None),
                        Task.due_date >= today,
                        Task.due_date <= future_date
                    ),
                    # OU tarefas com início (start_date) nos próximos dias
                    db.and_(
                        Task.start_date.isnot(None),
                        Task.start_date >= today,
                        Task.start_date <= future_date
                    )
                )
            )
            
            # Não precisamos mais filtrar por coluna concluído, já que estamos filtrando apenas para coluna "A Fazer"
            # Mas mantemos o código por segurança
            if concluido_column:
                try:
                    upcoming_query = upcoming_query.filter(Task.column_id != concluido_column.id)
                    current_app.logger.info("[Timeline DEBUG] Filtro 'não concluído' aplicado para próximas tarefas")
                except Exception as e:
                    current_app.logger.error(f"[Timeline DEBUG] Erro ao filtrar tarefas não concluídas: {str(e)}")
            
            # Aplica ordenação e limite
            # Ordenando primeiro por start_date (data de início), depois por due_date (prazo)
            upcoming_tasks = upcoming_query.order_by(
                Task.start_date.asc().nullslast(),
                Task.due_date.asc().nullslast()
            ).limit(10).all()
            current_app.logger.info(f"[Timeline DEBUG] Próximas tarefas encontradas: {len(upcoming_tasks)}")
            
            # Log detalhado das tarefas encontradas
            for task in upcoming_tasks:
                current_app.logger.info(f"[Timeline DEBUG] Próxima tarefa: ID={task.id}, Título={task.title}, Prazo={task.due_date}, Início={task.start_date}")
        except Exception as e:
            current_app.logger.error(f"[Timeline DEBUG] Erro ao buscar próximas tarefas: {str(e)}")
            upcoming_tasks = []  # Garante que a lista esteja inicializada em caso de erro
        
        # 3. Tarefas iniciadas recentemente (na coluna Em Andamento)
        try:
            if em_andamento_column:
                current_app.logger.info(f"[Timeline DEBUG] Buscando tarefas em andamento na coluna ID={em_andamento_column.id}")
                
                # IMPORTANTE: Buscamos APENAS por coluna, ignorando a data inicialmente
                started_query = Task.query.filter(
                    Task.backlog_id == backlog_id,
                    Task.column_id == em_andamento_column.id
                )
                
                # Opcional: Ordenar por start_date se existir, senão por posição
                try:
                    started_query = started_query.order_by(Task.start_date.desc().nullslast())
                    current_app.logger.info("[Timeline DEBUG] Ordenação por data de início aplicada")
                except Exception as e:
                    current_app.logger.warning(f"[Timeline DEBUG] Falha ao ordenar por start_date: {str(e)}")
                    started_query = started_query.order_by(Task.position)
                
                # Aplicar limite para evitar retornar muitas tarefas antigas
                recently_started = started_query.limit(10).all()
                current_app.logger.info(f"[Timeline DEBUG] Tarefas em andamento encontradas: {len(recently_started)}")
                
                # Log detalhado de cada tarefa encontrada
                for task in recently_started:
                    current_app.logger.info(f"[Timeline DEBUG] Tarefa em andamento: ID={task.id}, Título={task.title}, Iniciada em={task.start_date}")
            else:
                current_app.logger.warning("[Timeline DEBUG] Coluna 'Em Andamento' não encontrada, usando lista vazia para tarefas iniciadas")
        except Exception as e:
            current_app.logger.error(f"[Timeline DEBUG] Erro ao buscar tarefas em andamento: {str(e)}")
        
        # Serializa e organiza os resultados
        try:
            current_app.logger.info("[Timeline DEBUG] Serializando resultados")
            result = {
                'recently_completed': [serialize_task(task) for task in recently_completed],
                'upcoming_tasks': [serialize_task(task) for task in upcoming_tasks],
                'recently_started': [serialize_task(task) for task in recently_started]
            }
            current_app.logger.info(f"[Timeline DEBUG] Serialização concluída: {len(recently_completed)} concluídas, {len(upcoming_tasks)} próximas, {len(recently_started)} iniciadas")
            return jsonify(result)
        except Exception as e:
            current_app.logger.error(f"[Timeline DEBUG] Erro ao serializar resultados: {str(e)}")
            raise
        
    except Exception as e:
        current_app.logger.error(f"[Timeline DEBUG] Erro global ao buscar tarefas da timeline para backlog {backlog_id}: {str(e)}", exc_info=True)
        # Em vez de abortar com 500, retorne uma resposta de erro com as listas vazias
        result = {
            'recently_completed': [],
            'upcoming_tasks': [],
            'recently_started': [],
            'error': f"Erro ao processar a linha do tempo: {str(e)}"
        }
        return jsonify(result), 500 

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