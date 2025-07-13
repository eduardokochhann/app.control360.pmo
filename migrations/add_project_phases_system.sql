-- Migration: Adicionar Sistema de Gestão de Fases de Projetos
-- Data: 2025-01-11
-- Descrição: Adiciona campos para gestão de fases de projetos (Waterfall/Ágil) ao modelo Backlog,
--           estende ProjectMilestone com gatilhos de fase e cria tabela de configuração de fases

-- 1. Adicionar novos campos ao Backlog para gestão de fases
ALTER TABLE backlog ADD COLUMN project_type VARCHAR(20) DEFAULT NULL;
ALTER TABLE backlog ADD COLUMN current_phase INTEGER NOT NULL DEFAULT 1;
ALTER TABLE backlog ADD COLUMN phases_config TEXT DEFAULT NULL;
ALTER TABLE backlog ADD COLUMN phase_started_at DATETIME DEFAULT NULL;

-- 2. Adicionar novos campos ao ProjectMilestone para gatilhos de fase
ALTER TABLE project_milestone ADD COLUMN triggers_next_phase BOOLEAN NOT NULL DEFAULT 0;
ALTER TABLE project_milestone ADD COLUMN phase_order INTEGER DEFAULT NULL;
ALTER TABLE project_milestone ADD COLUMN auto_created BOOLEAN NOT NULL DEFAULT 0;

-- 3. Criar tabela de configuração de fases de projetos
CREATE TABLE IF NOT EXISTS project_phase_configuration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_type VARCHAR(20) NOT NULL,
    phase_number INTEGER NOT NULL,
    phase_name VARCHAR(100) NOT NULL,
    phase_description TEXT,
    phase_color VARCHAR(20) DEFAULT '#E8F5E8',
    milestone_names TEXT,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_project_type_phase UNIQUE (project_type, phase_number)
);

-- 4. Criar índices para performance
CREATE INDEX IF NOT EXISTS idx_backlog_project_type ON backlog(project_type);
CREATE INDEX IF NOT EXISTS idx_backlog_current_phase ON backlog(current_phase);
CREATE INDEX IF NOT EXISTS idx_milestone_triggers_phase ON project_milestone(triggers_next_phase);
CREATE INDEX IF NOT EXISTS idx_milestone_phase_order ON project_milestone(phase_order);
CREATE INDEX IF NOT EXISTS idx_phase_config_type ON project_phase_configuration(project_type);
CREATE INDEX IF NOT EXISTS idx_phase_config_active ON project_phase_configuration(is_active);

-- 5. Inserir configurações padrão de fases Waterfall
INSERT OR IGNORE INTO project_phase_configuration (
    project_type, phase_number, phase_name, phase_description, phase_color, milestone_names
) VALUES
('waterfall', 1, 'Planejamento', 'Fase de planejamento e definição de requisitos', '#E8F5E8', '["Milestone Start"]'),
('waterfall', 2, 'Execução', 'Fase de execução e desenvolvimento do projeto', '#E8F0FF', '["Milestone Setup"]'),
('waterfall', 3, 'CutOver', 'Fase de testes e validações finais', '#FFF8E1', '["Milestone CutOver"]'),
('waterfall', 4, 'GoLive', 'Fase de entrega e encerramento do projeto', '#E8FFE8', '["Milestone Finish Project"]');

-- 6. Inserir configurações padrão de fases Ágil
INSERT OR IGNORE INTO project_phase_configuration (
    project_type, phase_number, phase_name, phase_description, phase_color, milestone_names
) VALUES
('agile', 1, 'Planejamento', 'Fase de planejamento inicial e definição do backlog', '#E8F5E8', '["Milestone Start"]'),
('agile', 2, 'Sprint Planning', 'Fase de planejamento de sprints e organização de equipe', '#F0F8FF', '["Milestone Setup"]'),
('agile', 3, 'Desenvolvimento', 'Fase de desenvolvimento iterativo e sprints', '#E8F0FF', '["Milestone Developer"]'),
('agile', 4, 'CutOver', 'Fase de testes contínuos e ajustes finais', '#FFF8E1', '["Milestone CutOver"]'),
('agile', 5, 'GoLive', 'Fase de entrega e acompanhamento pós-deploy', '#E8FFE8', '["Milestone Finish Project"]');

-- 7. Comentários para documentação
COMMENT ON COLUMN backlog.project_type IS 'Tipo do projeto: waterfall ou agile';
COMMENT ON COLUMN backlog.current_phase IS 'Número da fase atual do projeto (1, 2, 3, ...)';
COMMENT ON COLUMN backlog.phases_config IS 'Configuração personalizada das fases em formato JSON';
COMMENT ON COLUMN backlog.phase_started_at IS 'Data e hora de início da fase atual';

COMMENT ON COLUMN project_milestone.triggers_next_phase IS 'Se este marco dispara automaticamente a próxima fase quando concluído';
COMMENT ON COLUMN project_milestone.phase_order IS 'Ordem do marco na sequência de fases do projeto';
COMMENT ON COLUMN project_milestone.auto_created IS 'Se o marco foi criado automaticamente pelo sistema';

COMMENT ON TABLE project_phase_configuration IS 'Configurações das fases para projetos Waterfall e Ágil';
COMMENT ON COLUMN project_phase_configuration.milestone_names IS 'Nomes dos marcos desta fase em formato JSON array';

-- 8. Trigger para atualizar updated_at na tabela project_phase_configuration
CREATE TRIGGER IF NOT EXISTS update_phase_config_timestamp 
    AFTER UPDATE ON project_phase_configuration
    FOR EACH ROW
BEGIN
    UPDATE project_phase_configuration 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE id = NEW.id;
END; 