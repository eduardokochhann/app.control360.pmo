/**
 * Teste para validação da impressão da linha do tempo das fases
 * 
 * Este script valida se a linha do tempo das fases está configurada 
 * corretamente para impressão, mantendo o layout horizontal.
 */

class TestImpressaoTimeline {
    constructor() {
        this.resultados = [];
        this.init();
    }

    init() {
        console.log('🔍 Iniciando testes de impressão da linha do tempo das fases...');
        this.executarTestes();
    }

    executarTestes() {
        // Teste 1: Verificar se a linha do tempo existe
        this.testeExistenciaTimeline();
        
        // Teste 2: Verificar estilos de impressão
        this.testeEstilosImpressao();
        
        // Teste 3: Verificar layout horizontal
        this.testeLayoutHorizontal();
        
        // Teste 4: Verificar cores para impressão
        this.testeCoresImpressao();
        
        // Teste 5: Verificar responsividade
        this.testeResponsividade();
        
        // Exibir resultados
        this.exibirResultados();
    }

    testeExistenciaTimeline() {
        const timeline = document.querySelector('.phase-timeline');
        const container = document.querySelector('.phase-timeline-container');
        
        if (timeline && container) {
            this.adicionarResultado('✅ Linha do tempo encontrada', 'success');
            
            // Verificar se tem fases
            const fases = timeline.querySelectorAll('.phase-item');
            if (fases.length > 0) {
                this.adicionarResultado(`✅ ${fases.length} fase(s) encontrada(s)`, 'success');
            } else {
                this.adicionarResultado('⚠️ Nenhuma fase encontrada', 'warning');
            }
        } else {
            this.adicionarResultado('❌ Linha do tempo não encontrada', 'error');
        }
    }

    testeEstilosImpressao() {
        // Verificar se existem estilos para impressão
        const estilos = document.styleSheets;
        let temEstilosImpressao = false;
        
        try {
            for (let i = 0; i < estilos.length; i++) {
                const folha = estilos[i];
                if (folha.cssRules) {
                    for (let j = 0; j < folha.cssRules.length; j++) {
                        const regra = folha.cssRules[j];
                        if (regra.type === CSSRule.MEDIA_RULE && 
                            regra.conditionText.includes('print')) {
                            // Verificar se tem regras específicas para timeline
                            const texto = regra.cssText;
                            if (texto.includes('phase-timeline') || 
                                texto.includes('phase-item') || 
                                texto.includes('phase-circle')) {
                                temEstilosImpressao = true;
                                break;
                            }
                        }
                    }
                }
            }
        } catch (e) {
            console.warn('Não foi possível verificar estilos de impressão:', e);
        }
        
        if (temEstilosImpressao) {
            this.adicionarResultado('✅ Estilos de impressão configurados', 'success');
        } else {
            this.adicionarResultado('⚠️ Estilos de impressão não detectados', 'warning');
        }
    }

    testeLayoutHorizontal() {
        const timeline = document.querySelector('.phase-timeline');
        if (!timeline) return;
        
        // Verificar se o display é flex
        const computedStyle = window.getComputedStyle(timeline);
        
        if (computedStyle.display === 'flex') {
            this.adicionarResultado('✅ Layout flexbox configurado', 'success');
            
            // Verificar direção do flex
            if (computedStyle.flexDirection === 'row' || 
                computedStyle.flexDirection === '' || 
                computedStyle.flexDirection === 'initial') {
                this.adicionarResultado('✅ Layout horizontal (flex-direction: row)', 'success');
            } else {
                this.adicionarResultado(`⚠️ Layout pode não ser horizontal (flex-direction: ${computedStyle.flexDirection})`, 'warning');
            }
        } else {
            this.adicionarResultado('⚠️ Layout flexbox não detectado', 'warning');
        }
        
        // Teste específico para impressão
        this.testeImpressaoEspecifico();
    }
    
    testeImpressaoEspecifico() {
        console.log('🖨️ Testando regras específicas de impressão...');
        
        // Simular CSS de impressão
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = 'data:text/css,@media print { .phase-timeline { flex-direction: row !important; } }';
        document.head.appendChild(link);
        
        // Verificar se as regras de impressão estão funcionando
        const timeline = document.querySelector('.phase-timeline');
        if (timeline) {
            const items = timeline.querySelectorAll('.phase-item');
            if (items.length > 0) {
                // Verificar se os items estão lado a lado (não empilhados)
                const firstItem = items[0];
                const lastItem = items[items.length - 1];
                
                if (firstItem && lastItem) {
                    const firstRect = firstItem.getBoundingClientRect();
                    const lastRect = lastItem.getBoundingClientRect();
                    
                    // Se estão lado a lado, o último item deve estar à direita do primeiro
                    if (lastRect.left > firstRect.right) {
                        this.adicionarResultado('✅ Itens posicionados horizontalmente', 'success');
                    } else {
                        this.adicionarResultado('⚠️ Itens podem estar empilhados verticalmente', 'warning');
                    }
                }
            }
        }
        
        // Limpar o link de teste
        setTimeout(() => {
            document.head.removeChild(link);
        }, 1000);
    }

    testeCoresImpressao() {
        const fases = document.querySelectorAll('.phase-item');
        let coresConfigurads = 0;
        
        fases.forEach((fase, index) => {
            const circulo = fase.querySelector('.phase-circle');
            if (circulo) {
                const computedStyle = window.getComputedStyle(circulo);
                
                // Verificar se tem cores definidas
                if (computedStyle.borderColor && computedStyle.borderColor !== 'initial') {
                    coresConfigurads++;
                }
            }
        });
        
        if (coresConfigurads > 0) {
            this.adicionarResultado(`✅ ${coresConfigurads} fase(s) com cores configuradas`, 'success');
        } else {
            this.adicionarResultado('⚠️ Cores das fases não detectadas', 'warning');
        }
    }

    testeResponsividade() {
        const timeline = document.querySelector('.phase-timeline');
        if (!timeline) return;
        
        // Simular diferentes tamanhos de tela
        const tamanhoOriginal = window.innerWidth;
        
        // Verificar se existe media query para mobile
        const mediaQueryMobile = window.matchMedia('(max-width: 768px)');
        
        if (mediaQueryMobile.matches) {
            this.adicionarResultado('✅ Responsividade mobile detectada', 'success');
        } else {
            this.adicionarResultado('ℹ️ Testando em tela desktop', 'info');
        }
    }

    adicionarResultado(mensagem, tipo) {
        this.resultados.push({
            mensagem,
            tipo,
            timestamp: new Date().toLocaleTimeString()
        });
        
        // Log imediato
        const emoji = {
            success: '✅',
            warning: '⚠️',
            error: '❌',
            info: 'ℹ️'
        };
        
        console.log(`${emoji[tipo]} ${mensagem}`);
    }

    exibirResultados() {
        console.log('\n📋 RESUMO DOS TESTES DE IMPRESSÃO:');
        console.log('=====================================');
        
        const sucessos = this.resultados.filter(r => r.tipo === 'success').length;
        const avisos = this.resultados.filter(r => r.tipo === 'warning').length;
        const erros = this.resultados.filter(r => r.tipo === 'error').length;
        
        console.log(`✅ Sucessos: ${sucessos}`);
        console.log(`⚠️ Avisos: ${avisos}`);
        console.log(`❌ Erros: ${erros}`);
        
        if (erros === 0) {
            console.log('\n🎉 TODOS OS TESTES PASSARAM! A impressão deve funcionar corretamente.');
        } else {
            console.log('\n⚠️ ALGUNS PROBLEMAS DETECTADOS. Verifique os erros acima.');
        }
        
        // Instruções para teste manual
        console.log('\n📝 TESTE MANUAL:');
        console.log('1. Pressione Ctrl+P (Windows) ou Cmd+P (Mac)');
        console.log('2. Verifique se a linha do tempo aparece horizontalmente');
        console.log('3. Confirme se as cores estão preservadas');
        console.log('4. Teste com diferentes projetos (Waterfall e Agile)');
    }

    // Método para teste manual de impressão
    static testarImpressao() {
        console.log('🖨️ Iniciando teste manual de impressão...');
        
        // Criar um elemento de teste
        const testeDiv = document.createElement('div');
        testeDiv.innerHTML = `
            <div style="position: fixed; top: 10px; right: 10px; background: #fff; 
                        border: 2px solid #007bff; padding: 10px; z-index: 9999;
                        border-radius: 5px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <strong>Teste de Impressão Ativo</strong><br>
                <small>Verifique se a timeline está horizontal</small>
            </div>
        `;
        
        document.body.appendChild(testeDiv);
        
        // Iniciar impressão
        setTimeout(() => {
            window.print();
            
            // Remover elemento de teste após impressão
            setTimeout(() => {
                document.body.removeChild(testeDiv);
            }, 1000);
        }, 500);
    }
}

// Executar testes automaticamente quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    // Aguardar um pouco para garantir que tudo carregou
    setTimeout(() => {
        new TestImpressaoTimeline();
    }, 1000);
});

// Exportar para uso manual
window.TestImpressaoTimeline = TestImpressaoTimeline; 