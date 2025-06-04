# Sistema de Arquivamento de Sprints

## Visão Geral

O sistema de arquivamento permite organizar sprints antigas mantendo-as acessíveis para consulta posterior. Sprints arquivadas não aparecem na visualização principal mas podem ser facilmente revisitadas quando necessário.

## Funcionalidades Principais

### 🗂️ **Visualizações Disponíveis**
- **Sprints Ativas**: Apenas sprints não arquivadas (padrão)
- **Sprints Arquivadas**: Apenas sprints que foram arquivadas
- **Todas as Sprints**: Visualização combinada de ativas e arquivadas

### 📦 **Arquivamento Individual**
- Botão "Arquivar" em cada sprint ativa
- Modal de confirmação com campos para:
  - Motivo do arquivamento (opcional)
  - Nome de quem está arquivando
- Preserva todas as tarefas e dados da sprint

### 📋 **Arquivamento em Lote**
- Modo de seleção múltipla com checkboxes
- Arquivamento simultâneo de várias sprints
- Modal específico para operações em lote

### 🔄 **Desarquivamento**
- Sprints arquivadas podem ser desarquivadas
- Retornam para a lista de sprints ativas
- Mantém histórico de arquivamento

### 🔍 **Busca e Filtros**
- Campo de busca por nome ou objetivo da sprint
- Filtros visuais por status de arquivamento
- Busca funciona em todas as visualizações

## Como Usar

### Visualizar Sprints por Status

1. **Sprints Ativas** (padrão)
   - Clique no botão "Sprints Ativas" na toolbar
   - Mostra apenas sprints não arquivadas

2. **Sprints Arquivadas**
   - Clique no botão "Sprints Arquivadas"
   - Mostra apenas sprints que foram arquivadas
   - Cards aparecem com visual diferenciado (opacidade reduzida, borda tracejada)

3. **Todas as Sprints**
   - Clique no botão "Todas as Sprints"
   - Exibe sprints ativas e arquivadas juntas

### Arquivar Sprint Individual

1. **Localizar a Sprint**
   - Na visualização de "Sprints Ativas"
   - Encontre a sprint que deseja arquivar

2. **Iniciar Arquivamento**
   - Clique no botão de ações da sprint
   - Selecione "Arquivar" (ícone de arquivo)

3. **Confirmar Arquivamento**
   - Modal abrirá solicitando confirmação
   - Preencha o motivo (opcional)
   - Confirme o nome de quem está arquivando
   - Clique em "Arquivar Sprint"

### Arquivamento em Lote

1. **Ativar Modo de Seleção**
   - Na visualização de "Sprints Ativas"
   - Clique em "Selecionar Múltiplas"

2. **Selecionar Sprints**
   - Checkboxes aparecerão em cada sprint
   - Marque as sprints que deseja arquivar
   - Botão "Arquivar Selecionadas" se tornará disponível

3. **Executar Arquivamento**
   - Clique em "Arquivar Selecionadas"
   - Modal mostrará lista das sprints selecionadas
   - Preencha motivo e responsável
   - Confirme o arquivamento

### Desarquivar Sprint

1. **Visualizar Sprints Arquivadas**
   - Mude para a visualização "Sprints Arquivadas"

2. **Desarquivar Individual**
   - Clique no botão de "Desarquivar" na sprint (ícone de caixa com seta)
   - Confirme no modal que abrirá

3. **Desarquivar em Lote**
   - Use o modo de seleção múltipla
   - Selecione sprints arquivadas
   - Clique em "Desarquivar Selecionadas"

### Buscar Sprints

1. **Campo de Busca**
   - Use o campo na parte superior direita da toolbar
   - Digite nome da sprint ou parte do objetivo

2. **Filtrar Resultados**
   - A busca funciona em tempo real
   - Aplicada à visualização atual (ativa, arquivada ou todas)
   - Botão "X" limpa a busca

## Características Visuais

### Sprints Ativas
- Visual normal com cores vibrantes
- Botões de editar e arquivar disponíveis
- Drag & drop habilitado

### Sprints Arquivadas
- **Opacidade reduzida** (70%)
- **Bordas tracejadas** para diferenciação
- **Badge "Arquivada"** no cabeçalho
- **Botão de editar oculto**
- **Botão de desarquivar** substitui o de deletar
- **Drag & drop desabilitado**

## APIs Disponíveis

### Arquivamento
```http
PUT /backlog/api/sprints/{sprint_id}/archive
Content-Type: application/json

{
  "archived_by": "Nome do Usuário",
  "reason": "Motivo do arquivamento"
}
```

### Desarquivamento
```http
PUT /backlog/api/sprints/{sprint_id}/unarchive
Content-Type: application/json

{
  "unarchived_by": "Nome do Usuário", 
  "reason": "Motivo do desarquivamento"
}
```

### Listagem de Sprints Ativas
```http
GET /backlog/api/sprints/active?limit=20&include_completed=true
```

### Listagem de Sprints Arquivadas
```http
GET /backlog/api/sprints/archived?limit=50&page=1&search=termo
```

### Arquivamento em Lote
```http
POST /backlog/api/sprints/archive-bulk
Content-Type: application/json

{
  "sprint_ids": [1, 2, 3],
  "archived_by": "Nome do Usuário",
  "reason": "Arquivamento em lote"
}
```

### Detalhes Completos de Sprint
```http
GET /backlog/api/sprints/{sprint_id}/details
```

## Estrutura do Banco de Dados

### Novos Campos na Tabela `sprint`

```sql
-- Campo boolean para marcar se está arquivada
is_archived BOOLEAN NOT NULL DEFAULT FALSE

-- Data/hora do arquivamento 
archived_at DATETIME NULL

-- Quem arquivou (opcional)
archived_by VARCHAR(150) NULL
```

### Índices para Performance
```sql
-- Otimização para consultas por status de arquivamento
CREATE INDEX idx_sprint_is_archived ON sprint(is_archived);
```

## Benefícios

### ✅ **Organização**
- Interface limpa com apenas sprints relevantes
- Histórico preservado e acessível

### ✅ **Performance**
- Consultas mais rápidas na visualização principal
- Índices otimizados para status de arquivamento

### ✅ **Flexibilidade**
- Arquivamento/desarquivamento reversível
- Operações individuais e em lote
- Múltiplas visualizações

### ✅ **Auditoria**
- Registro de quem arquivou e quando
- Motivos documentados
- Histórico completo preservado

### ✅ **Usabilidade**
- Interface intuitiva com controles visuais claros
- Feedback visual para sprints arquivadas
- Busca unificada em todas as visualizações

## Migração

Para aplicar as alterações no banco de dados:

```bash
# Execute o script de migração SQL
mysql -u usuario -p database < migrations/add_sprint_archiving.sql
```

Ou via interface de administração do banco:

```sql
-- Adicionar campos à tabela sprint
ALTER TABLE sprint ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT 0;
ALTER TABLE sprint ADD COLUMN archived_at DATETIME NULL;
ALTER TABLE sprint ADD COLUMN archived_by VARCHAR(150) NULL;

-- Criar índice de performance
CREATE INDEX idx_sprint_is_archived ON sprint(is_archived);
```

## Considerações Importantes

### 🚨 **Dados Preservados**
- Arquivar uma sprint **NÃO** deleta dados
- Todas as tarefas e informações são mantidas
- Apenas altera a visibilidade na interface

### 🚨 **Segurança**
- Não há confirmação extra para desarquivamento
- Usuários podem arquivar/desarquivar livremente
- Considere implementar permissões se necessário

### 🚨 **Performance**
- Sprints arquivadas não afetam performance da visualização principal
- Busca em "Todas as Sprints" pode ser mais lenta com muitos dados
- Considere paginação para grandes volumes

### 🚨 **Integração**
- APIs existentes continuam funcionando normalmente
- Filtros de sprint ativa são aplicados automaticamente
- Relatórios podem precisar ser ajustados para incluir/excluir arquivadas

## Próximos Passos Sugeridos

1. **Sistema de Notificações**: Substituir `alert()` por toasts
2. **Permissões de Usuário**: Controle de quem pode arquivar
3. **Relatórios**: Incluir opções para sprints arquivadas
4. **Auto-arquivamento**: Arquivamento automático de sprints antigas
5. **Categorização**: Tags ou categorias para sprints arquivadas
6. **Exportação**: Export específico de dados arquivados

---

**Versão**: 1.0  
**Data**: Dezembro 2024  
**Autor**: Sistema Control360 SOU 