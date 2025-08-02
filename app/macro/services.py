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

# Instância global do leitor de tipos de serviço
type_service_reader = None

# Constantes de status atualizadas
STATUS_NAO_ATIVOS = ['FECHADO', 'ENCERRADO', 'RESOLVIDO', 'CANCELADO']
STATUS_EM_ANDAMENTO = ['NOVO', 'AGUARDANDO', 'BLOQUEADO', 'EM ATENDIMENTO']
STATUS_ATRASADO = ['ATRASADO']
STATUS_ATIVO = ['ATIVO']

# 🚀 CACHE AGRESSIVO PARA CONTAINERS: TTLs aumentados drasticamente
_MACRO_CACHE = {
    'dados': None,
    'timestamp': None,
    'ttl_seconds': 300,  # 🚀 CACHE AGRESSIVO: 5 minutos (era 2min)
    'project_details_cache': {},
    'project_cache_ttl': 600,  # 🚀 CACHE AGRESSIVO: 10 minutos (era 5min)
    'api_cache': {},  # ⚡ NOVO: Cache para resultados de APIs
    'api_cache_ttl': 180,  # 🚀 Cache de APIs: 3 minutos
    'processing_lock': False  # 🔒 NOVO: Evita carregamento simultâneo
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

# ⚡ NOVO: Cache para APIs específicas
def _get_cached_api_result(api_key):
    """Retorna resultado da API do cache se válido."""
    cache_data = _MACRO_CACHE['api_cache'].get(api_key)
    
    if cache_data is None:
        return None
    
    elapsed = time.time() - cache_data['timestamp']
    if elapsed < _MACRO_CACHE['api_cache_ttl']:
        return cache_data['result']
    else:
        # Remove cache expirado
        del _MACRO_CACHE['api_cache'][api_key]
        return None

def _set_cached_api_result(api_key, result):
    """Cacheia resultado de uma API específica."""
    _MACRO_CACHE['api_cache'][api_key] = {
        'result': result,
        'timestamp': time.time()
    }

# 🔒 NOVO: Sistema de lock para evitar carregamentos simultâneos
def _is_processing_locked():
    """Verifica se há carregamento em andamento."""
    return _MACRO_CACHE['processing_lock']

def _set_processing_lock(locked):
    """Define/remove lock de processamento."""
    _MACRO_CACHE['processing_lock'] = locked

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
        
        # Inicializa o leitor de tipos de serviço
        global type_service_reader
        if type_service_reader is None:
            from .typeservice_reader import TypeServiceReader
            type_service_reader = TypeServiceReader()
            logger.info("TypeServiceReader inicializado no MacroService")

    def carregar_dados(self, fonte=None):
        """
        ⚡ OTIMIZADO: Carrega dados com cache agressivo e sistema de lock para containers.
        
        Args:
            fonte (str, optional): Nome específico do arquivo ou None para dadosr.csv
        
        Returns:
            pd.DataFrame: DataFrame com os dados processados
        """
        start_time = time.time()
        
        # 🚀 CACHE HIT: Verificar cache primeiro (fonte=None usa cache)
        if fonte is None:
            cached_dados = _get_cached_dados()
            if cached_dados is not None:
                cache_time = (time.time() - start_time) * 1000
                logger.info(f"⚡ CACHE HIT: Dados carregados em {cache_time:.1f}ms ({len(cached_dados)} registros)")
                return cached_dados
        
        # 🔒 LOCK: Evita carregamentos simultâneos para dados principais
        if fonte is None and _is_processing_locked():
            logger.info("🔒 AGUARDANDO: Outro processo carregando dados principais...")
            # Aguarda até 3 segundos pelo lock
            for _ in range(30):  # 30 x 100ms = 3s
                time.sleep(0.1)
                if not _is_processing_locked():
                    break
                cached_dados = _get_cached_dados()
                if cached_dados is not None:
                    lock_time = (time.time() - start_time) * 1000
                    logger.info(f"⚡ CACHE APÓS LOCK: Dados disponíveis em {lock_time:.1f}ms")
                    return cached_dados
        
        # 🔒 DEFINE LOCK para dados principais
        if fonte is None:
            _set_processing_lock(True)
        
        try:
            # 📁 DETERMINA ARQUIVO
            if fonte:
                data_dir = self.csv_path.parent
                if not fonte.endswith('.csv'):
                    fonte = fonte + '.csv'
                csv_path = data_dir / fonte
                logger.info(f"📁 Fonte específica: {fonte}")
            else:
                csv_path = self.csv_path
                logger.info(f"📁 Fonte principal: dadosr.csv")
            
            if not csv_path.is_file():
                logger.error(f"❌ Arquivo não encontrado: {csv_path}")
                return pd.DataFrame()
            
            # 📊 CARREGAMENTO DO CSV
            read_start = time.time()
            dados = pd.read_csv(
                csv_path,
                dtype=str,
                sep=';',
                encoding='latin1',
            )
            read_time = (time.time() - read_start) * 1000
            logger.info(f"📊 CSV lido em {read_time:.1f}ms ({len(dados)} linhas)")
            
            # 🔄 PROCESSAMENTO
            process_start = time.time()
            dados_processados = self._processar_dados_otimizado(dados, csv_path)
            process_time = (time.time() - process_start) * 1000
            
            # 💾 CACHE apenas dados principais
            if fonte is None:
                _set_cached_dados(dados_processados)
                cache_set_time = (time.time() - process_start - process_time/1000) * 1000
                logger.info(f"💾 Cache atualizado em {cache_set_time:.1f}ms")
            
            total_time = (time.time() - start_time) * 1000
            logger.info(f"✅ DADOS CARREGADOS: {total_time:.1f}ms total (CSV: {read_time:.1f}ms, Proc: {process_time:.1f}ms)")
            
            return dados_processados
            
        except Exception as e:
            logger.error(f"❌ ERRO ao carregar: {str(e)}")
            return pd.DataFrame()
        finally:
            # 🔓 REMOVE LOCK sempre
            if fonte is None:
                _set_processing_lock(False)

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
                    # Tenta primeiro formato com horas, depois sem horas
                    dados[col] = pd.to_datetime(original_col, format='%d/%m/%Y %H:%M', errors='coerce')
                    # Se falhar, tenta formato sem horas
                    mask_failed = dados[col].isna() & original_col.notna() & (original_col != '')
                    if mask_failed.any():
                        dados.loc[mask_failed, col] = pd.to_datetime(original_col[mask_failed], format='%d/%m/%Y', errors='coerce')
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
                'Cliente (Completo)': 'Cliente',
                'Assunto': 'Projeto',
                'Serviço (2º Nível)': 'Squad',
                'Serviço (3º Nível)': 'TipoServico',
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
            
            # --- Passo 1.3.1: Fallback para coluna Projeto (NOVO) ---
            # Se Assunto está vazio ou não existe, usa Cliente como fallback
            if 'Projeto' in dados.columns and 'Cliente' in dados.columns:
                mask_projeto_vazio = dados['Projeto'].isna() | (dados['Projeto'] == '') | (dados['Projeto'] == 'nan')
                if mask_projeto_vazio.any():
                    dados.loc[mask_projeto_vazio, 'Projeto'] = dados.loc[mask_projeto_vazio, 'Cliente']
                    # Log apenas se houver fallbacks aplicados
                    num_fallbacks = mask_projeto_vazio.sum()
                    if num_fallbacks > 0:
                        logger.info(f"Aplicado fallback Cliente→Projeto em {num_fallbacks} registros")
            elif 'Cliente' in dados.columns and 'Projeto' not in dados.columns:
                # Se a coluna Assunto não existe ainda, cria Projeto copiando de Cliente
                dados['Projeto'] = dados['Cliente']
                logger.info("Criada coluna 'Projeto' usando dados de 'Cliente' (coluna Assunto não encontrada)")
            
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

        # Importa o leitor de tipos de serviço
        from .typeservice_reader import type_service_reader
        
        resultados = []
        hoje = datetime.now().date()
        
        try:
            for _, row in projetos.iterrows():
                # Usa .get(col_name, default_value) para evitar KeyError se uma coluna não existir
                numero_val = row.get(col_numero, '')
                # Fallback para 'Número' original se 'Numero' não existir
                if numero_val == '' and 'Número' in row:
                    numero_val = row.get('Número', '')
                
                # Trata Account Manager com e sem espaço no final
                account_val = row.get(col_account, row.get('Account Manager ', ''))
                
                # CORREÇÃO 1: Cliente real (não projeto)
                cliente_val = row.get('Cliente', 'N/A')
                projeto_val = row.get(col_projeto, 'N/A')
                
                # CORREÇÃO 2: Categoria do tipo de serviço
                # Busca o tipo de serviço em várias colunas possíveis (incluindo nomes pré e pós renomeação)
                colunas_tipo_servico = [
                    'TipoServico', 'Tipo de Serviço', 'Tipo de servico',   # Nomes possíveis no CSV atual
                    'Serviço (2º Nível)', 'Servico 2 Nivel',               # Nomes nos CSVs históricos  
                    'Serviço (3º Nível)', 'Servico 3 Nivel',               # Nomes alternativos
                    'Projeto'                                               # Nome após renomeação (pode conter o tipo)
                ]
                tipo_servico_raw = ''
                for col in colunas_tipo_servico:
                    if col in row.index and pd.notna(row[col]) and str(row[col]).strip():
                        valor = str(row[col]).strip()
                        # Se for a coluna 'Projeto' e contém apenas categoria simples (M365, Azure, etc.), usa
                        if col == 'Projeto' and valor in ['M365', 'Azure', 'Data e Power', 'Outros']:
                            tipo_servico_raw = valor
                            break
                        elif col != 'Projeto':  # Para outras colunas, usa diretamente
                            tipo_servico_raw = valor
                            break
                
                categoria_servico = type_service_reader.obter_categoria(tipo_servico_raw) if tipo_servico_raw else 'N/A'
                
                # CORREÇÃO 3: Cálculo do tempo de vida do projeto
                tempo_vida_dias = 0
                data_abertura = None
                
                # Tenta encontrar data de abertura em diferentes colunas possíveis
                colunas_abertura = ['DataInicio', 'DataAbertura', 'Data Abertura', 'data_abertura', 'Aberto em']
                for col in colunas_abertura:
                    if col in row.index and pd.notna(row[col]):
                        data_abertura = row[col]
                        break
                
                if data_abertura and pd.notna(data_abertura):
                    try:
                        if isinstance(data_abertura, str):
                            # Tenta converter string para data
                            data_abertura = pd.to_datetime(data_abertura, errors='coerce')
                        
                        if pd.notna(data_abertura):
                            data_abertura_date = data_abertura.date() if hasattr(data_abertura, 'date') else data_abertura
                            tempo_vida_dias = (hoje - data_abertura_date).days
                    except Exception as e:
                        logger.debug(f"Erro ao calcular tempo de vida para projeto {numero_val}: {str(e)}")
                        tempo_vida_dias = 0
                
                # Formata as datas com verificação
                data_inicio_str = row.get(col_data_inicio, pd.NaT)
                data_inicio_fmt = data_inicio_str.strftime('%d/%m/%Y') if pd.notna(data_inicio_str) else ''
                
                # CORREÇÃO 4: Vencimento com "-" se vazio
                data_vencimento_str = row.get(col_data_vencimento, pd.NaT)
                data_vencimento_fmt = data_vencimento_str.strftime('%d/%m/%Y') if pd.notna(data_vencimento_str) else '-'
                
                # CORREÇÃO 5: Data resolvido com "-" se vazio
                # Nota: 'Resolvido em' é renomeado para 'DataTermino' no processamento
                data_resolvido = row.get('DataTermino', row.get('Resolvido em', pd.NaT))
                data_resolvido_fmt = data_resolvido.strftime('%d/%m/%Y') if pd.notna(data_resolvido) else '-'
                
                # Outros dados
                faturamento_val = row.get('Faturamento', row.get('TipoFaturamento', 'N/A'))
                
                # Dicionário base do projeto
                projeto_dict = {
                    'numero': numero_val,
                    'projeto': projeto_val,  # Nome do projeto
                    'status': row.get(col_status, 'N/A'),
                    'squad': row.get(col_squad, 'N/A'),
                    'especialista': row.get(col_especialista, 'N/A'),
                    'account': account_val,
                    'data_inicio': data_inicio_fmt,
                    'dataPrevEnc': data_vencimento_fmt,  # CORRIGIDO: usar "-" se vazio
                    'conclusao': float(row.get(col_conclusao, 0.0)) if pd.notna(row.get(col_conclusao)) else 0.0,
                    'horas_trabalhadas': float(row.get(col_horas_trab, 0.0)) if pd.notna(row.get(col_horas_trab)) else 0.0,
                    'horasRestantes': float(row.get(col_horas_rest, 0.0)) if pd.notna(row.get(col_horas_rest)) else 0.0,
                    'Horas': float(row.get(col_horas_prev, 0.0)) if pd.notna(row.get(col_horas_prev)) else 0.0,
                    'backlog_exists': row.get('backlog_exists', False),
                    # Campos corrigidos para o relatório geral
                    'cliente': cliente_val,  # CORRIGIDO: cliente real
                    'servico': categoria_servico,  # CORRIGIDO: categoria do tipo de serviço
                    'tipo_faturamento': faturamento_val,
                    'data_resolvido': data_resolvido_fmt,  # CORRIGIDO: "-" se vazio
                    'account_manager': account_val,
                    'tempo_vida': tempo_vida_dias  # CORRIGIDO: dias calculados
                }
                
                # Adiciona campos auxiliares se existirem (para relatórios evolutivo, comparativo, etc.)
                if '_fonte_periodo' in row.index:
                    projeto_dict['_fonte_periodo'] = row.get('_fonte_periodo', 'N/A')
                
                if '_ordem_periodo' in row.index:
                    projeto_dict['_ordem_periodo'] = row.get('_ordem_periodo', 0)
                
                if '_mudancas' in row.index:
                    projeto_dict['_mudancas'] = row.get('_mudancas', '')
                
                if '_status_anterior' in row.index:
                    projeto_dict['_status_anterior'] = row.get('_status_anterior', '')
                
                resultados.append(projeto_dict)
            
            logger.info(f"Formatados {len(resultados)} projetos para relatório geral")
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
            
            # Filtra projetos concluídos (sem filtro de Squad para debug)
            projetos_concluidos = dados_base[
                (dados_base['Status'].isin(self.status_concluidos)) &
                (pd.to_datetime(dados_base['DataTermino'], format='%d/%m/%Y %H:%M', errors='coerce').dt.month == mes_atual) &
                (pd.to_datetime(dados_base['DataTermino'], format='%d/%m/%Y %H:%M', errors='coerce').dt.year == ano_atual)
            ].copy()
            
            # Log para debug
            logger.debug(f"Projetos concluídos filtrados (sem CDB): {len(projetos_concluidos)}")
            
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
            
            # Prepara dados para o modal - INCLUINDO TODAS AS COLUNAS NECESSÁRIAS
            colunas_necessarias = ['Numero', 'Projeto', 'Status', 'Squad', 'Horas', 'HorasTrabalhadas', 'HorasRestantes', 'VencimentoEm', 'DataTermino', 'backlog_exists']
            
            # Adiciona colunas importantes que podem existir nos dados
            colunas_opcionais = ['Especialista', 'Account Manager', 'TipoServico', 'Faturamento', 'Conclusao']
            for col in colunas_opcionais:
                if col in projetos_concluidos.columns:
                    colunas_necessarias.append(col)
            
            dados_modal = projetos_concluidos[colunas_necessarias].copy()
            
            # Renomeia colunas para o formato esperado pelo frontend
            mapeamento_colunas = {
                'Numero': 'numero',
                'Projeto': 'projeto',
                'Status': 'status',
                'Squad': 'squad',
                'Horas': 'horasContratadas',
                'HorasTrabalhadas': 'horasTrabalhadas',
                'HorasRestantes': 'horasRestantes',
                'VencimentoEm': 'dataPrevEnc',
                'DataTermino': 'dataTermino',
                'backlog_exists': 'backlog_exists',  # Mantém o nome
                'Especialista': 'especialista',
                'Account Manager': 'account',
                'TipoServico': 'servico',
                'Faturamento': 'tipo_faturamento',
                'Conclusao': 'conclusao'
            }
            
            # Aplica apenas os mapeamentos para colunas que existem
            mapeamento_existente = {k: v for k, v in mapeamento_colunas.items() if k in dados_modal.columns}
            dados_modal = dados_modal.rename(columns=mapeamento_existente)
            
            # Adiciona colunas que podem estar faltando com valores padrão
            if 'especialista' not in dados_modal.columns:
                dados_modal['especialista'] = '-'
            if 'account' not in dados_modal.columns:
                dados_modal['account'] = '-'
            if 'servico' not in dados_modal.columns:
                dados_modal['servico'] = '-'
            if 'tipo_faturamento' not in dados_modal.columns:
                dados_modal['tipo_faturamento'] = '-'
            if 'conclusao' not in dados_modal.columns:
                dados_modal['conclusao'] = 0
            
            # Padroniza valores vazios ou N/A para "-"
            colunas_texto = ['especialista', 'account', 'servico', 'tipo_faturamento']
            for col in colunas_texto:
                if col in dados_modal.columns:
                    dados_modal[col] = dados_modal[col].fillna('-')
                    dados_modal[col] = dados_modal[col].replace(['N/A', 'NÃO DEFINIDO', 'NÃO ALOCADO', ''], '-')
            
            # Formatação de horas igual ao Relatório Geral (duas casas decimais)
            dados_modal['horasContratadas'] = pd.to_numeric(dados_modal['horasContratadas'], errors='coerce').fillna(0).round(2)
            dados_modal['horasTrabalhadas'] = pd.to_numeric(dados_modal['horasTrabalhadas'], errors='coerce').fillna(0).round(2)
            dados_modal['horasRestantes'] = pd.to_numeric(dados_modal['horasRestantes'], errors='coerce').fillna(0).round(2)
            
            # Formatação de datas igual ao Relatório Geral (sem timestamp/timezone)
            dados_modal['dataTermino'] = pd.to_datetime(dados_modal['dataTermino'], errors='coerce').dt.strftime('%d/%m/%Y')
            dados_modal['dataTermino'] = dados_modal['dataTermino'].replace('NaT', None)
            
            dados_modal['dataPrevEnc'] = pd.to_datetime(dados_modal['dataPrevEnc'], errors='coerce').dt.strftime('%d/%m/%Y')
            dados_modal['dataPrevEnc'] = dados_modal['dataPrevEnc'].replace('NaT', None)
            
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
            
            # Calcula tempo de vida do projeto (em dias)
            if 'DataInicio' in dados_base.columns:
                hoje = datetime.now()
                dados_base['TempoVida'] = (hoje - dados_base['DataInicio']).dt.days.fillna(0).astype(int)
            else:
                dados_base['TempoVida'] = 0
            
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
        Calcula a eficiência geral dos projetos usando a mesma metodologia do Status Report por Período.
        Fórmula composta: 70% eficiência de horas + 30% eficiência de prazo
        
        Retorna:
        - total: eficiência geral (porcentagem)
        - dados: DataFrame com os projetos e suas eficiências
        - metricas: métricas específicas de eficiência
        """
        try:
            logger.info("Calculando eficiência...")
            
            # Usa dados já tratados
            dados_base = self.preparar_dados_base(dados)

            # --- Filtra projetos da CDB DATA SOLUTIONS ---
            if 'Especialista' in dados_base.columns:
                dados_filtrados_cdb = dados_base[~dados_base['Especialista'].astype(str).str.upper().isin(['CDB DATA SOLUTIONS'])]
                logger.info(f"Eficiência: Removidos {len(dados_base) - len(dados_filtrados_cdb)} projetos da CDB DATA SOLUTIONS.")
            else:
                logger.warning("Eficiência: Coluna 'Especialista' não encontrada para filtrar CDB.")
                dados_filtrados_cdb = dados_base.copy()

            # === 1. EFICIÊNCIA DE HORAS (Fechados + Em Andamento) ===
            # Inclui projetos fechados e em andamento para análise mais abrangente
            projetos_para_eficiencia = dados_filtrados_cdb[
                dados_filtrados_cdb['Status'].isin(self.status_concluidos + ['NOVO', 'EM ATENDIMENTO', 'AGUARDANDO', 'BLOQUEADO'])
            ].copy()
            
            logger.info(f"Eficiência: Analisando {len(projetos_para_eficiencia)} projetos (fechados + em andamento).")

            # Filtra projetos com horas válidas
            projetos_com_horas = projetos_para_eficiencia[
                (projetos_para_eficiencia['Horas'].fillna(0) > 0) &
                (projetos_para_eficiencia['HorasTrabalhadas'].fillna(0) > 0)
            ].copy()

            eficiencia_horas = 0.0
            if len(projetos_com_horas) > 0:
                horas_estimadas_total = projetos_com_horas['Horas'].sum()
                horas_trabalhadas_total = projetos_com_horas['HorasTrabalhadas'].sum()
                
                if horas_estimadas_total > 0 and horas_trabalhadas_total > 0:
                    # FÓRMULA INVERTIDA: (Horas Estimadas / Horas Trabalhadas) × 100
                    # Maior = melhor (120% = 20% mais eficiente que estimado)
                    eficiencia_horas = round((horas_estimadas_total / horas_trabalhadas_total * 100), 1)
                    
                    # Aplica limite máximo para evitar valores extremos
                    eficiencia_horas = min(eficiencia_horas, 200.0)

            # Calcula eficiência individual dos projetos com horas (para o modal)
            if len(projetos_com_horas) > 0:
                projetos_com_horas['eficiencia_horas'] = (projetos_com_horas['Horas'] / projetos_com_horas['HorasTrabalhadas'] * 100).round(1)
                # Aplica limite nos projetos individuais também
                projetos_com_horas['eficiencia_horas'] = projetos_com_horas['eficiencia_horas'].clip(upper=200.0)

            # === 2. EFICIÊNCIA DE PRAZO (Fechados + Em Andamento) ===
            eficiencia_prazo = 0.0
            projetos_no_prazo = 0
            projetos_com_prazo = 0

            # Mapeia colunas se necessário
            if 'Resolvido em' in projetos_para_eficiencia.columns:
                projetos_para_eficiencia['DataTermino'] = projetos_para_eficiencia['Resolvido em']
            if 'Vencimento em' in projetos_para_eficiencia.columns:
                projetos_para_eficiencia['VencimentoEm'] = projetos_para_eficiencia['Vencimento em']

            # Para projetos EM ANDAMENTO, usa data atual como "data de análise"
            from datetime import datetime
            data_atual = datetime.now()
            projetos_para_eficiencia['DataAnalise'] = projetos_para_eficiencia['DataTermino'].fillna(data_atual)

            # Filtra projetos com datas válidas para análise de prazo
            projetos_com_datas = projetos_para_eficiencia[
                projetos_para_eficiencia['VencimentoEm'].notna() & 
                (projetos_para_eficiencia['VencimentoEm'] != '')
            ].copy()

            if len(projetos_com_datas) > 0:
                try:
                    # Converte datas
                    projetos_com_datas['VencimentoEm'] = pd.to_datetime(
                        projetos_com_datas['VencimentoEm'], 
                        errors='coerce', 
                        dayfirst=True
                    )
                    projetos_com_datas['DataAnalise'] = pd.to_datetime(
                        projetos_com_datas['DataAnalise'], 
                        errors='coerce'
                    )
                    
                    # Remove projetos com datas inválidas
                    validos_para_prazo = projetos_com_datas.dropna(subset=['VencimentoEm', 'DataAnalise']).copy()
                    
                    if not validos_para_prazo.empty:
                        # Aplica lógica de prazo (mesma do Status Report)
                        for _, projeto in validos_para_prazo.iterrows():
                            data_analise = projeto['DataAnalise']
                            data_vencimento = projeto['VencimentoEm']
                            
                            # Início do mês de análise
                            inicio_mes_analise = datetime(data_analise.year, data_analise.month, 1)
                            inicio_mes_analise = pd.Timestamp(inicio_mes_analise).normalize()
                            
                            # Projeto no prazo se VencimentoEm >= início do mês de análise
                            if data_vencimento.normalize() >= inicio_mes_analise:
                                projetos_no_prazo += 1
                        
                        projetos_com_prazo = len(validos_para_prazo)
                        eficiencia_prazo = round((projetos_no_prazo / projetos_com_prazo) * 100, 1)
                        
                except Exception as e:
                    logger.warning(f"Erro ao processar datas para eficiência de prazo: {str(e)}")
                    eficiencia_prazo = 0.0

            # === 3. EFICIÊNCIA COMPOSTA (70% Horas + 30% Prazo) ===
            peso_horas = 0.7  # 70% para eficiência de horas
            peso_prazo = 0.3  # 30% para eficiência de prazo
            
            eficiencia_composta = round(
                (eficiencia_horas * peso_horas) + (eficiencia_prazo * peso_prazo), 1
            )

            # === 4. PREPARA DADOS PARA O MODAL ===
            # Usa projetos com horas válidas para exibir no modal
            dados_modal = pd.DataFrame()
            if len(projetos_com_horas) > 0:
                # Adiciona verificação de backlog
                projetos_com_horas = self._adicionar_verificacao_backlog(projetos_com_horas)

                # Prepara colunas do modal
                colunas_modal = ['Numero', 'Projeto', 'Status', 'Squad', 'Horas', 'HorasTrabalhadas', 'eficiencia_horas', 'backlog_exists']
                
                # Certifica-se de que a coluna Numero existe
                if 'Numero' not in projetos_com_horas.columns and 'Número' in projetos_com_horas.columns:
                    projetos_com_horas['Numero'] = projetos_com_horas['Número']
                elif 'Numero' not in projetos_com_horas.columns:
                    projetos_com_horas['Numero'] = ''
                    
                # Seleciona apenas as colunas que existem
                colunas_existentes = [col for col in colunas_modal if col in projetos_com_horas.columns]
                dados_modal = projetos_com_horas[colunas_existentes].copy()
                
                # Renomeia colunas para o formato esperado pelo frontend
                dados_modal = dados_modal.rename(columns={
                    'Numero': 'numero',
                    'Projeto': 'projeto',
                    'Status': 'status',
                    'Squad': 'squad',
                    'Horas': 'horasContratadas',
                    'HorasTrabalhadas': 'horasTrabalhadas',
                    'eficiencia_horas': 'eficiencia',
                    'backlog_exists': 'backlog_exists'
                })
                
                # Arredonda as horas para uma casa decimal
                dados_modal['horasContratadas'] = dados_modal['horasContratadas'].round(1)
                dados_modal['horasTrabalhadas'] = dados_modal['horasTrabalhadas'].round(1)

            # === 5. CALCULA MÉTRICAS ADICIONAIS ===
            metricas = {
                'eficiencia_geral': eficiencia_composta,
                'eficiencia_composta': eficiencia_composta,
                'eficiencia_horas': eficiencia_horas,
                'eficiencia_prazo': eficiencia_prazo,
                'total_projetos': len(projetos_com_horas),
                'projetos_analisados': len(projetos_para_eficiencia),
                'projetos_com_prazo': projetos_com_prazo,
                'projetos_no_prazo': projetos_no_prazo,
                'peso_horas': peso_horas,
                'peso_prazo': peso_prazo
            }
            
            # Calcula métricas por squad se houver dados
            if len(projetos_com_horas) > 0:
                metricas['media_por_squad'] = projetos_com_horas.groupby('Squad')['eficiencia_horas'].mean().round(1).to_dict()
                metricas['projetos_acima_100'] = len(projetos_com_horas[projetos_com_horas['eficiencia_horas'] > 100])
                metricas['projetos_abaixo_80'] = len(projetos_com_horas[projetos_com_horas['eficiencia_horas'] < 80])
            else:
                metricas['media_por_squad'] = {}
                metricas['projetos_acima_100'] = 0
                metricas['projetos_abaixo_80'] = 0
            
            logger.info(f"Eficiência calculada: {eficiencia_composta}% (Horas: {eficiencia_horas}%, Prazo: {eficiencia_prazo}%)")
            
            return {
                'total': eficiencia_composta,
                'dados': dados_modal.replace({np.nan: None}) if not dados_modal.empty else pd.DataFrame(),
                'metricas': metricas
            }
            
        except Exception as e:
            logger.error(f"Erro ao calcular eficiência: {str(e)}", exc_info=True)
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
            
            # Projetos concluídos
            projetos_concluidos = dados_base[dados_base['Status'].isin(self.status_concluidos)]
            projetos_concluidos_count = len(projetos_concluidos)

            # Eficiência de entrega (usa o método específico corrigido)
            eficiencia_entrega_result = self.calcular_eficiencia_entrega(dados_base)
            eficiencia = eficiencia_entrega_result['total']

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
                
                # Extrai valores garantindo que sejam válidos e JSON-serializáveis
                horas_totais = float(soma_horas.get(status, 0.0))
                conclusao_media_raw = media_conclusao.get(status, 0.0)
                
                # 🔧 CORREÇÃO: Trata valores NaN antes da serialização JSON
                if pd.isna(horas_totais):
                    horas_totais = 0.0
                if pd.isna(conclusao_media_raw):
                    conclusao_media_raw = 0.0
                
                conclusao_media = round(float(conclusao_media_raw), 1)
                
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
                    'quantidade': int(quantidade),  # Garante que é int
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
                    
                    # 🔧 CORREÇÃO: Trata valores NaN para projetos concluídos
                    if pd.isna(horas_concluidos):
                        horas_concluidos = 0.0
                    if pd.isna(conclusao_concluidos):
                        conclusao_concluidos = 0.0
                    
                    por_status['FECHADO'] = {
                        'quantidade': quantidade_concluidos,
                        'horas_totais': round(float(horas_concluidos), 1),
                        'conclusao_media': round(float(conclusao_concluidos), 1),
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
            # 🔧 CORREÇÃO: Substitui valores NaN por None antes da conversão para dict
            if not projetos_risco_df.empty:
                resultado['projetos_risco'] = projetos_risco_df.replace({np.nan: None}).to_dict('records')
            else:
                resultado['projetos_risco'] = []
            
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
                    taxa_uso = (projetos_ativos_esp / total_projetos_ativos_geral) * 100
                    # 🔧 CORREÇÃO: Trata valores NaN e garante arredondamento seguro
                    if pd.isna(taxa_uso):
                        taxa_uso = 0.0
                    else:
                        taxa_uso = round(float(taxa_uso), 1)
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

                # 🔧 CORREÇÃO: Trata valores NaN para horas
                total_horas_safe = 0.0 if pd.isna(total_horas_esp) else float(total_horas_esp)
                horas_trabalhadas_safe = 0.0 if pd.isna(horas_trabalhadas_esp) else float(horas_trabalhadas_esp)
                horas_restantes_safe = 0.0 if pd.isna(horas_restantes_esp) else float(horas_restantes_esp)
                
                resultado_final[especialista] = {
                    # A chave 'total_projetos' agora reflete os projetos ativos do especialista
                    'total_projetos': int(projetos_ativos_esp),
                    # Mantém as colunas de horas como antes
                    'horas_contratadas': round(total_horas_safe, 1),
                    'horas_trabalhadas': round(horas_trabalhadas_safe, 1),
                    'horas_restantes': round(horas_restantes_safe, 1),
                    'projetos_bloqueados': int(projetos_bloqueados),
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

                    # 🔧 CORREÇÃO: Arredonda valores numéricos e trata NaN
                    for col in ['horas_totais', 'horas_restantes', 'conclusao_media']:
                        accounts_agg[col] = accounts_agg[col].fillna(0.0).round(1)

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
                (dados_filtrados['DataTermino'] >= inicio_periodo) &
                (dados_filtrados['DataTermino'] <= fim_periodo) &
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
                        if mes_hist == 6: fonte_historico = 'dadosr_apt_jun'  # ADICIONADO: mapeamento para junho
                        # Adicionar mapeamentos futuros aqui (Julho, Agosto, etc.)
                    
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
                    fora_prazo_com_data = (validos_para_prazo['VencimentoEm'] < inicio_mes_ref).sum()
                    
                    # 🔧 CORREÇÃO: Projetos sem data de vencimento são considerados FORA DO PRAZO
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
            else:
                # Se não há coluna VencimentoEm ou dados filtrados vazios, todos são fora do prazo
                no_prazo = 0
                fora_prazo = total_mes
                logger.warning(f"[Visão Atual] Coluna 'VencimentoEm' não encontrada ou dados filtrados vazios. Todos os {total_mes} projetos serão considerados FORA DO PRAZO.")

            # Chama a função auxiliar para calcular o histórico dinâmico
            historico = self._calcular_historico_dinamico(mes_referencia)
            
            resultado = {
                'total_mes': total_mes,
                'no_prazo': no_prazo,
                'fora_prazo': fora_prazo,
                'historico': historico
            }
            
            logger.info(f"[Visão Atual] Projetos entregues calculados (CORRIGIDO): {total_mes} no total, {no_prazo} no prazo, {fora_prazo} fora do prazo")
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
                'total': total_novos,
                'novos_projetos': dados_mes  # Adiciona os dados dos projetos novos
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
        Detecta automaticamente arquivos dadosr_apt_* disponíveis no diretório de dados.
        Estes são arquivos "legados" que representam um espelho específico do mês.
        NÃO inclui dadosr.csv pois este contém todos os dados (visão atual para Status Report).
        
        Returns:
            list: Lista de dicionários com informações sobre fontes disponíveis
                  Formato: [{'arquivo': 'dadosr_apt_jan', 'nome_exibicao': 'Janeiro/2025', 'mes': 1, 'ano': 2025}, ...]
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
                
                # Ignora arquivos de backup (que contêm '_backup_' no nome)
                if '_backup_' in nome_arquivo:
                    logger.info(f"Ignorando arquivo de backup: {nome_arquivo}")
                    continue
                
                # Extrai a abreviação do mês do nome do arquivo
                # Formato esperado: dadosr_apt_abr, dadosr_apt_jan, etc.
                if '_' in nome_arquivo:
                    partes = nome_arquivo.split('_')
                    if len(partes) >= 3:
                        abrev_mes = partes[2]  # 'abr', 'jan', etc.
                        
                        # Mapeia abreviação para mês/ano
                        mes_num, ano = self._mapear_abreviacao_para_data(abrev_mes)
                        
                        if mes_num and ano:
                            nome_mes_completo = self._obter_nome_mes_completo(mes_num)
                            fontes.append({
                                'arquivo': nome_arquivo,
                                'nome_exibicao': f"{nome_mes_completo}/{ano}",
                                'mes': mes_num,
                                'ano': ano,
                                'abreviacao': abrev_mes.upper()
                            })
                            logger.info(f"Fonte detectada: {nome_arquivo} -> {nome_mes_completo}/{ano}")
            
            # Ordena por ano e mês (mais recente primeiro)
            fontes.sort(key=lambda x: (x['ano'], x['mes']), reverse=True)
            
            logger.info(f"Total de fontes históricas detectadas: {len(fontes)}")
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
    
    def _obter_nome_mes_completo(self, mes_num):
        """
        Obtém o nome completo do mês em português para o número do mês.
        
        Args:
            mes_num (int): Número do mês (1-12)
            
        Returns:
            str: Nome completo do mês em português
        """
        mes_num_to_nome_completo = {
            1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
            7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
        }
        
        return mes_num_to_nome_completo.get(mes_num, f"Mês {mes_num}")

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
            
            # Calcular progresso - LÓGICA ESPECIAL PARA DEMANDAS INTERNAS
            servico_terceiro_nivel = projeto_row.get('TipoServico', '')
            
            if servico_terceiro_nivel == 'Demandas Internas':
                # Para Demandas Internas, calcular percentual baseado em tarefas
                percentual_concluido = self._calcular_percentual_por_tarefas(project_id)
                logger.info(f"Projeto Demandas Internas detectado - Percentual calculado por tarefas: {percentual_concluido:.1f}%")
            else:
                # Para projetos normais, usar percentual do CSV
                percentual_concluido = float(projeto_row.get('Conclusao', 0.0))
                logger.info(f"Projeto normal - Percentual do CSV: {percentual_concluido:.1f}%")
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
            
            # Calcular esforço - LÓGICA ESPECIAL PARA DEMANDAS INTERNAS
            horas_trabalhadas = float(projeto_row.get('HorasTrabalhadas', 0))
            horas_restantes = float(projeto_row.get('HorasRestantes', 0))
            
            if servico_terceiro_nivel == 'Demandas Internas':
                # Para Demandas Internas, calcular esforço baseado em tarefas
                horas_planejadas = self._calcular_esforco_por_tarefas(project_id)
                logger.info(f"Projeto Demandas Internas detectado - Esforço calculado por tarefas: {horas_planejadas}h")
            else:
                # Para projetos normais, usar esforço do CSV
                horas_planejadas = horas_trabalhadas + horas_restantes
                logger.info(f"Projeto normal - Esforço do CSV: {horas_planejadas}h")
            
            if horas_planejadas > 0:
                percentual_consumido = round((horas_trabalhadas / horas_planejadas) * 100, 1)
            else:
                percentual_consumido = 0.0
            
            # === NOVA LÓGICA DE STATUS GERAL BASEADA EM TAREFAS REAIS ===
            # Inicializar variáveis para análise posterior
            status_projeto = projeto_row.get('Status', '').upper()
            status_concluidos = ['FECHADO', 'ENCERRADO', 'RESOLVIDO', 'CANCELADO']
            status_geral_indicador = 'cinza'  # Default
            
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
                            logger.debug(f"Categorizando tarefa '{task.title}' com status '{status_nome}' (lower: '{status_lower}')")
                            
                            # PRIORIDADE 1: Status da coluna (define o estado atual da tarefa)
                            if 'concluído' in status_lower or 'concluido' in status_lower or 'done' in status_lower or 'finalizado' in status_lower:
                                tarefas_concluidas.append(task_data)
                                logger.debug(f"  → Categorizada como CONCLUÍDA")
                            elif 'andamento' in status_lower or 'progresso' in status_lower or 'doing' in status_lower or 'em progresso' in status_lower:
                                tarefas_em_andamento.append(task_data)
                                logger.debug(f"  → Categorizada como EM ANDAMENTO")
                            elif 'revisão' in status_lower or 'revisao' in status_lower or 'review' in status_lower:
                                tarefas_em_revisao.append(task_data)
                                logger.debug(f"  → Categorizada como EM REVISÃO")
                            
                            # PRIORIDADE 2: Tarefas pendentes SEMPRE vão para "Pendente" (independente da data)
                            elif 'fazer' in status_lower or 'todo' in status_lower or 'pendente' in status_lower:
                                # TODAS as tarefas pendentes vão para seção "Pendente"
                                tarefas_pendentes.append(task_data)
                                logger.debug(f"  → Categorizada como PENDENTE (status reconhecido)")
                            
                            # PRIORIDADE 3: Demais tarefas (status não reconhecido) - verificar data
                            else:
                                # Verificar data para categorizar tarefas com status desconhecido
                                if data_vencimento and data_vencimento > hoje and data_vencimento <= sete_dias:
                                    # Tarefas com status desconhecido mas com prazo próximo
                                    tarefas_proximo_prazo.append(task_data)
                                    logger.debug(f"  → Categorizada como PRÓXIMO PRAZO (status desconhecido, data próxima)")
                                else:
                                    # Tarefas com status desconhecido sem prazo próximo
                                    tarefas_pendentes.append(task_data)
                                    logger.debug(f"  → Categorizada como PENDENTE (status desconhecido, sem data próxima)")
                            
                        except Exception as e:
                            logger.error(f"Erro ao processar tarefa {task.id}: {str(e)}")
                            continue
                    
                    logger.info(f"Tarefas categorizadas: Próximo prazo: {len(tarefas_proximo_prazo)}, Em andamento: {len(tarefas_em_andamento)}, Em revisão: {len(tarefas_em_revisao)}, Pendentes: {len(tarefas_pendentes)}, Concluídas: {len(tarefas_concluidas)}")
                    
                except Exception as e:
                    logger.error(f"Erro ao carregar tarefas do backlog: {str(e)}")
            else:
                logger.warning(f"Backlog não encontrado para projeto {project_id}")
            
            # === NOVA LÓGICA INTELIGENTE DE STATUS GERAL ===
            # Usar percentual do CSV (não das tarefas)
            logger.info(f"Percentual do CSV: {percentual_concluido:.1f}%")
            
            # Calcular indicadores de atividade das tarefas
            total_tarefas = len(tarefas_concluidas) + len(tarefas_em_andamento) + len(tarefas_em_revisao) + len(tarefas_pendentes) + len(tarefas_proximo_prazo)
            tarefas_ativas = len(tarefas_em_andamento) + len(tarefas_em_revisao)
            tem_atividade = tarefas_ativas > 0
            percentual_ativo = (tarefas_ativas / total_tarefas * 100) if total_tarefas > 0 else 0
            
            # Verificar se há tarefas atrasadas (vencimento passado)
            from datetime import datetime
            hoje = datetime.now()
            tarefas_atrasadas = 0
            
            # Contar tarefas em andamento/pendentes que já passaram do prazo
            for task_list in [tarefas_em_andamento, tarefas_em_revisao, tarefas_pendentes]:
                for task in task_list:
                    data_venc_str = task.get('data_vencimento', 'N/A')
                    if data_venc_str != 'N/A':
                        try:
                            data_venc = datetime.strptime(data_venc_str, '%d/%m/%Y')
                            if data_venc < hoje:
                                tarefas_atrasadas += 1
                        except:
                            pass
            
            tem_tarefas_atrasadas = tarefas_atrasadas > 0
            logger.info(f"Tarefas atrasadas: {tarefas_atrasadas}/{total_tarefas}")
            
            # Verificar status do projeto
            status_iniciais = ['NOVO', 'ABERTO']
            projeto_recente = status_projeto in status_iniciais
            projeto_bloqueado = status_projeto == 'BLOQUEADO'
            
            # === ALGORITMO BASEADO NAS ESPECIFICAÇÕES ===
            if status_projeto in status_concluidos:
                # 🔵 AZUL - "Concluído" - Status oficial concluído
                status_geral_indicador = 'azul'
                logger.info(f"Status AZUL: Projeto oficialmente concluído ({status_projeto})")
                
            elif projeto_bloqueado:
                # 🔴 VERMELHO - "Crítico" - Status BLOQUEADO
                status_geral_indicador = 'vermelho'
                logger.info(f"Status VERMELHO: Projeto bloqueado ({status_projeto})")
                
            elif projeto_recente:
                # ⚫ CINZA - "Não Iniciado" - Projeto com status NOVO/ABERTO
                status_geral_indicador = 'cinza'
                logger.info(f"Status CINZA: Projeto recente ({status_projeto}) ainda não iniciado")
                
            elif not tem_tarefas_atrasadas and status_prazo != 'Atrasado':
                # 🟢 VERDE - "Saudável" - Tarefas não atrasadas E projeto no prazo
                status_geral_indicador = 'verde'
                logger.info(f"Status VERDE: Projeto saudável - tarefas no prazo e projeto no prazo")
                
            elif percentual_concluido >= 50 and status_prazo == 'Atrasado':
                # 🟡 AMARELO - "Atenção" - Progresso bom (≥50%) mas atrasado
                status_geral_indicador = 'amarelo'
                logger.info(f"Status AMARELO: Progresso bom ({percentual_concluido:.1f}%) mas projeto atrasado")
                
            elif percentual_concluido >= 40 and percentual_concluido < 75 and tem_atividade:
                # 🟡 AMARELO - "Atenção" - Progresso moderado (40-74%) com atividade
                status_geral_indicador = 'amarelo'
                logger.info(f"Status AMARELO: Progresso moderado ({percentual_concluido:.1f}%) com atividade ({tarefas_ativas} tarefas)")
                
            elif percentual_concluido >= 15 and percentual_concluido < 40 and percentual_ativo >= 20:
                # 🟡 AMARELO - "Atenção" - Progresso baixo (15-39%) mas com ≥20% atividade
                status_geral_indicador = 'amarelo'
                logger.info(f"Status AMARELO: Progresso baixo ({percentual_concluido:.1f}%) mas com {percentual_ativo:.1f}% de atividade")
                
            else:
                # 🔴 VERMELHO - "Crítico" - Demais casos críticos
                if percentual_concluido >= 40 and not tem_atividade:
                    logger.info(f"Status VERMELHO: Progresso moderado ({percentual_concluido:.1f}%) mas sem atividade")
                elif percentual_concluido >= 15 and percentual_ativo < 20:
                    logger.info(f"Status VERMELHO: Progresso baixo ({percentual_concluido:.1f}%) sem atividade suficiente ({percentual_ativo:.1f}%)")
                elif percentual_concluido < 15:
                    logger.info(f"Status VERMELHO: Progresso muito baixo ({percentual_concluido:.1f}%)")
                else:
                    logger.info(f"Status VERMELHO: Situação crítica não categorizada - progresso: {percentual_concluido:.1f}%, atividade: {percentual_ativo:.1f}%")
                
                status_geral_indicador = 'vermelho'
            
            logger.info(f"Status final: {status_geral_indicador} | Progresso CSV: {percentual_concluido:.1f}% | Tarefas ativas: {tarefas_ativas}/{total_tarefas} | Atrasadas: {tarefas_atrasadas} | Projeto: {status_projeto}")
            
            # Buscar marcos recentes
            try:
                marcos_recentes = self.obter_marcos_recentes(project_id)
                logger.info(f"Marcos recentes encontrados: {len(marcos_recentes) if marcos_recentes else 0}")
            except Exception as e:
                logger.error(f"Erro ao buscar marcos recentes: {str(e)}")
                marcos_recentes = []

            # 🆕 NOVO: Buscar fases do projeto
            try:
                fases_projeto = self.obter_fases_projeto(project_id, backlog_id)
                logger.info(f"Fases do projeto encontradas: {len(fases_projeto) if fases_projeto else 0}")
            except Exception as e:
                logger.error(f"Erro ao buscar fases do projeto: {str(e)}")
                fases_projeto = []

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
                            'titulo': risk.title,  # ✅ ADICIONADO: Campo título
                            'title': risk.title,   # ✅ FALLBACK: Para compatibilidade
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
                    ).order_by(
                        Note.event_date.desc().nulls_last(),  # Ordena por data do evento (mais recente primeiro)
                        Note.created_at.desc()  # Fallback para data de criação
                    ).all()
                    
                    for note in project_notes:
                        # Traduzir campos para português
                        categoria_pt = self._traduzir_categoria(note.category)
                        prioridade_pt = self._traduzir_prioridade(note.priority)
                        
                        # Usar data do evento quando disponível, senão usar data de criação
                        data_exibicao = note.event_date.strftime('%d/%m/%Y') if note.event_date else (note.created_at.strftime('%d/%m/%Y %H:%M') if note.created_at else 'N/A')
                        
                        nota_data = {
                            'id': note.id,
                            'conteudo': note.content,
                            'categoria': categoria_pt,
                            'prioridade': prioridade_pt,
                            'status_relatorio': note.report_status,
                            'data_criacao': note.created_at.strftime('%d/%m/%Y %H:%M') if note.created_at else 'N/A',
                            'data_evento': note.event_date.strftime('%d/%m/%Y') if note.event_date else None,
                            'data_exibicao': data_exibicao,  # Campo unificado para exibição
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
                'data_inicio': projeto_row.get('DataInicio').strftime('%d/%m/%Y') if pd.notnull(projeto_row.get('DataInicio')) else 'N/A',
                'data_vencimento': projeto_row.get('VencimentoEm').strftime('%d/%m/%Y') if pd.notnull(projeto_row.get('VencimentoEm')) else 'N/A',
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
                'fases_projeto': fases_projeto or [],  # 🆕 NOVO: Fases do projeto
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
            'fases_projeto': [],  # 🆕 NOVO: Fases do projeto
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
                # 🔄 USAR O STATUS REAL CALCULADO
                status_real = milestone.get('status_real', 'Pendente')
                
                marco_data = {
                    'id': milestone.get('id'),
                    'nome': milestone.get('titulo', 'N/A'),
                    'title': milestone.get('titulo', 'N/A'),  # fallback para compatibilidade
                    'data_planejada': milestone.get('data_vencimento', 'N/A'),
                    'due_date': milestone.get('data_vencimento', 'N/A'),  # fallback para compatibilidade
                    'status': status_real,  # 🆕 USAR STATUS REAL EM VEZ DE LÓGICA SIMPLES
                    'atrasado': milestone.get('atrasado', False),
                    'descricao': milestone.get('descricao', ''),
                    'data_criacao': milestone.get('data_criacao', 'N/A'),
                    'data_inicio_real': milestone.get('data_inicio_real'),
                    'criticidade': milestone.get('criticidade', 'Média')
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
        MELHORADO: Agora considera o status real das tarefas para determinar o status do marco.
        """
        try:
            from app.models import ProjectMilestone, Task, Column  # Import local
            
            milestones = ProjectMilestone.query.filter_by(backlog_id=backlog_id).all()
            
            milestones_data = []
            for milestone in milestones:
                # 🔄 NOVA LÓGICA: Determinar status baseado no estado real das tarefas
                status_real = self._determinar_status_real_marco(milestone, backlog_id)
                
                milestone_data = {
                    'id': milestone.id,
                    'titulo': milestone.name or 'N/A',
                    'descricao': milestone.description or '',
                    'data_vencimento': milestone.planned_date.strftime('%d/%m/%Y') if milestone.planned_date else 'N/A',
                    'concluido': status_real == 'Concluído',
                    'status_real': status_real,  # 🆕 NOVO: Status calculado baseado nas tarefas
                    'data_criacao': milestone.created_at.strftime('%d/%m/%Y') if milestone.created_at else 'N/A',
                    'data_inicio_real': milestone.started_at.strftime('%d/%m/%Y') if milestone.started_at else None,
                    'atrasado': milestone.is_delayed,
                    'criticidade': milestone.criticality.value if milestone.criticality else 'Média'
                }
                milestones_data.append(milestone_data)
            
            logger.info(f"Encontrados {len(milestones_data)} milestones para backlog {backlog_id}")
            return milestones_data
            
        except Exception as e:
            logger.error(f"Erro ao buscar milestones do backlog {backlog_id}: {str(e)}")
            return []

    def _determinar_status_real_marco(self, milestone, backlog_id):
        """
        Determina o status real do marco baseado no estado das tarefas relacionadas.
        """
        try:
            from app.models import Task, Column
            from datetime import datetime
            
            # Se o marco tem data de início real, então pelo menos começou
            if milestone.started_at:
                logger.info(f"Marco '{milestone.name}' tem data de início: {milestone.started_at}")
                
                # Se está marcado como concluído no banco, mantém concluído
                if milestone.status.value == 'Concluído':
                    return 'Concluído'
                else:
                    # Se começou mas não foi concluído, está em andamento
                    return 'Em Andamento'
            
            # Verificar se há tarefas relacionadas ao marco no backlog
            # Vamos considerar que marcos estão relacionados por nome ou proximidade temporal
            marco_nome = milestone.name.lower()
            
            # Buscar tarefas que podem estar relacionadas ao marco
            all_tasks = Task.query.filter_by(backlog_id=backlog_id).all()
            
            tarefas_relacionadas = []
            for task in all_tasks:
                if task.title and any(palavra in task.title.lower() for palavra in marco_nome.split()):
                    tarefas_relacionadas.append(task)
            
            logger.info(f"Marco '{milestone.name}': {len(tarefas_relacionadas)} tarefas relacionadas encontradas")
            
            if not tarefas_relacionadas:
                # Se não há tarefas relacionadas, usar o status do banco
                return milestone.status.value
            
            # Analisar status das tarefas relacionadas
            status_tarefas = []
            for task in tarefas_relacionadas:
                if task.column_id:
                    column = Column.query.get(task.column_id)
                    if column:
                        status_tarefas.append(column.name.lower())
            
            if not status_tarefas:
                return milestone.status.value
            
            # Lógica para determinar status do marco baseado nas tarefas
            concluidas = sum(1 for status in status_tarefas if any(palavra in status for palavra in ['concluí', 'done', 'finalizado']))
            em_andamento = sum(1 for status in status_tarefas if any(palavra in status for palavra in ['andamento', 'progress', 'execu']))
            
            logger.info(f"Marco '{milestone.name}': {concluidas} tarefas concluídas, {em_andamento} em andamento de {len(status_tarefas)} total")
            
            if concluidas == len(status_tarefas):
                return 'Concluído'
            elif em_andamento > 0 or concluidas > 0:
                return 'Em Andamento'
            else:
                return 'Pendente'
                
        except Exception as e:
            logger.error(f"Erro ao determinar status real do marco: {str(e)}")
            return milestone.status.value if milestone.status else 'Pendente'

    def obter_fases_projeto(self, project_id, backlog_id=None):
        """
        Obtém as fases do projeto com informações sobre progresso e status.
        """
        try:
            from app.models import Backlog, ProjectPhaseConfiguration, ProjectMilestone
            
            if not backlog_id:
                backlog_id = self.get_backlog_id_for_project(project_id)
            
            if not backlog_id:
                logger.warning(f"Nenhum backlog encontrado para projeto {project_id}")
                return []
            
            # Buscar configuração do backlog
            backlog = Backlog.query.get(backlog_id)
            if not backlog:
                logger.warning(f"Backlog {backlog_id} não encontrado")
                return []
            
            # 🔄 CORREÇÃO: Determinar tipo de projeto usando ProjectPhaseService
            from app.utils.project_phase_service import ProjectPhaseService
            phase_service = ProjectPhaseService()
            
            # Obtém o tipo de projeto do serviço
            project_type_enum = phase_service.get_project_type(project_id)
            
            # Se não há tipo definido, assume waterfall como padrão
            if not project_type_enum:
                logger.warning(f"Tipo de projeto não definido para projeto {project_id}, usando Waterfall como padrão")
                from app.models import ProjectType
                project_type_enum = ProjectType.WATERFALL
            
            # Determina o tipo como string para logs
            project_type_str = project_type_enum.value.lower()
            current_phase = backlog.current_phase or 1
            
            logger.info(f"Projeto {project_id}: Tipo={project_type_str}, Fase atual={current_phase}")
            
            # Buscar configuração das fases para o tipo de projeto
            fases_config = ProjectPhaseConfiguration.get_phases_for_type(project_type_enum)
            
            # Se não há configuração, criar fases padrão
            if not fases_config:
                fases_config = self._criar_fases_padrao(project_type_str)
            
            # Buscar marcos do projeto
            milestones = self.get_milestones_from_backlog(backlog_id)
            
            # Mapear marcos para fases
            fases_timeline = []
            for fase_config in fases_config:
                fase_number = fase_config.phase_number if hasattr(fase_config, 'phase_number') else fase_config.get('phase_number', 1)
                fase_name = fase_config.phase_name if hasattr(fase_config, 'phase_name') else fase_config.get('phase_name', 'Fase')
                fase_color = fase_config.phase_color if hasattr(fase_config, 'phase_color') else fase_config.get('phase_color', '#E8F5E8')
                
                # Determinar status da fase
                if fase_number < current_phase:
                    status = 'completed'
                elif fase_number == current_phase:
                    status = 'current'
                else:
                    status = 'pending'
                
                # Buscar marcos relacionados à fase
                marcos_da_fase = []
                milestone_names = []
                if hasattr(fase_config, 'get_milestone_names'):
                    milestone_names = fase_config.get_milestone_names()
                elif isinstance(fase_config, dict) and 'milestone_names' in fase_config:
                    milestone_names = fase_config['milestone_names']
                
                # Encontrar marcos que correspondem aos nomes esperados
                for milestone_name in milestone_names:
                    for milestone in milestones:
                        if milestone_name.lower() in milestone.get('titulo', '').lower():
                            marcos_da_fase.append({
                                'nome': milestone.get('titulo'),
                                'status': milestone.get('status_real', 'Pendente'),
                                'data_planejada': milestone.get('data_vencimento'),
                                'atrasado': milestone.get('atrasado', False)
                            })
                            break
                
                # Calcular progresso da fase baseado nos marcos
                total_marcos = len(marcos_da_fase)
                marcos_concluidos = sum(1 for marco in marcos_da_fase if marco['status'] == 'Concluído')
                marcos_em_andamento = sum(1 for marco in marcos_da_fase if marco['status'] == 'Em Andamento')
                
                if total_marcos > 0:
                    progresso = int((marcos_concluidos / total_marcos) * 100)
                    if marcos_em_andamento > 0 and progresso == 0:
                        progresso = 25  # Mostrar algum progresso se há marcos em andamento
                else:
                    progresso = 100 if status == 'completed' else (50 if status == 'current' else 0)
                
                fase_data = {
                    'numero': fase_number,
                    'nome': fase_name,
                    'status': status,
                    'cor': fase_color,
                    'progresso': progresso,
                    'marcos': marcos_da_fase,
                    'descricao': fase_config.phase_description if hasattr(fase_config, 'phase_description') else fase_config.get('phase_description', '')
                }
                
                fases_timeline.append(fase_data)
                
            logger.info(f"Fases do projeto {project_id}: {len(fases_timeline)} fases carregadas")
            return fases_timeline
            
        except Exception as e:
            logger.error(f"Erro ao obter fases do projeto {project_id}: {str(e)}")
            return []

    def _criar_fases_padrao(self, project_type):
        """
        Cria fases padrão se não houver configuração no banco.
        """
        if project_type == 'waterfall':
            return [
                {'phase_number': 1, 'phase_name': 'Planejamento', 'phase_color': '#E8F5E8', 'milestone_names': ['Milestone Start']},
                {'phase_number': 2, 'phase_name': 'Execução', 'phase_color': '#E8F0FF', 'milestone_names': ['Milestone Setup']},
                {'phase_number': 3, 'phase_name': 'CutOver', 'phase_color': '#FFF8E1', 'milestone_names': ['Milestone CutOver']},
                {'phase_number': 4, 'phase_name': 'GoLive', 'phase_color': '#E8FFE8', 'milestone_names': ['Milestone Finish Project']}
            ]
        else:  # agile
            return [
                {'phase_number': 1, 'phase_name': 'Planejamento', 'phase_color': '#E8F5E8', 'milestone_names': ['Milestone Start']},
                {'phase_number': 2, 'phase_name': 'Sprint Planning', 'phase_color': '#F0F8FF', 'milestone_names': ['Milestone Setup']},
                {'phase_number': 3, 'phase_name': 'Desenvolvimento', 'phase_color': '#E8F0FF', 'milestone_names': ['Milestone Developer']},
                {'phase_number': 4, 'phase_name': 'CutOver', 'phase_color': '#FFF8E1', 'milestone_names': ['Milestone CutOver']},
                {'phase_number': 5, 'phase_name': 'GoLive', 'phase_color': '#E8FFE8', 'milestone_names': ['Milestone Finish Project']}
            ]

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

    def calcular_metricas_tipos_servico_simples(self, dados):
        """
        Calcula métricas básicas por tipo de serviço usando categorização CSV.
        Versão simples e incremental.
        
        Args:
            dados (pd.DataFrame): DataFrame com os projetos
            
        Returns:
            dict: Métricas organizadas por categoria
        """
        try:
            from .typeservice_reader import type_service_reader
            
            logger.info("🔄 Calculando métricas simples dos tipos de serviço...")
            
            # Valida arquivo CSV primeiro
            valido, mensagem = type_service_reader.validar_arquivo()
            if not valido:
                logger.error(f"❌ Arquivo CSV inválido: {mensagem}")
                return {'erro': mensagem, 'categorias': {}, 'tipos': {}}
            
            logger.info(f"✅ {mensagem}")
            
            # Verifica coluna TipoServico nos dados
            if 'TipoServico' not in dados.columns:
                logger.warning("Coluna 'TipoServico' não encontrada nos dados")
                return {'erro': 'Coluna TipoServico não encontrada', 'categorias': {}, 'tipos': {}}
            
            # Prepara dados básicos
            dados_limpos = dados[dados['TipoServico'].notna() & (dados['TipoServico'] != '')].copy()
            
            if dados_limpos.empty:
                logger.warning("Nenhum projeto com tipo de serviço válido")
                return {'erro': 'Nenhum projeto com tipo de serviço válido', 'categorias': {}, 'tipos': {}}
            
            # Carrega mapeamento do CSV
            mapeamento_tipos = type_service_reader.carregar_tipos_servico()
            
            # Calcula métricas por tipo
            metricas_tipos = {}
            metricas_categorias = {}
            
            tipos_unicos = dados_limpos['TipoServico'].unique()
            
            for tipo in tipos_unicos:
                dados_tipo = dados_limpos[dados_limpos['TipoServico'] == tipo]
                categoria = type_service_reader.obter_categoria(tipo)
                
                # Métricas básicas do tipo
                metricas_tipo = {
                    'nome': tipo,
                    'categoria': categoria,
                    'total_projetos': len(dados_tipo),
                    'projetos_ativos': len(dados_tipo[~dados_tipo['Status'].isin(['FECHADO', 'ENCERRADO', 'RESOLVIDO', 'CANCELADO'])]),
                    'projetos_concluidos': len(dados_tipo[dados_tipo['Status'].isin(['FECHADO', 'ENCERRADO', 'RESOLVIDO', 'CANCELADO'])])
                }
                
                # Adiciona horas se disponível
                if 'Horas' in dados_tipo.columns:
                    metricas_tipo['horas_totais'] = float(dados_tipo['Horas'].sum())
                else:
                    metricas_tipo['horas_totais'] = 0.0
                
                metricas_tipos[tipo] = metricas_tipo
                
                # Agrega por categoria
                if categoria not in metricas_categorias:
                    metricas_categorias[categoria] = {
                        'nome': categoria,
                        'total_projetos': 0,
                        'projetos_ativos': 0,
                        'projetos_concluidos': 0,
                        'horas_totais': 0.0,
                        'tipos_na_categoria': []
                    }
                
                metricas_categorias[categoria]['total_projetos'] += metricas_tipo['total_projetos']
                metricas_categorias[categoria]['projetos_ativos'] += metricas_tipo['projetos_ativos']
                metricas_categorias[categoria]['projetos_concluidos'] += metricas_tipo['projetos_concluidos']
                metricas_categorias[categoria]['horas_totais'] += metricas_tipo['horas_totais']
                metricas_categorias[categoria]['tipos_na_categoria'].append(tipo)
            
            # Adiciona informações de período
            import datetime
            data_atual = datetime.datetime.now()
            
            # Pega datas mínima e máxima dos dados se disponível
            periodo_info = {
                'data_analise': data_atual.strftime('%d/%m/%Y %H:%M'),
                'mes_referencia': data_atual.strftime('%m/%Y'),
                'total_registros_analisados': len(dados_limpos)
            }
            
            # Tenta obter período dos dados se houver coluna de data
            if 'DataCriacao' in dados_limpos.columns or 'DataInicio' in dados_limpos.columns:
                coluna_data = 'DataCriacao' if 'DataCriacao' in dados_limpos.columns else 'DataInicio'
                try:
                    # Converte para datetime se necessário
                    datas_validas = pd.to_datetime(dados_limpos[coluna_data], errors='coerce').dropna()
                    if not datas_validas.empty:
                        periodo_info['data_inicio'] = datas_validas.min().strftime('%d/%m/%Y')
                        periodo_info['data_fim'] = datas_validas.max().strftime('%d/%m/%Y')
                        periodo_info['periodo_dias'] = (datas_validas.max() - datas_validas.min()).days
                except:
                    pass
            
            resultado = {
                'tipos': metricas_tipos,
                'categorias': metricas_categorias,
                'resumo': {
                    'total_tipos': len(tipos_unicos),
                    'total_categorias': len(metricas_categorias),
                    'total_projetos': len(dados_limpos),
                    'tipos_cadastrados_csv': len(mapeamento_tipos)
                },
                'periodo': periodo_info,
                'status': 'sucesso'
            }
            
            logger.info(f"✅ Métricas calculadas: {len(tipos_unicos)} tipos, {len(metricas_categorias)} categorias")
            return resultado
            
        except Exception as e:
            logger.error(f"❌ Erro ao calcular métricas tipos de serviço: {str(e)}", exc_info=True)
            return {
                'erro': str(e),
                'categorias': {},
                'tipos': {},
                'status': 'erro'
            }

    def calcular_projetos_principais_mes(self, dados, mes_referencia=None):
        """
        Calcula os 5 principais projetos do mês baseado em:
        1. Seleção manual (quando disponível) 
        2. Volume de horas trabalhadas ESPECIFICAMENTE no mês (fallback automático)
        
        Args:
            dados (pd.DataFrame): DataFrame com os dados dos projetos do mês atual
            mes_referencia (datetime): Mês de referência para o cálculo
            
        Returns:
            dict: Lista com os 5 principais projetos e suas informações
        """
        try:
            logger.info(f"🚀 CALCULAR: Iniciando calcular_projetos_principais_mes")
            logger.info(f"🚀 CALCULAR: dados.shape = {dados.shape if not dados.empty else 'VAZIO'}")
            logger.info(f"🚀 CALCULAR: mes_referencia = {mes_referencia}")
            
            if dados.empty:
                logger.warning("⚠️ CALCULAR: DataFrame vazio para calcular projetos principais do mês")
                return {'projetos': [], 'total_encontrados': 0}
            
            logger.info(f"📊 CALCULAR: Calculando projetos principais do mês: {mes_referencia.strftime('%B/%Y') if mes_referencia else 'atual'}")
            
            logger.info(f"📊 CALCULAR: Preparando dados base...")
            dados_base = self.preparar_dados_base(dados)
            logger.info(f"📊 CALCULAR: Dados base preparados: {dados_base.shape}")
            
            # === CALCULAR HORAS TRABALHADAS NO MÊS ESPECÍFICO ===
            logger.info(f"⏰ CALCULAR: Calculando horas trabalhadas no mês...")
            dados_com_horas_mes = self._calcular_horas_trabalhadas_no_mes(dados_base, mes_referencia)
            logger.info(f"⏰ CALCULAR: Horas calculadas para {dados_com_horas_mes.shape[0]} projetos")
            
            # Filtros para projetos principais:
            # 1. Tem horas trabalhadas no mês específico
            # 2. Não são projetos cancelados
            
            logger.info(f"🔍 CALCULAR: Aplicando filtros...")
            projetos_filtrados = dados_com_horas_mes[
                (dados_com_horas_mes['horas_trabalhadas_mes'].fillna(0) > 0) &  # Tem horas trabalhadas no mês
                (~dados_com_horas_mes['Status'].isin(['CANCELADO']))  # Exclui cancelados
            ].copy()
            
            logger.info(f"🔍 CALCULAR: Projetos filtrados (com horas trabalhadas no mês): {len(projetos_filtrados)}")
            
            if projetos_filtrados.empty:
                logger.warning("⚠️ CALCULAR: Nenhum projeto encontrado com atividade no mês")
                return {'projetos': [], 'total_encontrados': 0}
                
            logger.info(f"✅ CALCULAR: {len(projetos_filtrados)} projetos passaram nos filtros, prosseguindo...")
            
            # === VERIFICAR SE HÁ SELEÇÃO MANUAL ===
            logger.info(f"🔍 CALCULAR: CHEGOU ATÉ A VERIFICAÇÃO DE SELEÇÃO MANUAL!")
            logger.info(f"🔍 CALCULAR: Chamando carregar_projetos_principais_selecionados...")
            projetos_selecionados_manual = self.carregar_projetos_principais_selecionados(mes_referencia)
            
            logger.info(f"🔍 CARD: Verificando seleção manual para {mes_referencia.strftime('%Y-%m') if mes_referencia else 'None'}")
            logger.info(f"🔍 CARD: Projetos selecionados manual: {projetos_selecionados_manual}")
            logger.info(f"🔍 CARD: Total projetos filtrados disponíveis: {len(projetos_filtrados)}")
            
            if projetos_selecionados_manual:
                logger.info(f"✅ CARD: Usando seleção manual: {len(projetos_selecionados_manual)} projetos configurados")
                logger.info(f"🔍 CARD: Números únicos nos dados: {list(projetos_filtrados['Numero'].unique())[:10]}...")
                
                # Debug: verificar tipos de dados
                tipos_manual = [type(x) for x in projetos_selecionados_manual[:3]]
                tipos_dados = [type(x) for x in projetos_filtrados['Numero'].head(3)]
                logger.info(f"🔍 CARD: Tipos manual: {tipos_manual}, Tipos dados: {tipos_dados}")
                
                # Converter ambos para string para comparação consistente
                projetos_selecionados_manual_str = [str(x) for x in projetos_selecionados_manual]
                projetos_filtrados_str = projetos_filtrados.copy()
                projetos_filtrados_str['Numero'] = projetos_filtrados_str['Numero'].astype(str)
                
                # Filtrar apenas os projetos selecionados manualmente que existem nos dados
                top_projetos = projetos_filtrados_str[
                    projetos_filtrados_str['Numero'].isin(projetos_selecionados_manual_str)
                ].copy()
                
                logger.info(f"🔍 CARD: Projetos encontrados na seleção: {len(top_projetos)}")
                logger.info(f"🔍 CARD: Números encontrados: {list(top_projetos['Numero'].values)}")
                
                if not top_projetos.empty:
                    # Manter a ordem da seleção manual
                    top_projetos = top_projetos.set_index('Numero').loc[
                        [num for num in projetos_selecionados_manual_str if num in top_projetos.index]
                    ].reset_index()
                    
                    # Converter de volta para tipo original
                    top_projetos['Numero'] = top_projetos['Numero'].astype(projetos_filtrados['Numero'].dtype)
                    
                    criterio_usado = f"Seleção manual ({len(top_projetos)} projetos configurados)"
                    logger.info(f"✅ CARD: Projetos manuais selecionados com sucesso: {len(top_projetos)}")
                else:
                    logger.warning(f"⚠️  CARD: Nenhum projeto manual encontrado nos dados disponíveis!")
                    logger.info(f"🔍 CARD: Fallback para seleção automática")
                    top_projetos = projetos_filtrados.nlargest(5, 'horas_trabalhadas_mes')
                    criterio_usado = "Volume de horas trabalhadas no mês (fallback - projetos manuais não encontrados)"
                
            else:
                logger.info("🔄 CARD: Nenhuma seleção manual encontrada, usando ranking automático por horas")
                
                # Ordena apenas por horas trabalhadas no mês específico (critério principal)
                # Ordena por horas trabalhadas no mês e pega top 5
                top_projetos = projetos_filtrados.nlargest(5, 'horas_trabalhadas_mes')
                criterio_usado = "Volume de horas trabalhadas no mês"
                logger.info(f"🔄 CARD: Seleção automática: {len(top_projetos)} projetos por ranking")
            
            # === BUSCAR INFORMAÇÕES COMPLEMENTARES (DE-PARA) ===
            top_projetos_enriquecido = self._enriquecer_projetos_com_historico(top_projetos, mes_referencia)
            
            # Formata dados para o template
            projetos_principais = []
            for _, projeto in top_projetos_enriquecido.iterrows():
                # Usa andamento da coluna Conclusao
                andamento = projeto.get('Conclusao', 0)
                if pd.isna(andamento):
                    andamento = 0
                andamento = round(float(andamento), 1)
                
                # Formata data brasileira sem horário
                data_prevista = self._formatar_data_brasileira(projeto.get('VencimentoEm'))
                
                # Nome do cliente com múltiplas tentativas de extração
                nome_cliente = projeto.get('nome_cliente_enriquecido', projeto.get('Cliente', 'N/A'))
                nome_projeto = projeto.get('Projeto', 'N/A')
                
                # Se não conseguiu obter do histórico ou coluna Cliente, tenta extrair do nome do projeto
                if nome_cliente == 'N/A' and nome_projeto and nome_projeto != 'N/A':
                    # TENTATIVA ESPECIAL: Projetos internos da SOU.cloud
                    # Mais específico para evitar falsos positivos como PBSF que contém "SOU PLUS"
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
                        logger.debug(f"Projeto interno detectado: {nome_projeto} -> Cliente: SOU.cloud")
                    # Tentativa 1: separador " - "
                    elif ' - ' in nome_projeto:
                        partes = nome_projeto.split(' - ', 1)
                        if len(partes) >= 2:
                            nome_cliente = partes[0].strip()
                            nome_projeto = partes[1].strip()
                    # Tentativa 2: separador " | "
                    elif ' | ' in nome_projeto:
                        partes = nome_projeto.split(' | ', 1)
                        if len(partes) >= 2:
                            nome_cliente = partes[0].strip()
                            nome_projeto = partes[1].strip()
                    # Tentativa 3: separador ": "
                    elif ': ' in nome_projeto:
                        partes = nome_projeto.split(': ', 1)
                        if len(partes) >= 2:
                            nome_cliente = partes[0].strip()
                            nome_projeto = partes[1].strip()
                    # Se chegou até aqui, tenta extrair as duas primeiras palavras se houver espaços
                    elif ' ' in nome_projeto:
                        palavras = nome_projeto.split()
                        if len(palavras) >= 2:
                            nome_cliente = ' '.join(palavras[:2])
                            logger.debug(f"Cliente extraído das primeiras palavras: {nome_cliente}")
                
                # Aplica truncamento para nomes muito longos (exceto SOU.cloud)
                if nome_cliente != 'N/A' and nome_cliente != 'SOU.cloud':
                    nome_cliente = self._truncar_nome_cliente(nome_cliente)
                
                projeto_info = {
                    'numero': projeto.get('Numero', ''),
                    'nome_cliente': nome_cliente,
                    'nome_projeto': nome_projeto,
                    'data_prevista': data_prevista,
                    'squad': projeto.get('Squad', 'N/A'),
                    'andamento': andamento,
                    'horas_estimadas': round(projeto.get('Horas', 0), 1),
                    'horas_trabalhadas_mes': round(projeto.get('horas_trabalhadas_mes', 0), 1),
                    'posicao': len(projetos_principais) + 1,  # Posição no ranking
                    'status': projeto.get('Status', 'N/A')
                }
                projetos_principais.append(projeto_info)
            
            logger.info(f"✅ CARD: Top {len(projetos_principais)} projetos principais calculados: {[p['nome_projeto'] for p in projetos_principais]}")
            logger.info(f"📊 CARD: Critério usado: {criterio_usado}")
            logger.info(f"📊 CARD: Total projetos retornados: {len(projetos_principais)}")
            
            resultado = {
                'projetos': projetos_principais,
                'total_encontrados': len(projetos_filtrados),
                'criterios': criterio_usado
            }
            
            logger.info(f"🎯 CARD: Retornando resultado final com {len(resultado['projetos'])} projetos")
            return resultado
            
        except Exception as e:
            logger.error(f"Erro ao calcular projetos principais do mês: {str(e)}", exc_info=True)
            return {'projetos': [], 'total_encontrados': 0}

    def _calcular_horas_trabalhadas_no_mes(self, dados, mes_referencia):
        """
        Calcula as horas trabalhadas especificamente no mês analisado.
        Fórmula: Horas_Atual - Horas_Ultimo_Mes_Encontrado
        
        Busca o projeto nos últimos 6 meses para encontrar a base de comparação mais recente.
        """
        try:
            if mes_referencia is None:
                logger.warning("Mês de referência não fornecido para cálculo de horas do mês")
                dados['horas_trabalhadas_mes'] = dados.get('HorasTrabalhadas', 0)
                return dados
            
            logger.info(f"Calculando horas trabalhadas especificamente no mês: {mes_referencia.strftime('%B/%Y')}")
            
            # Prepara resultado
            dados_resultado = dados.copy()
            dados_resultado['horas_trabalhadas_mes'] = 0.0
            
            # Para cada projeto, busca nos últimos 6 meses para encontrar a base de comparação
            for index, projeto_atual in dados.iterrows():
                numero_projeto = projeto_atual.get('Numero')
                horas_atuais = float(projeto_atual.get('HorasTrabalhadas', 0) or 0)
                
                if pd.isna(numero_projeto):
                    # Sem número do projeto, não consegue comparar
                    dados_resultado.at[index, 'horas_trabalhadas_mes'] = horas_atuais
                    continue
                
                # Busca o projeto nos últimos 6 meses
                horas_base_encontrada = None
                mes_base_encontrado = None
                
                for i in range(1, 7):  # Busca nos últimos 6 meses
                    try:
                        # Calcula mês a verificar
                        if mes_referencia.month - i <= 0:
                            mes_busca = mes_referencia.replace(
                                year=mes_referencia.year - 1, 
                                month=12 + (mes_referencia.month - i)
                            )
                        else:
                            mes_busca = mes_referencia.replace(month=mes_referencia.month - i)
                        
                        # Tenta carregar dados desse mês
                        fonte_busca = self._obter_fonte_historica(mes_busca.year, mes_busca.month)
                        if not fonte_busca:
                            continue
                            
                        dados_busca = self.carregar_dados(fonte=fonte_busca)
                        if dados_busca.empty:
                            continue
                            
                        # Procura o projeto neste mês
                        projeto_encontrado = dados_busca[dados_busca['Numero'] == numero_projeto]
                        if not projeto_encontrado.empty:
                            horas_base_encontrada = float(projeto_encontrado.iloc[0].get('HorasTrabalhadas', 0) or 0)
                            mes_base_encontrado = mes_busca.strftime('%B/%Y')
                            logger.debug(f"Projeto {numero_projeto}: encontrado base em {mes_base_encontrado} com {horas_base_encontrada}h")
                            break
                            
                    except Exception as e:
                        logger.debug(f"Erro ao buscar projeto {numero_projeto} em mês anterior: {str(e)}")
                        continue
                
                # Calcula horas trabalhadas no mês específico
                if horas_base_encontrada is not None:
                    horas_do_mes = max(0, horas_atuais - horas_base_encontrada)
                    dados_resultado.at[index, 'horas_trabalhadas_mes'] = horas_do_mes
                    logger.debug(f"Projeto {numero_projeto}: {horas_atuais}h atual - {horas_base_encontrada}h base ({mes_base_encontrado}) = {horas_do_mes}h no mês")
                else:
                    # Projeto não encontrado em nenhum mês anterior - pode ser novo
                    # Para ser conservador, considera apenas 10% das horas como do mês atual
                    horas_conservadoras = horas_atuais * 0.1
                    dados_resultado.at[index, 'horas_trabalhadas_mes'] = horas_conservadoras
                    logger.debug(f"Projeto {numero_projeto}: Não encontrado em meses anteriores, usando {horas_conservadoras}h conservadoras (10% de {horas_atuais}h)")
            
            total_horas_mes = dados_resultado['horas_trabalhadas_mes'].sum()
            logger.info(f"Total de horas trabalhadas especificamente no mês: {total_horas_mes:.1f}h")
            
            return dados_resultado
            
        except Exception as e:
            logger.error(f"Erro ao calcular horas trabalhadas no mês: {str(e)}", exc_info=True)
            dados['horas_trabalhadas_mes'] = dados.get('HorasTrabalhadas', 0)
            return dados

    def _enriquecer_projetos_com_historico(self, projetos, mes_referencia):
        """
        Tenta enriquecer os projetos com informações de arquivos históricos
        para capturar nome do cliente e outras informações complementares.
        """
        try:
            # Lista de meses para buscar informações históricas (últimos 6 meses)
            meses_busca = []
            mes_atual = mes_referencia
            
            for i in range(6):  # Busca nos últimos 6 meses
                if mes_atual.month == 1:
                    mes_anterior = mes_atual.replace(year=mes_atual.year - 1, month=12)
                else:
                    mes_anterior = mes_atual.replace(month=mes_atual.month - 1)
                
                fonte = self._obter_fonte_historica(mes_anterior.year, mes_anterior.month)
                if fonte:
                    meses_busca.append((mes_anterior, fonte))
                mes_atual = mes_anterior
            
            projetos_enriquecido = projetos.copy()
            projetos_enriquecido['nome_cliente_enriquecido'] = 'N/A'
            
            # Para cada projeto, busca informações históricas
            for index, projeto in projetos.iterrows():
                numero_projeto = projeto.get('Numero')
                
                for mes_hist, fonte_hist in meses_busca:
                    try:
                        dados_hist = self.carregar_dados(fonte=fonte_hist)
                        
                        if not dados_hist.empty and numero_projeto in dados_hist['Numero'].values:
                            projeto_hist = dados_hist[dados_hist['Numero'] == numero_projeto].iloc[0]
                            
                            # Tenta extrair nome do cliente do histórico
                            nome_projeto_hist = projeto_hist.get('Projeto', '')
                            nome_cliente_encontrado = None
                            
                            # Primeira tentativa: projetos internos SOU.cloud
                            # Mais específico para evitar falsos positivos
                            if nome_projeto_hist:
                                projeto_hist_upper = nome_projeto_hist.upper()
                                is_sou_internal_hist = (
                                    'COPILOT' in projeto_hist_upper or
                                    'SHAREPOINT' in projeto_hist_upper or 
                                    'REESTRUTURA' in projeto_hist_upper or
                                    'INTERNO' in projeto_hist_upper or
                                    'INTERNAL' in projeto_hist_upper or
                                    (projeto_hist_upper.startswith('SOU ') or projeto_hist_upper.endswith(' SOU') or projeto_hist_upper == 'SOU') or
                                    ('PMO' in projeto_hist_upper and 'SOU' in projeto_hist_upper) or
                                    ('CONTROL' in projeto_hist_upper and 'SOU' in projeto_hist_upper)
                                )
                                
                                if is_sou_internal_hist:
                                    nome_cliente_encontrado = 'SOU.cloud'
                                    logger.debug(f"Projeto interno SOU.cloud encontrado no histórico: {nome_projeto_hist}")
                            # Segunda tentativa: separador " - "
                            elif nome_projeto_hist and ' - ' in nome_projeto_hist:
                                partes = nome_projeto_hist.split(' - ', 1)
                                if len(partes) >= 2:
                                    nome_cliente_encontrado = partes[0].strip()
                            # Terceira tentativa: coluna Cliente diretamente
                            elif projeto_hist.get('Cliente'):
                                nome_cliente_encontrado = projeto_hist.get('Cliente').strip()
                            
                            if nome_cliente_encontrado:
                                projetos_enriquecido.at[index, 'nome_cliente_enriquecido'] = nome_cliente_encontrado
                                logger.debug(f"Cliente encontrado para projeto {numero_projeto}: {nome_cliente_encontrado}")
                                break  # Para de buscar se encontrou
                                    
                    except Exception as e:
                        logger.debug(f"Erro ao buscar dados históricos em {fonte_hist}: {str(e)}")
                        continue
            
            return projetos_enriquecido
            
        except Exception as e:
            logger.error(f"Erro ao enriquecer projetos com histórico: {str(e)}", exc_info=True)
            projetos['nome_cliente_enriquecido'] = 'N/A'
            return projetos

    def _truncar_nome_cliente(self, nome_cliente):
        """
        Trunca nomes de clientes muito longos para as duas primeiras palavras
        """
        try:
            if not nome_cliente or nome_cliente == 'N/A':
                return nome_cliente
            
            palavras = nome_cliente.strip().split()
            if len(palavras) <= 2:
                return nome_cliente
            
            # Retorna apenas as duas primeiras palavras
            nome_truncado = ' '.join(palavras[:2])
            logger.debug(f"Nome do cliente truncado: '{nome_cliente}' -> '{nome_truncado}'")
            return nome_truncado
            
        except Exception as e:
            logger.debug(f"Erro ao truncar nome do cliente: {str(e)}")
            return nome_cliente

    def carregar_projetos_principais_selecionados(self, mes_referencia):
        """
        Carrega a lista de projetos principais selecionados manualmente para um mês
        """
        try:
            import json
            import os
            
            # Arquivo de configuração baseado no mês
            config_dir = os.path.join('instance', 'config')
            os.makedirs(config_dir, exist_ok=True)
            
            mes_str = mes_referencia.strftime('%Y-%m')
            config_file = os.path.join(config_dir, f'projetos_principais_{mes_str}.json')
            
            logger.info(f"🔍 CARREGAR: Procurando configuração em: {config_file}")
            logger.info(f"🔍 CARREGAR: Caminho absoluto: {os.path.abspath(config_file)}")
            logger.info(f"🔍 CARREGAR: Arquivo existe: {os.path.exists(config_file)}")
            
            if os.path.exists(config_file):
                try:
                    logger.info(f"📖 CARREGAR: Abrindo arquivo para leitura...")
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config_content = f.read()
                        logger.info(f"📖 CARREGAR: Conteúdo bruto lido: {config_content[:200]}...")
                        
                        config = json.loads(config_content)
                        logger.info(f"📖 CARREGAR: JSON parseado: {config}")
                        
                        projetos_selecionados = config.get('projetos_selecionados', [])
                        logger.info(f"✅ CARREGAR: {len(projetos_selecionados)} projetos extraídos para {mes_str}: {projetos_selecionados}")
                        return projetos_selecionados
                        
                except json.JSONDecodeError as e:
                    logger.error(f"❌ CARREGAR: Erro JSON decode: {str(e)}")
                    return []
                except Exception as e:
                    logger.error(f"❌ CARREGAR: Erro ao ler arquivo: {str(e)}")
                    return []
            else:
                logger.info(f"📁 Nenhuma configuração de projetos principais encontrada para {mes_str} em {config_file}")
                
                # Listar arquivos disponíveis para debug
                try:
                    arquivos_disponiveis = os.listdir(config_dir)
                    logger.info(f"📋 Arquivos de configuração disponíveis: {arquivos_disponiveis}")
                except Exception as list_error:
                    logger.warning(f"Erro ao listar arquivos de configuração: {str(list_error)}")
                
                return []
                
        except Exception as e:
            logger.error(f"❌ Erro ao carregar projetos principais selecionados: {str(e)}", exc_info=True)
            return []

    def salvar_projetos_principais_selecionados(self, projetos_selecionados, mes_referencia):
        """
        Salva a lista de projetos principais selecionados manualmente para um mês
        """
        try:
            import json
            import os
            from datetime import datetime
            
            # Arquivo de configuração baseado no mês
            config_dir = os.path.join('instance', 'config')
            os.makedirs(config_dir, exist_ok=True)
            
            mes_str = mes_referencia.strftime('%Y-%m')
            config_file = os.path.join(config_dir, f'projetos_principais_{mes_str}.json')
            
            logger.info(f"💾 Salvando {len(projetos_selecionados)} projetos para {mes_str}: {projetos_selecionados}")
            logger.info(f"📁 Arquivo de destino: {config_file}")
            
            config_data = {
                'mes_referencia': mes_str,
                'projetos_selecionados': projetos_selecionados,
                'data_configuracao': datetime.now().isoformat(),
                'total_selecionados': len(projetos_selecionados)
            }
            
            # Verificar se diretório existe
            if not os.path.exists(config_dir):
                logger.info(f"📁 Criando diretório: {config_dir}")
                os.makedirs(config_dir, exist_ok=True)
            
            # Salvar arquivo
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            # Verificar se arquivo foi criado
            if os.path.exists(config_file):
                file_size = os.path.getsize(config_file)
                logger.info(f"✅ Arquivo salvo com sucesso: {config_file} ({file_size} bytes)")
                
                # Verificar conteúdo
                with open(config_file, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                    logger.info(f"🔍 Conteúdo salvo: {saved_data}")
                
                return True
            else:
                logger.error(f"❌ Arquivo não foi criado: {config_file}")
                return False
            
        except PermissionError as e:
            logger.error(f"❌ PERMISSÃO: Erro de permissão ao salvar arquivo: {str(e)}")
            logger.error(f"❌ PERMISSÃO: Verifique se o processo tem permissão para escrever em: {config_dir}")
            return False
        except IOError as e:
            logger.error(f"❌ IO: Erro de I/O ao salvar arquivo: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ GERAL: Erro ao salvar projetos principais selecionados: {str(e)}", exc_info=True)
            return False

    def _formatar_data_brasileira(self, data):
        """
        Formata data para o padrão brasileiro DD/MM/YYYY
        """
        try:
            if pd.isna(data) or not data:
                return 'N/A'
            
            # Se já é string, tenta converter
            if isinstance(data, str):
                # Remove horário se presente
                data_clean = data.split(' ')[0]
                
                # Tenta diferentes formatos
                formatos = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d']
                
                for formato in formatos:
                    try:
                        data_obj = datetime.strptime(data_clean, formato)
                        return data_obj.strftime('%d/%m/%Y')
                    except ValueError:
                        continue
                        
                return data_clean  # Retorna original se não conseguir converter
                
            # Se é datetime
            elif hasattr(data, 'strftime'):
                return data.strftime('%d/%m/%Y')
                
            return str(data)
            
        except Exception as e:
            logger.debug(f"Erro ao formatar data {data}: {str(e)}")
            return 'N/A'

    def calcular_projetos_previstos_encerramento(self, dados, mes_referencia=None):
        """
        Projetos com vencimento no próximo mês - VERSÃO CORRIGIDA
        """
        logger.info(f"✅ Calculando projetos previstos para encerramento")
        
        try:
            # Define mês seguinte
            if mes_referencia is None:
                mes_referencia = datetime.now().replace(day=1)
            
            mes_seguinte = mes_referencia.replace(month=mes_referencia.month + 1) if mes_referencia.month < 12 else mes_referencia.replace(year=mes_referencia.year + 1, month=1)
            
            # Mapear mês para português
            meses_pt = {
                1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
                7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
            }
            
            mes_nome = meses_pt.get(mes_seguinte.month, str(mes_seguinte.month))
            mes_previsto = f"{mes_nome}/{mes_seguinte.year}"
            
            logger.info(f"✅ Buscando projetos para: {mes_previsto}")
            
            # Prepara dados
            dados_work = dados.copy()
            
            # Converte datas
            dados_work['VencimentoEm_dt'] = pd.to_datetime(dados_work['VencimentoEm'], format='%d/%m/%Y %H:%M', errors='coerce')
            
            # Filtra projetos do mês seguinte
            inicio = datetime(mes_seguinte.year, mes_seguinte.month, 1)
            if mes_seguinte.month == 12:
                fim = datetime(mes_seguinte.year + 1, 1, 1) - pd.Timedelta(days=1)
            else:
                fim = datetime(mes_seguinte.year, mes_seguinte.month + 1, 1) - pd.Timedelta(days=1)
            
            projetos_mes = dados_work[
                (dados_work['VencimentoEm_dt'] >= inicio) &
                (dados_work['VencimentoEm_dt'] <= fim) &
                (dados_work['Status'] != 'CANCELADO')  # Exclui apenas cancelados
            ].copy()
            
            logger.info(f"✅ Encontrados {len(projetos_mes)} projetos para {mes_previsto}")
            
            # Processa projetos
            projetos_lista = []
            for idx, projeto in projetos_mes.iterrows():
                nome_completo = projeto.get('Cliente (Completo)', 'N/A')
                squad = projeto.get('Serviço (2º Nível)', 'N/A')
                
                # Extrai nome do cliente (mais inteligente)
                if ' - ' in nome_completo:
                    cliente = nome_completo.split(' - ')[0].strip()
                elif len(nome_completo) > 25:
                    cliente = nome_completo[:22] + '...'
                else:
                    cliente = nome_completo
                
                projetos_lista.append({
                    'cliente': cliente,
                    'projeto': nome_completo,
                    'squad': squad
                })
            
            # Ordena por cliente
            projetos_lista.sort(key=lambda x: x['cliente'])
            
            resultado = {
                'projetos': projetos_lista,
                'mes_previsto': mes_previsto,
                'total_encontrados': len(projetos_lista),
                'periodo_analise': f"01/{mes_seguinte.month:02d} a {fim.day:02d}/{mes_seguinte.month:02d}/{mes_seguinte.year}"
            }
            
            logger.info(f"✅ Retornando {len(projetos_lista)} projetos para {mes_previsto}")
            return resultado
            
        except Exception as e:
            logger.error(f"❌ Erro ao calcular projetos previstos: {str(e)}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return {
                'projetos': [],
                'mes_previsto': 'Julho/2025',
                'total_encontrados': 0,
                'periodo_analise': '01/07 a 31/07/2025'
            }

    def analisar_mapeamento_tipos_servico(self, dados):
        """
        Analisa o mapeamento entre tipos de serviço nos projetos vs CSV.
        Funcionalidade "DexPra" para identificar não mapeados.
        
        Args:
            dados (pd.DataFrame): DataFrame com os projetos
            
        Returns:
            dict: Análise completa do mapeamento
        """
        try:
            from .typeservice_reader import type_service_reader
            
            logger.info("🔄 Analisando mapeamento DexPra...")
            
            # Carrega mapeamento do CSV
            mapeamento_csv = type_service_reader.carregar_tipos_servico()
            if not mapeamento_csv:
                return {'erro': 'Erro ao carregar arquivo CSV', 'status': 'erro'}
            
            # Verifica coluna TipoServico nos dados
            if 'TipoServico' not in dados.columns:
                return {'erro': 'Coluna TipoServico não encontrada', 'status': 'erro'}
            
            # Prepara dados
            dados_limpos = dados[dados['TipoServico'].notna() & (dados['TipoServico'] != '')].copy()
            if dados_limpos.empty:
                return {'erro': 'Nenhum projeto com tipo de serviço válido', 'status': 'erro'}
            
            # Função auxiliar para normalizar strings
            def normalizar_string(s):
                """Normaliza string removendo espaços extras, acentos e padronizando case"""
                if pd.isna(s) or s == '':
                    return ''
                import unicodedata
                # Remove acentos
                s = unicodedata.normalize('NFD', str(s)).encode('ascii', 'ignore').decode('ascii')
                # Remove espaços extras e converte para lowercase
                return ' '.join(str(s).strip().lower().split())
            
            # Analisa tipos nos projetos
            tipos_projetos = dados_limpos['TipoServico'].value_counts().to_dict()
            
            # DEBUG: Log dos tipos encontrados nos projetos
            logger.info(f"🔍 Tipos encontrados nos projetos ({len(tipos_projetos)}):")
            for tipo, qtd in list(tipos_projetos.items())[:5]:
                logger.info(f"  - '{tipo}' ({qtd} projetos)")
            
            # Função auxiliar para normalizar strings
            def normalizar_string(s):
                """Normaliza string removendo espaços extras, acentos e padronizando case"""
                if pd.isna(s) or s == '':
                    return ''
                import unicodedata
                # Remove acentos
                s = unicodedata.normalize('NFD', str(s)).encode('ascii', 'ignore').decode('ascii')
                # Remove espaços extras e converte para lowercase
                return ' '.join(str(s).strip().lower().split())
            
            # DEBUG: Log dos tipos do CSV
            logger.info(f"🔍 Tipos encontrados no CSV ({len(mapeamento_csv)}):")
            for tipo, categoria in list(mapeamento_csv.items())[:5]:
                logger.info(f"  - '{tipo}' -> '{categoria}'")
            
            # Cria mapeamento normalizado para comparação
            csv_normalizado = {}
            for tipo_original, categoria in mapeamento_csv.items():
                tipo_norm = normalizar_string(tipo_original)
                if tipo_norm:  # Só adiciona se não estiver vazio após normalização
                    csv_normalizado[tipo_norm] = {
                        'original': tipo_original,
                        'categoria': categoria
                    }
            
            # DEBUG: Log dos tipos normalizados do CSV
            logger.info(f"🔍 Tipos normalizados do CSV ({len(csv_normalizado)}):")
            for tipo_norm, info in list(csv_normalizado.items())[:5]:
                logger.info(f"  - '{tipo_norm}' -> '{info['categoria']}'")
            
            # Cria sets para análise (usando versões normalizadas)
            tipos_projetos_norm = {normalizar_string(tipo): tipo for tipo in tipos_projetos.keys()}
            tipos_csv_norm = set(csv_normalizado.keys())
            tipos_reais_norm = set(tipos_projetos_norm.keys())
            
            # Remove strings vazias
            tipos_csv_norm.discard('')
            tipos_reais_norm.discard('')
            
            # DEBUG: Verifica tipos específicos problemáticos
            tipos_problema = ['Migração de tenant CSP para EA', 'Assessment for Rapid Migration']
            for tipo in tipos_problema:
                tipo_norm = normalizar_string(tipo)
                logger.info(f"🔍 Verificando '{tipo}':")
                logger.info(f"  - Normalizado: '{tipo_norm}'")
                logger.info(f"  - No CSV normalizado: {tipo_norm in csv_normalizado}")
                logger.info(f"  - Nos projetos: {tipo in tipos_projetos}")
                
                # Procura por versões similares nos projetos
                tipos_similares = [t for t in tipos_projetos.keys() if tipo.lower() in t.lower() or t.lower() in tipo.lower()]
                if tipos_similares:
                    logger.info(f"  - Tipos similares nos projetos: {tipos_similares}")
            
            # Identifica mapeamentos usando versões normalizadas
            tipos_mapeados_norm = tipos_reais_norm.intersection(tipos_csv_norm)
            tipos_nao_mapeados_norm = tipos_reais_norm - tipos_csv_norm
            tipos_csv_nao_usados_norm = tipos_csv_norm - tipos_reais_norm
            
            # Constrói listas detalhadas usando tipos originais
            nao_mapeados = []
            for tipo_norm in tipos_nao_mapeados_norm:
                tipo_original = tipos_projetos_norm[tipo_norm]
                qtd_projetos = tipos_projetos.get(tipo_original, 0)
                categoria_atual = type_service_reader.obter_categoria(tipo_original)  # Retorna "Outros"
                
                # Sugere ação baseada no nome do tipo
                acao_sugerida = self._sugerir_acao_tipo(tipo_original)
                
                nao_mapeados.append({
                    'tipo': tipo_original,
                    'qtd_projetos': qtd_projetos,
                    'categoria_atual': categoria_atual,
                    'acao_sugerida': acao_sugerida
                })
            
            # Ordena por quantidade de projetos (mais críticos primeiro)
            nao_mapeados.sort(key=lambda x: x['qtd_projetos'], reverse=True)
            
            mapeados = []
            for tipo_norm in tipos_mapeados_norm:
                tipo_original = tipos_projetos_norm[tipo_norm]
                qtd_projetos = tipos_projetos.get(tipo_original, 0)
                categoria = csv_normalizado[tipo_norm]['categoria']
                
                mapeados.append({
                    'tipo': tipo_original,
                    'qtd_projetos': qtd_projetos,
                    'categoria': categoria
                })
            
            mapeados.sort(key=lambda x: x['qtd_projetos'], reverse=True)
            
            csv_nao_usados = []
            for tipo_norm in tipos_csv_nao_usados_norm:
                info_csv = csv_normalizado[tipo_norm]
                tipo_original = info_csv['original']
                categoria = info_csv['categoria']
                
                csv_nao_usados.append({
                    'tipo': tipo_original,
                    'categoria': categoria,
                    'status': 'Não utilizado nos projetos atuais'
                })
            
            csv_nao_usados.sort(key=lambda x: x['tipo'])
            
            # Log para debug
            logger.info(f"📊 Análise normalizada:")
            logger.info(f"  - Tipos nos projetos: {len(tipos_reais_norm)}")
            logger.info(f"  - Tipos no CSV: {len(tipos_csv_norm)}")
            logger.info(f"  - Mapeados: {len(tipos_mapeados_norm)}")
            logger.info(f"  - Não mapeados: {len(tipos_nao_mapeados_norm)}")
            logger.info(f"  - CSV não usados: {len(tipos_csv_nao_usados_norm)}")
            
            # Monta resultado
            resultado = {
                'nao_mapeados': nao_mapeados,
                'mapeados': mapeados,
                'csv_nao_usados': csv_nao_usados,
                'resumo': {
                    'total_tipos_projetos': len(tipos_reais_norm),
                    'total_tipos_csv': len(tipos_csv_norm),
                    'total_nao_mapeados': len(tipos_nao_mapeados_norm),
                    'total_mapeados': len(tipos_mapeados_norm),
                    'total_csv_nao_usados': len(tipos_csv_nao_usados_norm),
                    'percentual_mapeado': round((len(tipos_mapeados_norm) / len(tipos_reais_norm)) * 100, 1) if tipos_reais_norm else 0
                },
                'status': 'sucesso'
            }
            
            logger.info(f"✅ Mapeamento analisado: {len(tipos_nao_mapeados_norm)} não mapeados, {len(tipos_mapeados_norm)} mapeados")
            return resultado
            
        except Exception as e:
            logger.error(f"❌ Erro ao analisar mapeamento: {str(e)}", exc_info=True)
            return {
                'erro': str(e),
                'status': 'erro'
            }

    def aplicar_filtros_relatorio(self, dados, filtros):
        """
        Aplica filtros avançados nos dados do relatório geral.
        
        Args:
            dados (DataFrame): Dados a serem filtrados
            filtros (dict): Dicionário com os filtros a aplicar
            
        Returns:
            DataFrame: Dados filtrados
        """
        try:
            logger.info(f"Aplicando filtros ao relatório: {filtros}")
            dados_filtrados = dados.copy()
            
            # Filtro por Categoria
            if 'categoria' in filtros and filtros['categoria']:
                try:
                    from .typeservice_reader import TypeServiceReader
                    reader = TypeServiceReader()
                    
                    # Obtém todos os tipos de serviço da categoria selecionada
                    tipos_por_categoria = reader.obter_tipos_por_categoria()
                    tipos_da_categoria = tipos_por_categoria.get(filtros['categoria'], [])
                    
                    if tipos_da_categoria and 'TipoServico' in dados_filtrados.columns:
                        # Filtra projetos que têm tipos de serviço pertencentes à categoria
                        dados_filtrados = dados_filtrados[dados_filtrados['TipoServico'].isin(tipos_da_categoria)]
                        logger.info(f"Filtro Categoria aplicado: {filtros['categoria']} ({len(tipos_da_categoria)} tipos) - Registros restantes: {len(dados_filtrados)}")
                    else:
                        logger.warning(f"Categoria '{filtros['categoria']}' não possui tipos de serviço ou coluna TipoServico não encontrada")
                except Exception as e:
                    logger.error(f"Erro ao aplicar filtro de categoria: {str(e)}")
            
            # Filtro por Squad
            if 'squad' in filtros and filtros['squad']:
                dados_filtrados = dados_filtrados[dados_filtrados['Squad'].str.upper() == filtros['squad'].upper()]
                logger.info(f"Filtro Squad aplicado: {filtros['squad']} - Registros restantes: {len(dados_filtrados)}")
            
            # Filtro por Serviço
            if 'servico' in filtros and filtros['servico']:
                if 'TipoServico' in dados_filtrados.columns:
                    dados_filtrados = dados_filtrados[dados_filtrados['TipoServico'].str.upper() == filtros['servico'].upper()]
                    logger.info(f"Filtro Serviço aplicado: {filtros['servico']} - Registros restantes: {len(dados_filtrados)}")
            
            # Filtro por Status
            if 'status' in filtros and filtros['status']:
                dados_filtrados = dados_filtrados[dados_filtrados['Status'].str.upper() == filtros['status'].upper()]
                logger.info(f"Filtro Status aplicado: {filtros['status']} - Registros restantes: {len(dados_filtrados)}")
            
            # Filtro por Faturamento
            if 'faturamento' in filtros and filtros['faturamento']:
                if 'Faturamento' in dados_filtrados.columns:
                    dados_filtrados = dados_filtrados[dados_filtrados['Faturamento'].str.upper() == filtros['faturamento'].upper()]
                    logger.info(f"Filtro Faturamento aplicado: {filtros['faturamento']} - Registros restantes: {len(dados_filtrados)}")
            
            # Filtros por Data de Abertura
            if 'data_abertura_inicio' in filtros and filtros['data_abertura_inicio']:
                try:
                    data_inicio = pd.to_datetime(filtros['data_abertura_inicio'])
                    if 'DataInicio' in dados_filtrados.columns:
                        dados_filtrados = dados_filtrados[pd.to_datetime(dados_filtrados['DataInicio']) >= data_inicio]
                        logger.info(f"Filtro Data Abertura Início aplicado: {filtros['data_abertura_inicio']} - Registros restantes: {len(dados_filtrados)}")
                except Exception as e:
                    logger.warning(f"Erro ao aplicar filtro de data de abertura início: {e}")
            
            if 'data_abertura_fim' in filtros and filtros['data_abertura_fim']:
                try:
                    data_fim = pd.to_datetime(filtros['data_abertura_fim'])
                    if 'DataInicio' in dados_filtrados.columns:
                        dados_filtrados = dados_filtrados[pd.to_datetime(dados_filtrados['DataInicio']) <= data_fim]
                        logger.info(f"Filtro Data Abertura Fim aplicado: {filtros['data_abertura_fim']} - Registros restantes: {len(dados_filtrados)}")
                except Exception as e:
                    logger.warning(f"Erro ao aplicar filtro de data de abertura fim: {e}")
            
            # Filtros por Data de Fechamento
            if 'data_fechamento_inicio' in filtros and filtros['data_fechamento_inicio']:
                try:
                    data_inicio = pd.to_datetime(filtros['data_fechamento_inicio'])
                    if 'DataTermino' in dados_filtrados.columns:
                        # Filtra apenas projetos que foram fechados no período
                        dados_fechados = dados_filtrados[dados_filtrados['Status'].str.upper().isin(['FECHADO', 'ENCERRADO', 'RESOLVIDO'])]
                        dados_fechados = dados_fechados[pd.to_datetime(dados_fechados['DataTermino']) >= data_inicio]
                        # Mantém também projetos que não foram fechados (DataTermino nula)
                        dados_nao_fechados = dados_filtrados[~dados_filtrados['Status'].str.upper().isin(['FECHADO', 'ENCERRADO', 'RESOLVIDO'])]
                        dados_filtrados = pd.concat([dados_fechados, dados_nao_fechados], ignore_index=True)
                        logger.info(f"Filtro Data Fechamento Início aplicado: {filtros['data_fechamento_inicio']} - Registros restantes: {len(dados_filtrados)}")
                except Exception as e:
                    logger.warning(f"Erro ao aplicar filtro de data de fechamento início: {e}")
            
            if 'data_fechamento_fim' in filtros and filtros['data_fechamento_fim']:
                try:
                    data_fim = pd.to_datetime(filtros['data_fechamento_fim'])
                    if 'DataTermino' in dados_filtrados.columns:
                        # Filtra apenas projetos que foram fechados no período
                        dados_fechados = dados_filtrados[dados_filtrados['Status'].str.upper().isin(['FECHADO', 'ENCERRADO', 'RESOLVIDO'])]
                        dados_fechados = dados_fechados[pd.to_datetime(dados_fechados['DataTermino']) <= data_fim]
                        # Mantém também projetos que não foram fechados (DataTermino nula)
                        dados_nao_fechados = dados_filtrados[~dados_filtrados['Status'].str.upper().isin(['FECHADO', 'ENCERRADO', 'RESOLVIDO'])]
                        dados_filtrados = pd.concat([dados_fechados, dados_nao_fechados], ignore_index=True)
                        logger.info(f"Filtro Data Fechamento Fim aplicado: {filtros['data_fechamento_fim']} - Registros restantes: {len(dados_filtrados)}")
                except Exception as e:
                    logger.warning(f"Erro ao aplicar filtro de data de fechamento fim: {e}")
            
            logger.info(f"Filtros aplicados com sucesso. Registros finais: {len(dados_filtrados)}")
            return dados_filtrados
            
        except Exception as e:
            logger.error(f"Erro ao aplicar filtros: {e}")
            return dados  # Retorna dados originais em caso de erro

    def _traduzir_categoria(self, categoria):
        """
        Traduz categorias do inglês para português.
        """
        traducoes = {
            'decision': 'Decisão',
            'impediment': 'Impedimento',
            'general': 'Geral',
            'risk': 'Risco',
            'meeting': 'Reunião',
            'update': 'Atualização'
        }
        return traducoes.get(categoria, categoria.title() if categoria else 'Geral')

    def _traduzir_prioridade(self, prioridade):
        """
        Traduz prioridades do inglês para português.
        """
        traducoes = {
            'high': 'Alta',
            'medium': 'Média',
            'low': 'Baixa',
            'urgent': 'Urgente',
            'normal': 'Normal'
        }
        return traducoes.get(prioridade.lower() if prioridade else '', prioridade.title() if prioridade else 'Normal')

    def _calcular_percentual_por_tarefas(self, project_id):
        """
        Calcula o percentual de conclusão baseado nas tarefas do backlog.
        Usado especificamente para projetos de "Demandas Internas".
        """
        try:
            logger.info(f"Calculando percentual por tarefas para projeto {project_id}")
            
            # Buscar backlog_id do projeto
            backlog_id = self.get_backlog_id_for_project(project_id)
            if not backlog_id:
                logger.warning(f"Nenhum backlog encontrado para projeto {project_id}")
                return 0.0
            
            # Buscar todas as tarefas do backlog
            from app.models import Task, Column
            
            total_tarefas = Task.query.filter_by(backlog_id=backlog_id).count()
            logger.info(f"Total de tarefas no backlog {backlog_id}: {total_tarefas}")
            
            if total_tarefas == 0:
                logger.info("Nenhuma tarefa encontrada - retornando 0%")
                return 0.0
            
            # Contar tarefas concluídas baseado no nome da coluna
            tarefas_concluidas = Task.query.filter_by(backlog_id=backlog_id)\
                .join(Column, Task.column_id == Column.id)\
                .filter(
                    Column.name.ilike('%concluí%') |
                    Column.name.ilike('%concluido%') |
                    Column.name.ilike('%done%') |
                    Column.name.ilike('%finalizado%') |
                    Column.name.ilike('%finalizada%')
                ).count()
            
            logger.info(f"Tarefas concluídas no backlog {backlog_id}: {tarefas_concluidas}")
            
            # Calcular percentual
            percentual = round((tarefas_concluidas / total_tarefas) * 100, 1)
            
            logger.info(f"Percentual calculado: {tarefas_concluidas}/{total_tarefas} = {percentual}%")
            
            return percentual
            
        except Exception as e:
            logger.error(f"Erro ao calcular percentual por tarefas para projeto {project_id}: {str(e)}")
            return 0.0

    def _calcular_esforco_por_tarefas(self, project_id):
        """
        Calcula o esforço total (horas planejadas) baseado nas tarefas do backlog.
        Usado especificamente para projetos de "Demandas Internas".
        """
        try:
            logger.info(f"Calculando esforço por tarefas para projeto {project_id}")
            
            # Buscar backlog_id do projeto
            backlog_id = self.get_backlog_id_for_project(project_id)
            if not backlog_id:
                logger.warning(f"Nenhum backlog encontrado para projeto {project_id}")
                return 0.0
            
            # Buscar todas as tarefas do backlog
            from app.models import Task
            
            all_tasks = Task.query.filter_by(backlog_id=backlog_id).all()
            
            if not all_tasks:
                logger.info(f"Nenhuma tarefa encontrada no backlog {backlog_id} - retornando 0h")
                return 0.0
            
            # Somar esforço estimado de todas as tarefas
            total_esforco = 0.0
            tarefas_com_esforco = 0
            
            for task in all_tasks:
                esforco_tarefa = float(task.estimated_effort or 0)
                total_esforco += esforco_tarefa
                if esforco_tarefa > 0:
                    tarefas_com_esforco += 1
                logger.debug(f"Tarefa '{task.title}' - Esforço: {esforco_tarefa}h")
            
            logger.info(f"Esforço total calculado: {total_esforco}h ({tarefas_com_esforco}/{len(all_tasks)} tarefas com esforço)")
            
            return total_esforco
            
        except Exception as e:
            logger.error(f"Erro ao calcular esforço por tarefas para projeto {project_id}: {str(e)}")
            return 0.0


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
