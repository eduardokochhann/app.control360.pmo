/**
 * 🎨 RICH TEXT EDITOR MANAGER - Control360
 * Sistema avançado de edição de texto com suporte a:
 * - Colar planilhas mantendo formatação
 * - Colar imagens via Ctrl+C/Ctrl+V
 * - Formatação rica de texto
 */

class RichTextEditorManager {
    constructor() {
        this.editors = new Map();
        this.imageUploadUrl = '/upload-image'; // Endpoint para upload de imagens
        this.isQuillLoaded = false;
        
        // 🛡️ Sistema de prevenção de eventos múltiplos
        this.processingEvents = new Set();
        this.lastEventTime = new Map();
        
        this.initialized = false;
        this.init();
    }

    /**
     * 🚀 Inicializa o sistema de editores
     */
    async init() {
        if (this.initialized) return;
        
        console.log('🎨 Inicializando Rich Text Editor Manager...');
        
        // Aguarda a disponibilidade do Quill
        await this.waitForQuill();
        
        // Registra módulos customizados
        this.registerCustomModules();
        
        this.initialized = true;
        console.log('✅ Rich Text Editor Manager inicializado!');
    }

    /**
     * ⏳ Aguarda o Quill.js estar disponível
     */
    waitForQuill() {
        return new Promise((resolve) => {
            if (typeof Quill !== 'undefined') {
                resolve();
                return;
            }
            
            const checkQuill = () => {
                if (typeof Quill !== 'undefined') {
                    resolve();
                } else {
                    setTimeout(checkQuill, 100);
                }
            };
            checkQuill();
        });
    }

    /**
     * 🔧 Registra módulos customizados do Quill
     */
    registerCustomModules() {
        // Módulo para lidar com paste de imagens
        const ImagePasteModule = Quill.import('modules/clipboard');
        
        class CustomClipboard extends ImagePasteModule {
            onPaste(e) {
                if (e.clipboardData && e.clipboardData.files && e.clipboardData.files.length) {
                    this.readFiles(e.clipboardData.files, (dataUrl, file) => {
                        this.insertImage(dataUrl, file);
                    });
                    return;
                }
                super.onPaste(e);
            }

            readFiles(files, callback) {
                Array.from(files).forEach(file => {
                    if (!file.type.match(/^image\/(gif|jpe?g|a?png|svg|webp|bmp|vnd\.microsoft\.icon)/i)) {
                        return;
                    }
                    
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        callback(e.target.result, file);
                    };
                    reader.readAsDataURL(file);
                });
            }

            insertImage(dataUrl, file) {
                const range = this.quill.getSelection();
                if (range) {
                    // Inserir imagem temporariamente
                    this.quill.insertEmbed(range.index, 'image', dataUrl);
                    
                    // Se houver endpoint de upload, fazer upload da imagem
                    if (this.uploadImage) {
                        this.uploadImage(file, range.index);
                    }
                }
            }
        }

        Quill.register('modules/clipboard', CustomClipboard, true);
    }

    /**
     * 🎛️ Configurações padrão do editor
     */
    getDefaultConfig() {
        return {
            theme: 'snow',
            placeholder: 'Digite aqui... (suporte a Ctrl+V para imagens e tabelas)',
            modules: {
                toolbar: {
                    container: [
                        [{ 'header': [1, 2, 3, false] }],
                        ['bold', 'italic', 'underline', 'strike'],
                        [{ 'color': [] }, { 'background': [] }],
                        [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                        [{ 'indent': '-1'}, { 'indent': '+1' }],
                        ['blockquote', 'code-block'],
                        ['link', 'image'],
                        [{ 'align': [] }],
                        ['clean']
                    ],
                    handlers: {
                        'image': this.imageHandler.bind(this)
                    }
                },
                clipboard: {
                    matchers: [
                        // Matcher para Excel/planilhas
                        ['table', this.tableMatcherHandler.bind(this)],
                        ['tr', this.rowMatcherHandler.bind(this)],
                        ['td', this.cellMatcherHandler.bind(this)]
                    ]
                }
            }
        };
    }

    /**
     * 📊 Handler para colar tabelas/planilhas
     */
    tableMatcherHandler(node, delta) {
        console.log('📊 Detectada tabela colada:', node);
        
        // Preserva a estrutura da tabela
        const rows = Array.from(node.querySelectorAll('tr'));
        let tableText = '\n';
        
        rows.forEach(row => {
            const cells = Array.from(row.querySelectorAll('td, th'));
            const rowText = cells.map(cell => cell.textContent.trim()).join(' | ');
            tableText += rowText + '\n';
        });
        
        // Insere como blockquote formatado para destacar
        return new Delta().insert(tableText, { 'blockquote': true });
    }

    rowMatcherHandler(node, delta) {
        return delta;
    }

    cellMatcherHandler(node, delta) {
        return delta;
    }

    /**
     * 🖼️ Handler para inserir imagens
     */
    imageHandler() {
        const input = document.createElement('input');
        input.setAttribute('type', 'file');
        input.setAttribute('accept', 'image/*');
        input.click();

        input.onchange = () => {
            const file = input.files[0];
            if (file) {
                this.processImageFile(file);
            }
        };
    }

    /**
     * 📁 Processa arquivo de imagem (atualizado para usar método específico por editor)
     */
    processImageFile(file) {
        // Encontra o editor ativo mais recente
        const activeEditor = Array.from(this.editors.values()).find(editorData => {
            const container = editorData.container;
            return container && container.style.display !== 'none';
        });
        
        if (activeEditor) {
            this.processImageFileForEditor(file, activeEditor.editor);
        } else {
            console.warn('❌ Nenhum editor ativo encontrado para processar imagem');
        }
    }

    /**
     * ✨ Cria um editor rico para um elemento
     */
    createEditor(elementId, config = {}) {
        const element = document.getElementById(elementId);
        if (!element) {
            console.warn(`❌ Elemento ${elementId} não encontrado`);
            return null;
        }

        // 🧹 LIMPEZA COMPLETA ANTES DE CRIAR
        this.destroyEditor(elementId);
        
        // Aguarda um tick para garantir que a limpeza foi feita
        setTimeout(() => {
            this._actuallyCreateEditor(elementId, element, config);
        }, 10);
        
        return null; // Retorna null porque a criação é assíncrona
    }

    /**
     * 🔨 Realmente cria o editor (método interno)
     */
    _actuallyCreateEditor(elementId, element, config) {
        // Remove textarea e cria container do editor
        const container = this.createEditorContainer(element);
        
        // Merge configurações
        const finalConfig = { ...this.getDefaultConfig(), ...config };
        
        // Cria o editor Quill
        const editor = new Quill(container, finalConfig);
        
        // Armazena referências
        this.editors.set(elementId, {
            editor,
            originalElement: element,
            container
        });

        // Configura eventos
        this.setupEditorEvents(elementId, editor, element);

        console.log(`✅ Editor criado para ${elementId}`);
        return editor;
    }

    /**
     * 🏗️ Cria container do editor
     */
    createEditorContainer(originalElement) {
        // 🧹 Limpeza: remove containers existentes com o mesmo ID
        const existingContainer = document.getElementById(`${originalElement.id}_quill`);
        if (existingContainer) {
            existingContainer.remove();
            console.log(`🧹 Container existente removido: ${originalElement.id}_quill`);
        }
        
        // Limpeza adicional: remove todos os containers órfãos próximos
        const orphans = originalElement.parentNode.querySelectorAll(`[id^="${originalElement.id}_quill"]`);
        orphans.forEach(orphan => {
            orphan.remove();
            console.log(`🧹 Container órfão removido: ${orphan.id}`);
        });
        
        // Esconde o elemento original
        originalElement.style.display = 'none';
        
        // Cria container do editor
        const container = document.createElement('div');
        container.className = 'rich-editor-container';
        container.id = `${originalElement.id}_quill`;
        
        // Insere após o elemento original
        originalElement.parentNode.insertBefore(container, originalElement.nextSibling);
        
        console.log(`🏗️ Novo container criado: ${container.id}`);
        return container;
    }

    /**
     * ⚡ Configura eventos do editor
     */
    setupEditorEvents(elementId, editor, originalElement) {
        // Sincroniza conteúdo com elemento original
        editor.on('text-change', () => {
            const html = editor.root.innerHTML;
            originalElement.value = html;
            
            // Dispara evento para compatibilidade
            originalElement.dispatchEvent(new Event('input', { bubbles: true }));
        });

        // Evento de foco para tracking
        editor.on('selection-change', (range) => {
            if (range) {
                this.currentEditor = editor;
            }
        });

        // Suporte a paste de imagens via Ctrl+V
        editor.root.addEventListener('paste', (e) => {
            this.handlePaste(e, editor);
        });
    }

    /**
     * 📋 Gerencia eventos de cola (paste) - MELHORADO para Excel
     */
    handlePaste(e, editor) {
        const clipboardData = e.clipboardData || window.clipboardData;
        
        console.log('📋 Paste evento detectado');
        
        // 📊 PRIORIDADE 1: Detectar dados tabulares do Excel/Google Sheets
        const htmlData = clipboardData.getData('text/html');
        const textData = clipboardData.getData('text/plain');
        
        // Se tem HTML com tabela OU texto com tabs/quebras, trata como tabela
        if ((htmlData && (htmlData.includes('<table') || htmlData.includes('<tr') || htmlData.includes('<td'))) ||
            (textData && textData.includes('\t') && textData.includes('\n'))) {
            
            console.log('📊 DADOS TABULARES detectados - processando como tabela');
            e.preventDefault();
            e.stopPropagation();
            
            this.processTableData(textData, htmlData, editor);
            return false;
        }
        
        // 🖼️ PRIORIDADE 2: Verificar se tem imagens REAIS (não do Excel)
        if (clipboardData.files && clipboardData.files.length > 0) {
            
            // Verifica se são arquivos de imagem reais
            const imageFiles = Array.from(clipboardData.files).filter(file => 
                file.type.startsWith('image/') && file.size > 0
            );
            
            if (imageFiles.length > 0) {
                console.log(`🖼️ Imagens reais detectadas: ${imageFiles.length}`);
                e.preventDefault();
                e.stopPropagation();
                
                // Processa apenas uma vez por evento
                const processedFiles = new Set();
                
                imageFiles.forEach(file => {
                    const fileKey = file.name + file.size + file.lastModified;
                    if (!processedFiles.has(fileKey)) {
                        processedFiles.add(fileKey);
                        console.log('🖼️ Processando imagem real:', file.name);
                        this.processImageFileForEditor(file, editor);
                    }
                });
                
                return false;
            }
        }
        
        console.log('📝 Paste normal - deixando Quill processar');
        // Para outros tipos de paste, deixa o Quill processar naturalmente
    }

    /**
     * 📊 Processa dados tabulares (Excel/Sheets)
     */
    processTableData(textData, htmlData, editor) {
        let tableContent = '';
        
        if (textData && textData.includes('\t')) {
            // Processa dados separados por tab (Excel padrão)
            const rows = textData.trim().split('\n');
            tableContent = '<table border="1" style="border-collapse: collapse; width: 100%;">\n';
            
            rows.forEach((row, index) => {
                const cells = row.split('\t');
                const tag = index === 0 ? 'th' : 'td'; // Primeira linha como header
                const style = index === 0 ? ' style="background-color: #f8f9fa; font-weight: bold;"' : '';
                
                tableContent += '  <tr>\n';
                cells.forEach(cell => {
                    tableContent += `    <${tag}${style} style="padding: 8px; border: 1px solid #dee2e6;">${cell.trim()}</${tag}>\n`;
                });
                tableContent += '  </tr>\n';
            });
            
            tableContent += '</table>\n';
        } else if (htmlData) {
            // Se tem HTML, tenta extrair e limpar
            tableContent = htmlData;
        }
        
        if (tableContent) {
            const range = editor.getSelection() || { index: 0 };
            const delta = editor.clipboard.convert(tableContent);
            editor.updateContents(delta, 'user');
            editor.setSelection(range.index + delta.length(), 'user');
            
            console.log('✅ Tabela inserida com sucesso');
            this.showToast('Tabela colada com formatação preservada!', 'success');
        }
    }

    /**
     * 📁 Processa arquivo de imagem para um editor específico
     */
    processImageFileForEditor(file, editor) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const range = editor.getSelection();
            if (range) {
                editor.insertEmbed(range.index, 'image', e.target.result);
                console.log(`✅ Imagem inserida no editor: ${file.name}`);
            }
        };
        reader.readAsDataURL(file);
    }

    /**
     * 📝 Define conteúdo de um editor
     */
    setContent(elementId, content) {
        const editorData = this.editors.get(elementId);
        if (editorData) {
            editorData.editor.root.innerHTML = content || '';
            editorData.originalElement.value = content || '';
        }
    }

    /**
     * 📖 Obtém conteúdo de um editor
     */
    getContent(elementId) {
        const editorData = this.editors.get(elementId);
        return editorData ? editorData.editor.root.innerHTML : '';
    }

    /**
     * 🧹 Obtém conteúdo como texto puro
     */
    getTextContent(elementId) {
        const editorData = this.editors.get(elementId);
        return editorData ? editorData.editor.getText() : '';
    }

    /**
     * 🎯 Foca em um editor
     */
    focus(elementId) {
        const editorData = this.editors.get(elementId);
        if (editorData) {
            editorData.editor.focus();
        }
    }

    /**
     * 🗑️ Destroi um editor - VERSÃO ROBUSTA
     */
    destroyEditor(elementId) {
        console.log(`🗑️ Iniciando destruição do editor: ${elementId}`);
        
        const editorData = this.editors.get(elementId);
        if (editorData) {
            try {
                // Salva conteúdo antes de destruir
                if (editorData.editor && editorData.originalElement) {
                    const content = editorData.editor.getText();
                    editorData.originalElement.value = content;
                }
                
                // Remove container do DOM
                if (editorData.container && editorData.container.parentNode) {
                    editorData.container.remove();
                }
                
                // Restaura elemento original
                if (editorData.originalElement) {
                    editorData.originalElement.style.display = '';
                }
                
                console.log(`✅ Editor ${elementId} destruído com sucesso`);
            } catch (error) {
                console.warn(`⚠️ Erro ao destruir editor ${elementId}:`, error);
            }
            
            // Remove da memória
            this.editors.delete(elementId);
        }
        
        // LIMPEZA FORÇADA: remove TODOS os containers órfãos
        this.forceCleanupAllOrphans(elementId);
    }

    /**
     * 🧹 Limpeza forçada de todos os órfãos
     */
    forceCleanupAllOrphans(elementId) {
        // Remove containers órfãos específicos
        const orphanContainers = document.querySelectorAll(`[id^="${elementId}_quill"]`);
        orphanContainers.forEach(container => {
            container.remove();
            console.log(`🧹 Container órfão removido: ${container.id}`);
        });
        
        // Remove toolbars órfãs que podem ter sobrado
        const orphanToolbars = document.querySelectorAll('.ql-toolbar');
        orphanToolbars.forEach(toolbar => {
            // Se a toolbar não tem um editor correspondente, remove
            const parentContainer = toolbar.closest('.rich-editor-container');
            const nextSibling = toolbar.nextElementSibling;
            
            if (!parentContainer || !nextSibling || !nextSibling.classList.contains('ql-container')) {
                toolbar.remove();
                console.log(`🧹 Toolbar órfã removida`);
            }
        });
        
        // Remove containers Quill órfãos
        const orphanQuillContainers = document.querySelectorAll('.ql-container');
        orphanQuillContainers.forEach(container => {
            const parentEditor = container.closest('.rich-editor-container');
            if (!parentEditor) {
                container.remove();
                console.log(`🧹 Container Quill órfão removido`);
            }
        });
    }

    /**
     * 🧹 Limpa containers órfãos
     */
    cleanupOrphanContainers(elementId) {
        const orphanContainers = document.querySelectorAll(`[id^="${elementId}_quill"]`);
        orphanContainers.forEach(container => {
            container.remove();
            console.log(`🧹 Container órfão removido: ${container.id}`);
        });
    }

    /**
     * 🔄 Alterna entre modo simples e rico (versão robusta com anti-spam)
     */
    toggleMode(elementId) {
        // 🛡️ Prevenção de cliques múltiplos
        const eventKey = `toggle_${elementId}`;
        const now = Date.now();
        const lastTime = this.lastEventTime.get(eventKey) || 0;
        
        if (this.processingEvents.has(eventKey) || (now - lastTime) < 500) {
            console.log(`⏳ Evento ${eventKey} ignorado - muito frequente`);
            return;
        }
        
        this.processingEvents.add(eventKey);
        this.lastEventTime.set(eventKey, now);
        
        const button = document.getElementById(`toggleBtn_${elementId}`);
        if (!button) {
            console.warn(`❌ Botão toggle não encontrado para ${elementId}`);
            this.processingEvents.delete(eventKey);
            return;
        }

        // Verifica estado REAL (não apenas se está no Map)
        const hasActiveEditor = this.editors.has(elementId) && 
                               document.getElementById(`${elementId}_quill`);

        console.log(`🔄 Toggle para ${elementId}: hasActiveEditor=${hasActiveEditor}`);

        if (hasActiveEditor) {
            // Está no modo rico -> mudar para simples
            this.switchToSimpleMode(elementId, button, eventKey);
        } else {
            // Está no modo simples -> mudar para rico
            this.switchToRichMode(elementId, button, eventKey);
        }
    }

    /**
     * 📝 Muda para modo simples
     */
    switchToSimpleMode(elementId, button, eventKey) {
        console.log(`📝 Mudando para modo simples: ${elementId}`);
        button.disabled = true;
        button.innerHTML = '<i class="bi bi-hourglass-split"></i> Processando...';
        
        // Salva conteúdo antes de destruir
        const editorData = this.editors.get(elementId);
        let content = '';
        if (editorData && editorData.editor) {
            content = editorData.editor.getText();
        }
        
        this.destroyEditor(elementId);
        
        setTimeout(() => {
            // Garante que o textarea original está visível e com conteúdo
            const originalElement = document.getElementById(elementId);
            if (originalElement) {
                originalElement.style.display = '';
                originalElement.value = content;
            }
            
            button.disabled = false;
            button.innerHTML = '<i class="bi bi-magic"></i> Editor Rico';
            this.showToast('Modo simples ativado', 'success');
            
            // 🛡️ Libera o evento após processamento
            this.processingEvents.delete(eventKey);
        }, 200);
    }

    /**
     * 🎨 Muda para modo rico - PRESERVANDO CONTEÚDO
     */
    switchToRichMode(elementId, button, eventKey) {
        console.log(`🎨 Mudando para modo rico: ${elementId}`);
        button.disabled = true;
        button.innerHTML = '<i class="bi bi-hourglass-split"></i> Processando...';
        
        // ✅ CAPTURA CONTEÚDO ANTES DE DESTRUIR
        const originalElement = document.getElementById(elementId);
        const currentContent = originalElement ? originalElement.value : '';
        console.log(`📄 Conteúdo capturado para ${elementId}:`, currentContent);
        
        // LIMPEZA FORÇADA antes de criar
        this.destroyEditor(elementId);
        
        const config = this.getFieldConfig(elementId);
        
        // Aguarda limpeza terminar
        setTimeout(() => {
            this.createEditor(elementId, config);
            
            // Aguarda criação terminar
            setTimeout(() => {
                const hasEditor = this.editors.has(elementId) && 
                                 document.getElementById(`${elementId}_quill`);
                
                if (hasEditor) {
                    // ✅ TRANSFERE CONTEÚDO PARA O EDITOR RICO
                    if (currentContent) {
                        console.log(`🔄 Transferindo conteúdo para editor rico: ${elementId}`);
                        this.setContent(elementId, currentContent);
                    }
                    
                    button.disabled = false;
                    button.innerHTML = '<i class="bi bi-keyboard"></i> Modo Simples';
                    this.showToast('Editor rico ativado', 'success');
                } else {
                    button.disabled = false;
                    button.innerHTML = '<i class="bi bi-magic"></i> Editor Rico';
                    this.showToast('Erro ao ativar editor rico', 'error');
                }
                
                // 🛡️ Libera o evento após processamento completo
                this.processingEvents.delete(eventKey);
            }, 300);
        }, 100);
    }

    /**
     * 📋 Obtém configuração específica do campo
     */
    getFieldConfig(elementId) {
        const configs = {
            // 📝 Configurações para Tarefas
            'task_description': {
                placeholder: 'Descreva a tarefa... (suporte a Ctrl+V para imagens)',
                modules: {
                    toolbar: [
                        ['bold', 'italic', 'underline'],
                        [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                        ['link', 'image'],
                        ['clean']
                    ]
                }
            },
            
            // ⚠️ Configurações para Riscos
            'risk_description': {
                placeholder: 'Descreva o risco identificado...',
                modules: {
                    toolbar: [
                        ['bold', 'italic'],
                        [{ 'color': [] }],
                        [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                        ['clean']
                    ]
                }
            },
            'mitigation_plan': {
                placeholder: 'Plano de mitigação...',
                modules: {
                    toolbar: [
                        ['bold', 'italic', 'underline'],
                        [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                        ['clean']
                    ]
                }
            },
            
            // 🎯 Configurações para Marcos
            'milestone_description': {
                placeholder: 'Descreva o marco do projeto...',
                modules: {
                    toolbar: [
                        ['bold', 'italic'],
                        [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                        ['link'],
                        ['clean']
                    ]
                }
            },
            
            // 📋 Configurações para Notas
            'note_content': {
                placeholder: 'Digite sua nota... (suporte a imagens e formatação)',
                modules: {
                    toolbar: [
                        [{ 'header': [1, 2, 3, false] }],
                        ['bold', 'italic', 'underline'],
                        [{ 'color': [] }],
                        [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                        ['blockquote', 'link', 'image'],
                        ['clean']
                    ]
                }
            },
            
            // 🧮 Configurações para Complexidade
            'complexity_notes': {
                placeholder: 'Notas sobre complexidade...',
                modules: {
                    toolbar: [
                        ['bold', 'italic'],
                        [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                        ['clean']
                    ]
                }
            }
        };
        
        // Retorna configuração específica ou padrão
        return configs[elementId] || {
            placeholder: 'Digite aqui... (suporte a Ctrl+V para imagens)',
            modules: {
                toolbar: [
                    ['bold', 'italic', 'underline'],
                    [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                    ['link', 'image'],
                    ['clean']
                ]
            }
        };
    }

    /**
     * 🍞 Mostra mensagem toast - VISUAL
     */
    showToast(message, type = 'info') {
        console.log(`📬 Toast ${type}: ${message}`);
        
        // Cria o toast visual
        const toast = document.createElement('div');
        toast.className = `toast-notification toast-${type}`;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : '#007bff'};
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 9999;
            font-family: system-ui, -apple-system, sans-serif;
            font-size: 14px;
            font-weight: 500;
            max-width: 300px;
            word-wrap: break-word;
            transform: translateX(400px);
            transition: all 0.3s ease;
            border-left: 4px solid rgba(255,255,255,0.5);
        `;
        
        const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
        toast.innerHTML = `${icon} ${message}`;
        
        document.body.appendChild(toast);
        
        // Anima entrada
        setTimeout(() => {
            toast.style.transform = 'translateX(0)';
        }, 10);
        
        // Remove após 3 segundos
        setTimeout(() => {
            toast.style.transform = 'translateX(400px)';
            toast.style.opacity = '0';
            
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, 3000);
    }

    /**
     * 📊 Estatísticas dos editores
     */
    getStats() {
        const stats = {
            totalEditors: this.editors.size,
            editors: []
        };

        this.editors.forEach((data, elementId) => {
            stats.editors.push({
                id: elementId,
                textLength: data.editor.getText().length,
                hasContent: data.editor.getText().trim().length > 0
            });
        });

        return stats;
    }
}

// 🌟 Instância global do gerenciador
window.richTextManager = new RichTextEditorManager();

// 🚀 Funções utilitárias globais
window.createRichEditor = (elementId, config) => {
    return window.richTextManager.createEditor(elementId, config);
};

window.setRichEditorContent = (elementId, content) => {
    window.richTextManager.setContent(elementId, content);
};

window.getRichEditorContent = (elementId) => {
    return window.richTextManager.getContent(elementId);
};

window.destroyRichEditor = (elementId) => {
    window.richTextManager.destroyEditor(elementId);
};

window.toggleRichEditorMode = (elementId) => {
    window.richTextManager.toggleMode(elementId);
};

// 🎯 Auto-inicialização quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    console.log('🎨 Rich Text Editor system ready!');
});

console.log('📝 Rich Text Editor Manager carregado!'); 