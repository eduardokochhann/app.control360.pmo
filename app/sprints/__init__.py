from flask import Blueprint

sprints_bp = Blueprint('sprints', __name__, url_prefix='/sprints') # Definindo prefixo base, se desejado

# Importar rotas depois da criação do blueprint para evitar importação circular
from . import routes 