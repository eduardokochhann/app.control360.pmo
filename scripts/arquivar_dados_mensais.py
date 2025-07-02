#!/usr/bin/env python3
"""
Script para arquivar dados mensais do Control360
Cria cópias dos dados atuais para análise histórica
"""

import os
import sys
import shutil
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

def obter_mes_anterior():
    """Obtém o mês anterior baseado na data atual"""
    hoje = datetime.now()
    primeiro_dia_mes_atual = hoje.replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
    return ultimo_dia_mes_anterior.month, ultimo_dia_mes_anterior.year

def obter_abreviacao_mes(mes_numero):
    """Converte número do mês para abreviação"""
    meses_abbr = {
        1: 'jan', 2: 'fev', 3: 'mar', 4: 'abr', 5: 'mai', 6: 'jun',
        7: 'jul', 8: 'ago', 9: 'set', 10: 'out', 11: 'nov', 12: 'dez'
    }
    return meses_abbr.get(mes_numero)

def obter_nome_mes_completo(mes_numero):
    """Converte número do mês para nome completo"""
    meses_completos = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
        7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }
    return meses_completos.get(mes_numero, f'Mês {mes_numero}')

def arquivar_dados_mensal(mes_numero=None, ano=None, forcar=False):
    """
    Arquiva os dados atuais para o mês especificado
    
    Args:
        mes_numero: Número do mês (1-12). Se None, usa o mês anterior
        ano: Ano. Se None, usa o ano atual ou anterior conforme o mês
        forcar: Se True, sobrescreve arquivo existente
    """
    
    # Define mês e ano se não especificados
    if mes_numero is None:
        mes_numero, ano_anterior = obter_mes_anterior()
        if ano is None:
            ano = ano_anterior
    elif ano is None:
        ano = datetime.now().year
    
    # Obter abreviação do mês
    mes_abbr = obter_abreviacao_mes(mes_numero)
    if not mes_abbr:
        print(f"ERRO: Mês inválido: {mes_numero}")
        return False
    
    # Caminhos dos arquivos
    projeto_dir = Path(__file__).parent.parent
    data_dir = projeto_dir / 'data'
    arquivo_origem = data_dir / 'dadosr.csv'
    arquivo_destino = data_dir / f'dadosr_apt_{mes_abbr}.csv'
    
    # Verificações
    if not arquivo_origem.exists():
        print(f"ERRO: Arquivo de origem não encontrado: {arquivo_origem}")
        return False
    
    if arquivo_destino.exists() and not forcar:
        print(f"AVISO: Arquivo já existe: {arquivo_destino}")
        print(f"    Use --forcar para sobrescrever")
        return False
    
    try:
        # Criar backup se arquivo já existir
        if arquivo_destino.exists():
            backup_file = data_dir / f'dadosr_apt_{mes_abbr}_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            shutil.copy2(arquivo_destino, backup_file)
            print(f"Backup criado: {backup_file.name}")
        
        # Copiar dados atuais
        shutil.copy2(arquivo_origem, arquivo_destino)
        
        # Verificar integridade do arquivo copiado
        dados_origem = pd.read_csv(arquivo_origem, dtype=str, sep=';', encoding='latin1')
        dados_destino = pd.read_csv(arquivo_destino, dtype=str, sep=';', encoding='latin1')
        
        if len(dados_origem) != len(dados_destino):
            print(f"ERRO: Arquivo copiado tem tamanho diferente!")
            return False
        
        print(f"Dados arquivados com sucesso!")
        print(f"Origem: {arquivo_origem.name} ({len(dados_origem)} registros)")
        print(f"Destino: {arquivo_destino.name}")
        print(f"Mes arquivado: {mes_abbr.capitalize()}/{ano}")
        
        return True
        
    except Exception as e:
        print(f"ERRO ao arquivar dados: {str(e)}")
        return False

def arquivar_automatico():
    """
    Arquivamento automático baseado na data atual
    Arquiva o mês anterior automaticamente
    """
    hoje = datetime.now()
    
    print(f"Iniciando arquivamento automático para o mês anterior...")
    print(f"Data atual: {hoje.strftime('%d/%m/%Y')}")
    
    mes_anterior, ano_anterior = obter_mes_anterior()
    mes_abbr = obter_abreviacao_mes(mes_anterior)
    
    print(f"Arquivando dados de {mes_abbr.capitalize()}/{ano_anterior}")
    
    return arquivar_dados_mensal(mes_anterior, ano_anterior, forcar=True)

def main():
    """Função principal do script"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Arquiva dados mensais do Control360')
    parser.add_argument('--mes', type=int, choices=range(1, 13), 
                       help='Mês para arquivar (1-12)')
    parser.add_argument('--ano', type=int, 
                       help='Ano (padrão: ano atual)')
    parser.add_argument('--forcar', action='store_true', 
                       help='Sobrescrever arquivo existente')
    parser.add_argument('--automatico', action='store_true', 
                       help='Modo automático (arquiva mês anterior se for início do mês)')
    
    args = parser.parse_args()
    
    print("Script de Arquivamento de Dados Mensais - Control360")
    print("=" * 60)
    
    if args.automatico:
        sucesso = arquivar_automatico()
    else:
        if args.mes is None:
            # Modo interativo
            print("Nenhum mês especificado. Usando mês anterior...")
            mes_anterior, ano_anterior = obter_mes_anterior()
            mes_abbr = obter_abreviacao_mes(mes_anterior)
            print(f"Será arquivado: {mes_abbr.capitalize()}/{ano_anterior}")
            
            resposta = input("Confirma? (s/N): ").strip().lower()
            if resposta != 's':
                print("Operação cancelada")
                return
            
            sucesso = arquivar_dados_mensal(mes_anterior, ano_anterior, args.forcar)
        else:
            sucesso = arquivar_dados_mensal(args.mes, args.ano, args.forcar)
    
    if sucesso:
        print("\nArquivamento concluído com sucesso!")
        print("O arquivo pode agora ser usado nas análises históricas")
    else:
        print("\nFalha no arquivamento")
        sys.exit(1)

if __name__ == '__main__':
    main() 