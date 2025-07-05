/**
 * Script para forçar atualização visual dos símbolos de concluído
 * Garante que tarefas concluídas mostrem os badges e overlays corretos
 */

/**
 * Força atualização visual de todas as tarefas na tela
 */
function forceVisualUpdate() {
    console.log('🔄 Forçando atualização visual de todas as tarefas...');
    
    // Busca todos os cards de tarefa
    const taskCards = document.querySelectorAll('[data-task-id]');
    let updatedCount = 0;
    
    taskCards.forEach(async (taskCard) => {
        const taskId = taskCard.getAttribute('data-task-id');
        if (!taskId) return;
        
        try {
            // Busca dados atualizados da tarefa
            const response = await fetch(`/backlog/api/tasks/${taskId}`);
            if (!response.ok) return;
            
            const task = await response.json();
            
            // Verifica se está concluída
            const isCompleted = checkIfTaskCompleted(task);
            
            // Atualiza visual se necessário
            if (updateTaskCardVisual(taskCard, task, isCompleted)) {
                updatedCount++;
                console.log(`✅ Card ${taskId} atualizado visualmente`);
            }
            
        } catch (error) {
            console.warn(`⚠️ Erro ao atualizar card ${taskId}:`, error);
        }
    });
    
    setTimeout(() => {
        console.log(`🎉 Atualização visual concluída: ${updatedCount} cards atualizados`);
        showUpdateNotification(updatedCount);
    }, 2000);
}

/**
 * Atualiza o visual de um card específico
 * @param {HTMLElement} taskCard - Elemento do card
 * @param {Object} task - Dados da tarefa
 * @param {boolean} isCompleted - Se está concluída
 * @returns {boolean} - Se houve atualização
 */
function updateTaskCardVisual(taskCard, task, isCompleted) {
    let updated = false;
    
    // Atualiza badge de concluído no header
    const taskHeader = taskCard.querySelector('.task-header .d-flex');
    if (taskHeader) {
        const existingBadge = taskHeader.querySelector('.badge.bg-success');
        
        if (isCompleted && !existingBadge) {
            // Adiciona badge se concluído e não existe
            const completedBadge = document.createElement('span');
            completedBadge.className = 'badge bg-success text-white';
            completedBadge.title = 'Tarefa Concluída';
            completedBadge.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i>Concluído';
            taskHeader.appendChild(completedBadge);
            updated = true;
        } else if (!isCompleted && existingBadge) {
            // Remove badge se não concluído mas existe
            existingBadge.remove();
            updated = true;
        }
    }
    
    // Atualiza overlay de concluído
    let completedOverlay = taskCard.querySelector('.task-completed-overlay');
    if (isCompleted && !completedOverlay) {
        // Adiciona overlay se concluído e não existe
        completedOverlay = document.createElement('div');
        completedOverlay.className = 'task-completed-overlay';
        completedOverlay.innerHTML = '<i class="bi bi-check-circle-fill"></i>';
        taskCard.appendChild(completedOverlay);
        updated = true;
    } else if (!isCompleted && completedOverlay) {
        // Remove overlay se não concluído mas existe
        completedOverlay.remove();
        updated = true;
    }
    
    return updated;
}

/**
 * Mostra notificação de atualização
 * @param {number} count - Número de cards atualizados
 */
function showUpdateNotification(count) {
    const notification = document.createElement('div');
    notification.className = 'update-notification';
    notification.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        background: #28a745;
        color: white;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 9999;
        font-weight: bold;
        animation: slideIn 0.3s ease-out;
    `;
    
    // Adiciona animação CSS
    if (!document.getElementById('update-animation-style')) {
        const style = document.createElement('style');
        style.id = 'update-animation-style';
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
        `;
        document.head.appendChild(style);
    }
    
    notification.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <i class="bi bi-check-circle-fill"></i>
            <span>${count} tarefa${count !== 1 ? 's' : ''} atualizada${count !== 1 ? 's' : ''} visualmente</span>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Remove após 4 segundos
    setTimeout(() => {
        notification.style.animation = 'slideIn 0.3s ease-out reverse';
        setTimeout(() => notification.remove(), 300);
    }, 4000);
}

/**
 * Atualiza visual de uma tarefa específica
 * @param {string} taskId - ID da tarefa
 */
async function forceUpdateTask(taskId) {
    console.log(`🔄 Forçando atualização da tarefa ${taskId}...`);
    
    try {
        const response = await fetch(`/backlog/api/tasks/${taskId}`);
        if (!response.ok) {
            throw new Error(`Erro ${response.status}`);
        }
        
        const task = await response.json();
        const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
        
        if (!taskCard) {
            console.warn('⚠️ Card da tarefa não encontrado na UI');
            return;
        }
        
        const isCompleted = checkIfTaskCompleted(task);
        const updated = updateTaskCardVisual(taskCard, task, isCompleted);
        
        if (updated) {
            console.log(`✅ Tarefa ${taskId} atualizada visualmente`);
            showUpdateNotification(1);
        } else {
            console.log(`ℹ️ Tarefa ${taskId} já está com visual correto`);
        }
        
    } catch (error) {
        console.error(`❌ Erro ao atualizar tarefa ${taskId}:`, error);
    }
}

/**
 * Auto-atualização periódica (opcional)
 */
function startAutoUpdate() {
    console.log('🔄 Iniciando auto-atualização visual a cada 30 segundos...');
    
    setInterval(() => {
        const taskCards = document.querySelectorAll('[data-task-id]');
        if (taskCards.length > 0) {
            forceVisualUpdate();
        }
    }, 30000); // 30 segundos
}

// Disponibiliza funções globalmente
window.forceVisualUpdate = forceVisualUpdate;
window.forceUpdateTask = forceUpdateTask;
window.startAutoUpdate = startAutoUpdate;

// Auto-executa atualização após carregar a página
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(() => {
        if (document.querySelectorAll('[data-task-id]').length > 0) {
            console.log('🚀 Executando atualização visual inicial...');
            forceVisualUpdate();
        }
    }, 2000); // 2 segundos após carregar
});

console.log('🔧 Script de atualização visual carregado');
console.log('📝 Use forceVisualUpdate() para atualizar todos os cards');
console.log('📝 Use forceUpdateTask(543) para atualizar tarefa específica'); 