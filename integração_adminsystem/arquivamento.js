/**
 * SCRIPT DE ARQUIVAMENTO MENSAL - CONTROL360
 * Integração AdminSystem ↔ Control360
 * 
 * Adicionar este script no AdminSystem ou incluir via <script src="...">
 */

// Configurações
const CONFIG = {
    // URL base do Control360 (ajustar conforme necessário)
    CONTROL360_BASE_URL: 'http://localhost:5000',
    
    // Endpoint da API de arquivamento
    API_ENDPOINT: '/macro/api/arquivar-mensal',
    
    // Timeout para requisições (30 segundos)
    REQUEST_TIMEOUT: 30000
};

// Elementos DOM
let btnArquivar, loadingDiv, statusDiv, statusTexto, modalConfirmacao, mesParaArquivar;

// Inicialização quando DOM estiver carregado
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Inicializando sistema de arquivamento Control360...');
    
    // Obter referências dos elementos
    btnArquivar = document.getElementById('btnArquivarMensal');
    loadingDiv = document.getElementById('loadingArquivamento');
    statusDiv = document.getElementById('statusArquivamento');
    statusTexto = document.getElementById('statusTexto');
    modalConfirmacao = new bootstrap.Modal(document.getElementById('modalConfirmacao'));
    mesParaArquivar = document.getElementById('mesParaArquivar');
    
    // Verificar se todos os elementos foram encontrados
    if (!btnArquivar) {
        console.error('❌ Elemento btnArquivarMensal não encontrado');
        return;
    }
    
    // Configurar event listeners
    btnArquivar.addEventListener('click', mostrarConfirmacao);
    
    // Event listener para confirmação no modal
    const btnConfirmar = document.getElementById('confirmarArquivamento');
    if (btnConfirmar) {
        btnConfirmar.addEventListener('click', executarArquivamento);
    }
    
    // Atualizar informações do mês
    atualizarInfoMes();
    
    console.log('✅ Sistema de arquivamento inicializado com sucesso');
});

/**
 * Atualiza as informações do mês que será arquivado
 */
function atualizarInfoMes() {
    const hoje = new Date();
    const mesAnterior = new Date(hoje.getFullYear(), hoje.getMonth() - 1, 1);
    
    const meses = [
        'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ];
    
    const nomeCompleto = `${meses[mesAnterior.getMonth()]}/${mesAnterior.getFullYear()}`;
    
    if (mesParaArquivar) {
        mesParaArquivar.textContent = nomeCompleto;
    }
    
    // Atualizar tooltip do botão
    if (btnArquivar) {
        btnArquivar.title = `Arquivar dados de ${nomeCompleto}`;
    }
}

/**
 * Mostra o modal de confirmação
 */
function mostrarConfirmacao() {
    console.log('📋 Solicitação de arquivamento - mostrando confirmação');
    
    // Atualizar informações no modal
    atualizarInfoMes();
    
    // Mostrar modal
    modalConfirmacao.show();
}

/**
 * Executa o arquivamento após confirmação
 */
async function executarArquivamento() {
    console.log('⚡ Iniciando processo de arquivamento...');
    
    // Fechar modal
    modalConfirmacao.hide();
    
    // Mostrar loading
    mostrarLoading(true);
    mostrarStatus('🔄 Iniciando arquivamento...', 'info');
    
    try {
        // Construir URL completa
        const url = CONFIG.CONTROL360_BASE_URL + CONFIG.API_ENDPOINT;
        console.log(`📡 Chamando API: ${url}`);
        
        // Configurar requisição
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), CONFIG.REQUEST_TIMEOUT);
        
        // Fazer requisição para a API
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                origem: 'AdminSystem',
                timestamp: new Date().toISOString()
            }),
            signal: controller.signal
        });
        
        // Limpar timeout
        clearTimeout(timeoutId);
        
        // Verificar resposta
        if (!response.ok) {
            throw new Error(`Erro HTTP: ${response.status} - ${response.statusText}`);
        }
        
        // Processar resposta
        const resultado = await response.json();
        console.log('✅ Arquivamento concluído:', resultado);
        
        // Mostrar sucesso
        mostrarStatus(
            `✅ Arquivamento concluído com sucesso! 
             Arquivo criado: ${resultado.arquivo_criado || 'N/A'}
             ${resultado.backup_criado ? `| Backup: ${resultado.backup_criado}` : ''}`,
            'success'
        );
        
        // Mostrar informações adicionais se disponíveis
        if (resultado.detalhes) {
            console.log('📊 Detalhes do arquivamento:', resultado.detalhes);
        }
        
    } catch (error) {
        console.error('❌ Erro durante arquivamento:', error);
        
        let mensagemErro = '❌ Erro durante o arquivamento: ';
        
        if (error.name === 'AbortError') {
            mensagemErro += 'Timeout - Operação demorou mais que o esperado';
        } else if (error.message.includes('Failed to fetch')) {
            mensagemErro += 'Não foi possível conectar com o Control360. Verifique se o serviço está rodando.';
        } else {
            mensagemErro += error.message;
        }
        
        mostrarStatus(mensagemErro, 'danger');
        
    } finally {
        // Esconder loading
        mostrarLoading(false);
    }
}

/**
 * Controla exibição do loading
 */
function mostrarLoading(mostrar) {
    if (loadingDiv) {
        loadingDiv.style.display = mostrar ? 'block' : 'none';
    }
    
    if (btnArquivar) {
        btnArquivar.disabled = mostrar;
        
        if (mostrar) {
            btnArquivar.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Processando...';
        } else {
            btnArquivar.innerHTML = '<i class="bi bi-calendar-plus me-2"></i>Arquivar Mês Anterior';
        }
    }
}

/**
 * Mostra status/mensagem para o usuário
 */
function mostrarStatus(mensagem, tipo = 'info') {
    if (!statusDiv || !statusTexto) return;
    
    // Mapear tipos Bootstrap
    const tiposBootstrap = {
        'info': 'alert-info',
        'success': 'alert-success', 
        'warning': 'alert-warning',
        'danger': 'alert-danger'
    };
    
    // Limpar classes anteriores
    statusDiv.className = 'alert';
    
    // Adicionar nova classe
    const classeBootstrap = tiposBootstrap[tipo] || 'alert-info';
    statusDiv.classList.add(classeBootstrap);
    
    // Definir mensagem
    statusTexto.innerHTML = mensagem;
    
    // Mostrar
    statusDiv.style.display = 'block';
    
    // Auto-esconder após 10 segundos se for sucesso
    if (tipo === 'success') {
        setTimeout(() => {
            if (statusDiv) {
                statusDiv.style.display = 'none';
            }
        }, 10000);
    }
    
    console.log(`📢 Status exibido (${tipo}): ${mensagem.replace(/<[^>]*>/g, '')}`);
}

/**
 * Função de teste (opcional - remover em produção)
 */
function testarConexaoControl360() {
    console.log('🧪 Testando conexão com Control360...');
    
    fetch(CONFIG.CONTROL360_BASE_URL + '/macro/dashboard', {
        method: 'GET',
        mode: 'no-cors' // Para contornar CORS em testes
    })
    .then(() => {
        console.log('✅ Control360 está acessível');
        mostrarStatus('✅ Conexão com Control360 OK', 'success');
    })
    .catch(error => {
        console.warn('⚠️ Não foi possível verificar conexão:', error);
        mostrarStatus('⚠️ Não foi possível verificar conexão com Control360', 'warning');
    });
}

// Exportar funções para uso global (opcional)
window.ArquivamentoControl360 = {
    executar: mostrarConfirmacao,
    testarConexao: testarConexaoControl360,
    config: CONFIG
}; 