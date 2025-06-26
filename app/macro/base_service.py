import pandas as pd
from pathlib import Path
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class BaseService:
    """Classe base para serviços de processamento de dados."""
    
    def __init__(self):
        """Inicializa o serviço com configurações básicas."""
        self.csv_path = Path(__file__).parent.parent.parent / 'data' / 'dadosr.csv'
        logger.info(f"Caminho do CSV definido para: {self.csv_path}")
        
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
                logger.info(f"CSV lido com sucesso usando encoding {encoding}.")
                return df
            except (UnicodeDecodeError, ValueError) as e:
                logger.warning(f"Falha ao ler CSV com encoding {encoding}: {e}")
                continue
        logger.error(f"Falha ao ler o CSV {path} com todos os encodings tentados.")
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
            logger.error(f"Arquivo CSV não encontrado em {self.csv_path}")
            return pd.DataFrame()

        # As colunas de data já estão renomeadas pelo AdminService
        date_columns = ['DataInicio', 'DataTermino', 'VencimentoEm', 'UltimaInteracao']
        
        # Passa as colunas de data para serem processadas durante a leitura
        df = self._robust_read_csv(self.csv_path, date_columns)
        if df.empty:
            return df

        # A renomeação de colunas não é mais necessária aqui, pois o AdminService já faz.
        # Os tipos de data já foram convertidos na leitura.
        df = self._convert_data_types(df)
        
        return df

    def get_base_data(self):
        """Retorna o DataFrame base, pronto para uso."""
        return self._load_data()

    @staticmethod
    def converter_tempo_para_horas(tempo_str):
        """Converte string de tempo (HH:MM) para horas decimais."""
        try:
            if pd.isna(tempo_str) or tempo_str == '' or tempo_str == 'nan':
                return 0.0
            if isinstance(tempo_str, (int, float)):
                return float(tempo_str)
            
            tempo_str = str(tempo_str).strip()
            if tempo_str.replace('.', '', 1).isdigit():
                return float(tempo_str)
            
            partes = tempo_str.split(':')
            if len(partes) >= 2:
                horas = int(partes[0])
                minutos = int(partes[1])
                return horas + (minutos/60)
            return 0.0
        except (ValueError, TypeError):
            return 0.0
            
    def calcular_horas_restantes(self, dados):
        """Calcula horas restantes para cada projeto."""
        try:
            if 'HorasTrabalhadas' not in dados.columns or 'HorasPrevistas' not in dados.columns:
                return dados
                
            dados['HorasRestantes'] = dados['HorasPrevistas'] - dados['HorasTrabalhadas']
            dados['HorasRestantes'] = dados['HorasRestantes'].clip(lower=0)
            
            return dados
            
        except Exception as e:
            logger.error(f"Erro ao calcular horas restantes: {str(e)}")
            return dados
            
    def limpar_nome_projeto(self, nome):
        """Remove partes do nome do projeto após vírgulas."""
        try:
            if pd.isna(nome) or nome == '':
                return ''
                
            nome = str(nome).strip()
            if ',' in nome:
                nome = nome.split(',')[0].strip()
                
            return nome
            
        except Exception as e:
            logger.error(f"Erro ao limpar nome do projeto '{nome}': {str(e)}")
            return str(nome) 