# Control360 SOU - Sistema de Gestão e Análise de Projetos

## 🚀 Visão Geral

O Control360 SOU é uma plataforma integrada de gestão de projetos desenvolvida em Flask que oferece análise e controle em três níveis: **Gerencial**, **Macro** e **Status Report Diretoria**. O sistema foi concebido para oferecer visibilidade completa dos projetos, KPIs estratégicos e relatórios executivos para tomada de decisão.

### 🎯 Propósito do Sistema
- **Visão Gerencial**: Dashboard estratégico com KPIs de alto nível para gestores
- **Visão Macro**: Análise detalhada de projetos, especialistas e performance operacional
- **Status Report**: Apresentação executiva para diretoria com comparativos e tendências

## 🛠️ Tecnologias e Arquitetura

### Stack Principal
- **Backend**: Python 3.8+ com Flask
- **ORM**: SQLAlchemy com Flask-Migrate
- **Banco de Dados**: SQLite (produção) / PostgreSQL (futuro)
- **Frontend**: Bootstrap 5.3 + Chart.js + Bootstrap Icons
- **Processamento de Dados**: Pandas, NumPy
- **Autenticação**: JWT (JSON Web Tokens)

### Arquitetura Modular
```
app/
├── gerencial/          # Módulo de gestão estratégica
├── macro/             # Módulo de análise operacional
├── backlog/           # Módulo de gestão de backlog
├── sprints/           # Módulo de gestão de sprints
├── utils/             # Utilitários compartilhados
├── models.py          # Modelos de dados
└── __init__.py        # Configuração da aplicação
```

## 📦 Instalação e Configuração

### Pré-requisitos
- Python 3.8 ou superior
- pip (gerenciador de pacotes Python)
- Git

### 1. Clone e Configuração do Ambiente
```bash
# Clone o repositório
git clone [URL_DO_REPOSITORIO]
cd app.control360.SOU

# Crie e ative o ambiente virtual
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 2. Instalação de Dependências
```bash
pip install -r requirements.txt
```

### 3. Configuração do Banco de Dados
```bash
# Aplica todas as migrações (cria o banco automaticamente)
flask db upgrade

# Adiciona dados iniciais (colunas padrão, configurações)
flask seed-db
```

### 4. Configuração de Dados
O sistema utiliza arquivos CSV como fonte de dados principal:
- **Localização**: `data/dadosr.csv` (arquivo principal)
- **Formato**: CSV com separador `;` e encoding `latin1`
- **Estrutura esperada**:
  - Número, Cliente (Completo), Serviço (2º Nível)
  - Status, Esforço estimado, Tempo trabalhado
  - Andamento, Responsável, Account Manager
  - Aberto em, Resolvido em, Vencimento em

### 5. Execução da Aplicação
```bash
python app.py
```

A aplicação estará disponível em: `http://localhost:5000`

## 🗂️ Estrutura do Banco de Dados

### Configuração SQLite
- **Localização**: `instance/app.db` (criado automaticamente)
- **Migrações**: Pasta `migrations/` (versionada no Git)
- **Modelos**: `app/models.py`

### ⚠️ Importante para Deploy
- O arquivo `instance/app.db` **NÃO** é versionado no Git
- As migrações reconstroem a estrutura automaticamente
- Execute `flask db upgrade` sempre após deploy ou pull de novas migrações
- Execute `flask seed-db` para dados iniciais após configuração

### Principais Tabelas
- **projects**: Dados centrais dos projetos
- **backlogs**: Itens de backlog vinculados aos projetos
- **notes**: Notas e observações dos projetos
- **milestones**: Marcos e entregas dos projetos

## 🌟 Estrutura de Branches

### Branches Principais
- `master` → Ambiente de produção
- `refactor/estrutura-modular` → Reorganização do projeto
- `feature/macro-dashboard` → Funcionalidades macro
- `feature/micro-dashboard` → Funcionalidades micro (futuro)
- `feature/gerencial/dashboard` → Funcionalidades gerenciais

### Workflow de Deploy
1. Desenvolvimento em branches `feature/*`
2. Merge para `refactor/estrutura-modular` para testes
3. Merge para `master` para produção

## 📋 Configurações Importantes

### Variáveis de Ambiente
```bash
FLASK_APP=app.py
FLASK_ENV=production  # ou development
SECRET_KEY=[sua_chave_secreta]
DATABASE_URL=[url_do_banco]  # opcional para PostgreSQL
```

### Configurações de Sistema
- **Capacidade por Squad**: 540 horas/mês (3 pessoas × 180h)
- **Cache de Dados**: 30 segundos para otimização de performance
- **Timezone**: America/Sao_Paulo
- **Formato de Data**: dd/mm/yyyy

### Logging
- **Localização**: `logs/app.log`
- **Níveis**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Rotação**: 5MB por arquivo, 3 backups
- **Formato**: [timestamp] [level] [module] - message

## 🔧 Comandos Úteis

### Gerenciamento do Banco
```bash
# Criar nova migração
flask db migrate -m "Descrição da mudança"

# Aplicar migrações
flask db upgrade

# Reverter migração
flask db downgrade

# Reinicializar banco (CUIDADO!)
flask db init
```

### Testes e Debug
```bash
# Executar testes
python -m pytest

# Debug de dados
python debug_data.py

# Verificar integridade dos dados
python check_data_integrity.py
```

### Performance e Monitoramento
```bash
# Ver logs em tempo real
tail -f logs/app.log

# Verificar tamanho do banco
du -h instance/app.db

# Limpar cache (se implementado)
flask clear-cache
```

## 🚦 Status do Sistema

### Módulos Implementados
- ✅ **Gerencial**: Dashboard completo com KPIs estratégicos
- ✅ **Macro**: Análise detalhada de projetos e performance
- ✅ **Status Report**: Apresentação executiva para diretoria
- ✅ **Backlog**: Gestão de itens e notas
- 🔄 **Sprints**: Em desenvolvimento
- ⏳ **Micro**: Planejado para próximas versões

### Integrações
- ✅ Importação de dados CSV
- ✅ Export para PDF (Status Report)
- 🔄 API REST (em desenvolvimento)
- ⏳ Integração Azure DevOps (planejado)

## 📈 Monitoramento e Manutenção

### Logs Importantes
- Erros de carregamento de dados
- Performance de consultas lentas
- Falhas de autenticação
- Processos de cache

### Backup e Recuperação
- Backup diário automático do banco de dados
- Retenção de 30 dias
- Procedimentos de recuperação documentados

### Atualizações
1. Backup do banco de dados atual
2. Pull das mudanças do repositório
3. Ativação do ambiente virtual
4. Instalação de novas dependências
5. Aplicação de migrações
6. Reinicialização do serviço

## 🆘 Troubleshooting

### Problemas Comuns
1. **Erro de arquivo não encontrado**: Verificar se `data/dadosr.csv` existe
2. **Erro de encoding**: Confirmar que CSV usa encoding `latin1`
3. **Banco não inicializa**: Executar `flask db upgrade`
4. **Performance lenta**: Verificar logs para consultas lentas

---

## 📚 Documentação Adicional
- [Documentação Completa do Projeto](docs/documentacao_completa.md)
- [Manual de KPIs e Métricas](docs/kpis_metricas.md)
- [Guia de Troubleshooting](docs/troubleshooting.md)
