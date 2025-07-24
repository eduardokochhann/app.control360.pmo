# 🔧 Solução Completa: Database is Locked

## 📋 Resumo do Problema

O erro `sqlite3.OperationalError: database is locked` ocorreu em ambiente containerizado quando múltiplas operações tentavam acessar o banco SQLite simultaneamente.

## ✅ Soluções Implementadas

### 1. **Configuração Robusta do SQLite**
- **Arquivo:** `app/__init__.py`
- **Melhorias:**
  - ✅ WAL Mode (`journal_mode=WAL`) para concorrência
  - ✅ Timeout de 30 segundos (`busy_timeout=30000`)
  - ✅ Checkpoint automático (`wal_autocheckpoint=1000`)
  - ✅ Cache otimizado (`cache_size=10000`)
  - ✅ Configurações específicas para containers

### 2. **Pool de Conexões Otimizado**
- **Arquivo:** `app/__init__.py`
- **Configurações:**
  - ✅ Pool timeout: 30 segundos
  - ✅ Pre-ping para verificar conexões
  - ✅ Reciclagem de conexões a cada hora
  - ✅ Configurações thread-safe

### 3. **Sistema de Retry Automático**
- **Arquivo:** `app/utils/db_helper.py`
- **Funcionalidades:**
  - ✅ Decorator `@with_db_retry` para operações de banco
  - ✅ Função `safe_commit()` com retry automático
  - ✅ Backoff exponencial
  - ✅ Rollback automático em caso de erro

### 4. **Aplicação em Pontos Críticos**
- **Arquivo:** `app/backlog/routes.py`
- **Modificações:**
  - ✅ Substituição de `db.session.commit()` por `safe_commit()`
  - ✅ Tratamento específico para operações críticas
  - ✅ Logs detalhados para troubleshooting

### 5. **Sistema de Monitoramento**
- **Arquivos:** `app/admin/db_monitor.py` e `app/admin/routes.py`
- **Endpoints:**
  - ✅ `/admin/api/database/health` - Health check básico
  - ✅ `/admin/api/database/status` - Status detalhado
  - ✅ `/admin/api/database/unlock` - Desbloqueio de emergência

### 6. **Script de Diagnóstico**
- **Arquivo:** `scripts/diagnose_db_locks.py`
- **Funcionalidades:**
  - ✅ Verificação de integridade do banco
  - ✅ Análise de arquivos WAL/SHM
  - ✅ Listagem de processos ativos
  - ✅ Tentativa automática de desbloqueio

## 🚀 Como Usar

### **Em Desenvolvimento:**
```bash
# 1. As configurações são aplicadas automaticamente
# 2. Use safe_commit() em novos códigos:
from app.utils.db_helper import safe_commit

# Suas operações
db.session.add(novo_objeto)
safe_commit()  # Substitui db.session.commit()
```

### **Em Produção (Container):**

#### **1. Monitoramento:**
```bash
# Health check simples
curl http://localhost:5000/admin/api/database/health

# Status detalhado
curl http://localhost:5000/admin/api/database/status
```

#### **2. Desbloqueio de Emergência:**
```bash
# Via API
curl -X POST http://localhost:5000/admin/api/database/unlock

# Via script (dentro do container)
python scripts/diagnose_db_locks.py
```

#### **3. Diagnóstico Completo:**
```bash
# Execute dentro do container
docker exec -it <container_name> python scripts/diagnose_db_locks.py
```

## 📊 Monitoramento Contínuo

### **Métricas Importantes:**
- ✅ Tempo de resposta das operações de banco
- ✅ Frequência de erros de lock
- ✅ Tamanho dos arquivos WAL
- ✅ Número de conexões ativas

### **Alertas Recomendados:**
- 🚨 Mais de 3 locks em 1 minuto
- 🚨 Arquivo WAL > 10MB
- 🚨 Timeout de conexão > 30s

## 🔧 Configurações Críticas

### **SQLite PRAGMA Settings:**
```sql
PRAGMA busy_timeout=30000;        -- 30 segundos timeout
PRAGMA journal_mode=WAL;          -- Write-Ahead Logging
PRAGMA synchronous=NORMAL;        -- Balanço performance/segurança
PRAGMA wal_autocheckpoint=1000;   -- Checkpoint automático
PRAGMA cache_size=10000;          -- Cache otimizado
```

### **SQLAlchemy Settings:**
```python
{
    'pool_timeout': 30,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
    'pool_size': 5,
    'max_overflow': 10,
    'connect_args': {
        'timeout': 30,
        'check_same_thread': False
    }
}
```

## 🆘 Troubleshooting Rápido

### **Problema:** Database is Locked
**Soluções por ordem de prioridade:**

1. **🔄 Reiniciar Aplicação** (mais seguro)
2. **🔧 Desbloqueio via API**: `POST /admin/api/database/unlock`
3. **📜 Script de diagnóstico**: `python scripts/diagnose_db_locks.py`
4. **⚠️ Remoção manual de WAL/SHM** (último recurso)

### **Problema:** Performance Lenta
**Verificações:**

1. **📈 Tamanho do arquivo WAL**: Deve ser < 10MB
2. **🔄 Checkpoint**: Execute `PRAGMA wal_checkpoint`
3. **📊 Pool de conexões**: Verifique conexões ativas
4. **💾 Espaço em disco**: Verifique disponibilidade

## 📞 Suporte e Manutenção

### **Logs Importantes:**
- `logs/app.log` - Logs gerais da aplicação
- Console do container - Erros de banco em tempo real

### **Comandos de Manutenção:**
```bash
# Verificar logs em tempo real
docker logs -f <container_name>

# Backup do banco (precaução)
docker exec <container_name> cp /app/instance/app.db /app/instance/app.db.backup

# Reiniciar apenas a aplicação
docker restart <container_name>
```

### **Escalação:**
Se o problema persistir após aplicar todas as soluções:
1. Colete logs detalhados
2. Execute diagnóstico completo
3. Considere migração para PostgreSQL para maior concorrência

---

**📝 Nota:** Todas as soluções foram implementadas de forma **backward-compatible** e **não-invasiva**. O sistema continuará funcionando mesmo se algumas funcionalidades de retry falharem. 