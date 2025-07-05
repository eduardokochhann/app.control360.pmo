/**
 * Integração do Sistema de Tempo Real com Funções Existentes
 * Conecta o RealtimeSync com as funções do sistema atual
 */

// Aguarda carregamento completo
document.addEventListener('DOMContentLoaded', function() {
    // Aguarda o RealtimeSync estar disponível
    const waitForRealtimeSync = () => {
        if (typeof window.RealtimeSync !== 'undefined') {
            initializeRealtimeIntegration();
        } else {
            setTimeout(waitForRealtimeSync, 100);
        }
    };

    waitForRealtimeSync();
});

function initializeRealtimeIntegration() {
    console.log('🔗 Iniciando integração do sistema de tempo real');

    // Detecta módulo atual
    const currentModule = detectCurrentModule();
    
    // Configura integração específica do módulo
    switch (currentModule) {
        case 'sprints':
            setupSprintsIntegration();
            break;
        case 'backlog':
            setupBacklogIntegration();
            break;
        case 'dashboard':
            setupDashboardIntegration();
            break;
    }

    // Configura interceptadores globais
    setupGlobalInterceptors();
}

/**
 * Detecta módulo atual
 */
function detectCurrentModule() {
    const path = window.location.pathname;
    
    if (path.includes('/sprints') || path.includes('/sprint')) {
        return 'sprints';
    } else if (path.includes('/backlog') || path.includes('/board')) {
        return 'backlog';
    } else if (path.includes('/macro') || path.includes('/dashboard')) {
        return 'dashboard';
    }
    
    return 'unknown';
}

/**
 * Configuração para módulo Sprints
 */
function setupSprintsIntegration() {
    console.log('⚡ Configurando integração para Sprints');

    // Intercepta salvamento de tarefas
    const originalSaveTask = window.saveTask;
    if (typeof originalSaveTask === 'function') {
        window.saveTask = function(...args) {
            console.log('💾 Salvando tarefa - disparando sincronização');
            
            // Executa função original
            const result = originalSaveTask.apply(this, args);
            
            // Agenda sincronização
            window.RealtimeSync.queueSync('tasks', 'task_saved');
            
            return result;
        };
    }

    // Intercepta mudanças de status
    const originalUpdateTaskStatus = window.updateTaskStatus;
    if (typeof originalUpdateTaskStatus === 'function') {
        window.updateTaskStatus = function(...args) {
            console.log('🔄 Atualizando status - disparando sincronização');
            
            const result = originalUpdateTaskStatus.apply(this, args);
            
            // Agenda sincronização após mudança
            setTimeout(() => {
                window.RealtimeSync.queueSync('tasks', 'status_updated');
            }, 1000);
            
            return result;
        };
    }

    // Intercepta carregamento de sprints
    const originalLoadSprints = window.loadSprints;
    if (typeof originalLoadSprints === 'function') {
        window.loadSprints = async function(...args) {
            console.log('📋 Carregando sprints...');
            
            // Executa função original
            const result = await originalLoadSprints.apply(this, args);
            
            // Força atualização visual
            setTimeout(() => {
                updateSprintsVisualElements();
            }, 500);
            
            return result;
        };
    }

    // Monitora mudanças no DOM das sprints
    const sprintsContainer = document.querySelector('#sprints-container, .sprints-content, .sprint-columns');
    if (sprintsContainer) {
        const observer = new MutationObserver((mutations) => {
            let hasRelevantChange = false;
            
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    hasRelevantChange = true;
                }
            });
            
            if (hasRelevantChange) {
                console.log('🔍 Mudança detectada no DOM das sprints');
                // Agenda sincronização suave
                setTimeout(() => {
                    window.RealtimeSync.queueSync('tasks', 'dom_change');
                }, 2000);
            }
        });

        observer.observe(sprintsContainer, {
            childList: true,
            subtree: true
        });
    }
}

/**
 * Configuração para módulo Backlog
 */
function setupBacklogIntegration() {
    console.log('📋 Configurando integração para Backlog');

    // Intercepta mudanças de drag & drop
    const originalOnDrop = window.onDrop;
    if (typeof originalOnDrop === 'function') {
        window.onDrop = function(...args) {
            console.log('🎯 Drop detectado - disparando sincronização');
            
            const result = originalOnDrop.apply(this, args);
            
            // Agenda sincronização após drop
            setTimeout(() => {
                window.RealtimeSync.queueSync('tasks', 'task_moved');
            }, 1000);
            
            return result;
        };
    }

    // Intercepta atualizações de tarefas
    const originalUpdateTask = window.updateTask;
    if (typeof originalUpdateTask === 'function') {
        window.updateTask = function(...args) {
            console.log('✏️ Atualizando tarefa - disparando sincronização');
            
            const result = originalUpdateTask.apply(this, args);
            
            // Agenda sincronização
            window.RealtimeSync.queueSync('tasks', 'task_updated');
            
            return result;
        };
    }

    // Monitora mudanças no quadro Kanban
    const kanbanBoard = document.querySelector('#kanban-board, .kanban-columns, .board-container');
    if (kanbanBoard) {
        const observer = new MutationObserver((mutations) => {
            let hasTaskChange = false;
            
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList') {
                    const target = mutation.target;
                    if (target.classList.contains('kanban-column') || 
                        target.classList.contains('task-card')) {
                        hasTaskChange = true;
                    }
                }
            });
            
            if (hasTaskChange) {
                console.log('📊 Mudança detectada no quadro Kanban');
                // Agenda sincronização suave
                setTimeout(() => {
                    window.RealtimeSync.queueSync('tasks', 'kanban_change');
                }, 1500);
            }
        });

        observer.observe(kanbanBoard, {
            childList: true,
            subtree: true
        });
    }
}

/**
 * Configuração para Dashboard
 */
function setupDashboardIntegration() {
    console.log('📊 Configurando integração para Dashboard');

    // Intercepta carregamento de dados do dashboard
    const originalLoadDashboard = window.loadDashboard;
    if (typeof originalLoadDashboard === 'function') {
        window.loadDashboard = async function(...args) {
            console.log('📈 Carregando dashboard...');
            
            const result = await originalLoadDashboard.apply(this, args);
            
            // Agenda sincronização suave
            setTimeout(() => {
                window.RealtimeSync.queueSync('tasks', 'dashboard_loaded');
            }, 1000);
            
            return result;
        };
    }

    // Monitora mudanças em gráficos e widgets
    const dashboardContainer = document.querySelector('#dashboard-container, .dashboard-content');
    if (dashboardContainer) {
        const observer = new MutationObserver((mutations) => {
            let hasDataChange = false;
            
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    hasDataChange = true;
                }
            });
            
            if (hasDataChange) {
                console.log('📊 Mudança detectada no dashboard');
                // Agenda sincronização menos frequente para dashboard
                setTimeout(() => {
                    window.RealtimeSync.queueSync('tasks', 'dashboard_change');
                }, 3000);
            }
        });

        observer.observe(dashboardContainer, {
            childList: true,
            subtree: true
        });
    }
}

/**
 * Configurações globais
 */
function setupGlobalInterceptors() {
    console.log('🌐 Configurando interceptadores globais');

    // Intercepta chamadas AJAX/Fetch
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        const url = args[0];
        
        // Detecta requisições relevantes
        if (typeof url === 'string' && shouldSyncAfterRequest(url)) {
            console.log(`🌐 Requisição relevante detectada: ${url}`);
            
            return originalFetch.apply(this, args).then(response => {
                // Agenda sincronização após requisição bem-sucedida
                if (response.ok) {
                    setTimeout(() => {
                        window.RealtimeSync.queueSync('tasks', 'api_call');
                    }, 1000);
                }
                return response;
            });
        }
        
        return originalFetch.apply(this, args);
    };

    // Intercepta mudanças de localStorage que podem indicar mudanças
    const originalSetItem = localStorage.setItem;
    localStorage.setItem = function(key, value) {
        const result = originalSetItem.apply(this, arguments);
        
        // Detecta mudanças relevantes
        if (key.includes('task') || key.includes('sprint') || key.includes('backlog')) {
            console.log(`💾 Mudança no localStorage: ${key}`);
            setTimeout(() => {
                window.RealtimeSync.queueSync('tasks', 'localStorage_change');
            }, 500);
        }
        
        return result;
    };

    // Monitora mudanças na URL (navegação)
    let lastUrl = window.location.href;
    const urlObserver = new MutationObserver(() => {
        if (window.location.href !== lastUrl) {
            lastUrl = window.location.href;
            console.log('🔄 Mudança de URL detectada');
            
            // Reconfigura integração para novo módulo
            setTimeout(() => {
                initializeRealtimeIntegration();
                window.RealtimeSync.forceSyncAll();
            }, 1000);
        }
    });

    urlObserver.observe(document.body, {
        childList: true,
        subtree: true
    });
}

/**
 * Verifica se deve sincronizar após requisição
 */
function shouldSyncAfterRequest(url) {
    const relevantPaths = [
        '/api/tasks',
        '/api/sprints',
        '/api/backlog',
        '/update_task',
        '/save_task',
        '/move_task',
        '/delete_task'
    ];
    
    return relevantPaths.some(path => url.includes(path));
}

/**
 * Atualiza elementos visuais das sprints
 */
function updateSprintsVisualElements() {
    // Força atualização de badges e símbolos
    const taskCards = document.querySelectorAll('.task-card, .sprint-task');
    taskCards.forEach(card => {
        const taskId = card.getAttribute('data-task-id');
        if (taskId) {
            // Reaplica verificação de status
            if (typeof window.checkIfTaskCompleted === 'function') {
                window.checkIfTaskCompleted(taskId);
            }
        }
    });
}

/**
 * Configurações específicas para produção
 */
function setupProductionOptimizations() {
    if (window.location.hostname.includes('localhost')) return;

    console.log('🚀 Aplicando otimizações para produção');

    // Intervalos mais conservadores em produção
    window.RealtimeSync.setSyncInterval(20000); // 20 segundos
    window.RealtimeSync.fastSyncInterval = 10000; // 10 segundos

    // Reduz logs em produção
    const originalLog = window.RealtimeSync.log;
    window.RealtimeSync.log = function(message, level = 'info') {
        if (level === 'error' || level === 'warning') {
            originalLog.call(this, message, level);
        }
    };
}

// Aplica otimizações específicas do ambiente
setupProductionOptimizations();

// Expõe função para debug
window.debugRealtimeIntegration = function() {
    console.log('🔍 Debug do sistema de tempo real:');
    console.log('📊 Estatísticas:', window.RealtimeSync.getStats());
    console.log('🎯 Módulo atual:', detectCurrentModule());
    console.log('🔗 Integrações ativas:', {
        sprints: typeof window.saveTask === 'function',
        backlog: typeof window.onDrop === 'function',
        dashboard: typeof window.loadDashboard === 'function'
    });
};

console.log('🔗 Sistema de integração em tempo real carregado');
console.log('🐛 Use debugRealtimeIntegration() para debug completo'); 