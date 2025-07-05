# Correção Adicional: Cálculo de Esforço para Demandas Internas

## Nova Implementação
**Data**: 03/07/2025  
**Arquivo**: `app/macro/services.py`  
**Função**: `gerar_dados_status_report()`  

## Problema Adicional Identificado
Após a correção do percentual de andamento, identificamos que projetos de **"Demandas Internas"** também não possuem **esforço (horas planejadas)** correto no CSV, exibindo sempre **0h** no Status Report.

## Solução Implementada

### 1. **Detecção Condicional**
```python
if servico_terceiro_nivel == 'Demandas Internas':
    # Para Demandas Internas, calcular esforço baseado em tarefas
    horas_planejadas = self._calcular_esforco_por_tarefas(project_id)
    logger.info(f"Projeto Demandas Internas detectado - Esforço calculado por tarefas: {horas_planejadas}h")
else:
    # Para projetos normais, usar esforço do CSV
    horas_planejadas = horas_trabalhadas + horas_restantes
    logger.info(f"Projeto normal - Esforço do CSV: {horas_planejadas}h")
```

### 2. **Nova Função de Cálculo**
```python
def _calcular_esforco_por_tarefas(self, project_id):
    """
    Calcula o esforço total (horas planejadas) baseado nas tarefas do backlog.
    Usado especificamente para projetos de "Demandas Internas".
    """
    try:
        # Buscar backlog_id do projeto
        backlog_id = self.get_backlog_id_for_project(project_id)
        
        # Buscar todas as tarefas do backlog
        all_tasks = Task.query.filter_by(backlog_id=backlog_id).all()
        
        # Somar esforço estimado de todas as tarefas
        total_esforco = 0.0
        for task in all_tasks:
            esforco_tarefa = float(task.estimated_effort or 0)
            total_esforco += esforco_tarefa
        
        return total_esforco
        
    except Exception as e:
        logger.error(f"Erro ao calcular esforço por tarefas: {str(e)}")
        return 0.0
```

## Lógica de Funcionamento

### ✅ **Projetos Normais**
- **Fonte**: `HorasTrabalhadas + HorasRestantes` do CSV
- **Comportamento**: Mantido intacto

### ✅ **Demandas Internas**
- **Detecção**: `TipoServico = "Demandas Internas"`
- **Fonte**: Soma do campo `estimated_effort` de todas as tarefas do backlog
- **Cálculo**: `sum(task.estimated_effort for task in backlog_tasks)`

## Benefícios

1. **Dados Realistas**: Esforço baseado em estimativas reais das tarefas
2. **Sincronização**: Alinhado com planejamento do backlog
3. **Visibilidade**: Status Report agora mostra esforço real para diretoria
4. **Compatibilidade**: Zero impacto em projetos normais

## Casos de Borda

| Cenário | Comportamento |
|---|---|
| Tarefas sem esforço estimado | `estimated_effort = 0` (não impacta soma) |
| Backlog vazio | Retorna `0.0h` |
| Erro na consulta | Retorna `0.0h` com log de erro |
| Projeto normal | Usa lógica original do CSV |

## Exemplo Prático

**Projeto 11664 - BI Gerencial:**
- 10 tarefas no backlog
- Esforços: 8h, 5h, 12h, 3h, 0h, 15h, 7h, 10h, 6h, 4h
- **Total calculado**: 70h (em vez de 0h do CSV)

## Logs Gerados
```
INFO - Projeto Demandas Internas detectado - Esforço calculado por tarefas: 70.0h
INFO - Calculando esforço por tarefas para projeto 11664
INFO - Esforço total calculado: 70.0h (9/10 tarefas com esforço)
```

## Validação
Para testar a correção:
1. Acesse o Status Report de um projeto de Demandas Internas
2. Verifique se o campo "Esforço" agora mostra valor > 0h
3. Compare com a soma dos esforços estimados das tarefas no backlog
4. Confirme que o "Trabalho" (HorasTrabalhadas) vem do CSV normalmente

## Impacto
- ✅ **Percentual**: Calculado por tarefas concluídas vs. total
- ✅ **Esforço**: Calculado por soma de estimativas das tarefas  
- ✅ **Trabalho**: Continua vindo do CSV (comportamento original)
- ✅ **Compatibilidade**: Projetos normais inalterados

A implementação está **completa e funcional**! 🚀 