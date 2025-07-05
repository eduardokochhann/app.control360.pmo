/**
 * Script de Teste para Sistema de Sincronização
 * Este arquivo pode ser carregado no console para testar a sincronização
 */

function testSyncSystem() {
    console.log('🧪 Iniciando testes do sistema de sincronização...');
    
    if (!window.SyncManager) {
        console.error('❌ SyncManager não encontrado!');
        return false;
    }
    
    // Teste 1: Verificar se o SyncManager está funcionando
    console.log('✅ SyncManager encontrado');
    console.log('📊 Estatísticas atuais:', window.SyncManager.getStats());
    
    // Teste 2: Registrar um listener de teste
    window.SyncManager.on('test_event', (data, source) => {
        console.log(`🔔 Evento de teste recebido de ${source}:`, data);
    }, 'test_module');
    
    // Teste 3: Emitir evento de teste
    setTimeout(() => {
        window.SyncManager.emit('test_event', { message: 'Teste de sincronização' }, 'test_source');
    }, 1000);
    
    // Teste 4: Simular atualização de tarefa
    setTimeout(() => {
        window.SyncManager.emitTaskUpdated(999, { 
            name: 'Tarefa de Teste', 
            priority: 'Alta' 
        }, 'test_module');
    }, 2000);
    
    // Teste 5: Verificar estatísticas finais
    setTimeout(() => {
        console.log('📊 Estatísticas finais:', window.SyncManager.getStats());
        console.log('✅ Testes de sincronização concluídos');
    }, 3000);
    
    return true;
}

// Função para simular cenários de uso
function simulateRealScenarios() {
    console.log('🎬 Simulando cenários reais...');
    
    // Cenário 1: Atualização de tarefa no backlog
    setTimeout(() => {
        console.log('📝 Simulando: Tarefa atualizada no backlog');
        window.SyncManager.emitTaskUpdated(123, {
            name: 'Tarefa Atualizada',
            priority: 'Média',
            specialist_name: 'João Silva'
        }, 'backlog');
    }, 1000);
    
    // Cenário 2: Tarefa movida para sprint
    setTimeout(() => {
        console.log('🔄 Simulando: Tarefa movida para sprint');
        window.SyncManager.emitTaskMoved(123, null, 5, 'sprints');
    }, 2000);
    
    // Cenário 3: Tarefa excluída
    setTimeout(() => {
        console.log('🗑️ Simulando: Tarefa excluída');
        window.SyncManager.emitTaskDeleted(456, 'backlog');
    }, 3000);
    
    // Cenário 4: Nova tarefa criada
    setTimeout(() => {
        console.log('➕ Simulando: Nova tarefa criada');
        window.SyncManager.emitTaskCreated({
            id: 789,
            name: 'Nova Tarefa',
            priority: 'Baixa'
        }, 'sprints');
    }, 4000);
}

// Função para verificar funcionalidade específica
function checkSyncFeatures() {
    console.log('🔍 Verificando funcionalidades específicas...');
    
    // Verifica localStorage
    const testKey = 'sync_test_' + Date.now();
    try {
        localStorage.setItem(testKey, 'test');
        localStorage.removeItem(testKey);
        console.log('✅ localStorage funcionando');
    } catch (error) {
        console.error('❌ Problema com localStorage:', error);
    }
    
    // Verifica eventos de storage
    const storageHandler = (e) => {
        if (e.key === testKey) {
            console.log('✅ Eventos de storage funcionando');
            window.removeEventListener('storage', storageHandler);
        }
    };
    
    window.addEventListener('storage', storageHandler);
    
    // Simula mudança de storage de outra aba
    setTimeout(() => {
        localStorage.setItem(testKey, 'test_value');
        setTimeout(() => {
            localStorage.removeItem(testKey);
        }, 100);
    }, 500);
}

// Expõe funções globalmente para uso no console
window.testSyncSystem = testSyncSystem;
window.simulateRealScenarios = simulateRealScenarios;
window.checkSyncFeatures = checkSyncFeatures;

console.log('🧪 Script de teste carregado. Use as seguintes funções no console:');
console.log('- testSyncSystem() - Testa funcionalidades básicas');
console.log('- simulateRealScenarios() - Simula cenários reais');
console.log('- checkSyncFeatures() - Verifica funcionalidades específicas'); 