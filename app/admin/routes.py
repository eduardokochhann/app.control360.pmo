from flask import render_template, jsonify, request, current_app, redirect, url_for, flash
from . import admin_bp
from .. import db
from ..models import ComplexityCriteria, ComplexityCriteriaOption, ComplexityThreshold, ComplexityCategory
from datetime import datetime

@admin_bp.route('/')
def dashboard():
    """Dashboard principal da central administrativa"""
    try:
        # Estatísticas básicas do sistema
        stats = {
            'complexity_criteria': ComplexityCriteria.query.filter_by(is_active=True).count(),
            'complexity_options': ComplexityCriteriaOption.query.filter_by(is_active=True).count(),
            'complexity_thresholds': ComplexityThreshold.query.count(),
            'last_update': datetime.utcnow()
        }
        
        return render_template('admin/dashboard.html', stats=stats)
        
    except Exception as e:
        current_app.logger.error(f"Erro no dashboard administrativo: {str(e)}", exc_info=True)
        return render_template('admin/erro.html', erro="Erro ao carregar dashboard"), 500

@admin_bp.route('/complexity')
def complexity_management():
    """Página de gerenciamento de parâmetros de complexidade"""
    try:
        # Carrega critérios com suas opções
        criteria = ComplexityCriteria.query.filter_by(is_active=True).order_by(ComplexityCriteria.criteria_order).all()
        
        # Carrega thresholds
        thresholds = ComplexityThreshold.query.order_by(ComplexityThreshold.min_score).all()
        
        return render_template('admin/complexity_management.html', 
                             criteria=criteria, 
                             thresholds=thresholds)
        
    except Exception as e:
        current_app.logger.error(f"Erro ao carregar gerenciamento de complexidade: {str(e)}", exc_info=True)
        return render_template('admin/erro.html', erro="Erro ao carregar parâmetros de complexidade"), 500

# =====================================================
# APIs para Gerenciamento de Complexidade
# =====================================================

@admin_bp.route('/api/complexity/criteria', methods=['GET'])
def get_criteria_admin():
    """Retorna todos os critérios para administração"""
    try:
        criteria = ComplexityCriteria.query.order_by(ComplexityCriteria.criteria_order).all()
        
        result = []
        for criterion in criteria:
            options = ComplexityCriteriaOption.query.filter_by(criteria_id=criterion.id).order_by(ComplexityCriteriaOption.option_order).all()
            
            criterion_data = {
                'id': criterion.id,
                'name': criterion.name,
                'description': criterion.description,
                'is_active': criterion.is_active,
                'order': criterion.criteria_order,
                'options': [
                    {
                        'id': opt.id,
                        'label': opt.option_label or opt.option_name,
                        'description': opt.description,
                        'points': opt.points,
                        'order': opt.option_order,
                        'is_active': opt.is_active
                    } for opt in options
                ]
            }
            result.append(criterion_data)
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Erro ao buscar critérios admin: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erro interno do servidor'}), 500

@admin_bp.route('/api/complexity/thresholds', methods=['GET'])
def get_thresholds_admin():
    """Retorna thresholds para administração"""
    try:
        thresholds = ComplexityThreshold.query.order_by(ComplexityThreshold.min_score).all()
        
        result = []
        for threshold in thresholds:
            result.append({
                'id': threshold.id,
                'category': threshold.category.name,
                'category_label': threshold.category.value,
                'min_score': threshold.min_score,
                'max_score': threshold.max_score
            })
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Erro ao buscar thresholds admin: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erro interno do servidor'}), 500

@admin_bp.route('/api/complexity/thresholds', methods=['PUT'])
def update_thresholds():
    """Atualiza thresholds de complexidade"""
    try:
        data = request.get_json()
        
        if not data or 'thresholds' not in data:
            return jsonify({'error': 'Dados de thresholds são obrigatórios'}), 400
        
        # Atualiza cada threshold
        for threshold_data in data['thresholds']:
            threshold_id = threshold_data.get('id')
            threshold = ComplexityThreshold.query.get(threshold_id)
            
            if threshold:
                threshold.min_score = threshold_data['min_score']
                threshold.max_score = threshold_data.get('max_score')
                
        db.session.commit()
        
        current_app.logger.info(f"Thresholds de complexidade atualizados via admin")
        return jsonify({'message': 'Thresholds atualizados com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao atualizar thresholds: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erro ao atualizar thresholds'}), 500

@admin_bp.route('/api/complexity/criteria/option', methods=['PUT'])
def update_criteria_option():
    """Atualiza uma opção de critério"""
    try:
        data = request.get_json()
        
        if not data or 'id' not in data:
            return jsonify({'error': 'ID da opção é obrigatório'}), 400
        
        option = ComplexityCriteriaOption.query.get(data['id'])
        if not option:
            return jsonify({'error': 'Opção não encontrada'}), 404
        
        # Atualiza campos permitidos
        if 'label' in data:
            option.option_label = data['label']
            option.option_name = data['label']  # Mantém compatibilidade
        
        if 'description' in data:
            option.description = data['description']
            
        if 'points' in data:
            option.points = int(data['points'])
            
        if 'order' in data:
            option.option_order = int(data['order'])
            
        if 'is_active' in data:
            option.is_active = bool(data['is_active'])
        
        db.session.commit()
        
        current_app.logger.info(f"Opção {option.id} atualizada via admin")
        return jsonify({'message': 'Opção atualizada com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao atualizar opção: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erro ao atualizar opção'}), 500

@admin_bp.route('/api/complexity/criteria', methods=['PUT'])
def update_criteria():
    """Atualiza um critério"""
    try:
        data = request.get_json()
        
        if not data or 'id' not in data:
            return jsonify({'error': 'ID do critério é obrigatório'}), 400
        
        criterion = ComplexityCriteria.query.get(data['id'])
        if not criterion:
            return jsonify({'error': 'Critério não encontrado'}), 404
        
        # Atualiza campos permitidos
        if 'name' in data:
            criterion.name = data['name']
            
        if 'description' in data:
            criterion.description = data['description']
            
        if 'order' in data:
            criterion.criteria_order = int(data['order'])
            
        if 'is_active' in data:
            criterion.is_active = bool(data['is_active'])
        
        db.session.commit()
        
        current_app.logger.info(f"Critério {criterion.id} atualizado via admin")
        return jsonify({'message': 'Critério atualizado com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao atualizar critério: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erro ao atualizar critério'}), 500

@admin_bp.route('/api/system/backup', methods=['POST'])
def create_backup():
    """Cria backup das configurações do sistema"""
    try:
        from datetime import datetime
        import json
        
        # Coleta dados atuais
        criteria = ComplexityCriteria.query.all()
        options = ComplexityCriteriaOption.query.all()
        thresholds = ComplexityThreshold.query.all()
        
        backup_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'criteria': [
                {
                    'id': c.id, 'name': c.name, 'description': c.description,
                    'is_active': c.is_active, 'order': c.criteria_order
                } for c in criteria
            ],
            'options': [
                {
                    'id': o.id, 'criteria_id': o.criteria_id, 'label': o.option_label or o.option_name,
                    'description': o.description, 'points': o.points, 'order': o.option_order,
                    'is_active': o.is_active
                } for o in options
            ],
            'thresholds': [
                {
                    'id': t.id, 'category': t.category.name, 
                    'min_score': t.min_score, 'max_score': t.max_score
                } for t in thresholds
            ]
        }
        
        # Salva backup (pode ser expandido para salvar em arquivo)
        current_app.logger.info(f"Backup do sistema criado: {len(criteria)} critérios, {len(options)} opções, {len(thresholds)} thresholds")
        
        return jsonify({
            'message': 'Backup criado com sucesso',
            'backup_data': backup_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Erro ao criar backup: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erro ao criar backup'}), 500 