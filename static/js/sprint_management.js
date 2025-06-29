/**
 * Sprint Management JavaScript
 * Gerenciamento de Sprints - Funcionalidades principais
 */

// Variáveis globais
let editingSprintId = null;
let sortableInstances = [];
let popoverInstances = {};

// Variáveis globais para filtros
let activeFilters = {
    project: null,
    specialist: null
};

let allProjects = new Map(); // Map usando project_id como chave
let allSpecialists = new Set();

// Elementos DOM
const sprintBoard = document.getElementById('sprintBoard');
const sprintModalElement = document.getElementById('sprintModal');
const sprintModal = new bootstrap.Modal(sprintModalElement);
const sprintForm = document.getElementById('sprintForm');
const sprintModalLabel = document.getElementById('sprintModalLabel');
const formMethodInput = document.getElementById('formMethod');
const modalDeleteBtn = document.getElementById('modalDeleteBtn');

// URLs da API
const apiSprintsBaseUrl = '/sprints/api/sprints';
const apiBacklogTasksUrl = '/backlog/api/backlogs/unassigned-tasks';

// Inicialização
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Inicializando Sprint Management...');
    
    // Inicializa controles de visibilidade primeiro
    initializeColumnVisibility();
    
    // Inicializa sistema de filtros
    initializeFilters();
    
    // Carrega dados iniciais
    Promise.all([
        loadSprints(),
        loadBacklogTasks(),
        loadGenericTasks()
    ]).then(() => {
        console.log('✅ Dados iniciais carregados');
        initializeSortable();
        setupEventListeners();
        setupSearch();
        
        // Atualiza filtros após carregar dados
        updateFilterLists();
        applyFilters();
        
        // ✅ NOVA FUNCIONALIDADE: Verifica e aplica filtro automático por projeto
        setTimeout(checkAndApplyAutoFilter, 1000);
        
    }).catch(error => {
        console.error('❌ Erro ao carregar dados iniciais:', error);
        showToast('Erro ao carregar dados iniciais', 'error');
    });
});

// Funções utilitárias
function showModalLoading(isLoading) {
    const overlay = sprintForm.querySelector('.loading-overlay');
    const submitButton = sprintForm.querySelector('button[type="submit"]');
    const cancelButton = sprintForm.querySelector('button[data-bs-dismiss="modal"]');
    
    if (overlay) overlay.style.display = isLoading ? 'flex' : 'none';
    if (submitButton) submitButton.disabled = isLoading;
    if (cancelButton) cancelButton.disabled = isLoading;
}

function formatDate(isoDateString) {
    if (!isoDateString) return 'Data não definida';
    
    try {
        const dateStr = isoDateString.includes('T') ? isoDateString : isoDateString + 'T00:00:00';
        const date = new Date(dateStr);
        
        if (isNaN(date.getTime())) return 'Data inválida';
        
        const day = String(date.getDate()).padStart(2, '0');
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const year = date.getFullYear();
        
        return `${day}/${month}/${year}`;
    } catch (error) {
        console.error('Erro ao formatar data:', error);
        return 'Data inválida';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(message, type = 'info') {
    // Implementação básica de toast
    console.log(`[${type.toUpperCase()}] ${message}`);
    
    // Verifica se existe uma função de toast global diferente desta
    if (typeof window.globalShowToast === 'function') {
        window.globalShowToast(message, type);
    } else if (typeof window.bootstrap !== 'undefined') {
        // Usa Bootstrap Toast se disponível
        createBootstrapToast(message, type);
    } else {
        // Fallback para alert apenas em caso de erro
        if (type === 'error') {
            alert(`Erro: ${message}`);
        }
    }
}

function createBootstrapToast(message, type) {
    // Cria um toast usando Bootstrap se disponível
    const toastContainer = document.getElementById('toast-container') || createToastContainer();
    
    const toastId = 'toast-' + Date.now();
    const bgClass = type === 'error' ? 'bg-danger' : type === 'success' ? 'bg-success' : 'bg-info';
    
    const toastHtml = `
        <div id="${toastId}" class="toast ${bgClass} text-white" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="toast-body">
                ${escapeHtml(message)}
            </div>
        </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    
    const toastElement = document.getElementById(toastId);
    if (toastElement && window.bootstrap) {
        const toast = new window.bootstrap.Toast(toastElement, { delay: 3000 });
        toast.show();
        
        // Remove o toast após ser ocultado
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '9999';
    document.body.appendChild(container);
    return container;
}

// Funções de carregamento de dados
async function loadSprints() {
    try {
        console.log('🔄 Carregando sprints...');
        const response = await fetch('/sprints/api/sprints');
        
        if (!response.ok) {
            throw new Error(`Erro ${response.status}: ${response.statusText}`);
        }

        const sprints = await response.json();
        console.log(`✅ ${sprints.length} sprints carregadas`);
        
        // Armazena os dados das sprints globalmente para uso em cálculos
        window.sprintsData = sprints;

        renderSprints(sprints);
        initializeSortable();
        initializePopovers();
        
        // Atualiza filtros mantendo estado atual
        updateFilterLists();
        applyFilters();
        
        // ✅ NOVA LINHA: Atualiza botões de análise
        updateAnalysisButtons();
        
    } catch (error) {
        console.error('❌ Erro ao carregar sprints:', error);
        renderSprintError(`Erro ao carregar sprints: ${error.message}`);
        
        // ✅ NOVA LINHA: Atualiza botões mesmo em caso de erro
        updateAnalysisButtons();
    }
}

function renderSprintError(errorMessage) {
    if (!sprintBoard) return;
    
    sprintBoard.innerHTML = `
        <div class="col-12 text-center p-4">
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i>
                Erro ao carregar sprints: ${errorMessage}
            </div>
        </div>
    `;
}

async function loadBacklogTasks() {
    try {
        console.log('📋 Carregando tarefas do backlog...');
        const backlogList = document.getElementById('backlogList');
        if (!backlogList) return;
        
        backlogList.innerHTML = '<div class="text-center p-3"><div class="spinner-border spinner-border-sm"></div> Carregando...</div>';
        
        const response = await fetch(apiBacklogTasksUrl);
        if (!response.ok) throw new Error(`Erro ${response.status}`);
        
        const backlogs = await response.json();
        console.log(`✅ ${backlogs.length} projetos de backlog carregados`);
        
        renderBacklogProjects(backlogs);
        
        // Atualiza filtros para incluir novos dados do backlog
        updateFilterLists();
        applyFilters();
        
    } catch (error) {
        console.error('❌ Erro ao carregar backlog:', error);
        const backlogList = document.getElementById('backlogList');
        if (backlogList) {
            backlogList.innerHTML = `<div class="alert alert-danger">Erro ao carregar: ${error.message}</div>`;
        }
    }
}

async function loadGenericTasks() {
    try {
        console.log('📋 Carregando tarefas genéricas...');
        const response = await fetch('/sprints/api/generic-tasks');
        if (!response.ok) throw new Error(`Erro ${response.status}`);
        
        const tasks = await response.json();
        console.log(`✅ ${tasks.length} tarefas genéricas carregadas`);
        
        renderGenericTasks(tasks);
        
    } catch (error) {
        console.error('❌ Erro ao carregar tarefas genéricas:', error);
        const genericTasksList = document.getElementById('genericTasksList');
        if (genericTasksList) {
            genericTasksList.innerHTML = `<div class="alert alert-danger">Erro: ${error.message}</div>`;
        }
    }
}

// Funções de renderização
function renderSprints(sprints) {
    if (!sprintBoard) return;
    
    sprintBoard.innerHTML = '';
    
    if (!sprints || sprints.length === 0) {
        sprintBoard.innerHTML = `
            <div class="col-12 text-center p-4">
                <div class="alert alert-info">
                    <i class="bi bi-info-circle"></i>
                    Nenhuma sprint encontrada. Clique em "Nova Sprint" para começar.
                </div>
            </div>
        `;
        return;
    }
    
    sprints.forEach(sprint => {
        const sprintCard = createSprintCard(sprint);
        sprintBoard.appendChild(sprintCard);
    });
}

function createSprintCard(sprint) {
    const sprintCard = document.createElement('div');
    sprintCard.className = 'sprint-card';
    sprintCard.dataset.sprintId = sprint.id;
    
    // Calcula totais
    let totalSprintHours = 0;
    let hoursBySpecialist = {};
    
    if (sprint.tasks) {
        sprint.tasks.forEach(task => {
            const hours = parseFloat(task.estimated_effort || task.estimated_hours || 0);
            totalSprintHours += hours;
            
            const specialist = task.specialist_name || 'Não Atribuído';
            hoursBySpecialist[specialist] = (hoursBySpecialist[specialist] || 0) + hours;
        });
    }
    
    // Calcula capacidade baseada na duração da sprint
    const sprintCapacity = calculateSprintCapacity(sprint);
    
    // Gera conteúdo do popover
    let popoverContent = Object.entries(hoursBySpecialist)
        .map(([name, allocatedHours]) => {
            const remainingHours = Math.max(0, sprintCapacity - allocatedHours);
            const utilizationPercent = (allocatedHours / sprintCapacity) * 100;
            
            let alertBadge = '';
            if (utilizationPercent > 100) {
                alertBadge = '<span class="badge bg-danger ms-2">⚠️ Sobrecarga</span>';
            } else if (utilizationPercent > 80) {
                alertBadge = '<span class="badge bg-warning ms-2">⚠️ Limite</span>';
            } else {
                alertBadge = '<span class="badge bg-success ms-2">✅ OK</span>';
            }
            
            return `
                <div class="mb-1">
                    <strong>${escapeHtml(name)}</strong><br>
                    <small>Consumo: ${allocatedHours.toFixed(1)}h | Saldo: ${remainingHours.toFixed(1)}h</small>
                    ${alertBadge}
                </div>
            `;
        })
        .join('');
    
    if (!popoverContent) {
        popoverContent = '<small class="text-muted">Nenhum especialista alocado</small>';
    }
    
    // Renderiza o card
    sprintCard.innerHTML = `
        <div class="sprint-card-header criticality-${(sprint.criticality || 'normal').toLowerCase()}">
            <div class="sprint-header-top">
                <div class="sprint-title-area">
                    <h6 class="sprint-card-title">${escapeHtml(sprint.name || 'Sprint sem nome')}</h6>
                    <div class="sprint-meta">
                        <span class="sprint-badge">
                            <i class="bi bi-list-task"></i>
                            ${sprint.tasks ? sprint.tasks.length : 0} tarefas
                        </span>
                        <span class="sprint-badge sprint-total-hours">
                            <i class="bi bi-clock"></i>
                            ${totalSprintHours.toFixed(1)}h
                        </span>
                        ${Object.keys(hoursBySpecialist).length > 0 ? `
                            <button class="btn btn-sm btn-outline-secondary specialist-hours-popover" 
                                    data-bs-toggle="popover" 
                                    data-bs-placement="bottom" 
                                    data-bs-html="true"
                                    data-bs-content="${popoverContent.replace(/"/g, '&quot;')}"
                                    data-bs-title="Especialistas">
                                <i class="bi bi-people"></i>
                            </button>
                        ` : ''}
                    </div>
                </div>
                <div class="sprint-card-actions">
                    <a href="/sprints/report/${sprint.id}" class="btn btn-sm btn-outline-info" title="Relatório da Sprint">
                        <i class="bi bi-file-text"></i>
                    </a>
                    <button class="btn btn-sm btn-outline-primary edit-btn" data-id="${sprint.id}">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-warning archive-btn" data-id="${sprint.id}" data-name="${escapeHtml(sprint.name || '')}" title="Arquivar Sprint">
                        <i class="bi bi-archive"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger delete-btn" data-id="${sprint.id}" data-name="${escapeHtml(sprint.name || '')}">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </div>
            <div class="sprint-header-bottom">
                <div class="sprint-dates">
                    <i class="bi bi-calendar-range"></i>
                    ${formatDate(sprint.start_date)} - ${formatDate(sprint.end_date)}
                </div>
                ${sprint.goal ? `<p class="sprint-goal">${escapeHtml(sprint.goal)}</p>` : ''}
            </div>
        </div>
        <div class="sprint-card-body">
            <div class="sprint-tasks" data-sprint-id="${sprint.id}">
                ${sprint.tasks ? sprint.tasks.map(task => renderSprintTask(task)).join('') : ''}
            </div>
        </div>
    `;
    
    return sprintCard;
}

function renderSprintTask(task) {
    const projectPart = task.project_id || 'PROJ';
    const columnPart = (task.column_identifier || 'UNK').substring(0, 3).toUpperCase();
    // Verifica se a tarefa está concluída
    const isCompleted = task.column_identifier === 'concluido' || 
                       task.status === 'Concluído' || 
                       task.status === 'DONE';
    const fullTaskId = `${projectPart}-${columnPart}-${task.id}`;
    
    // Determina o tipo de origem da tarefa
    const isGenericTask = !task.project_id || !task.backlog_id;
    const originType = isGenericTask ? 'generic' : 'backlog';
    const returnTitle = isGenericTask ? 'Retornar para Tarefas Genéricas' : 'Retornar para Backlog do Projeto';
    const returnIcon = isGenericTask ? 'bi-gear' : 'bi-kanban';
    
    return `
        <div class="backlog-task-card sprint-task-card" 
             data-task-id="${task.id}"
             data-estimated-hours="${task.estimated_effort || 0}"
             data-specialist-name="${escapeHtml(task.specialist_name || '')}"
             data-project-id="${task.project_id || ''}"
             data-project-name="${escapeHtml(task.project_name || '')}"
             data-backlog-id="${task.backlog_id || ''}"
             data-origin-type="${originType}"
             onclick="openTaskDetailsModal(this, ${JSON.stringify(task).replace(/"/g, '&quot;')})"
             style="cursor: pointer; position: relative;">
            
            <!-- Botões de ação da tarefa -->
            <div class="task-action-buttons">
                <!-- Botão de clonagem -->
                <button class="btn btn-sm btn-outline-info task-clone-btn" 
                        onclick="event.stopPropagation(); cloneTask(${task.id})" 
                        title="Clonar tarefa para o backlog">
                    <i class="bi bi-copy"></i>
                </button>
                
                <!-- Botão de retorno -->
                <button class="btn btn-sm btn-outline-secondary task-return-btn" 
                        onclick="event.stopPropagation(); returnTaskToOrigin(${task.id}, '${originType}')" 
                        title="${returnTitle}">
                    <i class="bi ${returnIcon}"></i>
                </button>
            </div>
            
            <div class="task-header">
                <div class="task-id-badge">${escapeHtml(fullTaskId)}</div>
                <div class="d-flex align-items-center gap-1">
                    <span class="task-priority-badge ${getPriorityClass(task.priority)}">${escapeHtml(task.priority || 'Média')}</span>
                    ${isCompleted ? '<span class="badge bg-success text-white" title="Tarefa Concluída"><i class="bi bi-check-circle-fill me-1"></i>Concluído</span>' : ''}
                </div>
            </div>
            <div class="task-content">
                <div class="task-title">${escapeHtml(task.title || 'Sem título')}</div>
                ${task.project_name ? `<div class="task-project">📁 ${escapeHtml(task.project_name)}</div>` : ''}
                ${task.specialist_name ? `<div class="task-specialist">👤 ${escapeHtml(task.specialist_name)}</div>` : ''}
                ${task.estimated_effort ? `<div class="task-hours">⏱️ ${task.estimated_effort}h</div>` : ''}
            </div>
            ${isCompleted ? '<div class="task-completed-overlay"><i class="bi bi-check-circle-fill"></i></div>' : ''}
        </div>
    `;
}

function renderBacklogProjects(backlogs) {
    const backlogList = document.getElementById('backlogList');
    if (!backlogList) return;
    
    if (!backlogs || backlogs.length === 0) {
        backlogList.innerHTML = '<div class="alert alert-info">Nenhuma tarefa disponível no backlog.</div>';
        return;
    }
    
    backlogList.innerHTML = backlogs.map(backlog => renderBacklogProject(backlog)).join('');
}

function renderBacklogProject(backlog) {
    const projectBoardUrl = `/backlog/board/${backlog.project_id}`;
    let displayName = backlog.project_name || 'Sem Nome';
    
    // Trunca nomes muito longos
    if (displayName.length > 50) {
        const palavras = displayName.split(' ');
        if (palavras.length > 1) {
            displayName = palavras.slice(0, 3).join(' ') + '...';
        } else {
            displayName = displayName.substring(0, 47) + '...';
        }
    }
    
    // Indicador de visibilidade
    const visibilityBadge = backlog.available_for_sprint !== false ? 
        '<span class="badge bg-success ms-2" title="Visível em Sprints"><i class="bi bi-eye"></i></span>' :
        '<span class="badge bg-secondary ms-2" title="Oculto em Sprints"><i class="bi bi-eye-slash"></i></span>';
    
    return `
        <div class="project-group mb-3">
            <div class="project-header" onclick="toggleProjectTasks(this)">
                <div class="d-flex justify-content-between align-items-center">
                    <div class="project-info">
                        <strong>${escapeHtml(displayName)}</strong>
                        ${visibilityBadge}
                        <small class="text-muted d-block">${backlog.tasks ? backlog.tasks.length : 0} tarefas</small>
                    </div>
                    <div class="d-flex align-items-center gap-2">
                        <a href="${projectBoardUrl}" class="btn btn-sm btn-outline-primary" title="Abrir Quadro">
                            <i class="bi bi-kanban"></i>
                        </a>
                        <i class="bi bi-chevron-down"></i>
                    </div>
                </div>
            </div>
            <div class="project-tasks" style="display: none;">
                ${backlog.tasks ? backlog.tasks.map(task => renderBacklogTask(task)).join('') : ''}
            </div>
        </div>
    `;
}

function renderBacklogTask(task) {
    const projectPart = task.project_id || 'PROJ';
    const columnPart = (task.column_identifier || 'UNK').substring(0, 3).toUpperCase();
    const isCompleted = task.column_identifier === 'concluido';
    const fullTaskId = `${projectPart}-${columnPart}-${task.id}`;
    
    return `
        <div class="backlog-task-card" 
             data-task-id="${task.id}"
             data-estimated-hours="${task.estimated_effort || 0}"
             data-specialist-name="${escapeHtml(task.specialist_name || '')}"
             data-project-id="${task.project_id || ''}"
             data-project-name="${escapeHtml(task.project_name || '')}"
             data-backlog-id="${task.backlog_id || ''}">
            <div class="task-header">
                <div class="task-id-badge">${escapeHtml(fullTaskId)}</div>
                <span class="task-priority-badge ${getPriorityClass(task.priority)}">${escapeHtml(task.priority || 'Média')}</span>
            </div>
            <div class="task-content">
                <div class="task-title">${escapeHtml(task.title || 'Sem título')}</div>
                ${task.specialist_name ? `<div class="task-specialist">${escapeHtml(task.specialist_name)}</div>` : ''}
                ${task.estimated_effort ? `<div class="task-hours">${task.estimated_effort}h</div>` : ''}
            </div>
            ${isCompleted ? '<div class="task-completed-overlay"><i class="bi bi-check-circle-fill"></i></div>' : ''}
        </div>
    `;
}

function renderGenericTasks(tasks) {
    const genericTasksList = document.getElementById('genericTasksList');
    if (!genericTasksList) return;
    
    if (!tasks || tasks.length === 0) {
        genericTasksList.innerHTML = '<div class="alert alert-info">Nenhuma tarefa genérica encontrada.</div>';
        return;
    }
    
    genericTasksList.innerHTML = tasks.map(task => `
        <div class="backlog-task-card generic-task" 
             data-task-id="${task.id}"
             data-estimated-hours="${task.estimated_effort || 0}"
             data-specialist-name="${escapeHtml(task.specialist_name || '')}"
             data-project-id=""
             data-project-name="Tarefa Genérica"
             onclick="openGenericTaskModal(${JSON.stringify(task).replace(/"/g, '&quot;')})">
            <div class="task-header">
                <div class="task-id-badge">GEN-${task.id}</div>
                <span class="task-priority-badge ${getPriorityClass(task.priority)}">${escapeHtml(task.priority || 'Média')}</span>
            </div>
            <div class="task-content">
                <div class="task-title">${escapeHtml(task.title || 'Sem título')}</div>
                ${task.specialist_name ? `<div class="task-specialist">${escapeHtml(task.specialist_name)}</div>` : ''}
                ${task.estimated_effort ? `<div class="task-hours">${task.estimated_effort}h</div>` : ''}
            </div>
        </div>
    `).join('');
}

function getPriorityClass(priority) {
    const priorityLower = (priority || '').toLowerCase();
    if (priorityLower === 'alta') return 'text-bg-danger';
    if (priorityLower === 'baixa') return 'text-bg-success';
    return 'text-bg-primary'; // Média
}

// Funções de interação
function setupEventListeners() {
    // Event listeners para formulários e botões
    if (sprintForm) {
        sprintForm.addEventListener('submit', handleSprintFormSubmit);
    }
    
    // Event listeners para botões de ação das sprints
    if (sprintBoard) {
        sprintBoard.addEventListener('click', handleSprintActions);
    }
    
    // Event listeners para tarefas genéricas
    const addGenericTaskBtn = document.getElementById('addGenericTaskBtn');
    if (addGenericTaskBtn) {
        addGenericTaskBtn.addEventListener('click', () => openGenericTaskModal());
    }
    
    // Handler para formulário de tarefa genérica
    const genericTaskForm = document.getElementById('genericTaskForm');
    if (genericTaskForm) {
        genericTaskForm.addEventListener('submit', handleGenericTaskFormSubmit);
    }
    
    // Handler para formulário de detalhes da tarefa
    const taskDetailsForm = document.getElementById('taskDetailsForm');
    if (taskDetailsForm) {
        taskDetailsForm.addEventListener('submit', handleTaskDetailsFormSubmit);
    }
    
    // Handler para botão de excluir tarefa
    const taskDeleteBtn = document.getElementById('taskDeleteBtn');
    if (taskDeleteBtn) {
        taskDeleteBtn.addEventListener('click', handleTaskDelete);
    }
    
    // Handler para botão de excluir tarefa genérica
    const genericTaskDeleteBtn = document.getElementById('genericTaskDeleteBtn');
    if (genericTaskDeleteBtn) {
        genericTaskDeleteBtn.addEventListener('click', handleGenericTaskDelete);
    }
    
    // Inicializar popovers após renderização
    initializePopovers();
}

function setupSearch() {
    setupSearchInput('backlogSearch', document.getElementById('backlogList'), '.project-group');
    setupSearchInput('genericTasksSearch', document.getElementById('genericTasksList'), '.backlog-task-card');
}

function setupSearchInput(inputId, container, itemSelector) {
    const searchInput = document.getElementById(inputId);
    if (!searchInput || !container) return;
    
    searchInput.addEventListener('input', function(e) {
        const searchTerm = e.target.value.toLowerCase();
        const items = container.querySelectorAll(itemSelector);
        
        items.forEach(item => {
            const text = item.textContent.toLowerCase();
            item.style.display = text.includes(searchTerm) ? '' : 'none';
        });
    });
}

// Funções de drag and drop
function initializeSortable() {
    console.log('🔄 Inicializando Sortable...');
    
    // Destroi instâncias existentes
    sortableInstances.forEach(instance => {
        if (instance && instance.destroy) {
            instance.destroy();
        }
    });
    sortableInstances = [];
    
    // Inicializa para todas as listas de tarefas
    const taskLists = document.querySelectorAll('.project-tasks, #genericTasksList, .sprint-tasks');
    
    taskLists.forEach(list => {
        const instance = new Sortable(list, {
            group: 'shared',
            animation: 150,
            ghostClass: 'sortable-ghost',
            chosenClass: 'sortable-chosen',
            dragClass: 'sortable-drag',
            onEnd: handleSortableEnd
        });
        sortableInstances.push(instance);
    });
    
    console.log(`✅ ${sortableInstances.length} instâncias Sortable criadas`);
}

function handleSortableEnd(evt) {
    const item = evt.item;
    const taskId = item.dataset.taskId;
    const fromList = evt.from;
    const toList = evt.to;
    const newIndex = evt.newIndex;
    
    console.log(`🔄 Tarefa ${taskId} movida de ${fromList.className} para ${toList.className}`);
    
    // Determina o tipo de movimento
    const targetSprintId = toList.dataset.sprintId || null;
    
    // Atualiza a tarefa no backend
    updateTaskAssignment(taskId, targetSprintId, newIndex);
    
    // Atualiza displays de horas
    updateSprintHoursDisplay(toList);
    if (fromList !== toList) {
        updateSprintHoursDisplay(fromList);
    }
}

async function updateTaskAssignment(taskId, sprintId, position) {
    try {
        const url = sprintId 
            ? `/backlog/api/tasks/${taskId}/assign`
            : `/sprints/api/sprints/tasks/${taskId}/move-to-backlog`;
        
        const data = sprintId 
            ? { sprint_id: sprintId, position: position }
            : {};
        
        const response = await fetch(url, {
            method: sprintId ? 'PUT' : 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            throw new Error(`Erro ${response.status}`);
        }
        
        console.log(`✅ Tarefa ${taskId} atualizada`);
        
    } catch (error) {
        console.error('❌ Erro ao atualizar tarefa:', error);
        showToast('Erro ao mover tarefa', 'error');
        // Recarrega para reverter mudança visual
        loadSprints();
    }
}

function updateSprintHoursDisplay(listElement) {
    const sprintCard = listElement.closest('.sprint-card');
    if (!sprintCard) return;
    
    const tasks = listElement.querySelectorAll('.backlog-task-card');
    let totalHours = 0;
    let hoursBySpecialist = {};
    
    tasks.forEach(task => {
        const hours = parseFloat(task.dataset.estimatedHours) || 0;
        totalHours += hours;
        
        // Calcula horas por especialista
        const specialist = task.dataset.specialistName;
        if (specialist && specialist.trim()) {
            hoursBySpecialist[specialist] = (hoursBySpecialist[specialist] || 0) + hours;
        }
    });
    
    // Atualiza o total de horas
    const hoursSpan = sprintCard.querySelector('.sprint-total-hours');
    if (hoursSpan) {
        hoursSpan.innerHTML = `<i class="bi bi-clock"></i> ${totalHours.toFixed(1)}h`;
    }
    
    // Atualiza o popover dos especialistas
    updateSpecialistPopover(sprintCard, hoursBySpecialist);
}

// Funções de modal
function handleSprintFormSubmit(event) {
    event.preventDefault();
    
    const formData = new FormData(sprintForm);
    const sprintData = {
        name: formData.get('name'),
        start_date: formData.get('start_date'),
        end_date: formData.get('end_date'),
        goal: formData.get('goal'),
        criticality: formData.get('criticality')
    };
    
    if (editingSprintId) {
        updateSprint(editingSprintId, sprintData);
    } else {
        createSprint(sprintData);
    }
}

async function createSprint(sprintData) {
    try {
        showModalLoading(true);
        
        const response = await fetch(apiSprintsBaseUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(sprintData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || `Erro ${response.status}`);
        }
        
        sprintModal.hide();
        showToast('Sprint criada com sucesso!', 'success');
        loadSprints();
        
    } catch (error) {
        console.error('❌ Erro ao criar sprint:', error);
        showToast(`Erro ao criar sprint: ${error.message}`, 'error');
    } finally {
        showModalLoading(false);
    }
}

async function updateSprint(sprintId, sprintData) {
    try {
        showModalLoading(true);
        
        const response = await fetch(`${apiSprintsBaseUrl}/${sprintId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(sprintData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || `Erro ${response.status}`);
        }
        
        sprintModal.hide();
        showToast('Sprint atualizada com sucesso!', 'success');
        loadSprints();
        
    } catch (error) {
        console.error('❌ Erro ao atualizar sprint:', error);
        showToast(`Erro ao atualizar sprint: ${error.message}`, 'error');
    } finally {
        showModalLoading(false);
    }
}

function handleSprintActions(event) {
    const editButton = event.target.closest('.edit-btn');
    const archiveButton = event.target.closest('.archive-btn');
    const deleteButton = event.target.closest('.delete-btn');
    
    if (editButton) {
        const sprintId = editButton.dataset.id;
        openEditModal(sprintId);
    } else if (archiveButton) {
        const sprintId = archiveButton.dataset.id;
        const sprintName = archiveButton.dataset.name;
        archiveSprint(sprintId, sprintName);
    } else if (deleteButton) {
        const sprintId = deleteButton.dataset.id;
        const sprintName = deleteButton.dataset.name;
        deleteSprint(sprintId, sprintName);
    }
}

async function openEditModal(sprintId) {
    try {
        const response = await fetch(`${apiSprintsBaseUrl}/${sprintId}`);
        if (!response.ok) throw new Error(`Erro ${response.status}`);
        
        const sprint = await response.json();
        
        // Preenche o formulário
        document.getElementById('sprintName').value = sprint.name || '';
        document.getElementById('sprintStartDate').value = sprint.start_date ? sprint.start_date.split('T')[0] : '';
        document.getElementById('sprintEndDate').value = sprint.end_date ? sprint.end_date.split('T')[0] : '';
        document.getElementById('sprintGoal').value = sprint.goal || '';
        document.getElementById('sprintCriticality').value = sprint.criticality || 'Normal';
        
        // Configura modal para edição
        editingSprintId = sprintId;
        sprintModalLabel.textContent = 'Editar Sprint';
        modalDeleteBtn.style.display = 'inline-block';
        
        sprintModal.show();
        
    } catch (error) {
        console.error('❌ Erro ao carregar sprint:', error);
        showToast('Erro ao carregar dados da sprint', 'error');
    }
}

async function archiveSprint(sprintId, sprintName) {
    if (!confirm(`Tem certeza que deseja arquivar a sprint "${sprintName}"?\n\nEla será removida da visualização principal mas poderá ser recuperada posteriormente.`)) {
        return;
    }
    
    try {
        const response = await fetch(`${apiSprintsBaseUrl}/${sprintId}/archive`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                archived_by: 'Usuário' // Pode ser melhorado com autenticação
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || `Erro ${response.status}`);
        }
        
        const result = await response.json();
        showToast(result.message || 'Sprint arquivada com sucesso!', 'success');
        loadSprints(); // Recarrega sprints ativas
        
    } catch (error) {
        console.error('❌ Erro ao arquivar sprint:', error);
        showToast(`Erro ao arquivar sprint: ${error.message}`, 'error');
    }
}

async function unarchiveSprint(sprintId, sprintName) {
    if (!confirm(`Tem certeza que deseja desarquivar a sprint "${sprintName}"?\n\nEla voltará a aparecer na visualização principal.`)) {
        return;
    }
    
    try {
        const response = await fetch(`${apiSprintsBaseUrl}/${sprintId}/unarchive`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || `Erro ${response.status}`);
        }
        
        const result = await response.json();
        showToast(result.message || 'Sprint desarquivada com sucesso!', 'success');
        loadSprints(); // Recarrega sprints ativas
        refreshArchivedSprints(); // Atualiza modal de arquivadas
        
    } catch (error) {
        console.error('❌ Erro ao desarquivar sprint:', error);
        showToast(`Erro ao desarquivar sprint: ${error.message}`, 'error');
    }
}

async function deleteSprint(sprintId, sprintName) {
    if (!confirm(`Tem certeza que deseja excluir a sprint "${sprintName}"?\n\nAs tarefas serão movidas de volta para o backlog.`)) {
        return;
    }
    
    try {
        const response = await fetch(`${apiSprintsBaseUrl}/${sprintId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || `Erro ${response.status}`);
        }
        
        showToast('Sprint excluída com sucesso!', 'success');
        loadSprints();
        loadBacklogTasks(); // Recarrega backlog pois tarefas voltaram
        
    } catch (error) {
        console.error('❌ Erro ao excluir sprint:', error);
        showToast(`Erro ao excluir sprint: ${error.message}`, 'error');
    }
}

// Funções globais expostas
window.toggleProjectTasks = function(header) {
    const tasksDiv = header.nextElementSibling;
    const chevron = header.querySelector('.bi');
    
    if (tasksDiv.style.display === 'none') {
        tasksDiv.style.display = 'block';
        chevron.className = 'bi bi-chevron-up';
    } else {
        tasksDiv.style.display = 'none';
        chevron.className = 'bi bi-chevron-down';
    }
};

window.openSprintModal = function() {
    sprintForm.reset();
    editingSprintId = null;
    sprintModalLabel.textContent = 'Nova Sprint';
    modalDeleteBtn.style.display = 'none';
    sprintModal.show();
};

window.openGenericTaskModal = function(task = null) {
    const modal = document.getElementById('genericTaskModal');
    const form = document.getElementById('genericTaskForm');
    const modalTitle = document.getElementById('genericTaskModalLabel');
    const deleteBtn = document.getElementById('genericTaskDeleteBtn');
    
    if (!modal || !form) {
        console.error('Modal ou formulário de tarefa genérica não encontrado');
        return;
    }
    
    // Limpa o formulário
    form.reset();
    
    if (task) {
        // Modo edição
        modalTitle.textContent = 'Editar Tarefa Genérica';
        document.getElementById('genericTaskTitle').value = task.title || '';
        document.getElementById('genericTaskDescription').value = task.description || '';
        document.getElementById('genericTaskPriority').value = task.priority || 'Média';
        document.getElementById('genericTaskEstimatedHours').value = task.estimated_effort || '';
        document.getElementById('genericTaskSpecialist').value = task.specialist_name || '';
        
        // Armazena ID para edição
        form.dataset.editingId = task.id;
        
        // Mostra botão de exclusão
        if (deleteBtn) deleteBtn.style.display = 'block';
    } else {
        // Modo criação
        modalTitle.textContent = 'Nova Tarefa Genérica';
        delete form.dataset.editingId;
        
        // Esconde botão de exclusão
        if (deleteBtn) deleteBtn.style.display = 'none';
    }
    
    // Mostra o modal
    const bootstrapModal = new bootstrap.Modal(modal);
    bootstrapModal.show();
};

window.openArchivedSprintsModal = async function() {
    const modal = document.getElementById('archivedSprintsModal');
    if (!modal) {
        console.error('Modal de sprints arquivadas não encontrado');
        return;
    }
    
    // Mostra o modal
    const bootstrapModal = new bootstrap.Modal(modal);
    bootstrapModal.show();
    
    // Carrega sprints arquivadas
    await loadArchivedSprints();
};

window.refreshArchivedSprints = async function() {
    await loadArchivedSprints();
};

async function loadArchivedSprints() {
    const container = document.getElementById('archivedSprintsContainer');
    if (!container) return;
    
    // Mostra loading
    container.innerHTML = `
        <div class="text-center p-4">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Carregando...</span>
            </div>
            <p class="mt-2 text-muted">Carregando sprints arquivadas...</p>
        </div>
    `;
    
    try {
        const response = await fetch(`${apiSprintsBaseUrl}/archived`);
        if (!response.ok) throw new Error(`Erro ${response.status}`);
        
        const archivedSprints = await response.json();
        renderArchivedSprints(archivedSprints);
        
    } catch (error) {
        console.error('❌ Erro ao carregar sprints arquivadas:', error);
        container.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i>
                Erro ao carregar sprints arquivadas: ${error.message}
            </div>
        `;
    }
}

function renderArchivedSprints(sprints) {
    const container = document.getElementById('archivedSprintsContainer');
    if (!container) return;
    
    if (!sprints || sprints.length === 0) {
        container.innerHTML = `
            <div class="text-center p-4">
                <i class="bi bi-archive display-4 text-muted"></i>
                <p class="mt-3 text-muted">Nenhuma sprint arquivada encontrada.</p>
                <small class="text-muted">Sprints arquivadas aparecerão aqui.</small>
            </div>
        `;
        return;
    }
    
    container.innerHTML = `
        <div class="table-responsive">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>Nome</th>
                        <th>Período</th>
                        <th>Tarefas</th>
                        <th>Arquivada em</th>
                        <th>Arquivada por</th>
                        <th>Ações</th>
                    </tr>
                </thead>
                <tbody>
                    ${sprints.map(sprint => renderArchivedSprintRow(sprint)).join('')}
                </tbody>
            </table>
        </div>
    `;
}

function renderArchivedSprintRow(sprint) {
    const taskCount = sprint.tasks ? sprint.tasks.length : 0;
    const archivedDate = sprint.archived_at ? new Date(sprint.archived_at).toLocaleString('pt-BR') : 'N/A';
    const archivedBy = sprint.archived_by || 'N/A';
    
    return `
        <tr>
            <td>
                <strong>${escapeHtml(sprint.name || 'Sprint sem nome')}</strong>
                ${sprint.goal ? `<br><small class="text-muted">${escapeHtml(sprint.goal)}</small>` : ''}
            </td>
            <td>
                <small>
                    ${formatDate(sprint.start_date)} - ${formatDate(sprint.end_date)}
                </small>
            </td>
            <td>
                <span class="badge bg-secondary">${taskCount} tarefas</span>
            </td>
            <td>
                <small>${archivedDate}</small>
            </td>
            <td>
                <small>${escapeHtml(archivedBy)}</small>
            </td>
            <td>
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-success" 
                            onclick="unarchiveSprint(${sprint.id}, '${escapeHtml(sprint.name || '')}')"
                            title="Desarquivar Sprint">
                        <i class="bi bi-arrow-up-circle"></i>
                    </button>
                    <a href="/sprints/report/${sprint.id}" 
                       class="btn btn-outline-info" 
                       title="Ver Relatório">
                        <i class="bi bi-file-text"></i>
                    </a>
                    <button class="btn btn-outline-danger" 
                            onclick="deleteArchivedSprint(${sprint.id}, '${escapeHtml(sprint.name || '')}')"
                            title="Excluir Permanentemente">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
    `;
}

async function deleteArchivedSprint(sprintId, sprintName) {
    if (!confirm(`Tem certeza que deseja EXCLUIR PERMANENTEMENTE a sprint "${sprintName}"?\n\nEsta ação não pode ser desfeita!`)) {
        return;
    }
    
    try {
        const response = await fetch(`${apiSprintsBaseUrl}/${sprintId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || `Erro ${response.status}`);
        }
        
        showToast('Sprint excluída permanentemente!', 'success');
        refreshArchivedSprints(); // Atualiza lista de arquivadas
        
    } catch (error) {
        console.error('❌ Erro ao excluir sprint arquivada:', error);
        showToast(`Erro ao excluir sprint: ${error.message}`, 'error');
    }
}

// Função para inicializar popovers do Bootstrap
function initializePopovers() {
    console.log('🔄 Inicializando popovers...');
    
    // Verifica se o Bootstrap está disponível
    if (typeof bootstrap === 'undefined') {
        console.error('❌ Bootstrap não está disponível! Popovers não podem ser inicializados.');
        return;
    }
    
    // Destroi popovers existentes
    Object.values(popoverInstances).forEach(popover => {
        if (popover && popover.dispose) {
            try {
                popover.dispose();
            } catch (error) {
                console.warn('⚠️ Erro ao destruir popover existente:', error);
            }
        }
    });
    popoverInstances = {};
    
    // Aguarda um pequeno delay para garantir que o DOM foi atualizado
    setTimeout(() => {
        // Inicializa novos popovers
        const popoverElements = document.querySelectorAll('[data-bs-toggle="popover"]');
        console.log(`📊 Encontrados ${popoverElements.length} elementos com popover`);
        
        if (popoverElements.length === 0) {
            console.log('ℹ️ Nenhum elemento com popover encontrado');
            return;
        }
        
        popoverElements.forEach((element, index) => {
            try {
                // Verifica se o elemento tem conteúdo
                const content = element.getAttribute('data-bs-content');
                const title = element.getAttribute('data-bs-title');
                
                if (!content) {
                    console.warn(`⚠️ Elemento ${index} não tem conteúdo para popover`);
                    return;
                }
                
                console.log(`📊 Inicializando popover ${index} com título: "${title}"`);
                
                const popover = new bootstrap.Popover(element, {
                    html: true,
                    trigger: 'hover focus',
                    placement: 'bottom',
                    container: 'body',
                    delay: { show: 300, hide: 100 }
                });
                
                popoverInstances[`popover_${index}`] = popover;
                console.log(`✅ Popover ${index} inicializado com sucesso`);
                
            } catch (error) {
                console.error(`❌ Erro ao inicializar popover ${index}:`, error);
            }
        });
        
        console.log(`✅ ${Object.keys(popoverInstances).length} popovers inicializados de ${popoverElements.length} elementos`);
    }, 200); // Aumentei o delay para 200ms
}

// Handler para formulário de tarefa genérica
async function handleGenericTaskFormSubmit(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    const editingId = form.dataset.editingId;
    
    const taskData = {
        title: formData.get('title'),
        description: formData.get('description'),
        priority: formData.get('priority'),
        estimated_hours: formData.get('estimated_hours') ? parseFloat(formData.get('estimated_hours')) : null,
        specialist_name: formData.get('specialist_name') || null
    };
    
    try {
        const url = editingId 
            ? `/sprints/api/generic-tasks/${editingId}`
            : '/sprints/api/generic-tasks';
        
        const response = await fetch(url, {
            method: editingId ? 'PUT' : 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(taskData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || `Erro ${response.status}`);
        }
        
        const savedTask = await response.json();
        
        // Fecha o modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('genericTaskModal'));
        if (modal) modal.hide();
        
        // 🚀 OTIMIZAÇÃO: Atualização local em vez de reload completo
        if (editingId) {
            console.log('✅ Tarefa genérica atualizada, atualizando UI localmente...');
            await updateGenericTaskCardInUI(editingId, taskData);
        } else {
            console.log('✅ Nova tarefa genérica criada, adicionando à UI...');
            await addNewGenericTaskToUI(savedTask);
        }
        
        showToast(editingId ? 'Tarefa atualizada com sucesso!' : 'Tarefa criada com sucesso!', 'success');
        
    } catch (error) {
        console.error('❌ Erro ao salvar tarefa genérica:', error);
        showToast(`Erro ao salvar tarefa: ${error.message}`, 'error');
    }
}

/**
 * 🚀 NOVA FUNÇÃO: Atualiza card de tarefa genérica na UI
 */
async function updateGenericTaskCardInUI(taskId, updatedData) {
    try {
        const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
        if (!taskCard) {
            console.log('💡 Card da tarefa genérica não encontrado, fazendo reload...');
            await loadGenericTasks();
            return;
        }
        
        // Atualiza elementos visuais
        const titleElement = taskCard.querySelector('.task-title');
        if (titleElement && updatedData.title) {
            titleElement.textContent = updatedData.title;
        }
        
        const priorityElement = taskCard.querySelector('.task-priority');
        if (priorityElement && updatedData.priority) {
            priorityElement.className = priorityElement.className.replace(/priority-\w+/g, '');
            priorityElement.classList.add(`priority-${updatedData.priority.toLowerCase()}`);
            priorityElement.textContent = updatedData.priority;
        }
        
        const hoursElement = taskCard.querySelector('.task-hours');
        if (hoursElement && updatedData.estimated_hours !== null) {
            hoursElement.textContent = `${updatedData.estimated_hours}h`;
            taskCard.dataset.estimatedHours = updatedData.estimated_hours;
        }
        
        const specialistElement = taskCard.querySelector('.task-specialist');
        if (specialistElement && updatedData.specialist_name) {
            specialistElement.textContent = updatedData.specialist_name;
            taskCard.dataset.specialistName = updatedData.specialist_name;
        }
        
        console.log('✅ Card da tarefa genérica atualizado localmente');
        
    } catch (error) {
        console.error('❌ Erro ao atualizar card genérico na UI:', error);
        await loadGenericTasks();
    }
}

/**
 * 🚀 NOVA FUNÇÃO: Adiciona nova tarefa genérica à UI
 */
async function addNewGenericTaskToUI(newTask) {
    try {
        const genericTasksList = document.getElementById('genericTasksList');
        if (!genericTasksList) {
            console.log('💡 Lista de tarefas genéricas não encontrada');
            return;
        }
        
        // Cria o HTML do novo card
        const taskCard = document.createElement('div');
        taskCard.className = 'generic-task card mb-2';
        taskCard.dataset.taskId = newTask.id;
        taskCard.dataset.estimatedHours = newTask.estimated_hours || 0;
        taskCard.dataset.specialistName = newTask.specialist_name || '';
        
        const priorityClass = getPriorityClass(newTask.priority || 'Média');
        
        taskCard.innerHTML = `
            <div class="card-body p-2">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <h6 class="task-title mb-1">${escapeHtml(newTask.title)}</h6>
                        <div class="d-flex flex-wrap gap-1">
                            <span class="badge ${priorityClass} task-priority">${newTask.priority || 'Média'}</span>
                            ${newTask.estimated_hours ? `<span class="badge bg-info task-hours">${newTask.estimated_hours}h</span>` : ''}
                            ${newTask.specialist_name ? `<span class="badge bg-secondary task-specialist">${escapeHtml(newTask.specialist_name)}</span>` : ''}
                        </div>
                    </div>
                    <div class="task-actions">
                        <button type="button" class="btn btn-sm btn-outline-primary" 
                                onclick="openTaskDetailsModal(this, ${JSON.stringify(newTask).replace(/"/g, '&quot;')})">
                            <i class="bi bi-pencil"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        // Adiciona animação de entrada
        taskCard.style.opacity = '0';
        taskCard.style.transform = 'scale(0.8)';
        taskCard.style.transition = 'all 0.3s ease';
        
        genericTasksList.appendChild(taskCard);
        
        // Anima a entrada
        setTimeout(() => {
            taskCard.style.opacity = '1';
            taskCard.style.transform = 'scale(1)';
        }, 10);
        
        console.log('✅ Nova tarefa genérica adicionada à UI');
        
    } catch (error) {
        console.error('❌ Erro ao adicionar nova tarefa genérica à UI:', error);
        await loadGenericTasks();
    }
}

/**
 * Abre o modal de detalhes da tarefa para edição
 * @param {HTMLElement} taskElement - Elemento da tarefa clicada
 * @param {Object} task - Dados da tarefa
 */
function openTaskDetailsModal(taskElement, task) {
    console.log('🔄 Abrindo modal de detalhes da tarefa:', task);
    
    const modal = document.getElementById('taskDetailsModal');
    const form = document.getElementById('taskDetailsForm');
    const modalTitle = document.getElementById('taskDetailsModalLabel');
    
    if (!modal || !form) {
        console.error('❌ Modal ou formulário de detalhes da tarefa não encontrado');
        return;
    }
    
    // Preenche o formulário com os dados da tarefa
    document.getElementById('taskId').value = task.id || '';
    document.getElementById('taskType').value = task.is_generic ? 'generic' : 'backlog';
    document.getElementById('taskTitle').value = task.title || '';
    document.getElementById('taskPriority').value = task.priority || 'Média';
    document.getElementById('taskSpecialist').value = task.specialist_name || '';
    document.getElementById('taskEstimatedHours').value = task.estimated_effort || '';
    document.getElementById('taskDescription').value = task.description || '';
    
    // Preenche campos específicos do backlog se não for tarefa genérica
    if (!task.is_generic) {
        document.getElementById('taskProjectId').value = task.project_id || '';
        // Usa column_name (nome em português) em vez de column_identifier (identificador em inglês)
        document.getElementById('taskColumnIdentifier').value = task.column_name || task.column_identifier || '';
        
        // === CAMPOS DE DATAS ===
        // Função auxiliar para converter ISO datetime para formato input date/datetime-local
        function formatDateForInput(isoString, inputType = 'date') {
            if (!isoString) return '';
            
            try {
                const date = new Date(isoString);
                if (isNaN(date.getTime())) return '';
                
                if (inputType === 'date') {
                    // Formato YYYY-MM-DD para input type="date"
                    return date.toISOString().split('T')[0];
                } else {
                    // Formato YYYY-MM-DDTHH:mm para input type="datetime-local"
                    const offset = date.getTimezoneOffset();
                    const localDate = new Date(date.getTime() - (offset * 60 * 1000));
                    return localDate.toISOString().slice(0, 16);
                }
            } catch (error) {
                console.warn('Erro ao formatar data:', isoString, error);
                return '';
            }
        }
        
        // Preenche campos de data editáveis
        document.getElementById('taskStartDate').value = formatDateForInput(task.start_date, 'date');
        document.getElementById('taskDueDate').value = formatDateForInput(task.due_date, 'date');
        
        // Preenche campos de data somente leitura (gerados automaticamente)
        document.getElementById('taskActuallyStartedAt').value = formatDateForInput(task.actually_started_at, 'datetime-local');
        document.getElementById('taskCompletedAt').value = formatDateForInput(task.completed_at, 'datetime-local');
        document.getElementById('taskCreatedAt').value = formatDateForInput(task.created_at, 'datetime-local');
        document.getElementById('taskUpdatedAt').value = formatDateForInput(task.updated_at, 'datetime-local');
        
        console.log('📅 Campos de data preenchidos:', {
            start_date: task.start_date,
            due_date: task.due_date,
            actually_started_at: task.actually_started_at,
            completed_at: task.completed_at,
            created_at: task.created_at,
            updated_at: task.updated_at
        });
        
        // Mostra campos específicos do backlog
        const backlogFields = document.getElementById('backlogSpecificFields');
        if (backlogFields) {
            backlogFields.style.display = 'block';
        }
    } else {
        // Esconde campos específicos do backlog para tarefas genéricas
        const backlogFields = document.getElementById('backlogSpecificFields');
        if (backlogFields) {
            backlogFields.style.display = 'none';
        }
    }
    
    // Define o status se disponível
    const statusSelect = document.getElementById('taskStatus');
    if (statusSelect && task.status) {
        // Mapeia os valores do enum para os valores do select
        let statusValue = task.status;
        
        // Se o status vier como string do enum, mapeia para os valores corretos
        if (typeof task.status === 'string') {
            const statusMapping = {
                'A Fazer': 'TODO',
                'Em Andamento': 'IN_PROGRESS', 
                'Revisão': 'REVIEW',
                'Concluído': 'DONE',
                'Arquivado': 'ARCHIVED'
            };
            
            // Se o status já está no formato correto (TODO, IN_PROGRESS, etc), usa direto
            // Se está no formato de texto (A Fazer, Em Andamento, etc), converte
            statusValue = statusMapping[task.status] || task.status;
        }
        
        console.log('🔄 Definindo status:', { original: task.status, mapped: statusValue });
        statusSelect.value = statusValue;
    }
    
    // Atualiza título do modal
    const taskId = task.project_id ? `${task.project_id}-${(task.column_identifier || 'UNK').substring(0, 3).toUpperCase()}-${task.id}` : `GEN-${task.id}`;
    modalTitle.textContent = `Editar Tarefa: ${taskId}`;
    
    // Mostra o modal
    const bootstrapModal = new bootstrap.Modal(modal);
    bootstrapModal.show();
}

/**
 * Handler para submissão do formulário de detalhes da tarefa
 */
async function handleTaskDetailsFormSubmit(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    const taskId = formData.get('taskId');
    const taskType = formData.get('taskType');
    
    if (!taskId) {
        showToast('ID da tarefa não encontrado', 'error');
        return;
    }
    
    const data = {
        name: formData.get('title'),
        priority: formData.get('priority'),
        specialist_name: formData.get('specialist_name'),
        estimated_hours: formData.get('estimated_hours') ? parseFloat(formData.get('estimated_hours')) : null,
        description: formData.get('description'),
        start_date: formData.get('start_date') || null,
        due_date: formData.get('due_date') || null
    };
    
    // Para tarefas do backlog, precisamos mapear o status para o ID da coluna correspondente
    const statusValue = formData.get('status');
    if (statusValue && statusValue !== 'None' && statusValue !== '' && taskType !== 'generic') {
        // Mapeia status para ID da coluna correspondente
        const columnId = await getColumnIdFromStatus(statusValue);
        if (columnId) {
            data.status = columnId;
        }
    } else if (taskType === 'generic' && statusValue && statusValue !== 'None' && statusValue !== '') {
        // Para tarefas genéricas, envia o status diretamente
        data.status = statusValue;
    }
    
    console.log('💾 Salvando alterações da tarefa:', { taskId, taskType, data });
    
    try {
        // Determina a URL da API baseada no tipo de tarefa
        let apiUrl;
        if (taskType === 'generic') {
            apiUrl = `/sprints/api/generic-tasks/${taskId}`;
        } else {
            apiUrl = `/backlog/api/tasks/${taskId}`;
        }
        
        const response = await fetch(apiUrl, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || `Erro ${response.status}`);
        }
        
        // Fecha o modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('taskDetailsModal'));
        if (modal) modal.hide();
        
        // 🚀 OTIMIZAÇÃO CRÍTICA: Atualização local em vez de reload completo
        // Em vez de recarregar tudo (loadSprints + loadBacklogTasks), 
        // atualizamos apenas o card específico na UI
        console.log('✅ Tarefa atualizada com sucesso, atualizando UI localmente...');
        
        // Atualiza o card da tarefa na UI
        await updateTaskCardInUI(taskId, data, taskType);
        
        showToast('Tarefa atualizada com sucesso!', 'success');
        
    } catch (error) {
        console.error('❌ Erro ao salvar alterações da tarefa:', error);
        showToast(`Erro ao salvar alterações: ${error.message}`, 'error');
    }
}

/**
 * 🚀 NOVA FUNÇÃO: Atualiza apenas o card da tarefa na UI sem reload completo
 * Isso elimina os logs excessivos e melhora drasticamente a performance
 */
async function updateTaskCardInUI(taskId, updatedData, taskType) {
    try {
        // Encontra o card da tarefa na UI
        const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
        if (!taskCard) {
            console.log('💡 Card da tarefa não encontrado na UI atual, fazendo reload seletivo...');
            // Se não encontrar o card, faz apenas um reload seletivo da área necessária
            if (taskType === 'generic') {
                await loadGenericTasks();
            } else {
                // Para tarefas do backlog, atualiza apenas se estiver na view de sprints
                const sprintBoard = document.getElementById('sprintBoard');
                if (sprintBoard && sprintBoard.querySelector(`[data-task-id="${taskId}"]`)) {
                    await loadSprints();
                }
            }
            return;
        }
        
        // Atualiza os elementos visuais do card
        const titleElement = taskCard.querySelector('.task-title');
        if (titleElement && updatedData.name) {
            titleElement.textContent = updatedData.name;
        }
        
        const priorityElement = taskCard.querySelector('.task-priority');
        if (priorityElement && updatedData.priority) {
            // Remove classes de prioridade antigas
            priorityElement.className = priorityElement.className.replace(/priority-\w+/g, '');
            // Adiciona nova classe de prioridade
            priorityElement.classList.add(`priority-${updatedData.priority.toLowerCase()}`);
            priorityElement.textContent = updatedData.priority;
        }
        
        const hoursElement = taskCard.querySelector('.task-hours');
        if (hoursElement && updatedData.estimated_hours !== null) {
            hoursElement.textContent = `${updatedData.estimated_hours}h`;
            // Atualiza o dataset para cálculos
            taskCard.dataset.estimatedHours = updatedData.estimated_hours;
        }
        
        const specialistElement = taskCard.querySelector('.task-specialist');
        if (specialistElement && updatedData.specialist_name) {
            specialistElement.textContent = updatedData.specialist_name;
            // Atualiza o dataset
            taskCard.dataset.specialistName = updatedData.specialist_name;
        }
        
        // Atualiza tooltips se existirem
        const tooltipElement = taskCard.querySelector('[data-bs-toggle="tooltip"]');
        if (tooltipElement && updatedData.description) {
            tooltipElement.setAttribute('data-bs-original-title', updatedData.description);
        }
        
        // Força atualização dos totais de horas apenas da sprint atual
        const sprintCard = taskCard.closest('.sprint-card');
        if (sprintCard) {
            updateSprintHoursDisplay(taskCard.closest('.sprint-tasks'));
        }
        
        console.log('✅ Card da tarefa atualizado localmente');
        
    } catch (error) {
        console.error('❌ Erro ao atualizar card na UI, fazendo reload:', error);
        // Em caso de erro, faz reload como fallback
        if (taskType === 'generic') {
            await loadGenericTasks();
        } else {
            await loadSprints();
        }
    }
}

/**
 * Handler para exclusão de tarefa
 */
async function handleTaskDelete() {
    const taskId = document.getElementById('taskId').value;
    const taskType = document.getElementById('taskType').value;
    const taskTitle = document.getElementById('taskTitle').value;
    
    if (!taskId) {
        showToast('ID da tarefa não encontrado', 'error');
        return;
    }
    
    if (!confirm(`Tem certeza que deseja excluir a tarefa "${taskTitle}"?`)) {
        return;
    }
    
    console.log('🗑️ Excluindo tarefa:', { taskId, taskType });
    
    try {
        // Determina a URL da API baseada no tipo de tarefa
        let apiUrl;
        if (taskType === 'generic') {
            apiUrl = `/sprints/api/generic-tasks/${taskId}`;
        } else {
            apiUrl = `/backlog/api/tasks/${taskId}`;
        }
        
        const response = await fetch(apiUrl, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || `Erro ${response.status}`);
        }
        
        // Fecha o modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('taskDetailsModal'));
        if (modal) modal.hide();
        
        // 🚀 OTIMIZAÇÃO: Remove o card da UI localmente em vez de reload completo
        console.log('✅ Tarefa excluída com sucesso, removendo da UI...');
        
        const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
        if (taskCard) {
            // Atualiza totais de horas antes de remover
            const sprintCard = taskCard.closest('.sprint-card');
            if (sprintCard) {
                const taskHours = parseFloat(taskCard.dataset.estimatedHours) || 0;
                updateSprintHoursAfterRemoval(sprintCard, taskHours);
            }
            
            // Remove o card com animação
            taskCard.style.transition = 'all 0.3s ease';
            taskCard.style.opacity = '0';
            taskCard.style.transform = 'scale(0.8)';
            
            setTimeout(() => {
                taskCard.remove();
                console.log('✅ Card da tarefa removido da UI');
            }, 300);
        } else {
            // Se não encontrar o card, faz reload seletivo como fallback
            console.log('💡 Card não encontrado, fazendo reload seletivo...');
            if (taskType === 'generic') {
                await loadGenericTasks();
            } else {
                await loadSprints();
            }
        }
        
        showToast('Tarefa excluída com sucesso!', 'success');
        
    } catch (error) {
        console.error('❌ Erro ao excluir tarefa:', error);
        showToast(`Erro ao excluir tarefa: ${error.message}`, 'error');
    }
}

/**
 * Handler para exclusão de tarefa genérica
 */
async function handleGenericTaskDelete() {
    const form = document.getElementById('genericTaskForm');
    const taskId = form.dataset.editingId;
    const taskTitle = document.getElementById('genericTaskTitle').value;
    
    if (!taskId) {
        showToast('ID da tarefa não encontrado', 'error');
        return;
    }
    
    if (!confirm(`Tem certeza que deseja excluir a tarefa genérica "${taskTitle}"?`)) {
        return;
    }
    
    console.log('🗑️ Excluindo tarefa genérica:', taskId);
    
    try {
        const response = await fetch(`/sprints/api/generic-tasks/${taskId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || `Erro ${response.status}`);
        }
        
        // Fecha o modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('genericTaskModal'));
        if (modal) modal.hide();
        
        // 🚀 OTIMIZAÇÃO: Remove o card da UI localmente
        console.log('✅ Tarefa genérica excluída com sucesso, removendo da UI...');
        
        const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
        if (taskCard) {
            // Remove o card com animação
            taskCard.style.transition = 'all 0.3s ease';
            taskCard.style.opacity = '0';
            taskCard.style.transform = 'scale(0.8)';
            
            setTimeout(() => {
                taskCard.remove();
                console.log('✅ Card da tarefa genérica removido da UI');
            }, 300);
        } else {
            // Fallback: reload apenas das tarefas genéricas
            await loadGenericTasks();
        }
        
        showToast('Tarefa genérica excluída com sucesso!', 'success');
        
    } catch (error) {
        console.error('❌ Erro ao excluir tarefa genérica:', error);
        showToast(`Erro ao excluir tarefa genérica: ${error.message}`, 'error');
    }
}

/**
 * 🚀 NOVA FUNÇÃO: Atualiza totais de horas da sprint após remoção de tarefa
 */
function updateSprintHoursAfterRemoval(sprintCard, removedHours) {
    try {
        const hoursSpan = sprintCard.querySelector('.sprint-total-hours');
        if (hoursSpan) {
            // Extrai horas atuais do texto (formato: "123.5h")
            const currentText = hoursSpan.textContent;
            const currentHours = parseFloat(currentText.match(/[\d.]+/)?.[0] || '0');
            const newHours = Math.max(0, currentHours - removedHours);
            
            // Atualiza o display
            hoursSpan.innerHTML = `<i class="bi bi-clock"></i> ${newHours.toFixed(1)}h`;
            
            console.log(`🔄 Horas da sprint atualizadas: ${currentHours.toFixed(1)}h → ${newHours.toFixed(1)}h (-${removedHours.toFixed(1)}h)`);
        }
    } catch (error) {
        console.error('❌ Erro ao atualizar horas da sprint:', error);
    }
}

/**
 * Mapeia status para ID da coluna correspondente
 * @param {string} status - Status da tarefa (TODO, IN_PROGRESS, etc.)
 * @returns {Promise<number>} - ID da coluna correspondente
 */
async function getColumnIdFromStatus(status) {
    try {
        // Cache das colunas para evitar múltiplas requisições
        if (!window.columnsCache) {
            const response = await fetch('/backlog/api/columns');
            if (!response.ok) {
                throw new Error('Erro ao buscar colunas');
            }
            window.columnsCache = await response.json();
        }
        
        // Mapeamento de status para nomes de coluna (em português)
        const statusToColumnName = {
            'TODO': ['a fazer', 'afazer', 'todo', 'pendente'],
            'IN_PROGRESS': ['em andamento', 'andamento', 'progresso', 'desenvolvimento'],
            'REVIEW': ['revisão', 'revisao', 'review', 'validação', 'teste'],
            'DONE': ['concluído', 'concluido', 'done', 'finalizado', 'pronto'],
            'ARCHIVED': ['arquivado', 'archived', 'cancelado']
        };
        
        const possibleNames = statusToColumnName[status] || [];
        
        // Busca a coluna correspondente
        for (const column of window.columnsCache) {
            const columnNameLower = column.name.toLowerCase();
            if (possibleNames.some(name => columnNameLower.includes(name) || name.includes(columnNameLower))) {
                console.log(`🔄 Mapeando status '${status}' para coluna '${column.name}' (ID: ${column.id})`);
                return column.id;
            }
        }
        
        // Se não encontrou, retorna null para não enviar o status
        console.warn(`⚠️ Não foi possível mapear status '${status}' para uma coluna`);
        return null;
        
    } catch (error) {
        console.error('❌ Erro ao mapear status para coluna:', error);
        return null;
    }
}

/**
 * Calcula a capacidade total de um especialista para uma sprint baseada na duração
 * @param {Object} sprint - Objeto da sprint com start_date e end_date
 * @returns {number} - Capacidade total em horas para a sprint
 */
function calculateSprintCapacity(sprint) {
    const HORAS_POR_SEMANA = 36.0; // 36h por semana conforme especificação
    
    if (!sprint.start_date || !sprint.end_date) {
        return HORAS_POR_SEMANA; // Default 1 semana se não tiver datas
    }
    
    try {
        const startDate = new Date(sprint.start_date);
        const endDate = new Date(sprint.end_date);
        
        // Calcula duração em dias
        const durationDays = Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24)) + 1;
        
        // Calcula duração em semanas (mínimo 1, arredonda para cima)
        const weeks = Math.max(1, Math.ceil(durationDays / 7));
        
        // Capacidade total = semanas × 36h
        return HORAS_POR_SEMANA * weeks;
        
    } catch (error) {
        console.error('Erro ao calcular capacidade da sprint:', error);
        return HORAS_POR_SEMANA; // Fallback para 1 semana
    }
}

// Controles de Visibilidade das Colunas
let columnVisibility = {
    backlog: true,
    genericTasks: true
};

/**
 * Alterna a visibilidade de uma coluna
 * @param {string} columnType - Tipo da coluna ('backlog' ou 'genericTasks')
 */
function toggleColumnVisibility(columnType) {
    const isVisible = columnVisibility[columnType];
    const newVisibility = !isVisible;
    
    // Atualiza o estado
    columnVisibility[columnType] = newVisibility;
    
    // Aplica a mudança visual
    applyColumnVisibility(columnType, newVisibility);
    
    // Atualiza o botão
    updateToggleButton(columnType, newVisibility);
    
    // Salva a preferência no localStorage
    saveColumnPreferences();
    
    console.log(`🔄 Coluna ${columnType} ${newVisibility ? 'mostrada' : 'ocultada'}`);
}

/**
 * Aplica a visibilidade de uma coluna
 * @param {string} columnType - Tipo da coluna
 * @param {boolean} isVisible - Se deve estar visível
 */
function applyColumnVisibility(columnType, isVisible) {
    const columnMap = {
        'backlog': 'backlogColumn',
        'genericTasks': 'genericTasksColumn'
    };
    
    const columnElement = document.getElementById(columnMap[columnType]);
    if (!columnElement) return;
    
    if (isVisible) {
        columnElement.classList.remove('hidden');
    } else {
        columnElement.classList.add('hidden');
    }
}

/**
 * Atualiza o estado visual do botão de toggle
 * @param {string} columnType - Tipo da coluna
 * @param {boolean} isVisible - Se está visível
 */
function updateToggleButton(columnType, isVisible) {
    const buttonMap = {
        'backlog': 'toggleBacklogBtn',
        'genericTasks': 'toggleGenericTasksBtn'
    };
    
    const button = document.getElementById(buttonMap[columnType]);
    if (!button) return;
    
    // Remove classes anteriores
    button.classList.remove('btn-toggle-active', 'btn-toggle-inactive');
    
    // Adiciona a classe apropriada
    if (isVisible) {
        button.classList.add('btn-toggle-active');
        button.title = `Ocultar ${columnType === 'backlog' ? 'Backlog' : 'Tarefas Genéricas'}`;
    } else {
        button.classList.add('btn-toggle-inactive');
        button.title = `Mostrar ${columnType === 'backlog' ? 'Backlog' : 'Tarefas Genéricas'}`;
    }
}

/**
 * Salva as preferências de visibilidade no localStorage
 */
function saveColumnPreferences() {
    try {
        localStorage.setItem('sprintColumnVisibility', JSON.stringify(columnVisibility));
    } catch (error) {
        console.warn('⚠️ Não foi possível salvar preferências de visibilidade:', error);
    }
}

/**
 * Carrega as preferências de visibilidade do localStorage
 */
function loadColumnPreferences() {
    try {
        const saved = localStorage.getItem('sprintColumnVisibility');
        if (saved) {
            const preferences = JSON.parse(saved);
            columnVisibility = { ...columnVisibility, ...preferences };
        }
    } catch (error) {
        console.warn('⚠️ Não foi possível carregar preferências de visibilidade:', error);
    }
}

/**
 * Inicializa os controles de visibilidade
 */
function initializeColumnVisibility() {
    // Carrega preferências salvas
    loadColumnPreferences();
    
    // Aplica a visibilidade inicial
    Object.keys(columnVisibility).forEach(columnType => {
        applyColumnVisibility(columnType, columnVisibility[columnType]);
        updateToggleButton(columnType, columnVisibility[columnType]);
    });
    
    console.log('✅ Controles de visibilidade inicializados:', columnVisibility);
}

// Expõe a função globalmente para uso nos botões
window.toggleColumnVisibility = toggleColumnVisibility;

/**
 * Atualiza o popover de horas por especialista de uma sprint
 * @param {HTMLElement} sprintCard - Elemento do card da sprint
 * @param {Object} hoursBySpecialist - Objeto com horas por especialista
 */
function updateSpecialistPopover(sprintCard, hoursBySpecialist) {
    if (!sprintCard) return;

    // Obtém a capacidade da sprint baseada na duração
    const sprintId = sprintCard.dataset.sprintId;
    let sprintCapacity = 36; // Default 1 semana
    
    // Busca a sprint nos dados carregados para calcular capacidade correta
    if (window.sprintsData && sprintId) {
        const sprint = window.sprintsData.find(s => s.id == sprintId);
        if (sprint) {
            sprintCapacity = calculateSprintCapacity(sprint);
        }
    }

    // Formata o conteúdo do popover com informações baseadas na capacidade real
    let popoverContent = Object.entries(hoursBySpecialist)
        .map(([name, allocatedHours]) => {
            const remainingHours = Math.max(0, sprintCapacity - allocatedHours);
            const utilizationPercent = (allocatedHours / sprintCapacity) * 100;
            
            // Badge de alerta baseado na capacidade real da sprint
            let alertBadge = '';
            if (utilizationPercent > 100) {
                alertBadge = '<span class="badge bg-danger ms-2">⚠️ Sobrecarga</span>';
            } else if (utilizationPercent > 80) {
                alertBadge = '<span class="badge bg-warning ms-2">⚠️ Limite</span>';
            } else {
                alertBadge = '<span class="badge bg-success ms-2">✅ OK</span>';
            }
            
            return `
                <div class="mb-1">
                    <strong>${escapeHtml(name)}</strong><br>
                    <small>Consumo: ${allocatedHours.toFixed(1)}h | Saldo: ${remainingHours.toFixed(1)}h</small>
                    <br><small class="text-muted">Capacidade: ${sprintCapacity.toFixed(1)}h</small>
                    ${alertBadge}
                </div>
            `;
        })
        .join('');
    
    if (!popoverContent) {
        popoverContent = '<small class="text-muted">Nenhum especialista alocado</small>';
    }

    // Atualiza o popover
    const popoverButton = sprintCard.querySelector('.specialist-hours-popover');
    if (popoverButton) {
        // Destrói o popover existente
        const popoverInstance = bootstrap.Popover.getInstance(popoverButton);
        if (popoverInstance) {
            popoverInstance.dispose();
        }

        if (Object.keys(hoursBySpecialist).length > 0) {
            // Cria um novo popover com o conteúdo atualizado
            new bootstrap.Popover(popoverButton, {
                content: popoverContent,
                html: true,
                placement: 'bottom',
                trigger: 'hover focus',
                title: 'Especialistas'
            });
            popoverButton.style.display = 'inline-flex';
        } else {
            popoverButton.style.display = 'none';
        }
    }
}

/**
 * Retorna uma tarefa para sua origem (backlog do projeto ou tarefas genéricas)
 * @param {number} taskId - ID da tarefa
 * @param {string} originType - Tipo de origem ('backlog' ou 'generic')
 */
async function returnTaskToOrigin(taskId, originType) {
    try {
        console.log(`🔄 Retornando tarefa ${taskId} para origem: ${originType}`);
        
        let apiUrl, successMessage;
        
        if (originType === 'generic') {
            // Para tarefas genéricas, remove da sprint
            apiUrl = `/sprints/api/sprints/tasks/${taskId}/move-to-backlog`;
            successMessage = 'Tarefa retornada para Tarefas Genéricas';
        } else {
            // Para tarefas de backlog, remove da sprint (volta para o backlog do projeto)
            apiUrl = `/sprints/api/sprints/tasks/${taskId}/move-to-backlog`;
            successMessage = 'Tarefa retornada para o Backlog do Projeto';
        }
        
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.message || `Erro ${response.status}`);
        }
        
        // ✅ OTIMIZAÇÃO: Remove tarefa localmente da UI sem recarregar tudo
        const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
        if (taskCard) {
            // Obtém informações antes de remover
            const sprintContainer = taskCard.closest('.sprint-tasks');
            const estimatedHours = parseFloat(taskCard.dataset.estimatedHours) || 0;
            
            // Remove tarefa com animação
            taskCard.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
            taskCard.style.opacity = '0';
            taskCard.style.transform = 'scale(0.8)';
            
            setTimeout(() => {
                taskCard.remove();
                
                // Atualiza contador de horas da sprint
                if (sprintContainer) {
                    const sprintCard = sprintContainer.closest('.sprint-card');
                    if (sprintCard && estimatedHours > 0) {
                        updateSprintHoursAfterRemoval(sprintCard, estimatedHours);
                    }
                }
                
                console.log(`✅ Tarefa ${taskId} removida da UI`);
            }, 300);
            
            // Recarrega apenas a lista de destino, não todas as listas
            if (originType === 'generic') {
                await loadGenericTasks();
            } else {
                await loadBacklogTasks();
            }
        } else {
            // Fallback: se não encontrou a tarefa na UI, recarrega sprints apenas
            console.log(`⚠️ Tarefa ${taskId} não encontrada na UI, recarregando sprints...`);
            await loadSprints();
        }
        
        // Feedback visual
        showToast(successMessage, 'success');
        
        console.log(`✅ Tarefa ${taskId} retornada com sucesso para ${originType}`);
        
    } catch (error) {
        console.error('❌ Erro ao retornar tarefa:', error);
        showToast(`Erro ao retornar tarefa: ${error.message}`, 'error');
        
        // Em caso de erro, faz fallback para recarregamento completo
        console.log('🔄 Fazendo fallback para recarregamento completo...');
        await Promise.all([
            loadSprints(),
            loadBacklogTasks(),
            loadGenericTasks()
        ]);
    }
}

// Expõe a função globalmente para uso nos botões
window.returnTaskToOrigin = returnTaskToOrigin;

console.log('✅ Sprint Management JavaScript carregado');

// === SISTEMA DE FILTROS POR PROJETO E ESPECIALISTA ===

/**
 * Inicializa o sistema de filtros
 */
function initializeFilters() {
    console.log('🔧 Inicializando sistema de filtros...');
    
    // Carrega filtros salvos do localStorage
    loadSavedFilters();
    
    // Configura eventos dos dropdowns
    setupFilterDropdowns();
    
    console.log('✅ Sistema de filtros inicializado');
}

/**
 * Carrega filtros salvos do localStorage
 */
function loadSavedFilters() {
    try {
        const savedFilters = localStorage.getItem('sprintFilters');
        if (savedFilters) {
            activeFilters = { ...activeFilters, ...JSON.parse(savedFilters) };
            updateFilterUI();
        }
    } catch (error) {
        console.warn('⚠️ Erro ao carregar filtros salvos:', error);
    }
}

/**
 * Salva filtros no localStorage
 */
function saveFilters() {
    try {
        localStorage.setItem('sprintFilters', JSON.stringify(activeFilters));
    } catch (error) {
        console.warn('⚠️ Erro ao salvar filtros:', error);
    }
}

/**
 * Configura eventos dos dropdowns de filtros
 */
function setupFilterDropdowns() {
    // Previne fechamento ao clicar nos inputs de busca
    document.getElementById('projectFilterSearch').addEventListener('click', (e) => {
        e.stopPropagation();
    });
    
    document.getElementById('specialistFilterSearch').addEventListener('click', (e) => {
        e.stopPropagation();
    });
}

/**
 * Extrai e atualiza listas de projetos e especialistas das sprints
 */
function updateFilterLists() {
    console.log('🔄 Atualizando listas de filtros...');
    
    allProjects.clear();
    allSpecialists.clear();
    
    // Percorre todas as sprints carregadas
    if (window.sprintsData) {
        window.sprintsData.forEach(sprint => {
            if (sprint.tasks) {
                sprint.tasks.forEach(task => {
                    // Adiciona projeto se existir (usando Map para evitar duplicatas)
                    if (task.project_name && task.project_id) {
                        allProjects.set(task.project_id, {
                            id: task.project_id,
                            name: task.project_name
                        });
                    }
                    
                    // Adiciona especialista se existir
                    if (task.specialist_name && task.specialist_name !== 'Não atribuído') {
                        allSpecialists.add(task.specialist_name);
                    }
                });
            }
        });
    }
    
    // Atualiza dropdowns
    updateProjectFilterDropdown();
    updateSpecialistFilterDropdown();
    
    console.log(`✅ Filtros atualizados: ${allProjects.size} projetos, ${allSpecialists.size} especialistas`);
}

/**
 * Atualiza dropdown de filtros de projeto
 */
function updateProjectFilterDropdown() {
    const container = document.getElementById('projectFilterList');
    if (!container) return;
    
    const projectsArray = Array.from(allProjects.values());
    
    if (projectsArray.length === 0) {
        container.innerHTML = '<li class="px-3 py-2 text-muted">Nenhum projeto encontrado</li>';
        return;
    }
    
    // Ordena projetos por nome
    projectsArray.sort((a, b) => a.name.localeCompare(b.name));
    
    container.innerHTML = projectsArray.map(project => `
        <li>
            <div class="filter-project-item ${activeFilters.project === project.id ? 'selected' : ''}" 
                 onclick="selectProjectFilter('${project.id}', '${escapeHtml(project.name)}')">
                <span class="project-name">${escapeHtml(project.name)}</span>
                <span class="project-id">ID: ${project.id}</span>
            </div>
        </li>
    `).join('');
}

/**
 * Atualiza dropdown de filtros de especialista
 */
function updateSpecialistFilterDropdown() {
    const container = document.getElementById('specialistFilterList');
    if (!container) return;
    
    const specialistsArray = Array.from(allSpecialists);
    
    if (specialistsArray.length === 0) {
        container.innerHTML = '<li class="px-3 py-2 text-muted">Nenhum especialista encontrado</li>';
        return;
    }
    
    // Ordena especialistas alfabeticamente
    specialistsArray.sort();
    
    container.innerHTML = specialistsArray.map(specialist => {
        // Conta tarefas do especialista
        const taskCount = countTasksBySpecialist(specialist);
        
        return `
            <li>
                <div class="filter-specialist-item ${activeFilters.specialist === specialist ? 'selected' : ''}" 
                     onclick="selectSpecialistFilter('${escapeHtml(specialist)}')">
                    <span class="specialist-name">${escapeHtml(specialist)}</span>
                    <span class="task-count">${taskCount} tarefa(s)</span>
                </div>
            </li>
        `;
    }).join('');
}

/**
 * Conta tarefas por especialista
 */
function countTasksBySpecialist(specialistName) {
    let count = 0;
    if (window.sprintsData) {
        window.sprintsData.forEach(sprint => {
            if (sprint.tasks) {
                count += sprint.tasks.filter(task => task.specialist_name === specialistName).length;
            }
        });
    }
    return count;
}

/**
 * Seleciona filtro de projeto
 */
function selectProjectFilter(projectId, projectName) {
    console.log(`🎯 Selecionando filtro de projeto: ${projectId} - ${projectName}`);
    
    activeFilters.project = projectId;
    
    // Atualiza UI
    document.getElementById('projectFilterText').textContent = projectName;
    updateProjectFilterDropdown();
    
    // Aplica filtros
    applyFilters();
    updateActiveFiltersIndicator();
    saveFilters();
    
    // Fecha dropdown
    const dropdown = bootstrap.Dropdown.getInstance(document.getElementById('projectFilterBtn'));
    if (dropdown) dropdown.hide();
}

/**
 * Seleciona filtro de especialista
 */
function selectSpecialistFilter(specialistName) {
    console.log(`🎯 Selecionando filtro de especialista: ${specialistName}`);
    
    activeFilters.specialist = specialistName;
    
    // Atualiza UI
    document.getElementById('specialistFilterText').textContent = specialistName;
    updateSpecialistFilterDropdown();
    
    // Aplica filtros
    applyFilters();
    updateActiveFiltersIndicator();
    saveFilters();
    
    // Fecha dropdown
    const dropdown = bootstrap.Dropdown.getInstance(document.getElementById('specialistFilterBtn'));
    if (dropdown) dropdown.hide();
}

/**
 * Limpa filtro de projeto
 */
function clearProjectFilter() {
    console.log('🧹 Limpando filtro de projeto');
    
    activeFilters.project = null;
    
    // Atualiza UI
    document.getElementById('projectFilterText').textContent = 'Projeto';
    updateProjectFilterDropdown();
    
    // Aplica filtros
    applyFilters();
    updateActiveFiltersIndicator();
    saveFilters();
    
    // Fecha dropdown
    const dropdown = bootstrap.Dropdown.getInstance(document.getElementById('projectFilterBtn'));
    if (dropdown) dropdown.hide();
}

/**
 * Limpa filtro de especialista
 */
function clearSpecialistFilter() {
    console.log('🧹 Limpando filtro de especialista');
    
    activeFilters.specialist = null;
    
    // Atualiza UI
    document.getElementById('specialistFilterText').textContent = 'Especialista';
    updateSpecialistFilterDropdown();
    
    // Aplica filtros
    applyFilters();
    updateActiveFiltersIndicator();
    saveFilters();
    
    // Fecha dropdown
    const dropdown = bootstrap.Dropdown.getInstance(document.getElementById('specialistFilterBtn'));
    if (dropdown) dropdown.hide();
}

/**
 * Aplica filtros ativos às tarefas
 */
function applyFilters() {
    console.log('🔍 Aplicando filtros:', activeFilters);
    
    const allTaskCards = document.querySelectorAll('.sprint-task-card, .backlog-task-card');
    const allSprintCards = document.querySelectorAll('.sprint-card');
    
    // Se não há filtros ativos, mostra todas as tarefas
    if (!activeFilters.project && !activeFilters.specialist) {
        allTaskCards.forEach(card => {
            // Transição suave para mostrar
            if (card.style.display === 'none') {
                card.style.display = '';
                // Pequeno delay para a transição funcionar
                setTimeout(() => {
                    card.style.opacity = '1';
                }, 10);
            } else {
                card.style.display = '';
                card.style.opacity = '1';
            }
            card.classList.remove('task-filtered-out', 'task-filtered-in');
        });
        
        allSprintCards.forEach(card => {
            card.classList.remove('no-visible-tasks');
        });
        
        return;
    }
    
    // Aplica filtros - OCULTA totalmente as tarefas que não passam
    allTaskCards.forEach(card => {
        const taskData = extractTaskDataFromCard(card);
        const shouldShow = passesFilters(taskData);
        
        if (shouldShow) {
            // Mostra a tarefa com transição suave
            if (card.style.display === 'none') {
                card.style.display = '';
                setTimeout(() => {
                    card.style.opacity = '1';
                }, 10);
            } else {
                card.style.display = '';
                card.style.opacity = '1';
            }
            card.classList.add('task-filtered-in');
            card.classList.remove('task-filtered-out');
        } else {
            // Oculta com transição suave
            card.style.opacity = '0';
            setTimeout(() => {
                card.style.display = 'none';
            }, 300); // Aguarda a transição de opacity
            card.classList.add('task-filtered-out');
            card.classList.remove('task-filtered-in');
        }
    });
    
    // Aguarda um pouco para verificar sprints sem tarefas visíveis (após as transições)
    setTimeout(() => {
        allSprintCards.forEach(sprintCard => {
            const visibleTasks = sprintCard.querySelectorAll('.sprint-task-card:not([style*="display: none"]), .backlog-task-card:not([style*="display: none"])');
            
            if (visibleTasks.length === 0) {
                sprintCard.classList.add('no-visible-tasks');
            } else {
                sprintCard.classList.remove('no-visible-tasks');
            }
        });
    }, 350);
}

/**
 * Extrai dados da tarefa do elemento DOM
 */
function extractTaskDataFromCard(taskCard) {
    return {
        projectId: taskCard.dataset.projectId,
        projectName: taskCard.dataset.projectName,
        specialistName: taskCard.dataset.specialistName
    };
}

/**
 * Verifica se uma tarefa passa pelos filtros ativos
 */
function passesFilters(taskData) {
    // Filtro de projeto
    if (activeFilters.project && taskData.projectId !== activeFilters.project) {
        return false;
    }
    
    // Filtro de especialista
    if (activeFilters.specialist && taskData.specialistName !== activeFilters.specialist) {
        return false;
    }
    
    return true;
}

/**
 * Atualiza indicador de filtros ativos
 */
function updateActiveFiltersIndicator() {
    const indicator = document.getElementById('activeFiltersIndicator');
    const hasActiveFilters = activeFilters.project || activeFilters.specialist;
    
    if (hasActiveFilters) {
        indicator.style.display = 'block';
    } else {
        indicator.style.display = 'none';
    }
}

/**
 * Atualiza UI dos filtros
 */
function updateFilterUI() {
    // Atualiza textos dos botões
    if (activeFilters.project) {
        // Busca nome do projeto no Map
        const project = allProjects.get(activeFilters.project);
        if (project) {
            document.getElementById('projectFilterText').textContent = project.name;
        }
    }
    
    if (activeFilters.specialist) {
        document.getElementById('specialistFilterText').textContent = activeFilters.specialist;
    }
    
    updateActiveFiltersIndicator();
}

/**
 * Filtra dropdown de projetos baseado na busca
 */
function filterProjectDropdown() {
    const searchTerm = document.getElementById('projectFilterSearch').value.toLowerCase();
    const items = document.querySelectorAll('.filter-project-item');
    
    items.forEach(item => {
        const projectName = item.querySelector('.project-name').textContent.toLowerCase();
        const projectId = item.querySelector('.project-id').textContent.toLowerCase();
        
        const matches = projectName.includes(searchTerm) || projectId.includes(searchTerm);
        item.parentElement.style.display = matches ? 'block' : 'none';
    });
}

/**
 * Filtra dropdown de especialistas baseado na busca
 */
function filterSpecialistDropdown() {
    const searchTerm = document.getElementById('specialistFilterSearch').value.toLowerCase();
    const items = document.querySelectorAll('.filter-specialist-item');
    
    items.forEach(item => {
        const specialistName = item.querySelector('.specialist-name').textContent.toLowerCase();
        
        const matches = specialistName.includes(searchTerm);
        item.parentElement.style.display = matches ? 'block' : 'none';
    });
}

// === SISTEMA DE CÁLCULO AUTOMÁTICO DE DATAS ===

/**
 * Calcula datas para a sprint selecionada
 * @param {number} sprintId - ID da sprint
 */
async function calculateSelectedSprintDates(sprintId) {
    try {
        console.log(`🗓️ Calculando datas para sprint ${sprintId}...`);
        
        // Encontra a sprint
        const sprint = window.sprintsData?.find(s => s.id === sprintId);
        if (!sprint) {
            throw new Error('Sprint não encontrada');
        }
        
        // Mostra indicador de carregamento
        showToast('Calculando datas das tarefas...', 'info');
        
        // Chama API para calcular datas
        const response = await fetch(`/sprints/api/sprints/${sprintId}/calculate-dates`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `Erro ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            showToast(`Datas calculadas para ${result.tasks_updated} tarefas`, 'success');
            
            // Recarrega sprints para mostrar novas datas
            await loadSprints();
            
            // Atualiza alertas
            await refreshAllAlerts();
            
            console.log(`✅ Datas calculadas com sucesso para sprint ${sprintId}`);
        } else {
            throw new Error(result.error || 'Erro no cálculo');
        }
        
    } catch (error) {
        console.error('❌ Erro ao calcular datas:', error);
        showToast(`Erro ao calcular datas: ${error.message}`, 'error');
    }
}

/**
 * Atualiza todos os alertas de capacidade das sprints
 */
async function refreshAllAlerts() {
    try {
        console.log('🔄 Atualizando alertas de capacidade...');
        
        // Para cada sprint ativa, busca alertas
        const activeSprintIds = window.sprintsData?.filter(s => !s.is_archived).map(s => s.id) || [];
        
        for (const sprintId of activeSprintIds) {
            await updateSprintCapacityAlerts(sprintId);
        }
        
        console.log('✅ Alertas atualizados');
        
    } catch (error) {
        console.error('❌ Erro ao atualizar alertas:', error);
    }
}

/**
 * Atualiza alertas de capacidade para uma sprint específica
 * @param {number} sprintId - ID da sprint
 */
async function updateSprintCapacityAlerts(sprintId) {
    try {
        const response = await fetch(`/sprints/api/sprints/${sprintId}/capacity-alerts`);
        
        if (!response.ok) {
            console.warn(`⚠️ Erro ao buscar alertas para sprint ${sprintId}`);
            return;
        }
        
        const result = await response.json();
        
        if (result.success && result.alerts) {
            updateAlertsBadge(sprintId, result.alerts);
        }
        
    } catch (error) {
        console.warn('⚠️ Erro ao buscar alertas:', error);
    }
}

/**
 * Atualiza badge de alertas no menu de análises
 * @param {number} sprintId - ID da sprint
 * @param {Object} alerts - Objeto com alertas
 */
function updateAlertsBadge(sprintId, alerts) {
    // Conta total de alertas
    let totalAlerts = 0;
    
    if (alerts.capacity_warnings) totalAlerts += alerts.capacity_warnings.length;
    if (alerts.overload_warnings) totalAlerts += alerts.overload_warnings.length;
    if (alerts.date_conflicts) totalAlerts += alerts.date_conflicts.length;
    
    // Atualiza badge no menu de análises (se existir)
    const analysisBadge = document.querySelector(`[data-sprint-id="${sprintId}"] .analysis-alerts-badge`);
    if (analysisBadge) {
        if (totalAlerts > 0) {
            analysisBadge.textContent = totalAlerts;
            analysisBadge.style.display = 'inline-block';
            analysisBadge.className = `analysis-alerts-badge badge ${getAlertBadgeClass(alerts)}`;
        } else {
            analysisBadge.style.display = 'none';
        }
    }
}

/**
 * Retorna classe CSS apropriada para badge de alertas
 * @param {Object} alerts - Objeto com alertas
 * @returns {string} Classe CSS
 */
function getAlertBadgeClass(alerts) {
    if (alerts.overload_warnings?.length > 0 || alerts.date_conflicts?.length > 0) {
        return 'bg-danger'; // Crítico
    } else if (alerts.capacity_warnings?.length > 0) {
        return 'bg-warning'; // Aviso
    }
    return 'bg-success'; // OK
}

/**
 * Mostra modal para cálculo em lote
 */
function showBatchCalculationModal() {
    console.log('📋 Abrindo modal de cálculo em lote...');
    
    // Verifica se há sprints ativas
    const activeSprints = window.sprintsData?.filter(s => !s.is_archived) || [];
    
    if (activeSprints.length === 0) {
        showToast('Nenhuma sprint ativa encontrada', 'warning');
        return;
    }
    
    // Cria modal dinamicamente
    const modalHtml = `
        <div class="modal fade" id="batchCalculationModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="bi bi-calculator me-2"></i>Cálculo em Lote
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p>Selecione as sprints para calcular as datas automaticamente:</p>
                        
                        <div class="form-check mb-2">
                            <input class="form-check-input" type="checkbox" id="selectAllSprints">
                            <label class="form-check-label fw-bold" for="selectAllSprints">
                                Selecionar Todas
                            </label>
                        </div>
                        
                        <hr>
                        
                        ${activeSprints.map(sprint => `
                            <div class="form-check mb-2">
                                <input class="form-check-input sprint-checkbox" type="checkbox" 
                                       id="sprint_${sprint.id}" value="${sprint.id}">
                                <label class="form-check-label" for="sprint_${sprint.id}">
                                    ${sprint.name}
                                    <small class="text-muted">(${sprint.tasks?.length || 0} tarefas)</small>
                                </label>
                            </div>
                        `).join('')}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                        <button type="button" class="btn btn-primary" onclick="executeBatchCalculation()">
                            <i class="bi bi-play-fill me-1"></i>Calcular Datas
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove modal anterior se existir
    const existingModal = document.getElementById('batchCalculationModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Adiciona ao DOM
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Configura eventos
    document.getElementById('selectAllSprints').addEventListener('change', function() {
        const checkboxes = document.querySelectorAll('.sprint-checkbox');
        checkboxes.forEach(cb => cb.checked = this.checked);
    });
    
    // Mostra modal
    const modal = new bootstrap.Modal(document.getElementById('batchCalculationModal'));
    modal.show();
}

/**
 * Executa cálculo em lote para sprints selecionadas
 */
async function executeBatchCalculation() {
    try {
        // Pega sprints selecionadas
        const selectedSprints = Array.from(document.querySelectorAll('.sprint-checkbox:checked'))
            .map(cb => parseInt(cb.value));
        
        if (selectedSprints.length === 0) {
            showToast('Selecione pelo menos uma sprint', 'warning');
            return;
        }
        
        console.log(`🚀 Executando cálculo em lote para ${selectedSprints.length} sprints...`);
        
        // Fecha modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('batchCalculationModal'));
        modal.hide();
        
        // Mostra progresso
        showToast(`Calculando datas para ${selectedSprints.length} sprints...`, 'info');
        
        // Chama API para cálculo em lote
        const response = await fetch('/sprints/api/sprints/batch-calculate-dates', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sprint_ids: selectedSprints })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `Erro ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            const totalTasks = result.results.reduce((sum, r) => sum + r.tasks_updated, 0);
            showToast(`Cálculo concluído! ${totalTasks} tarefas atualizadas`, 'success');
            
            // Recarrega dados
            await Promise.all([
                loadSprints(),
                refreshAllAlerts()
            ]);
            
            console.log(`✅ Cálculo em lote concluído`);
        } else {
            throw new Error(result.error || 'Erro no cálculo em lote');
        }
        
    } catch (error) {
        console.error('❌ Erro no cálculo em lote:', error);
        showToast(`Erro no cálculo em lote: ${error.message}`, 'error');
    }
}

// Expõe funções globalmente
window.calculateSelectedSprintDates = calculateSelectedSprintDates;
window.refreshAllAlerts = refreshAllAlerts;
window.showBatchCalculationModal = showBatchCalculationModal;
window.executeBatchCalculation = executeBatchCalculation;

console.log('✅ Funções de cálculo de datas carregadas');

/**
 * Calcula datas para a sprint atualmente selecionada no menu de análises
 */
async function calculateCurrentSprintDates() {
    try {
        // Verifica se há uma sprint selecionada (primeira sprint ativa por padrão)
        const activeSprintCards = document.querySelectorAll('.sprint-card:not([data-archived="true"])');
        
        if (activeSprintCards.length === 0) {
            showToast('Nenhuma sprint ativa encontrada', 'warning');
            return;
        }
        
        // Pega a primeira sprint ativa ou a que tem mais tarefas
        let targetSprintId;
        let maxTasks = 0;
        
        activeSprintCards.forEach(card => {
            const sprintId = parseInt(card.dataset.sprintId);
            const taskCount = card.querySelectorAll('.sprint-task-card').length;
            
            if (taskCount > maxTasks) {
                maxTasks = taskCount;
                targetSprintId = sprintId;
            }
        });
        
        // Se não achou nenhuma com tarefas, pega a primeira
        if (!targetSprintId && activeSprintCards.length > 0) {
            targetSprintId = parseInt(activeSprintCards[0].dataset.sprintId);
        }
        
        if (!targetSprintId) {
            showToast('Não foi possível identificar uma sprint para calcular', 'warning');
            return;
        }
        
        console.log(`🎯 Calculando datas para sprint ${targetSprintId} (sprint com mais tarefas)`);
        
        // Chama a função principal
        await calculateSelectedSprintDates(targetSprintId);
        
    } catch (error) {
        console.error('❌ Erro ao identificar sprint para cálculo:', error);
        showToast(`Erro: ${error.message}`, 'error');
    }
}

// Expõe funções globalmente
window.calculateSelectedSprintDates = calculateSelectedSprintDates;
window.calculateCurrentSprintDates = calculateCurrentSprintDates;
window.refreshAllAlerts = refreshAllAlerts;
window.showBatchCalculationModal = showBatchCalculationModal;
window.executeBatchCalculation = executeBatchCalculation;

// === SISTEMA DE CLONAGEM DE TAREFAS ===

/**
 * Clona uma tarefa da sprint para o backlog
 * @param {number} taskId - ID da tarefa a ser clonada
 */
async function cloneTask(taskId) {
    try {
        console.log(`🔄 Iniciando clonagem da tarefa ${taskId}...`);
        
        // Confirmação do usuário
        const confirmClone = confirm(
            'Deseja clonar esta tarefa?\n\n' +
            'A tarefa clonada será criada na MESMA SPRINT da tarefa original, ' +
            'permitindo "quebrar" a tarefa em partes menores.'
        );
        
        if (!confirmClone) {
            console.log('🚫 Clonagem cancelada pelo usuário');
            return;
        }
        
        // Mostra feedback visual
        showToast('Clonando tarefa...', 'info');
        
        // Chama API para clonar
        const response = await fetch(`/sprints/api/sprints/tasks/${taskId}/clone`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `Erro ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            // Feedback de sucesso
            let message = `Tarefa clonada com sucesso na Sprint "${result.added_to_sprint}"!`;
            
            showToast(message, 'success');
            
            // Recarrega dados para mostrar as alterações
            await Promise.all([
                loadSprints(),
                loadBacklogTasks(),
                loadGenericTasks()
            ]);
            
            console.log(`✅ Tarefa ${taskId} clonada com sucesso. Nova tarefa: ${result.cloned_task.id}`);
        } else {
            throw new Error(result.error || 'Erro desconhecido na clonagem');
        }
        
    } catch (error) {
        console.error('❌ Erro ao clonar tarefa:', error);
        showToast(`Erro ao clonar tarefa: ${error.message}`, 'error');
    }
}

// Expõe funções globalmente
window.calculateSelectedSprintDates = calculateSelectedSprintDates;
window.calculateCurrentSprintDates = calculateCurrentSprintDates;
window.refreshAllAlerts = refreshAllAlerts;
window.showBatchCalculationModal = showBatchCalculationModal;
window.executeBatchCalculation = executeBatchCalculation;
window.cloneTask = cloneTask;
window.selectSprintForAnalysis = selectSprintForAnalysis;
window.updateAnalysisButtons = updateAnalysisButtons;

console.log('✅ Funções de clonagem de tarefas carregadas');

/**
 * Atualiza estado dos botões de análise baseado nas sprints carregadas
 */
function updateAnalysisButtons() {
    const calculateDatesBtn = document.getElementById('calculateDatesBtn');
    const alertsMenuText = document.getElementById('alertsMenuText');
    
    if (!calculateDatesBtn || !alertsMenuText) return;
    
    // Verifica se há sprints ativas carregadas
    const activeSprintCards = document.querySelectorAll('.sprint-card:not([data-archived="true"])');
    const hasActiveSprints = activeSprintCards.length > 0;
    
    if (hasActiveSprints) {
        // Habilita botão e atualiza texto
        calculateDatesBtn.disabled = false;
        calculateDatesBtn.classList.remove('btn-secondary');
        calculateDatesBtn.classList.add('btn-primary');
        alertsMenuText.textContent = `Análises (${activeSprintCards.length})`;
        
        console.log(`✅ Botões de análise habilitados - ${activeSprintCards.length} sprints ativas`);
    } else {
        // Desabilita botão e atualiza texto
        calculateDatesBtn.disabled = true;
        calculateDatesBtn.classList.remove('btn-primary');
        calculateDatesBtn.classList.add('btn-secondary');
        alertsMenuText.textContent = 'Análises';
        
        console.log('⚠️ Botões de análise desabilitados - nenhuma sprint ativa');
    }
    
    // ✅ NOVA FUNÇÃO: Atualiza conteúdo do menu
    updateAnalysisMenu();
}

/**
 * Atualiza o conteúdo do menu de análises
 */
function updateAnalysisMenu() {
    const defaultMessage = document.getElementById('defaultAnalysisMessage');
    const analysisList = document.getElementById('sprintAnalysisList');
    
    if (!defaultMessage || !analysisList) return;
    
    // Verifica se há dados de sprints carregados
    if (!window.sprintsData || window.sprintsData.length === 0) {
        defaultMessage.style.display = 'block';
        analysisList.style.display = 'none';
        defaultMessage.innerHTML = `
            <i class="bi bi-exclamation-triangle"></i>
            <p class="mb-0 small">Nenhuma sprint encontrada</p>
        `;
        return;
    }
    
    // Filtra apenas sprints ativas
    const activeSprints = window.sprintsData.filter(sprint => !sprint.is_archived);
    
    if (activeSprints.length === 0) {
        defaultMessage.style.display = 'block';
        analysisList.style.display = 'none';
        defaultMessage.innerHTML = `
            <i class="bi bi-archive"></i>
            <p class="mb-0 small">Todas as sprints estão arquivadas</p>
        `;
        return;
    }
    
    // Mostra lista de sprints
    defaultMessage.style.display = 'none';
    analysisList.style.display = 'block';
    
    // Gera HTML das sprints
    analysisList.innerHTML = activeSprints.map(sprint => {
        const taskCount = sprint.tasks ? sprint.tasks.length : 0;
        const totalHours = sprint.tasks ? sprint.tasks.reduce((sum, task) => sum + (task.estimated_effort || 0), 0) : 0;
        
        return `
            <div class="sprint-analysis-item mb-2 p-2 border rounded" style="cursor: pointer;"
                 onclick="selectSprintForAnalysis(${sprint.id})">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <strong class="text-primary">${escapeHtml(sprint.name)}</strong>
                        <div class="small text-muted">
                            ${taskCount} tarefas • ${totalHours}h estimadas
                        </div>
                    </div>
                    <button class="btn btn-sm btn-outline-primary" 
                            onclick="event.stopPropagation(); calculateSelectedSprintDates(${sprint.id})">
                        <i class="bi bi-calculator"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');
    
    console.log(`✅ Menu de análises atualizado com ${activeSprints.length} sprints`);
}

/**
 * Seleciona uma sprint para análise detalhada
 * @param {number} sprintId - ID da sprint
 */
function selectSprintForAnalysis(sprintId) {
    console.log(`🎯 Sprint ${sprintId} selecionada para análise`);
    
    // Podemos expandir esta função no futuro para mostrar análises detalhadas
    showToast(`Sprint selecionada! Use o botão de calculadora para calcular datas.`, 'info');
}

// === FILTRO AUTOMÁTICO POR PROJETO (CENTRAL DE COMANDO PMO) ===

/**
 * Detecta e aplica filtro automático baseado nos parâmetros da URL
 */
function checkAndApplyAutoFilter() {
    const urlParams = new URLSearchParams(window.location.search);
    const autoFilterProject = urlParams.get('auto_filter_project');
    const autoFilterProjectName = urlParams.get('auto_filter_project_name');
    
    if (autoFilterProject) {
        console.log(`🎯 Detectado filtro automático para projeto: ${autoFilterProject} - ${autoFilterProjectName}`);
        
        // Aguarda um pouco para garantir que os dados foram carregados
        setTimeout(() => {
            applyAutoProjectFilter(autoFilterProject, decodeURIComponent(autoFilterProjectName || ''));
        }, 1500);
        
        // Remove os parâmetros da URL para deixar ela limpa (após um delay)
        setTimeout(() => {
            const newUrl = new URL(window.location);
            newUrl.searchParams.delete('auto_filter_project');
            newUrl.searchParams.delete('auto_filter_project_name');
            
            // Atualiza a URL sem recarregar a página
            window.history.replaceState({}, document.title, newUrl.toString());
        }, 3000);
    }
}

/**
 * Aplica filtro automático de projeto
 */
function applyAutoProjectFilter(projectId, projectName) {
    console.log(`🔄 Aplicando filtro automático: ${projectId} - ${projectName}`);
    
    // Verifica se o projeto existe na lista
    if (!allProjects.has(projectId)) {
        console.warn(`⚠️ Projeto ${projectId} não encontrado na lista de projetos`);
        
        // Mostra toast informativo
        showToast(`Projeto "${projectName}" não foi encontrado nas sprints atuais`, 'warning');
        return;
    }
    
    // Aplica o filtro usando a função existente
    selectProjectFilter(projectId, projectName);
    
    // Mostra toast de confirmação com destaque
    showToast(`🎯 Visualizando apenas sprints do projeto "${projectName}"`, 'success');
    
    // Destaque visual no filtro aplicado
    highlightActiveFilter();
    
    console.log(`✅ Filtro automático aplicado com sucesso`);
}

/**
 * Destaca visualmente que há um filtro ativo
 */
function highlightActiveFilter() {
    const projectFilterBtn = document.getElementById('projectFilterBtn');
    if (projectFilterBtn) {
        // Adiciona destaque visual temporário
        projectFilterBtn.classList.add('btn-warning');
        projectFilterBtn.style.boxShadow = '0 0 10px rgba(255, 193, 7, 0.5)';
        
        // Remove destaque após alguns segundos
        setTimeout(() => {
            projectFilterBtn.classList.remove('btn-warning');
            projectFilterBtn.style.boxShadow = '';
        }, 4000);
    }
    
    // Adiciona destaque no indicador de filtros ativos
    const activeFiltersIndicator = document.getElementById('activeFiltersIndicator');
    if (activeFiltersIndicator) {
        activeFiltersIndicator.style.animation = 'pulse 1s infinite';
        
        setTimeout(() => {
            activeFiltersIndicator.style.animation = '';
        }, 3000);
    }
}

// Adiciona CSS para animação de pulso se não existir
if (!document.getElementById('auto-filter-styles')) {
    const style = document.createElement('style');
    style.id = 'auto-filter-styles';
    style.textContent = `
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
    `;
    document.head.appendChild(style);
}

// A verificação de filtro automático será integrada à inicialização existente
// Isso será chamado após o carregamento completo dos dados