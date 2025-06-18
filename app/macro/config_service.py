import json
import os
from pathlib import Path
import logging
import pandas as pd
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class TiposServicoConfigService:
    """
    Serviço para gerenciar configurações e categorizações dos tipos de serviço
    utilizando o arquivo typeservices.csv
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Configuração de caminhos
        base_dir = Path(__file__).resolve().parent.parent.parent
        data_dir = base_dir / 'data'
        self.typeservices_path = data_dir / 'typeservices.csv'
        
        # Cache das configurações
        self._cache_categorias = None
        self._cache_mapeamento = None
    
    def carregar_categorias(self):
        """Carrega as categorias do arquivo typeservices.csv"""
        try:
            if not self.typeservices_path.is_file():
                self.logger.warning(f"Arquivo typeservices.csv não encontrado em: {self.typeservices_path}")
                return {}
            
            # Lê o arquivo CSV
            df_tipos = pd.read_csv(
                self.typeservices_path,
                sep=';',
                encoding='latin1',
                dtype=str
            )
            
            # Verifica se as colunas esperadas existem
            if 'TipoServico' not in df_tipos.columns or 'Categoria' not in df_tipos.columns:
                self.logger.error("Arquivo typeservices.csv deve conter as colunas 'TipoServico' e 'Categoria'")
                return {}
            
            # Remove entradas vazias
            df_tipos = df_tipos.dropna(subset=['TipoServico', 'Categoria'])
            
            # Cria mapeamento de tipo -> categoria
            mapeamento = df_tipos.set_index('TipoServico')['Categoria'].to_dict()
            
            # Organiza por categorias
            categorias = {}
            for tipo, categoria in mapeamento.items():
                if categoria not in categorias:
                    categorias[categoria] = []
                categorias[categoria].append(tipo)
            
            self._cache_categorias = categorias
            self._cache_mapeamento = mapeamento
            
            self.logger.info(f"Carregadas {len(categorias)} categorias com {len(mapeamento)} tipos de serviço")
            return categorias
            
        except Exception as e:
            self.logger.error(f"Erro ao carregar categorias: {str(e)}")
            return {}
    
    def obter_categoria_por_tipo(self, tipo_servico: str) -> str:
        """Retorna a categoria de um tipo de serviço"""
        if self._cache_mapeamento is None:
            self.carregar_categorias()
        
        return self._cache_mapeamento.get(tipo_servico, 'Outros Serviços')
    
    def obter_categorias(self) -> Dict[str, List[str]]:
        """Retorna todas as categorias organizadas"""
        if self._cache_categorias is None:
            self.carregar_categorias()
        
        return self._cache_categorias or {}
    
    def obter_tipos_por_categoria(self, categoria: str) -> List[str]:
        """Retorna todos os tipos de uma categoria específica"""
        categorias = self.obter_categorias()
        return categorias.get(categoria, [])
    
    def classificar_complexidade(self, horas_medias: float) -> str:
        """Classifica a complexidade baseada nas horas médias"""
        if horas_medias < 20:
            return 'Simples'
        elif horas_medias < 50:
            return 'Médio'
        elif horas_medias < 100:
            return 'Complexo'
        else:
            return 'Muito Complexo'
    
    def obter_cor_complexidade(self, complexidade: str) -> str:
        """Retorna a cor correspondente à complexidade"""
        cores = {
            'Simples': '#28a745',      # Verde
            'Médio': '#ffc107',        # Amarelo
            'Complexo': '#fd7e14',     # Laranja
            'Muito Complexo': '#dc3545' # Vermelho
        }
        return cores.get(complexidade, '#6c757d')
    
    def obter_cor_categoria(self, categoria: str) -> str:
        """Retorna uma cor consistente para cada categoria"""
        # Hash simples para cores consistentes
        cores_disponiveis = [
            '#007bff', '#28a745', '#dc3545', '#ffc107', 
            '#6f42c1', '#fd7e14', '#20c997', '#e83e8c',
            '#17a2b8', '#6c757d', '#343a40', '#f8f9fa'
        ]
        
        # Usa o hash da categoria para selecionar uma cor
        hash_categoria = hash(categoria) % len(cores_disponiveis)
        return cores_disponiveis[hash_categoria]
    
    def obter_icone_categoria(self, categoria: str) -> str:
        """Retorna um ícone Bootstrap Icons para cada categoria"""
        # Mapeamento de categorias conhecidas para ícones
        icones = {
            'Azure Active Directory': 'shield-lock',
            'Azure App Services': 'globe',
            'Azure Application Gateway': 'router',
            'Azure Backup': 'hdd-stack',
            'Azure Database Migration Service': 'arrow-left-right',
            'Azure Landing Zones': 'diagram-3',
            'Azure Marketplace': 'shop',
            'Azure Automation': 'gear',
            'Azure Kubernetes Service (AKS)': 'boxes',
            'Azure Firewall': 'shield-check',
            'Azure Content Delivery Network (CDN)': 'cloud-arrow-down',
            'Azure DDoS Protection': 'shield-exclamation',
            'Active Directory Domain Services (ADDS)': 'building',
            'Microsoft Defender for Cloud': 'shield-fill-check',
            'Azure DevOps': 'code-square',
            'Azure ExpressRoute': 'arrow-repeat',
            'Azure Resource Manager': 'sliders',
            'Azure Migrate': 'arrow-up-right-square',
            'Azure Training': 'mortarboard',
            'Azure Site Recovery': 'arrow-clockwise',
            'Azure Storage': 'hdd',
            'Azure Virtual Desktop': 'display',
            'Azure VPN Gateway': 'lock',
            'Exchange Online': 'envelope',
            'Fast Track': 'lightning',
            'Microsoft 365 Admin Center': 'grid-3x3-gap',
            'Microsoft Copilot Studio': 'robot',
            'Azure Data Factory, Synapse Analytics, Databricks, Stream Analytics, SQL Database, Microsoft Purview (para governança)e outros': 'database',
            'Microsoft Fabric': 'layers',
            'Azure AI Document Intelligence': 'file-text',
            'Azure OpenAI': 'brain',
            'Microsoft Power Pages': 'file-earmark-code',
            'Microsoft Power Apps': 'app',
            'Microsoft Power Automate': 'arrow-repeat',
            'Microsoft Power BI': 'bar-chart',
            'Azure Logic Apps': 'diagram-2',
            'Microsoft Power Automate RPA': 'cpu',
            'Microsoft 365 Migration': 'arrow-up-circle',
            'Threat protection engagement': 'shield-slash',
            'Microsoft Defender for Office 365': 'shield-check',
            'Microsoft Entra ID': 'person-badge',
            'Microsoft Information Protection (MIP)': 'file-lock',
            'Microsoft Intune': 'phone',
            'Microsoft Purview': 'eye',
            'Microsoft Teams': 'camera-video',
            'Windows 365': 'windows',
            'Data security engagement': 'lock-fill',
            'Microsoft Sentinel': 'search',
            'SharePoint Online': 'share',
            'Web Application Firewall (WAF)': 'shield-fill',
            'N/A (serviço personalizado)': 'gear-wide-connected'
        }
        
        return icones.get(categoria, 'gear')
    
    def obter_configuracoes_exibicao(self) -> Dict[str, Any]:
        """Retorna configurações para exibição dos tipos de serviço"""
        return {
            'exibir_cards_resumo': True,
            'exibir_ranking': True,
            'exibir_matriz_squad': True,
            'exibir_grafico_distribuicao': True,
            'exibir_historico_simplificado': True,
            'max_tipos_ranking': 10,
            'max_categorias_grafico': 8
        }

# Instância global do serviço
tipos_servico_config = TiposServicoConfigService() 