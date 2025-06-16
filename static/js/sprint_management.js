/**
 * Sprint Management JavaScript
 * Gerenciamento de Sprints - Funcionalidades principais
 */

// Variáveis globais
let editingSprintId = null;
let sortableInstances = [];
let popoverInstances = {};

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
    
    // Se houver uma função global de toast, usa ela
    if (typeof window.showToast === 'function') {
        window.showToast(message, type);
    } else {
        // Fallback para alert
        if (type === 'error') {
            alert(`Erro: ${message}`);
        }
    }
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
        
        renderSprints(sprints);
        initializeSortable();
        initializePopovers();
        
    } catch (error) {
        console.error('❌ Erro ao carregar sprints:', error);
        renderSprintError(`Erro ao carregar sprints: ${error.message}`);
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
    
    // Gera conteúdo do popover
    let popoverContent = Object.entries(hoursBySpecialist)
        .map(([name, allocatedHours]) => {
            const remainingHours = Math.max(0, 40 - allocatedHours);
            const utilizationPercent = (allocatedHours / 40) * 100;
            
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
    const isCompleted = task.column_identifier === 'concluido';
    const fullTaskId = `${projectPart}-${columnPart}-${task.id}`;
    
    return `
        <div class="backlog-task-card sprint-task-card" 
             data-task-id="${task.id}"
             data-estimated-hours="${task.estimated_effort || 0}"
             data-specialist-name="${escapeHtml(task.specialist_name || '')}"
             data-project-id="${task.project_id || ''}"
             data-backlog-id="${task.backlog_id || ''}">
            <div class="task-header">
                <div class="task-id-badge">${escapeHtml(fullTaskId)}</div>
                <span class="task-priority-badge ${getPriorityClass(task.priority)}">${escapeHtml(task.priority || 'Média')}</span>
            </div>
            <div class="task-content">
                <div class="task-title">${escapeHtml(task.title || 'Sem título')}</div>
                ${task.project_name ? `<div class="task-project">${escapeHtml(task.project_name)}</div>` : ''}
                ${task.specialist_name ? `<div class="task-specialist">${escapeHtml(task.specialist_name)}</div>` : ''}
                ${task.estimated_effort ? `<div class="task-hours">${task.estimated_effort}h</div>` : ''}
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
    
    return `
        <div class="project-group mb-3">
            <div class="project-header" onclick="toggleProjectTasks(this)">
                <div class="d-flex justify-content-between align-items-center">
                    <div class="project-info">
                        <strong>${escapeHtml(displayName)}</strong>
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
    
    tasks.forEach(task => {
        const hours = parseFloat(task.dataset.estimatedHours) || 0;
        totalHours += hours;
    });
    
    const hoursSpan = sprintCard.querySelector('.sprint-total-hours');
    if (hoursSpan) {
        hoursSpan.innerHTML = `<i class="bi bi-clock"></i> ${totalHours.toFixed(1)}h`;
    }
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
    const deleteButton = event.target.closest('.delete-btn');
    
    if (editButton) {
        const sprintId = editButton.dataset.id;
        openEditModal(sprintId);
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
    } else {
        // Modo criação
        modalTitle.textContent = 'Nova Tarefa Genérica';
        delete form.dataset.editingId;
    }
    
    // Mostra o modal
    const bootstrapModal = new bootstrap.Modal(modal);
    bootstrapModal.show();
};

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
        
        // Fecha o modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('genericTaskModal'));
        if (modal) modal.hide();
        
        // Recarrega tarefas genéricas
        loadGenericTasks();
        showToast(editingId ? 'Tarefa atualizada com sucesso!' : 'Tarefa criada com sucesso!', 'success');
        
    } catch (error) {
        console.error('❌ Erro ao salvar tarefa genérica:', error);
        showToast(`Erro ao salvar tarefa: ${error.message}`, 'error');
    }
}

console.log('✅ Sprint Management JavaScript carregado'); 