# Automação do Quarter Fiscal no Card Performance de Entregas

## Problema Identificado
O Card Performance de Entregas no módulo Gerencial estava **fixo** no Q4 FY25 (01/04/2025 a 30/06/2025), não se atualizando automaticamente conforme o período atual.

## Solução Implementada

### 1. **Função Auxiliar para Quarters Fiscais Microsoft**
**Arquivo**: `app/gerencial/services.py`  
**Função**: `_calcular_quarter_fiscal_atual()`

```python
def _calcular_quarter_fiscal_atual(self):
    """
    Calcula o quarter fiscal atual baseado no modelo Microsoft.
    
    Quarters fiscais Microsoft:
    - Q1: 01/07 a 30/09
    - Q2: 01/10 a 31/12  
    - Q3: 01/01 a 31/03
    - Q4: 01/04 a 30/06
    """
    hoje = datetime.now()
    
    # Determina quarter baseado no mês atual
    if 7 <= hoje.month <= 9:  # Q1
        quarter = "Q1"
        inicio_periodo = datetime(hoje.year, 7, 1)
        fim_periodo = datetime(hoje.year, 9, 30)
        ano_fiscal = hoje.year + 1
    elif 10 <= hoje.month <= 12:  # Q2
        quarter = "Q2"
        inicio_periodo = datetime(hoje.year, 10, 1)
        fim_periodo = datetime(hoje.year, 12, 31)
        ano_fiscal = hoje.year + 1
    elif 1 <= hoje.month <= 3:  # Q3
        quarter = "Q3"
        inicio_periodo = datetime(hoje.year, 1, 1)
        fim_periodo = datetime(hoje.year, 3, 31)
        ano_fiscal = hoje.year
    else:  # Q4 (abril a junho)
        quarter = "Q4"
        inicio_periodo = datetime(hoje.year, 4, 1)
        fim_periodo = datetime(hoje.year, 6, 30)
        ano_fiscal = hoje.year
    
    return {
        'quarter': quarter,
        'ano_fiscal': ano_fiscal,
        'inicio_periodo': inicio_periodo,
        'fim_periodo': fim_periodo,
        'quarter_display': f"{quarter} - FY{str(ano_fiscal)[-2:]}"
    }
```

### 2. **Atualização da Função de Performance**
**Mudança na função**: `_calcular_metricas_performance()`

```python
# ANTES (fixo)
inicio_periodo = datetime(2025, 4, 1)
fim_periodo = datetime(2025, 6, 30)

# DEPOIS (automático)
quarter_info = self._calcular_quarter_fiscal_atual()
inicio_periodo = quarter_info['inicio_periodo']
fim_periodo = quarter_info['fim_periodo']
```

### 3. **Informações do Quarter Atualizadas**
O `quarter_info` agora é dinâmico:

```python
metricas['quarter_info'] = {
    'quarter': quarter_info['quarter_display'],  # Ex: "Q1 - FY26"
    'inicio': inicio_periodo.strftime('%d/%m/%Y'),
    'fim': fim_periodo.strftime('%d/%m/%Y'),
    'total_projetos_previstos': total_previstos,
    'projetos_concluidos': total_concluidos,
    'projetos_entregues_mes_previsto': total_entregues_mes_previsto,
    'projetos_em_andamento': total_previstos - total_concluidos
}
```

## Lógica dos Quarters Fiscais Microsoft

| Quarter | Período | Exemplo FY26 |
|---------|---------|--------------|
| Q1 | 01/07 a 30/09 | 01/07/2025 a 30/09/2025 |
| Q2 | 01/10 a 31/12 | 01/10/2025 a 31/12/2025 |
| Q3 | 01/01 a 31/03 | 01/01/2026 a 31/03/2026 |
| Q4 | 01/04 a 30/06 | 01/04/2026 a 30/06/2026 |

## Comportamento Atual
- **Se hoje é 03/07/2025**: Mostra Q1 - FY26 (01/07/2025 a 30/09/2025)
- **Se hoje é 15/11/2025**: Mostra Q2 - FY26 (01/10/2025 a 31/12/2025)
- **Se hoje é 20/02/2026**: Mostra Q3 - FY26 (01/01/2026 a 31/03/2026)
- **Se hoje é 05/05/2026**: Mostra Q4 - FY26 (01/04/2026 a 30/06/2026)

## Critérios de Performance

### **Taxa de Sucesso**
- **Numerador**: Projetos concluídos no mês previsto (mês/ano término = mês/ano vencimento)
- **Denominador**: Projetos com vencimento no quarter atual
- **Fórmula**: `(Entregues no Mês Previsto / Previstos) * 100`

### **Tempo Médio de Entrega**
- **Base**: Projetos concluídos no prazo (DataTermino <= VencimentoEm)
- **Cálculo**: Média de dias entre DataInicio e DataTermino
- **Filtros**: Remove outliers (< 0 ou > 365 dias)

## Melhorias Implementadas
1. ✅ **Automação Total**: Não requer mais alterações manuais
2. ✅ **Compatibilidade**: Mantém toda a lógica existente
3. ✅ **Flexibilidade**: Funciona para qualquer data/quarter
4. ✅ **Logs Detalhados**: Auditoria completa do período calculado
5. ✅ **Remoção de Código Duplicado**: Elimina duplicação de funções

## Exemplo de Logs
```
=== PERÍODO DE ANÁLISE (AUTOMÁTICO) ===
Quarter: Q1 - FY26
Início: 2025-07-01 00:00:00
Fim: 2025-09-30 00:00:00
```

## Status da Implementação
- ✅ Função auxiliar criada
- ✅ Função de performance atualizada
- ✅ Logs atualizados
- ✅ Documentação criada
- ✅ Código duplicado removido
- ✅ **IMPLEMENTAÇÃO CONCLUÍDA COM SUCESSO**

## Resultado Final
O Card Performance de Entregas agora:
1. **Atualiza automaticamente** o quarter fiscal baseado na data atual
2. **Não requer mais intervenções manuais** para mudanças de período
3. **Mantém 100% de compatibilidade** com a lógica existente
4. **Exibe informações precisas** do quarter fiscal Microsoft atual

**Exemplo atual (03/07/2025)**: Mostra Q1 - FY26 (01/07/2025 a 30/09/2025) 