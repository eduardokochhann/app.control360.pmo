// Funções utilitárias para o board
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

// Função para mostrar toast (implementação básica)
function showToast(message, type = 'info') {
    console.log(`[Toast-${type}]: ${message}`);
    
    // Verifica se existe um container de toast
    let toastContainer = document.getElementById('toastPlacement');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toastPlacement';
        toastContainer.style.position = 'fixed';
        toastContainer.style.top = '20px';
        toastContainer.style.right = '20px';
        toastContainer.style.zIndex = '1090';
        document.body.appendChild(toastContainer);
    }

    const toastId = 'toast-' + Date.now();
    const bgClass = type === 'error' ? 'danger' : (type === 'warning' ? 'warning' : (type === 'success' ? 'success' : 'info'));
    
    const toastHTML = `
        <div id="${toastId}" class="toast align-items-center text-white bg-${bgClass} border-0" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHTML);
    const toastElement = document.getElementById(toastId);
    
    if (toastElement && typeof bootstrap !== 'undefined') {
        const toast = new bootstrap.Toast(toastElement, { delay: 5000 });
        toast.show();
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    } else {
        // Fallback se Bootstrap não estiver disponível
        alert(`${type.toUpperCase()}: ${message}`);
        if (toastElement) toastElement.remove();
    }
}

console.log('board.js carregado - funções utilitárias disponíveis');