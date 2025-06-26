"""
Serviços administrativos para gerenciamento de configurações do sistema
"""

from flask import current_app
from .. import db
from ..models import ComplexityCriteria, ComplexityCriteriaOption, ComplexityThreshold, ComplexityCategory
from datetime import datetime
import json


class AdminService:
    """Serviço principal para operações administrativas"""
    
    @staticmethod
    def get_system_stats():
        """Retorna estatísticas do sistema"""
        try:
            stats = {
                'complexity': {
                    'criteria_count': ComplexityCriteria.query.filter_by(is_active=True).count(),
                    'options_count': ComplexityCriteriaOption.query.filter_by(is_active=True).count(),
                    'thresholds_count': ComplexityThreshold.query.count(),
                    'last_modified': datetime.utcnow()
                },
                'system': {
                    'version': '1.0.0',
                    'modules': ['admin', 'backlog', 'macro', 'micro', 'gerencial', 'sprints'],
                    'uptime': datetime.utcnow()
                }
            }
            return stats
            
        except Exception as e:
            current_app.logger.error(f"Erro ao obter estatísticas do sistema: {e}")
            return None
    
    @staticmethod
    def validate_threshold_data(threshold_data):
        """Valida dados de threshold antes de salvar"""
        errors = []
        
        for i, threshold in enumerate(threshold_data):
            if not isinstance(threshold.get('min_score'), int) or threshold['min_score'] < 0:
                errors.append(f"Threshold {i+1}: Score mínimo deve ser um número inteiro positivo")
            
            max_score = threshold.get('max_score')
            if max_score is not None and (not isinstance(max_score, int) or max_score <= threshold['min_score']):
                errors.append(f"Threshold {i+1}: Score máximo deve ser maior que o mínimo")
        
        # Verifica sobreposições
        sorted_thresholds = sorted(threshold_data, key=lambda x: x['min_score'])
        for i in range(len(sorted_thresholds) - 1):
            current = sorted_thresholds[i]
            next_threshold = sorted_thresholds[i + 1]
            
            if current.get('max_score') and current['max_score'] >= next_threshold['min_score']:
                errors.append(f"Sobreposição entre thresholds: {current['category']} e {next_threshold['category']}")
        
        return errors
    
    @staticmethod
    def backup_complexity_config():
        """Cria backup das configurações de complexidade"""
        try:
            criteria = ComplexityCriteria.query.all()
            options = ComplexityCriteriaOption.query.all()
            thresholds = ComplexityThreshold.query.all()
            
            backup = {
                'timestamp': datetime.utcnow().isoformat(),
                'version': '1.0',
                'complexity_config': {
                    'criteria': [
                        {
                            'id': c.id,
                            'name': c.name,
                            'description': c.description,
                            'is_active': c.is_active,
                            'order': c.criteria_order
                        } for c in criteria
                    ],
                    'options': [
                        {
                            'id': o.id,
                            'criteria_id': o.criteria_id,
                            'label': o.option_label or o.option_name,
                            'description': o.description,
                            'points': o.points,
                            'order': o.option_order,
                            'is_active': o.is_active
                        } for o in options
                    ],
                    'thresholds': [
                        {
                            'id': t.id,
                            'category': t.category.name,
                            'min_score': t.min_score,
                            'max_score': t.max_score
                        } for t in thresholds
                    ]
                }
            }
            
            return backup
            
        except Exception as e:
            current_app.logger.error(f"Erro ao criar backup: {e}")
            return None
    
    @staticmethod
    def restore_complexity_config(backup_data):
        """Restaura configurações de complexidade a partir do backup"""
        try:
            if not backup_data or 'complexity_config' not in backup_data:
                return False, "Dados de backup inválidos"
            
            config = backup_data['complexity_config']
            
            # Restaura thresholds
            for threshold_data in config.get('thresholds', []):
                threshold = ComplexityThreshold.query.get(threshold_data['id'])
                if threshold:
                    threshold.min_score = threshold_data['min_score']
                    threshold.max_score = threshold_data.get('max_score')
            
            # Restaura opções
            for option_data in config.get('options', []):
                option = ComplexityCriteriaOption.query.get(option_data['id'])
                if option:
                    option.option_label = option_data['label']
                    option.option_name = option_data['label']
                    option.description = option_data.get('description')
                    option.points = option_data['points']
                    option.option_order = option_data['order']
                    option.is_active = option_data['is_active']
            
            # Restaura critérios
            for criteria_data in config.get('criteria', []):
                criterion = ComplexityCriteria.query.get(criteria_data['id'])
                if criterion:
                    criterion.name = criteria_data['name']
                    criterion.description = criteria_data.get('description')
                    criterion.criteria_order = criteria_data['order']
                    criterion.is_active = criteria_data['is_active']
            
            db.session.commit()
            return True, "Configurações restauradas com sucesso"
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao restaurar backup: {e}")
            return False, f"Erro ao restaurar: {str(e)}"


class ComplexityAdminService:
    """Serviço específico para administração de complexidade"""
    
    @staticmethod
    def get_complexity_overview():
        """Retorna visão geral das configurações de complexidade"""
        try:
            criteria = ComplexityCriteria.query.filter_by(is_active=True).order_by(ComplexityCriteria.criteria_order).all()
            thresholds = ComplexityThreshold.query.order_by(ComplexityThreshold.min_score).all()
            
            overview = {
                'criteria_count': len(criteria),
                'total_combinations': 1,
                'score_range': {
                    'min': 0,
                    'max': 0
                },
                'categories': []
            }
            
            # Calcula combinações possíveis e faixa de pontuação
            for criterion in criteria:
                options = ComplexityCriteriaOption.query.filter_by(criteria_id=criterion.id, is_active=True).all()
                if options:
                    overview['total_combinations'] *= len(options)
                    overview['score_range']['max'] += max(opt.points for opt in options)
            
            # Informações das categorias
            for threshold in thresholds:
                overview['categories'].append({
                    'name': threshold.category.value,
                    'range': f"{threshold.min_score}-{threshold.max_score or '∞'}",
                    'min_score': threshold.min_score,
                    'max_score': threshold.max_score
                })
            
            return overview
            
        except Exception as e:
            current_app.logger.error(f"Erro ao obter overview de complexidade: {e}")
            return None
    
    @staticmethod
    def simulate_scoring(test_selections):
        """Simula pontuação baseada em seleções de teste"""
        try:
            total_score = 0
            details = []
            
            for criteria_id, option_id in test_selections.items():
                option = ComplexityCriteriaOption.query.get(option_id)
                if option:
                    total_score += option.points
                    details.append({
                        'criteria_id': criteria_id,
                        'option_id': option_id,
                        'points': option.points,
                        'label': option.option_label or option.option_name
                    })
            
            # Determina categoria
            category = 'ALTA'
            thresholds = ComplexityThreshold.query.order_by(ComplexityThreshold.min_score).all()
            for threshold in thresholds:
                if total_score >= threshold.min_score and (threshold.max_score is None or total_score <= threshold.max_score):
                    category = threshold.category.value
                    break
            
            return {
                'total_score': total_score,
                'category': category,
                'details': details
            }
            
        except Exception as e:
            current_app.logger.error(f"Erro na simulação de pontuação: {e}")
            return None 