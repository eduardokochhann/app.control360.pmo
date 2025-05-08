from app import create_app
import logging
from flask import current_app
from app.models import Backlog, Task, Column

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = create_app()

with app.app_context():
    try:
        # Verificar se o backlog existe
        backlog_id = 4  # ID que está causando erro
        logger.info(f"Verificando se o backlog ID {backlog_id} existe")
        backlog = Backlog.query.get(backlog_id)
        
        if not backlog:
            logger.error(f"Backlog ID {backlog_id} não encontrado!")
        else:
            logger.info(f"Backlog encontrado: {backlog.id} - Projeto ID: {backlog.project_id}")
            
            # Verificar colunas
            logger.info("Buscando colunas disponíveis:")
            columns = Column.query.all()
            for col in columns:
                logger.info(f"Coluna: ID={col.id}, Nome={col.name}, Identifier={col.identifier}")
                
            # Buscar coluna concluído manualmente
            concluido_cols = Column.query.filter(
                Column.name.ilike('%concluído%') | 
                Column.name.ilike('%concluido%') | 
                Column.identifier.ilike('%concluido%')
            ).all()
            
            if concluido_cols:
                logger.info(f"Colunas 'concluído' encontradas: {len(concluido_cols)}")
                for col in concluido_cols:
                    logger.info(f"Coluna 'concluído': ID={col.id}, Nome={col.name}, Identifier={col.identifier}")
            else:
                logger.warning("Nenhuma coluna 'concluído' encontrada!")
                
            # Verificar tarefas do backlog
            tasks_count = Task.query.filter_by(backlog_id=backlog_id).count()
            logger.info(f"Número de tarefas para o backlog {backlog_id}: {tasks_count}")
            
    except Exception as e:
        logger.exception(f"Erro durante a depuração: {str(e)}")
        
    logger.info("Script de depuração finalizado")

print("Execução do script finalizada.") 