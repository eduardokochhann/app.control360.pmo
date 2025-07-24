# -*- coding: utf-8 -*-
# app/__init__.py

from flask import Flask, redirect, url_for, render_template
import logging
# Logging handlers removidos para evitar problemas de rotação no Windows
import os # Pode ser útil para caminhos ou variáveis de ambiente
from pathlib import Path
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Configuração robusta para SQLite em ambientes concorrentes
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """
    Configura SQLite para máxima robustez em ambientes containerizados/concorrentes
    """
    cursor = dbapi_connection.cursor()
    
    # Configurações básicas
    cursor.execute("PRAGMA encoding='UTF-8'")
    
    # 🔧 CONFIGURAÇÕES ANTI-LOCK (OTIMIZADAS PARA WEB)
    cursor.execute("PRAGMA busy_timeout=5000")         # 5 segundos - mais responsivo para web
    cursor.execute("PRAGMA journal_mode=WAL")          # Write-Ahead Logging para concorrência
    cursor.execute("PRAGMA synchronous=NORMAL")        # Balanço entre performance e segurança
    cursor.execute("PRAGMA wal_autocheckpoint=1000")   # Checkpoint automático
    cursor.execute("PRAGMA cache_size=10000")          # Cache maior para performance
    
    # 🔧 CONFIGURAÇÕES DE LOCKING
    cursor.execute("PRAGMA locking_mode=NORMAL")       # Permite múltiplas conexões
    cursor.execute("PRAGMA temp_store=MEMORY")         # Tabelas temporárias em memória
    
    # 🔧 CONFIGURAÇÕES PARA CONTAINERS/DOCKER
    cursor.execute("PRAGMA foreign_keys=ON")          # Integridade referencial
    cursor.execute("PRAGMA defer_foreign_keys=OFF")   # Checagem imediata de FK
    
    cursor.close()

# Importe o JSON Provider customizado
# Ajuste o caminho se sua pasta 'utils' estiver em outro lugar relativo a este __init__.py
from .utils.json_provider import NumpyJSONProvider

# Define o diretório base da aplicação
BASE_DIR = Path(__file__).parent.parent
INSTANCE_FOLDER_PATH = BASE_DIR / 'instance'

# Inicializa as extensões fora da factory para serem importáveis em outros módulos
db = SQLAlchemy()
migrate = Migrate()

# --- Definição do Filtro de Logging (mantido como no seu original) ---
class MarkdownFilter(logging.Filter):
    def filter(self, record):
        if hasattr(record, 'markdown'):
            # Adiciona novas linhas antes e depois para simular um bloco markdown no log
            record.msg = f"\n---\n{record.msg}\n---\n" # Melhor formatação
        return True

def register_blueprints(app):
    """Registra todos os blueprints da aplicação."""
    app.logger.info("Registrando blueprints...")
    
    try:
        from app.gerencial import gerencial_bp
        app.register_blueprint(gerencial_bp)
        app.logger.info("✅ Blueprint 'gerencial' registrado")
    except ImportError as e:
        app.logger.error(f"❌ Erro ao importar ou registrar blueprint 'gerencial': {e}", exc_info=True)

    try:
        from app.macro import macro_bp
        app.register_blueprint(macro_bp)
        app.logger.info("✅ Blueprint 'macro' registrado")
    except ImportError as e:
        app.logger.error(f"❌ Erro ao importar ou registrar blueprint 'macro': {e}", exc_info=True)

    # <<< INÍCIO: Comentar Bloco Micro >>>
    # try:
    #     from app.micro import micro_bp
    #     app.register_blueprint(micro_bp)
    #     app.logger.info("✅ Blueprint 'micro' registrado")
    # except ImportError as e:
    #     app.logger.error(f"❌ Erro ao importar ou registrar blueprint 'micro': {e}", exc_info=True)
    # <<< FIM: Comentar Bloco Micro >>>

    try:
        from app.backlog import backlog_bp
        app.register_blueprint(backlog_bp)
        app.logger.info("--- BACKLOG BLUEPRINT REGISTRATION CALL COMPLETE ---")
        app.logger.info("✅ Blueprint 'backlog' registrado")
    except ImportError as e:
        app.logger.error(f"❌ Erro ao importar ou registrar blueprint 'backlog': {e}", exc_info=True)

    try:
        from app.sprints import sprints_bp
        app.register_blueprint(sprints_bp)
        app.logger.info("✅ Blueprint 'sprints' registrado")
    except ImportError as e:
        app.logger.error(f"❌ Erro ao importar ou registrar blueprint 'sprints': {e}", exc_info=True)

    try:
        from app.admin import admin_bp
        app.register_blueprint(admin_bp)
        app.logger.info("✅ Blueprint 'admin' registrado")
    except ImportError as e:
        app.logger.error(f"❌ Erro ao importar ou registrar blueprint 'admin': {e}", exc_info=True)

def create_app():
    """Cria e configura a instância da aplicação Flask."""
    # Cria a pasta 'instance' se não existir
    INSTANCE_FOLDER_PATH.mkdir(parents=True, exist_ok=True)

    app = Flask(__name__,
                instance_path=str(INSTANCE_FOLDER_PATH), # Informa ao Flask onde está a pasta 'instance'
                template_folder=str(BASE_DIR / 'templates'),
                static_folder=str(BASE_DIR / 'static'))

    # --- Configurações da Aplicação ---
    # Chave secreta (idealmente viria de variável de ambiente)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_secret_key') # Adicione uma chave secreta

    # Configuração robusta do Banco de Dados SQLAlchemy para containers
    db_path = INSTANCE_FOLDER_PATH / 'app.db'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path.as_posix()}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # 🔧 CONFIGURAÇÕES OTIMIZADAS PARA AMBIENTES WEB
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_timeout': 10,           # 10s timeout para obter conexão (mais responsivo)
        'pool_recycle': 3600,         # Recicla conexões a cada 1 hora  
        'pool_pre_ping': True,        # Verifica conexões antes do uso
        'pool_size': 3,               # Pool menor para SQLite (reduzido)
        'max_overflow': 5,            # Menos conexões extras (reduzido)
        'connect_args': {
            'timeout': 10,            # 10s timeout de conexão individual
            'check_same_thread': False # Permite uso em múltiplas threads
        }
    }

    # Configuração do JSON Provider
    app.json = NumpyJSONProvider(app)

    # --- Inicialização das Extensões ---
    db.init_app(app)
    migrate.init_app(app, db)

    # Importa os modelos para que o Flask-Migrate os reconheça
    from . import models

    # Registra comandos CLI customizados
    from . import commands
    commands.register_commands(app)

    # Configuração de Logging
    log_dir = BASE_DIR / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'app.log'
    log_level = logging.DEBUG

    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s [in %(pathname)s:%(lineno)d]'
    )

    # Usa FileHandler simples para evitar problemas de rotação no Windows
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(log_format)
    file_handler.setLevel(log_level)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(log_format)
    stream_handler.setLevel(log_level)

    app.logger.addHandler(file_handler)
    app.logger.addHandler(stream_handler)
    app.logger.setLevel(log_level)
    app.logger.addFilter(MarkdownFilter())

    app.logger.info("Aplicação Flask criada e logging configurado.")
    app.logger.info(f"Usando banco de dados SQLite em: {app.config['SQLALCHEMY_DATABASE_URI']}") # Log do DB URI
    app.logger.info(f"Logs sendo escritos em: {log_file}")

    # Registra os blueprints
    register_blueprints(app)

    # Inicializa configurações padrão de fases de projetos
    def initialize_phase_configurations():
        """Inicializa configurações padrão de fases de projetos na primeira execução."""
        try:
            from .utils.project_phase_service import ProjectPhaseService
            ProjectPhaseService.initialize_phase_configurations()
            app.logger.info("✅ Configurações de fases de projetos inicializadas")
        except Exception as e:
            app.logger.warning(f"⚠️ Erro ao inicializar configurações de fases: {e}")

    # Adiciona contexto ao template para obter a data atual (útil para o copyright)
    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow}
    
    # Context processor para configurações de módulos
    @app.context_processor
    def inject_module_config():
        """Disponibiliza configurações de módulos para todos os templates."""
        try:
            from .models import ModuleConfiguration
            
            # Busca módulos habilitados
            enabled_modules = ModuleConfiguration.get_enabled_modules()
            
            # Cria um dicionário para acesso rápido
            module_config = {}
            for module in enabled_modules:
                module_config[module.module_key] = module.to_dict()
            
            # Função helper para verificar se módulo está habilitado
            def is_module_enabled(module_key):
                return ModuleConfiguration.is_module_enabled(module_key)
            
            return {
                'enabled_modules': enabled_modules,
                'module_config': module_config,
                'is_module_enabled': is_module_enabled
            }
        except Exception as e:
            app.logger.error(f"Erro no context processor de módulos: {e}")
            # Em caso de erro (ex: tabela não criada ainda), retorna fallback seguro
            return {
                'enabled_modules': [],
                'module_config': {},
                'is_module_enabled': lambda x: True  # Fallback: todos habilitados para não quebrar o sistema
            }

    # Modifica a rota raiz para renderizar a nova página inicial
    @app.route('/')
    def index():
        try:
            from .models import ModuleConfiguration
            
            # Busca todos os módulos e funcionalidades habilitados
            enabled_configs = ModuleConfiguration.query.filter_by(is_enabled=True, maintenance_mode=False).order_by(ModuleConfiguration.display_order).all()
            
            # Mapeamento dos módulos reorganizados
            module_mapping = {
                'gerencial': {
                    'url': url_for('gerencial.dashboard'),
                    'icon': 'bi-kanban',
                    'desc': 'Dashboard executivo com KPIs e métricas estratégicas do PMO.',
                    'css_class': 'card-gerencial'
                },
                'macro': {
                    'url': url_for('macro.dashboard'),
                    'icon': 'bi-speedometer2',
                    'desc': 'Gestão de projetos e relatórios macro organizacionais.',
                    'css_class': 'card-macro'
                },
                'status_report': {
                    'url': url_for('macro.apresentacao'),
                    'icon': 'bi-file-earmark-slides',
                    'desc': 'Relatório de status executivo para apresentações.',
                    'css_class': 'card-status-report'
                },
                'backlog': {
                    'url': url_for('backlog.project_selection'),
                    'icon': 'bi-view-list',
                    'desc': 'Gestão de backlog e board de tarefas por projeto.',
                    'css_class': 'card-backlog'
                },
                'sprint': {
                    'url': url_for('sprints.sprint_management_page'),
                    'icon': 'bi-calendar3-week',
                    'desc': 'Planejamento e gestão de sprints semanais.',
                    'css_class': 'card-sprints'
                },
                'admin': {
                    'url': url_for('admin.dashboard'),
                    'icon': 'bi-gear',
                    'desc': 'Central administrativa e configurações do sistema.',
                    'css_class': 'card-admin'
                }
            }
            
            # Constrói lista de cards para módulos principais e funcionalidades importantes
            cards = []
            for config in enabled_configs:
                if config.module_key in module_mapping:
                    card_info = module_mapping[config.module_key].copy()
                    card_info['title'] = config.display_name
                    
                    # Usa descrição do banco se disponível, senão usa padrão do mapeamento
                    if config.description:
                        card_info['desc'] = config.description
                    
                    cards.append(card_info)
            
            app.logger.info(f"Página inicial carregada com {len(cards)} módulos habilitados")
            
        except Exception as e:
            app.logger.error(f"Erro ao carregar configurações de módulos: {e}")
            # Fallback para configuração fixa em caso de erro
            cards = [
                {'url': url_for('gerencial.dashboard'), 'title': 'Visão Gerencial', 'icon': 'bi-kanban', 'desc': 'Dashboard executivo com KPIs e métricas estratégicas do PMO.', 'css_class': 'card-gerencial'},
                {'url': url_for('macro.dashboard'), 'title': 'Visão Macro', 'icon': 'bi-speedometer2', 'desc': 'Gestão de projetos e relatórios macro organizacionais.', 'css_class': 'card-macro'},
                {'url': url_for('macro.apresentacao'), 'title': 'Status Report', 'icon': 'bi-file-earmark-slides', 'desc': 'Relatório de status executivo para apresentações.', 'css_class': 'card-status-report'},
                {'url': url_for('backlog.project_selection'), 'title': 'Backlog de Projetos', 'icon': 'bi-view-list', 'desc': 'Gestão de backlog e board de tarefas por projeto.', 'css_class': 'card-backlog'},
                {'url': url_for('sprints.sprint_management_page'), 'title': 'Sprints Semanais', 'icon': 'bi-calendar3-week', 'desc': 'Planejamento e gestão de sprints semanais.', 'css_class': 'card-sprints'},
                {'url': url_for('admin.dashboard'), 'title': 'Configurações', 'icon': 'bi-gear', 'desc': 'Central administrativa e configurações do sistema.', 'css_class': 'card-admin'}
            ]
        
        return render_template('index.html', cards=cards)

    # Verifica a existência de templates essenciais
    check_templates(app)

    # Inicializa configurações de fases de projetos
    initialize_phase_configurations()

    return app

# --- Funções Auxiliares ---
def check_templates(app):
    """Verifica a existência de arquivos de template essenciais."""
    app.logger.info("Verificando templates essenciais...")
    required_templates = [
        'gerencial/dashboard.html',
        'gerencial/erro.html',
        'macro/dashboard.html',
        'macro/partials/tabela_especialistas.html',
        # 'micro/dashboard.html', # Bloco micro comentado
        'index.html' # Adiciona o novo template à verificação
    ]

    all_found = True
    for template in required_templates:
        if not template_exists(app, template):
            app.logger.warning(f"⚠️ Template essencial não encontrado: {template}")
            all_found = False

    if all_found:
        app.logger.info("Todos os templates essenciais verificados foram encontrados.")

def template_exists(app, template_path):
    """Verifica se um arquivo de template existe no loader do Jinja2."""
    try:
        app.jinja_env.get_template(template_path)
        return True
    except Exception:
        return False

# --- Remover a configuração de logging redundante que estava aqui no final ---
# logging.basicConfig(...) # REMOVIDO
