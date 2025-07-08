-- Migration: Criar tabela module_configuration
-- Data: 2025-01-02
-- Descrição: Sistema de configuração de módulos e funcionalidades

-- Criar tabela module_configuration
CREATE TABLE IF NOT EXISTS module_configuration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_key VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(150) NOT NULL,
    description TEXT,
    module_type VARCHAR(20) NOT NULL DEFAULT 'module',
    is_enabled BOOLEAN NOT NULL DEFAULT 1,
    requires_authentication BOOLEAN NOT NULL DEFAULT 1,
    parent_module VARCHAR(100),
    dependencies TEXT,
    icon VARCHAR(100),
    color VARCHAR(20),
    display_order INTEGER NOT NULL DEFAULT 0,
    allowed_roles TEXT,
    maintenance_mode BOOLEAN NOT NULL DEFAULT 0,
    maintenance_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(150),
    updated_by VARCHAR(150)
);

-- Criar índice na chave do módulo
CREATE INDEX IF NOT EXISTS idx_module_configuration_module_key ON module_configuration(module_key);

-- Inserir configurações padrão dos módulos
INSERT INTO module_configuration (
    module_key, display_name, description, module_type, 
    icon, color, display_order, is_enabled
) VALUES
-- Módulos principais
('gerencial', 'Visão Gerencial', 'Dashboard executivo com KPIs e métricas estratégicas do PMO', 'module', 'fas fa-chart-line', '#FF2D5F', 1, 1),
('macro', 'Visão Macro', 'Gestão de projetos e relatórios macro organizacionais', 'module', 'fas fa-project-diagram', '#07304F', 2, 1),
('macro.status_report', 'Status Report', 'Relatório de status executivo para apresentações', 'feature', 'fas fa-file-chart', '#FF2D5F', 3, 1),
('backlog', 'Backlog de Projetos', 'Gestão de backlog e board de tarefas por projeto', 'module', 'fas fa-tasks', '#07304F', 4, 1),
('sprints', 'Sprints Semanais', 'Planejamento e gestão de sprints semanais', 'module', 'fas fa-calendar-week', '#FF2D5F', 5, 1),
('admin', 'Configurações', 'Central administrativa e configurações do sistema', 'module', 'fas fa-cog', '#6C757D', 6, 1),

-- Funcionalidades específicas (podem ser desabilitadas individualmente)
('macro.performance', 'Card Performance', 'Card de métricas de performance de entregas', 'feature', 'fas fa-tachometer-alt', '#FF2D5F', 0, 1),
('macro.relatorios', 'Relatórios Macro', 'Suite de relatórios gerenciais macro', 'feature', 'fas fa-chart-bar', '#07304F', 0, 1),
('backlog.capacity', 'Capacidade Especialistas', 'Análise de capacidade e alocação de especialistas', 'feature', 'fas fa-users', '#FF2D5F', 0, 1),
('backlog.notes', 'Sistema de Notas', 'Gestão de notas e observações de projetos/tarefas', 'feature', 'fas fa-sticky-note', '#07304F', 0, 1),
('sprints.archiving', 'Arquivamento de Sprints', 'Sistema de arquivamento automático de sprints', 'feature', 'fas fa-archive', '#6C757D', 0, 1),
('admin.complexity', 'Gestão de Complexidade', 'Sistema de avaliação de complexidade de projetos', 'feature', 'fas fa-brain', '#FF2D5F', 0, 1),
('admin.specialists', 'Configuração Especialistas', 'Configurações individuais de especialistas', 'feature', 'fas fa-user-cog', '#07304F', 0, 1);

-- Definir dependências (JSON)
UPDATE module_configuration SET dependencies = '["macro"]' WHERE module_key = 'macro.status_report';
UPDATE module_configuration SET dependencies = '["macro"]' WHERE module_key = 'macro.performance';
UPDATE module_configuration SET dependencies = '["macro"]' WHERE module_key = 'macro.relatorios';
UPDATE module_configuration SET dependencies = '["backlog"]' WHERE module_key = 'backlog.capacity';
UPDATE module_configuration SET dependencies = '["backlog"]' WHERE module_key = 'backlog.notes';
UPDATE module_configuration SET dependencies = '["sprints"]' WHERE module_key = 'sprints.archiving';
UPDATE module_configuration SET dependencies = '["admin"]' WHERE module_key = 'admin.complexity';
UPDATE module_configuration SET dependencies = '["admin"]' WHERE module_key = 'admin.specialists';

-- Definir parent_module para funcionalidades
UPDATE module_configuration SET parent_module = 'macro' WHERE module_key LIKE 'macro.%';
UPDATE module_configuration SET parent_module = 'backlog' WHERE module_key LIKE 'backlog.%';
UPDATE module_configuration SET parent_module = 'sprints' WHERE module_key LIKE 'sprints.%';
UPDATE module_configuration SET parent_module = 'admin' WHERE module_key LIKE 'admin.%';

-- Inserir configuração especial para micro (se necessário no futuro)
INSERT INTO module_configuration (
    module_key, display_name, description, module_type, 
    icon, color, display_order, is_enabled
) VALUES
('micro', 'Visão Micro', 'Análises detalhadas e micro gestão (Futuro)', 'module', 'fas fa-microscope', '#6C757D', 7, 0);

COMMIT; 