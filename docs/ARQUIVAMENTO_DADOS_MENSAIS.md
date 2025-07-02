# 📁 Arquivamento de Dados Mensais - Control360

## Visão Geral

O sistema Control360 possui um mecanismo de arquivamento de dados mensais que permite preservar snapshots dos dados para análises históricas no Status Report da Diretoria.

## Como Funciona

### Padrão de Arquivos

Os dados mensais são arquivados seguindo o padrão:
```
data/dadosr_apt_[mes].csv
```

Onde `[mes]` é a abreviação de 3 letras:
- `jan` - Janeiro
- `fev` - Fevereiro  
- `mar` - Março
- `abr` - Abril
- `mai` - Maio
- `jun` - Junho
- `jul` - Julho
- `ago` - Agosto
- `set` - Setembro
- `out` - Outubro
- `nov` - Novembro
- `dez` - Dezembro

### Script de Arquivamento

O script `scripts/arquivar_dados_mensais.py` automatiza o processo de criação dos arquivos mensais.

## Uso do Script

### Arquivamento Automático

Para arquivar o mês anterior automaticamente (recomendado nos dias 1-2 do mês):

```bash
python scripts/arquivar_dados_mensais.py --automatico
```

### Arquivamento Manual

Para arquivar um mês específico:

```bash
# Arquivar junho de 2025
python scripts/arquivar_dados_mensais.py --mes 6 --ano 2025

# Forçar sobrescrita de arquivo existente
python scripts/arquivar_dados_mensais.py --mes 6 --ano 2025 --forcar
```

### Modo Interativo

Executar sem parâmetros para modo interativo:

```bash
python scripts/arquivar_dados_mensais.py
```

## Processo de Arquivamento

1. **Backup Automático**: Se o arquivo já existir, um backup é criado automaticamente
2. **Cópia dos Dados**: Os dados atuais (`dadosr.csv`) são copiados para o arquivo mensal
3. **Verificação de Integridade**: O script verifica se a cópia foi bem-sucedida
4. **Relatório**: Exibe informações sobre o arquivamento realizado

## Integração com Status Report

### Abas Históricas

Os arquivos arquivados aparecem automaticamente como abas no Status Report:
- **Visão Atual**: Usa `dadosr.csv` (dados correntes)
- **Jun/2025**: Usa `dadosr_apt_jun.csv`
- **Mai/2025**: Usa `dadosr_apt_mai.csv`
- **Abr/2025**: Usa `dadosr_apt_abr.csv`
- E assim por diante...

### Detecção Automática

O sistema detecta automaticamente os arquivos disponíveis e cria as abas correspondentes.

## Cronograma Recomendado

### Dia 1º de cada mês

Execute o arquivamento do mês anterior:

```bash
# Exemplo: No dia 1º de julho, arquivar junho
python scripts/arquivar_dados_mensais.py --automatico
```

### Verificação

Após o arquivamento, verifique se:

1. ✅ O arquivo foi criado em `data/dadosr_apt_[mes].csv`
2. ✅ A nova aba aparece no Status Report
3. ✅ Os dados históricos estão consistentes

## Solução de Problemas

### Arquivo não aparece nas abas

1. Verifique se o arquivo foi criado com o nome correto
2. Certifique-se de que segue o padrão `dadosr_apt_[mes].csv`
3. Reinicie a aplicação se necessário

### Dados inconsistentes

1. Verifique a integridade do arquivo com o script
2. Compare o número de registros com o arquivo original
3. Se necessário, execute novamente com `--forcar`

### Arquivo já existe

Use a opção `--forcar` para sobrescrever:

```bash
python scripts/arquivar_dados_mensais.py --mes 6 --forcar
```

## Estrutura de Arquivos

```
data/
├── dadosr.csv                    # Dados atuais (sempre atualizado)
├── dadosr_apt_jan.csv           # Dados arquivados de Janeiro
├── dadosr_apt_fev.csv           # Dados arquivados de Fevereiro
├── dadosr_apt_mar.csv           # Dados arquivados de Março
├── dadosr_apt_abr.csv           # Dados arquivados de Abril
├── dadosr_apt_mai.csv           # Dados arquivados de Maio
└── dadosr_apt_jun.csv           # Dados arquivados de Junho
```

## Automatização

Para automatizar completamente o processo, considere configurar uma tarefa agendada que execute o script no dia 1º de cada mês:

### Windows (Task Scheduler)

1. Abra o Agendador de Tarefas
2. Crie uma nova tarefa
3. Configure para executar no dia 1º de cada mês
4. Comando: `python [caminho_projeto]/scripts/arquivar_dados_mensais.py --automatico`

### Linux/Mac (Cron)

```bash
# Editar crontab
crontab -e

# Adicionar linha para executar no dia 1º às 02:00
0 2 1 * * cd /caminho/projeto && python scripts/arquivar_dados_mensais.py --automatico
```

## Benefícios

- 📊 **Análises Históricas**: Permite comparar dados entre meses
- 🔒 **Preservação**: Dados mensais ficam preservados mesmo com atualizações
- 🚀 **Automação**: Processo pode ser completamente automatizado
- 📈 **Relatórios**: Status Reports mais ricos com dados históricos
- 🔍 **Rastreabilidade**: Histórico completo da evolução dos projetos

## Exemplo de Uso

```bash
# Dia 1º de julho de 2025 - Arquivar junho
$ python scripts/arquivar_dados_mensais.py --automatico

📊 Script de Arquivamento de Dados Mensais - Control360
============================================================
🤖 Iniciando arquivamento automático para o mês anterior...
📅 Data atual: 01/07/2025
📂 Arquivando dados de Junho/2025
✅ Dados arquivados com sucesso!
📁 Origem: dadosr.csv (167 registros)
📁 Destino: dadosr_apt_jun.csv
📅 Mês arquivado: Jun/2025

🎉 Arquivamento concluído com sucesso!
💡 O arquivo pode agora ser usado nas análises históricas
``` 