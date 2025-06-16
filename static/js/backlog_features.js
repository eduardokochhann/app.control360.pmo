/**
 * Script para funcionalidades avançadas do Backlog (Riscos, Marcos, Timeline, Notas).
 * Estrutura modular para evitar conflitos de escopo e garantir inicialização correta.
 * Autor: Assistente Gemini
 * Data: 14 de Junho de 2025
 */
function initializeProjectTools() {
    // --- Variáveis de Estado e Elementos do DOM ---
    const projectId = window.boardData.projectId;
    let currentBacklogId = window.boardData.backlogId;

    const projectToolsSection = document.getElementById('projectToolsSection');
    const toggleBtn = document.querySelector('a[onclick="toggleProjectTools()"]');
    const toolsChevron = toggleBtn ? toggleBtn.querySelector('i') : null;
    
    // Modais e Forms
    const riskModal = new bootstrap.Modal(document.getElementById('riskModal'));
    const riskForm = document.getElementById('riskForm');
    const milestoneModal = new bootstrap.Modal(document.getElementById('milestoneModal'));
    const milestoneForm = document.getElementById('milestoneForm');
    const noteModal = new bootstrap.Modal(document.getElementById('noteModal'));
    const noteForm = document.getElementById('noteForm');

    // Abas
    const tabs = {
        risks: document.querySelector('#pills-risks-tab'),
        milestones: document.querySelector('#pills-milestones-tab'),
        timeline: document.querySelector('#pills-timeline-tab'),
        notes: document.querySelector('#pills-notes-tab')
    };

    // --- Funções de Inicialização ---

    // Função principal de inicialização do módulo
    function init() {
        if (!projectId) {
            console.error("ID do Projeto não encontrado. As ferramentas não podem ser inicializadas.");
            return;
        }
        setupEventListeners();
        console.log("Ferramentas do Projeto prontas.");

        // Se o backlogId não for passado diretamente, busca os detalhes
        if (!currentBacklogId) {
            console.log("Backlog ID não encontrado, buscando detalhes do projeto...");
            fetchProjectDetails();
        } else {
            console.log(`Backlog ID definido: ${currentBacklogId}. Carregando todos os dados.`);
            loadAllData();
        }
    }

    // Busca detalhes do projeto para obter o backlog_id
    async function fetchProjectDetails() {
        try {
            const response = await fetch(`/backlog/api/projects/${projectId}/details`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            
            if (data.backlog_id) {
                currentBacklogId = data.backlog_id;
                window.boardData.backlogId = data.backlog_id; // Atualiza globalmente
                console.log(`Backlog ID obtido: ${currentBacklogId}`);
                loadAllData();
            } else {
                throw new Error("backlog_id não encontrado na resposta da API.");
            }
        } catch (error) {
            console.error("Erro ao buscar detalhes do projeto:", error);
            showToast('Erro ao carregar dados do projeto.', 'error');
        }
    }
    
    // --- Configuração de Event Listeners ---
    function setupEventListeners() {
        // Botão para mostrar/esconder as ferramentas - usando onclick no HTML

        // Salvar formulários
        riskForm?.addEventListener('submit', event => { event.preventDefault(); saveRisk(); });
        milestoneForm?.addEventListener('submit', event => { event.preventDefault(); saveMilestone(); });
        noteForm?.addEventListener('submit', event => { event.preventDefault(); saveNote(); });

        // Recarregar dados quando a aba se torna visível
        Object.values(tabs).forEach(tab => {
            tab?.addEventListener('shown.bs.tab', (event) => {
                const targetId = event.target.getAttribute('aria-controls');
                console.log(`Aba ${targetId} ativada. Recarregando dados...`);
                switch(targetId) {
                    case 'pills-risks': loadRisks(); break;
                    case 'pills-milestones': loadMilestones(); break;
                    case 'pills-timeline': loadTimeline(); break;
                    case 'pills-notes': loadNotes(); break;
                }
            });
        });
    }

    // --- Funções Principais (Carregamento de Dados) ---
    
    function loadAllData() {
        if (!currentBacklogId) {
            console.warn("Aguardando Backlog ID para carregar os dados.");
            return;
        }
        console.log("Carregando todos os dados para o backlog:", currentBacklogId);
        loadRisks();
        loadMilestones();
        loadTimeline();
        loadNotes();
    }

    // --- Funções de Riscos ---

    async function loadRisks() {
        if (!currentBacklogId) return;
        
        try {
            const response = await fetch(`/backlog/api/backlogs/${currentBacklogId}/risks`);
            if (!response.ok) throw new Error('Erro ao carregar riscos');
            
            const risks = await response.json();
            renderRisks(risks);
            updateTabCount('risks', risks.length);
            
        } catch (error) {
            console.error('Erro ao carregar riscos:', error);
            document.getElementById('risksContainer').innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i> Erro ao carregar riscos: ${error.message}
                </div>
            `;
        }
    }

    function renderRisks(risks) {
        const container = document.getElementById('risksContainer');
        if (!container) return;

        if (risks.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="bi bi-exclamation-triangle fs-1"></i>
                    <p>Nenhum risco cadastrado</p>
                </div>
            `;
            return;
        }

        const risksHtml = risks.map(risk => `
            <div class="card mb-3 risk-card" data-risk-id="${risk.id}">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <h6 class="card-title mb-1">${risk.title}</h6>
                            ${risk.description ? `<p class="card-text text-muted small">${risk.description}</p>` : ''}
                            
                            <div class="d-flex gap-3 mt-2 flex-wrap">
                                <div>
                                    <small class="text-muted d-block" style="font-size: 0.75em;">Prob.</small>
                                    <span class="badge bg-${getRiskColor(risk.probability.key)}">${risk.probability.value}</span>
                                </div>
                                <div>
                                    <small class="text-muted d-block" style="font-size: 0.75em;">Impacto</small>
                                    <span class="badge bg-${getRiskColor(risk.impact.key)}">${risk.impact.value}</span>
                                </div>
                                <div>
                                    <small class="text-muted d-block" style="font-size: 0.75em;">Status</small>
                                    <span class="badge bg-${getStatusColor(risk.status.key)}">${risk.status.value}</span>
                                </div>
                            </div>
                        </div>
                        <div class="btn-group-vertical ms-2">
                            <button class="btn btn-sm btn-outline-primary" onclick="editRisk(${risk.id})">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger" onclick="deleteRisk(${risk.id})">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');

        container.innerHTML = risksHtml;
    }

    function openRiskModal(risk = null) {
        riskForm.reset();
        const modalTitle = document.getElementById('riskModalTitle');
        const deleteBtn = document.getElementById('deleteRiskBtn');

        if (risk) {
            modalTitle.textContent = 'Editar Risco';
            deleteBtn.style.display = 'block';
            
            document.getElementById('riskId').value = risk.id;
            document.getElementById('riskTitle').value = risk.title || '';
            document.getElementById('riskDescription').value = risk.description || '';
            document.getElementById('riskProbability').value = risk.probability.key || 'MEDIUM';
            document.getElementById('riskImpact').value = risk.impact.key || 'MEDIUM';
            document.getElementById('riskStatus').value = risk.status.key || 'IDENTIFIED';
            document.getElementById('riskMitigationPlan').value = risk.mitigation_plan || '';
        } else {
            modalTitle.textContent = 'Novo Risco';
            deleteBtn.style.display = 'none';
            document.getElementById('riskId').value = '';
            // Limpa os campos para um novo risco
            document.getElementById('riskTitle').value = '';
            document.getElementById('riskDescription').value = '';
            // Define valores padrão corretos para novo risco
            document.getElementById('riskProbability').value = 'MEDIUM';
            document.getElementById('riskImpact').value = 'MEDIUM';
            document.getElementById('riskStatus').value = 'IDENTIFIED';
        }
        
        riskModal.show();
    }

    async function saveRisk() {
        const riskId = document.getElementById('riskId').value;
        const data = {
            title: document.getElementById('riskTitle').value,
            description: document.getElementById('riskDescription').value,
            probability: document.getElementById('riskProbability').value,
            impact: document.getElementById('riskImpact').value,
            status: document.getElementById('riskStatus').value,
            mitigation_plan: document.getElementById('riskMitigationPlan').value,
            backlog_id: currentBacklogId
        };

        const url = riskId ? `/backlog/api/risks/${riskId}` : '/backlog/api/risks';
        const method = riskId ? 'PUT' : 'POST';

        try {
            const response = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                // Tenta extrair uma mensagem de erro JSON, se falhar, usa o status
                let errorData;
                try {
                    errorData = await response.json();
                } catch (e) {
                    throw new Error(response.statusText);
                }
                throw new Error(errorData.description || errorData.message || 'Erro desconhecido');
            }
            
            riskModal.hide();
            showToast('Risco salvo com sucesso!', 'success');
            loadRisks();
            
        } catch (error) {
            console.error('Erro ao salvar risco:', error);
            showToast('Erro ao salvar risco: ' + error.message, 'error');
        }
    }

    async function editRisk(riskId) {
        try {
            const response = await fetch(`/backlog/api/risks/${riskId}`);
            if (!response.ok) throw new Error('Erro ao carregar risco');
            
            const risk = await response.json();
            openRiskModal(risk);
            
        } catch (error) {
            console.error('Erro ao carregar risco:', error);
            showToast('Erro ao carregar risco: ' + error.message, 'error');
        }
    }

    async function deleteRisk(riskId) {
        if (!confirm('Tem certeza que deseja excluir este risco?')) return;

        try {
            const response = await fetch(`/backlog/api/risks/${riskId}`, {
                method: 'DELETE'
            });

            if (!response.ok) throw new Error('Erro ao excluir risco');
            
            showToast('Risco excluído com sucesso!', 'success');
            loadRisks();
            
        } catch (error) {
            console.error('Erro ao excluir risco:', error);
            showToast('Erro ao excluir risco: ' + error.message, 'error');
        }
    }

    // --- Funções de Marcos ---

    async function loadMilestones() {
        if (!currentBacklogId) return;
        
        try {
            const response = await fetch(`/backlog/api/backlogs/${currentBacklogId}/milestones`);
            if (!response.ok) throw new Error('Erro ao carregar marcos');
            
            const milestones = await response.json();
            renderMilestones(milestones);
            updateTabCount('milestones', milestones.length);
            
        } catch (error) {
            console.error('Erro ao carregar marcos:', error);
            document.getElementById('milestonesContainer').innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-flag"></i> Erro ao carregar marcos: ${error.message}
                </div>
            `;
        }
    }

    function renderMilestones(milestones) {
        const container = document.getElementById('milestonesContainer');
        if (!container) return;

        if (milestones.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="bi bi-flag fs-1"></i>
                    <p>Nenhum marco cadastrado</p>
                </div>
            `;
            return;
        }

        const milestonesHtml = milestones.map(milestone => `
            <div class="card mb-3 milestone-card" data-milestone-id="${milestone.id}">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <h6 class="card-title mb-1">${milestone.is_checkpoint ? '<i class="bi bi-star-fill text-warning"></i> ' : ''}${milestone.name}</h6>
                            ${milestone.description ? `<p class="card-text text-muted small">${milestone.description}</p>` : ''}
                            
                            <div class="d-flex align-items-center gap-3 mt-2 flex-wrap">
                                <span class="badge bg-light text-dark">
                                    <i class="bi bi-calendar-event"></i> Planejado: ${formatDate(milestone.planned_date)}
                                </span>
                                ${milestone.actual_date ? `
                                <span class="badge bg-light text-dark">
                                    <i class="bi bi-calendar-check"></i> Real: ${formatDate(milestone.actual_date)}
                                </span>` : ''}
                                <span class="badge bg-${getStatusColor(milestone.status.key)}">${milestone.status.value}</span>
                                <span class="badge bg-${getCriticalityColor(milestone.criticality.key)}">${milestone.criticality.value}</span>
                            </div>
                        </div>
                        <div class="btn-group-vertical ms-2">
                             <button class="btn btn-sm btn-outline-primary" onclick="editMilestone(${milestone.id})">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger" onclick="deleteMilestone(${milestone.id})">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');

        container.innerHTML = milestonesHtml;
    }

    function openMilestoneModal(milestone = null) {
        milestoneForm.reset();
        const modalTitle = document.getElementById('milestoneModalTitle');
        const deleteBtn = document.getElementById('deleteMilestoneBtn');

        if (milestone) {
            modalTitle.textContent = 'Editar Marco';
            deleteBtn.style.display = 'block';
            
            document.getElementById('milestoneId').value = milestone.id;
            document.getElementById('milestoneName').value = milestone.name || '';
            document.getElementById('milestoneDescription').value = milestone.description || '';
            document.getElementById('milestonePlannedDate').value = milestone.planned_date || '';
            document.getElementById('milestoneActualDate').value = milestone.actual_date || '';
            document.getElementById('milestoneStatus').value = milestone.status.key || 'PENDING';
            document.getElementById('milestoneCriticality').value = milestone.criticality.key || 'MEDIUM';
            document.getElementById('milestoneIsCheckpoint').checked = milestone.is_checkpoint || false;

        } else {
            modalTitle.textContent = 'Novo Marco';
            deleteBtn.style.display = 'none';
            document.getElementById('milestoneId').value = '';
            document.getElementById('milestoneName').value = '';
            document.getElementById('milestoneDescription').value = '';
            document.getElementById('milestonePlannedDate').value = '';
            document.getElementById('milestoneActualDate').value = '';
            document.getElementById('milestoneStatus').value = 'PENDING';
            document.getElementById('milestoneCriticality').value = 'MEDIUM';
            document.getElementById('milestoneIsCheckpoint').checked = false;
        }

        milestoneModal.show();
    }

    async function saveMilestone() {
        const milestoneId = document.getElementById('milestoneId').value;
        const data = {
            name: document.getElementById('milestoneName').value,
            description: document.getElementById('milestoneDescription').value,
            planned_date: document.getElementById('milestonePlannedDate').value,
            actual_date: document.getElementById('milestoneActualDate').value || null,
            status: document.getElementById('milestoneStatus').value,
            criticality: document.getElementById('milestoneCriticality').value,
            is_checkpoint: document.getElementById('milestoneIsCheckpoint').checked,
            backlog_id: currentBacklogId
        };

        const url = milestoneId ? `/backlog/api/milestones/${milestoneId}` : '/backlog/api/milestones';
        const method = milestoneId ? 'PUT' : 'POST';

        try {
            const response = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Erro ao salvar marco');
            }
            
            milestoneModal.hide();
            showToast('Marco salvo com sucesso!', 'success');
            loadMilestones();
            
        } catch (error) {
            console.error('Erro ao salvar marco:', error);
            showToast('Erro ao salvar marco: ' + error.message, 'error');
        }
    }

    async function editMilestone(milestoneId) {
        try {
            const response = await fetch(`/backlog/api/milestones/${milestoneId}`);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Erro ao carregar marco');
            }
            
            const milestone = await response.json();
            openMilestoneModal(milestone);
            
        } catch (error) {
            console.error('Erro ao carregar marco:', error);
            showToast('Erro ao carregar marco: ' + error.message, 'error');
        }
    }

    async function deleteMilestone(milestoneId) {
        if (!confirm('Tem certeza que deseja excluir este marco?')) return;

        try {
            const response = await fetch(`/backlog/api/milestones/${milestoneId}`, {
                method: 'DELETE'
            });

            if (!response.ok) throw new Error('Erro ao excluir marco');
            
            showToast('Marco excluído com sucesso!', 'success');
            loadMilestones();
            
        } catch (error) {
            console.error('Erro ao excluir marco:', error);
            showToast('Erro ao excluir marco: ' + error.message, 'error');
        }
    }

    // --- Funções de Timeline ---

    async function loadTimeline() {
        if (!currentBacklogId) return;
        
        const daysBack = document.getElementById('timelineDaysBack')?.value || 7;
        const daysForward = document.getElementById('timelineDaysForward')?.value || 7;
        
        try {
            const response = await fetch(`/backlog/api/backlogs/${currentBacklogId}/timeline-tasks?days_back=${daysBack}&days_forward=${daysForward}`);
            if (!response.ok) throw new Error('Erro ao carregar timeline');
            
            const timelineResponse = await response.json();
            
            // A API retorna um objeto com arrays, vamos converter para um array único
            const timelineEvents = [];
            
            // Adiciona tarefas concluídas
            if (timelineResponse.all_completed && Array.isArray(timelineResponse.all_completed)) {
                timelineResponse.all_completed.forEach(task => {
                    timelineEvents.push({
                        title: task.title,
                        description: task.description || '',
                        date: task.actually_finished_at || task.finished_at,
                        type: 'Concluída'
                    });
                });
            }
            
            // Adiciona próximas tarefas
            if (timelineResponse.upcoming_tasks && Array.isArray(timelineResponse.upcoming_tasks)) {
                timelineResponse.upcoming_tasks.forEach(task => {
                    timelineEvents.push({
                        title: task.title,
                        description: task.description || '',
                        date: task.start_date,
                        type: 'Próxima'
                    });
                });
            }
            
            // Adiciona tarefas iniciadas recentemente
            if (timelineResponse.recently_started && Array.isArray(timelineResponse.recently_started)) {
                timelineResponse.recently_started.forEach(task => {
                    timelineEvents.push({
                        title: task.title,
                        description: task.description || '',
                        date: task.actually_started_at || task.start_date,
                        type: 'Iniciada'
                    });
                });
            }
            
            // Ordena por data
            timelineEvents.sort((a, b) => new Date(b.date) - new Date(a.date));
            
            renderTimeline(timelineEvents);
            
        } catch (error) {
            console.error('Erro ao carregar timeline:', error);
            document.getElementById('timelineContainer').innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-clock-history"></i> Erro ao carregar timeline: ${error.message}
                </div>
            `;
        }
    }

    function renderTimeline(timelineData) {
        const container = document.getElementById('timelineContainer');
        if (!container) return;

        // Verifica se timelineData é um array
        if (!Array.isArray(timelineData)) {
            console.error('Timeline data não é um array:', timelineData);
            container.innerHTML = `
                <div class="alert alert-warning">
                    <i class="bi bi-clock-history"></i> Dados da timeline inválidos
                </div>
            `;
            return;
        }

        if (!timelineData || timelineData.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="bi bi-clock-history fs-1"></i>
                    <p>Nenhum evento na timeline</p>
                </div>
            `;
            return;
        }

        const timelineHtml = timelineData.map(item => `
            <div class="timeline-item mb-3">
                <div class="card">
                    <div class="card-body">
                        <div class="d-flex justify-content-between">
                            <div>
                                <h6 class="card-title">${item.title}</h6>
                                <p class="card-text">${item.description || ''}</p>
                                <small class="text-muted">${formatDateTime(item.date)}</small>
                            </div>
                            <span class="badge bg-${getEventTypeColor(item.type)}">${item.type}</span>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');

        container.innerHTML = timelineHtml;
    }

    // --- Funções de Notas ---

    async function loadNotes() {
        if (!currentBacklogId) return;
        
        try {
            const response = await fetch(`/backlog/api/backlogs/${currentBacklogId}/notes`);
            if (!response.ok) throw new Error('Erro ao carregar notas');
            
            const notes = await response.json();
            renderNotes(notes);
            updateTabCount('notes', notes.length);
            
        } catch (error) {
            console.error('Erro ao carregar notas:', error);
            document.getElementById('notesContainer').innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-sticky"></i> Erro ao carregar notas: ${error.message}
                </div>
            `;
        }
    }

    function renderNotes(notes) {
        const container = document.getElementById('notesContainer');
        if (!container) return;

        if (notes.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="bi bi-sticky fs-1"></i>
                    <p>Nenhuma nota cadastrada</p>
                </div>
            `;
            return;
        }

        const notesHtml = notes.map(note => `
            <div class="card mb-3">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <div class="d-flex gap-2 mb-2">
                                <span class="badge bg-${getCategoryColor(note.category)}">${note.category}</span>
                                <span class="badge bg-${getPriorityColor(note.priority)}">${note.priority}</span>
                                ${note.include_in_report ? '<span class="badge bg-info">Relatório</span>' : ''}
                            </div>
                            <p class="card-text">${note.content}</p>
                            ${note.event_date ? `<small class="text-muted">Data do evento: ${formatDate(note.event_date)}</small>` : ''}
                            ${note.tags && typeof note.tags === 'string' ? `<div class="mt-2">${note.tags.split(',').map(tag => `<span class="badge bg-light text-dark me-1">${tag.trim()}</span>`).join('')}</div>` : ''}
                        </div>
                        <div class="btn-group">
                            <button class="btn btn-sm btn-outline-primary" onclick="editNote(${note.id})">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger" onclick="deleteNote(${note.id})">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');

        container.innerHTML = notesHtml;
    }

    function openNoteModal(note = null) {
        noteForm.reset();
        const modalTitle = document.getElementById('noteModalTitle');
        const deleteBtn = document.getElementById('deleteNoteBtn');

        if (note) {
            modalTitle.textContent = 'Editar Nota';
            deleteBtn.style.display = 'block';
            
            document.getElementById('noteId').value = note.id;
            document.getElementById('noteContent').value = note.content || '';
            document.getElementById('noteCategory').value = note.category || 'general';
            document.getElementById('notePriority').value = note.priority || 'medium';
            document.getElementById('noteEventDate').value = note.event_date || '';
            document.getElementById('noteIncludeInReport').checked = note.include_in_report || false;
            document.getElementById('noteTags').value = note.tags || '';
        } else {
            modalTitle.textContent = 'Nova Nota';
            deleteBtn.style.display = 'none';
            document.getElementById('noteId').value = '';
        }
        
        noteModal.show();
    }

    async function saveNote() {
        const noteId = document.getElementById('noteId').value;
        const data = {
            content: document.getElementById('noteContent').value,
            category: document.getElementById('noteCategory').value,
            priority: document.getElementById('notePriority').value,
            event_date: document.getElementById('noteEventDate').value || null,
            include_in_report: document.getElementById('noteIncludeInReport').checked,
            tags: document.getElementById('noteTags').value,
            backlog_id: currentBacklogId
        };

        const url = noteId ? `/backlog/api/notes/${noteId}` : '/backlog/api/notes';
        const method = noteId ? 'PUT' : 'POST';

        try {
            const response = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || errorData.message || 'Erro ao salvar nota');
            }
            
            noteModal.hide();
            showToast('Nota salva com sucesso!', 'success');
            loadNotes();
            
        } catch (error) {
            console.error('Erro ao salvar nota:', error);
            showToast('Erro ao salvar nota: ' + error.message, 'error');
        }
    }

    async function editNote(noteId) {
        try {
            const response = await fetch(`/backlog/api/notes/${noteId}`);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || errorData.message || 'Erro ao carregar nota');
            }
            
            const note = await response.json();
            openNoteModal(note);
            
        } catch (error) {
            console.error('Erro ao carregar nota:', error);
            showToast('Erro ao carregar nota: ' + error.message, 'error');
        }
    }

    async function deleteNote(noteId) {
        if (!confirm('Tem certeza que deseja excluir esta nota?')) return;

        try {
            const response = await fetch(`/backlog/api/notes/${noteId}`, {
                method: 'DELETE'
            });

            if (!response.ok) throw new Error('Erro ao excluir nota');
            
            showToast('Nota excluída com sucesso!', 'success');
            loadNotes();
            
        } catch (error) {
            console.error('Erro ao excluir nota:', error);
            showToast('Erro ao excluir nota: ' + error.message, 'error');
        }
    }

    // --- Funções Utilitárias ---

    function toggleProjectTools() {
        const isHidden = projectToolsSection.style.display === 'none';
        projectToolsSection.style.display = isHidden ? 'block' : 'none';
        
        if (toolsChevron) {
            toolsChevron.classList.toggle('bi-chevron-down', !isHidden);
            toolsChevron.classList.toggle('bi-chevron-up', isHidden);
        }

        if (isHidden) {
            // Apenas carrega os dados se o painel for aberto e os dados ainda não tiverem sido carregados
            if (currentBacklogId && !tabs.risks.classList.contains('active')) {
                // Ativa a primeira aba e carrega os dados
                const firstTab = new bootstrap.Tab(tabs.risks);
                firstTab.show();
            } else if (currentBacklogId) {
                 loadAllData();
            }
        }
    }

    function updateTabCount(tabName, count) {
        const tabElement = document.getElementById(`pills-${tabName}-tab`);
        if (tabElement) {
            const badge = tabElement.querySelector('.badge');
            if (badge) {
                badge.textContent = count;
            }
        }
    }

    function showToast(message, type = 'info') {
        // Evita recursão infinita - usa função global diferente se disponível
        if (typeof window.globalShowToast === 'function') {
            window.globalShowToast(message, type);
        } else {
            console.log(`[${type.toUpperCase()}] TOAST: ${message}`);
            if (type === 'error') {
                alert(message);
            }
        }
    }

    // Funções auxiliares para cores e formatação
    function getRiskColor(level) {
        switch(level?.toUpperCase()) {
            case 'HIGH': return 'danger';
            case 'MEDIUM': return 'warning';
            case 'LOW': return 'success';
            default: return 'secondary';
        }
    }

    function getStatusColor(status) {
        switch(status?.toUpperCase()) {
            case 'COMPLETED': case 'RESOLVED': return 'success';
            case 'IN_PROGRESS': case 'MITIGATED': return 'warning';
            case 'PENDING': case 'IDENTIFIED': return 'info';
            case 'DELAYED': case 'ACTIVE': return 'danger';
            case 'ACCEPTED': return 'primary';
            default: return 'secondary';
        }
    }

    function getCriticalityColor(criticality) {
        return getRiskColor(criticality);
    }

    function getPriorityColor(priority) {
        switch(priority?.toLowerCase()) {
            case 'high': return 'danger';
            case 'medium': return 'warning';
            case 'low': return 'success';
            default: return 'secondary';
        }
    }

    function getCategoryColor(category) {
        switch(category?.toLowerCase()) {
            case 'issue': return 'danger';
            case 'decision': return 'warning';
            case 'progress': return 'success';
            case 'meeting': return 'info';
            default: return 'primary';
        }
    }

    function getEventTypeColor(type) {
        switch(type?.toLowerCase()) {
            case 'milestone': return 'success';
            case 'risk': return 'danger';
            case 'task': return 'primary';
            default: return 'secondary';
        }
    }

    const formatDate = (dateString) => {
        if (!dateString) return 'N/A';
        const date = new Date(dateString);
        return new Intl.DateTimeFormat('pt-BR', { timeZone: 'UTC' }).format(date);
    };

    const formatDateTime = (dateString) => {
        if (!dateString) return 'N/A';
        const date = new Date(dateString);
        return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(date);
    };

    // --- Exposição de Funções e Inicialização ---

    // Expõe as funções que precisam ser chamadas pelo HTML (onclick)
    window.toggleProjectTools = toggleProjectTools;
    window.openRiskModal = openRiskModal;
    window.saveRisk = saveRisk;
    window.editRisk = editRisk;
    window.deleteRisk = deleteRisk;
    window.loadRisks = loadRisks;
    
    window.openMilestoneModal = openMilestoneModal;
    window.saveMilestone = saveMilestone;
    window.editMilestone = editMilestone;
    window.deleteMilestone = deleteMilestone;
    window.loadMilestones = loadMilestones;
    
    window.loadTimeline = loadTimeline;
    
    window.openNoteModal = openNoteModal;
    window.saveNote = saveNote;
    window.editNote = editNote;
    window.deleteNote = deleteNote;
    window.loadNotes = loadNotes;

    // Inicializa o módulo
    init();
} 