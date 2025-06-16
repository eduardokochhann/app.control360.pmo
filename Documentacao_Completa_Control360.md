# DOCUMENTAÇÃO COMPLETA DOS MÓDULOS  
## Control360 SOU - Sistema de Gestão e Análise de Projetos

---
**Versão:** 2.0  
**Data:** Janeiro 2024  
**Preparado para:** C-Level TI - Ambiente de Testes Produtivos  
---

## SUMÁRIO EXECUTIVO

O Control360 SOU é uma plataforma integrada de análise e gestão de projetos estruturada em três módulos principais: **Gerencial**, **Macro** e **Status Report Diretoria**. Cada módulo oferece funcionalidades específicas com KPIs calculados em tempo real, dashboards interativos e relatórios executivos.

**Principais Características:**
- Processamento de dados em tempo real com cache otimizado (30 segundos)
- Interface responsiva com Bootstrap 5.3 e visualizações Chart.js
- Arquitetura modular Flask com SQLAlchemy
- Suporte a múltiplas fontes de dados CSV com encoding latin1

---

## 1. MÓDULO GERENCIAL

### 1.1 Visão Geral
O módulo Gerencial oferece uma visão estratégica de alto nível para gestores, focando em KPIs essenciais para tomada de decisão executiva.

**Objetivo:** Fornecer métricas consolidadas de performance e status geral dos projetos para liderança técnica.

### 1.2 Cards de KPIs Principais

#### PROJETOS ATIVOS
- **Definição:** Projetos com status "Novo", "Aguardando", "Em Atendimento" ou "Bloqueado"
- **Cálculo:** COUNT de projetos onde Status IN ('Novo', 'Aguardando', 'Em Atendimento', 'Bloqueado')
- **Cor do Card:** Verde (border-left-success)
- **Ícone:** bi-play-circle-fill
- **Interatividade:** Clicável - abre modal com lista detalhada
- **Função de Cálculo:** `GerencialService.obter_projetos_ativos()`

#### EM ATENDIMENTO
- **Definição:** Projetos especificamente com status "Em Atendimento"
- **Cálculo:** COUNT de projetos onde Status = 'Em Atendimento'
- **Cor do Card:** Amarelo (border-left-warning)
- **Ícone:** bi-clock-fill
- **Interatividade:** Clicável - abre modal com projetos em atendimento
- **Função de Cálculo:** `GerencialService.obter_projetos_em_atendimento()`

#### BURN RATE
- **Definição:** Taxa de consumo de horas trabalhadas vs. horas planejadas
- **Cálculo:** (Σ HorasTrabalhadas / Σ Horas) × 100
- **Unidade:** Percentual (%)
- **Cor do Card:** Azul (border-left-info)
- **Ícone:** bi-speedometer2
- **Lógica Especial:** Se Horas = 0, considera 100% de burn rate
- **Função de Cálculo:** Calculado em `processar_gerencial()`

#### PROJETOS CRÍTICOS
- **Definição:** Projetos com problemas identificados
- **Critérios Críticos:**
  - Status = "Bloqueado"
  - HorasRestantes < 0 (horas negativas)
  - VencimentoEm < Data Atual (atrasado)
- **Cor do Card:** Vermelho (border-left-danger)
- **Ícone:** bi-exclamation-triangle
- **Interatividade:** Clicável - abre modal com detalhes dos problemas
- **Função de Cálculo:** `GerencialService.obter_projetos_criticos()`

#### PARA FATURAR
- **Definição:** Projetos elegíveis para faturamento baseado no tipo e conclusão
- **Critérios de Elegibilidade:**
  - Faturamento = "TERMINO" AND Conclusao >= 100%
  - Faturamento = "PLUS" AND qualquer conclusão
  - Status IN ('Fechado', 'Encerrado', 'Resolvido')
- **Cor do Card:** Roxo (border-left-purple)
- **Ícone:** bi-cash-stack
- **Função de Cálculo:** `GerencialService.obter_projetos_para_faturar()`

---

## 2. MÓDULO MACRO

### 2.1 Visão Geral
O módulo Macro oferece análise operacional detalhada com foco em especialistas, accounts e performance de entrega.

**Objetivo:** Fornecer visibilidade granular sobre alocação de recursos, performance individual e indicadores operacionais.

### 2.2 Grid Principal de KPIs

#### PROJETOS ATIVOS
- **Definição:** Projetos em andamento (não concluídos)
- **Cálculo:** COUNT onde Status NOT IN ('Fechado', 'Encerrado', 'Resolvido', 'Cancelado')
- **Cor:** Verde (border-left-success)
- **Ícone:** bi-calendar
- **Modal:** Lista completa com busca e ordenação
- **Função:** `MacroService.calcular_projetos_ativos()`

#### PROJETOS CRÍTICOS
- **Definição:** Projetos com indicadores de risco
- **Critérios Críticos:**
  - HorasRestantes < 0 (horas negativas)
  - Status = "Bloqueado"
  - VencimentoEm < Data Atual (atrasado)
  - Conclusao < 25% após 30 dias de abertura
- **Cor:** Vermelho (border-left-danger)
- **Ícone:** bi-exclamation-triangle
- **Função:** `MacroService.calcular_projetos_criticos()`

#### EFICIÊNCIA DE ENTREGA
- **Definição:** Relação entre horas planejadas e horas trabalhadas
- **Cálculo:** (Σ HorasTrabalhadas / Σ Horas) × 100
- **Interpretação:**
  - > 100%: Sobre-esforço (vermelho)
  - 90-100%: Eficiente (verde)
  - 70-89%: Aceitável (amarelo)
  - < 70%: Sub-utilizado (azul)
- **Cor:** Amarelo (border-left-warning)
- **Ícone:** bi-speedometer2

---

## 3. STATUS REPORT DIRETORIA

### 3.1 Visão Geral (/macro/apresentacao)
Apresentação executiva formatada para diretoria com comparativos mensais e tendências.

**Objetivo:** Fornecer visão estratégica condensada para tomada de decisão executiva.

### 3.2 KPIs Comparativos

#### PROJETOS ATIVOS vs. MÊS ANTERIOR
- **Métrica Principal:** Número absoluto de projetos ativos
- **Comparativo:** Diferença absoluta e percentual vs. mês anterior
- **Indicadores Visuais:**
  - Seta verde (↑): Aumento
  - Seta vermelha (↓): Diminuição
  - Percentual de variação

#### PROJETOS ENTREGUES
- **Definição:** Projetos concluídos no mês de referência
- **Comparação:** vs. mesmo período do mês anterior
- **Histórico:** Gráfico de linha dos últimos 6 meses
- **Cálculo:** COUNT de projetos com DataTermino no período

---

**Documento preparado para apresentação ao C-Level da TI**  
**Control360 SOU - Sistema de Gestão e Análise de Projetos**  
**Janeiro 2024** 