import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from .constants import *

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

    def carregar_dados(self):
        """Carrega e processa os dados do CSV"""
        try:
            self.logger.info(f"Tentando carregar dados de: {self.csv_path}")
            
            if not self.csv_path.is_file():
                self.logger.error(f"Arquivo CSV não encontrado: {self.csv_path}")
                return pd.DataFrame()
            
            dados = pd.read_csv(
                self.csv_path, 
                dtype=str, 
                sep=';', 
                encoding='latin1'
            )
            self.logger.info(f"Arquivo {self.csv_path} carregado com {len(dados)} linhas.")
            
            return self._processar_dados(dados)
            
        except Exception as e:
            self.logger.error(f"Erro ao carregar dados: {str(e)}")
            return pd.DataFrame()

    def _processar_dados(self, dados):
        """Processa os dados carregados"""
        try:
            # Converter datas
            colunas_data = ['Aberto em', 'Resolvido em', 'Data da última ação', 'Vencimento em']
            for col in colunas_data:
                if col in dados.columns:
                    dados[col] = pd.to_datetime(dados[col], format='%d/%m/%Y', errors='coerce')
            
            # Converter valores numéricos
            for col in COLUNAS_NUMERICAS:
                if col in dados.columns:
                    dados[col] = pd.to_numeric(dados[col], errors='coerce').fillna(0)
            
            # Padronizar texto
            for col in COLUNAS_TEXTO:
                if col in dados.columns:
                    dados[col] = dados[col].str.strip().str.upper()
            
            return dados
            
        except Exception as e:
            self.logger.error(f"Erro ao processar dados: {str(e)}")
            return pd.DataFrame()

    def validar_dados(self, dados):
        """Valida a estrutura básica dos dados"""
        if not isinstance(dados, pd.DataFrame):
            raise ValueError("Dados devem ser um DataFrame")
        
        if dados.empty:
            raise ValueError("DataFrame vazio recebido")
        
        colunas_faltantes = [col for col in COLUNAS_OBRIGATORIAS if col not in dados.columns]
        if colunas_faltantes:
            self.logger.warning(f"Colunas obrigatórias não encontradas: {', '.join(colunas_faltantes)}")
            for col in colunas_faltantes:
                if col in COLUNAS_NUMERICAS:
                    dados[col] = 0.0
                else:
                    dados[col] = 'NÃO DEFINIDO'
        
        return True 