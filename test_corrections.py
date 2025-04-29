from app.gerencial.services import GerencialService
import pandas as pd

# Inicializa o serviço
gs = GerencialService()

# Carrega os dados
print("Carregando dados com as correções aplicadas...")
dados = gs.carregar_dados()

# Verificar a distribuição de faturamento após as correções
print("\n===== DISTRIBUIÇÃO DE FATURAMENTO APÓS CORREÇÕES =====")
faturamento_counts = dados['Faturamento'].value_counts()
print(faturamento_counts)

# Verificar se ainda existem projetos NAO_MAPEADO
nao_mapeados = dados[dados['Faturamento'] == 'NAO_MAPEADO']
print(f"\nTotal de projetos NAO_MAPEADO após correções: {len(nao_mapeados)}")

if not nao_mapeados.empty:
    print("\nValores originais que ainda estão sendo mapeados para NAO_MAPEADO:")
    for val in nao_mapeados['Faturamento_Original'].unique():
        count = nao_mapeados[nao_mapeados['Faturamento_Original'] == val].shape[0]
        print(f"Valor: '{val}' | Contagem: {count}")
    
    print("\nAmostra dos projetos ainda mapeados como NAO_MAPEADO:")
    print(nao_mapeados[['Projeto', 'Faturamento_Original', 'Faturamento']].head().to_string(index=False))
else:
    print("Sucesso! Não existem mais projetos classificados como NAO_MAPEADO.")

print("\nVerificando projetos anteriormente classificados como 'nan':")
nan_projetos = dados[dados['Faturamento_Original'] == 'nan']
if not nan_projetos.empty:
    print(f"Total: {len(nan_projetos)} projetos")
    print(f"Novo faturamento atribuído: {nan_projetos['Faturamento'].unique().tolist()}")
    print(nan_projetos[['Projeto', 'Faturamento_Original', 'Faturamento']].head().to_string(index=False))
else:
    print("Nenhum projeto com valor 'nan' encontrado.") 