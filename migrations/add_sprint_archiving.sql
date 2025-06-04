-- Migration: Adicionar campos de arquivamento à tabela Sprint
-- Data: 2024-12-19
-- Descrição: Permite arquivar sprints passadas mantendo histórico acessível

-- Adicionar coluna is_archived
ALTER TABLE sprint ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT 0;

-- Adicionar coluna archived_at
ALTER TABLE sprint ADD COLUMN archived_at DATETIME NULL;

-- Adicionar coluna archived_by
ALTER TABLE sprint ADD COLUMN archived_by VARCHAR(150) NULL;

-- Criar índice para otimizar consultas por sprints ativas/arquivadas
CREATE INDEX idx_sprint_is_archived ON sprint(is_archived);

-- Comentários para documentação
ALTER TABLE sprint COMMENT = 'Tabela de sprints com suporte a arquivamento';

-- Inserir registro de migração (se houver tabela de migrações)
-- INSERT INTO migrations (name, executed_at) VALUES ('add_sprint_archiving', NOW());

COMMIT; 