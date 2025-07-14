/**
 * Script de Debug para Sincronização de Status
 * Para testar especificamente o problema de status não sincronizado
 */

function debugSyncStatus() {
    console.log('🔍 Iniciando debug da sincronização de status...');
    
    // Verifica se SyncManager está disponível
    if (!window.SyncManager) {
        console.error('❌ SyncManager não disponível!');
        return;
    }
    
    // Testa funções específicas
    testStatusDetection();
    testSyncStatusUpdate();
    testModalStatusMapping();
    
    console.log('✅ Debug concluído!');
}

function testStatusDetection() {
    console.log('🧪 Testando detecção de status...');
    
    // Testa diferentes cenários de tarefa
    const testTasks = [
        { 
            id: 1, 
            column_identifier: 'concluido', 
            status: 'Revisão',
            title: 'Tarefa 1 - Concluído por coluna'
        },
        { 
            id: 2, 
            column_identifier: 'revisao', 
            status: 'DONE',
            title: 'Tarefa 2 - Status DONE'
        },
        { 
            id: 3, 
            column_identifier: 'andamento', 
            status: 'Em Andamento',
            title: 'Tarefa 3 - Em andamento'
        }
    ];
    
    testTasks.forEach(task => {
        if (typeof checkIfTaskCompleted !== 'undefined') {
            const isCompleted = checkIfTaskCompleted(task);
            console.log(`📋 ${task.title}: ${isCompleted ? '✅ Concluída' : '⏳ Pendente'}`);
        } else {
            console.warn('⚠️ Função checkIfTaskCompleted não encontrada');
        }
    });
}

function testSyncStatusUpdate() {
    console.log('🧪 Testando sincronização de status...');
    
    // Simula uma atualização de status
    const mockTaskData = {
        id: 999,
        name: 'Tarefa de teste',
        status: 15, // ID da coluna "Concluído"
        column_identifier: 'concluido'
    };
    
    // Registra listener temporário para capturar evento
    window.SyncManager.on('task_updated', (data, source) => {
        console.log('📡 Evento de sincronização capturado:', {
            taskId: data.taskId,
            source: source,
            statusChanged: data.statusChanged,
            newStatus: data.newStatus
        });
    }, 'debug_test');
    
    // Emite evento de teste
    window.SyncManager.emitTaskUpdated(999, mockTaskData, 'debug_test');
    
    // Remove listener após teste
    setTimeout(() => {
        window.SyncManager.off('task_updated', 'debug_test');
    }, 1000);
}

function testModalStatusMapping() {
    console.log('🧪 Testando mapeamento de status do modal...');
    
    const testTasks = [
        { column_identifier: 'concluido', status: 'Revisão' },
        { column_identifier: 'revisao', status: 'Em Andamento' },
        { column_identifier: 'andamento', status: 'A Fazer' }
    ];
    
    testTasks.forEach(task => {
        console.log(`📋 Tarefa com coluna '${task.column_identifier}' e status '${task.status}':`);
        
        // Simula lógica do modal
        let statusValue = 'TODO';
        
        if (typeof checkIfTaskCompleted !== 'undefined' && checkIfTaskCompleted(task)) {
            statusValue = 'DONE';
        } else if (task.column_identifier) {
            const columnToStatus = {
                'concluido': 'DONE',
                'revisao': 'REVIEW',
                'andamento': 'IN_PROGRESS'
            };
            statusValue = columnToStatus[task.column_identifier] || statusValue;
        }
        
        console.log(`   → Status mapeado: ${statusValue}`);
    });
}

// Auto-executa se carregado no console
if (typeof window !== 'undefined' && window.location) {
    console.log('🔧 Script de debug carregado. Execute debugSyncStatus() para testar.');
}

// Disponibiliza globalmente
window.debugSyncStatus = debugSyncStatus; 