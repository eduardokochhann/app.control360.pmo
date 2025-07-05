/**
 * Sistema de Atualização em Tempo Real para Sprints
 * Atualiza tarefas movidas do backlog para sprint sem reload da página
 */

class SprintRealtimeUpdater {
    constructor() {
        this.isEnabled = true;
        this.pendingUpdates = new Set();
        this.retryAttempts = new Map();
        this.maxRetries = 3;
        
        console.log('🚀 [Sprint] Sistema de atualização em tempo real inicializado');
    }

    /**
     * Atualiza uma tarefa após ela ser movida para uma sprint
     * @param {string} taskId - ID da tarefa
     * @param {string} sprintId - ID da sprint (null se movida para backlog)
     * @param {HTMLElement} taskElement - Elemento DOM da tarefa
     */
    async updateMovedTask(taskId, sprintId, taskElement) {
        if (!this.isEnabled || this.pendingUpdates.has(taskId)) {
            return;
        }

        this.pendingUpdates.add(taskId);
        console.log(`🔄 [Sprint] Atualizando tarefa movida: ${taskId} -> Sprint ${sprintId}`);

        try {
            // 1. Busca dados completos da tarefa da API
            const taskData = await this.fetchTaskData(taskId);
            
            if (taskData) {
                // 2. Re-renderiza o card com dados completos
                await this.refreshTaskCard(taskElement, taskData, sprintId);
                
                // 3. Reaplica event listeners
                this.reattachEventListeners(taskElement, taskData);
                
                // 4. Emite evento de sincronização
                this.emitSyncEvent(taskId, taskData, sprintId);
                
                console.log(`✅ [Sprint] Tarefa ${taskId} atualizada em tempo real`);
            }
            
        } catch (error) {
            console.error(`❌ [Sprint] Erro ao atualizar tarefa ${taskId}:`, error);
            await this.handleUpdateError(taskId, taskElement, error);
        } finally {
            this.pendingUpdates.delete(taskId);
        }
    }

    /**
     * Busca dados completos da tarefa da API
     */
    async fetchTaskData(taskId) {
        try {
            const response = await fetch(`/backlog/api/tasks/${taskId}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Cache-Control': 'no-cache'
                }
            });

            if (!response.ok) {
                throw new Error(`API retornou status ${response.status}`);
            }

            const taskData = await response.json();
            console.log(`📡 [Sprint] Dados da tarefa ${taskId} obtidos:`, taskData);
            
            return taskData;
            
        } catch (error) {
            console.error(`❌ [Sprint] Erro ao buscar dados da tarefa ${taskId}:`, error);
            throw error;
        }
    }

    /**
     * Re-renderiza o card da tarefa com dados completos
     */
    async refreshTaskCard(taskElement, taskData, sprintId) {
        try {
            // Determina se a tarefa está em uma sprint ou no backlog
            const isInSprint = sprintId && sprintId !== 'null';
            
            // Gera HTML atualizado baseado no tipo
            let updatedHTML;
            if (isInSprint) {
                updatedHTML = this.generateSprintTaskHTML(taskData);
            } else {
                updatedHTML = this.generateBacklogTaskHTML(taskData);
            }
            
            // Substitui o conteúdo do card mantendo estrutura externa
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = updatedHTML;
            const newCardContent = tempDiv.firstElementChild;
            
            // Copia atributos importantes
            taskElement.className = newCardContent.className;
            taskElement.innerHTML = newCardContent.innerHTML;
            
            // Atualiza data attributes
            this.updateDataAttributes(taskElement, taskData);
            
            console.log(`🔄 [Sprint] Card da tarefa ${taskData.id} re-renderizado`);
            
        } catch (error) {
            console.error(`❌ [Sprint] Erro ao re-renderizar card:`, error);
            throw error;
        }
    }

    /**
     * Gera HTML para tarefa em sprint
     */
    generateSprintTaskHTML(task) {
        const priorityClass = this.getPriorityClass(task.priority);
        const isCompleted = this.checkIfTaskCompleted(task);
        const completedBadge = isCompleted ? '<span class="badge bg-success text-white"><i class="bi bi-check-circle-fill me-1"></i>Concluído</span>' : '';
        const completedOverlay = isCompleted ? '<div class="task-completed-overlay"><i class="bi bi-check-circle-fill"></i></div>' : '';
        
        return `
            <div class="backlog-task-card mb-2 position-relative" 
                 data-task-id="${task.id}" 
                 data-estimated-hours="${task.estimated_effort || 0}"
                 data-specialist-name="${task.specialist_name || ''}"
                 data-project-id="${task.project_id || ''}"
                 data-project-name="${task.project_name || ''}">
                
                <div class="task-header d-flex justify-content-between align-items-start mb-2">
                    <div class="d-flex align-items-center flex-wrap gap-1">
                        <span class="task-priority-badge badge ${priorityClass}">${task.priority || 'Média'}</span>
                        ${completedBadge}
                    </div>
                    <small class="text-muted">${task.project_name || task.project_id || ''}</small>
                </div>
                
                <div class="task-content">
                    <h6 class="task-title mb-2">${this.escapeHtml(task.title || task.name || 'Sem título')}</h6>
                    
                    <div class="task-details d-flex flex-column gap-1">
                        ${task.specialist_name ? `<small class="task-specialist text-primary">👤 ${this.escapeHtml(task.specialist_name)}</small>` : ''}
                        <small class="task-hours text-secondary">⏱️ ${task.estimated_effort || 0}h</small>
                        ${task.description ? `<small class="text-muted task-description" title="${this.escapeHtml(task.description)}">${this.truncateText(task.description, 80)}</small>` : ''}
                    </div>
                </div>
                
                ${completedOverlay}
            </div>
        `;
    }

    /**
     * Gera HTML para tarefa no backlog
     */
    generateBacklogTaskHTML(task) {
        const priorityClass = this.getPriorityClass(task.priority);
        
        return `
            <div class="backlog-task-card mb-2" 
                 data-task-id="${task.id}" 
                 data-estimated-hours="${task.estimated_effort || 0}"
                 data-specialist-name="${task.specialist_name || ''}"
                 data-project-id="${task.project_id || ''}"
                 data-project-name="${task.project_name || ''}">
                
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <span class="task-priority-badge badge ${priorityClass}">${task.priority || 'Média'}</span>
                    <small class="text-muted">${task.project_name || task.project_id || ''}</small>
                </div>
                
                <h6 class="task-title mb-2">${this.escapeHtml(task.title || task.name || 'Sem título')}</h6>
                
                <div class="task-details">
                    ${task.specialist_name ? `<small class="task-specialist text-primary d-block">👤 ${this.escapeHtml(task.specialist_name)}</small>` : ''}
                    <small class="task-hours text-secondary d-block">⏱️ ${task.estimated_effort || 0}h</small>
                </div>
            </div>
        `;
    }

    /**
     * Atualiza data attributes do elemento
     */
    updateDataAttributes(taskElement, taskData) {
        taskElement.dataset.taskId = taskData.id;
        taskElement.dataset.estimatedHours = taskData.estimated_effort || 0;
        taskElement.dataset.specialistName = taskData.specialist_name || '';
        taskElement.dataset.projectId = taskData.project_id || '';
        taskElement.dataset.projectName = taskData.project_name || '';
    }

    /**
     * Reaplica event listeners no card atualizado
     */
    reattachEventListeners(taskElement, taskData) {
        try {
            // Remove listeners existentes
            const clonedElement = taskElement.cloneNode(true);
            taskElement.parentNode.replaceChild(clonedElement, taskElement);
            
            // Adiciona listener para abrir modal de detalhes
            clonedElement.addEventListener('click', (e) => {
                // Evita abrir modal se clicou em um botão
                if (e.target.closest('button') || e.target.closest('.btn')) {
                    return;
                }
                
                if (typeof window.openTaskDetailsModal === 'function') {
                    window.openTaskDetailsModal(clonedElement, taskData);
                }
            });
            
            // Adiciona listener para drag & drop (se necessário)
            if (clonedElement.closest('.sprint-tasks')) {
                this.makeDraggable(clonedElement);
            }
            
            console.log(`🎯 [Sprint] Event listeners reaplicados na tarefa ${taskData.id}`);
            
        } catch (error) {
            console.error(`❌ [Sprint] Erro ao reaplicar event listeners:`, error);
        }
    }

    /**
     * Torna o elemento arrastável
     */
    makeDraggable(element) {
        try {
            // Se Sortable está disponível, reinicializa
            if (typeof window.initializeSortable === 'function') {
                // Reaplica sortable no container pai
                const container = element.closest('.sprint-tasks, .project-tasks');
                if (container && window.Sortable) {
                    // Verifica se já tem sortable instance
                    const existingInstance = container[window.Sortable.utils.expando];
                    if (existingInstance) {
                        existingInstance.option('disabled', false);
                    }
                }
            }
        } catch (error) {
            console.warn(`⚠️ [Sprint] Não foi possível reaplicar sortable:`, error);
        }
    }

    /**
     * Emite evento de sincronização
     */
    emitSyncEvent(taskId, taskData, sprintId) {
        try {
            if (window.SyncManager) {
                window.SyncManager.emitTaskMoved(taskId, taskData, sprintId, 'sprints');
            }
            
            // Emite evento customizado local
            const event = new CustomEvent('taskRealtimeUpdated', {
                detail: { taskId, taskData, sprintId }
            });
            document.dispatchEvent(event);
            
        } catch (error) {
            console.warn(`⚠️ [Sprint] Erro ao emitir evento de sincronização:`, error);
        }
    }

    /**
     * Trata erros de atualização
     */
    async handleUpdateError(taskId, taskElement, error) {
        const retryCount = this.retryAttempts.get(taskId) || 0;
        
        if (retryCount < this.maxRetries) {
            this.retryAttempts.set(taskId, retryCount + 1);
            console.log(`🔄 [Sprint] Tentativa ${retryCount + 1}/${this.maxRetries} para tarefa ${taskId}`);
            
            // Aguarda um pouco antes de tentar novamente
            await new Promise(resolve => setTimeout(resolve, 1000 * (retryCount + 1)));
            
            // Remove da lista de pendentes para permitir nova tentativa
            this.pendingUpdates.delete(taskId);
            
            // Tenta novamente
            const sprintContainer = taskElement.closest('.sprint-tasks');
            const sprintId = sprintContainer ? sprintContainer.dataset.sprintId : null;
            return this.updateMovedTask(taskId, sprintId, taskElement);
            
        } else {
            console.error(`❌ [Sprint] Falha definitiva ao atualizar tarefa ${taskId} após ${this.maxRetries} tentativas`);
            this.retryAttempts.delete(taskId);
            
            // Como fallback, mostra mensagem e sugere reload
            if (typeof window.showToast === 'function') {
                window.showToast('Tarefa movida, mas detalhes podem não estar atualizados. Recarregue a página se necessário.', 'warning');
            }
        }
    }

    /**
     * Utilitários
     */
    getPriorityClass(priority) {
        const priorityMap = {
            'Baixa': 'text-bg-secondary',
            'Média': 'text-bg-info', 
            'Alta': 'text-bg-warning',
            'Crítica': 'text-bg-danger'
        };
        return priorityMap[priority] || 'text-bg-info';
    }

    checkIfTaskCompleted(task) {
        // Múltiplas verificações para detectar tarefa concluída
        const checks = [
            task.column_identifier === 'concluido',
            task.column_identifier === 'concluído',
            task.column_identifier === 'done',
            task.status === 'Concluído',
            task.status === 'DONE',
            task.column && task.column.name && task.column.name.toLowerCase().includes('conclu'),
            task.column_id === 15 // ID típico da coluna concluído
        ];
        
        return checks.some(check => check);
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    truncateText(text, maxLength) {
        if (!text || text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }

    /**
     * Ativa/desativa o sistema
     */
    setEnabled(enabled) {
        this.isEnabled = enabled;
        console.log(`🔧 [Sprint] Sistema de atualização ${enabled ? 'ativado' : 'desativado'}`);
    }
}

// Instância global
window.SprintRealtimeUpdater = window.SprintRealtimeUpdater || new SprintRealtimeUpdater();

// Aguarda DOM estar carregado
document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ [Sprint] Sistema de atualização em tempo real pronto');
});

console.log('📦 [Sprint] Módulo de atualização em tempo real carregado'); 