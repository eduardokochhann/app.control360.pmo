/**
 * Script de Teste - Sincronização de Status entre Kanban e WBS
 * Verifica se as correções implementadas estão funcionando adequadamente
 */

class StatusSyncTestSuite {
    constructor() {
        this.testResults = [];
        this.isRunning = false;
        
        console.log('🔄 [Teste Status Sync] Suite de testes iniciada');
    }

    async runAllTests() {
        if (this.isRunning) {
            console.log('⚠️ [Teste Status Sync] Testes já estão rodando...');
            return;
        }

        this.isRunning = true;
        this.testResults = [];
        
        console.log('🚀 [Teste Status Sync] Iniciando testes de sincronização...');

        try {
            await this.testKanbanSync();
            await this.testWBSStatusConsistency();
            await this.testStatusMappingService();
            await this.testColumnStatusMapping();
            
            this.printTestResults();
        } catch (error) {
            console.error('❌ [Teste Status Sync] Erro durante os testes:', error);
        } finally {
            this.isRunning = false;
        }
    }

    async testKanbanSync() {
        console.log('🔍 [Teste] Verificando sincronização do Kanban...');
        
        // Simula uma mudança de coluna no Kanban
        const testTaskId = await this.getFirstAvailableTask();
        if (!testTaskId) {
            this.addTestResult('Tarefa disponível para teste', false, true);
            return;
        }

        try {
            // Busca estado inicial da tarefa
            const initialTask = await this.fetchTaskData(testTaskId);
            const initialColumn = initialTask.column_name;
            const initialStatus = initialTask.status;
            
            console.log(`📋 [Teste] Tarefa ${testTaskId}: Coluna='${initialColumn}', Status='${initialStatus}'`);
            
            // Simula movimento para uma coluna diferente
            const targetColumn = this.getAlternativeColumn(initialColumn);
            if (!targetColumn) {
                this.addTestResult('Coluna alternativa encontrada para teste', false, false);
                return;
            }

            // Simula movimento via API
            await this.simulateTaskMove(testTaskId, targetColumn.id);
            
            // Espera um pouco para processamento
            await this.sleep(1000);
            
            // Verifica se a sincronização funcionou
            const updatedTask = await this.fetchTaskData(testTaskId);
            const syncWorked = updatedTask.column_name === targetColumn.name && 
                              updatedTask.status !== initialStatus;
            
            this.addTestResult(
                `Sincronização Kanban->Status (${initialColumn} → ${targetColumn.name})`,
                syncWorked,
                true
            );

            // Restaura estado original
            await this.simulateTaskMove(testTaskId, initialTask.column_id);
            
        } catch (error) {
            console.error('❌ [Teste] Erro no teste Kanban:', error);
            this.addTestResult('Teste de sincronização Kanban', false, true);
        }
    }

    async testWBSStatusConsistency() {
        console.log('🔍 [Teste] Verificando consistência de status na WBS...');
        
        try {
            // Busca dados da WBS
            const projectId = this.getCurrentProjectId();
            if (!projectId) {
                this.addTestResult('ID do projeto encontrado', false, true);
                return;
            }

            const response = await fetch(`/backlog/api/projects/${projectId}/tasks`);
            if (!response.ok) {
                throw new Error('Erro ao buscar tarefas para WBS');
            }

            const wbsTasks = await response.json();
            
            // Verifica se há inconsistências
            let consistentTasks = 0;
            let inconsistentTasks = 0;
            
            for (const task of wbsTasks) {
                // Busca dados detalhados da tarefa
                const detailedTask = await this.fetchTaskData(task.id);
                
                if (detailedTask.status_consistent === false) {
                    inconsistentTasks++;
                    console.log(`⚠️ [Teste] Tarefa ${task.id} tem inconsistência: coluna='${detailedTask.column_name}', status='${detailedTask.status}'`);
                } else {
                    consistentTasks++;
                }
            }
            
            const totalTasks = wbsTasks.length;
            const consistencyRate = totalTasks > 0 ? (consistentTasks / totalTasks) * 100 : 0;
            
            this.addTestResult(
                `Taxa de consistência WBS (${consistentTasks}/${totalTasks})`,
                consistencyRate >= 95, // 95% ou mais deve estar consistente
                true
            );
            
            console.log(`📊 [Teste] Consistência: ${consistencyRate.toFixed(1)}% (${consistentTasks}/${totalTasks})`);
            
        } catch (error) {
            console.error('❌ [Teste] Erro no teste WBS:', error);
            this.addTestResult('Teste de consistência WBS', false, true);
        }
    }

    async testStatusMappingService() {
        console.log('🔍 [Teste] Verificando ColumnStatusService...');
        
        // Testa mapeamentos conhecidos
        const testMappings = [
            { column: 'A Fazer', expectedStatus: 'A Fazer' },
            { column: 'Em Andamento', expectedStatus: 'Em Andamento' },
            { column: 'Revisão', expectedStatus: 'Revisão' },
            { column: 'Concluído', expectedStatus: 'Concluído' }
        ];

        let mappingsWorking = 0;
        
        for (const mapping of testMappings) {
            try {
                // Busca uma tarefa nesta coluna
                const task = await this.findTaskInColumn(mapping.column);
                if (task && task.status === mapping.expectedStatus) {
                    mappingsWorking++;
                }
            } catch (error) {
                console.log(`⚠️ [Teste] Erro ao testar mapeamento ${mapping.column}:`, error);
            }
        }

        this.addTestResult(
            `Mapeamentos ColumnStatusService (${mappingsWorking}/${testMappings.length})`,
            mappingsWorking >= testMappings.length * 0.75, // 75% deve funcionar
            true
        );
    }

    async testColumnStatusMapping() {
        console.log('🔍 [Teste] Verificando mapeamento coluna<->status...');
        
        try {
            // Busca todas as colunas disponíveis
            const response = await fetch('/backlog/api/columns');
            if (!response.ok) {
                throw new Error('Erro ao buscar colunas');
            }

            const columns = await response.json();
            let mappedColumns = 0;
            
            for (const column of columns) {
                // Verifica se consegue mapear o nome da coluna
                const knownMappings = ['fazer', 'andamento', 'revisão', 'revisao', 'concluído', 'concluido'];
                const columnLower = column.name.toLowerCase();
                
                if (knownMappings.some(mapping => columnLower.includes(mapping))) {
                    mappedColumns++;
                }
            }
            
            const mappingRate = columns.length > 0 ? (mappedColumns / columns.length) * 100 : 0;
            
            this.addTestResult(
                `Taxa de mapeamento de colunas (${mappedColumns}/${columns.length})`,
                mappingRate >= 80, // 80% das colunas devem ser mapeáveis
                true
            );
            
            console.log(`📊 [Teste] Mapeamento: ${mappingRate.toFixed(1)}% (${mappedColumns}/${columns.length})`);
            
        } catch (error) {
            console.error('❌ [Teste] Erro no teste de mapeamento:', error);
            this.addTestResult('Teste de mapeamento de colunas', false, true);
        }
    }

    // Métodos auxiliares
    async getFirstAvailableTask() {
        try {
            const backlogId = window.boardData?.backlogId;
            if (!backlogId) return null;

            const response = await fetch(`/backlog/api/tasks?backlog_id=${backlogId}`);
            if (!response.ok) return null;

            const tasks = await response.json();
            return tasks.length > 0 ? tasks[0].id : null;
        } catch (error) {
            console.error('Erro ao buscar tarefa:', error);
            return null;
        }
    }

    async fetchTaskData(taskId) {
        const response = await fetch(`/backlog/api/tasks/${taskId}`);
        if (!response.ok) {
            throw new Error(`Erro ao buscar tarefa ${taskId}`);
        }
        return await response.json();
    }

    getAlternativeColumn(currentColumn) {
        const columns = window.boardData?.columns || [];
        return columns.find(col => col.name !== currentColumn);
    }

    async simulateTaskMove(taskId, newColumnId) {
        const response = await fetch(`/backlog/api/tasks/${taskId}/move`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                column_id: newColumnId,
                position: 0
            })
        });
        
        if (!response.ok) {
            throw new Error(`Erro ao mover tarefa ${taskId}`);
        }
        
        return await response.json();
    }

    getCurrentProjectId() {
        return window.projectId || window.boardData?.projectId;
    }

    async findTaskInColumn(columnName) {
        try {
            const backlogId = window.boardData?.backlogId;
            if (!backlogId) return null;

            const response = await fetch(`/backlog/api/tasks?backlog_id=${backlogId}`);
            if (!response.ok) return null;

            const tasks = await response.json();
            return tasks.find(task => task.column_name === columnName);
        } catch (error) {
            return null;
        }
    }

    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    addTestResult(description, passed, critical = false) {
        const result = {
            description,
            passed,
            critical,
            timestamp: new Date().toISOString()
        };
        
        this.testResults.push(result);
        
        const icon = passed ? '✅' : '❌';
        const criticalText = critical ? ' [CRÍTICO]' : '';
        console.log(`${icon} [Teste] ${description}${criticalText}`);
    }

    printTestResults() {
        console.log('\n📋 [Teste Status Sync] RESUMO DOS RESULTADOS:');
        console.log('='.repeat(60));
        
        const totalTests = this.testResults.length;
        const passedTests = this.testResults.filter(r => r.passed).length;
        const criticalFailed = this.testResults.filter(r => !r.passed && r.critical).length;
        
        this.testResults.forEach(result => {
            const icon = result.passed ? '✅' : '❌';
            const criticalText = result.critical ? ' [CRÍTICO]' : '';
            console.log(`${icon} ${result.description}${criticalText}`);
        });
        
        console.log('='.repeat(60));
        console.log(`📊 Taxa de sucesso: ${passedTests}/${totalTests} (${((passedTests/totalTests)*100).toFixed(1)}%)`);
        
        if (criticalFailed > 0) {
            console.log(`🚨 ATENÇÃO: ${criticalFailed} teste(s) crítico(s) falharam!`);
        } else {
            console.log('🎉 Todos os testes críticos passaram!');
        }
        
        return {
            total: totalTests,
            passed: passedTests,
            failed: totalTests - passedTests,
            criticalFailed: criticalFailed,
            successRate: (passedTests / totalTests) * 100
        };
    }
}

// Função global para executar os testes
window.testStatusSync = async function() {
    const testSuite = new StatusSyncTestSuite();
    return await testSuite.runAllTests();
};

// Auto-execução se chamado via URL com parâmetro debug
if (window.location.search.includes('debug=status-sync')) {
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(() => {
            console.log('🔧 [Auto Debug] Executando testes de status sync...');
            window.testStatusSync();
        }, 2000);
    });
}

console.log('🔧 [Teste Status Sync] Script carregado. Use testStatusSync() para executar os testes.'); 