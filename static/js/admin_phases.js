// =====================================================
// AdminSystem - Gestão de Fases de Projetos
// Arquivo JavaScript separado para evitar conflitos
// =====================================================

console.log("🚀 AdminSystem Phases JS carregando...");

// Dados globais
var phasesData = { waterfall: [], agile: [] };
var currentType = 'waterfall';

// ===== FUNÇÕES GLOBAIS =====

function switchProjectTypeView(type) {
    console.log("✅ switchProjectTypeView funcionando:", type);
    currentType = type;
    
    // Atualizar abas
    document.querySelectorAll('.tab-button').forEach(function(btn) {
        btn.classList.remove('active');
    });
    document.getElementById(type + 'Tab').classList.add('active');
    
    // Mostrar/esconder conteúdo
    document.querySelectorAll('.phases-content').forEach(function(content) {
        content.style.display = 'none';
    });
    document.getElementById(type + 'Phases').style.display = 'block';
    
    // Renderizar dados
    renderPhases(type);
}

function showNewPhaseModal() {
    console.log("✅ showNewPhaseModal funcionando");
    alert("✅ FUNCIONOU! Nova Fase para: " + currentType);
}

function loadStatistics() {
    console.log("✅ loadStatistics funcionando");
    
    fetch('/adminsystem/api/project-phases/statistics')
        .then(function(response) {
            return response.json();
        })
        .then(function(data) {
            var msg = "📊 ESTATÍSTICAS:\n\n";
            msg += "• Projetos Waterfall: " + (data.waterfall_projects || 0) + "\n";
            msg += "• Projetos Ágil: " + (data.agile_projects || 0) + "\n";
            msg += "• Fases Waterfall: " + (data.waterfall_phases || 0) + "\n";
            msg += "• Fases Ágil: " + (data.agile_phases || 0);
            alert(msg);
        })
        .catch(function(error) {
            alert("❌ Erro ao carregar estatísticas: " + error);
        });
}

function savePhase() {
    console.log("✅ savePhase funcionando");
    alert("✅ FUNCIONOU! Salvar Fase");
}

function resetDefaults(type) {
    console.log("✅ resetDefaults funcionando:", type);
    
    if (confirm("Restaurar configurações padrão para " + type + "?")) {
        fetch('/adminsystem/api/project-phases/reset-defaults', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({project_type: type})
        })
        .then(function(response) {
            return response.json();
        })
        .then(function(data) {
            alert("✅ Configurações padrão restauradas!");
            loadPhases();
        })
        .catch(function(error) {
            alert("❌ Erro: " + error);
        });
    }
}

function editPhase(id) {
    console.log("✅ editPhase funcionando:", id);
    alert("✅ FUNCIONOU! Editando fase ID: " + id);
}

function deletePhase(id) {
    console.log("✅ deletePhase funcionando:", id);
    
    if (confirm("Excluir fase ID " + id + "?")) {
        fetch('/adminsystem/api/project-phases/configurations/' + id, {
            method: 'DELETE'
        })
        .then(function(response) {
            return response.json();
        })
        .then(function(data) {
            alert("✅ Fase excluída!");
            loadPhases();
        })
        .catch(function(error) {
            alert("❌ Erro: " + error);
        });
    }
}

function showPhaseModal(type, id) {
    console.log("✅ showPhaseModal funcionando:", type, id);
    var msg = "✅ FUNCIONOU! Modal para: " + type;
    if (id) msg += " (editando ID: " + id + ")";
    else msg += " (nova fase)";
    alert(msg);
}

// ===== FUNÇÕES INTERNAS =====

function renderPhases(type) {
    console.log("Renderizando fases para:", type);
    var container = document.getElementById(type + 'PhasesGrid');
    var phases = phasesData[type] || [];
    
    if (phases.length === 0) {
        container.innerHTML = '<div class="col-12 text-center p-5">' +
            '<h5>Nenhuma fase encontrada para ' + type + '</h5>' +
            '<button class="btn btn-primary" onclick="showPhaseModal(\'' + type + '\')">Criar Primeira Fase</button>' +
            '</div>';
        return;
    }
    
    var html = '';
    for (var i = 0; i < phases.length; i++) {
        var phase = phases[i];
        html += '<div class="col-md-4 mb-3">';
        html += '<div class="card" style="border-left: 4px solid ' + (phase.phase_color || '#007bff') + ';">';
        html += '<div class="card-header d-flex justify-content-between align-items-center">';
        html += '<strong>' + phase.phase_number + '. ' + phase.phase_name + '</strong>';
        html += '<div>';
        html += '<button class="btn btn-sm btn-outline-primary me-1" onclick="editPhase(' + phase.id + ')" title="Editar">📝</button>';
        html += '<button class="btn btn-sm btn-outline-danger" onclick="deletePhase(' + phase.id + ')" title="Excluir">🗑️</button>';
        html += '</div>';
        html += '</div>';
        html += '<div class="card-body">';
        html += '<p class="small text-muted">' + (phase.phase_description || 'Sem descrição') + '</p>';
        
        if (phase.milestone_names && phase.milestone_names.length > 0) {
            html += '<div class="mb-2"><small class="text-muted fw-bold">Marcos:</small><br>';
            for (var j = 0; j < phase.milestone_names.length; j++) {
                html += '<span class="badge bg-light text-dark me-1 mb-1">' + phase.milestone_names[j] + '</span>';
            }
            html += '</div>';
        }
        
        html += '<div class="d-flex justify-content-between align-items-center">';
        html += '<small class="text-muted">🎨 ' + (phase.phase_color || '#007bff') + '</small>';
        html += '<span class="badge ' + (phase.is_active !== false ? 'bg-success' : 'bg-secondary') + '">';
        html += (phase.is_active !== false ? 'Ativa' : 'Inativa');
        html += '</span>';
        html += '</div>';
        html += '</div>';
        html += '</div>';
        html += '</div>';
    }
    
    container.innerHTML = html;
}

function loadPhases() {
    console.log("🔄 Carregando fases...");
    
    // Mostrar loading
    document.getElementById('waterfallPhasesGrid').innerHTML = '<div class="col-12 text-center p-3"><div class="spinner-border text-primary"></div><p class="mt-2">Carregando fases Waterfall...</p></div>';
    document.getElementById('agilePhasesGrid').innerHTML = '<div class="col-12 text-center p-3"><div class="spinner-border text-primary"></div><p class="mt-2">Carregando fases Ágil...</p></div>';
    
    Promise.all([
        fetch('/adminsystem/api/project-phases/configurations?project_type=waterfall'),
        fetch('/adminsystem/api/project-phases/configurations?project_type=agile')
    ])
    .then(function(responses) {
        return Promise.all(responses.map(function(r) { return r.json(); }));
    })
    .then(function(data) {
        phasesData.waterfall = data[0] || [];
        phasesData.agile = data[1] || [];
        
        console.log("✅ Fases carregadas:", phasesData);
        
        renderPhases('waterfall');
        renderPhases('agile');
    })
    .catch(function(error) {
        console.error("❌ Erro ao carregar fases:", error);
        document.getElementById('waterfallPhasesGrid').innerHTML = '<div class="col-12 text-center text-danger p-3">❌ Erro ao carregar fases Waterfall</div>';
        document.getElementById('agilePhasesGrid').innerHTML = '<div class="col-12 text-center text-danger p-3">❌ Erro ao carregar fases Ágil</div>';
    });
}

// ===== INICIALIZAÇÃO =====

document.addEventListener('DOMContentLoaded', function() {
    console.log("🚀 AdminSystem Phases iniciando...");
    
    // Carregar dados
    loadPhases();
    
    // Definir estado inicial
    setTimeout(function() {
        switchProjectTypeView('waterfall');
    }, 500);
    
    console.log("✅ AdminSystem Phases pronto!");
});

console.log("📁 AdminSystem Phases JS carregado!"); 