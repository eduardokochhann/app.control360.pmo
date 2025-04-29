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
