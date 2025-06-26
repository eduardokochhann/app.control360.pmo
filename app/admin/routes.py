from flask import render_template, jsonify, request, current_app, redirect, url_for, flash
from . import admin_bp
from .. import db
from ..models import ComplexityCriteria, ComplexityCriteriaOption, ComplexityThreshold, ComplexityCategory
from datetime import datetime
from .services import AdminService
from pathlib import Path

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

@admin_bp.route('/data-management')
def data_management():
    """Página de gerenciamento de dados CSV"""
    try:
        # Estatísticas dos dados atuais
        stats = AdminService.get_data_statistics()
        return render_template('admin/data_management.html', stats=stats)
    except Exception as e:
        current_app.logger.error(f"Erro no gerenciamento de dados: {str(e)}")
        return render_template('admin/erro.html', erro=str(e))

@admin_bp.route('/api/data/upload', methods=['POST'])
def upload_csv():
    """Upload e processamento de arquivo CSV"""
    try:
        current_app.logger.info("🚀 Iniciando upload CSV...")
        
        if 'file' not in request.files:
            current_app.logger.warning("❌ Nenhum arquivo na requisição")
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
        file = request.files['file']
        current_app.logger.info(f"📁 Arquivo recebido: {file.filename}, tamanho: {file.content_length}")
        
        if file.filename == '':
            current_app.logger.warning("❌ Nome do arquivo vazio")
            return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
        
        if not file.filename.lower().endswith('.csv'):
            current_app.logger.warning(f"❌ Formato inválido: {file.filename}")
            return jsonify({'error': 'Formato de arquivo inválido. Apenas CSV aceito.'}), 400
        
        # Salva o arquivo temporariamente para processamento
        current_app.logger.info("🔄 Salvando arquivo temporário...")
        import tempfile
        import os
        
        # Cria arquivo temporário
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as temp_file:
            temp_path = temp_file.name
            file.save(temp_file)
        
        current_app.logger.info(f"📁 Arquivo salvo temporariamente: {temp_path}")
        
        try:
            # Processa o arquivo
            current_app.logger.info("🔄 Iniciando processamento...")
            result = AdminService.process_csv_upload(temp_path)
        finally:
            # Remove arquivo temporário
            try:
                os.unlink(temp_path)
                current_app.logger.info("🗑️ Arquivo temporário removido")
            except:
                pass
        
        # Log detalhado do resultado
        current_app.logger.info(f"📋 Resultado do processamento: {result}")
        
        if result.get('success'):
            stats = result.get('stats', {})
            records_count = stats.get('records_count', 0)
            current_app.logger.info(f"✅ CSV processado: {records_count} registros")
            return jsonify(result), 200
        else:
            current_app.logger.error(f"❌ Erro no processamento: {result.get('error', 'Erro desconhecido')}")
            return jsonify(result), 400
        
    except Exception as e:
        current_app.logger.error(f"💥 Erro crítico no upload CSV: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@admin_bp.route('/api/data/preview')
def preview_data():
    """Preview dos dados atuais"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        search = request.args.get('search', '')
        
        result = AdminService.get_data_preview(page, per_page, search)
        return jsonify(result)
    
    except Exception as e:
        current_app.logger.error(f"Erro no preview de dados: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/data/record/<int:record_id>', methods=['GET', 'PUT', 'DELETE'])
def manage_record(record_id):
    """Gerencia um registro específico"""
    try:
        if request.method == 'GET':
            record = AdminService.get_record_by_id(record_id)
            return jsonify(record)
        
        elif request.method == 'PUT':
            data = request.get_json()
            updated_record = AdminService.update_record(record_id, data)
            current_app.logger.info(f"Registro {record_id} atualizado via admin")
            return jsonify(updated_record)
        
        elif request.method == 'DELETE':
            AdminService.delete_record(record_id)
            current_app.logger.info(f"Registro {record_id} deletado via admin")
            return jsonify({'success': True})
    
    except Exception as e:
        current_app.logger.error(f"Erro ao gerenciar registro {record_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/data/backup', methods=['POST'])
def create_data_backup():
    """Cria backup dos dados atuais"""
    try:
        backup_info = AdminService.create_data_backup()
        current_app.logger.info(f"Backup criado: {backup_info['filename']}")
        return jsonify(backup_info)
    
    except Exception as e:
        current_app.logger.error(f"Erro ao criar backup: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/data/validate', methods=['POST'])
def validate_data():
    """Valida dados antes de salvar"""
    try:
        data = request.get_json()
        validation_result = AdminService.validate_data_integrity(data)
        return jsonify(validation_result)
    
    except Exception as e:
        current_app.logger.error(f"Erro na validação: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/data/apply-changes', methods=['POST'])
def apply_changes():
    """Aplica todas as alterações pendentes"""
    try:
        data = request.get_json()
        result = AdminService.apply_data_changes(data)
        current_app.logger.info(f"Alterações aplicadas: {result['affected_records']} registros")
        return jsonify(result)
    
    except Exception as e:
        current_app.logger.error(f"Erro ao aplicar alterações: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/data/apply-upload', methods=['POST'])
def apply_upload():
    """Aplica arquivo temporário como dados principais"""
    try:
        temp_path = Path("data/dadosr_temp.csv")
        main_path = Path("data/dadosr.csv")
        
        if not temp_path.exists():
            return jsonify({'error': 'Arquivo temporário não encontrado'}), 400
        
        # Cria backup do arquivo atual
        backup_result = AdminService.create_data_backup()
        
        # Move o arquivo temporário para o principal
        import shutil
        shutil.move(str(temp_path), str(main_path))
        
        current_app.logger.info("Arquivo CSV atualizado via upload")
        
        return jsonify({
            'success': True,
            'message': 'Dados atualizados com sucesso!',
            'backup_created': backup_result.get('filename', '')
        })
    
    except Exception as e:
        current_app.logger.error(f"Erro ao aplicar upload: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/data/test')
def test_data_loading():
    """Endpoint de teste para verificar carregamento de dados"""
    try:
        # Testa se consegue carregar estatísticas
        stats = AdminService.get_data_statistics()
        
        # Testa se consegue carregar preview
        preview = AdminService.get_data_preview(1, 5)
        
        return jsonify({
            'stats_test': 'OK' if not stats.get('error') else f"ERRO: {stats.get('error')}",
            'preview_test': 'OK' if not preview.get('error') else f"ERRO: {preview.get('error')}",
            'total_records': stats.get('total_records', 0),
            'preview_records': len(preview.get('data', [])),
            'columns': len(stats.get('columns', [])),
            'details': {
                'stats': stats,
                'preview_sample': preview.get('data', [])[:2] if preview.get('data') else []
            }
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'stats_test': 'ERRO',
            'preview_test': 'ERRO'
        }), 500 