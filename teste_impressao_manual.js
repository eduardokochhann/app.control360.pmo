/**
 * Teste Manual para Verificar Correção da Impressão Timeline
 * 
 * Execute este script no console do navegador na página do Status Report
 * para verificar se as correções de impressão estão funcionando.
 */

console.log('🔍 TESTE MANUAL - CORREÇÃO IMPRESSÃO TIMELINE');
console.log('==============================================');

// Verificar se a timeline existe
const timeline = document.querySelector('.phase-timeline');
if (!timeline) {
    console.log('❌ Timeline não encontrada na página');
    return;
}

console.log('✅ Timeline encontrada');

// Verificar propriedades CSS atuais
const computedStyle = window.getComputedStyle(timeline);
console.log('📊 Propriedades CSS atuais:');
console.log('   Display:', computedStyle.display);
console.log('   Flex Direction:', computedStyle.flexDirection);
console.log('   Gap:', computedStyle.gap);

// Verificar se existem fases
const fases = timeline.querySelectorAll('.phase-item');
console.log(`📋 Fases encontradas: ${fases.length}`);

// Verificar posicionamento horizontal
if (fases.length > 1) {
    const primeira = fases[0];
    const ultima = fases[fases.length - 1];
    
    const primeiraRect = primeira.getBoundingClientRect();
    const ultimaRect = ultima.getBoundingClientRect();
    
    console.log('📐 Posicionamento:');
    console.log(`   Primeira fase - Left: ${primeiraRect.left}, Right: ${primeiraRect.right}`);
    console.log(`   Última fase - Left: ${ultimaRect.left}, Right: ${ultimaRect.right}`);
    
    if (ultimaRect.left > primeiraRect.right) {
        console.log('✅ Fases posicionadas horizontalmente (lado a lado)');
    } else {
        console.log('⚠️ Fases podem estar empilhadas verticalmente');
    }
}

// Verificar regras de impressão
console.log('\n🖨️ VERIFICANDO REGRAS DE IMPRESSÃO:');

// Criar elemento de teste para simular impressão
const testDiv = document.createElement('div');
testDiv.className = 'phase-timeline-container';
testDiv.style.position = 'absolute';
testDiv.style.top = '-9999px';
testDiv.innerHTML = `
    <div class="phase-timeline">
        <div class="phase-item">Teste 1</div>
        <div class="phase-item">Teste 2</div>
        <div class="phase-item">Teste 3</div>
    </div>
`;

document.body.appendChild(testDiv);

// Verificar se as regras de impressão seriam aplicadas
const testTimeline = testDiv.querySelector('.phase-timeline');
const testStyle = window.getComputedStyle(testTimeline);

console.log('🧪 Teste de regras de impressão:');
console.log('   Display:', testStyle.display);
console.log('   Flex Direction:', testStyle.flexDirection);

// Limpar elemento de teste
document.body.removeChild(testDiv);

// Instruções para teste manual
console.log('\n📝 INSTRUÇÕES PARA TESTE MANUAL:');
console.log('1. Pressione Ctrl+P (Windows) ou Cmd+P (Mac)');
console.log('2. No preview de impressão, verifique se as fases aparecem lado a lado');
console.log('3. Confirme se as cores estão preservadas');
console.log('4. Teste com diferentes projetos (Waterfall e Agile)');

// Função para testar impressão
window.testarImpressaoAgora = function() {
    console.log('🖨️ Iniciando teste de impressão...');
    
    // Adicionar indicador visual
    const indicator = document.createElement('div');
    indicator.style.cssText = `
        position: fixed;
        top: 10px;
        right: 10px;
        background: #ff2d5f;
        color: white;
        padding: 10px 15px;
        border-radius: 5px;
        z-index: 9999;
        font-weight: bold;
        box-shadow: 0 2px 10px rgba(0,0,0,0.3);
    `;
    indicator.textContent = 'TESTE: Verifique se timeline está horizontal';
    document.body.appendChild(indicator);
    
    setTimeout(() => {
        window.print();
        setTimeout(() => {
            document.body.removeChild(indicator);
        }, 2000);
    }, 500);
};

console.log('\n🚀 Para testar a impressão agora, execute:');
console.log('   testarImpressaoAgora()');

console.log('\n✅ Teste concluído!'); 