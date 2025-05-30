# Control360 - Sistema de Gestão de Projetos

## 🚀 Instalação e Configuração

### Pré-requisitos
- Python 3.8 ou superior
- pip (gerenciador de pacotes Python)

### 1. Clone o repositório
```bash
git clone [URL_DO_REPOSITORIO]
cd app.control360.SOU
```

### 2. Crie e ative o ambiente virtual
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Instale as dependências
```bash
pip install -r requirements.txt
```

### 4. Configure o banco de dados
```bash
# Aplica todas as migrações (cria o banco automaticamente)
flask db upgrade

# Adiciona dados iniciais (colunas padrão, etc.)
flask seed-db
```

### 5. Execute a aplicação
```bash
python app.py
```

A aplicação estará disponível em: `http://localhost:5000`

## 📁 Estrutura do Banco de Dados

O projeto usa **SQLite** e **Flask-Migrate** para gerenciamento do banco:

- **Localização**: `instance/app.db` (criado automaticamente)
- **Migrações**: Pasta `migrations/` (versionada no Git)
- **Modelos**: `app/models.py`

### ⚠️ Importante
- O arquivo `instance/app.db` **NÃO** é versionado no Git
- As migrações reconstroem a estrutura automaticamente
- Execute `flask db upgrade` sempre após clonar ou pull de novas migrações
- Execute `flask seed-db` para dados iniciais

## Estrutura de Branches
- `master` -> produção
- `refactor/estrutura-modular` -> reorganização do projeto
- `feature/macro-dashboard` -> funcionalidade - categorização macro
- `feature/micro-dashboard` -> funcionalidade - categorização micro
- `feature/gerencial/dashboard` -> funcionalidade - categorização gerencial


APP.CONTROL360.SOU
├── app
│   ├── __pycache__
│   ├── gerencial
│   │   ├── __pycache__
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   ├── services.py
│   ├── macro
│   │   ├── __pycache__
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   ├── services.py
│   ├── error_handlers.py
├── data
│   ├── dados.xlsx
│   ├── projetos.CSV
├── log
│   ├── app.log
│   ├── logs
├── static
├── templates
│   ├── gerencial
│   │   ├── dashboard.html
│   ├── macro
│   │   ├── dashboard.html
│   │   ├── erro.html
├── venv
├── .gitignore
├── app.py
├── README.md
├── requirements.txt
├── TODO.md
