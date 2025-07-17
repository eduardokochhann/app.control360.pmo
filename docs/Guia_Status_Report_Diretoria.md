# GUIA DO STATUS REPORT DIRETORIA
## Control360 SOU - Sistema de Gestão e Análise de Projetos

---
**Versão:** 2.0  
**Data:** Janeiro 2024  
**Tipo:** Guia de Usuário - Status Report Diretoria  
**Preparado para:** C-Level TI - Ambiente de Testes Produtivos  
---

## INTRODUÇÃO

O Status Report Diretoria é uma apresentação executiva especializada do Control360 SOU, desenhada para fornecer uma visão estratégica consolidada para a alta liderança. Este guia detalha todas as funcionalidades, interpretações e melhores práticas de uso.

**Objetivo:** Capacitar a liderança executiva a interpretar e utilizar o Status Report para tomada de decisões estratégicas.

**URL de Acesso:** `/macro/apresentacao`

---

## 1. VISÃO GERAL DA APRESENTAÇÃO

### 1.1 Propósito Executivo

O Status Report foi desenvolvido especificamente para atender às necessidades de **C-Level** e **Diretoria de TI**, fornecendo:

- **Visão Consolidada:** KPIs estratégicos em uma única tela
- **Comparativos Temporais:** Tendências mensais e trimestrais
- **Indicadores Visuais:** Setas e cores para rápida interpretação
- **Drill-down Controlado:** Detalhes essenciais sem complexidade operacional

### 1.2 Arquitetura da Apresentação

```
CABEÇALHO
├── Título: Status Report
├── Fonte de Dados: dadosr.csv ou arquivo histórico
└── Data de Referência: Mês/Ano selecionado

SEÇÃO PRINCIPAL
├── KPIs Comparativos (4 cards principais)
├── Gráficos de Tendência (2 gráficos)
├── Distribuição por Squad e Status
└── Indicadores de Novos Projetos

NAVEGAÇÃO
├── Seletor de Mês/Ano
├── Botões de Atualização
└── Links para outros módulos
```

---

## 2. FUNCIONALIDADES PRINCIPAIS

### 2.1 Seletor de Período

#### Como Usar
1. **Localização:** Dropdown no canto superior direito
2. **Opções Disponíveis:** Detecção automática de arquivos históricos
3. **Formato:** Mês/Ano (ex: Janeiro/2024)
4. **Ação:** Clique no período desejado para carregar dados

#### Tipos de Visualização

**VISÃO ATUAL**
- **Fonte:** dadosr.csv (dados do mês corrente)
- **Indicador:** Banner azul "Dados Atuais"
- **Atualização:** Dados em tempo real
- **Uso:** Monitoramento contínuo

**VISÃO HISTÓRICA**
- **Fonte:** dadosr_MMM_YYYY.csv (ex: dadosr_jan_2024.csv)
- **Indicador:** Banner amarelo "Dados Históricos - Jan/2024"
- **Atualização:** Dados fixos do período
- **Uso:** Análise temporal e comparações

#### Detecção Automática de Fontes
O sistema detecta automaticamente arquivos no formato:
- `dadosr_jan_2024.csv`
- `dadosr_fev_2024.csv`
- `dadosr_mar_2024.csv`

**Requisitos dos Arquivos:**
- Localização: pasta `data/`
- Encoding: latin1
- Separador: ponto e vírgula (;)
- Estrutura: Idêntica ao dadosr.csv

---

### 2.2 KPIs Comparativos

#### 2.2.1 PROJETOS ATIVOS vs. MÊS ANTERIOR

**Localização:** Card superior esquerdo

**Elementos Visuais:**
- **Número Principal:** Quantidade absoluta de projetos ativos
- **Seta de Tendência:** 
  - Verde (↑): Aumento em relação ao mês anterior
  - Vermelha (↓): Diminuição em relação ao mês anterior
- **Percentual de Variação:** Magnitude da mudança

**Interpretação Executiva:**
```
Exemplo de Leitura:
"65 projetos ativos (↑ +8, +14%)"
= 65 projetos ativos no mês atual
= 8 projetos a mais que o mês anterior  
= Aumento de 14% na carga de trabalho
```

**Cenários de Interpretação:**
| Cenário | Sinal | Implicação Estratégica |
|---------|-------|------------------------|
| ↑ >20% | Atenção | Crescimento acelerado - verificar capacidade |
| ↑ 5-20% | Positivo | Crescimento saudável |
| ↑ 0-5% | Estável | Maturidade operacional |
| ↓ 0-10% | Normal | Possível conclusão de projetos |
| ↓ >10% | Investigar | Possível redução de demanda ou problemas |

#### 2.2.2 PROJETOS ENTREGUES

**Localização:** Card superior direito

**Elementos Visuais:**
- **Número Principal:** Projetos concluídos no mês
- **Comparativo:** Diferença vs. mês anterior
- **Histórico:** Gráfico de linha dos últimos 6 meses

**Cálculo Base:**
```sql
COUNT(projetos) WHERE 
DataTermino >= InicioMês AND DataTermino <= FimMês
AND Status IN ('Fechado', 'Encerrado', 'Resolvido')
```

**Interpretação:**
- **Tendência Crescente:** Melhoria na capacidade de entrega
- **Tendência Estável:** Processo maduro e previsível
- **Picos Isolados:** Possível concentração de entregas (investigar causas)
- **Quedas Bruscas:** Possível gargalo ou redução de recursos

#### 2.2.3 TEMPO MÉDIO DE VIDA

**Localização:** Card inferior esquerdo

**Definição:** Média de dias entre abertura e conclusão dos projetos concluídos nos últimos 3 meses.

**Elementos Visuais:**
- **Número Principal:** Dias (ex: 42 dias)
- **Variação:** Percentual vs. período anterior
- **Indicador de Tendência:** Seta verde (melhoria) ou vermelha (piora)

**Benchmarks de Referência:**
| Faixa | Classificação | Ação Executiva |
|-------|---------------|----------------|
| < 30 dias | Excelente | Manter padrão |
| 30-45 dias | Bom | Monitorar |
| 46-60 dias | Aceitável | Avaliar processos |
| > 60 dias | Necessita Ação | Revisar metodologia |

#### 2.2.4 FATURAMENTO COMPARATIVO

**Localização:** Card inferior direito

**Elementos Incluídos:**
- **Projetos Para Faturar:** Elegíveis para cobrança
- **Valor Estimado:** Baseado em horas × taxa
- **Comparativo:** vs. período anterior

---

### 2.3 Gráficos de Análise

#### 2.3.1 Gráfico de Pizza - Distribuição por Squad

**Localização:** Seção central esquerda

**Dados Apresentados:**
- **AZURE:** Projetos da squad Azure
- **M365:** Projetos da squad Microsoft 365
- **DATA E POWER:** Projetos da squad Data & Power BI
- **CDB:** Projetos da squad CDB (Cosmos DB)

**Cores Padronizadas:**
```css
AZURE: #0078d4 (Azul Microsoft)
M365: #185abd (Azul escuro)
DATA E POWER: #ca5010 (Laranja)
CDB: #8764b8 (Roxo)
```

**Interpretação:**
- **Distribuição Equilibrada:** ~25% cada squad (ideal)
- **Concentração:** Uma squad com >40% (investigar causas)
- **Squad Ociosa:** <10% dos projetos (realocação de recursos)

#### 2.3.2 Gráfico de Linha - Tendência de Projetos Ativos

**Localização:** Seção central direita

**Período:** Últimos 6 meses
**Eixo X:** Meses
**Eixo Y:** Número de projetos ativos

**Padrões de Interpretação:**
- **Linha Ascendente:** Crescimento sustentado
- **Linha Descendente:** Possível redução de demanda
- **Picos e Vales:** Sazonalidade ou irregularidades
- **Platô:** Maturidade operacional

---

### 2.4 Tabela de Agregação por Status

#### Estrutura da Matriz

```
DISTRIBUIÇÃO POR STATUS E SQUAD

STATUS         | AZURE | M365 | DATA&POWER | CDB | TOTAL
---------------|-------|------|------------|-----|------
Novo           |   X   |  Y   |     Z      |  W  |   Σ
Em Atendimento |   A   |  B   |     C      |  D  |   Σ
Aguardando     |   E   |  F   |     G      |  H  |   Σ
Bloqueado      |   I   |  J   |     K      |  L  |   Σ
Fechado        |   M   |  N   |     O      |  P  |   Σ
TOTAL          |   Σ   |  Σ   |     Σ      |  Σ  |  ΣΣ
```

#### Códigos de Cores por Status
- **Novo:** Azul claro (#e3f2fd)
- **Em Atendimento:** Verde claro (#e8f5e8)
- **Aguardando:** Amarelo claro (#fff8e1)
- **Bloqueado:** Vermelho claro (#ffebee)
- **Fechado:** Verde escuro (#c8e6c9)

#### Análises Executivas Possíveis

**Por Linha (Status):**
- Identificar gargalos no fluxo de trabalho
- Detectar acúmulo em status específicos
- Monitorar efetividade das entregas

**Por Coluna (Squad):**
- Avaliar balanceamento de carga
- Identificar squads sobrecarregadas
- Planejar redistribuição de recursos

**Por Célula Específica:**
- Drill-down em problemas pontuais
- Análise de padrões específicos
- Ações direcionadas por squad/status

---

### 2.5 Seção de Novos Projetos

#### Métricas Apresentadas

**NOVOS PROJETOS NO MÊS**
- **Definição:** Projetos com DataInicio no período de referência
- **Comparativo:** vs. mês anterior
- **Tendência:** Gráfico de linha dos últimos 3 meses

**Interpretação Estratégica:**
- **Crescimento Sustentado:** Pipeline saudável
- **Picos Isolados:** Possível demanda sazonal
- **Queda Abrupta:** Investigar redução de demanda
- **Correlação com Entregas:** Balancear entrada vs. saída

---

## 3. NAVEGAÇÃO E USABILIDADE

### 3.1 Elementos de Interface

#### Cabeçalho da Apresentação
```html
Status Report
Fonte de dados: dadosr.csv
Mês de referência: Janeiro/2024
[Atualizar] [Gerencial] [Macro]
```

#### Menu de Navegação Superior
- **Gerencial:** Link direto para dashboard gerencial
- **Macro:** Link para análise macro detalhada
- **Status Report:** Página atual (destacada)

#### Botões de Ação
- **Atualizar:** Recarrega dados da fonte atual
- **Exportar:** (Futuro) Gerar PDF da apresentação
- **Imprimir:** Versão otimizada para impressão

### 3.2 Responsividade

#### Desktop (>1200px)
- Layout em grid 2x2 para KPIs principais
- Gráficos lado a lado
- Tabela completa visível

#### Tablet (768px - 1199px)
- KPIs em grid 2x2 compacto
- Gráficos empilhados verticalmente
- Tabela com scroll horizontal

#### Mobile (<768px)
- KPIs empilhados verticalmente
- Gráficos em tela cheia
- Tabela com zoom interativo

---

## 4. INTERPRETAÇÃO AVANÇADA

### 4.1 Análise de Tendências

#### Tendências Positivas
- **Projetos Ativos Crescendo:** Pipeline saudável
- **Entregas Aumentando:** Melhoria na capacidade
- **TMV Diminuindo:** Eficiência crescente
- **Distribuição Equilibrada:** Boa gestão de recursos

#### Sinais de Alerta
- **Projetos Ativos Crescendo Muito Rápido:** Risco de sobrecarga
- **Entregas Diminuindo:** Possível gargalo
- **TMV Aumentando:** Perda de eficiência
- **Concentração em Uma Squad:** Desbalanceamento

#### Correlações Importantes
- **Alta Entrada + Baixa Saída:** Acúmulo futuro
- **TMV Alto + Muitos Bloqueados:** Problemas de processo
- **Distribuição Desigual + Entregas Baixas:** Ineficiência

### 4.2 Cenários de Tomada de Decisão

#### Cenário 1: Crescimento Acelerado
**Indicadores:** ↑ Projetos Ativos >20%, ↑ Novos Projetos
**Ações:**
1. Avaliar capacidade atual vs. demanda
2. Considerar contratação ou redistribuição
3. Implementar priorização rigorosa
4. Monitorar qualidade das entregas

#### Cenário 2: Estagnação
**Indicadores:** Projetos estáveis, ↓ Novos Projetos, TMV alto
**Ações:**
1. Investigar redução de demanda
2. Revisar processos internos
3. Buscar otimizações de eficiência
4. Considerar realocação de recursos

#### Cenário 3: Gargalo Operacional
**Indicadores:** ↑ Projetos Ativos, ↓ Entregas, ↑ TMV
**Ações:**
1. Identificar pontos de bloqueio
2. Implementar ações de desbloqueio
3. Revisar alocação de especialistas
4. Considerar processo de escalação

---

## 5. MELHORES PRÁTICAS DE USO

### 5.1 Frequência de Análise

#### Análise Diária (C-Level)
- **Foco:** KPIs principais e alertas críticos
- **Tempo:** 2-3 minutos
- **Objetivo:** Monitoramento de saúde geral

#### Análise Semanal (Diretoria)
- **Foco:** Tendências e comparativos
- **Tempo:** 10-15 minutos
- **Objetivo:** Identificação de padrões

#### Análise Mensal (Estratégica)
- **Foco:** Análise completa e planejamento
- **Tempo:** 30-45 minutos
- **Objetivo:** Decisões estratégicas e ajustes

### 5.2 Pontos de Atenção

#### Durante a Apresentação
1. **Começar pelos KPIs:** Visão geral primeiro
2. **Focar nas Tendências:** Setas e variações percentuais
3. **Drill-down Seletivo:** Investigar apenas anomalias
4. **Correlacionar Métricas:** Buscar padrões entre indicadores

#### Na Tomada de Decisão
1. **Contexto Temporal:** Comparar com períodos anteriores
2. **Múltiplos Indicadores:** Não se basear em um único KPI
3. **Validação:** Confirmar dados com equipes operacionais
4. **Ações Mensuráveis:** Definir métricas para acompanhar impacto

---

## 6. INTEGRAÇÃO COM OUTROS MÓDULOS

### 6.1 Fluxo de Análise Recomendado

```
Status Report (Visão Estratégica)
↓
Módulo Macro (Análise Operacional)
↓
Módulo Gerencial (Ações Táticas)
```

#### Quando Usar Cada Módulo

**Status Report:** 
- Reuniões executivas
- Reports para board
- Análise de tendências estratégicas

**Módulo Macro:**
- Análise de especialistas
- Investigação de gargalos
- Planejamento de recursos

**Módulo Gerencial:**
- Gestão operacional diária
- Acompanhamento de projetos críticos
- Controle de faturamento

### 6.2 Escalação de Informações

#### Do Operacional para o Estratégico
1. **Módulo Gerencial** identifica problema
2. **Módulo Macro** analisa impacto e causas
3. **Status Report** mostra tendência e contexto

#### Do Estratégico para o Operacional
1. **Status Report** identifica tendência
2. **Módulo Macro** investiga detalhes
3. **Módulo Gerencial** implementa ações

---

## 7. TROUBLESHOOTING

### 7.1 Problemas Comuns

#### Dados Não Carregando
**Sintomas:** KPIs zerados ou mensagem de erro
**Causas Possíveis:**
- Arquivo dadosr.csv não encontrado
- Formato incorreto do arquivo
- Problemas de encoding

**Soluções:**
1. Verificar existência do arquivo em `data/dadosr.csv`
2. Validar formato CSV com separador `;`
3. Confirmar encoding `latin1`
4. Verificar permissões de leitura

#### Comparativos Incorretos
**Sintomas:** Variações percentuais estranhas
**Causas Possíveis:**
- Dados históricos incompletos
- Mudanças na estrutura dos dados
- Problemas de datas

**Soluções:**
1. Verificar arquivos históricos disponíveis
2. Validar estrutura dos arquivos antigos
3. Conferir formato de datas

#### Performance Lenta
**Sintomas:** Carregamento demorado
**Causas Possíveis:**
- Cache expirado
- Arquivos muito grandes
- Muitos cálculos simultâneos

**Soluções:**
1. Aguardar recarregamento do cache (30s)
2. Otimizar tamanho dos arquivos CSV
3. Acessar fora de horários de pico

### 7.2 Validação de Dados

#### Checklist de Integridade
- [ ] Soma das partes = Total geral
- [ ] Percentuais entre 0% e 100%
- [ ] Datas no formato dd/mm/yyyy
- [ ] Números positivos onde esperado
- [ ] Status dentro dos valores válidos

#### Pontos de Validação Manual
1. **KPIs vs. Realidade:** Comparar com conhecimento operacional
2. **Tendências vs. Contexto:** Validar com eventos conhecidos
3. **Distribuições vs. Organização:** Confirmar estrutura de squads
4. **Comparativos vs. Memória:** Verificar coerência temporal

---

## 8. GLOSSÁRIO EXECUTIVO

| Termo | Definição | Uso no Status Report |
|-------|-----------|---------------------|
| **KPI** | Key Performance Indicator - Indicador chave de performance | Métricas principais dos cards |
| **Drill-down** | Navegação para níveis de detalhe | Clique nos cards para mais informações |
| **Baseline** | Valor de referência para comparações | Mês anterior como referência |
| **Throughput** | Quantidade processada por período | Projetos entregues por mês |
| **Pipeline** | Fluxo de projetos em andamento | Novos projetos + ativos |
| **Burndown** | Taxa de conclusão ao longo do tempo | Tempo médio de vida |
| **Squad** | Equipe especializada | AZURE, M365, DATA&POWER, CDB |
| **Status** | Estado atual do projeto | Novo, Em Atendimento, etc. |

---

## 9. ANEXOS

### 9.1 Códigos de Cores Padronizados

#### Cores por Status
```css
Novo: #e3f2fd (azul claro)
Em Atendimento: #e8f5e8 (verde claro)  
Aguardando: #fff8e1 (amarelo claro)
Bloqueado: #ffebee (vermelho claro)
Fechado: #c8e6c9 (verde escuro)
```

#### Cores por Squad
```css
AZURE: #0078d4 (azul Microsoft)
M365: #185abd (azul escuro)
DATA E POWER: #ca5010 (laranja)
CDB: #8764b8 (roxo)
```

#### Cores de Indicadores
```css
Positivo/Crescimento: #28a745 (verde)
Negativo/Redução: #dc3545 (vermelho)
Neutro/Estável: #6c757d (cinza)
Atenção: #ffc107 (amarelo)
```

### 9.2 Atalhos de Teclado

| Tecla | Ação |
|-------|------|
| F5 | Atualizar dados |
| Ctrl + P | Imprimir |
| Esc | Fechar modais |
| Tab | Navegar entre elementos |

---

**Guia preparado para apresentação ao C-Level da TI**  
**Control360 SOU - Sistema de Gestão e Análise de Projetos**  
**Janeiro 2024** 