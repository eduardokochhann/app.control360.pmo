# 🚀 Sistema Automatizado Completo - Control360
## Arquivamento e Exibição de Dados Mensais

### ✅ **O que JÁ ESTÁ AUTOMÁTICO:**

#### 1. **Detecção de Abas** 🔍
- ✅ Sistema detecta automaticamente arquivos `dadosr_apt_*.csv`
- ✅ Cria abas dinâmicas no Status Report da Diretoria
- ✅ Ignora arquivos de backup automaticamente
- ✅ Ordena abas por data (mais recente primeiro)

#### 2. **Sistema de Arquivamento** 📦
- ✅ Script `scripts/arquivar_dados_mensais.py` pronto
- ✅ Modo automático funcional
- ✅ Criação de backups automáticos
- ✅ Validação de integridade

#### 3. **API para Integração** 🔗
- ✅ Endpoint: `POST /macro/api/arquivar-mensal`
- ✅ Integração com Adminsystem preparada
- ✅ Logs e monitoramento

### 📅 **CRONOGRAMA DE EXECUÇÃO:**

#### **Para Agosto (01/08/2025):**

**Opção 1: Manual (Garantido)**
```bash
# Execute no dia 01/08/2025
python scripts/arquivar_dados_mensais.py --automatico
```
**Resultado**: Cria `dadosr_apt_jul.csv` → Aba "Julho/2025" aparece automaticamente

**Opção 2: Via API (Integração Adminsystem)**
```bash
# Adminsystem faz POST para:
# http://localhost:5000/macro/api/arquivar-mensal
curl -X POST http://localhost:5000/macro/api/arquivar-mensal
```

**Opção 3: Agendamento no Servidor**
```bash
# Adicionar no crontab (Linux) ou Task Scheduler (Windows)
# Todo dia 1º às 6:00 AM
0 6 1 * * cd /caminho/control360 && python scripts/arquivar_dados_mensais.py --automatico
```

### 🔄 **FLUXO COMPLETO AUTOMATIZADO:**

```mermaid
graph TD
    A[Dia 1º do mês] --> B{Trigger}
    B -->|Manual| C[Executar script]
    B -->|API| D[Adminsystem chama API]
    B -->|Cron| E[Agendamento automático]
    
    C --> F[Script executa]
    D --> F
    E --> F
    
    F --> G[Cria dadosr_apt_[mes_anterior].csv]
    G --> H[Sistema detecta automaticamente]
    H --> I[Nova aba aparece]
    I --> J[Dados históricos disponíveis]
```

### 🎯 **EXEMPLOS PRÁTICOS:**

#### **No dia 01/08/2025:**
- ✅ Script detecta: "mês anterior = julho"
- ✅ Cria: `dadosr_apt_jul.csv`
- ✅ Backup: `dadosr_apt_jun_backup_[timestamp].csv`
- ✅ Sistema detecta e cria aba "Julho/2025"

#### **No dia 01/09/2025:**
- ✅ Script detecta: "mês anterior = agosto"
- ✅ Cria: `dadosr_apt_ago.csv`
- ✅ Sistema detecta e cria aba "Agosto/2025"

### 📊 **ARQUIVOS GERADOS:**

```
data/
├── dadosr.csv                    # Dados atuais (sempre atualizado)
├── dadosr_apt_jan.csv           # Janeiro/2025 ✅
├── dadosr_apt_fev.csv           # Fevereiro/2025 ✅
├── dadosr_apt_mar.csv           # Março/2025 ✅
├── dadosr_apt_abr.csv           # Abril/2025 ✅
├── dadosr_apt_mai.csv           # Maio/2025 ✅
├── dadosr_apt_jun.csv           # Junho/2025 ✅
├── dadosr_apt_jul.csv           # Julho/2025 🔄 (01/08)
├── dadosr_apt_ago.csv           # Agosto/2025 🔄 (01/09)
└── ...
```

### 🚨 **PONTOS IMPORTANTES:**

#### **1. Timing Crítico:**
- ⚠️ Arquivamento deve ser feito **ANTES** de qualquer atualização do `dadosr.csv`
- ⚠️ Se dados já foram atualizados, o arquivo será do mês atual, não anterior

#### **2. Validação:**
- ✅ Script verifica integridade automaticamente
- ✅ Compara número de registros origem vs destino
- ✅ Cria backups antes de sobrescrever

#### **3. Recuperação:**
- ✅ Backups automáticos com timestamp
- ✅ Possível executar múltiplas vezes com `--forcar`

### 🔧 **INTEGRAÇÃO COM ADMINSYSTEM:**

#### **Código para Adminsystem:**
```python
import requests
import datetime

def arquivar_mensal_control360():
    """Função para chamar do Adminsystem"""
    try:
        # URL da API do Control360
        url = "http://localhost:5000/macro/api/arquivar-mensal"
        
        response = requests.post(url, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            if data["status"] == "success":
                print("✅ Arquivamento mensal realizado com sucesso")
                return True
            else:
                print(f"❌ Erro no arquivamento: {data['mensagem']}")
                return False
        else:
            print(f"❌ Erro HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro na integração: {e}")
        return False

# Chamar todo dia 1º do mês
if datetime.date.today().day == 1:
    arquivar_mensal_control360()
```

### 📈 **BENEFÍCIOS DO SISTEMA:**

1. **✅ Zero Configuração Manual**: Sistema detecta arquivos automaticamente
2. **✅ Tolerante a Falhas**: Ignora backups, cria novos se necessário
3. **✅ Integridade Garantida**: Validação automática de dados
4. **✅ Flexível**: Funciona manual, API ou agendado
5. **✅ Retrocompatível**: Funciona com arquivos existentes

### 🎯 **RESUMO FINAL:**

**Resposta à sua pergunta**: Sim, o sistema está **totalmente automático** para detectar e exibir abas. O único passo que precisa ser executado é **arquivar os dados no dia 1º** (manual, API ou agendado).

**Para agosto**: Execute `python scripts/arquivar_dados_mensais.py --automatico` no dia 01/08 e a aba "Julho/2025" aparecerá automaticamente! 🚀 