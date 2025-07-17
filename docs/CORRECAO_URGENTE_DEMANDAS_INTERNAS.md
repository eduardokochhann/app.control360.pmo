# CORREÇÃO URGENTE: Nome da Coluna para Demandas Internas

## 🚨 Problema Identificado
A implementação inicial **não estava funcionando** porque usávamos o nome errado da coluna após o processamento do pandas.

## ❌ **ERRO INICIAL**
```python
# INCORRETO - nome da coluna no CSV original
servico_terceiro_nivel = projeto_row.get('Serviço (3º Nível)', '')
```

## ✅ **CORREÇÃO APLICADA**
```python
# CORRETO - nome da coluna após processamento do pandas
servico_terceiro_nivel = projeto_row.get('TipoServico', '')
```

## 🔍 **Causa do Problema**
No processamento de dados do `MacroService` (linha 251), há um mapeamento que renomeia as colunas:

```python
rename_map_new_to_old = {
    'Serviço (3º Nível)': 'TipoServico',  # Esta linha causava o problema
    # ... outras colunas
}
```

## 📋 **Cronologia da Correção**
1. **Implementação inicial**: Usava `'Serviço (3º Nível)'`
2. **Teste em produção**: Status Report ainda mostrava 0.0%
3. **Investigação**: Descoberto mapeamento de colunas no pandas
4. **Correção**: Alterado para `'TipoServico'`

## 🛠️ **Arquivos Corrigidos**
- ✅ `app/macro/services.py` - Função `gerar_dados_status_report()`
- ✅ `CORRECAO_DEMANDAS_INTERNAS_PERCENTUAL.md` - Documentação atualizada
- ✅ `static/js/test_demandas_internas.js` - Testes atualizados

## ⚡ **Status Atual**
**CORREÇÃO APLICADA E ATIVA**

Agora o sistema deve detectar corretamente os projetos de Demandas Internas:
- Projeto 9336 (PIM)
- Projeto 10407 (Copilot SOU) 
- Projeto 11664 (BI Gerencial)

## 🧪 **Como Verificar**
1. Acesse `/macro/status-report/11664`
2. O campo **PROGRESSO** deve mostrar percentual calculado por tarefas
3. Verifique logs do servidor para confirmação

## 📝 **Lição Aprendida**
Sempre verificar se o processamento de dados do pandas renomeia colunas antes de implementar funcionalidades que dependem dos nomes das colunas. 