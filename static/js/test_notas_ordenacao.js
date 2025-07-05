/**
 * Script de Teste - Ordenação de Notas por Data do Evento
 * Verifica se as notas estão sendo ordenadas corretamente na Central de Comando PMO
 */

class NotasOrdenacaoTestSuite {
    constructor() {
        this.testResults = [];
        this.isRunning = false;
        
        console.log('📅 [Teste Ordenação Notas] Suite de testes iniciada');
    }

    /**
     * Executa todos os testes de ordenação de notas
     */
    async runAllTests() {
        if (this.isRunning) {
            console.log('⚠️ [Teste] Testes já em execução');
            return;
        }

        this.isRunning = true;
        this.testResults = [];
        
        console.log('🚀 [Teste Ordenação Notas] Iniciando testes...');
        
        try {
            await this.testApiEndpoints();
            await this.testNotesOrder();
            await this.testNotesWithEventDate();
            await this.testNotesWithoutEventDate();
            
            this.generateReport();
            
        } catch (error) {
            console.error('❌ [Teste] Erro durante execução dos testes:', error);
        } finally {
            this.isRunning = false;
        }
    }

    /**
     * Testa endpoints da API de notas
     */
    async testApiEndpoints() {
        console.log('🔍 [Teste] Verificando endpoints de notas...');
        
        // Verifica se está na página correta
        const isOnBacklogPage = window.location.pathname.includes('/board/');
        this.addTestResult('Página de backlog detectada', isOnBacklogPage, false);
        
        if (!isOnBacklogPage) {
            this.addTestResult('Página apropriada para teste', false, true);
            return;
        }
        
        // Busca backlog ID atual
        const backlogId = this.getCurrentBacklogId();
        this.addTestResult('Backlog ID encontrado', backlogId !== null, true);
        
        if (backlogId) {
            try {
                // Testa API de notas
                const response = await fetch(`/backlog/api/backlogs/${backlogId}/notes`);
                const available = response.ok;
                this.addTestResult('API de notas acessível', available, true);
                
                if (available) {
                    const notes = await response.json();
                    this.addTestResult(`${notes.length} notas carregadas`, Array.isArray(notes), true);
                    
                    // Armazena notas para outros testes
                    this.notes = notes;
                    
                    // Verifica estrutura das notas
                    if (notes.length > 0) {
                        const firstNote = notes[0];
                        const hasEventDate = 'event_date' in firstNote;
                        const hasCreatedAt = 'created_at' in firstNote;
                        
                        this.addTestResult('Campo event_date presente', hasEventDate, true);
                        this.addTestResult('Campo created_at presente', hasCreatedAt, true);
                    }
                }
                
            } catch (error) {
                this.addTestResult('Conectividade com API de notas', false, true);
                console.error('❌ [Teste] Erro de conectividade:', error);
            }
        }
    }

    /**
     * Testa ordenação geral das notas
     */
    async testNotesOrder() {
        console.log('🔍 [Teste] Verificando ordenação das notas...');
        
        if (!this.notes || this.notes.length === 0) {
            this.addTestResult('Notas disponíveis para teste de ordenação', false, false);
            return;
        }
        
        const notesWithEventDate = this.notes.filter(note => note.event_date);
        const notesWithoutEventDate = this.notes.filter(note => !note.event_date);
        
        this.addTestResult(`${notesWithEventDate.length} notas com data do evento`, notesWithEventDate.length >= 0, false);
        this.addTestResult(`${notesWithoutEventDate.length} notas sem data do evento`, notesWithoutEventDate.length >= 0, false);
        
        // Verifica se notas com data do evento estão ordenadas corretamente
        if (notesWithEventDate.length > 1) {
            let correctOrder = true;
            for (let i = 0; i < notesWithEventDate.length - 1; i++) {
                const currentDate = new Date(notesWithEventDate[i].event_date);
                const nextDate = new Date(notesWithEventDate[i + 1].event_date);
                
                if (currentDate < nextDate) {
                    correctOrder = false;
                    console.log(`❌ [Teste] Ordem incorreta encontrada: ${notesWithEventDate[i].event_date} < ${notesWithEventDate[i + 1].event_date}`);
                    break;
                }
            }
            this.addTestResult('Notas com data do evento ordenadas corretamente', correctOrder, true);
        }
        
        // Verifica se notas sem data do evento estão no final
        const lastNotesAreWithoutEventDate = this.notes.slice(-notesWithoutEventDate.length).every(note => !note.event_date);
        if (notesWithoutEventDate.length > 0) {
            this.addTestResult('Notas sem data do evento estão no final', lastNotesAreWithoutEventDate, true);
        }
    }

    /**
     * Testa especificamente notas com data do evento
     */
    async testNotesWithEventDate() {
        console.log('🔍 [Teste] Verificando notas com data do evento...');
        
        if (!this.notes) return;
        
        const notesWithEventDate = this.notes.filter(note => note.event_date);
        
        if (notesWithEventDate.length === 0) {
            this.addTestResult('Notas com data do evento para testar', false, false);
            return;
        }
        
        // Cria mapa de datas para verificar ordenação
        const eventDates = notesWithEventDate.map(note => note.event_date);
        const sortedDates = [...eventDates].sort((a, b) => new Date(b) - new Date(a));
        
        const isCorrectlySorted = JSON.stringify(eventDates) === JSON.stringify(sortedDates);
        this.addTestResult('Datas do evento em ordem decrescente', isCorrectlySorted, true);
        
        // Log das datas para visualização
        console.log('📅 [Teste] Ordem das datas do evento:');
        eventDates.forEach((date, index) => {
            console.log(`  ${index + 1}. ${date}`);
        });
        
        // Verifica se há datas duplicadas e como são tratadas
        const duplicateDates = eventDates.filter((date, index, arr) => arr.indexOf(date) !== index);
        if (duplicateDates.length > 0) {
            this.addTestResult('Datas duplicadas detectadas (critério de desempate)', true, false);
            console.log('📊 [Teste] Datas duplicadas encontradas:', [...new Set(duplicateDates)]);
        }
    }

    /**
     * Testa especificamente notas sem data do evento
     */
    async testNotesWithoutEventDate() {
        console.log('🔍 [Teste] Verificando notas sem data do evento...');
        
        if (!this.notes) return;
        
        const notesWithoutEventDate = this.notes.filter(note => !note.event_date);
        
        if (notesWithoutEventDate.length === 0) {
            this.addTestResult('Notas sem data do evento para testar', false, false);
            return;
        }
        
        // Verifica se estão ordenadas por created_at
        let correctCreatedAtOrder = true;
        for (let i = 0; i < notesWithoutEventDate.length - 1; i++) {
            const currentCreated = new Date(notesWithoutEventDate[i].created_at);
            const nextCreated = new Date(notesWithoutEventDate[i + 1].created_at);
            
            if (currentCreated < nextCreated) {
                correctCreatedAtOrder = false;
                break;
            }
        }
        
        this.addTestResult('Notas sem data do evento ordenadas por created_at', correctCreatedAtOrder, true);
        
        // Log das datas de criação para visualização
        console.log('🕐 [Teste] Ordem das datas de criação (notas sem evento):');
        notesWithoutEventDate.forEach((note, index) => {
            console.log(`  ${index + 1}. ${note.created_at}`);
        });
    }

    /**
     * Obtém o ID do backlog atual da página
     */
    getCurrentBacklogId() {
        // Tenta extrair o backlog ID da URL ou variáveis globais
        if (window.currentBacklogId) {
            return window.currentBacklogId;
        }
        
        // Tenta extrair da URL
        const pathMatch = window.location.pathname.match(/\/board\/(.+)/);
        if (pathMatch) {
            // Pode ser um project_id, precisa converter para backlog_id
            return null; // Para este teste, retorna null se não encontrar diretamente
        }
        
        return null;
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
        console.log('\n📊 [Teste Ordenação Notas] RELATÓRIO FINAL');
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
            console.log('🎉 [Teste] Ordenação de notas funcionando corretamente!');
        } else {
            console.log('⚠️ [Teste] Problemas críticos detectados na ordenação!');
        }
        
        console.log('='.repeat(50));
        
        // Instruções para teste manual
        console.log('\n🧪 [Teste] PARA TESTAR MANUALMENTE:');
        console.log('1. Acesse a Central de Comando PMO');
        console.log('2. Vá para a aba "Notas"');
        console.log('3. Verifique se as datas dos eventos estão em ordem decrescente');
        console.log('4. Crie uma nota com data anterior - deve aparecer depois');
        console.log('5. Crie uma nota sem data - deve aparecer no final');
    }

    /**
     * Simula criação de nota para teste
     */
    async simulateNoteCreation(eventDate, content) {
        const backlogId = this.getCurrentBacklogId();
        if (!backlogId) {
            console.error('❌ [Teste] Backlog ID não encontrado para simulação');
            return false;
        }
        
        try {
            const response = await fetch('/backlog/api/notes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    content: content || `Nota de teste criada em ${new Date().toLocaleString()}`,
                    backlog_id: backlogId,
                    event_date: eventDate,
                    category: 'general',
                    priority: 'medium'
                })
            });
            
            if (response.ok) {
                console.log('✅ [Teste] Nota criada com sucesso para teste');
                return true;
            } else {
                console.error('❌ [Teste] Erro ao criar nota:', response.status);
                return false;
            }
            
        } catch (error) {
            console.error('❌ [Teste] Erro na criação de nota:', error);
            return false;
        }
    }
}

// Instância global
window.NotasOrdenacaoTestSuite = new NotasOrdenacaoTestSuite();

// Comandos disponíveis no console
window.testNotasOrdenacao = () => window.NotasOrdenacaoTestSuite.runAllTests();
window.simulateNoteCreation = (eventDate, content) => window.NotasOrdenacaoTestSuite.simulateNoteCreation(eventDate, content);

// Auto-execução em modo debug
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(() => {
        if (window.location.search.includes('debug=notas-ordenacao')) {
            console.log('📅 [Teste] Auto-executando testes de ordenação de notas...');
            window.testNotasOrdenacao();
        }
    }, 3000);
});

console.log('📅 [Teste Ordenação Notas] Sistema carregado. Comandos disponíveis:');
console.log('  • testNotasOrdenacao() - Executa todos os testes');
console.log('  • simulateNoteCreation("2023-06-27", "Texto da nota") - Cria nota para teste'); 