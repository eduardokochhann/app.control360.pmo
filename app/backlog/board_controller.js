// Arquivo para testes de API
document.addEventListener('DOMContentLoaded', function() {
    // Verificar as APIs disponíveis
    const projectId = document.getElementById('currentBacklogId')?.value;
    console.log("Project ID: ", projectId);
    
    // Botão de teste
    const testButton = document.createElement('button');
    testButton.innerText = 'Testar API Notas';
    testButton.className = 'btn btn-sm btn-primary';
    testButton.onclick = testNotesApi;
    
    // Adicionar à página
    document.body.appendChild(testButton);
    
    // Função de teste
    function testNotesApi() {
        console.log("Testando API de notas...");
        
        // Testar GET
        fetch('/backlog/api/notes?project_id=' + projectId)
            .then(response => {
                console.log("GET /backlog/api/notes Status: ", response.status);
                if (!response.ok) throw new Error("Erro " + response.status);
                return response.json();
            })
            .then(data => {
                console.log("GET /backlog/api/notes Result: ", data);
            })
            .catch(error => {
                console.error("GET /backlog/api/notes Error: ", error);
            });
        
        // Testar POST
        const noteData = {
            content: "Nota de teste " + new Date().toISOString(),
            category: "general",
            priority: "medium",
            project_id: projectId,
            note_type: "project",
            tags: ["teste", "debug"]
        };
        
        fetch('/backlog/api/notes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(noteData)
        })
            .then(response => {
                console.log("POST /backlog/api/notes Status: ", response.status);
                if (!response.ok) throw new Error("Erro " + response.status);
                return response.json();
            })
            .then(data => {
                console.log("POST /backlog/api/notes Result: ", data);
            })
            .catch(error => {
                console.error("POST /backlog/api/notes Error: ", error);
            });
    }
}); 