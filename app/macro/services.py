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

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constantes de status atualizadas
STATUS_NAO_ATIVOS = ['FECHADO', 'ENCERRADO', 'RESOLVIDO', 'CANCELADO']
STATUS_EM_ANDAMENTO = ['NOVO', 'AGUARDANDO', 'BLOQUEADO', 'EM ATENDIMENTO']
STATUS_ATRASADO = ['ATRASADO']
STATUS_ATIVO = ['ATIVO']

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
        Carrega e processa os dados do CSV, permitindo especificar uma fonte alternativa.
        
        Args:
            fonte: Nome do arquivo de dados alternativo (opcional)
                  Se None, usa a fonte padrão 'dadosr.csv'
        
        Returns:
            DataFrame pandas com os dados processados
        """
        try:
            # Determina qual arquivo deve ser carregado
            if fonte:
                arquivo_nome = f"{fonte}.csv"
                # Obtém o diretório data (mesmo local do dadosr.csv)
                data_dir = self.csv_path.parent
                csv_path = data_dir / arquivo_nome
                logger.info(f"Tentando carregar dados da fonte alternativa: {csv_path}")
            else:
                logger.info(f"Tentando carregar dados da fonte padrão: {self.csv_path}")
                csv_path = self.csv_path
            
            # Verifica se o arquivo existe
            if not csv_path.is_file():
                arquivo_esperado = str(csv_path)
                mensagem_erro = f"Arquivo CSV não encontrado: {arquivo_esperado}"
                logger.error(mensagem_erro)
                
                # Verifica quais arquivos estão disponíveis no diretório
                data_dir = csv_path.parent
                arquivos_disponiveis = [f.name for f in data_dir.glob("*.csv")]
                logger.info(f"Arquivos disponíveis no diretório: {arquivos_disponiveis}")
                
                return pd.DataFrame()
            
            # Lê o CSV com parâmetros corretos
            dados = pd.read_csv(
                csv_path,
                dtype=str,
                sep=';',
                encoding='latin1',
            )
            logger.info(f"Arquivo {csv_path} carregado com {len(dados)} linhas.")
            
            # Log das colunas originais para depuração
            logger.info(f"Colunas originais no arquivo {os.path.basename(csv_path)}: {dados.columns.tolist()}")
            
            # --- Passo 1.2: Tratamento Inicial (Usando Nomes de dadosr.csv) ---
            
            # 1.2.1 Conversão de Datas
            colunas_data_simples = ['Aberto em', 'Resolvido em', 'Data da última ação']
            for col in colunas_data_simples:
                if col in dados.columns:
                    original_col = dados[col].copy()
                    dados[col] = pd.to_datetime(original_col, format='%d/%m/%Y', errors='coerce')
                    # Log de erros na conversão de datas simples
                    mask_nat_simple = dados[col].isna()
                    if mask_nat_simple.any():
                        problematic_values = original_col[mask_nat_simple].unique().tolist()
                        logger.warning(f"Falha ao converter {mask_nat_simple.sum()} valores para data na coluna '{col}' (formato esperado dd/mm/yyyy). Valores originais problemáticos: {problematic_values}")
                else:
                    logger.warning(f"Coluna de data esperada não encontrada: {col}")
            
            # Tratamento especial para 'Vencimento em' (pode ter hora)
            if 'Vencimento em' in dados.columns:
                col_vencimento = 'Vencimento em'
                # Guarda a coluna original para a segunda tentativa de parse
                original_vencimento = dados[col_vencimento].copy()
                
                # Tentativa 1: Formato com hora
                dados[col_vencimento] = pd.to_datetime(original_vencimento, format='%d/%m/%Y %H:%M', errors='coerce')
                
                # Identifica as linhas que falharam (viraram NaT)
                mask_nat = dados[col_vencimento].isna()
                
                # Tentativa 2: Formato sem hora (APENAS para as que falharam E não eram originalmente vazias)
                mask_retry = mask_nat & original_vencimento.notna() & (original_vencimento != '')
                if mask_retry.any():
                    logger.info(f"Tentando formato %d/%m/%Y para {mask_retry.sum()} valores de '{col_vencimento}' que falharam no formato com hora.")
                    # Usa a string ORIGINAL guardada para a segunda tentativa
                    dados.loc[mask_retry, col_vencimento] = pd.to_datetime(original_vencimento[mask_retry], format='%d/%m/%Y', errors='coerce')
                    
                    # Log de erros na segunda tentativa (se houver)
                    mask_failed_again = dados.loc[mask_retry, col_vencimento].isna()
                    if mask_failed_again.any():
                        logger.warning(f"{mask_failed_again.sum()} valores de '{col_vencimento}' falharam em AMBOS os formatos (dd/mm/yyyy HH:MM e dd/mm/yyyy). Valores originais problemáticos: {original_vencimento[mask_retry][mask_failed_again].unique().tolist()}")
            else:
                logger.warning("Coluna de data esperada não encontrada: Vencimento em")

            # 1.2.2 Conversão Numérica
            if 'Número' in dados.columns:
                dados['Número'] = pd.to_numeric(dados['Número'], errors='coerce').astype('Int64')
            else:
                logger.warning("Coluna numérica esperada não encontrada: Número")

            if 'Esforço estimado' in dados.columns:
                dados['Esforço estimado'] = dados['Esforço estimado'].str.replace(',', '.', regex=False)
                dados['Esforço estimado'] = pd.to_numeric(dados['Esforço estimado'], errors='coerce').fillna(0.0)
            else:
                logger.warning("Coluna numérica esperada não encontrada: Esforço estimado")
                dados['Esforço estimado'] = 0.0

            if 'Andamento' in dados.columns:
                dados['Andamento'] = dados['Andamento'].str.rstrip('%').str.replace(',', '.', regex=False)
                dados['Andamento'] = pd.to_numeric(dados['Andamento'], errors='coerce').fillna(0.0)
                dados['Andamento'] = dados['Andamento'].clip(lower=0, upper=100)
            else:
                logger.warning("Coluna numérica esperada não encontrada: Andamento")
                dados['Andamento'] = 0.0
            
            # 1.2.3 Conversão de Tempo para Horas Decimais
            if 'Tempo trabalhado' in dados.columns:
                dados['Tempo trabalhado'] = dados['Tempo trabalhado'].apply(self.converter_tempo_para_horas)
            else:
                logger.warning("Coluna de tempo esperada não encontrada: Tempo trabalhado")
                dados['Tempo trabalhado'] = 0.0

            # --- Passo 1.3: Renomeação (Novos Nomes -> Nomes Antigos/Apelidos) ---
            
            # 1.3.1 Renomeação de colunas
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
            
            # Log dos valores únicos de Squad antes da renomeação
            if 'Serviço (2º Nível)' in dados.columns:
                logger.info(f"Valores únicos em 'Serviço (2º Nível)' (Squad) antes da renomeação: {dados['Serviço (2º Nível)'].unique().tolist()}")
            
            colunas_para_renomear = {k: v for k, v in rename_map_new_to_old.items() if k in dados.columns}
            dados.rename(columns=colunas_para_renomear, inplace=True)
            logger.info(f"Colunas renomeadas para nomes antigos/apelidos: {list(colunas_para_renomear.values())}")

            # --- Passo 1.4: Padronização Final (Usando Nomes Antigos/Apelidos) ---
            
            # 1.4.1 Padronização de Status (para UPPERCASE)
            if 'Status' in dados.columns:
                dados['Status'] = dados['Status'].astype(str).str.strip().str.upper()
                logger.info(f"Coluna 'Status' padronizada para UPPERCASE. Valores únicos: {dados['Status'].unique().tolist()}")
            else:
                logger.warning("Coluna 'Status' não encontrada para padronização final.")

            # 1.4.2 Padronização de Faturamento
            faturamento_map = {
                "PRIME": "PRIME",
                "Descontar do PLUS no inicio do projeto": "PLUS",
                "Faturar no inicio do projeto": "INICIO",
                "Faturar no final do projeto": "TERMINO",
                "Faturado em outro projeto": "FEOP", # Chave sem o ponto
                "Engajamento": "ENGAJAMENTO"
            }
            if 'Faturamento' in dados.columns:
                dados['Faturamento'] = dados['Faturamento'].astype(str).str.strip()
                # --- INÍCIO ADIÇÃO: Remover ponto final (e outros espaços) --- 
                dados['Faturamento'] = dados['Faturamento'].str.rstrip('. ').str.strip() # Remove . ou espaço do final e strip de novo
                # --- FIM ADIÇÃO ---
                dados['Faturamento_Original'] = dados['Faturamento'] # Guarda após limpeza
                dados['Faturamento'] = dados['Faturamento'].map(faturamento_map)
                nao_mapeados = dados['Faturamento'].isna()
                if nao_mapeados.any():
                    # Agora Faturamento_Original já está limpo, o log mostrará o valor limpo que falhou
                    logger.warning(f"Valores de faturamento não mapeados encontrados (após limpeza): {dados.loc[nao_mapeados, 'Faturamento_Original'].unique().tolist()}")
                    dados['Faturamento'] = dados['Faturamento'].fillna('NAO_MAPEADO')
                logger.info(f"Coluna 'Faturamento' mapeada para códigos curtos. Valores únicos: {dados['Faturamento'].unique().tolist()}")
            else:
                logger.warning("Coluna 'Faturamento' não encontrada para padronização final.")

            # 1.4.3 Padronização de outras colunas de texto
            colunas_texto_padrao = ['Projeto', 'Squad', 'Especialista', 'Account Manager']
            for col in colunas_texto_padrao:
                if col in dados.columns:
                    dados[col] = dados[col].astype(str).str.strip()
                    dados[col] = dados[col].fillna('')
                else:
                    logger.warning(f"Coluna de texto '{col}' não encontrada para padronização final.")
            
            # Log dos valores únicos de Squad após padronização
            if 'Squad' in dados.columns:
                logger.info(f"Valores únicos em 'Squad' após padronização: {dados['Squad'].unique().tolist()}")
            
            # Cálculo de HorasRestantes
            if 'Horas' in dados.columns and 'HorasTrabalhadas' in dados.columns:
                dados['HorasRestantes'] = (dados['Horas'] - dados['HorasTrabalhadas']).round(1)
                logger.info("Coluna 'HorasRestantes' calculada.")
            else:
                logger.warning("Não foi possível calcular 'HorasRestantes': colunas 'Horas' ou 'HorasTrabalhadas' ausentes após renomeação.")
                dados['HorasRestantes'] = 0.0

            logger.info(f"Dados processados com sucesso: {len(dados)} registros")
            return dados
            
        except Exception as e:
            logger.error(f"Erro ao carregar dados: {str(e)}", exc_info=True)
            return pd.DataFrame()

    def obter_dados_e_referencia_atual(self):
        """
        Carrega os dados atuais (dadosr.csv) e determina o mês de referência
        com base na data mais recente da coluna 'UltimaInteracao'.

        Returns:
            tuple: (pd.DataFrame, datetime.datetime) contendo os dados carregados
                   e o mês de referência (primeiro dia do mês). Retorna (DataFrame vazio, None)
                   se os dados não puderem ser carregados ou a data de referência
                   não puder ser determinada.
        """
        logger.info("Obtendo dados e mês de referência atuais...")
        dados_atuais = self.carregar_dados(fonte=None) # Carrega dadosr.csv

        if dados_atuais.empty:
            logger.warning("Não foi possível carregar dados atuais (dadosr.csv).")
            return pd.DataFrame(), None

        # Verifica se a coluna 'UltimaInteracao' (renomeada de 'Data da última ação') existe
        if 'UltimaInteracao' not in dados_atuais.columns:
            logger.error("Coluna 'UltimaInteracao' não encontrada nos dados atuais após renomeação.")
            # Tentar com o nome original como fallback? Ou retornar erro? Por hora, erro.
            return dados_atuais, None # Retorna os dados, mas sem referência

        # Converte para datetime, tratando erros
        datas_interacao = pd.to_datetime(dados_atuais['UltimaInteracao'], errors='coerce')

        # Remove valores NaT (datas inválidas)
        datas_validas = datas_interacao.dropna()

        if datas_validas.empty:
            logger.warning("Nenhuma data válida encontrada na coluna 'UltimaInteracao' para determinar o mês de referência.")
            # Definir um padrão? Usar data do sistema? Por hora, retorna None.
            # Poderia usar: return dados_atuais, datetime.now().replace(day=1)
            return dados_atuais, None

        # Encontra a data mais recente
        data_maxima = datas_validas.max()
        logger.info(f"Data máxima encontrada em 'UltimaInteracao': {data_maxima.strftime('%d/%m/%Y')}")

        # Define o mês de referência como o primeiro dia do mês da data máxima
        mes_referencia_atual = data_maxima.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        logger.info(f"Mês de referência atual determinado: {mes_referencia_atual.strftime('%B/%Y')}")

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
                data_vencimento_fmt = data_vencimento_str.strftime('%d/%m/%Y') if pd.notna(data_vencimento_str) else ''
                
                resultados.append({
                    'numero': numero_val,
                    'projeto': row.get(col_projeto, 'N/A'),
                    'status': row.get(col_status, 'N/A'),
                    'squad': row.get(col_squad, 'N/A'),
                    'especialista': row.get(col_especialista, 'N/A'),
                    'account': account_val,
                    'data_inicio': data_inicio_fmt,
                    'data_vencimento': data_vencimento_fmt,
                    'conclusao': float(row.get(col_conclusao, 0.0)) if pd.notna(row.get(col_conclusao)) else 0.0,
                    'horas_trabalhadas': float(row.get(col_horas_trab, 0.0)) if pd.notna(row.get(col_horas_trab)) else 0.0,
                    'horas_previstas': float(row.get(col_horas_prev, 0.0)) if pd.notna(row.get(col_horas_prev)) else 0.0, # Adicionado Horas previstas
                    'horas_restantes': float(row.get(col_horas_rest, 0.0)) if pd.notna(row.get(col_horas_rest)) else 0.0
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
        - dados: DataFrame com os projetos ativos
        - metricas: métricas específicas dos projetos ativos
        """
        try:
            logger.info("Calculando projetos ativos...")
            
            # Usa dados já tratados
            dados_base = self.preparar_dados_base(dados)
            
            # Filtra apenas projetos ativos (não concluídos) e exclui CDB DATA SOLUTIONS
            projetos_ativos = dados_base[
                (~dados_base['Status'].isin(self.status_concluidos)) &
                (dados_base['Squad'] != 'CDB DATA SOLUTIONS')
            ].copy()
            
            # Calcula métricas específicas
            metricas = {
                'total': len(projetos_ativos),
                'por_squad': projetos_ativos.groupby('Squad').size().to_dict(),
                'media_conclusao': round(projetos_ativos['Conclusao'].mean(), 1),
                'media_horas_restantes': round(projetos_ativos['HorasRestantes'].mean(), 1)
            }
            
            # Prepara dados para o modal
            colunas_modal = ['Numero', 'Projeto', 'Status', 'Squad', 'Conclusao', 'HorasRestantes', 'VencimentoEm', 'Horas']
            
            # Certifica-se de que a coluna Numero existe
            if 'Numero' not in projetos_ativos.columns and 'Número' in projetos_ativos.columns:
                projetos_ativos['Numero'] = projetos_ativos['Número']
            elif 'Numero' not in projetos_ativos.columns:
                logger.warning("Coluna 'Numero' não encontrada. Criando coluna vazia.")
                projetos_ativos['Numero'] = ''
            
            # Seleciona apenas as colunas que existem
            colunas_existentes = [col for col in colunas_modal if col in projetos_ativos.columns]
            dados_modal = projetos_ativos[colunas_existentes].copy()
            
            # Renomeia colunas para o formato esperado pelo frontend
            dados_modal = dados_modal.rename(columns={
                'Numero': 'numero',
                'Projeto': 'projeto',
                'Status': 'status',
                'Squad': 'squad',
                'Conclusao': 'conclusao',
                'HorasRestantes': 'horasRestantes',
                'VencimentoEm': 'dataPrevEnc'
            })
            
            # Formata a data de vencimento
            dados_modal['dataPrevEnc'] = dados_modal['dataPrevEnc'].dt.strftime('%d/%m/%Y')
            dados_modal['dataPrevEnc'].fillna('N/A', inplace=True)
            
            return {
                'total': metricas['total'],
                'dados': dados_modal.replace({np.nan: None}),
                'metricas': metricas
            }
            
        except Exception as e:
            logger.error(f"Erro ao calcular projetos ativos: {str(e)}", exc_info=True)
            return {'total': 0, 'dados': pd.DataFrame(), 'metricas': {}}

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
            
            # Prepara dados para o modal
            colunas_modal = ['Numero', 'Projeto', 'Status', 'Squad', 'Conclusao', 'HorasRestantes', 'VencimentoEm', 'motivo', 'Horas']
            
            # Certifica-se de que a coluna Numero existe
            if 'Numero' not in projetos_criticos.columns and 'Número' in projetos_criticos.columns:
                projetos_criticos['Numero'] = projetos_criticos['Número']
            elif 'Numero' not in projetos_criticos.columns:
                logger.warning("Coluna 'Numero' não encontrada em projetos críticos. Criando coluna vazia.")
                projetos_criticos['Numero'] = ''
            
            # Seleciona apenas as colunas que existem
            colunas_existentes = [col for col in colunas_modal if col in projetos_criticos.columns]
            dados_modal = projetos_criticos[colunas_existentes].copy()
            
            # Renomeia colunas para o formato esperado pelo frontend
            dados_modal = dados_modal.rename(columns={
                'Numero': 'numero',
                'Projeto': 'projeto',
                'Status': 'status',
                'Squad': 'squad',
                'Conclusao': 'conclusao',
                'HorasRestantes': 'horasRestantes',
                'VencimentoEm': 'dataPrevEnc'
            })
            
            # Formata a data de vencimento
            dados_modal['dataPrevEnc'] = dados_modal['dataPrevEnc'].dt.strftime('%d/%m/%Y')
            dados_modal['dataPrevEnc'].fillna('N/A', inplace=True)
            
            return {
                'total': metricas['total'],
                'dados': dados_modal.replace({np.nan: None}),
                'metricas': metricas
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
            
            # Prepara dados para o modal
            colunas_modal = ['Projeto', 'Status', 'Squad', 'Horas', 'HorasTrabalhadas', 'DataTermino']
            dados_modal = projetos_concluidos[colunas_modal].copy()
            
            # Renomeia colunas para o formato esperado pelo frontend
            dados_modal = dados_modal.rename(columns={
                'Projeto': 'projeto',
                'Status': 'status',
                'Squad': 'squad',
                'Horas': 'horasContratadas',
                'HorasTrabalhadas': 'horasTrabalhadas',
                'DataTermino': 'dataTermino'
            })
            
            # Arredonda as horas para uma casa decimal
            dados_modal['horasContratadas'] = dados_modal['horasContratadas'].round(1)
            dados_modal['horasTrabalhadas'] = dados_modal['horasTrabalhadas'].round(1)
            
            # Formata a data de término para o padrão brasileiro
            dados_modal['dataTermino'] = pd.to_datetime(dados_modal['dataTermino']).dt.strftime('%d/%m/%Y')
            
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
            if 'HorasRestantes' in dados_base.columns and 'VencimentoEm' in dados_base.columns:
                try:
                    dias_ate_termino = (projetos_nao_concluidos['VencimentoEm'] - hoje).dt.days
                    horas_por_dia = projetos_nao_concluidos['HorasRestantes'] / dias_ate_termino.clip(lower=1)
                    horas_criticas_prazo = (
                        (dias_ate_termino > 0) &  # Garante que não está vencido
                        (horas_por_dia < 1)  # Menos de 1 hora por dia até o prazo
                    )
                    condicoes.append(horas_criticas_prazo)
                    logger.debug(f"Projetos com poucas horas por dia até o prazo: {len(projetos_nao_concluidos[horas_criticas_prazo])}")
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
                
                if 'HorasRestantes' in dados_base.columns and 'VencimentoEm' in dados_base.columns:
                    dias_ate_termino = (projetos_risco['VencimentoEm'] - hoje).dt.days
                    horas_por_dia = projetos_risco['HorasRestantes'] / dias_ate_termino.clip(lower=1)
                    mascara_horas_dia = (
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

            # Prepara dados para o modal
            colunas_modal = ['Projeto', 'Status', 'Squad', 'Horas', 'HorasTrabalhadas', 'eficiencia']
            dados_modal = projetos_validos[colunas_modal].copy()
            
            # Renomeia colunas para o formato esperado pelo frontend
            dados_modal = dados_modal.rename(columns={
                'Projeto': 'projeto',
                'Status': 'status',
                'Squad': 'squad',
                'Horas': 'horasContratadas',
                'HorasTrabalhadas': 'horasTrabalhadas',
                'eficiencia': 'eficiencia'
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
                    fora_prazo = (validos_para_prazo['VencimentoEm'] < inicio_mes_ref).sum()

                    logger.info(f"Contagem Final Prazo: No Prazo = {no_prazo}, Fora Prazo = {fora_prazo}")
                    
                    projetos_sem_vencimento = total_mes - len(validos_para_prazo) # Ajuste para comparar com o total após dropna
                    if projetos_sem_vencimento > 0:
                        logger.warning(f"{projetos_sem_vencimento} projetos concluídos no mês não possuem data de vencimento válida e foram ignorados no cálculo de prazo.")
                else:
                     logger.warning("Nenhum projeto concluído no mês com data de vencimento válida encontrado após dropna.") # Log ajustado
            else:
                 logger.warning("Coluna 'VencimentoEm' não encontrada ou DataFrame 'dados_filtrados' vazio. Não foi possível calcular no_prazo/fora_prazo.")

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
                        # Adicionar mapeamentos futuros aqui (Abril, Maio, etc.)
                    
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
            
            # Calcular projetos entregues no prazo e fora do prazo (mesma lógica da função original)
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
                        logger.warning(f"[Visão Atual] {projetos_sem_vencimento} projetos concluídos não possuem data de vencimento válida.")
                else:
                     logger.warning("[Visão Atual] Nenhum projeto concluído com data de vencimento válida encontrado.")
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
            
            logger.info(f"[Visão Atual] Projetos entregues calculados: {total_mes} no total, {no_prazo} no prazo, {fora_prazo} fora do prazo")
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
            logger.exception(f"Erro ao calcular novos projetos do mês: {str(e)}")
            return {'por_squad': {}, 'total': 0}

    def calcular_novos_projetos_atual(self, dados, mes_referencia):
        """
        Calcula a quantidade de projetos iniciados no mês de referência para a Visão Atual
        e compara com o mês anterior, carregando a fonte histórica dinamicamente.

        Args:
            dados: DataFrame com os dados dos projetos (geralmente dadosr.csv).
            mes_referencia: Data (datetime) do mês de referência determinado dinamicamente.

        Returns:
            Dictionary com a comparação: {'por_squad': {...}, 'total': {...}}
        """
        try:
            logger.info(f"[Visão Atual] Calculando comparação de novos projetos para {mes_referencia.strftime('%m/%Y')}...")

            # 1. Calcula novos projetos para o mês de referência (atual)
            novos_projetos_atual = self.calcular_novos_projetos_mes(dados, mes_referencia)
            logger.info(f"  Novos projetos (atual - {mes_referencia.strftime('%m/%Y')}): {novos_projetos_atual['total']}")

            # 2. Calcula o mês anterior
            primeiro_dia_mes_ref = mes_referencia.replace(day=1)
            ultimo_dia_mes_anterior = primeiro_dia_mes_ref - timedelta(days=1)
            mes_comparativo = ultimo_dia_mes_anterior.replace(day=1)
            logger.info(f"  Mês comparativo determinado: {mes_comparativo.strftime('%m/%Y')}")

            # 3. Tenta carregar dados do mês anterior
            novos_projetos_anterior = {'por_squad': {}, 'total': 0} # Default
            fonte_anterior = self._obter_fonte_historica(mes_comparativo.year, mes_comparativo.month)
            
            dados_anterior = pd.DataFrame() # Inicializa vazio
            if fonte_anterior:
                logger.info(f"  Tentando carregar dados da fonte anterior: {fonte_anterior}")
                try:
                    dados_anterior = self.carregar_dados(fonte=fonte_anterior)
                    if not dados_anterior.empty:
                        logger.info(f"    Fonte anterior '{fonte_anterior}' carregada com sucesso.")
                        # Calcula novos projetos para o mês anterior
                        novos_projetos_anterior = self.calcular_novos_projetos_mes(dados_anterior, mes_comparativo)
                        logger.info(f"    Novos projetos (anterior - {mes_comparativo.strftime('%m/%Y')}): {novos_projetos_anterior['total']}")
                    else:
                        logger.warning(f"    Fonte anterior '{fonte_anterior}' carregada, mas está vazia.")
                except Exception as e_load_ant:
                     logger.error(f"    Erro ao carregar ou processar dados da fonte anterior '{fonte_anterior}': {e_load_ant}")                 
            else:
                 # Tenta usar valores fixos como fallback (se aplicável)
                 ano_ant = mes_comparativo.year
                 mes_ant = mes_comparativo.month
                 if ano_ant == 2024 and mes_ant == 12:
                      # Exemplo: Definir valores fixos para Dez/24 se a fonte não existir
                      # novos_projetos_anterior = {'por_squad': {'AZURE': 2, ...}, 'total': 5}
                      logger.warning(f"  Fonte para {mes_comparativo.strftime('%m/%Y')} não encontrada, usando valores fixos (se definidos).")
                      # Implementar lógica de valores fixos aqui se necessário
                      pass # Por enquanto, mantém zerado
                 elif ano_ant == 2025 and mes_ant == 1:
                      # Exemplo: Definir valores fixos para Jan/25
                      # novos_projetos_anterior = {'por_squad': {'M365': 3, ...}, 'total': 6}
                      logger.warning(f"  Fonte para {mes_comparativo.strftime('%m/%Y')} não encontrada, usando valores fixos (se definidos).")
                      pass # Por enquanto, mantém zerado
                 else:
                      logger.warning(f"  Nenhuma fonte ou valor fixo encontrado para o mês comparativo: {mes_comparativo.strftime('%m/%Y')}")
            
            # 4. Calcula a comparação
            novos_projetos_comparativo = {
                'por_squad': {},
                'total': {
                    'atual': novos_projetos_atual['total'],
                    'anterior': novos_projetos_anterior['total'],
                    'variacao_pct': 0,
                    'variacao_abs': 0
                }
            }
            # Assume squads principais (pode ser pego do contexto no futuro)
            squads_para_comparar = ['AZURE', 'M365', 'DATA E POWER', 'CDB'] 
            
            for squad in squads_para_comparar:
                qtd_atual = novos_projetos_atual['por_squad'].get(squad, 0) 
                qtd_anterior = novos_projetos_anterior['por_squad'].get(squad, 0)
                variacao_pct = 0
                variacao_abs = qtd_atual - qtd_anterior
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
                
            # Calcula variação total
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
            
            logger.info(f"  Comparativo de novos projetos calculado. Atual: {total_atual}, Anterior: {total_anterior}, VarAbs: {total_variacao_abs} ({total_variacao_pct}%)")
            
            return novos_projetos_comparativo

        except Exception as e:
            logger.exception(f"[Visão Atual] Erro ao calcular comparação de novos projetos: {str(e)}")
            # Retorna estrutura vazia em caso de erro
            return {
                'por_squad': {s: {'atual': 0, 'anterior': 0, 'variacao_pct': 0, 'variacao_abs': 0} for s in ['AZURE', 'M365', 'DATA E POWER', 'CDB']},
                'total': {'atual': 0, 'anterior': 0, 'variacao_pct': 0, 'variacao_abs': 0}
            }

    def _obter_fonte_historica(self, ano, mes):
        """
        Determina o nome da fonte de dados histórica esperada para um dado ano e mês,
        seguindo a convenção 'dadosr_apt_mmm'.

        Args:
            ano (int): O ano.
            mes (int): O número do mês (1-12).

        Returns:
            str or None: O nome da fonte (ex: 'dadosr_apt_jan') ou None se o mês for inválido.
        """
        if not 1 <= mes <= 12:
            logger.warning(f"Mês inválido fornecido para obter fonte histórica: {mes}")
            return None
            
        # Mapeamento de número do mês para abreviação de 3 letras minúsculas
        mes_abbr_map = {
            1: 'jan', 2: 'fev', 3: 'mar', 4: 'abr', 5: 'mai', 6: 'jun',
            7: 'jul', 8: 'ago', 9: 'set', 10: 'out', 11: 'nov', 12: 'dez'
        }
        
        mes_abbr = mes_abbr_map.get(mes)
        
        if mes_abbr:
            nome_fonte = f"dadosr_apt_{mes_abbr}"
            logger.info(f"Nome da fonte histórica determinada para {mes}/{ano}: {nome_fonte}")
            return nome_fonte
        else:
            # Isso não deve acontecer com a validação acima, mas por segurança
            logger.error(f"Não foi possível encontrar a abreviação para o mês {mes}")
            return None

    # --- ADICIONAR NOVO MÉTODO PARA DETALHES DO PROJETO --- 
    def obter_detalhes_projeto(self, project_id):
        """Busca e retorna os detalhes de um projeto específico pelo seu ID numérico."""
        self.logger.info(f"Buscando detalhes para project_id: {project_id}")
        dados_df = self.carregar_dados() 
        
        if dados_df.empty:
            self.logger.warning("DataFrame vazio, não foi possível buscar detalhes do projeto.")
            return None
            
        # Garante que a coluna 'Numero' exista após o carregamento/renomeação
        if 'Numero' not in dados_df.columns:
             self.logger.error("Coluna 'Numero' não encontrada no DataFrame após carregar_dados.")
             return None
             
        try:
            # Converte o project_id (que vem como string da URL) para int para comparação
            # A coluna 'Numero' no DataFrame foi convertida para Int64
            project_id_int = int(project_id)
        except (ValueError, TypeError):
            self.logger.error(f"project_id inválido: {project_id}. Esperado um número.")
            return None

        # Filtra o DataFrame pelo ID do projeto
        # Usamos .loc para acesso baseado em label/condição
        projeto_data = dados_df.loc[dados_df['Numero'] == project_id_int]

        if projeto_data.empty:
            self.logger.warning(f"Nenhum projeto encontrado com Numero = {project_id_int}")
            return None
        
        # Pega a primeira linha (deve ser única)
        # Usamos .iloc[0] para acessar a primeira linha pelo índice posicional
        details = projeto_data.iloc[0]
        
        # Monta o dicionário de retorno com os nomes de campo esperados pelo frontend
        # Usa .get() para evitar erros se alguma coluna não existir (embora devam existir)
        result = {
            'id': project_id, # Mantém o ID original (string)
            'name': details.get('Projeto', 'N/A'),
            'squad': details.get('Squad', 'N/A'),
            'specialist': details.get('Especialista', 'N/A'),
            'status': details.get('Status', 'N/A'),
            'estimated_hours': details.get('Horas', 0.0), # Era 'Esforço estimado'
            'logged_hours': details.get('HorasTrabalhadas', 0.0), # Era 'Tempo trabalhado'
            'remaining_hours': details.get('HorasRestantes', 0.0) # Calculado no carregar_dados
        }
        
        self.logger.info(f"Detalhes encontrados para projeto {project_id}: {result}")
        return result
    # --------------------------------------------------------

    # <<< INÍCIO: Novo método para obter lista de especialistas >>>
    def get_specialist_list(self):
        """Carrega os dados e retorna uma lista única e ordenada de especialistas."""
        try:
            # Carrega os dados (padrão ou de fonte específica, se necessário)
            # Usaremos a fonte padrão (dadosr.csv) por enquanto.
            dados = self.carregar_dados()
            
            if dados.empty or 'Especialista' not in dados.columns:
                self.logger.warning("Não foi possível obter a lista de especialistas: dados vazios ou coluna 'Especialista' ausente.")
                return []
            
            # Obtém valores únicos, remove vazios/nulos, converte para string, ordena e retorna
            specialists = dados['Especialista'].dropna().astype(str).unique()
            specialist_list = sorted([spec for spec in specialists if spec.strip()])
            
            self.logger.info(f"Lista de {len(specialist_list)} especialistas únicos obtida.")
            return specialist_list
            
        except Exception as e:
            self.logger.error(f"Erro ao obter lista de especialistas: {e}", exc_info=True)
            return [] # Retorna lista vazia em caso de erro
    # <<< FIM: Novo método para obter lista de especialistas >>>

