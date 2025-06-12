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

---

### 1.2 BURN RATE

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

#### Interpretação dos Resultados
| Faixa | Interpretação | Significado | Ação |
|-------|---------------|-------------|------|
| 0-70% | Sub-utilização | Projetos subestimados ou baixa produtividade | Revisar estimativas |
| 71-100% | Utilização ideal | Estimativas precisas | Manter controle |
| 101-120% | Sobre-esforço controlado | Pequenos desvios aceitáveis | Monitorar |
| >120% | Sobre-esforço crítico | Projetos mal estimados | Ação corretiva |

---

### 1.3 PROJETOS CRÍTICOS

#### Definição
Projetos que apresentam um ou mais indicadores de risco que requerem atenção imediata.

#### Critérios de Criticidade
1. **Bloqueado:** Status = 'Bloqueado'
2. **Horas Negativas:** HorasRestantes < 0 (sobre-esforço)
3. **Atrasado:** Vencimento passou e projeto não foi concluído

#### Interpretação dos Resultados
| Percentual vs Total | Status | Ação Requerida |
|--------------------|--------|-----------------|
| 0-5% | Excelente | Manutenção preventiva |
| 6-15% | Bom | Monitoramento ativo |
| 16-25% | Atenção | Plano de ação |
| >25% | Crítico | Intervenção imediata |

---

## 2. KPIs DO MÓDULO MACRO

### 2.1 EFICIÊNCIA DE ENTREGA

#### Definição
Relação entre horas planejadas e horas efetivamente utilizadas, com foco em performance operacional.

#### Categorização de Performance
| Faixa | Classificação | Cor | Interpretação |
|-------|---------------|-----|---------------|
| > 100% | Sobre-esforço | Vermelho | Projetos subestimados |
| 90-100% | Eficiente | Verde | Performance ideal |
| 70-89% | Aceitável | Amarelo | Margem de melhoria |
| < 70% | Sub-utilizado | Azul | Recursos ociosos |

### 2.2 TEMPO MÉDIO DE VIDA

#### Definição
Média de dias entre a abertura e conclusão de projetos, indicando velocidade de entrega.

#### Categorização por Tempo
| Faixa | Categoria | Interpretação |
|-------|-----------|---------------|
| < 30 dias | Rápido | Projetos de baixa complexidade |
| 30-60 dias | Normal | Projetos de complexidade média |
| 61-90 dias | Demorado | Projetos complexos |
| > 90 dias | Muito Demorado | Projetos críticos ou mal gerenciados |

---

## 3. FÓRMULAS CONSOLIDADAS

### 3.1 Capacidade e Ocupação

#### Capacidade por Squad
```sql
CapacidadeSquad = 3 pessoas × 180 horas/mês = 540 horas/squad
```

#### Taxa de Ocupação
```sql
Ocupacao = (Σ HorasRestantes / CapacidadeSquad) × 100
```

---

## 4. TROUBLESHOOTING

### 4.1 Problemas Comuns

#### KPIs Zerados
- **Causa:** Dados não carregados ou arquivo CSV vazio
- **Solução:** Verificar existência e integridade do dadosr.csv

#### Valores Inconsistentes
- **Causa:** Dados corrompidos ou formato incorreto
- **Solução:** Validar encoding (latin1) e separador (;)

---

**Manual preparado para apresentação ao C-Level da TI**  
**Control360 SOU - Sistema de Gestão e Análise de Projetos**  
**Janeiro 2024** 