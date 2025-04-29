from flask import Blueprint, render_template, jsonify
from app.micro import bp
from app.micro.services import MicroService
import logging

# Configurar logging
logger = logging.getLogger(__name__)

# Instanciar serviço
service = MicroService()

@bp.route('/')
def dashboard():
    """Rota principal do dashboard micro"""
    try:
        # Carregar dados
        dados = service.carregar_dados()
        if dados is None or dados.empty:
            logger.warning("Nenhum dado encontrado para o dashboard micro")
            return render_template('micro/dashboard.html', context={})
            
        # Obter métricas
        metricas = service.obter_metricas_micro(dados)
        
        # Preparar contexto
        context = {
            'metricas': metricas
        }
        
        return render_template('micro/dashboard.html', context=context)
        
    except Exception as e:
        logger.error(f"Erro ao carregar dashboard micro: {str(e)}")
        return render_template('micro/dashboard.html', context={})

@bp.route('/api/projetos/especialista/<path:nome_especialista>')
def projetos_por_especialista(nome_especialista):
    """API para obter projetos por especialista"""
    try:
        dados = service.carregar_dados()
        if dados is None or dados.empty:
            return jsonify([])
            
        projetos = service.obter_projetos_por_especialista(dados, nome_especialista)
        return jsonify(projetos)
        
    except Exception as e:
        logger.error(f"Erro ao obter projetos por especialista: {str(e)}")
        return jsonify([])

@bp.route('/api/projetos/account/<path:nome_account>')
def projetos_por_account(nome_account):
    """API para obter projetos por account manager"""
    try:
        dados = service.carregar_dados()
        if dados is None or dados.empty:
            return jsonify([])
            
        projetos = service.obter_projetos_por_account(dados, nome_account)
        return jsonify(projetos)
        
    except Exception as e:
        logger.error(f"Erro ao obter projetos por account: {str(e)}")
        return jsonify([])

@bp.route('/api/projetos/ativos')
def projetos_ativos():
    """API para obter projetos ativos"""
    try:
        dados = service.carregar_dados()
        if dados is None or dados.empty:
            return jsonify([])
            
        projetos = service.obter_projetos_ativos(dados)
        return jsonify(projetos)
        
    except Exception as e:
        logger.error(f"Erro ao obter projetos ativos: {str(e)}")
        return jsonify([])

@bp.route('/api/projetos/criticos')
def projetos_criticos():
    """API para obter projetos críticos"""
    try:
        dados = service.carregar_dados()
        if dados is None or dados.empty:
            return jsonify([])
            
        projetos = service.obter_projetos_criticos(dados)
        return jsonify(projetos)
        
    except Exception as e:
        logger.error(f"Erro ao obter projetos críticos: {str(e)}")
        return jsonify([])

@bp.route('/api/projetos/concluidos')
def projetos_concluidos():
    """API para obter projetos concluídos"""
    try:
        dados = service.carregar_dados()
        if dados is None or dados.empty:
            return jsonify([])
            
        projetos = service.obter_projetos_concluidos(dados)
        return jsonify(projetos)
        
    except Exception as e:
        logger.error(f"Erro ao obter projetos concluídos: {str(e)}")
        return jsonify([])

@bp.route('/api/projetos/eficiencia')
def projetos_eficiencia():
    """API para obter projetos ordenados por eficiência"""
    try:
        dados = service.carregar_dados()
        if dados is None or dados.empty:
            return jsonify([])
            
        projetos = service.obter_projetos_eficiencia(dados)
        return jsonify(projetos)
        
    except Exception as e:
        logger.error(f"Erro ao obter projetos por eficiência: {str(e)}")
        return jsonify([])