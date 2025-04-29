import pandas as pd
from pathlib import Path
import logging
from datetime import datetime, timedelta
import os
import numpy as np

class BaseService:
    """Classe base para serviços de processamento de dados."""
    
    def __init__(self):
        """Inicializa o serviço com configurações básicas."""
        self.csv_path = Path(__file__).parent.parent.parent / 'data' / 'dadosr.csv'
        logger = logging.getLogger(__name__)
        logger.info(f"Caminho do CSV definido para: {self.csv_path}")
        
    def carregar_dados(self):
        """Carrega dados do arquivo CSV."""
        try:
            if not self.csv_path.exists():
                raise FileNotFoundError(f"Arquivo CSV não encontrado: {self.csv_path}")
                
            dados = pd.read_csv(self.csv_path, 
                              sep=';',
                              encoding='latin1',
                              quoting=1)  # QUOTE_ALL
                              
            if dados.empty:
                logger.warning("Arquivo CSV está vazio")
                return pd.DataFrame()
                
            # Verifica colunas obrigatórias
            colunas_obrigatorias = ['Status', 'Squad', 'Especialista', 'Conclusao']
            colunas_faltantes = [col for col in colunas_obrigatorias if col not in dados.columns]
            if colunas_faltantes:
                raise ValueError(f"Colunas obrigatórias ausentes: {colunas_faltantes}")
                
            # Converte datas
            for col in ['DataInicio', 'DataTermino', 'VencimentoEm']:
                if col in dados.columns:
                    dados[col] = pd.to_datetime(dados[col], errors='coerce')
                    
            # Padroniza texto
            for col in ['Status', 'Squad', 'Especialista', 'Account Manager']:
                if col in dados.columns:
                    dados[col] = dados[col].fillna('').astype(str).str.strip()
                    
            # Converte conclusão para numérico
            if 'Conclusao' in dados.columns:
                dados['Conclusao'] = pd.to_numeric(dados['Conclusao'], errors='coerce')
                dados['Conclusao'] = dados['Conclusao'].clip(0, 100)
                
            # Converte horas trabalhadas
            if 'HorasTrabalhadas' in dados.columns:
                dados['HorasTrabalhadas'] = dados['HorasTrabalhadas'].apply(self.converter_tempo_para_horas)
                
            # Limpa nomes de projetos
            if 'Projeto' in dados.columns:
                dados['Projeto'] = dados['Projeto'].apply(self.limpar_nome_projeto)
                
            # Calcula horas restantes
            dados = self.calcular_horas_restantes(dados)
            
            logger.info(f"Dados carregados com sucesso: {len(dados)} registros")
            return dados
            
        except Exception as e:
            logger.error(f"Erro ao carregar dados: {str(e)}", exc_info=True)
            return pd.DataFrame()
            
    def converter_tempo_para_horas(self, tempo_str):
        """Converte string de tempo (HH:MM) para horas decimais."""
        try:
            if pd.isna(tempo_str) or tempo_str == '':
                return 0.0
                
            if isinstance(tempo_str, (int, float)):
                return float(tempo_str)
                
            # Remove espaços e converte para string
            tempo_str = str(tempo_str).strip()
            
            # Se já for um número, retorna como float
            try:
                return float(tempo_str)
            except ValueError:
                pass
                
            # Tenta diferentes formatos
            if ':' in tempo_str:
                # Formato HH:MM
                horas, minutos = tempo_str.split(':')
                return float(horas) + float(minutos)/60
            elif 'h' in tempo_str.lower():
                # Formato Xh Ym
                tempo_str = tempo_str.lower().replace(' ', '')
                if 'h' in tempo_str:
                    horas = float(tempo_str.split('h')[0])
                    minutos = float(tempo_str.split('h')[1].replace('m', '')) if 'm' in tempo_str else 0
                    return horas + minutos/60
                    
            return 0.0
            
        except Exception as e:
            logger.error(f"Erro ao converter tempo '{tempo_str}': {str(e)}")
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