# MANUAL DE KPIs E MÉTRICAS
## Control360 SOU - Sistema de Gestão e Análise de Projetos

---
**Versão:** 2.0  
**Data:** Janeiro 2024  
**Tipo:** Manual Técnico de KPIs e Métricas  
**Preparado para:** C-Level TI - Ambiente de Testes Produtivos  
---

## INTRODUÇÃO

Este manual apresenta a especificação completa de todos os KPIs (Key Performance Indicators) e métricas utilizados no sistema Control360 SOU. Cada indicador é detalhado com sua fórmula de cálculo, interpretação, casos de uso e troubleshooting.

**Objetivo:** Fornecer compreensão completa dos indicadores para tomada de decisão baseada em dados.

---

## 1. KPIs DO MÓDULO GERENCIAL

### 1.1 PROJETOS ATIVOS

#### Definição
Contagem total de projetos que estão em andamento, ou seja, que ainda não foram finalizados.

#### Fórmula de Cálculo
```sql
COUNT(projetos) WHERE Status IN ('Novo', 'Aguardando', 'Em Atendimento', 'Bloqueado')
```

#### Lógica de Negócio
- **Incluídos:** Projetos com status que indicam trabalho em andamento
- **Excluídos:** Projetos finalizados ('Fechado', 'Encerrado', 'Resolvido', 'Cancelado')
- **Tratamento de Nulos:** Status nulos são considerados como 'Novo'

#### Interpretação dos Resultados
| Valor | Interpretação | Ação Recomendada |
|-------|---------------|-------------------|
| 0-30 | Baixa carga de trabalho | Buscar novos projetos ou redistribuir recursos |
| 31-80 | Carga normal | Monitorar distribuição por squads |
| 81-120 | Carga alta | Avaliar capacidade e priorização |
| >120 | Sobrecarga crítica | Ações imediatas de balanceamento |

#### Casos de Uso
1. **Planejamento de Capacidade:** Avaliar se há recursos suficientes
2. **Distribuição de Trabalho:** Verificar balanceamento entre squads
3. **Tomada de Decisão:** Priorizar novos projetos ou pausar existentes

#### Troubleshooting
- **KPI zerado:** Verificar se dados estão sendo carregados corretamente
- **Valor muito alto:** Validar se status estão sendo atualizados (projetos concluídos marcados como tal)
- **Flutuação anormal:** Verificar mudanças em massa de status

---

### 1.2 EM ATENDIMENTO

#### Definição
Projetos que estão sendo ativamente trabalhados no momento.

#### Fórmula de Cálculo
```sql
COUNT(projetos) WHERE Status = 'Em Atendimento'
```

#### Lógica de Negócio
- **Filtro Específico:** Apenas status 'Em Atendimento'
- **Diferença do "Projetos Ativos":** Subconjunto mais específico
- **Indicador de Produtividade:** Mostra projetos em execução ativa

#### Interpretação dos Resultados
| Percentual vs Ativos | Interpretação | Ação |
|---------------------|---------------|------|
| 60-80% | Excelente produtividade | Manter ritmo atual |
| 40-59% | Produtividade boa | Investigar projetos aguardando/bloqueados |
| 20-39% | Produtividade baixa | Ações para desbloqueio |
| <20% | Produtividade crítica | Intervenção imediata |

#### Casos de Uso
1. **Monitoramento de Produtividade:** Quantos projetos estão sendo executados
2. **Identificação de Gargalos:** Se muito baixo, há impedimentos
3. **Gestão de Fluxo:** Balancear entrada e saída de projetos

---

### 1.3 BURN RATE

#### Definição
Taxa de consumo de horas, indicando a relação entre horas trabalhadas e horas estimadas.

#### Fórmula de Cálculo
```sql
Burn Rate = (Σ HorasTrabalhadas / Σ Horas) × 100

Onde:
- HorasTrabalhadas: Tempo efetivamente investido nos projetos
- Horas: Esforço estimado original
- Resultado: Percentual de consumo
```

#### Lógica de Negócio
- **Tratamento de Divisão por Zero:** Se Horas = 0, considera 100%
- **Agregação:** Soma todas as horas de todos os projetos ativos
- **Atualização:** Recalculado a cada carregamento de dados

#### Interpretação dos Resultados
| Faixa | Interpretação | Significado | Ação |
|-------|---------------|-------------|------|
| 0-70% | Sub-utilização | Projetos subestimados ou baixa produtividade | Revisar estimativas |
| 71-100% | Utilização ideal | Estimativas precisas | Manter controle |
| 101-120% | Sobre-esforço controlado | Pequenos desvios aceitáveis | Monitorar |
| >120% | Sobre-esforço crítico | Projetos mal estimados | Ação corretiva |

#### Casos de Uso
1. **Controle de Estimativas:** Verificar precisão do planejamento
2. **Gestão de Recursos:** Identificar sub ou sobre-utilização
3. **Melhoria de Processos:** Ajustar metodologia de estimativas

#### Troubleshooting
- **Burn Rate > 200%:** Verificar se horas trabalhadas estão sendo lançadas corretamente
- **Burn Rate 0%:** Confirmar se dados de tempo trabalhado estão sendo importados
- **Flutuação extrema:** Validar integridade dos dados de horas

---

### 1.4 PROJETOS CRÍTICOS

#### Definição
Projetos que apresentam um ou mais indicadores de risco que requerem atenção imediata.

#### Fórmula de Cálculo
```sql
COUNT(projetos) WHERE (
    Status = 'Bloqueado' 
    OR HorasRestantes < 0 
    OR (VencimentoEm < DataAtual AND Status NOT IN ('Fechado', 'Encerrado', 'Resolvido'))
)
```

#### Critérios de Criticidade
1. **Bloqueado:** Status = 'Bloqueado'
2. **Horas Negativas:** HorasRestantes < 0 (sobre-esforço)
3. **Atrasado:** Vencimento passou e projeto não foi concluído

#### Lógica de Negócio
- **Critério "OU":** Basta atender UM critério para ser crítico
- **Exclusão de Concluídos:** Projetos finalizados não são considerados atrasados
- **Cálculo de Horas Restantes:** Horas - HorasTrabalhadas

#### Interpretação dos Resultados
| Percentual vs Total | Status | Ação Requerida |
|--------------------|--------|-----------------|
| 0-5% | Excelente | Manutenção preventiva |
| 6-15% | Bom | Monitoramento ativo |
| 16-25% | Atenção | Plano de ação |
| >25% | Crítico | Intervenção imediata |

#### Detalhamento por Tipo
- **Bloqueados:** Requerem desbloqueio de dependências
- **Horas Negativas:** Necessitam re-estimativa ou aprovação de budget adicional
- **Atrasados:** Precisam de repriorização ou renegociação de prazo

#### Casos de Uso
1. **Gestão de Riscos:** Identificação proativa de problemas
2. **Priorização:** Focar esforços em projetos problemáticos
3. **Comunicação:** Alertar stakeholders sobre projetos em risco

---

### 1.5 PARA FATURAR

#### Definição
Projetos elegíveis para faturamento com base no tipo de contrato e percentual de conclusão.

#### Fórmula de Cálculo
```sql
COUNT(projetos) WHERE (
    (Faturamento = 'TERMINO' AND Conclusao >= 100%) 
    OR (Faturamento = 'PLUS' AND Conclusao > 0)
    OR (Faturamento = 'INICIO' AND DataInicio >= (DataAtual - 30 dias))
    OR Status IN ('Fechado', 'Encerrado', 'Resolvido')
)
```

#### Critérios por Tipo de Faturamento
| Tipo | Critério | Descrição |
|------|----------|-----------|
| TERMINO | Conclusao >= 100% | Faturar apenas quando 100% concluído |
| PLUS | Qualquer conclusão > 0% | Faturamento antecipado permitido |
| INICIO | Primeiros 30 dias | Faturar no início do projeto |
| PRIME | Baseado em milestones | Faturamento por entregas específicas |
| FEOP | Já faturado | Faturado em outro projeto (excluído) |
| ENGAJAMENTO | Por tempo | Baseado em tempo decorrido |

#### Interpretação dos Resultados
- **Valor Alto:** Boa geração de receita potencial
- **Valor Baixo:** Poucos projetos prontos para faturamento
- **Tendência Crescente:** Pipeline de faturamento saudável
- **Tendência Decrescente:** Necessita acelerar conclusões

#### Casos de Uso
1. **Planejamento Financeiro:** Projeção de receitas
2. **Gestão de Fluxo de Caixa:** Priorizar projetos faturáveis
3. **Performance Comercial:** Avaliar efetividade das entregas

---

## 2. KPIs DO MÓDULO MACRO

### 2.1 PROJETOS ATIVOS (MACRO)

#### Definição
Contagem de projetos em andamento com análise mais granular por especialista e squad.

#### Fórmula de Cálculo
```sql
COUNT(projetos) WHERE Status NOT IN ('Fechado', 'Encerrado', 'Resolvido', 'Cancelado')
```

#### Diferença do Módulo Gerencial
- **Granularidade:** Detalhamento por especialista e squad
- **Análise:** Foco em distribuição de carga
- **Drill-down:** Capacidade de navegar para detalhes específicos

#### Métricas Relacionadas
- **Por Especialista:** Distribuição de projetos por pessoa
- **Por Squad:** Balanceamento entre equipes
- **Por Status:** Distribuição detalhada dos status

---

### 2.2 EFICIÊNCIA DE ENTREGA

#### Definição
Relação entre horas planejadas e horas efetivamente utilizadas, com foco em performance operacional.

#### Fórmula de Cálculo
```sql
Eficiência = (Σ HorasTrabalhadas / Σ Horas) × 100
```

#### Categorização de Performance
| Faixa | Classificação | Cor | Interpretação |
|-------|---------------|-----|---------------|
| > 100% | Sobre-esforço | Vermelho | Projetos subestimados |
| 90-100% | Eficiente | Verde | Performance ideal |
| 70-89% | Aceitável | Amarelo | Margem de melhoria |
| < 70% | Sub-utilizado | Azul | Recursos ociosos |

#### Análise Avançada
- **Tendência Temporal:** Acompanhar evolução ao longo do tempo
- **Comparação por Squad:** Identificar equipes mais eficientes
- **Correlação com Qualidade:** Eficiência vs. retrabalho

---

### 2.3 TEMPO MÉDIO DE VIDA

#### Definição
Média de dias entre a abertura e conclusão de projetos, indicando velocidade de entrega.

#### Fórmula de Cálculo
```sql
TMV = AVG(DataTermino - DataInicio) 
WHERE Status IN ('Fechado', 'Encerrado', 'Resolvido')
AND DataTermino >= (DataAtual - 90 dias)
```

#### Lógica de Negócio
- **Filtro Temporal:** Últimos 3 meses para relevância
- **Apenas Concluídos:** Projetos com DataTermino preenchida
- **Resultado em Dias:** Número inteiro de dias

#### Categorização por Tempo
| Faixa | Categoria | Interpretação |
|-------|-----------|---------------|
| < 30 dias | Rápido | Projetos de baixa complexidade |
| 30-60 dias | Normal | Projetos de complexidade média |
| 61-90 dias | Demorado | Projetos complexos |
| > 90 dias | Muito Demorado | Projetos críticos ou mal gerenciados |

#### Fatores de Influência
- **Complexidade do Projeto:** Projetos maiores tendem a demorar mais
- **Disponibilidade de Recursos:** Especialistas sobrecarregados aumentam o tempo
- **Dependências Externas:** Aguardo de aprovações ou recursos externos
- **Qualidade dos Requisitos:** Requisitos mal definidos geram retrabalho

---

### 2.4 PROJETOS EM RISCO

#### Definição
Projetos com indicadores que sugerem potencial problema futuro, antes que se tornem críticos.

#### Fórmula de Cálculo
```sql
COUNT(projetos) WHERE (
    (Conclusao < 50 AND HorasRestantes < (Horas * 0.2))
    OR UltimaInteracao < (DataAtual - 15 dias)
    OR (HorasTrabalhadas / Horas) > 1.5
)
```

#### Critérios de Risco
1. **Baixa Conclusão com Poucas Horas:** < 50% conclusão e < 20% horas restantes
2. **Sem Atualização:** Mais de 15 dias sem movimentação
3. **Burn Rate Alto:** Mais de 150% de consumo de horas

#### Interpretação e Ações
| Critério | Risco | Ação Preventiva |
|----------|-------|-----------------|
| Horas vs Conclusão | Estouro de budget | Revisar escopo ou aprovar horas adicionais |
| Sem atualização | Abandono/bloqueio | Contatar responsável e verificar status |
| Burn rate alto | Má estimativa | Reavaliar complexidade e recursos |

---

## 3. MÉTRICAS DO STATUS REPORT DIRETORIA

### 3.1 VARIAÇÃO MENSAL DE PROJETOS ATIVOS

#### Definição
Comparação do número de projetos ativos entre o mês atual e o mês anterior.

#### Fórmula de Cálculo
```sql
Variação Absoluta = ProjetosAtivos_MesAtual - ProjetosAtivos_MesAnterior
Variação Percentual = (Variação_Absoluta / ProjetosAtivos_MesAnterior) × 100
```

#### Interpretação dos Indicadores
- **Seta Verde (↑):** Aumento no número de projetos
- **Seta Vermelha (↓):** Diminuição no número de projetos
- **Percentual:** Magnitude da variação

#### Análise Estratégica
| Cenário | Interpretação | Implicação |
|---------|---------------|------------|
| Aumento > 20% | Crescimento acelerado | Avaliar capacidade |
| Aumento 5-20% | Crescimento controlado | Cenário ideal |
| Estável (-5% a +5%) | Maturidade operacional | Manter monitoramento |
| Redução 5-20% | Possível finalização de projetos | Verificar pipeline |
| Redução > 20% | Possível problema | Investigar causas |

---

### 3.2 PROJETOS ENTREGUES

#### Definição
Número de projetos concluídos no mês de referência com comparativo temporal.

#### Fórmula de Cálculo
```sql
COUNT(projetos) WHERE DataTermino >= InicioMes AND DataTermino <= FimMes
AND Status IN ('Fechado', 'Encerrado', 'Resolvido')
```

#### Métricas Derivadas
- **Histórico 6 Meses:** Gráfico de linha mostrando tendência
- **Comparativo Mensal:** vs. mês anterior
- **Meta de Entregas:** Comparação com target estabelecido

#### Indicadores de Performance
| Métrica | Interpretação |
|---------|---------------|
| Tendência Crescente | Melhoria na capacidade de entrega |
| Tendência Estável | Capacidade madura e previsível |
| Tendência Decrescente | Possível gargalo ou redução de demanda |
| Picos Isolados | Entregas concentradas (possível atraso acumulado) |

---

### 3.3 DISTRIBUIÇÃO POR STATUS E SQUAD

#### Definição
Matriz de distribuição cruzada mostrando quantidade de projetos por status e por squad.

#### Estrutura da Matriz
```
           AZURE  M365  DATA&POWER  CDB  TOTAL
Novo         X     Y       Z       W     Σ
Em Atend.    A     B       C       D     Σ
Aguardando   E     F       G       H     Σ
Bloqueado    I     J       K       L     Σ
Fechado      M     N       O       P     Σ
TOTAL        Σ     Σ       Σ       Σ     ΣΣ
```

#### Análises Possíveis
1. **Por Squad:** Identificar equipes sobrecarregadas
2. **Por Status:** Detectar gargalos no fluxo
3. **Distribuição:** Verificar balanceamento de trabalho
4. **Padrões:** Identificar comportamentos recorrentes

---

## 4. FÓRMULAS CONSOLIDADAS

### 4.1 Capacidade e Ocupação

#### Capacidade por Squad
```sql
CapacidadeSquad = NumeroPessoas × HorasPorPessoa × DiasUteis
Padrão = 3 pessoas × 180 horas/mês = 540 horas/squad
```

#### Taxa de Ocupação
```sql
Ocupacao = (Σ HorasRestantes / CapacidadeSquad) × 100
```

### 4.2 Performance Temporal

#### Taxa de Sucesso
```sql
TaxaSucesso = (ProjetosConcluidos_NoPrazo / TotalProjetosConcluidos) × 100
Onde: NoPrazo = DataTermino <= VencimentoEm
```

#### Tempo Médio Geral
```sql
TempoMedio = AVG(DataTermino - DataInicio)
Para projetos concluídos no período
```

---

## 5. TROUBLESHOOTING E VALIDAÇÃO

### 5.1 Problemas Comuns

#### KPIs Zerados
- **Causa:** Dados não carregados ou arquivo CSV vazio
- **Solução:** Verificar existência e integridade do dadosr.csv
- **Prevenção:** Implementar alertas de carregamento

#### Valores Inconsistentes
- **Causa:** Dados corrompidos ou formato incorreto
- **Solução:** Validar encoding (latin1) e separador (;)
- **Prevenção:** Validação automática na importação

#### Performance Lenta
- **Causa:** Cache expirado ou dados muito grandes
- **Solução:** Verificar TTL do cache (30 segundos)
- **Prevenção:** Otimizar consultas e implementar paginação

### 5.2 Validação de Dados

#### Checklist de Integridade
1. **Datas:** Formato dd/mm/yyyy consistente
2. **Números:** Valores numéricos válidos (não texto)
3. **Status:** Valores dentro do conjunto esperado
4. **Horas:** Valores positivos e realistas
5. **Relacionamentos:** Consistência entre campos relacionados

#### Testes de Sanidade
- **Soma das Partes:** Total = Soma das categorias
- **Percentuais:** Sempre entre 0 e 100%
- **Datas Lógicas:** DataTermino >= DataInicio
- **Horas Lógicas:** HorasTrabalhadas <= Horas (exceto casos de sobre-esforço)

---

## 6. GLOSSÁRIO DE TERMOS

| Termo | Definição |
|-------|-----------|
| **Burn Rate** | Taxa de consumo de horas trabalhadas vs. estimadas |
| **TTL** | Time To Live - tempo de vida do cache |
| **Drill-down** | Capacidade de navegar para níveis de detalhe |
| **Pipeline** | Fluxo de projetos em diferentes estágios |
| **Baseline** | Valor de referência para comparações |
| **Milestone** | Marco ou entrega importante do projeto |
| **Throughput** | Quantidade de projetos processados por período |
| **Lead Time** | Tempo total do início ao fim do projeto |
| **Bottleneck** | Gargalo que limita a capacidade de entrega |

---

**Manual preparado para apresentação ao C-Level da TI**  
**Control360 SOU - Sistema de Gestão e Análise de Projetos**  
**Janeiro 2024** 