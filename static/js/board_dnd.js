/**
 * Script para a funcionalidade do quadro Kanban (Drag and Drop).
 * 
 * Autor: Assistente Gemini
 * Data: 14 de Junho de 2025
 */
function initializeSortable() {
    // --- Variáveis de Estado e Elementos do DOM ---
    const backlogId = window.boardData.backlogId;
    let tasksData = window.boardData.tasks || [];
    const columns = window.boardData.columns || [];
    const specialists = window.boardData.specialists || [];
    
    const taskModal = new bootstrap.Modal(document.getElementById('taskModal'));
    const taskForm = document.getElementById('taskForm');
    const importFileInput = document.getElementById('import-file-input');

    // --- Funções de Inicialização ---

    function init() {
        if (!backlogId) {
            console.error("ID do Backlog não encontrado. O quadro Kanban não pode ser inicializado.");
            return;
        }
        setupEventListeners();
        populateStaticModalData();
        renderTasks();
        initializeSortableJS();
        loadSpecialists();
        loadProjectHeader();
        loadSprintVisibility();
    }

    function setupEventListeners() {
        // Event listener para importação de arquivos
        importFileInput?.addEventListener('change', handleFileImport);
        
        // Event listener para salvar tarefa
        taskForm?.addEventListener('submit', (e) => {
            e.preventDefault();
            saveTask();
        });
    }
    
    function populateStaticModalData() {
        const statusSelect = document.getElementById('taskStatus');
        if (statusSelect && columns.length > 0) {
            statusSelect.innerHTML = '';
            columns.forEach(c => {
                statusSelect.innerHTML += `<option value="${c.id}">${c.name}</option>`;
            });
        }
    }

    async function loadSpecialists() {
        try {
            const response = await fetch('/backlog/api/available-specialists');
            if (response.ok) {
                const specialistsData = await response.json();
                const specialistSelect = document.getElementById('taskSpecialistId');
                if (specialistSelect) {
                    specialistSelect.innerHTML = '<option value="">Não atribuído</option>';
                    specialistsData.forEach(specialistName => {
                        specialistSelect.innerHTML += `<option value="${specialistName}">${specialistName}</option>`;
                    });
                }
                // Atualiza dados globais
                window.boardData.specialists = specialistsData;
            }
        } catch (error) {
            console.error('Erro ao carregar especialistas:', error);
        }
    }

    async function loadProjectHeader() {
        const projectId = window.boardData.projectId;
        const headerDiv = document.getElementById('projectHeader');
        if (!projectId || !headerDiv) {
            console.warn("ID do Projeto ou div do cabeçalho não encontrados.");
            return;
        }

        try {
            const [detailsRes, phaseRes, projectTypeRes] = await Promise.all([
                fetch(`/backlog/api/projects/${projectId}/details`),
                fetch(`/backlog/api/projects/${projectId}/current-phase`),
                fetch(`/backlog/api/projects/${projectId}/project-type`)
            ]);
            
            const data = detailsRes.ok ? await detailsRes.json() : {};
            const phase = phaseRes.ok ? await phaseRes.json() : {};
            const projectType = projectTypeRes.ok ? await projectTypeRes.json() : {};
            
            // Preenche os dados básicos do projeto
            document.getElementById('headerProjectName').textContent = data.projeto || 'Projeto não encontrado';
            document.getElementById('headerSpecialist').textContent = `Especialista: ${data.especialista || 'N/A'}`;
            
            // Verifica se existe campo AM nos dados e cria se necessário
            let amElement = document.getElementById('headerAM');
            if (!amElement) {
                const specialistElement = document.getElementById('headerSpecialist');
                amElement = document.createElement('p');
                amElement.className = 'small text-muted mb-1';
                amElement.id = 'headerAM';
                specialistElement.parentNode.insertBefore(amElement, specialistElement.nextSibling);
            }
            amElement.textContent = `AM: ${data.account_manager || '-'}`;
            
            // Atualiza informações da fase com tipo do projeto
            const phaseContainer = document.getElementById('headerPhase');
            if (phaseContainer) {
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
            }
            
            // Preenche métricas básicas
            const metrics = {
                'STATUS': data.status || 'N/A',
                'HORAS REST.': `${Math.round(data.horasrestantes || 0)}h`,
                'HORAS PREV.': `${Math.round(data.horas || 0)}h`,
                'CONCLUSÃO': `${Math.round(data.conclusao || 0)}%`,
                'TÉRMINO PREVISTO': data.vencimentoem ? new Date(data.vencimentoem).toLocaleDateString('pt-BR', { timeZone: 'UTC' }) : '-'
            };

            let metricsHtml = '';
            for (const [label, value] of Object.entries(metrics)) {
                metricsHtml += `
                    <div class="col-auto">
                        <div class="metric-item">
                            <div class="metric-label">${label}</div>
                            <div class="metric-value">${value}</div>
                        </div>
                    </div>
                `;
            }
            
            document.getElementById('headerMetrics').innerHTML = metricsHtml;

            // Mostra o cabeçalho
            headerDiv.style.display = 'block';

        } catch (error) {
            console.error("Erro ao carregar cabeçalho do projeto:", error);
            // Mostra o cabeçalho com uma mensagem de erro
            headerDiv.style.display = 'block';
            document.getElementById('headerProjectName').textContent = 'Erro ao carregar dados do projeto';
        }
    }

    function renderTasks() {
        // Limpa todas as colunas
        columns.forEach(column => {
            const columnElement = document.getElementById(`column-${column.id}`);
            if (columnElement) {
                columnElement.innerHTML = '';
            }
        });

        // Renderiza tarefas em suas respectivas colunas
        tasksData.forEach(task => {
            const taskElement = createTaskElement(task);
            const columnElement = document.getElementById(`column-${task.column_id}`);
            
            if (columnElement) {
                columnElement.appendChild(taskElement);
            } else {
                console.error(`❌ Coluna ${task.column_id} não encontrada para tarefa ${task.id}`);
            }
        });

        updateAllColumnCounts();
    }

    function createTaskElement(task) {
        const taskDiv = document.createElement('div');
        taskDiv.className = 'task-card';
        taskDiv.draggable = true;
        taskDiv.dataset.taskId = task.id;
        taskDiv.dataset.columnId = task.column_id;
        
        // Função para formatar datas
        function formatDate(dateString) {
            if (!dateString) return null;
            try {
                const date = new Date(dateString);
                return date.toLocaleDateString('pt-BR');
            } catch (e) {
                return null;
            }
        }
        
        // Formatar datas
        const startDate = formatDate(task.start_date);
        const dueDate = formatDate(task.due_date);
        
        taskDiv.innerHTML = `
            <div class="task-title">${task.title}</div>
            ${task.description ? `<div class="task-description">${task.description}</div>` : ''}
            
            <!-- ✅ NOVA SEÇÃO: Datas -->
            ${(startDate || dueDate) ? `
                <div class="task-dates" style="margin-bottom: 0.5rem; font-size: 0.75em; color: #666;">
                    ${startDate ? `<div style="display: flex; align-items: center; margin-bottom: 2px;">
                        <i class="bi bi-play-circle" style="margin-right: 4px; color: #28a745;"></i>
                        <span>Início: ${startDate}</span>
                    </div>` : ''}
                    ${dueDate ? `<div style="display: flex; align-items: center;">
                        <i class="bi bi-flag" style="margin-right: 4px; color: #dc3545;"></i>
                        <span>Prazo: ${dueDate}</span>
                    </div>` : ''}
                </div>
            ` : ''}
            
            <div class="task-meta">
                <div>
                    ${task.priority ? `<span class="task-priority priority-${task.priority.toLowerCase()}">${task.priority}</span>` : ''}
                    ${task.estimated_hours ? `<span class="task-estimated-hours">${task.estimated_hours}h</span>` : ''}
                </div>
                ${task.specialist_name ? `<span class="task-specialist">${task.specialist_name}</span>` : ''}
            </div>
        `;
        taskDiv.addEventListener('click', () => openTaskModal(task.column_id, task));
        return taskDiv;
    }

    function updateAllColumnCounts() {
        columns.forEach(column => {
            // Garante que a comparação seja feita com o mesmo tipo
            const count = tasksData.filter(t => parseInt(t.column_id) === parseInt(column.id)).length;
            const countElement = document.getElementById(`count-${column.id}`);
            if (countElement) {
                countElement.textContent = count;
            }
        });
    }

    function initializeSortableJS() {
        console.log('🚀 Inicializando SortableJS...');
        
        // Remove qualquer instância anterior do SortableJS
        document.querySelectorAll('.task-list').forEach(el => {
            if (el.sortable) {
                el.sortable.destroy();
            }
        });
        
        // Inicializa SortableJS para cada coluna
        document.querySelectorAll('.task-list').forEach(taskList => {
            console.log(`📋 Configurando coluna: ${taskList.id}`);
            
            new Sortable(taskList, {
                group: 'shared', // Nome do grupo para permitir movimento entre colunas
                animation: 150,
                ghostClass: 'task-card-ghost',
                chosenClass: 'task-card-chosen',
                dragClass: 'task-card-drag',
                
                // Evento quando o drag termina
                onEnd: function(evt) {
                    const fromColumnId = evt.from.id.replace('column-', '');
                    const toColumnId = evt.to.id.replace('column-', '');
                    const taskId = evt.item.dataset.taskId;
                    
                    // Condição para salvar: mudou de coluna OU mudou de posição na mesma coluna
                    if (fromColumnId !== toColumnId || evt.oldIndex !== evt.newIndex) {
                        console.log(`🚀 Salvando nova ordem: Tarefa ${taskId}, Coluna ${toColumnId}, Posição ${evt.newIndex}`);
                        updateTaskColumn(taskId, toColumnId, evt.newIndex);
                    } else {
                        console.log('ℹ️ Tarefa não teve sua posição alterada.');
                    }
                }
            });
        });
        
        console.log('✅ SortableJS inicializado com sucesso!');
    }

    // Função separada para atualizar a tarefa no servidor
    async function updateTaskColumn(taskId, newColumnId, newPosition) {
        try {
            console.log(`🔄 Enviando atualização: Tarefa ${taskId} -> Coluna ${newColumnId}`);
            
            const response = await fetch(`/backlog/api/tasks/${taskId}/move`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    column_id: parseInt(newColumnId),
                    position: newPosition
                })
            });
            
            if (response.ok) {
                const result = await response.json();
                console.log('✅ Tarefa atualizada com sucesso:', result);
                
                // Atualiza os dados locais
                const task = tasksData.find(t => t.id == taskId);
                if (task) {
                    task.column_id = parseInt(newColumnId);
                }
                
                // Atualiza contadores das colunas
                updateAllColumnCounts();
                
                showToast('Tarefa movida com sucesso!', 'success');
            } else {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Erro ao mover tarefa');
            }
        } catch (error) {
            console.error('❌ Erro ao atualizar tarefa:', error);
            showToast('Erro ao mover tarefa: ' + error.message, 'error');
            
            // Recarrega as tarefas para reverter a mudança visual
            await reloadTasks();
        }
    }

    async function openTaskModal(columnId, task = null) {
        taskForm.reset();
        document.getElementById('taskStatus').value = columnId;
        
        if (task) {
            // Editando tarefa existente
            document.getElementById('taskModalLabel').textContent = 'Editar Tarefa';
            document.getElementById('taskId').value = task.id;
            document.getElementById('taskTitle').value = task.title;
            
            // ✅ CORRIGIDO: Carrega descrição considerando editor rico
            if (window.loadContentIntoField) {
                window.loadContentIntoField('taskDescription', task.description || '');
            } else {
                document.getElementById('taskDescription').value = task.description || '';
                console.log('⚠️ loadContentIntoField não encontrada, usando fallback');
            }
            document.getElementById('taskPriority').value = task.priority || 'Média';
            document.getElementById('taskStatus').value = task.column_id;
            document.getElementById('taskSpecialistId').value = task.specialist_name || '';
            document.getElementById('taskEstimatedEffort').value = task.estimated_effort || '';
            
            // Novos campos
            document.getElementById('taskStartDate').value = task.start_date ? task.start_date.split('T')[0] : '';
            document.getElementById('taskDueDate').value = task.due_date ? task.due_date.split('T')[0] : '';
            document.getElementById('taskLoggedTime').value = task.logged_time || 0;
            document.getElementById('taskIsUnplanned').checked = task.is_unplanned || false;
            
            // Botão de exclusão
            document.getElementById('deleteTaskBtn').style.display = 'block';
        } else {
            // Criando nova tarefa
            document.getElementById('taskModalLabel').textContent = 'Adicionar Tarefa';
            document.getElementById('taskId').value = '';
            document.getElementById('deleteTaskBtn').style.display = 'none';

            // Opcional: Pré-preencher especialista com o do projeto ao criar nova tarefa
            const projectSpecialist = document.getElementById('headerSpecialist').textContent.replace('Especialista: ', '').trim();
            if (projectSpecialist && projectSpecialist !== 'N/A') {
                document.getElementById('taskSpecialistId').value = projectSpecialist;
            }
        }
        
        taskModal.show();
    }

    async function saveTask() {
        const taskId = document.getElementById('taskId').value;
        const title = document.getElementById('taskTitle').value;
        const columnId = document.getElementById('taskStatus').value; // O select de status agora contém o ID da coluna
        
        if (!title.trim()) {
            showToast('O título da tarefa é obrigatório.', 'error');
            return;
        }

        const taskData = {
            title: title,
            description: document.getElementById('taskDescription').value,
            priority: document.getElementById('taskPriority').value,
            specialist_name: document.getElementById('taskSpecialistId').value,
            estimated_hours: document.getElementById('taskEstimatedEffort').value,
            start_date: document.getElementById('taskStartDate').value || null,
            due_date: document.getElementById('taskDueDate').value || null,
            logged_time: parseFloat(document.getElementById('taskLoggedTime').value) || null,
            is_unplanned: document.getElementById('taskIsUnplanned').checked,
            status: columnId, // Envia o ID da coluna como 'status' para a API de update
        };

        const url = taskId ? `/backlog/api/tasks/${taskId}` : `/backlog/api/backlogs/${backlogId}/tasks`;
        const method = taskId ? 'PUT' : 'POST';

        if (!taskId) {
            // Para novas tarefas, a API espera 'column_id' e 'position'
            delete taskData.status; // Remove o campo 'status' que não é usado na criação
            taskData.column_id = parseInt(columnId);
            const columnTasks = tasksData.filter(t => t.column_id == columnId);
            taskData.position = columnTasks.length;
        }
        
        try {
            const response = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(taskData)
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Falha ao salvar a tarefa.');
            
            taskModal.hide();
            showToast('Tarefa salva com sucesso!', 'success');
            
            // Atualiza a UI
            if (taskId) { // Edição
                const index = tasksData.findIndex(t => t.id == taskId);
                if (index !== -1) {
                    tasksData[index] = result.task || result;
                }
                
                // 🔄 SINCRONIZAÇÃO: Emite evento de tarefa atualizada
                if (window.SyncManager) {
                    window.SyncManager.emitTaskUpdated(taskId, result.task || result, 'backlog');
                }
            } else { // Criação
                tasksData.push(result.task || result);
                
                // 🔄 SINCRONIZAÇÃO: Emite evento de tarefa criada
                if (window.SyncManager) {
                    window.SyncManager.emitTaskCreated(result.task || result, 'backlog');
                }
            }
            renderTasks();

        } catch (error) {
            console.error('Erro ao salvar tarefa:', error);
            showToast(error.message, 'error');
        }
    }

    async function deleteTask() {
        const taskId = document.getElementById('taskId').value;
        if (!taskId || !confirm('Tem certeza que deseja excluir esta tarefa?')) return;

        try {
            const response = await fetch(`/backlog/api/tasks/${taskId}`, { method: 'DELETE' });
            
            if (!response.ok) {
                // Tenta obter erro da resposta se houver conteúdo
                let errorMessage = 'Falha ao excluir a tarefa.';
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.error || errorMessage;
                } catch {
                    // Se não conseguir fazer parse do JSON, usa mensagem padrão
                    errorMessage = `Erro ${response.status}: ${response.statusText}`;
                }
                throw new Error(errorMessage);
            }

            taskModal.hide();
            showToast('Tarefa excluída com sucesso!', 'success');
            
            // 🔄 SINCRONIZAÇÃO: Emite evento de tarefa excluída
            if (window.SyncManager) {
                window.SyncManager.emitTaskDeleted(taskId, 'backlog');
            }
            
            // Atualiza UI
            tasksData = tasksData.filter(t => t.id != taskId);
            renderTasks();

        } catch (error) {
            console.error('Erro ao excluir tarefa:', error);
            showToast(error.message, 'error');
        }
    }

    async function handleFileImport(event) {
        const file = event.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('excel_file', file);

        showToast('Importando arquivo...', 'info');

        try {
            const response = await fetch(`/backlog/api/backlogs/${backlogId}/import-tasks`, {
                method: 'POST',
                body: formData
            });
            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.message || 'Erro na importação.');
            }

            showToast(result.message, 'success');
            
            // Recarrega as tarefas após importação
            await reloadTasks();
            
        } catch (error) {
            console.error('Erro ao importar arquivo:', error);
            showToast(error.message, 'error');
        } finally {
            // Limpa o input para permitir importar o mesmo arquivo novamente
            importFileInput.value = '';
        }
    }

    async function reloadTasks() {
        try {
            const response = await fetch(`/backlog/api/tasks?backlog_id=${backlogId}`);
            if (response.ok) {
                const tasks = await response.json();
                tasksData = tasks;
                renderTasks();
            }
        } catch (error) {
            console.error('Erro ao recarregar tarefas:', error);
        }
    }

    function exportTasks() {
        // Implementar exportação se necessário
        showToast('Funcionalidade de exportação em desenvolvimento', 'info');
    }
    
    // --- Utilitários ---
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
    
    // --- Funções de Sprint Visibility ---
    async function loadSprintVisibility() {
        const backlogId = window.boardData.backlogId;
        if (!backlogId) {
            console.log('⚠️ BacklogId não encontrado, não é possível carregar visibilidade do sprint');
            return;
        }
        
        console.log(`🔄 Carregando visibilidade do sprint para backlog ${backlogId}`);
        
        try {
            const response = await fetch(`/backlog/api/backlogs/${backlogId}/details`);
            if (response.ok) {
                const data = await response.json();
                const sprintSwitch = document.getElementById('sprintVisibilitySwitch');
                
                console.log('📡 Dados do backlog recebidos:', data);
                console.log(`🎯 available_for_sprint: ${data.available_for_sprint}`);
                
                if (sprintSwitch) {
                    sprintSwitch.checked = data.available_for_sprint === true;
                    console.log(`✅ Switch definido para: ${sprintSwitch.checked}`);
                } else {
                    console.warn('⚠️ Switch sprintVisibilitySwitch não encontrado no DOM');
                }
            } else {
                console.error(`❌ Erro na resposta da API: ${response.status} ${response.statusText}`);
            }
        } catch (error) {
            console.error('❌ Erro ao carregar visibilidade do sprint:', error);
        }
    }
    
    async function toggleSprintVisibility() {
        const backlogId = window.boardData.backlogId;
        const sprintSwitch = document.getElementById('sprintVisibilitySwitch');
        
        if (!backlogId || !sprintSwitch) {
            console.warn('⚠️ BacklogId ou switch não encontrado');
            return;
        }
        
        const isEnabled = sprintSwitch.checked;
        console.log(`🔄 Alterando visibilidade do sprint para: ${isEnabled}`);
        
        try {
            const response = await fetch(`/backlog/api/backlogs/${backlogId}/sprint-availability`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    available_for_sprint: isEnabled
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                const action = isEnabled ? 'habilitado' : 'desabilitado';
                showToast(`Projeto ${action} para exibição no Sprint`, 'success');
                console.log(`✅ Sprint visibility ${action}:`, data);
            } else {
                const errorData = await response.json();
                console.error(`❌ Erro na API: ${response.status}`, errorData);
                throw new Error(errorData.error || 'Erro ao atualizar visibilidade');
            }
        } catch (error) {
            console.error('❌ Erro ao atualizar visibilidade do sprint:', error);
            showToast('Erro ao atualizar configuração do Sprint', 'error');
            // Reverte o switch em caso de erro
            sprintSwitch.checked = !isEnabled;
            console.log(`🔄 Switch revertido para: ${sprintSwitch.checked}`);
        }
    }
    
    // --- Exposição de Funções e Inicialização ---
    window.openTaskModal = openTaskModal;
    window.saveTask = saveTask;
    window.deleteTask = deleteTask;
    window.importTasks = () => importFileInput.click();
    window.exportTasks = exportTasks;
    window.toggleSprintVisibility = toggleSprintVisibility;
    window.loadSprintVisibility = loadSprintVisibility;

    // 🔄 SINCRONIZAÇÃO: Registra listeners para eventos de outros módulos
    function registerSyncListeners() {
        if (window.SyncManager) {
            // Listener para tarefas atualizadas em outros módulos
            window.SyncManager.on('task_updated', (data, source) => {
                console.log(`🔄 [Backlog] Tarefa atualizada em ${source}:`, data);
                // Atualiza a tarefa na lista local se existir
                const taskIndex = tasksData.findIndex(t => t.id == data.taskId);
                if (taskIndex !== -1) {
                    tasksData[taskIndex] = { ...tasksData[taskIndex], ...data.taskData };
                    renderTasks();
                }
            }, 'backlog');
            
            // Listener para tarefas excluídas em outros módulos
            window.SyncManager.on('task_deleted', (data, source) => {
                console.log(`🔄 [Backlog] Tarefa excluída em ${source}:`, data);
                // Remove a tarefa da lista local se existir
                const originalLength = tasksData.length;
                tasksData = tasksData.filter(t => t.id != data.taskId);
                if (tasksData.length < originalLength) {
                    renderTasks();
                }
            }, 'backlog');
            
            // Listener para tarefas movidas entre sprints
            window.SyncManager.on('task_moved', (data, source) => {
                console.log(`🔄 [Backlog] Tarefa movida em ${source}:`, data);
                // Se a tarefa foi movida para fora de uma sprint, pode aparecer no backlog
                if (data.toSprintId === null) {
                    // Recarrega tarefas para incluir a tarefa que voltou ao backlog
                    reloadTasks();
                }
            }, 'backlog');
            
            console.log('✅ [Backlog] Listeners de sincronização registrados');
        }
    }
    
    // Inicializa automaticamente
    init();
    
    // Registra listeners de sincronização após inicialização
    registerSyncListeners();
}

// Expõe a função principal globalmente para ser chamada pelo template
window.initializeSortable = initializeSortable; 