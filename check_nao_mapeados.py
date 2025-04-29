from app.gerencial.services import GerencialService
import pandas as pd

# Inicializa o serviço
gs = GerencialService()

# Carrega os dados
dados = gs.carregar_dados()

# Analisar o mapeamento de faturamento
if 'Faturamento_Original' in dados.columns and 'Faturamento' in dados.columns:
    print("\n===== ANÁLISE DE MAPEAMENTO DE FATURAMENTO =====")
    
    # Mostrar mapeamento definido no código
    faturamento_map = {
        "PRIME": "PRIME",
        "Descontar do PLUS no inicio do projeto": "PLUS",
        "Faturar no inicio do projeto": "INICIO",
        "Faturar no final do projeto": "TERMINO",
        "Faturado em outro projeto": "FEOP",
        "Engajamento": "ENGAJAMENTO"
    }
    print("\nMapeamento definido no código:")
    for k, v in faturamento_map.items():
        print(f"'{k}' -> '{v}'")
    
    # Mostrar valores únicos originais e seus mapeamentos
    print("\nValores únicos originais e seus mapeamentos atuais:")
    faturamento_df = dados[['Faturamento_Original', 'Faturamento']].drop_duplicates()
    for _, row in faturamento_df.iterrows():
        print(f"'{row['Faturamento_Original']}' -> '{row['Faturamento']}'")
    
    # Analise específica dos NAO_MAPEADOS
    nao_mapeados = dados[dados['Faturamento'] == 'NAO_MAPEADO']
    print(f"\nTotal de projetos NAO_MAPEADO: {len(nao_mapeados)}")
    
    print("\nAnálise detalhada dos valores NÃO MAPEADOS:")
    for val in nao_mapeados['Faturamento_Original'].unique():
        count = nao_mapeados[nao_mapeados['Faturamento_Original'] == val].shape[0]
        print(f"Valor: '{val}' | Contagem: {count}")
        
    # Exibe amostra de projetos não mapeados com dados limpos para comparação
    if not nao_mapeados.empty:
        print("\nAmostra de projetos NAO_MAPEADO com valores originais:")
        # Limpar os valores para análise
        sample_df = nao_mapeados[['Projeto', 'Faturamento_Original', 'Faturamento']].head(5)
        sample_df['Faturamento_Original_Limpo'] = sample_df['Faturamento_Original'].str.strip()
        
        # Adiciona uma coluna que sugere o motivo pelo qual não foi mapeado
        sample_df['Motivo_Provável'] = sample_df['Faturamento_Original_Limpo'].apply(
            lambda x: "Texto com formato diferente ('Faturado em outro projeto.' vs 'Faturado em outro projeto')" 
            if "Faturado em outro projeto" in x else "Valor não está no mapeamento"
        )
        
        print(sample_df.to_string(index=False))
        
        print("\nSugestão de correção no mapeamento:")
        print("""
faturamento_map = {
    "PRIME": "PRIME",
    "Descontar do PLUS no inicio do projeto": "PLUS",
    "Faturar no inicio do projeto": "INICIO",
    "Faturar no final do projeto": "TERMINO",
    "Faturado em outro projeto": "FEOP",
    "Faturado em outro projeto.": "FEOP",  # Adicionado ponto final
    "Engajamento": "ENGAJAMENTO"
}
""")
else:
    print("Coluna 'Faturamento_Original' não encontrada nos dados.") 