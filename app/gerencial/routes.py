import uuid
import logging
import traceback
import pandas as pd
from flask import render_template, request, jsonify
from . import gerencial_bp
from .services import GerencialService

# Instancia o serviço
gerencial_service = GerencialService()

logger = logging.getLogger(__name__)

@gerencial_bp.route('/')
def dashboard():
    """Rota principal do dashboard gerencial"""
    try:
        # Gera ID único para rastreamento de erros
        request_id = str(uuid.uuid4())[:8]
        logger.info(f"[{request_id}] Iniciando carregamento do dashboard gerencial.")
        
        # Obtém parâmetros de filtro da URL
        squad = request.args.get('squad', '').strip()
        faturamento = request.args.get('faturamento', '').strip()
        
        # Carrega dados usando o serviço
        dados = gerencial_service.carregar_dados()
        
        if dados.empty:
            logger.error(f"[{request_id}] Nenhum dado encontrado para exibição")
            return render_template('gerencial/dashboard.html', 
                                erro="Não foi possível carregar os dados do dashboard", 
                                codigo_erro=request_id,
                                filtro_aplicado={'squad': '', 'faturamento': ''},
                                metricas={'total_projetos': 0, 'projetos_ativos': 0, 'projetos_abertos': 0, 'burn_rate': 0.0})
        
        # Aplica filtros se necessário
        dados_filtrados = dados.copy()
        if squad and squad != 'Todos':
            dados_filtrados = dados_filtrados[dados_filtrados['Squad'] == squad]
        if faturamento and faturamento != 'Todos':
            dados_filtrados = dados_filtrados[dados_filtrados['Faturamento'] == faturamento]
        
        # Processa dados para o dashboard
        resultado = gerencial_service.processar_gerencial(dados_filtrados)
        
        # Log detalhado dos projetos críticos
        logger.info(f"[{request_id}] Total de projetos críticos: {len(resultado['projetos_criticos'])}")
        if resultado['projetos_criticos']:
            logger.info(f"[{request_id}] Exemplo de projeto crítico: {resultado['projetos_criticos'][0]}")
        else:
            logger.warning(f"[{request_id}] Nenhum projeto crítico encontrado")
            
        # Verifica contagem de projetos críticos nos metadados
        if 'projetos_criticos_count' in resultado['metricas']:
            logger.info(f"[{request_id}] Contagem de projetos críticos: {resultado['metricas']['projetos_criticos_count']}")
        
        # Prepara contexto para o template
        context = {
            'metricas': resultado['metricas'],
            'projetos_criticos': resultado['projetos_criticos'],
            'projetos_por_squad': resultado['projetos_por_squad'],
            'projetos_por_faturamento': resultado['projetos_por_faturamento'],
            'squads_disponiveis': resultado['squads_disponiveis'],
            'faturamentos_disponiveis': resultado['faturamentos_disponiveis'],
            'ocupacao_squads': resultado.get('ocupacao_squads', []),
            'filtro_aplicado': {
                'squad': squad,
                'faturamento': faturamento
            },
            'grafico_squads': {
                'labels': list(resultado['projetos_por_squad'].keys()),
                'data': list(resultado['projetos_por_squad'].values())
            },
            'grafico_faturamento': {
                'labels': list(resultado['projetos_por_faturamento'].keys()),
                'data': list(resultado['projetos_por_faturamento'].values())
            },
            'alertas': [],  # Lista vazia por padrão
            
            # Métricas para Performance de Entregas
            'taxa_sucesso': resultado['metricas'].get('taxa_sucesso', 0),
            'tempo_medio_geral': resultado['metricas'].get('tempo_medio_geral', 0.0),
            
            # Informações do trimestre fiscal (quarter)
            'quarter_info': resultado['metricas'].get('quarter_info', {})
        }
        
        logger.info(f"[{request_id}] Contexto preparado: {context}")
        return render_template('gerencial/dashboard.html', **context)
        
    except Exception as e:
        logger.error(f"ERRO FATAL [{request_id}]: {str(e)}", exc_info=True)
        return render_template('gerencial/dashboard.html', 
                             erro=f"Não foi possível carregar os dados do dashboard", 
                             codigo_erro=request_id,
                             filtro_aplicado={'squad': '', 'faturamento': ''},
                             metricas={'total_projetos': 0, 'projetos_ativos': 0, 'projetos_abertos': 0, 'burn_rate': 0.0},
                             grafico_squads={'labels': [], 'data': []},
                             grafico_faturamento={'labels': [], 'data': []},
                             alertas=[])

@gerencial_bp.route('/api/projetos-ativos')
def api_projetos_ativos():
    """API para listar projetos ativos"""
    try:
        # Obtém parâmetros de filtro da URL
        squad = request.args.get('squad', '').strip()
        faturamento = request.args.get('faturamento', '').strip()
        
        dados = gerencial_service.carregar_dados()
        if dados.empty:
            return jsonify([])
        
        # Aplica filtros se fornecidos
        dados_filtrados = dados.copy()
        if squad and squad != 'Todos':
            dados_filtrados = dados_filtrados[dados_filtrados['Squad'] == squad]
        if faturamento and faturamento != 'Todos':
            dados_filtrados = dados_filtrados[dados_filtrados['Faturamento'] == faturamento]
        
        projetos = gerencial_service.obter_projetos_ativos(dados_filtrados)
        # Log para debug
        logger.info(f"Projetos ativos retornados pela API: {len(projetos)} projetos")
        if projetos:
            logger.info(f"Exemplo dos primeiros registros: {projetos[:2]}")
        
        return jsonify(projetos)
    except Exception as e:
        logger.error(f"Erro ao obter projetos ativos: {str(e)}")
        return jsonify([])

@gerencial_bp.route('/api/projetos-criticos')
def api_projetos_criticos():
    """API para listar projetos críticos"""
    try:
        # Obtém parâmetros de filtro da URL
        squad = request.args.get('squad', '').strip()
        faturamento = request.args.get('faturamento', '').strip()
        
        dados = gerencial_service.carregar_dados()
        logger.info(f"API projetos-criticos: Carregou dados com {len(dados)} registros")
        
        if dados.empty:
            logger.warning("API projetos-criticos: DataFrame vazio")
            return jsonify([])
        
        # Aplica filtros se fornecidos
        dados_filtrados = dados.copy()
        if squad and squad != 'Todos':
            dados_filtrados = dados_filtrados[dados_filtrados['Squad'] == squad]
            logger.info(f"Filtro por squad '{squad}' aplicado. Restam {len(dados_filtrados)} registros")
        if faturamento and faturamento != 'Todos':
            dados_filtrados = dados_filtrados[dados_filtrados['Faturamento'] == faturamento]
            logger.info(f"Filtro por faturamento '{faturamento}' aplicado. Restam {len(dados_filtrados)} registros")
            
        # Verifica valores únicos na coluna Status
        logger.info(f"API projetos-criticos: Status únicos nos dados: {dados_filtrados['Status'].unique().tolist()}")
        
        # Calcula projetos críticos
        projetos = gerencial_service.obter_projetos_criticos(dados_filtrados)
        logger.info(f"API projetos-criticos: Encontrou {len(projetos)} projetos críticos")
        
        # Log do primeiro projeto crítico (se existir) para debug
        if projetos:
            logger.info(f"API projetos-criticos: Exemplo do primeiro projeto: {projetos[0]}")
        else:
            logger.warning("API projetos-criticos: Nenhum projeto crítico encontrado")
            
        return jsonify(projetos)
    except Exception as e:
        logger.error(f"Erro ao obter projetos críticos: {str(e)}", exc_info=True)
        return jsonify([])

@gerencial_bp.route('/api/projetos-em-atendimento')
def api_projetos_em_atendimento():
    """API para listar projetos em atendimento"""
    try:
        # Obtém parâmetros de filtro da URL
        squad = request.args.get('squad', '').strip()
        faturamento = request.args.get('faturamento', '').strip()
        
        dados = gerencial_service.carregar_dados()
        
        # Aplica filtros se fornecidos
        dados_filtrados = dados.copy()
        if squad and squad != 'Todos':
            dados_filtrados = dados_filtrados[dados_filtrados['Squad'] == squad]
        if faturamento and faturamento != 'Todos':
            dados_filtrados = dados_filtrados[dados_filtrados['Faturamento'] == faturamento]
        
        projetos = gerencial_service.obter_projetos_em_atendimento(dados_filtrados)
        return jsonify(projetos)
    except Exception as e:
        logger.error(f"Erro ao obter projetos em atendimento: {str(e)}")
        return jsonify({'erro': 'Erro ao carregar projetos em atendimento'}), 500

@gerencial_bp.route('/api/projetos-para-faturar')
def api_projetos_para_faturar():
    """API para listar projetos para faturar"""
    try:
        # Obtém parâmetros de filtro da URL
        squad = request.args.get('squad', '').strip()
        faturamento = request.args.get('faturamento', '').strip()
        
        dados = gerencial_service.carregar_dados()
        
        # Aplica filtros se fornecidos
        dados_filtrados = dados.copy()
        if squad and squad != 'Todos':
            dados_filtrados = dados_filtrados[dados_filtrados['Squad'] == squad]
        if faturamento and faturamento != 'Todos':
            dados_filtrados = dados_filtrados[dados_filtrados['Faturamento'] == faturamento]
        
        projetos = gerencial_service.obter_projetos_para_faturar(dados_filtrados)
        return jsonify(projetos)
    except Exception as e:
        logger.error(f"Erro ao obter projetos para faturar: {str(e)}")
        return jsonify({'erro': 'Erro ao carregar projetos para faturar'}), 500

