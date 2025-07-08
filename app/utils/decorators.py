from functools import wraps
from flask import abort, flash, redirect, url_for, render_template, current_app
from ..models import ModuleConfiguration

def module_required(module_key, redirect_to='index', show_message=True):
    """
    Decorador para proteger rotas baseado em configurações de módulos.
    
    Args:
        module_key (str): Chave do módulo a ser verificado
        redirect_to (str): Endpoint para redirecionamento se módulo desabilitado 
        show_message (bool): Se deve mostrar mensagem de erro
    
    Usage:
        @module_required('gerencial')
        def dashboard():
            return render_template('dashboard.html')
            
        @module_required('macro.status_report', redirect_to='macro.dashboard')
        def status_report():
            return render_template('status_report.html')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # Verifica se o módulo está habilitado
                if not ModuleConfiguration.is_module_enabled(module_key):
                    current_app.logger.warning(f"Acesso negado ao módulo desabilitado: {module_key}")
                    
                    # Busca configuração do módulo para informações detalhadas
                    module_config = ModuleConfiguration.get_module_config(module_key)
                    
                    if module_config and module_config.maintenance_mode:
                        # Se está em modo de manutenção, mostra mensagem específica
                        message = module_config.maintenance_message or f"O módulo '{module_config.display_name}' está em manutenção."
                        if show_message:
                            flash(message, 'warning')
                    else:
                        # Módulo desabilitado
                        module_name = module_config.display_name if module_config else module_key
                        message = f"O módulo '{module_name}' não está disponível no momento."
                        if show_message:
                            flash(message, 'error')
                    
                    # Tenta redirecionar para o endpoint especificado
                    try:
                        return redirect(url_for(redirect_to))
                    except:
                        # Se falhar, redireciona para index
                        return redirect(url_for('index'))
                
                # Módulo habilitado, executa a função normalmente
                return f(*args, **kwargs)
                
            except Exception as e:
                current_app.logger.error(f"Erro no decorador module_required para {module_key}: {e}")
                # Em caso de erro crítico (ex: tabela não existe), permite acesso (fail-safe)
                # Isso evita que o sistema trave completamente por problemas de configuração
                return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def feature_required(feature_key, parent_module=None, fallback_function=None):
    """
    Decorador para funcionalidades específicas dentro de módulos.
    
    Args:
        feature_key (str): Chave da funcionalidade
        parent_module (str): Módulo pai que deve estar habilitado
        fallback_function (callable): Função a executar se feature desabilitada
    
    Usage:
        @feature_required('macro.performance', parent_module='macro')
        def performance_card():
            return render_template('performance.html')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # Verifica módulo pai se especificado
                if parent_module and not ModuleConfiguration.is_module_enabled(parent_module):
                    current_app.logger.warning(f"Módulo pai '{parent_module}' desabilitado para feature '{feature_key}'")
                    abort(404)
                
                # Verifica se a funcionalidade está habilitada
                if not ModuleConfiguration.is_module_enabled(feature_key):
                    current_app.logger.warning(f"Feature desabilitada: {feature_key}")
                    
                    if fallback_function:
                        return fallback_function(*args, **kwargs)
                    else:
                        # Retorna uma resposta vazia ou erro 404
                        abort(404)
                
                # Feature habilitada, executa normalmente
                return f(*args, **kwargs)
                
            except Exception as e:
                current_app.logger.error(f"Erro no decorador feature_required para {feature_key}: {e}")
                # Em caso de erro, executa função normalmente (fail-safe)
                return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def admin_required(message="Acesso restrito à área administrativa."):
    """
    Decorador específico para rotas administrativas.
    
    Args:
        message (str): Mensagem de erro personalizada
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not ModuleConfiguration.is_module_enabled('admin'):
                current_app.logger.warning("Tentativa de acesso à área administrativa desabilitada")
                flash(message, 'error')
                return redirect(url_for('index'))
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def maintenance_check(module_key):
    """
    Verifica se um módulo está em modo de manutenção.
    
    Args:
        module_key (str): Chave do módulo
        
    Returns:
        bool: True se em manutenção, False caso contrário
    """
    try:
        config = ModuleConfiguration.get_module_config(module_key)
        return config.maintenance_mode if config else False
    except:
        return False

def get_maintenance_message(module_key):
    """
    Obtém a mensagem de manutenção de um módulo.
    
    Args:
        module_key (str): Chave do módulo
        
    Returns:
        str: Mensagem de manutenção ou None
    """
    try:
        config = ModuleConfiguration.get_module_config(module_key)
        if config and config.maintenance_mode:
            return config.maintenance_message or f"O módulo '{config.display_name}' está em manutenção."
        return None
    except:
        return None 