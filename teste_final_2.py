#!/usr/bin/env python3
"""
Teste final para verificar se o dePara está funcionando corretamente
"""
import sys
import os

# Adiciona o diretório do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.macro.periodo_fiscal_service import StatusReportHistoricoService

def main():
    print("🎯 TESTE FINAL COMPLETO - dePara para corrigir distribuição por squad")
    
    try:
        # Inicializa serviço
        service = StatusReportHistoricoService()
        
        # Meses padrão (Jan-Mai)
        meses = ['jan', 'fev', 'mar', 'abr', 'mai']
        
        print(f"📅 Testando período: {' '.join([m.upper() for m in meses])}")
        print(f"🔍 Esperando que o dePara corrija automaticamente a distribuição de 91 projetos")
        
        # Calcula KPIs com dePara automático
        resultado = service.calcular_kpis_periodo_historico(meses)
        
        if resultado and 'kpis_gerais' in resultado:
            kpis = resultado['kpis_gerais']
            
            print(f"\n📊 === RESULTADO FINAL ===")
            projetos_fechados = kpis.get('projetos_fechados', 0)
            projetos_abertos = kpis.get('projetos_abertos', 0)
            horas_trabalhadas = kpis.get('horas_trabalhadas', 0)
            
            print(f"📈 Projetos Fechados: {projetos_fechados}")
            print(f"🆕 Projetos Abertos: {projetos_abertos}")
            print(f"⏱️ Horas Trabalhadas: {horas_trabalhadas:.1f}")
            
            # Verifica distribuição por squad
            distribuicao = kpis.get('distribuicao_squad', {})
            if 'total_squad' in distribuicao:
                squad_dist = distribuicao['total_squad']
                
                azure = squad_dist.get('AZURE', 0)
                m365 = squad_dist.get('M365', 0)
                data_power = squad_dist.get('DATA E POWER', 0)
                total_squad = azure + m365 + data_power
                
                print(f"\n🎯 === DISTRIBUIÇÃO POR SQUAD ===")
                print(f"🔵 AZURE: {azure}")
                print(f"🟠 M365: {m365}")
                print(f"🟢 DATA E POWER: {data_power}")
                print(f"📊 Total Squad: {total_squad}")
                
                # Verifica consistência
                if total_squad == 91 and projetos_abertos == 91:
                    print(f"\n✅ 🎉 SUCESSO COMPLETO!")
                    print(f"   ✅ Projetos abertos: {projetos_abertos} = 91 ✓")
                    print(f"   ✅ Total squad: {total_squad} = 91 ✓")
                    print(f"   ✅ Consistência perfeita alcançada!")
                    print(f"   🎯 O dePara funcionou exatamente como esperado!")
                    return True
                elif total_squad > 0:
                    print(f"\n⚠️ PARCIALMENTE FUNCIONAL")
                    print(f"   📊 Total squad: {total_squad} (esperado: 91)")
                    print(f"   📊 Projetos abertos: {projetos_abertos} (esperado: 91)")
                    if total_squad == projetos_abertos:
                        print(f"   ✅ Pelo menos há consistência entre squad e projetos abertos")
                    print(f"   🔧 O dePara funcionou, mas pode precisar de ajustes")
                    return False
                else:
                    print(f"\n❌ FALHA NA DISTRIBUIÇÃO")
                    print(f"   ❌ Total squad: {total_squad} (todos zerados)")
                    print(f"   📊 Projetos abertos: {projetos_abertos}")
                    print(f"   💥 O dePara não foi aplicado corretamente")
                    return False
            else:
                print(f"\n❌ ERRO: Distribuição por squad não encontrada no resultado")
                return False
        else:
            print(f"\n❌ ERRO: KPIs não encontrados no resultado")
            if resultado and 'erro' in resultado:
                print(f"💥 Erro relatado: {resultado['erro']}")
            return False
            
    except Exception as e:
        print(f"\n💥 ERRO CRÍTICO: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    sucesso = main()
    if sucesso:
        print(f"\n🏆 TESTE CONCLUÍDO COM SUCESSO!")
    else:
        print(f"\n⚠️ TESTE CONCLUÍDO COM PROBLEMAS") 