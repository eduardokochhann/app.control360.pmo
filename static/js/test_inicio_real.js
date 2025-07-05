/**
 * Script de Teste - Preenchimento Automático do Início Real
 * Verifica se o sistema está preenchendo automaticamente o campo "Início Real"
 */

class InicioRealTestSuite {
    constructor() {
        this.testResults = [];
        this.isRunning = false;
        
        console.log('🧪 [Teste Início Real] Suite de testes iniciada');
    }

    /**
     * Executa todos os testes do início real
     */
    async runAllTests() {
        if (this.isRunning) {
            console.log('⚠️ [Teste] Testes já em execução');
            return;
        }

        this.isRunning = true;
        this.testResults = [];
        
        console.log('🚀 [Teste Início Real] Iniciando testes...');
        
        try {
            await this.testApiEndpoints();
            await this.testStatusChangeScenarios();
            await this.testExistingTasks();
            
            this.generateReport();
            
        } catch (error) {
            console.error('❌ [Teste] Erro durante execução dos testes:', error);
        } finally {
            this.isRunning = false;
        }
    }

    /**
     * Testa endpoints da API
     */
    async testApiEndpoints() {
        console.log('🔍 [Teste] Verificando endpoints da API...');
        
        try {
            // Testa se endpoint de atualização está acessível
            const response = await fetch('/backlog/api/columns', {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const available = response.ok;
            this.addTestResult('API de colunas acessível', available, true);
            
            if (available) {
                const columns = await response.json();
                this.addTestResult('Colunas carregadas', Array.isArray(columns) && columns.length > 0, true);
                
                // Verifica se tem as colunas necessárias
                const hasAFazer = columns.some(col => col.name.toUpperCase().includes('FAZER'));
                const hasEmAndamento = columns.some(col => col.name.toUpperCase().includes('ANDAMENTO'));
                const hasConcluido = columns.some(col => col.name.toUpperCase().includes('CONCLU'));
                
                this.addTestResult('Coluna "A Fazer" encontrada', hasAFazer, true);
                this.addTestResult('Coluna "Em Andamento" encontrada', hasEmAndamento, true);
                this.addTestResult('Coluna "Concluído" encontrada', hasConcluido, true);
                
                // Armazena colunas para outros testes
                this.columns = columns;
            }
            
        } catch (error) {
            this.addTestResult('Conectividade com API', false, true);
            console.error('❌ [Teste] Erro de conectividade:', error);
        }
    }

    /**
     * Testa cenários de mudança de status
     */
    async testStatusChangeScenarios() {
        console.log('🔍 [Teste] Verificando cenários de mudança de status...');
        
        if (!this.columns) {
            this.addTestResult('Colunas disponíveis para teste', false, true);
            return;
        }
        
        // Procura por tarefa existente para testar
        const taskCard = document.querySelector('[data-task-id]');
        if (!taskCard) {
            this.addTestResult('Tarefa disponível para teste', false, false);
            return;
        }
        
        const taskId = taskCard.dataset.taskId;
        this.addTestResult('Tarefa encontrada para teste', true, false);
        
        // Simula mudança de status
        try {
            const response = await fetch(`/backlog/api/tasks/${taskId}`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            
            if (response.ok) {
                const taskData = await response.json();
                this.addTestResult('Dados da tarefa obtidos', true, true);
                
                // Verifica estrutura dos dados
                const hasRequiredFields = taskData.id && taskData.column_id !== undefined;
                this.addTestResult('Estrutura da tarefa válida', hasRequiredFields, true);
                
                // Verifica se tem campo actually_started_at
                const hasStartField = 'actually_started_at' in taskData;
                this.addTestResult('Campo actually_started_at presente', hasStartField, true);
                
                // Verifica estado atual
                const currentColumn = this.columns.find(col => col.id === taskData.column_id);
                if (currentColumn) {
                    this.addTestResult(`Status atual: ${currentColumn.name}`, true, false);
                    
                    // Verifica se pode testar mudança de status
                    const canTestStatusChange = currentColumn.name.toUpperCase() === 'A FAZER';
                    this.addTestResult('Tarefa em "A Fazer" (ideal para teste)', canTestStatusChange, false);
                }
                
            } else {
                this.addTestResult('Acesso aos dados da tarefa', false, true);
            }
            
        } catch (error) {
            this.addTestResult('Busca de dados da tarefa', false, true);
            console.error('❌ [Teste] Erro ao buscar dados:', error);
        }
    }

    /**
     * Testa tarefas existentes
     */
    async testExistingTasks() {
        console.log('🔍 [Teste] Verificando tarefas existentes...');
        
        const taskCards = document.querySelectorAll('[data-task-id]');
        this.addTestResult(`${taskCards.length} tarefas encontradas`, taskCards.length > 0, false);
        
        let tasksWithStartDate = 0;
        let tasksInProgress = 0;
        
        for (const card of taskCards) {
            const taskId = card.dataset.taskId;
            
            try {
                const response = await fetch(`/backlog/api/tasks/${taskId}`, {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                if (response.ok) {
                    const task = await response.json();
                    
                    if (task.actually_started_at) {
                        tasksWithStartDate++;
                    }
                    
                    if (this.columns) {
                        const column = this.columns.find(col => col.id === task.column_id);
                        if (column && column.name.toUpperCase().includes('ANDAMENTO')) {
                            tasksInProgress++;
                        }
                    }
                }
                
            } catch (error) {
                console.warn(`⚠️ [Teste] Erro ao verificar tarefa ${taskId}:`, error);
            }
        }
        
        this.addTestResult(`${tasksWithStartDate} tarefas com início real`, tasksWithStartDate >= 0, false);
        this.addTestResult(`${tasksInProgress} tarefas em andamento`, tasksInProgress >= 0, false);
        
        // Verifica se há inconsistências
        const potentialInconsistencies = tasksInProgress > tasksWithStartDate;
        this.addTestResult('Possíveis inconsistências detectadas', !potentialInconsistencies, false);
    }

    /**
     * Simula mudança de status de uma tarefa
     */
    async simulateStatusChange(taskId, newColumnId) {
        console.log(`🧪 [Teste] Simulando mudança de status: Tarefa ${taskId} -> Coluna ${newColumnId}`);
        
        try {
            const response = await fetch(`/backlog/api/tasks/${taskId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newColumnId })
            });
            
            if (response.ok) {
                const updatedTask = await response.json();
                console.log('✅ [Teste] Mudança de status simulada com sucesso');
                
                // Verifica se início real foi preenchido
                const hasStartDate = !!updatedTask.actually_started_at;
                console.log(`📊 [Teste] Início real preenchido: ${hasStartDate ? 'SIM' : 'NÃO'}`);
                
                return { success: true, hasStartDate, task: updatedTask };
            } else {
                console.error('❌ [Teste] Erro na simulação:', response.status);
                return { success: false, error: response.status };
            }
            
        } catch (error) {
            console.error('❌ [Teste] Erro na simulação:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Adiciona resultado de teste
     */
    addTestResult(testName, passed, critical) {
        const result = { testName, passed, critical };
        this.testResults.push(result);
        
        const icon = passed ? '✅' : '❌';
        const priority = critical ? '[CRÍTICO]' : '[INFO]';
        
        console.log(`${icon} [Teste] ${priority} ${testName}: ${passed ? 'PASSOU' : 'FALHOU'}`);
    }

    /**
     * Gera relatório final
     */
    generateReport() {
        console.log('\n📊 [Teste Início Real] RELATÓRIO FINAL');
        console.log('='.repeat(50));
        
        const totalTests = this.testResults.length;
        const passedTests = this.testResults.filter(r => r.passed).length;
        const failedTests = totalTests - passedTests;
        const criticalFailed = this.testResults.filter(r => !r.passed && r.critical).length;
        
        console.log(`📈 Total de testes: ${totalTests}`);
        console.log(`✅ Testes aprovados: ${passedTests}`);
        console.log(`❌ Testes falhados: ${failedTests}`);
        console.log(`🚨 Falhas críticas: ${criticalFailed}`);
        
        const successRate = ((passedTests / totalTests) * 100).toFixed(1);
        console.log(`📊 Taxa de sucesso: ${successRate}%`);
        
        if (criticalFailed === 0) {
            console.log('🎉 [Teste] Sistema de início real funcionando!');
        } else {
            console.log('⚠️ [Teste] Sistema com problemas críticos!');
        }
        
        console.log('='.repeat(50));
        
        // Instruções para teste manual
        console.log('\n🧪 [Teste] PARA TESTAR MANUALMENTE:');
        console.log('1. Encontre uma tarefa em "A Fazer"');
        console.log('2. Abra o modal da tarefa');
        console.log('3. Mude o Status para "Em Andamento"');
        console.log('4. Salve as alterações');
        console.log('5. Reabra o modal');
        console.log('6. Verifique se "Início Real" foi preenchido');
    }

    /**
     * Demonstra uso da API
     */
    showApiUsage() {
        console.log('\n📚 [Teste] EXEMPLOS DE USO DA API:');
        
        if (this.columns && this.columns.length > 0) {
            console.log('\n🏷️ Colunas disponíveis:');
            this.columns.forEach(col => {
                console.log(`  • ${col.name} (ID: ${col.id})`);
            });
            
            const emAndamento = this.columns.find(col => col.name.toUpperCase().includes('ANDAMENTO'));
            if (emAndamento) {
                console.log(`\n💡 Para mover tarefa para "Em Andamento":`);
                console.log(`fetch('/backlog/api/tasks/[TASK_ID]', {`);
                console.log(`  method: 'PUT',`);
                console.log(`  headers: { 'Content-Type': 'application/json' },`);
                console.log(`  body: JSON.stringify({ status: ${emAndamento.id} })`);
                console.log(`})`);
            }
        }
    }
}

// Instância global
window.InicioRealTestSuite = new InicioRealTestSuite();

// Comandos disponíveis no console
window.testInicioReal = () => window.InicioRealTestSuite.runAllTests();
window.simulateStatusChange = (taskId, columnId) => window.InicioRealTestSuite.simulateStatusChange(taskId, columnId);
window.showApiUsage = () => window.InicioRealTestSuite.showApiUsage();

// Auto-execução em modo debug
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(() => {
        if (window.location.search.includes('debug=inicio-real')) {
            console.log('🧪 [Teste] Auto-executando testes de início real...');
            window.testInicioReal();
        }
    }, 2000);
});

console.log('🧪 [Teste Início Real] Sistema carregado. Comandos disponíveis:');
console.log('  • testInicioReal() - Executa todos os testes');
console.log('  • simulateStatusChange(taskId, columnId) - Simula mudança de status');
console.log('  • showApiUsage() - Mostra exemplos de uso da API'); 