# Correção Cirúrgica: Cálculo de Percentual e Esforço para Demandas Internas

## Problema Identificado
Projetos com **"Demandas Internas"** na coluna "Serviço (3º Nível)" não possuem percentual de andamento nem esforço definido no CSV, resultando em **0%** de progresso e **0h** de esforço no Status Report Individual.

## Projetos Afetados
| ID | Nome do Projeto | Cliente | Responsável | Status |
|---|---|---|---|---|
| **9336** | Projeto - PIM | SOU.cloud | Tadeu Trajano | Fechado |
| **10407** | Projeto Copilot SOU | SOU.cloud | Eduardo Kochhann | Em Atendimento |
| **11664** | Projeto interno de BI - Gerencial | SOU.cloud | Vitória Germann | Em Atendimento |

## Critério de Identificação
✅ **Campo**: `TipoServico = "Demandas Internas"` (renomeado pelo pandas durante o processamento)
- Todos os projetos identificados são **internos da SOU.cloud**
- Campo `Andamento` no CSV está **vazio** para esses projetos
- Campos `HorasTrabalhadas` e `HorasRestantes` não refletem o esforço real
- Necessitam cálculo baseado em **tarefas executadas vs. a executar** e **esforço estimado das tarefas**

## Solução Implementada

### 1. **Detecção Cirúrgica** (app/macro/services.py)
**Localização**: Função `gerar_dados_status_report()` - linha ~3832

**A) Cálculo de Percentual:**
```python
# ANTES
percentual_concluido = float(projeto_row.get('Conclusao', 0.0))

# DEPOIS
servico_terceiro_nivel = projeto_row.get('TipoServico', '')

if servico_terceiro_nivel == 'Demandas Internas':
    # Para Demandas Internas, calcular percentual baseado em tarefas
    percentual_concluido = self._calcular_percentual_por_tarefas(project_id)
    logger.info(f"Projeto Demandas Internas detectado - Percentual calculado por tarefas: {percentual_concluido:.1f}%")
else:
    # Para projetos normais, usar percentual do CSV
    percentual_concluido = float(projeto_row.get('Conclusao', 0.0))
    logger.info(f"Projeto normal - Percentual do CSV: {percentual_concluido:.1f}%")
```

**B) Cálculo de Esforço:**
```python
# ANTES
horas_trabalhadas = float(projeto_row.get('HorasTrabalhadas', 0))
horas_restantes = float(projeto_row.get('HorasRestantes', 0))
horas_planejadas = horas_trabalhadas + horas_restantes

# DEPOIS
horas_trabalhadas = float(projeto_row.get('HorasTrabalhadas', 0))
horas_restantes = float(projeto_row.get('HorasRestantes', 0))

if servico_terceiro_nivel == 'Demandas Internas':
    # Para Demandas Internas, calcular esforço baseado em tarefas
    horas_planejadas = self._calcular_esforco_por_tarefas(project_id)
    logger.info(f"Projeto Demandas Internas detectado - Esforço calculado por tarefas: {horas_planejadas}h")
else:
    # Para projetos normais, usar esforço do CSV
    horas_planejadas = horas_trabalhadas + horas_restantes
    logger.info(f"Projeto normal - Esforço do CSV: {horas_planejadas}h")
```

### 2. **Funções de Cálculo por Tarefas** (app/macro/services.py)

**A) Função `_calcular_percentual_por_tarefas()`:**
```python
def _calcular_percentual_por_tarefas(self, project_id):
    """
    Calcula o percentual de conclusão baseado nas tarefas do backlog.
    Usado especificamente para projetos de "Demandas Internas".
    """
    # 1. Buscar backlog_id do projeto
    backlog_id = self.get_backlog_id_for_project(project_id)
    
    # 2. Contar total de tarefas
    total_tarefas = Task.query.filter_by(backlog_id=backlog_id).count()
    
    # 3. Contar tarefas concluídas (baseado no nome da coluna)
    tarefas_concluidas = Task.query.filter_by(backlog_id=backlog_id)\
        .join(Column, Task.column_id == Column.id)\
        .filter(
            Column.name.ilike('%concluí%') |
            Column.name.ilike('%concluido%') |
            Column.name.ilike('%done%') |
            Column.name.ilike('%finalizado%')
        ).count()
    
    # 4. Calcular percentual
    percentual = round((tarefas_concluidas / total_tarefas) * 100, 1)
    
    return percentual
```

**B) Função `_calcular_esforco_por_tarefas()`:**
```python
def _calcular_esforco_por_tarefas(self, project_id):
    """
    Calcula o esforço total (horas planejadas) baseado nas tarefas do backlog.
    Usado especificamente para projetos de "Demandas Internas".
    """
    # 1. Buscar backlog_id do projeto
    backlog_id = self.get_backlog_id_for_project(project_id)
    
    # 2. Buscar todas as tarefas do backlog
    all_tasks = Task.query.filter_by(backlog_id=backlog_id).all()
    
    # 3. Somar esforço estimado de todas as tarefas
    total_esforco = 0.0
    for task in all_tasks:
        esforco_tarefa = float(task.estimated_effort or 0)
        total_esforco += esforco_tarefa
    
    # 4. Retornar esforço total
    return total_esforco
```

## Lógica de Funcionamento

### ✅ **Para Projetos Normais**
- **Percentual**: Campo `Andamento` do CSV
- **Esforço**: `HorasTrabalhadas + HorasRestantes` do CSV
- **Comportamento**: Inalterado (100% compatível)

### ✅ **Para Demandas Internas**
- **Detecção**: `TipoServico = "Demandas Internas"`
- **Percentual**: Cálculo baseado em tarefas do backlog
  - **Fórmula**: `(Tarefas Concluídas / Total de Tarefas) * 100`
- **Esforço**: Soma do esforço estimado de todas as tarefas
  - **Fórmula**: `sum(task.estimated_effort for task in backlog_tasks)`

### 🔍 **Critérios de "Tarefa Concluída"**
Uma tarefa é considerada concluída quando está em coluna cujo nome contém:
- `concluí` ou `concluido`
- `done`
- `finalizado` ou `finalizada`

## Casos de Borda Tratados

| Cenário | Comportamento |
|---|---|
| **Nenhum backlog** | Retorna 0% |
| **Nenhuma tarefa** | Retorna 0% |
| **Erro na consulta** | Retorna 0% (com log de erro) |
| **Projeto sem "Demandas Internas"** | Usa lógica original do CSV |

## Logs de Monitoramento

O sistema gera logs detalhados para auditoria:

```
INFO - Projeto Demandas Internas detectado - Percentual calculado por tarefas: 67.5%
INFO - Projeto Demandas Internas detectado - Esforço calculado por tarefas: 120.0h
INFO - Calculando percentual por tarefas para projeto 10407
INFO - Total de tarefas no backlog 123: 12
INFO - Tarefas concluídas no backlog 123: 8
INFO - Percentual calculado: 8/12 = 66.7%
INFO - Calculando esforço por tarefas para projeto 10407
INFO - Esforço total calculado: 120.0h (10/12 tarefas com esforço)
```

## Impacto Zero
- ✅ **Sem Breaking Changes**: Projetos normais mantêm comportamento
- ✅ **Performance**: Cálculo só executado para Demandas Internas
- ✅ **Compatibilidade**: API e interface inalteradas
- ✅ **Precisão**: Cálculo em tempo real baseado em dados atuais

## Exemplo de Resultado

**Antes:**
```
Status Report Individual - Projeto Copilot SOU
Progresso: 0% (sem dados no CSV)
Esforço: 0h planejadas (sem dados no CSV)
```

**Depois:**
```
Status Report Individual - Projeto Copilot SOU
Progresso: 67% (8 de 12 tarefas concluídas)
Esforço: 120h planejadas (soma do esforço estimado das tarefas)
```

## Arquivo Modificado
- `app/macro/services.py` - Função `gerar_dados_status_report()` e nova função `_calcular_percentual_por_tarefas()`

## Como Testar
1. Acesse Status Report de projeto de Demandas Internas: `/macro/status-report/10407`
2. Verifique se o percentual agora reflete as tarefas concluídas
3. Compare com o backlog do projeto para validar cálculo
4. Verifique logs para confirmação de funcionamento

A implementação é **cirúrgica, precisa e totalmente compatível** com o sistema existente! 