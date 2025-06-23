"""
Script para verificar se o projeto [10407] Copilot SOU 
está sendo contabilizado como FEOP no consolidado
"""
from app.macro.periodo_fiscal_service import StatusReportHistoricoService
import pandas as pd

def verificar_copilot_sou():
    """
    Verifica especificamente o projeto Copilot SOU
    """
    print("🔍 VERIFICANDO PROJETO [10407] COPILOT SOU")
    print("=" * 50)
    
    service = StatusReportHistoricoService()
    
    # Carrega dados de fevereiro onde está o Copilot SOU
    print("\n📅 Carregando dados de Fevereiro...")
    dados_fev = service._carregar_dados_mes_historico('dadosr_apt_fev.csv')
    
    if dados_fev is not None and not dados_fev.empty:
        # Procura pelo projeto Copilot SOU
        copilot_sou = dados_fev[dados_fev['Numero'] == 10407]
        
        if not copilot_sou.empty:
            projeto = copilot_sou.iloc[0]
            
            print(f"📋 PROJETO ENCONTRADO:")
            print(f"   ID: {projeto.get('Numero', 'N/A')}")
            print(f"   Cliente: '{projeto.get('Cliente', 'N/A')}'")
            print(f"   Faturamento: '{projeto.get('Faturamento', 'N/A')}'")
            print(f"   Status: {projeto.get('Status', 'N/A')}")
            print(f"   DataInicio: {projeto.get('DataInicio', 'N/A')}")
            
            # Verifica se seria filtrado pelo filtro SOU.cloud
            cliente = projeto.get('Cliente', '')
            seria_filtrado = 'SOU.cloud' in str(cliente)
            
            print(f"\n🔍 ANÁLISE DO FILTRO:")
            print(f"   Cliente contém 'SOU.cloud'? {seria_filtrado}")
            print(f"   Seria filtrado pelo filtro atual? {'SIM' if seria_filtrado else 'NÃO'}")
            
            if not seria_filtrado:
                print(f"   ⚠️ ESSE É O PROBLEMA: Cliente '{cliente}' não é filtrado")
                print(f"   💡 Solução: Incluir 'Copilot SOU' no filtro ou normalizar para 'SOU.cloud'")
            
            # Verifica se é projeto novo de fevereiro
            data_inicio_str = str(projeto.get('DataInicio', ''))
            print(f"\n📅 VERIFICAÇÃO DE MÊS:")
            print(f"   DataInicio: {data_inicio_str}")
            
            if '19/02/2025' in data_inicio_str or '2025-02' in data_inicio_str:
                print(f"   ✅ É projeto NOVO de Fevereiro")
            else:
                print(f"   ❓ Verificar se é contabilizado como novo projeto")
        else:
            print("❌ Projeto [10407] Copilot SOU não encontrado em Fevereiro")
    else:
        print("❌ Erro ao carregar dados de Fevereiro")
    
    # Testa também o resultado consolidado
    print(f"\n🔄 Testando resultado consolidado...")
    resultado = service.calcular_kpis_periodo_historico(['jan', 'fev', 'mar', 'abr', 'mai', 'jun'])
    
    if 'kpis_gerais' in resultado and 'distribuicao_faturamento' in resultado['kpis_gerais']:
        distribuicao = resultado['kpis_gerais']['distribuicao_faturamento']
        feop_consolidado = distribuicao.get('FEOP', 0)
        print(f"📊 FEOP no resultado consolidado: {feop_consolidado}")
        
        if feop_consolidado == 1:
            print(f"✅ Confirmado: 1 projeto FEOP no consolidado")
            print(f"💡 Muito provavelmente é o [10407] Copilot SOU")
    
    return copilot_sou if 'copilot_sou' in locals() and not copilot_sou.empty else None

if __name__ == "__main__":
    verificar_copilot_sou() 