#!/usr/bin/env python3
import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime, date

# Configurando logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Adicionando diretório raiz ao path para importações
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Importando o serviço
from app.gerencial.services import processar_gerencial, GerencialService

def testar_datas():
    """Testa especificamente as questões de data de vencimento"""
    print("\n" + "=" * 50)
    print("Teste detalhado das datas de vencimento")
    print("=" * 50)
    
    service = GerencialService()
    dados = service.carregar_dados()
    
    if dados.empty:
        print("Dados vazios!")
        return
    
    # Define o mês e ano atual
    hoje = datetime.now()
    mes_atual = hoje.month
    ano_atual = hoje.year
    
    # Filtrar os projetos potenciais para faturar
    projetos_prime_plus_inicio = dados[dados['Faturamento'].isin(['PRIME', 'PLUS', 'INICIO'])]
    projetos_engajamento_termino = dados[dados['Faturamento'].isin(['TERMINO', 'ENGAJAMENTO'])]
    
    print(f"\nProjetos com faturamento PRIME/PLUS/INICIO: {len(projetos_prime_plus_inicio)}")
    print(f"Projetos com faturamento FINAL/ENGAJAMENTO: {len(projetos_engajamento_termino)}")
    
    # Verifica valores de DataTermino e VencimentoEm
    df_datas = dados.copy()
    
    # Para os projetos para faturar, verificamos as datas individualmente
    cond_inicio = (
        df_datas['Faturamento'].isin(['PRIME', 'PLUS', 'INICIO']) &
        (df_datas['DataInicio'].dt.month == mes_atual) &
        (df_datas['DataInicio'].dt.year == ano_atual)
    )
    
    cond_termino = (
        df_datas['Faturamento'].isin(['TERMINO', 'ENGAJAMENTO']) &
        (
            # Verifica se a data prevista (VencimentoEm) é no mês atual para projetos em andamento
            ((~df_datas['Status'].isin(['Fechado', 'Resolvido'])) & 
             (df_datas['VencimentoEm'].dt.month == mes_atual) & 
             (df_datas['VencimentoEm'].dt.year == ano_atual)) |
            # OU se a data de término (DataTermino) é no mês atual para projetos concluídos
            ((df_datas['Status'].isin(['Fechado', 'Resolvido'])) & 
             (df_datas['DataTermino'].dt.month == mes_atual) & 
             (df_datas['DataTermino'].dt.year == ano_atual))
        )
    )
    
    # Projetos que entram para faturar
    projetos_para_faturar = df_datas[
        (cond_inicio | cond_termino) & 
        (df_datas['Faturamento'] != 'FTOP')
    ]
    
    # Exibe informações detalhadas sobre as datas desses projetos
    print(f"\nDetalhes dos {len(projetos_para_faturar)} projetos que entram para faturar:")
    for idx, row in projetos_para_faturar.iterrows():
        data_inicio = row['DataInicio'].strftime('%d/%m/%Y') if pd.notna(row['DataInicio']) else 'N/A'
        data_termino = row['DataTermino'].strftime('%d/%m/%Y') if pd.notna(row['DataTermino']) else 'N/A'
        vencimento_em = row['VencimentoEm'].strftime('%d/%m/%Y') if pd.notna(row['VencimentoEm']) else 'N/A'
        
        print(f"\n{row['Projeto']} - {row['Faturamento']} - {row['Status']}")
        print(f"  DataInicio: {data_inicio}")
        print(f"  DataTermino: {data_termino}")
        print(f"  VencimentoEm: {vencimento_em}")

if __name__ == "__main__":
    print("=" * 50)
    print("Teste de projetos para faturar")
    print("=" * 50)
    
    service = GerencialService()
    service.teste_projetos_para_faturar()
    
    # Executar teste adicional para datas
    testar_datas()

    print("\n==================================================")
    print("Teste das métricas gerenciais")
    print("==================================================")
    gerencial = GerencialService()
    metricas = gerencial.obter_metricas_gerencial()
    print(f"Total de projetos: {metricas['total_projetos']}")
    print(f"Projetos ativos: {metricas['projetos_ativos']}")
    print(f"Projetos em atendimento: {metricas['projetos_em_atendimento']}")
    print(f"Projetos críticos: {metricas['projetos_criticos']}")
    print(f"Projetos para faturar: {metricas['projetos_para_faturar']}") 