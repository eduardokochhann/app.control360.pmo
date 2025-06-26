import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from .constants import *

logger = logging.getLogger(__name__)

class BaseService:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._setup_paths()
        
    def _setup_paths(self):
        """Configura os caminhos base do projeto"""
        base_dir = Path(__file__).resolve().parent.parent.parent
        self.data_dir = base_dir / 'data'
        self.csv_path = self.data_dir / 'dadosr.csv'
        self.logger.info(f"Caminho do CSV definido para: {self.csv_path}")

    def _robust_read_csv(self, path, date_parser_columns=None):
        """Lê um CSV de forma robusta, tentando encodings e parseando datas na leitura."""
        encodings = ['cp1252', 'latin1', 'utf-8']
        
        # Parser customizado para ser resiliente ao formato que padronizamos (sem segundos)
        date_parser = lambda x: pd.to_datetime(x, format='%d/%m/%Y %H:%M', errors='coerce')
        
        for encoding in encodings:
            try:
                df = pd.read_csv(
                    path, 
                    sep=';', 
                    encoding=encoding, 
                    low_memory=False,
                    parse_dates=date_parser_columns,
                    date_parser=date_parser
                )
                self.logger.info(f"CSV lido com sucesso usando encoding {encoding}.")
                return df
            except (UnicodeDecodeError, ValueError) as e:
                self.logger.warning(f"Falha ao ler CSV com encoding {encoding}: {e}")
                continue
        self.logger.error(f"Falha ao ler o CSV {path} com todos os encodings tentados.")
        return pd.DataFrame()

    def _convert_data_types(self, df):
        """Converte os tipos de dados das colunas para otimização."""
        numeric_cols = ['Horas', 'HorasTrabalhadas', 'Conclusao']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        string_cols = ['Numero', 'Status', 'Projeto', 'TipoServico', 'Especialista', 'Account Manager', 'Squad']
        for col in string_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).fillna('N/A')
                
        return df

    def _load_data(self):
        """Carrega e prepara os dados do CSV."""
        if not self.csv_path.exists():
            self.logger.error(f"Arquivo CSV não encontrado em {self.csv_path}")
            return pd.DataFrame()

        # As colunas de data já estão renomeadas pelo AdminService
        date_columns = ['DataInicio', 'DataTermino', 'VencimentoEm', 'UltimaInteracao']
        
        # Passa as colunas de data para serem processadas durante a leitura
        df = self._robust_read_csv(self.csv_path, date_columns)
        if df.empty:
            return df

        # A renomeação de colunas não é mais necessária aqui.
        # Os tipos de data já foram convertidos na leitura.
        df = self._convert_data_types(df)
        
        return df

    def _parse_dates_robustly(self, series):
        """Converte uma série de strings para datetime de forma robusta."""
        parsed_series = pd.to_datetime(series, errors='coerce', format=None)
        
        failed_mask = parsed_series.isna()
        if failed_mask.any():
            alternative_formats = ['%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%d/%m/%Y']
            for fmt in alternative_formats:
                converted_alt = pd.to_datetime(series[failed_mask], format=fmt, errors='coerce')
                parsed_series.loc[failed_mask] = converted_alt
                failed_mask = parsed_series.isna()
                if not failed_mask.any():
                    break
        return parsed_series

    def carregar_dados(self):
        """Carrega e processa os dados do CSV de forma padronizada e robusta."""
        try:
            if not self.csv_path.exists():
                self.logger.error(f"Arquivo CSV não encontrado: {self.csv_path}")
                return pd.DataFrame()
            
            dados = self._robust_read_csv(self.csv_path)
            
            if dados.empty:
                self.logger.warning("Arquivo CSV está vazio ou não pôde ser lido.")
                return pd.DataFrame()

            self.logger.info(f"Arquivo {self.csv_path.name} carregado com {len(dados)} linhas.")
            
            # Padronização de datas
            date_cols = [col for col in dados.columns if 'data' in col.lower() or 'em' in col.lower() or 'vencimento' in col.lower()]
            for col in date_cols:
                if col in dados.columns:
                    dados[col] = self._parse_dates_robustly(dados[col])

            return self._processar_dados(dados)
            
        except Exception as e:
            self.logger.error(f"Erro ao carregar dados: {str(e)}", exc_info=True)
            return pd.DataFrame()

    def _processar_dados(self, dados):
        """Processa os dados carregados (conversões numéricas e de texto)."""
        try:
            # Converter valores numéricos
            for col in COLUNAS_NUMERICAS:
                if col in dados.columns:
                    # Substitui vírgula por ponto e converte
                    dados[col] = pd.to_numeric(dados[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
            
            # Padronizar texto
            for col in COLUNAS_TEXTO:
                if col in dados.columns:
                    dados[col] = dados[col].astype(str).str.strip().str.upper()
            
            return dados
            
        except Exception as e:
            self.logger.error(f"Erro ao processar dados: {str(e)}")
            # Retorna os dados como estão se o processamento falhar
            return dados

    def validar_dados(self, dados):
        """Valida a estrutura básica dos dados"""
        if not isinstance(dados, pd.DataFrame) or dados.empty:
            self.logger.error("Validação falhou: dados inválidos ou vazios.")
            return False
        
        colunas_faltantes = [col for col in COLUNAS_OBRIGATORIAS if col not in dados.columns]
        if colunas_faltantes:
            self.logger.warning(f"Colunas obrigatórias não encontradas: {', '.join(colunas_faltantes)}")
            # Adicionar colunas faltantes com valores padrão pode ser uma opção aqui
            for col in colunas_faltantes:
                dados[col] = 0.0 if col in COLUNAS_NUMERICAS else 'N/A'
        
        return True 
        return True 