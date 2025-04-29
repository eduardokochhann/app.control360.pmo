from flask import Blueprint
from .services import MacroService

# Cria o blueprint
macro_bp = Blueprint('macro', __name__, url_prefix='/macro')

# Cria uma instância global do serviço
macro_service = MacroService()

# Importa as rotas após criar o blueprint
from . import routes