// Sistema de Notas
const NotesManager = {
    projectId: null,
    noteModal: null,
    reportPreviewModal: null,
    
    init: function(projectId) {
        this.projectId = projectId;
        this.noteModal = new bootstrap.Modal(document.getElementById('noteModal'));
        this.reportPreviewModal = new bootstrap.Modal(document.getElementById('reportPreviewModal'));
        
        this.setupEventListeners();
        this.loadNotes();
    },
    
    setupEventListeners: function() {
        // Botões principais
        document.getElementById('addProjectNoteBtn').addEventListener('click', () => this.showNoteModal('project'));
        document.getElementById('addTaskNoteBtn').addEventListener('click', () => this.showNoteModal('task'));
        document.getElementById('previewReportBtn').addEventListener('click', () => this.showReportPreview());
        document.getElementById('generateReportBtn').addEventListener('click', () => this.generateReport());
        document.getElementById('saveNoteBtn').addEventListener('click', () => this.saveNote());
        document.getElementById('deleteNoteBtn').addEventListener('click', () => this.deleteNote());
        
        // Filtros
        document.getElementById('noteTypeFilter').addEventListener('change', () => this.applyFilters());
        document.getElementById('noteCategoryFilter').addEventListener('change', () => this.applyFilters());
        document.getElementById('notePriorityFilter').addEventListener('change', () => this.applyFilters());
        document.getElementById('noteSearchBtn').addEventListener('click', () => this.applyFilters());
        document.getElementById('noteSearchInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.applyFilters();
        });
    },
    
    loadNotes: function() {
        const url = `/api/notes?project_id=${this.projectId}`;
        fetch(url)
            .then(response => response.json())
            .then(notes => {
                this.renderNotes(notes);
            })
            .catch(error => {
                console.error('Erro ao carregar notas:', error);
                showToast('error', 'Erro ao carregar notas');
            });
    },
    
    renderNotes: function(notes) {
        const projectNotes = notes.filter(note => note.note_type === 'project');
        const taskNotes = notes.filter(note => note.note_type === 'task');
        
        document.getElementById('projectNotesList').innerHTML = this.generateNotesList(projectNotes);
        document.getElementById('taskNotesList').innerHTML = this.generateNotesList(taskNotes);
        
        // Adiciona listeners para edição
        document.querySelectorAll('.edit-note-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const noteId = e.target.closest('.note-card').dataset.noteId;
                this.editNote(noteId);
            });
        });
    },
    
    generateNotesList: function(notes) {
        if (notes.length === 0) {
            return '<div class="text-center text-muted py-3">Nenhuma nota encontrada</div>';
        }
        
        return notes.map(note => `
            <div class="note-card priority-${note.priority}" data-note-id="${note.id}">
                <div class="note-header">
                    <div class="note-title">
                        ${note.task_title ? `<strong>Tarefa:</strong> ${note.task_title}` : ''}
                        <span class="badge bg-${this.getCategoryBadgeColor(note.category)} ms-2">
                            ${this.getCategoryLabel(note.category)}
                        </span>
                    </div>
                    <div class="note-meta">
                        ${new Date(note.created_at).toLocaleString()}
                    </div>
                </div>
                <div class="note-content">${note.content}</div>
                <div class="note-footer">
                    <div class="note-tags">
                        ${note.tags.map(tag => `
                            <span class="note-tag">${tag}</span>
                        `).join('')}
                    </div>
                    <div class="note-actions">
                        <button class="btn btn-sm btn-outline-primary edit-note-btn">
                            <i class="bi bi-pencil"></i>
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
    },
    
    showNoteModal: function(type, noteId = null) {
        const modal = document.getElementById('noteModal');
        const form = document.getElementById('noteForm');
        const taskSelect = document.getElementById('taskSelectGroup');
        
        // Reset form
        form.reset();
        document.getElementById('noteId').value = '';
        document.getElementById('noteType').value = type;
        
        // Configura o modal baseado no tipo
        modal.querySelector('.modal-title').textContent = noteId ? 'Editar Nota' : 'Nova Nota';
        taskSelect.style.display = type === 'task' ? 'block' : 'none';
        
        if (type === 'task') {
            this.loadTasksForSelect();
        }
        
        // Configura botão de exclusão
        document.getElementById('deleteNoteBtn').style.display = noteId ? 'block' : 'none';
        
        this.noteModal.show();
    },
    
    loadTasksForSelect: function() {
        const select = document.getElementById('noteTaskId');
        select.innerHTML = '<option value="">Carregando...</option>';
        
        fetch(`/api/backlogs/${this.projectId}/tasks`)
            .then(response => response.json())
            .then(tasks => {
                select.innerHTML = tasks.map(task =>
                    `<option value="${task.id}">${task.title}</option>`
                ).join('');
            })
            .catch(error => {
                console.error('Erro ao carregar tarefas:', error);
                select.innerHTML = '<option value="">Erro ao carregar tarefas</option>';
            });
    },
    
    saveNote: function() {
        const form = document.getElementById('noteForm');
        const noteId = document.getElementById('noteId').value;
        
        const data = {
            content: document.getElementById('noteContent').value,
            note_type: document.getElementById('noteType').value,
            category: document.getElementById('noteCategory').value,
            priority: document.getElementById('notePriority').value,
            project_id: this.projectId,
            tags: document.getElementById('noteTags').value.split(',').map(tag => tag.trim()).filter(tag => tag),
            report_status: document.getElementById('noteReadyForReport').checked ? 'READY_FOR_REPORT' : 'DRAFT'
        };
        
        if (data.note_type === 'task') {
            data.task_id = document.getElementById('noteTaskId').value;
            if (!data.task_id) {
                showToast('error', 'Selecione uma tarefa');
                return;
            }
        }
        
        const url = `/api/notes${noteId ? `/${noteId}` : ''}`;
        const method = noteId ? 'PUT' : 'POST';
        
        fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(result => {
            if (result.error) throw new Error(result.error);
            this.noteModal.hide();
            this.loadNotes();
            showToast('success', 'Nota salva com sucesso');
        })
        .catch(error => {
            console.error('Erro ao salvar nota:', error);
            showToast('error', 'Erro ao salvar nota');
        });
    },
    
    editNote: function(noteId) {
        fetch(`/api/notes/${noteId}`)
            .then(response => response.json())
            .then(note => {
                document.getElementById('noteId').value = note.id;
                document.getElementById('noteType').value = note.note_type;
                document.getElementById('noteContent').value = note.content;
                document.getElementById('noteCategory').value = note.category;
                document.getElementById('notePriority').value = note.priority;
                document.getElementById('noteTags').value = note.tags.join(', ');
                document.getElementById('noteReadyForReport').checked = note.report_status === 'READY_FOR_REPORT';
                
                if (note.note_type === 'task') {
                    document.getElementById('taskSelectGroup').style.display = 'block';
                    this.loadTasksForSelect().then(() => {
                        document.getElementById('noteTaskId').value = note.task_id;
                    });
                }
                
                this.showNoteModal(note.note_type, note.id);
            })
            .catch(error => {
                console.error('Erro ao carregar nota:', error);
                showToast('error', 'Erro ao carregar nota');
            });
    },
    
    deleteNote: function() {
        const noteId = document.getElementById('noteId').value;
        if (!noteId) return;
        
        if (!confirm('Tem certeza que deseja excluir esta nota?')) return;
        
        fetch(`/api/notes/${noteId}`, {
            method: 'DELETE'
        })
        .then(response => {
            if (!response.ok) throw new Error('Erro ao excluir nota');
            this.noteModal.hide();
            this.loadNotes();
            showToast('success', 'Nota excluída com sucesso');
        })
        .catch(error => {
            console.error('Erro ao excluir nota:', error);
            showToast('error', 'Erro ao excluir nota');
        });
    },
    
    showReportPreview: function() {
        fetch(`/api/notes/report/preview?project_id=${this.projectId}`)
            .then(response => response.json())
            .then(data => {
                // Preenche cada seção do relatório
                Object.keys(data).forEach(section => {
                    const container = document.getElementById(`report${section.charAt(0).toUpperCase() + section.slice(1)}`);
                    container.innerHTML = data[section].length > 0
                        ? this.generateReportItems(data[section])
                        : '<div class="text-muted">Nenhum item nesta seção</div>';
                });
                
                this.reportPreviewModal.show();
            })
            .catch(error => {
                console.error('Erro ao carregar preview do relatório:', error);
                showToast('error', 'Erro ao carregar preview do relatório');
            });
    },
    
    generateReportItems: function(items) {
        return items.map(item => `
            <div class="report-item">
                <div class="report-item-header">
                    <span>
                        ${item.task_title ? `<strong>Tarefa:</strong> ${item.task_title} - ` : ''}
                        ${new Date(item.created_at).toLocaleString()}
                    </span>
                    <span class="badge bg-${this.getPriorityBadgeColor(item.priority)}">
                        ${this.getPriorityLabel(item.priority)}
                    </span>
                </div>
                <div class="report-item-content">${item.content}</div>
            </div>
        `).join('');
    },
    
    generateReport: function() {
        fetch(`/api/notes/report/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                project_id: this.projectId
            })
        })
        .then(response => response.json())
        .then(result => {
            if (result.error) throw new Error(result.error);
            this.reportPreviewModal.hide();
            this.loadNotes();
            showToast('success', 'Relatório gerado com sucesso');
        })
        .catch(error => {
            console.error('Erro ao gerar relatório:', error);
            showToast('error', 'Erro ao gerar relatório');
        });
    },
    
    applyFilters: function() {
        const type = document.getElementById('noteTypeFilter').value;
        const category = document.getElementById('noteCategoryFilter').value;
        const priority = document.getElementById('notePriorityFilter').value;
        const search = document.getElementById('noteSearchInput').value;
        
        let url = `/api/notes?project_id=${this.projectId}`;
        if (type) url += `&type=${type}`;
        if (category) url += `&category=${category}`;
        if (priority) url += `&priority=${priority}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        
        fetch(url)
            .then(response => response.json())
            .then(notes => {
                this.renderNotes(notes);
            })
            .catch(error => {
                console.error('Erro ao filtrar notas:', error);
                showToast('error', 'Erro ao filtrar notas');
            });
    },
    
    getCategoryBadgeColor: function(category) {
        const colors = {
            'decision': 'primary',
            'risk': 'danger',
            'impediment': 'warning',
            'status_update': 'info',
            'general': 'secondary'
        };
        return colors[category] || 'secondary';
    },
    
    getPriorityBadgeColor: function(priority) {
        const colors = {
            'high': 'danger',
            'medium': 'warning',
            'low': 'info'
        };
        return colors[priority] || 'secondary';
    },
    
    getCategoryLabel: function(category) {
        const labels = {
            'decision': 'Decisão',
            'risk': 'Risco',
            'impediment': 'Impedimento',
            'status_update': 'Atualização',
            'general': 'Geral'
        };
        return labels[category] || category;
    },
    
    getPriorityLabel: function(priority) {
        const labels = {
            'high': 'Alta',
            'medium': 'Média',
            'low': 'Baixa'
        };
        return labels[priority] || priority;
    }
}; 