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
        notes: document.querySelector('#pills-notes-tab'),
        complexity: document.querySelector('#pills-complexity-tab')
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

    // ✅ NOVA FUNÇÃO: Inicialização apenas do cabeçalho (independente das ferramentas)
    function initProjectHeader() {
        if (!projectId) {
            console.error("ID do Projeto não encontrado para carregar cabeçalho.");
            return;
        }
        
        console.log("Carregando cabeçalho do projeto independentemente das ferramentas...");
        loadProjectHeader();
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
                    case 'pills-complexity': loadComplexityInfo(); break;
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
        loadProjectHeader(); // Carrega o novo cabeçalho unificado
        loadRisks();
        loadMilestones();
        loadTimeline();
        loadNotes();
        // A complexidade agora é carregada dentro do loadProjectHeader
    }

    // --- Funções do Cabeçalho Unificado ---

    async function loadProjectHeader() {
        if (!projectId) return;

        try {
            console.log(`[DEBUG] Carregando cabeçalho do projeto: ${projectId}`);
            
            const [detailsRes, complexityRes, phaseRes, projectTypeRes] = await Promise.all([
                fetch(`/backlog/api/projects/${projectId}/details`),
                fetch(`/backlog/api/projects/${projectId}/complexity/assessment`),
                fetch(`/backlog/api/projects/${projectId}/current-phase`),
                fetch(`/backlog/api/projects/${projectId}/project-type`)
            ]);

            console.log(`[DEBUG] Status das respostas - Details: ${detailsRes.status}, Complexity: ${complexityRes.status}, Phase: ${phaseRes.status}, ProjectType: ${projectTypeRes.status}`);

            const details = detailsRes.ok ? await detailsRes.json() : {};
            const complexityData = complexityRes.ok ? await complexityRes.json() : {};
            const phase = phaseRes.ok ? await phaseRes.json() : {};
            const projectType = projectTypeRes.ok ? await projectTypeRes.json() : {};

            console.log('[DEBUG] Dados recebidos:');
            console.log('- Details:', details);
            console.log('- Complexity:', complexityData);
            console.log('- Phase:', phase);
            console.log('- ProjectType:', projectType);

            // Extrai a complexidade corretamente
            const complexity = complexityData.assessment || {};
            console.log('[DEBUG] Complexidade extraída:', complexity);

            renderProjectHeader(details, complexity, phase, projectType);

        } catch (error) {
            console.error("Erro ao carregar dados do cabeçalho do projeto:", error);
            // Renderiza um estado de erro/padrão
            renderProjectHeader({}, {}, {}, {});
        }
    }

    function renderProjectHeader(details, complexity, phase, projectType) {
        // --- Coluna Esquerda: Informações Gerais ---
        document.getElementById('headerProjectName').textContent = details.projeto || 'Projeto sem nome';
        document.getElementById('headerSpecialist').textContent = `Especialista: ${details.especialista || '-'}`;
        
        // Verificar se existe campo AM nos dados
        const amElement = document.getElementById('headerAM');
        if (amElement) {
            amElement.textContent = `AM: ${details.account_manager || '-'}`;
        } else {
            // Se não existe, criar o elemento
            const specialistElement = document.getElementById('headerSpecialist');
            const amElement = document.createElement('p');
            amElement.className = 'small text-muted mb-1';
            amElement.id = 'headerAM';
            amElement.textContent = `AM: ${details.account_manager || '-'}`;
            specialistElement.parentNode.insertBefore(amElement, specialistElement.nextSibling);
        }
        
        const phaseContainer = document.getElementById('headerPhase');
        if (phase && phase.current_phase) {
            const currentPhase = phase.current_phase;
            const typeLabel = getProjectTypeLabel(projectType);
            phaseContainer.textContent = `${currentPhase.number}. ${currentPhase.name} (${typeLabel})`;
            phaseContainer.style.backgroundColor = currentPhase.color || '#6c757d';
            phaseContainer.className = 'badge';
        } else {
            const typeLabel = getProjectTypeLabel(projectType);
            phaseContainer.textContent = `Fase não configurada (${typeLabel})`;
            phaseContainer.className = 'badge bg-secondary';
        }

        // --- Coluna Central: Métricas ---
        const metrics = {
            'STATUS': details.status || 'N/A',
            'HORAS REST.': `${Math.round(details.horasrestantes || 0)}h`,
            'HORAS PREV.': `${Math.round(details.horas || 0)}h`,
            'CONCLUSÃO': `${Math.round(details.conclusao || 0)}%`,
            'COMPLEXIDADE': complexity.category_label || complexity.category || 'N/A',
            'TÉRMINO PREVISTO': details.vencimentoem ? new Date(details.vencimentoem).toLocaleDateString('pt-BR', { timeZone: 'UTC' }) : '-'
        };

        let metricsHtml = '';
        for (const [label, value] of Object.entries(metrics)) {
            let valueClass = 'metric-value';
            if (label === 'COMPLEXIDADE' && value !== 'N/A') {
                console.log(`[DEBUG] Aplicando cor para complexidade: "${value}"`);
                const catLower = value.toLowerCase();
                if (catLower.includes('baixa')) {
                    valueClass += ' complexity-baixa';
                } else if (catLower.includes('média') || catLower.includes('media')) {
                    valueClass += ' complexity-media';
                } else if (catLower.includes('alta')) {
                    valueClass += ' complexity-alta';
                }
            }
            
            metricsHtml += `
                <div class="col-auto">
                    <div class="metric-item">
                        <div class="metric-label">${label}</div>
                        <div class="${valueClass}">${value}</div>
                    </div>
                </div>
            `;
        }
        
        document.getElementById('headerMetrics').innerHTML = metricsHtml;
    }

    // Função auxiliar para converter tipo do projeto em rótulo
    function getProjectTypeLabel(projectType) {
        if (!projectType || !projectType.project_type) {
            return 'Tipo não definido';
        }
        
        const type = projectType.project_type.toLowerCase();
        switch (type) {
            case 'waterfall':
                return 'Waterfall';
            case 'agile':
                return 'Ágil';
            default:
                return 'Tipo não definido';
        }
    }

    // Expor a função para atualizações externas
    window.refreshProjectHeader = loadProjectHeader;

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
            document.getElementById('riskProbability').value = risk.probability.key || 'MEDIUM';
            document.getElementById('riskImpact').value = risk.impact.key || 'MEDIUM';
            document.getElementById('riskStatus').value = risk.status.key || 'IDENTIFIED';
        } else {
            modalTitle.textContent = 'Novo Risco';
            deleteBtn.style.display = 'none';
            document.getElementById('riskId').value = '';
            // Limpa os campos para um novo risco
            document.getElementById('riskTitle').value = '';
            // Define valores padrão corretos para novo risco
            document.getElementById('riskProbability').value = 'MEDIUM';
            document.getElementById('riskImpact').value = 'MEDIUM';
            document.getElementById('riskStatus').value = 'IDENTIFIED';
        }
        
        riskModal.show();
        
        // ✅ CARREGA CONTEÚDO APÓS O MODAL SER MOSTRADO E SISTEMA PROCESSAR
        setTimeout(() => {
            console.log('🕒 Timeout executado - iniciando carregamento do risco');
            
            // Debug antes do carregamento
            window.debugModalContent('riskDescription');
            window.debugModalContent('riskMitigationPlan');
            
            if (risk) {
                console.log('🔄 Carregando conteúdo do risco após modal abrir:', risk);
                loadContentIntoField('riskDescription', risk.description || '');
                loadContentIntoField('riskMitigationPlan', risk.mitigation_plan || '');
                
                // Debug após o carregamento
                setTimeout(() => {
                    console.log('🔍 Estado após carregamento:');
                    window.debugModalContent('riskDescription');
                    window.debugModalContent('riskMitigationPlan');
                }, 100);
            } else {
                loadContentIntoField('riskDescription', '');
                loadContentIntoField('riskMitigationPlan', '');
            }
        }, 500); // ⏰ Aumentado para 500ms para aguardar sistema processar
    }

    // ✅ NOVA FUNÇÃO: Carrega conteúdo no campo adequado (textarea ou editor rico)
    function loadContentIntoField(fieldId, content) {
        console.log(`🎯 loadContentIntoField chamada para ${fieldId} com conteúdo:`, content);
        
        const textarea = document.getElementById(fieldId);
        if (!textarea) {
            console.error(`❌ Elemento ${fieldId} não encontrado!`);
            return;
        }
        
        // Função para carregar com múltiplas tentativas
        const loadContent = (attempt = 1) => {
            console.log(`🔄 Tentativa ${attempt} de carregar conteúdo para ${fieldId}`);
            
            // Se há um editor rico ativo para este campo
            if (window.richTextManager && window.richTextManager.editors.has(fieldId)) {
                const editorData = window.richTextManager.editors.get(fieldId);
                if (editorData && editorData.quill) {
                    // Aguarda um pouco para o editor estar totalmente pronto
                    setTimeout(() => {
                        editorData.quill.clipboard.dangerouslyPasteHTML(content);
                        console.log(`✅ Conteúdo HTML carregado no editor rico: ${fieldId} (tentativa ${attempt})`);
                    }, 50);
                    return true;
                } else {
                    console.warn(`⚠️ Editor rico existe mas Quill não está pronto para ${fieldId} (tentativa ${attempt})`);
                }
            } 
            
            // Carrega no textarea normal
            textarea.value = content;
            console.log(`✅ Conteúdo carregado no textarea: ${fieldId} (tentativa ${attempt})`);
            return true;
        };
        
        // Múltiplas tentativas com delays crescentes
        const tryLoad = (attempt) => {
            if (attempt > 5) {
                console.error(`❌ Falha ao carregar conteúdo para ${fieldId} após 5 tentativas`);
                return;
            }
            
            if (!loadContent(attempt)) {
                const delay = attempt * 200; // 200ms, 400ms, 600ms, etc.
                setTimeout(() => {
                    tryLoad(attempt + 1);
                }, delay);
            }
        };
        
        // Inicia as tentativas
        tryLoad(1);
    }

    // ✅ EXPORTA A FUNÇÃO GLOBALMENTE
    window.loadContentIntoField = loadContentIntoField;

    // 🔍 DEBUG: Função para monitorar estado dos modais
    window.debugModalContent = function(fieldId) {
        console.log(`🔍 DEBUG para ${fieldId}:`);
        
        const textarea = document.getElementById(fieldId);
        console.log(`📝 Textarea encontrada:`, !!textarea);
        console.log(`📝 Valor atual textarea:`, textarea ? textarea.value : 'N/A');
        
        const hasRichEditor = window.richTextManager && window.richTextManager.editors.has(fieldId);
        console.log(`🎨 Tem editor rico:`, hasRichEditor);
        
        if (hasRichEditor) {
            const editorData = window.richTextManager.editors.get(fieldId);
            console.log(`🎨 Editor data:`, !!editorData);
            console.log(`🎨 Quill instance:`, !!editorData?.quill);
            
            if (editorData?.quill) {
                console.log(`🎨 Conteúdo do Quill:`, editorData.quill.getContents());
                console.log(`🎨 HTML do Quill:`, editorData.quill.root.innerHTML);
            }
        }
        
        const toggleBtn = document.getElementById(`toggleBtn_${fieldId}`);
        console.log(`🔘 Botão toggle encontrado:`, !!toggleBtn);
        console.log(`🔘 Texto do botão:`, toggleBtn ? toggleBtn.innerHTML : 'N/A');
    };

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
            document.getElementById('milestonePlannedDate').value = milestone.planned_date || '';
            document.getElementById('milestoneStartedAt').value = milestone.started_at ? milestone.started_at.slice(0, 16) : '';
            document.getElementById('milestoneActualDate').value = milestone.actual_date || '';
            document.getElementById('milestoneStatus').value = milestone.status.key || 'PENDING';
            document.getElementById('milestoneCriticality').value = milestone.criticality.key || 'MEDIUM';
            document.getElementById('milestoneIsCheckpoint').checked = milestone.is_checkpoint || false;

        } else {
            modalTitle.textContent = 'Novo Marco';
            deleteBtn.style.display = 'none';
            document.getElementById('milestoneId').value = '';
            document.getElementById('milestoneName').value = '';
            document.getElementById('milestonePlannedDate').value = '';
            document.getElementById('milestoneStartedAt').value = '';
            document.getElementById('milestoneActualDate').value = '';
            document.getElementById('milestoneStatus').value = 'PENDING';
            document.getElementById('milestoneCriticality').value = 'MEDIUM';
            document.getElementById('milestoneIsCheckpoint').checked = false;
        }

        milestoneModal.show();
        
        // ✅ CARREGA CONTEÚDO APÓS O MODAL SER MOSTRADO E SISTEMA PROCESSAR
        setTimeout(() => {
            if (milestone) {
                console.log('🔄 Carregando conteúdo do marco após modal abrir:', milestone);
                loadContentIntoField('milestoneDescription', milestone.description || '');
            } else {
                loadContentIntoField('milestoneDescription', '');
            }
        }, 500); // ⏰ Aumentado para 500ms para aguardar sistema processar
    }

    async function saveMilestone() {
        const milestoneId = document.getElementById('milestoneId').value;
        const data = {
            name: document.getElementById('milestoneName').value,
            description: document.getElementById('milestoneDescription').value,
            planned_date: document.getElementById('milestonePlannedDate').value,
            started_at: document.getElementById('milestoneStartedAt').value || null,
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
                                <span class="badge bg-${getCategoryColor(note.category)}">${getCategoryLabel(note.category)}</span>
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
        
        // ✅ CARREGA CONTEÚDO APÓS O MODAL SER MOSTRADO E SISTEMA PROCESSAR
        setTimeout(() => {
            if (note) {
                console.log('🔄 Carregando conteúdo da nota após modal abrir:', note);
                loadContentIntoField('noteContent', note.content || '');
            } else {
                loadContentIntoField('noteContent', '');
            }
        }, 500); // ⏰ Aumentado para 500ms para aguardar sistema processar
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
        
        // Atualiza também os cards de métricas
        updateMetricCard(tabName, count);
    }
    
    function updateMetricCard(tabName, count) {
        const metricCards = {
            'risks': 'risk-count',
            'milestones': 'milestone-count', 
            'notes': 'notes-count',
            'complexity': 'complexity-level'
        };
        
        const elementId = metricCards[tabName];
        if (elementId) {
            const element = document.getElementById(elementId);
            if (element) {
                // Animação de atualização
                element.style.animation = 'none';
                element.offsetHeight; // trigger reflow
                element.style.animation = 'numberUpdate 0.6s ease-out';
                element.textContent = count;
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
            case 'decision': return 'warning';
            case 'risk': return 'danger';
            case 'impediment': return 'danger';
            case 'status_update': return 'info';
            case 'general': return 'primary';
            default: return 'secondary';
        }
    }

    function getCategoryLabel(category) {
        switch(category?.toLowerCase()) {
            case 'decision': return 'Decisão';
            case 'risk': return 'Risco';
            case 'impediment': return 'Impedimento';
            case 'status_update': return 'Atualização de Status';
            case 'general': return 'Geral';
            default: return category || 'Categoria';
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

    // --- Funções Expostas Globalmente ---
    window.toggleProjectTools = toggleProjectTools;
    window.loadRisks = loadRisks;
    window.openRiskModal = openRiskModal;
    window.saveRisk = saveRisk;
    window.editRisk = editRisk;
    window.deleteRisk = deleteRisk;
    window.loadMilestones = loadMilestones;
    window.openMilestoneModal = openMilestoneModal;
    window.saveMilestone = saveMilestone;
    window.editMilestone = editMilestone;
    window.deleteMilestone = deleteMilestone;
    window.loadTimeline = loadTimeline;
    window.loadNotes = loadNotes;
    window.openNoteModal = openNoteModal;
    window.saveNote = saveNote;
    window.editNote = editNote;
    window.deleteNote = deleteNote;
    
    // Funções de complexidade
    window.loadComplexityInfo = loadComplexityInfo;
    window.openComplexityModal = openComplexityModal;
    window.openComplexityHistoryModal = openComplexityHistoryModal;
    window.saveComplexityAssessment = saveComplexityAssessment;
    
    // Funções de exportação para os novos botões
    window.exportRisks = function() {
        showToast('Funcionalidade de exportação de riscos em desenvolvimento', 'info');
    };
    
    window.exportMilestones = function() {
        showToast('Funcionalidade de exportação de marcos em desenvolvimento', 'info');
    };
    
    window.exportNotes = function() {
        showToast('Funcionalidade de exportação de notas em desenvolvimento', 'info');
    };
    
    window.exportTimeline = function() {
        showToast('Funcionalidade de exportação de timeline em desenvolvimento', 'info');
    };

    // --- FUNÇÕES DE COMPLEXIDADE ---
    
    let complexityCriteria = [];
    let complexityThresholds = [];
    let currentComplexityAssessment = {};

    async function loadComplexityInfo() {
        if (!projectId) return;
        
        try {
            const response = await fetch(`/backlog/api/projects/${projectId}/complexity/assessment`);
            if (!response.ok) throw new Error('Erro ao carregar complexidade');
            
            const data = await response.json();
            renderComplexityInfo(data.assessment);
            updateComplexityBadge(data.assessment);
            
        } catch (error) {
            console.error('Erro ao carregar complexidade:', error);
            document.getElementById('complexityContainer').innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i> Erro ao carregar complexidade: ${error.message}
                </div>
            `;
        }
    }

    function renderComplexityInfo(assessment) {
        const container = document.getElementById('complexityContainer');
        if (!container) return;

        if (!assessment) {
            container.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="bi bi-bar-chart fs-1"></i>
                    <p>Nenhuma avaliação de complexidade realizada</p>
                    <button class="btn btn-warning" onclick="openComplexityModal()">
                        <i class="bi bi-calculator"></i> Fazer Primeira Avaliação
                    </button>
                </div>
            `;
            return;
        }

        const categoryColors = {
            'BAIXA': 'success',
            'MÉDIA': 'warning', 
            'ALTA': 'danger',
            // Compatibilidade com valores antigos
            'LOW': 'success',
            'MEDIUM': 'warning', 
            'HIGH': 'danger'
        };

        const color = categoryColors[assessment.category] || 'secondary';

        container.innerHTML = `
            <div class="card">
                <div class="card-body">
                    <div class="row align-items-center">
                        <div class="col-md-8">
                            <h5 class="card-title mb-2">
                                <span class="badge bg-${color}">${assessment.category_label}</span>
                                Complexidade do Projeto
                            </h5>
                            <p class="card-text">
                                <strong>Score Total:</strong> ${assessment.total_score} pontos
                            </p>
                            ${assessment.notes ? `<p class="text-muted small">${assessment.notes}</p>` : ''}
                            <small class="text-muted">
                                Avaliado por ${assessment.assessed_by} em ${formatDateTime(assessment.created_at)}
                            </small>
                        </div>
                        <div class="col-md-4 text-center">
                            <div class="display-4 text-${color}">${assessment.total_score}</div>
                            <small class="text-muted">pontos</small>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    function updateComplexityBadge(assessment) {
        const badge = document.getElementById('complexity-badge');
        if (!badge) return;

        if (assessment) {
            const categoryLabels = {
                'BAIXA': 'B',
                'MÉDIA': 'M',
                'ALTA': 'A',
                // Compatibilidade com valores antigos
                'LOW': 'B',
                'MEDIUM': 'M',
                'HIGH': 'A'
            };
            
            const categoryColors = {
                'BAIXA': 'bg-success',
                'MÉDIA': 'bg-warning',
                'ALTA': 'bg-danger',
                // Compatibilidade com valores antigos
                'LOW': 'bg-success',
                'MEDIUM': 'bg-warning',
                'HIGH': 'bg-danger'
            };
            
            badge.textContent = categoryLabels[assessment.category] || '-';
            badge.className = `badge ms-1 ${categoryColors[assessment.category] || 'bg-secondary'}`;
            badge.style.display = 'inline';
            
            // Atualiza também o card de métrica
            updateMetricCard('complexity', assessment.category_label || assessment.category);
        } else {
            badge.style.display = 'none';
            updateMetricCard('complexity', '-');
        }
    }

    async function openComplexityModal() {
        try {
            // Carrega critérios se não estiverem carregados
            if (complexityCriteria.length === 0) {
                const criteriaResponse = await fetch('/backlog/api/complexity/criteria');
                if (!criteriaResponse.ok) throw new Error('Erro ao carregar critérios');
                complexityCriteria = await criteriaResponse.json();
            }

            // Carrega thresholds se não estiverem carregados
            if (complexityThresholds.length === 0) {
                const thresholdsResponse = await fetch('/backlog/api/complexity/thresholds');
                if (!thresholdsResponse.ok) throw new Error('Erro ao carregar thresholds');
                complexityThresholds = await thresholdsResponse.json();
            }

            // Carrega avaliação atual se existir
            const assessmentResponse = await fetch(`/backlog/api/projects/${projectId}/complexity/assessment`);
            const assessmentData = await assessmentResponse.json();
            
            renderComplexityForm(assessmentData.assessment);
            
            const modal = new bootstrap.Modal(document.getElementById('complexityModal'));
            modal.show();
            
        } catch (error) {
            console.error('Erro ao abrir modal de complexidade:', error);
            showToast('Erro ao carregar formulário de complexidade', 'error');
        }
    }

    function renderComplexityForm(currentAssessment = null) {
        const container = document.getElementById('complexityCriteriaContainer');
        if (!container) return;

        // Ícones para cada critério
        const criteriaIcons = {
            'Quantidade de horas': 'bi-clock-fill',
            'Tipo de escopo': 'bi-diagram-3-fill', 
            'DeadLine Previsto': 'bi-calendar-event-fill',
            'Tipo de cliente': 'bi-people-fill'
        };

        const criteriaHtml = complexityCriteria.map((criterion, index) => {
            const currentSelection = currentAssessment?.details?.find(d => d.criteria_id === criterion.id);
            const icon = criteriaIcons[criterion.name] || 'bi-star-fill';
            
            const optionsHtml = criterion.options.map((option, optIndex) => {
                const scoreColor = option.score <= 25 ? 'success' : option.score <= 50 ? 'warning' : option.score <= 75 ? 'orange' : 'danger';
                return `
                    <div class="form-check option-item p-3 mb-2 border rounded hover-effect" style="cursor: pointer; transition: all 0.2s ease;">
                        <input class="form-check-input complexity-option" 
                               type="radio" 
                               name="criteria_${criterion.id}" 
                               id="option_${option.id}" 
                               value="${option.id}"
                               data-score="${option.score}"
                               ${currentSelection?.option_id === option.id ? 'checked' : ''}
                               onchange="calculateComplexityScore()"
                               style="transform: scale(1.2);">
                        <label class="form-check-label w-100" for="option_${option.id}" style="cursor: pointer;">
                            <div class="d-flex justify-content-between align-items-center">
                                <div class="flex-grow-1">
                                    <strong>${option.label}</strong>
                                    ${option.description ? `<div><small class="text-muted">${option.description}</small></div>` : ''}
                                </div>
                                <div class="flex-shrink-0">
                                    <span class="badge bg-${scoreColor} fs-6 px-2 py-1">${option.score}pts</span>
                                </div>
                            </div>
                        </label>
                    </div>
                `;
            }).join('');

            const cardGradients = [
                'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)', 
                'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
                'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)'
            ];

            return `
                <div class="card border-0 shadow-sm mb-4 criteria-card" style="overflow: hidden;">
                    <div class="card-header border-0 text-white" style="background: ${cardGradients[index % cardGradients.length]};">
                        <div class="d-flex align-items-center">
                            <div class="flex-shrink-0">
                                <i class="${icon} fs-4 me-3"></i>
                            </div>
                            <div class="flex-grow-1">
                                <h6 class="mb-0 fw-bold">${criterion.name}</h6>
                                ${criterion.description ? `<small class="text-white-50">${criterion.description}</small>` : ''}
                            </div>
                        </div>
                    </div>
                    <div class="card-body p-4" style="background: linear-gradient(to bottom, #f8f9fa, #ffffff);">
                        ${optionsHtml}
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = criteriaHtml;

        // Preenche observações se houver
        if (currentAssessment?.notes) {
            document.getElementById('complexityNotes').value = currentAssessment.notes;
        }

        // Calcula score inicial
        calculateComplexityScore();
    }

    function calculateComplexityScore() {
        const selectedOptions = document.querySelectorAll('.complexity-option:checked');
        let totalScore = 0;
        
        selectedOptions.forEach(option => {
            totalScore += parseInt(option.dataset.score) || 0;
        });

        // Atualiza display do score
        document.getElementById('totalScoreDisplay').textContent = totalScore;

        // Determina categoria baseada nos thresholds
        let category = 'Baixa Complexidade';
        let categoryColor = 'text-success';
        
        for (const threshold of complexityThresholds) {
            if (totalScore >= threshold.min_score && 
                (threshold.max_score === null || totalScore <= threshold.max_score)) {
                category = threshold.category_label;
                categoryColor = (threshold.category === 'LOW' || threshold.category === 'BAIXA') ? 'text-success' : 
                              (threshold.category === 'MEDIUM' || threshold.category === 'MÉDIA') ? 'text-warning' : 'text-danger';
                break;
            }
        }

        const categoryDisplay = document.getElementById('categoryDisplay');
        categoryDisplay.textContent = category;
        
        // Remove classes antigas e adiciona as novas com animação
        categoryDisplay.className = 'badge fs-6 px-3 py-2';
        categoryDisplay.classList.remove('baixa', 'media', 'alta');
        
        // Adiciona classe baseada na categoria com animação suave
        if (category.toLowerCase().includes('baixa') || categoryColor.includes('success')) {
            categoryDisplay.classList.add('baixa');
        } else if (category.toLowerCase().includes('média') || categoryColor.includes('warning')) {
            categoryDisplay.classList.add('media'); 
        } else {
            categoryDisplay.classList.add('alta');
        }
        
        // Anima o score display
        const scoreDisplay = document.getElementById('totalScoreDisplay');
        scoreDisplay.style.animation = 'none';
        scoreDisplay.offsetHeight; // trigger reflow
        scoreDisplay.style.animation = 'scoreUpdate 0.5s ease-out';
    }

    async function saveComplexityAssessment() {
        const saveButton = document.querySelector('button[onclick="saveComplexityAssessment()"]');
        const originalText = saveButton.innerHTML;
        
        try {
            // Adiciona estado de loading
            saveButton.classList.add('btn-loading');
            saveButton.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Salvando...';
            saveButton.disabled = true;
            
            const form = document.getElementById('complexityForm');
            const formData = new FormData(form);
            
            // Coleta as avaliações selecionadas
            const assessments = {};
            complexityCriteria.forEach(criterion => {
                const selected = document.querySelector(`input[name="criteria_${criterion.id}"]:checked`);
                if (selected) {
                    assessments[criterion.id] = parseInt(selected.value);
                }
            });

            if (Object.keys(assessments).length !== complexityCriteria.length) {
                showToast('Por favor, avalie todos os critérios antes de salvar', 'error');
                return;
            }

            const data = {
                criteria: assessments,  // Corrige o nome do campo para 'criteria'
                notes: document.getElementById('complexityNotes').value,
                assessed_by: 'Usuário Sistema' // Você pode pegar do contexto do usuário
            };

            const response = await fetch(`/backlog/api/projects/${projectId}/complexity/assessment`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Erro ao salvar avaliação');
            }

            const result = await response.json();
            
            showToast('Avaliação de complexidade salva com sucesso!', 'success');
            
            // Fecha o modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('complexityModal'));
            modal.hide();
            
            // Recarrega as informações de complexidade
            loadComplexityInfo();
            
        } catch (error) {
            console.error('Erro ao salvar avaliação:', error);
            showToast('Erro ao salvar avaliação: ' + error.message, 'error');
        } finally {
            // Remove estado de loading
            saveButton.classList.remove('btn-loading');
            saveButton.innerHTML = originalText;
            saveButton.disabled = false;
        }
    }

    async function openComplexityHistoryModal() {
        try {
            const response = await fetch(`/backlog/api/projects/${projectId}/complexity/history`);
            if (!response.ok) throw new Error('Erro ao carregar histórico');
            
            const history = await response.json();
            renderComplexityHistory(history);
            
            const modal = new bootstrap.Modal(document.getElementById('complexityHistoryModal'));
            modal.show();
            
        } catch (error) {
            console.error('Erro ao carregar histórico:', error);
            showToast('Erro ao carregar histórico de complexidade', 'error');
        }
    }

    function renderComplexityHistory(history) {
        const container = document.getElementById('complexityHistoryContainer');
        if (!container) return;

        if (history.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="bi bi-clock-history fs-1"></i>
                    <p>Nenhuma avaliação encontrada no histórico</p>
                </div>
            `;
            return;
        }

        const historyHtml = history.map((assessment, index) => {
            const categoryColors = {
                'BAIXA': 'success',
                'MÉDIA': 'warning',
                'ALTA': 'danger',
                // Compatibilidade com valores antigos
                'LOW': 'success',
                'MEDIUM': 'warning',
                'HIGH': 'danger'
            };
            
            const color = categoryColors[assessment.category] || 'secondary';
            const isLatest = index === 0;

            return `
                <div class="card mb-3 ${isLatest ? 'border-primary' : ''}">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <h6 class="card-title">
                                    <span class="badge bg-${color}">${assessment.category_label}</span>
                                    ${isLatest ? '<span class="badge bg-primary ms-1">Atual</span>' : ''}
                                </h6>
                                <p class="mb-1"><strong>Score:</strong> ${assessment.total_score} pontos</p>
                                ${assessment.notes ? `<p class="text-muted small">${assessment.notes}</p>` : ''}
                            </div>
                            <div class="text-end text-muted small">
                                <div>${formatDateTime(assessment.created_at)}</div>
                                <div>por ${assessment.assessed_by}</div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = historyHtml;
    }

    // ========================================
    // MÓDULO WBS - WORK BREAKDOWN STRUCTURE
    // ========================================

    let wbsData = [];
    let wbsMilestones = [];

    async function generateWBS() {
        const generateButton = document.querySelector('button[onclick="generateWBS()"]');
        const originalText = generateButton.innerHTML;
        
        try {
            generateButton.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Gerando...';
            generateButton.disabled = true;

            // Busca tarefas e marcos
            const [tasksResponse, milestonesResponse] = await Promise.all([
                fetch(`/backlog/api/projects/${projectId}/tasks`),
                fetch(`/backlog/api/projects/${projectId}/milestones`)
            ]);

            if (!tasksResponse.ok || !milestonesResponse.ok) {
                throw new Error('Erro ao carregar dados para WBS');
            }

            const tasks = await tasksResponse.json();
            const milestones = await milestonesResponse.json();

            // Processa e organiza os dados
            wbsData = processWBSData(tasks, milestones);
            
            // Renderiza a WBS
            renderWBS(wbsData);
            
            // Atualiza contador
            document.getElementById('wbs-total-items').textContent = `${wbsData.length} itens`;
            document.getElementById('wbs-badge').style.display = 'inline';
            document.getElementById('wbs-badge').textContent = wbsData.length;

            showToast('WBS gerada com sucesso!', 'success');

        } catch (error) {
            console.error('Erro ao gerar WBS:', error);
            showToast('Erro ao gerar WBS: ' + error.message, 'error');
        } finally {
            generateButton.innerHTML = originalText;
            generateButton.disabled = false;
        }
    }

    function processWBSData(tasks, milestones) {
        const startDate = document.getElementById('wbs-start-date').value || new Date().toISOString().split('T')[0];
        const includeMilestones = document.getElementById('wbs-include-milestones').value === 'true';
        const sortOrder = document.getElementById('wbs-sort-order').value;

        let wbsItems = [];
        let currentDate = new Date(startDate);

        // Processa tarefas
        tasks.forEach((task, index) => {
            let taskStartDate, taskEndDate, estimatedDays;
            
            // Prioridade: usar datas reais da tarefa se existirem
            if (task.start_date && task.due_date) {
                taskStartDate = new Date(task.start_date);
                taskEndDate = new Date(task.due_date);
                estimatedDays = getTaskEstimatedDays(task); // Calcula com base nas datas reais
            } else {
                // Usa sequenciamento automático
                taskStartDate = new Date(currentDate);
                estimatedDays = getTaskEstimatedDays(task);
                taskEndDate = new Date(taskStartDate);
                taskEndDate.setDate(taskEndDate.getDate() + estimatedDays);
            }

            wbsItems.push({
                id: task.id,
                wbs_id: `${index + 1}`,
                type: 'task',
                name: task.title || task.name,
                description: task.description || '',
                start_date: formatDateForWBS(taskStartDate),
                end_date: formatDateForWBS(taskEndDate),
                duration_days: estimatedDays,
                specialist: task.assigned_to || 'Não atribuído',
                status: task.status || 'TODO',
                priority: task.priority || 'MEDIUM',
                column: task.column_name || 'A Fazer'
            });

            // Só avança data automática se não está usando datas reais
            if (!task.start_date || !task.due_date) {
                currentDate.setDate(currentDate.getDate() + Math.max(1, Math.floor(estimatedDays / 2)));
            } else {
                // Se está usando datas reais, avança para depois da tarefa atual
                currentDate = new Date(taskEndDate);
                currentDate.setDate(currentDate.getDate() + 1);
            }
        });

        // Adiciona marcos se solicitado
        if (includeMilestones && milestones.length > 0) {
            milestones.forEach((milestone, index) => {
                wbsItems.push({
                    id: `milestone_${milestone.id}`,
                    wbs_id: `M${index + 1}`,
                    type: 'milestone',
                    name: `🏁 ${milestone.name}`,
                    description: milestone.description || '',
                    start_date: formatDateForWBS(milestone.planned_date),
                    end_date: formatDateForWBS(milestone.planned_date),
                    duration_days: 0,
                    specialist: 'Marco do Projeto',
                    status: milestone.status || 'PENDING',
                    priority: milestone.criticality || 'HIGH',
                    column: 'Marco'
                });
            });
        }

        // Ordena conforme solicitado
        return sortWBSItems(wbsItems, sortOrder);
    }

    function getTaskEstimatedDays(task) {
        // 1. Prioridade: Se a tarefa já tem datas definidas, calcula duração real
        if (task.start_date && task.due_date) {
            const startDate = new Date(task.start_date);
            const endDate = new Date(task.due_date);
            const diffTime = Math.abs(endDate - startDate);
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            if (diffDays > 0 && diffDays <= 365) { // Sanity check
                return diffDays;
            }
        }

        // 2. Se tem estimated_effort (horas), converte para dias (8h/dia)
        if (task.estimated_effort && task.estimated_effort > 0) {
            const days = Math.ceil(task.estimated_effort / 8);
            return Math.max(1, Math.min(days, 30)); // Entre 1 e 30 dias
        }

        // 3. Usa complexidade da tarefa individual (não do projeto)
        const complexityMap = {
            'LOW': 2,
            'MEDIUM': 5, 
            'HIGH': 8,
            'BAIXA': 2,
            'MÉDIA': 5,
            'ALTA': 8
        };

        if (task.complexity && task.complexity !== 'ALTA') { // Ignora complexidade do projeto
            return complexityMap[task.complexity] || 3;
        }

        // 4. Estima baseado no título/descrição da tarefa
        const text = ((task.title || task.name) + ' ' + (task.description || '')).toLowerCase();
        
        if (text.includes('simples') || text.includes('pequeno') || text.includes('rápido') || text.includes('validação')) {
            return 1;
        } else if (text.includes('complexo') || text.includes('grande') || text.includes('detalhado') || text.includes('migração')) {
            return 7;
        } else if (text.includes('integração') || text.includes('desenvolvimento') || text.includes('implementação')) {
            return 5;
        } else if (text.includes('configuração') || text.includes('setup') || text.includes('instalação')) {
            return 3;
        } else if (text.includes('teste') || text.includes('checkpoint') || text.includes('documentação')) {
            return 2;
        }

        // 5. Padrão baseado no status
        if (task.status === 'Concluído' || task.status === 'DONE') {
            return 2; // Tarefas concluídas geralmente são menores
        }

        return 3; // Padrão geral
    }

    function sortWBSItems(items, sortOrder) {
        switch (sortOrder) {
            case 'date':
                return items.sort((a, b) => new Date(a.start_date) - new Date(b.start_date));
            case 'specialist':
                return items.sort((a, b) => a.specialist.localeCompare(b.specialist));
            case 'column':
                return items.sort((a, b) => a.column.localeCompare(b.column));
            case 'priority':
            default:
                const priorityOrder = { 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1, 'ALTA': 3, 'MÉDIA': 2, 'BAIXA': 1 };
                return items.sort((a, b) => (priorityOrder[b.priority] || 2) - (priorityOrder[a.priority] || 2));
        }
    }

    function renderWBS(wbsItems) {
        const container = document.getElementById('wbsContainer');
        
        if (wbsItems.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-5">
                    <i class="bi bi-diagram-3 fs-1"></i>
                    <h5 class="mt-3">Nenhuma tarefa encontrada</h5>
                    <p>Adicione tarefas ao quadro para gerar a WBS</p>
                </div>
            `;
            return;
        }

        const tableHtml = `
            <div class="table-responsive">
                <table class="table table-hover mb-0">
                    <thead class="table-light">
                        <tr>
                            <th width="80">WBS ID</th>
                            <th width="60">Tipo</th>
                            <th>Tarefa/Marco</th>
                            <th>Descrição</th>
                            <th width="110">Data Início</th>
                            <th width="110">Data Fim</th>
                            <th width="80">Duração</th>
                            <th width="150">Especialista</th>
                            <th width="100">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${wbsItems.map(item => `
                            <tr class="${item.type === 'milestone' ? 'table-warning' : ''}">
                                <td><strong>${item.wbs_id}</strong></td>
                                <td>
                                    <span class="badge bg-${item.type === 'milestone' ? 'warning' : 'primary'}">
                                        ${item.type === 'milestone' ? 'Marco' : 'Tarefa'}
                                    </span>
                                </td>
                                <td>
                                    <strong>${item.name}</strong>
                                    ${item.priority !== 'MEDIUM' && item.priority !== 'MÉDIA' ? 
                                        `<span class="badge bg-${getPriorityColor(item.priority)} ms-1">${item.priority}</span>` : ''}
                                </td>
                                <td class="text-muted small">${item.description}</td>
                                <td>${item.start_date}</td>
                                <td>${item.end_date}</td>
                                <td>
                                    ${item.duration_days > 0 ? 
                                        `<span class="badge bg-info">${item.duration_days} ${item.duration_days === 1 ? 'dia' : 'dias'}</span>` : 
                                        '<span class="text-muted">-</span>'}
                                </td>
                                <td>${item.specialist}</td>
                                <td>
                                    <span class="badge bg-${getStatusColor(item.status)}">${getStatusLabel(item.status)}</span>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;

        container.innerHTML = tableHtml;
    }

    function getStatusLabel(status) {
        const labels = {
            'TODO': 'A Fazer',
            'IN_PROGRESS': 'Em Progresso', 
            'DONE': 'Concluído',
            'PENDING': 'Pendente',
            'COMPLETED': 'Concluído',
            'DELAYED': 'Atrasado'
        };
        return labels[status] || status;
    }

    async function exportWBSToExcel() {
        if (wbsData.length === 0) {
            showToast('Gere a WBS primeiro antes de exportar', 'warning');
            return;
        }

        const exportButton = document.querySelector('button[onclick="exportWBSToExcel()"]');
        const originalText = exportButton.innerHTML;
        
        try {
            exportButton.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Exportando...';
            exportButton.disabled = true;

            // Prepara dados para exportação
            const exportData = wbsData.map(item => ({
                'WBS_ID': item.wbs_id,
                'Tipo': item.type === 'milestone' ? 'Marco' : 'Tarefa',
                'ID_Tarefa': item.id,
                'Tarefa': item.name,
                'Descrição': item.description,
                'Data_Inicio': item.start_date,
                'Data_Prevista_Fim': item.end_date,
                'Intervalo_Dias': item.duration_days,
                'Especialista': item.specialist,
                'Status': getStatusLabel(item.status),
                'Prioridade': item.priority,
                'Coluna': item.column
            }));

            const response = await fetch('/backlog/api/wbs/export', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    project_id: projectId,
                    wbs_data: exportData
                })
            });

            if (!response.ok) {
                throw new Error('Erro ao exportar WBS');
            }

            // Download do arquivo
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `WBS_Projeto_${projectId}_${new Date().toISOString().split('T')[0]}.xlsx`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            showToast('WBS exportada com sucesso!', 'success');

        } catch (error) {
            console.error('Erro ao exportar WBS:', error);
            showToast('Erro ao exportar WBS: ' + error.message, 'error');
        } finally {
            exportButton.innerHTML = originalText;
            exportButton.disabled = false;
        }
    }

    function refreshWBS() {
        if (wbsData.length > 0) {
            generateWBS();
        } else {
            showToast('Gere a WBS primeiro', 'info');
        }
    }

    function previewWBS() {
        if (wbsData.length === 0) {
            showToast('Gere a WBS primeiro para visualizar', 'warning');
            return;
        }

        // Muda para a aba WBS se não estiver ativa
        const wbsTab = document.getElementById('pills-wbs-tab');
        if (wbsTab && !wbsTab.classList.contains('active')) {
            wbsTab.click();
        }

        // Scroll suave para a tabela
        const container = document.getElementById('wbsContainer');
        container.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function formatDateForWBS(date) {
        if (!date) return '';
        
        // Usa a mesma função formatDate da interface para manter consistência
        // Isso evita problemas de fuso horário que causavam diferença de 1 dia entre interface e WBS
        return formatDate(date);
    }

    async function copyWBSToClipboard() {
        if (wbsData.length === 0) {
            showToast('Gere a WBS primeiro antes de copiar', 'warning');
            return;
        }

        const copyButton = document.querySelector('button[onclick="copyWBSToClipboard()"]');
        const originalText = copyButton.innerHTML;
        
        try {
            copyButton.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Copiando...';
            copyButton.disabled = true;

            // Configurações de paginação
            const LINHAS_POR_PAGINA = 17; // Ideal para A4
            const totalItems = wbsData.length;
            const totalPaginas = Math.ceil(totalItems / LINHAS_POR_PAGINA);

            if (totalPaginas === 1) {
                // Projeto pequeno - copia tudo
                const tableHTML = generateTableHTML(wbsData, 1, totalPaginas);
                await copyToClipboard(tableHTML);
                showToast('✅ WBS copiada! Cole no PowerPoint com Ctrl+V', 'success');
            } else {
                // Projeto grande - oferece opções de paginação
                const escolha = await showPaginationModal(totalItems, totalPaginas);
                
                if (escolha.action === 'all') {
                    // Copia tudo mesmo sendo grande
                    const tableHTML = generateTableHTML(wbsData, 1, 1, 'Todas as páginas');
                    await copyToClipboard(tableHTML);
                    showToast(`✅ WBS completa copiada! (${totalItems} itens)`, 'success');
                } else if (escolha.action === 'page') {
                    // Copia página específica
                    const startIndex = (escolha.page - 1) * LINHAS_POR_PAGINA;
                    const endIndex = Math.min(startIndex + LINHAS_POR_PAGINA, totalItems);
                    const pageData = wbsData.slice(startIndex, endIndex);
                    
                    const tableHTML = generateTableHTML(pageData, escolha.page, totalPaginas);
                    await copyToClipboard(tableHTML);
                    showToast(`✅ Página ${escolha.page}/${totalPaginas} copiada! (${pageData.length} itens)`, 'success');
                } else {
                    // Cancelou
                    showToast('Cópia cancelada', 'info');
                }
            }

        } catch (error) {
            console.error('Erro ao copiar WBS:', error);
            
            // Fallback final - copia texto simples
            try {
                const textTable = generatePlainTextTable();
                await navigator.clipboard.writeText(textTable);
                showToast('📋 WBS copiada como texto! Cole no PowerPoint e converta para tabela', 'info');
            } catch (textError) {
                showToast('❌ Erro ao copiar WBS: ' + error.message, 'error');
            }
        } finally {
            copyButton.innerHTML = originalText;
            copyButton.disabled = false;
        }
    }

    function generateTableHTML(data, pagina, totalPaginas, titulo = null) {
        const tituloDisplay = titulo || `Página ${pagina} de ${totalPaginas}`;
        
        // Dimensões otimizadas para PowerPoint
        // Altura: 14,12 cm = ~400px | Largura: 27,73 cm = ~785px
        let tableHTML = `<div style="font-family: Arial, sans-serif; width: 785px; max-height: 400px;">
<h3 style="color: #07304F; margin-bottom: 8px; font-size: 12pt; font-weight: bold;">WBS - Estrutura Analítica do Projeto</h3>
<p style="color: #6c757d; margin-bottom: 12px; font-size: 9pt;">${tituloDisplay} • ${data.length} itens</p>
<table border="1" cellpadding="4" cellspacing="0" style="border-collapse: collapse; font-family: Arial, sans-serif; font-size: 10pt; width: 100%; max-width: 785px;">
<thead>
<tr style="background-color: #07304F; color: white; font-weight: bold; font-size: 12pt;">
<td style="text-align: center; width: 50px; padding: 4px 2px;">WBS ID</td>
<td style="text-align: center; width: 45px; padding: 4px 2px;">Tipo</td>
<td style="text-align: center; width: 160px; padding: 4px 6px;">Tarefa/Marco</td>
<td style="text-align: center; width: 180px; padding: 4px 6px;">Descrição</td>
<td style="text-align: center; width: 70px; padding: 4px 2px;">Data Início</td>
<td style="text-align: center; width: 70px; padding: 4px 2px;">Data Fim</td>
<td style="text-align: center; width: 50px; padding: 4px 2px;">Duração</td>
<td style="text-align: center; width: 100px; padding: 4px 4px;">Especialista</td>
<td style="text-align: center; width: 60px; padding: 4px 2px;">Status</td>
</tr>
</thead>
<tbody>`;

        // Adiciona cada linha da WBS
        data.forEach(item => {
            const isMarco = item.type === 'milestone';
            const rowStyle = isMarco ? 'background-color: #fff3cd;' : '';
            
            tableHTML += `<tr style="${rowStyle}">
<td style="text-align: center; font-weight: bold; font-size: 10pt; padding: 3px 2px;">${item.wbs_id}</td>
<td style="text-align: center; background-color: ${isMarco ? '#ffc107' : '#0d6efd'}; color: white; font-size: 8pt; font-weight: bold; padding: 2px 1px;">${isMarco ? 'Marco' : 'Tarefa'}</td>
<td style="font-weight: bold; font-size: 10pt; padding: 3px 6px; line-height: 1.2;">${item.name}${item.priority !== 'MEDIUM' && item.priority !== 'MÉDIA' ? ` <span style="color: #dc3545; font-size: 9pt;">(${item.priority})</span>` : ''}</td>
<td style="color: #6c757d; font-size: 10pt; padding: 3px 6px; line-height: 1.2;">${item.description}</td>
<td style="text-align: center; font-size: 10pt; padding: 3px 2px;">${item.start_date}</td>
<td style="text-align: center; font-size: 10pt; padding: 3px 2px;">${item.end_date}</td>
<td style="text-align: center; background-color: #d1ecf1; font-weight: bold; font-size: 9pt; padding: 3px 2px;">${item.duration_days > 0 ? `${item.duration_days}d` : '-'}</td>
<td style="text-align: center; font-size: 10pt; padding: 3px 4px;">${item.specialist}</td>
<td style="text-align: center; background-color: ${getStatusColorForCopy(item.status)}; color: white; font-size: 9pt; font-weight: bold; padding: 2px 1px;">${getStatusLabel(item.status)}</td>
</tr>`;
        });

        tableHTML += `</tbody>
</table>
<div style="margin-top: 8px; font-size: 8pt; color: #9ca3af; text-align: right;">
    Gerado em ${new Date().toLocaleString('pt-BR')} | Central de Comando PMO
</div>
</div>`;

        return tableHTML;
    }

    async function copyToClipboard(tableHTML) {
        if (navigator.clipboard && window.isSecureContext) {
            // Método moderno - copia como HTML
            const clipboardItem = new ClipboardItem({
                'text/html': new Blob([tableHTML], { type: 'text/html' }),
                'text/plain': new Blob([generatePlainTextTable()], { type: 'text/plain' })
            });
            await navigator.clipboard.write([clipboardItem]);
        } else {
            // Fallback - cria elemento temporário e copia
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = tableHTML;
            tempDiv.style.position = 'absolute';
            tempDiv.style.left = '-9999px';
            document.body.appendChild(tempDiv);
            
            const range = document.createRange();
            range.selectNode(tempDiv);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            
            document.execCommand('copy');
            document.body.removeChild(tempDiv);
            selection.removeAllRanges();
        }
    }

    async function showPaginationModal(totalItems, totalPaginas) {
        return new Promise((resolve) => {
            const modalHtml = `
<div class="modal fade" id="paginationModal" tabindex="-1" data-bs-backdrop="static">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header bg-primary text-white">
                <h5 class="modal-title">📋 Projeto Grande - Opções de Cópia</h5>
            </div>
            <div class="modal-body">
                <div class="alert alert-info">
                    <i class="bi bi-info-circle me-2"></i>
                    <strong>Total:</strong> ${totalItems} itens • <strong>Páginas:</strong> ${totalPaginas}
                    <br><small>Recomendamos copiar por páginas para melhor formatação no PowerPoint (17 itens por página)</small>
                </div>
                
                <div class="row">
                    <div class="col-md-6">
                        <div class="card border-success">
                            <div class="card-body text-center">
                                <i class="bi bi-file-earmark-text fs-1 text-success"></i>
                                <h6 class="mt-2">Copiar por Página</h6>
                                <p class="small text-muted">Ideal para PowerPoint<br>~17 itens por página</p>
                                <select class="form-select form-select-sm mb-2" id="pageSelect">
                                    ${Array.from({length: totalPaginas}, (_, i) => 
                                        `<option value="${i+1}">Página ${i+1} (${Math.min(17, totalItems - (i*17))} itens)</option>`
                                    ).join('')}
                                </select>
                                <button class="btn btn-success btn-sm w-100" onclick="resolvePagination('page')">
                                    <i class="bi bi-clipboard-check me-1"></i>Copiar Página
                                </button>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-6">
                        <div class="card border-warning">
                            <div class="card-body text-center">
                                <i class="bi bi-file-earmark-spreadsheet fs-1 text-warning"></i>
                                <h6 class="mt-2">Copiar Tudo</h6>
                                <p class="small text-muted">Todos os ${totalItems} itens<br>Pode ficar grande no PPT</p>
                                <button class="btn btn-warning btn-sm w-100 mt-4" onclick="resolvePagination('all')">
                                    <i class="bi bi-clipboard me-1"></i>Copiar Completo
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" onclick="resolvePagination('cancel')">
                    <i class="bi bi-x-lg me-1"></i>Cancelar
                </button>
            </div>
        </div>
    </div>
</div>`;

            // Remove modal anterior se existir
            const existingModal = document.getElementById('paginationModal');
            if (existingModal) existingModal.remove();

            // Adiciona modal ao DOM
            document.body.insertAdjacentHTML('beforeend', modalHtml);
            
            // Função global para resolver
            window.resolvePagination = (action) => {
                let result = { action };
                if (action === 'page') {
                    result.page = parseInt(document.getElementById('pageSelect').value);
                }
                
                // Remove modal
                const modal = document.getElementById('paginationModal');
                const bsModal = bootstrap.Modal.getInstance(modal);
                bsModal.hide();
                modal.remove();
                delete window.resolvePagination;
                
                resolve(result);
            };

            // Mostra modal
            const modal = new bootstrap.Modal(document.getElementById('paginationModal'));
            modal.show();
        });
    }

    function getStatusColorForCopy(status) {
        const colors = {
            'Concluído': '#28a745',
            'DONE': '#28a745',
            'Em Progresso': '#007bff',
            'IN_PROGRESS': '#007bff',
            'Em Andamento': '#17a2b8',
            'A Fazer': '#6c757d',
            'TODO': '#6c757d',
            'Pendente': '#ffc107',
            'PENDING': '#ffc107',
            'Atrasado': '#dc3545',
            'DELAYED': '#dc3545'
        };
        return colors[status] || '#6c757d';
    }

    function generatePlainTextTable() {
        let textTable = 'WBS ID\tTipo\tTarefa/Marco\tDescrição\tData Início\tData Fim\tDuração\tEspecialista\tStatus\n';
        
        wbsData.forEach(item => {
            textTable += `${item.wbs_id}\t${item.type === 'milestone' ? 'Marco' : 'Tarefa'}\t${item.name}\t${item.description}\t${item.start_date}\t${item.end_date}\t${item.duration_days > 0 ? `${item.duration_days} dias` : '-'}\t${item.specialist}\t${getStatusLabel(item.status)}\n`;
        });
        
        return textTable;
    }

    // Expõe funções globais
    window.generateWBS = generateWBS;
    window.exportWBSToExcel = exportWBSToExcel;
    window.copyWBSToClipboard = copyWBSToClipboard;
    window.refreshWBS = refreshWBS;
    window.previewWBS = previewWBS;

    // Expõe função global para cálculo de score
    window.calculateComplexityScore = calculateComplexityScore;

    // Inicializa o módulo
    init();
} 