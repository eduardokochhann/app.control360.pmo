# Documentação do Projeto Control360 SOU

## 1. Visão Geral do Projeto

O Control360 SOU é uma aplicação web desenvolvida em Flask que fornece uma plataforma integrada para análise e gestão de dados em três níveis: Gerencial, Macro e Micro. A aplicação é estruturada em módulos independentes que trabalham em conjunto para fornecer uma visão completa dos dados e métricas do negócio.

### 1.1 Tecnologias Principais
- Python 3.x
- Flask (Framework Web)
- SQLAlchemy (ORM)
- Pandas (Manipulação de Dados)
- NumPy (Processamento Numérico)
- Bootstrap (Frontend)

## 2. Arquitetura do Sistema

### 2.1 Estrutura de Diretórios
```
app/
├── gerencial/         # Módulo de gestão gerencial
├── macro/            # Módulo de análise macro
├── micro/            # Módulo de análise micro
├── utils/            # Utilitários compartilhados
├── __init__.py       # Configuração principal
└── error_handlers.py # Tratamento de erros
```

### 2.2 Componentes Principais
- **Blueprints**: Organização modular da aplicação
- **Services**: Lógica de negócio
- **Routes**: Endpoints da API
- **Templates**: Interface do usuário
- **Static**: Recursos estáticos (CSS, JS, imagens)

## 3. Módulos Principais

### 3.1 Módulo Gerencial
O módulo gerencial é responsável pela visão estratégica do negócio, fornecendo dashboards e análises de alto nível.

#### 3.1.1 Principais Funcionalidades
- Dashboard gerencial
- Análise de performance
- Relatórios executivos
- KPIs estratégicos

#### 3.1.2 Arquivos Principais
- `routes.py`: Definição das rotas
- `services.py`: Lógica de negócio
- `base_service.py`: Classes base
- `constants.py`: Constantes e configurações

### 3.2 Módulo Macro
O módulo macro foca em análises de médio prazo e tendências do mercado.

#### 3.2.1 Principais Funcionalidades
- Análise de mercado
- Tendências e previsões
- Comparativos setoriais
- Indicadores macroeconômicos

### 3.3 Módulo Micro
O módulo micro concentra-se em análises detalhadas e operacionais.

#### 3.3.1 Principais Funcionalidades
- Análise operacional
- Métricas de performance
- Indicadores de eficiência
- Relatórios detalhados

## 4. KPIs e Métricas

### 4.1 KPIs Gerenciais
- Taxa de crescimento
- Margem de lucro
- ROI
- Market share

### 4.2 KPIs Macro
- Crescimento do mercado
- Participação de mercado
- Tendências setoriais
- Indicadores econômicos

### 4.3 KPIs Micro
- Eficiência operacional
- Produtividade
- Qualidade
- Tempo de ciclo

## 5. Rotas e Endpoints

### 5.1 Rotas Gerenciais
#### 5.1.1 Dashboard Principal
- **Rota**: `/gerencial/`
- **Método**: GET
- **Parâmetros**:
  - `squad`: Filtro por squad (opcional)
  - `faturamento`: Filtro por tipo de faturamento (opcional)
- **Funcionalidades**:
  - Exibe métricas gerais
  - Gráficos de projetos por squad
  - Gráficos de projetos por faturamento
  - Lista de projetos críticos
  - Ocupação das squads
- **Tratamento de Erros**:
  - Retorna estrutura vazia em caso de erro
  - Inclui código de erro para rastreamento
  - Mantém filtros aplicados

#### 5.1.2 APIs
- **Projetos Ativos**
  - Rota: `/gerencial/api/projetos-ativos`
  - Método: GET
  - Retorno: Lista de projetos em andamento
  - Tratamento de Erros: Retorna lista vazia em caso de erro

- **Projetos Críticos**
  - Rota: `/gerencial/api/projetos-criticos`
  - Método: GET
  - Retorno: Projetos com status crítico
  - Inclui métricas:
    - Bloqueados
    - Horas negativas
    - Atrasados
  - Tratamento de Erros: Retorna estrutura vazia com métricas zeradas

- **Projetos em Atendimento**
  - Rota: `/gerencial/api/projetos-em-atendimento`
  - Método: GET
  - Retorno: Lista de projetos em fase de atendimento
  - Tratamento de Erros: Retorna lista vazia em caso de erro

- **Projetos para Faturar**
  - Rota: `/gerencial/api/projetos-para-faturar`
  - Método: GET
  - Retorno: Projetos pendentes de faturamento
  - Tratamento de Erros: Retorna lista vazia em caso de erro

### 5.1.3 Métricas e KPIs
- **Métricas Principais**:
  - Total de projetos
  - Projetos ativos
  - Projetos abertos
  - Taxa de burn rate

- **Filtros Disponíveis**:
  - Por Squad
  - Por Tipo de Faturamento
  - Por Status do Projeto

### 5.2 Rotas Macro
#### 5.2.1 Dashboard Principal
- **Rota**: `/macro/`
- **Método**: GET
- **Funcionalidades**:
  - KPIs macro
  - Projetos ativos
  - Projetos críticos
  - Projetos concluídos
  - Eficiência de entrega
  - Projetos em risco
  - Tempo médio de vida
  - Ocupação de squads
- **Tratamento de Erros**:
  - Retorna estrutura vazia em caso de erro
  - Mantém KPIs zerados
  - Preserva filtros aplicados

#### 5.2.2 APIs
- **Especialistas**
  - Rota: `/macro/api/especialistas`
  - Método: GET
  - Retorno: Dados de alocação dos especialistas
  - Inclui:
    - Taxa de uso
    - Projetos ativos
    - Métricas por especialista
  - Tratamento de Erros: Retorna dicionário vazio

- **Accounts**
  - Rota: `/macro/api/accounts`
  - Método: GET
  - Retorno: Dados de accounts e seus projetos
  - Inclui:
    - Métricas por account manager
    - Projetos associados
    - Status e indicadores
  - Tratamento de Erros: Retorna lista vazia

- **Filtros**
  - Rota: `/macro/api/filter`
  - Método: GET
  - Parâmetros:
    - `squad`: Filtro por squad
    - `especialista`: Filtro por especialista
    - `date`: Filtro por data
  - Retorno: Dados filtrados com:
    - KPIs
    - Agregações
    - Alocação de especialistas
    - Dados de accounts
  - Tratamento de Erros: Retorna estrutura vazia

- **Projetos por Especialista**
  - Rota: `/macro/api/projetos/especialista/<nome_especialista>`
  - Método: GET
  - Retorno: Projetos ativos do especialista
  - Inclui:
    - Status
    - Horas restantes
    - Conclusão
    - Data prevista de encerramento
  - Tratamento de Erros: Retorna lista vazia

- **Projetos por Account**
  - Rota: `/macro/api/projetos/account/<nome_account>`
  - Método: GET
  - Retorno: Projetos associados à account
  - Inclui:
    - Métricas
    - Status
    - Indicadores de performance
  - Tratamento de Erros: Retorna lista vazia

#### 5.2.3 Métricas e KPIs
- **Métricas Principais**:
  - Projetos ativos
  - Projetos críticos
  - Média de horas
  - Projetos concluídos
  - Eficiência de entrega
  - Tempo médio de vida

- **Indicadores de Status**:
  - Novo (azul claro)
  - Em atendimento (azul)
  - Aguardando (amarelo)
  - Encerrado/Resolvido/Fechado (verde)
  - Bloqueado (preto)
  - Atrasado (amarelo)
  - Cancelado (vermelho)

- **Indicadores de Conclusão**:
  - ≥90% (verde)
  - ≥70% (azul)
  - ≥50% (amarelo)
  - <50% (vermelho)

### 5.3 Rotas Micro
#### 5.3.1 Dashboard Principal
- **Rota**: `/micro/`
- **Método**: GET
- **Funcionalidades**:
  - Métricas micro
  - Visualização detalhada de projetos
  - Análise de eficiência
  - Indicadores operacionais
- **Tratamento de Erros**:
  - Retorna estrutura vazia em caso de erro
  - Mantém métricas zeradas

#### 5.3.2 APIs
- **Projetos por Especialista**
  - Rota: `/micro/api/projetos/especialista/<nome_especialista>`
  - Método: GET
  - Retorno: Projetos detalhados do especialista
  - Inclui:
    - Métricas
    - Status
    - Indicadores de performance
  - Tratamento de Erros: Retorna lista vazia

- **Projetos por Account**
  - Rota: `/micro/api/projetos/account/<nome_account>`
  - Método: GET
  - Retorno: Projetos detalhados da account
  - Inclui:
    - Métricas
    - Status
    - Indicadores de performance
  - Tratamento de Erros: Retorna lista vazia

- **Projetos Ativos**
  - Rota: `/micro/api/projetos/ativos`
  - Método: GET
  - Retorno: Lista de projetos em andamento
  - Inclui:
    - Detalhes operacionais
    - Status atual
    - Métricas de performance
  - Tratamento de Erros: Retorna lista vazia

- **Projetos Críticos**
  - Rota: `/micro/api/projetos/criticos`
  - Método: GET
  - Retorno: Projetos em situação crítica
  - Inclui:
    - Indicadores de risco
    - Status atual
    - Métricas de performance
  - Tratamento de Erros: Retorna lista vazia

- **Projetos Concluídos**
  - Rota: `/micro/api/projetos/concluidos`
  - Método: GET
  - Retorno: Projetos finalizados
  - Inclui:
    - Métricas de conclusão
    - Tempo de execução
    - Indicadores de qualidade
  - Tratamento de Erros: Retorna lista vazia

- **Projetos por Eficiência**
  - Rota: `/micro/api/projetos/eficiencia`
  - Método: GET
  - Retorno: Projetos ordenados por eficiência
  - Inclui:
    - Indicadores de performance
    - Métricas de eficiência
    - Comparativos
  - Tratamento de Erros: Retorna lista vazia

#### 5.3.3 Métricas e KPIs
- **Métricas Operacionais**:
  - Tempo de ciclo
  - Taxa de conclusão
  - Eficiência operacional
  - Qualidade de entrega

## 6. Tratamento de Dados

### 6.1 Carregamento de Dados
- Arquivo CSV principal: `dadosr.csv`
- Codificação: latin1
- Separador: ponto e vírgula (;)
- Tratamento de valores nulos
- Conversão de tipos de dados
- Mapeamento de colunas:
  - 'Número' -> 'Numero'
  - 'Cliente (Completo)' -> 'Projeto'
  - 'Serviço (2º Nível)' -> 'Squad'
  - 'Esforço estimado' -> 'Horas'
  - 'Tempo trabalhado' -> 'HorasTrabalhadas'
  - 'Andamento' -> 'Conclusao'
  - 'Data da última ação' -> 'UltimaInteracao'
  - 'Tipo de faturamento' -> 'Faturamento'
  - 'Responsável' -> 'Especialista'
  - 'Account Manager ' -> 'Account Manager'
  - 'Aberto em' -> 'DataInicio'
  - 'Resolvido em' -> 'DataTermino'
  - 'Vencimento em' -> 'VencimentoEm'

### 6.2 Processamento de Dados
- Conversão de datas:
  - Formato padrão: '%d/%m/%Y'
  - Tratamento especial para 'Vencimento em': '%d/%m/%Y %H:%M'
- Padronização de texto:
  - Status em Title Case
  - Faturamento mapeado para códigos curtos
  - Valores vazios tratados como 'NÃO DEFINIDO'
- Cálculo de métricas:
  - Horas restantes = Horas - HorasTrabalhadas
  - Conclusão limitada entre 0 e 100%
  - Eficiência = Conclusão / HorasTrabalhadas

### 6.3 Validação de Dados
- Colunas obrigatórias:
  - Projeto
  - Status
  - Squad
  - Faturamento
  - HorasTrabalhadas
- Colunas numéricas:
  - Horas
  - HorasRestantes
  - Conclusao
  - HorasTrabalhadas
- Colunas de texto:
  - Squad
  - Status
  - Faturamento
  - Especialista
  - Account Manager

## 7. Configurações

### 7.1 Constantes
- Status dos projetos:
  - FECHADO
  - ENCERRADO
  - RESOLVIDO
  - CANCELADO
  - NOVO
  - AGUARDANDO
  - BLOQUEADO
  - EM ATENDIMENTO
  - ATRASADO
  - ATIVO

- Tipos de faturamento:
  - PRIME
  - PLUS
  - INICIO
  - TERMINO
  - FEOP
  - ENGAJAMENTO

- Grupos de status:
  - STATUS_NAO_ATIVOS: [FECHADO, ENCERRADO, RESOLVIDO, CANCELADO]
  - STATUS_EM_ANDAMENTO: [NOVO, AGUARDANDO, BLOQUEADO, EM ATENDIMENTO]
  - STATUS_ATRASADO: [ATRASADO]
  - STATUS_ATIVO: [ATIVO]

- Configurações de capacidade:
  - HORAS_POR_PESSOA: 180 (horas/mês)
  - PESSOAS_POR_SQUAD: 3
  - CAPACIDADE_TOTAL: 540 (horas por squad)

### 7.2 Logging
- Configuração de níveis:
  - DEBUG
  - INFO
  - WARNING
  - ERROR
  - CRITICAL
- Rotação de arquivos:
  - Tamanho máximo: 5MB
  - Backup count: 3
- Formatação:
  - Timestamp
  - Nome do logger
  - Nível
  - Mensagem
  - Arquivo e linha
- Filtros:
  - MarkdownFilter para formatação especial

### 7.3 JSON Provider
- Serialização de tipos:
  - NumPy integers -> Python int
  - NumPy floats -> Python float
  - NumPy bool -> Python bool
  - NumPy arrays -> Python lists
  - Datetime objects -> ISO format
  - NaN values -> None
- Configurações:
  - ensure_ascii: False
  - sort_keys: True
- Tratamento de erros:
  - TypeError
  - RecursionError

## 8. Tratamento de Erros

### 8.1 Erros Comuns
- **Arquivo CSV vazio**
  - Mensagem: "Arquivo CSV vazio ou inválido"
  - Ação: Retorna DataFrame vazio
  - Log: Nível WARNING

- **Arquivo não encontrado**
  - Mensagem: "Arquivo de dados não encontrado"
  - Ação: Retorna DataFrame vazio
  - Log: Nível ERROR

- **Formato inválido**
  - Mensagem: "Formato do arquivo CSV inválido"
  - Ação: Retorna DataFrame vazio
  - Log: Nível ERROR

- **Dados inconsistentes**
  - Mensagem: "Erro ao processar dados: {mensagem_erro}"
  - Ação: Retorna DataFrame vazio
  - Log: Nível ERROR com stack trace

### 8.2 Mensagens de Erro
- **Formato Padrão**
  - Timestamp
  - Nível do erro
  - Mensagem descritiva
  - Código de erro (quando aplicável)
  - Stack trace (para erros críticos)

- **Fallbacks**
  - Estruturas vazias para APIs
  - Valores padrão para métricas
  - Mensagens amigáveis para usuários
  - Logs detalhados para desenvolvedores

### 8.3 Tratamento por Módulo
- **Gerencial**
  - Retorna estrutura vazia com KPIs zerados
  - Mantém filtros aplicados
  - Inclui código de erro para rastreamento

- **Macro**
  - Retorna dicionário vazio para especialistas
  - Retorna lista vazia para accounts
  - Preserva filtros aplicados
  - Mantém KPIs zerados

- **Micro**
  - Retorna lista vazia para projetos
  - Mantém métricas zeradas
  - Preserva contexto de erro

### 8.4 Logging de Erros
- **Configuração**
  - Níveis: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - Rotação: 5MB por arquivo, 3 backups
  - Formato: Timestamp, nível, mensagem, arquivo, linha

- **Filtros**
  - MarkdownFilter para formatação especial
  - Filtros por módulo
  - Filtros por nível

- **Tratamento de Exceções**
  - Try/except em pontos críticos
  - Logging de stack trace
  - Preservação de contexto

### 8.5 Recuperação de Erros
- **Carregamento de Dados**
  - Verificação de arquivo existente
  - Validação de formato
  - Tratamento de valores nulos
  - Conversão segura de tipos

- **Processamento**
  - Validação de colunas obrigatórias
  - Tratamento de valores inválidos
  - Cálculos seguros
  - Agregações robustas

- **APIs**
  - Respostas consistentes
  - Códigos de status HTTP apropriados
  - Mensagens de erro claras
  - Fallbacks seguros

### 8.6 Monitoramento
- **Métricas de Erro**
  - Contagem por tipo
  - Frequência por módulo
  - Tempo de recuperação
  - Impacto no sistema

- **Alertas**
  - Erros críticos
  - Padrões de falha
  - Degradação de performance
  - Inconsistências de dados

## 9. Segurança

### 9.1 Autenticação e Autorização
- **Autenticação**
  - JWT (JSON Web Tokens)
  - Validação de token em cada requisição
  - Refresh tokens para renovação segura
  - Expiração configurável

- **Autorização**
  - RBAC (Role-Based Access Control)
  - Permissões granulares por módulo
  - Validação de permissões em endpoints
  - Log de tentativas de acesso não autorizado

### 9.2 Proteção de Dados
- **Dados Sensíveis**
  - Criptografia em repouso
  - Criptografia em trânsito (TLS 1.3)
  - Mascaramento de dados sensíveis
  - Política de retenção de dados

- **Backup e Recuperação**
  - Backups automáticos diários
  - Retenção de 30 dias
  - Testes de recuperação mensais
  - Criptografia de backups

### 9.3 Segurança da API
- **Rate Limiting**
  - Limite de requisições por IP
  - Limite de requisições por usuário
  - Detecção de padrões suspeitos
  - Bloqueio temporário de IPs maliciosos

- **Validação de Entrada**
  - Sanitização de dados
  - Validação de tipos
  - Proteção contra SQL Injection
  - Proteção contra XSS

### 9.4 Monitoramento de Segurança
- **Logs de Segurança**
  - Tentativas de login
  - Acessos não autorizados
  - Alterações de permissões
  - Ações críticas

- **Alertas de Segurança**
  - Múltiplas tentativas de login
  - Acessos de IPs suspeitos
  - Alterações em configurações críticas
  - Detecção de vulnerabilidades

### 9.5 Conformidade
- **LGPD**
  - Consentimento explícito
  - Direito ao esquecimento
  - Portabilidade de dados
  - Relatórios de acesso

- **ISO 27001**
  - Políticas de segurança
  - Controles de acesso
  - Gestão de incidentes
  - Auditorias regulares

### 9.6 Práticas de Desenvolvimento Seguro
- **Code Review**
  - Análise de segurança
  - Verificação de vulnerabilidades
  - Testes de penetração
  - Documentação de segurança

- **Dependências**
  - Verificação de vulnerabilidades
  - Atualizações automáticas
  - Política de versões
  - Monitoramento de CVE

## 10. Manutenção

### 10.1 Monitoramento
- Logs de aplicação
- Métricas de performance
- Alertas de erro
- Status do sistema

### 10.2 Atualizações
- Versionamento
- Backup de dados
- Migrações
- Rollback

## 11. Desenvolvimento

### 11.1 Ambiente
- Python 3.x
- Dependências
- Virtualenv
- IDE recomendada

### 11.2 Testes
- Unitários
- Integração
- Performance
- Cobertura

### 11.3 Deploy
- Requisitos
- Processo
- Rollback
- Monitoramento

## 12. Estrutura do Projeto

### 12.1 Estrutura de Diretórios
```
.
├── .git/                  # Controle de versão
├── .vscode/              # Configurações do VS Code
├── app/                  # Código fonte principal
│   ├── gerencial/        # Módulo gerencial
│   ├── macro/           # Módulo macro
│   ├── micro/           # Módulo micro
│   ├── utils/           # Utilitários
│   └── __init__.py      # Inicialização do app
├── data/                # Dados e arquivos CSV
├── docs/                # Documentação
├── logs/                # Arquivos de log
├── static/              # Arquivos estáticos
├── templates/           # Templates HTML
├── venv/                # Ambiente virtual
├── app.py              # Ponto de entrada
├── app.log             # Log da aplicação
├── requirements.txt     # Dependências
└── README.md           # Documentação inicial
```

### 12.2 Dependências (requirements.txt)
```
Flask==2.0.1
pandas==1.3.3
numpy==1.21.2
python-dotenv==0.19.0
gunicorn==20.1.0
Werkzeug==2.0.1
Jinja2==3.0.1
itsdangerous==2.0.1
click==8.0.1
MarkupSafe==2.0.1
```

## 13. Código Fonte

### 13.1 Arquivo Principal (app.py)
```python
from flask import Flask
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
```

### 13.2 Inicialização do App (app/__init__.py)
```python
from flask import Flask
from flask.json import JSONEncoder
import numpy as np
from datetime import datetime

class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        return super().default(obj)

def create_app():
    app = Flask(__name__)
    app.json_encoder = CustomJSONEncoder
    
    # Registrar blueprints
    from app.gerencial import gerencial_bp
    from app.macro import macro_bp
    from app.micro import micro_bp
    
    app.register_blueprint(gerencial_bp)
    app.register_blueprint(macro_bp)
    app.register_blueprint(micro_bp)
    
    return app
```

### 13.3 Módulo Gerencial (app/gerencial/__init__.py)
```python
from flask import Blueprint

gerencial_bp = Blueprint('gerencial', __name__)

from . import routes
```

### 13.4 Módulo Macro (app/macro/__init__.py)
```python
from flask import Blueprint

macro_bp = Blueprint('macro', __name__)

from . import routes
```

### 13.5 Módulo Micro (app/micro/__init__.py)
```python
from flask import Blueprint

micro_bp = Blueprint('micro', __name__)

from . import routes
```

### 13.6 Utilitários (app/utils/data_loader.py)
```python
import pandas as pd
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def load_data(file_path='data/dadosr.csv'):
    try:
        df = pd.read_csv(file_path, encoding='latin1', sep=';')
        
        # Mapeamento de colunas
        column_mapping = {
            'Número': 'Numero',
            'Cliente (Completo)': 'Projeto',
            'Serviço (2º Nível)': 'Squad',
            'Esforço estimado': 'Horas',
            'Tempo trabalhado': 'HorasTrabalhadas',
            'Andamento': 'Conclusao',
            'Data da última ação': 'UltimaInteracao',
            'Tipo de faturamento': 'Faturamento',
            'Responsável': 'Especialista',
            'Account Manager ': 'Account Manager',
            'Aberto em': 'DataInicio',
            'Resolvido em': 'DataTermino',
            'Vencimento em': 'VencimentoEm'
        }
        
        df = df.rename(columns=column_mapping)
        
        # Tratamento de datas
        date_columns = ['DataInicio', 'DataTermino', 'UltimaInteracao']
        for col in date_columns:
            df[col] = pd.to_datetime(df[col], format='%d/%m/%Y', errors='coerce')
        
        df['VencimentoEm'] = pd.to_datetime(df['VencimentoEm'], format='%d/%m/%Y %H:%M', errors='coerce')
        
        # Cálculo de métricas
        df['HorasRestantes'] = df['Horas'] - df['HorasTrabalhadas']
        df['Conclusao'] = df['Conclusao'].clip(0, 100)
        
        return df
        
    except Exception as e:
        logger.error(f"Erro ao carregar dados: {str(e)}")
        return pd.DataFrame()
```

### 13.7 Templates Base (templates/base.html)
```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Control360 SOU{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/">Control360 SOU</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav">
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('gerencial.index') }}">Gerencial</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('macro.index') }}">Macro</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('micro.index') }}">Micro</a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        {% block content %}{% endblock %}
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="{{ url_for('static', filename='js/main.js') }}"></script>
</body>
</html>
```

### 13.8 Estilos CSS (static/css/style.css)
```css
:root {
    --primary-color: #007bff;
    --secondary-color: #6c757d;
    --success-color: #28a745;
    --danger-color: #dc3545;
    --warning-color: #ffc107;
    --info-color: #17a2b8;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background-color: #f8f9fa;
}

.navbar {
    box-shadow: 0 2px 4px rgba(0,0,0,.1);
}

.card {
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,.1);
    margin-bottom: 20px;
}

.card-header {
    background-color: #fff;
    border-bottom: 1px solid rgba(0,0,0,.125);
}

.chart-container {
    position: relative;
    height: 300px;
    margin-bottom: 20px;
}

.table th {
    background-color: #f8f9fa;
}

.badge {
    padding: 5px 10px;
    border-radius: 4px;
}

.status-novo { background-color: var(--info-color); }
.status-em-atendimento { background-color: var(--primary-color); }
.status-aguardando { background-color: var(--warning-color); }
.status-encerrado { background-color: var(--success-color); }
.status-bloqueado { background-color: var(--danger-color); }
.status-atrasado { background-color: var(--warning-color); }
.status-cancelado { background-color: var(--danger-color); }
```

### 13.9 Scripts JavaScript (static/js/main.js)
```javascript
document.addEventListener('DOMContentLoaded', function() {
    // Inicialização de tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Configuração de gráficos
    Chart.defaults.font.family = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";
    Chart.defaults.color = '#6c757d';
});

// Função para criar gráficos
function createChart(canvasId, type, data, options) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: type,
        data: data,
        options: options
    });
}

// Função para atualizar dados via AJAX
function updateData(endpoint, callback) {
    fetch(endpoint)
        .then(response => response.json())
        .then(data => callback(data))
        .catch(error => console.error('Erro ao carregar dados:', error));
}
```

### 13.10 Configuração do VS Code (.vscode/settings.json)
```json
{
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "editor.formatOnSave": true,
    "python.analysis.typeCheckingMode": "basic",
    "files.exclude": {
        "**/__pycache__": true,
        "**/.pytest_cache": true,
        "**/*.pyc": true
    }
}
```

### 13.11 Gitignore (.gitignore)
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
ENV/
env/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Logs
*.log
logs/

# Data
data/*.csv
!data/dadosr.csv

# OS
.DS_Store
Thumbs.db
```

### 13.12 README.md
```markdown
# Control360 SOU

Sistema de gestão e análise de projetos desenvolvido em Flask.

## Requisitos

- Python 3.8+
- pip
- virtualenv (recomendado)

## Instalação

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/control360-sou.git
cd control360-sou
```

2. Crie e ative o ambiente virtual:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Configure as variáveis de ambiente:
```bash
cp .env.example .env
# Edite o arquivo .env com suas configurações
```

5. Execute a aplicação:
```bash
python app.py
```

## Estrutura do Projeto

- `app/`: Código fonte principal
- `data/`: Arquivos de dados
- `docs/`: Documentação
- `static/`: Arquivos estáticos
- `templates/`: Templates HTML
- `logs/`: Arquivos de log

## Documentação

Consulte a documentação completa em `docs/documentacao_projeto.md`.

## Licença

Este projeto está licenciado sob a licença MIT.