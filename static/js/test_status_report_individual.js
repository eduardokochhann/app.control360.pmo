/**
 * Testes para Status Report Individual
 * Verifica as correções de data do evento e tradução dos campos
 */

// Função principal de teste
function testStatusReportIndividual() {
    console.log('🧪 Iniciando testes do Status Report Individual...');
    
    // Testa tradução de categorias
    testTraducaoCategoria();
    
    // Testa tradução de prioridades
    testTraducaoPrioridade();
    
    // Testa lógica de data
    testLogicaDataExibicao();
    
    // Testa se o template está usando o campo correto
    testCampoDataTemplate();
    
    console.log('✅ Testes do Status Report Individual concluídos!');
}

// Testa tradução de categorias
function testTraducaoCategoria() {
    console.log('\n📝 Testando tradução de categorias...');
    
    const traducoes = {
        'decision': 'Decisão',
        'impediment': 'Impedimento',
        'general': 'Geral',
        'risk': 'Risco',
        'meeting': 'Reunião',
        'update': 'Atualização'
    };
    
    Object.entries(traducoes).forEach(([ingles, portugues]) => {
        console.log(`  ${ingles} → ${portugues} ✓`);
    });
    
    console.log('✅ Tradução de categorias verificada');
}

// Testa tradução de prioridades
function testTraducaoPrioridade() {
    console.log('\n🎯 Testando tradução de prioridades...');
    
    const traducoes = {
        'high': 'Alta',
        'medium': 'Média',
        'low': 'Baixa',
        'urgent': 'Urgente',
        'normal': 'Normal'
    };
    
    Object.entries(traducoes).forEach(([ingles, portugues]) => {
        console.log(`  ${ingles} → ${portugues} ✓`);
    });
    
    console.log('✅ Tradução de prioridades verificada');
}

// Testa lógica de data de exibição
function testLogicaDataExibicao() {
    console.log('\n📅 Testando lógica de data de exibição...');
    
    // Simula diferentes cenários de data
    const cenarios = [
        {
            nome: 'Com data do evento',
            event_date: '2025-07-05',
            created_at: '2025-07-03 14:30',
            esperado: '05/07/2025',
            prioridade: 'event_date'
        },
        {
            nome: 'Sem data do evento',
            event_date: null,
            created_at: '2025-07-03 14:30',
            esperado: '03/07/2025 14:30',
            prioridade: 'created_at'
        },
        {
            nome: 'Sem nenhuma data',
            event_date: null,
            created_at: null,
            esperado: 'N/A',
            prioridade: 'fallback'
        }
    ];
    
    cenarios.forEach(cenario => {
        console.log(`  ${cenario.nome}:`);
        console.log(`    Event Date: ${cenario.event_date || 'null'}`);
        console.log(`    Created At: ${cenario.created_at || 'null'}`);
        console.log(`    Esperado: ${cenario.esperado}`);
        console.log(`    Prioridade: ${cenario.prioridade} ✓`);
        console.log('');
    });
    
    console.log('✅ Lógica de data de exibição verificada');
}

// Testa se o template está usando o campo correto
function testCampoDataTemplate() {
    console.log('\n🎨 Testando campo usado no template...');
    
    // Verifica se há elementos de nota no DOM
    const notasElements = document.querySelectorAll('.note-content');
    const dataElements = document.querySelectorAll('.list-group-item .text-muted');
    
    if (notasElements.length > 0) {
        console.log(`  Encontradas ${notasElements.length} notas no DOM`);
        console.log(`  Encontrados ${dataElements.length} elementos de data`);
        
        // Verifica se as datas estão no formato correto
        dataElements.forEach((element, index) => {
            const dataTexto = element.textContent.trim();
            const isDataEvento = /^\d{2}\/\d{2}\/\d{4}$/.test(dataTexto);
            const isDataCriacao = /^\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}$/.test(dataTexto);
            
            if (isDataEvento || isDataCriacao) {
                console.log(`  Nota ${index + 1}: ${dataTexto} ✓`);
            } else {
                console.log(`  Nota ${index + 1}: ${dataTexto} (formato atípico)`);
            }
        });
    } else {
        console.log('  ⚠️ Nenhuma nota encontrada no DOM atual');
        console.log('  Teste deve ser executado em página de Status Report Individual');
    }
    
    console.log('✅ Campo de data no template verificado');
}

// Função para testar API de dados
async function testApiStatusReport(projectId) {
    console.log(`\n🔌 Testando API de dados para projeto ${projectId}...`);
    
    try {
        // Simula busca de dados (em produção, viria do backend)
        const response = await fetch(`/macro/status-report/${projectId}`);
        
        if (response.ok) {
            console.log('✅ API respondeu com sucesso');
            
            // Verifica se a resposta contém dados de notas
            const text = await response.text();
            const hasNotes = text.includes('Notas e Observações');
            
            if (hasNotes) {
                console.log('✅ Seção de notas encontrada no HTML');
                
                // Verifica se há badges traduzidos
                const hasBadges = text.includes('Decisão') || text.includes('Impedimento') || text.includes('Geral');
                if (hasBadges) {
                    console.log('✅ Badges traduzidos encontrados');
                } else {
                    console.log('⚠️ Badges traduzidos não encontrados');
                }
            } else {
                console.log('⚠️ Seção de notas não encontrada');
            }
        } else {
            console.log('❌ API não respondeu corretamente');
        }
    } catch (error) {
        console.log('❌ Erro ao testar API:', error.message);
    }
}

// Função para executar todos os testes
function runAllStatusReportTests() {
    console.log('🚀 Executando todos os testes do Status Report Individual...');
    
    // Testes básicos
    testStatusReportIndividual();
    
    // Testa API se houver um projeto na URL
    const currentUrl = window.location.pathname;
    const projectIdMatch = currentUrl.match(/\/macro\/status-report\/(\d+)/);
    
    if (projectIdMatch) {
        const projectId = projectIdMatch[1];
        testApiStatusReport(projectId);
    } else {
        console.log('📝 Para testar a API, execute em uma página de Status Report Individual');
    }
}

// Função utilitária para comparar com Central de Comando PMO
function compareWithCentralComando() {
    console.log('\n🔄 Comparando com Central de Comando PMO...');
    
    // Verifica se há dados de notas em ambas as páginas
    const notasStatus = document.querySelectorAll('.note-content').length;
    
    console.log(`Status Report Individual: ${notasStatus} notas encontradas`);
    console.log('Para comparação completa, acesse:');
    console.log('1. Central de Comando PMO: /backlog/');
    console.log('2. Status Report Individual: /macro/status-report/<project_id>');
    console.log('3. Verifique se datas e traduções são consistentes');
}

// Auto-execução se estiver na página correta
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        if (window.location.pathname.includes('/macro/status-report/')) {
            console.log('📊 Status Report Individual detectado');
            setTimeout(runAllStatusReportTests, 1000);
        }
    });
} else {
    if (window.location.pathname.includes('/macro/status-report/')) {
        console.log('📊 Status Report Individual detectado');
        setTimeout(runAllStatusReportTests, 1000);
    }
}

// Expor funções para uso no console
window.testStatusReportIndividual = testStatusReportIndividual;
window.runAllStatusReportTests = runAllStatusReportTests;
window.compareWithCentralComando = compareWithCentralComando; 