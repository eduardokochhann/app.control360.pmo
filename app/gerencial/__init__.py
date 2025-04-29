from flask import Blueprint
from .services import GerencialService

# Cria o blueprint
gerencial_bp = Blueprint('gerencial', __name__, url_prefix='/gerencial')

# Cria uma instância global do serviço
gerencial_service = GerencialService()

# Importa as rotas após criar o blueprint
from . import routes