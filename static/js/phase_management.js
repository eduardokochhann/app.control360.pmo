// Gestão de Fases de Projetos - Central de Comando PMO
// Arquivo: static/js/phase_management.js

// Variáveis globais para gestão de fases
let currentProjectPhases = null;
let currentProjectType = null;
let currentProjectId = null;

// Inicialização quando a aba de fases é ativada
document.addEventListener('shown.bs.tab', function(e) {
    if (e.target.id === 'pills-phases-tab') {
        loadPhaseManagement();
    }
});

/**
 * Carrega as informações de gestão de fases do projeto atual
 */
function loadPhaseManagement() {
    console.log('Carregando gestão de fases...');
    
    // Obtém o ID do projeto atual
    currentProjectId = window.boardData?.projectId || getCurrentProjectId();
    
    if (!currentProjectId) {
        console.error('ID do projeto não encontrado!');
        return;
    }
    
    // Carrega tipo do projeto
    loadProjectType();
    
    // Carrega informações da fase atual
    loadCurrentPhase();
    
    // Carrega overview das fases
    loadPhasesOverview();
}

/**
 * Carrega o tipo do projeto atual
 */
function loadProjectType() {
    fetch(`/backlog/api/projects/${currentProjectId}/project-type`)
        .then(response => response.json())
        .then(data => {
            // ✅ CORREÇÃO: A API retorna dados diretamente, sem campo 'success'
            if (data && data.project_type) {
                currentProjectType = data.project_type;
                updateProjectTypeUI(data.project_type);
            } else {
                console.warn('Tipo de projeto não configurado');
                updateProjectTypeUI(null);
            }
        })
        .catch(error => {
            console.error('Erro ao carregar tipo do projeto:', error);
            updateProjectTypeUI(null);
        });
}

/**
 * Carrega informações da fase atual do projeto
 */
function loadCurrentPhase() {
    fetch(`/backlog/api/projects/${currentProjectId}/current-phase`)
        .then(response => response.json())
        .then(data => {
            // ✅ CORREÇÃO: A API retorna dados diretamente, sem campo 'success'
            if (data && data.current_phase) {
                updateCurrentPhaseUI(data);
            } else {
                updateCurrentPhaseUI(null);
            }
        })
        .catch(error => {
            console.error('Erro ao carregar fase atual:', error);
            updateCurrentPhaseUI(null);
        });
}

/**
 * Carrega overview das fases do projeto
 */
function loadPhasesOverview() {
    fetch(`/backlog/api/projects/${currentProjectId}/phases-overview`)
        .then(response => response.json())
        .then(data => {
            // ✅ CORREÇÃO: A API retorna dados diretamente, sem campo 'success'
            if (data && data.phases) {
                updatePhasesOverviewUI(data.phases);
                updatePhaseBadge(data.phases);
            } else {
                console.warn('Nenhuma fase encontrada');
                updatePhasesOverviewUI([]);
            }
        })
        .catch(error => {
            console.error('Erro ao carregar overview das fases:', error);
            updatePhasesOverviewUI([]);
        });
}

/**
 * Atualiza a UI com o tipo de projeto
 */
function updateProjectTypeUI(projectType) {
    const waterfallRadio = document.getElementById('projectTypeWaterfall');
    const agileRadio = document.getElementById('projectTypeAgile');
    
    if (projectType === 'waterfall') {
        waterfallRadio.checked = true;
    } else if (projectType === 'agile') {
        agileRadio.checked = true;
    } else {
        waterfallRadio.checked = false;
        agileRadio.checked = false;
    }
}

/**
 * Atualiza a UI com informações da fase atual
 */
function updateCurrentPhaseUI(phaseData) {
    const container = document.getElementById('statusContainer');
    if (!container) return;

    if (phaseData && phaseData.current_phase) {
        const phase = phaseData.current_phase;
        const totalPhases = phaseData.total_phases || 1;
        const startedAt = phaseData.started_at 
            ? new Date(phaseData.started_at).toLocaleDateString('pt-BR') 
            : '-';
        
        const progress = Math.round((phase.number / totalPhases) * 100);

        container.innerHTML = `
            <div class="row align-items-center">
                <div class="col-md-5">
                    <div class="fw-bold">Fase Atual:</div>
                    <div class="badge fs-6" style="background-color: ${phase.color || '#0d6efd'};">
                        <i class="bi bi-arrow-right-circle-fill"></i> ${phase.number}. ${phase.name}
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="fw-bold">Progresso Total:</div>
                    <div class="progress" style="height: 20px;">
                        <div class="progress-bar" role="progressbar" style="width: ${progress}%;" 
                             aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100">${progress}%</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="fw-bold">Iniciado em:</div>
                    <div>${startedAt}</div>
                </div>
            </div>
        `;
    } else {
        // Estado inicial ou de erro
        container.innerHTML = `
            <div class="row">
                <div class="col">
                    <span class="fw-bold">Fase Atual:</span>
                    <span class="badge bg-secondary">Não configurado</span>
                </div>
                <div class="col">
                    <span class="fw-bold">Iniciado em:</span> -
                </div>
            </div>
        `;
    }
}

/**
 * Atualiza a UI com o overview das fases
 */
function updatePhasesOverviewUI(phases) {
    const phasesContainer = document.getElementById('phasesContainer');
    
    if (!phases || phases.length === 0) {
        phasesContainer.innerHTML = `
            <div class="text-center text-muted py-4">
                <i class="bi bi-layers fs-1"></i>
                <h5 class="mt-3">Gestão de Fases</h5>
                <p class="mb-3">Configure o tipo de projeto para visualizar as fases</p>
            </div>
        `;
        return;
    }
    
    let html = '<div class="row">';
    
    phases.forEach((phase, index) => {
        const phaseClass = phase.is_current ? 'current' : 
                          phase.is_completed ? 'completed' : 'pending';
        
        const phaseNumberClass = phase.is_current ? 'current' : 
                                phase.is_completed ? 'completed' : 'pending';
        
        html += `
            <div class="col-md-6 mb-3">
                <div class="phase-card ${phaseClass}">
                    <div class="d-flex align-items-center">
                        <div class="phase-number ${phaseNumberClass} me-3">
                            ${phase.is_completed ? '<i class="bi bi-check-lg"></i>' : phase.phase_number}
                        </div>
                        <div class="flex-grow-1">
                            <h6 class="mb-1 fw-bold">${phase.phase_name}</h6>
                            <p class="mb-1 text-muted small">${phase.phase_description || 'Sem descrição'}</p>
                            <div class="d-flex align-items-center text-sm">
                                <i class="bi bi-clock me-1"></i>
                                <span class="text-muted">
                                    ${phase.started_at ? 
                                        `Iniciado em ${new Date(phase.started_at).toLocaleDateString('pt-BR')}` : 
                                        'Não iniciado'}
                                </span>
                            </div>
                        </div>
                        <div class="text-end">
                            ${phase.is_current ? 
                                '<span class="badge bg-primary">Atual</span>' : 
                                phase.is_completed ? 
                                '<span class="badge bg-success">Concluído</span>' : 
                                '<span class="badge bg-secondary">Pendente</span>'}
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    phasesContainer.innerHTML = html;
}

/**
 * Atualiza o badge da aba de fases
 */
function updatePhaseBadge(phases) {
    const phaseBadge = document.getElementById('phases-badge');
    
    if (phases && phases.length > 0) {
        const currentPhase = phases.find(p => p.is_current);
        if (currentPhase) {
            phaseBadge.textContent = currentPhase.phase_number;
            phaseBadge.style.display = 'inline';
        } else {
            phaseBadge.style.display = 'none';
        }
    } else {
        phaseBadge.style.display = 'none';
    }
}

/**
 * Salva o tipo do projeto selecionado
 */
function saveProjectType() {
    const selectedType = document.querySelector('input[name="projectType"]:checked')?.value;
    
    if (!selectedType) {
        showToast('Por favor, selecione um tipo de projeto', 'warning');
        return;
    }
    
    fetch(`/backlog/api/projects/${currentProjectId}/project-type`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ project_type: selectedType })
    })
    .then(response => response.json())
    .then(data => {
        // ✅ CORREÇÃO: A API retorna dados diretamente, sem campo 'success'
        if (data && data.project_type) {
            showToast('Tipo de projeto salvo com sucesso!', 'success');
            currentProjectType = data.project_type;
            
            // Recarrega as informações das fases
            loadCurrentPhase();
            loadPhasesOverview();
        } else {
            showToast('Erro ao salvar tipo do projeto', 'error');
        }
    })
    .catch(error => {
        console.error('Erro ao salvar tipo do projeto:', error);
        showToast('Erro ao salvar tipo do projeto', 'error');
    });
}

/**
 * Avança o projeto para a próxima fase
 */
function advancePhase() {
    if (!confirm('Tem certeza que deseja avançar para a próxima fase?')) {
        return;
    }
    
    fetch(`/backlog/api/projects/${currentProjectId}/advance-phase`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        // ✅ CORREÇÃO: A API retorna dados diretamente, sem campo 'success'
        if (data && data.message) {
            showToast(data.message, 'success');
            
            // Recarrega as informações das fases
            loadCurrentPhase();
            loadPhasesOverview();
        } else {
            showToast('Erro ao avançar fase', 'error');
        }
    })
    .catch(error => {
        console.error('Erro ao avançar fase:', error);
        showToast('Erro ao avançar fase', 'error');
    });
}

/**
 * Atualiza as informações de fases
 */
async function refreshPhaseInfo() {
    if (!currentProjectId) {
        showToast('Erro: ID do projeto não encontrado', 'error');
        return;
    }

    try {
        // ✅ CHAMA A API DE RECÁLCULO DE FASE
        const response = await fetch(`/backlog/api/projects/${currentProjectId}/recalculate-phase`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        const result = await response.json();

        if (result.success) {
            console.log('Fase recalculada:', result.message);
            showToast(`✅ ${result.message}`, 'success');
        } else {
            console.warn('Recálculo de fase:', result.error || result.message);
            showToast(result.error || result.message, 'warning');
        }
    } catch (error) {
        console.error('Erro ao recalcular fase:', error);
        showToast('Erro ao recalcular fase', 'error');
    }

    // Sempre recarrega as informações na interface
    loadPhaseManagement();
}

/**
 * Abre modal de histórico de fases
 */
function openPhaseHistoryModal() {
    showToast('Funcionalidade de histórico será implementada em breve', 'info');
}

/**
 * Obtém o ID do projeto atual
 */
function getCurrentProjectId() {
    // Tenta obter do boardData
    if (window.boardData && window.boardData.projectId) {
        return window.boardData.projectId;
    }
    
    // Tenta obter da URL
    const urlMatch = window.location.pathname.match(/\/board\/(.+)$/);
    if (urlMatch) {
        return urlMatch[1];
    }
    
    // Tenta obter de elementos da página
    const projectElement = document.querySelector('[data-project-id]');
    if (projectElement) {
        return projectElement.dataset.projectId;
    }
    
    return null;
}

/**
 * Exibe toast/notificação
 */
function showToast(message, type = 'info') {
    // Usa a função de toast existente ou cria uma simples
    if (typeof mostrarNotificacao === 'function') {
        mostrarNotificacao(message, type);
    } else {
        console.log(`[${type.toUpperCase()}] ${message}`);
        alert(message);
    }
}

console.log('📋 Phase Management JavaScript carregado'); 