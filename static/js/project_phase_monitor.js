/**
 * Monitor de Fases de Projetos
 * Monitora mudanças de fase em tempo real e exibe notificações ao usuário
 */

class ProjectPhaseMonitor {
    constructor() {
        this.checkInterval = 30000; // 30 segundos
        this.lastPhaseCheck = new Date().getTime();
        this.currentProjectId = null;
        this.currentPhase = null;
        this.isMonitoring = false;
        
        this.init();
    }

    init() {
        // Detecta automaticamente o projeto atual na página
        this.detectCurrentProject();
        
        // Inicia monitoramento se estiver em uma página de projeto
        if (this.currentProjectId) {
            this.startMonitoring();
        }

        // Escuta eventos personalizados para controle manual
        document.addEventListener('phaseMonitor:start', (e) => {
            this.startMonitoring(e.detail.projectId);
        });

        document.addEventListener('phaseMonitor:stop', () => {
            this.stopMonitoring();
        });

        console.log('[PhaseMonitor] Inicializado');
    }

    detectCurrentProject() {
        // Tenta detectar o projeto atual baseado na URL ou elementos da página
        const urlParts = window.location.pathname.split('/');
        
        // Para páginas como /backlog/board/123456
        if (urlParts.includes('board') && urlParts.length > 3) {
            this.currentProjectId = urlParts[urlParts.length - 1];
            console.log('[PhaseMonitor] Projeto detectado via URL:', this.currentProjectId);
            return;
        }

        // Para outras páginas, tenta detectar via atributos data
        const projectElement = document.querySelector('[data-project-id]');
        if (projectElement) {
            this.currentProjectId = projectElement.dataset.projectId;
            console.log('[PhaseMonitor] Projeto detectado via data-project-id:', this.currentProjectId);
            return;
        }

        // Busca em meta tags ou outras fontes
        const metaProject = document.querySelector('meta[name="project-id"]');
        if (metaProject) {
            this.currentProjectId = metaProject.content;
            console.log('[PhaseMonitor] Projeto detectado via meta tag:', this.currentProjectId);
            return;
        }

        console.log('[PhaseMonitor] Projeto não detectado automaticamente');
    }

    startMonitoring(projectId = null) {
        if (projectId) {
            this.currentProjectId = projectId;
        }

        if (!this.currentProjectId) {
            console.warn('[PhaseMonitor] Não é possível iniciar monitoramento sem ID do projeto');
            return;
        }

        if (this.isMonitoring) {
            console.log('[PhaseMonitor] Monitoramento já está ativo');
            return;
        }

        console.log('[PhaseMonitor] Iniciando monitoramento para projeto:', this.currentProjectId);
        this.isMonitoring = true;

        // Carrega fase inicial
        this.loadCurrentPhase().then(() => {
            // Inicia verificação periódica
            this.intervalId = setInterval(() => {
                this.checkPhaseChanges();
            }, this.checkInterval);
        });
    }

    stopMonitoring() {
        if (!this.isMonitoring) {
            return;
        }

        console.log('[PhaseMonitor] Parando monitoramento');
        this.isMonitoring = false;

        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
    }

    async loadCurrentPhase() {
        try {
            const response = await fetch(`/backlog/api/projects/${this.currentProjectId}/current-phase`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const phaseData = await response.json();
            
            if (phaseData.current_phase) {
                this.currentPhase = {
                    number: phaseData.current_phase.number,
                    name: phaseData.current_phase.name,
                    color: phaseData.current_phase.color
                };
                console.log('[PhaseMonitor] Fase atual carregada:', this.currentPhase);
            }

        } catch (error) {
            console.warn('[PhaseMonitor] Erro ao carregar fase atual:', error);
        }
    }

    async checkPhaseChanges() {
        if (!this.isMonitoring || !this.currentProjectId) {
            return;
        }

        try {
            const response = await fetch(`/backlog/api/projects/${this.currentProjectId}/current-phase`);
            
            if (!response.ok) {
                return;
            }

            const phaseData = await response.json();
            
            if (phaseData.current_phase && this.currentPhase) {
                const newPhase = phaseData.current_phase;
                
                // Verifica se houve mudança de fase
                if (newPhase.number !== this.currentPhase.number) {
                    console.log('[PhaseMonitor] Mudança de fase detectada:', {
                        anterior: this.currentPhase,
                        nova: newPhase
                    });

                    this.handlePhaseChange(this.currentPhase, newPhase);
                    
                    // Atualiza fase atual
                    this.currentPhase = {
                        number: newPhase.number,
                        name: newPhase.name,
                        color: newPhase.color
                    };
                }
            }

        } catch (error) {
            console.warn('[PhaseMonitor] Erro ao verificar mudanças de fase:', error);
        }
    }

    handlePhaseChange(oldPhase, newPhase) {
        // Notifica mudança de fase ao usuário
        this.showPhaseChangeNotification(oldPhase, newPhase);

        // Atualiza elementos da interface se existirem
        this.updatePhaseUI(newPhase);

        // Dispara evento customizado para outros componentes
        document.dispatchEvent(new CustomEvent('phaseChanged', {
            detail: {
                projectId: this.currentProjectId,
                oldPhase: oldPhase,
                newPhase: newPhase
            }
        }));

        // Log para auditoria
        console.log(`[PhaseMonitor] Projeto ${this.currentProjectId} avançou da fase "${oldPhase.name}" para "${newPhase.name}"`);
    }

    showPhaseChangeNotification(oldPhase, newPhase) {
        // Usando Toast do Bootstrap se disponível
        if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
            this.showBootstrapToast(oldPhase, newPhase);
        } else {
            // Fallback para alert nativo
            alert(`🎉 Projeto avançou para a próxima fase!\n\nDe: ${oldPhase.name}\nPara: ${newPhase.name}`);
        }
    }

    showBootstrapToast(oldPhase, newPhase) {
        // Cria toast dinamicamente
        const toastHtml = `
            <div class="toast" role="alert" aria-live="assertive" aria-atomic="true" data-bs-delay="8000">
                <div class="toast-header" style="background: linear-gradient(135deg, #FF2D5F 0%, #07304F 100%); color: white;">
                    <i class="bi bi-diagram-3 me-2"></i>
                    <strong class="me-auto">Transição de Fase</strong>
                    <small class="text-light opacity-75">Agora</small>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">
                    <div class="d-flex align-items-center">
                        <div class="me-3">
                            <i class="bi bi-check-circle-fill text-success fs-4"></i>
                        </div>
                        <div>
                            <strong>Projeto avançou automaticamente!</strong><br>
                            <small class="text-muted">
                                De: <span class="badge" style="background-color: ${oldPhase.color}">${oldPhase.name}</span><br>
                                Para: <span class="badge" style="background-color: ${newPhase.color}">${newPhase.name}</span>
                            </small>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Adiciona à página
        let toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            document.body.appendChild(toastContainer);
        }

        toastContainer.insertAdjacentHTML('beforeend', toastHtml);
        
        // Ativa o toast
        const toastElement = toastContainer.lastElementChild;
        const toast = new bootstrap.Toast(toastElement);
        toast.show();

        // Remove o elemento após ser ocultado
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }

    updatePhaseUI(newPhase) {
        // Atualiza elementos da UI que mostram informações de fase
        const phaseElements = document.querySelectorAll('.current-phase-info, .project-phase-display');
        
        phaseElements.forEach(element => {
            if (element.dataset.projectId === this.currentProjectId) {
                // Atualiza conteúdo do elemento
                element.innerHTML = `
                    <span class="badge text-white" style="background-color: ${newPhase.color}">
                        <i class="bi bi-arrow-right-circle"></i> ${newPhase.number}. ${newPhase.name}
                    </span>
                `;
            }
        });

        // Atualiza título da página se aplicável
        const titleElement = document.querySelector('.page-title, h1, h2');
        if (titleElement && titleElement.textContent.includes('Fase')) {
            // Adiciona informação de fase ao título se ainda não estiver presente
            const phaseInfo = ` - Fase ${newPhase.number}: ${newPhase.name}`;
            if (!titleElement.textContent.includes(phaseInfo)) {
                titleElement.textContent += phaseInfo;
            }
        }
    }

    // Métodos públicos para controle manual
    static start(projectId) {
        document.dispatchEvent(new CustomEvent('phaseMonitor:start', {
            detail: { projectId: projectId }
        }));
    }

    static stop() {
        document.dispatchEvent(new CustomEvent('phaseMonitor:stop'));
    }

    static checkNow() {
        if (window.phaseMonitor && window.phaseMonitor.isMonitoring) {
            window.phaseMonitor.checkPhaseChanges();
        }
    }
}

// Inicializa automaticamente quando o DOM está pronto
document.addEventListener('DOMContentLoaded', function() {
    // Verifica se estamos em uma página relevante (que tem projetos)
    const projectPages = [
        '/backlog/',
        '/macro/',
        '/sprints/'
    ];

    const currentPath = window.location.pathname;
    const isProjectPage = projectPages.some(page => currentPath.includes(page));

    if (isProjectPage) {
        // Cria instância global para acesso via console/outros scripts
        window.phaseMonitor = new ProjectPhaseMonitor();
        
        console.log('[PhaseMonitor] Disponível globalmente via window.phaseMonitor');
        console.log('[PhaseMonitor] Métodos: ProjectPhaseMonitor.start(projectId), ProjectPhaseMonitor.stop(), ProjectPhaseMonitor.checkNow()');
    }
});

// Export para uso como módulo se necessário
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ProjectPhaseMonitor;
} 