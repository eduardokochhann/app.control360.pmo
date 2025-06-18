import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import logging
import numpy as np
import glob
import os
from .base_service import BaseService
from .constants import *

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constantes de status atualizadas
STATUS_NAO_ATIVOS = ['FECHADO', 'ENCERRADO', 'RESOLVIDO', 'CANCELADO']
STATUS_EM_ANDAMENTO = ['NOVO', 'AGUARDANDO', 'BLOQUEADO', 'EM ATENDIMENTO']
STATUS_ATRASADO = ['ATRASADO']
STATUS_ATIVO = ['ATIVO']

# Colunas obrigatórias
COLUNAS_OBRIGATORIAS = ['Projeto', 'Status', 'Squad', 'Faturamento', 'HorasTrabalhadas']
COLUNAS_NUMERICAS = ['Horas', 'HorasRestantes', 'Conclusao', 'HorasTrabalhadas']
COLUNAS_TEXTO = ['Squad', 'Status', 'Faturamento', 'Especialista', 'Account Manager']

class GerencialService(BaseService):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        # Configuração de status
        self.status_ativos = ['Novo', 'Aguardando', 'Em Atendimento', 'Bloqueado']
        self.status_concluidos = ['Fechado', 'Encerrado', 'Resolvido', 'Cancelado']
        
        # Configuração de caminhos - Aponta diretamente para dadosr.csv
        base_dir = Path(__file__).resolve().parent.parent.parent
        data_dir = base_dir / 'data'
        self.csv_path = data_dir / 'dadosr.csv' # Alterado para usar dadosr.csv
        logger.info(f"Caminho do CSV definido para: {self.csv_path}")

    def carregar_dados(self):
        """Carrega e processa os dados do CSV"""
        try:
            logger.info(f"Tentando carregar dados de: {self.csv_path}")
            
            # Verifica se o arquivo existe
            if not self.csv_path.is_file(): # Usa .is_file() para Path objects
                logger.error(f"Arquivo CSV não encontrado: {self.csv_path}")
                return pd.DataFrame() # Retorna DataFrame vazio
            
            # Lê o CSV dadosr.csv com parâmetros corretos
            # dtype=str ainda é útil para ler tudo inicialmente e tratar depois
            dados = pd.read_csv(
                self.csv_path, 
                dtype=str, 
                sep=';', 
                encoding='latin1', # Codificação correta para dadosr.csv
                # quoting=csv.QUOTE_MINIMAL (ou 1) pode ser necessário se campos contêm delimitador
                # Vamos começar sem quoting explícito, pode ser adicionado se necessário
            )
            logger.info(f"Arquivo {self.csv_path} carregado com {len(dados)} linhas.")
            
            # --- Passo 1.2: Tratamento Inicial (Usando Nomes de dadosr.csv) ---
            
            # 1.2.1 Conversão de Datas
            colunas_data_simples = ['Aberto em', 'Resolvido em', 'Data da última ação']
            for col in colunas_data_simples:
                if col in dados.columns:
                    dados[col] = pd.to_datetime(dados[col], format='%d/%m/%Y', errors='coerce')
                else:
                    logger.warning(f"Coluna de data esperada não encontrada: {col}")
            
            # Tratamento especial para 'Vencimento em' (pode ter hora)
            if 'Vencimento em' in dados.columns:
                logger.info("=== Processando Vencimento em ===")
                # Log dos 5 primeiros valores originais
                logger.info(f"Valores originais (head): {dados['Vencimento em'].head().tolist()}")
                
                # Tenta primeiro com data e hora
                dados['Vencimento em_Original'] = dados['Vencimento em'] # Guarda original para debug
                dados['Vencimento em'] = pd.to_datetime(dados['Vencimento em_Original'], format='%d/%m/%Y %H:%M', errors='coerce')
                logger.info(f"Após 1ª tentativa (data/hora) (head): {dados['Vencimento em'].head().tolist()}")
                
                # Onde falhou (virou NaT), tenta apenas com data
                mask_nat = dados['Vencimento em'].isna()
                logger.info(f"Linhas que falharam na 1ª tentativa: {mask_nat.sum()}")
                
                if mask_nat.any():
                    # Log de alguns valores que falharam
                    logger.info(f"Exemplos de valores que falharam (originais): {dados.loc[mask_nat, 'Vencimento em_Original'].head().tolist()}")
                    
                    dados.loc[mask_nat, 'Vencimento em'] = pd.to_datetime(dados.loc[mask_nat, 'Vencimento em_Original'], format='%d/%m/%Y', errors='coerce')
                    logger.info(f"Após 2ª tentativa (data) para NaTs (head dos que falharam antes): {dados.loc[mask_nat, 'Vencimento em'].head().tolist()}")
                    
                    # Verifica se ainda há NaTs após a 2ª tentativa
                    mask_nat_final = dados['Vencimento em'].isna()
                    if mask_nat_final.sum() > 0:
                        logger.warning(f"{mask_nat_final.sum()} valores em 'Vencimento em' ainda são NaT após todas as tentativas.")
                        logger.warning(f"Exemplos finais de NaT (originais): {dados.loc[mask_nat_final, 'Vencimento em_Original'].head().tolist()}")
                
                # Remove a coluna original de debug
                # del dados['Vencimento em_Original']
            else:
                logger.warning("Coluna de data esperada não encontrada: Vencimento em")

            # 1.2.2 Conversão Numérica
            # 'Número' para Inteiro (usando Int64 para suportar possíveis NaNs da conversão)
            if 'Número' in dados.columns:
                dados['Número'] = pd.to_numeric(dados['Número'], errors='coerce').astype('Int64')
            else:
                logger.warning("Coluna numérica esperada não encontrada: Número")

            # 'Esforço estimado' para Float (trata vírgula e nulos)
            if 'Esforço estimado' in dados.columns:
                dados['Esforço estimado'] = dados['Esforço estimado'].str.replace(',', '.', regex=False)
                dados['Esforço estimado'] = pd.to_numeric(dados['Esforço estimado'], errors='coerce').fillna(0.0)
            else:
                logger.warning("Coluna numérica esperada não encontrada: Esforço estimado")
                dados['Esforço estimado'] = 0.0 # Cria a coluna se não existir, para segurança

            # 'Andamento' para Float (trata % e nulos)
            if 'Andamento' in dados.columns:
                dados['Andamento'] = dados['Andamento'].str.rstrip('%').str.replace(',', '.', regex=False)
                dados['Andamento'] = pd.to_numeric(dados['Andamento'], errors='coerce').fillna(0.0)
                dados['Andamento'] = dados['Andamento'].clip(lower=0, upper=100) # Garante 0-100
            else:
                logger.warning("Coluna numérica esperada não encontrada: Andamento")
                dados['Andamento'] = 0.0 # Cria a coluna se não existir
            
            # 1.2.3 Conversão de Tempo para Horas Decimais
            if 'Tempo trabalhado' in dados.columns:
                # Reutiliza a função de conversão existente na classe
                dados['Tempo trabalhado'] = dados['Tempo trabalhado'].apply(self.converter_tempo_para_horas)
            else:
                 logger.warning("Coluna de tempo esperada não encontrada: Tempo trabalhado")
                 dados['Tempo trabalhado'] = 0.0 # Cria a coluna se não existir

            # --- Fim do Passo 1.2 ---

            # --- Passo 1.3: Renomeação (Novos Nomes -> Nomes Antigos/Apelidos) ---
            rename_map_new_to_old = {
                'Número': 'Numero',
                'Cliente (Completo)': 'Cliente',
                'Assunto': 'Projeto',
                'Serviço (2º Nível)': 'Squad',
                'Serviço (3º Nível)': 'TipoServico',
                'Status': 'Status', # Mantém o nome
                'Esforço estimado': 'Horas',
                'Tempo trabalhado': 'HorasTrabalhadas',
                'Andamento': 'Conclusao',
                'Data da última ação': 'UltimaInteracao',
                'Tipo de faturamento': 'Faturamento',
                'Responsável': 'Especialista',
                'Account Manager ': 'Account Manager', # Remove espaço final
                'Aberto em': 'DataInicio',
                'Resolvido em': 'DataTermino',
                'Vencimento em': 'VencimentoEm'
            }
            
            # Verifica quais colunas do mapa realmente existem no DataFrame antes de renomear
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
            
            logger.info(f"Colunas renomeadas para nomes antigos/apelidos: {list(colunas_para_renomear.values())}")
            # --- Fim do Passo 1.3 ---
            
            # --- Passo 1.4: Padronização Final (Usando Nomes Antigos/Apelidos) ---
            
            # 1.4.1 Padronização de Status (para Title Case)
            if 'Status' in dados.columns:
                # Converte para string, remove espaços extras e aplica Title Case
                dados['Status'] = dados['Status'].astype(str).str.strip().str.title()
                # Opcional: Preencher NaNs restantes, se houver, após conversão inicial
                # dados['Status'] = dados['Status'].fillna('Desconhecido') 
                logger.info(f"Coluna 'Status' padronizada para Title Case. Valores únicos: {dados['Status'].unique().tolist()}")
            else:
                logger.warning("Coluna 'Status' não encontrada para padronização final.")

            # 1.4.2 Padronização de Faturamento (Texto Longo -> Código Curto/Apelido)
            faturamento_map = {
                # Mapeia os textos originais de dadosr.csv para os apelidos
                "PRIME": "PRIME",
                "Descontar do PLUS no inicio do projeto": "PLUS",
                "Faturar no inicio do projeto": "INICIO",
                "Faturar no final do projeto": "TERMINO",
                "Faturado em outro projeto": "FEOP", # Inclui os que eram vazios
                "Faturado em outro projeto.": "FEOP", # Adicionado com ponto final
                "Engajamento": "ENGAJAMENTO"
            }
            if 'Faturamento' in dados.columns:
                # Garante que é string e remove espaços
                dados['Faturamento'] = dados['Faturamento'].astype(str).str.strip()
                # Aplica o mapeamento. Valores não encontrados no mapa se tornarão NaN.
                dados['Faturamento_Original'] = dados['Faturamento'] # Guarda o original para debug, se necessário
                dados['Faturamento'] = dados['Faturamento'].map(faturamento_map)
                # Trata valores que não foram mapeados (viraram NaN)
                nao_mapeados = dados['Faturamento'].isna()
                if nao_mapeados.any():
                    logger.warning(f"Valores de faturamento não mapeados encontrados: {dados.loc[nao_mapeados, 'Faturamento_Original'].unique().tolist()}")
                    # Valores "nan" ou vazios devem ser mapeados para EAN (Em Análise)
                    # Verifica valores que são NaN ou 'nan' string no original
                    mask_nan = dados['Faturamento_Original'].isna() | (dados['Faturamento_Original'] == 'nan')
                    if mask_nan.any():
                        dados.loc[mask_nan, 'Faturamento'] = 'EAN'
                        logger.info(f"Mapeado {mask_nan.sum()} valores nan/vazios para EAN")
                    
                    # Outros valores não mapeados ainda são preenchidos com NAO_MAPEADO
                    dados['Faturamento'] = dados['Faturamento'].fillna('NAO_MAPEADO')
                    
                logger.info(f"Coluna 'Faturamento' mapeada para códigos curtos. Valores únicos: {dados['Faturamento'].unique().tolist()}")
                # Remove a coluna original de debug se não for mais necessária
                # del dados['Faturamento_Original'] 
            else:
                 logger.warning("Coluna 'Faturamento' não encontrada para padronização final.")

            # 1.4.3 Padronização de outras colunas de texto
            colunas_texto_padrao = ['Projeto', 'Squad', 'Especialista', 'Account Manager']
            for col in colunas_texto_padrao:
                if col in dados.columns:
                    dados[col] = dados[col].astype(str).str.strip()
                    # Tratamento especial para Squad: valores vazios ou 'nan' viram 'Em Planejamento - PMO'
                    if col == 'Squad':
                        dados[col] = dados[col].replace({'': 'Em Planejamento - PMO', 'nan': 'Em Planejamento - PMO', 'NÃO DEFINIDO': 'Em Planejamento - PMO'})
                        dados[col] = dados[col].fillna('Em Planejamento - PMO')
                    else:
                        # Para outras colunas, mantém o comportamento original
                        dados[col] = dados[col].replace({'': 'NÃO DEFINIDO', 'nan': 'NÃO DEFINIDO'})
                        dados[col] = dados[col].fillna('NÃO DEFINIDO')
                else:
                    logger.warning(f"Coluna de texto '{col}' não encontrada para padronização final.")
            # --- Fim do Passo 1.4 ---
            
            # Reavaliação do cálculo de HorasRestantes
            # A função antiga calculava Horas - HorasTrabalhadas. Isso ainda é válido?
            # Ambas as colunas agora são numéricas decimais.
            if 'Horas' in dados.columns and 'HorasTrabalhadas' in dados.columns:
                 dados['HorasRestantes'] = (dados['Horas'] - dados['HorasTrabalhadas']).round(1)
                 logger.info("Coluna 'HorasRestantes' calculada.")
            else:
                 logger.warning("Não foi possível calcular 'HorasRestantes': colunas 'Horas' ou 'HorasTrabalhadas' ausentes após renomeação.")
                 dados['HorasRestantes'] = 0.0 # Define como 0 se não puder calcular

            logger.info(f"Dados carregados e totalmente processados. Total de registros: {len(dados)}")
            return dados

        except Exception as e:
            logger.error(f"Erro ao carregar e tratar dados: {str(e)}")
            return pd.DataFrame()

    def converter_tempo_para_horas(self, tempo_str):
        """Converte string de tempo (HH:MM:SS ou HH:MM) para horas decimais"""
        try:
            if pd.isna(tempo_str) or tempo_str == '':
                return 0.0
            if isinstance(tempo_str, (int, float)):
                return float(tempo_str)
            
            tempo_str = str(tempo_str).strip()
            if tempo_str.replace('.', '').isdigit():
                return float(tempo_str)
            
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

    def calcular_horas_restantes(self, dados):
        """Calcula as horas restantes dos projetos"""
        try:
            # Garante que as colunas existam
            for coluna in ['Horas', 'HorasTrabalhadas']:
                if coluna not in dados.columns:
                    logger.warning(f"Coluna {coluna} não encontrada. Criando com valor 0.0")
                    dados[coluna] = 0.0
            
            # Converte para numérico
            dados['Horas'] = pd.to_numeric(dados['Horas'], errors='coerce').fillna(0.0)
            dados['HorasTrabalhadas'] = pd.to_numeric(dados['HorasTrabalhadas'], errors='coerce').fillna(0.0)
            
            # Calcula horas restantes
            dados['HorasRestantes'] = dados['Horas'] - dados['HorasTrabalhadas']
            dados['HorasRestantes'] = dados['HorasRestantes'].round(1)
            
            return dados
            
        except Exception as e:
            logger.error(f"Erro ao calcular horas restantes: {str(e)}")
            return dados

    def obter_projetos_ativos(self, dados):
        """Filtra projetos ativos para o modal"""
        try:
            STATUS_NAO_ATIVOS = ['FECHADO', 'ENCERRADO', 'RESOLVIDO', 'CANCELADO']
            dados_limpos = dados.copy()
            dados_limpos['Status'] = dados_limpos['Status'].str.strip().str.upper()
            
            projetos_ativos = dados_limpos[~dados_limpos['Status'].isin(STATUS_NAO_ATIVOS)]
            
            # Verifica se existe coluna Numero ou Número e padroniza para Numero
            if 'Numero' not in projetos_ativos.columns and 'Número' in projetos_ativos.columns:
                projetos_ativos['Numero'] = projetos_ativos['Número']
                logger.info(f"Coluna 'Número' encontrada e convertida para 'Numero'")
            
            # Debug: verificar se a coluna 'Numero' existe após a conversão
            logger.info(f"Colunas após conversão: {projetos_ativos.columns.tolist()}")
            if 'Numero' in projetos_ativos.columns:
                logger.info(f"Amostra de valores da coluna 'Numero': {projetos_ativos['Numero'].head().tolist()}")
            
            # Seleciona colunas relevantes
            colunas = ['Numero', 'Projeto', 'Squad', 'Status', 'Horas', 'HorasRestantes', 'Conclusao', 'Account Manager', 'VencimentoEm']
            
            # Garante que todas as colunas existem
            colunas_existentes = [col for col in colunas if col in projetos_ativos.columns]
            logger.info(f"Colunas existentes para seleção: {colunas_existentes}")
            
            dados_formatados = projetos_ativos[colunas_existentes].copy()
            
            # Garantir que Squad não tenha valores nulos
            if 'Squad' in dados_formatados.columns:
                dados_formatados['Squad'] = dados_formatados['Squad'].fillna('Em Planejamento - PMO')
                dados_formatados['Squad'] = dados_formatados['Squad'].replace({'nan': 'Em Planejamento - PMO', '': 'Em Planejamento - PMO', 'NÃO DEFINIDO': 'Em Planejamento - PMO'})
            
            # Garante que Conclusao seja numérico
            dados_formatados['Conclusao'] = pd.to_numeric(dados_formatados['Conclusao'], errors='coerce').fillna(0.0)
            dados_formatados['Conclusao'] = dados_formatados['Conclusao'].clip(lower=0, upper=100)
            
            # Garante que HorasRestantes seja numérico
            dados_formatados['HorasRestantes'] = pd.to_numeric(dados_formatados['HorasRestantes'], errors='coerce').fillna(0.0)
            
            # Se 'Numero' existe, converte para string para exibição adequada
            if 'Numero' in dados_formatados.columns:
                dados_formatados['Numero'] = dados_formatados['Numero'].astype('Int64').astype(str)
                logger.info(f"Coluna 'Numero' convertida para string. Amostra: {dados_formatados['Numero'].head().tolist()}")
            
            # Formata a data de vencimento
            dados_formatados['VencimentoEm'] = pd.to_datetime(dados_formatados['VencimentoEm'], errors='coerce')
            dados_formatados['VencimentoEm'] = dados_formatados['VencimentoEm'].dt.strftime('%d/%m/%Y')
            dados_formatados['VencimentoEm'] = dados_formatados['VencimentoEm'].fillna('N/A')
            
            # Log para debug
            logger.debug(f"Amostra dos projetos ativos:\n{dados_formatados.head()}")
            logger.info(f"Total de projetos ativos: {len(dados_formatados)}")
            
            # Converte para dicionário e normaliza as chaves para minúsculas para compatibilidade com o frontend
            resultado = dados_formatados.replace({np.nan: None}).to_dict('records')
            
            # Normaliza as chaves para o formato esperado pelo frontend
            resultado_normalizado = []
            for projeto in resultado:
                projeto_normalizado = {}
                for k, v in projeto.items():
                    # Normalização específica para campos especiais
                    if k == 'Numero':
                        projeto_normalizado['numero'] = v
                    elif k == 'HorasRestantes':
                        projeto_normalizado['horas_restantes'] = v
                    elif k == 'VencimentoEm':
                        projeto_normalizado['data_vencimento'] = v
                    elif k == 'Conclusao':
                        projeto_normalizado['conclusao'] = v
                    else:
                        # Para outros campos, apenas converte para minúsculo
                        projeto_normalizado[k.lower()] = v
                resultado_normalizado.append(projeto_normalizado)
            
            if resultado_normalizado:
                logger.info(f"Exemplo de projeto normalizado (primeiro registro): {resultado_normalizado[0]}")
            
            return resultado_normalizado
        
        except Exception as e:
            logger.error(f"Erro ao obter projetos ativos: {str(e)}")
            return []

    def obter_projetos_criticos(self, dados=None):
        """Retorna lista de projetos críticos"""
        try:
            if dados is None:
                dados = self.carregar_dados()
                
            if dados.empty:
                return []

            self.validar_dados(dados)
            
            # Log para verificar os valores únicos de Status
            logger.info(f"obter_projetos_criticos: Valores únicos na coluna Status: {dados['Status'].unique().tolist()}")
            logger.info(f"obter_projetos_criticos: Status concluídos considerados: {self.status_concluidos}")
            
            # Data atual para comparação
            hoje = pd.Timestamp(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))
            logger.info(f"obter_projetos_criticos: Data de referência (hoje): {hoje.strftime('%d/%m/%Y')}")
            
            # Cria uma cópia dos dados com Status em maiúsculo para comparação case-insensitive
            dados_temp = dados.copy()
            
            # Garante que Status seja tratado como string
            dados_temp['Status'] = dados_temp['Status'].astype(str)
            
            # Filtra apenas projetos não concluídos - usando comparação case-insensitive
            status_concluidos_upper = [s.upper() for s in self.status_concluidos]
            projetos_nao_concluidos = dados_temp[~dados_temp['Status'].str.upper().isin(status_concluidos_upper)]
            
            logger.info(f"obter_projetos_criticos: Total de projetos não concluídos: {len(projetos_nao_concluidos)}")
            
            # Condições de criticidade
            # 1. Projetos bloqueados - usando comparação case-insensitive
            bloqueados = projetos_nao_concluidos['Status'].str.upper() == 'BLOQUEADO'
            logger.info(f"obter_projetos_criticos: Projetos bloqueados: {sum(bloqueados)}")
            
            # 2. Projetos com horas restantes negativas
            horas_negativas = projetos_nao_concluidos['HorasRestantes'] < 0
            logger.info(f"obter_projetos_criticos: Projetos com horas negativas: {sum(horas_negativas)}")
            
            # 3. Projetos com prazo vencido
            # Normaliza as datas primeiro
            projetos_nao_concluidos['VencimentoEm'] = pd.to_datetime(projetos_nao_concluidos['VencimentoEm'], errors='coerce').dt.normalize()
            
            # Cria uma coluna de flag para prazos vencidos para facilitar a contagem
            projetos_nao_concluidos['prazo_vencido'] = projetos_nao_concluidos.apply(
                lambda row: pd.notna(row['VencimentoEm']) and row['VencimentoEm'] < hoje,
                axis=1
            )
            prazo_vencido = projetos_nao_concluidos['prazo_vencido']
            
            logger.info(f"obter_projetos_criticos: Projetos com prazo vencido: {sum(prazo_vencido)}")
            
            # Combina todas as condições
            projetos_criticos = projetos_nao_concluidos[bloqueados | horas_negativas | prazo_vencido].copy()
            
            # Adiciona campo de motivo para cada projeto
            projetos_criticos['Motivo'] = ''
            projetos_criticos.loc[bloqueados, 'Motivo'] += 'Projeto bloqueado; '
            projetos_criticos.loc[horas_negativas, 'Motivo'] += 'Horas excedidas; '
            projetos_criticos.loc[prazo_vencido, 'Motivo'] += 'Prazo vencido; '
            projetos_criticos['Motivo'] = projetos_criticos['Motivo'].str.rstrip('; ')
            
            logger.info(f"obter_projetos_criticos: Total de projetos críticos encontrados: {len(projetos_criticos)}")
            if len(projetos_criticos) > 0:
                logger.info(f"obter_projetos_criticos: Exemplo de projeto crítico: {projetos_criticos.iloc[0]['Projeto']}")
                logger.info(f"obter_projetos_criticos: Distribuição por motivo: Bloqueados: {sum(bloqueados & (bloqueados | horas_negativas | prazo_vencido))}, Horas negativas: {sum(horas_negativas & (bloqueados | horas_negativas | prazo_vencido))}, Prazo vencido: {sum(prazo_vencido & (bloqueados | horas_negativas | prazo_vencido))}")
            
            # Verifica as colunas antes de formatar
            logger.info(f"obter_projetos_criticos: Colunas disponíveis para formatação: {projetos_criticos.columns.tolist()}")
            
            projetos_formatados = self._formatar_projetos(projetos_criticos)
            logger.info(f"obter_projetos_criticos: Total de projetos após formatação: {len(projetos_formatados)}")
            
            return projetos_formatados
            
        except Exception as e:
            self.logger.error(f"Erro ao obter projetos críticos: {str(e)}", exc_info=True)
            return []

    def obter_projetos_em_atendimento(self, dados):
        """Filtra projetos com status 'EM ATENDIMENTO' ou 'NOVO' para o modal"""
        try:
            dados_limpos = dados.copy()
            dados_limpos['Status'] = dados_limpos['Status'].str.strip().str.upper()
            
            projetos_filtrados = dados_limpos[
                dados_limpos['Status'].isin(['EM ATENDIMENTO', 'NOVO'])
            ]
            
            # Verifica se existe coluna Numero ou Número e padroniza para Numero
            if 'Numero' not in projetos_filtrados.columns and 'Número' in projetos_filtrados.columns:
                projetos_filtrados['Numero'] = projetos_filtrados['Número']
            
            # Seleciona colunas relevantes
            colunas = ['Numero', 'Projeto', 'Squad', 'Status', 'Conclusao', 'HorasRestantes', 'VencimentoEm']
            
            # Garante que todas as colunas existem
            colunas_existentes = [col for col in colunas if col in projetos_filtrados.columns]
            projetos_formatados = projetos_filtrados[colunas_existentes].copy()
            
            # Garantir que Squad não tenha valores nulos
            if 'Squad' in projetos_formatados.columns:
                projetos_formatados['Squad'] = projetos_formatados['Squad'].fillna('Em Planejamento - PMO')
                projetos_formatados['Squad'] = projetos_formatados['Squad'].replace({'nan': 'Em Planejamento - PMO', '': 'Em Planejamento - PMO', 'NÃO DEFINIDO': 'Em Planejamento - PMO'})
            
            # Formata conclusão e horas restantes
            if 'Conclusao' in projetos_formatados.columns:
                projetos_formatados['Conclusao'] = projetos_formatados['Conclusao'].fillna(0)
            
            if 'HorasRestantes' in projetos_formatados.columns:
                projetos_formatados['HorasRestantes'] = projetos_formatados['HorasRestantes'].fillna(0)
            
            # Se 'Numero' existe, converte para string para exibição adequada
            if 'Numero' in projetos_formatados.columns:
                projetos_formatados['Numero'] = projetos_formatados['Numero'].astype('Int64').astype(str)
            
            # Formata a data de vencimento
            if 'VencimentoEm' in projetos_formatados.columns:
                projetos_formatados['VencimentoEm'] = pd.to_datetime(
                    projetos_formatados['VencimentoEm'], 
                    errors='coerce'
                ).dt.strftime('%d/%m/%Y')
                projetos_formatados['VencimentoEm'] = projetos_formatados['VencimentoEm'].fillna('N/A')
            
            # Seleciona as colunas na ordem correta
            colunas_finais = [col for col in colunas if col in projetos_formatados.columns]
            projetos_formatados = projetos_formatados[colunas_finais].copy()
            
            # Converte para dicionário e normaliza as chaves para minúsculas para compatibilidade com o frontend
            resultado = projetos_formatados.replace({np.nan: None}).to_dict('records')
            
            # Normaliza as chaves para o formato esperado pelo frontend
            resultado_normalizado = []
            for projeto in resultado:
                projeto_normalizado = {}
                for k, v in projeto.items():
                    # Normalização específica para campos especiais
                    if k == 'Numero':
                        projeto_normalizado['numero'] = v
                    elif k == 'HorasRestantes':
                        projeto_normalizado['horas_restantes'] = v
                    elif k == 'VencimentoEm':
                        projeto_normalizado['data_vencimento'] = v
                    elif k == 'Conclusao':
                        projeto_normalizado['conclusao'] = v
                    else:
                        # Para outros campos, apenas converte para minúsculo
                        projeto_normalizado[k.lower()] = v
                resultado_normalizado.append(projeto_normalizado)
                
            return resultado_normalizado
        
        except Exception as e:
            logging.error(f"Erro ao obter projetos em atendimento: {str(e)}")
            return []

    def obter_projetos_para_faturar(self, dados=None):
        """Retorna projetos para faturar usando a mesma lógica das métricas gerenciais"""
        try:
            if dados is None:
                dados = self.carregar_dados()
            
            if dados.empty:
                logger.warning("Nenhum dado disponível para projetos para faturar")
                return []
            
            # FILTRO: Exclui projetos com especialista CDB DATA SOLUTIONS
            if 'Especialista' in dados.columns:
                dados_antes = len(dados)
                dados = dados[~dados['Especialista'].str.upper().isin(['CDB DATA SOLUTIONS'])]
                dados_depois = len(dados)
                logger.info(f"Projetos para faturar - Filtro CDB DATA SOLUTIONS: {dados_antes} → {dados_depois} (excluídos: {dados_antes - dados_depois})")
            
            # Obtém data atual para filtros
            hoje = pd.Timestamp.now()
            mes_atual = hoje.month
            ano_atual = hoje.year
            
            logger.info(f"Buscando projetos para faturar - Mês atual: {mes_atual}, Ano atual: {ano_atual}")
            logger.info(f"Total de projetos antes do filtro: {len(dados)}")
            
            # DEBUG: Verificar os valores únicos na coluna Status
            logger.info(f"DEBUG - Valores únicos na coluna Status: {dados['Status'].unique()}")
            
            # Condição para faturar no início (PRIME, PLUS, INICIO)
            cond_inicio = (
                dados['Faturamento'].isin(['PRIME', 'PLUS', 'INICIO']) &
                (dados['DataInicio'].dt.month == mes_atual) &
                (dados['DataInicio'].dt.year == ano_atual)
            )
            
            projetos_inicio = dados[
                dados['Faturamento'].isin(['PRIME', 'PLUS', 'INICIO']) &
                (dados['DataInicio'].dt.month == mes_atual) &
                (dados['DataInicio'].dt.year == ano_atual)
            ]
            
            logger.info(f"Projetos com faturamento PRIME/PLUS/INICIO no mês atual: {len(projetos_inicio)}")
            if len(projetos_inicio) > 0:
                logger.info(f"Exemplos: {projetos_inicio['Projeto'].head(3).tolist()}")
            
            # DEBUG: Verificar projetos com status Resolvido
            projetos_resolvidos = dados[dados['Status'] == 'Resolvido']
            logger.info(f"DEBUG - Projetos com status Resolvido: {len(projetos_resolvidos)}")
            if len(projetos_resolvidos) > 0:
                logger.info(f"DEBUG - Exemplos de projetos Resolvidos: {projetos_resolvidos['Projeto'].head(3).tolist()}")
                logger.info(f"DEBUG - Faturamento dos resolvidos: {projetos_resolvidos['Faturamento'].unique().tolist()}")
            
            # Condição para faturar no término - APENAS TERMINO (não ENGAJAMENTO)
            cond_termino = (
                (dados['Faturamento'] == 'TERMINO') &
                (
                    # Verifica se a data prevista (VencimentoEm) é no mês atual para projetos em andamento
                    ((~dados['Status'].isin(['Fechado', 'Resolvido'])) & 
                     (dados['VencimentoEm'].dt.month == mes_atual) & 
                     (dados['VencimentoEm'].dt.year == ano_atual)) |
                    # OU se a data de término (DataTermino) é no mês atual para projetos concluídos
                    ((dados['Status'].isin(['Fechado', 'Resolvido'])) & 
                     (dados['DataTermino'].dt.month == mes_atual) & 
                     (dados['DataTermino'].dt.year == ano_atual))
                )
            )
            
            # Condição especial para ENGAJAMENTO - VencimentoEm + 30 dias no mês atual
            # Calcula a data de faturamento (VencimentoEm + 30 dias)
            dados_engajamento = dados[dados['Faturamento'] == 'ENGAJAMENTO'].copy()
            if not dados_engajamento.empty:
                # Adiciona 30 dias à data de vencimento
                dados_engajamento['DataFaturamentoEngajamento'] = dados_engajamento['VencimentoEm'] + pd.Timedelta(days=30)
                
                # Verifica se a data de faturamento está no mês atual
                cond_engajamento = (
                    (dados['Faturamento'] == 'ENGAJAMENTO') &
                    (dados['VencimentoEm'].notna()) &  # Garante que tem data de vencimento
                    ((dados['VencimentoEm'] + pd.Timedelta(days=30)).dt.month == mes_atual) &
                    ((dados['VencimentoEm'] + pd.Timedelta(days=30)).dt.year == ano_atual)
                )
                
                logger.info(f"Projetos ENGAJAMENTO com VencimentoEm + 30 dias no mês atual: {cond_engajamento.sum()}")
            else:
                cond_engajamento = pd.Series([False] * len(dados), index=dados.index)
                logger.info("Nenhum projeto com faturamento ENGAJAMENTO encontrado")
            
            # Log dos projetos TERMINO
            projetos_termino = dados[cond_termino]
            logger.info(f"Projetos com faturamento TERMINO com datas no mês atual: {len(projetos_termino)}")
            if len(projetos_termino) > 0:
                logger.info(f"Exemplos TERMINO: {projetos_termino['Projeto'].head(3).tolist()}")
            
            # Log dos projetos ENGAJAMENTO
            projetos_engajamento = dados[cond_engajamento]
            logger.info(f"Projetos com faturamento ENGAJAMENTO (VencimentoEm + 30 dias): {len(projetos_engajamento)}")
            if len(projetos_engajamento) > 0:
                logger.info(f"Exemplos ENGAJAMENTO: {projetos_engajamento['Projeto'].head(3).tolist()}")
                # Log das datas para debug
                for _, row in projetos_engajamento.head(3).iterrows():
                    venc_original = row['VencimentoEm'].strftime('%d/%m/%Y') if pd.notna(row['VencimentoEm']) else 'N/A'
                    venc_mais_30 = (row['VencimentoEm'] + pd.Timedelta(days=30)).strftime('%d/%m/%Y') if pd.notna(row['VencimentoEm']) else 'N/A'
                    logger.info(f"  {row['Projeto']}: Vencimento={venc_original}, Faturamento={venc_mais_30}")
            
            # Filtra projetos para faturar (exclui FTOP)
            projetos_para_faturar = dados[
                (cond_inicio | cond_termino | cond_engajamento) & 
                (dados['Faturamento'] != 'FTOP')
            ].copy()
            
            logger.info(f"Total após filtros e exclusão de FTOP: {len(projetos_para_faturar)}")
            
            # Formata as datas para exibição - NOVA LÓGICA:
            # 1. Projetos PRIME/PLUS/INICIO usam DataInicio
            # 2. Projetos TERMINO com status ativo usam VencimentoEm
            # 3. Projetos TERMINO já finalizados usam DataTermino
            # 4. Projetos ENGAJAMENTO usam VencimentoEm + 30 dias
            
            # Inicializa a coluna de data formatada
            projetos_para_faturar['DataFaturamento'] = None
            
            # Caso 1: PRIME/PLUS/INICIO usam DataInicio
            mask_inicio = projetos_para_faturar['Faturamento'].isin(['PRIME', 'PLUS', 'INICIO'])
            if mask_inicio.any():
                mask_inicio_valido = mask_inicio & pd.notna(projetos_para_faturar['DataInicio'])
                if mask_inicio_valido.any():
                    projetos_para_faturar.loc[mask_inicio_valido, 'DataFaturamento'] = projetos_para_faturar.loc[mask_inicio_valido, 'DataInicio'].dt.strftime('%d/%m/%Y')
                    logger.info(f"Projetos de início com data válida: {mask_inicio_valido.sum()}")
            
            # Caso 2: TERMINO com status não concluído usam VencimentoEm
            mask_termino_ativo = (
                (projetos_para_faturar['Faturamento'] == 'TERMINO') & 
                ~projetos_para_faturar['Status'].isin(['Fechado', 'Resolvido'])
            )
            if mask_termino_ativo.any():
                mask_termino_ativo_valido = mask_termino_ativo & pd.notna(projetos_para_faturar['VencimentoEm'])
                if mask_termino_ativo_valido.any():
                    projetos_para_faturar.loc[mask_termino_ativo_valido, 'DataFaturamento'] = projetos_para_faturar.loc[mask_termino_ativo_valido, 'VencimentoEm'].dt.strftime('%d/%m/%Y')
                    logger.info(f"Projetos TERMINO ativos com data de vencimento válida: {mask_termino_ativo_valido.sum()}")
            
            # Caso 3: TERMINO com status concluído usam DataTermino
            mask_termino_concluido = (
                (projetos_para_faturar['Faturamento'] == 'TERMINO') & 
                projetos_para_faturar['Status'].isin(['Fechado', 'Resolvido'])
            )
            if mask_termino_concluido.any():
                mask_termino_concluido_valido = mask_termino_concluido & pd.notna(projetos_para_faturar['DataTermino'])
                if mask_termino_concluido_valido.any():
                    projetos_para_faturar.loc[mask_termino_concluido_valido, 'DataFaturamento'] = projetos_para_faturar.loc[mask_termino_concluido_valido, 'DataTermino'].dt.strftime('%d/%m/%Y')
                    logger.info(f"Projetos TERMINO concluídos com data de término válida: {mask_termino_concluido_valido.sum()}")
            
            # Caso 4: ENGAJAMENTO usam VencimentoEm + 30 dias
            mask_engajamento = projetos_para_faturar['Faturamento'] == 'ENGAJAMENTO'
            if mask_engajamento.any():
                mask_engajamento_valido = mask_engajamento & pd.notna(projetos_para_faturar['VencimentoEm'])
                if mask_engajamento_valido.any():
                    # Calcula VencimentoEm + 30 dias e formata
                    data_faturamento_engajamento = (projetos_para_faturar.loc[mask_engajamento_valido, 'VencimentoEm'] + pd.Timedelta(days=30)).dt.strftime('%d/%m/%Y')
                    projetos_para_faturar.loc[mask_engajamento_valido, 'DataFaturamento'] = data_faturamento_engajamento
                    logger.info(f"Projetos ENGAJAMENTO com data de vencimento + 30 dias válida: {mask_engajamento_valido.sum()}")
            
            # Atualiza a coluna VencimentoEm para exibição com nossa nova DataFaturamento
            projetos_para_faturar['VencimentoEm'] = projetos_para_faturar['DataFaturamento']
            
            # Adicionar coluna com o tipo de data sendo usada (apenas para debugging)
            projetos_para_faturar['TipoData'] = 'N/D'
            projetos_para_faturar.loc[mask_inicio & pd.notna(projetos_para_faturar['DataFaturamento']), 'TipoData'] = 'Início'
            projetos_para_faturar.loc[mask_termino_ativo & pd.notna(projetos_para_faturar['DataFaturamento']), 'TipoData'] = 'Vencimento'
            projetos_para_faturar.loc[mask_termino_concluido & pd.notna(projetos_para_faturar['DataFaturamento']), 'TipoData'] = 'Término'
            projetos_para_faturar.loc[mask_engajamento & pd.notna(projetos_para_faturar['DataFaturamento']), 'TipoData'] = 'Engajamento+30'
            
            # Seleciona e renomeia as colunas necessárias
            colunas = ['Projeto', 'Squad', 'Account Manager', 'Faturamento', 'Status', 'VencimentoEm', 'TipoData']
            colunas_existentes = [col for col in colunas if col in projetos_para_faturar.columns]
            projetos_formatados = projetos_para_faturar[colunas_existentes].copy()
            
            # Preenche campos ausentes
            for col in colunas:
                if col not in projetos_formatados.columns:
                    projetos_formatados[col] = 'N/D'
            
            # Garantir que Squad não tenha valores nulos
            if 'Squad' in projetos_formatados.columns:
                projetos_formatados['Squad'] = projetos_formatados['Squad'].fillna('Em Planejamento - PMO')
                projetos_formatados['Squad'] = projetos_formatados['Squad'].replace({'nan': 'Em Planejamento - PMO', '': 'Em Planejamento - PMO', 'NÃO DEFINIDO': 'Em Planejamento - PMO'})
            
            result = projetos_formatados.replace({np.nan: None}).to_dict('records')
            logger.info(f"Retornando {len(result)} projetos para faturar")
            return result
            
        except Exception as e:
            logger.error(f"Erro ao obter projetos para faturar: {str(e)}")
            return []

    def _formatar_projetos(self, projetos):
        """Formata dados dos projetos para retorno"""
        try:
            # Verifica se 'Numero' existe, se não, tenta com 'Número'
            numero_field = 'Numero' if 'Numero' in projetos.columns else ('Número' if 'Número' in projetos.columns else None)
            
            result = []
            for _, row in projetos.iterrows():
                projeto_dict = {
                    'numero': str(row[numero_field]) if numero_field and pd.notna(row[numero_field]) else '',
                    'projeto': row['Projeto'],
                    'status': row['Status'],
                    'squad': row['Squad'],
                    'data_inicio': row['DataInicio'].strftime('%d/%m/%Y') if pd.notnull(row['DataInicio']) else '',
                    'data_vencimento': row['VencimentoEm'].strftime('%d/%m/%Y') if pd.notnull(row['VencimentoEm']) else '',
                    'conclusao': float(row['Conclusao']) if pd.notnull(row['Conclusao']) else 0.0,
                    'horas_restantes': float(row['HorasRestantes']) if pd.notnull(row['HorasRestantes']) else 0.0,
                    'horas_trabalhadas': float(row['HorasTrabalhadas']) if pd.notnull(row['HorasTrabalhadas']) else 0.0,
                    'motivo': row['Motivo'] if 'Motivo' in row and pd.notnull(row['Motivo']) else ''
                }
                result.append(projeto_dict)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Erro ao formatar projetos: {str(e)}")
            return []

    def processar_gerencial(self, dados, squad_filtro=None, faturamento_filtro=None):
        """
        Processa dados para o dashboard gerencial
        
        Args:
            dados: DataFrame com os dados dos projetos
            squad_filtro: Filtro de squad aplicado na rota (se houver)
            faturamento_filtro: Filtro de faturamento aplicado na rota (se houver)
        """
        try:
            logger.info(f"[Burn Rate Debug] Parâmetros recebidos - squad_filtro: '{squad_filtro}', faturamento_filtro: '{faturamento_filtro}'")
            
            # Validação inicial
            if dados.empty:
                logger.warning("DataFrame vazio recebido para processamento")
                return self.criar_estrutura_vazia()

            # Cria cópia dos dados para evitar modificações no original
            dados_limpos = dados.copy()
            
            # --- PRÉ-PROCESSAMENTO DO TEMPO TRABALHADO ---
            if 'Tempo trabalhado' in dados_limpos.columns:
                # Função robusta para conversão de horas
                def converter_horas(time_str):
                    try:
                        # Remove espaços e divide em componentes
                        parts = str(time_str).strip().split(':')
                        # Garante que temos 3 componentes (HH:MM:SS)
                        if len(parts) == 3:
                            h, m, s = map(int, parts)
                            return h + m/60 + s/3600
                        return 0.0
                    except (ValueError, AttributeError):
                        return 0.0
                
                # Aplica conversão e verifica resultados
                dados_limpos['HorasTrabalhadas'] = dados_limpos['Tempo trabalhado'].apply(converter_horas)
                
                # Debug: Verifique a conversão
                logger.debug(f"Total horas convertidas: {dados_limpos['HorasTrabalhadas'].sum():.2f}")
                if not dados_limpos.empty:
                    logger.debug(f"Exemplo de conversão: {dados_limpos['Tempo trabalhado'].iloc[0]} -> {dados_limpos['HorasTrabalhadas'].iloc[0]:.2f}")

            # Calcula métricas básicas
            projetos_ativos = len(dados_limpos[~dados_limpos['Status'].isin(self.status_concluidos)])
            projetos_em_atendimento = len(dados_limpos[
                dados_limpos['Status'].isin(['Em Atendimento', 'Novo'])
            ])
            
            # Adicione logs para debug
            logger.info(f"DEBUG - Card - Total de projetos no dataframe: {len(dados_limpos)}")
            logger.info(f"DEBUG - Card - Valores únicos na coluna Status: {dados_limpos['Status'].unique().tolist()}")
            logger.info(f"DEBUG - Card - Projetos ativos: {projetos_ativos}")
            logger.info(f"DEBUG - Card - Projetos em atendimento: {projetos_em_atendimento}")
            
            # --- CÁLCULO DO BURN RATE ---
            # Determina ano e mês para cálculo
            hoje = pd.Timestamp.now()
            ano_calc = hoje.year
            mes_calc = hoje.month
            
            # Extrai o filtro de squad aplicado na rota (se houver)
            squad_filtro_rota = None
            if squad_filtro and squad_filtro.strip() and squad_filtro != 'Todos':
                squad_filtro_rota = squad_filtro.strip()
                logger.info(f"[Burn Rate] Detectado filtro de squad da rota: {squad_filtro_rota}")
            
            # NOVA LÓGICA: Se há filtro aplicado, calcula Burn Rate baseado nos dados atuais
            # para ser consistente com a Ocupação por Squad
            if squad_filtro_rota:
                logger.info(f"[Burn Rate] Calculando com base nos dados atuais filtrados para squad: {squad_filtro_rota}")
                
                # Filtra dados para o squad específico (excluindo CDB DATA SOLUTIONS)
                dados_burn_atual = dados_limpos[
                    (dados_limpos['Squad'] == squad_filtro_rota) &
                    (~dados_limpos['Status'].isin(self.status_concluidos)) &
                    (~dados_limpos['Especialista'].str.upper().isin(['CDB DATA SOLUTIONS']))
                ].copy()
                
                if not dados_burn_atual.empty and 'HorasRestantes' in dados_burn_atual.columns:
                    # Ajusta horas restantes negativas para 10% do esforço inicial (mesma lógica da ocupação)
                    def ajustar_horas_restantes(row):
                        if row['HorasRestantes'] >= 0:
                            return row['HorasRestantes']
                        else:
                            return 0.10 * row['Horas']
                    
                    dados_burn_atual['HorasRestantesAjustadas'] = dados_burn_atual.apply(ajustar_horas_restantes, axis=1)
                    
                    # Calcula burn rate baseado nas horas restantes ajustadas vs capacidade mensal
                    horas_restantes_squad = dados_burn_atual['HorasRestantesAjustadas'].sum()
                    capacidade_squad = 540  # 540h por squad
                    
                    # Calcula o percentual de ocupação (igual ao cálculo da Ocupação por Squad)
                    burn_rate = round((horas_restantes_squad / capacidade_squad) * 100, 1) if capacidade_squad > 0 else 0.0
                    
                    logger.info(f"[Burn Rate] Squad {squad_filtro_rota}: {horas_restantes_squad:.2f}h restantes de {capacidade_squad}h = {burn_rate}%")
                else:
                    burn_rate = 0.0
                    logger.warning(f"[Burn Rate] Nenhum dado encontrado para squad {squad_filtro_rota}")
            else:
                # Sem filtro específico: calcula baseado nos dados atuais (consistente com Ocupação por Squad)
                logger.info("[Burn Rate] Calculando média geral com base nos dados atuais")
                
                # Filtra dados ativos (excluindo CDB DATA SOLUTIONS e PMO)
                dados_burn_geral = dados_limpos[
                    (~dados_limpos['Status'].isin(self.status_concluidos)) &
                    (dados_limpos['Squad'] != 'Em Planejamento - PMO') &
                    (~dados_limpos['Especialista'].str.upper().isin(['CDB DATA SOLUTIONS']))
                ].copy()
                
                if not dados_burn_geral.empty and 'HorasRestantes' in dados_burn_geral.columns:
                    # Ajusta horas restantes negativas para 10% do esforço inicial (mesma lógica da ocupação)
                    def ajustar_horas_restantes_geral(row):
                        if row['HorasRestantes'] >= 0:
                            return row['HorasRestantes']
                        else:
                            return 0.10 * row['Horas']
                    
                    dados_burn_geral['HorasRestantesAjustadas'] = dados_burn_geral.apply(ajustar_horas_restantes_geral, axis=1)
                    
                    # Calcula burn rate baseado nas horas restantes ajustadas vs capacidade total
                    horas_restantes_total = dados_burn_geral['HorasRestantesAjustadas'].sum()
                    
                    # Calcula capacidade total baseada nos squads presentes (excluindo PMO)
                    squads_ativos = dados_burn_geral['Squad'].unique()
                    num_squads_ativos = len(squads_ativos)
                    capacidade_total = num_squads_ativos * 540  # 540h por squad
                    
                    # Calcula o percentual de ocupação geral
                    burn_rate = round((horas_restantes_total / capacidade_total) * 100, 1) if capacidade_total > 0 else 0.0
                    
                    logger.info(f"[Burn Rate] Média geral: {horas_restantes_total:.2f}h restantes de {capacidade_total}h ({num_squads_ativos} squads) = {burn_rate}%")
                    logger.info(f"[Burn Rate] Squads considerados: {list(squads_ativos)}")
                else:
                    burn_rate = 0.0
                    logger.warning("[Burn Rate] Nenhum dado encontrado para cálculo da média geral")

            # Calcula o Burn Rate Projetado usando o valor mensal como base
            burn_rate_projetado = 0.0
            # ... (lógica de projeção removida, como decidido anteriormente) ...
            logger.warning("[Burn Rate Mensal] Projeção removida. Dados históricos não suportam projeção intra-mês.")

            # --- FIM CÁLCULO DO BURN RATE ---

            # --- Métricas de projetos para faturar (CORRIGIDO INDENTAÇÃO) ---
            hoje_fatura = pd.Timestamp.now()
            mes_atual = hoje_fatura.month
            ano_atual = hoje_fatura.year
            
            # FILTRO: Exclui projetos com especialista CDB DATA SOLUTIONS para cálculo do contador
            dados_faturamento = dados_limpos.copy()
            if 'Especialista' in dados_faturamento.columns:
                dados_antes = len(dados_faturamento)
                dados_faturamento = dados_faturamento[~dados_faturamento['Especialista'].str.upper().isin(['CDB DATA SOLUTIONS'])]
                dados_depois = len(dados_faturamento)
                logger.info(f"[Contador] Filtro CDB DATA SOLUTIONS: {dados_antes} → {dados_depois} (excluídos: {dados_antes - dados_depois})")
            
            # NOVA LÓGICA PARA CALCULAR PROJETOS PARA FATURAR
            # Condição para faturar no início (PRIME, PLUS, INICIO)
            cond_inicio = (
                dados_faturamento['Faturamento'].isin(['PRIME', 'PLUS', 'INICIO']) &
                (dados_faturamento['DataInicio'].dt.month == mes_atual) &
                (dados_faturamento['DataInicio'].dt.year == ano_atual)
            )
            
            # Condição para faturar no término - APENAS TERMINO (não ENGAJAMENTO)
            cond_termino = (
                (dados_faturamento['Faturamento'] == 'TERMINO') &
                (
                    # Verifica se a data prevista (VencimentoEm) é no mês atual para projetos em andamento
                    ((~dados_faturamento['Status'].isin(['Fechado', 'Resolvido'])) & 
                     (dados_faturamento['VencimentoEm'].dt.month == mes_atual) & 
                     (dados_faturamento['VencimentoEm'].dt.year == ano_atual)) |
                    # OU se a data de término (DataTermino) é no mês atual para projetos concluídos
                    ((dados_faturamento['Status'].isin(['Fechado', 'Resolvido'])) & 
                     (dados_faturamento['DataTermino'].dt.month == mes_atual) & 
                     (dados_faturamento['DataTermino'].dt.year == ano_atual))
                )
            )
            
            # Condição especial para ENGAJAMENTO - VencimentoEm + 30 dias no mês atual
            dados_engajamento = dados_faturamento[dados_faturamento['Faturamento'] == 'ENGAJAMENTO'].copy()
            if not dados_engajamento.empty:
                # Verifica se a data de faturamento está no mês atual
                cond_engajamento = (
                    (dados_faturamento['Faturamento'] == 'ENGAJAMENTO') &
                    (dados_faturamento['VencimentoEm'].notna()) &  # Garante que tem data de vencimento
                    ((dados_faturamento['VencimentoEm'] + pd.Timedelta(days=30)).dt.month == mes_atual) &
                    ((dados_faturamento['VencimentoEm'] + pd.Timedelta(days=30)).dt.year == ano_atual)
                )
                logger.info(f"[Contador] Projetos ENGAJAMENTO com VencimentoEm + 30 dias no mês atual: {cond_engajamento.sum()}")
            else:
                cond_engajamento = pd.Series([False] * len(dados_faturamento), index=dados_faturamento.index)
                logger.info("[Contador] Nenhum projeto com faturamento ENGAJAMENTO encontrado")
            
            # Filtra projetos para faturar (exclui FTOP)
            projetos_para_faturamento_df = dados_faturamento[
                (cond_inicio | cond_termino | cond_engajamento) & 
                (dados_faturamento['Faturamento'] != 'FTOP')
            ]
            
            # Número de projetos para faturar
            projetos_para_faturar_count = len(projetos_para_faturamento_df)
            
            # Registra no log para debug
            logger.info(f"[Contador Mensal] Total de projetos para faturar (nova lógica com ENGAJAMENTO): {projetos_para_faturar_count}")
            logger.info(f"[Contador Mensal] Breakdown: INÍCIO={cond_inicio.sum()}, TERMINO={cond_termino.sum()}, ENGAJAMENTO={cond_engajamento.sum()}")

            # Métricas avançadas (Passa dados_limpos originais)
            metricas_avancadas = self.calcular_metricas_avancadas(dados_limpos)

            # Prepara resultado final
            resultado = {
                'metricas': {
                    'projetos_ativos': projetos_ativos,
                    'projetos_em_atendimento': projetos_em_atendimento,
                    'burn_rate': burn_rate,
                    'burn_rate_projetado': burn_rate_projetado,
                    'projetos_para_faturar': projetos_para_faturar_count, # Usa a contagem
                    'projetos_criticos_count': len(self.obter_projetos_criticos(dados_limpos)),
                    **metricas_avancadas # Inclui as métricas avançadas
                },
                'projetos_criticos': self.obter_projetos_criticos(dados_limpos),
                'projetos_por_squad': dados_limpos[~dados_limpos['Status'].isin(self.status_concluidos)]
                                    .groupby('Squad').size().to_dict(),
                'projetos_por_faturamento': dados_limpos[~dados_limpos['Status'].isin(self.status_concluidos)]
                                        .groupby('Faturamento').size().to_dict(),
                'squads_disponiveis': sorted(dados_limpos['Squad'].dropna().unique().tolist()),
                'faturamentos_disponiveis': sorted(dados_limpos['Faturamento'].dropna().unique().tolist())
            }
            
            
            logger.info(f"Métricas calculadas - Burn Rate: {burn_rate}%, Projetado: {burn_rate_projetado}%")
            return resultado
            
        except Exception as e:
            logger.error(f"Erro no processamento gerencial: {str(e)}", exc_info=True)
            return self.criar_estrutura_vazia()

    def criar_estrutura_vazia(self):
        """Retorna uma estrutura vazia padrão"""
        return {
            'metricas': {
                'projetos_ativos': 0,
                'projetos_em_atendimento': 0,
                'burn_rate': 0.0,
                'projetos_para_faturar': 0,
                'projetos_criticos_count': 0
            },
            'projetos_criticos': [],
            'projetos_por_squad': {},
            'projetos_por_faturamento': {},
            'squads_disponiveis': [],
            'faturamentos_disponiveis': [],
            'ocupacao_squads': []
        }

    def calcular_metricas_avancadas(self, dados):
        """Calcula métricas gerenciais avançadas"""
        try:
            metricas = {}
            # Configurações de capacidade por squad
            HORAS_POR_PESSOA = 180  # horas/mês
            PESSOAS_POR_SQUAD = 3  # pessoas por squad
            CAPACIDADE_TOTAL = HORAS_POR_PESSOA * PESSOAS_POR_SQUAD  # 540 horas por squad
            
            # Preparar dados base para cálculos
            dados_base = dados.copy()
            
            # 1. Primeiro filtramos especialistas da CDB DATA SOLUTIONS (antes de qualquer outro filtro)
            # Isso garante que não incluímos projetos da CDB DATA SOLUTIONS no cálculo
            if 'Especialista' in dados_base.columns:
                # Utilizamos upper para garantir que filtraremos independente de case
                dados_base = dados_base[~dados_base['Especialista'].str.upper().isin(['CDB DATA SOLUTIONS'])]
                logger.info(f"Projetos após filtrar Especialista CDB DATA SOLUTIONS: {len(dados_base)}")
            
            # 2. Filtra apenas projetos ativos
            # Removido filtro por Squad CDB DATA SOLUTIONS, pois já filtramos pelo Especialista
            dados_calc = dados_base[
                (~dados_base['Status'].isin(self.status_concluidos))
                # Removido: & (~dados_base['Squad'].str.upper().isin(['CDB DATA SOLUTIONS']))
            ].copy()
            
            # Adiciona logs detalhados para depuração, especialmente para DATA E POWER
            data_power_projetos = dados_calc[dados_calc['Squad'] == 'DATA E POWER']
            if not data_power_projetos.empty:
                logger.info(f"Encontrados {len(data_power_projetos)} projetos para o squad DATA E POWER:")
                for _, projeto in data_power_projetos.iterrows():
                    logger.info(f"  Projeto: {projeto.get('Projeto', 'N/A')}")
                    logger.info(f"    Status: {projeto.get('Status', 'N/A')}")
                    logger.info(f"    Horas Originais: {projeto.get('Horas', 0.0)}")
                    logger.info(f"    Horas Trabalhadas: {projeto.get('HorasTrabalhadas', 0.0)}")
                    logger.info(f"    Horas Restantes: {projeto.get('HorasRestantes', 0.0)}")
                    logger.info(f"    Especialista: {projeto.get('Especialista', 'N/A')}")
            
            # Ajusta horas restantes: para negativas, usa 10% do esforço inicial
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
            
            dados_calc['HorasRestantesAjustadas'] = dados_calc.apply(ajustar_horas_restantes, axis=1)
            
            # Separa projetos em planejamento
            planejamento_pmo = dados_calc[dados_calc['Squad'] == 'Em Planejamento - PMO'].copy()
            dados_squads = dados_calc[dados_calc['Squad'] != 'Em Planejamento - PMO'].copy()
            
            # Calcula horas totais em planejamento
            total_horas_planejamento = planejamento_pmo['HorasRestantesAjustadas'].sum() if not planejamento_pmo.empty else 0
            total_projetos_planejamento = len(planejamento_pmo)
            
            # Adiciona as métricas de planejamento
            metricas['projetos_planejamento'] = total_projetos_planejamento
            metricas['horas_planejamento'] = round(total_horas_planejamento, 1)
            
            # Lista para armazenar resultado da ocupação dos squads
            resultado_ocupacao_squads = []
            
            # Ocupação por Squad (apenas squads regulares)
            if 'Squad' in dados_squads.columns and not dados_squads.empty:
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
                    resultado_ocupacao_squads.append(squad_info)
            
            # Adiciona linha para Em Planejamento - PMO se houver projetos
            if total_projetos_planejamento > 0:
                # PMO tem capacidade de apenas 1 pessoa (180 horas), não 3 pessoas
                CAPACIDADE_PMO = HORAS_POR_PESSOA  # 180 horas (1 pessoa)
                
                # Calcula capacidade utilizada para PMO
                capacidade_utilizada_pmo = (
                    (total_horas_planejamento / CAPACIDADE_PMO) * 100
                ).round(1) if CAPACIDADE_PMO > 0 else 0
                
                # Calcula horas disponíveis para PMO
                horas_disponiveis_pmo = (
                    CAPACIDADE_PMO - total_horas_planejamento
                ).round(1) if total_horas_planejamento <= CAPACIDADE_PMO else 0
                
                # Prepara os dados do PMO
                projetos_output_pmo = planejamento_pmo[['Projeto', 'Status', 'HorasRestantes', 'Conclusao']].copy()
                projetos_output_pmo['HorasRestantesAjustadas'] = planejamento_pmo['HorasRestantesAjustadas']
                
                pmo_info = {
                    'nome': 'Em Planejamento - PMO',
                    'horas_restantes': round(total_horas_planejamento, 1),
                    'total_projetos': total_projetos_planejamento,
                    'percentual_ocupacao': 0,  # Não calculamos percentual para planejamento
                    'tem_horas_negativas': False,
                    'capacidade_utilizada': capacidade_utilizada_pmo,
                    'horas_disponiveis': horas_disponiveis_pmo,
                    'projetos': projetos_output_pmo.to_dict('records')
                }
                resultado_ocupacao_squads.append(pmo_info)
            
            # Ordena por horas restantes (decrescente)
            resultado_ocupacao_squads = sorted(resultado_ocupacao_squads, key=lambda x: x['horas_restantes'], reverse=True)
            
            # Adiciona o resultado de ocupação de squads às métricas
            metricas['ocupacao_squads'] = resultado_ocupacao_squads
            
            # Cria dicionário de horas disponíveis (compatibilidade com código legado)
            horas_disponiveis_dict = {}
            for squad_info in resultado_ocupacao_squads:
                if squad_info['nome'] != 'Em Planejamento - PMO':
                    horas_disponiveis_dict[squad_info['nome']] = squad_info['horas_disponiveis']
            
            metricas['horas_disponiveis'] = horas_disponiveis_dict
            
            # Calcula métricas de Performance de Entregas
            self._calcular_metricas_performance(dados_base, metricas)
            
            return metricas
        except Exception as e:
            logger.error(f"Erro ao calcular métricas avançadas: {str(e)}")
            return {}
            
    def _calcular_metricas_performance(self, dados, metricas):
        """Calcula métricas de Performance de Entregas (Taxa de Sucesso e Tempo Médio)"""
        try:
            # Verifica se os dados são válidos
            if dados.empty:
                logger.warning("DataFrame vazio ao calcular métricas de performance")
                metricas['taxa_sucesso'] = 0
                metricas['tempo_medio_geral'] = 0.0
                return
                
            # Log inicial dos dados
            logger.info("=== DIAGNÓSTICO DE DADOS ===")
            logger.info(f"Total de projetos no DataFrame: {len(dados)}")
            logger.info(f"Colunas disponíveis: {dados.columns.tolist()}")
            logger.info(f"Status únicos encontrados: {dados['Status'].unique().tolist()}")
            
            # Log das datas antes da conversão
            logger.info("=== AMOSTRA DE DATAS ANTES DA CONVERSÃO ===")
            for coluna in ['DataInicio', 'DataTermino', 'VencimentoEm']:
                if coluna in dados.columns:
                    logger.info(f"{coluna} - Primeiros 5 valores: {dados[coluna].head().tolist()}")
            
            # Converte colunas de data para datetime
            for coluna in ['DataInicio', 'DataTermino', 'VencimentoEm']:
                if coluna in dados.columns:
                    dados[coluna] = pd.to_datetime(dados[coluna], errors='coerce')
                    # Log após conversão
                    logger.info(f"=== {coluna} após conversão - Primeiros 5 valores: {dados[coluna].head().tolist()}")
            
            # Período de análise fixo: Q4 FY25 (1/4/2025 a 30/6/2025)
            inicio_periodo = datetime(2025, 4, 1)
            fim_periodo = datetime(2025, 6, 30)
            
            logger.info("=== PERÍODO DE ANÁLISE ===")
            logger.info(f"Início: {inicio_periodo}")
            logger.info(f"Fim: {fim_periodo}")
            
            # Log de projetos com status de conclusão
            projetos_fechados = dados[dados['Status'].isin(['Fechado', 'Resolvido'])]
            logger.info(f"\nTotal de projetos fechados/resolvidos (geral): {len(projetos_fechados)}")
            if not projetos_fechados.empty:
                logger.info("Amostra de projetos fechados:")
                for _, proj in projetos_fechados.head().iterrows():
                    logger.info(f"Projeto: {proj['Projeto']}")
                    logger.info(f"Status: {proj['Status']}")
                    logger.info(f"Data Término: {proj['DataTermino']}")
                    logger.info(f"Data Vencimento: {proj['VencimentoEm']}")
                    logger.info("---")
            
            # 1. Filtra todos os projetos concluídos no período
            projetos_concluidos = dados[
                (dados['Status'].isin(['Fechado', 'Resolvido'])) &
                (pd.notna(dados['DataTermino'])) &
                (dados['DataTermino'] >= inicio_periodo) &
                (dados['DataTermino'] <= fim_periodo)
            ]
            
            logger.info("\n=== PROJETOS CONCLUÍDOS NO PERÍODO ===")
            logger.info(f"Total: {len(projetos_concluidos)}")
            if not projetos_concluidos.empty:
                logger.info("Detalhes dos projetos concluídos:")
                for _, proj in projetos_concluidos.iterrows():
                    logger.info(f"Projeto: {proj['Projeto']}")
                    logger.info(f"Status: {proj['Status']}")
                    logger.info(f"Data Término: {proj['DataTermino']}")
                    logger.info(f"Data Vencimento: {proj['VencimentoEm']}")
                    logger.info("---")
            
            # 2. Filtra projetos com vencimento no período
            projetos_previstos = dados[
                (pd.notna(dados['VencimentoEm'])) &
                (dados['VencimentoEm'] >= inicio_periodo) &
                (dados['VencimentoEm'] <= fim_periodo)
            ]
            
            logger.info("\n=== PROJETOS PREVISTOS PARA O PERÍODO ===")
            logger.info(f"Total: {len(projetos_previstos)}")
            if not projetos_previstos.empty:
                logger.info("Detalhes dos projetos previstos:")
                for _, proj in projetos_previstos.iterrows():
                    logger.info(f"Projeto: {proj['Projeto']}")
                    logger.info(f"Status: {proj['Status']}")
                    logger.info(f"Data Vencimento: {proj['VencimentoEm']}")
                    logger.info("---")
            
            # 3. Identifica projetos entregues NO MÊS PREVISTO (e dentro do período Q4)
            # Filtra projetos concluídos onde o mês/ano de término == mês/ano de vencimento
            entregues_mes_previsto = projetos_concluidos[
                (projetos_concluidos['DataTermino'].dt.year == projetos_concluidos['VencimentoEm'].dt.year) &
                (projetos_concluidos['DataTermino'].dt.month == projetos_concluidos['VencimentoEm'].dt.month)
            ]
            
            logger.info("\n=== PROJETOS ENTREGUES NO MÊS PREVISTO ===") # Log Atualizado
            logger.info(f"Total: {len(entregues_mes_previsto)}")
            if not entregues_mes_previsto.empty:
                logger.info("Detalhes dos projetos entregues no mês previsto:")
                for _, proj in entregues_mes_previsto.iterrows():
                    logger.info(f"Projeto: {proj['Projeto']}")
                    logger.info(f"Data Término: {proj['DataTermino']}")
                    logger.info(f"Data Vencimento: {proj['VencimentoEm']}")
                    logger.info("---")
            
            # 4. Calcula métricas
            total_previstos = len(projetos_previstos)
            total_concluidos = len(projetos_concluidos)
            total_entregues_mes_previsto = len(entregues_mes_previsto) # Usa a nova contagem
            
            if total_previstos > 0:
                # Usa a nova contagem no numerador
                taxa_sucesso = round((total_entregues_mes_previsto / total_previstos) * 100)
            else:
                taxa_sucesso = 0
            
            # Calcula tempo médio de entrega (agora usa entregues_mes_previsto como base? Ou mantém concluidos? Manter concluidos parece mais geral)
            # *** Decisão: Manter o cálculo do tempo médio baseado nos projetos concluídos no prazo original ***
            # *** Isso evita penalizar o tempo médio por entregas no mês certo, mas no último dia vs primeiro.***
            entregues_no_prazo_para_tempo_medio = projetos_concluidos[
                projetos_concluidos['DataTermino'] <= projetos_concluidos['VencimentoEm']
            ]
            if not entregues_no_prazo_para_tempo_medio.empty:
                entregues_no_prazo_para_tempo_medio['duracao_dias'] = (
                    entregues_no_prazo_para_tempo_medio['DataTermino'] - entregues_no_prazo_para_tempo_medio['DataInicio']
                ).dt.days
                
                # Remove outliers
                entregues_validos = entregues_no_prazo_para_tempo_medio[
                    (entregues_no_prazo_para_tempo_medio['duracao_dias'] >= 0) &
                    (entregues_no_prazo_para_tempo_medio['duracao_dias'] <= 365)
                ]
                
                tempo_medio = round(entregues_validos['duracao_dias'].mean(), 1) if not entregues_validos.empty else 0.0
            else:
                tempo_medio = 0.0
            
            # Adiciona as métricas
            metricas['taxa_sucesso'] = taxa_sucesso
            metricas['tempo_medio_geral'] = tempo_medio
            
            # Adiciona informações do trimestre (ajustado para usar a nova métrica)
            metricas['quarter_info'] = {
                'quarter': 'Q4 - Ano Fiscal Microsoft',
                'inicio': inicio_periodo.strftime('%d/%m/%Y'),
                'fim': fim_periodo.strftime('%d/%m/%Y'),
                'total_projetos_previstos': total_previstos,
                'projetos_concluidos': total_concluidos,
                'projetos_entregues_mes_previsto': total_entregues_mes_previsto, # Adicionado/Renomeado
                'projetos_em_andamento': total_previstos - total_concluidos # Lógica mantida
            }
            
            logger.info("\n=== MÉTRICAS FINAIS ===")
            logger.info(f"Taxa de Sucesso (Concluídos no Mês Previsto / Previstos): {taxa_sucesso}%") # Log atualizado
            logger.info(f"Tempo Médio (baseado nos entregues no prazo original): {tempo_medio} dias") # Log atualizado
            logger.info(f"Total Previstos (no período): {total_previstos}")
            logger.info(f"Total Concluídos (no período): {total_concluidos}")
            # logger.info(f"Total Entregues no Prazo (no período): {total_no_prazo}") # Log antigo removido
            logger.info(f"Total Entregues no Mês Previsto (no período): {total_entregues_mes_previsto}") # Log novo
            logger.info(f"Conteúdo final de quarter_info: {metricas['quarter_info']}") # Log final
                
        except Exception as e:
            logger.error(f"Erro ao calcular métricas de performance: {str(e)}", exc_info=True)
            metricas['taxa_sucesso'] = 0
            metricas['tempo_medio_geral'] = 0.0

    def validar_dados(self, dados):
        """Valida a estrutura básica dos dados"""
        if not isinstance(dados, pd.DataFrame):
            raise ValueError("Dados devem ser um DataFrame")
        if dados.empty:
            raise ValueError("DataFrame vazio recebido")
            
        # Verifica colunas obrigatórias
        colunas_faltantes = [col for col in COLUNAS_OBRIGATORIAS if col not in dados.columns]
        if colunas_faltantes:
            logger.warning(f"Colunas obrigatórias não encontradas: {', '.join(colunas_faltantes)}")
            # Adiciona colunas faltantes com valores padrão
            for col in colunas_faltantes:
                if col in COLUNAS_NUMERICAS:
                    dados[col] = 0.0
                else:
                    dados[col] = 'NÃO DEFINIDO'
                logger.info(f"Coluna '{col}' adicionada com valor padrão")
            
        # Verifica tipos de dados
        for col in COLUNAS_NUMERICAS:
            if col in dados.columns:
                if not pd.api.types.is_numeric_dtype(dados[col]):
                    logger.warning(f"Coluna {col} não é numérica. Tentando converter...")
                    try:
                        if dados[col].dtype == 'object':
                            dados[col] = dados[col].str.replace(',', '.', regex=False)
                        dados[col] = pd.to_numeric(dados[col], errors='coerce')
                        logger.info(f"Coluna {col} convertida para numérica com sucesso")
                    except Exception as e:
                        logger.error(f"Erro ao converter coluna {col} para numérica: {str(e)}")
                        dados[col] = 0.0
        
        # Verifica valores nulos em colunas críticas
        for col in COLUNAS_OBRIGATORIAS:
            if col in dados.columns:
                nulos = dados[col].isna().sum()
                if nulos > 0:
                    logger.warning(f"Encontrados {nulos} valores nulos na coluna {col}")
                    if col in COLUNAS_NUMERICAS:
                        dados[col] = dados[col].fillna(0.0)
                    else:
                        dados[col] = dados[col].fillna('NÃO DEFINIDO')
            
        return True

    def calcular_alertas(self, dados):
        """Calcula alertas críticos baseado em indicadores-chave"""
        alertas = []
        
        # Regras de alerta prioritárias (nível CRÍTICO)
        if dados.empty:
            alertas.append({
                'tipo': 'critico',
                'codigo': 'ALERTA_001',
                'titulo': 'Dados não encontrados',
                'mensagem': 'Nenhum projeto encontrado com os filtros atuais',
                'icone': 'bi-database-exclamation',
                'prioridade': 1
            })
            return alertas  # Retorna imediatamente pois os outros checks não fazem sentido
        
        total_projetos = len(dados)
        
        # 1. Alertas de SLA (Status)
        projetos_atrasados = dados[dados['Status'] == 'Atrasado']
        if len(projetos_atrasados) > 0:
            alertas.append({
                'tipo': 'critico',
                'codigo': 'ALERTA_101',
                'titulo': 'Projetos atrasados',
                'mensagem': f"{len(projetos_atrasados)} projeto(s) com status 'Atrasado'",
                'icone': 'bi-clock-history',
                'prioridade': 2,
                'detalhes': projetos_atrasados[['Projeto', 'Squad']].to_dict('records')
            })
        
        # 2. Alertas de Alocação
        projetos_sem_squad = dados[dados['Squad'] == 'Em Planejamento - PMO']
        if len(projetos_sem_squad) > 0:
            alertas.append({
                'tipo': 'alocacao',
                'codigo': 'ALERTA_102',
                'titulo': 'Projetos em planejamento',
                'mensagem': f"{len(projetos_sem_squad)} projeto(s) em fase de planejamento aguardando alocação",
                'icone': 'bi-people',
                'prioridade': 3,
                'detalhes': projetos_sem_squad[['Projeto', 'Account Manager']].to_dict('records')
            })
        
        # 3. Alertas de Horas (Micro)
        if 'HorasRestantes' in dados.columns:
            projetos_sem_horas = dados[dados['HorasRestantes'] <= 0]
            if len(projetos_sem_horas) > 0:
                alertas.append({
                    'tipo': 'horas',
                    'codigo': 'ALERTA_103',
                    'titulo': 'Saldo de horas esgotado',
                    'mensagem': f"{len(projetos_sem_horas)} projeto(s) com saldo zero ou negativo de horas",
                    'icone': 'bi-hourglass-bottom',
                    'prioridade': 4,
                    'detalhes': projetos_sem_horas[['Projeto', 'HorasRestantes']].to_dict('records')
                })
        
        # 4. Alertas de Conclusão (Progresso)
        if 'Conclusao' in dados.columns:
            projetos_estagnados = dados[(dados['Conclusao'] < 50) & 
                                       (dados['Status'] == 'Ativo')]
            if len(projetos_estagnados) > 0:
                alertas.append({
                    'tipo': 'progresso',
                    'codigo': 'ALERTA_104',
                    'titulo': 'Projetos estagnados',
                    'mensagem': f"{len(projetos_estagnados)} projeto(s) ativos com menos de 50% de conclusão",
                    'icone': 'bi-speedometer',
                    'prioridade': 5,
                    'detalhes': projetos_estagnados[['Projeto', 'Conclusao']].to_dict('records')
                })
        
        # 5. Alertas de Faturamento (Financeiro)
        if 'Faturamento' in dados.columns:
            projetos_para_faturar = dados[dados['Faturamento'].isin(['PRIME', 'PLUS', 'INICIO'])]
            if len(projetos_para_faturar) > 0:
                alertas.append({
                    'tipo': 'financeiro',
                    'codigo': 'ALERTA_105',
                    'titulo': 'Projetos para faturar',
                    'mensagem': f"{len(projetos_para_faturar)} projeto(s) com faturamento PRIME/PLUS/INICIO",
                    'icone': 'bi-cash-stack',
                    'prioridade': 6,
                    'detalhes': projetos_para_faturar[['Projeto', 'Faturamento']].to_dict('records')
                })
        
        # Ordenar alertas por prioridade
        alertas.sort(key=lambda x: x['prioridade'])
        
        return alertas

    def calcular_faturamento_pendente(self, dados):
        try:
            hoje = datetime.now()
            mes_atual = hoje.month
            ano_atual = hoje.year
            
            # Verifica se as colunas necessárias existem
            colunas_necessarias = ['Faturamento', 'DataInicio', 'DataTermino', 'VencimentoEm', 'Status']
            for coluna in colunas_necessarias:
                if coluna not in dados.columns:
                    logger.warning(f"Coluna {coluna} não encontrada para cálculo de faturamento pendente")
                    return []
            
            # Condição para faturar no início (PRIME, PLUS, INICIO) que começaram neste mês
            cond_inicio = (
                dados['Faturamento'].isin(['PRIME', 'PLUS', 'INICIO']) &
                (dados['DataInicio'].dt.month == mes_atual) &
                (dados['DataInicio'].dt.year == ano_atual)
            )
            
            # Condição para faturar no término (TERMINO e ENGAJAMENTO)
            cond_termino = (
                dados['Faturamento'].isin(['TERMINO', 'ENGAJAMENTO']) &
                (
                    # Verifica se a data prevista (VencimentoEm) é no mês atual para projetos em andamento
                    ((~dados['Status'].isin(['Fechado', 'Resolvido'])) & 
                     (dados['VencimentoEm'].dt.month == mes_atual) & 
                     (dados['VencimentoEm'].dt.year == ano_atual)) |
                    # OU se a data de término (DataTermino) é no mês atual para projetos concluídos
                    ((dados['Status'].isin(['Fechado', 'Resolvido'])) & 
                     (dados['DataTermino'].dt.month == mes_atual) & 
                     (dados['DataTermino'].dt.year == ano_atual))
                )
            )
            
            # Filtra projetos para faturar (exclui FTOP)
            projetos_faturar = dados[
                (cond_inicio | cond_termino) & 
                (dados['Faturamento'] != 'FTOP')
            ].copy()
            
            # Inicializa a coluna de data formatada para exibição
            projetos_faturar['DataFaturamento'] = None
            
            # Caso 1: PRIME/PLUS/INICIO usam DataInicio
            mask_inicio = projetos_faturar['Faturamento'].isin(['PRIME', 'PLUS', 'INICIO'])
            if mask_inicio.any():
                mask_inicio_valido = mask_inicio & pd.notna(projetos_faturar['DataInicio'])
                if mask_inicio_valido.any():
                    projetos_faturar.loc[mask_inicio_valido, 'DataFaturamento'] = projetos_faturar.loc[mask_inicio_valido, 'DataInicio'].dt.strftime('%d/%m/%Y')
            
            # Caso 2: TERMINO/ENGAJAMENTO com status não concluído usam VencimentoEm
            mask_termino_ativo = (
                projetos_faturar['Faturamento'].isin(['TERMINO', 'ENGAJAMENTO']) & 
                ~projetos_faturar['Status'].isin(['Fechado', 'Resolvido'])
            )
            if mask_termino_ativo.any():
                mask_termino_ativo_valido = mask_termino_ativo & pd.notna(projetos_faturar['VencimentoEm'])
                if mask_termino_ativo_valido.any():
                    projetos_faturar.loc[mask_termino_ativo_valido, 'DataFaturamento'] = projetos_faturar.loc[mask_termino_ativo_valido, 'VencimentoEm'].dt.strftime('%d/%m/%Y')
            
            # Caso 3: TERMINO/ENGAJAMENTO com status concluído usam DataTermino
            mask_termino_concluido = (
                projetos_faturar['Faturamento'].isin(['TERMINO', 'ENGAJAMENTO']) & 
                projetos_faturar['Status'].isin(['Fechado', 'Resolvido'])
            )
            if mask_termino_concluido.any():
                mask_termino_concluido_valido = mask_termino_concluido & pd.notna(projetos_faturar['DataTermino'])
                if mask_termino_concluido_valido.any():
                    projetos_faturar.loc[mask_termino_concluido_valido, 'DataFaturamento'] = projetos_faturar.loc[mask_termino_concluido_valido, 'DataTermino'].dt.strftime('%d/%m/%Y')
            
            # Atualiza a coluna VencimentoEm para exibição
            projetos_faturar['VencimentoEm'] = projetos_faturar['DataFaturamento']
            
            # Seleciona e renomeia as colunas necessárias
            colunas = ['Projeto', 'Squad', 'Account Manager', 'Faturamento', 'Status', 'VencimentoEm']
            colunas_existentes = [col for col in colunas if col in projetos_faturar.columns]
            projetos_formatados = projetos_faturar[colunas_existentes].copy()
            
            # Garantir que Squad não tenha valores nulos
            if 'Squad' in projetos_formatados.columns:
                projetos_formatados['Squad'] = projetos_formatados['Squad'].fillna('Em Planejamento - PMO')
                projetos_formatados['Squad'] = projetos_formatados['Squad'].replace({'nan': 'Em Planejamento - PMO', '': 'Em Planejamento - PMO', 'NÃO DEFINIDO': 'Em Planejamento - PMO'})
            
            return projetos_formatados.replace({np.nan: None}).to_dict('records')
            
        except Exception as e:
            logger.error(f"Erro ao calcular faturamento pendente: {str(e)}")
            return []
    
    def obter_metricas_gerencial(self):
        """Retorna métricas gerenciais"""
        try:
            dados = self.carregar_dados()
            if dados.empty:
                return {
                    'projetos_ativos': 0,
                    'projetos_criticos': 0,
                    'projetos_em_atendimento': 0,
                    'projetos_para_faturar': 0,
                    'faturamento_pendente': 0
                }

            self.validar_dados(dados)
            
            # Define o mês e ano atual
            hoje = datetime.now()
            mes_atual = hoje.month
            ano_atual = hoje.year
            
            # Definir status em Title Case (consistente com o processamento que padroniza os status)
            status_concluidos = ['Fechado', 'Encerrado', 'Resolvido', 'Cancelado']
            status_em_atendimento = ['Em Atendimento', 'Novo']
            
            # Projetos ativos (todos que não estão concluídos)
            projetos_ativos = dados[~dados['Status'].isin(status_concluidos)]
            
            # Projetos críticos - usa critérios avançados do método obter_projetos_criticos
            projetos_criticos = self.obter_projetos_criticos(dados)
            
            # Projetos em atendimento
            projetos_em_atendimento = dados[dados['Status'].isin(status_em_atendimento)]
            
            # Condição para faturar no início (PRIME, PLUS, INICIO)
            cond_inicio = (
                dados['Faturamento'].isin(['PRIME', 'PLUS', 'INICIO']) &
                (dados['DataInicio'].dt.month == mes_atual) &
                (dados['DataInicio'].dt.year == ano_atual)
            )
            
            # Condição para faturar no término (TERMINO e ENGAJAMENTO)
            cond_termino = (
                dados['Faturamento'].isin(['TERMINO', 'ENGAJAMENTO']) &
                (
                    # Verifica se a data prevista (VencimentoEm) é no mês atual para projetos em andamento
                    ((~dados['Status'].isin(['Fechado', 'Resolvido'])) & 
                     (dados['VencimentoEm'].dt.month == mes_atual) & 
                     (dados['VencimentoEm'].dt.year == ano_atual)) |
                    # OU se a data de término (DataTermino) é no mês atual para projetos concluídos
                    ((dados['Status'].isin(['Fechado', 'Resolvido'])) & 
                     (dados['DataTermino'].dt.month == mes_atual) & 
                     (dados['DataTermino'].dt.year == ano_atual))
                )
            )
            
            # Filtra projetos para faturar (exclui FTOP)
            projetos_para_faturar = dados[
                (cond_inicio | cond_termino) & 
                (dados['Faturamento'] != 'FTOP')
            ]
            
            # Número de projetos para faturar
            num_projetos_para_faturar = len(projetos_para_faturar)
            
            # Log para debug
            logger.info(f"DEBUG - Total de projetos no dataframe: {len(dados)}")
            logger.info(f"DEBUG - Status concluídos considerados: {status_concluidos}")
            logger.info(f"DEBUG - Status em atendimento considerados: {status_em_atendimento}")
            logger.info(f"DEBUG - Valores únicos na coluna Status: {dados['Status'].unique().tolist()}")
            logger.info(f"DEBUG - Projetos ativos: {len(projetos_ativos)}")
            logger.info(f"DEBUG - Projetos críticos: {len(projetos_criticos)}")
            logger.info(f"DEBUG - Projetos em atendimento: {len(projetos_em_atendimento)}")
            
            metricas = {
                'projetos_ativos': len(projetos_ativos),
                'projetos_criticos': len(projetos_criticos),
                'projetos_em_atendimento': len(projetos_em_atendimento),
                'projetos_para_faturar': num_projetos_para_faturar,
                'faturamento_pendente': num_projetos_para_faturar,  # Mantém compatibilidade com o frontend
                'projetos_criticos_count': len(projetos_criticos)   # Garante que projetos_criticos_count use a mesma contagem
            }
            
            logger.info(f"Métricas gerenciais calculadas: {metricas}")
            return metricas
            
        except Exception as e:
            logger.error(f"Erro ao obter métricas gerenciais: {str(e)}")
            return {
                'projetos_ativos': 0,
                'projetos_criticos': 0,
                'projetos_em_atendimento': 0,
                'projetos_para_faturar': 0,
                'faturamento_pendente': 0,
                'projetos_criticos_count': 0
            }
    
    def teste_projetos_para_faturar(self):
        """Função para testar a obtenção de projetos para faturar"""
        try:
            dados = self.carregar_dados()
            if dados.empty:
                print("Dados vazios!")
                return
                
            # Para testes, vamos forçar a data atual para ver se isso afeta os resultados
            # Comentar esta linha para usar a data atual real
            # hoje = datetime(2025, 4, 11)  # Data dos testes
            hoje = datetime.now()
            print(f"Data de teste: {hoje.strftime('%d/%m/%Y')}")
            print(f"Total de projetos no dataset: {len(dados)}")
            
            # Verificar tipos de faturamento disponíveis
            if 'Faturamento' in dados.columns:
                faturamentos = dados['Faturamento'].value_counts().to_dict()
                print(f"Tipos de faturamento disponíveis: {faturamentos}")
            
            # Verificar projetos por mês de início
            if 'DataInicio' in dados.columns:
                meses_inicio = dados['DataInicio'].dt.month.value_counts().sort_index().to_dict()
                print(f"Distribuição por mês de início: {meses_inicio}")
            
            # Verificar distribuição de meses em DataTermino
            if 'DataTermino' in dados.columns:
                meses_termino = dados['DataTermino'].dt.month.value_counts().sort_index().to_dict()
                print(f"Distribuição por mês de término: {meses_termino}")
            
            # Executar a função que queremos testar
            projetos = self.obter_projetos_para_faturar(dados)
            
            # Exibir resultados
            print(f"\nTotal de projetos para faturar: {len(projetos)}")
            if projetos:
                for i, p in enumerate(projetos):
                    print(f"{i+1}. {p['Projeto']} - {p['Faturamento']} - {p['Status']} - {p['VencimentoEm']}")
            
            return projetos
        except Exception as e:
            print(f"ERRO no teste: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return []
    
    def _carregar_dados_historicos(self, ano, mes):
        """Carrega e processa dados de um arquivo histórico específico (dadosr_apt_mes.csv)."""
        try:
            mes_str = f"{mes:02d}" # Formata mês com zero à esquerda (01, 02, ..., 12)
            # Mapeia número do mês para abreviação de 3 letras em minúsculo
            mes_abrev_map = {1: 'jan', 2: 'fev', 3: 'mar', 4: 'abr', 5: 'mai', 6: 'jun', 
                             7: 'jul', 8: 'ago', 9: 'set', 10: 'out', 11: 'nov', 12: 'dez'}
            mes_abrev = mes_abrev_map.get(mes)
            
            if not mes_abrev:
                logger.error(f"Mês inválido fornecido para dados históricos: {mes}")
                return pd.DataFrame()
                
            nome_arquivo = f"dadosr_apt_{mes_abrev}.csv" # Formato do nome do arquivo
            caminho_historico = self.csv_path.parent / nome_arquivo # Assume que está na mesma pasta 'data'
            
            logger.info(f"Tentando carregar dados históricos de: {caminho_historico}")
            
            if not caminho_historico.is_file():
                logger.error(f"Arquivo histórico CSV não encontrado: {caminho_historico}")
                return pd.DataFrame()
            
            # Lê o CSV histórico (mesmos parâmetros de carregar_dados)
            dados = pd.read_csv(
                caminho_historico, 
                dtype=str, 
                sep=';', 
                encoding='latin1'
            )
            logger.info(f"Arquivo histórico {nome_arquivo} carregado com {len(dados)} linhas.")
            
            # Aplica EXATAMENTE O MESMO pré-processamento de carregar_dados
            # (Conversão de Datas, Números, Tempo, Renomeação, Padronização)
            # --- Copiado e adaptado de carregar_dados --- 
            # 1.2.1 Conversão de Datas
            colunas_data_simples = ['Aberto em', 'Resolvido em', 'Data da última ação']
            # ... (resto do código de conversão de datas igual a carregar_dados) ...
            for col in colunas_data_simples:
                 if col in dados.columns:
                     dados[col] = pd.to_datetime(dados[col], format='%d/%m/%Y', errors='coerce')
                 # else: # Não loga warning para históricos, podem ter colunas diferentes
                 #    logger.warning(f"[Histórico] Coluna de data {col} não encontrada em {nome_arquivo}")
            
            if 'Vencimento em' in dados.columns:
                 dados['Vencimento em_Original'] = dados['Vencimento em']
                 dados['Vencimento em'] = pd.to_datetime(dados['Vencimento em_Original'], format='%d/%m/%Y %H:%M', errors='coerce')
                 mask_nat = dados['Vencimento em'].isna()
                 if mask_nat.any():
                     dados.loc[mask_nat, 'Vencimento em'] = pd.to_datetime(dados.loc[mask_nat, 'Vencimento em_Original'], format='%d/%m/%Y', errors='coerce')
                 # del dados['Vencimento em_Original'] 
            
            # 1.2.2 Conversão Numérica
            if 'Número' in dados.columns:
                 dados['Número'] = pd.to_numeric(dados['Número'], errors='coerce').astype('Int64')
            if 'Esforço estimado' in dados.columns:
                 dados['Esforço estimado'] = dados['Esforço estimado'].str.replace(',', '.', regex=False)
                 dados['Esforço estimado'] = pd.to_numeric(dados['Esforço estimado'], errors='coerce').fillna(0.0)
            else: dados['Esforço estimado'] = 0.0
            if 'Andamento' in dados.columns:
                 dados['Andamento'] = dados['Andamento'].str.rstrip('%').str.replace(',', '.', regex=False)
                 dados['Andamento'] = pd.to_numeric(dados['Andamento'], errors='coerce').fillna(0.0).clip(lower=0, upper=100)
            else: dados['Andamento'] = 0.0
            if 'Tempo trabalhado' in dados.columns:
                 dados['Tempo trabalhado'] = dados['Tempo trabalhado'].apply(self.converter_tempo_para_horas)
            else: dados['Tempo trabalhado'] = 0.0
            
            # 1.3 Renomeação
            rename_map_new_to_old = { ... } # Usar o mesmo mapa de carregar_dados
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
            
            # 1.4 Padronização Final
            if 'Status' in dados.columns: dados['Status'] = dados['Status'].astype(str).str.strip().str.title()
            faturamento_map = { ... } # Usar o mesmo mapa de carregar_dados
            faturamento_map = {
                "PRIME": "PRIME",
                "Descontar do PLUS no inicio do projeto": "PLUS",
                "Faturar no inicio do projeto": "INICIO",
                "Faturar no final do projeto": "TERMINO",
                "Faturado em outro projeto": "FEOP",
                "Faturado em outro projeto.": "FEOP",
                "Engajamento": "ENGAJAMENTO"
            }
            if 'Faturamento' in dados.columns:
                dados['Faturamento'] = dados['Faturamento'].astype(str).str.strip()
                dados['Faturamento_Original'] = dados['Faturamento']
                dados['Faturamento'] = dados['Faturamento'].map(faturamento_map)
                nao_mapeados = dados['Faturamento'].isna()
                if nao_mapeados.any():
                    mask_nan = dados['Faturamento_Original'].isna() | (dados['Faturamento_Original'] == 'nan')
                    if mask_nan.any(): dados.loc[mask_nan, 'Faturamento'] = 'EAN'
                    dados['Faturamento'] = dados['Faturamento'].fillna('NAO_MAPEADO')
                # del dados['Faturamento_Original']
            colunas_texto_padrao = ['Projeto', 'Squad', 'Especialista', 'Account Manager']
            for col in colunas_texto_padrao:
                if col in dados.columns:
                    dados[col] = dados[col].astype(str).str.strip()
                    if col == 'Squad': dados[col] = dados[col].replace({'': 'Em Planejamento - PMO', 'nan': 'Em Planejamento - PMO', 'NÃO DEFINIDO': 'Em Planejamento - PMO'}).fillna('Em Planejamento - PMO')
                    else: dados[col] = dados[col].replace({'': 'NÃO DEFINIDO', 'nan': 'NÃO DEFINIDO'}).fillna('NÃO DEFINIDO')
            
            # Recalcula HorasRestantes (importante após carregar e renomear)
            if 'Horas' in dados.columns and 'HorasTrabalhadas' in dados.columns:
                 dados['HorasRestantes'] = (dados['Horas'] - dados['HorasTrabalhadas']).round(1)
            else: dados['HorasRestantes'] = 0.0
            # --- Fim do código copiado --- 
            
            logger.info(f"Dados históricos de {mes_abrev.upper()}/{ano} processados.")
            return dados

        except Exception as e:
            logger.error(f"Erro ao carregar dados históricos para {ano}-{mes_str}: {str(e)}")
            return pd.DataFrame()
    
    def calcular_burn_rate_mensal(self, ano, mes, squad_filtro=None):
        """Calcula o Burn Rate para um mês específico usando dados históricos."""
        try:
            logger.info(f"[Burn Rate Mensal] Calculando para {mes:02d}/{ano}, filtro squad: '{squad_filtro if squad_filtro else 'Nenhum'}'")
            
            # Carrega dados do mês atual (mês para o qual calculamos o burn rate)
            df_atual = self._carregar_dados_historicos(ano, mes)
            if df_atual.empty:
                logger.warning(f"[Burn Rate Mensal] Não foi possível carregar dados para {mes:02d}/{ano}. Retornando 0.")
                return 0.0, 0.0 # Retorna Burn Rate e Burn Rate Projetado
                
            # Determina o mês/ano anterior
            data_ref = datetime(ano, mes, 1)
            data_anterior = data_ref - timedelta(days=1)
            ano_prev = data_anterior.year
            mes_prev = data_anterior.month
            
            # Carrega dados do mês anterior
            df_prev = self._carregar_dados_historicos(ano_prev, mes_prev)
            if df_prev.empty:
                logger.warning(f"[Burn Rate Mensal] Não foi possível carregar dados do mês anterior ({mes_prev:02d}/{ano_prev}). Calculando com base apenas no mês atual.")
                # Se não há dados anteriores, não podemos calcular a diferença.
                # Poderíamos retornar 0 ou calcular usando o total atual (mas isso seria o cálculo antigo)
                # Vamos retornar 0 por segurança, pois a métrica seria enganosa.
                return 0.0, 0.0

            # Seleciona colunas necessárias para merge e cálculo
            cols_atual = ['Numero', 'Projeto', 'Squad', 'Especialista', 'Status', 'HorasTrabalhadas']
            cols_prev = ['Numero', 'HorasTrabalhadas']
            
            # Garante que as colunas existem
            for col in cols_atual: 
                if col not in df_atual.columns: df_atual[col] = 0 if col == 'HorasTrabalhadas' else ('N/A' if col != 'Numero' else pd.NA)
            for col in cols_prev: 
                if col not in df_prev.columns: df_prev[col] = 0 if col == 'HorasTrabalhadas' else pd.NA
                
            # Renomeia colunas do df_prev para evitar conflito no merge
            df_prev_renamed = df_prev[cols_prev].rename(columns={'HorasTrabalhadas': 'HT_prev'})
            
            # Merge usando 'Numero' como chave (garantir que 'Numero' seja tipo consistente)
            df_atual['Numero'] = df_atual['Numero'].astype(str)
            df_prev_renamed['Numero'] = df_prev_renamed['Numero'].astype(str)
            
            df_merged = pd.merge(df_atual[cols_atual], df_prev_renamed, on='Numero', how='left')
            
            # Calcula Horas Trabalhadas Mensais
            df_merged['HT_prev'] = df_merged['HT_prev'].fillna(0)
            df_merged['HT_mensal'] = df_merged['HorasTrabalhadas'] - df_merged['HT_prev']
            
            # Lida com possíveis valores negativos (pode indicar inconsistência, mas clampamos para 0)
            df_merged['HT_mensal'] = df_merged['HT_mensal'].clip(lower=0)
            
            logger.info(f"[Burn Rate Mensal] {len(df_merged)} projetos após merge.")
            logger.info(f"[Burn Rate Mensal] Amostra HT_mensal: {df_merged['HT_mensal'].head().tolist()}")
            
            # Aplica filtros para cálculo do Burn Rate
            df_burn = df_merged[
                (~df_merged['Status'].isin(self.status_concluidos)) &
                (df_merged['Squad'] != 'Em Planejamento - PMO') &
                (df_merged['Especialista'].str.upper() != 'CDB DATA SOLUTIONS')
            ].copy()
            
            # Aplica filtro de squad se fornecido
            if squad_filtro and squad_filtro != 'Todos':
                df_burn = df_burn[df_burn['Squad'].str.upper() == squad_filtro.upper()]
                logger.info(f"[Burn Rate Mensal] Aplicado filtro para Squad: '{squad_filtro}'. {len(df_burn)} projetos restantes.")
            else:
                 logger.info("[Burn Rate Mensal] Nenhum filtro de squad específico aplicado.")

            if df_burn.empty:
                logger.warning("[Burn Rate Mensal] Nenhum projeto encontrado após filtros. Burn Rate será 0.")
                return 0.0, 0.0
                
            # Calcula horas consumidas e capacidade
            horas_consumidas_mes = df_burn['HT_mensal'].sum()
            squads_presentes = df_burn['Squad'].unique()
            num_squads = len(squads_presentes)
            capacidade_mensal = 540 * num_squads # Assume 540h/squad
            
            logger.info(f"[Burn Rate Mensal] Horas Consumidas (Mensal): {horas_consumidas_mes:.2f}")
            logger.info(f"[Burn Rate Mensal] Squads considerados: {squads_presentes.tolist()}, Num: {num_squads}")
            logger.info(f"[Burn Rate Mensal] Capacidade Mensal: {capacidade_mensal}")
            
            # Calcula Burn Rate Mensal
            burn_rate_mensal = 0.0
            if capacidade_mensal > 0:
                burn_rate_mensal = round((horas_consumidas_mes / capacidade_mensal) * 100, 1)
            else:
                 logger.warning("[Burn Rate Mensal] Capacidade mensal calculada como 0. Burn Rate será 0.")
            
            logger.info(f"[Burn Rate Mensal] Calculado: {burn_rate_mensal}%")

            # Calcula Burn Rate Projetado (usando o mensal como base)
            burn_rate_projetado = 0.0
            # Para projeção, precisamos saber o dia atual *relativo ao mês que calculamos*
            # Se estamos calculando para Abril (mês 4), e hoje é 1 de Maio, o mês de Abril está completo.
            # Se hoje for 15 de Abril, e calculamos para Março, Março está completo.
            # A projeção só faz sentido se calcularmos para o mês *corrente*.
            # VAMOS SIMPLIFICAR: a função retorna o mensal e a projeção é feita em processar_gerencial.
            
            return burn_rate_mensal
            
        except Exception as e:
            logger.error(f"Erro ao calcular Burn Rate Mensal para {mes:02d}/{ano}: {str(e)}", exc_info=True)
            return 0.0 # Retorna 0 em caso de erro

    def criar_estrutura_vazia(self):
        """Retorna uma estrutura vazia padrão"""
        return {
            'metricas': {
                'projetos_ativos': 0,
                'projetos_em_atendimento': 0,
                'burn_rate': 0.0,
                'projetos_para_faturar': 0,
                'projetos_criticos_count': 0
            },
            'projetos_criticos': [],
            'projetos_por_squad': {},
            'projetos_por_faturamento': {},
            'squads_disponiveis': [],
            'faturamentos_disponiveis': [],
            'ocupacao_squads': []
        }

    def calcular_metricas_avancadas(self, dados):
        """Calcula métricas gerenciais avançadas"""
        try:
            metricas = {}
            # Configurações de capacidade por squad
            HORAS_POR_PESSOA = 180  # horas/mês
            PESSOAS_POR_SQUAD = 3  # pessoas por squad
            CAPACIDADE_TOTAL = HORAS_POR_PESSOA * PESSOAS_POR_SQUAD  # 540 horas por squad
            
            # Preparar dados base para cálculos
            dados_base = dados.copy()
            
            # 1. Primeiro filtramos especialistas da CDB DATA SOLUTIONS (antes de qualquer outro filtro)
            # Isso garante que não incluímos projetos da CDB DATA SOLUTIONS no cálculo
            if 'Especialista' in dados_base.columns:
                # Utilizamos upper para garantir que filtraremos independente de case
                dados_base = dados_base[~dados_base['Especialista'].str.upper().isin(['CDB DATA SOLUTIONS'])]
                logger.info(f"Projetos após filtrar Especialista CDB DATA SOLUTIONS: {len(dados_base)}")
            
            # 2. Filtra apenas projetos ativos
            # Removido filtro por Squad CDB DATA SOLUTIONS, pois já filtramos pelo Especialista
            dados_calc = dados_base[
                (~dados_base['Status'].isin(self.status_concluidos))
                # Removido: & (~dados_base['Squad'].str.upper().isin(['CDB DATA SOLUTIONS']))
            ].copy()
            
            # Adiciona logs detalhados para depuração, especialmente para DATA E POWER
            data_power_projetos = dados_calc[dados_calc['Squad'] == 'DATA E POWER']
            if not data_power_projetos.empty:
                logger.info(f"Encontrados {len(data_power_projetos)} projetos para o squad DATA E POWER:")
                for _, projeto in data_power_projetos.iterrows():
                    logger.info(f"  Projeto: {projeto.get('Projeto', 'N/A')}")
                    logger.info(f"    Status: {projeto.get('Status', 'N/A')}")
                    logger.info(f"    Horas Originais: {projeto.get('Horas', 0.0)}")
                    logger.info(f"    Horas Trabalhadas: {projeto.get('HorasTrabalhadas', 0.0)}")
                    logger.info(f"    Horas Restantes: {projeto.get('HorasRestantes', 0.0)}")
                    logger.info(f"    Especialista: {projeto.get('Especialista', 'N/A')}")
            
            # Ajusta horas restantes: para negativas, usa 10% do esforço inicial
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
            
            dados_calc['HorasRestantesAjustadas'] = dados_calc.apply(ajustar_horas_restantes, axis=1)
            
            # Separa projetos em planejamento
            planejamento_pmo = dados_calc[dados_calc['Squad'] == 'Em Planejamento - PMO'].copy()
            dados_squads = dados_calc[dados_calc['Squad'] != 'Em Planejamento - PMO'].copy()
            
            # Calcula horas totais em planejamento
            total_horas_planejamento = planejamento_pmo['HorasRestantesAjustadas'].sum() if not planejamento_pmo.empty else 0
            total_projetos_planejamento = len(planejamento_pmo)
            
            # Adiciona as métricas de planejamento
            metricas['projetos_planejamento'] = total_projetos_planejamento
            metricas['horas_planejamento'] = round(total_horas_planejamento, 1)
            
            # Lista para armazenar resultado da ocupação dos squads
            resultado_ocupacao_squads = []
            
            # Ocupação por Squad (apenas squads regulares)
            if 'Squad' in dados_squads.columns and not dados_squads.empty:
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
                    resultado_ocupacao_squads.append(squad_info)
            
            # Adiciona linha para Em Planejamento - PMO se houver projetos
            if total_projetos_planejamento > 0:
                # PMO tem capacidade de apenas 1 pessoa (180 horas), não 3 pessoas
                CAPACIDADE_PMO = HORAS_POR_PESSOA  # 180 horas (1 pessoa)
                
                # Calcula capacidade utilizada para PMO
                capacidade_utilizada_pmo = (
                    (total_horas_planejamento / CAPACIDADE_PMO) * 100
                ).round(1) if CAPACIDADE_PMO > 0 else 0
                
                # Calcula horas disponíveis para PMO
                horas_disponiveis_pmo = (
                    CAPACIDADE_PMO - total_horas_planejamento
                ).round(1) if total_horas_planejamento <= CAPACIDADE_PMO else 0
                
                # Prepara os dados do PMO
                projetos_output_pmo = planejamento_pmo[['Projeto', 'Status', 'HorasRestantes', 'Conclusao']].copy()
                projetos_output_pmo['HorasRestantesAjustadas'] = planejamento_pmo['HorasRestantesAjustadas']
                
                pmo_info = {
                    'nome': 'Em Planejamento - PMO',
                    'horas_restantes': round(total_horas_planejamento, 1),
                    'total_projetos': total_projetos_planejamento,
                    'percentual_ocupacao': 0,  # Não calculamos percentual para planejamento
                    'tem_horas_negativas': False,
                    'capacidade_utilizada': capacidade_utilizada_pmo,
                    'horas_disponiveis': horas_disponiveis_pmo,
                    'projetos': projetos_output_pmo.to_dict('records')
                }
                resultado_ocupacao_squads.append(pmo_info)
            
            # Ordena por horas restantes (decrescente)
            resultado_ocupacao_squads = sorted(resultado_ocupacao_squads, key=lambda x: x['horas_restantes'], reverse=True)
            
            # Adiciona o resultado de ocupação de squads às métricas
            metricas['ocupacao_squads'] = resultado_ocupacao_squads
            
            # Cria dicionário de horas disponíveis (compatibilidade com código legado)
            horas_disponiveis_dict = {}
            for squad_info in resultado_ocupacao_squads:
                if squad_info['nome'] != 'Em Planejamento - PMO':
                    horas_disponiveis_dict[squad_info['nome']] = squad_info['horas_disponiveis']
            
            metricas['horas_disponiveis'] = horas_disponiveis_dict
            
            # Calcula métricas de Performance de Entregas
            self._calcular_metricas_performance(dados_base, metricas)
            
            return metricas
        except Exception as e:
            logger.error(f"Erro ao calcular métricas avançadas: {str(e)}")
            return {}
            
    def _calcular_metricas_performance(self, dados, metricas):
        """Calcula métricas de Performance de Entregas (Taxa de Sucesso e Tempo Médio)"""
        try:
            # Verifica se os dados são válidos
            if dados.empty:
                logger.warning("DataFrame vazio ao calcular métricas de performance")
                metricas['taxa_sucesso'] = 0
                metricas['tempo_medio_geral'] = 0.0
                return
                
            # Log inicial dos dados
            logger.info("=== DIAGNÓSTICO DE DADOS ===")
            logger.info(f"Total de projetos no DataFrame: {len(dados)}")
            logger.info(f"Colunas disponíveis: {dados.columns.tolist()}")
            logger.info(f"Status únicos encontrados: {dados['Status'].unique().tolist()}")
            
            # Log das datas antes da conversão
            logger.info("=== AMOSTRA DE DATAS ANTES DA CONVERSÃO ===")
            for coluna in ['DataInicio', 'DataTermino', 'VencimentoEm']:
                if coluna in dados.columns:
                    logger.info(f"{coluna} - Primeiros 5 valores: {dados[coluna].head().tolist()}")
            
            # Converte colunas de data para datetime
            for coluna in ['DataInicio', 'DataTermino', 'VencimentoEm']:
                if coluna in dados.columns:
                    dados[coluna] = pd.to_datetime(dados[coluna], errors='coerce')
                    # Log após conversão
                    logger.info(f"=== {coluna} após conversão - Primeiros 5 valores: {dados[coluna].head().tolist()}")
            
            # Período de análise fixo: Q4 FY25 (1/4/2025 a 30/6/2025)
            inicio_periodo = datetime(2025, 4, 1)
            fim_periodo = datetime(2025, 6, 30)
            
            logger.info("=== PERÍODO DE ANÁLISE ===")
            logger.info(f"Início: {inicio_periodo}")
            logger.info(f"Fim: {fim_periodo}")
            
            # Log de projetos com status de conclusão
            projetos_fechados = dados[dados['Status'].isin(['Fechado', 'Resolvido'])]
            logger.info(f"\nTotal de projetos fechados/resolvidos (geral): {len(projetos_fechados)}")
            if not projetos_fechados.empty:
                logger.info("Amostra de projetos fechados:")
                for _, proj in projetos_fechados.head().iterrows():
                    logger.info(f"Projeto: {proj['Projeto']}")
                    logger.info(f"Status: {proj['Status']}")
                    logger.info(f"Data Término: {proj['DataTermino']}")
                    logger.info(f"Data Vencimento: {proj['VencimentoEm']}")
                    logger.info("---")
            
            # 1. Filtra todos os projetos concluídos no período
            projetos_concluidos = dados[
                (dados['Status'].isin(['Fechado', 'Resolvido'])) &
                (pd.notna(dados['DataTermino'])) &
                (dados['DataTermino'] >= inicio_periodo) &
                (dados['DataTermino'] <= fim_periodo)
            ]
            
            logger.info("\n=== PROJETOS CONCLUÍDOS NO PERÍODO ===")
            logger.info(f"Total: {len(projetos_concluidos)}")
            if not projetos_concluidos.empty:
                logger.info("Detalhes dos projetos concluídos:")
                for _, proj in projetos_concluidos.iterrows():
                    logger.info(f"Projeto: {proj['Projeto']}")
                    logger.info(f"Status: {proj['Status']}")
                    logger.info(f"Data Término: {proj['DataTermino']}")
                    logger.info(f"Data Vencimento: {proj['VencimentoEm']}")
                    logger.info("---")
            
            # 2. Filtra projetos com vencimento no período
            projetos_previstos = dados[
                (pd.notna(dados['VencimentoEm'])) &
                (dados['VencimentoEm'] >= inicio_periodo) &
                (dados['VencimentoEm'] <= fim_periodo)
            ]
            
            logger.info("\n=== PROJETOS PREVISTOS PARA O PERÍODO ===")
            logger.info(f"Total: {len(projetos_previstos)}")
            if not projetos_previstos.empty:
                logger.info("Detalhes dos projetos previstos:")
                for _, proj in projetos_previstos.iterrows():
                    logger.info(f"Projeto: {proj['Projeto']}")
                    logger.info(f"Status: {proj['Status']}")
                    logger.info(f"Data Vencimento: {proj['VencimentoEm']}")
                    logger.info("---")
            
            # 3. Identifica projetos entregues NO MÊS PREVISTO (e dentro do período Q4)
            # Filtra projetos concluídos onde o mês/ano de término == mês/ano de vencimento
            entregues_mes_previsto = projetos_concluidos[
                (projetos_concluidos['DataTermino'].dt.year == projetos_concluidos['VencimentoEm'].dt.year) &
                (projetos_concluidos['DataTermino'].dt.month == projetos_concluidos['VencimentoEm'].dt.month)
            ]
            
            logger.info("\n=== PROJETOS ENTREGUES NO MÊS PREVISTO ===") # Log Atualizado
            logger.info(f"Total: {len(entregues_mes_previsto)}")
            if not entregues_mes_previsto.empty:
                logger.info("Detalhes dos projetos entregues no mês previsto:")
                for _, proj in entregues_mes_previsto.iterrows():
                    logger.info(f"Projeto: {proj['Projeto']}")
                    logger.info(f"Data Término: {proj['DataTermino']}")
                    logger.info(f"Data Vencimento: {proj['VencimentoEm']}")
                    logger.info("---")
            
            # 4. Calcula métricas
            total_previstos = len(projetos_previstos)
            total_concluidos = len(projetos_concluidos)
            total_entregues_mes_previsto = len(entregues_mes_previsto) # Usa a nova contagem
            
            if total_previstos > 0:
                # Usa a nova contagem no numerador
                taxa_sucesso = round((total_entregues_mes_previsto / total_previstos) * 100)
            else:
                taxa_sucesso = 0
            
            # Calcula tempo médio de entrega (agora usa entregues_mes_previsto como base? Ou mantém concluidos? Manter concluidos parece mais geral)
            # *** Decisão: Manter o cálculo do tempo médio baseado nos projetos concluídos no prazo original ***
            # *** Isso evita penalizar o tempo médio por entregas no mês certo, mas no último dia vs primeiro.***
            entregues_no_prazo_para_tempo_medio = projetos_concluidos[
                projetos_concluidos['DataTermino'] <= projetos_concluidos['VencimentoEm']
            ]
            if not entregues_no_prazo_para_tempo_medio.empty:
                entregues_no_prazo_para_tempo_medio['duracao_dias'] = (
                    entregues_no_prazo_para_tempo_medio['DataTermino'] - entregues_no_prazo_para_tempo_medio['DataInicio']
                ).dt.days
                
                # Remove outliers
                entregues_validos = entregues_no_prazo_para_tempo_medio[
                    (entregues_no_prazo_para_tempo_medio['duracao_dias'] >= 0) &
                    (entregues_no_prazo_para_tempo_medio['duracao_dias'] <= 365)
                ]
                
                tempo_medio = round(entregues_validos['duracao_dias'].mean(), 1) if not entregues_validos.empty else 0.0
            else:
                tempo_medio = 0.0
            
            # Adiciona as métricas
            metricas['taxa_sucesso'] = taxa_sucesso
            metricas['tempo_medio_geral'] = tempo_medio
            
            # Adiciona informações do trimestre (ajustado para usar a nova métrica)
            metricas['quarter_info'] = {
                'quarter': 'Q4 - Ano Fiscal Microsoft',
                'inicio': inicio_periodo.strftime('%d/%m/%Y'),
                'fim': fim_periodo.strftime('%d/%m/%Y'),
                'total_projetos_previstos': total_previstos,
                'projetos_concluidos': total_concluidos,
                'projetos_entregues_mes_previsto': total_entregues_mes_previsto, # Adicionado/Renomeado
                'projetos_em_andamento': total_previstos - total_concluidos # Lógica mantida
            }
            
            logger.info("\n=== MÉTRICAS FINAIS ===")
            logger.info(f"Taxa de Sucesso (Concluídos no Mês Previsto / Previstos): {taxa_sucesso}%") # Log atualizado
            logger.info(f"Tempo Médio (baseado nos entregues no prazo original): {tempo_medio} dias") # Log atualizado
            logger.info(f"Total Previstos (no período): {total_previstos}")
            logger.info(f"Total Concluídos (no período): {total_concluidos}")
            # logger.info(f"Total Entregues no Prazo (no período): {total_no_prazo}") # Log antigo removido
            logger.info(f"Total Entregues no Mês Previsto (no período): {total_entregues_mes_previsto}") # Log novo
            logger.info(f"Conteúdo final de quarter_info: {metricas['quarter_info']}") # Log final
                
        except Exception as e:
            logger.error(f"Erro ao calcular métricas de performance: {str(e)}", exc_info=True)
            metricas['taxa_sucesso'] = 0
            metricas['tempo_medio_geral'] = 0.0

    def validar_dados(self, dados):
        """Valida a estrutura básica dos dados"""
        if not isinstance(dados, pd.DataFrame):
            raise ValueError("Dados devem ser um DataFrame")
        if dados.empty:
            raise ValueError("DataFrame vazio recebido")
            
        # Verifica colunas obrigatórias
        colunas_faltantes = [col for col in COLUNAS_OBRIGATORIAS if col not in dados.columns]
        if colunas_faltantes:
            logger.warning(f"Colunas obrigatórias não encontradas: {', '.join(colunas_faltantes)}")
            # Adiciona colunas faltantes com valores padrão
            for col in colunas_faltantes:
                if col in COLUNAS_NUMERICAS:
                    dados[col] = 0.0
                else:
                    dados[col] = 'NÃO DEFINIDO'
                logger.info(f"Coluna '{col}' adicionada com valor padrão")
            
        # Verifica tipos de dados
        for col in COLUNAS_NUMERICAS:
            if col in dados.columns:
                if not pd.api.types.is_numeric_dtype(dados[col]):
                    logger.warning(f"Coluna {col} não é numérica. Tentando converter...")
                    try:
                        if dados[col].dtype == 'object':
                            dados[col] = dados[col].str.replace(',', '.', regex=False)
                        dados[col] = pd.to_numeric(dados[col], errors='coerce')
                        logger.info(f"Coluna {col} convertida para numérica com sucesso")
                    except Exception as e:
                        logger.error(f"Erro ao converter coluna {col} para numérica: {str(e)}")
                        dados[col] = 0.0
        
        # Verifica valores nulos em colunas críticas
        for col in COLUNAS_OBRIGATORIAS:
            if col in dados.columns:
                nulos = dados[col].isna().sum()
                if nulos > 0:
                    logger.warning(f"Encontrados {nulos} valores nulos na coluna {col}")
                    if col in COLUNAS_NUMERICAS:
                        dados[col] = dados[col].fillna(0.0)
                    else:
                        dados[col] = dados[col].fillna('NÃO DEFINIDO')
            
        return True

    def calcular_alertas(self, dados):
        """Calcula alertas críticos baseado em indicadores-chave"""
        alertas = []
        
        # Regras de alerta prioritárias (nível CRÍTICO)
        if dados.empty:
            alertas.append({
                'tipo': 'critico',
                'codigo': 'ALERTA_001',
                'titulo': 'Dados não encontrados',
                'mensagem': 'Nenhum projeto encontrado com os filtros atuais',
                'icone': 'bi-database-exclamation',
                'prioridade': 1
            })
            return alertas  # Retorna imediatamente pois os outros checks não fazem sentido
        
        total_projetos = len(dados)
        
        # 1. Alertas de SLA (Status)
        projetos_atrasados = dados[dados['Status'] == 'Atrasado']
        if len(projetos_atrasados) > 0:
            alertas.append({
                'tipo': 'critico',
                'codigo': 'ALERTA_101',
                'titulo': 'Projetos atrasados',
                'mensagem': f"{len(projetos_atrasados)} projeto(s) com status 'Atrasado'",
                'icone': 'bi-clock-history',
                'prioridade': 2,
                'detalhes': projetos_atrasados[['Projeto', 'Squad']].to_dict('records')
            })
        
        # 2. Alertas de Alocação
        projetos_sem_squad = dados[dados['Squad'] == 'Em Planejamento - PMO']
        if len(projetos_sem_squad) > 0:
            alertas.append({
                'tipo': 'alocacao',
                'codigo': 'ALERTA_102',
                'titulo': 'Projetos em planejamento',
                'mensagem': f"{len(projetos_sem_squad)} projeto(s) em fase de planejamento aguardando alocação",
                'icone': 'bi-people',
                'prioridade': 3,
                'detalhes': projetos_sem_squad[['Projeto', 'Account Manager']].to_dict('records')
            })
        
        # 3. Alertas de Horas (Micro)
        if 'HorasRestantes' in dados.columns:
            projetos_sem_horas = dados[dados['HorasRestantes'] <= 0]
            if len(projetos_sem_horas) > 0:
                alertas.append({
                    'tipo': 'horas',
                    'codigo': 'ALERTA_103',
                    'titulo': 'Saldo de horas esgotado',
                    'mensagem': f"{len(projetos_sem_horas)} projeto(s) com saldo zero ou negativo de horas",
                    'icone': 'bi-hourglass-bottom',
                    'prioridade': 4,
                    'detalhes': projetos_sem_horas[['Projeto', 'HorasRestantes']].to_dict('records')
                })
        
        # 4. Alertas de Conclusão (Progresso)
        if 'Conclusao' in dados.columns:
            projetos_estagnados = dados[(dados['Conclusao'] < 50) & 
                                       (dados['Status'] == 'Ativo')]
            if len(projetos_estagnados) > 0:
                alertas.append({
                    'tipo': 'progresso',
                    'codigo': 'ALERTA_104',
                    'titulo': 'Projetos estagnados',
                    'mensagem': f"{len(projetos_estagnados)} projeto(s) ativos com menos de 50% de conclusão",
                    'icone': 'bi-speedometer',
                    'prioridade': 5,
                    'detalhes': projetos_estagnados[['Projeto', 'Conclusao']].to_dict('records')
                })
        
        # 5. Alertas de Faturamento (Financeiro)
        if 'Faturamento' in dados.columns:
            projetos_para_faturar = dados[dados['Faturamento'].isin(['PRIME', 'PLUS', 'INICIO'])]
            if len(projetos_para_faturar) > 0:
                alertas.append({
                    'tipo': 'financeiro',
                    'codigo': 'ALERTA_105',
                    'titulo': 'Projetos para faturar',
                    'mensagem': f"{len(projetos_para_faturar)} projeto(s) com faturamento PRIME/PLUS/INICIO",
                    'icone': 'bi-cash-stack',
                    'prioridade': 6,
                    'detalhes': projetos_para_faturar[['Projeto', 'Faturamento']].to_dict('records')
                })
        
        # Ordenar alertas por prioridade
        alertas.sort(key=lambda x: x['prioridade'])
        
        return alertas

    def calcular_faturamento_pendente(self, dados):
        try:
            hoje = datetime.now()
            mes_atual = hoje.month
            ano_atual = hoje.year
            
            # Verifica se as colunas necessárias existem
            colunas_necessarias = ['Faturamento', 'DataInicio', 'DataTermino', 'VencimentoEm', 'Status']
            for coluna in colunas_necessarias:
                if coluna not in dados.columns:
                    logger.warning(f"Coluna {coluna} não encontrada para cálculo de faturamento pendente")
                    return []
            
            # Condição para faturar no início (PRIME, PLUS, INICIO) que começaram neste mês
            cond_inicio = (
                dados['Faturamento'].isin(['PRIME', 'PLUS', 'INICIO']) &
                (dados['DataInicio'].dt.month == mes_atual) &
                (dados['DataInicio'].dt.year == ano_atual)
            )
            
            # Condição para faturar no término (TERMINO e ENGAJAMENTO)
            cond_termino = (
                dados['Faturamento'].isin(['TERMINO', 'ENGAJAMENTO']) &
                (
                    # Verifica se a data prevista (VencimentoEm) é no mês atual para projetos em andamento
                    ((~dados['Status'].isin(['Fechado', 'Resolvido'])) & 
                     (dados['VencimentoEm'].dt.month == mes_atual) & 
                     (dados['VencimentoEm'].dt.year == ano_atual)) |
                    # OU se a data de término (DataTermino) é no mês atual para projetos concluídos
                    ((dados['Status'].isin(['Fechado', 'Resolvido'])) & 
                     (dados['DataTermino'].dt.month == mes_atual) & 
                     (dados['DataTermino'].dt.year == ano_atual))
                )
            )
            
            # Filtra projetos para faturar (exclui FTOP)
            projetos_faturar = dados[
                (cond_inicio | cond_termino) & 
                (dados['Faturamento'] != 'FTOP')
            ].copy()
            
            # Inicializa a coluna de data formatada para exibição
            projetos_faturar['DataFaturamento'] = None
            
            # Caso 1: PRIME/PLUS/INICIO usam DataInicio
            mask_inicio = projetos_faturar['Faturamento'].isin(['PRIME', 'PLUS', 'INICIO'])
            if mask_inicio.any():
                mask_inicio_valido = mask_inicio & pd.notna(projetos_faturar['DataInicio'])
                if mask_inicio_valido.any():
                    projetos_faturar.loc[mask_inicio_valido, 'DataFaturamento'] = projetos_faturar.loc[mask_inicio_valido, 'DataInicio'].dt.strftime('%d/%m/%Y')
            
            # Caso 2: TERMINO/ENGAJAMENTO com status não concluído usam VencimentoEm
            mask_termino_ativo = (
                projetos_faturar['Faturamento'].isin(['TERMINO', 'ENGAJAMENTO']) & 
                ~projetos_faturar['Status'].isin(['Fechado', 'Resolvido'])
            )
            if mask_termino_ativo.any():
                mask_termino_ativo_valido = mask_termino_ativo & pd.notna(projetos_faturar['VencimentoEm'])
                if mask_termino_ativo_valido.any():
                    projetos_faturar.loc[mask_termino_ativo_valido, 'DataFaturamento'] = projetos_faturar.loc[mask_termino_ativo_valido, 'VencimentoEm'].dt.strftime('%d/%m/%Y')
            
            # Caso 3: TERMINO/ENGAJAMENTO com status concluído usam DataTermino
            mask_termino_concluido = (
                projetos_faturar['Faturamento'].isin(['TERMINO', 'ENGAJAMENTO']) & 
                projetos_faturar['Status'].isin(['Fechado', 'Resolvido'])
            )
            if mask_termino_concluido.any():
                mask_termino_concluido_valido = mask_termino_concluido & pd.notna(projetos_faturar['DataTermino'])
                if mask_termino_concluido_valido.any():
                    projetos_faturar.loc[mask_termino_concluido_valido, 'DataFaturamento'] = projetos_faturar.loc[mask_termino_concluido_valido, 'DataTermino'].dt.strftime('%d/%m/%Y')
            
            # Atualiza a coluna VencimentoEm para exibição
            projetos_faturar['VencimentoEm'] = projetos_faturar['DataFaturamento']
            
            # Seleciona e renomeia as colunas necessárias
            colunas = ['Projeto', 'Squad', 'Account Manager', 'Faturamento', 'Status', 'VencimentoEm']
            colunas_existentes = [col for col in colunas if col in projetos_faturar.columns]
            projetos_formatados = projetos_faturar[colunas_existentes].copy()
            
            # Garantir que Squad não tenha valores nulos
            if 'Squad' in projetos_formatados.columns:
                projetos_formatados['Squad'] = projetos_formatados['Squad'].fillna('Em Planejamento - PMO')
                projetos_formatados['Squad'] = projetos_formatados['Squad'].replace({'nan': 'Em Planejamento - PMO', '': 'Em Planejamento - PMO', 'NÃO DEFINIDO': 'Em Planejamento - PMO'})
            
            return projetos_formatados.replace({np.nan: None}).to_dict('records')
            
        except Exception as e:
            logger.error(f"Erro ao calcular faturamento pendente: {str(e)}")
            return []
    
    def obter_metricas_gerencial(self):
        """Retorna métricas gerenciais"""
        try:
            dados = self.carregar_dados()
            if dados.empty:
                return {
                    'projetos_ativos': 0,
                    'projetos_criticos': 0,
                    'projetos_em_atendimento': 0,
                    'projetos_para_faturar': 0,
                    'faturamento_pendente': 0
                }

            self.validar_dados(dados)
            
            # Define o mês e ano atual
            hoje = datetime.now()
            mes_atual = hoje.month
            ano_atual = hoje.year
            
            # Definir status em Title Case (consistente com o processamento que padroniza os status)
            status_concluidos = ['Fechado', 'Encerrado', 'Resolvido', 'Cancelado']
            status_em_atendimento = ['Em Atendimento', 'Novo']
            
            # Projetos ativos (todos que não estão concluídos)
            projetos_ativos = dados[~dados['Status'].isin(status_concluidos)]
            
            # Projetos críticos - usa critérios avançados do método obter_projetos_criticos
            projetos_criticos = self.obter_projetos_criticos(dados)
            
            # Projetos em atendimento
            projetos_em_atendimento = dados[dados['Status'].isin(status_em_atendimento)]
            
            # Condição para faturar no início (PRIME, PLUS, INICIO)
            cond_inicio = (
                dados['Faturamento'].isin(['PRIME', 'PLUS', 'INICIO']) &
                (dados['DataInicio'].dt.month == mes_atual) &
                (dados['DataInicio'].dt.year == ano_atual)
            )
            
            # Condição para faturar no término (TERMINO e ENGAJAMENTO)
            cond_termino = (
                dados['Faturamento'].isin(['TERMINO', 'ENGAJAMENTO']) &
                (
                    # Verifica se a data prevista (VencimentoEm) é no mês atual para projetos em andamento
                    ((~dados['Status'].isin(['Fechado', 'Resolvido'])) & 
                     (dados['VencimentoEm'].dt.month == mes_atual) & 
                     (dados['VencimentoEm'].dt.year == ano_atual)) |
                    # OU se a data de término (DataTermino) é no mês atual para projetos concluídos
                    ((dados['Status'].isin(['Fechado', 'Resolvido'])) & 
                     (dados['DataTermino'].dt.month == mes_atual) & 
                     (dados['DataTermino'].dt.year == ano_atual))
                )
            )
            
            # Filtra projetos para faturar (exclui FTOP)
            projetos_para_faturar = dados[
                (cond_inicio | cond_termino) & 
                (dados['Faturamento'] != 'FTOP')
            ]
            
            # Número de projetos para faturar
            num_projetos_para_faturar = len(projetos_para_faturar)
            
            # Log para debug
            logger.info(f"DEBUG - Total de projetos no dataframe: {len(dados)}")
            logger.info(f"DEBUG - Status concluídos considerados: {status_concluidos}")
            logger.info(f"DEBUG - Status em atendimento considerados: {status_em_atendimento}")
            logger.info(f"DEBUG - Valores únicos na coluna Status: {dados['Status'].unique().tolist()}")
            logger.info(f"DEBUG - Projetos ativos: {len(projetos_ativos)}")
            logger.info(f"DEBUG - Projetos críticos: {len(projetos_criticos)}")
            logger.info(f"DEBUG - Projetos em atendimento: {len(projetos_em_atendimento)}")
            
            metricas = {
                'projetos_ativos': len(projetos_ativos),
                'projetos_criticos': len(projetos_criticos),
                'projetos_em_atendimento': len(projetos_em_atendimento),
                'projetos_para_faturar': num_projetos_para_faturar,
                'faturamento_pendente': num_projetos_para_faturar,  # Mantém compatibilidade com o frontend
                'projetos_criticos_count': len(projetos_criticos)   # Garante que projetos_criticos_count use a mesma contagem
            }
            
            logger.info(f"Métricas gerenciais calculadas: {metricas}")
            return metricas
            
        except Exception as e:
            logger.error(f"Erro ao obter métricas gerenciais: {str(e)}")
            return {
                'projetos_ativos': 0,
                'projetos_criticos': 0,
                'projetos_em_atendimento': 0,
                'projetos_para_faturar': 0,
                'faturamento_pendente': 0,
                'projetos_criticos_count': 0
            }
    
    def teste_projetos_para_faturar(self):
        """Função para testar a obtenção de projetos para faturar"""
        try:
            dados = self.carregar_dados()
            if dados.empty:
                print("Dados vazios!")
                return
                
            # Para testes, vamos forçar a data atual para ver se isso afeta os resultados
            # Comentar esta linha para usar a data atual real
            # hoje = datetime(2025, 4, 11)  # Data dos testes
            hoje = datetime.now()
            print(f"Data de teste: {hoje.strftime('%d/%m/%Y')}")
            print(f"Total de projetos no dataset: {len(dados)}")
            
            # Verificar tipos de faturamento disponíveis
            if 'Faturamento' in dados.columns:
                faturamentos = dados['Faturamento'].value_counts().to_dict()
                print(f"Tipos de faturamento disponíveis: {faturamentos}")
            
            # Verificar projetos por mês de início
            if 'DataInicio' in dados.columns:
                meses_inicio = dados['DataInicio'].dt.month.value_counts().sort_index().to_dict()
                print(f"Distribuição por mês de início: {meses_inicio}")
            
            # Verificar distribuição de meses em DataTermino
            if 'DataTermino' in dados.columns:
                meses_termino = dados['DataTermino'].dt.month.value_counts().sort_index().to_dict()
                print(f"Distribuição por mês de término: {meses_termino}")
            
            # Executar a função que queremos testar
            projetos = self.obter_projetos_para_faturar(dados)
            
            # Exibir resultados
            print(f"\nTotal de projetos para faturar: {len(projetos)}")
            if projetos:
                for i, p in enumerate(projetos):
                    print(f"{i+1}. {p['Projeto']} - {p['Faturamento']} - {p['Status']} - {p['VencimentoEm']}")
            
            return projetos
        except Exception as e:
            print(f"ERRO no teste: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return []
    
    def _carregar_dados_historicos(self, ano, mes):
        """Carrega e processa dados de um arquivo histórico específico (dadosr_apt_mes.csv)."""
        try:
            mes_str = f"{mes:02d}" # Formata mês com zero à esquerda (01, 02, ..., 12)
            # Mapeia número do mês para abreviação de 3 letras em minúsculo
            mes_abrev_map = {1: 'jan', 2: 'fev', 3: 'mar', 4: 'abr', 5: 'mai', 6: 'jun', 
                             7: 'jul', 8: 'ago', 9: 'set', 10: 'out', 11: 'nov', 12: 'dez'}
            mes_abrev = mes_abrev_map.get(mes)
            
            if not mes_abrev:
                logger.error(f"Mês inválido fornecido para dados históricos: {mes}")
                return pd.DataFrame()
                
            nome_arquivo = f"dadosr_apt_{mes_abrev}.csv" # Formato do nome do arquivo
            caminho_historico = self.csv_path.parent / nome_arquivo # Assume que está na mesma pasta 'data'
            
            logger.info(f"Tentando carregar dados históricos de: {caminho_historico}")
            
            if not caminho_historico.is_file():
                logger.error(f"Arquivo histórico CSV não encontrado: {caminho_historico}")
                return pd.DataFrame()
            
            # Lê o CSV histórico (mesmos parâmetros de carregar_dados)
            dados = pd.read_csv(
                caminho_historico, 
                dtype=str, 
                sep=';', 
                encoding='latin1'
            )
            logger.info(f"Arquivo histórico {nome_arquivo} carregado com {len(dados)} linhas.")
            
            # Aplica EXATAMENTE O MESMO pré-processamento de carregar_dados
            # (Conversão de Datas, Números, Tempo, Renomeação, Padronização)
            # --- Copiado e adaptado de carregar_dados --- 
            # 1.2.1 Conversão de Datas
            colunas_data_simples = ['Aberto em', 'Resolvido em', 'Data da última ação']
            # ... (resto do código de conversão de datas igual a carregar_dados) ...
            for col in colunas_data_simples:
                 if col in dados.columns:
                     dados[col] = pd.to_datetime(dados[col], format='%d/%m/%Y', errors='coerce')
                 # else: # Não loga warning para históricos, podem ter colunas diferentes
                 #    logger.warning(f"[Histórico] Coluna de data {col} não encontrada em {nome_arquivo}")
            
            if 'Vencimento em' in dados.columns:
                 dados['Vencimento em_Original'] = dados['Vencimento em']
                 dados['Vencimento em'] = pd.to_datetime(dados['Vencimento em_Original'], format='%d/%m/%Y %H:%M', errors='coerce')
                 mask_nat = dados['Vencimento em'].isna()
                 if mask_nat.any():
                     dados.loc[mask_nat, 'Vencimento em'] = pd.to_datetime(dados.loc[mask_nat, 'Vencimento em_Original'], format='%d/%m/%Y', errors='coerce')
                 # del dados['Vencimento em_Original'] 
            
            # 1.2.2 Conversão Numérica
            if 'Número' in dados.columns:
                 dados['Número'] = pd.to_numeric(dados['Número'], errors='coerce').astype('Int64')
            if 'Esforço estimado' in dados.columns:
                 dados['Esforço estimado'] = dados['Esforço estimado'].str.replace(',', '.', regex=False)
                 dados['Esforço estimado'] = pd.to_numeric(dados['Esforço estimado'], errors='coerce').fillna(0.0)
            else: dados['Esforço estimado'] = 0.0
            if 'Andamento' in dados.columns:
                 dados['Andamento'] = dados['Andamento'].str.rstrip('%').str.replace(',', '.', regex=False)
                 dados['Andamento'] = pd.to_numeric(dados['Andamento'], errors='coerce').fillna(0.0).clip(lower=0, upper=100)
            else: dados['Andamento'] = 0.0
            if 'Tempo trabalhado' in dados.columns:
                 dados['Tempo trabalhado'] = dados['Tempo trabalhado'].apply(self.converter_tempo_para_horas)
            else: dados['Tempo trabalhado'] = 0.0
            
            # 1.3 Renomeação
            rename_map_new_to_old = { ... } # Usar o mesmo mapa de carregar_dados
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
            
            # 1.4 Padronização Final
            if 'Status' in dados.columns: dados['Status'] = dados['Status'].astype(str).str.strip().str.title()
            faturamento_map = { ... } # Usar o mesmo mapa de carregar_dados
            faturamento_map = {
                "PRIME": "PRIME",
                "Descontar do PLUS no inicio do projeto": "PLUS",
                "Faturar no inicio do projeto": "INICIO",
                "Faturar no final do projeto": "TERMINO",
                "Faturado em outro projeto": "FEOP",
                "Faturado em outro projeto.": "FEOP",
                "Engajamento": "ENGAJAMENTO"
            }
            if 'Faturamento' in dados.columns:
                dados['Faturamento'] = dados['Faturamento'].astype(str).str.strip()
                dados['Faturamento_Original'] = dados['Faturamento']
                dados['Faturamento'] = dados['Faturamento'].map(faturamento_map)
                nao_mapeados = dados['Faturamento'].isna()
                if nao_mapeados.any():
                    mask_nan = dados['Faturamento_Original'].isna() | (dados['Faturamento_Original'] == 'nan')
                    if mask_nan.any(): dados.loc[mask_nan, 'Faturamento'] = 'EAN'
                    dados['Faturamento'] = dados['Faturamento'].fillna('NAO_MAPEADO')
                # del dados['Faturamento_Original']
            colunas_texto_padrao = ['Projeto', 'Squad', 'Especialista', 'Account Manager']
            for col in colunas_texto_padrao:
                if col in dados.columns:
                    dados[col] = dados[col].astype(str).str.strip()
                    if col == 'Squad': dados[col] = dados[col].replace({'': 'Em Planejamento - PMO', 'nan': 'Em Planejamento - PMO', 'NÃO DEFINIDO': 'Em Planejamento - PMO'}).fillna('Em Planejamento - PMO')
                    else: dados[col] = dados[col].replace({'': 'NÃO DEFINIDO', 'nan': 'NÃO DEFINIDO'}).fillna('NÃO DEFINIDO')
            
            # Recalcula HorasRestantes (importante após carregar e renomear)
            if 'Horas' in dados.columns and 'HorasTrabalhadas' in dados.columns:
                 dados['HorasRestantes'] = (dados['Horas'] - dados['HorasTrabalhadas']).round(1)
            else: dados['HorasRestantes'] = 0.0
            # --- Fim do código copiado --- 
            
            logger.info(f"Dados históricos de {mes_abrev.upper()}/{ano} processados.")
            return dados

        except Exception as e:
            logger.error(f"Erro ao carregar dados históricos para {ano}-{mes_str}: {str(e)}")
            return pd.DataFrame()
    
    