from flask import Blueprint
from .services import MicroService

# Criar blueprint com prefixo de URL
bp = Blueprint('micro', __name__, url_prefix='/micro')

# Importar rotas após o blueprint para evitar importação circular
from app.micro import routes