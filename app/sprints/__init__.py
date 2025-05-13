from flask import Blueprint

sprints_bp = Blueprint('sprints', __name__, url_prefix='/sprints') # Definindo prefixo base

# Importar rotas depois da criação do blueprint para evitar importação circular
from . import routes 