"""
Helper para operações robustas de banco de dados
Trata especificamente o problema de "database is locked" em ambientes containerizados
"""

import time
import logging
from functools import wraps
from sqlalchemy.exc import OperationalError
from flask import current_app
from .. import db

logger = logging.getLogger(__name__)

class DatabaseLockError(Exception):
    """Exceção customizada para problemas de lock do banco"""
    pass

def with_db_retry(max_retries=3, delay=0.1, backoff=2.0):
    """
    Decorator para retry automático em operações de banco de dados.
    
    Args:
        max_retries (int): Número máximo de tentativas
        delay (float): Delay inicial entre tentativas (segundos)
        backoff (float): Multiplicador do delay a cada tentativa
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except OperationalError as e:
                    last_exception = e
                    
                    # Verifica se é erro de database locked
                    if "database is locked" in str(e).lower():
                        if attempt < max_retries:
                            logger.warning(
                                f"Database locked (tentativa {attempt + 1}/{max_retries + 1}). "
                                f"Aguardando {current_delay:.2f}s antes da próxima tentativa..."
                            )
                            
                            # Força rollback para limpar estado da transação
                            try:
                                db.session.rollback()
                            except Exception as rollback_error:
                                logger.debug(f"Erro no rollback: {rollback_error}")
                            
                            time.sleep(current_delay)
                            current_delay *= backoff
                            continue
                        else:
                            logger.error(
                                f"Database locked após {max_retries + 1} tentativas. "
                                f"Falha definitiva na operação."
                            )
                            raise DatabaseLockError(
                                f"Banco de dados bloqueado após {max_retries + 1} tentativas"
                            ) from e
                    else:
                        # Para outros tipos de OperationalError, não faz retry
                        raise
                        
                except Exception as e:
                    # Para outras exceções, não faz retry
                    last_exception = e
                    raise
            
            # Se chegou aqui, esgotou todas as tentativas
            raise last_exception
            
        return wrapper
    return decorator

@with_db_retry(max_retries=5, delay=0.2, backoff=1.5)
def safe_commit():
    """
    Commit seguro com retry automático.
    
    Uso:
        from app.utils.db_helper import safe_commit
        
        # Suas operações no banco
        db.session.add(novo_objeto)
        
        # Commit seguro
        safe_commit()
    """
    try:
        db.session.commit()
        logger.debug("Commit realizado com sucesso")
    except Exception as e:
        logger.error(f"Erro no commit: {e}")
        db.session.rollback()
        raise

@with_db_retry(max_retries=3, delay=0.1, backoff=2.0)
def safe_execute(operation, *args, **kwargs):
    """
    Executa uma operação de banco com retry automático.
    
    Args:
        operation: Função a ser executada
        *args, **kwargs: Argumentos para a função
    
    Uso:
        from app.utils.db_helper import safe_execute
        
        def minha_operacao():
            obj = MinhaModel(dados)
            db.session.add(obj)
            db.session.commit()
            return obj
            
        resultado = safe_execute(minha_operacao)
    """
    return operation(*args, **kwargs)

def check_database_health():
    """
    Verifica a saúde do banco de dados.
    
    Returns:
        dict: Status da verificação
    """
    try:
        # Testa uma consulta simples
        result = db.session.execute(db.text("SELECT 1"))
        result.fetchone()
        
        return {
            'status': 'healthy',
            'message': 'Banco de dados respondendo normalmente'
        }
        
    except OperationalError as e:
        if "database is locked" in str(e).lower():
            return {
                'status': 'locked',
                'message': 'Banco de dados está bloqueado',
                'error': str(e)
            }
        else:
            return {
                'status': 'error',
                'message': 'Erro operacional no banco de dados',
                'error': str(e)
            }
            
    except Exception as e:
        return {
            'status': 'error',
            'message': 'Erro inesperado no banco de dados',
            'error': str(e)
        }

def force_unlock_database():
    """
    Força desbloqueio do banco SQLite em situações extremas.
    
    ⚠️ USAR COM CUIDADO: Pode causar perda de dados se usado incorretamente
    """
    try:
        logger.warning("Tentando forçar desbloqueio do banco de dados...")
        
        # Fecha todas as conexões pendentes
        db.session.close_all()
        
        # Força limpeza do pool de conexões
        db.engine.dispose()
        
        # Tenta uma operação simples para verificar se desbloqueou
        result = db.session.execute(db.text("SELECT 1"))
        result.fetchone()
        
        logger.info("Banco de dados desbloqueado com sucesso")
        return True
        
    except Exception as e:
        logger.error(f"Falha ao forçar desbloqueio: {e}")
        return False
        
def get_lock_info():
    """
    Obtém informações sobre locks ativos no SQLite.
    
    Returns:
        dict: Informações dos locks
    """
    try:
        # Verifica modo WAL
        wal_mode = db.session.execute(db.text("PRAGMA journal_mode")).fetchone()
        
        # Verifica timeout busy
        busy_timeout = db.session.execute(db.text("PRAGMA busy_timeout")).fetchone()
        
        # Verifica modo de locking
        locking_mode = db.session.execute(db.text("PRAGMA locking_mode")).fetchone()
        
        return {
            'journal_mode': wal_mode[0] if wal_mode else 'unknown',
            'busy_timeout': busy_timeout[0] if busy_timeout else 'unknown',
            'locking_mode': locking_mode[0] if locking_mode else 'unknown'
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter informações de lock: {e}")
        return {'error': str(e)} 