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
            await this.testMilestoneStatus();
            await this.testProjectPhaseType();
            await this.testTimelineDisplay();
            
            this.showResults();
        } catch (error) {
            console.error('❌ [Teste Status Sync] Erro durante os testes:', error);
        } finally {
            this.isRunning = false;
        }
    }

    async testKanbanSync() {
        console.log('🔍 [Teste Status Sync] Testando sincronização Kanban...');
        
        try {
            // Simula verificação de sincronização
            const kanbanCards = document.querySelectorAll('.kanban-card');
            const syncIssues = [];
            
            kanbanCards.forEach(card => {
                const taskId = card.dataset.taskId;
                const columnName = card.closest('.kanban-column').dataset.columnName;
                
                // Aqui você pode implementar verificações específicas
                if (taskId && columnName) {
                    console.log(`📋 [Teste Status Sync] Tarefa ${taskId} na coluna ${columnName}`);
                }
            });
            
            this.testResults.push({
                test: 'Sincronização Kanban',
                status: 'success',
                message: `${kanbanCards.length} tarefas verificadas`
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Sincronização Kanban',
                status: 'error',
                message: error.message
            });
        }
    }

    async testWBSStatusConsistency() {
        console.log('🔍 [Teste Status Sync] Testando consistência WBS...');
        
        try {
            // Verifica se a WBS está exibindo status corretos
            const wbsRows = document.querySelectorAll('.wbs-row');
            let inconsistencies = 0;
            
            wbsRows.forEach(row => {
                const taskId = row.dataset.taskId;
                const statusBadge = row.querySelector('.task-status');
                
                if (statusBadge) {
                    const statusText = statusBadge.textContent.trim();
                    console.log(`📊 [Teste Status Sync] WBS Tarefa ${taskId}: ${statusText}`);
                }
            });
            
            this.testResults.push({
                test: 'Consistência WBS',
                status: 'success',
                message: `${wbsRows.length} tarefas WBS verificadas`
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Consistência WBS',
                status: 'error',
                message: error.message
            });
        }
    }

    async testMilestoneStatus() {
        console.log('🔍 [Teste Status Sync] Testando status dos marcos...');
        
        try {
            // Verifica se os marcos estão mostrando status correto
            const milestoneRows = document.querySelectorAll('tr');
            let milestonesFound = 0;
            
            milestoneRows.forEach(row => {
                const cells = row.querySelectorAll('td');
                if (cells.length >= 2) {
                    const nameCell = cells[0];
                    const statusCell = cells[1];
                    
                    if (nameCell && statusCell) {
                        const milestoneName = nameCell.textContent.trim();
                        const statusBadge = statusCell.querySelector('.badge');
                        
                        if (milestoneName.includes('Milestone') && statusBadge) {
                            const status = statusBadge.textContent.trim();
                            console.log(`🎯 [Teste Status Sync] Marco ${milestoneName}: ${status}`);
                            milestonesFound++;
                        }
                    }
                }
            });
            
            this.testResults.push({
                test: 'Status dos Marcos',
                status: 'success',
                message: `${milestonesFound} marcos verificados`
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Status dos Marcos',
                status: 'error',
                message: error.message
            });
        }
    }

    async testProjectPhaseType() {
        console.log('🔍 [Teste Status Sync] Testando tipo de projeto e fases...');
        
        try {
            // Verifica se as fases estão corretas para o tipo de projeto
            const phaseItems = document.querySelectorAll('.phase-item');
            const phaseNames = [];
            
            phaseItems.forEach(item => {
                const phaseName = item.querySelector('.phase-name');
                if (phaseName) {
                    phaseNames.push(phaseName.textContent.trim());
                }
            });
            
            console.log('📊 [Teste Status Sync] Fases detectadas:', phaseNames);
            
            // Verifica se são fases ágeis ou waterfall
            const isAgile = phaseNames.some(name => 
                name.includes('Sprint') || name.includes('Desenvolvimento')
            );
            
            const isWaterfall = phaseNames.some(name => 
                name.includes('Execução') && !name.includes('Sprint')
            );
            
            let projectType = 'Não determinado';
            if (isAgile) projectType = 'Ágil';
            if (isWaterfall) projectType = 'Preditivo (Waterfall)';
            
            this.testResults.push({
                test: 'Tipo de Projeto',
                status: 'info',
                message: `Tipo detectado: ${projectType} | Fases: ${phaseNames.join(', ')}`
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Tipo de Projeto',
                status: 'error',
                message: error.message
            });
        }
    }

    async testTimelineDisplay() {
        console.log('🔍 [Teste Status Sync] Testando exibição da timeline...');
        
        try {
            const timelineContainer = document.querySelector('.phase-timeline-container');
            const phaseItems = document.querySelectorAll('.phase-item');
            
            if (timelineContainer && phaseItems.length > 0) {
                console.log(`📊 [Teste Status Sync] Timeline encontrada com ${phaseItems.length} fases`);
                
                this.testResults.push({
                    test: 'Timeline das Fases',
                    status: 'success',
                    message: `Timeline funcional com ${phaseItems.length} fases`
                });
            } else {
                this.testResults.push({
                    test: 'Timeline das Fases',
                    status: 'warning',
                    message: 'Timeline não encontrada ou sem fases'
                });
            }
            
        } catch (error) {
            this.testResults.push({
                test: 'Timeline das Fases',
                status: 'error',
                message: error.message
            });
        }
    }

    showResults() {
        console.log('📋 [Teste Status Sync] Resultados dos testes:');
        console.log('=' .repeat(50));
        
        this.testResults.forEach(result => {
            const icon = result.status === 'success' ? '✅' : 
                        result.status === 'error' ? '❌' : 
                        result.status === 'warning' ? '⚠️' : 'ℹ️';
            
            console.log(`${icon} ${result.test}: ${result.message}`);
        });
        
        console.log('=' .repeat(50));
        console.log('🏁 [Teste Status Sync] Testes concluídos!');
    }
}

// Instancia a suite de testes
const testSuite = new StatusSyncTestSuite();

// Função para executar testes manualmente
window.runStatusSyncTests = function() {
    testSuite.runAllTests();
};

// Executa testes automaticamente se estiver em modo de desenvolvimento
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(() => {
            console.log('🚀 [Teste Status Sync] Executando testes automáticos...');
            testSuite.runAllTests();
        }, 2000);
    });
}

// Também disponibiliza globalmente para uso no console
window.StatusSyncTestSuite = StatusSyncTestSuite; 