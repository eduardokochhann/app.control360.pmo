from flask import Blueprint, render_template, jsonify, request, current_app, redirect, url_for
from . import macro_bp, macro_service
from urllib.parse import unquote
import logging
from datetime import datetime, timedelta
import pandas as pd

# Use o logger configurado no app factory (se aplicável)
# logger = current_app.logger
# Ou use o logger do módulo se não estiver usando app factory / current_app
logger = logging.getLogger(__name__)

def get_status_color(status):
    """Define a cor do badge baseado no status do projeto"""
    status = status.upper() if status else ''
    
    # Status ativos em tons de azul
    if status == 'NOVO':
        return 'info'  # azul claro
    elif status == 'EM ATENDIMENTO':
        return 'primary'  # azul
    elif status == 'AGUARDANDO':
        return 'warning'  # amarelo forte
    
    # Status concluídos em tons de verde
    elif status in ['ENCERRADO', 'RESOLVIDO', 'FECHADO']:
        return 'success'  # verde
    
    # Status de alerta em tons quentes
    elif status == 'BLOQUEADO':
        return 'dark'  # preto
    elif status == 'ATRASADO':
        return 'warning'  # amarelo
    elif status == 'CANCELADO':
        return 'danger'  # vermelho
    
    return 'secondary'  # cor padrão (cinza)

def get_conclusao_color(conclusao):
    """Define a cor da barra de progresso baseada na porcentagem de conclusão"""
    try:
        conclusao = float(conclusao)
        if conclusao >= 90:
            return 'success'  # verde
        elif conclusao >= 70:
            return 'info'     # azul
        elif conclusao >= 50:
            return 'warning'  # amarelo
        else:
            return 'danger'   # vermelho
    except:
        return 'secondary'    # cinza (erro)

@macro_bp.route('/')
def dashboard():
    """Rota principal do dashboard macro"""
    try:
        # --- INÍCIO: Carregar dados para Tempo Médio de Vida (Dashboard - Atual + 2 meses anteriores) ---
        hoje = datetime.now()
        dataframes_periodo_dash = []
        fontes_carregadas_dash = []
        mes_atual_dash_loop = hoje.replace(day=1)
        
        for i in range(3): # Carrega mês atual (i=0) e os 2 anteriores (i=1, i=2)
            mes_loop = mes_atual_dash_loop.month
            ano_loop = mes_atual_dash_loop.year
            fonte_mes_loop = None
            fonte_desc = ""
            
            is_current_month = (i == 0)
            
            if is_current_month:
                fonte_mes_loop = None # Usar default dadosr.csv
                fonte_desc = "dadosr.csv (atual)"
            else:
                # Lógica para determinar a fonte dos meses anteriores
                # Precisa ser robusta para diferentes meses/anos
                if mes_loop == 3 and ano_loop == 2025:
                     fonte_mes_loop = 'dadosr_apt_mar'
                elif mes_loop == 2 and ano_loop == 2025:
                     fonte_mes_loop = 'dadosr_apt_fev'
                elif mes_loop == 1 and ano_loop == 2025:
                     fonte_mes_loop = 'dadosr_apt_jan'
                # Adicionar mais regras aqui, ou uma lógica mais dinâmica baseada no nome do mês
                # Exemplo dinâmico (requer teste): 
                # else:
                #    mes_nome_abbr = mes_atual_dash_loop.strftime('%b').lower()
                #    fonte_mes_loop = f'dadosr_apt_{mes_nome_abbr}'
                
                if fonte_mes_loop:
                    fonte_desc = fonte_mes_loop
                else:
                    fonte_desc = f"Não encontrada para {mes_loop}/{ano_loop}"

            # Tenta carregar os dados se a fonte foi definida (ou se for o mês atual)
            if fonte_mes_loop is not None or is_current_month:
                logger.info(f"[Dashboard TMV] Tentando carregar dados da fonte: {fonte_desc} para {mes_loop}/{ano_loop}")
                # Passa None para carregar dadosr.csv no mês atual
                dados_mes = macro_service.carregar_dados(fonte=fonte_mes_loop) 
                if not dados_mes.empty:
                    dataframes_periodo_dash.append(dados_mes)
                    fontes_carregadas_dash.append(fonte_desc)
                else:
                    logger.warning(f"[Dashboard TMV] Dados vazios ou falha ao carregar fonte: {fonte_desc}")
            else:
                 logger.warning(f"[Dashboard TMV] Fonte de dados não encontrada/definida para mês passado {mes_loop}/{ano_loop}")

            # Calcula o mês anterior para a próxima iteração
            primeiro_dia_mes_anterior_loop = mes_atual_dash_loop - timedelta(days=1)
            mes_atual_dash_loop = primeiro_dia_mes_anterior_loop.replace(day=1)
            
        # Combina os dataframes
        dados_combinados_dash = pd.DataFrame()
        if dataframes_periodo_dash:
            try:
                 dados_combinados_dash = pd.concat(dataframes_periodo_dash, ignore_index=True)
                 logger.info(f"[Dashboard TMV] Dados combinados de {len(dataframes_periodo_dash)} fontes ({fontes_carregadas_dash}) para cálculo. Total de linhas: {len(dados_combinados_dash)}")
            except Exception as e_concat:
                 logger.error(f"[Dashboard TMV] Erro ao concatenar dataframes: {e_concat}")
        else:
            logger.warning("[Dashboard TMV] Nenhum dataframe carregado para o período de 3 meses (atual + 2 anteriores).")
            
        # Calcula o tempo médio de vida usando os dados combinados e HOJE como referência
        tempo_medio_vida = macro_service.calcular_tempo_medio_vida(dados_combinados_dash, hoje)
        # --- FIM: Carregar dados para Tempo Médio de Vida --- 
        
        # --- INÍCIO: Carregar dados apenas do mês atual (dadosr.csv) para outros KPIs --- 
        logger.info("[Dashboard] Carregando dados atuais (dadosr.csv) para outros KPIs.")
        dados_atuais = macro_service.carregar_dados(fonte=None) # fonte=None carrega dadosr.csv
        
        if dados_atuais.empty:
            logger.warning("[Dashboard] Dados atuais (dadosr.csv) vazios. Alguns KPIs podem não ser calculados.")
            # Cria DataFrame vazio para evitar erros, mas KPIs baseados nele serão 0/vazios
            dados_atuais = pd.DataFrame() 
        # --- FIM: Carregar dados apenas do mês atual --- 
        
        # Calcula KPIs específicos usando DADOS ATUAIS (dadosr.csv)
        projetos_ativos = macro_service.calcular_projetos_ativos(dados_atuais)
        projetos_criticos = macro_service.calcular_projetos_criticos(dados_atuais)
        media_horas = macro_service.calcular_media_horas(dados_atuais)
        projetos_concluidos = macro_service.calcular_projetos_concluidos(dados_atuais)
        eficiencia_entrega = macro_service.calcular_eficiencia_entrega(dados_atuais)
        projetos_risco = macro_service.calcular_projetos_risco(dados_atuais)
        # tempo_medio_vida já foi calculado acima com dados combinados
        
        # Calcula agregações por status usando DADOS ATUAIS
        agregacoes = macro_service.calcular_agregacoes(dados_atuais)
        
        # Prepara dados dos especialistas usando DADOS ATUAIS
        dados_especialistas = macro_service.calcular_alocacao_especialistas(dados_atuais)
        
        # Prepara dados das abas (incluindo Account Managers) usando DADOS ATUAIS
        dados_abas = macro_service.preparar_dados_abas(dados_atuais)
        
        # Calcula média de alocação
        media_alocacao = 0.0
        if dados_especialistas:
            taxas_uso = [dados.get('taxa_uso', 0) for dados in dados_especialistas.values()]
            if taxas_uso:
                media_alocacao = sum(taxas_uso) / len(taxas_uso)
        
        # Calcula ocupação dos Squads usando DADOS ATUAIS
        ocupacao_squads = macro_service.calcular_ocupacao_squads(dados_atuais)
        
        # Prepara contexto para o template
        context = {
            'kpis': {
                'projetos_ativos': projetos_ativos['total'],
                'projetos_criticos': projetos_criticos['total'],
                'media_horas': media_horas['total'],
                'projetos_concluidos': projetos_concluidos['total'],
                'eficiencia_entrega': eficiencia_entrega['total'],
                'tempo_medio_vida': tempo_medio_vida['media_dias']
            },
            'projetos_ativos': projetos_ativos['dados'].to_dict('records'),
            'projetos_criticos': projetos_criticos['dados'].to_dict('records'),
            'projetos_concluidos': projetos_concluidos['dados'].to_dict('records'),
            'eficiencia_entrega': eficiencia_entrega['dados'].to_dict('records'),
            'projetos_risco': projetos_risco.to_dict('records') if not projetos_risco.empty else [],
            'por_status': agregacoes['por_status'],
            'get_status_color': get_status_color,
            'get_conclusao_color': get_conclusao_color,
            'dados_especialistas': dados_especialistas,
            'media_alocacao': media_alocacao,
            'dados_accounts': dados_abas['dados_accounts'],
            'tempo_medio_vida_distribuicao': tempo_medio_vida['distribuicao'],
            'tempo_medio_vida_dados': tempo_medio_vida['dados'],
            'ocupacao_squads': ocupacao_squads
        }
        
        # Adiciona a hora atual para exibição
        context['hora_atualizacao'] = datetime.now()
        
        logger.info(f"Contexto preparado - média de horas: {context['kpis']['media_horas']}")
        logger.info(f"Agregações por status: {context['por_status']}")
        logger.info(f"Total de projetos em risco: {len(context['projetos_risco'])}")
        
        return render_template('macro/dashboard.html', **context)
        
    except Exception as e:
        logger.exception(f"Erro na rota dashboard: {str(e)}")
        return render_template('macro/dashboard.html', 
                             error=str(e),
                             kpis={'projetos_ativos': 0, 'projetos_criticos': 0, 'media_horas': 0.0, 'projetos_concluidos': 0},
                             projetos_ativos=[],
                             projetos_criticos=[],
                             projetos_concluidos=[],
                             projetos_risco=[],
                             por_status={})

# --- Rotas de API (Mantidas exatamente como estavam) ---
@macro_bp.route('/api/especialistas')
def api_especialistas():
    logger.info("Acessando rota /api/especialistas")
    dados = macro_service.carregar_dados()
    if dados.empty:
        logger.warning("Dados vazios para /api/especialistas.")
        return jsonify({})  # Retorna dicionário vazio em vez de lista vazia
    alocacao_especialistas = macro_service.calcular_alocacao_especialistas(dados)
    logger.debug(f"Retornando {len(alocacao_especialistas)} registros para /api/especialistas")
    return jsonify(alocacao_especialistas)

@macro_bp.route('/api/accounts')
def api_accounts():
    logger.info("Acessando rota /api/accounts")
    dados = macro_service.carregar_dados()
    if dados.empty:
        logger.warning("Dados vazios para /api/accounts.")
        return jsonify([]) # Retorna lista vazia
    dados_accounts = macro_service.preparar_dados_abas(dados)['dados_accounts']
    logger.debug(f"Retornando {len(dados_accounts)} registros para /api/accounts")
    return jsonify(dados_accounts)

@macro_bp.route('/api/filter', methods=['GET'])
def api_filter():
    """API para filtro de dados"""
    try:
        logger.info("Iniciando api_filter: carregando dados...")
        service = macro_service
        dados = service.carregar_dados()
        
        # LOG 1: Verificar dados carregados
        logger.info(f"[api_filter] Dados carregados: {dados.shape}")
        if not dados.empty and 'Status' in dados.columns:
            logger.info(f"[api_filter] Contagem de Status (bruto): {dados['Status'].astype(str).str.upper().value_counts().to_dict()}")
        else:
            logger.warning("[api_filter] DataFrame vazio ou sem coluna 'Status' após carregar.")
            
        # Verificação básica dos dados
        if dados.empty:
            logger.warning("Dados vazios retornados ao chamar api_filter")
            # Retorna estrutura mínima garantida apenas com os status desejados
            return jsonify({
                'por_status': {
                    'NOVO': {'quantidade': 0, 'horas_totais': 0.0, 'conclusao_media': 0.0, 'cor': 'info'},
                    'EM ATENDIMENTO': {'quantidade': 0, 'horas_totais': 0.0, 'conclusao_media': 0.0, 'cor': 'primary'},
                    'AGUARDANDO': {'quantidade': 0, 'horas_totais': 0.0, 'conclusao_media': 0.0, 'cor': 'warning'},
                    'BLOQUEADO': {'quantidade': 0, 'horas_totais': 0.0, 'conclusao_media': 0.0, 'cor': 'dark'},
                    'FECHADO': {'quantidade': 0, 'horas_totais': 0.0, 'conclusao_media': 0.0, 'cor': 'success'}
                },
                'projetos_risco': []
            })
        
        # Calcula agregações
        agregacoes = service.calcular_agregacoes(dados)
        
        # LOG 2: Verificar resultado da agregação
        logger.info(f"[api_filter] Agregações retornadas por service: {agregacoes.get('por_status')}")
        
        # Garante que o campo por_status existe
        if 'por_status' not in agregacoes:
            logger.error("Campo 'por_status' não encontrado nas agregações")
            agregacoes['por_status'] = {}
        
        # Lista dos status que queremos manter
        status_permitidos = ['NOVO', 'EM ATENDIMENTO', 'AGUARDANDO', 'BLOQUEADO', 'FECHADO']
        
        # Filtra para manter apenas os status permitidos
        por_status_filtrado = {}
        for status, dados_status in agregacoes['por_status'].items():
            if status.upper() in status_permitidos:
                por_status_filtrado[status] = dados_status
                logger.info(f"Mantendo status {status} com {dados_status.get('quantidade', 0)} projetos")
        
        # Garante que todos os status permitidos existam com valores padrão
        cores_padrao = {
            'NOVO': 'info',
            'EM ATENDIMENTO': 'primary',
            'AGUARDANDO': 'warning',
            'BLOQUEADO': 'dark',
            'FECHADO': 'success'
        }
        
        for status in status_permitidos:
            if status not in por_status_filtrado:
                por_status_filtrado[status] = {
                    'quantidade': 0,
                    'horas_totais': 0.0,
                    'conclusao_media': 0.0,
                    'cor': cores_padrao.get(status, 'secondary')
                }
                logger.info(f"Adicionando status padrão para {status}")
        
        # Atualiza as agregações com os status filtrados
        agregacoes['por_status'] = por_status_filtrado
        
        # LOG 3: Verificar status filtrado antes de retornar
        logger.info(f"[api_filter] Status filtrado para JSON: {por_status_filtrado}")
        
        # Garante que projetos_risco existe
        if 'projetos_risco' not in agregacoes:
            logger.warning("Campo 'projetos_risco' não encontrado nas agregações")
            agregacoes['projetos_risco'] = []
        
        # Retorna o objeto com dados filtrados
        logger.info(f"api_filter: Finalizando com sucesso. Status incluídos: {list(por_status_filtrado.keys())}")
        return jsonify(agregacoes)
    
    except Exception as e:
        logger.exception(f"Erro ao processar api_filter: {str(e)}")
        # Retorna estrutura mínima garantida apenas com os status desejados
        return jsonify({
            'por_status': {
                'NOVO': {'quantidade': 0, 'horas_totais': 0.0, 'conclusao_media': 0.0, 'cor': 'info'},
                'EM ATENDIMENTO': {'quantidade': 0, 'horas_totais': 0.0, 'conclusao_media': 0.0, 'cor': 'primary'},
                'AGUARDANDO': {'quantidade': 0, 'horas_totais': 0.0, 'conclusao_media': 0.0, 'cor': 'warning'},
                'BLOQUEADO': {'quantidade': 0, 'horas_totais': 0.0, 'conclusao_media': 0.0, 'cor': 'dark'},
                'FECHADO': {'quantidade': 0, 'horas_totais': 0.0, 'conclusao_media': 0.0, 'cor': 'success'}
            },
            'projetos_risco': []
        })

@macro_bp.route('/api/projetos/especialista/<path:nome_especialista>')
def api_projetos_por_especialista(nome_especialista):
    """
    Retorna a lista de projetos ATIVOS para um especialista específico.
    """
    nome_decodificado = unquote(nome_especialista)
    logger.info(f"API: Buscando projetos ativos para o especialista: '{nome_decodificado}'")
    dados = macro_service.carregar_dados()

    if dados.empty:
        logger.warning(f"API: Dados gerais vazios ao buscar projetos para '{nome_decodificado}'.")
        return jsonify([])

    try:
        # Status que indicam que o projeto não está mais ativo
        STATUS_NAO_ATIVOS = ['FECHADO', 'ENCERRADO', 'RESOLVIDO', 'CANCELADO']
        
        # Filtrar apenas projetos ativos
        dados_ativos = dados[~dados['Status'].str.upper().isin([s.upper() for s in STATUS_NAO_ATIVOS])].copy()
        
        # Log para debug
        logger.debug(f"Total de projetos ativos encontrados: {len(dados_ativos)}")
        
        # Filtrar pelos projetos do especialista (case insensitive)
        dados_especialista = dados_ativos[
            dados_ativos['Especialista'].str.upper() == nome_decodificado.upper()
        ]
        
        # Log para debug
        logger.debug(f"Projetos encontrados para {nome_decodificado}: {len(dados_especialista)}")
        if not dados_especialista.empty:
            logger.debug(f"Projetos: {dados_especialista['Projeto'].tolist()}")

        # Certifica-se de que a coluna Numero existe
        if 'Numero' not in dados_especialista.columns and 'Número' in dados_especialista.columns:
            dados_especialista['Numero'] = dados_especialista['Número']
        elif 'Numero' not in dados_especialista.columns:
            logger.warning(f"Coluna 'Numero' não encontrada para especialista '{nome_decodificado}'. Criando coluna vazia.")
            dados_especialista['Numero'] = ''

        # Selecionar e renomear colunas relevantes
        colunas = {
            'Numero': 'numero',
            'Projeto': 'projeto',
            'Status': 'status',
            'Squad': 'squad',
            'HorasRestantes': 'horasRestantes',
            'Conclusao': 'conclusao',
            'VencimentoEm': 'dataPrevEnc',
            'Horas': 'Horas' # Adicionado Horas (Esforço) - Não precisa renomear
        }
        
        # Garantir que todas as colunas existem
        colunas_existentes = {k: v for k, v in colunas.items() if k in dados_especialista.columns}
        dados_formatados = dados_especialista[list(colunas_existentes.keys())].copy()
        
        # Renomear colunas
        dados_formatados = dados_formatados.rename(columns=colunas_existentes)

        # Formatar a data de previsão de encerramento
        if 'dataPrevEnc' in dados_formatados.columns:
            dados_formatados['dataPrevEnc'] = pd.to_datetime(
                dados_formatados['dataPrevEnc'], 
                errors='coerce'
            ).dt.strftime('%d/%m/%Y')
            # Substituir NaN por 'N/A' sem usar inplace
            dados_formatados['dataPrevEnc'] = dados_formatados['dataPrevEnc'].fillna('N/A')

        # Converter para lista de dicionários
        projetos = dados_formatados.to_dict('records')
        
        logger.info(f"API: Encontrados {len(projetos)} projetos ativos para '{nome_decodificado}'.")
        return jsonify(projetos)

    except Exception as e:
        logger.exception(f"API: Erro ao buscar projetos para '{nome_decodificado}': {str(e)}")
        return jsonify({"error": f"Erro ao buscar projetos para {nome_decodificado}"}), 500

@macro_bp.route('/api/projetos/ativos')
def get_projetos_ativos():
    """Retorna lista de projetos ativos para o modal"""
    try:
        dados = macro_service.carregar_dados()
        
        if dados.empty:
            return jsonify([])

        projetos_ativos = macro_service.calcular_projetos_ativos(dados)
        return jsonify(projetos_ativos['dados'].to_dict('records'))
        
    except Exception as e:
        logger.exception(f"Erro ao buscar projetos ativos: {str(e)}")
        return jsonify([])

@macro_bp.route('/api/projetos/criticos')
def get_projetos_criticos():
    """Retorna lista de projetos críticos para o modal"""
    try:
        dados = macro_service.carregar_dados()
        
        if dados.empty:
            return jsonify([])

        projetos_criticos = macro_service.calcular_projetos_criticos(dados)
        return jsonify(projetos_criticos['dados'].to_dict('records'))
        
    except Exception as e:
        logger.exception(f"Erro ao buscar projetos críticos: {str(e)}")
        return jsonify([])

@macro_bp.route('/api/projetos/concluidos')
def get_projetos_concluidos():
    """Retorna lista de projetos concluídos para o modal"""
    try:
        dados = macro_service.carregar_dados()
        
        if dados.empty:
            return jsonify([])

        projetos_concluidos = macro_service.calcular_projetos_concluidos(dados)
        return jsonify(projetos_concluidos['dados'].to_dict('records'))
        
    except Exception as e:
        logger.exception(f"Erro ao buscar projetos concluídos: {str(e)}")
        return jsonify([])

@macro_bp.route('/api/projetos/eficiencia')
def get_projetos_eficiencia():
    """Retorna lista de projetos com suas eficiências para o modal"""
    try:
        dados = macro_service.carregar_dados()
        
        if dados.empty:
            return jsonify([])

        eficiencia_entrega = macro_service.calcular_eficiencia_entrega(dados)
        return jsonify(eficiencia_entrega['dados'].to_dict('records'))
        
    except Exception as e:
        logger.exception(f"Erro ao buscar eficiência dos projetos: {str(e)}")
        return jsonify([])

@macro_bp.route('/api/projetos/account/<path:nome_account>')
def api_projetos_por_account(nome_account):
    """
    Retorna a lista de projetos ATIVOS para um Account Manager específico.
    """
    nome_decodificado = unquote(nome_account)
    logger.info(f"API: Buscando projetos ativos para o Account Manager: '{nome_decodificado}'")
    dados = macro_service.carregar_dados()

    if dados.empty:
        logger.warning(f"API: Dados gerais vazios ao buscar projetos para '{nome_decodificado}'.")
        return jsonify([])

    try:
        # Status que indicam que o projeto não está mais ativo
        STATUS_NAO_ATIVOS = ['FECHADO', 'ENCERRADO', 'RESOLVIDO', 'CANCELADO']
        
        # Filtrar apenas projetos ativos
        dados_ativos = dados[~dados['Status'].str.upper().isin([s.upper() for s in STATUS_NAO_ATIVOS])].copy()
        
        # Log para debug
        logger.debug(f"Total de projetos ativos encontrados: {len(dados_ativos)}")
        
        # Filtrar pelos projetos do Account Manager (case insensitive)
        dados_account = dados_ativos[
            dados_ativos['Account Manager'].str.upper() == nome_decodificado.upper()
        ]
        
        # Log para debug
        logger.debug(f"Projetos encontrados para {nome_decodificado}: {len(dados_account)}")
        if not dados_account.empty:
            logger.debug(f"Projetos: {dados_account['Projeto'].tolist()}")

        # Certifica-se de que a coluna Numero existe
        if 'Numero' not in dados_account.columns and 'Número' in dados_account.columns:
            dados_account['Numero'] = dados_account['Número']
        elif 'Numero' not in dados_account.columns:
            logger.warning(f"Coluna 'Numero' não encontrada para account '{nome_decodificado}'. Criando coluna vazia.")
            dados_account['Numero'] = ''

        # Selecionar e renomear colunas relevantes
        colunas = {
            'Numero': 'numero',
            'Projeto': 'projeto',
            'Status': 'status',
            'Squad': 'squad',
            'Especialista': 'especialista',
            'HorasRestantes': 'horasRestantes',
            'Conclusao': 'conclusao',
            'VencimentoEm': 'dataPrevEnc',
            'Horas': 'Horas' # Adicionado Horas (Esforço) - Não precisa renomear
        }
        
        # Garantir que todas as colunas existem
        colunas_existentes = {k: v for k, v in colunas.items() if k in dados_account.columns}
        dados_formatados = dados_account[list(colunas_existentes.keys())].copy()
        
        # Renomear colunas
        dados_formatados = dados_formatados.rename(columns=colunas_existentes)

        # Formatar a data de previsão de encerramento
        if 'dataPrevEnc' in dados_formatados.columns:
            dados_formatados['dataPrevEnc'] = pd.to_datetime(
                dados_formatados['dataPrevEnc'], 
                errors='coerce'
            ).dt.strftime('%d/%m/%Y')
            # Substituir NaN por 'N/A'
            dados_formatados['dataPrevEnc'] = dados_formatados['dataPrevEnc'].fillna('N/A')

        # Converter para lista de dicionários
        projetos = dados_formatados.to_dict('records')
        
        logger.info(f"API: Encontrados {len(projetos)} projetos ativos para '{nome_decodificado}'.")
        return jsonify(projetos)

    except Exception as e:
        logger.exception(f"API: Erro ao buscar projetos para '{nome_decodificado}': {str(e)}")
        return jsonify({"error": f"Erro ao buscar projetos para {nome_decodificado}"}), 500

@macro_bp.route('/api/debug', methods=['GET'])
def api_debug():
    """Rota para debug de dados da macro"""
    try:
        logger.info("Iniciando api_debug: carregando dados...")
        service = macro_service
        dados = service.carregar_dados()
        
        # Informações básicas
        info = {
            'total_registros': len(dados),
            'colunas': dados.columns.tolist(),
        }
        
        if dados.empty:
            logger.warning("api_debug: Dados vazios retornados")
            return jsonify({
                'msg': 'Dados vazios',
                'data': info
            })
        
        # Informações sobre status
        if 'Status' in dados.columns:
            status_unicos = dados['Status'].astype(str).str.upper().unique().tolist()
            contagem_status = dados['Status'].astype(str).str.upper().value_counts().to_dict()
            info['status_unicos'] = status_unicos
            info['contagem_status'] = contagem_status
            logger.info(f"api_debug: Encontrados {len(status_unicos)} status únicos")
            for status, count in contagem_status.items():
                logger.debug(f"api_debug: Status {status}: {count} projetos")
        else:
            logger.error("api_debug: Coluna 'Status' não encontrada nos dados")
            info['erro_status'] = "Coluna 'Status' não encontrada"
        
        # Analisa integridade dos dados
        colunas_esperadas = ['Projeto', 'Status', 'Squad', 'Especialista', 'Horas', 'HorasTrabalhadas']
        colunas_faltantes = [col for col in colunas_esperadas if col not in dados.columns]
        if colunas_faltantes:
            logger.warning(f"api_debug: Colunas esperadas não encontradas: {colunas_faltantes}")
            info['colunas_faltantes'] = colunas_faltantes
        
        # Verifica valores nulos
        valores_nulos = {col: int(dados[col].isna().sum()) for col in dados.columns}
        colunas_com_nulos = {col: count for col, count in valores_nulos.items() if count > 0}
        if colunas_com_nulos:
            logger.warning(f"api_debug: Colunas com valores nulos: {colunas_com_nulos}")
            info['valores_nulos'] = colunas_com_nulos
        
        # Amostra de dados e agregações
        info['amostra_dados'] = dados.head(5).to_dict('records')
        
        try:
            logger.info("api_debug: Calculando agregações...")
            info['agregacoes'] = service.calcular_agregacoes(dados)
            logger.info("api_debug: Agregações calculadas com sucesso")
        except Exception as agg_error:
            logger.error(f"api_debug: Erro ao calcular agregações: {str(agg_error)}")
            info['erro_agregacoes'] = str(agg_error)
        
        logger.info("api_debug: Processamento concluído com sucesso")
        return jsonify({
            'msg': 'Informações de debug',
            'data': info
        })
        
    except Exception as e:
        logger.exception(f"Erro na API de debug: {str(e)}")
        return jsonify({
            'msg': 'Erro ao gerar debug',
            'error': str(e)
        }), 500

@macro_bp.route('/apresentacao')
def apresentacao():
    """Rota para página de apresentação para diretoria"""
    try:
        logger.info("Acessando página de apresentação para diretoria")
        
        # Obter parâmetros de consulta para mês e ano
        mes_param = request.args.get('mes', None)
        ano_param = request.args.get('ano', None)
        
        # Determina se é a Visão Atual ou uma Visão Histórica
        is_visao_atual = not mes_param or not ano_param
        
        if is_visao_atual:
            logger.info("Processando como Visão Atual (sem parâmetros de data específicos).")
            # --- LÓGICA PARA VISÃO ATUAL ---
            dados_atuais, mes_referencia = macro_service.obter_dados_e_referencia_atual()
            
            if mes_referencia is None:
                # Se não foi possível determinar o mês de referência, usar padrão ou mostrar erro
                logger.error("Não foi possível determinar o mês de referência da Visão Atual. Usando mês anterior como fallback.")
                hoje = datetime.now()
                primeiro_dia_mes_atual = hoje.replace(day=1)
                ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
                mes_referencia = ultimo_dia_mes_anterior.replace(day=1)
                # Idealmente, tratar esse erro de forma mais robusta (ex: mensagem no template)
                # Poderia também carregar os dados novamente aqui se o service não os retornou
                if dados_atuais.empty:
                    dados_atuais = macro_service.carregar_dados(fonte=None)
            
            # Calcula o mês anterior para comparação
            primeiro_dia_mes_referencia = mes_referencia
            ultimo_dia_mes_anterior_ref = primeiro_dia_mes_referencia - timedelta(days=1)
            mes_comparativo = ultimo_dia_mes_anterior_ref.replace(day=1)
            
            logger.info(f"Visão Atual - Mês de Referência: {mes_referencia.strftime('%B/%Y')}, Mês Comparativo: {mes_comparativo.strftime('%B/%Y')}")
            
            # Renomeia dados_atuais para dados_ref para manter consistência com o resto do código por enquanto
            # Idealmente, refatoraríamos as funções de cálculo para aceitar nomes diferentes
            dados_ref = dados_atuais
            fonte_dados_ref = 'dadosr.csv'
            
            # --- Aqui chamaremos as NOVAS funções de cálculo (quando existirem) ---
            # Exemplo (ainda usando as antigas temporariamente):
            # comparativo_atual = macro_service.calcular_comparativo_atual(dados_ref, mes_referencia, mes_comparativo)
            # projetos_entregues_atuais = macro_service.calcular_projetos_entregues_atuais(dados_ref, mes_referencia)
            # ... etc

        else:
            logger.info(f"Processando como Visão Histórica para {mes_param}/{ano_param}.")
            # --- LÓGICA PARA VISÃO HISTÓRICA (como estava antes) ---
            try:
                mes_referencia = datetime(int(ano_param), int(mes_param), 1)
                logger.info(f"Usando mês de referência dos parâmetros: {mes_referencia.strftime('%m/%Y')}")
            except ValueError:
                logger.warning(f"Parâmetros de data inválidos: mes={mes_param}, ano={ano_param}. Redirecionando para visão atual.")
                # Redireciona para a URL sem parâmetros se a data for inválida
                return redirect(url_for('macro.apresentacao'))
            
            # Calcula o mês anterior para comparação
            primeiro_dia_mes_referencia = mes_referencia
            ultimo_dia_mes_anterior_ref = primeiro_dia_mes_referencia - timedelta(days=1)
            mes_comparativo = ultimo_dia_mes_anterior_ref.replace(day=1)
            
            logger.info(f"Visão Histórica - Mês de Referência: {mes_referencia.strftime('%B/%Y')}, Mês Comparativo: {mes_comparativo.strftime('%B/%Y')}")

            # --- Carregamento de dados APENAS para o mês de referência (VISÃO HISTÓRICA) ---
            # Determina qual fonte de dados usar com base no mês de referência
            fonte_dados_ref = None
            if mes_referencia.month == 3 and mes_referencia.year == 2025:
                fonte_dados_ref = 'dadosr_apt_mar'
            elif mes_referencia.month == 4 and mes_referencia.year == 2025: # <-- Adicionado Abril
                fonte_dados_ref = 'dadosr_apt_abr'
            elif mes_referencia.month == 2 and mes_referencia.year == 2025:
                fonte_dados_ref = 'dadosr_apt_fev'
            elif mes_referencia.month == 1 and mes_referencia.year == 2025:
                fonte_dados_ref = 'dadosr_apt_jan'
            # Adicionar mais fontes históricas aqui
            
            if not fonte_dados_ref:
                logger.error(f"Fonte de dados histórica não definida para {mes_referencia.strftime('%m/%Y')}. Não é possível carregar dados.")
                # Mostrar erro para o usuário
                return render_template('macro/erro.html',
                                     error=f"Fonte de dados não encontrada para o período {mes_referencia.strftime('%B/%Y')}.",
                                     titulo="Erro na Apresentação")
                
            logger.info(f"Carregando dados da fonte histórica: {fonte_dados_ref} para {mes_referencia.strftime('%m/%Y')}")
            dados_ref = macro_service.carregar_dados(fonte=fonte_dados_ref)
            
            if dados_ref.empty:
                logger.warning(f"Dados históricos vazios retornados para {fonte_dados_ref}")
                # Mostrar erro ou página vazia?
                return render_template('macro/erro.html',
                                     error=f"Não foram encontrados dados para o período {mes_referencia.strftime('%B/%Y')} (Fonte: {fonte_dados_ref}).",
                                     titulo="Erro na Apresentação")
            
        # --- CÁLCULOS COMUNS OU TEMPORÁRIOS --- 
        # (Esta seção agora executa APÓS o IF/ELSE, usando dados_ref e mes_referencia definidos)
        
        # --- INÍCIO: Carregar dados para Tempo Médio de Vida (Últimos 3 meses a partir da REFERÊNCIA) ---
        # (A lógica precisa ser ajustada para usar o mes_referencia correto)
        dataframes_periodo = []
        fontes_carregadas = []
        mes_atual_loop = mes_referencia.replace(day=1) # USA O MES DE REFERÊNCIA DEFINIDO
        
        for i in range(3): # Carrega mês de referência e os 2 anteriores
            mes_loop = mes_atual_loop.month
            ano_loop = mes_atual_loop.year
            fonte_mes_loop = None
            
            # Lógica unificada para determinar a fonte (precisa ser robusta)
            # Se for a visão atual E i==0 (o próprio mês de referência), usa dados_ref já carregado
            if is_visao_atual and i == 0:
                 dados_mes = dados_ref
                 fonte_mes_loop = 'dadosr.csv (atual)' # Descritivo
                 logger.info(f"[Tempo Médio Vida] Usando dados já carregados para mês de referência atual ({mes_referencia.strftime('%m/%Y')})")
            else:
                # Lógica para determinar a fonte histórica (igual à anterior, mas precisa ser mais completa)
                if mes_loop == 3 and ano_loop == 2025: fonte_mes_loop = 'dadosr_apt_mar'
                elif mes_loop == 4 and ano_loop == 2025: fonte_mes_loop = 'dadosr_apt_abr' # <-- Adicionado Abril
                elif mes_loop == 2 and ano_loop == 2025: fonte_mes_loop = 'dadosr_apt_fev'
                elif mes_loop == 1 and ano_loop == 2025: fonte_mes_loop = 'dadosr_apt_jan'
                # Adicionar mais fontes aqui...
                
                if fonte_mes_loop:
                    logger.info(f"[Tempo Médio Vida] Tentando carregar dados da fonte: {fonte_mes_loop} para {mes_loop}/{ano_loop}")
                    dados_mes = macro_service.carregar_dados(fonte=fonte_mes_loop)
                else:
                    logger.warning(f"[Tempo Médio Vida] Fonte de dados não definida para {mes_loop}/{ano_loop}")
                    dados_mes = pd.DataFrame() # Define como vazio para evitar erro
            
            if not dados_mes.empty:
                dataframes_periodo.append(dados_mes)
                if isinstance(fonte_mes_loop, str): # Adiciona fonte apenas se for string (não o df atual)
                     fontes_carregadas.append(fonte_mes_loop)
            else:
                if isinstance(fonte_mes_loop, str): # Loga aviso apenas se tentou carregar fonte
                    logger.warning(f"[Tempo Médio Vida] Dados vazios ou falha ao carregar fonte: {fonte_mes_loop}")

            # Calcula o mês anterior para a próxima iteração
            primeiro_dia_mes_anterior_loop = mes_atual_loop - timedelta(days=1)
            mes_atual_loop = primeiro_dia_mes_anterior_loop.replace(day=1)
            
        # Combina os dataframes
        dados_combinados_tmv = pd.DataFrame()
        if dataframes_periodo:
            try:
                 dados_combinados_tmv = pd.concat(dataframes_periodo, ignore_index=True).drop_duplicates()
                 logger.info(f"[Tempo Médio Vida] Dados combinados de {len(fontes_carregadas)} fontes ({fontes_carregadas}) para cálculo. Total de linhas únicas: {len(dados_combinados_tmv)}")
            except Exception as e_concat:
                 logger.error(f"[Tempo Médio Vida] Erro ao concatenar dataframes: {e_concat}")
        else:
            logger.warning("[Tempo Médio Vida] Nenhum dataframe carregado para o período de 3 meses a partir da referência.")
            
        # Calcula o tempo médio de vida usando os dados combinados e o mes_referencia correto
        tempo_medio_vida_dados = macro_service.calcular_tempo_medio_vida(dados_combinados_tmv, mes_referencia)
        # --- FIM: Carregar dados para Tempo Médio de Vida ---
        
        # --- INÍCIO: Calcular Tempo Médio de Vida do Período Comparativo --- 
        # (Usa mes_comparativo)
        tempo_medio_vida_anterior_val = 0.0 # Default
        try:
            dataframes_periodo_anterior = []
            fontes_carregadas_anterior = []
            # Mês de referência para o período anterior é o mes_comparativo
            mes_atual_loop_ant = mes_comparativo.replace(day=1) 
            
            for i in range(3): # Carrega mês comparativo e os 2 anteriores a ele
                mes_loop = mes_atual_loop_ant.month
                ano_loop = mes_atual_loop_ant.year
                fonte_mes_loop = None
                
                # Lógica para determinar a fonte (precisa ser expandida)
                if mes_loop == 3 and ano_loop == 2025: fonte_mes_loop = 'dadosr_apt_mar'
                elif mes_loop == 4 and ano_loop == 2025: fonte_mes_loop = 'dadosr_apt_abr' # <-- Precisa de Março aqui para comparar Abril
                elif mes_loop == 2 and ano_loop == 2025: fonte_mes_loop = 'dadosr_apt_fev'
                elif mes_loop == 1 and ano_loop == 2025: fonte_mes_loop = 'dadosr_apt_jan'
                elif mes_loop == 12 and ano_loop == 2024: fonte_mes_loop = 'dadosr_apt_dez' 
                # Adicionar mais regras aqui...
                
                if fonte_mes_loop:
                    logger.info(f"[TMV Anterior] Tentando carregar dados da fonte: {fonte_mes_loop} para {mes_loop}/{ano_loop}")
                    dados_mes_ant = macro_service.carregar_dados(fonte=fonte_mes_loop)
                    if not dados_mes_ant.empty:
                        dataframes_periodo_anterior.append(dados_mes_ant)
                        fontes_carregadas_anterior.append(fonte_mes_loop)
                    else:
                        logger.warning(f"[TMV Anterior] Dados vazios ou falha ao carregar fonte: {fonte_mes_loop}")
                else:
                    logger.warning(f"[TMV Anterior] Fonte de dados não definida para {mes_loop}/{ano_loop}")
                    
                # Calcula o mês anterior para a próxima iteração
                primeiro_dia_mes_anterior_loop = mes_atual_loop_ant - timedelta(days=1)
                mes_atual_loop_ant = primeiro_dia_mes_anterior_loop.replace(day=1)
                
            # Combina os dataframes do período anterior
            dados_combinados_tmv_anterior = pd.DataFrame()
            if dataframes_periodo_anterior:
                dados_combinados_tmv_anterior = pd.concat(dataframes_periodo_anterior, ignore_index=True).drop_duplicates()
                logger.info(f"[TMV Anterior] Dados combinados de {len(fontes_carregadas_anterior)} fontes ({fontes_carregadas_anterior}). Total único: {len(dados_combinados_tmv_anterior)}")
                
                # Calcula o tempo médio de vida do período anterior (usando mes_comparativo)
                tempo_medio_vida_anterior = macro_service.calcular_tempo_medio_vida(dados_combinados_tmv_anterior, mes_comparativo)
                tempo_medio_vida_anterior_val = tempo_medio_vida_anterior.get('media_dias', 0.0)
                logger.info(f"[TMV Anterior] Média calculada para {mes_comparativo.strftime('%B/%Y')}: {tempo_medio_vida_anterior_val}")
            else:
                logger.warning(f"[TMV Anterior] Nenhum dataframe carregado para o período comparativo ({mes_comparativo.strftime('%B/%Y')}).")

        except Exception as e_tmv_ant:
            logger.error(f"Erro ao calcular tempo médio de vida anterior: {e_tmv_ant}")

        # Calcular variação percentual do Tempo Médio de Vida
        tempo_medio_vida_atual = tempo_medio_vida_dados.get('media_dias', 0.0)
        variacao_pct_tmv = 0.0
        if tempo_medio_vida_anterior_val > 0:
            variacao_pct_tmv = round(((tempo_medio_vida_atual - tempo_medio_vida_anterior_val) / tempo_medio_vida_anterior_val) * 100, 1)
        elif tempo_medio_vida_atual > 0: # Anterior era 0, atual não é
            variacao_pct_tmv = 100.0 # Ou outra convenção para indicar aumento grande
        logger.info(f"[TMV Comp] Ref ({mes_referencia.strftime('%m/%Y')}): {tempo_medio_vida_atual}, Comp ({mes_comparativo.strftime('%m/%Y')}): {tempo_medio_vida_anterior_val}, VarPct: {variacao_pct_tmv}%")
        # --- FIM: Calcular Tempo Médio de Vida do Período Comparativo --- 
        
        # --- CALCULA DADOS USANDO dados_ref e mes_referencia ---
        # (Estes podem precisar de versões _atuais vs _historicas no futuro)
        
        # Calcula dados sobre projetos entregues
        if is_visao_atual:
            projetos_entregues = macro_service.calcular_projetos_entregues_atual(dados_ref, mes_referencia)
        else:
            projetos_entregues = macro_service.calcular_projetos_entregues(dados_ref, mes_referencia)
        
        # Calcula dados sobre novos projetos no mês
        if is_visao_atual:
            novos_projetos = macro_service.calcular_novos_projetos_atual(dados_ref, mes_referencia)
        else:
            novos_projetos = macro_service.calcular_novos_projetos_mes(dados_ref, mes_referencia)

        # --- INÍCIO: Calcular comparação de Projetos Entregues --- 
        # (Usa o histórico dentro de projetos_entregues)
        entregues_atual = projetos_entregues.get('total_mes', 0)
        entregues_anterior_val = 0
        
        # Mapeamento Num -> Nome PT (minúsculo) para comparação robusta
        mes_comparativo_num = mes_comparativo.month
        nomes_meses_pt = {
            1: 'janeiro', 2: 'fevereiro', 3: 'março', 4: 'abril', 5: 'maio', 6: 'junho',
            7: 'julho', 8: 'agosto', 9: 'setembro', 10: 'outubro', 11: 'novembro', 12: 'dezembro'
        }
        nome_mes_comparativo_pt = nomes_meses_pt.get(mes_comparativo_num, '')
        
        historico_entregas = projetos_entregues.get('historico', [])
        if historico_entregas:
            logger.info(f"[Entregas Comp.] Histórico encontrado: {historico_entregas}")
            if nome_mes_comparativo_pt: 
                for item_hist in historico_entregas:
                    if item_hist.get('mes', '').lower() == nome_mes_comparativo_pt:
                        entregues_anterior_val = item_hist.get('quantidade', 0)
                        logger.info(f"[Entregas Comp.] Encontrada quantidade para {nome_mes_comparativo_pt.capitalize()} no histórico: {entregues_anterior_val}")
                        break 
                if entregues_anterior_val == 0 and nome_mes_comparativo_pt: # Log apenas se nome foi encontrado mas qtde não
                    logger.warning(f"[Entregas Comp.] Mês {nome_mes_comparativo_pt.capitalize()} (Num: {mes_comparativo_num}) não encontrado ou com 0 projetos no histórico de entregas.")
            else:
                 logger.warning(f"[Entregas Comp.] Não foi possível mapear o número do mês comparativo ({mes_comparativo_num}) para nome em PT.")
        else:
            logger.warning("[Entregas Comp.] Chave 'historico' não encontrada ou vazia em projetos_entregues.")
            
        # Calcular a diferença absoluta
        diferenca_entregues_abs = entregues_atual - entregues_anterior_val
        
        # Calcular a diferença percentual
        variacao_entregues_pct = 0.0
        if entregues_anterior_val > 0:
            variacao_entregues_pct = round(((entregues_atual - entregues_anterior_val) / entregues_anterior_val) * 100, 1)
        elif entregues_atual > 0: # Anterior era 0, atual não é
            variacao_entregues_pct = 100.0
            
        logger.info(f"[Entregas Comp.] Comparativo calculado. Atual: {entregues_atual}, Anterior: {entregues_anterior_val}, VarAbs: {diferenca_entregues_abs}, VarPct: {variacao_entregues_pct}%") # Log atualizado
        # --- FIM: Calcular comparação de Projetos Entregues --- 

        # --- INÍCIO: Calcular variação de novos projetos (Refatorado) --- 
        if is_visao_atual:
            # Na visão atual, a função _atual já retorna a comparação
            novos_projetos_comparativo = novos_projetos # novos_projetos já contém a comparação
            logger.info(f"[Visão Atual] Usando comparação de novos projetos calculada no Service: {novos_projetos_comparativo['total']}")
        else:
            # Na visão histórica, calculamos a comparação aqui
            logger.info(f"[Visão Histórica] Calculando comparação de novos projetos para {mes_referencia.strftime('%m/%Y')} vs {mes_comparativo.strftime('%m/%Y')}...")
            
            # 'novos_projetos' aqui contém os dados do mês histórico (o 'atual' da comparação)
            novos_projetos_atuais_hist = novos_projetos 
            
            # Carrega dados do mês anterior ao histórico
            novos_projetos_anterior_hist = {'por_squad': {}, 'total': 0} # Default
            fonte_dados_anterior = macro_service._obter_fonte_historica(mes_comparativo.year, mes_comparativo.month) # Usa a função auxiliar
            
            dados_anterior = pd.DataFrame() # Inicializa vazio
            if fonte_dados_anterior:
                logger.info(f"  Determinada fonte para mês comparativo ({mes_comparativo.strftime('%m/%Y')}): {fonte_dados_anterior}")
                try:
                    dados_anterior = macro_service.carregar_dados(fonte=fonte_dados_anterior)
                    if not dados_anterior.empty:
                        novos_projetos_anterior_hist = macro_service.calcular_novos_projetos_mes(dados_anterior, mes_comparativo)
                        logger.info(f"  Novos projetos do mês anterior ({mes_comparativo.strftime('%m/%Y')}) calculados: {novos_projetos_anterior_hist['total']}")
                    else:
                        logger.warning(f"  Não foi possível carregar dados da fonte anterior: {fonte_dados_anterior}")
                except Exception as e_load_ant:
                     logger.error(f"  Erro ao carregar dados anteriores {fonte_dados_anterior}: {e_load_ant}")                 
            else:
                 # Fallback para valores fixos (se necessário)
                 ano_ant_hist = mes_comparativo.year
                 mes_ant_hist = mes_comparativo.month
                 # Adicionar lógica de fallback aqui se precisar, similar à de calcular_novos_projetos_atual
                 logger.warning(f"  Não foi definida/encontrada uma fonte de dados para o mês comparativo: {mes_comparativo.strftime('%m/%Y')}")
            
            # Calcula a estrutura de comparação
            novos_projetos_comparativo = {
                'por_squad': {},
                'total': {
                    'atual': novos_projetos_atuais_hist['total'],
                    'anterior': novos_projetos_anterior_hist['total'],
                    'variacao_pct': 0,
                    'variacao_abs': 0
                }
            }
            squads_para_comparar = ['AZURE', 'M365', 'DATA E POWER', 'CDB'] 
            
            for squad in squads_para_comparar:
                qtd_atual = novos_projetos_atuais_hist['por_squad'].get(squad.upper(), 0) 
                qtd_anterior = novos_projetos_anterior_hist['por_squad'].get(squad.upper(), 0)
                variacao_pct = 0
                variacao_abs = qtd_atual - qtd_anterior # Agora ambos devem ser inteiros
                if qtd_anterior > 0:
                    variacao_pct = round(((qtd_atual - qtd_anterior) / qtd_anterior) * 100, 1)
                elif qtd_atual > 0:
                    variacao_pct = 100.0
                novos_projetos_comparativo['por_squad'][squad] = {
                    'atual': qtd_atual,
                    'anterior': qtd_anterior,
                    'variacao_pct': variacao_pct,
                    'variacao_abs': variacao_abs
                }
                
            total_atual = novos_projetos_comparativo['total']['atual']
            total_anterior = novos_projetos_comparativo['total']['anterior']
            total_variacao_abs = total_atual - total_anterior
            total_variacao_pct = 0
            if total_anterior > 0:
                total_variacao_pct = round(((total_atual - total_anterior) / total_anterior) * 100, 1)
            elif total_atual > 0:
                total_variacao_pct = 100.0
            novos_projetos_comparativo['total']['variacao_pct'] = total_variacao_pct
            novos_projetos_comparativo['total']['variacao_abs'] = total_variacao_abs
            logger.info(f"[Visão Histórica] Comparativo de novos projetos calculado. Atual: {total_atual}, Anterior: {total_anterior}, VarAbs: {total_variacao_abs}")
        
        # --- FIM: Calcular variação de novos projetos (Refatorado) --- 

        # --- INÍCIO: Determinar e Carregar Dados do Mês Comparativo (Anterior) --- 
        # (MOVENDO ESTE BLOCO PARA ANTES DO CÁLCULO DE FATURAMENTO)
        dados_anterior = pd.DataFrame() # Inicializa vazio por segurança
        fonte_dados_anterior = None
        try:
            # Usa a função auxiliar para obter a fonte histórica para o mes_comparativo
            fonte_dados_anterior = macro_service._obter_fonte_historica(mes_comparativo.year, mes_comparativo.month)
            
            if fonte_dados_anterior:
                logger.info(f"Tentando carregar dados para o mês comparativo ({mes_comparativo.strftime('%m/%Y')}) da fonte: {fonte_dados_anterior}")
                dados_anterior = macro_service.carregar_dados(fonte=fonte_dados_anterior)
                if dados_anterior.empty:
                    logger.warning(f"Dados do mês comparativo ({fonte_dados_anterior}) retornaram vazios.")
            else:
                # Se a visão é a ATUAL e não achou fonte histórica, tenta pegar do service (pode ser o caso de comparar com o mês anterior que ainda está no service)
                if is_visao_atual:
                    logger.warning(f"Fonte histórica não encontrada para {mes_comparativo.strftime('%m/%Y')}. Tentando obter dados anteriores via service (Visão Atual).")
                    # Nota: Esta lógica pode precisar ser ajustada dependendo de como o service lida com dados anteriores recentes
                    # Por ora, deixamos dados_anterior vazio se a fonte não for encontrada.
                    pass
                else:
                     logger.warning(f"Fonte histórica não definida/encontrada para o mês comparativo: {mes_comparativo.strftime('%m/%Y')}")

        except Exception as e_load_ant:
            logger.error(f"Erro ao carregar dados do mês comparativo ({mes_comparativo.strftime('%m/%Y')} - Fonte: {fonte_dados_anterior}): {e_load_ant}")
        # --- FIM: Determinar e Carregar Dados do Mês Comparativo (Anterior) --- 

        # --- INÍCIO: Calcular Faturamento dos Projetos Ativos ---
        # (AGORA EXECUTA APÓS CARREGAR dados_anterior)
        try:
            faturamento_ativos = macro_service.calcular_projetos_por_faturamento(dados_ref, mes_ref=mes_referencia)
            logger.info(f"Contagem de faturamento para ativos em {mes_referencia.strftime('%m/%Y')}: {faturamento_ativos.get('contagem')}")
            
            # Calcular também para o mês anterior
            faturamento_ativos_anterior = {'contagem': {}, 'dados': [], 'total': 0}
            # Agora a verificação de dados_anterior deve funcionar
            if 'dados_anterior' in locals() and not dados_anterior.empty:
                 try:
                      faturamento_ativos_anterior = macro_service.calcular_projetos_por_faturamento(dados_anterior, mes_ref=mes_comparativo)
                      logger.info(f"Contagem de faturamento para ativos em {mes_comparativo.strftime('%m/%Y')}: {faturamento_ativos_anterior.get('contagem')}")
                 except Exception as e_fat_ant:
                      logger.error(f"Erro ao calcular faturamento de ativos do mês anterior: {e_fat_ant}")
            else:
                 logger.warning("Dados do mês anterior não disponíveis para cálculo de faturamento comparativo.")
                 
            # Estruturar dados para comparação no template
            faturamento_comparativo = {}
            tipos_faturamento = list(faturamento_ativos.get('contagem', {}).keys()) + \
                                list(faturamento_ativos_anterior.get('contagem', {}).keys())
            tipos_faturamento = sorted(list(set(tipos_faturamento))) # Lista única e ordenada
            
            for tipo in tipos_faturamento:
                 if tipo == 'NAO_MAPEADO': continue # Ignora NAO_MAPEADO na comparação visual
                 
                 atual = faturamento_ativos.get('contagem', {}).get(tipo, 0)
                 anterior = faturamento_ativos_anterior.get('contagem', {}).get(tipo, 0)
                 variacao_abs = atual - anterior # Calcula a diferença absoluta
                 # Formata o texto da variação para exibição no template
                 variacao_texto = ""
                 if variacao_abs != 0:
                     sinal = "+" if variacao_abs > 0 else ""
                     variacao_texto = f"({sinal}{variacao_abs})"
                     
                 faturamento_comparativo[tipo] = {
                     'atual': atual,
                     'anterior': anterior,
                     'variacao_abs': variacao_abs,
                     'variacao_texto': variacao_texto # Adiciona o texto formatado
                 }
            logger.info(f"Estrutura de comparação de faturamento criada: {faturamento_comparativo}")
                 
        except Exception as e_fat:
            logger.error(f"Erro ao calcular faturamento de ativos: {e_fat}")
            faturamento_ativos = {'contagem': {}, 'dados': [], 'total': 0}
            faturamento_comparativo = {} # Estrutura vazia em caso de erro
        # --- FIM: Calcular Faturamento dos Projetos Ativos ---

        # --- INÍCIO: Filtrar dados ativos e Calcular Totais ---
        STATUS_NAO_ATIVOS = ['FECHADO', 'ENCERRADO', 'RESOLVIDO', 'CANCELADO']
        
        # Filtra projetos ativos do mês de referência (dados_ref)
        dados_ativos = pd.DataFrame() # Default
        if 'Status' in dados_ref.columns: # Garante que a coluna existe
             dados_ativos = dados_ref[~dados_ref['Status'].str.upper().isin([s.upper() for s in STATUS_NAO_ATIVOS])].copy()
             logger.info(f"Projetos ativos do mês de referência ({mes_referencia.strftime('%m/%Y')}) filtrados: {len(dados_ativos)}")
        else:
             logger.error(f"Coluna 'Status' não encontrada em dados_ref. Não foi possível filtrar ativos.")

        # Total Atual
        total_ativos_atual = len(dados_ativos)
        
        # Total Anterior (calculado a partir de dados_anterior, se existir)
        total_ativos_anterior = 0
        if 'dados_anterior' in locals() and not dados_anterior.empty and 'Status' in dados_anterior.columns:
            try:
                logger.debug(f"[Debug Ativos Ant] Calculando total_ativos_anterior para {mes_comparativo.strftime('%m/%Y')}. Tamanho dados_anterior: {dados_anterior.shape}")
                # Log a contagem de status antes de filtrar, se possível
                if not dados_anterior.empty:
                    logger.debug(f"[Debug Ativos Ant] Contagem de Status em dados_anterior: {dados_anterior['Status'].value_counts().to_dict()}")
                
                # Aplicar o mesmo filtro de status não ativos
                dados_ativos_anterior = dados_anterior[
                    ~dados_anterior['Status'].str.upper().isin([s.upper() for s in STATUS_NAO_ATIVOS])
                ].copy()
                total_ativos_anterior = len(dados_ativos_anterior)
                logger.info(f"Total de projetos ativos do mês anterior ({mes_comparativo.strftime('%m/%Y')}) calculado: {total_ativos_anterior}") # <<< Check this log output
                logger.debug(f"[Debug Ativos Ant] Tamanho dados_ativos_anterior após filtro: {dados_ativos_anterior.shape}")
            except Exception as e_ativos_ant:
                logger.error(f"Erro ao calcular total de ativos do mês anterior: {e_ativos_ant}")
        elif 'dados_anterior' not in locals() or dados_anterior.empty:
            logger.warning("Dados do mês anterior não disponíveis para calcular total de ativos anterior.")
        else: # dados_anterior existe mas não tem a coluna Status
             logger.error("Coluna 'Status' não encontrada nos dados anteriores. Não foi possível calcular total de ativos anterior.")
        # --- FIM: Filtrar dados ativos e Calcular Totais ---

        # --- INÍCIO: Calcular Agregações por Status/Squad (Usando dados_ativos) --- 
        # (Esta parte agora usa a variável dados_ativos definida acima)
        por_status_squad = {}
        por_status_squad_especialista = {
            'AZURE': {},
            'M365': {},
            'DATA E POWER': {},
            'CDB': {}
        }
        
        # Preenche a estrutura com zeros
        status_para_contar = ['NOVO', 'EM ATENDIMENTO', 'AGUARDANDO', 'BLOQUEADO']
        squads_para_contar = ['AZURE', 'M365', 'DATA E POWER', 'CDB']
        for status in status_para_contar:
            por_status_squad[status] = {squad: 0 for squad in squads_para_contar}
            for squad in squads_para_contar:
                 if squad not in por_status_squad_especialista: # Garante que o squad existe
                     por_status_squad_especialista[squad] = {}
                 por_status_squad_especialista[squad][status] = 0
        
        if not dados_ativos.empty: # Procede apenas se temos dados ativos
            # Itera pelos projetos ativos de dados_ref (agora na variável dados_ativos)
            for _, projeto in dados_ativos.iterrows():
                status = projeto.get('Status', '').upper() # Usa .get com default
                if status not in status_para_contar:
                     continue # Pula se não for um status ativo relevante
                     
                # Squad para agregação geral
                squad_original = projeto.get('Squad')
                squad = str(squad_original).upper() if squad_original and not pd.isna(squad_original) else 'OUTROS'
                target_squad = squad if squad in squads_para_contar else 'OUTROS'
                
                # Conta para a agregação por_status_squad (se target_squad != 'OUTROS')
                if target_squad != 'OUTROS':
                    por_status_squad[status][target_squad] += 1
                
                # Squad para agregação por especialista
                especialista_original = projeto.get('Especialista')
                especialista = str(especialista_original).upper() if especialista_original and not pd.isna(especialista_original) else ''
                
                target_squad_esp = 'OUTROS' # Default
                if especialista == 'CDB DATA SOLUTIONS':
                    target_squad_esp = 'CDB'
                elif squad in squads_para_contar: # Se o squad direto for um dos principais
                     target_squad_esp = squad
                
                # Adiciona à contagem especialista se for um dos squads principais
                if target_squad_esp != 'OUTROS':
                    por_status_squad_especialista[target_squad_esp][status] += 1
            
            logger.info(f"Agregações por status/squad calculadas para {mes_referencia.strftime('%m/%Y')}")
        else:
            logger.warning("DataFrame 'dados_ativos' está vazio, pulando cálculo de agregações por status/squad.")
        # --- FIM: Calcular Agregações por Status/Squad --- 

        # --- INÍCIO: Calcular Agregação Geral por Status (para cards individuais) --- 
        por_status_geral = {status: {'quantidade': 0} for status in status_para_contar}
        for squad_data in por_status_squad_especialista.values():
            for status, count in squad_data.items():
                if status in por_status_geral:
                     por_status_geral[status]['quantidade'] += count
        logger.info(f"Agregação geral por status calculada: {por_status_geral}")
        # --- FIM: Calcular Agregação Geral por Status --- 

        # --- Preparação do Contexto para o Template ---
        # Define as listas de squads e status esperados para o contexto
        squads_para_contar = ['AZURE', 'M365', 'DATA E POWER', 'CDB']
        status_para_contar = ['NOVO', 'EM ATENDIMENTO', 'AGUARDANDO', 'BLOQUEADO']

        # Prepara contexto adicional
        context = {
            # 'comparativo': comparativo, # Removido, dados agora são passados individualmente
            'get_status_color': get_status_color,
            'get_conclusao_color': get_conclusao_color,
            # 'titulo_pagina': f"Apresentação Diretoria - {comparativo['mes_atual']['nome']}", # Substituído
            'titulo_pagina': f"Apresentação Diretoria - {mes_referencia.strftime('%B/%Y')}", # <-- Chave corrigida para aspas simples
            'fonte_dados': fonte_dados_ref if not is_visao_atual else 'dadosr.csv',
            'mes_referencia': mes_referencia.strftime('%B/%Y'), # Usado para exibição
            'nome_mes_comparativo': nome_mes_comparativo_pt.capitalize() if nome_mes_comparativo_pt else 'mês anterior',
            'mes_comparativo_abrev': mes_comparativo.strftime('%b') if mes_comparativo else 'mês ant.',
            'total_ativos_atual': total_ativos_atual,
            'total_ativos_anterior': total_ativos_anterior,
            'agregacoes_por_status': por_status_geral, # <-- Corrigido para usar a variável correta
            'agregacoes_por_status_squad_especialista': por_status_squad_especialista,
            'projetos_entregues': projetos_entregues, # Já contém o 'historico'
            'diferenca_entregues_abs': diferenca_entregues_abs,
            'variacao_entregues_pct': variacao_entregues_pct, # <-- ADICIONADO AO CONTEXTO
            'novos_projetos_comparativo': novos_projetos_comparativo,
            'tempo_medio_vida': tempo_medio_vida_dados,
            'tempo_medio_vida_variacao_pct': variacao_pct_tmv,
            'faturamento_comparativo': faturamento_comparativo,
            'is_visao_atual': is_visao_atual,
            'error': None # Assume sem erro inicialmente
        }
        
        # Calcula totais de squad para os gráficos
        totais_squad = {}
        # Usa as variáveis locais definidas anteriormente
        for squad in squads_para_contar: 
            total = 0
            # Usa a chave correta do contexto e a variável local de status
            for status in status_para_contar: 
                 # O status TOTAL não existe mais na lista, então a verificação if status != 'TOTAL' não é necessária
                 total += context['agregacoes_por_status_squad_especialista'].get(squad, {}).get(status, 0)
            totais_squad[squad] = total
        
        context['totais_squad'] = totais_squad
        
        # --- INÍCIO: Preparar dados para gráficos Javascript ---
        squad_chart_data = [
            totais_squad.get('AZURE', 0),
            totais_squad.get('M365', 0),
            totais_squad.get('DATA E POWER', 0),
            totais_squad.get('CDB', 0)
        ]
        
        tendencia_chart_data = [
            total_ativos_anterior,
            total_ativos_atual
        ]
        
        context['squad_chart_data'] = squad_chart_data
        context['tendencia_chart_data'] = tendencia_chart_data
        # --- FIM: Preparar dados para gráficos Javascript ---

        logger.info(f"Contexto preparado para apresentação - Mês Referência: {mes_referencia.strftime('%B/%Y')}")
        
        return render_template('macro/apresentacao.html', **context)
        
    except Exception as e:
        logger.exception(f"Erro na rota apresentacao: {str(e)}")
        return render_template('macro/erro.html', 
                             error=str(e),
                             titulo="Erro na Apresentação")

@macro_bp.route('/api/projetos-squad-status-mes')
def api_projetos_squad_status_mes():
    """API para obter projetos por squad e status para um mês específico"""
    try:
        # Obtém parâmetros da URL
        squad = request.args.get('squad', '').strip()
        mes = request.args.get('mes', None)
        ano = request.args.get('ano', None)
        
        # Valida os parâmetros
        if not squad:
            return jsonify({'error': 'É necessário especificar um squad'}), 400
            
        # Determina a data de referência
        try:
            if mes and ano:
                mes_referencia = datetime(int(ano), int(mes), 1)
            else:
                # Use o último dia do mês atual se não for especificado
                hoje = datetime.now()
                mes_referencia = hoje
                
            logger.info(f"Obtendo projetos para squad {squad} no mês {mes_referencia.strftime('%m/%Y')}")
        except ValueError as e:
            logger.error(f"Erro nos parâmetros de data: {str(e)}")
            return jsonify({'error': 'Formato de data inválido. Use mes=MM&ano=YYYY'}), 400
        
        # Determina qual fonte de dados usar com base no mês e ano
        fonte_dados = None
        if mes == '3' and ano == '2025':
            fonte_dados = 'dadosr_apt_mar'
            logger.info(f"Usando fonte de dados específica para março/2025: {fonte_dados}")
        elif mes == '2' and ano == '2025':
            fonte_dados = 'dadosr_apt_fev'
            logger.info(f"Usando fonte de dados específica para fevereiro/2025: {fonte_dados}")
        
        # Carrega os dados com a fonte apropriada
        dados = macro_service.carregar_dados(fonte=fonte_dados)
        if dados.empty:
            logger.warning(f"API: Dados vazios ao buscar projetos para squad '{squad}'")
            return jsonify({'error': 'Não foi possível carregar os dados'}), 500
            
        # Obtém os projetos filtrados
        resultado = macro_service.obter_projetos_por_squad_status_mes(dados, squad, mes_referencia)
        
        return jsonify(resultado)
        
    except Exception as e:
        logger.exception(f"Erro na API de projetos por squad e status: {str(e)}")
        return jsonify({'error': str(e)}), 500
