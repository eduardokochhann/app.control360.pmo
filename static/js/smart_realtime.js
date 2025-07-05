/**
 * Sistema de Sincronização Inteligente em Tempo Real
 * Versão otimizada para não sobrecarregar o sistema
 */

class SmartRealtimeSync {
    constructor() {
        this.isActive = true;
        this.syncInterval = 15000; // 15 segundos padrão
        this.fastInterval = 5000; // 5 segundos quando ativo
        this.isUserActive = true;
        this.lastActivity = Date.now();
        this.lastSync = {};
        this.syncQueue = new Set();
        this.isVisible = true;
        this.currentModule = this.detectModule();
        
        this.init();
    }

    init() {
        this.log('🚀 Sistema de sincronização inteligente iniciado');
        this.setupActivityMonitoring();
        this.setupVisibilityMonitoring();
        this.setupCrossTabSync();
        this.startSmartPolling();
        this.setupChangeDetection();
    }

    /**
     * Detecta módulo atual
     */
    detectModule() {
        const path = window.location.pathname;
        if (path.includes('sprint')) return 'sprints';
        if (path.includes('backlog') || path.includes('board')) return 'backlog';
        if (path.includes('macro') || path.includes('dashboard')) return 'dashboard';
        return 'unknown';
    }

    /**
     * Monitora atividade do usuário
     */
    setupActivityMonitoring() {
        const events = ['click', 'keydown', 'scroll'];
        
        events.forEach(event => {
            document.addEventListener(event, () => {
                this.lastActivity = Date.now();
                this.isUserActive = true;
            }, { passive: true });
        });

        // Verifica inatividade a cada 30 segundos
        setInterval(() => {
            this.isUserActive = (Date.now() - this.lastActivity) < 60000; // 1 minuto
        }, 30000);
    }

    /**
     * Monitora visibilidade da aba
     */
    setupVisibilityMonitoring() {
        document.addEventListener('visibilitychange', () => {
            this.isVisible = !document.hidden;
            if (this.isVisible) {
                this.log('👁️ Aba visível - sincronizando');
                this.syncNow();
            }
        });
    }

    /**
     * Sincronização entre abas
     */
    setupCrossTabSync() {
        window.addEventListener('storage', (e) => {
            if (e.key === 'smart_sync_trigger') {
                const data = JSON.parse(e.newValue || '{}');
                if (data.module !== this.currentModule) {
                    this.log(`📨 Sincronização solicitada por ${data.module}`);
                    this.syncNow();
                }
            }
        });
    }

    /**
     * Polling inteligente
     */
    startSmartPolling() {
        const poll = () => {
            if (!this.isVisible) {
                // Aba não visível - polling muito lento
                setTimeout(poll, this.syncInterval * 3);
                return;
            }

            const interval = this.isUserActive ? this.fastInterval : this.syncInterval;
            
            if (this.syncQueue.size > 0) {
                this.processQueue();
            }
            
            setTimeout(poll, interval);
        };

        setTimeout(poll, 3000); // Inicia após 3 segundos
    }

    /**
     * Detecta mudanças que requerem sincronização
     */
    setupChangeDetection() {
        // Monitora fechamento de modais
        document.addEventListener('hidden.bs.modal', (e) => {
            if (e.target.id === 'taskModal' || e.target.classList.contains('task-modal')) {
                this.log('📝 Modal fechado - agendando sincronização');
                this.queueSync('modal_closed');
            }
        });

        // Monitora mudanças no DOM
        const observer = new MutationObserver((mutations) => {
            let hasRelevantChange = false;

            mutations.forEach((mutation) => {
                if (mutation.type === 'childList') {
                    const target = mutation.target;
                    
                    // Verifica se é mudança relevante
                    if (target.classList.contains('kanban-column') ||
                        target.classList.contains('sprint-column') ||
                        target.id === 'sprints-container' ||
                        target.id === 'kanban-board') {
                        hasRelevantChange = true;
                    }
                }
            });

            if (hasRelevantChange) {
                this.log('🔄 Mudança relevante detectada no DOM');
                this.queueSync('dom_change');
            }
        });

        // Observa apenas containers relevantes
        const containers = document.querySelectorAll('#kanban-board, #sprints-container, .dashboard-content');
        containers.forEach(container => {
            observer.observe(container, {
                childList: true,
                subtree: false // Não observa sub-elementos para economizar recursos
            });
        });
    }

    /**
     * Agenda sincronização
     */
    queueSync(reason = 'manual') {
        this.syncQueue.add(reason);
        this.log(`📋 Sincronização agendada: ${reason}`);
        
        // Processa em breve se necessário
        if (this.isVisible && this.syncQueue.size === 1) {
            setTimeout(() => this.processQueue(), 2000);
        }
    }

    /**
     * Processa queue de sincronização
     */
    async processQueue() {
        if (!this.isVisible || this.syncQueue.size === 0) return;

        const reasons = Array.from(this.syncQueue);
        this.syncQueue.clear();

        this.log(`🔄 Processando sincronização: ${reasons.join(', ')}`);

        try {
            await this.performSync();
            this.notifyOtherTabs();
            this.showSyncNotification('Dados atualizados');
        } catch (error) {
            this.log(`❌ Erro na sincronização: ${error.message}`, 'error');
        }
    }

    /**
     * Executa sincronização baseada no módulo atual
     */
    async performSync() {
        const now = Date.now();
        const lastSyncTime = this.lastSync[this.currentModule] || 0;
        
        // Evita sincronização muito frequente
        if (now - lastSyncTime < 3000) {
            this.log('⏱️ Sincronização muito recente - pulando');
            return;
        }

        this.lastSync[this.currentModule] = now;

        switch (this.currentModule) {
            case 'sprints':
                await this.syncSprints();
                break;
            case 'backlog':
                await this.syncBacklog();
                break;
            case 'dashboard':
                await this.syncDashboard();
                break;
        }
    }

    /**
     * Sincroniza módulo Sprints
     */
    async syncSprints() {
        if (typeof window.loadSprints === 'function') {
            this.log('📋 Sincronizando sprints...');
            await window.loadSprints();
            
            // Força atualização visual
            setTimeout(() => {
                this.updateSprintsVisuals();
            }, 500);
        }
    }

    /**
     * Sincroniza módulo Backlog
     */
    async syncBacklog() {
        // Verifica se há mudanças recentes
        const response = await fetch('/api/backlog/check_updates', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (response.ok) {
            const data = await response.json();
            if (data.has_updates) {
                this.log('📊 Atualizações encontradas no backlog');
                
                // Recarrega dados se necessário
                if (typeof window.loadBacklogTasks === 'function') {
                    await window.loadBacklogTasks();
                }
                
                // Atualiza elementos visuais
                this.updateBacklogVisuals();
            }
        }
    }

    /**
     * Sincroniza dashboard
     */
    async syncDashboard() {
        if (typeof window.loadDashboard === 'function') {
            this.log('📈 Sincronizando dashboard...');
            await window.loadDashboard();
        }
    }

    /**
     * Atualiza elementos visuais das sprints
     */
    updateSprintsVisuals() {
        const taskCards = document.querySelectorAll('.task-card[data-task-id]');
        taskCards.forEach(card => {
            const taskId = card.getAttribute('data-task-id');
            if (taskId && typeof window.checkIfTaskCompleted === 'function') {
                window.checkIfTaskCompleted(taskId);
            }
        });
    }

    /**
     * Atualiza elementos visuais do backlog
     */
    updateBacklogVisuals() {
        // Força atualização de badges
        if (typeof window.force_visual_update === 'function') {
            window.force_visual_update();
        }
    }

    /**
     * Notifica outras abas
     */
    notifyOtherTabs() {
        const message = {
            module: this.currentModule,
            timestamp: Date.now()
        };

        localStorage.setItem('smart_sync_trigger', JSON.stringify(message));
        
        // Remove após 2 segundos
        setTimeout(() => {
            localStorage.removeItem('smart_sync_trigger');
        }, 2000);
    }

    /**
     * Sincronização forçada
     */
    syncNow() {
        this.log('🚀 Sincronização forçada');
        this.queueSync('force_sync');
        this.processQueue();
    }

    /**
     * Mostra notificação de sincronização
     */
    showSyncNotification(message) {
        // Cria notificação toast simples
        const toast = document.createElement('div');
        toast.className = 'smart-sync-toast';
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #28a745;
            color: white;
            padding: 8px 16px;
            border-radius: 4px;
            font-size: 14px;
            z-index: 9999;
            opacity: 0;
            transform: translateY(10px);
            transition: all 0.3s ease;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        `;

        toast.innerHTML = `
            <i class="bi bi-check-circle me-2"></i>
            ${message}
        `;

        document.body.appendChild(toast);

        // Anima entrada
        setTimeout(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateY(0)';
        }, 100);

        // Remove após 2 segundos
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            setTimeout(() => toast.remove(), 300);
        }, 2000);
    }

    /**
     * Controla ativação/desativação
     */
    setActive(active) {
        this.isActive = active;
        this.log(`🔄 Sincronização ${active ? 'ativada' : 'desativada'}`);
    }

    /**
     * Obtém estatísticas
     */
    getStats() {
        return {
            isActive: this.isActive,
            isUserActive: this.isUserActive,
            isVisible: this.isVisible,
            currentModule: this.currentModule,
            queueSize: this.syncQueue.size,
            lastActivity: new Date(this.lastActivity).toLocaleTimeString(),
            lastSync: Object.keys(this.lastSync).map(module => ({
                module,
                time: new Date(this.lastSync[module]).toLocaleTimeString()
            }))
        };
    }

    /**
     * Logs otimizados
     */
    log(message, level = 'info') {
        const isDebug = window.location.hostname.includes('localhost') || 
                       window.location.search.includes('debug=true');
        
        if (!isDebug && level === 'info') return;

        const prefix = '[SmartSync]';
        const timestamp = new Date().toLocaleTimeString();

        switch (level) {
            case 'error':
                console.error(`${prefix} ${timestamp} ${message}`);
                break;
            case 'warning':
                console.warn(`${prefix} ${timestamp} ${message}`);
                break;
            default:
                console.log(`${prefix} ${timestamp} ${message}`);
        }
    }
}

// Inicializa quando DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    // Aguarda outros scripts carregarem
    setTimeout(() => {
        window.SmartRealtimeSync = new SmartRealtimeSync();
        
        // Atalhos globais
        window.smartSync = () => window.SmartRealtimeSync.syncNow();
        window.smartStats = () => console.table(window.SmartRealtimeSync.getStats());
        
        console.log('🚀 Sistema de sincronização inteligente ativo');
        console.log('💡 Use smartSync() para sincronizar e smartStats() para ver estatísticas');
    }, 1000);
});

// Intercepta funções existentes para trigger automático
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(() => {
        if (window.SmartRealtimeSync) {
            // Intercepta saveTask
            const originalSaveTask = window.saveTask;
            if (typeof originalSaveTask === 'function') {
                window.saveTask = function(...args) {
                    const result = originalSaveTask.apply(this, args);
                    setTimeout(() => window.SmartRealtimeSync.queueSync('task_saved'), 1000);
                    return result;
                };
            }

            // Intercepta updateTask
            const originalUpdateTask = window.updateTask;
            if (typeof originalUpdateTask === 'function') {
                window.updateTask = function(...args) {
                    const result = originalUpdateTask.apply(this, args);
                    setTimeout(() => window.SmartRealtimeSync.queueSync('task_updated'), 1000);
                    return result;
                };
            }
        }
    }, 1500);
}); 