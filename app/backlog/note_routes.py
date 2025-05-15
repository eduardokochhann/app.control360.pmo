from flask import request, jsonify, current_app, abort
from app import db
from app.models import Note, Tag, Backlog
from . import backlog_bp
import logging

logger = logging.getLogger(__name__)

# API para Notas
@backlog_bp.route('/api/notes', methods=['GET']) # URL final: /backlog/api/notes
def get_notes():
    """Retorna todas as notas de um projeto ou tarefa específica."""
    logger.info("[API Notes] Recebendo requisição GET para /api/notes")
    project_id = request.args.get('project_id')
    task_id = request.args.get('task_id', type=int)
    
    query = Note.query
    
    if project_id:
        # Garante que o project_id seja uma string limpa (apenas números)
        project_id = str(project_id).strip().split('.')[0]
        logger.info(f"[API Notes] Filtrando por project_id: {project_id}")
        query = query.filter_by(project_id=project_id)
    if task_id:
        logger.info(f"[API Notes] Filtrando por task_id: {task_id}")
        query = query.filter_by(task_id=task_id)
    
    notes = query.order_by(Note.created_at.desc()).all()
    logger.info(f"[API Notes] Retornando {len(notes)} notas")
    return jsonify([note.to_dict() for note in notes])

@backlog_bp.route('/api/notes/<int:note_id>', methods=['GET'])
def get_note(note_id):
    """Retorna uma nota específica."""
    logger.info(f"[API Notes] Recebendo requisição GET para /api/notes/{note_id}")
    note = Note.query.get_or_404(note_id)
    logger.info(f"[API Notes] Retornando nota ID: {note.id}")
    return jsonify(note.to_dict())

@backlog_bp.route('/api/notes', methods=['POST'])
def create_note():
    """Cria uma nova nota."""
    logger.info("[API Notes] Recebendo requisição POST para /api/notes")
    data = request.get_json()
    
    if not data:
        logger.error("[API Notes] Nenhum dado JSON recebido")
        return jsonify({'error': 'Dados JSON não fornecidos'}), 400
    
    if not data.get('content'):
        logger.error("[API Notes] Conteúdo da nota não fornecido")
        return jsonify({'error': 'Conteúdo da nota é obrigatório'}), 400
    
    if not data.get('project_id'):
        logger.error("[API Notes] ID do projeto não fornecido")
        return jsonify({'error': 'ID do projeto é obrigatório'}), 400
    
    # Limpar project_id (remover parte decimal se existir)
    cleaned_project_id = str(data['project_id']).strip().split('.')[0]
    
    # Busca o backlog pelo project_id
    backlog = Backlog.query.filter_by(project_id=cleaned_project_id).first()
    if not backlog:
        logger.error(f"[API Notes] Backlog não encontrado para project_id: {cleaned_project_id}")
        return jsonify({'error': f'Backlog não encontrado para o projeto ID {cleaned_project_id}'}), 404
    
    # Processa as tags
    tags = []
    if data.get('tags'):
        for tag_name in data['tags']:
            if not tag_name or not tag_name.strip():
                continue
                
            tag = Tag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                db.session.add(tag)
            tags.append(tag)
    
    # Garante que note_type seja 'project' ou 'task'
    note_type = data.get('note_type', 'project')
    if note_type not in ['project', 'task']:
        note_type = 'project' if not data.get('task_id') else 'task'
    
    note = Note(
        content=data['content'],
        project_id=cleaned_project_id,  # ID do projeto limpo
        backlog_id=backlog.id,  # ID do backlog
        task_id=data.get('task_id'),
        category=data.get('category', 'general'),
        priority=data.get('priority', 'medium'),
        note_type=note_type,
        tags=tags
    )
    
    try:
        db.session.add(note)
        db.session.commit()
        logger.info(f"[API Notes] Nota criada com sucesso ID: {note.id}")
        return jsonify(note.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        logger.exception(f"[API Notes] Erro ao criar nota: {str(e)}")
        return jsonify({'error': f'Erro ao salvar nota: {str(e)}'}), 500

@backlog_bp.route('/api/notes/<int:note_id>', methods=['PUT'])
def update_note(note_id):
    """Atualiza uma nota existente."""
    logger.info(f"[API Notes] Recebendo requisição PUT para /api/notes/{note_id}")
    note = Note.query.get_or_404(note_id)
    data = request.get_json()
    
    if not data:
        logger.error("[API Notes] Nenhum dado JSON recebido")
        return jsonify({'error': 'Dados JSON não fornecidos'}), 400
    
    if 'content' in data:
        note.content = data['content']
    if 'category' in data:
        note.category = data['category']
    if 'priority' in data:
        note.priority = data['priority']
    if 'task_id' in data:
        note.task_id = data['task_id']
    
    # Atualiza tags
    if 'tags' in data:
        note.tags.clear()
        for tag_name in data['tags']:
            if not tag_name or not tag_name.strip():
                continue
                
            tag = Tag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                db.session.add(tag)
            note.tags.append(tag)
    
    try:
        db.session.commit()
        logger.info(f"[API Notes] Nota atualizada com sucesso ID: {note.id}")
        return jsonify(note.to_dict())
    except Exception as e:
        db.session.rollback()
        logger.exception(f"[API Notes] Erro ao atualizar nota: {str(e)}")
        return jsonify({'error': f'Erro ao atualizar nota: {str(e)}'}), 500

@backlog_bp.route('/api/notes/<int:note_id>', methods=['DELETE'])
def delete_note(note_id):
    """Exclui uma nota."""
    logger.info(f"[API Notes] Recebendo requisição DELETE para /api/notes/{note_id}")
    note = Note.query.get_or_404(note_id)
    
    try:
        db.session.delete(note)
        db.session.commit()
        logger.info(f"[API Notes] Nota excluída com sucesso ID: {note_id}")
        return '', 204
    except Exception as e:
        db.session.rollback()
        logger.exception(f"[API Notes] Erro ao excluir nota: {str(e)}")
        return jsonify({'error': f'Erro ao excluir nota: {str(e)}'}), 500

@backlog_bp.route('/api/tags', methods=['GET'])
def get_tags():
    """Retorna todas as tags disponíveis."""
    logger.info("[API Notes] Recebendo requisição GET para /api/tags")
    tags = Tag.query.all()
    return jsonify([{'id': tag.id, 'name': tag.name} for tag in tags])

# Rotas do relatório
@backlog_bp.route('/api/notes/report/preview', methods=['GET'])
def preview_report():
    """Retorna um preview do relatório baseado nas notas do projeto."""
    logger.info("[API Notes] Recebendo requisição GET para /api/notes/report/preview")
    project_id = request.args.get('project_id')
    
    if not project_id:
        logger.error("[API Notes] Parâmetro project_id não fornecido")
        return jsonify({'error': 'ID do projeto é obrigatório'}), 400
    
    # Limpar project_id (remover parte decimal se existir)
    cleaned_project_id = str(project_id).strip().split('.')[0]
    
    # Buscar notas do projeto em ordem de prioridade
    notes = Note.query.filter_by(project_id=cleaned_project_id) \
                     .order_by(Note.priority.desc(), Note.created_at.desc()) \
                     .all()
    
    # Organizar por categoria
    report_data = {
        'project_id': cleaned_project_id,
        'decisions': [],
        'risks': [],
        'impedimentos': [],
        'atualizacoes': [],
        'geral': []
    }
    
    category_mapping = {
        'decision': 'decisions',
        'risk': 'risks',
        'impediment': 'impedimentos',
        'status_update': 'atualizacoes',
        'general': 'geral'
    }
    
    for note in notes:
        category_key = category_mapping.get(note.category, 'geral')
        report_data[category_key].append(note.to_dict())
    
    logger.info(f"[API Notes] Preview de relatório gerado para project_id: {cleaned_project_id}")
    return jsonify(report_data)

@backlog_bp.route('/api/notes/report/generate', methods=['POST'])
def generate_report():
    """Gera um relatório baseado nas notas do projeto."""
    logger.info("[API Notes] Recebendo requisição POST para /api/notes/report/generate")
    data = request.get_json()
    
    if not data or not data.get('project_id'):
        logger.error("[API Notes] Parâmetro project_id não fornecido no JSON")
        return jsonify({'error': 'ID do projeto é obrigatório'}), 400
    
    # Limpar project_id (remover parte decimal se existir)
    cleaned_project_id = str(data['project_id']).strip().split('.')[0]
    
    # Obter notas selecionadas para relatório
    note_ids = data.get('note_ids', [])
    
    if not note_ids:
        logger.error("[API Notes] Nenhuma nota selecionada para o relatório")
        return jsonify({'error': 'Selecione pelo menos uma nota para o relatório'}), 400
    
    try:
        # Marcar notas como reportadas
        notes = Note.query.filter(Note.id.in_(note_ids)).all()
        for note in notes:
            note.report_status = 'reported'
            note.report_date = db.func.now()
        
        db.session.commit()
        
        # Estrutura básica do relatório
        report = {
            'project_id': cleaned_project_id,
            'generated_at': db.func.now().isoformat(),
            'notes': [note.to_dict() for note in notes]
        }
        
        logger.info(f"[API Notes] Relatório gerado para project_id: {cleaned_project_id} com {len(notes)} notas")
        return jsonify(report), 201
    except Exception as e:
        db.session.rollback()
        logger.exception(f"[API Notes] Erro ao gerar relatório: {str(e)}")
        return jsonify({'error': f'Erro ao gerar relatório: {str(e)}'}), 500 