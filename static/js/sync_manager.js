/**
 * Sistema de Sincronização Centralizado para Control360
 * Gerencia eventos de sincronização entre módulos Sprints e Backlog
 */

class SyncManager {
    constructor() {
        this.eventListeners = new Map();
        this.isDebugMode = false;
        this.init();
    }

    init() {
        this.log('SyncManager inicializado');
        
        // Adiciona listener global para mudanças de storage
        window.addEventListener('storage', (e) => {
            if (e.key && e.key.startsWith('sync_')) {
                this.handleSyncEvent(e.key, e.newValue);
            }
        });
    }

    /**
     * Registra um listener para eventos de sincronização
     * @param {string} eventType - Tipo do evento (task_updated, task_created, task_deleted, etc.)
     * @param {Function} callback - Função a ser executada quando o evento ocorrer
     * @param {string} moduleId - ID do módulo que está registrando o listener
     */
    on(eventType, callback, moduleId = 'unknown') {
        if (!this.eventListeners.has(eventType)) {
            this.eventListeners.set(eventType, []);
        }
        
        this.eventListeners.get(eventType).push({
            callback,
            moduleId,
            timestamp: Date.now()
        });
        
        this.log(`Listener registrado: ${eventType} por ${moduleId}`);
    }

    /**
     * Remove um listener específico
     * @param {string} eventType - Tipo do evento
     * @param {string} moduleId - ID do módulo
     */
    off(eventType, moduleId) {
        if (this.eventListeners.has(eventType)) {
            const listeners = this.eventListeners.get(eventType);
            const filtered = listeners.filter(l => l.moduleId !== moduleId);
            this.eventListeners.set(eventType, filtered);
            this.log(`Listener removido: ${eventType} de ${moduleId}`);
        }
    }

    /**
     * Emite um evento de sincronização
     * @param {string} eventType - Tipo do evento
     * @param {Object} data - Dados do evento
     * @param {string} source - Módulo que está emitindo o evento
     */
    emit(eventType, data, source = 'unknown') {
        this.log(`Evento emitido: ${eventType} por ${source}`, data);
        
        // Armazena o evento no localStorage para sincronização entre abas
        const syncKey = `sync_${eventType}_${Date.now()}`;
        const syncData = {
            eventType,
            data,
            source,
            timestamp: Date.now()
        };
        
        try {
            localStorage.setItem(syncKey, JSON.stringify(syncData));
            
            // Remove o item após um tempo para evitar acúmulo
            setTimeout(() => {
                localStorage.removeItem(syncKey);
            }, 5000);
            
            // Executa callbacks locais
            this.executeCallbacks(eventType, data, source);
            
        } catch (error) {
            this.log(`Erro ao armazenar evento de sincronização: ${error.message}`, 'error');
        }
    }

    /**
     * Manipula eventos de sincronização recebidos
     * @param {string} key - Chave do localStorage
     * @param {string} value - Valor do evento
     */
    handleSyncEvent(key, value) {
        if (!value) return;
        
        try {
            const syncData = JSON.parse(value);
            this.log(`Evento recebido: ${syncData.eventType} de ${syncData.source}`, syncData.data);
            
            // Executa callbacks para o evento recebido
            this.executeCallbacks(syncData.eventType, syncData.data, syncData.source);
            
        } catch (error) {
            this.log(`Erro ao processar evento de sincronização: ${error.message}`, 'error');
        }
    }

    /**
     * Executa callbacks registrados para um evento
     * @param {string} eventType - Tipo do evento
     * @param {Object} data - Dados do evento
     * @param {string} source - Fonte do evento
     */
    executeCallbacks(eventType, data, source) {
        if (!this.eventListeners.has(eventType)) return;
        
        const listeners = this.eventListeners.get(eventType);
        
        listeners.forEach(listener => {
            // Não executa callback no módulo que originou o evento
            if (listener.moduleId === source) return;
            
            try {
                listener.callback(data, source);
            } catch (error) {
                this.log(`Erro ao executar callback ${eventType} em ${listener.moduleId}: ${error.message}`, 'error');
            }
        });
    }

    /**
     * Métodos específicos para eventos de tarefas
     */
    emitTaskUpdated(taskId, taskData, source) {
        const data = {
            taskId, 
            taskData,
            // 🔄 CORREÇÃO: Inclui informações de status para melhor sincronização
            statusChanged: taskData.status !== undefined,
            newStatus: taskData.status
        };
        this.emit('task_updated', data, source);
    }

    emitTaskCreated(taskData, source) {
        this.emit('task_created', { taskData }, source);
    }

    emitTaskDeleted(taskId, source) {
        this.emit('task_deleted', { taskId }, source);
    }

    emitTaskMoved(taskId, fromSprintId, toSprintId, source) {
        this.emit('task_moved', { taskId, fromSprintId, toSprintId }, source);
    }

    emitSprintUpdated(sprintId, sprintData, source) {
        this.emit('sprint_updated', { sprintId, sprintData }, source);
    }

    /**
     * Métodos utilitários
     */
    enableDebug() {
        this.isDebugMode = true;
        this.log('Debug mode habilitado');
    }

    disableDebug() {
        this.isDebugMode = false;
    }

    log(message, level = 'info', data = null) {
        if (!this.isDebugMode && level === 'info') return;
        
        const prefix = `[SyncManager] `;
        const timestamp = new Date().toLocaleTimeString();
        
        switch (level) {
            case 'error':
                console.error(`${prefix}${timestamp} ERROR: ${message}`, data);
                break;
            case 'warning':
                console.warn(`${prefix}${timestamp} WARNING: ${message}`, data);
                break;
            default:
                console.log(`${prefix}${timestamp} ${message}`, data);
        }
    }

    /**
     * Obtém estatísticas do sistema de sincronização
     */
    getStats() {
        const stats = {
            totalListeners: 0,
            eventTypes: [],
            moduleIds: new Set()
        };
        
        this.eventListeners.forEach((listeners, eventType) => {
            stats.totalListeners += listeners.length;
            stats.eventTypes.push({
                eventType,
                listenerCount: listeners.length
            });
            
            listeners.forEach(listener => {
                stats.moduleIds.add(listener.moduleId);
            });
        });
        
        stats.moduleIds = Array.from(stats.moduleIds);
        
        return stats;
    }
}

// Instância global do SyncManager
window.SyncManager = new SyncManager();

// Atalhos para facilitar uso
window.syncEmit = (eventType, data, source) => window.SyncManager.emit(eventType, data, source);
window.syncOn = (eventType, callback, moduleId) => window.SyncManager.on(eventType, callback, moduleId);
window.syncOff = (eventType, moduleId) => window.SyncManager.off(eventType, moduleId);

// Habilita debug se estivermos em desenvolvimento
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    window.SyncManager.enableDebug();
}

console.log('SyncManager carregado e pronto para uso'); 