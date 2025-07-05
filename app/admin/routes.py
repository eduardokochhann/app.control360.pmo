from flask import render_template, jsonify, request, current_app, redirect, url_for, flash
from . import admin_bp
from .. import db
from ..models import ComplexityCriteria, ComplexityCriteriaOption, ComplexityThreshold, ComplexityCategory, SpecialistConfiguration
from datetime import datetime
from .services import AdminService
from pathlib import Path
import json
import pytz

# Define o fuso horário brasileiro
br_timezone = pytz.timezone('America/Sao_Paulo')

@admin_bp.route('/')
def dashboard():
    """Dashboard principal da central administrativa"""
    try:
        # Estatísticas básicas do sistema
        stats = {
            'complexity_criteria': ComplexityCriteria.query.filter_by(is_active=True).count(),
            'complexity_options': ComplexityCriteriaOption.query.filter_by(is_active=True).count(),
            'complexity_thresholds': ComplexityThreshold.query.count(),
            'specialist_configs': SpecialistConfiguration.query.filter_by(is_active=True).count(),
            'last_update': datetime.now(br_timezone)
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
            'timestamp': datetime.now(br_timezone).isoformat(),
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

# --- ROTAS PARA CONFIGURAÇÕES DE ESPECIALISTAS ---

@admin_bp.route('/specialist-configuration')
def specialist_configuration():
    """Interface para gerenciar configurações de especialistas"""
    try:
        # Busca todas as configurações existentes
        configurations = SpecialistConfiguration.query.filter_by(is_active=True).all()
        
        # Busca especialistas únicos do sistema (da tabela Task)
        from ..models import Task
        specialists_in_system = db.session.query(Task.specialist_name).filter(
            Task.specialist_name.isnot(None), 
            Task.specialist_name != ''
        ).distinct().all()
        
        specialist_names = [s[0] for s in specialists_in_system if s[0]]
        
        return render_template('admin/specialist_configuration.html', 
                             configurations=configurations,
                             available_specialists=specialist_names)
        
    except Exception as e:
        current_app.logger.error(f"Erro ao carregar configurações: {str(e)}", exc_info=True)
        return render_template('admin/erro.html', erro="Erro ao carregar configurações"), 500

@admin_bp.route('/api/specialist-configuration', methods=['GET'])
def get_specialist_configurations():
    """API para obter configurações de especialistas"""
    try:
        configurations = SpecialistConfiguration.query.filter_by(is_active=True).all()
        
        return jsonify({
            'success': True,
            'configurations': [config.to_dict() for config in configurations]
        })
        
    except Exception as e:
        current_app.logger.error(f"Erro ao obter configurações: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/specialist-configuration/<int:config_id>', methods=['GET'])
def get_specialist_configuration(config_id):
    """API para obter configuração específica"""
    try:
        config = SpecialistConfiguration.query.get_or_404(config_id)
        
        return jsonify({
            'success': True,
            'configuration': config.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Erro ao obter configuração: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/specialist-configuration', methods=['POST'])
def create_specialist_configuration():
    """API para criar nova configuração de especialista"""
    try:
        data = request.get_json()
        
        # Valida dados obrigatórios
        if not data.get('specialist_name'):
            return jsonify({'success': False, 'error': 'Nome do especialista é obrigatório'}), 400
        
        # Verifica se já existe
        existing = SpecialistConfiguration.query.filter_by(
            specialist_name=data['specialist_name']
        ).first()
        
        if existing:
            return jsonify({'success': False, 'error': 'Especialista já possui configuração'}), 400
        
        # Cria nova configuração
        config = SpecialistConfiguration(
            specialist_name=data['specialist_name'],
            daily_work_hours=data.get('daily_work_hours', 8.0),
            weekly_work_days=data.get('weekly_work_days', 5),
            consider_holidays=data.get('consider_holidays', True),
            buffer_percentage=data.get('buffer_percentage', 10.0),
            timezone=data.get('timezone', 'America/Sao_Paulo')
        )
        
        # Configura dias úteis se fornecido
        if 'work_days_config' in data:
            config.set_work_days_config(data['work_days_config'])
        
        # Configura feriados personalizados se fornecido
        if 'custom_holidays' in data:
            config.set_custom_holidays(data['custom_holidays'])
        
        db.session.add(config)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Configuração criada com sucesso',
            'configuration': config.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao criar configuração: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/specialist-configuration/<int:config_id>', methods=['PUT'])
def update_specialist_configuration(config_id):
    """API para atualizar configuração de especialista"""
    try:
        config = SpecialistConfiguration.query.get_or_404(config_id)
        data = request.get_json()
        
        # Atualiza campos
        if 'daily_work_hours' in data:
            config.daily_work_hours = float(data['daily_work_hours'])
        
        if 'weekly_work_days' in data:
            config.weekly_work_days = int(data['weekly_work_days'])
        
        if 'consider_holidays' in data:
            config.consider_holidays = bool(data['consider_holidays'])
        
        if 'buffer_percentage' in data:
            config.buffer_percentage = float(data['buffer_percentage'])
        
        if 'timezone' in data:
            config.timezone = data['timezone']
        
        if 'work_days_config' in data:
            config.set_work_days_config(data['work_days_config'])
        
        if 'custom_holidays' in data:
            config.set_custom_holidays(data['custom_holidays'])
        
        if 'is_active' in data:
            config.is_active = bool(data['is_active'])
        
        config.updated_at = datetime.now(br_timezone)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Configuração atualizada com sucesso',
            'configuration': config.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao atualizar configuração: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/specialist-configuration/<int:config_id>', methods=['DELETE'])
def delete_specialist_configuration(config_id):
    """API para desativar configuração de especialista"""
    try:
        config = SpecialistConfiguration.query.get_or_404(config_id)
        
        # Soft delete - apenas desativa
        config.is_active = False
        config.updated_at = datetime.now(br_timezone)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Configuração desativada com sucesso'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao deletar configuração: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/available-specialists', methods=['GET'])
def get_available_specialists():
    """API para obter lista de especialistas do sistema"""
    try:
        from ..models import Task
        
        # Busca especialistas únicos que não têm configuração ainda
        specialists_in_tasks = db.session.query(Task.specialist_name).filter(
            Task.specialist_name.isnot(None), 
            Task.specialist_name != ''
        ).distinct().all()
        
        configured_specialists = db.session.query(SpecialistConfiguration.specialist_name).filter(
            SpecialistConfiguration.is_active == True
        ).all()
        
        specialist_names = [s[0] for s in specialists_in_tasks if s[0]]
        configured_names = [s[0] for s in configured_specialists]
        
        return jsonify({
            'success': True,
            'all_specialists': specialist_names,
            'configured_specialists': configured_names,
            'unconfigured_specialists': [name for name in specialist_names if name not in configured_names]
        })
        
    except Exception as e:
        current_app.logger.error(f"Erro ao obter especialistas: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

# --- FIM ROTAS ESPECIALISTAS --- 