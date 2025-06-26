from flask import Blueprint

# Cria o blueprint do módulo admin
admin_bp = Blueprint('admin', __name__, url_prefix='/adminsystem')

# Importa as rotas após criar o blueprint para evitar importação circular
from . import routes 