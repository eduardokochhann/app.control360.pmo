"""
Monitoramento da saúde do banco de dados SQLite
Específico para detectar e diagnosticar problemas de lock
"""

from flask import jsonify, current_app
from .. import db
from ..utils.db_helper import check_database_health, get_lock_info, force_unlock_database
import logging

logger = logging.getLogger(__name__)

def get_database_status():
    """
    Retorna status completo do banco de dados.
    
    Returns:
        dict: Status detalhado do banco
    """
    try:
        # Verifica saúde básica
        health = check_database_health()
        
        # Obtém informações de lock
        lock_info = get_lock_info()
        
        # Estatísticas do pool de conexões
        pool_info = {}
        try:
            if hasattr(db.engine.pool, 'size'):
                pool_info = {
                    'pool_size': db.engine.pool.size(),
                    'checked_in': db.engine.pool.checkedin(),
                    'checked_out': db.engine.pool.checkedout(),
                    'overflow': db.engine.pool.overflow(),
                    'invalid': db.engine.pool.invalid()
                }
        except Exception as e:
            pool_info = {'error': f'Erro ao obter info do pool: {e}'}
        
        # Tenta algumas operações de teste
        test_results = {}
        try:
            # Teste de leitura
            start_time = time.time()
            result = db.session.execute(db.text("SELECT COUNT(*) FROM sqlite_master")).fetchone()
            read_time = time.time() - start_time
            test_results['read_test'] = {
                'success': True,
                'time_ms': round(read_time * 1000, 2),
                'tables_count': result[0] if result else 0
            }
        except Exception as e:
            test_results['read_test'] = {
                'success': False,
                'error': str(e)
            }
        
        try:
            # Teste de escrita (temporária)
            start_time = time.time()
            db.session.execute(db.text("CREATE TEMP TABLE test_lock_table (id INTEGER)"))
            db.session.execute(db.text("DROP TABLE test_lock_table"))
            db.session.commit()
            write_time = time.time() - start_time
            test_results['write_test'] = {
                'success': True,
                'time_ms': round(write_time * 1000, 2)
            }
        except Exception as e:
            test_results['write_test'] = {
                'success': False,
                'error': str(e)
            }
            # Força rollback em caso de erro
            try:
                db.session.rollback()
            except:
                pass
        
        return {
            'timestamp': datetime.now().isoformat(),
            'health': health,
            'lock_info': lock_info,
            'pool_info': pool_info,
            'test_results': test_results,
            'database_path': str(current_app.config.get('SQLALCHEMY_DATABASE_URI', '')),
            'status': 'healthy' if health['status'] == 'healthy' else 'warning'
        }
        
    except Exception as e:
        logger.error(f"Erro ao verificar status do banco: {e}")
        return {
            'timestamp': datetime.now().isoformat(),
            'status': 'error',
            'error': str(e)
        }

def emergency_unlock():
    """
    Força desbloqueio do banco em situação de emergência.
    
    Returns:
        dict: Resultado da operação
    """
    try:
        logger.warning("Iniciando procedimento de desbloqueio de emergência...")
        
        # Tenta desbloqueio forçado
        success = force_unlock_database()
        
        if success:
            return {
                'success': True,
                'message': 'Banco de dados desbloqueado com sucesso',
                'timestamp': datetime.now().isoformat()
            }
        else:
            return {
                'success': False,
                'message': 'Falha ao desbloquear banco de dados',
                'timestamp': datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Erro no desbloqueio de emergência: {e}")
        return {
            'success': False,
            'message': f'Erro durante desbloqueio: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }

def get_recent_errors():
    """
    Busca erros recentes relacionados ao banco de dados nos logs.
    
    Returns:
        list: Lista de erros recentes
    """
    errors = []
    try:
        # Busca nos logs do Flask (se disponível)
        if hasattr(current_app, 'logger'):
            # Esta é uma implementação básica
            # Em produção, seria melhor usar um sistema de logs mais robusto
            errors.append({
                'type': 'info',
                'message': 'Sistema de monitoramento ativo',
                'timestamp': datetime.now().isoformat()
            })
    except Exception as e:
        errors.append({
            'type': 'error',
            'message': f'Erro ao buscar logs: {str(e)}',
            'timestamp': datetime.now().isoformat()
        })
    
    return errors

# Importações necessárias
import time
from datetime import datetime 