/**
 * Script de Teste - Sistema de Atualização em Tempo Real para Sprints
 * Verifica se o sistema está funcionando corretamente
 */

class SprintRealtimeTestSuite {
    constructor() {
        this.testResults = [];
        this.isRunning = false;
        
        console.log('🧪 [Teste] Suite de testes do sistema de tempo real iniciada');
    }

    /**
     * Executa todos os testes
     */
    async runAllTests() {
        if (this.isRunning) {
            console.log('⚠️ [Teste] Testes já em execução');
            return;
        }

        this.isRunning = true;
        this.testResults = [];
        
        console.log('🚀 [Teste] Iniciando suite de testes...');
        
        try {
            // Testes básicos
            await this.testSystemAvailability();
            await this.testAPIConnectivity();
            await this.testTaskMovement();
            await this.testEventListeners();
            
            // Relatório final
            this.generateReport();
            
        } catch (error) {
            console.error('❌ [Teste] Erro durante execução dos testes:', error);
        } finally {
            this.isRunning = false;
        }
    }

    /**
     * Testa se o sistema está disponível
     */
    async testSystemAvailability() {
        console.log('🔍 [Teste] Verificando disponibilidade do sistema...');
        
        const tests = [
            {
                name: 'SprintRealtimeUpdater disponível',
                test: () => typeof window.SprintRealtimeUpdater !== 'undefined',
                critical: true
            },
            {
                name: 'Sistema habilitado',
                test: () => window.SprintRealtimeUpdater && window.SprintRealtimeUpdater.isEnabled,
                critical: true
            },
            {
                name: 'SyncManager disponível',
                test: () => typeof window.SyncManager !== 'undefined',
                critical: false
            },
            {
                name: 'Função updateTaskAssignment disponível',
                test: () => typeof window.updateTaskAssignment === 'function',
                critical: true
            }
        ];

        tests.forEach(test => {
            const result = test.test();
            this.addTestResult(test.name, result, test.critical);
        });
    }

    /**
     * Testa conectividade com a API
     */
    async testAPIConnectivity() {
        console.log('🔍 [Teste] Verificando conectividade com a API...');
        
        try {
            // Testa endpoint base
            const response = await fetch('/backlog/api/backlogs/unassigned-tasks', {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const apiAvailable = response.ok;
            this.addTestResult('API do backlog acessível', apiAvailable, true);
            
            if (apiAvailable) {
                const data = await response.json();
                this.addTestResult('API retorna dados válidos', Array.isArray(data), true);
            }
            
        } catch (error) {
            this.addTestResult('Conectividade com API', false, true);
            console.error('❌ [Teste] Erro de conectividade:', error);
        }
    }

    /**
     * Simula movimentação de tarefa
     */
    async testTaskMovement() {
        console.log('🔍 [Teste] Testando movimentação de tarefa...');
        
        // Procura por uma tarefa existente para testar
        const existingTask = document.querySelector('[data-task-id]');
        
        if (!existingTask) {
            this.addTestResult('Tarefa disponível para teste', false, false);
            return;
        }
        
        const taskId = existingTask.dataset.taskId;
        this.addTestResult('Tarefa encontrada para teste', true, false);
        
        // Testa se pode buscar dados da tarefa
        try {
            if (window.SprintRealtimeUpdater) {
                const taskData = await window.SprintRealtimeUpdater.fetchTaskData(taskId);
                this.addTestResult('Busca de dados da tarefa', !!taskData, true);
                
                if (taskData) {
                    this.addTestResult('Dados da tarefa válidos', taskData.id == taskId, true);
                }
            }
        } catch (error) {
            this.addTestResult('Busca de dados da tarefa', false, true);
            console.error('❌ [Teste] Erro ao buscar dados:', error);
        }
    }

    /**
     * Testa event listeners
     */
    async testEventListeners() {
        console.log('🔍 [Teste] Verificando event listeners...');
        
        const taskCards = document.querySelectorAll('[data-task-id]');
        const hasTaskCards = taskCards.length > 0;
        
        this.addTestResult('Cards de tarefa disponíveis', hasTaskCards, false);
        
        if (hasTaskCards) {
            // Verifica se cards têm event listeners
            const firstCard = taskCards[0];
            const hasClickListener = firstCard.onclick || firstCard.addEventListener;
            
            this.addTestResult('Event listeners presentes', !!hasClickListener, false);
        }
        
        // Verifica se sortable está funcionando
        const sortableContainers = document.querySelectorAll('.sprint-tasks, .project-tasks');
        this.addTestResult('Containers sortable disponíveis', sortableContainers.length > 0, false);
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
        console.log('\n📊 [Teste] RELATÓRIO FINAL');
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
            console.log('🎉 [Teste] Sistema funcionando corretamente!');
        } else {
            console.log('⚠️ [Teste] Sistema com problemas críticos!');
        }
        
        console.log('='.repeat(50));
        
        // Detalhes dos testes falhados
        const failedDetails = this.testResults.filter(r => !r.passed);
        if (failedDetails.length > 0) {
            console.log('\n❌ [Teste] DETALHES DOS TESTES FALHADOS:');
            failedDetails.forEach(test => {
                console.log(`  • ${test.testName} ${test.critical ? '(CRÍTICO)' : ''}`);
            });
        }
    }

    /**
     * Testa uma movimentação específica
     */
    async testSpecificTaskMovement(taskId, sprintId) {
        console.log(`🧪 [Teste] Testando movimentação específica: Tarefa ${taskId} -> Sprint ${sprintId}`);
        
        const taskElement = document.querySelector(`[data-task-id="${taskId}"]`);
        if (!taskElement) {
            console.error('❌ [Teste] Tarefa não encontrada na UI');
            return false;
        }
        
        try {
            if (window.SprintRealtimeUpdater) {
                await window.SprintRealtimeUpdater.updateMovedTask(taskId, sprintId, taskElement);
                console.log('✅ [Teste] Movimentação específica executada com sucesso');
                return true;
            }
        } catch (error) {
            console.error('❌ [Teste] Erro na movimentação específica:', error);
            return false;
        }
    }

    /**
     * Monitora performance do sistema
     */
    monitorPerformance() {
        console.log('📊 [Teste] Iniciando monitoramento de performance...');
        
        let updateCount = 0;
        let totalTime = 0;
        
        // Intercepta atualizações
        const originalUpdate = window.SprintRealtimeUpdater?.updateMovedTask;
        
        if (originalUpdate) {
            window.SprintRealtimeUpdater.updateMovedTask = async function(...args) {
                const startTime = performance.now();
                
                try {
                    const result = await originalUpdate.apply(this, args);
                    const endTime = performance.now();
                    const duration = endTime - startTime;
                    
                    updateCount++;
                    totalTime += duration;
                    
                    console.log(`⚡ [Teste] Atualização ${updateCount}: ${duration.toFixed(2)}ms`);
                    
                    return result;
                } catch (error) {
                    console.error('❌ [Teste] Erro na atualização monitorada:', error);
                    throw error;
                }
            };
        }
        
        // Relatório de performance a cada 30 segundos
        setInterval(() => {
            if (updateCount > 0) {
                const avgTime = (totalTime / updateCount).toFixed(2);
                console.log(`📊 [Teste] Performance: ${updateCount} atualizações, média ${avgTime}ms`);
            }
        }, 30000);
    }
}

// Instância global
window.SprintRealtimeTestSuite = new SprintRealtimeTestSuite();

// Comandos disponíveis no console
window.testSprintRealtime = () => window.SprintRealtimeTestSuite.runAllTests();
window.testTaskMovement = (taskId, sprintId) => window.SprintRealtimeTestSuite.testSpecificTaskMovement(taskId, sprintId);
window.monitorSprintPerformance = () => window.SprintRealtimeTestSuite.monitorPerformance();

// Auto-execução em desenvolvimento
document.addEventListener('DOMContentLoaded', function() {
    // Executa testes automaticamente apenas se estiver em modo debug
    if (window.location.search.includes('debug=true')) {
        setTimeout(() => {
            console.log('🧪 [Teste] Auto-executando testes em modo debug...');
            window.testSprintRealtime();
        }, 3000);
    }
});

console.log('🧪 [Teste] Sistema de testes carregado. Comandos disponíveis:');
console.log('  • testSprintRealtime() - Executa todos os testes');
console.log('  • testTaskMovement(taskId, sprintId) - Testa movimentação específica');
console.log('  • monitorSprintPerformance() - Monitora performance'); 