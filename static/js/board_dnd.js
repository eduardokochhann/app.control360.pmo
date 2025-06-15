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
        
        taskDiv.innerHTML = `
            <div class="task-title">${task.title}</div>
            ${task.description ? `<div class="task-description">${task.description}</div>` : ''}
            <div class="task-meta">
                <div>
                    ${task.priority ? `<span class="task-priority priority-${task.priority.toLowerCase()}">${task.priority}</span>` : ''}
                    ${task.estimated_effort ? `<span class="task-estimated-hours">${task.estimated_effort}h</span>` : ''}
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
        const modalTitle = document.getElementById('taskModalLabel');
        const deleteBtn = document.getElementById('deleteTaskBtn');

        if (task) {
            // Editando tarefa existente
            modalTitle.textContent = 'Editar Tarefa';
            deleteBtn.style.display = 'block';
            
            document.getElementById('taskId').value = task.id;
            document.getElementById('taskColumnId').value = task.column_id;
            document.getElementById('taskTitle').value = task.title;
            document.getElementById('taskDescription').value = task.description || '';
            document.getElementById('taskSpecialistId').value = task.specialist_id || '';
            document.getElementById('taskPriority').value = task.priority || 'Média';
            document.getElementById('taskEstimatedEffort').value = task.estimated_effort || '';
            document.getElementById('taskStatus').value = task.column_id;

        } else {
            // Criando nova tarefa
            modalTitle.textContent = 'Nova Tarefa';
            deleteBtn.style.display = 'none';
            document.getElementById('taskId').value = '';
            document.getElementById('taskColumnId').value = columnId;
        }
        taskModal.show();
    }

    async function saveTask() {
        const taskId = document.getElementById('taskId').value;
        const columnId = document.getElementById('taskColumnId').value;
        
        const data = {
            title: document.getElementById('taskTitle').value,
            description: document.getElementById('taskDescription').value,
            priority: document.getElementById('taskPriority').value,
            estimated_effort: document.getElementById('taskEstimatedEffort').value || null,
            specialist_id: document.getElementById('taskSpecialistId').value || null,
            backlog_id: backlogId,
            column_id: document.getElementById('taskStatus').value,
        };

        const url = taskId ? `/backlog/api/tasks/${taskId}` : `/backlog/api/backlogs/${backlogId}/tasks`;
        const method = taskId ? 'PUT' : 'POST';

        try {
            const response = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
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
            } else { // Criação
                tasksData.push(result.task || result);
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
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Falha ao excluir a tarefa.');

            taskModal.hide();
            showToast('Tarefa excluída com sucesso!', 'success');
            
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
    function showToast(message, type = 'info') {
        // Usa a função do board.js se disponível
        if (typeof window.showToast === 'function') {
            window.showToast(message, type);
        } else {
            console.log(`[${type.toUpperCase()}] TOAST: ${message}`);
            alert(message);
        }
    }
    
    // --- Exposição de Funções e Inicialização ---
    window.openTaskModal = openTaskModal;
    window.saveTask = saveTask;
    window.deleteTask = deleteTask;
    window.importTasks = () => importFileInput.click();
    window.exportTasks = exportTasks;

    // Inicializa automaticamente
    init();
}

// Expõe a função principal globalmente para ser chamada pelo template
window.initializeSortable = initializeSortable; 