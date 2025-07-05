/**
 * Script específico para testar a tarefa 543
 * Garante que ela apareça como concluída visualmente
 */

async function testTask543() {
    console.log('🔍 Testando especificamente a tarefa 543...');
    
    const taskId = '543';
    
    try {
        // 1. Busca dados da tarefa na API
        const response = await fetch(`/backlog/api/tasks/${taskId}`);
        if (!response.ok) {
            throw new Error(`Erro ${response.status}`);
        }
        
        const task = await response.json();
        console.log('📊 Dados da tarefa 543:', task);
        
        // 2. Verifica se está marcada como concluída
        const isCompleted = checkIfTaskCompleted(task);
        console.log(`🎯 Tarefa 543 está concluída: ${isCompleted ? '✅ SIM' : '❌ NÃO'}`);
        
        // 3. Encontra o card na UI
        const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
        if (!taskCard) {
            console.warn('⚠️ Card da tarefa 543 não encontrado na UI');
            return;
        }
        
        // 4. Verifica se tem os símbolos visuais corretos
        const hasBadge = taskCard.querySelector('.badge.bg-success');
        const hasOverlay = taskCard.querySelector('.task-completed-overlay');
        
        console.log('🎨 Status visual atual:', {
            tem_badge_concluido: !!hasBadge,
            tem_overlay_concluido: !!hasOverlay
        });
        
        // 5. Força atualização visual se necessário
        if (isCompleted && (!hasBadge || !hasOverlay)) {
            console.log('🔧 Forçando atualização visual da tarefa 543...');
            updateTaskCardVisual(taskCard, task, isCompleted);
            
            // Verifica novamente
            setTimeout(() => {
                const newBadge = taskCard.querySelector('.badge.bg-success');
                const newOverlay = taskCard.querySelector('.task-completed-overlay');
                
                console.log('✅ Status visual após atualização:', {
                    tem_badge_concluido: !!newBadge,
                    tem_overlay_concluido: !!newOverlay,
                    atualizado_com_sucesso: !!(newBadge && newOverlay)
                });
                
                if (newBadge && newOverlay) {
                    showTask543Success();
                } else {
                    showTask543Warning();
                }
            }, 500);
        } else if (isCompleted && hasBadge && hasOverlay) {
            console.log('🎉 Tarefa 543 já está com visual correto!');
            showTask543Success();
        } else {
            console.log('ℹ️ Tarefa 543 não está marcada como concluída');
        }
        
    } catch (error) {
        console.error('❌ Erro ao testar tarefa 543:', error);
    }
}

function showTask543Success() {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 120px;
        right: 20px;
        background: #28a745;
        color: white;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 9999;
        font-weight: bold;
        border: 2px solid #155724;
    `;
    
    notification.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <i class="bi bi-check-circle-fill" style="font-size: 18px;"></i>
            <div>
                <div>✅ Tarefa 543 OK!</div>
                <small>Símbolos de concluído visíveis</small>
            </div>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => notification.remove(), 5000);
}

function showTask543Warning() {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 120px;
        right: 20px;
        background: #ffc107;
        color: #212529;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 9999;
        font-weight: bold;
        border: 2px solid #d39e00;
    `;
    
    notification.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <i class="bi bi-exclamation-triangle-fill" style="font-size: 18px;"></i>
            <div>
                <div>⚠️ Tarefa 543 Problema</div>
                <small>Símbolos não aparecem - execute forceUpdateTask(543)</small>
            </div>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => notification.remove(), 8000);
}

// Auto-testa tarefa 543 quando página carrega
document.addEventListener('DOMContentLoaded', function() {
    // Aguarda um pouco para a página carregar completamente
    setTimeout(() => {
        const task543Card = document.querySelector('[data-task-id="543"]');
        if (task543Card) {
            console.log('🚀 Testando tarefa 543 automaticamente...');
            testTask543();
        } else {
            console.log('ℹ️ Tarefa 543 não encontrada na página atual');
        }
    }, 3000);
});

// Disponibiliza globalmente
window.testTask543 = testTask543;

console.log('🔧 Script de teste da tarefa 543 carregado');
console.log('📝 Use testTask543() para testar manualmente'); 