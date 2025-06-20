-- Migração para Sistema de Complexidade de Projetos
-- Data: 2024-12-19

-- 1. Criar tabela de critérios de complexidade
CREATE TABLE IF NOT EXISTS complexity_criteria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    'order' INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. Criar tabela de opções dos critérios
CREATE TABLE IF NOT EXISTS complexity_criteria_option (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    criteria_id INTEGER NOT NULL,
    label VARCHAR(100) NOT NULL,
    description TEXT,
    score INTEGER NOT NULL,
    'order' INTEGER DEFAULT 0,
    FOREIGN KEY (criteria_id) REFERENCES complexity_criteria (id) ON DELETE CASCADE
);

-- 3. Criar tabela de avaliações de complexidade
CREATE TABLE IF NOT EXISTS project_complexity_assessment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id VARCHAR(50) NOT NULL,
    total_score INTEGER NOT NULL,
    category VARCHAR(10) NOT NULL CHECK (category IN ('LOW', 'MEDIUM', 'HIGH')),
    notes TEXT,
    assessed_by VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 4. Criar índice para project_id
CREATE INDEX IF NOT EXISTS idx_project_complexity_project_id 
ON project_complexity_assessment(project_id);

-- 5. Criar tabela de detalhes da avaliação
CREATE TABLE IF NOT EXISTS project_complexity_assessment_detail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id INTEGER NOT NULL,
    criteria_id INTEGER NOT NULL,
    option_id INTEGER NOT NULL,
    score INTEGER NOT NULL,
    FOREIGN KEY (assessment_id) REFERENCES project_complexity_assessment (id) ON DELETE CASCADE,
    FOREIGN KEY (criteria_id) REFERENCES complexity_criteria (id),
    FOREIGN KEY (option_id) REFERENCES complexity_criteria_option (id)
);

-- 6. Criar tabela de thresholds de complexidade
CREATE TABLE IF NOT EXISTS complexity_threshold (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category VARCHAR(10) NOT NULL UNIQUE CHECK (category IN ('LOW', 'MEDIUM', 'HIGH')),
    min_score INTEGER NOT NULL,
    max_score INTEGER
);

-- 7. Inserir critérios baseados nas imagens fornecidas
INSERT OR IGNORE INTO complexity_criteria (id, name, description, 'order') VALUES
(1, 'Quantidade de horas', 'Total de horas estimadas para o projeto', 1),
(2, 'Tipo de escopo', 'Nível de customização e complexidade do escopo', 2),
(3, 'DeadLine Previsto', 'Prazo disponível para entrega do projeto', 3),
(4, 'Tipo de cliente', 'Categoria e nível de exigência do cliente', 4);

-- 8. Inserir opções para "Quantidade de horas"
INSERT OR IGNORE INTO complexity_criteria_option (criteria_id, label, description, score, 'order') VALUES
(1, '0-25 horas', 'Projetos pequenos com até 25 horas', 25, 1),
(1, '26-50 horas', 'Projetos médios entre 26 e 50 horas', 50, 2),
(1, '51-75 horas', 'Projetos grandes entre 51 e 75 horas', 75, 3),
(1, '76-100+ horas', 'Projetos muito grandes com mais de 76 horas', 100, 4);

-- 9. Inserir opções para "Tipo de escopo"
INSERT OR IGNORE INTO complexity_criteria_option (criteria_id, label, description, score, 'order') VALUES
(2, 'Padrão', 'Escopo bem definido e padronizado', 25, 1),
(2, 'Personalizado', 'Escopo com algumas personalizações', 50, 2),
(2, 'Customizado', 'Escopo altamente customizado', 75, 3),
(2, 'Complexo', 'Escopo muito complexo e inovador', 100, 4);

-- 10. Inserir opções para "DeadLine Previsto"
INSERT OR IGNORE INTO complexity_criteria_option (criteria_id, label, description, score, 'order') VALUES
(3, 'Flexível >6m', 'Prazo flexível, mais de 6 meses', 25, 1),
(3, 'Normal 3-6m', 'Prazo normal entre 3 e 6 meses', 50, 2),
(3, 'Apertado 1-3m', 'Prazo apertado entre 1 e 3 meses', 75, 3),
(3, 'Crítico <1m', 'Prazo crítico, menos de 1 mês', 100, 4);

-- 11. Inserir opções para "Tipo de cliente"
INSERT OR IGNORE INTO complexity_criteria_option (criteria_id, label, description, score, 'order') VALUES
(4, 'Padrão', 'Cliente com demandas padrão', 25, 1),
(4, 'Corporativo', 'Cliente corporativo com processos definidos', 50, 2),
(4, 'Estratégico', 'Cliente estratégico com alta importância', 75, 3),
(4, 'Especial', 'Cliente especial com demandas muito específicas', 100, 4);

-- 12. Inserir thresholds de complexidade
INSERT OR IGNORE INTO complexity_threshold (category, min_score, max_score) VALUES
('LOW', 0, 149),
('MEDIUM', 150, 249),
('HIGH', 250, NULL);

-- 13. Verificação dos dados inseridos
SELECT 'Critérios criados:' as info, COUNT(*) as total FROM complexity_criteria;
SELECT 'Opções criadas:' as info, COUNT(*) as total FROM complexity_criteria_option;
SELECT 'Thresholds criados:' as info, COUNT(*) as total FROM complexity_threshold; 