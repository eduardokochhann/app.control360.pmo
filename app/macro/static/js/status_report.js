/**
 * Status Report - Scripts para manipulação de elementos dinâmicos
 */
document.addEventListener("DOMContentLoaded", function() {

    // Função para preencher o card de Marcos Recentes
    function preencherCardMarcos() {
        // Pega os dados de marcos do console, onde sabemos que existem
        const marcosCardElement = document.querySelector('[data-card="marcos-recentes"]');
        if (!marcosCardElement) {
            console.log("Card de Marcos Recentes não encontrado.");
            
            // Fallback: tenta preencher o campo diretamente no HTML
            const marcosPlaceholder = document.getElementById('marcos-recentes-placeholder');
            if (marcosPlaceholder) {
                console.log("Localizando dados dos marcos na página...");
                // Pega todos os marcos da tabela principal
                const marcosTabelaPrincipal = document.querySelectorAll('.table-marcos-recentes tr');
                
                if (marcosTabelaPrincipal && marcosTabelaPrincipal.length > 0) {
                    // Cria HTML para os marcos
                    let html = '<div class="table-responsive"><table class="table table-sm"><tbody>';
                    marcosTabelaPrincipal.forEach(row => {
                        html += row.outerHTML;
                    });
                    html += '</tbody></table></div>';
                    
                    // Substitui o placeholder
                    marcosPlaceholder.innerHTML = html;
                    console.log("Marcos injetados com sucesso no card inferior.");
                } else {
                    // Alternativa: tenta extrair os dados das propriedades window
                    if (window.reportData && window.reportData.marcos_recentes) {
                        const marcos = window.reportData.marcos_recentes;
                        let html = '<div class="table-responsive"><table class="table table-sm"><tbody>';
                        
                        marcos.forEach(marco => {
                            const statusClass = 
                                marco.status === 'COMPLETED' || marco.status === 'CONCLUÍDO' ? 'bg-success' :
                                marco.status === 'IN_PROGRESS' || marco.status === 'EM ANDAMENTO' ? 'bg-warning text-dark' :
                                marco.status === 'DELAYED' || marco.status === 'ATRASADO' ? 'bg-danger' : 'bg-secondary';
                            
                            const statusText = 
                                marco.status === 'COMPLETED' || marco.status === 'CONCLUÍDO' ? 'Concluído' :
                                marco.status === 'IN_PROGRESS' || marco.status === 'EM ANDAMENTO' ? 'Em Andamento' :
                                marco.status === 'DELAYED' || marco.status === 'ATRASADO' ? 'Atrasado' : 'Pendente';
                            
                            html += `
                                <tr>
                                    <td class="text-start">
                                        ${marco.atrasado ? '<span class="badge bg-danger me-1">!</span>' : ''}
                                        <strong>${marco.nome}</strong>
                                    </td>
                                    <td>${marco.data_planejada}</td>
                                    <td>
                                        <span class="badge ${statusClass}">${statusText}</span>
                                    </td>
                                </tr>
                            `;
                        });
                        
                        html += '</tbody></table></div>';
                        marcosPlaceholder.innerHTML = html;
                        console.log("Marcos injetados de window.reportData no card inferior.");
                    }
                }
            }
        }
    }
    
    // Preenche os marcos após um pequeno delay para garantir que a página foi carregada
    setTimeout(preencherCardMarcos, 500);
}); 