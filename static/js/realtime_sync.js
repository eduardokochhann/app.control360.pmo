/**
 * Sistema de Sincronização em Tempo Real Inteligente
 * Atualiza dados entre módulos sem sobrecarregar o sistema
 */

class RealtimeSync {
    constructor() {
        this.isActive = true;
        this.lastSync = 0;
        this.syncInterval = 15000; // 15 segundos (configurável)
        this.fastSyncInterval = 5000; // 5 segundos quando há atividade recente
        this.activeThreshold = 60000; // 1 minuto de atividade recente
        this.maxRetries = 3;
        this.retryCount = 0;
        
        // Cache de dados para evitar requisições desnecessárias
        this.dataCache = new Map();
        this.cacheExpiry = 10000; // 10 segundos
        
        // Detectores de atividade
        this.lastActivity = Date.now();
        this.isUserActive = true;
        this.tabVisible = true;
        
        // Queue de sincronização
        this.syncQueue = new Set();
        
        this.init();
    }

    init() {
        this.log('🚀 Sistema de sincronização em tempo real iniciado');
        
        // Detecta atividade do usuário
        this.setupActivityDetection();
        
        // Detecta visibilidade da aba
        this.setupVisibilityDetection();
        
        // Sincronização entre abas
        this.setupCrossTabSync();
        
        // Inicia polling inteligente
        this.startIntelligentPolling();
        
        // Detecta mudanças específicas
        this.setupChangeDetection();
    }

    /**
     * Detecta atividade do usuário para ajustar frequência
     */
    setupActivityDetection() {
        const events = ['click', 'keydown', 'mousemove', 'scroll'];
        const updateActivity = () => {
            this.lastActivity = Date.now();
            this.isUserActive = true;
        };

        events.forEach(event => {
            document.addEventListener(event, updateActivity, { passive: true });
        });

        // Verifica inatividade periodicamente
        setInterval(() => {
            const inactiveTime = Date.now() - this.lastActivity;
            this.isUserActive = inactiveTime < this.activeThreshold;
        }, 30000);
    }

    /**
     * Detecta quando aba está visível
     */
    setupVisibilityDetection() {
        document.addEventListener('visibilitychange', () => {
            this.tabVisible = !document.hidden;
            
            if (this.tabVisible) {
                this.log('👁️ Aba ficou visível, sincronizando...');
                this.forceSyncAll();
            }
        });
    }

    /**
     * Sincronização entre abas usando localStorage
     */
    setupCrossTabSync() {
        window.addEventListener('storage', (e) => {
            if (e.key && e.key.startsWith('realtime_sync_')) {
                this.handleCrossTabMessage(e.key, e.newValue);
            }
        });
    }

    /**
     * Detecta mudanças específicas que requerem sincronização
     */
    setupChangeDetection() {
        // Detecta alterações em modais
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList') {
                    const target = mutation.target;
                    
                    // Modal de tarefa fechado = possível mudança
                    if (target.classList && target.classList.contains('modal') && 
                        !target.classList.contains('show')) {
                        this.queueSync('tasks', 'modal_closed');
                    }
                }
            });
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['class']
        });
    }

    /**
     * Polling inteligente baseado na atividade
     */
    startIntelligentPolling() {
        const poll = () => {
            if (!this.tabVisible) {
                // Aba não visível, polling menos frequente
                setTimeout(poll, this.syncInterval * 2);
                return;
            }

            const interval = this.isUserActive ? 
                this.fastSyncInterval : this.syncInterval;

            this.syncIfNeeded();
            setTimeout(poll, interval);
        };

        poll();
    }

    /**
     * Adiciona item à queue de sincronização
     */
    queueSync(type, reason = 'manual') {
        this.syncQueue.add(type);
        this.log(`📋 Sincronização agendada: ${type} (motivo: ${reason})`);
        
        // Executa em breve se aba estiver visível
        if (this.tabVisible) {
            setTimeout(() => this.processQueue(), 1000);
        }
    }

    /**
     * Processa queue de sincronização
     */
    async processQueue() {
        if (this.syncQueue.size === 0) return;

        const items = Array.from(this.syncQueue);
        this.syncQueue.clear();

        this.log(`🔄 Processando queue: ${items.join(', ')}`);

        for (const item of items) {
            try {
                await this.syncItem(item);
            } catch (error) {
                this.log(`❌ Erro ao sincronizar ${item}: ${error.message}`, 'error');
            }
        }
    }

    /**
     * Sincroniza item específico
     */
    async syncItem(type) {
        const now = Date.now();
        const cacheKey = `sync_${type}`;
        const cached = this.dataCache.get(cacheKey);

        // Verifica cache
        if (cached && (now - cached.timestamp) < this.cacheExpiry) {
            this.log(`💨 Usando cache para ${type}`);
            return cached.data;
        }

        let data = null;

        switch (type) {
            case 'tasks':
                data = await this.syncTasks();
                break;
            case 'sprints':
                data = await this.syncSprints();
                break;
            case 'backlog':
                data = await this.syncBacklog();
                break;
            default:
                this.log(`⚠️ Tipo de sincronização desconhecido: ${type}`);
                return;
        }

        // Atualiza cache
        this.dataCache.set(cacheKey, {
            data: data,
            timestamp: now
        });

        return data;
    }

    /**
     * Sincroniza tarefas
     */
    async syncTasks() {
        try {
            // Detecta qual módulo estamos
            const currentModule = this.detectCurrentModule();
            
            if (currentModule === 'sprints') {
                // Estamos em sprints, verifica mudanças no backlog
                await this.syncSprintsFromBacklog();
            } else if (currentModule === 'backlog') {
                // Estamos no backlog, verifica mudanças em sprints
                await this.syncBacklogFromSprints();
            }

            this.notifyCrossTab('tasks_synced', currentModule);
            
        } catch (error) {
            this.log(`❌ Erro na sincronização de tarefas: ${error.message}`, 'error');
            throw error;
        }
    }

    /**
     * Detecta módulo atual
     */
    detectCurrentModule() {
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
     * Sincroniza sprints com mudanças do backlog
     */
    async syncSprintsFromBacklog() {
        // Verifica se há função loadSprints disponível
        if (typeof loadSprints === 'function') {
            this.log('🔄 Sincronizando sprints...');
            
            // Carrega dados atualizados de forma silenciosa
            const currentTasks = this.getCurrentTaskIds();
            await loadSprints();
            const newTasks = this.getCurrentTaskIds();
            
            // Verifica se houve mudanças
            if (!this.arraysEqual(currentTasks, newTasks)) {
                this.log('✅ Sprints atualizadas com mudanças do backlog');
                this.showSyncNotification('Sprints atualizadas');
            }
        }
    }

    /**
     * Sincroniza backlog com mudanças de sprints
     */
    async syncBacklogFromSprints() {
        // Verifica se há função de reload do backlog
        if (typeof loadBacklogTasks === 'function') {
            this.log('🔄 Sincronizando backlog...');
            await loadBacklogTasks();
            this.log('✅ Backlog atualizado');
        }
    }

    /**
     * Obtém IDs das tarefas atuais
     */
    getCurrentTaskIds() {
        const taskCards = document.querySelectorAll('[data-task-id]');
        return Array.from(taskCards).map(card => card.getAttribute('data-task-id'));
    }

    /**
     * Compara arrays
     */
    arraysEqual(a, b) {
        return a.length === b.length && a.every((val, i) => val === b[i]);
    }

    /**
     * Sincronização forçada de todos os tipos
     */
    async forceSyncAll() {
        this.log('🚀 Sincronização forçada iniciada');
        
        this.queueSync('tasks', 'force_sync');
        this.queueSync('sprints', 'force_sync');
        
        await this.processQueue();
    }

    /**
     * Notifica outras abas
     */
    notifyCrossTab(action, data) {
        const message = {
            action: action,
            data: data,
            timestamp: Date.now(),
            source: this.detectCurrentModule()
        };

        localStorage.setItem(
            `realtime_sync_${action}_${Date.now()}`, 
            JSON.stringify(message)
        );

        // Remove depois de 5 segundos
        setTimeout(() => {
            localStorage.removeItem(`realtime_sync_${action}_${Date.now()}`);
        }, 5000);
    }

    /**
     * Manipula mensagens entre abas
     */
    handleCrossTabMessage(key, value) {
        if (!value) return;

        try {
            const message = JSON.parse(value);
            const currentModule = this.detectCurrentModule();

            // Não processa mensagens da própria aba
            if (message.source === currentModule) return;

            this.log(`📨 Mensagem recebida de ${message.source}: ${message.action}`);

            switch (message.action) {
                case 'tasks_synced':
                    if (currentModule !== message.source) {
                        this.queueSync('tasks', 'cross_tab_notification');
                    }
                    break;
            }
        } catch (error) {
            this.log(`❌ Erro ao processar mensagem entre abas: ${error.message}`, 'error');
        }
    }

    /**
     * Sincroniza apenas se necessário
     */
    async syncIfNeeded() {
        const now = Date.now();
        const timeSinceLastSync = now - this.lastSync;

        // Não sincroniza muito frequentemente
        if (timeSinceLastSync < 3000) return;

        if (this.syncQueue.size > 0) {
            await this.processQueue();
        }

        this.lastSync = now;
    }

    /**
     * Mostra notificação de sincronização
     */
    showSyncNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = 'realtime-sync-notification';
        notification.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: ${type === 'info' ? '#17a2b8' : '#28a745'};
            color: white;
            padding: 12px 16px;
            border-radius: 6px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            z-index: 9999;
            font-size: 14px;
            max-width: 300px;
            opacity: 0;
            transform: translateY(20px);
            transition: all 0.3s ease;
        `;

        notification.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px;">
                <i class="bi bi-arrow-clockwise" style="animation: spin 1s linear;"></i>
                <span>${message}</span>
            </div>
        `;

        // Adiciona CSS da animação
        if (!document.getElementById('sync-animation')) {
            const style = document.createElement('style');
            style.id = 'sync-animation';
            style.textContent = `
                @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }
            `;
            document.head.appendChild(style);
        }

        document.body.appendChild(notification);

        // Anima entrada
        setTimeout(() => {
            notification.style.opacity = '1';
            notification.style.transform = 'translateY(0)';
        }, 100);

        // Remove após 3 segundos
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateY(20px)';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    /**
     * Ativa/desativa sincronização
     */
    setActive(active) {
        this.isActive = active;
        this.log(`🔄 Sincronização ${active ? 'ativada' : 'desativada'}`);
    }

    /**
     * Configura intervalo de sincronização
     */
    setSyncInterval(interval) {
        this.syncInterval = interval;
        this.log(`⏱️ Intervalo de sincronização alterado para ${interval}ms`);
    }

    /**
     * Logs inteligentes
     */
    log(message, level = 'info') {
        if (!window.location.hostname.includes('localhost') && level === 'info') return;

        const prefix = '[RealtimeSync]';
        const timestamp = new Date().toLocaleTimeString();

        switch (level) {
            case 'error':
                console.error(`${prefix} ${timestamp} ERROR: ${message}`);
                break;
            case 'warning':
                console.warn(`${prefix} ${timestamp} WARNING: ${message}`);
                break;
            default:
                console.log(`${prefix} ${timestamp} ${message}`);
        }
    }

    /**
     * Obtém estatísticas
     */
    getStats() {
        return {
            isActive: this.isActive,
            isUserActive: this.isUserActive,
            tabVisible: this.tabVisible,
            lastActivity: new Date(this.lastActivity).toLocaleTimeString(),
            lastSync: new Date(this.lastSync).toLocaleTimeString(),
            queueSize: this.syncQueue.size,
            cacheSize: this.dataCache.size,
            currentModule: this.detectCurrentModule()
        };
    }
}

// Instância global
window.RealtimeSync = new RealtimeSync();

// Atalhos para facilitar uso
window.syncNow = () => window.RealtimeSync.forceSyncAll();
window.syncStats = () => console.table(window.RealtimeSync.getStats());

// Expõe controles
window.setSyncInterval = (interval) => window.RealtimeSync.setSyncInterval(interval);
window.setSyncActive = (active) => window.RealtimeSync.setActive(active);

console.log('🚀 Sistema de sincronização em tempo real carregado');
console.log('📝 Use syncNow() para sincronizar manualmente');
console.log('📊 Use syncStats() para ver estatísticas'); 