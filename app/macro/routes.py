from flask import Blueprint, render_template, jsonify, request, current_app, redirect, url_for, flash, Response
from . import macro_bp, macro_service
from urllib.parse import unquote
import logging
from datetime import datetime, timedelta
import pandas as pd
from io import BytesIO
import os # Removido para debug - PATH OK
import json
from ..utils.decorators import module_required, feature_required

# Inicializa logger
logger = logging.getLogger(__name__)

# Flags para geradores PDF - imports serão feitos sob demanda para evitar travamento na inicialização
weasyprint_installed = False
pdfkit_installed = False
HTML = None
CSS = None
pdf_generator_available = False

def _check_pdf_generators():
    """Verifica e importa geradores de PDF sob demanda"""
    global weasyprint_installed, pdfkit_installed, HTML, CSS, pdf_generator_available
    
    if pdf_generator_available:
        return True  # Já verificado anteriormente
    
    # Tenta WeasyPrint primeiro
    try:
        from weasyprint import HTML as WeasyHTML, CSS as WeasyCSS
        weasyprint_installed = True
        HTML = WeasyHTML
        CSS = WeasyCSS
        pdf_generator_available = True
        logger.info("WeasyPrint importado com sucesso (sob demanda)")
        return True
    except ImportError as e:
        logger.warning(f"WeasyPrint não disponível: {str(e)}")
    
    # Tenta pdfkit como alternativa
    try:
        import pdfkit
        pdfkit_installed = True
        pdf_generator_available = True
        logger.info("pdfkit importado como alternativa (sob demanda)")
        return True
    except ImportError as e:
        logger.warning(f"pdfkit também não disponível: {str(e)}")
    
    logger.warning("Nenhum gerador de PDF disponível")
    return False

# Use o logger configurado no app factory (se aplicável)
# logger = current_app.logger
# Ou use o logger do módulo se não estiver usando app factory / current_app
# logger já foi definido acima

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
@module_required('macro')
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
        eficiencia_entrega = macro_service.calcular_eficiencia_entrega(dados_combinados_dash) # Usa dados dos últimos 3 meses
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

@macro_bp.route('/relatorio/ativos')
def relatorio_projetos_ativos():
    """Rota para o relatório de projetos ativos com funcionalidades de exportação"""
    try:
        logger.info("Acessando relatório de projetos ativos")
        
        # Carrega dados atuais
        dados_atuais = macro_service.carregar_dados(fonte=None)
        
        if dados_atuais.empty:
            logger.warning("Dados vazios para o relatório de projetos ativos")
            return render_template('macro/relatorio_projetos_ativos.html', 
                                 title="Relatório de Projetos Ativos",
                                 error="Nenhum dado disponível para exibição",
                                 hora_atualizacao=datetime.now())
        
        # Prepara contexto para o template
        context = {
            'title': 'Relatório de Projetos Ativos',
            'hora_atualizacao': datetime.now()
        }
        
        logger.info(f"Renderizando relatório de projetos ativos com {len(dados_atuais)} registros")
        return render_template('macro/relatorio_projetos_ativos.html', **context)
        
    except Exception as e:
        logger.exception(f"Erro na rota relatorio_projetos_ativos: {str(e)}")
        return render_template('macro/relatorio_projetos_ativos.html', 
                             title="Relatório de Projetos Ativos",
                             error=str(e),
                             hora_atualizacao=datetime.now())

@macro_bp.route('/relatorio/criticos')
def relatorio_projetos_criticos():
    """Rota para o relatório de projetos críticos com funcionalidades de exportação"""
    try:
        logger.info("Acessando relatório de projetos críticos")
        
        # Carrega dados atuais
        dados_atuais = macro_service.carregar_dados(fonte=None)
        
        if dados_atuais.empty:
            logger.warning("Dados vazios para o relatório de projetos críticos")
            return render_template('macro/relatorio_projetos_criticos.html', 
                                 title="Relatório de Projetos Críticos",
                                 error="Nenhum dado disponível para exibição",
                                 hora_atualizacao=datetime.now())
        
        # Prepara contexto para o template
        context = {
            'title': 'Relatório de Projetos Críticos',
            'hora_atualizacao': datetime.now()
        }
        
        logger.info(f"Renderizando relatório de projetos críticos com {len(dados_atuais)} registros")
        return render_template('macro/relatorio_projetos_criticos.html', **context)
        
    except Exception as e:
        logger.exception(f"Erro na rota relatorio_projetos_criticos: {str(e)}")
        return render_template('macro/relatorio_projetos_criticos.html', 
                             title="Relatório de Projetos Críticos",
                             error=str(e),
                             hora_atualizacao=datetime.now())

# === NOVA ABA DE RELATÓRIOS ===

@macro_bp.route('/relatorios')
@feature_required('macro.suite_relatorios')
def relatorios_dashboard():
    """Dashboard principal da aba de relatórios"""
    try:
        logger.info("Acessando dashboard de relatórios")
        
        # Prepara contexto para o template
        context = {
            'title': 'Relatórios Macro',
            'hora_atualizacao': datetime.now()
        }
        
        return render_template('macro/relatorios_dashboard.html', **context)
        
    except Exception as e:
        logger.exception(f"Erro na rota relatorios_dashboard: {str(e)}")
        return render_template('macro/relatorios_dashboard.html', 
                             title="Relatórios Macro",
                             error=str(e),
                             hora_atualizacao=datetime.now())

@macro_bp.route('/relatorios/geral')
@feature_required('macro.suite_relatorios')
def relatorio_geral():
    """Página de seleção de meses para o relatório geral"""
    try:
        logger.info("Acessando seleção de relatório geral")
        
        # Obter fontes disponíveis para seleção
        fontes_disponiveis = macro_service.obter_fontes_disponiveis()
        
        context = {
            'title': 'Relatório Geral - Seleção de Período',
            'fontes_disponiveis': fontes_disponiveis,
            'hora_atualizacao': datetime.now()
        }
        
        return render_template('macro/relatorio_geral_selecao.html', **context)
        
    except Exception as e:
        logger.exception(f"Erro na rota relatorio_geral: {str(e)}")
        return render_template('macro/relatorio_geral_selecao.html', 
                             title="Relatório Geral - Seleção de Período",
                             error=str(e),
                             hora_atualizacao=datetime.now())

@macro_bp.route('/relatorios/geral/gerar', methods=['POST'])
@feature_required('macro.suite_relatorios')
def gerar_relatorio_geral():
    """Gera o relatório geral com base nos meses selecionados e filtros aplicados"""
    try:
        # Obtém os meses selecionados do formulário
        meses_selecionados = request.form.getlist('meses_selecionados[]')
        
        if not meses_selecionados:
            logger.warning("Nenhum mês selecionado para o relatório geral")
            return redirect(url_for('macro.relatorio_geral'))
        
        # Coleta filtros avançados
        filtros = {
            'data_abertura_inicio': request.form.get('data_abertura_inicio'),
            'data_abertura_fim': request.form.get('data_abertura_fim'),
            'data_fechamento_inicio': request.form.get('data_fechamento_inicio'),
            'data_fechamento_fim': request.form.get('data_fechamento_fim'),
            'squad': request.form.get('filtro_squad'),
            'servico': request.form.get('filtro_servico'),
            'categoria': request.form.get('filtro_categoria'),
            'status': request.form.get('filtro_status'),
            'faturamento': request.form.get('filtro_faturamento')
        }
        
        # Remove filtros vazios
        filtros = {k: v for k, v in filtros.items() if v and str(v).strip()}
        
        logger.info(f"Gerando relatório geral para os meses: {meses_selecionados}")
        if filtros:
            logger.info(f"Filtros aplicados: {filtros}")
        
        # Passa os meses selecionados e filtros como parâmetros
        meses_param = ','.join(meses_selecionados)
        
        context = {
            'title': 'Relatório Geral de Projetos',
            'meses_selecionados': meses_param,
            'filtros_aplicados': json.dumps(filtros) if filtros else '{}',
            'categoria_filtrada': filtros.get('categoria') if filtros else None,
            'hora_atualizacao': datetime.now()
        }
        
        return render_template('macro/relatorio_geral.html', **context)
        
    except Exception as e:
        logger.exception(f"Erro ao gerar relatório geral: {str(e)}")
        return redirect(url_for('macro.relatorio_geral'))

@macro_bp.route('/relatorios/entregues')
@feature_required('macro.suite_relatorios')
def relatorio_projetos_entregues():
    """Rota para o relatório de projetos entregues"""
    try:
        logger.info("Acessando relatório de projetos entregues")
        
        # Carrega dados atuais
        dados_atuais = macro_service.carregar_dados(fonte=None)
        
        if dados_atuais.empty:
            logger.warning("Dados vazios para o relatório de projetos entregues")
            return render_template('macro/relatorio_projetos_entregues.html', 
                                 title="Relatório de Projetos Entregues",
                                 error="Nenhum dado disponível para exibição",
                                 hora_atualizacao=datetime.now())
        
        # Prepara contexto para o template
        context = {
            'title': 'Relatório de Projetos Entregues',
            'hora_atualizacao': datetime.now()
        }
        
        logger.info(f"Renderizando relatório de projetos entregues com {len(dados_atuais)} registros")
        return render_template('macro/relatorio_projetos_entregues.html', **context)
        
    except Exception as e:
        logger.exception(f"Erro na rota relatorio_projetos_entregues: {str(e)}")
        return render_template('macro/relatorio_projetos_entregues.html', 
                             title="Relatório de Projetos Entregues",
                             error=str(e),
                             hora_atualizacao=datetime.now())

# === APIs PARA OS NOVOS RELATÓRIOS ===

@macro_bp.route('/api/projetos/entregues')
@feature_required('macro.suite_relatorios')
def get_projetos_entregues():
    """API para obter projetos entregues"""
    try:
        logger.info("API: Carregando projetos entregues")
        dados = macro_service.carregar_dados()
        
        if dados.empty:
            logger.warning("Dados vazios para projetos entregues")
            return jsonify([])
        
        # Usa a função específica para calcular projetos concluídos (que filtra pelo mês atual)
        resultado_projetos = macro_service.calcular_projetos_concluidos(dados)
        projetos_entregues = resultado_projetos.get('dados', [])
        
        # Se for DataFrame, converte para lista de dicionários
        if hasattr(projetos_entregues, 'to_dict'):
            projetos_entregues = projetos_entregues.to_dict('records')
        
        # Formata os dados igual ao Relatório Geral
        dados_formatados = []
        for projeto in projetos_entregues:
            # Tratamento de horas com formatação padrão (dados já vêm formatados do service)
            horas_trabalhadas = projeto.get('horasTrabalhadas', projeto.get('HorasTrabalhadas', 0))
            horas_previstas = projeto.get('horasContratadas', projeto.get('Horas', 0))
            
            # Os dados já vêm formatados corretamente do service calcular_projetos_concluidos
            # Mas garantimos a consistência
            try:
                horas_trabalhadas = round(float(horas_trabalhadas), 2) if horas_trabalhadas else 0.0
                horas_previstas = round(float(horas_previstas), 2) if horas_previstas else 0.0
            except (ValueError, TypeError):
                horas_trabalhadas = 0.0
                horas_previstas = 0.0
            
            # Padroniza campos de texto para "-" quando vazios
            def padronizar_campo(valor):
                if valor in [None, 'N/A', 'NÃO DEFINIDO', 'NÃO ALOCADO', '']:
                    return '-'
                return valor
            
            dados_formatados.append({
                'numero': projeto.get('numero', projeto.get('Numero', '-')),
                'projeto': padronizar_campo(projeto.get('projeto', projeto.get('Projeto'))),
                'squad': padronizar_campo(projeto.get('squad', projeto.get('Squad'))),
                'servico': padronizar_campo(projeto.get('servico', projeto.get('Servico'))),
                'status': padronizar_campo(projeto.get('status', projeto.get('Status'))),
                'tipo_faturamento': padronizar_campo(projeto.get('tipo_faturamento', projeto.get('Faturamento'))),
                'horas_trabalhadas': horas_trabalhadas,
                'horas_previstas': horas_previstas,
                'conclusao': projeto.get('conclusao', projeto.get('Conclusao', 0)),
                'data_entrega': projeto.get('dataTermino', projeto.get('DataTermino', '-')),
                'especialista': padronizar_campo(projeto.get('especialista', projeto.get('Especialista'))),
                'account': padronizar_campo(projeto.get('account', projeto.get('Account Manager'))),
                'backlog_exists': projeto.get('backlog_exists', False)
            })
        
        logger.info(f"API: Retornando {len(dados_formatados)} projetos entregues formatados")
        return jsonify(dados_formatados)
        
    except Exception as e:
        logger.exception(f"Erro na API de projetos entregues: {str(e)}")
        return jsonify([])

@macro_bp.route('/api/projetos/entregues/todos')
@feature_required('macro.suite_relatorios')
def get_todos_projetos_entregues():
    """API para obter todos os projetos entregues (histórico completo)"""
    try:
        logger.info("API: Carregando todos os projetos entregues")
        dados = macro_service.carregar_dados()
        
        if dados.empty:
            logger.warning("Dados vazios para todos os projetos entregues")
            return jsonify([])
        
        # Usa dados já tratados
        dados_base = macro_service.preparar_dados_base(dados)
        
        # Filtra TODOS os projetos concluídos (sem filtro de data) e exclui CDB DATA SOLUTIONS
        todos_projetos_entregues = dados_base[
            (dados_base['Status'].isin(macro_service.status_concluidos)) &
            (dados_base['Squad'] != 'CDB DATA SOLUTIONS')
        ].copy()
        
        # Adiciona verificação de backlog
        todos_projetos_entregues = macro_service._adicionar_verificacao_backlog(todos_projetos_entregues)
        
        # Converte para lista de dicionários
        if hasattr(todos_projetos_entregues, 'to_dict'):
            projetos_lista = todos_projetos_entregues.to_dict('records')
        else:
            projetos_lista = todos_projetos_entregues
        
        # Formata os dados igual ao Relatório Geral
        dados_formatados = []
        for projeto in projetos_lista:
            # Tratamento de horas com formatação padrão
            horas_trabalhadas = projeto.get('HorasTrabalhadas', projeto.get('horas_trabalhadas', 0))
            horas_previstas = projeto.get('Horas', projeto.get('horas_previstas', 0))
            conclusao = projeto.get('Conclusao', projeto.get('conclusao', 0))
            
            # Formatação numérica igual ao Relatório Geral
            try:
                horas_trabalhadas = round(float(horas_trabalhadas), 2) if horas_trabalhadas else 0.0
                horas_previstas = round(float(horas_previstas), 2) if horas_previstas else 0.0
                conclusao = round(float(conclusao), 1) if conclusao else 0.0
                conclusao = max(0, min(100, conclusao))  # Limita entre 0-100
            except (ValueError, TypeError):
                horas_trabalhadas = 0.0
                horas_previstas = 0.0
                conclusao = 0.0
            
            # Formatação de data igual ao Relatório Geral
            data_entrega = projeto.get('DataTermino', projeto.get('data_entrega', 'N/A'))
            if data_entrega and data_entrega != 'N/A':
                try:
                    import pandas as pd
                    data_formatada = pd.to_datetime(data_entrega, errors='coerce')
                    if pd.notna(data_formatada):
                        data_entrega = data_formatada.strftime('%d/%m/%Y')
                    else:
                        data_entrega = '-'
                except:
                    data_entrega = '-'
            
            # Padroniza campos de texto para "-" quando vazios
            def padronizar_campo(valor):
                if valor in [None, 'N/A', 'NÃO DEFINIDO', 'NÃO ALOCADO', '']:
                    return '-'
                return valor
            
            dados_formatados.append({
                'numero': projeto.get('Numero', projeto.get('numero', '-')),
                'projeto': padronizar_campo(projeto.get('Projeto', projeto.get('projeto'))),
                'squad': padronizar_campo(projeto.get('Squad', projeto.get('squad'))),
                'servico': padronizar_campo(projeto.get('Servico', projeto.get('servico'))),
                'status': padronizar_campo(projeto.get('Status', projeto.get('status'))),
                'tipo_faturamento': padronizar_campo(projeto.get('Faturamento', projeto.get('tipo_faturamento'))),
                'horas_trabalhadas': horas_trabalhadas,
                'horas_previstas': horas_previstas,
                'conclusao': conclusao,
                'data_entrega': data_entrega,
                'especialista': padronizar_campo(projeto.get('Especialista', projeto.get('especialista'))),
                'account': padronizar_campo(projeto.get('Account Manager', projeto.get('account'))),
                'backlog_exists': projeto.get('backlog_exists', False)
            })
        
        logger.info(f"API: Retornando {len(dados_formatados)} projetos entregues (histórico completo)")
        return jsonify(dados_formatados)
        
    except Exception as e:
        logger.exception(f"Erro na API de todos os projetos entregues: {str(e)}")
        return jsonify([])

@macro_bp.route('/api/filter-options')
def api_filter_options():
    """API para obter opções dos filtros do relatório geral"""
    try:
        dados = macro_service.carregar_dados()
        
        if dados.empty:
            return jsonify({'success': False, 'message': 'Dados não disponíveis'})
        
        # Obtém valores únicos para os filtros básicos
        squads = sorted(dados['Squad'].dropna().unique().tolist()) if 'Squad' in dados.columns else []
        servicos = sorted(dados['TipoServico'].dropna().unique().tolist()) if 'TipoServico' in dados.columns else []
        faturamentos = sorted(dados['Faturamento'].dropna().unique().tolist()) if 'Faturamento' in dados.columns else []
        
        # Remove valores vazios e limpa dados
        squads = [s for s in squads if s and str(s).strip() != '']
        servicos = [s for s in servicos if s and str(s).strip() != '']
        faturamentos = [f for f in faturamentos if f and str(f).strip() != '']
        
        # Obtém categorias dos tipos de serviço usando o TypeServiceReader
        categorias = []
        if servicos:
            try:
                from .typeservice_reader import TypeServiceReader
                reader = TypeServiceReader()
                categorias_disponiveis = reader.obter_categorias_disponiveis()
                categorias = sorted(categorias_disponiveis)
                logger.info(f"Categorias carregadas: {len(categorias)}")
            except Exception as e:
                logger.warning(f"Erro ao carregar categorias: {str(e)}")
                categorias = []
        
        return jsonify({
            'success': True,
            'squads': squads,
            'servicos': servicos,
            'faturamentos': faturamentos,
            'categorias': categorias
        })
        
    except Exception as e:
        logger.exception(f"Erro ao obter opções de filtros: {str(e)}")
        return jsonify({'success': False, 'message': 'Erro interno do servidor'})

@macro_bp.route('/api/relatorio/geral')
def api_relatorio_geral_dados():
    """
    API para fornecer os dados para o Relatório Geral.
    Carrega os dados dos meses selecionados, aplica os filtros e retorna
    os dados consolidados (mostrando a entrada mais recente de cada projeto).
    """
    meses_selecionados_str = request.args.get('meses', '')
    filtros_json = request.args.get('filtros')  # Pega o valor sem default

    # Garante que filtros_json seja um JSON válido, mesmo se estiver vazio ou ausente
    if not filtros_json:
        filtros_json = '{}'
    
    logger.info(f"API Relatório Geral chamada com meses: {meses_selecionados_str} e filtros: {filtros_json}")

    meses = unquote(meses_selecionados_str).split(',') if meses_selecionados_str else []
    filtros_dict = json.loads(unquote(filtros_json))

    if not meses:
        logger.warning("Nenhum mês selecionado para o relatório.")
        return jsonify([])

    # Carrega dados de todos os meses selecionados
    try:
        dataframes_periodo = []
        
        for mes in meses:
            mes = mes.strip()
            if mes == 'atual':
                # Carrega dados atuais (dadosr.csv)
                dados_mes = macro_service.carregar_dados(fonte=None)
                if not dados_mes.empty:
                    dados_mes['Período'] = 'atual'
                    dataframes_periodo.append(dados_mes)
                    logger.info(f"Dados atuais carregados: {len(dados_mes)} registros")
            else:
                # Carrega dados históricos (ex: dadosr_apt_mai)
                dados_mes = macro_service.carregar_dados(fonte=mes)
                if not dados_mes.empty:
                    dados_mes['Período'] = mes
                    dataframes_periodo.append(dados_mes)
                    logger.info(f"Dados históricos '{mes}' carregados: {len(dados_mes)} registros")
        
        if not dataframes_periodo:
            logger.warning("Nenhum dado foi carregado para os meses selecionados.")
            return jsonify([])
        
        # Combina todos os dados
        dados_relatorio = pd.concat(dataframes_periodo, ignore_index=True)
        logger.info(f"Total de dados combinados: {len(dados_relatorio)} registros")
        
        # Aplica filtros se existirem
        if filtros_dict:
            dados_relatorio = macro_service.aplicar_filtros_relatorio(dados_relatorio, filtros_dict)
            logger.info(f"Dados após filtros: {len(dados_relatorio)} registros")
        
        if dados_relatorio.empty:
            logger.info("Nenhum dado encontrado após a filtragem.")
            return jsonify([])

        # --- Lógica de Consolidação ---
        # Garante que 'Período' exista e cria uma chave para ordenação
        if 'Período' in dados_relatorio.columns:
            # Converte 'Período' para um formato de data. 'atual' recebe uma data futura para ficar no topo da ordenação.
            dados_relatorio['sort_key'] = pd.to_datetime(
                dados_relatorio['Período'].apply(lambda x: x if x != 'atual' else '2999-12'),
                format='%Y-%m',
                errors='coerce'
            )
        else:
            # Fallback se a coluna 'Período' não existir
            dados_relatorio['sort_key'] = pd.Timestamp.now()

        # Ordena pelo ID do projeto e pela data (sort_key)
        if 'Numero' in dados_relatorio.columns:
            dados_relatorio.sort_values(by=['Numero', 'sort_key'], ascending=[True, True], inplace=True)
            # Mantém apenas a última ocorrência de cada projeto, que é a mais recente
            dados_consolidados_df = dados_relatorio.drop_duplicates(subset=['Numero'], keep='last')
        else:
            # Fallback se não houver coluna Numero
            dados_consolidados_df = dados_relatorio
        
        # Remove a coluna temporária usada para ordenação
        dados_consolidados_df = dados_consolidados_df.drop(columns=['sort_key'])

        # === FORMATAÇÃO E AJUSTE DE DADOS ===
        
        # Calcula tempo de vida se não existir
        if 'TempoVida' not in dados_consolidados_df.columns and 'DataInicio' in dados_consolidados_df.columns:
            def calcular_dias_vida(data_inicio):
                try:
                    if pd.isna(data_inicio):
                        return None
                    hoje = pd.Timestamp.now()
                    if isinstance(data_inicio, str):
                        data_inicio = pd.to_datetime(data_inicio, errors='coerce')
                    if pd.isna(data_inicio):
                        return None
                    dias = (hoje - data_inicio).days
                    return max(0, dias)  # Não permite dias negativos
                except:
                    return None
            
            dados_consolidados_df['TempoVida'] = dados_consolidados_df['DataInicio'].apply(calcular_dias_vida)
        
        # Formata datas para o formato brasileiro
        colunas_data = ['DataInicio', 'VencimentoEm', 'DataTermino']
        for col in colunas_data:
            if col in dados_consolidados_df.columns:
                dados_consolidados_df[col] = pd.to_datetime(dados_consolidados_df[col], errors='coerce')
                dados_consolidados_df[col] = dados_consolidados_df[col].dt.strftime('%d/%m/%Y')
                dados_consolidados_df[col] = dados_consolidados_df[col].replace('NaT', None)
        
        # Garante que valores numéricos estão formatados corretamente
        colunas_numericas = ['Horas', 'HorasTrabalhadas', 'HorasRestantes']
        for col in colunas_numericas:
            if col in dados_consolidados_df.columns:
                dados_consolidados_df[col] = pd.to_numeric(dados_consolidados_df[col], errors='coerce').fillna(0)
                dados_consolidados_df[col] = dados_consolidados_df[col].round(2)
        
        # Garante que Conclusao (porcentagem) está entre 0 e 100
        if 'Conclusao' in dados_consolidados_df.columns:
            dados_consolidados_df['Conclusao'] = pd.to_numeric(dados_consolidados_df['Conclusao'], errors='coerce').fillna(0)
            dados_consolidados_df['Conclusao'] = dados_consolidados_df['Conclusao'].clip(0, 100).round(1)
        
        # Limpa valores de texto
        colunas_texto = ['Cliente', 'Projeto', 'Squad', 'TipoServico', 'Especialista', 'Account Manager', 'Faturamento']
        for col in colunas_texto:
            if col in dados_consolidados_df.columns:
                dados_consolidados_df[col] = dados_consolidados_df[col].astype(str).str.strip()
                dados_consolidados_df[col] = dados_consolidados_df[col].replace(['nan', 'NaN', 'None', ''], None)
        
        # === ADIÇÃO DE INFORMAÇÕES DE CATEGORIA ===
        # Adiciona coluna de categoria se há filtro por categoria ou sempre para referência
        categoria_filtrada = None
        if filtros_dict and 'categoria' in filtros_dict and filtros_dict['categoria']:
            categoria_filtrada = filtros_dict['categoria']
        
        # Sempre adiciona informação de categoria para cada serviço
        if 'TipoServico' in dados_consolidados_df.columns:
            try:
                from .typeservice_reader import TypeServiceReader
                reader = TypeServiceReader()
                
                # Adiciona coluna com a categoria de cada serviço
                dados_consolidados_df['Categoria'] = dados_consolidados_df['TipoServico'].apply(
                    lambda servico: reader.obter_categoria(servico) if servico else 'N/A'
                )
                
                # Se há filtro de categoria, adiciona também uma coluna de indicação
                if categoria_filtrada:
                    dados_consolidados_df['CategoriaSelecionada'] = categoria_filtrada
                    logger.info(f"Adicionada informação de categoria filtrada: {categoria_filtrada}")
                
            except Exception as e:
                logger.warning(f"Erro ao adicionar informações de categoria: {str(e)}")
                # Fallback: adiciona coluna vazia
                dados_consolidados_df['Categoria'] = 'N/A'
        
        # Prepara dados para o frontend (renomeia colunas para compatibilidade)
        colunas_frontend = {
            'Numero': 'Nº',
            'Cliente': 'Cliente',
            'Squad': 'Squad',
            'TipoServico': 'Serviço',
            'Categoria': 'Categoria',
            'Status': 'Status',
            'Horas': 'Esforço',
            'HorasTrabalhadas': 'H. Trab.',
            'HorasRestantes': 'H. Rest.',
            'Faturamento': 'Faturamento',
            'DataInicio': 'Abertura',
            'VencimentoEm': 'Vencimento',
            'DataTermino': 'Resolvido',
            'Account Manager': 'Account Manager',
            'TempoVida': 'Dias',
            'Conclusao': 'Conclusão'
        }
        
        # Renomeia apenas as colunas que existem
        colunas_para_renomear = {k: v for k, v in colunas_frontend.items() if k in dados_consolidados_df.columns}
        dados_consolidados_df.rename(columns=colunas_para_renomear, inplace=True)
        
        # Substitui valores NaN por None para melhor serialização JSON
        dados_consolidados_df = dados_consolidados_df.where(pd.notnull(dados_consolidados_df), None)

        logger.info(f"Dados consolidados com sucesso. Total de {len(dados_consolidados_df)} projetos únicos retornados.")
        
        json_result = dados_consolidados_df.to_json(orient='records', date_format='iso')
        return Response(json_result, mimetype='application/json')

    except Exception as e:
        logger.error(f"Erro ao processar dados consolidados no relatório geral: {e}", exc_info=True)
        return jsonify({"error": "Erro interno ao processar os dados."}), 500

@macro_bp.route('/api/especialistas')
def api_especialistas():
    """Retorna uma lista de especialistas e seus projetos."""
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
    """⚡ OTIMIZADO: API para filtro de dados com cache agressivo"""
    import time
    start_time = time.time()
    
    try:
        # 🚀 CACHE API: Verificar cache primeiro
        from .services import _get_cached_api_result, _set_cached_api_result
        cache_key = 'api_filter'
        cached_result = _get_cached_api_result(cache_key)
        
        if cached_result is not None:
            cache_time = (time.time() - start_time) * 1000
            logger.info(f"⚡ API CACHE HIT: filter em {cache_time:.1f}ms")
            return jsonify(cached_result)
        
        # 📊 CARREGAMENTO DE DADOS
        logger.info("📊 API filter: carregando dados...")
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
        
        # 🔧 CORREÇÃO: Garante que todos os valores são JSON-serializáveis
        def sanitize_for_json(obj):
            """Remove valores NaN e outros problemas de serialização JSON"""
            import numpy as np
            if isinstance(obj, dict):
                return {k: sanitize_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [sanitize_for_json(item) for item in obj]
            elif pd.isna(obj) or (isinstance(obj, float) and np.isnan(obj)):
                return None
            elif obj == float('inf') or obj == float('-inf'):
                return None
            return obj
        
        agregacoes_sanitized = sanitize_for_json(agregacoes)
        
        # 💾 CACHE RESULTADO
        _set_cached_api_result(cache_key, agregacoes_sanitized)
        
        # Retorna o objeto com dados filtrados
        total_time = (time.time() - start_time) * 1000
        logger.info(f"✅ API filter: {total_time:.1f}ms (Status: {list(por_status_filtrado.keys())}, Riscos: {len(agregacoes_sanitized.get('projetos_risco', []))})")
        return jsonify(agregacoes_sanitized)
    
    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(f"❌ ERRO API filter ({total_time:.1f}ms): {str(e)}")
        # Retorna estrutura mínima garantida apenas com os status desejados
        fallback_result = {
            'por_status': {
                'NOVO': {'quantidade': 0, 'horas_totais': 0.0, 'conclusao_media': 0.0, 'cor': 'info'},
                'EM ATENDIMENTO': {'quantidade': 0, 'horas_totais': 0.0, 'conclusao_media': 0.0, 'cor': 'primary'},
                'AGUARDANDO': {'quantidade': 0, 'horas_totais': 0.0, 'conclusao_media': 0.0, 'cor': 'warning'},
                'BLOQUEADO': {'quantidade': 0, 'horas_totais': 0.0, 'conclusao_media': 0.0, 'cor': 'dark'},
                'FECHADO': {'quantidade': 0, 'horas_totais': 0.0, 'conclusao_media': 0.0, 'cor': 'success'}
            },
            'projetos_risco': []
        }
        return jsonify(fallback_result)

# ⚡ ROTA DE CACHE MANAGEMENT
@macro_bp.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """🗑️ Limpa todos os caches do MacroService para desenvolvimento"""
    try:
        from .services import _MACRO_CACHE
        
        # Backup dos TTLs
        old_data_ttl = _MACRO_CACHE['ttl_seconds']
        old_project_ttl = _MACRO_CACHE['project_cache_ttl']
        old_api_ttl = _MACRO_CACHE['api_cache_ttl']
        
        # Limpa todos os caches
        _MACRO_CACHE['dados'] = None
        _MACRO_CACHE['timestamp'] = None
        _MACRO_CACHE['project_details_cache'] = {}
        _MACRO_CACHE['api_cache'] = {}
        _MACRO_CACHE['processing_lock'] = False
        
        cache_info = {
            'status': 'success',
            'message': 'Todos os caches foram limpos',
            'caches_cleared': ['dados', 'project_details', 'api_results'],
            'ttl_config': {
                'dados_ttl': old_data_ttl,
                'projects_ttl': old_project_ttl,
                'api_ttl': old_api_ttl
            },
            'timestamp': time.time()
        }
        
        logger.info("🗑️ Cache do MacroService limpo manualmente via API")
        return jsonify(cache_info)
        
    except Exception as e:
        logger.error(f"❌ Erro ao limpar cache: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@macro_bp.route('/api/cache/status', methods=['GET'])
def cache_status():
    """📊 Mostra status atual do cache"""
    try:
        from .services import _MACRO_CACHE, _is_cache_valid
        import time
        
        now = time.time()
        
        # Status do cache principal
        data_valid = _is_cache_valid()
        data_age = (now - _MACRO_CACHE['timestamp']) if _MACRO_CACHE['timestamp'] else None
        
        # Status dos caches de projeto
        project_count = len(_MACRO_CACHE['project_details_cache'])
        
        # Status dos caches de API
        api_count = len(_MACRO_CACHE['api_cache'])
        
        status_info = {
            'main_cache': {
                'valid': data_valid,
                'has_data': _MACRO_CACHE['dados'] is not None,
                'age_seconds': round(data_age, 2) if data_age else None,
                'ttl_seconds': _MACRO_CACHE['ttl_seconds']
            },
            'project_cache': {
                'count': project_count,
                'ttl_seconds': _MACRO_CACHE['project_cache_ttl']
            },
            'api_cache': {
                'count': api_count,
                'keys': list(_MACRO_CACHE['api_cache'].keys()),
                'ttl_seconds': _MACRO_CACHE['api_cache_ttl']
            },
            'processing_lock': _MACRO_CACHE['processing_lock'],
            'timestamp': now
        }
        
        logger.info(f"📊 Cache status: Data={data_valid}, Projects={project_count}, APIs={api_count}")
        return jsonify(status_info)
        
    except Exception as e:
        logger.error(f"❌ Erro ao verificar status do cache: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

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
        else:
            # Garante que 'Numero' seja string para a consulta do backlog
            dados_especialista['Numero'] = dados_especialista['Numero'].astype(str)

        # <<< INÍCIO: Adicionar verificação de backlog >>>
        if not dados_especialista.empty and 'Numero' in dados_especialista.columns:
            # Pega todos os IDs de projeto (números) únicos e não vazios
            project_ids = dados_especialista['Numero'].dropna().unique().tolist()
            project_ids = [pid for pid in project_ids if pid]  # Remove vazios

            if project_ids:
                # Consulta o banco para ver quais IDs têm backlog
                try:
                    from app.models import Backlog
                    from app import db
                    
                    backlogs_existentes = db.session.query(Backlog.project_id)\
                                                    .filter(Backlog.project_id.in_(project_ids))\
                                                    .all()
                    # Cria um set com os IDs que têm backlog para busca rápida
                    ids_com_backlog = {result[0] for result in backlogs_existentes}
                    logger.info(f"Encontrados {len(ids_com_backlog)} backlogs para {len(project_ids)} projetos do especialista verificados.")
                    
                    # Adiciona a coluna 'backlog_exists' ao DataFrame
                    dados_especialista['backlog_exists'] = dados_especialista['Numero'].apply(
                        lambda pid: pid in ids_com_backlog if pd.notna(pid) else False
                    )

                except Exception as db_error:
                    logger.error(f"Erro ao consultar backlogs existentes: {db_error}", exc_info=True)
                    # Se der erro no DB, assume que nenhum backlog existe para não quebrar
                    dados_especialista['backlog_exists'] = False
            else:
                logger.info("Nenhum ID de projeto válido encontrado para verificar backlog.")
                dados_especialista['backlog_exists'] = False
        else:
            logger.info("DataFrame vazio ou sem coluna 'Numero'. Pulando verificação de backlog.")
            if 'Numero' in dados_especialista.columns:
                dados_especialista['backlog_exists'] = False
        # <<< FIM: Adicionar verificação de backlog >>>

        # Usar a função _formatar_projetos para manter consistência
        projetos = macro_service._formatar_projetos(dados_especialista)
        
        logger.info(f"API: Encontrados {len(projetos)} projetos ativos para '{nome_decodificado}'.")
        return jsonify(projetos)

    except Exception as e:
        logger.exception(f"API: Erro ao buscar projetos para '{nome_decodificado}': {str(e)}")
        return jsonify({"error": f"Erro ao buscar projetos para {nome_decodificado}"}), 500

@macro_bp.route('/api/projetos/ativos')
def get_projetos_ativos():
    """⚡ OTIMIZADO: Retorna lista de projetos ativos com cache agressivo"""
    import time
    start_time = time.time()
    
    try:
        # 🚀 CACHE API: Verificar cache primeiro
        from .services import _get_cached_api_result, _set_cached_api_result
        cache_key = 'projetos_ativos'
        cached_result = _get_cached_api_result(cache_key)
        
        if cached_result is not None:
            cache_time = (time.time() - start_time) * 1000
            logger.info(f"⚡ API CACHE HIT: projetos/ativos em {cache_time:.1f}ms")
            return jsonify(cached_result)
        
        # 📊 CARREGAMENTO DE DADOS
        dados = macro_service.carregar_dados()
        
        if dados.empty:
            logger.warning("❌ Dados vazios para projetos ativos")
            return jsonify([])

        # 🔄 PROCESSAMENTO
        process_start = time.time()
        projetos_ativos = macro_service.calcular_projetos_ativos(dados)
        result = projetos_ativos['dados'].to_dict('records')
        process_time = (time.time() - process_start) * 1000
        
        # 💾 CACHE RESULTADO
        _set_cached_api_result(cache_key, result)
        
        total_time = (time.time() - start_time) * 1000
        logger.info(f"✅ API projetos/ativos: {total_time:.1f}ms ({len(result)} projetos, proc: {process_time:.1f}ms)")
        
        return jsonify(result)
        
    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(f"❌ ERRO API projetos/ativos ({total_time:.1f}ms): {str(e)}")
        return jsonify([])

@macro_bp.route('/api/projetos/criticos')
def get_projetos_criticos():
    """⚡ OTIMIZADO: Retorna lista de projetos críticos com cache agressivo"""
    import time
    start_time = time.time()
    
    try:
        # 🚀 CACHE API: Verificar cache primeiro
        from .services import _get_cached_api_result, _set_cached_api_result
        cache_key = 'projetos_criticos'
        cached_result = _get_cached_api_result(cache_key)
        
        if cached_result is not None:
            cache_time = (time.time() - start_time) * 1000
            logger.info(f"⚡ API CACHE HIT: projetos/criticos em {cache_time:.1f}ms")
            return jsonify(cached_result)
        
        # 📊 CARREGAMENTO DE DADOS
        dados = macro_service.carregar_dados()
        
        if dados.empty:
            logger.warning("❌ Dados vazios para projetos críticos")
            return jsonify([])

        # 🔄 PROCESSAMENTO
        process_start = time.time()
        projetos_criticos = macro_service.calcular_projetos_criticos(dados)
        result = projetos_criticos['dados'].to_dict('records')
        process_time = (time.time() - process_start) * 1000
        
        # 💾 CACHE RESULTADO
        _set_cached_api_result(cache_key, result)
        
        total_time = (time.time() - start_time) * 1000
        logger.info(f"✅ API projetos/criticos: {total_time:.1f}ms ({len(result)} projetos, proc: {process_time:.1f}ms)")
        
        return jsonify(result)
        
    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(f"❌ ERRO API projetos/criticos ({total_time:.1f}ms): {str(e)}")
        return jsonify([])

@macro_bp.route('/api/projetos/concluidos')
def get_projetos_concluidos():
    """⚡ OTIMIZADO: Retorna lista de projetos concluídos com cache agressivo"""
    import time
    start_time = time.time()
    
    try:
        # 🚀 CACHE API: Verificar cache primeiro
        from .services import _get_cached_api_result, _set_cached_api_result
        cache_key = 'projetos_concluidos'
        cached_result = _get_cached_api_result(cache_key)
        
        if cached_result is not None:
            cache_time = (time.time() - start_time) * 1000
            logger.info(f"⚡ API CACHE HIT: projetos/concluidos em {cache_time:.1f}ms")
            return jsonify(cached_result)
        
        # 📊 CARREGAMENTO DE DADOS
        dados = macro_service.carregar_dados()
        
        if dados.empty:
            logger.warning("❌ Dados vazios para projetos concluídos")
            return jsonify([])

        # 🔄 PROCESSAMENTO
        process_start = time.time()
        projetos_concluidos = macro_service.calcular_projetos_concluidos(dados)
        result = projetos_concluidos['dados'].to_dict('records')
        process_time = (time.time() - process_start) * 1000
        
        # 💾 CACHE RESULTADO
        _set_cached_api_result(cache_key, result)
        
        total_time = (time.time() - start_time) * 1000
        logger.info(f"✅ API projetos/concluidos: {total_time:.1f}ms ({len(result)} projetos, proc: {process_time:.1f}ms)")
        
        return jsonify(result)
        
    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(f"❌ ERRO API projetos/concluidos ({total_time:.1f}ms): {str(e)}")
        return jsonify([])

@macro_bp.route('/api/projetos/eficiencia')
def get_projetos_eficiencia():
    """⚡ OTIMIZADO: Retorna lista de projetos com eficiência e cache agressivo"""
    import time
    start_time = time.time()
    
    try:
        # 🚀 CACHE API: Verificar cache primeiro
        from .services import _get_cached_api_result, _set_cached_api_result
        cache_key = 'projetos_eficiencia'
        cached_result = _get_cached_api_result(cache_key)
        
        if cached_result is not None:
            cache_time = (time.time() - start_time) * 1000
            logger.info(f"⚡ API CACHE HIT: projetos/eficiencia em {cache_time:.1f}ms")
            return jsonify(cached_result)
        
        # 📊 CARREGAMENTO DE DADOS
        dados = macro_service.carregar_dados()
        
        if dados.empty:
            logger.warning("❌ Dados vazios para projetos eficiência")
            return jsonify([])

        # 🔄 PROCESSAMENTO
        process_start = time.time()
        eficiencia_entrega = macro_service.calcular_eficiencia_entrega(dados)
        result = eficiencia_entrega['dados'].to_dict('records')
        process_time = (time.time() - process_start) * 1000
        
        # 💾 CACHE RESULTADO
        _set_cached_api_result(cache_key, result)
        
        total_time = (time.time() - start_time) * 1000
        logger.info(f"✅ API projetos/eficiencia: {total_time:.1f}ms ({len(result)} projetos, proc: {process_time:.1f}ms)")
        
        return jsonify(result)
        
    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(f"❌ ERRO API projetos/eficiencia ({total_time:.1f}ms): {str(e)}")
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
        else:
            # Garante que 'Numero' seja string para a consulta do backlog
            dados_account['Numero'] = dados_account['Numero'].astype(str)

        # <<< INÍCIO: Adicionar verificação de backlog >>>
        if not dados_account.empty and 'Numero' in dados_account.columns:
            # Pega todos os IDs de projeto (números) únicos e não vazios
            project_ids = dados_account['Numero'].dropna().unique().tolist()
            project_ids = [pid for pid in project_ids if pid]  # Remove vazios

            if project_ids:
                # Consulta o banco para ver quais IDs têm backlog
                try:
                    from app.models import Backlog
                    from app import db
                    
                    backlogs_existentes = db.session.query(Backlog.project_id)\
                                                    .filter(Backlog.project_id.in_(project_ids))\
                                                    .all()
                    # Cria um set com os IDs que têm backlog para busca rápida
                    ids_com_backlog = {result[0] for result in backlogs_existentes}
                    logger.info(f"Encontrados {len(ids_com_backlog)} backlogs para {len(project_ids)} projetos do account manager verificados.")
                    
                    # Adiciona a coluna 'backlog_exists' ao DataFrame
                    dados_account['backlog_exists'] = dados_account['Numero'].apply(
                        lambda pid: pid in ids_com_backlog if pd.notna(pid) else False
                    )

                except Exception as db_error:
                    logger.error(f"Erro ao consultar backlogs existentes: {db_error}", exc_info=True)
                    # Se der erro no DB, assume que nenhum backlog existe para não quebrar
                    dados_account['backlog_exists'] = False
            else:
                logger.info("Nenhum ID de projeto válido encontrado para verificar backlog.")
                dados_account['backlog_exists'] = False
        else:
            logger.info("DataFrame vazio ou sem coluna 'Numero'. Pulando verificação de backlog.")
            if 'Numero' in dados_account.columns:
                dados_account['backlog_exists'] = False
        # <<< FIM: Adicionar verificação de backlog >>>

        # Usar a função _formatar_projetos para manter consistência
        projetos = macro_service._formatar_projetos(dados_account)
        
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
@feature_required('macro.status_report', parent_module='macro')
def apresentacao():
    """Rota para página de apresentação para diretoria"""
    try:
        logger.info("🚀 ROTA: Iniciando rota /apresentacao")
        logger.info("🚀 ROTA: Acessando página de apresentação para diretoria")
        
        # --- INÍCIO: Detectar fontes disponíveis automaticamente ---
        fontes_disponiveis = macro_service.obter_fontes_disponiveis()
        logger.info(f"Fontes detectadas automaticamente: {[f['nome_exibicao'] for f in fontes_disponiveis]}")
        # --- FIM: Detectar fontes disponíveis automaticamente ---
        
        logger.info("🚀 ROTA: Fontes detectadas com sucesso")
        
        # Obter parâmetros de consulta para mês e ano
        mes_param = request.args.get('mes', None)
        ano_param = request.args.get('ano', None)
        
        logger.info(f"🚀 ROTA: Parâmetros recebidos - mes: {mes_param}, ano: {ano_param}")
        
        # Determina se é a Visão Atual ou uma Visão Histórica
        is_visao_atual = not mes_param or not ano_param
        
        logger.info(f"🚀 ROTA: is_visao_atual = {is_visao_atual}")
        
        if is_visao_atual:
            logger.info("🚀 ROTA: Processando como Visão Atual (sem parâmetros de data específicos).")
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
            logger.info(f"🚀 ROTA: Processando como Visão Histórica para {mes_param}/{ano_param}.")
            # --- LÓGICA PARA VISÃO HISTÓRICA (como estava antes) ---
            try:
                mes_referencia = datetime(int(ano_param), int(mes_param), 1)
                logger.info(f"🚀 ROTA: Usando mês de referência dos parâmetros: {mes_referencia.strftime('%m/%Y')}")
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
            # Agora usa detecção automática de fontes em vez de hardcoded
            fonte_dados_ref = None
            
            # Procura a fonte correspondente nas fontes detectadas
            for fonte in fontes_disponiveis:
                if fonte['mes'] == mes_referencia.month and fonte['ano'] == mes_referencia.year:
                    fonte_dados_ref = fonte['arquivo']
                    logger.info(f"Fonte detectada automaticamente para {mes_referencia.strftime('%m/%Y')}: {fonte_dados_ref}")
                    break
            
            # Fallback para o método antigo caso não encontre automaticamente
            if not fonte_dados_ref:
                logger.warning(f"Fonte não detectada automaticamente para {mes_referencia.strftime('%m/%Y')}, usando método de fallback")
                if mes_referencia.month == 3 and mes_referencia.year == 2025:
                    fonte_dados_ref = 'dadosr_apt_mar'
                elif mes_referencia.month == 4 and mes_referencia.year == 2025:
                    fonte_dados_ref = 'dadosr_apt_abr'
                elif mes_referencia.month == 2 and mes_referencia.year == 2025:
                    fonte_dados_ref = 'dadosr_apt_fev'
                elif mes_referencia.month == 1 and mes_referencia.year == 2025:
                    fonte_dados_ref = 'dadosr_apt_jan'
            
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
                # Lógica para determinar a fonte histórica - USA DETECÇÃO AUTOMÁTICA
                fonte_mes_loop = None
                
                # Procura a fonte nas fontes detectadas automaticamente
                for fonte in fontes_disponiveis:
                    if fonte['mes'] == mes_loop and fonte['ano'] == ano_loop:
                        fonte_mes_loop = fonte['arquivo']
                        break
                
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
                
                # Lógica para determinar a fonte - USA DETECÇÃO AUTOMÁTICA
                fonte_mes_loop = None
                
                # Procura a fonte nas fontes detectadas automaticamente  
                for fonte in fontes_disponiveis:
                    if fonte['mes'] == mes_loop and fonte['ano'] == ano_loop:
                        fonte_mes_loop = fonte['arquivo']
                        break
                
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

        # --- INÍCIO: Calcular Novos Cards do Status Report ---
        logger.info("🚀 ROTA: CHEGOU ATÉ O CÁLCULO DOS CARDS!")
        logger.info("🚀 ROTA: Calculando dados para os novos cards do Status Report...")
        
        # Card 1: Projetos Principais do Mês
        logger.info(f"🎯 ROTA: Chamando calcular_projetos_principais_mes para {mes_referencia.strftime('%Y-%m')}")
        logger.info(f"🎯 ROTA: Dados ref shape: {dados_ref.shape if not dados_ref.empty else 'VAZIO'}")
        projetos_principais = macro_service.calcular_projetos_principais_mes(dados_ref, mes_referencia)
        logger.info(f"🎯 ROTA: Projetos principais retornados: {len(projetos_principais.get('projetos', []))} projetos")
        logger.info(f"🎯 ROTA: Critério usado: {projetos_principais.get('criterios', 'N/A')}")
        logger.info(f"🎯 ROTA: Total encontrados: {projetos_principais['total_encontrados']}")
        
        # Card 2: Projetos Previstos para Encerramento (salto temporal)
        logger.info(f"🚀 NOVA VERSÃO: Calculando projetos previstos para encerramento...")
        projetos_previstos = macro_service.calcular_projetos_previstos_encerramento(dados_ref, mes_referencia)
        logger.info(f"🚀 RESULTADO: {projetos_previstos['mes_previsto']} - {projetos_previstos['total_encontrados']} projetos encontrados")
        logger.info(f"🚀 PROJETOS: {[p['cliente'] for p in projetos_previstos['projetos'][:3]]}")
        # --- FIM: Calcular Novos Cards do Status Report ---

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
            'fontes_disponiveis': fontes_disponiveis,  # <-- NOVA: Lista de fontes detectadas automaticamente
            'error': None, # Assume sem erro inicialmente
            # === NOVOS CARDS DO STATUS REPORT ===
            'projetos_principais': projetos_principais,  # Card Projetos Principais do Mês
            'projetos_previstos': projetos_previstos  # Card Projetos Previstos para Encerramento
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

# <<< INÍCIO: Nova Rota para Status Report >>>
@macro_bp.route('/status-report/<project_id>')
@feature_required('backlog.status_individual', parent_module='backlog')
def status_report(project_id):
    """Rota para exibir o Status Report de um projeto específico."""
    try:
        logger.info(f"[Status Report] Gerando Status Report para projeto ID: {project_id}")
        
        # Chama a função do service para preparar os dados
        report_data = macro_service.gerar_dados_status_report(project_id)
        
        if not report_data:
            logger.error(f"[Status Report] Não foi possível gerar os dados para o Status Report do projeto ID {project_id}.")
            return render_template('macro/status_report.html',
                                 error=f"Não foi possível gerar dados para o projeto ID {project_id}. Verifique os logs.",
                                 project_id=project_id,
                                 report_data=None)

        # Log detalhado dos dados
        logger.info(f"[Status Report] Dados recebidos do service para projeto {project_id}:")
        logger.info(f"[Status Report] Chaves no report_data: {list(report_data.keys())}")
        if 'notas' in report_data:
            logger.info(f"[Status Report] Número de notas: {len(report_data['notas'])}")
            for nota in report_data['notas']:
                conteudo = nota.get('conteudo', '') or ''  # Garante que não seja None
                logger.info(f"[Status Report] Nota encontrada: ID={nota.get('id')}, Project_ID={nota.get('project_id')}, Backlog_ID={nota.get('backlog_id')}, Categoria={nota.get('categoria')}, Conteúdo={conteudo[:50]}...")
        
        # Preparar contexto 
        context = {
            'report_data': report_data,
            'project_id': project_id,
            'titulo_pagina': f"Status Report - {report_data['info_geral'].get('nome', project_id)}",
            'data_geracao': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'pdf_generator_available': pdf_generator_available,
            'generator_type': 'weasyprint' if _check_pdf_generators() and weasyprint_installed else ('pdfkit' if pdfkit_installed else 'none'),
            'for_pdf': False  # Explicitly set to False for browser view
        }
        
        logger.info(f"[Status Report] Renderizando template com contexto: {context.keys()}")
        
        return render_template('macro/status_report.html', **context)

    except Exception as e:
        logger.exception(f"[Status Report] Erro ao gerar Status Report para projeto ID {project_id}: {str(e)}")
        # Renderiza o template com uma mensagem de erro genérica
        return render_template('macro/status_report.html',
                             error=f"Erro ao gerar o Status Report: {str(e)}",
                             project_id=project_id,
                             report_data=None)
# <<< FIM: Nova Rota para Status Report >>>

# <<< INÍCIO: Nova Rota para Download do PDF >>>
@macro_bp.route('/status-report/<project_id>/download')
@feature_required('backlog.status_individual', parent_module='backlog')
def download_status_report(project_id):
    """Gera e faz o download do Status Report em PDF usando WeasyPrint."""
    # Variáveis de verificação de instalação (para referência, mas não usadas diretamente na lógica abaixo)
    # weasyprint_installed = True  # Assumindo que queremos forçar
    # pdfkit_installed = False

    # pdf_generator_available = weasyprint_installed

    # if not pdf_generator_available: # Esta verificação pode ser simplificada se só temos WeasyPrint
    #     logger.error("Tentativa de download de PDF sem gerador WeasyPrint teoricamente disponível.")
    #     flash("Erro: Funcionalidade de download de PDF com WeasyPrint não está operacional.", "danger")
    #     return redirect(url_for('macro.status_report', project_id=project_id))

    try:
        logger.info(f"[PDF Download] Iniciando geração para projeto ID: {project_id} usando WeasyPrint")
        report_data = macro_service.gerar_dados_status_report(project_id)
        if not report_data:
            logger.error(f"[PDF Download] Falha ao obter dados para o projeto ID {project_id}.")
            flash(f"Erro ao gerar PDF: Não foi possível obter dados para o projeto {project_id}.", "danger")
            return redirect(url_for('macro.status_report', project_id=project_id))

        context = {
            'report_data': report_data,
            'project_id': project_id,
            'titulo_pagina': f"Status Report - {report_data['info_geral'].get('nome', project_id)}",
            'data_geracao': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'for_pdf': True
        }

        safe_project_name = report_data['info_geral'].get('nome', str(project_id)).replace(' ', '_').lower()
        pdf_filename = f"status_report_{safe_project_name}_{datetime.now().strftime('%Y%m%d')}.pdf"

        # Verifica e importa geradores PDF sob demanda
        if not _check_pdf_generators():
            raise Exception("Nenhum gerador de PDF disponível")
        
        logger.info(f"[PDF Download] Tentando gerar PDF com WeasyPrint.")
        html_string = render_template('macro/status_report.html', **context)
        
        # WeasyPrint usará sua configuração de fonte padrão.
        pdf_bytes = HTML(string=html_string, base_url=request.base_url).write_pdf() # Removido font_config=font_config
        
        logger.info(f"[PDF Download] PDF gerado com sucesso via WeasyPrint. Nome: {pdf_filename}")
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment;filename={pdf_filename}"}
        )
        
    # Removido o bloco elif pdfkit_installed para forçar o WeasyPrint
    # e para que qualquer erro do WeasyPrint seja capturado pelo except geral abaixo.

    except Exception as e:
        # Este except agora pegará erros do WeasyPrint diretamente ou qualquer outro erro.
        logger.exception(f"[PDF Download] Erro CRÍTICO ao tentar gerar PDF com WeasyPrint para projeto ID {project_id}: {e}")
        flash(f"Ocorreu um erro crítico ao gerar o PDF com WeasyPrint: {str(e)}. Verifique os logs do servidor.", "danger")
        # Não redirecionar para a página de status, mas sim mostrar um erro mais direto ou uma página de erro.
        # Para simplificar, vamos redirecionar, mas o flash conterá a mensagem de erro do WeasyPrint.
        return redirect(url_for('macro.status_report', project_id=project_id))
# <<< FIM: Nova Rota para Download do PDF >>>

@macro_bp.route('/api/projetos/status/<string:status>')
def api_projetos_por_status(status):
    """API para obter projetos filtrados por status específico"""
    try:
        logger.info(f"Buscando projetos com status: {status}")
        
        # Carrega dados atuais
        dados = macro_service.carregar_dados()
        
        if dados.empty:
            logger.warning("Dados vazios ao buscar projetos por status")
            return jsonify([])
        
        # Normaliza o status para comparação (uppercase)
        status_normalizado = status.upper().strip()
        
        # Se for status FECHADO, usar a função específica que filtra por mês atual
        if status_normalizado == 'FECHADO':
            logger.info("Status FECHADO detectado - usando filtro por mês atual")
            projetos_concluidos = macro_service.calcular_projetos_concluidos(dados)
            projetos_formatados = projetos_concluidos['dados'].to_dict('records')
            
            # Adiciona campos necessários para compatibilidade com o modal
            for projeto in projetos_formatados:
                # Adiciona campos que podem estar faltando
                if 'numero' not in projeto:
                    projeto['numero'] = ''
                if 'dataPrevEnc' not in projeto:
                    projeto['dataPrevEnc'] = 'N/A'
                if 'horasRestantes' not in projeto:
                    projeto['horasRestantes'] = 0.0  # Projetos fechados têm 0 horas restantes
                if 'Horas' not in projeto:
                    projeto['Horas'] = projeto.get('horasContratadas', 0.0)
                
                # REMOVE a coluna conclusão para projetos fechados
                if 'conclusao' in projeto:
                    del projeto['conclusao']
            
            logger.info(f"Encontrados {len(projetos_formatados)} projetos fechados no mês atual")
            return jsonify(projetos_formatados)
        
        # Para outros status, usar o filtro normal
        projetos_filtrados = dados[dados['Status'].str.upper() == status_normalizado].copy()
        
        if projetos_filtrados.empty:
            logger.info(f"Nenhum projeto encontrado com status: {status}")
            return jsonify([])
        
        # Adiciona verificação de backlog para todos os projetos (exceto FECHADO que já tem tratamento especial)
        if status_normalizado != 'FECHADO':
            # Certifica-se de que a coluna Numero existe
            if 'Numero' not in projetos_filtrados.columns and 'Número' in projetos_filtrados.columns:
                projetos_filtrados['Numero'] = projetos_filtrados['Número']
            elif 'Numero' not in projetos_filtrados.columns:
                logger.warning("Coluna 'Numero' não encontrada. Criando coluna vazia.")
                projetos_filtrados['Numero'] = ''
            else:
                # Garante que 'Numero' seja string para a consulta do backlog
                projetos_filtrados['Numero'] = projetos_filtrados['Numero'].astype(str)

            # Adiciona verificação de backlog
            if not projetos_filtrados.empty and 'Numero' in projetos_filtrados.columns:
                # Pega todos os IDs de projeto (números) únicos e não vazios
                project_ids = projetos_filtrados['Numero'].dropna().unique().tolist()
                project_ids = [pid for pid in project_ids if pid]  # Remove vazios

                if project_ids:
                    # Consulta o banco para ver quais IDs têm backlog
                    try:
                        from app.models import Backlog
                        from app import db
                        
                        backlogs_existentes = db.session.query(Backlog.project_id)\
                                                        .filter(Backlog.project_id.in_(project_ids))\
                                                        .all()
                        # Cria um set com os IDs que têm backlog para busca rápida
                        ids_com_backlog = {result[0] for result in backlogs_existentes}
                        logger.info(f"Encontrados {len(ids_com_backlog)} backlogs para {len(project_ids)} projetos verificados.")
                        
                        # Adiciona a coluna 'backlog_exists' ao DataFrame
                        projetos_filtrados['backlog_exists'] = projetos_filtrados['Numero'].apply(
                            lambda pid: pid in ids_com_backlog if pd.notna(pid) else False
                        )

                    except Exception as db_error:
                        logger.error(f"Erro ao consultar backlogs existentes: {db_error}", exc_info=True)
                        # Se der erro no DB, assume que nenhum backlog existe para não quebrar
                        projetos_filtrados['backlog_exists'] = False
                else:
                    logger.info("Nenhum ID de projeto válido encontrado para verificar backlog.")
                    projetos_filtrados['backlog_exists'] = False
            else:
                logger.info("DataFrame vazio ou sem coluna 'Numero'. Pulando verificação de backlog.")
                if 'Numero' in projetos_filtrados.columns:
                    projetos_filtrados['backlog_exists'] = False
        
        # Formata os projetos usando a função padrão
        projetos_formatados = macro_service._formatar_projetos(projetos_filtrados)
        
        logger.info(f"Encontrados {len(projetos_formatados)} projetos com status {status}")
        return jsonify(projetos_formatados)
        
    except Exception as e:
        logger.error(f"Erro ao buscar projetos por status {status}: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro interno do servidor'}), 500

@macro_bp.route('/api/especialistas/resumo')
@feature_required('macro.resumo_cards')
def api_resumo_especialistas():
    """
    Retorna resumo detalhado dos especialistas com métricas agregadas.
    Inclui: total de projetos, projetos ativos, projetos concluídos e horas utilizadas.
    """
    try:
        logger.info("API: Calculando resumo dos especialistas...")
        
        dados = macro_service.carregar_dados()
        if dados.empty:
            logger.warning("API: Dados vazios ao calcular resumo dos especialistas.")
            return jsonify([])
        
        # Prepara dados base
        dados_base = macro_service.preparar_dados_base(dados)
        
        if 'Especialista' not in dados_base.columns:
            logger.warning("API: Coluna 'Especialista' não encontrada nos dados.")
            return jsonify([])
        
        # Obtém data atual para filtrar projetos concluídos do mês
        hoje = datetime.now()
        mes_atual = hoje.month
        ano_atual = hoje.year
        
        # Status para categorização
        status_concluidos = ['FECHADO', 'ENCERRADO', 'RESOLVIDO', 'CANCELADO']
        status_ativos = ['NOVO', 'AGUARDANDO', 'EM ATENDIMENTO', 'BLOQUEADO']
        
        # Garante que colunas numéricas estão corretas
        colunas_numericas = ['Horas', 'HorasTrabalhadas', 'HorasRestantes']
        for col in colunas_numericas:
            if col in dados_base.columns:
                dados_base[col] = pd.to_numeric(dados_base[col], errors='coerce').fillna(0.0)
        
        # Filtra especialistas válidos (remove nulos, vazios, 'Não Alocado' e Squads/Entidades)
        especialistas_invalidos = [
            'Não Alocado', 'CDB DATA SOLUTIONS', 'SOU CLOUD', 'SQUAD', 'EQUIPE',
            'CONSULTORIA', 'DESENVOLVIMENTO', 'INFRAESTRUTURA', '', None
        ]
        dados_especialistas = dados_base[
            dados_base['Especialista'].notna() & 
            (dados_base['Especialista'] != '') & 
            (~dados_base['Especialista'].isin(especialistas_invalidos))
        ].copy()
        
        if dados_especialistas.empty:
            logger.warning("API: Nenhum especialista válido encontrado nos dados.")
            return jsonify([])
        
        resumo_especialistas = []
        
        # Agrupa por especialista
        for especialista in dados_especialistas['Especialista'].unique():
            dados_esp = dados_especialistas[dados_especialistas['Especialista'] == especialista]
            
            # Total de projetos (todos os projetos já trabalhados pelo especialista)
            total_projetos = len(dados_esp)
            
            # Projetos ativos (não concluídos)
            projetos_ativos = len(dados_esp[~dados_esp['Status'].isin(status_concluidos)])
            
            # TODOS os projetos concluídos (histórico completo)
            projetos_concluidos = len(dados_esp[dados_esp['Status'].isin(status_concluidos)])
            
            # Projetos concluídos no mês atual
            dados_concluidos_mes = dados_esp[
                (dados_esp['Status'].isin(status_concluidos)) &
                (pd.to_datetime(dados_esp['DataTermino']).dt.month == mes_atual) &
                (pd.to_datetime(dados_esp['DataTermino']).dt.year == ano_atual)
            ]
            projetos_concluidos_mes = len(dados_concluidos_mes)
            
            # Horas utilizadas (soma das horas trabalhadas em todos os projetos)
            horas_utilizadas = dados_esp['HorasTrabalhadas'].sum()
            
            # Calcula status de sobrecarga baseado apenas em projetos ativos
            dados_ativos = dados_esp[~dados_esp['Status'].isin(status_concluidos)]
            horas_ativas = dados_ativos['HorasRestantes'].sum()
            
            # Define status de sobrecarga baseado na carga ativa
            if projetos_ativos >= 8 or horas_ativas > 250:
                status_sobrecarga = 'CRÍTICO'
            elif projetos_ativos >= 5 or horas_ativas > 150:
                status_sobrecarga = 'SOBRECARREGADO'
            else:
                status_sobrecarga = 'NORMAL'
            
            resumo_especialistas.append({
                'nome': especialista,
                'projetos_total': total_projetos,  # Renomeado para ficar mais claro
                'projetos_ativos': projetos_ativos,
                'projetos_concluidos': projetos_concluidos,
                'projetos_concluidos_mes': projetos_concluidos_mes,
                'total_horas': round(horas_utilizadas, 1),  # Renomeado para ficar consistente
                'status_sobrecarga': status_sobrecarga
            })
        
        # Ordena por número de projetos ativos (decrescente) e depois por nome
        resumo_especialistas.sort(key=lambda x: (-x['projetos_ativos'], x['nome']))
        
        logger.info(f"API: Resumo calculado para {len(resumo_especialistas)} especialistas")
        logger.debug(f"API: Exemplo de dados - {resumo_especialistas[0] if resumo_especialistas else 'Nenhum dado'}")
        
        return jsonify(resumo_especialistas)
        
    except Exception as e:
        logger.error(f"Erro na API resumo especialistas: {str(e)}", exc_info=True)
        return jsonify([]), 500

@macro_bp.route('/api/tipos-servico-simples')
@feature_required('macro.tipos_servico')
def api_tipos_servico_simples():
    """API simples para testar tipos de serviço com CSV"""
    try:
        logger.info("🔄 API Tipos Serviço Simples - iniciando...")
        
        # Carrega dados
        dados = macro_service.carregar_dados()
        if dados.empty:
            logger.warning("Dados vazios")
            return jsonify({
                'success': False,
                'message': 'Nenhum dado disponível',
                'data': {}
            })
        
        # Calcula métricas simples
        metricas = macro_service.calcular_metricas_tipos_servico_simples(dados)
        
        # Verifica se houve erro
        if 'erro' in metricas:
            logger.error(f"Erro nas métricas: {metricas['erro']}")
            return jsonify({
                'success': False,
                'message': metricas['erro'],
                'data': metricas
            })
        
        logger.info(f"✅ API concluída: {metricas['resumo']['total_tipos']} tipos, {metricas['resumo']['total_categorias']} categorias")
        
        return jsonify({
            'success': True,
            'message': 'Dados calculados com sucesso',
            'data': metricas
        })
        
    except Exception as e:
        logger.error(f"❌ Erro na API tipos serviço simples: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Erro interno: {str(e)}',
            'data': {}
        }), 500

@macro_bp.route('/api/mapeamento-dexpra')
@feature_required('macro.tipos_servico')
def api_mapeamento_dexpra():
    """API para análise DexPra - tipos de serviço nos projetos vs CSV"""
    try:
        logger.info("🔄 API Mapeamento DexPra - iniciando...")
        
        # Carrega dados dos projetos
        dados = macro_service.carregar_dados()
        if dados.empty:
            return jsonify({
                'success': False,
                'message': 'Nenhum dado de projeto disponível',
                'data': {}
            })
        
        # Chama função específica para mapeamento
        mapeamento = macro_service.analisar_mapeamento_tipos_servico(dados)
        
        logger.info(f"✅ Mapeamento concluído: {mapeamento.get('resumo', {})}")
        
        return jsonify({
            'success': True,
            'message': 'Análise de mapeamento concluída',
            'data': mapeamento
        })
        
    except Exception as e:
        logger.error(f"❌ Erro na API mapeamento DexPra: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Erro interno: {str(e)}',
            'data': {}
        }), 500

@macro_bp.route('/api/refresh-tipos-servico', methods=['POST'])
@feature_required('macro.tipos_servico')
def api_refresh_tipos_servico():
    """API para forçar refresh do cache de tipos de serviço"""
    try:
        logger.info("🔄 Refresh manual dos tipos de serviço...")
        
        from app.macro.typeservice_reader import type_service_reader
        
        # Limpa cache e recarrega
        type_service_reader.limpar_cache()
        tipos_recarregados = type_service_reader.recarregar_csv()
        
        # Valida o arquivo
        valido, mensagem = type_service_reader.validar_arquivo()
        
        resultado = {
            'tipos_carregados': len(tipos_recarregados),
            'arquivo_valido': valido,
            'mensagem_validacao': mensagem,
            'amostra_tipos': list(tipos_recarregados.keys())[:5] if tipos_recarregados else []
        }
        
        logger.info(f"✅ Refresh concluído: {len(tipos_recarregados)} tipos carregados")
        
        return jsonify({
            'success': True,
            'message': f'Cache atualizado com sucesso - {len(tipos_recarregados)} tipos carregados',
            'data': resultado
        })
        
    except Exception as e:
        logger.error(f"❌ Erro no refresh tipos de serviço: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Erro interno: {str(e)}',
            'data': {}
        }), 500

@macro_bp.route('/api/debug-normalizacao')
@feature_required('macro.tipos_servico')
def api_debug_normalizacao():
    """API para debug da normalização de tipos de serviço - ajuda a identificar problemas de mapeamento"""
    try:
        logger.info("🔍 Debug da normalização - iniciando...")
        
        from app.macro.typeservice_reader import type_service_reader
        import unicodedata
        
        # Função auxiliar para normalizar strings (igual à do services.py)
        def normalizar_string(s):
            """Normaliza string removendo espaços extras, acentos e padronizando case"""
            if pd.isna(s) or s == '':
                return ''
            # Remove acentos
            s = unicodedata.normalize('NFD', str(s)).encode('ascii', 'ignore').decode('ascii')
            # Remove espaços extras e converte para lowercase
            return ' '.join(str(s).strip().lower().split())
        
        # Carrega dados
        dados = macro_service.carregar_dados()
        if dados.empty:
            return jsonify({
                'success': False,
                'message': 'Nenhum dado de projeto disponível',
                'data': {}
            })
        
        # Carrega mapeamento do CSV
        mapeamento_csv = type_service_reader.carregar_tipos_servico()
        if not mapeamento_csv:
            return jsonify({
                'success': False,
                'message': 'Erro ao carregar arquivo CSV',
                'data': {}
            })
        
        # Coleta tipos dos projetos
        dados_limpos = dados[dados['TipoServico'].notna() & (dados['TipoServico'] != '')].copy()
        tipos_projetos = dados_limpos['TipoServico'].unique()
        
        # Analisa normalização
        debug_info = {
            'tipos_projetos': [],
            'tipos_csv': [],
            'conflitos_potenciais': []
        }
        
        # Mapeia tipos dos projetos
        tipos_proj_norm = {}
        for tipo in tipos_projetos:
            tipo_normalizado = normalizar_string(tipo)
            debug_info['tipos_projetos'].append({
                'original': tipo,
                'normalizado': tipo_normalizado,
                'tamanho_original': len(tipo),
                'tamanho_normalizado': len(tipo_normalizado)
            })
            tipos_proj_norm[tipo_normalizado] = tipo
        
        # Mapeia tipos do CSV
        tipos_csv_norm = {}
        for tipo, categoria in mapeamento_csv.items():
            tipo_normalizado = normalizar_string(tipo)
            debug_info['tipos_csv'].append({
                'original': tipo,
                'normalizado': tipo_normalizado,
                'categoria': categoria,
                'tamanho_original': len(tipo),
                'tamanho_normalizado': len(tipo_normalizado)
            })
            tipos_csv_norm[tipo_normalizado] = {'original': tipo, 'categoria': categoria}
        
        # Identifica conflitos (normalizações iguais)
        for tipo_norm in tipos_proj_norm:
            if tipo_norm in tipos_csv_norm:
                tipo_projeto = tipos_proj_norm[tipo_norm]
                info_csv = tipos_csv_norm[tipo_norm]
                
                if tipo_projeto != info_csv['original']:
                    debug_info['conflitos_potenciais'].append({
                        'normalizado': tipo_norm,
                        'tipo_projeto': tipo_projeto,
                        'tipo_csv': info_csv['original'],
                        'categoria_csv': info_csv['categoria'],
                        'mesmo_texto': tipo_projeto == info_csv['original']
                    })
        
        # Ordena por tamanho para facilitar análise
        debug_info['tipos_projetos'].sort(key=lambda x: x['tamanho_original'], reverse=True)
        debug_info['tipos_csv'].sort(key=lambda x: x['tamanho_original'], reverse=True)
        
        resultado = {
            'total_tipos_projetos': len(tipos_projetos),
            'total_tipos_csv': len(mapeamento_csv),
            'total_conflitos': len(debug_info['conflitos_potenciais']),
            'debug_info': debug_info
        }
        
        logger.info(f"✅ Debug concluído: {len(tipos_projetos)} tipos projetos, {len(mapeamento_csv)} tipos CSV, {len(debug_info['conflitos_potenciais'])} conflitos")
        
        return jsonify({
            'success': True,
            'message': 'Debug da normalização concluído',
            'data': resultado
        })
        
    except Exception as e:
        logger.error(f"❌ Erro no debug normalização: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Erro interno: {str(e)}',
            'data': {}
        }), 500

@macro_bp.route('/api/test-reader')
def api_test_reader():
    """API para testar especificamente o reader de tipos de serviço"""
    try:
        logger.info("🔍 Testando reader...")
        
        from app.macro.typeservice_reader import type_service_reader
        
        # Força reload
        type_service_reader.limpar_cache()
        mapeamento = type_service_reader.recarregar_csv()
        
        # Tipos específicos para testar
        tipos_teste = [
            'Migração de tenant CSP para EA',
            'Assessment for Rapid Migration',
            'Migração de workload de Cloud privada para Azure'
        ]
        
        resultado = {
            'total_tipos_carregados': len(mapeamento),
            'tipos_teste': []
        }
        
        for tipo in tipos_teste:
            encontrado = tipo in mapeamento
            categoria = mapeamento.get(tipo, 'N/A')
            
            resultado['tipos_teste'].append({
                'tipo': tipo,
                'encontrado': encontrado,
                'categoria': categoria
            })
            
            logger.info(f"🔍 Tipo: '{tipo}' - Encontrado: {encontrado} - Categoria: {categoria}")
        
        # Mostra alguns tipos do mapeamento para debug
        resultado['amostra_mapeamento'] = list(mapeamento.items())[:5]
        
        return jsonify({
            'success': True,
            'message': 'Teste do reader concluído',
            'data': resultado
        })
        
    except Exception as e:
        logger.error(f"❌ Erro no teste reader: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Erro interno: {str(e)}',
            'data': {}
        }), 500

from app.macro.periodo_fiscal_service import StatusReportHistoricoService, PeriodoFiscalManager

@macro_bp.route('/api/arquivar-mensal', methods=['POST'])
def api_arquivar_mensal():
    """API para Adminsystem solicitar arquivamento mensal automático"""
    try:
        logger.info("Recebida solicitação de arquivamento mensal via API")
        
        # Importa e executa o módulo de arquivamento
        import subprocess
        import sys
        from pathlib import Path
        
        # Caminho para o script de arquivamento
        script_path = Path(__file__).parent.parent.parent / "scripts" / "arquivar_dados_mensais.py"
        
        if not script_path.exists():
            logger.error(f"Script de arquivamento não encontrado: {script_path}")
            return jsonify({
                "status": "error", 
                "mensagem": f"Script não encontrado: {script_path}"
            }), 500
        
        # Executa o script com parâmetros automáticos
        comando = [sys.executable, str(script_path), "--automatico"]
        
        logger.info(f"Executando comando: {' '.join(comando)}")
        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=60)
        
        if resultado.returncode == 0:
            logger.info("Arquivamento mensal executado com sucesso")
            return jsonify({
                "status": "success", 
                "mensagem": "Arquivamento mensal realizado com sucesso",
                "output": resultado.stdout
            })
        else:
            logger.error(f"Falha no arquivamento: {resultado.stderr}")
            return jsonify({
                "status": "error", 
                "mensagem": "Falha no arquivamento mensal",
                "error": resultado.stderr
            }), 500
            
    except subprocess.TimeoutExpired:
        logger.error("Timeout no arquivamento mensal")
        return jsonify({
            "status": "error", 
            "mensagem": "Timeout no processo de arquivamento"
        }), 500
    except Exception as e:
        logger.exception(f"Erro na API de arquivamento mensal: {str(e)}")
        return jsonify({
            "status": "error", 
            "mensagem": f"Erro interno: {str(e)}"
        }), 500

@macro_bp.route('/apresentacao-periodo')
def apresentacao_periodo():
    try:
        meses_selecionados_str = request.args.get('meses', 'jan,fev,mar,abr,mai,jun')
        meses_selecionados = [mes.strip() for mes in meses_selecionados_str.split(',')]
        
        service = StatusReportHistoricoService()
        kpis_dados = service.calcular_kpis_periodo_historico(meses_selecionados)

        if 'erro' in kpis_dados:
            flash(f"Erro ao calcular KPIs: {kpis_dados['erro']}", "danger")
            return render_template('macro/erro.html', mensagem_erro=kpis_dados['erro'])

        nomes_meses = [service.meses_disponiveis.get(m, {}).get('nome', m) for m in meses_selecionados]
        if len(nomes_meses) > 1:
            periodo_display = f"Análise do período de {nomes_meses[0]} a {nomes_meses[-1]}"
        else:
            periodo_display = f"Análise de {nomes_meses[0]}"

        # Cria os labels do período
        todos_meses_disponiveis = service.listar_meses_disponiveis()
        mapa_meses = {mes['key']: mes['nome'] for mes in todos_meses_disponiveis}
        nomes_meses_selecionados = sorted([mapa_meses.get(m, m) for m in meses_selecionados], key=lambda x: list(mapa_meses.values()).index(x))

        periodo_label = ""
        if len(nomes_meses_selecionados) > 1:
            periodo_label = f"{nomes_meses_selecionados[0]} a {nomes_meses_selecionados[-1]}"
        elif len(nomes_meses_selecionados) == 1:
            periodo_label = nomes_meses_selecionados[0]
        
        # Adiciona a lista de meses disponíveis para o seletor do modal
        contexto = {
            "kpis": kpis_dados.get('kpis_gerais', {}),
            "detalhes_mensais": list(kpis_dados.get('detalhes_mensais', {}).values()),
            "squad_distribution": kpis_dados.get('kpis_gerais', {}).get('distribuicao_squad', {}),
            "periodo_label": periodo_label,
            "meses_disponiveis": todos_meses_disponiveis,
            "meses_selecionados": meses_selecionados_str,
            "hora_atualizacao": datetime.now()
        }

        current_app.logger.info(f"✅ Status Report histórico renderizado para o período: {periodo_label}")
        
        return render_template('macro/apresentacao_periodo.html', **contexto)
        
    except Exception as e:
        current_app.logger.exception(f"❌ Erro fatal na rota apresentacao_periodo: {e}")
        return render_template('macro/erro.html', mensagem_erro=str(e))

@macro_bp.route('/exportar-status-periodo')
def exportar_status_periodo():
    """Exporta os dados do Status Report Histórico para Excel"""
    try:
        # Obtém os mesmos parâmetros da rota principal
        meses_selecionados_str = request.args.get('meses', 'jan,fev,mar,abr,mai,jun')
        meses_selecionados = [mes.strip() for mes in meses_selecionados_str.split(',')]
        
        # Usa o mesmo serviço para garantir consistência dos dados
        service = StatusReportHistoricoService()
        kpis_dados = service.calcular_kpis_periodo_historico(meses_selecionados)

        if 'erro' in kpis_dados:
            flash(f"Erro ao exportar dados: {kpis_dados['erro']}", "danger")
            return redirect(url_for('macro.apresentacao_periodo'))

        # Prepara o nome do arquivo
        nomes_meses = [service.meses_disponiveis.get(m, {}).get('nome', m) for m in meses_selecionados]
        if len(nomes_meses) > 1:
            nome_arquivo = f"Status_Report_Historico_{nomes_meses[0]}_a_{nomes_meses[-1]}.xlsx"
        else:
            nome_arquivo = f"Status_Report_Historico_{nomes_meses[0]}.xlsx"
        
        # Remove caracteres especiais do nome do arquivo
        nome_arquivo = nome_arquivo.replace('/', '_').replace('\\', '_').replace(':', '_')

        # Cria o arquivo Excel em memória
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            
            # Formatos para as células
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'fg_color': '#2c3e50',
                'font_color': 'white',
                'border': 1
            })
            
            data_format = workbook.add_format({
                'text_wrap': True,
                'valign': 'top',
                'border': 1
            })
            
            number_format = workbook.add_format({
                'num_format': '#,##0.0',
                'border': 1
            })
            
            # ABA 1: Resumo dos KPIs
            kpis_gerais = kpis_dados.get('kpis_gerais', {})
            resumo_data = []
            
            # KPIs principais
            resumo_data.append(['Indicador', 'Valor', 'Unidade'])
            resumo_data.append(['Projetos Únicos Fechados', kpis_gerais.get('projetos_fechados', 0), 'projetos'])
            resumo_data.append(['Tempo Médio de Vida', kpis_gerais.get('tempo_medio_vida', 0), 'dias'])
            resumo_data.append(['Horas Trabalhadas', kpis_gerais.get('horas_trabalhadas', 0), 'horas'])
            
            # Busca informações de faturamento nos detalhes mensais para ter dados mais precisos
            detalhes_mensais = kpis_dados.get('detalhes_mensais', {})
            distribuicao_faturamento = kpis_gerais.get('distribuicao_faturamento', {})
            
            # Calcula totais de faturamento
            total_faturado_inicio = distribuicao_faturamento.get('INICIO', 0)
            total_faturado_termino = distribuicao_faturamento.get('TERMINO', 0)
            total_plus = distribuicao_faturamento.get('PLUS', 0)
            total_prime = distribuicao_faturamento.get('PRIME', 0)
            total_engajamento = distribuicao_faturamento.get('ENGAJAMENTO', 0)
            total_feop = distribuicao_faturamento.get('FEOP', 0)
            
            resumo_data.append(['Projetos Faturados no Início', total_faturado_inicio, 'projetos'])
            resumo_data.append(['Projetos Faturados no Término', total_faturado_termino, 'projetos'])
            
            # Adiciona outros tipos de faturamento se houver dados
            if total_plus > 0:
                resumo_data.append(['Projetos PLUS', total_plus, 'projetos'])
            if total_prime > 0:
                resumo_data.append(['Projetos PRIME', total_prime, 'projetos'])
            if total_engajamento > 0:
                resumo_data.append(['Projetos ENGAJAMENTO', total_engajamento, 'projetos'])
            if total_feop > 0:
                resumo_data.append(['Projetos FEOP', total_feop, 'projetos'])
            
            # Distribuição por Squad (apenas se houver dados válidos)
            distribuicao_squad = kpis_gerais.get('distribuicao_squad', {})
            total_squad = distribuicao_squad.get('total_squad', {})
            if total_squad and any(valor > 0 for valor in total_squad.values()):
                resumo_data.append(['', '', ''])  # Linha em branco
                resumo_data.append(['DISTRIBUIÇÃO POR SQUAD', '', ''])
                for squad, valor in total_squad.items():
                    if valor > 0:  # Só inclui squads com projetos
                        resumo_data.append([f'Squad {squad}', valor, 'projetos'])
                
                # Total geral de squads
                total_geral_squad = distribuicao_squad.get('total_geral', 0)
                if total_geral_squad > 0:
                    resumo_data.append(['Total Geral (Squads)', total_geral_squad, 'projetos'])
            
            # Cria DataFrame e escreve na planilha
            df_resumo = pd.DataFrame(resumo_data[1:], columns=resumo_data[0])
            df_resumo.to_excel(writer, sheet_name='Resumo KPIs', index=False)
            
            # Formata a aba de resumo
            worksheet_resumo = writer.sheets['Resumo KPIs']
            worksheet_resumo.set_column('A:A', 35)
            worksheet_resumo.set_column('B:B', 15)
            worksheet_resumo.set_column('C:C', 15)
            
            # Aplica formatação ao cabeçalho
            for col_num, value in enumerate(df_resumo.columns.values):
                worksheet_resumo.write(0, col_num, value, header_format)
            
            # ABA 2: Detalhes Mensais
            detalhes_mensais = kpis_dados.get('detalhes_mensais', {})
            if detalhes_mensais:
                # Cabeçalho expandido com todos os tipos de faturamento
                detalhes_data = []
                detalhes_data.append([
                    'Mês', 'Projetos Fechados', 'Tempo Médio Vida (dias)', 'Horas Trabalhadas', 
                    'Faturado Início', 'Faturado Término', 'PLUS', 'PRIME', 'ENGAJAMENTO', 'FEOP'
                ])
                
                for mes_key, dados_mes in detalhes_mensais.items():
                    nome_mes = service.meses_disponiveis.get(mes_key, {}).get('nome', mes_key)
                    
                    # Busca dados de faturamento detalhados se disponíveis
                    faturamento_detalhado = dados_mes.get('faturamento', {})
                    
                    detalhes_data.append([
                        nome_mes,
                        dados_mes.get('fechados', dados_mes.get('projetos_fechados', 0)),
                        dados_mes.get('tempo_medio_vida', 0),
                        dados_mes.get('horas', dados_mes.get('horas_trabalhadas', 0)),
                        faturamento_detalhado.get('INICIO', 0),
                        faturamento_detalhado.get('TERMINO', 0),
                        faturamento_detalhado.get('PLUS', 0),
                        faturamento_detalhado.get('PRIME', 0),
                        faturamento_detalhado.get('ENGAJAMENTO', 0),
                        faturamento_detalhado.get('FEOP', 0)
                    ])
                
                df_detalhes = pd.DataFrame(detalhes_data[1:], columns=detalhes_data[0])
                df_detalhes.to_excel(writer, sheet_name='Detalhes Mensais', index=False)
                
                # Formata a aba de detalhes
                worksheet_detalhes = writer.sheets['Detalhes Mensais']
                worksheet_detalhes.set_column('A:A', 15)
                worksheet_detalhes.set_column('B:J', 15)  # Expandido para incluir todas as colunas
                
                # Aplica formatação ao cabeçalho
                for col_num, value in enumerate(df_detalhes.columns.values):
                    worksheet_detalhes.write(0, col_num, value, header_format)
                
                # Aplica formatação numérica às colunas de dados
                for row_num in range(1, len(df_detalhes) + 1):
                    worksheet_detalhes.write(row_num, 2, df_detalhes.iloc[row_num-1, 2], number_format)  # Tempo Médio Vida
                    worksheet_detalhes.write(row_num, 3, df_detalhes.iloc[row_num-1, 3], number_format)  # Horas Trabalhadas
            
            # ABA 3: Dados Brutos (para replicação de cálculos)
            # Carrega os dados brutos dos meses selecionados
            dados_brutos_combinados = service.carregar_dados_periodo(meses_selecionados)
            
            if not dados_brutos_combinados.empty:
                # Seleciona colunas mais completas para análise
                colunas_relevantes = [
                    'ID', 'NomeProjeto', 'Cliente', 'Status', 'DataInicio', 'DataFim', 
                    'Squad', 'Especialista', 'HorasEstimadas', 'TipoFaturamento', 'Faturamento',
                    'DataCriacao', 'DataAtualizacao', 'MesOrigem'
                ]
                
                # Filtra apenas as colunas que existem no DataFrame
                colunas_existentes = [col for col in colunas_relevantes if col in dados_brutos_combinados.columns]
                df_brutos = dados_brutos_combinados[colunas_existentes].copy()
                
                # Limpeza e formatação dos dados
                # 1. Remove registros com Squad NaN ou vazio
                if 'Squad' in df_brutos.columns:
                    df_brutos = df_brutos[df_brutos['Squad'].notna() & (df_brutos['Squad'] != '')]
                
                # 2. Formata datas removendo timestamp
                colunas_data = ['DataInicio', 'DataFim', 'DataCriacao', 'DataAtualizacao']
                for col_data in colunas_data:
                    if col_data in df_brutos.columns:
                        df_brutos[col_data] = pd.to_datetime(df_brutos[col_data], errors='coerce').dt.date
                
                # 3. Preenche valores NaN com texto mais legível
                df_brutos = df_brutos.fillna('N/A')
                
                # 4. Ordena por Cliente e ID para facilitar análise
                if 'Cliente' in df_brutos.columns and 'ID' in df_brutos.columns:
                    df_brutos = df_brutos.sort_values(['Cliente', 'ID'])
                
                df_brutos.to_excel(writer, sheet_name='Dados Brutos', index=False)
                
                # Formata a aba de dados brutos
                worksheet_brutos = writer.sheets['Dados Brutos']
                
                # Define larguras específicas para cada tipo de coluna
                col_widths = {
                    'ID': 10,
                    'NomeProjeto': 30,
                    'Cliente': 20,
                    'Status': 15,
                    'DataInicio': 12,
                    'DataFim': 12,
                    'Squad': 15,
                    'Especialista': 20,
                    'HorasEstimadas': 12,
                    'TipoFaturamento': 15,
                    'Faturamento': 15,
                    'DataCriacao': 12,
                    'DataAtualizacao': 12,
                    'MesOrigem': 12
                }
                
                # Aplica larguras personalizadas
                for col_num, col_name in enumerate(df_brutos.columns):
                    width = col_widths.get(col_name, 15)
                    worksheet_brutos.set_column(col_num, col_num, width)
                
                # Aplica formatação ao cabeçalho
                for col_num, value in enumerate(df_brutos.columns.values):
                    worksheet_brutos.write(0, col_num, value, header_format)
        
        # Prepara o arquivo para download
        output.seek(0)
        
        current_app.logger.info(f"✅ Arquivo Excel gerado com sucesso: {nome_arquivo}")
        
        return Response(
            output.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f'attachment; filename="{nome_arquivo}"',
                'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            }
        )
        
    except Exception as e:
        current_app.logger.exception(f"❌ Erro ao exportar Status Report: {e}")
        flash(f"Erro ao exportar dados: {str(e)}", "danger")
        return redirect(url_for('macro.apresentacao_periodo'))


# === ROTAS PARA CONFIGURAÇÃO DE PROJETOS PRINCIPAIS ===

@macro_bp.route('/api/projetos-disponiveis')
@module_required('macro')
def api_projetos_disponiveis():
    """
    API para listar todos os projetos disponíveis para seleção como principais
    """
    try:
        logger.info("Carregando projetos disponíveis para seleção")
        
        # Obter mês de referência usando a mesma lógica da rota /apresentacao
        mes_ano = request.args.get('mes_ano')
        if mes_ano:
            try:
                # Visão histórica - usar parâmetro específico
                mes_referencia = datetime.strptime(mes_ano, '%Y-%m')
                fonte_especifica = f'dadosr_apt_{["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"][mes_referencia.month-1]}.csv'
                dados = macro_service.carregar_dados(fonte=fonte_especifica)
                logger.info(f"API: Usando visão histórica para {mes_referencia.strftime('%B/%Y')} - fonte: {fonte_especifica}")
            except ValueError:
                return jsonify({'erro': 'Formato de data inválido. Use YYYY-MM'}), 400
        else:
            # Visão atual - usar a mesma lógica da rota principal
            logger.info("API: Detectando mês de referência da visão atual")
            dados_atuais, mes_referencia_detectado = macro_service.obter_dados_e_referencia_atual()
            
            if mes_referencia_detectado and not dados_atuais.empty:
                mes_referencia = mes_referencia_detectado
                dados = dados_atuais
                logger.info(f"API: Mês de referência detectado da visão atual: {mes_referencia.strftime('%B/%Y')}")
            else:
                # Fallback para mês anterior
                hoje = datetime.now()
                primeiro_dia_mes_atual = hoje.replace(day=1)
                ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
                mes_referencia = ultimo_dia_mes_anterior.replace(day=1)
                dados = macro_service.carregar_dados()
                logger.info(f"API: Usando fallback para mês anterior: {mes_referencia.strftime('%B/%Y')}")
        
        # Verificar se dados foram carregados
        if dados.empty:
            return jsonify({
                'projetos': [],
                'selecionados': [],
                'total': 0
            })
        
        # Preparar dados dos projetos
        dados_processados = macro_service.preparar_dados_base(dados)
        
        # Calcular horas trabalhadas no mês para cada projeto
        dados_com_horas = macro_service._calcular_horas_trabalhadas_no_mes(dados_processados, mes_referencia)
        
        # Filtrar apenas projetos com atividade no mês - OTIMIZADO
        projetos_ativos = dados_com_horas[
            (dados_com_horas['horas_trabalhadas_mes'].fillna(0) > 0) &
            (~dados_com_horas['Status'].isin(['CANCELADO']))
        ].copy()
        
        # Limitar resultados para performance (top 50 por horas trabalhadas)
        if len(projetos_ativos) > 50:
            projetos_ativos = projetos_ativos.nlargest(50, 'horas_trabalhadas_mes')
            logger.info(f"API: Limitando resultados a top 50 projetos para otimizar performance")
        
        # Enriquecer apenas os projetos filtrados (performance otimizada)
        projetos_enriquecidos = macro_service._enriquecer_projetos_com_historico(projetos_ativos, mes_referencia)
        
        # Formatar dados para o frontend - OTIMIZADO
        projetos_lista = []
        
        # Cache para clientes já processados (otimização)
        cache_clientes = {}
        
        for _, projeto in projetos_enriquecidos.iterrows():
            nome_projeto = projeto.get('Projeto', 'N/A')
            
            # Usar cache para clientes já processados
            if nome_projeto in cache_clientes:
                nome_cliente = cache_clientes[nome_projeto]
            else:
                # Extrair nome do cliente
                nome_cliente = projeto.get('nome_cliente_enriquecido', projeto.get('Cliente', 'N/A'))
                
                # Aplicar lógica de extração de cliente apenas se necessário
                if nome_cliente == 'N/A' and nome_projeto and nome_projeto != 'N/A':
                    projeto_upper = nome_projeto.upper()
                    is_sou_internal = (
                        'COPILOT' in projeto_upper or
                        'SHAREPOINT' in projeto_upper or 
                        'REESTRUTURA' in projeto_upper or
                        'INTERNO' in projeto_upper or
                        'INTERNAL' in projeto_upper or
                        (projeto_upper.startswith('SOU ') or projeto_upper.endswith(' SOU') or projeto_upper == 'SOU') or
                        ('PMO' in projeto_upper and 'SOU' in projeto_upper) or
                        ('CONTROL' in projeto_upper and 'SOU' in projeto_upper)
                    )
                    
                    if is_sou_internal:
                        nome_cliente = 'SOU.cloud'
                    elif ' - ' in nome_projeto:
                        nome_cliente = nome_projeto.split(' - ', 1)[0].strip()
                    elif ' | ' in nome_projeto:
                        nome_cliente = nome_projeto.split(' | ', 1)[0].strip()
                    elif ': ' in nome_projeto:
                        nome_cliente = nome_projeto.split(': ', 1)[0].strip()
                    elif ' ' in nome_projeto:
                        palavras = nome_projeto.split()
                        if len(palavras) >= 2:
                            nome_cliente = ' '.join(palavras[:2])
                
                # Aplicar truncamento
                if nome_cliente != 'N/A' and nome_cliente != 'SOU.cloud':
                    nome_cliente = macro_service._truncar_nome_cliente(nome_cliente)
                
                # Armazenar no cache
                cache_clientes[nome_projeto] = nome_cliente
            
            projeto_info = {
                'numero': projeto.get('Numero', ''),
                'nome': nome_projeto,
                'cliente': nome_cliente,
                'squad': projeto.get('Squad', 'N/A'),
                'status': projeto.get('Status', 'N/A'),
                'horas_mes': round(projeto.get('horas_trabalhadas_mes', 0), 1),
                'horas_total': round(projeto.get('Horas', 0), 1)
            }
            projetos_lista.append(projeto_info)
        
        # Ordenar por horas trabalhadas no mês (decrescente)
        projetos_lista.sort(key=lambda x: x['horas_mes'], reverse=True)
        
        # Carregar projetos já selecionados
        projetos_selecionados = macro_service.carregar_projetos_principais_selecionados(mes_referencia)
        
        logger.info(f"API: Retornando {len(projetos_lista)} projetos disponíveis")
        logger.info(f"API: Projetos já selecionados: {projetos_selecionados}")
        logger.info(f"API: Mês de referência: {mes_referencia.strftime('%Y-%m')}")
        
        response_data = {
            'projetos': projetos_lista,
            'selecionados': projetos_selecionados,
            'total': len(projetos_lista),
            'mes_referencia': mes_referencia.strftime('%Y-%m')
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Erro ao carregar projetos disponíveis: {str(e)}", exc_info=True)
        return jsonify({'erro': str(e)}), 500


@macro_bp.route('/api/salvar-projetos-principais', methods=['POST'])
@module_required('macro')
def api_salvar_projetos_principais():
    """
    API para salvar a seleção manual de projetos principais
    """
    try:
        logger.info("🚀 API SALVAR: Iniciando salvamento de projetos principais...")
        
        data = request.get_json()
        logger.info(f"📦 API SALVAR: Dados JSON recebidos: {data}")
        
        projetos_selecionados = data.get('projetos_selecionados', [])
        logger.info(f"📝 API SALVAR: Projetos extraídos: {projetos_selecionados} (tipo: {type(projetos_selecionados)})")
        
        logger.info(f"💾 API SALVAR: Salvando {len(projetos_selecionados)} projetos principais selecionados")
        
        # Validações
        if not isinstance(projetos_selecionados, list):
            return jsonify({'erro': 'projetos_selecionados deve ser uma lista'}), 400
        
        if len(projetos_selecionados) > 5:
            return jsonify({'erro': 'Máximo de 5 projetos podem ser selecionados'}), 400
        
        # Obter mês de referência usando a mesma lógica da rota /apresentacao
        mes_ano = request.args.get('mes_ano')
        if mes_ano:
            try:
                # Visão histórica - usar parâmetro específico
                mes_referencia = datetime.strptime(mes_ano, '%Y-%m')
                logger.info(f"API Salvar: Usando visão histórica para {mes_referencia.strftime('%B/%Y')}")
            except ValueError:
                return jsonify({'erro': 'Formato de data inválido. Use YYYY-MM'}), 400
        else:
            # Visão atual - detectar mês de referência
            logger.info("API Salvar: Detectando mês de referência da visão atual")
            dados_atuais, mes_referencia_detectado = macro_service.obter_dados_e_referencia_atual()
            
            if mes_referencia_detectado:
                mes_referencia = mes_referencia_detectado
                logger.info(f"API Salvar: Mês de referência detectado: {mes_referencia.strftime('%B/%Y')}")
            else:
                # Fallback para mês anterior
                hoje = datetime.now()
                primeiro_dia_mes_atual = hoje.replace(day=1)
                ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
                mes_referencia = ultimo_dia_mes_anterior.replace(day=1)
                logger.info(f"API Salvar: Usando fallback para mês anterior: {mes_referencia.strftime('%B/%Y')}")
        
        # Salvar seleção
        logger.info(f"💾 API SALVAR: Chamando service.salvar_projetos_principais_selecionados...")
        logger.info(f"💾 API SALVAR: Parâmetros - projetos: {projetos_selecionados}, mes_referencia: {mes_referencia.strftime('%Y-%m')}")
        
        resultado = macro_service.salvar_projetos_principais_selecionados(projetos_selecionados, mes_referencia)
        
        logger.info(f"💾 API SALVAR: Resultado do salvamento: {resultado}")
        
        if resultado:
            logger.info("✅ API SALVAR: Projetos principais salvos com sucesso!")
            return jsonify({
                'sucesso': True,
                'mensagem': f'{len(projetos_selecionados)} projetos principais configurados com sucesso',
                'projetos_selecionados': projetos_selecionados,
                'mes_referencia': mes_referencia.strftime('%Y-%m')
            })
        else:
            logger.error("❌ API SALVAR: Falha ao salvar projetos principais")
            return jsonify({'erro': 'Erro ao salvar configuração'}), 500
        
    except Exception as e:
        logger.error(f"❌ API SALVAR: Erro crítico ao salvar projetos principais: {str(e)}", exc_info=True)
        return jsonify({'erro': f'Erro interno: {str(e)}'}), 500

@macro_bp.route('/debug/projetos-previstos')
def debug_projetos_previstos():
    """Endpoint de debug para testar projetos previstos"""
    try:
        from datetime import datetime
        import pandas as pd
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Obtém mês de referência da URL ou usa mês atual como padrão
        mes_url = request.args.get('mes', str(datetime.now().month))
        ano_url = request.args.get('ano', str(datetime.now().year))
        mes_referencia = datetime(int(ano_url), int(mes_url), 1)
        
        # 🔍 DEBUG ADICIONAL: Log dos parâmetros recebidos
        logger.info(f"🔍 PARAMS: mes_url='{request.args.get('mes')}' (usando: {mes_url}), ano_url='{request.args.get('ano')}' (usando: {ano_url})")
        
        # 🎯 LÓGICA CORRIGIDA: Determina se é visão atual ou histórica
        mes_atual = datetime.now().month
        ano_atual = datetime.now().year
        eh_visao_atual = (int(mes_url) == mes_atual and int(ano_url) == ano_atual)
        
        logger.info(f"🎯 DETECÇÃO: mes_atual={mes_atual}, ano_atual={ano_atual}, eh_visao_atual={eh_visao_atual}")
        
        meses_abrev = {
            1: 'jan', 2: 'fev', 3: 'mar', 4: 'abr', 5: 'mai', 6: 'jun',
            7: 'jul', 8: 'ago', 9: 'set', 10: 'out', 11: 'nov', 12: 'dez'
        }
        
        # 🔄 NOVA LÓGICA: Arquivo e mês de busca baseados no tipo de visão
        if eh_visao_atual:
            # VISÃO ATUAL: Usa dadosr.csv e busca próximo mês real
            arquivo_dados = 'data/dadosr.csv'
            dados_ref = pd.read_csv(arquivo_dados, encoding='latin1', sep=';')
            logger.info(f"✅ VISÃO ATUAL: Usando {arquivo_dados}")
            
            # Busca projetos previstos para o PRÓXIMO MÊS real
            mes_seguinte = mes_atual + 1 if mes_atual < 12 else 1
            ano_seguinte = ano_atual if mes_atual < 12 else ano_atual + 1
            logger.info(f"🎯 VISÃO ATUAL: Buscando projetos previstos para {mes_seguinte:02d}/{ano_seguinte}")
            
        else:
            # VISÃO HISTÓRICA: Tenta arquivo histórico, busca mês seguinte ao histórico
            mes_abrev = meses_abrev.get(int(mes_url), 'jun')
            arquivo_historico = f'data/dadosr_apt_{mes_abrev}.csv'
            
            try:
                dados_ref = pd.read_csv(arquivo_historico, encoding='latin1', sep=';')
                arquivo_dados = arquivo_historico
                logger.info(f"✅ VISÃO HISTÓRICA: Usando {arquivo_historico}")
            except FileNotFoundError:
                # Fallback para dadosr.csv se não encontrar o histórico
                dados_ref = pd.read_csv('data/dadosr.csv', encoding='latin1', sep=';')
                arquivo_dados = 'data/dadosr.csv'
                logger.warning(f"⚠️ Arquivo {arquivo_historico} não encontrado, usando dadosr.csv")
            
            # Busca projetos previstos para o mês seguinte ao histórico
            mes_seguinte = mes_referencia.month + 1 if mes_referencia.month < 12 else 1
            ano_seguinte = mes_referencia.year if mes_referencia.month < 12 else mes_referencia.year + 1
            logger.info(f"🎯 VISÃO HISTÓRICA: Buscando projetos previstos para {mes_seguinte:02d}/{ano_seguinte}")
        
        # Processa projetos direto do CSV com Cliente + Assunto
        # Remove linhas com data de vencimento vazia
        dados_filtrados = dados_ref[dados_ref['Vencimento em'].notna() & (dados_ref['Vencimento em'].str.strip() != '')]
        
        dados_filtrados['Vencimento_dt'] = pd.to_datetime(dados_filtrados['Vencimento em'], format='%d/%m/%Y %H:%M', errors='coerce')
        
        projetos_mes_seguinte = dados_filtrados[
            (dados_filtrados['Vencimento_dt'].dt.month == mes_seguinte) &
            (dados_filtrados['Vencimento_dt'].dt.year == ano_seguinte) &
            (dados_filtrados['Vencimento_dt'].notna())  # Ignora datas inválidas
        ]
        
        logger.info(f"📊 Encontrados {len(projetos_mes_seguinte)} projetos previstos para {mes_seguinte:02d}/{ano_seguinte}")
        
        projetos_processados = []
        for _, row in projetos_mes_seguinte.iterrows():
            cliente_completo = row.get('Cliente (Completo)', '')
            assunto = row.get('Assunto', '')
            squad = row.get('Serviço (2º Nível)', 'N/A')
            
            # Extrai nome do cliente
            if ' - ' in cliente_completo:
                cliente = cliente_completo.split(' - ')[0].strip()
            elif len(cliente_completo) > 25:
                cliente = cliente_completo[:22] + '...'
            else:
                cliente = cliente_completo
            
            # Use Assunto como nome do projeto, se não tiver use cliente
            nome_projeto = assunto if assunto and assunto != cliente_completo else "Projeto " + cliente
            
            projetos_processados.append({
                'cliente': cliente,
                'projeto': nome_projeto,
                'squad': squad
            })
        
        # Calcula contagem por squad
        contagem_squads = {}
        for projeto in projetos_processados:
            squad = projeto['squad']
            contagem_squads[squad] = contagem_squads.get(squad, 0) + 1
        
        # Ordena squads por quantidade (maior para menor)
        squads_ordenados = sorted(contagem_squads.items(), key=lambda x: x[1], reverse=True)
        
        # Define nome do mês seguinte em português
        meses_pt = {
            1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
            7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
        }
        
        nome_mes_seguinte = meses_pt.get(mes_seguinte, str(mes_seguinte))
        mes_previsto_texto = f"{nome_mes_seguinte}/{ano_seguinte}"
        
        return jsonify({
            'success': True,
            'mes_referencia': mes_referencia.strftime('%Y-%m'),
            'total_encontrados': len(projetos_processados),
            'mes_previsto': mes_previsto_texto,
            'arquivo_usado': arquivo_dados,
            'eh_visao_atual': eh_visao_atual,
            'projetos': projetos_processados,
            'contagem_squads': contagem_squads,
            'squads_ordenados': squads_ordenados
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        })
