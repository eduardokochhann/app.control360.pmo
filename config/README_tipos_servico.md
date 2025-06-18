# 🔧 Sistema de Configuração de Tipos de Serviço

Este sistema permite configurar e categorizar tipos de serviço sem alterar código, usando um arquivo JSON simples.

## 📁 Arquivos de Configuração

### `tipos_servico_config.json`
Arquivo principal com todas as configurações de categorias, cores, ícones e métricas.

## 🏷️ Estrutura de Categorias

Cada categoria possui:
- **Nome**: Nome exibido na interface
- **Cor**: Código hexadecimal para visual consistency
- **Ícone**: Ícone Bootstrap Icons (ex: `bi-cloud`, `bi-shield-check`)
- **Descrição**: Descrição opcional
- **Tipos**: Lista de tipos de serviço pertencentes à categoria

## 🎨 Categorias Pré-configuradas

### Azure Infrastructure (`azure_infrastructure`)
- **Cor**: `#0078D4` (Azul Azure)
- **Ícone**: `bi-cloud`
- **Tipos**: Active Directory, App Services, Storage, etc.

### Microsoft 365 (`microsoft_365`)
- **Cor**: `#FF8C00` (Laranja M365)
- **Ícone**: `bi-microsoft`
- **Tipos**: Teams, SharePoint, Exchange, Power Platform

### Security & Compliance (`security_compliance`)
- **Cor**: `#E74856` (Vermelho Segurança)
- **Ícone**: `bi-shield-check`
- **Tipos**: Defender, Threat Protection, Compliance

### Data & Analytics (`data_analytics`)
- **Cor**: `#107C10` (Verde Dados)
- **Ícone**: `bi-graph-up`
- **Tipos**: Power BI, Data Factory, Analytics

### Migration Services (`migration_services`)
- **Cor**: `#8B4B9B` (Roxo Migração)
- **Ícone**: `bi-arrow-repeat`
- **Tipos**: Tenant migration, Hybrid setups

### Desenvolvimento Personalizado (`custom_development`)
- **Cor**: `#FF6B35` (Laranja Custom)
- **Ícone**: `bi-code-slash`
- **Tipos**: Soluções personalizadas

## ⚙️ Configurações de Exibição

```json
"configuracoes_exibicao": {
  "cards_por_linha": 6,
  "mostrar_detalhes_expandidos": false,
  "ordenacao_padrao": "total_projetos",
  "cores_graficos": ["#0078D4", "#FF8C00", "#E74856", ...]
}
```

## 📊 Métricas de Complexidade

```json
"metricas_personalizadas": {
  "complexidade_baixa": {"max_horas": 50, "cor": "#107C10"},
  "complexidade_media": {"max_horas": 200, "cor": "#FF8C00"},
  "complexidade_alta": {"max_horas": 999999, "cor": "#E74856"}
}
```

## 🚀 Como Fazer Alterações

### 1. Adicionar Novo Tipo de Serviço
```json
{
  "categorias": {
    "azure_infrastructure": {
      "tipos": [
        "Azure Active Directory",
        "Novo Serviço Azure"  // ← Adicione aqui
      ]
    }
  }
}
```

### 2. Criar Nova Categoria
```json
{
  "categorias": {
    "nova_categoria": {
      "nome": "Nova Categoria",
      "cor": "#FF6B35",
      "icone": "bi-gear",
      "descricao": "Descrição da categoria",
      "tipos": ["Tipo 1", "Tipo 2"]
    }
  }
}
```

### 3. Alterar Cores/Ícones
Simplesmente edite os valores `cor` e `icone` na categoria desejada.

### 4. Ajustar Complexidade
Modifique os valores `max_horas` nas métricas personalizadas.

## 🔄 Aplicar Mudanças

1. **Edite** o arquivo `tipos_servico_config.json`
2. **Reinicie** o servidor Flask
3. **Recarregue** a página do dashboard
4. **Verifique** se as mudanças foram aplicadas na aba "Tipos de Serviço"

## 🛠️ APIs Disponíveis

- `GET /macro/api/tipos-servico/config` - Obter configuração atual
- `POST /macro/api/tipos-servico/config` - Salvar nova configuração (futuro admin)

## 🎯 Boas Práticas

### Cores
- Use paleta de cores consistente
- Evite cores muito similares entre categorias
- Considere acessibilidade (contraste)

### Ícones
- Use apenas ícones do Bootstrap Icons
- Escolha ícones que façam sentido para a categoria
- Mantenha consistência visual

### Nomes de Tipos
- Use nomes claros e descritivos
- Mantenha consistência de nomenclatura
- Evite abreviações desnecessárias

## 🔧 Solução de Problemas

### Categoria não aparece
- Verifique se o JSON está válido
- Confirme se reiniciou o servidor
- Verifique logs de erro no console

### Cores não aplicadas
- Confirme formato hexadecimal (#RRGGBB)
- Limpe cache do navegador
- Verifique se não há CSS conflitante

### Tipos não categorizados
- Verifique nome exato do tipo no banco
- Confirme se está na lista da categoria correta
- Tipos não encontrados vão para "Outros Serviços"

## 📈 Monitoramento

O sistema automaticamente:
- ✅ Classifica complexidade por horas
- ✅ Organiza visualmente por categoria
- ✅ Calcula rankings configuráveis
- ✅ Identifica tipos não categorizados
- ✅ Aplica fallbacks para dados ausentes 