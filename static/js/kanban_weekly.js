/**
 * Kanban Semanal JavaScript
 * Gerenciamento de tarefas semanais em formato Kanban
 */

// Variáveis globais
let currentSpecialist = null;
let currentWeek = {
    start: null,
    end: null
};

// Elementos DOM
const kanbanBoard = document.getElementById('kanbanBoard');

// Inicialização
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Inicializando Kanban Semanal...');
    
    // Extrai o nome do especialista da URL
    const urlParams = new URLSearchParams(window.location.search);
    currentSpecialist = urlParams.get('specialist');
    
    if (!currentSpecialist) {
        showToast('Especialista não especificado', 'error');
        return;
    }
    
    // Inicializa o kanban
    initializeKanban();
});

// Funções principais
async function initializeKanban() {
    try {
        // Carrega tarefas do especialista
        await loadSpecialistTasks();
        
        // Inicializa eventos
        setupEventListeners();
        
    } catch (error) {
        console.error('❌ Erro ao inicializar kanban:', error);
        showToast('Erro ao inicializar kanban', 'error');
    }
}

async function loadSpecialistTasks() {
    try {
        const response = await fetch(`/backlog/api/specialists/${encodeURIComponent(currentSpecialist)}/kanban-weekly-tasks`);
        
        if (!response.ok) {
            throw new Error(`Erro ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        console.log('✅ Tarefas carregadas:', data);
        
        // Atualiza datas da semana
        currentWeek.start = data.week_start;
        currentWeek.end = data.week_end;
        
        // Renderiza tarefas
        renderTasks(data.tasks);
        
    } catch (error) {
        console.error('❌ Erro ao carregar tarefas:', error);
        showToast('Erro ao carregar tarefas', 'error');
    }
}

function renderTasks(tasks) {
    // Agrupa tarefas por dia
    const tasksByDay = {
        'segunda': [],
        'terca': [],
        'quarta': [],
        'quinta': [],
        'sexta': []
    };
    
    // Distribui tarefas pelos dias
    tasks.forEach(task => {
        task.dias_presentes.forEach(dia => {
            tasksByDay[dia].push(task);
        });
    });
    
    // Renderiza cada coluna
    Object.entries(tasksByDay).forEach(([dia, tarefas]) => {
        const diaNumero = {
            'segunda': 1,
            'terca': 2, 
            'quarta': 3,
            'quinta': 4,
            'sexta': 5
        }[dia];
        
        const coluna = document.querySelector(`.tarefas-container[data-dia="${diaNumero}"]`);
        if (!coluna) return;
        
        // Limpa coluna (mantém apenas o placeholder)
        coluna.innerHTML = '';
        
        // Adiciona tarefas ou placeholder
        if (tarefas.length > 0) {
            tarefas.forEach(tarefa => {
                coluna.appendChild(createTaskCard(tarefa));
            });
        } else {
            coluna.innerHTML = `
                <div class="text-center text-muted p-4">
                    <i class="bi bi-calendar-plus fs-3 opacity-25"></i>
                    <p class="mt-2 small">Nenhuma tarefa</p>
                </div>
            `;
        }
    });
}

function createTaskCard(task) {
    const card = document.createElement('div');
    card.className = 'task-card';
    card.dataset.taskId = task.id;
    
    // Define classes de status
    const statusClass = task.status === 'CONCLUIDA' ? 'concluida' : 
                       task.status === 'EM_ANDAMENTO' ? 'em-andamento' : 
                       task.status === 'REVISAO' ? 'revisao' : '';
    
    if (statusClass) {
        card.classList.add(statusClass);
    }
    
    card.innerHTML = `
        <div class="task-header">
            <h6 class="task-title">${escapeHtml(task.title)}</h6>
            <span class="task-project">${escapeHtml(task.project_name || 'Sem projeto')}</span>
        </div>
        <div class="task-body">
            <div class="task-description">${escapeHtml(task.description || '')}</div>
            <div class="task-meta">
                <span class="task-hours">${task.estimated_effort || 0}h</span>
                <span class="task-status badge ${getStatusClass(task.status)}">${getStatusLabel(task.status)}</span>
            </div>
        </div>
        <div class="task-actions">
            <button class="btn btn-sm btn-success" onclick="marcarComoConcluida(${task.id})">
                <i class="bi bi-check-lg"></i>
            </button>
            <button class="btn btn-sm btn-primary" onclick="editarTarefa(${task.id})">
                <i class="bi bi-pencil"></i>
            </button>
            <button class="btn btn-sm btn-danger" onclick="excluirTarefa(${task.id})">
                <i class="bi bi-trash"></i>
            </button>
        </div>
    `;
    
    return card;
}

// Funções de ação
async function marcarComoConcluida(taskId) {
    try {
        const response = await fetch(`/backlog/api/tasks/${taskId}/complete`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error(`Erro ${response.status}: ${response.statusText}`);
        }
        
        const updatedTask = await response.json();
        
        // Atualiza UI
        const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
        if (taskCard) {
            // Remove classes de status antigas
            taskCard.classList.remove('em-andamento', 'revisao');
            // Adiciona classe concluída
            taskCard.classList.add('concluida');
            
            // Atualiza badge de status
            const statusBadge = taskCard.querySelector('.task-status');
            if (statusBadge) {
                statusBadge.className = `task-status badge ${getStatusClass('CONCLUIDA')}`;
                statusBadge.textContent = getStatusLabel('CONCLUIDA');
            }
        }
        
        showToast('Tarefa marcada como concluída', 'success');
        
    } catch (error) {
        console.error('❌ Erro ao marcar tarefa como concluída:', error);
        showToast('Erro ao marcar tarefa como concluída', 'error');
    }
}

async function editarTarefa(taskId) {
    try {
        const response = await fetch(`/backlog/api/tasks/${taskId}`);
        
        if (!response.ok) {
            throw new Error(`Erro ${response.status}: ${response.statusText}`);
        }
        
        const task = await response.json();
        
        // Preenche o modal com os dados da tarefa
        document.getElementById('taskId').value = task.id;
        document.getElementById('taskTitle').value = task.title;
        document.getElementById('taskDescription').value = task.description || '';
        document.getElementById('taskStatus').value = task.status;
        document.getElementById('taskHours').value = task.estimated_effort || 0;
        
        // Mostra o modal
        const taskModal = new bootstrap.Modal(document.getElementById('taskModal'));
        taskModal.show();
        
    } catch (error) {
        console.error('❌ Erro ao carregar dados da tarefa:', error);
        showToast('Erro ao carregar dados da tarefa', 'error');
    }
}

async function excluirTarefa(taskId) {
    if (!confirm('Tem certeza que deseja excluir esta tarefa?')) {
        return;
    }
    
    try {
        const response = await fetch(`/backlog/api/tasks/${taskId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error(`Erro ${response.status}: ${response.statusText}`);
        }
        
        // Remove o card da UI
        const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
        if (taskCard) {
            taskCard.remove();
        }
        
        showToast('Tarefa excluída com sucesso', 'success');
        
    } catch (error) {
        console.error('❌ Erro ao excluir tarefa:', error);
        showToast('Erro ao excluir tarefa', 'error');
    }
}

// Funções utilitárias
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getStatusClass(status) {
    switch (status) {
        case 'CONCLUIDA': return 'bg-success';
        case 'EM_ANDAMENTO': return 'bg-primary';
        case 'REVISAO': return 'bg-warning';
        default: return 'bg-secondary';
    }
}

function getStatusLabel(status) {
    switch (status) {
        case 'CONCLUIDA': return 'Concluída';
        case 'EM_ANDAMENTO': return 'Em Andamento';
        case 'REVISAO': return 'Revisão';
        default: return 'Pendente';
    }
}

function showToast(message, type = 'info') {
    // Verifica se existe uma função de toast global
    if (typeof window.showToast === 'function') {
        window.showToast(message, type);
    } else {
        // Implementação básica de toast
        console.log(`[${type.toUpperCase()}] ${message}`);
        alert(message);
    }
}

// Função para salvar tarefa editada
async function salvarTarefa() {
    const taskId = document.getElementById('taskId').value;
    const title = document.getElementById('taskTitle').value;
    const description = document.getElementById('taskDescription').value;
    const status = document.getElementById('taskStatus').value;
    const estimated_hours = parseFloat(document.getElementById('taskHours').value) || 0;
    
    if (!title.trim()) {
        showToast('Por favor, preencha o título da tarefa', 'error');
        return;
    }
    
    try {
        const response = await fetch(`/backlog/api/tasks/${taskId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title: title,
                description: description,
                status: status,
                estimated_hours: estimated_hours
            })
        });
        
        if (!response.ok) {
            throw new Error(`Erro ${response.status}: ${response.statusText}`);
        }
        
        const updatedTask = await response.json();
        
        // Fecha o modal
        const taskModal = bootstrap.Modal.getInstance(document.getElementById('taskModal'));
        taskModal.hide();
        
        // Recarrega as tarefas para atualizar a interface
        await loadSpecialistTasks();
        
        showToast('Tarefa atualizada com sucesso', 'success');
        
    } catch (error) {
        console.error('❌ Erro ao salvar tarefa:', error);
        showToast('Erro ao salvar tarefa', 'error');
    }
}

// Exporta funções necessárias globalmente
window.marcarComoConcluida = marcarComoConcluida;
window.editarTarefa = editarTarefa;
window.excluirTarefa = excluirTarefa;
window.salvarTarefa = salvarTarefa; 