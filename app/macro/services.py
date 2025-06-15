# app/macro/services.py
import pandas as pd
from pathlib import Path
import logging
from datetime import datetime, timedelta
import os
import numpy as np
from flask import current_app
from app.utils import (
    BaseService, 
    STATUS_ATIVO, 
    STATUS_CRITICO, 
    STATUS_CONCLUIDO, 
    STATUS_ATENDIMENTO,
    COLUNAS_OBRIGATORIAS,
    COLUNAS_NUMERICAS,
    COLUNAS_TEXTO
)
import unicodedata
from .. import db
import time
from typing import Dict, Any, Optional

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constantes de status atualizadas
STATUS_NAO_ATIVOS = ['FECHADO', 'ENCERRADO', 'RESOLVIDO', 'CANCELADO']
STATUS_EM_ANDAMENTO = ['NOVO', 'AGUARDANDO', 'BLOQUEADO', 'EM ATENDIMENTO']
STATUS_ATRASADO = ['ATRASADO']
STATUS_ATIVO = ['ATIVO']

# OTIMIZAÇÃO: Cache global para MacroService (SEM LOGS EXCESSIVOS)
_MACRO_CACHE = {
    'dados': None,
    'timestamp': None,
    'ttl_seconds': 30,  # Cache de 30 segundos para performance
    'project_details_cache': {},  # Cache específico para detalhes de projetos
    'project_cache_ttl': 60  # Cache de projetos dura 60 segundos
}

def _is_cache_valid():
    """Verifica se o cache de dados está válido."""
    if _MACRO_CACHE['dados'] is None or _MACRO_CACHE['timestamp'] is None:
        return False
    
    elapsed = time.time() - _MACRO_CACHE['timestamp']
    return elapsed < _MACRO_CACHE['ttl_seconds']

def _get_cached_dados():
    """Retorna dados do cache se válido, senão None."""
    if _is_cache_valid():
        return _MACRO_CACHE['dados']
    return None

def _set_cached_dados(dados):
    """Define dados no cache com timestamp atual."""
    _MACRO_CACHE['dados'] = dados.copy() if dados is not None and not dados.empty else pd.DataFrame()
    _MACRO_CACHE['timestamp'] = time.time()

def _get_cached_project_details(project_id):
    """Retorna detalhes do projeto do cache se válido."""
    cache_key = str(project_id)
    cache_data = _MACRO_CACHE['project_details_cache'].get(cache_key)
    
    if cache_data is None:
        return None
    
    # Verifica se o cache do projeto ainda é válido
    elapsed = time.time() - cache_data['timestamp']
    if elapsed < _MACRO_CACHE['project_cache_ttl']:
        return cache_data['details']
    else:
        # Remove cache expirado
        del _MACRO_CACHE['project_details_cache'][cache_key]
        return None

def _set_cached_project_details(project_id, details):
    """Cacheia detalhes específicos de um projeto."""
    cache_key = str(project_id)
    _MACRO_CACHE['project_details_cache'][cache_key] = {
        'details': details,
        'timestamp': time.time()
    }

def _normalize_key(key):
    """Normaliza uma chave de dicionário para minúsculo, sem acentos e com underscores."""
    if not isinstance(key, str):
        return key
    # Remove acentos
    nfkd_form = unicodedata.normalize('NFKD', key)
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('utf-8')
    # Substitui espaços por underscore e converte para minúsculo
    return only_ascii.lower().replace(' ', '_')

class MacroService(BaseService):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # Configuração de status - Todos em UPPERCASE para consistência
        self.status_ativos = ['NOVO', 'AGUARDANDO', 'EM ATENDIMENTO', 'BLOQUEADO']
        self.status_concluidos = ['FECHADO', 'ENCERRADO', 'RESOLVIDO', 'CANCELADO']
        self.status_proximos_conclusao = ['NOVO', 'AGUARDANDO', 'EM ATENDIMENTO']
        
        # Para debug, registra os status considerados
        logger.info(f"Status ativos considerados: {self.status_ativos}")
        logger.info(f"Status concluídos considerados: {self.status_concluidos}")
        
        # Labels
        self.nao_alocado_label = 'Não Alocado'
        
        # Configuração de caminhos - Aponta diretamente para dadosr.csv
        base_dir = Path(__file__).resolve().parent.parent.parent
        data_dir = base_dir / 'data'
        self.csv_path = data_dir / 'dadosr.csv'
        logger.info(f"Caminho do CSV definido para: {self.csv_path}")

    def carregar_dados(self, fonte=None):
        """
        Carrega dados da fonte especificada (arquivo CSV) ou usa dados em cache.
        OTIMIZADO: Usa cache de 30 segundos e reduz logs para melhorar performance.
        
        Args:
            fonte (str, optional): Nome específico do arquivo (ex: 'dadosr.csv' ou 'dadosr_apt_jan.csv')
        
        Returns:
            pd.DataFrame: DataFrame com os dados processados, ou DataFrame vazio em caso de erro
        """
        # OTIMIZAÇÃO: Verificar cache primeiro (SEM LOGS se usar cache)
        if fonte is None:  # Apenas dados padrão usam cache
            cached_dados = _get_cached_dados()
            if cached_dados is not None:
                # SEM LOGS para evitar spam - dados já estão processados
                return cached_dados
        
        # Cache miss ou fonte específica - carregar dados
        try:
            # Determina o arquivo a ser carregado
            if fonte:
                # Obtém o diretório data (mesmo local do dadosr.csv)
                data_dir = self.csv_path.parent
                
                # CORREÇÃO CRÍTICA: Se a fonte não tem extensão, adiciona .csv
                if not fonte.endswith('.csv'):
                    fonte = fonte + '.csv'
                    
                csv_path = data_dir / fonte
                # OTIMIZAÇÃO: Log reduzido apenas para fontes específicas
                if fonte != 'dadosr.csv':
                    logger.info(f"Carregando fonte específica: {csv_path}")
            else:
                # OTIMIZAÇÃO: Log silenciado para carregamento padrão (evita spam)
                csv_path = self.csv_path
            
            # Verifica se o arquivo existe
            if not csv_path.is_file():
                logger.error(f"Arquivo CSV não encontrado: {csv_path}")
                return pd.DataFrame()
            
            # Lê o CSV com parâmetros corretos
            dados = pd.read_csv(
                csv_path,
                dtype=str,
                sep=';',
                encoding='latin1',
            )
            # OTIMIZAÇÃO: Log reduzido para evitar spam
            
            # OTIMIZAÇÃO: Processar dados sem logs excessivos
            dados_processados = self._processar_dados_otimizado(dados, csv_path)
            
            # OTIMIZAÇÃO: Cachear apenas dados padrão
            if fonte is None:
                _set_cached_dados(dados_processados)
            
            return dados_processados
            
        except Exception as e:
            logger.error(f"Erro ao carregar dados: {str(e)}")
            return pd.DataFrame()

    def _processar_dados_otimizado(self, dados, csv_path):
        """
        Processa dados com logs mínimos para evitar spam.
        OTIMIZAÇÃO: Versão silenciosa do processamento original.
        """
        try:
            # --- Passo 1.2: Tratamento Inicial (SEM LOGS EXCESSIVOS) ---
            
            # 1.2.1 Conversão de Datas (silenciosa)
            colunas_data_simples = ['Aberto em', 'Resolvido em', 'Data da última ação']
            for col in colunas_data_simples:
                if col in dados.columns:
                    original_col = dados[col].copy()
                    dados[col] = pd.to_datetime(original_col, format='%d/%m/%Y', errors='coerce')
                    # OTIMIZAÇÃO: Logs removidos para evitar spam

            # Tratamento especial para 'Vencimento em' (silencioso)
            if 'Vencimento em' in dados.columns:
                col_vencimento = 'Vencimento em'
                original_vencimento = dados[col_vencimento].copy()
                dados[col_vencimento] = pd.to_datetime(original_vencimento, format='%d/%m/%Y %H:%M', errors='coerce')
                mask_nat = dados[col_vencimento].isna()
                mask_retry = mask_nat & original_vencimento.notna() & (original_vencimento != '')
                if mask_retry.any():
                    dados.loc[mask_retry, col_vencimento] = pd.to_datetime(original_vencimento[mask_retry], format='%d/%m/%Y', errors='coerce')

            # 1.2.2 Conversão Numérica (silenciosa)
            if 'Número' in dados.columns:
                dados['Número'] = pd.to_numeric(dados['Número'], errors='coerce').astype('Int64')

            if 'Esforço estimado' in dados.columns:
                dados['Esforço estimado'] = dados['Esforço estimado'].str.replace(',', '.', regex=False)
                dados['Esforço estimado'] = pd.to_numeric(dados['Esforço estimado'], errors='coerce').fillna(0.0)
            else:
                dados['Esforço estimado'] = 0.0

            if 'Andamento' in dados.columns:
                dados['Andamento'] = dados['Andamento'].str.rstrip('%').str.replace(',', '.', regex=False)
                dados['Andamento'] = pd.to_numeric(dados['Andamento'], errors='coerce').fillna(0.0)
                dados['Andamento'] = dados['Andamento'].clip(lower=0, upper=100)
            else:
                dados['Andamento'] = 0.0
            
            # 1.2.3 Conversão de Tempo para Horas Decimais (silenciosa)
            if 'Tempo trabalhado' in dados.columns:
                dados['Tempo trabalhado'] = dados['Tempo trabalhado'].apply(self.converter_tempo_para_horas)
            else:
                dados['Tempo trabalhado'] = 0.0

            # --- Passo 1.3: Renomeação (SEM LOGS EXCESSIVOS) ---
            rename_map_new_to_old = {
                'Número': 'Numero',
                'Cliente (Completo)': 'Projeto',
                'Serviço (2º Nível)': 'Squad',
                'Status': 'Status',
                'Esforço estimado': 'Horas',
                'Tempo trabalhado': 'HorasTrabalhadas',
                'Andamento': 'Conclusao',
                'Data da última ação': 'UltimaInteracao',
                'Tipo de faturamento': 'Faturamento',
                'Responsável': 'Especialista',
                'Account Manager ': 'Account Manager',
                'Aberto em': 'DataInicio',
                'Resolvido em': 'DataTermino',
                'Vencimento em': 'VencimentoEm'
            }
            
            colunas_para_renomear = {k: v for k, v in rename_map_new_to_old.items() if k in dados.columns}
            dados.rename(columns=colunas_para_renomear, inplace=True)
            # OTIMIZAÇÃO: Log removido para evitar spam

            # --- Passo 1.4: Padronização Final (SEM LOGS EXCESSIVOS) ---
            
            # 1.4.1 Padronização de Status (silenciosa)
            if 'Status' in dados.columns:
                dados['Status'] = dados['Status'].astype(str).str.strip().str.upper()

            # 1.4.2 Padronização de Faturamento (silenciosa)
            faturamento_map = {
                "PRIME": "PRIME",
                "Descontar do PLUS no inicio do projeto": "PLUS",
                "Faturar no inicio do projeto": "INICIO",
                "Faturar no final do projeto": "TERMINO",
                "Faturado em outro projeto": "FEOP",
                "Engajamento": "ENGAJAMENTO"
            }
            if 'Faturamento' in dados.columns:
                dados['Faturamento'] = dados['Faturamento'].astype(str).str.strip()
                dados['Faturamento'] = dados['Faturamento'].str.rstrip('. ').str.strip()
                dados['Faturamento_Original'] = dados['Faturamento']
                dados['Faturamento'] = dados['Faturamento'].map(faturamento_map)
                nao_mapeados = dados['Faturamento'].isna()
                if nao_mapeados.any():
                    dados['Faturamento'] = dados['Faturamento'].fillna('NAO_MAPEADO')

            # 1.4.3 Padronização de outras colunas de texto (silenciosa)
            colunas_texto_padrao = ['Projeto', 'Squad', 'Especialista', 'Account Manager']
            for col in colunas_texto_padrao:
                if col in dados.columns:
                    dados[col] = dados[col].astype(str).str.strip()
                    dados[col] = dados[col].fillna('')
            
            # Cálculo de HorasRestantes (silencioso)
            if 'Horas' in dados.columns and 'HorasTrabalhadas' in dados.columns:
                dados['HorasRestantes'] = (dados['Horas'] - dados['HorasTrabalhadas']).round(1)
            else:
                dados['HorasRestantes'] = 0.0

            # OTIMIZAÇÃO: Log mínimo apenas quando necessário
            # logger.info(f"Dados processados: {len(dados)} registros")
            return dados
            
        except Exception as e:
            logger.error(f"Erro ao processar dados: {str(e)}")
            return pd.DataFrame()

    def obter_dados_e_referencia_atual(self):
        """
        Carrega os dados atuais (dadosr.csv) e define o mês de referência como o mês atual do sistema.
        
        A Visão Atual sempre usa:
        - Dados: dadosr.csv (dados correntes do mês atual)
        - Mês de referência: Mês atual do sistema (hoje = 04/Junho/2025 -> Junho/2025)
        - Comparações: Com dados históricos dos meses anteriores (Maio, Abril, Março)

        Returns:
            tuple: (pd.DataFrame, datetime.datetime) contendo os dados carregados
                   e o mês de referência (primeiro dia do mês atual). Retorna (DataFrame vazio, None)
                   se os dados não puderem ser carregados.
        """
        logger.info("Obtendo dados atuais (dadosr.csv) para Visão Atual...")
        
        # SEMPRE usa dadosr.csv para a visão atual
        dados_atuais = self.carregar_dados(fonte=None)  # Carrega dadosr.csv

        if dados_atuais.empty:
            logger.warning("Não foi possível carregar dados atuais (dadosr.csv).")
            return pd.DataFrame(), None

        # Para a Visão Atual, SEMPRE usa o mês atual do sistema
        mes_referencia_atual = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        logger.info(f"Visão Atual - Mês de referência definido como mês atual: {mes_referencia_atual.strftime('%B/%Y')}")
        
        # Log informativo sobre as datas nos dados (apenas para debug)
        if 'UltimaInteracao' in dados_atuais.columns:
            datas_interacao = pd.to_datetime(dados_atuais['UltimaInteracao'], errors='coerce')
            datas_validas = datas_interacao.dropna()
            if not datas_validas.empty:
                data_maxima = datas_validas.max()
                data_minima = datas_validas.min()
                logger.info(f"Dados carregados: datas de {data_minima.strftime('%d/%m/%Y')} até {data_maxima.strftime('%d/%m/%Y')} ({len(dados_atuais)} registros)")

        return dados_atuais, mes_referencia_atual

    def converter_tempo_para_horas(self, tempo_str):
        """Converte string de tempo (HH:MM:SS) para horas decimais"""
        try:
            if pd.isna(tempo_str) or tempo_str == '':
                return 0.0
            if isinstance(tempo_str, (int, float)):
                return float(tempo_str)
            # Remove espaços e converte para string
            tempo_str = str(tempo_str).strip()
            # Se já for um número, retorna como float
            if tempo_str.replace('.', '').isdigit():
                return float(tempo_str)
            # Converte formato HH:MM:SS para horas
            partes = tempo_str.split(':')
            if len(partes) == 3:
                horas = int(partes[0])
                minutos = int(partes[1])
                segundos = int(partes[2])
                return horas + (minutos/60) + (segundos/3600)
            elif len(partes) == 2:
                horas = int(partes[0])
                minutos = int(partes[1])
                return horas + (minutos/60)
            return 0.0
        except Exception as e:
            logger.error(f"Erro ao converter tempo '{tempo_str}': {str(e)}")
            return 0.0

    def obter_metricas_macro(self, dados):
        """Obtém métricas para o dashboard macro"""
        try:
            if dados is None or dados.empty:
                return {}
                
            metricas = {
                'total_projetos': len(dados),
                'projetos_ativos': len(dados[dados['Status'] == STATUS_ATIVO]),
                'projetos_criticos': len(dados[dados['Status'] == STATUS_CRITICO]),
                'projetos_concluidos': len(dados[dados['Status'] == STATUS_CONCLUIDO]),
                'projetos_em_atendimento': len(dados[dados['Status'] == STATUS_ATENDIMENTO])
            }
            
            return metricas
            
        except Exception as e:
            logger.error(f"Erro ao obter métricas macro: {str(e)}")
            return {}
            
    def obter_projetos_por_especialista(self, dados, nome_especialista):
        """Obtém projetos por especialista"""
        try:
            if dados is None or dados.empty:
                return []
                
            projetos = dados[dados['Especialista'] == nome_especialista].copy()
            
            # Adiciona verificação de backlog usando a função auxiliar
            projetos = self._adicionar_verificacao_backlog(projetos)
            
            return self._formatar_projetos(projetos)
            
        except Exception as e:
            logger.error(f"Erro ao obter projetos por especialista: {str(e)}")
            return []
            
    def obter_projetos_por_account(self, dados, nome_account):
        """Obtém projetos por account manager"""
        try:
            if dados is None or dados.empty:
                return []
                
            projetos = dados[dados['Account Manager'] == nome_account].copy()
            
            # Adiciona verificação de backlog usando a função auxiliar  
            projetos = self._adicionar_verificacao_backlog(projetos)
            
            return self._formatar_projetos(projetos)
            
        except Exception as e:
            logger.error(f"Erro ao obter projetos por account: {str(e)}")
            return []
            
    def obter_projetos_ativos(self, dados):
        """Obtém projetos ativos"""
        try:
            if dados is None or dados.empty:
                 logger.warning("DataFrame vazio fornecido para obter_projetos_ativos.")
                 return []
            
            if 'Status' not in dados.columns:
                 logger.error("Coluna 'Status' não encontrada no DataFrame.")
                 return []

            # CORREÇÃO: Usar isin com a lista self.status_ativos
            filtro_status = dados['Status'].isin(self.status_ativos)
            projetos = dados[filtro_status]
            logger.info(f"Filtrando por status ativos: {self.status_ativos}. Encontrados: {len(projetos)}")
            
            return self._formatar_projetos(projetos)
            
        except Exception as e:
            # Log do erro completo para melhor diagnóstico
            logger.error(f"Erro ao obter projetos ativos: {str(e)}", exc_info=True)
            return []

    def obter_projetos_criticos(self, dados):
        """Obtém projetos críticos"""
        try:
            if dados is None or dados.empty:
                return []
                
            projetos = dados[dados['Status'] == STATUS_CRITICO]
            return self._formatar_projetos(projetos)
            
        except Exception as e:
            logger.error(f"Erro ao obter projetos críticos: {str(e)}")
            return []
            
    def obter_projetos_concluidos(self, dados):
        """Obtém projetos concluídos"""
        try:
            if dados is None or dados.empty:
                return []
                
            projetos = dados[dados['Status'] == STATUS_CONCLUIDO]
            return self._formatar_projetos(projetos)
            
        except Exception as e:
            logger.error(f"Erro ao obter projetos concluídos: {str(e)}")
            return []
            
    def obter_projetos_eficiencia(self, dados):
        """Obtém projetos ordenados por eficiência"""
        try:
            if dados is None or dados.empty:
                return []
                
            # Calcular eficiência (conclusão / horas trabalhadas)
            dados['Eficiencia'] = dados['Conclusao'] / dados['HorasTrabalhadas']
            
            # Ordenar por eficiência
            projetos = dados.sort_values('Eficiencia', ascending=False)
            return self._formatar_projetos(projetos)
            
        except Exception as e:
            logger.error(f"Erro ao obter projetos por eficiência: {str(e)}")
            return []

    def _formatar_projetos(self, projetos):
        """Formata dados dos projetos para retorno usando os nomes RENOMEADOS."""
        # Nomes das colunas APÓS renomeação em carregar_dados
        col_numero = 'Numero' # Ou 'Número' se a renomeação falhar/não ocorrer
        col_projeto = 'Projeto'
        col_status = 'Status'
        col_squad = 'Squad'
        col_especialista = 'Especialista'
        col_account = 'Account Manager' # Atenção ao espaço no final se não foi removido na renomeação
        col_data_inicio = 'DataInicio'
        col_data_vencimento = 'VencimentoEm'
        col_conclusao = 'Conclusao'
        col_horas_trab = 'HorasTrabalhadas'
        col_horas_rest = 'HorasRestantes' # Calculado em preparar_dados_base
        col_horas_prev = 'Horas' # Nome após renomeação de 'Esforço estimado'

        resultados = []
        try:
            for _, row in projetos.iterrows():
                # Usa .get(col_name, default_value) para evitar KeyError se uma coluna não existir
                # por algum motivo inesperado no processamento anterior.
                numero_val = row.get(col_numero, '')
                # Fallback para 'Número' original se 'Numero' não existir
                if numero_val == '' and 'Número' in row:
                    numero_val = row.get('Número', '')
                
                # Trata Account Manager com e sem espaço no final
                account_val = row.get(col_account, row.get('Account Manager ', ''))
                
                # Formata as datas com verificação
                data_inicio_str = row.get(col_data_inicio, pd.NaT)
                data_inicio_fmt = data_inicio_str.strftime('%d/%m/%Y') if pd.notna(data_inicio_str) else ''
                
                data_vencimento_str = row.get(col_data_vencimento, pd.NaT)
                data_vencimento_fmt = data_vencimento_str.strftime('%d/%m/%Y') if pd.notna(data_vencimento_str) else 'N/A'
                
                resultados.append({
                    'numero': numero_val,
                    'projeto': row.get(col_projeto, 'N/A'),
                    'status': row.get(col_status, 'N/A'),
                    'squad': row.get(col_squad, 'N/A'),
                    'especialista': row.get(col_especialista, 'N/A'),
                    'account': account_val,
                    'data_inicio': data_inicio_fmt,
                    'dataPrevEnc': data_vencimento_fmt,  # CORRIGIDO: usar dataPrevEnc que o JS espera
                    'conclusao': float(row.get(col_conclusao, 0.0)) if pd.notna(row.get(col_conclusao)) else 0.0,
                    'horas_trabalhadas': float(row.get(col_horas_trab, 0.0)) if pd.notna(row.get(col_horas_trab)) else 0.0,
                    'horasRestantes': float(row.get(col_horas_rest, 0.0)) if pd.notna(row.get(col_horas_rest)) else 0.0,  # CORRIGIDO: usar horasRestantes que o JS espera
                    'Horas': float(row.get(col_horas_prev, 0.0)) if pd.notna(row.get(col_horas_prev)) else 0.0,  # CORRIGIDO: usar Horas que o JS espera
                    'backlog_exists': row.get('backlog_exists', False)  # Adiciona coluna backlog se existir
                })
            return resultados
            
        except Exception as e:
            # Log mais detalhado do erro e da linha onde ocorreu (se possível)
            logger.error(f"Erro ao formatar projetos: {str(e)}", exc_info=True)
            # Tenta retornar o que foi processado até agora
            return resultados if resultados else []

    def calcular_horas_restantes(self, dados):
        """Calcula horas restantes para cada projeto."""
        try:
            if 'HorasTrabalhadas' not in dados.columns or 'Horas' not in dados.columns:
                return dados
                
            # Converte horas previstas para numérico
            dados['Horas'] = pd.to_numeric(dados['Horas'].str.replace(',', '.'), errors='coerce')
            
            # Calcula horas restantes
            dados['HorasRestantes'] = dados['Horas'] - dados['HorasTrabalhadas']
            dados['HorasRestantes'] = dados['HorasRestantes'].clip(lower=0)
            
            return dados
            
        except Exception as e:
            logger.error(f"Erro ao calcular horas restantes: {str(e)}")
            return dados

    def calcular_projetos_ativos(self, dados):
        """
        Calcula especificamente os projetos ativos e suas métricas.
        Retorna um dicionário com:
        - total: número total de projetos ativos
        - dados: DataFrame com os projetos ativos (incluindo backlog_exists)
        - metricas: métricas específicas dos projetos ativos
        """
        try:
            logger.info("Calculando projetos ativos...")
            
            # Usa dados já tratados
            dados_base = self.preparar_dados_base(dados)
            
            # Filtra apenas projetos ativos (não concluídos) e exclui CDB DATA SOLUTIONS
            projetos_ativos_df = dados_base[
                (~dados_base['Status'].isin(self.status_concluidos)) &
                (dados_base['Squad'] != 'CDB DATA SOLUTIONS')
            ].copy()
            
            # Calcula métricas específicas (antes de adicionar backlog_exists)
            metricas = {
                'total': len(projetos_ativos_df),
                'por_squad': projetos_ativos_df.groupby('Squad').size().to_dict(),
                'media_conclusao': round(projetos_ativos_df['Conclusao'].mean(), 1),
                'media_horas_restantes': round(projetos_ativos_df['HorasRestantes'].mean(), 1)
            }
            
            # Prepara dados para o modal (colunas base)
            colunas_modal = ['Numero', 'Projeto', 'Status', 'Squad', 'Conclusao', 'HorasRestantes', 'VencimentoEm', 'Horas']
            
            # Certifica-se de que a coluna Numero existe
            if 'Numero' not in projetos_ativos_df.columns and 'Número' in projetos_ativos_df.columns:
                projetos_ativos_df['Numero'] = projetos_ativos_df['Número']
            elif 'Numero' not in projetos_ativos_df.columns:
                logger.warning("Coluna 'Numero' não encontrada nos projetos ativos. Criando coluna vazia.")
                projetos_ativos_df['Numero'] = ''
            else:
                 # Garante que 'Numero' seja string para a consulta do backlog
                 projetos_ativos_df['Numero'] = projetos_ativos_df['Numero'].astype(str)

            # <<< INÍCIO: Adicionar verificação de backlog >>>
            if not projetos_ativos_df.empty and 'Numero' in projetos_ativos_df.columns:
                # Pega todos os IDs de projeto (números) únicos e não vazios
                project_ids = projetos_ativos_df['Numero'].dropna().unique().tolist()
                project_ids = [pid for pid in project_ids if pid] # Remove vazios

                if project_ids:
                     # Consulta o banco para ver quais IDs têm backlog
                    try:
                        # Importa o modelo Backlog e db localmente para evitar importação circular
                        from app.models import Backlog
                        from app import db
                        
                        backlogs_existentes = db.session.query(Backlog.project_id)\
                                                        .filter(Backlog.project_id.in_(project_ids))\
                                                        .all()
                        # Cria um set com os IDs que têm backlog para busca rápida
                        ids_com_backlog = {result[0] for result in backlogs_existentes}
                        logger.info(f"Encontrados {len(ids_com_backlog)} backlogs para {len(project_ids)} projetos ativos verificados.")
                        
                        # Adiciona a coluna 'backlog_exists' ao DataFrame
                        projetos_ativos_df['backlog_exists'] = projetos_ativos_df['Numero'].apply(lambda pid: pid in ids_com_backlog if pd.notna(pid) else False)

                    except Exception as db_error:
                        logger.error(f"Erro ao consultar backlogs existentes: {db_error}", exc_info=True)
                        # Se der erro no DB, assume que nenhum backlog existe para não quebrar
                        projetos_ativos_df['backlog_exists'] = False
                else:
                    logger.info("Nenhum ID de projeto válido encontrado para verificar backlog.")
                    projetos_ativos_df['backlog_exists'] = False
            else:
                 logger.info("DataFrame de projetos ativos vazio ou sem coluna 'Numero'. Pulando verificação de backlog.")
                 # Garante que a coluna exista mesmo vazia
                 if 'Numero' in projetos_ativos_df.columns:
                      projetos_ativos_df['backlog_exists'] = False

            # <<< FIM: Adicionar verificação de backlog >>>

            # Seleciona apenas as colunas que existem no DataFrame final
            colunas_finais = colunas_modal + ['backlog_exists'] # Adiciona a nova coluna
            colunas_existentes = [col for col in colunas_finais if col in projetos_ativos_df.columns]
            
            dados_para_retorno = projetos_ativos_df[colunas_existentes].copy() # Usar .copy() para evitar SettingWithCopyWarning

            # <<< INÍCIO: Calcular tempo de vida do projeto >>>
            hoje = datetime.now().date()
            
            # Debug: mostrar colunas disponíveis
            logger.info(f"Colunas disponíveis para cálculo tempo de vida: {projetos_ativos_df.columns.tolist()}")
            
            def calcular_tempo_vida(row):
                try:
                    # Tenta encontrar data de abertura em diferentes colunas possíveis
                    data_abertura = None
                    
                    # Verifica colunas possíveis de data de abertura (ordem de prioridade)
                    colunas_possiveis = ['DataInicio', 'DataAbertura', 'Data Abertura', 'data_abertura', 'DataCriacao', 'Data Criacao', 'Data_Criacao', 'Aberto em']
                    for col in colunas_possiveis:
                        if col in row.index and pd.notna(row[col]):
                            data_abertura = row[col]
                            logger.debug(f"Encontrada data de abertura na coluna '{col}': {data_abertura} para projeto {row.get('Numero', 'N/A')}")
                            break
                    
                    if data_abertura is None:
                        # Se não encontrou data específica, usa uma estimativa baseada no número do projeto
                        # Projetos mais antigos têm números menores (aproximação)
                        if 'Numero' in row.index and pd.notna(row['Numero']):
                            numero = str(row['Numero'])
                            if numero.isdigit():
                                numero_int = int(numero)
                                # Estima: projetos com números menores são mais antigos
                                # Esta é uma aproximação que pode ser ajustada
                                if numero_int < 1000:
                                    logger.debug(f"Estimativa para projeto {numero}: 400 dias (< 1000)")
                                    return 400  # ~1 ano e 1 mês
                                elif numero_int < 3000:
                                    logger.debug(f"Estimativa para projeto {numero}: 300 dias (< 3000)")
                                    return 300  # ~10 meses
                                elif numero_int < 5000:
                                    logger.debug(f"Estimativa para projeto {numero}: 200 dias (< 5000)")
                                    return 200  # ~6-7 meses
                                elif numero_int < 7000:
                                    logger.debug(f"Estimativa para projeto {numero}: 150 dias (< 7000)")
                                    return 150  # ~5 meses
                                else:
                                    logger.debug(f"Estimativa para projeto {numero}: 90 dias (>= 7000)")
                                    return 90   # ~3 meses
                        logger.warning(f"Não foi possível calcular tempo de vida para projeto {row.get('Numero', 'N/A')} - dados insuficientes")
                        return None
                        
                    # Converte para datetime se for string
                    if isinstance(data_abertura, str):
                        # Tenta diferentes formatos de data
                        for formato in ['%Y-%m-%d', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S']:
                            try:
                                data_abertura = datetime.strptime(data_abertura, formato).date()
                                break
                            except ValueError:
                                continue
                    elif hasattr(data_abertura, 'date'):
                        data_abertura = data_abertura.date()
                    
                    if data_abertura:
                        diff = hoje - data_abertura
                        return diff.days
                        
                except Exception as e:
                    logger.debug(f"Erro ao calcular tempo de vida para projeto {row.get('Numero', 'N/A')}: {e}")
                
                return None
            
            # Adiciona coluna de tempo de vida
            dados_para_retorno['tempo_vida'] = projetos_ativos_df.apply(calcular_tempo_vida, axis=1)
            logger.info(f"Tempo de vida calculado - Exemplos: {dados_para_retorno['tempo_vida'].head().tolist()}")
            # <<< FIM: Calcular tempo de vida do projeto >>>

            # <<< INÍCIO: Restaurar Renomeação e Formatação >>>
            # Renomeia colunas para o formato esperado pelo frontend
            rename_map_final = {
                'Numero': 'numero',
                'Projeto': 'projeto',
                'Status': 'status',
                'Squad': 'squad',
                'Conclusao': 'conclusao',
                'HorasRestantes': 'horasRestantes',
                'VencimentoEm': 'dataPrevEnc',
                'Horas': 'Horas', # Manter Horas para cálculo no JS se necessário
                'backlog_exists': 'backlog_exists', # Manter a coluna de backlog
                'tempo_vida': 'tempo_vida' # Nova coluna de tempo de vida
            }
            # Filtra o mapa de renomeação para incluir apenas colunas que existem em dados_para_retorno
            colunas_para_renomear_final = {k: v for k, v in rename_map_final.items() if k in dados_para_retorno.columns}
            dados_para_retorno = dados_para_retorno.rename(columns=colunas_para_renomear_final)
            
            # Formata a data de vencimento (se a coluna existir após renomeação)
            if 'dataPrevEnc' in dados_para_retorno.columns:
                 # Primeiro converte para datetime (caso ainda não seja)
                 dados_para_retorno['dataPrevEnc'] = pd.to_datetime(dados_para_retorno['dataPrevEnc'], errors='coerce')
                 # Depois formata como string no formato brasileiro
                 dados_para_retorno['dataPrevEnc'] = dados_para_retorno['dataPrevEnc'].dt.strftime('%d/%m/%Y')
                 # Substitui valores NaT/None por 'N/A'
                 dados_para_retorno['dataPrevEnc'] = dados_para_retorno['dataPrevEnc'].fillna('N/A')
            # <<< FIM: Restaurar Renomeação e Formatação >>>

            logger.info(f"Calculados {metricas['total']} projetos ativos. Colunas retornadas após renomeação: {dados_para_retorno.columns.tolist()}")
            
            return {
                "total": metricas['total'],
                # Retorna o DataFrame formatado e substitui NaN por None na conversão para dict
                "dados": dados_para_retorno.replace({np.nan: None}), 
                "metricas": metricas
            }

        except KeyError as ke:
             logger.error(f"Erro de chave ao calcular projetos ativos: {ke}. Colunas disponíveis: {dados.columns.tolist()}", exc_info=True)
             # Retorna estrutura vazia em caso de erro grave de coluna
             return {"total": 0, "dados": pd.DataFrame(), "metricas": {}}
        except Exception as e:
            logger.exception(f"Erro inesperado ao calcular projetos ativos: {e}")
            # Retorna estrutura vazia em caso de erro inesperado
            return {"total": 0, "dados": pd.DataFrame(), "metricas": {}}

    def calcular_projetos_criticos(self, dados):
        """
        Calcula especificamente os projetos críticos e suas métricas.
        Um projeto é considerado crítico quando:
        - Está com status BLOQUEADO
        - Tem horas restantes negativas
        - Está com o prazo vencido
        Obs: Apenas projetos não concluídos são considerados
        """
        try:
            logger.info("Calculando projetos críticos...")
            
            # Usa dados já tratados
            dados_base = self.preparar_dados_base(dados)
            hoje = pd.Timestamp(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))
            logger.debug(f"Data de referência (hoje): {hoje.strftime('%d/%m/%Y')}")
            
            # Primeiro filtra apenas projetos não concluídos e exclui CDB DATA SOLUTIONS
            projetos_nao_concluidos = dados_base[
                (~dados_base['Status'].isin(self.status_concluidos)) &
                (dados_base['Squad'] != 'CDB DATA SOLUTIONS')
            ]
            logger.debug(f"Total de projetos não concluídos: {len(projetos_nao_concluidos)}")
            
            # Condições de criticidade (aplicadas apenas em projetos não concluídos)
            bloqueados = (projetos_nao_concluidos['Status'] == 'BLOQUEADO')
            logger.debug(f"Projetos bloqueados: {len(projetos_nao_concluidos[bloqueados])}")
            
            horas_negativas = (projetos_nao_concluidos['HorasRestantes'] < 0)
            logger.debug(f"Projetos com horas negativas: {len(projetos_nao_concluidos[horas_negativas])}")
            
            # Ajuste na verificação de prazo vencido
            projetos_nao_concluidos['VencimentoEm'] = pd.to_datetime(projetos_nao_concluidos['VencimentoEm']).dt.normalize()
            
            # Log para debug da data de hoje
            logger.debug(f"Data de referência (hoje normalizada): {hoje.strftime('%d/%m/%Y')}")
            
            # Verifica prazo vencido com log detalhado
            prazo_vencido = projetos_nao_concluidos.apply(
                lambda row: pd.notna(row['VencimentoEm']) and row['VencimentoEm'] < hoje,
                axis=1
            )
            
            # Log detalhado das comparações de data
            for idx, row in projetos_nao_concluidos.iterrows():
                if pd.notna(row['VencimentoEm']):
                    is_vencido = row['VencimentoEm'] < hoje
                    logger.debug(
                        f"Projeto: {row['Projeto']}, "
                        f"Data vencimento: {row['VencimentoEm'].strftime('%d/%m/%Y')}, "
                        f"Está vencido? {'Sim' if is_vencido else 'Não'}, "
                        f"Comparação: {row['VencimentoEm']} < {hoje}"
                    )
            
            logger.debug(f"Projetos com prazo vencido: {len(projetos_nao_concluidos[prazo_vencido])}")
            
            # Combina as condições
            projetos_criticos = projetos_nao_concluidos[bloqueados | horas_negativas | prazo_vencido].copy()
            
            # Log dos projetos críticos identificados
            logger.info(f"Total de projetos críticos identificados: {len(projetos_criticos)}")
            for idx, row in projetos_criticos.iterrows():
                logger.debug(f"Projeto crítico: {row['Projeto']}, "
                            f"Status: {row['Status']}, "
                            f"Horas Restantes: {row['HorasRestantes']}, "
                            f"Data vencimento: {row['VencimentoEm'].strftime('%d/%m/%Y') if pd.notna(row['VencimentoEm']) else 'N/A'}")
            
            # Adiciona motivos
            projetos_criticos['motivo'] = ''
            projetos_criticos.loc[bloqueados, 'motivo'] += 'Projeto bloqueado; '
            projetos_criticos.loc[horas_negativas, 'motivo'] += 'Horas excedidas; '
            projetos_criticos.loc[prazo_vencido, 'motivo'] += 'Prazo vencido; '
            projetos_criticos['motivo'] = projetos_criticos['motivo'].str.rstrip('; ')
            
            # Calcula métricas específicas
            metricas = {
                'total': len(projetos_criticos),
                'bloqueados': len(projetos_nao_concluidos[bloqueados]),
                'horas_negativas': len(projetos_nao_concluidos[horas_negativas]),
                'prazo_vencido': len(projetos_nao_concluidos[prazo_vencido])
            }
            
            # Certifica-se de que a coluna Numero existe
            if 'Numero' not in projetos_criticos.columns and 'Número' in projetos_criticos.columns:
                projetos_criticos['Numero'] = projetos_criticos['Número']
            elif 'Numero' not in projetos_criticos.columns:
                logger.warning("Coluna 'Numero' não encontrada em projetos críticos. Criando coluna vazia.")
                projetos_criticos['Numero'] = ''
            
            # Adiciona verificação de backlog usando a função auxiliar
            projetos_criticos = self._adicionar_verificacao_backlog(projetos_criticos)
            
            # Seleciona apenas as colunas existentes para retornar (igual ao método de projetos ativos)
            colunas_modal_criticos = ['Numero', 'Projeto', 'Status', 'Squad', 'Conclusao', 'HorasRestantes', 'VencimentoEm', 'Horas']
            
            # Certifica-se de que a coluna Numero existe
            if 'Numero' not in projetos_criticos.columns and 'Número' in projetos_criticos.columns:
                projetos_criticos['Numero'] = projetos_criticos['Número']
            elif 'Numero' not in projetos_criticos.columns:
                logger.warning("Coluna 'Numero' não encontrada nos projetos críticos. Criando coluna vazia.")
                projetos_criticos['Numero'] = ''
            else:
                # Garante que 'Numero' seja string
                projetos_criticos['Numero'] = projetos_criticos['Numero'].astype(str)

            # <<< INÍCIO: Adicionar verificação de backlog para projetos críticos >>>
            if not projetos_criticos.empty and 'Numero' in projetos_criticos.columns:
                project_ids = projetos_criticos['Numero'].dropna().unique().tolist()
                project_ids = [pid for pid in project_ids if pid]

                if project_ids:
                    try:
                        from app.models import Backlog
                        from app import db
                        
                        backlogs_existentes = db.session.query(Backlog.project_id)\
                                                        .filter(Backlog.project_id.in_(project_ids))\
                                                        .all()
                        ids_com_backlog = {result[0] for result in backlogs_existentes}
                        logger.info(f"Encontrados {len(ids_com_backlog)} backlogs para {len(project_ids)} projetos críticos verificados.")
                        
                        projetos_criticos['backlog_exists'] = projetos_criticos['Numero'].apply(
                            lambda pid: pid in ids_com_backlog if pd.notna(pid) else False
                        )

                    except Exception as db_error:
                        logger.error(f"Erro ao consultar backlogs para projetos críticos: {db_error}", exc_info=True)
                        projetos_criticos['backlog_exists'] = False
                else:
                    projetos_criticos['backlog_exists'] = False
            else:
                if 'Numero' in projetos_criticos.columns:
                    projetos_criticos['backlog_exists'] = False
            # <<< FIM: Adicionar verificação de backlog >>>

            # Adiciona a nova coluna de backlog à lista de colunas
            colunas_finais_criticos = colunas_modal_criticos + ['backlog_exists']
            colunas_existentes_criticos = [col for col in colunas_finais_criticos if col in projetos_criticos.columns]
            
            dados_para_retorno = projetos_criticos[colunas_existentes_criticos].copy()

            # <<< INÍCIO: Calcular tempo de vida para projetos críticos >>>
            hoje = datetime.now().date()
            
            # Debug: mostrar colunas disponíveis
            logger.info(f"Colunas disponíveis para projetos críticos: {projetos_criticos.columns.tolist()}")
            
            def calcular_tempo_vida_criticos(row):
                try:
                    # Tenta encontrar data de abertura em diferentes colunas possíveis
                    data_abertura = None
                    
                    # Verifica colunas possíveis de data de abertura (ordem de prioridade)
                    colunas_possiveis = ['DataInicio', 'DataAbertura', 'Data Abertura', 'data_abertura', 'DataCriacao', 'Data Criacao', 'DataCriacao', 'Data_Criacao']
                    for col in colunas_possiveis:
                        if col in row.index and pd.notna(row[col]):
                            data_abertura = row[col]
                            logger.debug(f"Encontrada data de abertura na coluna '{col}': {data_abertura} para projeto crítico {row.get('Numero', 'N/A')}")
                            break
                    
                    if data_abertura is None:
                        # Se não encontrou data específica, usa uma estimativa baseada no número do projeto
                        # Para projetos críticos, tendemos a assumir que são mais antigos
                        if 'Numero' in row.index and pd.notna(row['Numero']):
                            numero = str(row['Numero'])
                            if numero.isdigit():
                                numero_int = int(numero)
                                # Estima para projetos críticos (geralmente mais antigos)
                                if numero_int < 1000:
                                    logger.debug(f"Estimativa para projeto crítico {numero}: 500 dias (< 1000)")
                                    return 500  # ~1 ano e 4 meses
                                elif numero_int < 3000:
                                    logger.debug(f"Estimativa para projeto crítico {numero}: 400 dias (< 3000)")
                                    return 400  # ~1 ano e 1 mês
                                elif numero_int < 5000:
                                    logger.debug(f"Estimativa para projeto crítico {numero}: 300 dias (< 5000)")
                                    return 300  # ~10 meses
                                elif numero_int < 7000:
                                    logger.debug(f"Estimativa para projeto crítico {numero}: 200 dias (< 7000)")
                                    return 200  # ~6-7 meses
                                else:
                                    logger.debug(f"Estimativa para projeto crítico {numero}: 120 dias (>= 7000)")
                                    return 120  # ~4 meses
                        logger.warning(f"Não foi possível calcular tempo de vida para projeto crítico {row.get('Numero', 'N/A')} - dados insuficientes")
                        return None
                        
                    # Converte para datetime se for string
                    if isinstance(data_abertura, str):
                        # Tenta diferentes formatos de data
                        for formato in ['%Y-%m-%d', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S']:
                            try:
                                data_abertura = datetime.strptime(data_abertura, formato).date()
                                logger.debug(f"Data de abertura convertida com formato {formato}: {data_abertura}")
                                break
                            except ValueError:
                                continue
                    elif hasattr(data_abertura, 'date'):
                        data_abertura = data_abertura.date()
                    
                    if data_abertura:
                        diff = hoje - data_abertura
                        return diff.days
                        
                except Exception as e:
                    logger.debug(f"Erro ao calcular tempo de vida para projeto crítico {row.get('Numero', 'N/A')}: {e}")
                
                return None
            
            # Adiciona coluna de tempo de vida
            dados_para_retorno['tempo_vida'] = projetos_criticos.apply(calcular_tempo_vida_criticos, axis=1)
            logger.info(f"Tempo de vida calculado para críticos - Exemplos: {dados_para_retorno['tempo_vida'].head().tolist()}")
            # <<< FIM: Calcular tempo de vida >>>

            # Renomeia colunas para o formato esperado pelo frontend
            rename_map_criticos = {
                'Numero': 'numero',
                'Projeto': 'projeto',
                'Status': 'status',
                'Squad': 'squad',
                'Conclusao': 'conclusao',
                'HorasRestantes': 'horasRestantes',
                'VencimentoEm': 'dataPrevEnc',
                'Horas': 'Horas',
                'backlog_exists': 'backlog_exists',
                'tempo_vida': 'tempo_vida'
            }
            
            # Filtra o mapa de renomeação para incluir apenas colunas que existem
            colunas_para_renomear_criticos = {k: v for k, v in rename_map_criticos.items() if k in dados_para_retorno.columns}
            dados_para_retorno = dados_para_retorno.rename(columns=colunas_para_renomear_criticos)
            
            # Formata a data de vencimento
            if 'dataPrevEnc' in dados_para_retorno.columns:
                dados_para_retorno['dataPrevEnc'] = pd.to_datetime(dados_para_retorno['dataPrevEnc'], errors='coerce')
                dados_para_retorno['dataPrevEnc'] = dados_para_retorno['dataPrevEnc'].dt.strftime('%d/%m/%Y')
                dados_para_retorno['dataPrevEnc'] = dados_para_retorno['dataPrevEnc'].fillna('N/A')

            logger.info(f"Calculados {len(projetos_criticos)} projetos críticos. Colunas retornadas: {dados_para_retorno.columns.tolist()}")
            
            return {
                "total": len(projetos_criticos),
                "dados": dados_para_retorno.replace({np.nan: None}),
                "metricas": {
                    'bloqueados': len(projetos_nao_concluidos[bloqueados]),
                    'horas_negativas': len(projetos_nao_concluidos[horas_negativas]),
                    'prazo_vencido': len(projetos_nao_concluidos[prazo_vencido]),
                    'por_squad': projetos_criticos.groupby('Squad').size().to_dict()
                }
            }
            
        except Exception as e:
            logger.error(f"Erro ao calcular projetos críticos: {str(e)}", exc_info=True)
            return {'total': 0, 'dados': pd.DataFrame(), 'metricas': {}}

    def calcular_projetos_concluidos(self, dados):
        """
        Calcula métricas para projetos concluídos no mês atual.
        Retorna:
        - total: número total de projetos concluídos no mês
        - dados: DataFrame com os projetos concluídos
        - metricas: métricas específicas dos projetos concluídos
        """
        try:
            logger.info("Calculando projetos concluídos do mês atual...")
            
            # Obtém o mês e ano atual
            hoje = datetime.now()
            mes_atual = hoje.month
            ano_atual = hoje.year
            
            # Usa dados já tratados
            dados_base = self.preparar_dados_base(dados)
            
            # Filtra projetos concluídos e exclui CDB DATA SOLUTIONS
            projetos_concluidos = dados_base[
                (dados_base['Status'].isin(self.status_concluidos)) &
                (pd.to_datetime(dados_base['DataTermino']).dt.month == mes_atual) &
                (pd.to_datetime(dados_base['DataTermino']).dt.year == ano_atual) &
                (dados_base['Squad'] != 'CDB DATA SOLUTIONS')
            ].copy()
            
            # Calcula métricas
            total_concluidos = len(projetos_concluidos)
            if total_concluidos > 0:
                media_conclusao = projetos_concluidos['Conclusao'].mean()
                media_horas = projetos_concluidos['HorasTrabalhadas'].mean()
                projetos_por_squad = projetos_concluidos.groupby('Squad').size().to_dict()
            else:
                media_conclusao = 0
                media_horas = 0
                projetos_por_squad = {}
            
            # Adiciona verificação de backlog usando a função auxiliar
            projetos_concluidos = self._adicionar_verificacao_backlog(projetos_concluidos)
            
            # Prepara dados para o modal
            colunas_modal = ['Numero', 'Projeto', 'Status', 'Squad', 'Horas', 'HorasTrabalhadas', 'HorasRestantes', 'VencimentoEm', 'DataTermino', 'backlog_exists']
            dados_modal = projetos_concluidos[colunas_modal].copy()
            
            # Renomeia colunas para o formato esperado pelo frontend
            dados_modal = dados_modal.rename(columns={
                'Numero': 'numero',
                'Projeto': 'projeto',
                'Status': 'status',
                'Squad': 'squad',
                'Horas': 'horasContratadas',
                'HorasTrabalhadas': 'horasTrabalhadas',
                'HorasRestantes': 'horasRestantes',
                'VencimentoEm': 'dataPrevEnc',
                'DataTermino': 'dataTermino',
                'backlog_exists': 'backlog_exists'  # Mantém o nome
            })
            
            # Arredonda as horas para uma casa decimal
            dados_modal['horasContratadas'] = dados_modal['horasContratadas'].round(1)
            dados_modal['horasTrabalhadas'] = dados_modal['horasTrabalhadas'].round(1)
            dados_modal['horasRestantes'] = dados_modal['horasRestantes'].round(1)
            
            # Formata a data de término para o padrão brasileiro
            dados_modal['dataTermino'] = pd.to_datetime(dados_modal['dataTermino']).dt.strftime('%d/%m/%Y')
            
            # Formata a data de vencimento para o padrão brasileiro
            dados_modal['dataPrevEnc'] = pd.to_datetime(dados_modal['dataPrevEnc']).dt.strftime('%d/%m/%Y')
            
            # Calcula métricas adicionais
            metricas = {
                'media_conclusao': round(media_conclusao, 1),
                'media_horas': round(media_horas, 1),
                'total_projetos': total_concluidos,
                'projetos_por_squad': projetos_por_squad
            }
            
            logger.info(f"Total de projetos concluídos no mês: {total_concluidos}")
            
            return {
                'total': total_concluidos,
                'dados': dados_modal.replace({np.nan: None}),
                'metricas': metricas
            }
            
        except Exception as e:
            logger.error(f"Erro ao calcular projetos concluídos: {str(e)}", exc_info=True)
            return {'total': 0, 'dados': pd.DataFrame(), 'metricas': {}}

    def calcular_projetos_risco(self, dados):
        """
        Calcula projetos em risco com base em critérios preventivos:
        1. Menos de 20% das horas totais restantes
        2. Prazo próximo (15 dias) com conclusão menor que 70%
        3. Média de horas/dia até o prazo muito baixa (menos de 1 hora/dia)
        """
        try:
            hoje = pd.Timestamp(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))
            dados_base = self.preparar_dados_base(dados)
            projetos_risco = pd.DataFrame()
            
            logger.debug(f"Iniciando cálculo de projetos em risco. Total de projetos: {len(dados_base)}")
            
            # Filtra apenas projetos não concluídos e não críticos
            projetos_nao_concluidos = dados_base[
                ~dados_base['Status'].isin(self.status_concluidos) &
                ~dados_base['Status'].isin(['BLOQUEADO']) &
                (dados_base['Status'] != 'AGUARDANDO') & # <-- NOVA CONDIÇÃO: Status não pode ser AGUARDANDO
                (dados_base['HorasRestantes'] >= 0)
            ]
            
            # Normaliza as datas
            projetos_nao_concluidos['VencimentoEm'] = pd.to_datetime(projetos_nao_concluidos['VencimentoEm']).dt.normalize()
            
            # Lista para armazenar as condições
            condicoes = []
            
            # 1. Horas restantes críticas (menos de 20% das horas totais)
            if 'HorasRestantes' in dados_base.columns and 'Horas' in dados_base.columns:
                horas_criticas = (
                    (projetos_nao_concluidos['Horas'] > 0) & 
                    (projetos_nao_concluidos['HorasRestantes'] / projetos_nao_concluidos['Horas'] < 0.2) &
                    (projetos_nao_concluidos['HorasRestantes'] > 0)
                )
                condicoes.append(horas_criticas)
                logger.debug(f"Projetos com menos de 20% das horas: {len(projetos_nao_concluidos[horas_criticas])}")
            
            # 2. Projetos próximos ao prazo com conclusão preocupante
            if 'VencimentoEm' in dados_base.columns and 'Conclusao' in dados_base.columns:
                try:
                    dias_ate_termino = (projetos_nao_concluidos['VencimentoEm'] - hoje).dt.days
                    prazo_conclusao = (
                        (projetos_nao_concluidos['VencimentoEm'].notna()) &
                        (dias_ate_termino > 0) &  # Garante que não está vencido
                        (dias_ate_termino <= 15) &  # Próximo do prazo (15 dias)
                        (projetos_nao_concluidos['Conclusao'] < 70)  # Conclusão menor que 70%
                    )
                    condicoes.append(prazo_conclusao)
                    logger.debug(f"Projetos próximos ao prazo com conclusão preocupante: {len(projetos_nao_concluidos[prazo_conclusao])}")
                except Exception as e:
                    logger.error(f"Erro ao calcular projetos próximos ao prazo: {str(e)}")
            
            # 3. Horas restantes baixas em relação ao prazo
            if 'HorasRestantes' in dados_base.columns and 'VencimentoEm' in dados_base.columns and 'Horas' in dados_base.columns: # Adicionado 'Horas' in dados_base.columns
                try:
                    dias_ate_termino = (projetos_nao_concluidos['VencimentoEm'] - hoje).dt.days
                    horas_por_dia = projetos_nao_concluidos['HorasRestantes'] / dias_ate_termino.clip(lower=1)
                    horas_criticas_prazo = (
                        (projetos_nao_concluidos['Horas'] >= 30) &  # <-- Mínimo de 30h totais
                        (projetos_nao_concluidos['Status'] != 'AGUARDANDO') & # <-- NOVA CONDIÇÃO: Status não pode ser AGUARDANDO
                        (dias_ate_termino > 0) &  # Garante que não está vencido
                        (horas_por_dia < 1)  # Menos de 1 hora por dia até o prazo
                    )
                    condicoes.append(horas_criticas_prazo)
                    logger.debug(f"Projetos com poucas horas por dia até o prazo (e >= 30h totais e não AGUARDANDO): {len(projetos_nao_concluidos[horas_criticas_prazo])}")
                except Exception as e:
                    logger.error(f"Erro ao calcular horas por dia até o prazo: {str(e)}")
            
            # Combina todas as condições com OR lógico
            if condicoes:
                mascara_risco = np.logical_or.reduce(condicoes)
                projetos_risco = projetos_nao_concluidos[mascara_risco].copy()
                
                # Inicializa a coluna motivo_risco
                projetos_risco.loc[:, 'motivo_risco'] = ''
                
                # Adiciona os motivos específicos
                if 'HorasRestantes' in dados_base.columns and 'Horas' in dados_base.columns:
                    mascara_horas = (
                        (projetos_risco['Horas'] > 0) & 
                        (projetos_risco['HorasRestantes'] / projetos_risco['Horas'] < 0.2) & 
                        (projetos_risco['HorasRestantes'] > 0)
                    )
                    projetos_risco.loc[mascara_horas, 'motivo_risco'] += 'Restam menos de 20% das horas totais; '
                
                if 'VencimentoEm' in dados_base.columns and 'Conclusao' in dados_base.columns:
                    dias_ate_termino = (projetos_risco['VencimentoEm'] - hoje).dt.days
                    mascara_prazo = (
                        (dias_ate_termino > 0) &
                        (dias_ate_termino <= 15) &
                        (projetos_risco['Conclusao'] < 70)
                    )
                    projetos_risco.loc[mascara_prazo, 'motivo_risco'] += 'Prazo próximo (15 dias) com conclusão abaixo de 70%; '
                
                if 'HorasRestantes' in dados_base.columns and 'VencimentoEm' in dados_base.columns and 'Horas' in dados_base.columns: # Adicionado 'Horas' in dados_base.columns
                    dias_ate_termino = (projetos_risco['VencimentoEm'] - hoje).dt.days
                    horas_por_dia = projetos_risco['HorasRestantes'] / dias_ate_termino.clip(lower=1)
                    mascara_horas_dia = (
                        (projetos_risco['Horas'] >= 30) & # <-- Mínimo de 30h totais
                        (projetos_risco['Status'] != 'AGUARDANDO') & # <-- NOVA CONDIÇÃO: Status não pode ser AGUARDANDO
                        (dias_ate_termino > 0) &
                        (horas_por_dia < 1)
                    )
                    projetos_risco.loc[mascara_horas_dia, 'motivo_risco'] += 'Média de horas/dia até o prazo muito baixa; '
                
                # Remove o último '; ' do motivo
                projetos_risco['motivo_risco'] = projetos_risco['motivo_risco'].str.rstrip('; ')
                
                # Formata a data de vencimento para exibição
                projetos_risco['DataTermino'] = projetos_risco['VencimentoEm'].dt.strftime('%d/%m/%Y')
                projetos_risco['DataTermino'] = projetos_risco['DataTermino'].fillna('N/A')
                
                logger.info(f"Total de projetos em risco identificados: {len(projetos_risco)}")
                
                # Log para debug das datas
                for idx, row in projetos_risco.iterrows():
                    logger.debug(
                        f"Projeto em risco: {row['Projeto']}, "
                        f"Data Vencimento: {row['VencimentoEm'].strftime('%d/%m/%Y') if pd.notna(row['VencimentoEm']) else 'N/A'}, "
                        f"Data exibição: {row['DataTermino']}"
                    )
                
                return projetos_risco
            else:
                logger.warning("Nenhuma condição de risco foi aplicada")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Erro ao calcular projetos em risco: {str(e)}", exc_info=True)
            return pd.DataFrame()

    def preparar_dados_base(self, dados):
        """
        Prepara os dados base que serão usados por todas as funções de KPI.
        Faz as conversões e limpezas necessárias uma única vez.
        """
        try:
            dados_base = dados.copy()
            
            # Converte datas
            for col in ['DataInicio', 'DataTermino', 'VencimentoEm']:
                if col in dados_base.columns:
                    dados_base[col] = pd.to_datetime(dados_base[col], errors='coerce')
            
            # Garante tipos numéricos
            for col in ['Horas', 'HorasTrabalhadas', 'HorasRestantes', 'Conclusao']:
                if col in dados_base.columns:
                    dados_base[col] = pd.to_numeric(dados_base[col], errors='coerce').fillna(0.0)
            
            # Padroniza strings
            for col in ['Status', 'Squad', 'Especialista', 'Account Manager']:
                if col in dados_base.columns:
                    dados_base[col] = dados_base[col].str.strip().str.upper()
                    if col == 'Especialista':
                        dados_base[col] = dados_base[col].fillna('NÃO ALOCADO')
                    elif col == 'Account Manager':
                        dados_base[col] = dados_base[col].fillna('NÃO DEFINIDO')
                    else:
                        dados_base[col] = dados_base[col].fillna('NÃO DEFINIDO')
                elif col == 'Account Manager':
                    dados_base[col] = 'NÃO DEFINIDO'  # Garante que a coluna Account Manager sempre existe
            
            logger.debug(f"Dados base preparados. Colunas: {dados_base.columns.tolist()}")
            logger.debug(f"Account Managers após preparação: {dados_base['Account Manager'].unique().tolist() if 'Account Manager' in dados_base.columns else 'Coluna não existe'}")
            
            return dados_base
        except Exception as e:
            logger.error(f"Erro ao preparar dados base: {str(e)}", exc_info=True)
            return dados.copy()

    def calcular_media_horas(self, dados):
        """
        Calcula a média de horas dos projetos ativos.
        Retorna apenas a média geral para exibição no card.
        """
        try:
            logger.info("Calculando média de horas...")
            
            # Usa dados já tratados
            dados_base = self.preparar_dados_base(dados)
            
            # Filtra apenas projetos não concluídos
            projetos_nao_concluidos = dados_base[~dados_base['Status'].isin(self.status_concluidos)]
            
            # Calcula apenas a média geral
            media_geral = round(projetos_nao_concluidos['Horas'].mean(), 1)
            
            logger.info(f"Média de horas calculada: {media_geral}")
            
            return {
                'total': media_geral,  # para manter consistência com outros KPIs
                'metricas': {
                    'media_geral': media_geral,
                    'media_por_squad': projetos_nao_concluidos.groupby('Squad')['Horas'].mean().round(1).to_dict()
                }
            }
            
        except Exception as e:
            logger.error(f"Erro ao calcular média de horas: {str(e)}", exc_info=True)
            return {'total': 0.0, 'metricas': {'media_geral': 0.0, 'media_por_squad': {}}}

    def calcular_eficiencia_entrega(self, dados):
        """
        Calcula a eficiência de entrega dos projetos.
        Retorna:
        - total: eficiência geral (porcentagem)
        - dados: DataFrame com os projetos e suas eficiências
        - metricas: métricas específicas de eficiência
        """
        try:
            logger.info("Calculando eficiência de entrega...")
            
            # Usa dados já tratados
            dados_base = self.preparar_dados_base(dados)

            # --- NOVO: Filtra projetos da CDB DATA SOLUTIONS ---
            if 'Especialista' in dados_base.columns:
                # Usar .str.upper() para comparação case-insensitive e .isin() para clareza
                dados_filtrados_cdb = dados_base[~dados_base['Especialista'].astype(str).str.upper().isin(['CDB DATA SOLUTIONS'])]
                logger.info(f"Eficiência: Removidos {len(dados_base) - len(dados_filtrados_cdb)} projetos da CDB DATA SOLUTIONS.")
            else:
                logger.warning("Eficiência: Coluna 'Especialista' não encontrada para filtrar CDB.")
                dados_filtrados_cdb = dados_base.copy()
            # --- FIM NOVO FILTRO ---

            # --- NOVO: Filtra apenas projetos CONCLUÍDOS ---            
            projetos_concluidos_filtrados = dados_filtrados_cdb[
                dados_filtrados_cdb['Status'].isin(self.status_concluidos)
            ].copy()
            logger.info(f"Eficiência: Calculando com base em {len(projetos_concluidos_filtrados)} projetos concluídos (após filtro CDB).")
            # --- FIM NOVO FILTRO CONCLUÍDOS ---

            # Filtra projetos válidos (horas > 0) DENTRE OS CONCLUÍDOS
            projetos_validos = projetos_concluidos_filtrados[
                (projetos_concluidos_filtrados['Horas'] > 0) &
                (projetos_concluidos_filtrados['HorasTrabalhadas'] > 0)
            ].copy()

            # Calcula eficiência por projeto (INVERTIDO: Horas / HorasTrabalhadas)
            projetos_validos['eficiencia'] = (projetos_validos['Horas'] / projetos_validos['HorasTrabalhadas'] * 100).round(1)
            
            # Calcula eficiência geral (INVERTIDO: Horas / HorasTrabalhadas)
            if len(projetos_validos) > 0:
                horas_planejadas_total = projetos_validos['Horas'].sum()
                horas_trabalhadas_total = projetos_validos['HorasTrabalhadas'].sum()
                # Verifica se horas_trabalhadas_total > 0 para evitar divisão por zero (embora o filtro já deva garantir)
                if horas_trabalhadas_total > 0:
                    eficiencia_geral = round((horas_planejadas_total / horas_trabalhadas_total * 100), 1)
                else:
                    logger.warning("Eficiência: Total de horas trabalhadas é zero, definindo eficiência geral como 0.")
                    eficiencia_geral = 0.0 
            else:
                eficiencia_geral = 0.0

            # Adiciona verificação de backlog usando a função auxiliar
            projetos_validos = self._adicionar_verificacao_backlog(projetos_validos)

            # Prepara dados para o modal
            colunas_modal = ['Numero', 'Projeto', 'Status', 'Squad', 'Horas', 'HorasTrabalhadas', 'eficiencia', 'backlog_exists']
            
            # Certifica-se de que a coluna Numero existe
            if 'Numero' not in projetos_validos.columns and 'Número' in projetos_validos.columns:
                projetos_validos['Numero'] = projetos_validos['Número']
            elif 'Numero' not in projetos_validos.columns:
                logger.warning("Coluna 'Numero' não encontrada em projetos de eficiência. Criando coluna vazia.")
                projetos_validos['Numero'] = ''
                
            # Seleciona apenas as colunas que existem
            colunas_existentes = [col for col in colunas_modal if col in projetos_validos.columns]
            dados_modal = projetos_validos[colunas_existentes].copy()
            
            # Renomeia colunas para o formato esperado pelo frontend
            dados_modal = dados_modal.rename(columns={
                'Numero': 'numero',
                'Projeto': 'projeto',
                'Status': 'status',
                'Squad': 'squad',
                'Horas': 'horasContratadas',
                'HorasTrabalhadas': 'horasTrabalhadas',
                'eficiencia': 'eficiencia',
                'backlog_exists': 'backlog_exists'  # Mantém o nome
            })
            
            # Arredonda as horas para uma casa decimal
            dados_modal['horasContratadas'] = dados_modal['horasContratadas'].round(1)
            dados_modal['horasTrabalhadas'] = dados_modal['horasTrabalhadas'].round(1)
            
            # Calcula métricas adicionais
            metricas = {
                'eficiencia_geral': eficiencia_geral,
                'total_projetos': len(projetos_validos),
                'media_por_squad': projetos_validos.groupby('Squad')['eficiencia'].mean().round(1).to_dict(),
                'projetos_acima_100': len(projetos_validos[projetos_validos['eficiencia'] > 100]),
                'projetos_abaixo_50': len(projetos_validos[projetos_validos['eficiencia'] < 50])
            }
            
            logger.info(f"Eficiência de entrega calculada: {eficiencia_geral}%")
            
            return {
                'total': eficiencia_geral,
                'dados': dados_modal.replace({np.nan: None}),
                'metricas': metricas
            }
            
        except Exception as e:
            logger.error(f"Erro ao calcular eficiência de entrega: {str(e)}", exc_info=True)
            return {'total': 0.0, 'dados': pd.DataFrame(), 'metricas': {}}

    def calcular_kpis(self, dados):
        """Calcula KPIs principais do dashboard"""
        try:
            if dados.empty:
                return self.criar_kpis_vazios()

            # Usa dados já tratados
            dados_base = self.preparar_dados_base(dados)
            total_projetos = len(dados_base)
            
            # Usa funções específicas para cada KPI
            projetos_ativos = self.calcular_projetos_ativos(dados_base)
            projetos_criticos = self.calcular_projetos_criticos(dados_base)
            media_horas = self.calcular_media_horas(dados_base)
            eficiencia_entrega = self.calcular_eficiencia_entrega(dados_base)
            
            # Projetos concluídos
            projetos_concluidos = dados_base[dados_base['Status'].isin(self.status_concluidos)]
            projetos_concluidos_count = len(projetos_concluidos)

            # Eficiência de entrega
            eficiencia = 0.0
            if 'Horas' in dados_base.columns and 'HorasTrabalhadas' in dados_base.columns:
                projetos_com_horas = dados_base[
                    (dados_base['Horas'] > 0) &
                    (dados_base['HorasTrabalhadas'] > 0)
                ]
                if not projetos_com_horas.empty:
                    horas_planejadas = projetos_com_horas['Horas'].sum()
                    horas_trabalhadas = projetos_com_horas['HorasTrabalhadas'].sum()
                    if horas_planejadas > 0:
                        eficiencia = round((horas_trabalhadas / horas_planejadas) * 100, 1)

            kpis = {
                'projetos_ativos': projetos_ativos['total'],
                'total_projetos': total_projetos,
                'projetos_criticos': projetos_criticos['total'],
                'projetos_concluidos': projetos_concluidos_count,
                'porcentagem_concluidos': round((projetos_concluidos_count / total_projetos * 100), 1) if total_projetos > 0 else 0,
                'media_horas_projeto': media_horas['total'],
                'eficiencia_entrega': eficiencia
            }

            logger.info(f"[DEBUG] KPIs calculados: {kpis}")
            return kpis

        except Exception as e:
            logger.exception(f"Erro ao calcular KPIs: {str(e)}")
            return self.criar_kpis_vazios()

    def criar_kpis_vazios(self):
        return {
            'projetos_ativos': 0, 'total_projetos': 0, 'projetos_criticos': 0,
            'projetos_concluidos': 0, 'porcentagem_concluidos': 0.0,
            'media_horas_projeto': 0.0, 'eficiencia_entrega': 0.0
        }

    def calcular_agregacoes(self, dados):
        """
        Calcula agregações gerais dos dados, incluindo:
        - Distribuição por status
        - Agregações por squad
        - Projetos em risco
        
        Esta função mantém compatibilidade com o dashboard original e a página de apresentação.
        """
        try:
            logger.info("Calculando agregações gerais...")
            
            # Estrutura básica do resultado
            resultado = {
                'por_status': {},
                'por_squad': {},
                'projetos_risco': []
            }
            
            if dados.empty:
                logger.warning("DataFrame vazio ao calcular agregações")
                return resultado
            
            # Verificação de colunas essenciais
            if 'Status' not in dados.columns:
                logger.error("Coluna 'Status' não encontrada nos dados")
                return resultado
                
            # Prepara cópia de dados para evitar alterações no original
            dados_temp = dados.copy()
            
            # Garante que Status seja string e maiúsculo
            dados_temp['Status'] = dados_temp['Status'].astype(str).str.strip().str.upper()
            
            # Log dos valores únicos para debug
            status_unicos = dados_temp['Status'].unique().tolist()
            logger.info(f"Status únicos encontrados: {status_unicos}")
            
            # Se as colunas numéricas não existirem, cria com valores padrão
            for col, default in [('Horas', 0.0), ('HorasRestantes', 0.0), ('Conclusao', 0.0)]:
                if col not in dados_temp.columns:
                    logger.warning(f"Coluna '{col}' não encontrada. Criando com valor padrão {default}")
                    dados_temp[col] = default
                else:
                    # Converte para numérico, tratando valores problemáticos
                    dados_temp[col] = pd.to_numeric(dados_temp[col], errors='coerce').fillna(default)
            
            # Obtém o mês e ano atual para filtrar projetos fechados
            hoje = datetime.now()
            mes_atual = hoje.month
            ano_atual = hoje.year
            
            # Define os status ativos e outros
            status_ativos = ['NOVO', 'EM ATENDIMENTO', 'AGUARDANDO', 'BLOQUEADO']
            status_concluidos = ['FECHADO', 'RESOLVIDO', 'ENCERRADO']
            
            # Filtra apenas projetos ativos
            dados_ativos = dados_temp[~dados_temp['Status'].isin(status_concluidos)].copy()
            
            # 1. Agregações por Status
            # ------------------------
            por_status = {}
            
            # Agrupa por status e calcula as métricas
            # Modificado: Usar size() para contar linhas do grupo, mais robusto que contar não-nulos em 'Projeto'
            contagem_status = dados_ativos.groupby('Status').size()
            
            # Calcular métricas adicionais separadamente (se necessário)
            soma_horas = dados_ativos.groupby('Status')['Horas'].sum()
            media_conclusao = dados_ativos.groupby('Status')['Conclusao'].mean()
            
            # Status que serão ignorados no gráfico
            status_ignorados = ['ATRASADO', 'CANCELADO']
            logger.info(f"Status que serão ignorados no gráfico: {status_ignorados}")
            
            # Itera sobre os status contados
            for status, quantidade in contagem_status.items(): 
                # Pula status que não queremos exibir
                if status in status_ignorados:
                    logger.info(f"Ignorando status '{status}' conforme solicitado")
                    continue
                
                # Extrai valores garantindo que sejam válidos
                # quantidade = int(row['Projeto']) if pd.notna(row['Projeto']) else 0 <-- REMOVIDO
                horas_totais = float(soma_horas.get(status, 0.0)) # Usa .get com default
                conclusao_media = round(float(media_conclusao.get(status, 0.0)), 1) # Usa .get com default
                
                # Define a cor baseada no status
                if status == 'NOVO':
                    cor = 'info'  # azul claro
                elif status == 'EM ATENDIMENTO':
                    cor = 'primary'  # azul
                elif status == 'AGUARDANDO':
                    cor = 'warning'  # amarelo
                elif status == 'BLOQUEADO':
                    cor = 'dark'     # preto
                else:
                    cor = 'secondary'  # cinza
                
                por_status[status] = {
                    'quantidade': quantidade,
                    'horas_totais': round(horas_totais, 1),
                    'conclusao_media': conclusao_media,
                    'cor': cor,
                    'tipo': 'ativos' if status in status_ativos else 'outros'
                }
            
            # Garante que todos os status ativos existam, mesmo que vazios
            for status in status_ativos:
                if status not in por_status:
                    por_status[status] = {
                        'quantidade': 0,
                        'horas_totais': 0.0,
                        'conclusao_media': 0.0,
                        'cor': 'info' if status == 'NOVO' else ('primary' if status == 'EM ATENDIMENTO' else ('warning' if status == 'AGUARDANDO' else 'dark')),
                        'tipo': 'ativos'
                    }
            
            # Adiciona os projetos concluídos do mês atual
            if 'DataTermino' in dados_temp.columns:
                # Converte DataTermino para datetime se ainda não for
                if not pd.api.types.is_datetime64_any_dtype(dados_temp['DataTermino']):
                    dados_temp['DataTermino'] = pd.to_datetime(dados_temp['DataTermino'], errors='coerce')
                
                # Filtra projetos concluídos do mês atual
                projetos_concluidos_mes = dados_temp[
                    (dados_temp['Status'].isin(status_concluidos)) &
                    (dados_temp['DataTermino'].dt.month == mes_atual) &
                    (dados_temp['DataTermino'].dt.year == ano_atual)
                ]
                
                if not projetos_concluidos_mes.empty:
                    quantidade_concluidos = len(projetos_concluidos_mes)
                    horas_concluidos = projetos_concluidos_mes['Horas'].sum()
                    conclusao_concluidos = projetos_concluidos_mes['Conclusao'].mean()
                    
                    por_status['FECHADO'] = {
                        'quantidade': quantidade_concluidos,
                        'horas_totais': round(horas_concluidos, 1),
                        'conclusao_media': round(conclusao_concluidos, 1),
                        'cor': 'success',
                        'tipo': 'outros'
                    }
            
            resultado['por_status'] = por_status
            
            # 2. Agregações por Squad
            # -----------------------
            if 'Squad' in dados_temp.columns:
                # Normaliza os nomes dos squads
                dados_temp['Squad'] = dados_temp['Squad'].str.upper()
                
                # Agrupa por squad e calcula as métricas
                agregacao_squad = dados_ativos.groupby('Squad').agg({
                    'Projeto': 'count',    # quantidade
                    'Horas': 'sum',        # horas_totais
                    'Conclusao': 'mean'    # conclusao_media
                })
                
                por_squad = {}
                for squad, row in agregacao_squad.iterrows():
                    quantidade = int(row['Projeto']) if pd.notna(row['Projeto']) else 0
                    horas_totais = float(row['Horas']) if pd.notna(row['Horas']) else 0.0
                    conclusao_media = round(float(row['Conclusao']), 1) if pd.notna(row['Conclusao']) else 0.0
                    
                    por_squad[squad] = {
                        'quantidade': quantidade,
                        'horas_totais': round(horas_totais, 1),
                        'conclusao_media': conclusao_media
                    }
                
                resultado['por_squad'] = por_squad
            
            # 3. Projetos em Risco
            # --------------------
            projetos_risco_df = self.calcular_projetos_risco(dados_ativos)
            # Converter DataFrame para lista de dicts antes de adicionar ao resultado
            resultado['projetos_risco'] = projetos_risco_df.to_dict('records') if not projetos_risco_df.empty else []
            
            logger.info("Agregações calculadas com sucesso")
            return resultado
            
        except Exception as e:
            logger.error(f"Erro ao calcular agregações: {str(e)}", exc_info=True)
            return {
                'por_status': {},
                'por_squad': {},
                'projetos_risco': []
            }

    def calcular_historico_projetos(self, dados):
        """
        Calcula o histórico de projetos abertos e entregues nos últimos 4 meses.
        Retorna um dicionário com as datas e contagens.
        """
        try:
            if dados.empty:
                logger.warning("DataFrame vazio ao calcular histórico de projetos.")
                return {
                    'datas': [],
                    'projetos_abertos': [],
                    'projetos_entregues': []
                }

            # Obtém a data atual
            data_atual = pd.Timestamp.now()
            # Calcula a data de 4 meses atrás
            data_inicio = data_atual - pd.DateOffset(months=4)
            
            # Cria um range de datas mensais
            datas = pd.date_range(start=data_inicio, end=data_atual, freq='M')
            
            # Inicializa listas para armazenar as contagens
            projetos_abertos = []
            projetos_entregues = []
            
            # Para cada mês no range
            for data in datas:
                # Projetos abertos no mês
                abertos = len(dados[
                    (dados['DataInicio'].dt.to_period('M') == data.to_period('M'))
                ])
                
                # Projetos entregues no mês
                entregues = len(dados[
                    (dados['DataTermino'].dt.to_period('M') == data.to_period('M')) &
                    (dados['Status'].isin(self.status_concluidos))
                ])
                
                projetos_abertos.append(abertos)
                projetos_entregues.append(entregues)
            
            logger.info(f"Histórico calculado para {len(datas)} meses")
            logger.debug(f"Projetos abertos: {projetos_abertos}")
            logger.debug(f"Projetos entregues: {projetos_entregues}")
            
            return {
                'datas': [d.strftime('%B/%Y') for d in datas],
                'projetos_abertos': projetos_abertos,
                'projetos_entregues': projetos_entregues
            }
            
        except Exception as e:
            logger.exception(f"Erro ao calcular histórico de projetos: {str(e)}")
            return {
                'datas': [],
                'projetos_abertos': [],
                'projetos_entregues': []
            }

    def calcular_alocacao_especialistas(self, dados):
        """Calcula a alocação detalhada por especialista, focando em projetos ativos."""
        try:
            if dados.empty:
                logger.warning("DataFrame vazio ao calcular alocação por especialistas.")
                return {}

            # Usa dados já tratados
            dados_base = self.preparar_dados_base(dados)
            
            if 'Especialista' not in dados_base.columns:
                logger.warning("Coluna 'Especialista' não encontrada nos dados.")
                return {}

            # Filtra para incluir apenas projetos NÃO CONCLUÍDOS
            dados_ativos = dados_base[~dados_base['Status'].isin(self.status_concluidos)].copy()
            logger.info(f"Filtrando especialistas: {len(dados_base)} linhas no total -> {len(dados_ativos)} linhas ativas consideradas.")

            # --- NOVO: Calcular o número total de projetos ativos ---
            total_projetos_ativos_geral = len(dados_ativos)
            logger.info(f"Número total de projetos ativos (geral): {total_projetos_ativos_geral}")
            # ------------------------------------------------------

            # Garante que as colunas para agregação existem e são numéricas nos dados ATIVOS
            colunas_numericas = ['Horas', 'HorasTrabalhadas', 'HorasRestantes']
            for col in colunas_numericas:
                if col in dados_ativos.columns:
                    if dados_ativos[col].dtype == 'object':
                         dados_ativos[col] = dados_ativos[col].astype(str).str.strip().str.replace(',', '.', regex=False)
                    dados_ativos[col] = pd.to_numeric(dados_ativos[col], errors='coerce').fillna(0.0)
                else:
                    logger.warning(f"Coluna numérica '{col}' não encontrada nos dados ativos para cálculo de alocação. Usando 0.")
                    dados_ativos[col] = 0.0

            # Agrupa os dados JÁ FILTRADOS (ativos)
            agrupado = dados_ativos.groupby('Especialista', dropna=False)

            # Realiza as agregações necessárias
            sumario = agrupado.agg(
                # Conta os projetos ativos POR especialista
                total_projetos_especialista=('Projeto', 'count'),
                # Mantém as somas de horas para exibição na tabela
                total_horas_agregado=('Horas', 'sum'),
                horas_trabalhadas_agregado=('HorasTrabalhadas', 'sum'),
                horas_restantes_agregado=('HorasRestantes', 'sum')
            ).reset_index()

            # Calcula projetos bloqueados separadamente
            bloqueados = dados_ativos[dados_ativos['Status'] == 'BLOQUEADO'].groupby('Especialista').size()
            sumario = sumario.merge(bloqueados.rename('projetos_bloqueados'), on='Especialista', how='left')
            sumario['projetos_bloqueados'] = sumario['projetos_bloqueados'].fillna(0).astype(int)

            # Prepara o dicionário final
            resultado_final = {}
            for index, row in sumario.iterrows():
                especialista = row['Especialista']
                if pd.isna(especialista):
                    especialista = 'Não Alocado'
                
                # Número de projetos ativos DESTE especialista
                projetos_ativos_esp = row['total_projetos_especialista']
                # Obtém os valores de horas agregados
                total_horas_esp = row['total_horas_agregado']
                horas_restantes_esp = row['horas_restantes_agregado']
                horas_trabalhadas_esp = row['horas_trabalhadas_agregado']
                projetos_bloqueados = row['projetos_bloqueados']

                # --- NOVO CÁLCULO DA TAXA DE USO (BASEADO EM PROJETOS) ---
                taxa_uso = 0.0
                # Evita divisão por zero se não houver projetos ativos no total
                if total_projetos_ativos_geral > 0:
                    taxa_uso = round((projetos_ativos_esp / total_projetos_ativos_geral) * 100, 1)
                # ---------------------------------------------------------

                # --- NÍVEL DE RISCO (AJUSTADO para taxa baseada em PROJETOS) ---
                nivel_risco = 'secondary' # Padrão para 'Não Alocado' ou sem projetos
                if especialista != 'Não Alocado' and projetos_ativos_esp > 0:
                    # Ajuste os limites percentuais conforme necessário
                    if taxa_uso > 50: # Mais de 50% dos projetos ativos
                        nivel_risco = 'danger'
                    elif taxa_uso > 25: # Entre 25.1% e 50%
                        nivel_risco = 'warning'
                    else: # 25% ou menos
                        nivel_risco = 'success'
                # ----------------------------------------------------------

                resultado_final[especialista] = {
                    # A chave 'total_projetos' agora reflete os projetos ativos do especialista
                    'total_projetos': projetos_ativos_esp,
                    # Mantém as colunas de horas como antes
                    'horas_contratadas': round(total_horas_esp, 1),
                    'horas_trabalhadas': round(horas_trabalhadas_esp, 1),
                    'horas_restantes': round(horas_restantes_esp, 1),
                    'projetos_bloqueados': projetos_bloqueados,
                    'taxa_uso': taxa_uso, # Nova taxa (baseada em projetos)
                    'nivel_risco': nivel_risco # Novo risco (baseado na taxa de projetos)
                }

            logger.info(f"Alocação por especialista (ativos) calculada para {len(resultado_final)} especialistas.")
            if resultado_final:
                 first_key = list(resultado_final.keys())[0]
                 logger.debug(f"Exemplo alocação ('{first_key}'): {resultado_final[first_key]}")
            return resultado_final

        except Exception as e:
            logger.exception(f"Erro ao calcular alocação por especialistas: {str(e)}")
            return {}

    def preparar_dados_abas(self, dados):
        """Prepara dados agregados para as diferentes abas do dashboard"""
        dados_abas_padrao = {'dados_status': [], 'dados_especialistas': {}, 'dados_accounts': []}
        if dados.empty:
            logger.warning("DataFrame vazio ao preparar dados para abas.")
            return dados_abas_padrao

        try:
            # Usa dados já tratados
            dados_base = self.preparar_dados_base(dados)
            
            # --- Dados para aba de Status (usado no gráfico) ---
            # Reutiliza a agregação já feita
            agregacoes = self.calcular_agregacoes(dados_base)
            por_status_dict = agregacoes['por_status']
            # Converte para lista de dicionários se necessário para alguma tabela específica
            dados_status_lista = [{'Status': k, **v} for k, v in por_status_dict.items()]

            # --- Dados para aba de Especialistas ---
            dados_especialistas = self.calcular_alocacao_especialistas(dados_base)
            # Log já está dentro da função chamada

            # --- Dados para aba de Account Managers ---
            dados_accounts = []
            if 'Account Manager' in dados_base.columns:
                try:
                    # Status que indicam que o projeto não está mais ativo
                    STATUS_NAO_ATIVOS = ['FECHADO', 'ENCERRADO', 'RESOLVIDO', 'CANCELADO']
                    
                    # Filtra apenas projetos ativos
                    dados_ativos = dados_base[~dados_base['Status'].str.upper().isin([s.upper() for s in STATUS_NAO_ATIVOS])]
                    
                    # Log para debug
                    logger.debug(f"Total de projetos ativos para Account Managers: {len(dados_ativos)}")
                    
                    # Garante que colunas usadas na agregação são numéricas
                    for col in ['Horas', 'HorasRestantes', 'Conclusao']:
                        if col in dados_ativos.columns:
                            dados_ativos[col] = pd.to_numeric(dados_ativos[col], errors='coerce').fillna(0.0)

                    # Agrupa por Account Manager (incluindo 'Não Alocado')
                    accounts_agg = dados_ativos.groupby('Account Manager', dropna=False).agg(
                        total_projetos=('Projeto', 'count'),
                        horas_totais=('Horas', 'sum'),
                        horas_restantes=('HorasRestantes', 'sum'),
                        conclusao_media=('Conclusao', 'mean'),
                        projetos_bloqueados=('Status', lambda x: (x.str.upper() == 'BLOQUEADO').sum())
                    ).reset_index()

                    # Trata o caso de Account Manager ser NaN
                    accounts_agg['Account Manager'] = accounts_agg['Account Manager'].fillna('NÃO DEFINIDO')
                    
                    # Agrupa novamente se necessário
                    if accounts_agg['Account Manager'].duplicated().any():
                        accounts_agg = accounts_agg.groupby('Account Manager').agg({
                            'total_projetos': 'sum',
                            'horas_totais': 'sum',
                            'horas_restantes': 'sum',
                            'conclusao_media': 'mean',
                            'projetos_bloqueados': 'sum'
                        }).reset_index()

                    # Arredonda valores numéricos
                    for col in ['horas_totais', 'horas_restantes', 'conclusao_media']:
                        accounts_agg[col] = accounts_agg[col].round(1)

                    dados_accounts = accounts_agg.to_dict('records')
                    logger.debug(f"Dados para aba Account Managers preparados: {len(dados_accounts)} itens")
                    logger.debug(f"Account Managers encontrados: {accounts_agg['Account Manager'].tolist()}")
                except Exception as e:
                    logger.error(f"Erro ao preparar dados de Account Managers: {str(e)}")
                    dados_accounts = []
            else:
                logger.warning("Coluna 'Account Manager' não encontrada para preparar dados da aba.")

            return {
                'dados_status': dados_status_lista, # Retorna a lista para consistência
                'dados_especialistas': dados_especialistas, # Dicionário por especialista
                'dados_accounts': dados_accounts # Lista de dicionários por account
            }

        except Exception as e:
            logger.exception(f"Erro ao preparar dados para abas: {str(e)}")
            return dados_abas_padrao

    def calcular_tempo_medio_vida(self, dados, mes_referencia=None):
        """
        Calcula o tempo médio de vida dos projetos (em dias) concluídos
        em um mês específico.
        
        Args:
            dados: DataFrame com os dados dos projetos.
            mes_referencia: Data (datetime) do mês para filtrar os projetos concluídos.
                          Se None, usa o mês atual.
                          
        Returns:
            Dictionary com:
            - media_dias: média de dias entre início e término dos projetos concluídos no mês
            - total_projetos: número de projetos considerados no cálculo
            - distribuicao: distribuição dos projetos por faixa de tempo
            - dados: lista detalhada dos projetos considerados
        """
        try:
            # Define o mês de referência se não informado
            if not mes_referencia:
                mes_referencia = datetime.now()
            
            logger.info(f"Calculando tempo médio de vida para projetos concluídos em {mes_referencia.strftime('%m/%Y')}...")
            
            # Verifica se os dados são válidos
            if dados.empty:
                logger.warning("DataFrame vazio ao calcular tempo médio de vida")
                return {
                    'media_dias': 0,
                    'total_projetos': 0,
                    'distribuicao': {},
                    'dados': []
                }
            
            # Obtém dados do trimestre atual (fiscal Microsoft)
            hoje = datetime.now()
            # Determina o trimestre fiscal da Microsoft (começa em julho)
            mes_atual = hoje.month
            ano_atual = hoje.year
            
            # Determina o trimestre fiscal:
            # Q1: Jul-Sep, Q2: Oct-Dec, Q3: Jan-Mar, Q4: Apr-Jun
            if 7 <= mes_atual <= 9:
                quarter = "Q1"
                inicio_trimestre = datetime(ano_atual, 7, 1)
                fim_trimestre = datetime(ano_atual, 9, 30)
            elif 10 <= mes_atual <= 12:
                quarter = "Q2"
                inicio_trimestre = datetime(ano_atual, 10, 1)
                fim_trimestre = datetime(ano_atual, 12, 31)
            elif 1 <= mes_atual <= 3:
                quarter = "Q3"
                inicio_trimestre = datetime(ano_atual, 1, 1)
                fim_trimestre = datetime(ano_atual, 3, 31)
            else:  # 4-6
                quarter = "Q4"
                inicio_trimestre = datetime(ano_atual, 4, 1)
                fim_trimestre = datetime(ano_atual, 6, 30)
            
            # Filtra apenas projetos concluídos no trimestre atual
            dados_filtrados = dados.copy()
            
            # Normaliza Status para maiúsculo
            dados_filtrados['Status'] = dados_filtrados['Status'].str.upper()
            
            # Converte DataTermino e DataInicio para datetime
            dados_filtrados['DataTermino'] = pd.to_datetime(dados_filtrados['DataTermino'], errors='coerce')
            dados_filtrados['DataInicio'] = pd.to_datetime(dados_filtrados['DataInicio'], errors='coerce')
            
            # Calcula o primeiro e último dia do mês de referência
            ano_ref = mes_referencia.year
            mes_ref = mes_referencia.month
            inicio_mes_ref = datetime(ano_ref, mes_ref, 1)
            # Calcula o último dia do mês
            if mes_ref == 12:
                proximo_mes_inicio = datetime(ano_ref + 1, 1, 1)
            else:
                proximo_mes_inicio = datetime(ano_ref, mes_ref + 1, 1)
            fim_mes_ref = proximo_mes_inicio - timedelta(days=1)
            # Define o fim do dia para incluir todo o último dia
            fim_mes_ref = fim_mes_ref.replace(hour=23, minute=59, second=59, microsecond=999999)

            logger.info(f"Período de filtro para Tempo Médio Vida: {inicio_mes_ref.strftime('%Y-%m-%d')} a {fim_mes_ref.strftime('%Y-%m-%d')}")

            # --- INÍCIO DA ALTERAÇÃO PARA PERÍODO MÓVEL ---
            # Calcula o fim do período (último dia do mês de referência)
            ano_ref = mes_referencia.year
            mes_ref = mes_referencia.month
            # Calcula o último dia do mês de referência
            if mes_ref == 12:
                proximo_mes_inicio = datetime(ano_ref + 1, 1, 1)
            else:
                proximo_mes_inicio = datetime(ano_ref, mes_ref + 1, 1)
            fim_periodo = proximo_mes_inicio - timedelta(days=1)
            # Define o fim do dia para incluir todo o último dia
            fim_periodo = fim_periodo.replace(hour=23, minute=59, second=59, microsecond=999999)

            # Calcula o início do período (3 meses atrás, incluindo o atual)
            # Subtrai 2 meses da data de referência para obter o início da janela de 3 meses
            inicio_periodo_dt = mes_referencia.replace(day=1) # Garante que estamos no dia 1
            for _ in range(2): # Subtrai um mês duas vezes
                primeiro_dia_mes_anterior = inicio_periodo_dt - timedelta(days=1)
                inicio_periodo_dt = primeiro_dia_mes_anterior.replace(day=1)
            
            inicio_periodo = inicio_periodo_dt
            # Define o início do dia
            inicio_periodo = inicio_periodo.replace(hour=0, minute=0, second=0, microsecond=0)

            logger.info(f"Período de filtro para Tempo Médio Vida (últimos 3 meses): {inicio_periodo.strftime('%Y-%m-%d')} a {fim_periodo.strftime('%Y-%m-%d')}")
            # --- FIM DA ALTERAÇÃO PARA PERÍODO MÓVEL ---

            # Filtra apenas projetos concluídos no período
            projetos_concluidos = dados_filtrados[
                (dados_filtrados['Status'].str.upper().isin(self.status_concluidos)) &
                # (dados_filtrados['DataTermino'] >= inicio_trimestre) & # MUDAR
                # (dados_filtrados['DataTermino'] <= fim_trimestre) & # MUDAR
                (dados_filtrados['DataTermino'] >= inicio_periodo) & # ALTERADO
                (dados_filtrados['DataTermino'] <= fim_periodo) & # ALTERADO
                (dados_filtrados['DataInicio'].notna()) &
                (dados_filtrados['DataTermino'].notna())
            ].copy()

            logger.info(f"[Tempo Médio Vida - {mes_referencia.strftime('%m/%Y')} - Últimos 3 meses] Projetos concluídos encontrados no período: {len(projetos_concluidos)}") # Log ajustado

            # Log Adicionado: Verificar DataInicio e DataTermino dos projetos filtrados
            if not projetos_concluidos.empty:
                # Log detalhado do DataFrame filtrado
                logger.info(f"[Tempo Médio Vida - {mes_referencia.strftime('%m/%Y')}] DataFrame 'projetos_concluidos' ANTES do cálculo de tempo_vida:")
                try:
                    # Tenta logar como string para melhor visualização
                    log_df_str = projetos_concluidos[['Projeto', 'Status', 'DataInicio', 'DataTermino']].to_string()
                    logger.info(f"\n{log_df_str}\n") 
                except Exception as log_err:
                    logger.error(f"Erro ao formatar DataFrame para log: {log_err}")
                    # Fallback para log básico se to_string falhar
                    logger.info(projetos_concluidos[['Projeto', 'Status', 'DataInicio', 'DataTermino']].head())
                    
                # Verificar tipos das colunas de data DENTRO DESTE DATAFRAME FILTRADO
                if 'DataInicio' in projetos_concluidos.columns: logger.info(f"[Tempo Médio Vida - {mes_referencia.strftime('%m/%Y')}] Tipo DataInicio (filtrado): {projetos_concluidos['DataInicio'].dtype}")
                if 'DataTermino' in projetos_concluidos.columns: logger.info(f"[Tempo Médio Vida - {mes_referencia.strftime('%m/%Y')}] Tipo DataTermino (filtrado): {projetos_concluidos['DataTermino'].dtype}")
            
            if projetos_concluidos.empty:
                logger.warning("Nenhum projeto concluído neste mês para cálculo do tempo médio de vida")
                return {
                    'media_dias': 0,
                    'total_projetos': 0,
                    'distribuicao': {},
                    'dados': []
                }

            # Calcula a diferença em dias
            projetos_concluidos['tempo_vida'] = (
                projetos_concluidos['DataTermino'] - projetos_concluidos['DataInicio']
            ).dt.days

            # Log das durações calculadas ANTES de filtrar outliers
            logger.debug(f"  Durações calculadas (tempo_vida) antes de filtrar outliers:\n{projetos_concluidos[['Projeto', 'tempo_vida']]}") # Log Adicionado

            # Remove outliers (duração negativa ou maior que 365 dias)
            projetos_validos = projetos_concluidos[
                (projetos_concluidos['tempo_vida'] >= 0) &
                (projetos_concluidos['tempo_vida'] <= 365)
            ]

            logger.info(f"  Projetos válidos após filtrar outliers (<0 ou >365 dias): {len(projetos_validos)}") # Log Adicionado

            if projetos_validos.empty:
                logger.warning("Nenhum projeto válido após filtragem para cálculo do tempo médio de vida")
                return {
                    'media_dias': 0,
                    'total_projetos': 0,
                    'distribuicao': {},
                    'dados': []
                }

            # Calcula a média
            media_dias = round(projetos_validos['tempo_vida'].mean(), 1)

            # Cria faixas de tempo para distribuição
            def categorizar_tempo(dias):
                if dias <= 30:
                    return 'Até 30 dias'
                elif dias <= 90:
                    return '31 a 90 dias'
                elif dias <= 180:
                    return '91 a 180 dias'
                else:
                    return 'Mais de 180 dias'

            projetos_validos['faixa_tempo'] = projetos_validos['tempo_vida'].apply(categorizar_tempo)
            distribuicao = projetos_validos['faixa_tempo'].value_counts().to_dict()

            # Prepara dados detalhados para visualização
            dados_detalhados = projetos_validos[['Projeto', 'DataInicio', 'DataTermino', 'tempo_vida', 'Squad']].copy()
            dados_detalhados = dados_detalhados.sort_values('tempo_vida', ascending=False)

            logger.info(f"Tempo médio de vida calculado: {media_dias} dias, baseado em {len(projetos_validos)} projetos")
            logger.info(f"Distribuição por faixa: {distribuicao}")

            return {
                'media_dias': media_dias,
                'total_projetos': len(projetos_validos),
                'distribuicao': distribuicao,
                'dados': dados_detalhados.to_dict('records')
            }

        except Exception as e:
            logger.error(f"Erro ao calcular tempo médio de vida dos projetos: {str(e)}")
            return {
                'media_dias': 0,
                'total_projetos': 0,
                'distribuicao': {},
                'dados': []
            }

    def calcular_ocupacao_squads(self, dados):
        """
        Calcula a ocupação por squad, incluindo horas restantes e percentual de ocupação.
        Retorna uma lista de dicionários com informações de cada squad.
        """
        try:
            logger.info("Calculando ocupação por squad...")
            
            # Configurações de capacidade por squad (igual ao Gerencial)
            HORAS_POR_PESSOA = 180  # horas/mês
            PESSOAS_POR_SQUAD = 3   # pessoas por squad
            CAPACIDADE_TOTAL = HORAS_POR_PESSOA * PESSOAS_POR_SQUAD  # 540 horas por squad
            
            # Usa dados já tratados
            dados_base = self.preparar_dados_base(dados)
            
            # Primeiro filtramos especialistas da CDB DATA SOLUTIONS (antes de qualquer outro filtro)
            # Isso garante que não incluímos projetos da CDB DATA SOLUTIONS no cálculo
            if 'Especialista' in dados_base.columns:
                dados_base = dados_base[dados_base['Especialista'] != 'CDB DATA SOLUTIONS']
            
            # Filtra apenas projetos ativos e exclui o Squad CDB DATA SOLUTIONS também
            projetos_ativos = dados_base[
                (~dados_base['Status'].isin(self.status_concluidos)) &
                (dados_base['Squad'] != 'CDB DATA SOLUTIONS')
            ].copy()
            
            # Adiciona logs detalhados para depuração, especialmente para DATA E POWER
            data_power_projetos = projetos_ativos[projetos_ativos['Squad'] == 'DATA E POWER']
            if not data_power_projetos.empty:
                logger.info(f"Encontrados {len(data_power_projetos)} projetos para o squad DATA E POWER:")
                for _, projeto in data_power_projetos.iterrows():
                    logger.info(f"  Projeto: {projeto.get('Projeto', 'N/A')}")
                    logger.info(f"    Status: {projeto.get('Status', 'N/A')}")
                    logger.info(f"    Horas Originais: {projeto.get('Horas', 0.0)}")
                    logger.info(f"    Horas Trabalhadas: {projeto.get('HorasTrabalhadas', 0.0)}")
                    logger.info(f"    Horas Restantes: {projeto.get('HorasRestantes', 0.0)}")
            
            # Ajusta horas restantes: para negativas, usa 10% do esforço inicial (igual ao Gerencial)
            # Melhorado para garantir exatamente 10% e logging detalhado
            def ajustar_horas_restantes(row):
                if row['HorasRestantes'] >= 0:
                    return row['HorasRestantes']
                else:
                    valor_ajustado = 0.10 * row['Horas']
                    if row['Squad'] == 'DATA E POWER':
                        logger.info(f"  Ajustando projeto {row.get('Projeto', 'N/A')}: "
                                  f"Horas Restantes: {row['HorasRestantes']} -> "
                                  f"Ajustado (10% de {row['Horas']}): {valor_ajustado}")
                    return valor_ajustado
            
            projetos_ativos['HorasRestantesAjustadas'] = projetos_ativos.apply(ajustar_horas_restantes, axis=1)
            
            # Separa projetos em planejamento
            planejamento_pmo = projetos_ativos[projetos_ativos['Squad'] == 'Em Planejamento - PMO'].copy()
            dados_squads = projetos_ativos[projetos_ativos['Squad'] != 'Em Planejamento - PMO'].copy()
            
            # Calcula horas totais em planejamento
            total_horas_planejamento = planejamento_pmo['HorasRestantesAjustadas'].sum() if not planejamento_pmo.empty else 0
            total_projetos_planejamento = len(planejamento_pmo)
            
            # Lista para armazenar os resultados
            resultado = []
            
            # Processa os squads regulares
            if not dados_squads.empty:
                # Agrupa por Squad
                squads = dados_squads.groupby('Squad').agg({
                    'Projeto': 'count',
                    'HorasRestantesAjustadas': 'sum'
                }).reset_index()
                
                for _, squad in squads.iterrows():
                    nome_squad = squad['Squad']
                    # Calcula o percentual de ocupação baseado na capacidade mensal
                    horas_restantes = squad['HorasRestantesAjustadas']
                    capacidade_utilizada = round((horas_restantes / CAPACIDADE_TOTAL * 100), 1)
                    horas_disponiveis = round(CAPACIDADE_TOTAL - horas_restantes, 1)
                    
                    # Verifica se há projetos com horas negativas para este squad
                    projetos_squad = dados_squads[dados_squads['Squad'] == nome_squad]
                    tem_horas_negativas = any(projetos_squad['HorasRestantes'] < 0)
                    
                    # Log detalhado para o squad DATA E POWER
                    if nome_squad == 'DATA E POWER':
                        logger.info(f"Detalhes do cálculo para Squad DATA E POWER:")
                        logger.info(f"  Total de projetos: {len(projetos_squad)}")
                        logger.info(f"  Soma das Horas Restantes (não ajustadas): {projetos_squad['HorasRestantes'].sum()}")
                        logger.info(f"  Soma das Horas Restantes Ajustadas: {horas_restantes}")
                    
                    # Adiciona HorasRestantesAjustadas à saída dos projetos para coerência na exibição
                    projetos_output = projetos_squad[['Projeto', 'Status', 'HorasRestantes', 'Conclusao']].copy()
                    # Adiciona a coluna de horas ajustadas para referência
                    projetos_output['HorasRestantesAjustadas'] = projetos_squad['HorasRestantesAjustadas']
                    
                    # Prepara os dados do squad
                    squad_info = {
                        'nome': nome_squad,
                        'horas_restantes': round(horas_restantes, 1),
                        'total_projetos': int(squad['Projeto']),
                        'percentual_ocupacao': capacidade_utilizada,
                        'tem_horas_negativas': tem_horas_negativas,
                        'capacidade_utilizada': capacidade_utilizada,
                        'horas_disponiveis': horas_disponiveis,
                        'projetos': projetos_output.to_dict('records')
                    }
                    resultado.append(squad_info)
            
            # Adiciona linha para Em Planejamento - PMO se houver projetos
            if total_projetos_planejamento > 0:
                pmo_info = {
                    'nome': 'Em Planejamento - PMO',
                    'horas_restantes': round(total_horas_planejamento, 1),
                    'total_projetos': total_projetos_planejamento,
                    'percentual_ocupacao': 0,  # Não calculamos percentual para planejamento
                    'tem_horas_negativas': False,
                    'capacidade_utilizada': 0,  # Não calculamos capacidade para planejamento
                    'horas_disponiveis': 0,     # Não calculamos horas disponíveis para planejamento
                    'projetos': planejamento_pmo[['Projeto', 'Status', 'HorasRestantes', 'Conclusao']].to_dict('records')
                }
                resultado.append(pmo_info)
            
            # Ordena por horas restantes (decrescente)
            resultado = sorted(resultado, key=lambda x: x['horas_restantes'], reverse=True)
            
            logger.info(f"Ocupação calculada para {len(resultado)} squads")
            return resultado
            
        except Exception as e:
            logger.error(f"Erro ao calcular ocupação por squad: {str(e)}", exc_info=True)
            return []

    def processar_gerencial(self, dados):
        """Processa dados para a visão gerencial com os status reais"""
        try:
            if dados.empty:
                logging.warning("DataFrame vazio recebido em processar_gerencial")
                return self.criar_estrutura_vazia()

            dados_limpos = dados.copy()
            
            # Padronização de dados (uppercase e trim)
            for col in ['Status', 'Faturamento']:
                if col in dados_limpos.columns:
                    dados_limpos[col] = dados_limpos[col].str.strip().str.upper()
            
            # Calcula métricas principais
            metricas = self.calcular_kpis(dados_limpos)
            
            # Calcula projetos em risco
            projetos_risco = self.calcular_projetos_risco(dados_limpos)
            
            # Calcula ocupação dos Squads
            ocupacao_squads = self.calcular_ocupacao_squads(dados_limpos)
            
            resultado = {
                'metricas_qualidade': metricas,
                'projetos_criticos': projetos_risco.replace({np.nan: None}).to_dict('records'),
                'projetos_por_squad': dados_limpos.groupby('Squad').size().to_dict(),
                'projetos_por_faturamento': dados_limpos.groupby('Faturamento').size().to_dict(),
                'squads_disponiveis': sorted(dados_limpos['Squad'].unique().tolist()),
                'faturamentos_disponiveis': sorted(dados_limpos['Faturamento'].unique().tolist()),
                'ocupacao_squads': ocupacao_squads
            }
            
            return resultado
            
        except Exception as e:
            logging.error(f"Erro no processamento: {str(e)}")
            return self.criar_estrutura_vazia()

    def calcular_projetos_por_faturamento(self, dados, mes_ref=None):
        """
        Calcula a distribuição de projetos por tipo de faturamento.
        
        Args:
            dados: DataFrame com os dados dos projetos
            mes_ref: Mês de referência para filtrar os dados (formato datetime)
        
        Returns:
            Dictionary com contagem por tipo de faturamento e dados detalhados
        """
        try:
            logger.info("Calculando projetos por tipo de faturamento...")
            
            # Usa dados já tratados
            dados_base = self.preparar_dados_base(dados)
            
            # Filtra apenas projetos ativos
            projetos_ativos = dados_base[~dados_base['Status'].isin(self.status_concluidos)].copy()
            
            # Se um mês de referência for fornecido, filtra os dados
            if mes_ref:
                # Converte DataInicio para datetime se ainda não estiver
                if 'DataInicio' in projetos_ativos.columns:
                    projetos_ativos['DataInicio'] = pd.to_datetime(projetos_ativos['DataInicio'], errors='coerce')
                    # Filtra apenas projetos que já estavam abertos até o final do mês
                    primeiro_dia_proximo_mes = (mes_ref.replace(day=28) + timedelta(days=4)).replace(day=1)
                    projetos_ativos = projetos_ativos[projetos_ativos['DataInicio'] < primeiro_dia_proximo_mes]
            
            # Garante que a coluna Faturamento existe
            if 'Faturamento' not in projetos_ativos.columns:
                logger.warning("Coluna 'Faturamento' não encontrada ao calcular projetos por faturamento")
                return {
                    'contagem': {},
                    'dados': []
                }
            
            # Contagem por tipo de faturamento
            contagem = projetos_ativos['Faturamento'].value_counts().to_dict()
            
            # Define cores para os tipos de faturamento
            cores_faturamento = {
                'PRIME': '#4CAF50',   # Verde
                'PLUS': '#2196F3',    # Azul
                'INICIO': '#9C27B0',  # Roxo
                'TERMINO': '#FF9800', # Laranja
                'FEOP': '#F44336',    # Vermelho
                'ENGAJAMENTO': '#673AB7', # Roxo escuro
                'NAO_MAPEADO': '#9E9E9E'  # Cinza
            }
            
            # Prepara dados detalhados
            dados_detalhados = []
            for tipo, qtd in contagem.items():
                if tipo in cores_faturamento:
                    cor = cores_faturamento[tipo]
                else:
                    cor = '#9E9E9E'  # Cinza para não mapeados
                
                dados_detalhados.append({
                    'tipo': tipo,
                    'quantidade': qtd,
                    'cor': cor,
                    'percentual': round((qtd / len(projetos_ativos) * 100), 1) if len(projetos_ativos) > 0 else 0
                })
            
            # Ordena por quantidade em ordem decrescente
            dados_detalhados = sorted(dados_detalhados, key=lambda x: x['quantidade'], reverse=True)
            
            logger.info(f"Distribuição por tipo de faturamento calculada: {contagem}")
            
            return {
                'contagem': contagem,
                'dados': dados_detalhados,
                'total': len(projetos_ativos)
            }
            
        except Exception as e:
            logger.error(f"Erro ao calcular projetos por tipo de faturamento: {str(e)}")
            return {
                'contagem': {},
                'dados': [],
                'total': 0
            }

    def calcular_dados_comparativos(self, dados, mes_atual=None, mes_anterior=None):
        """
        Calcula dados comparativos entre dois meses.
        
        Args:
            dados: DataFrame com os dados dos projetos
            mes_atual: Data do mês atual para filtrar (formato datetime)
            mes_anterior: Data do mês anterior para filtrar (formato datetime)
            
        Returns:
            Dictionary com dados comparativos entre os dois meses
        """
        try:
            logger.info(f"--- Iniciando calcular_dados_comparativos para {mes_atual.strftime('%m/%Y')} vs {mes_anterior.strftime('%m/%Y')} ---") # Log Adicionado
            
            # Se não forem fornecidos meses, usa o mês atual e o anterior
            if not mes_atual:
                hoje = datetime.now()
                mes_atual = hoje.replace(day=1)
            
            if not mes_anterior:
                # Considera o mês anterior
                primeiro_dia_mes_atual = mes_atual.replace(day=1)
                mes_anterior = (primeiro_dia_mes_atual - timedelta(days=1)).replace(day=1)
                
            # Determinamos o final de cada mês
            # Para o mês atual (na verdade, mês de referência)
            if mes_atual.month == 12:
                ultimo_dia_mes_atual = datetime(mes_atual.year + 1, 1, 1) - timedelta(days=1)
            else:
                ultimo_dia_mes_atual = datetime(mes_atual.year, mes_atual.month + 1, 1) - timedelta(days=1)
                
            # Para o mês anterior (na verdade, mês de comparação)
            if mes_anterior.month == 12:
                ultimo_dia_mes_anterior = datetime(mes_anterior.year + 1, 1, 1) - timedelta(days=1)
            else:
                ultimo_dia_mes_anterior = datetime(mes_anterior.year, mes_anterior.month + 1, 1) - timedelta(days=1)
                
            logger.info(f"Período de referência: {mes_atual.strftime('%d/%m/%Y')} a {ultimo_dia_mes_atual.strftime('%d/%m/%Y')}")
            logger.info(f"Período comparativo: {mes_anterior.strftime('%d/%m/%Y')} a {ultimo_dia_mes_anterior.strftime('%d/%m/%Y')}")
                
            # Preparamos a cópia dos dados principal
            dados_completos = dados.copy()
            
            # Convertemos as datas para formato datetime
            for coluna_data in ['DataInicio', 'DataTermino']:
                if coluna_data in dados_completos.columns:
                    dados_completos[coluna_data] = pd.to_datetime(dados_completos[coluna_data], errors='coerce')
            
            # Filtramos os dados de cada mês
            # Para o mês atual (referência)
            # Incluímos projetos que existiam até o final do mês (início antes do final do mês)
            dados_mes_atual_df = dados_completos[
                (dados_completos['DataInicio'] <= ultimo_dia_mes_atual)
            ].copy()
            
            # Para o mês anterior (comparativo)
            # Incluímos projetos que existiam até o final do mês (início antes do final do mês)
            dados_mes_anterior_df = dados_completos[
                (dados_completos['DataInicio'] <= ultimo_dia_mes_anterior)
            ].copy()
            
            # Cálculo para o mês de referência (atual)
            dados_mes_atual = self.calcular_agregacoes(dados_mes_atual_df)
            faturamento_atual = self.calcular_projetos_por_faturamento(dados_mes_atual_df, mes_atual)
            
            # Log Adicionado: Verificar dados antes de calcular tempo de vida
            logger.info(f"Verificando dados para tempo_medio_vida (Mês: {mes_atual.strftime('%m/%Y')}). Total de linhas: {len(dados_mes_atual_df)}")
            if not dados_mes_atual_df.empty:
                 colunas_log = [col for col in ['Projeto', 'DataInicio', 'DataTermino', 'Status'] if col in dados_mes_atual_df.columns]
                 if colunas_log:
                      logger.info(f"Amostra dos dados (tempo_medio_vida):\n{dados_mes_atual_df[colunas_log].head()}")
                      # Verificar tipos das colunas de data
                      if 'DataInicio' in colunas_log: logger.info(f"Tipo DataInicio: {dados_mes_atual_df['DataInicio'].dtype}")
                      if 'DataTermino' in colunas_log: logger.info(f"Tipo DataTermino: {dados_mes_atual_df['DataTermino'].dtype}")
                 else:
                      logger.warning("Colunas essenciais para log de tempo_medio_vida não encontradas.")
                      
            tempo_vida_atual = self.calcular_tempo_medio_vida(dados_mes_atual_df, mes_atual) # Passa mes_atual
            
            # Log para debug
            logger.debug(f"Dados mês atual - status: {list(dados_mes_atual['por_status'].keys())}")
            logger.debug(f"Dados mês atual - squads: {list(dados_mes_atual.get('por_squad', {}).keys())}")
            
            # Cálculo para o mês de comparação (anterior)
            agregacoes_mes_anterior = self.calcular_agregacoes(dados_mes_anterior_df)
            faturamento_anterior = self.calcular_projetos_por_faturamento(dados_mes_anterior_df, mes_anterior)
            tempo_vida_anterior = self.calcular_tempo_medio_vida(dados_mes_anterior_df, mes_anterior) # Passa mes_anterior
            
            # Prepara resultado com comparativos
            comparativo = {
                'mes_atual': {
                    'nome': mes_atual.strftime('%B/%Y'),
                    'agregacoes': dados_mes_atual,
                    'faturamento': faturamento_atual,
                    'tempo_medio_vida': tempo_vida_atual
                },
                'mes_anterior': {
                    'nome': mes_anterior.strftime('%B/%Y'),
                    'agregacoes': agregacoes_mes_anterior,
                    'faturamento': faturamento_anterior,
                    'tempo_medio_vida': tempo_vida_anterior
                },
                'variacao': {
                    'por_status': {},
                    'por_squad': {}
                }
            }
            
            # Calcula variações percentuais entre os meses para STATUS
            if 'por_status' in dados_mes_atual and 'por_status' in agregacoes_mes_anterior:
                for status, dados_status in dados_mes_atual['por_status'].items():
                    qtd_atual = dados_status.get('quantidade', 0)
                    qtd_anterior = agregacoes_mes_anterior['por_status'].get(status, {}).get('quantidade', 0)
                    
                    if qtd_anterior > 0:
                        variacao_pct = ((qtd_atual - qtd_anterior) / qtd_anterior) * 100
                    else:
                        variacao_pct = 100 if qtd_atual > 0 else 0
                    
                    comparativo['variacao']['por_status'][status] = {
                        'valor_anterior': qtd_anterior,
                        'valor_atual': qtd_atual,
                        'variacao_absoluta': qtd_atual - qtd_anterior,
                        'variacao_percentual': round(variacao_pct, 1)
                    }
            
            # Calcula variações percentuais entre os meses para SQUAD
            if 'por_squad' in dados_mes_atual and 'por_squad' in agregacoes_mes_anterior:
                for squad, dados_squad in dados_mes_atual['por_squad'].items():
                    qtd_atual = dados_squad.get('quantidade', 0)
                    qtd_anterior = agregacoes_mes_anterior['por_squad'].get(squad, {}).get('quantidade', 0)
                    
                    if qtd_anterior > 0:
                        variacao_pct = ((qtd_atual - qtd_anterior) / qtd_anterior) * 100
                    else:
                        variacao_pct = 100 if qtd_atual > 0 else 0
                    
                    comparativo['variacao']['por_squad'][squad] = {
                        'valor_anterior': qtd_anterior,
                        'valor_atual': qtd_atual,
                        'variacao_absoluta': qtd_atual - qtd_anterior,
                        'variacao_percentual': round(variacao_pct, 1)
                    }
            
            logger.info("Dados comparativos calculados com sucesso")
            return comparativo
            
        except Exception as e:
            logger.error(f"Erro ao calcular dados comparativos: {str(e)}")
            return {
                'mes_atual': {
                    'nome': mes_atual.strftime('%B/%Y') if mes_atual else 'Atual',
                    'agregacoes': {'por_status': {}, 'por_squad': {}},
                    'faturamento': {'dados': []},
                    'tempo_medio_vida': {'media_dias': 0, 'distribuicao': {}}
                },
                'mes_anterior': {
                    'nome': mes_anterior.strftime('%B/%Y') if mes_anterior else 'Anterior',
                    'agregacoes': {'por_status': {}, 'por_squad': {}},
                    'faturamento': {'dados': []},
                    'tempo_medio_vida': {'media_dias': 0, 'distribuicao': {}}
                },
                'variacao': {
                    'por_status': {},
                    'por_squad': {}
                }
            }

    def obter_projetos_por_squad_status_mes(self, dados, squad, mes_referencia=None):
        """
        Obtém os projetos de um squad específico filtrados por status e por mês de referência.
        
        Args:
            dados: DataFrame com os dados dos projetos
            squad: Nome do squad para filtrar
            mes_referencia: Data de referência para filtro (formato datetime). Se None, usa o último dia do mês atual
            
        Returns:
            Dictionary com a contagem de projetos por status e o total
        """
        try:
            logger.info(f"Obtendo projetos do squad {squad} por status para o mês de referência")
            
            # Define o mês de referência como o mês atual, caso não seja fornecido
            if not mes_referencia:
                hoje = datetime.now()
                mes_referencia = hoje
                
            # Determina o último dia do mês de referência
            if mes_referencia.month == 12:
                ultimo_dia_mes = datetime(mes_referencia.year + 1, 1, 1) - timedelta(days=1)
            else:
                ultimo_dia_mes = datetime(mes_referencia.year, mes_referencia.month + 1, 1) - timedelta(days=1)
                
            logger.info(f"Período de referência: até {ultimo_dia_mes.strftime('%d/%m/%Y')}")
            
            # Prepara cópia dos dados
            dados_temp = dados.copy()
            
            # Mapeamento de squads para normalizar nomes
            # Adicione aqui qualquer mapeamento específico necessário
            squad_mapping = {
                'AZURE': ['AZURE', 'Azure'],
                'M365': ['M365', 'M365'],
                'DATA E POWER': ['DATA E POWER', 'Data e Power'],
                'CDB': ['CDB', 'CDB']
            }
            
            # Log para depuração - status e squads disponíveis nos dados
            if not dados_temp.empty:
                todos_status = dados_temp['Status'].dropna().unique().tolist()
                todos_squads = dados_temp['Squad'].dropna().unique().tolist()
                logger.info(f"Status disponíveis nos dados: {todos_status}")
                logger.info(f"Squads disponíveis nos dados: {todos_squads}")
            
            # Certifica-se que as colunas esperadas existem
            colunas_necessarias = ['DataInicio', 'Squad', 'Status', 'Especialista']
            colunas_faltantes = [col for col in colunas_necessarias if col not in dados_temp.columns]
            if colunas_faltantes:
                logger.warning(f"Colunas necessárias não encontradas: {colunas_faltantes}")
                return {
                    'total': 0,
                    'por_status': {},
                    'squad': squad
                }
                
            # Converte a coluna de data para datetime
            dados_temp['DataInicio'] = pd.to_datetime(dados_temp['DataInicio'], errors='coerce')
            
            # Função auxiliar para verificar se um registro corresponde ao squad solicitado
            # considerando o especialista
            def corresponde_squad_especialista(row, target_squad):
                if pd.isna(row['Squad']) or not row['Squad']:
                    return False
                
                # Trata valores NaN na coluna Especialista
                especialista = '' if pd.isna(row['Especialista']) else str(row['Especialista']).strip()
                row_squad = str(row['Squad']).strip().upper()
                target_squad = str(target_squad).strip().upper()
                
                # Caso especial para CDB
                if target_squad == 'CDB':
                    # Para CDB, verifica se o especialista é "CDB DATA SOLUTIONS"
                    return especialista.upper() == 'CDB DATA SOLUTIONS'
                
                # Para os outros squads (AZURE, M365, DATA E POWER)
                # Verifica se o especialista NÃO é "CDB DATA SOLUTIONS" e o squad corresponde
                if especialista.upper() == 'CDB DATA SOLUTIONS':
                    return False
                
                # Verifica correspondência direta
                if row_squad == target_squad:
                    return True
                
                # Verifica no mapeamento de squads
                for key, values in squad_mapping.items():
                    if target_squad == key.upper():
                        # Se o squad alvo é uma chave no mapeamento, verifica se o squad da linha está nos valores
                        return any(str(v).strip().upper() == row_squad for v in values)
                    elif row_squad == key.upper():
                        # Se o squad da linha é uma chave no mapeamento, verifica se o squad alvo está nos valores
                        return any(str(v).strip().upper() == target_squad for v in values)
                
                return False
            
            # Aplica a função de correspondência
            dados_temp['MatchSquad'] = dados_temp.apply(lambda row: corresponde_squad_especialista(row, squad), axis=1)
            
            # Filtra projetos até o último dia do mês de referência e do squad correto
            dados_filtrados = dados_temp[
                (dados_temp['DataInicio'] <= ultimo_dia_mes) &
                (dados_temp['MatchSquad'] == True)
            ].copy()
            
            # Log para depuração - projetos encontrados
            total_projetos = len(dados_filtrados)
            logger.info(f"Total de projetos encontrados para o squad {squad}: {total_projetos}")
            
            if not dados_filtrados.empty:
                primeiro_projeto = dados_filtrados.iloc[0]
                logger.info(f"Exemplo de projeto encontrado: Projeto={primeiro_projeto.get('Projeto', 'N/A')}, " 
                          f"Status={primeiro_projeto.get('Status', 'N/A')}, "
                          f"Squad={primeiro_projeto.get('Squad', 'N/A')}, "
                          f"Especialista={primeiro_projeto.get('Especialista', 'N/A')}")
                # Mostra todos os projetos do squad para depuração
                for idx, row in dados_filtrados.iterrows():
                    logger.debug(f"Projeto filtrado: {row.get('Projeto', 'N/A')} - Status: {row.get('Status', 'N/A')} - "
                               f"Squad: {row.get('Squad', 'N/A')} - Especialista: {row.get('Especialista', 'N/A')}")
            
            # Exclui projetos que já estavam fechados/concluídos
            dados_filtrados = dados_filtrados[~dados_filtrados['Status'].isin(self.status_concluidos)]
            logger.info(f"Projetos ativos após remover concluídos: {len(dados_filtrados)}")
            
            # Calcula contagem por status
            por_status = {}
            if not dados_filtrados.empty:
                contagem_status = dados_filtrados['Status'].value_counts().to_dict()
                for status, qtd in contagem_status.items():
                    por_status[status] = qtd
                    logger.info(f"Status {status}: {qtd} projetos")
            
            # Prepara resultado
            resultado = {
                'total': len(dados_filtrados),
                'por_status': por_status,
                'squad': squad
            }
            
            return resultado
            
        except Exception as e:
            logger.error(f"Erro ao obter projetos por squad e status: {str(e)}")
            logger.exception(e)
            return {
                'total': 0,
                'por_status': {},
                'squad': squad
            }

    def calcular_projetos_entregues(self, dados, mes_referencia=None):
        """
        Calcula os dados de projetos entregues no mês.
        
        Args:
            dados: DataFrame com os dados dos projetos
            mes_referencia: Data de referência (formato datetime). Se None, usa o mês atual
            
        Returns:
            Dictionary com dados sobre projetos entregues
        """
        try:
            logger.info("Calculando projetos entregues...")
            
            # Define o mês de referência se não informado
            if not mes_referencia:
                hoje = datetime.now()
                mes_referencia = hoje
            
            # Calcula início e fim do mês de referência
            mes_inicio = datetime(mes_referencia.year, mes_referencia.month, 1)
            if mes_referencia.month == 12:
                mes_fim = datetime(mes_referencia.year + 1, 1, 1) - timedelta(days=1)
            else:
                mes_fim = datetime(mes_referencia.year, mes_referencia.month + 1, 1) - timedelta(days=1)
            
            # Filtra projetos concluídos no período usando a fonte de dados correta
            dados_filtrados = self.filtrar_projetos_concluidos(dados, mes_inicio, mes_fim)
            
            # Total de projetos entregues no mês
            total_mes = len(dados_filtrados)
            
            # Calcular projetos entregues no prazo e fora do prazo dinamicamente
            no_prazo = 0
            fora_prazo = 0
            
            # Log para verificar os dados ANTES do dropna
            if not dados_filtrados.empty:
                logger.debug(f"VencimentoEm para projetos concluídos ANTES de dropna:\n{dados_filtrados[['Projeto', 'VencimentoEm', 'Status', 'DataTermino']]}")

            if not dados_filtrados.empty and 'VencimentoEm' in dados_filtrados.columns:
                # Converte VencimentoEm para datetime se necessário e normaliza (ignora hora)
                if not pd.api.types.is_datetime64_any_dtype(dados_filtrados['VencimentoEm']):
                     dados_filtrados['VencimentoEm'] = pd.to_datetime(dados_filtrados['VencimentoEm'], errors='coerce')
                dados_filtrados['VencimentoEm'] = dados_filtrados['VencimentoEm'].dt.normalize()

                # Filtra apenas onde a data de vencimento é válida
                validos_para_prazo = dados_filtrados.dropna(subset=['VencimentoEm']).copy()
                logger.info(f"Projetos concluídos com VencimentoEm válido: {len(validos_para_prazo)}") # Log adicionado

                if not validos_para_prazo.empty:
                    # Normaliza o mes_referencia para comparar apenas ano e mês (pegando o primeiro dia)
                    inicio_mes_ref = mes_referencia.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    logger.debug(f"--- Iniciando Cálculo Prazo para Mês Ref: {inicio_mes_ref.strftime('%Y-%m-%d')} ---")

                    # No prazo: VencimentoEm >= início do mês de referência
                    no_prazo = (validos_para_prazo['VencimentoEm'] >= inicio_mes_ref).sum()
                    
                    # Fora do prazo: VencimentoEm < início do mês de referência
                    fora_prazo_com_data = (validos_para_prazo['VencimentoEm'] < inicio_mes_ref).sum()

                    logger.info(f"Projetos com data válida: No Prazo = {no_prazo}, Fora Prazo com data = {fora_prazo_com_data}")
                    
                    # Projetos sem data de vencimento são considerados FORA DO PRAZO
                    projetos_sem_vencimento = total_mes - len(validos_para_prazo)
                    fora_prazo = fora_prazo_com_data + projetos_sem_vencimento
                    
                    logger.info(f"[Visão Atual] No Prazo = {no_prazo}, Fora Prazo = {fora_prazo} (incluindo {projetos_sem_vencimento} sem data)")
                    
                    if projetos_sem_vencimento > 0:
                        # Identifica quais projetos não têm data de vencimento válida
                        projetos_invalidos = dados_filtrados[dados_filtrados['VencimentoEm'].isna() | 
                                                            dados_filtrados['VencimentoEm'].isnull()]
                        
                        logger.warning(f"[Visão Atual] {projetos_sem_vencimento} projetos sem data de vencimento serão considerados FORA DO PRAZO.")
                        
                        for _, projeto in projetos_invalidos.iterrows():
                            numero = projeto.get('Numero', projeto.get('Número', 'N/A'))
                            nome_projeto = projeto.get('Projeto', 'N/A')
                            logger.warning(f"  - Projeto #{numero}: {nome_projeto}")
                else:
                    # Se não há projetos com data válida, todos são considerados fora do prazo
                    no_prazo = 0
                    fora_prazo = total_mes
                    logger.warning(f"[Visão Atual] Nenhum projeto com data válida. Todos os {total_mes} projetos serão considerados FORA DO PRAZO.")

            # Calcular histórico (agora apenas do mês anterior)
            historico = self.calcular_historico_entregas(dados, mes_referencia)
            
            resultado = {
                'total_mes': total_mes,
                'no_prazo': no_prazo,
                'fora_prazo': fora_prazo,
                'historico': historico
            }
            
            logger.info(f"Projetos entregues calculados: {total_mes} no total, {no_prazo} no prazo, {fora_prazo} fora do prazo")
            return resultado
            
        except Exception as e:
            logger.exception(f"Erro ao calcular projetos entregues: {str(e)}")
            # Retorna valores padrão em caso de erro
            return {
                'total_mes': 0,
                'no_prazo': 0,
                'fora_prazo': 0,
                'historico': []
            }
    
    def filtrar_projetos_concluidos(self, dados, data_inicio, data_fim):
        """
        Filtra projetos concluídos em um período específico.
        """
        try:
            # Status que indicam conclusão
            status_conclusao = ['FECHADO', 'ENCERRADO', 'RESOLVIDO']
            coluna_data_termino = 'DataTermino' # Usar a coluna correta após renomeação

            # Verifica se temos a coluna DataTermino
            if coluna_data_termino not in dados.columns:
                logger.warning(f"Coluna '{coluna_data_termino}' não encontrada. Não é possível filtrar concluídos por data.")
                # Retorna DataFrame vazio se não puder filtrar por data
                return pd.DataFrame()

            # Converte para datetime se necessário
            if not pd.api.types.is_datetime64_any_dtype(dados[coluna_data_termino]):
                dados[coluna_data_termino] = pd.to_datetime(dados[coluna_data_termino], errors='coerce')

            # Filtra projetos concluídos no período usando DataTermino
            concluidos = dados[
                (dados['Status'].str.upper().isin([s.upper() for s in status_conclusao])) &
                (dados[coluna_data_termino].notna()) & # Garante que a data não é NaT
                (dados[coluna_data_termino] >= data_inicio) &
                (dados[coluna_data_termino] <= data_fim)
            ].copy()

            logger.debug(f"Filtrados {len(concluidos)} projetos concluídos entre {data_inicio.strftime('%Y-%m-%d')} e {data_fim.strftime('%Y-%m-%d')}")
            return concluidos

        except Exception as e:
            logger.exception(f"Erro ao filtrar projetos concluídos: {str(e)}")
            return pd.DataFrame()  # Retorna DataFrame vazio em caso de erro
    
    def calcular_historico_entregas(self, dados, mes_referencia):
        """
        Calcula o histórico de entregas para os 3 meses anteriores ao mês de referência,
        incluindo valores fixos para Dez/24 e Jan/25.
        """
        try:
            logger.info(f"Calculando histórico de entregas para os 3 meses anteriores a {mes_referencia.strftime('%m/%Y')}")
            historico = []
            mes_nomes = [
                'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
            ]
            
            quantidades_meses = {}
            datas_meses = {}

            # Calcula as datas dos 3 meses anteriores
            for i in range(3, 0, -1):
                # Calcula o mês/ano do mês histórico
                mes_atual = mes_referencia.month
                ano_atual = mes_referencia.year
                
                # Subtrai 'i' meses
                mes_hist = mes_atual - i
                ano_hist = ano_atual
                while mes_hist <= 0:
                    mes_hist += 12
                    ano_hist -= 1
                
                data_mes_hist = datetime(ano_hist, mes_hist, 1)
                datas_meses[i] = data_mes_hist # Guarda a data (chave 3 = M-3, 2 = M-2, 1 = M-1)
                nome_mes_hist = mes_nomes[mes_hist - 1]
                logger.info(f"  Processando histórico para: {nome_mes_hist}/{ano_hist} (M-{i})")
                
                quantidade = 0
                # 1. Verifica valores hardcoded
                if ano_hist == 2024 and mes_hist == 12:
                    quantidade = 7
                    logger.info(f"    Usando valor hardcoded para Dez/24: {quantidade}")
                elif ano_hist == 2025 and mes_hist == 1:
                    quantidade = 8
                    logger.info(f"    Usando valor hardcoded para Jan/25: {quantidade}")
                else:
                    # 2. Tenta carregar fonte específica
                    fonte_historico = None
                    # Mapeamento simples (pode ser expandido)
                    if ano_hist == 2025:
                        if mes_hist == 2: fonte_historico = 'dadosr_apt_fev'
                        if mes_hist == 3: fonte_historico = 'dadosr_apt_mar'
                        if mes_hist == 4: fonte_historico = 'dadosr_apt_abr'  # ADICIONADO: mapeamento para abril
                        if mes_hist == 5: fonte_historico = 'dadosr_apt_mai'  # ADICIONADO: mapeamento para maio
                        # Adicionar mapeamentos futuros aqui (Junho, Julho, etc.)
                    
                    if fonte_historico:
                        logger.info(f"    Tentando carregar dados da fonte: {fonte_historico}")
                        dados_historico = self.carregar_dados(fonte=fonte_historico)
                        
                        if not dados_historico.empty:
                            # Define o primeiro e último dia do mês histórico
                            data_inicio = datetime(ano_hist, mes_hist, 1)
                            if mes_hist == 12:
                                data_fim = datetime(ano_hist + 1, 1, 1) - timedelta(days=1)
                            else:
                                data_fim = datetime(ano_hist, mes_hist + 1, 1) - timedelta(days=1)
                                
                            # Filtra projetos concluídos neste mês usando os dados históricos
                            concluidos_mes = self.filtrar_projetos_concluidos(dados_historico, data_inicio, data_fim)
                            quantidade = len(concluidos_mes)
                            logger.info(f"    Encontrados {quantidade} projetos concluídos em {nome_mes_hist} usando {fonte_historico}.csv")
                        else:
                            logger.warning(f"    Não foi possível carregar dados da fonte histórica: {fonte_historico}. Quantidade será 0.")
                    else:
                        logger.warning(f"    Nenhuma fonte de dados específica definida para {nome_mes_hist}/{ano_hist}. Quantidade será 0.")
                        
                quantidades_meses[i] = quantidade # Guarda a quantidade (chave 3 = Qtd M-3, etc.)

            # Monta o resultado final e calcula variações
            qtd_base_pct = quantidades_meses.get(3, 0) # Quantidade do primeiro mês (M-3) para cálculo %%
            logger.info(f"Base para cálculo percentual (Mês M-3): {qtd_base_pct}")

            for i in range(3, 0, -1):
                data_mes = datas_meses[i]
                nome_mes = mes_nomes[data_mes.month - 1]
                qtd_atual = quantidades_meses[i]
                variacao_abs = '-'
                variacao_pct = 0
                
                # Calcula variação ABSOLUTA em relação ao mês anterior (se houver)
                if i < 3:
                    qtd_anterior = quantidades_meses[i + 1] # Mês anterior é i+1
                    variacao_abs = qtd_atual - qtd_anterior
                # else: Mês M-3, variacao_abs permanece '-'
                    
                # Calcula variação PERCENTUAL em relação ao MÊS BASE (M-3)
                # Exceto para o próprio mês base (i=3)
                if i < 3:
                    if qtd_base_pct > 0:
                        variacao_pct = round(((qtd_atual - qtd_base_pct) / qtd_base_pct) * 100, 1)
                    elif qtd_atual > 0: # Base era 0, atual não é
                        variacao_pct = 100.0 
                    # else: ambos 0 (ou base 0), pct é 0
                        
                historico.append({
                    'mes': nome_mes,
                    'quantidade': qtd_atual,
                    'variacao': f"{variacao_abs:+}" if isinstance(variacao_abs, int) else variacao_abs,
                    'variacao_percentual': variacao_pct
                })
                
            logger.info(f"Histórico de entregas final calculado: {historico}")
            return historico

        except Exception as e:
            logger.exception(f"Erro ao calcular histórico de entregas (3 meses): {str(e)}")
            return []

    def _calcular_historico_dinamico(self, mes_referencia):
        """
        Função auxiliar para calcular o histórico de entregas dinamicamente 
        para os 3 meses anteriores ao mês de referência, tentando carregar fontes.
        Usado pela Visão Atual.
        """
        try:
            logger.info(f"[_calcular_historico_dinamico] Calculando para 3 meses antes de {mes_referencia.strftime('%m/%Y')}")
            historico = []
            mes_nomes = [
                'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
            ]
            quantidades_meses = {}
            datas_meses = {}

            # Calcula as datas dos 3 meses anteriores
            for i in range(3, 0, -1): # M-3, M-2, M-1
                mes_atual = mes_referencia.month
                ano_atual = mes_referencia.year
                mes_hist = mes_atual - i
                ano_hist = ano_atual
                while mes_hist <= 0:
                    mes_hist += 12
                    ano_hist -= 1
                
                data_mes_hist = datetime(ano_hist, mes_hist, 1)
                datas_meses[i] = data_mes_hist
                nome_mes_hist = mes_nomes[mes_hist - 1]
                logger.info(f"  Processando histórico para: {nome_mes_hist}/{ano_hist} (M-{i})")
                
                quantidade = 0
                # Determina a fonte de dados histórica usando a função auxiliar
                fonte_historico = self._obter_fonte_historica(ano_hist, mes_hist)
                
                if fonte_historico:
                    logger.info(f"    Tentando carregar dados da fonte: {fonte_historico}")
                    dados_historico = self.carregar_dados(fonte=fonte_historico)
                    
                    if not dados_historico.empty:
                        data_inicio = datetime(ano_hist, mes_hist, 1)
                        if mes_hist == 12:
                            data_fim = datetime(ano_hist + 1, 1, 1) - timedelta(days=1)
                        else:
                            data_fim = datetime(ano_hist, mes_hist + 1, 1) - timedelta(days=1)
                        
                        concluidos_mes = self.filtrar_projetos_concluidos(dados_historico, data_inicio, data_fim)
                        quantidade = len(concluidos_mes)
                        logger.info(f"    Encontrados {quantidade} projetos concluídos em {nome_mes_hist} usando {fonte_historico}.csv")
                    else:
                        logger.warning(f"    Não foi possível carregar dados da fonte histórica: {fonte_historico}. Quantidade será 0.")
                else:
                    # Verifica valores hardcoded como fallback
                    if ano_hist == 2024 and mes_hist == 12: 
                        quantidade = 7
                        logger.info(f"    Fonte não encontrada, usando valor hardcoded para Dez/24: {quantidade}")
                    elif ano_hist == 2025 and mes_hist == 1: 
                        quantidade = 8
                        logger.info(f"    Fonte não encontrada, usando valor hardcoded para Jan/25: {quantidade}")
                    else:
                         logger.warning(f"    Nenhuma fonte de dados específica ou valor fixo definido para {nome_mes_hist}/{ano_hist}. Quantidade será 0.")
                        
                quantidades_meses[i] = quantidade

            # Define a quantidade do primeiro mês do histórico (M-3) como base
            qtd_base_pct = quantidades_meses.get(3, 0)
            logger.info(f"[_calcular_historico_dinamico] Base para cálculo percentual (Mês M-3): {qtd_base_pct}")

            # Monta o resultado final e calcula variações
            for i in range(3, 0, -1):
                data_mes = datas_meses[i]
                nome_mes = mes_nomes[data_mes.month - 1]
                qtd_atual = quantidades_meses[i]
                variacao_abs = '-'
                variacao_pct = 0

                # Calcula variação ABSOLUTA em relação ao mês anterior (se houver)
                if i < 3:
                    qtd_anterior = quantidades_meses.get(i + 1, 0) # Usa .get para segurança
                    variacao_abs = qtd_atual - qtd_anterior
                # else: Mês M-3, variacao_abs permanece '-'

                # Calcula variação PERCENTUAL em relação ao MÊS BASE (M-3)
                # Exceto para o próprio mês base (i=3), onde a variação é 0 ou '-'
                if i < 3: # Apenas para M-2 e M-1
                    if qtd_base_pct > 0:
                        variacao_pct = round(((qtd_atual - qtd_base_pct) / qtd_base_pct) * 100, 1)
                    elif qtd_atual > 0: # Base era 0, atual não é
                        variacao_pct = 100.0
                    # else: base 0 ou ambos 0, pct é 0
                # else: i == 3 (mês base), variacao_pct permanece 0

                historico.append({
                    'mes': nome_mes,
                    'quantidade': qtd_atual,
                    'variacao': f"{variacao_abs:+}" if isinstance(variacao_abs, int) else variacao_abs,
                    # Mantém '-' para o primeiro mês, ou o percentual calculado para os outros
                    'variacao_percentual': variacao_pct if i < 3 else '-'
                })

            logger.info(f"[_calcular_historico_dinamico] Histórico final calculado: {historico}")
            return historico
        
        except Exception as e:
            logger.exception(f"[_calcular_historico_dinamico] Erro ao calcular histórico dinâmico: {str(e)}")
            return []

    def calcular_projetos_entregues_atual(self, dados, mes_referencia):
        """
        Calcula os dados de projetos entregues para a Visão Atual.
        Inclui cálculo dinâmico do histórico para os 3 meses anteriores.
        
        Args:
            dados: DataFrame com os dados dos projetos (geralmente dadosr.csv).
            mes_referencia: Data de referência (datetime) determinada dinamicamente.
            
        Returns:
            Dictionary com dados sobre projetos entregues.
        """
        try:
            logger.info(f"[Visão Atual] Calculando projetos entregues para {mes_referencia.strftime('%m/%Y')}...")
            
            # Calcula início e fim do mês de referência
            mes_inicio = datetime(mes_referencia.year, mes_referencia.month, 1)
            if mes_referencia.month == 12:
                mes_fim = datetime(mes_referencia.year + 1, 1, 1) - timedelta(days=1)
            else:
                mes_fim = datetime(mes_referencia.year, mes_referencia.month + 1, 1) - timedelta(days=1)
            
            # Filtra projetos concluídos no período usando os dados ATUAIS (dadosr.csv)
            dados_filtrados = self.filtrar_projetos_concluidos(dados, mes_inicio, mes_fim)
            
            # Total de projetos entregues no mês
            total_mes = len(dados_filtrados)
            
            # Calcular projetos entregues no prazo e fora do prazo (lógica original que resultava em não classificados)
            no_prazo = 0
            fora_prazo = 0
            if not dados_filtrados.empty and 'VencimentoEm' in dados_filtrados.columns:
                if not pd.api.types.is_datetime64_any_dtype(dados_filtrados['VencimentoEm']):
                     dados_filtrados['VencimentoEm'] = pd.to_datetime(dados_filtrados['VencimentoEm'], errors='coerce')
                dados_filtrados['VencimentoEm'] = dados_filtrados['VencimentoEm'].dt.normalize()
                validos_para_prazo = dados_filtrados.dropna(subset=['VencimentoEm']).copy()
                if not validos_para_prazo.empty:
                    inicio_mes_ref = mes_referencia.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    no_prazo = (validos_para_prazo['VencimentoEm'] >= inicio_mes_ref).sum()
                    fora_prazo = (validos_para_prazo['VencimentoEm'] < inicio_mes_ref).sum()
                    projetos_sem_vencimento = total_mes - len(validos_para_prazo)
                    if projetos_sem_vencimento > 0:
                        logger.warning(f"[Visão Atual] {projetos_sem_vencimento} projetos concluídos não possuem data de vencimento válida e não foram adicionados a 'fora_prazo' nesta lógica.")
                else:
                     logger.warning("[Visão Atual] Nenhum projeto concluído com data de vencimento válida encontrado para classificar prazo.")
            else:
                 logger.warning("[Visão Atual] Coluna 'VencimentoEm' não encontrada ou dados filtrados vazios. Cálculo de prazo não realizado.")

            # Chama a função auxiliar para calcular o histórico dinâmico
            historico = self._calcular_historico_dinamico(mes_referencia)
            
            resultado = {
                'total_mes': total_mes,
                'no_prazo': no_prazo,
                'fora_prazo': fora_prazo,
                'historico': historico
            }
            
            logger.info(f"[Visão Atual] Projetos entregues calculados (lógica original): {total_mes} no total, {no_prazo} no prazo, {fora_prazo} fora do prazo")
            logger.info(f"[Visão Atual] Histórico dinâmico: {historico}")
            return resultado
            
        except Exception as e:
            logger.exception(f"[Visão Atual] Erro ao calcular projetos entregues: {str(e)}")
            return {
                'total_mes': 0,
                'no_prazo': 0,
                'fora_prazo': 0,
                'historico': []
            }

    def calcular_novos_projetos_mes(self, dados, mes_referencia):
        """
        Calcula a quantidade de projetos iniciados no mês de referência, agregados por squad.

        Args:
            dados: DataFrame com os dados dos projetos.
            mes_referencia: Data (datetime) do mês de referência.

        Returns:
            Dictionary com contagem por squad e total. Ex: {'por_squad': {'AZURE': 5, ...}, 'total': 10}
        """
        try:
            logger.info(f"Calculando novos projetos para o mês {mes_referencia.strftime('%m/%Y')}...")

            if dados.empty or 'DataInicio' not in dados.columns or 'Squad' not in dados.columns:
                logger.warning("Dados insuficientes para calcular novos projetos (DataFrame vazio ou colunas faltando).")
                return {'por_squad': {}, 'total': 0}

            # Garante que DataInicio é datetime
            if not pd.api.types.is_datetime64_any_dtype(dados['DataInicio']):
                 dados['DataInicio'] = pd.to_datetime(dados['DataInicio'], errors='coerce')

            # Filtra projetos iniciados no mês/ano de referência
            dados_mes = dados[
                (dados['DataInicio'].dt.month == mes_referencia.month) &
                (dados['DataInicio'].dt.year == mes_referencia.year)
            ].copy()

            total_novos = len(dados_mes)
            logger.info(f"Total de projetos iniciados no mês: {total_novos}")

            # Agrupa por Squad (garante que Squad seja string e maiúsculo)
            dados_mes['Squad'] = dados_mes['Squad'].astype(str).str.strip().str.upper() # Garante que a coluna está em maiúsculas
            contagem_squad = dados_mes.groupby('Squad').size().to_dict()

            # Normaliza os squads principais
            squads_principais = ['AZURE', 'M365', 'DATA E POWER', 'CDB']
            resultado_squad = {s: 0 for s in squads_principais}
            outros = 0

            for squad, contagem in contagem_squad.items():
                # O squad já está em maiúsculas devido ao .str.upper() acima
                if squad in resultado_squad:
                    resultado_squad[squad] = contagem
                # Não precisamos mais do elif, pois a comparação direta já funciona
                else:
                    logger.debug(f"Squad '{squad}' não é principal, contagem: {contagem}")
                    outros += contagem

            # O total considera todos os projetos iniciados no mês
            resultado_final = {
                'por_squad': resultado_squad,
                'total': total_novos
            }
            logger.info(f"Contagem de novos projetos por squad: {resultado_squad}, Total: {total_novos}")

            return resultado_final

        except Exception as e:
            logger.error(f"Erro ao calcular novos projetos: {str(e)}")
            return {'por_squad': {}, 'total': 0}

    def calcular_novos_projetos_atual(self, dados, mes_referencia):
        """
        Calcula os dados de novos projetos para a Visão Atual.
        Retorna estrutura de comparação com mês atual vs anterior.
        
        Args:
            dados: DataFrame com os dados dos projetos (geralmente dadosr.csv).
            mes_referencia: Data de referência (datetime) determinada dinamicamente.
            
        Returns:
            Dictionary com estrutura de comparação de novos projetos.
        """
        try:
            logger.info(f"[Visão Atual] Calculando novos projetos para {mes_referencia.strftime('%m/%Y')}...")
            
            # Calcular novos projetos do mês atual
            resultado_mes_atual = self.calcular_novos_projetos_mes(dados, mes_referencia)
            
            # Calcular mês anterior
            if mes_referencia.month == 1:
                mes_anterior = mes_referencia.replace(year=mes_referencia.year - 1, month=12)
            else:
                mes_anterior = mes_referencia.replace(month=mes_referencia.month - 1)
            
            logger.info(f"[Visão Atual] Tentando calcular dados do mês anterior: {mes_anterior.strftime('%m/%Y')}")
            
            # Tentar obter dados históricos do mês anterior
            resultado_mes_anterior = {'por_squad': {}, 'total': 0}
            
            # Verifica se existe fonte histórica para o mês anterior
            fonte_anterior = self._obter_fonte_historica(mes_anterior.year, mes_anterior.month)
            if fonte_anterior:
                try:
                    dados_anterior = self.carregar_dados(fonte=fonte_anterior)
                    if not dados_anterior.empty:
                        resultado_mes_anterior = self.calcular_novos_projetos_mes(dados_anterior, mes_anterior)
                        logger.info(f"[Visão Atual] Dados do mês anterior carregados da fonte: {fonte_anterior}")
                    else:
                        logger.warning(f"[Visão Atual] Fonte {fonte_anterior} retornou dados vazios")
                except Exception as e:
                    logger.error(f"[Visão Atual] Erro ao carregar dados da fonte {fonte_anterior}: {e}")
            else:
                # Fallback: tentar calcular usando os mesmos dados atuais (pode incluir projetos do mês anterior)
                try:
                    resultado_mes_anterior = self.calcular_novos_projetos_mes(dados, mes_anterior)
                    logger.info(f"[Visão Atual] Usando fallback com dados atuais para calcular mês anterior")
                except Exception as e:
                    logger.warning(f"[Visão Atual] Fallback falhou: {e}")
            
            # Estruturar dados para comparação
            squads_principais = ['AZURE', 'M365', 'DATA E POWER', 'CDB']
            comparativo = {
                'por_squad': {},
                'total': {
                    'atual': resultado_mes_atual['total'],
                    'anterior': resultado_mes_anterior['total'],
                    'variacao_abs': 0,
                    'variacao_pct': 0
                }
            }
            
            # Calcular variações por squad
            for squad in squads_principais:
                atual = resultado_mes_atual['por_squad'].get(squad, 0)
                anterior = resultado_mes_anterior['por_squad'].get(squad, 0)
                variacao_abs = atual - anterior
                variacao_pct = 0
                
                if anterior > 0:
                    variacao_pct = round(((atual - anterior) / anterior) * 100, 1)
                elif atual > 0:
                    variacao_pct = 100.0
                
                comparativo['por_squad'][squad] = {
                    'atual': atual,
                    'anterior': anterior,
                    'variacao_abs': variacao_abs,
                    'variacao_pct': variacao_pct
                }
            
            # Calcular variações totais
            total_atual = comparativo['total']['atual']
            total_anterior = comparativo['total']['anterior']
            total_variacao_abs = total_atual - total_anterior
            total_variacao_pct = 0
            
            if total_anterior > 0:
                total_variacao_pct = round(((total_atual - total_anterior) / total_anterior) * 100, 1)
            elif total_atual > 0:
                total_variacao_pct = 100.0
            
            comparativo['total']['variacao_abs'] = total_variacao_abs
            comparativo['total']['variacao_pct'] = total_variacao_pct
            
            logger.info(f"[Visão Atual] Comparativo calculado. Atual: {total_atual}, Anterior: {total_anterior}, VarAbs: {total_variacao_abs}")
            
            return comparativo
            
        except Exception as e:
            logger.exception(f"[Visão Atual] Erro ao calcular novos projetos: {str(e)}")
            # Retorna estrutura vazia mas correta
            return {
                'por_squad': {squad: {'atual': 0, 'anterior': 0, 'variacao_abs': 0, 'variacao_pct': 0} 
                             for squad in ['AZURE', 'M365', 'DATA E POWER', 'CDB']},
                'total': {'atual': 0, 'anterior': 0, 'variacao_abs': 0, 'variacao_pct': 0}
            }

    def _obter_fonte_historica(self, ano, mes):
        """
        Obtém o nome da fonte histórica para um determinado mês/ano.
        
        Args:
            ano (int): Ano
            mes (int): Mês (1-12)
            
        Returns:
            str: Nome da fonte (sem extensão) ou None se não encontrada
        """
        # Mapeamento dos meses para abreviações
        mes_to_abbr = {
            1: 'jan', 2: 'fev', 3: 'mar', 4: 'abr', 5: 'mai', 6: 'jun',
            7: 'jul', 8: 'ago', 9: 'set', 10: 'out', 11: 'nov', 12: 'dez'
        }
        
        if mes in mes_to_abbr:
            fonte = f"dadosr_apt_{mes_to_abbr[mes]}"
            # Verifica se o arquivo existe
            arquivo_path = self.csv_path.parent / f"{fonte}.csv"
            if arquivo_path.exists():
                return fonte
        
        return None

    def obter_detalhes_projeto(self, project_id):
        """
        Busca os detalhes de um projeto específico pelo ID.
        OTIMIZADO: Usa cache de 60 segundos para projetos e reduz logs.
        
        Args:
            project_id: ID do projeto (int ou string)
            
        Returns:
            dict: Detalhes do projeto ou None se não encontrado
        """
        # OTIMIZAÇÃO: Verificar cache de projeto primeiro (SEM LOGS)
        cached_details = _get_cached_project_details(project_id)
        if cached_details is not None:
            # SEM LOGS para evitar spam - detalhes já estão no cache
            return cached_details
        
        # Cache miss - buscar projeto
        dados = self.carregar_dados()
        if dados.empty:
            return None
        
        # Converte project_id para int para garantir compatibilidade
        try:
            project_id_int = int(project_id)
        except (ValueError, TypeError):
            # OTIMIZAÇÃO: Log apenas em caso de erro real
            logger.warning(f"Não foi possível converter project_id '{project_id}' para int")
            return None
        
        # Busca o projeto pelo ID
        projeto = dados[dados['Numero'] == project_id_int]
        
        if projeto.empty:
            # OTIMIZAÇÃO: Log silenciado para projetos não encontrados (muito comum)
            # logger.warning(f"Projeto com ID {project_id_int} não encontrado")
            return None
        
        # Retorna o primeiro resultado como dicionário
        projeto_dict = projeto.iloc[0].to_dict()
        
        # --- INÍCIO: Normalização das chaves ---
        normalized_details = { _normalize_key(k): v for k, v in projeto_dict.items() }
        # --- FIM: Normalização das chaves ---

        # OTIMIZAÇÃO: Cache o resultado para futuras consultas
        _set_cached_project_details(project_id, normalized_details)
        
        # OTIMIZAÇÃO: Log silenciado para evitar spam (projeto encontrado é comum)
        # self.logger.info(f"Projeto encontrado: {projeto_dict.get('Projeto', 'N/A')}")
        
        return normalized_details

    def obter_fontes_disponiveis(self):
        """
        Detecta automaticamente arquivos dadosr_apt_* disponíveis no diretório de dados
        e retorna uma lista de meses/anos que podem ser usados para criar abas dinamicamente.
        NÃO inclui dadosr.csv pois este é sempre usado para a Visão Atual.
        
        Returns:
            list: Lista de dicionários com informações sobre fontes disponíveis
                  Formato: [{'mes': 1, 'ano': 2025, 'nome_arquivo': 'dadosr_apt_jan', 'label': 'Jan/2025'}, ...]
                  Ordenado do mais recente para o mais antigo
        """
        try:
            logger.info("Detectando fontes de dados dadosr_apt_* disponíveis...")
            
            # Obtém o diretório de dados
            data_dir = self.csv_path.parent
            
            # Lista todos os arquivos CSV que seguem o padrão dadosr_apt_*
            arquivos_apt = list(data_dir.glob("dadosr_apt_*.csv"))
            
            fontes = []
            
            # Processa cada arquivo encontrado
            for arquivo in arquivos_apt:
                nome_arquivo = arquivo.stem  # Remove a extensão .csv
                
                # Extrai a abreviação do mês do nome do arquivo
                # Formato esperado: dadosr_apt_abr, dadosr_apt_jan, etc.
                if '_' in nome_arquivo:
                    partes = nome_arquivo.split('_')
                    if len(partes) >= 3:
                        abrev_mes = partes[2]  # 'abr', 'jan', etc.
                        
                        # Mapeia abreviação para mês/ano
                        mes_num, ano = self._mapear_abreviacao_para_data(abrev_mes)
                        
                        if mes_num and ano:
                            label = f"{self._obter_nome_mes_pt(mes_num)}/{ano}"
                            fontes.append({
                                'mes': mes_num,
                                'ano': ano,
                                'nome_arquivo': nome_arquivo,
                                'label': label
                            })
                            logger.info(f"Fonte detectada: {nome_arquivo} -> {label}")
            
            # Ordena por ano e mês (mais recente primeiro)
            fontes.sort(key=lambda x: (x['ano'], x['mes']), reverse=True)
            
            logger.info(f"Total de fontes detectadas: {len(fontes)}")
            return fontes
            
        except Exception as e:
            logger.error(f"Erro ao detectar fontes disponíveis: {e}")
            return []

    def _mapear_abreviacao_para_data(self, abrev_mes):
        """
        Mapeia abreviação do mês para número do mês e ano.
        
        Args:
            abrev_mes (str): Abreviação do mês (ex: 'jan', 'fev', 'mar')
            
        Returns:
            tuple: (mes_num, ano) ou (None, None) se não conseguir mapear
        """
        # Mapeamento de abreviações para números de mês
        mes_abbr_to_num = {
            'jan': 1, 'fev': 2, 'mar': 3, 'abr': 4, 'mai': 5, 'jun': 6,
            'jul': 7, 'ago': 8, 'set': 9, 'out': 10, 'nov': 11, 'dez': 12
        }
        
        if abrev_mes.lower() not in mes_abbr_to_num:
            logger.warning(f"Abreviação de mês desconhecida: {abrev_mes}")
            return None, None
            
        mes_num = mes_abbr_to_num[abrev_mes.lower()]
        
        # Lógica melhorada para determinar o ano
        hoje = datetime.now()
        ano_atual = hoje.year
        
        # Para dados históricos de 2025, sempre usa 2025
        # Esta lógica pode ser expandida conforme necessário para outros anos
        if ano_atual == 2025:
            ano_assumido = 2025
            logger.info(f"Usando ano 2025 para mês {mes_num} (abrev: {abrev_mes})")
        else:
            # Lógica para anos futuros: 
            # Se o mês é significativamente maior que o atual (mais de 3 meses), pode ser do ano passado
            # Caso contrário, assume ano atual
            if mes_num > hoje.month + 3:
                ano_assumido = ano_atual - 1
                logger.info(f"Mês {mes_num} parece ser do ano anterior ({ano_assumido})")
            else:
                ano_assumido = ano_atual
                logger.info(f"Usando ano atual ({ano_assumido}) para mês {mes_num}")
            
        return mes_num, ano_assumido
    
    def _obter_nome_mes_pt(self, mes_num):
        """
        Obtém o nome do mês em português para o número do mês.
        
        Args:
            mes_num (int): Número do mês (1-12)
            
        Returns:
            str: Nome do mês abreviado em português
        """
        mes_num_to_label = {
            1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun',
            7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
        }
        
        return mes_num_to_label.get(mes_num, f"Mês{mes_num}")

    def get_specialist_list(self):
        """Carrega os dados e retorna uma lista única e ordenada de especialistas."""
        try:
            dados = self.carregar_dados()
            if dados.empty:
                self.logger.warning("Dados vazios para listar especialistas")
                return []
            
            if 'Especialista' not in dados.columns:
                self.logger.error("Coluna 'Especialista' não encontrada no DataFrame")
                return []
            
            # Remove valores nulos e obtém lista única ordenada
            especialistas = dados['Especialista'].dropna().unique()
            especialistas_sorted = sorted(especialistas)
            
            self.logger.info(f"Encontrados {len(especialistas_sorted)} especialistas únicos")
            return especialistas_sorted
            
        except Exception as e:
            self.logger.error(f"Erro ao obter lista de especialistas: {str(e)}")
            return []

    def gerar_dados_status_report(self, project_id):
        """
        Gera os dados necessários para o status report de um projeto específico.
        """
        try:
            logger.info(f"Gerando dados de status report para projeto {project_id}")
            
            # Converte project_id para int para garantir compatibilidade
            try:
                project_id_int = int(project_id)
            except (ValueError, TypeError):
                logger.warning(f"Não foi possível converter project_id '{project_id}' para int")
                return self._get_empty_status_report_data(project_id, f"ID de projeto inválido: {project_id}")
            
            # Carregar dados do projeto
            dados = self.carregar_dados()
            if dados.empty:
                logger.warning("Dados vazios para gerar status report")
                return self._get_empty_status_report_data(project_id, "Dados não disponíveis")
            
            # Buscar projeto específico usando o ID convertido
            projeto = dados[dados['Numero'] == project_id_int]
            if projeto.empty:
                logger.warning(f"Projeto {project_id_int} não encontrado")
                return self._get_empty_status_report_data(project_id, f"Projeto {project_id_int} não encontrado")
            
            projeto_row = projeto.iloc[0]
            
            # Calcular progresso
            percentual_concluido = float(projeto_row.get('Conclusao', 0.0))
            data_vencimento = projeto_row.get('VencimentoEm', 'N/A')
            logger.info(f"Data vencimento bruta: {repr(data_vencimento)} (tipo: {type(data_vencimento)})")
            
            if pd.notna(data_vencimento):
                try:
                    # Usar pandas para conversão como nos outros endpoints
                    data_vencimento_dt = pd.to_datetime(data_vencimento)
                    data_prevista_termino = data_vencimento_dt.strftime('%d/%m/%Y')
                    logger.info(f"Data prevista convertida com sucesso: {data_prevista_termino}")
                    
                    # Calcular status do prazo usando pandas Timestamp
                    from datetime import datetime as dt_module  # Import com alias para evitar conflito
                    hoje = dt_module.now()
                    data_vencimento_py = data_vencimento_dt.to_pydatetime()  # Converter para datetime do Python
                    
                    if data_vencimento_py < hoje:
                        status_prazo = 'Atrasado'
                    elif (data_vencimento_py - hoje).days <= 7:
                        status_prazo = 'Próximo do Prazo'
                    else:
                        status_prazo = 'No Prazo'
                        
                    logger.info(f"Status do prazo calculado: {status_prazo}")
                except Exception as e:
                    logger.error(f"Erro ao converter data de vencimento: {str(e)}")
                    data_prevista_termino = 'N/A'
                    status_prazo = 'N/A'
            else:
                logger.warning(f"Data de vencimento é NaT ou inválida: {data_vencimento}")
                data_prevista_termino = 'N/A'
                status_prazo = 'N/A'
            
            # Calcular esforço
            horas_trabalhadas = float(projeto_row.get('HorasTrabalhadas', 0))
            horas_restantes = float(projeto_row.get('HorasRestantes', 0))
            horas_planejadas = horas_trabalhadas + horas_restantes
            
            if horas_planejadas > 0:
                percentual_consumido = round((horas_trabalhadas / horas_planejadas) * 100, 1)
            else:
                percentual_consumido = 0.0
            
            # Determinar status geral do indicador
            # Primeiro verificar se o projeto está realmente concluído
            status_projeto = projeto_row.get('Status', '').upper()
            status_concluidos = ['FECHADO', 'ENCERRADO', 'RESOLVIDO', 'CANCELADO']
            
            if status_projeto in status_concluidos:
                # Projeto realmente concluído
                status_geral_indicador = 'azul'  # Azul para concluído
            elif percentual_concluido >= 90:
                # Alto percentual de conclusão, mas ainda não finalizado
                status_geral_indicador = 'verde'  # Verde para quase concluído
            elif percentual_concluido >= 70:
                # Bom progresso
                status_geral_indicador = 'verde'
            elif percentual_concluido >= 30:
                # Progresso moderado - verificar se está atrasado
                if status_prazo == 'Atrasado':
                    status_geral_indicador = 'vermelho'
                else:
                    status_geral_indicador = 'amarelo'
            else:
                # Baixo progresso
                status_geral_indicador = 'vermelho'
            
            # Buscar backlog_id para o projeto
            backlog_id = self.get_backlog_id_for_project(project_id)
            
            # Buscar milestones do backlog
            milestones = []
            # Inicializar categorias de tarefas
            tarefas_proximo_prazo = []
            tarefas_em_andamento = []
            tarefas_em_revisao = []
            tarefas_pendentes = []
            tarefas_concluidas = []
            
            if backlog_id:
                logger.info(f"Backlog ID encontrado: {backlog_id}")
                
                try:
                    milestones = self.get_milestones_from_backlog(backlog_id)
                    logger.info(f"Milestones encontrados: {len(milestones) if milestones else 0}")
                except Exception as e:
                    logger.error(f"Erro ao buscar milestones: {str(e)}")
                    milestones = []
                
                # Carregar tarefas do backlog
                try:
                    from app.models import Task, Column
                    from datetime import datetime, timedelta
                    
                    all_tasks = Task.query.filter_by(backlog_id=backlog_id).all()
                    logger.info(f"Total de tarefas encontradas: {len(all_tasks)}")
                    
                    hoje = datetime.now()
                    sete_dias = hoje + timedelta(days=7)
                    
                    for task in all_tasks:
                        try:
                            # Determinar o status da tarefa
                            status_nome = 'N/A'
                            if task.column_id:
                                column = Column.query.get(task.column_id)
                                if column:
                                    status_nome = column.name
                            
                            # Determinar data de vencimento
                            data_vencimento = None
                            if task.due_date:
                                data_vencimento = task.due_date
                            elif task.start_date:
                                data_vencimento = task.start_date
                            
                            task_data = {
                                'id': task.id,
                                'titulo': task.title or 'N/A',
                                'descricao': task.description or '',
                                'status': status_nome,
                                'especialista': task.specialist_name or 'N/A',
                                'prioridade': task.priority or 'N/A',
                                'data_criacao': task.created_at.strftime('%d/%m/%Y') if task.created_at else 'N/A',
                                'data_vencimento': data_vencimento.strftime('%d/%m/%Y') if data_vencimento else 'N/A',
                                'data_inicio': task.start_date.strftime('%d/%m/%Y') if task.start_date else 'N/A',
                                'estimativa': task.estimated_effort or 0,
                                'progresso': 0  # Não há campo progress no modelo, usar 0
                            }
                            
                            # Categorizar tarefa baseado no status da coluna PRIMEIRO
                            status_lower = status_nome.lower()
                            
                            # PRIORIDADE 1: Status da coluna (define o estado atual da tarefa)
                            if 'concluído' in status_lower or 'concluido' in status_lower or 'done' in status_lower or 'finalizado' in status_lower:
                                tarefas_concluidas.append(task_data)
                            elif 'andamento' in status_lower or 'progresso' in status_lower or 'doing' in status_lower or 'em progresso' in status_lower:
                                tarefas_em_andamento.append(task_data)
                            elif 'revisão' in status_lower or 'revisao' in status_lower or 'review' in status_lower:
                                tarefas_em_revisao.append(task_data)
                            
                            # PRIORIDADE 2: Para tarefas pendentes (A Fazer, etc), verificar data de vencimento
                            elif 'fazer' in status_lower or 'todo' in status_lower or 'pendente' in status_lower:
                                # Verificar se tem data de vencimento e se está próxima (no futuro)
                                if data_vencimento and data_vencimento > hoje and data_vencimento <= sete_dias:
                                    # Tarefas com vencimento futuro em até 7 dias
                                    tarefas_proximo_prazo.append(task_data)
                                else:
                                    # Tarefas pendentes sem prazo próximo (incluindo atrasadas)
                                    tarefas_pendentes.append(task_data)
                            
                            # PRIORIDADE 3: Demais tarefas (status não reconhecido)
                            else:
                                # Verificar data para categorizar tarefas com status desconhecido
                                if data_vencimento and data_vencimento > hoje and data_vencimento <= sete_dias:
                                    tarefas_proximo_prazo.append(task_data)
                                else:
                                    tarefas_pendentes.append(task_data)
                            
                        except Exception as e:
                            logger.error(f"Erro ao processar tarefa {task.id}: {str(e)}")
                            continue
                    
                    logger.info(f"Tarefas categorizadas: Próximo prazo: {len(tarefas_proximo_prazo)}, Em andamento: {len(tarefas_em_andamento)}, Em revisão: {len(tarefas_em_revisao)}, Pendentes: {len(tarefas_pendentes)}, Concluídas: {len(tarefas_concluidas)}")
                    
                except Exception as e:
                    logger.error(f"Erro ao carregar tarefas do backlog: {str(e)}")
            else:
                logger.warning(f"Backlog não encontrado para projeto {project_id}")
            
            # Buscar marcos recentes
            try:
                marcos_recentes = self.obter_marcos_recentes(project_id)
                logger.info(f"Marcos recentes encontrados: {len(marcos_recentes) if marcos_recentes else 0}")
            except Exception as e:
                logger.error(f"Erro ao buscar marcos recentes: {str(e)}")
                marcos_recentes = []

            # Buscar riscos e impedimentos do backlog
            riscos_impedimentos = []
            notas_observacoes = []
            
            if backlog_id:
                try:
                    # Buscar riscos
                    from app.models import ProjectRisk, Note
                    
                    project_risks = ProjectRisk.query.filter_by(backlog_id=backlog_id).order_by(ProjectRisk.created_at.desc()).all()
                    for risk in project_risks:
                        risco_data = {
                            'id': risk.id,
                            'descricao': risk.description,
                            'impacto': risk.impact.value if risk.impact else 'N/A',
                            'probabilidade': risk.probability.value if risk.probability else 'N/A',
                            'status': risk.status.value if risk.status else 'N/A',
                            'severidade': risk.severity,
                            'responsavel': risk.responsible or 'N/A',
                            'plano_mitigacao': risk.mitigation_plan or '',
                            'plano_contingencia': risk.contingency_plan or '',
                            'data_identificacao': risk.identified_date.strftime('%d/%m/%Y') if risk.identified_date else 'N/A',
                            'data_resolucao': risk.resolved_date.strftime('%d/%m/%Y') if risk.resolved_date else None,
                            'tendencia': risk.trend or 'N/A'
                        }
                        riscos_impedimentos.append(risco_data)
                    
                    logger.info(f"Riscos encontrados: {len(riscos_impedimentos)}")
                    
                    # Buscar notas e observações  
                    # NOVA ABORDAGEM: Usar flag include_in_status_report (opt-out)
                    # Por padrão todas as notas aparecem, apenas as marcadas como False são excluídas
                    project_notes = Note.query.filter_by(
                        backlog_id=backlog_id, 
                        include_in_status_report=True
                    ).order_by(Note.created_at.desc()).all()
                    
                    for note in project_notes:
                        nota_data = {
                            'id': note.id,
                            'conteudo': note.content,
                            'categoria': note.category,
                            'prioridade': note.priority,
                            'status_relatorio': note.report_status,
                            'data_criacao': note.created_at.strftime('%d/%m/%Y %H:%M') if note.created_at else 'N/A',
                            'data_evento': note.event_date.strftime('%d/%m/%Y') if note.event_date else None,
                            'tags': [tag.name for tag in note.tags] if note.tags else []
                        }
                        notas_observacoes.append(nota_data)
                    
                    logger.info(f"Notas encontradas: {len(notas_observacoes)}")
                    
                except Exception as e:
                    logger.error(f"Erro ao buscar riscos e notas: {str(e)}")
            
            # Informações gerais do projeto (para compatibilidade)
            info_geral = {
                'id': str(project_id),
                'numero': str(projeto_row.get('Numero', project_id)),
                'nome': str(projeto_row.get('Projeto', 'N/A')),
                'squad': str(projeto_row.get('Squad', 'N/A')),
                'especialista': str(projeto_row.get('Especialista', 'N/A')),
                'account_manager': str(projeto_row.get('Account Manager', 'N/A')),
                'data_inicio': projeto_row.get('DataInicio', 'N/A'),
                'data_vencimento': projeto_row.get('VencimentoEm', 'N/A'),
                'status': str(projeto_row.get('Status', 'N/A')),
                'status_atual': str(projeto_row.get('Status', 'N/A')),
                'conclusao': projeto_row.get('Conclusao', 0),
                'horas_trabalhadas': projeto_row.get('HorasTrabalhadas', 0),
                'horas_restantes': projeto_row.get('HorasRestantes', 0)
            }
            
            # Montar resultado final na estrutura esperada pelo template
            resultado = {
                'info_geral': info_geral,
                'progresso': {
                    'percentual_concluido': round(percentual_concluido, 1),
                    'data_prevista_termino': data_prevista_termino,
                    'status_prazo': status_prazo
                },
                'esforco': {
                    'horas_planejadas': round(horas_planejadas, 1),
                    'horas_utilizadas': round(horas_trabalhadas, 1),
                    'percentual_consumido': percentual_consumido
                },
                'status_geral_indicador': status_geral_indicador,
                'milestones': milestones or [],
                # Adicionar as tarefas categorizadas
                'tarefas_proximo_prazo': tarefas_proximo_prazo,
                'tarefas_em_andamento': tarefas_em_andamento,
                'tarefas_em_revisao': tarefas_em_revisao,
                'tarefas_pendentes': tarefas_pendentes,
                'tarefas_concluidas': tarefas_concluidas,
                'marcos_recentes': marcos_recentes or [],
                'backlog_id': backlog_id,
                'riscos_impedimentos': riscos_impedimentos,
                'notas': notas_observacoes,
                'proximos_passos': []
            }
            
            logger.info(f"Status report gerado com sucesso para projeto {project_id}")
            logger.info(f"Progresso: {percentual_concluido}%, Status: {status_prazo}, Indicador: {status_geral_indicador}")
            
            return resultado
            
        except Exception as e:
            logger.exception(f"Erro ao gerar dados de status report para projeto {project_id}: {str(e)}")
            return self._get_empty_status_report_data(project_id, f"Erro interno: {str(e)}")

    def _get_empty_status_report_data(self, project_id, error_message, info_geral=None):
        """
        Retorna uma estrutura vazia de status report em caso de erro.
        """
        default_info = {
            'id': str(project_id),
            'numero': str(project_id),
            'nome': 'Projeto não encontrado',
            'squad': 'N/A',
            'especialista': 'N/A',
            'account_manager': 'N/A',
            'data_inicio': 'N/A',
            'data_vencimento': 'N/A',
            'status': 'N/A',
            'status_atual': 'N/A',
            'conclusao': 0,
            'horas_trabalhadas': 0,
            'horas_restantes': 0
        }
        
        return {
            'info_geral': info_geral or default_info,
            'progresso': {
                'percentual_concluido': 0,
                'data_prevista_termino': 'N/A',
                'status_prazo': 'N/A'
            },
            'esforco': {
                'horas_planejadas': 0,
                'horas_utilizadas': 0,
                'percentual_consumido': 0
            },
            'status_geral_indicador': 'cinza',
            'milestones': [],
            # Corrigir para usar as categorias de tarefas esperadas pelo template
            'tarefas_proximo_prazo': [],
            'tarefas_em_andamento': [],
            'tarefas_em_revisao': [],
            'tarefas_pendentes': [],
            'tarefas_concluidas': [],
            'marcos_recentes': [],
            'backlog_id': None,
            'riscos_impedimentos': [],
            'notas': [],
            'proximos_passos': [],
            'error': error_message
        }

    def obter_marcos_recentes(self, project_id):
        """
        Obtém marcos recentes relacionados ao projeto.
        """
        try:
            logger.info(f"Buscando marcos recentes para projeto {project_id}")
            
            # Buscar o backlog_id para o projeto
            backlog_id = self.get_backlog_id_for_project(project_id)
            
            if not backlog_id:
                logger.warning(f"Nenhum backlog encontrado para projeto {project_id}")
                return []
            
            # Buscar os milestones do backlog
            milestones = self.get_milestones_from_backlog(backlog_id)
            
            # Converter para formato esperado pelo template (marcos_recentes)
            marcos_recentes = []
            for milestone in milestones:
                marco_data = {
                    'id': milestone.get('id'),
                    'nome': milestone.get('titulo', 'N/A'),  # titulo vem do get_milestones_from_backlog
                    'title': milestone.get('titulo', 'N/A'),  # fallback para compatibilidade
                    'data_planejada': milestone.get('data_vencimento', 'N/A'),  # data_vencimento vem do get_milestones_from_backlog
                    'due_date': milestone.get('data_vencimento', 'N/A'),  # fallback para compatibilidade
                    'status': 'Concluído' if milestone.get('concluido', False) else 'Pendente',
                    'atrasado': False,  # TODO: Implementar lógica de atraso se necessário
                    'descricao': milestone.get('descricao', ''),
                    'data_criacao': milestone.get('data_criacao', 'N/A')
                }
                marcos_recentes.append(marco_data)
            
            logger.info(f"Convertidos {len(marcos_recentes)} milestones para marcos recentes")
            return marcos_recentes
            
        except Exception as e:
            logger.error(f"Erro ao buscar marcos recentes: {str(e)}")
            return []

    def get_backlog_id_for_project(self, project_id):
        """
        Obtém o backlog_id associado a um projeto específico.
        """
        try:
            from app.models import Backlog  # Import local
            
            # Buscar backlog pelo project_id
            backlog = Backlog.query.filter_by(project_id=str(project_id)).first()
            
            if backlog:
                logger.info(f"Backlog encontrado: ID {backlog.id} para projeto {project_id}")
                return backlog.id
            else:
                logger.warning(f"Nenhum backlog encontrado para projeto {project_id}")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao buscar backlog para projeto {project_id}: {str(e)}")
            return None

    def get_milestones_from_backlog(self, backlog_id):
        """
        Obtém os milestones de um backlog específico.
        """
        try:
            from app.models import ProjectMilestone  # Import local
            
            milestones = ProjectMilestone.query.filter_by(backlog_id=backlog_id).all()
            
            milestones_data = []
            for milestone in milestones:
                milestone_data = {
                    'id': milestone.id,
                    'titulo': milestone.name or 'N/A',  # Usar name em vez de title
                    'descricao': milestone.description or '',
                    'data_vencimento': milestone.planned_date.strftime('%d/%m/%Y') if milestone.planned_date else 'N/A',  # Usar planned_date em vez de due_date
                    'concluido': milestone.status.value == 'Concluído' if milestone.status else False,  # Usar status enum
                    'data_criacao': milestone.created_at.strftime('%d/%m/%Y') if milestone.created_at else 'N/A'
                }
                milestones_data.append(milestone_data)
            
            logger.info(f"Encontrados {len(milestones_data)} milestones para backlog {backlog_id}")
            return milestones_data
            
        except Exception as e:
            logger.error(f"Erro ao buscar milestones do backlog {backlog_id}: {str(e)}")
            return []

    def gerar_status_report(self, project_id):
        """
        Gera um status report completo para um projeto.
        """
        try:
            logger.info(f"Gerando status report para projeto {project_id}")
            
            # Gerar dados do relatório
            dados_relatorio = self.gerar_dados_status_report(project_id)
            
            # Aqui você pode adicionar lógica adicional de formatação se necessário
            
            return dados_relatorio
            
        except Exception as e:
            logger.exception(f"Erro ao gerar status report para projeto {project_id}: {str(e)}")
            return self._get_empty_status_report_data(project_id, f"Erro ao gerar relatório: {str(e)}")

    def _adicionar_verificacao_backlog(self, dataframe):
        """
        Método auxiliar para adicionar a coluna 'backlog_exists' a um DataFrame.
        Verifica quais projetos têm backlog no banco de dados.
        """
        if dataframe.empty or 'Numero' not in dataframe.columns:
            logger.info("DataFrame vazio ou sem coluna 'Numero'. Pulando verificação de backlog.")
            if 'Numero' in dataframe.columns:
                dataframe['backlog_exists'] = False
            return dataframe
            
        # Garante que 'Numero' seja string para a consulta do backlog
        dataframe['Numero'] = dataframe['Numero'].astype(str)
        
        # Pega todos os IDs de projeto (números) únicos e não vazios
        project_ids = dataframe['Numero'].dropna().unique().tolist()
        project_ids = [pid for pid in project_ids if pid]  # Remove vazios

        if project_ids:
            try:
                # Importa o modelo Backlog e db localmente para evitar importação circular
                from app.models import Backlog
                from app import db
                
                # Consulta o banco para ver quais IDs têm backlog
                backlogs_existentes = db.session.query(Backlog.project_id)\
                                                .filter(Backlog.project_id.in_(project_ids))\
                                                .all()
                # Cria um set com os IDs que têm backlog para busca rápida
                ids_com_backlog = {result[0] for result in backlogs_existentes}
                logger.info(f"Encontrados {len(ids_com_backlog)} backlogs para {len(project_ids)} projetos ativos verificados.")
                
                # Adiciona a coluna 'backlog_exists' ao DataFrame
                dataframe['backlog_exists'] = dataframe['Numero'].apply(lambda pid: pid in ids_com_backlog if pd.notna(pid) else False)

            except Exception as db_error:
                logger.error(f"Erro ao consultar backlogs existentes: {db_error}", exc_info=True)
                # Se der erro no DB, assume que nenhum backlog existe para não quebrar
                dataframe['backlog_exists'] = False
        else:
            logger.info("Nenhum ID de projeto válido encontrado para verificar backlog.")
            dataframe['backlog_exists'] = False
            
        return dataframe


# Funções auxiliares fora da classe
def normalize_status(status):
    """Normaliza o status para comparação"""
    if pd.isna(status):
        return ''
    return str(status).strip().upper()

def map_status_concluido(status):
    """Mapeia diferentes variações de status concluído"""
    normalized = normalize_status(status)
    return normalized in ['CONCLUÍDO', 'CONCLUIDO', 'FINALIZADO', 'DONE', 'COMPLETED']

def format_status_frontend(status):
    """Formata o status para exibição no frontend"""
    if pd.isna(status):
        return 'N/A'
    return str(status).strip().title()
