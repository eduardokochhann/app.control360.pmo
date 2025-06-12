DOCUMENTAÇÃO COMPLETA DOS MÓDULOS
Control360 SOU - Sistema de Gestão e Análise de Projetos



Versão: 2.0  
Data: 12/06/2025  
Preparado para: C-Level TI - Ambiente de Testes Produtivos  
Documento: Especificação Técnica Detalhada dos Módulos



SUMÁRIO EXECUTIVO

O Control360 SOU é uma plataforma integrada de análise e gestão de projetos estruturada em três módulos principais: **Gerencial**, **Macro** e **Status Report Diretoria**. Cada módulo oferece funcionalidades específicas com KPIs calculados em tempo real, dashboards interativos e relatórios executivos.

Principais Características:

- Processamento de dados em tempo real com cache otimizado (30 segundos)
- Interface responsiva com Bootstrap 5.3 e visualizações Chart.js
- Arquitetura modular Flask com SQLAlchemy
- Suporte a múltiplas fontes de dados CSV com encoding latin1
































1. MÓDULO GERENCIAL

1.1 Visão Geral
O módulo Gerencial oferece uma visão estratégica de alto nível para gestores, focando em KPIs essenciais para tomada de decisão executiva.

Objetivo: Fornecer métricas consolidadas de performance e status geral dos projetos para liderança técnica.

1.2 Dashboard Principal (/gerencial/)

1.2.1 Cards de KPIs Principais


PROJETOS ATIVOS

- Definição: Projetos com status "Novo", "Aguardando", "Em Atendimento" ou "Bloqueado"
- Cálculo: COUNT de projetos onde Status IN ('Novo', 'Aguardando', 'Em Atendimento', 'Bloqueado')
- Cor do Card: Verde (border-left-success)
- Ícone: bi-play-circle-fill
- Interatividade: Clicável - abre modal com lista detalhada
- Função de Cálculo: `GerencialService.obter_projetos_ativos()`

EM ATENDIMENTO

- Definição: Projetos especificamente com status "Em Atendimento"
- Cálculo: COUNT de projetos onde Status = 'Em Atendimento'
- Cor do Card: Amarelo (border-left-warning)
- Ícone: bi-clock-fill
- Interatividade: Clicável - abre modal com projetos em atendimento
- Função de Cálculo: `GerencialService.obter_projetos_em_atendimento()`

BURN RATE

- Definição: Taxa de consumo de horas trabalhadas vs. horas planejadas
- Cálculo: (Σ HorasTrabalhadas / Σ Horas) × 100
- Unidade: Percentual (%)
- Cor do Card: Azul (border-left-info)
- Ícone: bi-speedometer2
- Lógica Especial: Se Horas = 0, considera 100% de burn rate
- Função de Cálculo: Calculado em `processar_gerencial()`

PROJETOS CRÍTICOS

- Definição: Projetos com problemas identificados (bloqueados, horas negativas, atrasados)
- Cálculo: COUNT de projetos com uma ou mais condições críticas:
  - Status = "Bloqueado"
  - HorasRestantes < 0
  - VencimentoEm < Data Atual
- Cor do Card: Vermelho (border-left-danger)
- Ícone: bi-exclamation-triangle
- Interatividade: Clicável - abre modal com detalhes dos problemas
- Função de Cálculo: `GerencialService.obter_projetos_criticos()`



PARA FATURAR

- Definição: Projetos elegíveis para faturamento baseado no tipo e conclusão
- Critérios de Elegibilidade:
  - Faturamento = "TERMINO" AND Conclusao >= 100%
  - Faturamento = "PLUS" AND qualquer conclusão
  - Status IN ('Fechado', 'Encerrado', 'Resolvido')
- Cor do Card: Roxo (border-left-purple)
- Ícone: bi-cash-stack
- Função de Cálculo: `GerencialService.obter_projetos_para_faturar()`


1.2.2 Gráficos de Distribuição

DISTRIBUIÇÃO POR SQUAD

- Tipo: Gráfico de Pizza (Chart.js)
- Dados: Contagem de projetos agrupados por campo "Squad"
- Cores: Paleta automática Chart.js
- Interatividade: Hover mostra valores absolutos e percentuais
- Filtros: Responsivo ao filtro de squad aplicado

DISTRIBUIÇÃO POR FATURAMENTO
- Tipo: Gráfico de Pizza (Chart.js)
- Dados: Contagem de projetos agrupados por campo "Faturamento"
- Categorias Esperadas: PRIME, PLUS, INICIO, TERMINO, FEOP, ENGAJAMENTO
- Interatividade: Hover mostra valores e percentuais


1.2.3 Seção de Métricas Avançadas

OCUPAÇÃO DE SQUADS
- Estrutura: Tabela com colunas Squad, Projetos Ativos, Capacidade, % Ocupação
- Cálculo de Capacidade: 540 horas/mês por squad (3 pessoas × 180h)
- Cálculo de Ocupação: (Σ HorasRestantes por Squad / Capacidade) × 100
- Indicadores Visuais:
  - Verde: < 80% ocupação
  - Amarelo: 80-100% ocupação  
  - Vermelho: > 100% ocupação

PERFORMANCE DE ENTREGAS
- Taxa de Sucesso: % de projetos concluídos no prazo
- Tempo Médio Geral: Média de dias entre abertura e conclusão
- Quarter Info: Informações do trimestre fiscal Microsoft
- Cálculo Quarter: Baseado no ano fiscal (julho a junho)


1.3 APIs do Módulo Gerencial

1.3.1 /gerencial/api/projetos-ativos
- Método: GET
- Retorno: Array de objetos projeto
- Estrutura do Objeto:
```json
{
  "id": "número_projeto",
  "nome": "nome_cliente",
  "squad": "nome_squad",
  "status": "status_atual",
  "horas_restantes": float,
  "conclusao": float,
  "especialista": "nome_especialista"
}
```

1.3.2 /gerencial/api/projetos-criticos
- Método: GET
- Retorno: Objeto com métricas e lista de projetos
- Estrutura:
```json
{
  "metricas": {
    "bloqueados": int,
    "horas_negativas": int,
    "atrasados": int
  },
  "projetos": [array_objetos_projeto]
}
```

1.4 Filtros Disponíveis

FILTRO POR SQUAD
- Parâmetro: ?squad=nome_squad
- Comportamento: Filtra todos os dados e gráficos
- Valores Esperados: AZURE, M365, DATA E POWER, CDB

FILTRO POR FATURAMENTO
- Parâmetro: ?faturamento=tipo_faturamento
- Comportamento: Filtra projetos pelo tipo de faturamento
- Valores Esperados: PRIME, PLUS, INICIO, TERMINO, FEOP, ENGAJAMENTO




2. MÓDULO MACRO

2.1 Visão Geral
O módulo Macro oferece análise operacional detalhada com foco em especialistas, accounts e performance de entrega.

       Objetivo: Fornecer visibilidade granular sobre alocação de recursos, performance individual e indicadores operacionais.

2.2 Dashboard Principal (/macro/)

2.2.1 Grid Principal de KPIs


PROJETOS ATIVOS

- Definição: Projetos em andamento (não concluídos)
- Cálculo: COUNT onde Status NOT IN ('Fechado', 'Encerrado', 'Resolvido', 'Cancelado')
- Cor: Verde (border-left-success)
- Ícone: bi-calendar
- Modal: Lista completa com busca e ordenação
- Função: `MacroService.calcular_projetos_ativos()`

PROJETOS CRÍTICOS
- Definição: Projetos com indicadores de risco
- Critérios Críticos:
  - HorasRestantes < 0 (horas negativas)
  - Status = "Bloqueado"
  - VencimentoEm < Data Atual (atrasado)
  - Conclusao < 25% após 30 dias de abertura
- Cor: Vermelho (border-left-danger)
- Ícone: bi-exclamation-triangle
- Função: `MacroService.calcular_projetos_criticos()`

EFICIÊNCIA DE ENTREGA
- Definição: Relação entre horas planejadas e horas trabalhadas
- Cálculo: (Σ HorasTrabalhadas / Σ Horas) × 100
- Interpretação:
  - > 100%: Sobre-esforço (vermelho)
  - 90-100%: Eficiente (verde)
  - 70-89%: Aceitável (amarelo)
  - < 70%: Sub-utilizado (azul)
- Cor: Amarelo (border-left-warning)
- Ícone: bi-speedometer2

PROJETOS CONCLUÍDOS
- Definição: Projetos finalizados no período
- Status Considerados: "Fechado", "Encerrado", "Resolvido"
- Cor: Verde (border-left-success)
- Ícone: bi-check-circle-fill
- Modal: Lista com datas de conclusão e métricas

2.2.2 Grid Secundário de KPIs

TEMPO MÉDIO DE VIDA
- Definição: Média de dias entre abertura e conclusão de projetos
- Cálculo: AVG(DataTermino - DataInicio) para projetos concluídos nos últimos 3 meses
- Unidade: Dias
- Cor: Azul (border-left-info)
- Ícone: bi-hourglass-split
- Função: `MacroService.calcular_tempo_medio_vida()`

MÉDIA DE HORAS POR PROJETO
- Definição: Média de horas estimadas por projeto
- Cálculo: AVG(Horas) para projetos ativos
- Unidade: Horas (h)
- Cor: Azul (border-left-primary)
- Ícone: bi-clock-history

PROJETOS EM RISCO
- Definição: Projetos com indicadores de potencial problema
- Critérios de Risco:
  - Conclusão < 50% e HorasRestantes < 20% das horas originais
  - Sem atualização há mais de 15 dias
  - Burn rate > 150%
- Cor: Laranja (border-left-warning)
- Ícone: bi-exclamation-circle

2.2.3 Gráfico de Status

DISTRIBUIÇÃO POR STATUS
- Tipo: Gráfico de Barras Horizontais
- Dados: Contagem de projetos por status
- Cores por Status:
  - Novo: Azul claro (#36b9cc)
  - Em Atendimento: Azul (#1cc88a)
  - Aguardando: Amarelo (#f6c23e)
  - Encerrado/Resolvido/Fechado: Verde (#1cc88a)
  - Bloqueado: Preto (#858796)
  - Atrasado: Amarelo (#f6c23e)
  - Cancelado: Vermelho (#e74a3b)

2.3 Seção de Especialistas

2.3.1 Tabela de Alocação
Estrutura da Tabela:
- Especialista: Nome do responsável
- Projetos Ativos: Contagem de projetos em andamento
- Taxa de Uso: % de capacidade utilizada
- Horas Restantes: Soma de horas restantes em todos os projetos
- Média de Conclusão: % média de conclusão dos projetos

Indicadores Visuais:
- Taxa de Uso:
  - Verde: < 80%
  - Amarelo: 80-100%
  - Vermelho: > 100%

2.3.2 Modal de Projetos por Especialista
- Ação: Clique no nome do especialista
- Conteúdo: Lista de todos os projetos do especialista
- Colunas: Projeto, Status, % Conclusão, Horas Restantes, Previsão de Término
- Funcionalidades: Busca, ordenação, filtros

2.4 Seção de Account Managers

2.4.1 Tabela de Performance
Estrutura:
- Account Manager: Nome do gerente de conta
- Projetos Ativos: Projetos sob responsabilidade
- Projetos Concluídos: Projetos finalizados no período
- Taxa de Sucesso: % de projetos entregues no prazo
- Valor Total: Soma das horas de todos os projetos

2.5 APIs do Módulo Macro

2.5.1 /macro/api/especialistas
- Método: GET
- Retorno: Dados de alocação dos especialistas
```json
{
  "especialista_nome": {
    "projetos_ativos": int,
    "taxa_uso": float,
    "horas_restantes": float,
    "media_conclusao": float
  }
}
```

2.5.2 /macro/api/filter
- Parâmetros:
  - squad: Filtro por squad
  - especialista: Filtro por especialista
  - date: Filtro por data
- Retorno: Dados filtrados com KPIs recalculados


3. STATUS REPORT DIRETORIA

3.1 Visão Geral (/macro/apresentacao)
Apresentação executiva formatada para diretoria com comparativos mensais e tendências.

       Objetivo: Fornecer visão estratégica condensada para tomada de decisão executiva.

3.2 Seção de KPIs Comparativos

3.2.1 Projetos Ativos vs. Mês Anterior
- Métrica Principal: Número absoluto de projetos ativos
- Comparativo: Diferença absoluta e percentual vs. mês anterior
- Indicadores Visuais:
  - Seta verde (↑): Aumento
  - Seta vermelha (↓): Diminuição
  - Percentual de variação

3.2.2 Projetos Entregues
- Definição: Projetos concluídos no mês de referência
- Comparação: vs. mesmo período do mês anterior
- Histórico: Gráfico de linha dos últimos 6 meses
- Cálculo: COUNT de projetos com DataTermino no período

3.2.3 Tempo Médio de Vida
- Métrica: Média de dias entre abertura e conclusão
- Tendência: Variação percentual vs. mês anterior
- Categorização:
  - Rápido: < 30 dias
  - Normal: 30-60 dias
  - Demorado: > 60 dias

3.3 Agregações por Status e Squad

3.3.1 Distribuição Geral por Status
Tabela de Agregação:
- Linhas: Status dos projetos
- Colunas: AZURE, M365, DATA E POWER, CDB, TOTAL
- Células: Contagem de projetos
- Cores: Baseadas no status (mesmo padrão do módulo Macro)

3.3.2 Gráfico de Pizza por Squad
- Dados: Total de projetos ativos por squad
- Cores Padronizadas:
  - AZURE: Azul
  - M365: Verde
  - DATA E POWER: Laranja
  - CDB: Roxo

3.4 Novos Projetos

3.4.1 Comparativo Mensal
- Métrica: Projetos abertos no mês
- Filtro: DataInicio no período de referência
- Comparação: vs. mês anterior
- Tendência: Gráfico de linha dos últimos 3 meses

3.5 Funcionalidades de Navegação

3.5.1 Seletor de Mês
- Funcionalidade: Dropdown para selecionar mês/ano de referência
- Fontes Disponíveis: Detecção automática de arquivos históricos
- Formato: dadosr_MMM_YYYY.csv (ex: dadosr_jan_2024.csv)

3.5.2 Visão Atual vs. Histórica
- Visão Atual: Dados de dadosr.csv (mês corrente)
- Visão Histórica: Dados de arquivos específicos do mês
- Indicador: Banner visual diferenciando o modo de visualização


4. CÁLCULOS E FÓRMULAS DETALHADAS

4.1 Fórmulas de KPIs Principais

4.1.1 Burn Rate

Burn Rate = (Σ HorasTrabalhadas / Σ Horas) × 100
Onde:
- HorasTrabalhadas: Tempo efetivamente investido
- Horas: Esforço estimado inicial
- Resultado em percentual


4.1.2 Eficiência de Entrega

Eficiência = (Projetos Entregues no Prazo / Total Projetos Concluídos) × 100
Onde:
- No Prazo: DataTermino <= VencimentoEm
- Concluídos: Status IN ('Fechado', 'Encerrado', 'Resolvido')


4.1.3 Tempo Médio de Vida

TMV = AVG(DataTermino - DataInicio)
Onde:
- Considera apenas projetos concluídos
- Resultado em dias
- Filtro dos últimos 3 meses para relevância


4.1.4 Taxa de Ocupação por Squad

Ocupação = (Σ HorasRestantes por Squad / Capacidade Squad) × 100
Onde:
- CapacidadeSquad = 540 horas/mês (3 pessoas × 180h)
- HorasRestantes: Horas ainda não trabalhadas


4.2 Regras de Negócio Específicas

4.2.1 Status de Projeto Crítico
Um projeto é considerado crítico se atender a UM ou MAIS critérios:
1. Horas Negativas: HorasRestantes < 0
2. Bloqueado: Status = "Bloqueado"
3. Atrasado: VencimentoEm < Data Atual AND Status NOT IN ('Fechado', 'Encerrado', 'Resolvido')
4. Baixa Conclusão: Conclusao < 25% após 30 dias de DataInicio

4.2.2 Projetos Elegíveis para Faturamento
Critérios por tipo de faturamento:
- TERMINO: Conclusao >= 100%
- PLUS: Qualquer conclusão (faturamento antecipado)
- INICIO: Projetos novos (primeiros 30 dias)
- PRIME: Baseado em milestones específicos
- FEOP: Já faturado em outro projeto
- ENGAJAMENTO: Baseado em tempo decorrido



5. ESTRUTURA TÉCNICA DO SISTEMA

       5.1 Arquitetura de Dados
       

5.1.1 Fonte Principal: dadosr.csv
Estrutura de Colunas:
- Número: ID único do projeto (Int64)
- Cliente (Completo): Nome do projeto/cliente
- Serviço (2º Nível): Squad responsável
- Status: Status atual do projeto
- Esforço estimado: Horas planejadas (Float)
- Tempo trabalhado: Horas executadas (Float)
- Andamento: Percentual de conclusão (0-100)
- Responsável: Especialista alocado
- Account Manager: Gerente de conta
- Aberto em: Data de criação (dd/mm/yyyy)
- Resolvido em: Data de conclusão (dd/mm/yyyy)
- Vencimento em: Data limite (dd/mm/yyyy HH:mm)
- Tipo de faturamento: Categoria de cobrança

5.1.2 Processamento de Dados
1. Carregamento: CSV com encoding latin1 e separador ';'
2. Conversão de Tipos:
   - Datas: pd.to_datetime com format '%d/%m/%Y'
   - Números: pd.to_numeric com errors='coerce'
   - Tempo: Conversão de formato HH:mm para decimal
3. Renomeação: Mapeamento para nomes internos do sistema
4. Padronização: Status em Title Case, Faturamento mapeado


5.2 Cache e Otimização

5.2.1 Cache de Dados
- TTL: 30 segundos para dados gerais
- Cache de Projetos: 60 segundos para detalhes específicos
- Invalidação: Automática por timestamp
- Benefício: Redução de 80% no tempo de resposta

5.2.2 Otimizações de Performance
- Logs Reduzidos: Minimização de logging em operações frequentes
- Processamento Silencioso: Carregamento sem logs excessivos
- Agregações Inteligentes: Cálculo incremental quando possível

5.3 APIs e Endpoints

5.3.1 Padrão de Resposta
```json
{
  "success": boolean,
  "data": object|array,
  "message": string,
  "timestamp": "ISO-8601",
  "filters_applied": object
}
```

5.3.2 Tratamento de Erros
- Fallback: Estruturas vazias em caso de erro
- Logging: Registro detalhado para debugging
- User-Friendly: Mensagens amigáveis para usuários
- Códigos HTTP: Status apropriados (200, 400, 500)



6. CONSIDERAÇÕES PARA DEPLOY

6.1 Requisitos de Ambiente
- Python 3.8+ com Flask
- Arquivo de Dados: dadosr.csv em data/
- Banco de Dados: SQLite inicializado
- Dependências: requirements.txt instalado

6.2 Pontos de Verificação
1. Dados Atualizados: Verificar data de modificação do dadosr.csv
2. Performance: Monitorar tempos de resposta dos dashboards
3. Cache: Verificar se cache está funcionando adequadamente
4. Logs: Acompanhar logs para erros ou warnings

6.3 Métricas de Sucesso
       - Tempo de Carregamento: < 2 segundos para dashboards
- Disponibilidade: > 99% de uptime
- Precisão dos Dados: Validação manual de KPIs críticos
- Usabilidade: Feedback positivo dos usuários C-Level


 
