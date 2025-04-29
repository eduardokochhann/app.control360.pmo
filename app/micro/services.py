from app.utils.base_service import BaseService
from app.utils.constants import (
    STATUS_ATIVO,
    STATUS_CRITICO,
    STATUS_CONCLUIDO,
    STATUS_ATENDIMENTO
)
import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MicroService(BaseService):
    """Serviço para o módulo micro"""
    
    def __init__(self):
        super().__init__()
        
    def obter_metricas_micro(self, dados):
        """Obtém métricas para o dashboard micro"""
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
            logger.error(f"Erro ao obter métricas micro: {str(e)}")
            return {}
            
    def obter_projetos_por_especialista(self, dados, nome_especialista):
        """Obtém projetos por especialista"""
        try:
            if dados is None or dados.empty:
                return []
                
            projetos = dados[dados['Especialista'] == nome_especialista]
            return self._formatar_projetos(projetos)
            
        except Exception as e:
            logger.error(f"Erro ao obter projetos por especialista: {str(e)}")
            return []
            
    def obter_projetos_por_account(self, dados, nome_account):
        """Obtém projetos por account manager"""
        try:
            if dados is None or dados.empty:
                return []
                
            projetos = dados[dados['Account Manager'] == nome_account]
            return self._formatar_projetos(projetos)
            
        except Exception as e:
            logger.error(f"Erro ao obter projetos por account: {str(e)}")
            return []
            
    def obter_projetos_ativos(self, dados):
        """Obtém projetos ativos"""
        try:
            if dados is None or dados.empty:
                return []
                
            projetos = dados[dados['Status'] == STATUS_ATIVO]
            return self._formatar_projetos(projetos)
            
        except Exception as e:
            logger.error(f"Erro ao obter projetos ativos: {str(e)}")
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

    def _calcular_eficiencia(self, row):
        """Calcula a eficiência de um projeto"""
        try:
            if pd.isnull(row['Vencimento em']) or pd.isnull(row['Aberto em']):
                return 0.0
                
            hoje = datetime.now()
            data_vencimento = pd.to_datetime(row['Vencimento em'])
            data_inicio = pd.to_datetime(row['Aberto em'])
            
            dias_totais = (data_vencimento - data_inicio).days
            dias_passados = (hoje - data_inicio).days
            
            if dias_totais <= 0 or dias_passados <= 0:
                return 0.0
                
            percentual_tempo = (dias_passados / dias_totais) * 100
            percentual_conclusao = float(row['Conclusão']) if pd.notnull(row['Conclusão']) else 0.0
            
            return percentual_conclusao - percentual_tempo
            
        except Exception as e:
            logger.error(f"Erro ao calcular eficiência: {str(e)}")
            return 0.0

    def _formatar_projetos(self, projetos):
        """Formata dados dos projetos para retorno"""
        try:
            return [{
                'numero': row['Número'],
                'projeto': row['Projeto'],
                'status': row['Status'],
                'squad': row['Squad'],
                'especialista': row['Especialista'],
                'account': row['Account Manager'],
                'data_inicio': row['Aberto em'].strftime('%d/%m/%Y') if pd.notnull(row['Aberto em']) else '',
                'data_vencimento': row['Vencimento em'].strftime('%d/%m/%Y') if pd.notnull(row['Vencimento em']) else '',
                'conclusao': float(row['Conclusão']) if pd.notnull(row['Conclusão']) else 0.0,
                'horas_trabalhadas': float(row['Horas trabalhadas']) if pd.notnull(row['Horas trabalhadas']) else 0.0,
                'horas_restantes': float(row['Horas restantes']) if pd.notnull(row['Horas restantes']) else 0.0
            } for _, row in projetos.iterrows()]
            
        except Exception as e:
            logger.error(f"Erro ao formatar projetos: {str(e)}")
            return []

def processar_micro(dados):
    """Processa os dados para a visão Micro"""
    try:
        dados_limpos = dados.dropna(subset=['Projeto'])
        return {
            'porcentagem_conclusao': dados_limpos.groupby('Projeto')['Conclusao'].mean().round(1).to_dict(),
            'saldo_horas': dados_limpos.groupby('Projeto')['HorasRestantes'].sum().astype(int).to_dict(),
            'ultima_interacao': dados_limpos.groupby('Projeto')['UltimaInteracao'].max().to_dict()
        }
    except Exception as e:
        logging.error(f"Erro ao processar dados Micro: {str(e)}")
        return {
            'porcentagem_conclusao': {},
            'saldo_horas': {},
            'ultima_interacao': {}
        }