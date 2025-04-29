from flask import request, jsonify, abort, render_template
from datetime import datetime

from . import sprints_bp
from .. import db
from ..models import Sprint, Task # Importar Sprint e Task
from ..backlog.routes import serialize_task # Importar função de serialização

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