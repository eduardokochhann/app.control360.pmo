/**
 * Script para testar o status do modal em tempo real
 * Monitora quando o modal é aberto e verifica se o status está correto
 */

// Monitor para modal aberto
document.addEventListener('DOMContentLoaded', function() {
    console.log('🔧 Monitor de status do modal ativado');
    
    // Observa quando o modal é mostrado
    const modalElement = document.getElementById('taskDetailsModal');
    if (modalElement) {
        modalElement.addEventListener('shown.bs.modal', function(event) {
            console.log('🔍 Modal de tarefa aberto, verificando status...');
            setTimeout(() => {
                testModalStatus();
            }, 500); // Aguarda meio segundo para o modal carregar
        });
    }
});

function testModalStatus() {
    const statusSelect = document.getElementById('taskStatus');
    const colunaInput = document.getElementById('taskColumn');
    const taskIdInput = document.getElementById('taskId');
    
    if (!statusSelect || !colunaInput || !taskIdInput) {
        console.warn('⚠️ Elementos do modal não encontrados');
        return;
    }
    
    const taskId = taskIdInput.value;
    const currentStatus = statusSelect.value;
    const currentColumn = colunaInput.value;
    
    console.log('📊 Status atual do modal:', {
        taskId: taskId,
        status: currentStatus,
        coluna: currentColumn,
        statusText: statusSelect.options[statusSelect.selectedIndex]?.text,
        colunaText: colunaInput.value
    });
    
    // Verifica se o status está correto baseado na coluna
    const expectedStatus = getExpectedStatusFromColumn(currentColumn);
    
    if (currentStatus === expectedStatus) {
        console.log('✅ Status do modal está CORRETO!');
        showStatusCheck('✅ Status correto', 'success');
    } else {
        console.log('❌ Status do modal está INCORRETO!');
        console.log(`   Esperado: ${expectedStatus}`);
        console.log(`   Atual: ${currentStatus}`);
        showStatusCheck('❌ Status incorreto', 'error');
    }
    
    // Adiciona botão de teste no modal se não existir
    addTestButtonToModal();
}

function getExpectedStatusFromColumn(columnName) {
    const columnLower = columnName.toLowerCase();
    
    if (columnLower.includes('fazer') || columnLower.includes('todo') || columnLower.includes('pendente')) {
        return 'TODO';
    } else if (columnLower.includes('andamento') || columnLower.includes('progress') || columnLower.includes('desenvolvimento')) {
        return 'IN_PROGRESS';
    } else if (columnLower.includes('revisão') || columnLower.includes('revisao') || columnLower.includes('review') || columnLower.includes('teste')) {
        return 'REVIEW';
    } else if (columnLower.includes('concluí') || columnLower.includes('done') || columnLower.includes('finalizado') || columnLower.includes('pronto')) {
        return 'DONE';
    } else if (columnLower.includes('arquivado') || columnLower.includes('cancelado')) {
        return 'ARCHIVED';
    }
    
    return 'TODO'; // Fallback
}

function showStatusCheck(message, type) {
    // Remove indicador anterior se existir
    const existingIndicator = document.querySelector('.status-check-indicator');
    if (existingIndicator) {
        existingIndicator.remove();
    }
    
    // Cria novo indicador
    const indicator = document.createElement('div');
    indicator.className = 'status-check-indicator';
    indicator.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 10px 20px;
        border-radius: 5px;
        color: white;
        font-weight: bold;
        z-index: 9999;
        background-color: ${type === 'success' ? '#28a745' : '#dc3545'};
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    `;
    indicator.textContent = message;
    
    document.body.appendChild(indicator);
    
    // Remove após 3 segundos
    setTimeout(() => {
        indicator.remove();
    }, 3000);
}

function addTestButtonToModal() {
    const modal = document.getElementById('taskDetailsModal');
    if (!modal) return;
    
    // Verifica se já existe o botão
    if (modal.querySelector('.btn-test-status')) return;
    
    // Encontra área de botões
    const buttonArea = modal.querySelector('.modal-footer');
    if (!buttonArea) return;
    
    // Cria botão de teste
    const testButton = document.createElement('button');
    testButton.type = 'button';
    testButton.className = 'btn btn-info btn-sm btn-test-status';
    testButton.innerHTML = '🔍 Testar Status';
    testButton.onclick = () => {
        testModalStatus();
    };
    
    // Adiciona o botão antes do botão de cancelar
    const cancelButton = buttonArea.querySelector('button[type="button"]');
    if (cancelButton) {
        buttonArea.insertBefore(testButton, cancelButton);
    } else {
        buttonArea.appendChild(testButton);
    }
}

// Função para testar manualmente
function testCurrentModalStatus() {
    const modal = document.getElementById('taskDetailsModal');
    if (!modal || !modal.classList.contains('show')) {
        console.warn('⚠️ Modal não está aberto');
        return;
    }
    
    testModalStatus();
}

// Disponibiliza globalmente
window.testCurrentModalStatus = testCurrentModalStatus;
window.testModalStatus = testModalStatus;

console.log('🔧 Script de teste de status do modal carregado');
console.log('📝 Use testCurrentModalStatus() para testar manualmente'); 