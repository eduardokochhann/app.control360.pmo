from flask import request, jsonify, current_app, abort
from app import db
from app.models import Note, Tag, Backlog
from . import backlog_bp
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# API para Notas de Backlog
@backlog_bp.route('/api/backlogs/<int:backlog_id>/notes', methods=['GET'])
def get_backlog_notes(backlog_id):
    """Retorna todas as notas de um backlog específico."""
    logger.info(f"[API Notes] Recebendo requisição GET para /api/backlogs/{backlog_id}/notes")
    
    # Verifica se o backlog existe
    backlog = Backlog.query.get_or_404(backlog_id)
    
    # Busca notas do backlog ordenadas por data do evento (quando disponível) e data de criação
    notes = Note.query.filter_by(backlog_id=backlog_id).order_by(
        Note.event_date.desc().nulls_last(),  # Ordena por data do evento (mais recente primeiro)
        Note.created_at.desc()  # Fallback para data de criação
    ).all()
    logger.info(f"[API Notes] Retornando {len(notes)} notas para backlog {backlog_id} ordenadas por data do evento")
    
    return jsonify([note.to_dict() for note in notes])

# API para Notas
@backlog_bp.route('/api/notes', methods=['GET']) # URL final: /backlog/api/notes
def get_notes():
    """Retorna todas as notas de um projeto ou tarefa específica."""
    logger.info("[API Notes] Recebendo requisição GET para /api/notes")
    project_id = request.args.get('project_id')
    task_id = request.args.get('task_id', type=int)
    backlog_id = request.args.get('backlog_id', type=int)
    
    query = Note.query
    
    if project_id:
        # Garante que o project_id seja uma string limpa (apenas números)
        project_id = str(project_id).strip().split('.')[0]
        logger.info(f"[API Notes] Filtrando por project_id: {project_id}")
        query = query.filter_by(project_id=project_id)
    if task_id:
        logger.info(f"[API Notes] Filtrando por task_id: {task_id}")
        query = query.filter_by(task_id=task_id)
    if backlog_id:
        logger.info(f"[API Notes] Filtrando por backlog_id: {backlog_id}")
        query = query.filter_by(backlog_id=backlog_id)
    
    notes = query.order_by(
        Note.event_date.desc().nulls_last(),  # Ordena por data do evento (mais recente primeiro)
        Note.created_at.desc()  # Fallback para data de criação
    ).all()
    logger.info(f"[API Notes] Retornando {len(notes)} notas ordenadas por data do evento")
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
    
    # Pode receber backlog_id diretamente ou project_id para buscar o backlog
    backlog_id = data.get('backlog_id')
    project_id = data.get('project_id')
    
    if not backlog_id and not project_id:
        logger.error("[API Notes] ID do backlog ou projeto não fornecido")
        return jsonify({'error': 'ID do backlog ou projeto é obrigatório'}), 400
    
    if backlog_id:
        # Verifica se o backlog existe
        backlog = Backlog.query.get(backlog_id)
        if not backlog:
            logger.error(f"[API Notes] Backlog não encontrado para backlog_id: {backlog_id}")
            return jsonify({'error': f'Backlog não encontrado para ID {backlog_id}'}), 404
        cleaned_project_id = backlog.project_id
    else:
        # Limpar project_id (remover parte decimal se existir)
        cleaned_project_id = str(project_id).strip().split('.')[0]
        
        # Busca o backlog pelo project_id
        backlog = Backlog.query.filter_by(project_id=cleaned_project_id).first()
        if not backlog:
            logger.error(f"[API Notes] Backlog não encontrado para project_id: {cleaned_project_id}")
            return jsonify({'error': f'Backlog não encontrado para o projeto ID {cleaned_project_id}'}), 404
        backlog_id = backlog.id
    
    # Processa as tags
    tags = []
    if data.get('tags'):
        tag_names = data['tags']
        if isinstance(tag_names, str):
            # Se for uma string, divide por vírgula
            tag_names = [tag.strip() for tag in tag_names.split(',') if tag.strip()]
        
        for tag_name in tag_names:
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
    
    # Processar event_date
    event_date_str = data.get('event_date')
    parsed_event_date = None
    if event_date_str:
        try:
            parsed_event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
        except ValueError:
            logger.warning(f"[API Notes] Formato inválido para event_date: {event_date_str}. Será ignorado.")

    note = Note(
        content=data['content'],
        project_id=cleaned_project_id,  # ID do projeto limpo
        backlog_id=backlog_id,  # ID do backlog
        task_id=data.get('task_id'),
        category=data.get('category', 'general'),
        priority=data.get('priority', 'medium'),
        note_type=note_type,
        event_date=parsed_event_date,
        include_in_status_report=data.get('include_in_report', data.get('include_in_status_report', True)),
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
    if 'include_in_status_report' in data:
        note.include_in_status_report = data['include_in_status_report']
    if 'include_in_report' in data:
        note.include_in_status_report = data['include_in_report']
    
    # Atualizar event_date
    if 'event_date' in data:
        event_date_str = data['event_date']
        if event_date_str:
            try:
                note.event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
            except ValueError:
                logger.warning(f"[API Notes] Formato inválido para event_date ao atualizar: {event_date_str}. Será ignorado.")
        else:
            note.event_date = None # Permite limpar a event_date enviando null ou string vazia

    # Atualiza tags
    if 'tags' in data:
        note.tags.clear()
        tag_names = data['tags']
        if isinstance(tag_names, str):
            # Se for uma string, divide por vírgula
            tag_names = [tag.strip() for tag in tag_names.split(',') if tag.strip()]
        
        for tag_name in tag_names:
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

# Rotas específicas para notas de tarefas
@backlog_bp.route('/api/tasks/<int:task_id>/notes', methods=['GET'])
def get_task_notes(task_id):
    """Retorna todas as notas de uma tarefa específica."""
    logger.info(f"[API Notes] Recebendo requisição GET para /api/tasks/{task_id}/notes")
    
    # Busca notas da tarefa ordenadas por data do evento
    notes = Note.query.filter_by(task_id=task_id).order_by(
        Note.event_date.desc().nulls_last(),  # Ordena por data do evento (mais recente primeiro)
        Note.created_at.desc()  # Fallback para data de criação
    ).all()
    logger.info(f"[API Notes] Retornando {len(notes)} notas para tarefa {task_id} ordenadas por data do evento")
    
    return jsonify([note.to_dict() for note in notes])

@backlog_bp.route('/api/tasks/<int:task_id>/notes', methods=['POST'])
def create_task_note(task_id):
    """Cria uma nova nota para uma tarefa específica."""
    logger.info(f"[API Notes] Recebendo requisição POST para /api/tasks/{task_id}/notes")
    
    # Importa Task aqui para evitar importação circular
    from app.models import Task
    
    # Verifica se a tarefa existe
    task = Task.query.get_or_404(task_id)
    
    data = request.get_json()
    
    if not data:
        logger.error("[API Notes] Nenhum dado JSON recebido")
        return jsonify({'error': 'Dados JSON não fornecidos'}), 400
    
    if not data.get('content'):
        logger.error("[API Notes] Conteúdo da nota não fornecido")
        return jsonify({'error': 'Conteúdo da nota é obrigatório'}), 400
    
    # Busca o backlog da tarefa
    backlog = Backlog.query.get(task.backlog_id)
    if not backlog:
        logger.error(f"[API Notes] Backlog não encontrado para a tarefa {task_id}")
        return jsonify({'error': f'Backlog não encontrado para a tarefa {task_id}'}), 404
    
    # Processa as tags
    tags = []
    if data.get('tags'):
        tag_names = data['tags']
        if isinstance(tag_names, str):
            # Se for uma string, divide por vírgula
            tag_names = [tag.strip() for tag in tag_names.split(',') if tag.strip()]
        
        for tag_name in tag_names:
            if not tag_name or not tag_name.strip():
                continue
                
            tag = Tag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                db.session.add(tag)
            tags.append(tag)
    
    # Processar event_date
    event_date_str = data.get('event_date')
    parsed_event_date = None
    if event_date_str:
        try:
            parsed_event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
        except ValueError:
            logger.warning(f"[API Notes] Formato inválido para event_date: {event_date_str}. Será ignorado.")

    note = Note(
        content=data['content'],
        project_id=backlog.project_id,
        backlog_id=backlog.id,
        task_id=task_id,
        category=data.get('category', 'general'),
        priority=data.get('priority', 'medium'),
        note_type='task',
        event_date=parsed_event_date,
        include_in_status_report=data.get('include_in_report', data.get('include_in_status_report', True)),
        tags=tags
    )
    
    try:
        db.session.add(note)
        db.session.commit()
        logger.info(f"[API Notes] Nota de tarefa criada com sucesso ID: {note.id}")
        return jsonify(note.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        logger.exception(f"[API Notes] Erro ao criar nota de tarefa: {str(e)}")
        return jsonify({'error': f'Erro ao salvar nota: {str(e)}'}), 500

@backlog_bp.route('/api/notes/report/preview', methods=['GET'])
def preview_report():
    """Gera uma prévia do relatório de notas."""
    logger.info("[API Notes] Recebendo requisição GET para /api/notes/report/preview")
    
    project_id = request.args.get('project_id')
    if not project_id:
        return jsonify({'error': 'ID do projeto é obrigatório'}), 400
    
    # Limpar project_id
    cleaned_project_id = str(project_id).strip().split('.')[0]
    
    # Buscar notas do projeto que devem ser incluídas no relatório, ordenadas por data do evento
    notes = Note.query.filter_by(
        project_id=cleaned_project_id,
        include_in_status_report=True
    ).order_by(
        Note.event_date.desc().nulls_last(),  # Ordena por data do evento (mais recente primeiro)
        Note.created_at.desc()  # Fallback para data de criação
    ).all()
    
    # Agrupar por categoria
    grouped_notes = {}
    for note in notes:
        category = note.category or 'general'
        if category not in grouped_notes:
            grouped_notes[category] = []
        grouped_notes[category].append(note.to_dict())
    
    logger.info(f"[API Notes] Prévia do relatório gerada para projeto {cleaned_project_id}: {len(notes)} notas")
    return jsonify({
        'project_id': cleaned_project_id,
        'total_notes': len(notes),
        'grouped_notes': grouped_notes
    })

@backlog_bp.route('/api/notes/report/generate', methods=['POST'])
def generate_report():
    """Gera um relatório completo de notas."""
    logger.info("[API Notes] Recebendo requisição POST para /api/notes/report/generate")
    
    data = request.get_json()
    if not data or not data.get('project_id'):
        return jsonify({'error': 'ID do projeto é obrigatório'}), 400
    
    # Limpar project_id
    cleaned_project_id = str(data['project_id']).strip().split('.')[0]
    
    # Filtros opcionais
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    categories = data.get('categories', [])
    
    query = Note.query.filter_by(
        project_id=cleaned_project_id,
        include_in_status_report=True
    )
    
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Note.created_at >= start_date_obj)
        except ValueError:
            return jsonify({'error': 'Formato de start_date inválido. Use YYYY-MM-DD'}), 400
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Note.created_at <= end_date_obj)
        except ValueError:
            return jsonify({'error': 'Formato de end_date inválido. Use YYYY-MM-DD'}), 400
    
    if categories:
        query = query.filter(Note.category.in_(categories))
    
    notes = query.order_by(
        Note.event_date.desc().nulls_last(),  # Ordena por data do evento (mais recente primeiro)
        Note.created_at.desc()  # Fallback para data de criação
    ).all()
    
    # Gerar relatório estruturado
    report = {
        'project_id': cleaned_project_id,
        'generated_at': datetime.now().isoformat(),
        'filters': {
            'start_date': start_date,
            'end_date': end_date,
            'categories': categories
        },
        'total_notes': len(notes),
        'notes': [note.to_dict() for note in notes]
    }
    
    logger.info(f"[API Notes] Relatório gerado para projeto {cleaned_project_id}: {len(notes)} notas")
    return jsonify(report) 