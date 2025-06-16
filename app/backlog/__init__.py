from flask import Blueprint

# Define o Blueprint para a funcionalidade de backlog
# O primeiro argumento é o nome do blueprint, usado internamente pelo Flask
# O segundo argumento é o nome do módulo ou pacote onde o blueprint está localizado (__name__)
# url_prefix adiciona um prefixo a todas as rotas definidas neste blueprint (ex: /backlog/tasks)
# Templates e static files agora são centralizados na raiz do projeto
backlog_bp = Blueprint('backlog', __name__, url_prefix='/backlog')

# Importa as rotas no final para evitar importações circulares
from . import routes
# Importar o módulo de rotas de notas separado
from . import note_routes 