# Correção do Status Report Individual - Data do Evento e Tradução

## Problema Identificado
No Status Report individual dos projetos (`/macro/status-report/<project_id>`), duas questões foram identificadas:
1. **Data incorreta**: Estava sendo mostrada a data de criação da nota em vez da data do evento
2. **Campos em inglês**: Prioridade e categoria apareciam em inglês (Low, High, decision, etc.)

## Solução Implementada

### 1. Correção da Data (Backend)
**Arquivo**: `app/macro/services.py`
- Adicionado campo `data_exibicao` que prioriza a data do evento
- Lógica implementada:
  - Se `event_date` existe: usa data do evento (formato: dd/mm/yyyy)
  - Se não existe: usa data de criação (formato: dd/mm/yyyy HH:MM)
  - Fallback: 'N/A' se nenhuma data disponível

```python
# Usar data do evento quando disponível, senão usar data de criação
data_exibicao = note.event_date.strftime('%d/%m/%Y') if note.event_date else (note.created_at.strftime('%d/%m/%Y %H:%M') if note.created_at else 'N/A')
```

### 2. Tradução dos Campos (Backend)
**Arquivo**: `app/macro/services.py`
- Criadas funções `_traduzir_categoria()` e `_traduzir_prioridade()`
- Mapeamento completo inglês → português:

**Categorias:**
- `decision` → `Decisão`
- `impediment` → `Impedimento`
- `general` → `Geral`
- `risk` → `Risco`
- `meeting` → `Reunião`
- `update` → `Atualização`

**Prioridades:**
- `high` → `Alta`
- `medium` → `Média`
- `low` → `Baixa`
- `urgent` → `Urgente`
- `normal` → `Normal`

### 3. Correção do Template (Frontend)
**Arquivo**: `templates/macro/status_report.html`
- Alterado de `nota.data_criacao` para `nota.data_exibicao`
- Agora mostra a data do evento quando disponível

## Benefícios da Correção

### ✅ Cronologia Correta
- Notas ordenadas por data do evento
- Timeline das atividades respeitada
- Histórico do projeto mais preciso

### ✅ Interface em Português
- Todas as informações em português
- Melhor usabilidade para usuários brasileiros
- Padronização com resto do sistema

### ✅ Consistência
- Mesmo comportamento da Central de Comando PMO
- Dados sincronizados entre módulos
- Experiência unificada

## Exemplo de Resultado

**Antes:**
```
[Impedimento] [Low] 
Reunião sobre migração do Exchange...
05/07/2025 09:24  ← Data de criação
```

**Depois:**
```
[Impedimento] [Baixa] 
Reunião sobre migração do Exchange...
05/07/2025  ← Data do evento
```

## Arquivos Modificados
1. `app/macro/services.py` - Tradução e lógica de data
2. `templates/macro/status_report.html` - Uso do campo correto

## Compatibilidade
- ✅ **Backward Compatible**: Mantém campos existentes
- ✅ **Sem Breaking Changes**: Fallback para data de criação
- ✅ **Sem Impacto Performance**: Mesma quantidade de queries
- ✅ **Ordenação Preservada**: Mantém ordenação por data do evento

## Testes
Para testar a correção:
1. Acesse `/macro/status-report/<project_id>`
2. Verifique se as datas mostradas correspondem à data do evento
3. Confirme que categorias e prioridades estão em português
4. Compare com a Central de Comando PMO para consistência

A correção garante que o Status Report Individual agora tenha a mesma cronologia correta da Central de Comando PMO, com todas as informações em português para uma melhor experiência do usuário. 