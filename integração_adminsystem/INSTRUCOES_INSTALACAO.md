# 🔧 Instruções de Instalação - Botão Arquivamento Control360

## 📋 **Pré-requisitos**

- AdminSystem rodando com Bootstrap 5
- Control360 acessível na rede
- Permissões para editar arquivos do AdminSystem

## 🚀 **Instalação Rápida**

### **1. Adicionar HTML**

Abra o arquivo principal do AdminSystem onde você quer o botão (provavelmente na página de gerenciamento) e adicione o conteúdo de `botao_arquivamento.html` na seção apropriada.

**Exemplo de localização:**
```html
<!-- Suas seções existentes do AdminSystem -->
<div class="container">
    <!-- Upload CSV, etc... -->
    
    <!-- ADICIONAR AQUI o conteúdo de botao_arquivamento.html -->
    <div class="card mb-4">
        <div class="card-header bg-info text-white">
            <h5 class="mb-0">
                <i class="bi bi-archive"></i> Arquivamento Mensal Control360
            </h5>
        </div>
        <!-- ... resto do HTML ... -->
    </div>
    
    <!-- Continuar com outras seções -->
</div>
```

### **2. Adicionar JavaScript**

#### **Opção A: Arquivo Separado (Recomendado)**
1. Copie `arquivamento.js` para a pasta `static/js/` do AdminSystem
2. Adicione no HTML do AdminSystem:

```html
<script src="static/js/arquivamento.js"></script>
```

#### **Opção B: Inline**
Adicione o conteúdo de `arquivamento.js` dentro de uma tag `<script>` no final da página:

```html
<script>
// Conteúdo do arquivo arquivamento.js aqui
</script>
```

### **3. Configurar URLs**

No arquivo `arquivamento.js`, ajuste a configuração conforme seu ambiente:

```javascript
const CONFIG = {
    // ⚠️ IMPORTANTE: Ajustar URL do Control360
    CONTROL360_BASE_URL: 'http://localhost:5000',  // <- Alterar se necessário
    
    // Endpoint (não alterar)
    API_ENDPOINT: '/macro/api/arquivar-mensal',
    
    // Timeout (ajustar se necessário)
    REQUEST_TIMEOUT: 30000
};
```

## 🎯 **Configurações por Ambiente**

### **Desenvolvimento:**
```javascript
CONTROL360_BASE_URL: 'http://localhost:5000'
```

### **Produção (mesmo servidor):**
```javascript
CONTROL360_BASE_URL: ''  // URL relativa
```

### **Produção (servidor diferente):**
```javascript
CONTROL360_BASE_URL: 'https://control360.seudominio.com'
```

## ✅ **Verificação da Instalação**

### **1. Verificar Elementos Visuais**
- [ ] Botão "Arquivar Mês Anterior" aparece
- [ ] Seção "Mais informações" expande/contrai
- [ ] Modal de confirmação abre ao clicar

### **2. Verificar Console**
Abra F12 → Console e procure por:
```
🚀 Inicializando sistema de arquivamento Control360...
✅ Sistema de arquivamento inicializado com sucesso
```

### **3. Testar Conexão (Opcional)**
No console do navegador, execute:
```javascript
ArquivamentoControl360.testarConexao()
```

## 🔧 **Resolução de Problemas**

### **Erro: "Elemento btnArquivarMensal não encontrado"**
- ✅ Verifique se o HTML foi adicionado corretamente
- ✅ Confirme que o JavaScript carrega após o HTML

### **Erro: "Failed to fetch" ou conexão**
- ✅ Verifique se Control360 está rodando
- ✅ Ajuste `CONTROL360_BASE_URL` no arquivo JS
- ✅ Verifique CORS se estiverem em domínios diferentes

### **Modal não abre**
- ✅ Confirme que Bootstrap 5 está carregado
- ✅ Verifique se não há conflitos de jQuery/Bootstrap

### **API retorna erro 404**
- ✅ Confirme que Control360 está atualizado
- ✅ Verifique se o endpoint `/macro/api/arquivar-mensal` existe

## 📱 **Layout Responsivo**

O componente foi criado com Bootstrap 5 e é totalmente responsivo:

- **Desktop**: Botão grande à direita
- **Mobile**: Botão centralizado embaixo
- **Tablet**: Layout adaptativo

## 🎨 **Personalização Visual**

### **Mudar Cor do Botão:**
```css
#btnArquivarMensal {
    background-color: #your-color !important;
    border-color: #your-color !important;
}
```

### **Mudar Cor do Card:**
No HTML, altere:
```html
<div class="card-header bg-info text-white">
```
Para:
```html
<div class="card-header bg-primary text-white">  <!-- ou bg-success, bg-warning, etc -->
```

## 🔄 **Próximos Passos**

Após instalação e teste:

1. **Testar em 01/08/2025** o processo completo
2. **Configurar automação** via cron job (opcional)
3. **Monitorar logs** do Control360 durante execução
4. **Treinar usuários** sobre quando usar

## 📞 **Suporte**

Em caso de problemas:
1. Verificar logs do Control360: `logs/`
2. Verificar console do navegador (F12)
3. Testar API diretamente: `POST http://localhost:5000/macro/api/arquivar-mensal` 