# app/__init__.py

from flask import Flask, redirect, url_for
import logging
# Logging handlers removidos para evitar problemas de rotação no Windows
import os # Pode ser útil para caminhos ou variáveis de ambiente
from pathlib import Path
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

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

    # Configuração do Banco de Dados SQLAlchemy
    # Usa um arquivo SQLite dentro da pasta 'instance'
    db_path = INSTANCE_FOLDER_PATH / 'app.db'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path.as_posix()}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

    # Adiciona rota raiz para redirecionar para o dashboard gerencial
    @app.route('/')
    def index():
        return redirect(url_for('gerencial.dashboard'))

    # Verifica a existência de templates essenciais
    check_templates(app)

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
        'micro/dashboard.html',
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
