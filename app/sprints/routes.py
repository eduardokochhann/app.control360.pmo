from flask import request, jsonify, abort, render_template, send_file
from datetime import datetime
from collections import defaultdict
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
import io
import os

from . import sprints_bp
from .. import db
from ..models import Sprint, Task, Column
from ..backlog.routes import serialize_task

# --- Rotas de Frontend --- 

# GET /sprints/ - Página de Gerenciamento de Sprints
@sprints_bp.route('/', methods=['GET'])
def sprint_management_page():
    # Por enquanto, apenas renderiza o template. Os dados virão via API.
    return render_template('sprints/sprint_management.html', title="Gerenciamento de Sprints")

# --- API Endpoints para Sprints --- 

# GET /api/sprints - Listar todas as Sprints
@sprints_bp.route('/api/sprints', methods=['GET'])
def get_sprints():
    try:
        sprints = Sprint.query.order_by(Sprint.start_date.asc()).all()
        sprints_list = [
            {
                'id': s.id,
                'name': s.name,
                'start_date': s.start_date.isoformat() if s.start_date else None,
                'end_date': s.end_date.isoformat() if s.end_date else None,
                'goal': s.goal,
                'criticality': s.criticality,
                'tasks': [serialize_task(task) for task in s.tasks]
                # Adicionar capacidade e carga horária aqui futuramente
            } for s in sprints
        ]
        return jsonify(sprints_list)
    except Exception as e:
        # Logar o erro seria ideal aqui
        print(f"Erro ao buscar sprints: {e}")
        return jsonify({"message": "Erro interno ao buscar sprints."}), 500

# GET /api/sprints/<int:sprint_id> - Obter detalhes de uma Sprint
@sprints_bp.route('/api/sprints/<int:sprint_id>', methods=['GET'])
def get_sprint(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)
    return jsonify({
        'id': sprint.id,
        'name': sprint.name,
        'start_date': sprint.start_date.isoformat() if sprint.start_date else None,
        'end_date': sprint.end_date.isoformat() if sprint.end_date else None,
        'goal': sprint.goal,
        'criticality': sprint.criticality,
        # Adicionar lista de tasks e totais aqui futuramente
    })

# POST /api/sprints - Criar uma nova Sprint
@sprints_bp.route('/api/sprints', methods=['POST'])
def create_sprint():
    data = request.get_json()
    if not data or not data.get('name') or not data.get('start_date') or not data.get('end_date'):
        abort(400, description="Campos obrigatórios ausentes: name, start_date, end_date")

    try:
        start_date = datetime.fromisoformat(data['start_date'])
        end_date = datetime.fromisoformat(data['end_date'])
    except ValueError:
        abort(400, description="Formato de data inválido. Use ISO 8601 (YYYY-MM-DDTHH:MM:SS ou YYYY-MM-DD).")

    new_sprint = Sprint(
        name=data['name'],
        start_date=start_date,
        end_date=end_date,
        goal=data.get('goal'), # Goal é opcional
        criticality=data.get('criticality', 'Normal') # Usa valor do form ou default
    )
    try:
        user_provided_name = new_sprint.name # Guarda o nome original

        db.session.add(new_sprint) # Adiciona à sessão
        db.session.flush() # Força a atribuição do ID sem commitar

        # Cria o nome final com prefixo e ID
        final_name = f"SPT-{new_sprint.id}-{user_provided_name}"
        new_sprint.name = final_name # Atualiza o nome no objeto

        db.session.commit()
        return jsonify({
            'id': new_sprint.id,
            'name': new_sprint.name,
            'start_date': new_sprint.start_date.isoformat(),
            'end_date': new_sprint.end_date.isoformat(),
            'goal': new_sprint.goal,
            'criticality': new_sprint.criticality
        }), 201
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao criar sprint: {e}")
        return jsonify({"message": "Erro interno ao criar sprint."}), 500

# PUT /api/sprints/<int:sprint_id> - Atualizar uma Sprint
@sprints_bp.route('/api/sprints/<int:sprint_id>', methods=['PUT'])
def update_sprint(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)
    data = request.get_json()
    if not data:
        abort(400, description="Nenhum dado fornecido para atualização.")

    try:
        if 'name' in data: sprint.name = data['name']
        if 'start_date' in data: sprint.start_date = datetime.fromisoformat(data['start_date'])
        if 'end_date' in data: sprint.end_date = datetime.fromisoformat(data['end_date'])
        if 'goal' in data: sprint.goal = data['goal']
        if 'criticality' in data: sprint.criticality = data['criticality']
        
        db.session.commit()
        return jsonify({
            'id': sprint.id,
            'name': sprint.name,
            'start_date': sprint.start_date.isoformat() if sprint.start_date else None,
            'end_date': sprint.end_date.isoformat() if sprint.end_date else None,
            'goal': sprint.goal,
            'criticality': sprint.criticality
        })
    except ValueError:
        db.session.rollback()
        abort(400, description="Formato de data inválido. Use ISO 8601.")
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao atualizar sprint {sprint_id}: {e}")
        return jsonify({"message": f"Erro interno ao atualizar sprint {sprint_id}."}), 500

# DELETE /api/sprints/<int:sprint_id> - Deletar uma Sprint
@sprints_bp.route('/api/sprints/<int:sprint_id>', methods=['DELETE'])
def delete_sprint(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)

    # Regra de negócio: O que fazer com as tarefas associadas?
    # Opção 1: Impedir exclusão se houver tarefas.
    # Opção 2: Desassociar tarefas (setar task.sprint_id = None).
    # Opção 3: Excluir tarefas (perigoso!).
    # Vamos implementar a Opção 2 por enquanto (desassociar).
    
    try:
        for task in sprint.tasks:
            task.sprint_id = None
        
        db.session.delete(sprint)
        db.session.commit()
        return jsonify({'message': f'Sprint {sprint_id} deletada e tarefas desassociadas.'}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao deletar sprint {sprint_id}: {e}")
        return jsonify({"message": f"Erro interno ao deletar sprint {sprint_id}."}), 500

# --- Rotas Adicionais (Exemplo: Associar Tarefas) ---
# POST /api/sprints/<int:sprint_id>/tasks
# GET /api/sprints/<int:sprint_id>/tasks
# DELETE /api/sprints/<int:sprint_id>/tasks/<int:task_id>
# TODO: Implementar estas rotas na próxima fase. 

# --- Rotas API ---

# GET /sprints/api/generic-tasks - Lista todas as tarefas genéricas
@sprints_bp.route('/api/generic-tasks', methods=['GET'])
def list_generic_tasks():
    # Busca apenas tarefas genéricas que não estão em nenhuma sprint
    tasks = Task.query.filter_by(
        is_generic=True,
        sprint_id=None
    ).order_by(Task.position).all()
    return jsonify([serialize_task(task) for task in tasks])

# POST /sprints/api/generic-tasks - Cria uma nova tarefa genérica
@sprints_bp.route('/api/generic-tasks', methods=['POST'])
def create_generic_task():
    data = request.get_json()
    
    # Validação básica
    if not data or 'title' not in data:
        abort(400, description="Título da tarefa é obrigatório")
        
    # Encontra a primeira coluna (TODO) para posicionar a tarefa
    first_column = Column.query.order_by(Column.position).first()
    if not first_column:
        abort(500, description="Nenhuma coluna encontrada no sistema")
    
    # Cria a tarefa genérica
    task = Task(
        title=data['title'],
        description=data.get('description', ''),
        priority=data.get('priority', 'Média'),
        estimated_effort=data.get('estimated_hours'),  # Usa estimated_hours do frontend
        specialist_name=data.get('specialist_name'),
        is_generic=True,
        column_id=first_column.id,
        backlog_id=1  # Assumindo que existe um backlog padrão com ID 1 para tarefas genéricas
    )
    
    db.session.add(task)
    db.session.commit()
    
    return jsonify(serialize_task(task)), 201

# PUT /sprints/api/generic-tasks/<task_id> - Atualiza uma tarefa genérica
@sprints_bp.route('/api/generic-tasks/<int:task_id>', methods=['PUT'])
def update_generic_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    # Verifica se é uma tarefa genérica
    if not task.is_generic:
        abort(400, description="Esta não é uma tarefa genérica")
    
    data = request.get_json()
    
    # Atualiza os campos permitidos
    if 'title' in data:
        task.title = data['title']
    if 'description' in data:
        task.description = data['description']
    if 'priority' in data:
        task.priority = data['priority']
    if 'estimated_hours' in data:  # Usa estimated_hours do frontend
        task.estimated_effort = data['estimated_hours']
    if 'specialist_name' in data:
        task.specialist_name = data['specialist_name']
    if 'status' in data:
        task.status = data['status']
    
    db.session.commit()
    return jsonify(serialize_task(task))

# DELETE /sprints/api/generic-tasks/<task_id> - Remove uma tarefa genérica
@sprints_bp.route('/api/generic-tasks/<int:task_id>', methods=['DELETE'])
def delete_generic_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    # Verifica se é uma tarefa genérica
    if not task.is_generic:
        abort(400, description="Esta não é uma tarefa genérica")
    
    db.session.delete(task)
    db.session.commit()
    return '', 204

# GET /sprints/report/<int:sprint_id> - Página de Relatório da Sprint
@sprints_bp.route('/report/<int:sprint_id>', methods=['GET'])
def sprint_report_page(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)
    
    # Agrupa tarefas por especialista
    specialist_tasks = defaultdict(list)
    specialist_effort = defaultdict(float)
    
    for task in sprint.tasks:
        if task.specialist_name:
            specialist_tasks[task.specialist_name].append(task)
            specialist_effort[task.specialist_name] += task.estimated_effort or 0
    
    return render_template(
        'sprints/sprint_report.html',
        sprint=sprint,
        specialist_tasks=dict(specialist_tasks),
        specialist_effort=dict(specialist_effort),
        title=f"Relatório - {sprint.name}"
    )

# GET /api/sprints/<int:sprint_id>/report - Obter dados do relatório da Sprint
@sprints_bp.route('/api/sprints/<int:sprint_id>/report', methods=['GET'])
def get_sprint_report(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)
    
    # Agrupa tarefas por especialista
    specialist_tasks = defaultdict(list)
    specialist_effort = defaultdict(float)
    
    for task in sprint.tasks:
        if task.specialist_name:
            specialist_tasks[task.specialist_name].append(serialize_task(task))
            specialist_effort[task.specialist_name] += task.estimated_effort or 0
    
    return jsonify({
        'sprint': {
            'id': sprint.id,
            'name': sprint.name,
            'start_date': sprint.start_date.isoformat() if sprint.start_date else None,
            'end_date': sprint.end_date.isoformat() if sprint.end_date else None,
            'goal': sprint.goal,
            'criticality': sprint.criticality
        },
        'specialist_tasks': dict(specialist_tasks),
        'specialist_effort': dict(specialist_effort)
    })

# GET /sprints/consolidated-report - Página de seleção de Sprints para relatório
@sprints_bp.route('/consolidated-report', methods=['GET'])
def consolidated_report_page():
    sprints = Sprint.query.order_by(Sprint.start_date.desc()).all()
    return render_template(
        'sprints/consolidated_report_select.html',
        title="Relatório Consolidado de Sprints",
        sprints=sprints
    )

# POST /sprints/consolidated-report - Gerar relatório consolidado
@sprints_bp.route('/consolidated-report', methods=['POST'])
def generate_consolidated_report():
    sprint_ids = request.form.getlist('sprint_ids[]')
    if not sprint_ids:
        abort(400, description="Nenhuma sprint selecionada")

    sprints = Sprint.query.filter(Sprint.id.in_(sprint_ids)).order_by(Sprint.start_date).all()
    if not sprints:
        abort(404, description="Nenhuma sprint encontrada")

    # Cálculo de datas do período total
    start_date = min(sprint.start_date for sprint in sprints)
    end_date = max(sprint.end_date for sprint in sprints)

    # Contadores e acumuladores
    total_tasks = 0
    specialist_summary = defaultdict(lambda: {"name": "", "total_tasks": 0, "total_hours": 0})
    processed_sprints = []

    # Processa cada sprint
    for sprint in sprints:
        sprint_total_hours = 0
        processed_tasks = []

        # Busca todas as tarefas da sprint
        tasks = Task.query.filter_by(sprint_id=sprint.id).all()
        
        for task in tasks:
            # Determina o status da tarefa baseado no nome da coluna
            status = "Em Andamento"
            if task.column_id:
                column = Column.query.get(task.column_id)
                if column and ('concluído' in column.name.lower() or 'concluido' in column.name.lower()):
                    status = "Concluído"
            
            # Processa a tarefa
            task_dict = {
                "id": task.id,
                "name": task.title,
                "specialist_name": task.specialist_name,
                "estimated_hours": task.estimated_effort or 0,
                "status": status
            }
            processed_tasks.append(task_dict)

            # Atualiza contadores
            total_tasks += 1
            sprint_total_hours += task.estimated_effort or 0

            # Atualiza resumo do especialista
            specialist = task.specialist_name or "Não Atribuído"
            specialist_summary[specialist]["name"] = specialist
            specialist_summary[specialist]["total_tasks"] += 1
            specialist_summary[specialist]["total_hours"] += task.estimated_effort or 0

        # Cria um dicionário com os dados processados da sprint
        sprint_dict = {
            "id": sprint.id,
            "name": sprint.name,
            "start_date": sprint.start_date,
            "end_date": sprint.end_date,
            "goal": sprint.goal,
            "criticality": sprint.criticality,
            "tasks": processed_tasks,
            "total_hours": sprint_total_hours
        }
        processed_sprints.append(sprint_dict)

    # Converte o resumo de especialistas para lista ordenada
    specialist_summary = sorted(
        specialist_summary.values(),
        key=lambda x: (-x["total_hours"], x["name"])
    )

    return render_template(
        'sprints/consolidated_report.html',
        sprints=processed_sprints,
        start_date=start_date,
        end_date=end_date,
        total_tasks=total_tasks,
        specialist_summary=specialist_summary,
        sprint_ids=sprint_ids  # Adicionando os IDs das sprints para o template
    )

# GET /sprints/export-consolidated-report - Exportar relatório consolidado para Excel
@sprints_bp.route('/export-consolidated-report', methods=['GET'])
def export_consolidated_report():
    sprint_ids = request.args.get('sprint_ids', '').split(',')
    if not sprint_ids or not sprint_ids[0]:
        abort(400, description="Nenhuma sprint selecionada")

    sprints = Sprint.query.filter(Sprint.id.in_(sprint_ids)).order_by(Sprint.start_date).all()
    if not sprints:
        abort(404, description="Nenhuma sprint encontrada")

    # Criar um novo workbook
    wb = Workbook()
    
    # Estilos
    header_font = Font(bold=True)
    header_fill = PatternFill(start_color='f8f9fa', end_color='f8f9fa', fill_type='solid')
    
    # 1. Planilha de Resumo Geral
    ws_resumo = wb.active
    ws_resumo.title = "Resumo Geral"
    
    # Calcular total de tarefas
    total_tasks = Task.query.filter(Task.sprint_id.in_(sprint_ids)).count()
    
    # Cabeçalhos
    headers = [
        ["Total de Sprints", str(len(sprints))],
        ["Período Início", min(sprint.start_date for sprint in sprints).strftime('%d/%m/%Y')],
        ["Período Fim", max(sprint.end_date for sprint in sprints).strftime('%d/%m/%Y')],
        ["Total de Tarefas", str(total_tasks)]
    ]
    
    for row_idx, (header, value) in enumerate(headers, 1):
        ws_resumo.cell(row=row_idx, column=1, value=header).font = header_font
        ws_resumo.cell(row=row_idx, column=2, value=value)
    
    # 2. Planilha de Capacidade por Especialista
    ws_especialistas = wb.create_sheet("Capacidade por Especialista")
    
    # Cabeçalhos
    headers = ["Especialista", "Total de Tarefas", "Horas Estimadas"]
    for col_idx, header in enumerate(headers, 1):
        cell = ws_especialistas.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
    
    # Dados dos especialistas
    specialist_summary = defaultdict(lambda: {"name": "", "total_tasks": 0, "total_hours": 0})
    
    # Buscar todas as tarefas de uma vez
    tasks = Task.query.filter(Task.sprint_id.in_(sprint_ids)).all()
    
    for task in tasks:
        specialist = task.specialist_name or "Não Atribuído"
        specialist_summary[specialist]["name"] = specialist
        specialist_summary[specialist]["total_tasks"] += 1
        specialist_summary[specialist]["total_hours"] += task.estimated_effort or 0
    
    sorted_specialists = sorted(
        specialist_summary.values(),
        key=lambda x: (-x["total_hours"], x["name"])
    )
    
    for row_idx, specialist in enumerate(sorted_specialists, 2):
        ws_especialistas.cell(row=row_idx, column=1, value=specialist["name"])
        ws_especialistas.cell(row=row_idx, column=2, value=specialist["total_tasks"])
        ws_especialistas.cell(row=row_idx, column=3, value=round(specialist["total_hours"], 1))
    
    # 3. Planilha de Detalhes por Sprint
    ws_detalhes = wb.create_sheet("Detalhes por Sprint")
    
    # Cabeçalhos
    headers = ["Sprint", "Período", "Tarefa", "Especialista", "Horas Estimadas", "Status"]
    for col_idx, header in enumerate(headers, 1):
        cell = ws_detalhes.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
    
    # Dados das tarefas
    current_row = 2
    for sprint in sprints:
        # Buscar tarefas da sprint
        sprint_tasks = Task.query.filter_by(sprint_id=sprint.id).all()
        
        for task in sprint_tasks:
            status = "Em Andamento"
            if task.column_id:
                column = Column.query.get(task.column_id)
                if column and ('concluído' in column.name.lower() or 'concluido' in column.name.lower()):
                    status = "Concluído"
            
            ws_detalhes.cell(row=current_row, column=1, value=sprint.name)
            ws_detalhes.cell(row=current_row, column=2, value=f"{sprint.start_date.strftime('%d/%m/%Y')} - {sprint.end_date.strftime('%d/%m/%Y')}")
            ws_detalhes.cell(row=current_row, column=3, value=task.title)
            ws_detalhes.cell(row=current_row, column=4, value=task.specialist_name or "Não Atribuído")
            ws_detalhes.cell(row=current_row, column=5, value=round(task.estimated_effort or 0, 1))
            ws_detalhes.cell(row=current_row, column=6, value=status)
            current_row += 1
    
    # Ajustar larguras das colunas
    for ws in [ws_resumo, ws_especialistas, ws_detalhes]:
        for column in ws.columns:
            max_length = 0
            column = list(column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2)
            ws.column_dimensions[column[0].column_letter].width = adjusted_width
    
    # Salvar o arquivo
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    filename = f"relatorio_consolidado_sprints_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    ) 