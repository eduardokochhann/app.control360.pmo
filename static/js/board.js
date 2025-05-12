// Funções movidas para o escopo global
// Função para formatar data para exibição (DD/MM/YYYY)
function formatDateForDisplay(isoDateString) {
    if (!isoDateString) return 'N/A';
    try {
        // Tenta criar a data. Se a string ISO já tiver timezone Z (UTC), 
        // o objeto Date a interpretará como UTC. Se não tiver, interpretará como local.
        const date = new Date(isoDateString);
        if (isNaN(date.getTime())) {
            // Se a data for inválida após a primeira tentativa (pode ser só YYYY-MM-DD)
            const parts = isoDateString.split('-');
            if (parts.length === 3) {
                const year = parseInt(parts[0], 10);
                const month = parseInt(parts[1], 10) - 1; // Mês é 0-indexado no JS
                const day = parseInt(parts[2], 10);
                const dateOnly = new Date(Date.UTC(year, month, day)); // Usar UTC para consistência com ISO
                if (!isNaN(dateOnly.getTime())) {
                    const d = String(dateOnly.getUTCDate()).padStart(2, '0');
                    const m = String(dateOnly.getUTCMonth() + 1).padStart(2, '0');
                    const y = dateOnly.getUTCFullYear();
                    return `${d}/${m}/${y}`;
                }
            }
            console.warn("formatDateForDisplay: Data inválida recebida após split:", isoDateString);
            return 'Data inválida';
        }
        // Formata como DD/MM/YYYY HH:MM se tiver hora, senão só DD/MM/YYYY
        const day = String(date.getUTCDate()).padStart(2, '0');
        const month = String(date.getUTCMonth() + 1).padStart(2, '0'); // Mês é 0-indexado
        const year = date.getUTCFullYear();
        
        let hours = null, minutes = null;
        // Verifica se a string original continha informação de hora (T)
        if (isoDateString.includes('T')) {
            hours = String(date.getUTCHours()).padStart(2, '0');
            minutes = String(date.getUTCMinutes()).padStart(2, '0');
        }

        let formattedDate = `${day}/${month}/${year}`;
        if (hours && minutes) {
            formattedDate += ` ${hours}:${minutes}`;
        }
        return formattedDate;
    } catch (e) {
        console.error("Erro ao formatar data:", isoDateString, e);
        return 'Data inválida';
    }
}

// Função auxiliar para escapar HTML (simples)
function escapeHTML(str) {
    if (str === null || typeof str === 'undefined') return '';
    return str.toString()
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Variáveis do modal de notas que serão inicializadas no DOMContentLoaded
let taskNotesModalInstance, taskNotesModalTaskNameEl, taskNotesListEl, currentTaskNotesTaskIdInputEl, taskNotesLoadingMessageEl, noTaskNotesMessageEl, noteEventDateInputEl, addNoteFormEl;

async function loadAndShowTaskNotes(taskId, taskName) {
    console.log('[Debug Notas] loadAndShowTaskNotes FOI CHAMADA com taskId:', taskId, 'taskName:', taskName);

    if (!taskNotesModalInstance || !taskNotesModalTaskNameEl || !taskNotesListEl || !currentTaskNotesTaskIdInputEl || !taskNotesLoadingMessageEl || !noTaskNotesMessageEl || !noteEventDateInputEl) {
        console.error("[Debug Notas] Elementos do modal de notas não estão todos disponíveis (loadAndShowTaskNotes).");
        showToast("Erro ao tentar abrir o modal de notas. Elementos não encontrados.", "error");
        return;
    }

    taskNotesModalTaskNameEl.textContent = escapeHTML(taskName) || 'Tarefa Desconhecida';
    currentTaskNotesTaskIdInputEl.value = taskId;
    taskNotesListEl.innerHTML = ''; // Limpa a lista de notas anterior
    taskNotesLoadingMessageEl.style.display = 'block';
    noTaskNotesMessageEl.style.display = 'none';
    
    if (noteEventDateInputEl) {
        noteEventDateInputEl.value = new Date().toISOString().split('T')[0]; // Data atual para nova nota
    }

    console.log('[Debug Notas] Prestes a chamar taskNotesModalInstance.show(). Instância:', taskNotesModalInstance);
    taskNotesModalInstance.show();

    try {
        // Usar a URL de API_URLS que foi definida em board.html
        let url_get_notes = API_URLS.getTaskNotes.replace('TASK_ID_PLACEHOLDER', taskId);
        const response = await fetch(url_get_notes);
        if (!response.ok) {
            throw new Error(`Erro ao buscar notas: ${response.status} ${response.statusText}`);
        }
        const notes = await response.json();

        taskNotesLoadingMessageEl.style.display = 'none';
        if (notes && notes.length > 0) {
            notes.forEach(note => {
                const noteEl = document.createElement('li'); // Usar <li> para ul
                // A classe base é list-group-item. As classes de tipo de nota são adicionadas dinamicamente.
                noteEl.className = `list-group-item mb-2 note-type-${escapeHTML(note.note_type_name || 'INFO')}`;

                noteEl.innerHTML = `
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${escapeHTML(note.note_type || 'Informação')}</h6>
                        <small class="note-meta">Ocorrência: ${formatDateForDisplay(note.event_date)}</small>
                    </div>
                    <p class="mb-1 note-description">${escapeHTML(note.description)}</p>
                    <small class="note-meta">Registrado em: ${formatDateForDisplay(note.created_at)} por Usuário #${escapeHTML(note.author_id || 'N/A')}</small>
                `;
                taskNotesListEl.appendChild(noteEl);
            });
        } else {
            noTaskNotesMessageEl.style.display = 'block';
        }
    } catch (error) {
        console.error("Erro ao carregar notas da tarefa:", error);
        taskNotesLoadingMessageEl.style.display = 'none';
        taskNotesListEl.innerHTML = '<li class="list-group-item text-danger">Erro ao carregar notas. Tente novamente mais tarde.</li>';
        showToast("Erro ao carregar notas da tarefa.", "error");
    }
}

// Garantir que o DOM está carregado antes de executar o script
document.addEventListener('DOMContentLoaded', () => {
    const taskNotesModalDOMEl = document.getElementById('taskNotesModal');
    if (taskNotesModalDOMEl) {
        taskNotesModalInstance = new bootstrap.Modal(taskNotesModalDOMEl);
    }
    taskNotesModalTaskNameEl = document.getElementById('taskNotesModalTaskName');
    taskNotesListEl = document.getElementById('taskNotesList'); // O <ul>
    addNoteFormEl = document.getElementById('addNoteForm');
    currentTaskNotesTaskIdInputEl = document.getElementById('currentTaskNotesTaskId'); 
    taskNotesLoadingMessageEl = document.getElementById('taskNotesLoadingMessage');
    noTaskNotesMessageEl = document.getElementById('noTaskNotesMessage');
    noteEventDateInputEl = document.getElementById('noteEventDate'); 
    const noteTypeSelectEl = document.getElementById('noteType');
    const noteDescriptionTextareaEl = document.getElementById('noteDescription');

    // Validação básica se os elementos essenciais foram encontrados
    if (!taskNotesModalInstance) console.error("Instância do Modal de Notas da Tarefa (taskNotesModalInstance) não pôde ser criada.");
    if (!addNoteFormEl) console.error("Formulário de adicionar nota (addNoteFormEl) não encontrado.");
    if (!taskNotesListEl) console.error("Elemento da lista de notas (taskNotesListEl) não encontrado.");

    // Event listener para o formulário de adicionar nota
    if (addNoteFormEl) {
        addNoteFormEl.addEventListener('submit', async (event) => {
            event.preventDefault();
            const taskId = currentTaskNotesTaskIdInputEl.value;
            const description = noteDescriptionTextareaEl.value.trim();
            const event_date = noteEventDateInputEl.value;
            const note_type = noteTypeSelectEl.value; // Valor do select (INFO, ISSUE, etc.)

            if (!description || !event_date || !note_type || !taskId) {
                showToast("Todos os campos são obrigatórios para adicionar a nota.", "warning");
                return;
            }

            const noteData = {
                description: description,
                event_date: event_date,
                note_type: note_type 
            };

            try {
                let url_add_note = API_URLS.addTaskNote.replace('TASK_ID_PLACEHOLDER', taskId);
                const response = await fetch(url_add_note, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        // Adicionar CSRF token se necessário: 'X-CSRFToken': csrftoken
                    },
                    body: JSON.stringify(noteData)
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ message: 'Erro desconhecido ao adicionar nota.' }));
                    throw new Error(errorData.message || `Erro ${response.status}: ${response.statusText}`);
                }
                // const newNote = await response.json(); // Desnecessário se apenas recarregarmos
                showToast("Nota adicionada com sucesso!", "success");
                addNoteFormEl.reset(); // Limpa o formulário
                noteEventDateInputEl.value = new Date().toISOString().split('T')[0]; // Reseta data do evento para hoje
                // Recarrega as notas no modal
                if (taskId && taskNotesModalTaskNameEl.textContent) {
                    loadAndShowTaskNotes(taskId, taskNotesModalTaskNameEl.textContent);
                }
            } catch (error) {
                console.error("Erro ao adicionar nota:", error);
                showToast(`Erro ao adicionar nota: ${error.message}`, "error");
            }
        });
    }

    // Event listener DELEGADO para os botões de notas nos cards
    // Escuta no #kanbanBoard pois é um pai estático mais próximo que body
    const kanbanBoardEl = document.getElementById('kanbanBoard'); // Certifique-se que seu board principal tem este ID
    if (kanbanBoardEl) {
        kanbanBoardEl.addEventListener('click', function(event) {
            const targetButton = event.target.closest('.btn-task-notes');
            if (targetButton) {
                console.log('[Debug Notas] CLIQUE DETECTADO no .btn-task-notes dentro de #kanbanBoard.');
                event.stopPropagation(); // Previne que o clique no botão abra o modal de edição da tarefa
                const taskId = targetButton.dataset.taskId;
                const taskName = targetButton.dataset.taskName;
                if (taskId && taskName) {
                    loadAndShowTaskNotes(taskId, taskName);
                } else {
                    console.error('Task ID ou Task Name não encontrado no botão de notas.');
                    showToast('Não foi possível carregar as notas: dados da tarefa ausentes.', 'error');
                }
            }
        });
    } else {
        console.warn("#kanbanBoard não encontrado. O listener delegado para notas pode não funcionar.");
        // Fallback para document.body se #kanbanBoard não for encontrado, embora menos performático
        document.body.addEventListener('click', function(event) {
            const targetButton = event.target.closest('.btn-task-notes');
            if (targetButton) {
                console.log('[Debug Notas] CLIQUE DETECTADO no .btn-task-notes dentro de document.body (fallback).');
                event.stopPropagation();
                const taskId = targetButton.dataset.taskId;
                const taskName = targetButton.dataset.taskName;
                if (taskId && taskName) {
                    loadAndShowTaskNotes(taskId, taskName);
                } else {
                    console.error('Task ID ou Task Name não encontrado no botão de notas (fallback listener).');
                    showToast('Não foi possível carregar as notas: dados da tarefa ausentes (fallback).', 'error');
                }
            }
        });
    }

}); // Fim do DOMContentLoaded

// ... (restante do código existente em board.js, se houver) ...

// Certifique-se de que a função showToast está definida,
// geralmente em board_utils.js ou em um script global.
// Exemplo de showToast (se não existir):

function showToast(message, type = 'info') {
    // Implementação básica de um toast. Você pode usar uma biblioteca como Toastify.js ou Bootstrap Toasts.
    console.log(`[Toast-${type}]: ${message}`);
    const toastContainer = document.getElementById('toastPlacement');
    if (!toastContainer) {
        const tempContainer = document.createElement('div');
        tempContainer.id = 'toastPlacement';
        tempContainer.style.position = 'fixed';
        tempContainer.style.top = '20px';
        tempContainer.style.right = '20px';
        tempContainer.style.zIndex = '1090'; // Acima de modais Bootstrap (1050-1070)
        document.body.appendChild(tempContainer);
    }

    const toastId = 'toast-' + Date.now();
    const toastHTML = `
        <div id="${toastId}" class="toast align-items-center text-white bg-${type === 'error' ? 'danger' : type} border-0" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;
    
    const toastPlacement = document.getElementById('toastPlacement');
    if (toastPlacement) {
         toastPlacement.insertAdjacentHTML('beforeend', toastHTML);
         const toastElement = document.getElementById(toastId);
         if (toastElement) {
            const toast = new bootstrap.Toast(toastElement, { delay: 5000 });
            toast.show();
            toastElement.addEventListener('hidden.bs.toast', () => {
                toastElement.remove();
            });
         }
    } else {
         alert(`${type.toUpperCase()}: ${message}`); // Fallback
    }
}

// Nota: O código acima para showToast é um exemplo. Se `board_utils.js` já tiver `showToast`,
// esta duplicata não é necessária e pode ser removida.
// O ideal é que `showToast`