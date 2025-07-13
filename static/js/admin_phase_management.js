/**
 * Gerenciamento de Configurações de Fases de Projetos - AdminSystem
 * Permite configurar fases padrão para projetos Waterfall e Ágil
 */

// Estado global da aplicação
let currentProjectType = null;
let currentPhases = [];
let milestoneTemplates = {};
let currentMilestones = [];
let editingPhase = null;

// Inicialização da aplicação
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Iniciando sistema de gestão de fases...');
    
    // Inicializar event listeners
    initializeEventListeners();
    
    // Carregar templates de marcos
    loadMilestoneTemplates();
    
    // Atualizar preview de cores
    updateColorPreview();
    
    console.log('✅ Sistema de gestão de fases inicializado');
});

// Inicializar event listeners
function initializeEventListeners() {
    // Event listeners para inputs de cor
    const colorInputs = ['phaseColor', 'editPhaseColor'];
    colorInputs.forEach(id => {
        const input = document.getElementById(id);
        if (input) {
            input.addEventListener('input', updateColorPreview);
        }
    });
    
    // Event listeners para inputs de marcos
    const milestoneInputs = ['milestoneInput', 'editMilestoneInput'];
    milestoneInputs.forEach(id => {
        const input = document.getElementById(id);
        if (input) {
            input.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    if (id === 'milestoneInput') {
                        addMilestone();
                    } else {
                        addEditMilestone();
                    }
                }
            });
        }
    });
    
    console.log('✅ Event listeners inicializados');
}

// Alternar tipo de projeto
function switchProjectType(type) {
    console.log(`🔄 Alternando para tipo: ${type}`);
    
    currentProjectType = type;
    
    // Atualizar seletores visuais
    document.querySelectorAll('.type-selector').forEach(selector => {
        selector.classList.remove('active');
    });
    
    const selector = document.getElementById(`${type}Selector`);
    if (selector) {
        selector.classList.add('active');
    }
    
    // Atualizar título
    const title = document.getElementById('currentTypeTitle');
    if (title) {
        title.textContent = type === 'waterfall' ? 'Fases Waterfall' : 'Fases Ágil/Sprints';
    }
    
    // Atualizar tema
    document.body.className = type === 'waterfall' ? 'waterfall-theme' : '';
    
    // Habilitar botões
    document.getElementById('addPhaseBtn').disabled = false;
    document.getElementById('templatesBtn').disabled = false;
    
    // Carregar fases do tipo selecionado
    loadPhases(type);
}

// Carregar fases
function loadPhases(type) {
    console.log(`📥 Carregando fases do tipo: ${type}`);
    
    showLoading(true);
    
    fetch(`/adminsystem/api/project-phases/configurations?project_type=${type}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            
            currentPhases = data.phases || [];
            renderPhases();
            
            console.log(`✅ ${currentPhases.length} fases carregadas`);
        })
        .catch(error => {
            console.error('❌ Erro ao carregar fases:', error);
            showError('Erro ao carregar fases: ' + error.message);
        })
        .finally(() => {
            showLoading(false);
        });
}

// Renderizar fases
function renderPhases() {
    const container = document.getElementById('phasesList');
    
    if (!currentPhases || currentPhases.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="bi bi-diagram-3"></i>
                <h5>Nenhuma fase configurada</h5>
                <p>Clique em "Nova Fase" para criar a primeira fase deste tipo</p>
            </div>
        `;
        return;
    }
    
    // Ordenar fases por número
    currentPhases.sort((a, b) => a.phase_number - b.phase_number);
    
    let html = '<div class="row">';
    
    currentPhases.forEach(phase => {
        html += `
            <div class="col-md-6 mb-3">
                <div class="card phase-card ${currentProjectType}" style="border-left-color: ${phase.phase_color}">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <div class="d-flex align-items-center">
                                <div class="phase-number ${currentProjectType}" style="background: ${phase.phase_color}">
                                    ${phase.phase_number}
                                </div>
                                <div class="ms-3">
                                    <h5 class="card-title mb-1">${phase.phase_name}</h5>
                                    <small class="text-muted">${phase.phase_description || 'Sem descrição'}</small>
                                </div>
                            </div>
                            <div class="dropdown">
                                <button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="dropdown">
                                    <i class="bi bi-three-dots-vertical"></i>
                                </button>
                                <ul class="dropdown-menu">
                                    <li><a class="dropdown-item" href="#" onclick="editPhase(${phase.id})">
                                        <i class="bi bi-pencil"></i> Editar
                                    </a></li>
                                    <li><a class="dropdown-item text-danger" href="#" onclick="deletePhase(${phase.id})">
                                        <i class="bi bi-trash"></i> Desativar
                                    </a></li>
                                </ul>
                            </div>
                        </div>
                        
                        <div class="mb-2">
                            <strong>Marcos:</strong>
                            <div class="mt-1">
                                ${phase.milestone_names && phase.milestone_names.length > 0 
                                    ? phase.milestone_names.map(name => `<span class="milestone-badge">${name}</span>`).join('')
                                    : '<span class="text-muted">Nenhum marco configurado</span>'
                                }
                            </div>
                        </div>
                        
                        <div class="d-flex justify-content-between align-items-center">
                            <small class="text-muted">
                                <i class="bi bi-calendar"></i>
                                Criado em ${new Date(phase.created_at).toLocaleDateString('pt-BR')}
                            </small>
                            <span class="badge bg-${phase.is_active ? 'success' : 'secondary'}">
                                ${phase.is_active ? 'Ativo' : 'Inativo'}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

// Mostrar modal de nova fase
function showNewPhaseModal() {
    console.log('📝 Abrindo modal de nova fase');
    
    if (!currentProjectType) {
        showError('Selecione um tipo de projeto primeiro');
        return;
    }
    
    // Limpar formulário
    document.getElementById('newPhaseForm').reset();
    document.getElementById('phaseColor').value = '#E8F5E8';
    document.getElementById('milestonesList').innerHTML = '';
    currentMilestones = [];
    
    // Sugerir próximo número de fase
    const maxPhase = currentPhases.length > 0 ? Math.max(...currentPhases.map(p => p.phase_number)) : 0;
    document.getElementById('phaseNumber').value = maxPhase + 1;
    
    // Atualizar preview de cor
    updateColorPreview();
    
    // Mostrar modal
    const modal = new bootstrap.Modal(document.getElementById('newPhaseModal'));
    modal.show();
}

// Adicionar marco
function addMilestone() {
    const input = document.getElementById('milestoneInput');
    const milestoneName = input.value.trim();
    
    if (!milestoneName) {
        return;
    }
    
    if (currentMilestones.includes(milestoneName)) {
        showError('Marco já adicionado');
        return;
    }
    
    currentMilestones.push(milestoneName);
    input.value = '';
    
    renderMilestones('milestonesList', currentMilestones);
}

// Adicionar marco na edição
function addEditMilestone() {
    const input = document.getElementById('editMilestoneInput');
    const milestoneName = input.value.trim();
    
    if (!milestoneName) {
        return;
    }
    
    if (!editingPhase.milestone_names) {
        editingPhase.milestone_names = [];
    }
    
    if (editingPhase.milestone_names.includes(milestoneName)) {
        showError('Marco já adicionado');
        return;
    }
    
    editingPhase.milestone_names.push(milestoneName);
    input.value = '';
    
    renderMilestones('editMilestonesList', editingPhase.milestone_names);
}

// Renderizar marcos
function renderMilestones(containerId, milestones) {
    const container = document.getElementById(containerId);
    
    if (!milestones || milestones.length === 0) {
        container.innerHTML = '<small class="text-muted">Nenhum marco adicionado</small>';
        return;
    }
    
    const isEdit = containerId === 'editMilestonesList';
    
    let html = '';
    milestones.forEach((milestone, index) => {
        html += `
            <span class="milestone-badge removable" onclick="removeMilestone(${index}, ${isEdit})">
                ${milestone}
                <i class="bi bi-x ms-1"></i>
            </span>
        `;
    });
    
    container.innerHTML = html;
}

// Remover marco
function removeMilestone(index, isEdit) {
    if (isEdit) {
        editingPhase.milestone_names.splice(index, 1);
        renderMilestones('editMilestonesList', editingPhase.milestone_names);
    } else {
        currentMilestones.splice(index, 1);
        renderMilestones('milestonesList', currentMilestones);
    }
}

// Salvar nova fase
function saveNewPhase() {
    console.log('💾 Salvando nova fase');
    
    const formData = {
        project_type: currentProjectType,
        phase_number: parseInt(document.getElementById('phaseNumber').value),
        phase_name: document.getElementById('phaseName').value.trim(),
        phase_description: document.getElementById('phaseDescription').value.trim(),
        phase_color: document.getElementById('phaseColor').value,
        milestone_names: currentMilestones
    };
    
    // Validações
    if (!formData.phase_name) {
        showError('Nome da fase é obrigatório');
        return;
    }
    
    if (formData.phase_number < 1) {
        showError('Número da fase deve ser maior que 0');
        return;
    }
    
    // Verificar se já existe fase com esse número
    if (currentPhases.some(p => p.phase_number === formData.phase_number)) {
        showError('Já existe uma fase com este número');
        return;
    }
    
    // Salvar via API
    fetch('/adminsystem/api/project-phases/configurations', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        
        console.log('✅ Fase criada com sucesso');
        showSuccess('Fase criada com sucesso');
        
        // Fechar modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('newPhaseModal'));
        modal.hide();
        
        // Recarregar fases
        loadPhases(currentProjectType);
    })
    .catch(error => {
        console.error('❌ Erro ao salvar fase:', error);
        showError('Erro ao salvar fase: ' + error.message);
    });
}

// Editar fase
function editPhase(phaseId) {
    console.log(`✏️ Editando fase ID: ${phaseId}`);
    
    const phase = currentPhases.find(p => p.id === phaseId);
    if (!phase) {
        showError('Fase não encontrada');
        return;
    }
    
    editingPhase = { ...phase };
    
    // Preencher formulário
    document.getElementById('editPhaseId').value = phase.id;
    document.getElementById('editPhaseNumber').value = phase.phase_number;
    document.getElementById('editPhaseName').value = phase.phase_name;
    document.getElementById('editPhaseDescription').value = phase.phase_description || '';
    document.getElementById('editPhaseColor').value = phase.phase_color;
    
    // Renderizar marcos
    renderMilestones('editMilestonesList', editingPhase.milestone_names || []);
    
    // Atualizar preview de cor
    updateColorPreview();
    
    // Mostrar modal
    const modal = new bootstrap.Modal(document.getElementById('editPhaseModal'));
    modal.show();
}

// Salvar edição de fase
function saveEditPhase() {
    console.log('💾 Salvando edição de fase');
    
    const phaseId = parseInt(document.getElementById('editPhaseId').value);
    
    const formData = {
        phase_name: document.getElementById('editPhaseName').value.trim(),
        phase_description: document.getElementById('editPhaseDescription').value.trim(),
        phase_color: document.getElementById('editPhaseColor').value,
        milestone_names: editingPhase.milestone_names || []
    };
    
    // Validações
    if (!formData.phase_name) {
        showError('Nome da fase é obrigatório');
        return;
    }
    
    // Salvar via API
    fetch(`/adminsystem/api/project-phases/configurations/${phaseId}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        
        console.log('✅ Fase atualizada com sucesso');
        showSuccess('Fase atualizada com sucesso');
        
        // Fechar modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('editPhaseModal'));
        modal.hide();
        
        // Recarregar fases
        loadPhases(currentProjectType);
    })
    .catch(error => {
        console.error('❌ Erro ao atualizar fase:', error);
        showError('Erro ao atualizar fase: ' + error.message);
    });
}

// Deletar fase
function deletePhase(phaseId) {
    console.log(`🗑️ Deletando fase ID: ${phaseId}`);
    
    const phase = currentPhases.find(p => p.id === phaseId);
    if (!phase) {
        showError('Fase não encontrada');
        return;
    }
    
    if (!confirm(`Deseja realmente desativar a fase "${phase.phase_name}"?`)) {
        return;
    }
    
    fetch(`/adminsystem/api/project-phases/configurations/${phaseId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        
        console.log('✅ Fase desativada com sucesso');
        showSuccess('Fase desativada com sucesso');
        
        // Recarregar fases
        loadPhases(currentProjectType);
    })
    .catch(error => {
        console.error('❌ Erro ao desativar fase:', error);
        showError('Erro ao desativar fase: ' + error.message);
    });
}

// Carregar templates de marcos
function loadMilestoneTemplates() {
    console.log('📋 Carregando templates de marcos');
    
    fetch('/adminsystem/api/project-phases/milestones/templates')
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            
            milestoneTemplates = data;
            console.log('✅ Templates de marcos carregados');
        })
        .catch(error => {
            console.error('❌ Erro ao carregar templates:', error);
        });
}

// Mostrar modal de templates
function showMilestoneTemplatesModal() {
    console.log('📋 Abrindo modal de templates');
    
    // Renderizar templates
    renderTemplates('waterfallTemplates', milestoneTemplates.waterfall || []);
    renderTemplates('agileTemplates', milestoneTemplates.agile || []);
    renderTemplates('customTemplates', milestoneTemplates.custom || []);
    
    // Mostrar modal
    const modal = new bootstrap.Modal(document.getElementById('milestoneTemplatesModal'));
    modal.show();
}

// Renderizar templates
function renderTemplates(containerId, templates) {
    const container = document.getElementById(containerId);
    
    if (!templates || templates.length === 0) {
        container.innerHTML = '<small class="text-muted">Nenhum template disponível</small>';
        return;
    }
    
    let html = '';
    templates.forEach(template => {
        html += `
            <div class="mb-2">
                <button class="btn btn-sm btn-outline-secondary w-100 text-start" 
                        onclick="useTemplate('${template}')">
                    <i class="bi bi-plus-circle"></i> ${template}
                </button>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

// Usar template
function useTemplate(templateName) {
    console.log(`📋 Usando template: ${templateName}`);
    
    // Adicionar à lista de marcos atual
    if (!currentMilestones.includes(templateName)) {
        currentMilestones.push(templateName);
        renderMilestones('milestonesList', currentMilestones);
    }
    
    // Fechar modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('milestoneTemplatesModal'));
    modal.hide();
}

// Carregar estatísticas
function loadStatistics() {
    console.log('📊 Carregando estatísticas');
    
    fetch('/adminsystem/api/project-phases/statistics')
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Atualizar estatísticas na interface
            document.getElementById('totalWaterfallPhases').textContent = data.total_waterfall_phases || 0;
            document.getElementById('totalAgilePhases').textContent = data.total_agile_phases || 0;
            document.getElementById('waterfallProjects').textContent = data.waterfall_projects || 0;
            document.getElementById('agileProjects').textContent = data.agile_projects || 0;
            
            // Mostrar seção de estatísticas
            document.getElementById('statisticsSection').style.display = 'block';
            
            console.log('✅ Estatísticas carregadas');
        })
        .catch(error => {
            console.error('❌ Erro ao carregar estatísticas:', error);
            showError('Erro ao carregar estatísticas: ' + error.message);
        });
}

// Mostrar modal de reset
function showResetModal() {
    console.log('🔄 Abrindo modal de reset');
    
    const modal = new bootstrap.Modal(document.getElementById('resetModal'));
    modal.show();
}

// Restaurar configurações padrão
function resetDefaults() {
    console.log('🔄 Restaurando configurações padrão');
    
    const resetType = document.querySelector('input[name="resetType"]:checked').value;
    
    if (!confirm(`Confirma a restauração das configurações padrão para ${resetType}?`)) {
        return;
    }
    
    fetch('/adminsystem/api/project-phases/reset-defaults', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ project_type: resetType })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        
        console.log('✅ Configurações restauradas com sucesso');
        showSuccess('Configurações restauradas com sucesso');
        
        // Fechar modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('resetModal'));
        modal.hide();
        
        // Recarregar fases se necessário
        if (currentProjectType && (resetType === 'all' || resetType === currentProjectType)) {
            loadPhases(currentProjectType);
        }
    })
    .catch(error => {
        console.error('❌ Erro ao restaurar configurações:', error);
        showError('Erro ao restaurar configurações: ' + error.message);
    });
}

// Atualizar preview de cor
function updateColorPreview() {
    const colorInput = document.getElementById('phaseColor');
    const colorPreview = document.getElementById('colorPreview');
    
    if (colorInput && colorPreview) {
        colorPreview.style.backgroundColor = colorInput.value;
    }
    
    const editColorInput = document.getElementById('editPhaseColor');
    const editColorPreview = document.getElementById('editColorPreview');
    
    if (editColorInput && editColorPreview) {
        editColorPreview.style.backgroundColor = editColorInput.value;
    }
}

// Mostrar loading
function showLoading(show) {
    const loading = document.getElementById('loadingIndicator');
    if (loading) {
        loading.style.display = show ? 'block' : 'none';
    }
}

// Mostrar mensagem de sucesso
function showSuccess(message) {
    console.log('✅ Sucesso:', message);
    
    // Criar toast de sucesso
    const toast = createToast('success', message);
    document.body.appendChild(toast);
    
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // Remover toast após exibição
    toast.addEventListener('hidden.bs.toast', () => {
        document.body.removeChild(toast);
    });
}

// Mostrar mensagem de erro
function showError(message) {
    console.error('❌ Erro:', message);
    
    // Criar toast de erro
    const toast = createToast('danger', message);
    document.body.appendChild(toast);
    
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // Remover toast após exibição
    toast.addEventListener('hidden.bs.toast', () => {
        document.body.removeChild(toast);
    });
}

// Criar toast
function createToast(type, message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.setAttribute('role', 'alert');
    toast.style.position = 'fixed';
    toast.style.top = '20px';
    toast.style.right = '20px';
    toast.style.zIndex = '9999';
    
    const icon = type === 'success' ? 'bi-check-circle' : 'bi-exclamation-triangle';
    const bgColor = type === 'success' ? 'bg-success' : 'bg-danger';
    
    toast.innerHTML = `
        <div class="toast-header ${bgColor} text-white">
            <i class="bi ${icon} me-2"></i>
            <strong class="me-auto">Sistema de Fases</strong>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
        </div>
        <div class="toast-body">
            ${message}
        </div>
    `;
    
    return toast;
}

// Funções globais para compatibilidade
window.switchProjectType = switchProjectType;
window.showNewPhaseModal = showNewPhaseModal;
window.showMilestoneTemplatesModal = showMilestoneTemplatesModal;
window.showResetModal = showResetModal;
window.loadStatistics = loadStatistics;
window.addMilestone = addMilestone;
window.addEditMilestone = addEditMilestone;
window.removeMilestone = removeMilestone;
window.saveNewPhase = saveNewPhase;
window.saveEditPhase = saveEditPhase;
window.editPhase = editPhase;
window.deletePhase = deletePhase;
window.useTemplate = useTemplate;
window.resetDefaults = resetDefaults;

console.log('📋 Sistema de gestão de fases carregado e pronto!'); 