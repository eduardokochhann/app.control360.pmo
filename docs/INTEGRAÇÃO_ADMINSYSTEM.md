# 🔗 Integração Control360 ↔ Adminsystem
## Arquivamento Automático de Dados Mensais

### 📋 **Requisitos para Automação Completa**

#### **1. Fluxo Proposto:**
```
Day 1 do mês → Adminsystem → Criar dadosr_apt_[mes_anterior].csv → Control360
```

#### **2. Implementação no Adminsystem:**

**2.1. Trigger Automático (Dia 1 do mês):**
```python
# Exemplo de integração no Adminsystem
import datetime
from pathlib import Path

def arquivar_dados_mensais_automatico():
    """Função a ser chamada todo dia 1º do mês pelo Adminsystem"""
    hoje = datetime.date.today()
    
    # Apenas executa no dia 1
    if hoje.day != 1:
        return
        
    # Calcula o mês anterior
    primeiro_dia_mes_atual = hoje.replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - datetime.timedelta(days=1)
    mes_anterior = ultimo_dia_mes_anterior.month
    ano_anterior = ultimo_dia_mes_anterior.year
    
    # Mapeia mês para abreviação
    mes_abbr = {
        1: 'jan', 2: 'fev', 3: 'mar', 4: 'abr', 5: 'mai', 6: 'jun',
        7: 'jul', 8: 'ago', 9: 'set', 10: 'out', 11: 'nov', 12: 'dez'
    }[mes_anterior]
    
    # Define o arquivo de destino
    arquivo_destino = f"dadosr_apt_{mes_abbr}.csv"
    
    # Copia dadosr.csv para o arquivo histórico
    copiar_dados_para_historico("dadosr.csv", arquivo_destino)
    
    print(f"✅ Arquivo {arquivo_destino} criado automaticamente")
```

**2.2. API Endpoint no Control360:**
```python
# Endpoint para receber comando de arquivamento do Adminsystem
@macro_bp.route('/api/arquivar-mensal', methods=['POST'])
def api_arquivar_mensal():
    """API para Adminsystem solicitar arquivamento mensal"""
    try:
        # Executa o script de arquivamento
        resultado = os.system("python scripts/arquivar_dados_mensais.py --automatico")
        
        if resultado == 0:
            return jsonify({"status": "success", "mensagem": "Arquivamento realizado"})
        else:
            return jsonify({"status": "error", "mensagem": "Falha no arquivamento"})
            
    except Exception as e:
        return jsonify({"status": "error", "mensagem": str(e)})
```

#### **3. Fluxo Completo Automatizado:**

```mermaid
graph TD
    A[Dia 1º do mês] --> B[Adminsystem detecta]
    B --> C[Cria dadosr_apt_[mes_anterior].csv]
    C --> D[Control360 detecta automaticamente]
    D --> E[Nova aba aparece no Status Report]
    E --> F[Dados históricos disponíveis]
```

#### **4. Configuração no Control360:**

**4.1. Verificação Automática de Arquivos:**
O sistema já faz isso automaticamente na função `obter_fontes_disponiveis()`.

**4.2. Script de Arquivamento Aprimorado:**
```bash
# Comando para uso pelo Adminsystem
python scripts/arquivar_dados_mensais.py --automatico --mes-anterior
```

#### **5. Monitoramento e Logs:**

**5.1. Logs do Processo:**
- `logs/arquivamento_YYYYMMDD.log`
- Registro de sucesso/falha
- Alertas em caso de problema

**5.2. Verificação de Integridade:**
- Confirma que o arquivo foi criado
- Valida quantidade de registros
- Compara com dados do mês anterior

### 🚨 **Pontos de Atenção:**

1. **Timing**: Arquivamento deve ser feito ANTES de qualquer atualização do dadosr.csv
2. **Backup**: Manter backups dos dados históricos
3. **Validação**: Verificar integridade dos dados arquivados
4. **Rollback**: Possibilidade de desfazer arquivamento se necessário

### 📅 **Cronograma de Implementação:**

#### **Fase 1: Manual Assistido**
- Adminsystem notifica sobre necessidade de arquivamento
- Usuário executa manualmente o script

#### **Fase 2: Semi-Automático**
- Adminsystem chama API do Control360
- Control360 executa arquivamento automaticamente

#### **Fase 3: Totalmente Automático**
- Adminsystem gerencia todo o processo
- Control360 apenas detecta e exibe

### 🔧 **Implementação Imediata (Para Agosto):**

```python
# Comando a ser executado no dia 01/08/2025
python scripts/arquivar_dados_mensais.py --mes 7 --ano 2025 --forcar
```

Isso criará o arquivo `dadosr_apt_jul.csv` e a aba "Julho/2025" aparecerá automaticamente. 