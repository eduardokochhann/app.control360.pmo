-- Migration: Adicionar campo started_at ao ProjectMilestone
-- Data: 2025-01-13
-- Descrição: Adiciona campo para registrar quando um marco foi iniciado (Em Andamento)

-- Adicionar campo started_at ao ProjectMilestone
ALTER TABLE project_milestone ADD COLUMN started_at DATETIME DEFAULT NULL;

-- Criar índice para performance
CREATE INDEX IF NOT EXISTS idx_milestone_started_at ON project_milestone(started_at);

-- Comentário para documentação
COMMENT ON COLUMN project_milestone.started_at IS 'Data e hora quando o marco foi colocado em andamento';

-- Atualizar marcos existentes que já estão "Em Andamento" mas não têm started_at
UPDATE project_milestone 
SET started_at = created_at 
WHERE status = 'IN_PROGRESS' 
AND started_at IS NULL;

-- Log da migração
INSERT INTO migration_log (migration_name, applied_at, description) 
VALUES ('add_milestone_started_at', CURRENT_TIMESTAMP, 'Adiciona campo started_at ao ProjectMilestone'); 