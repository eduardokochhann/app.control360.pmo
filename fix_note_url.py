import re

def fix_notes_api_url():
    print("Corrigindo a URL do método saveNote no board.html...")
    
    file_path = 'app/backlog/templates/backlog/board.html'
    
    # Ler o arquivo
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Padrão para encontrar a linha com a URL que precisa ser corrigida
    pattern = r'(\s*\?\s*`/backlog/api/notes/\${this\.currentEditingNoteId}`\s*\n\s*:\s*)[\'"](/?)api/notes[\'"]'
    
    # Checar se o padrão existe no conteúdo
    if re.search(pattern, content):
        # Corrigir a URL adicionando o prefixo /backlog/ se não estiver presente
        fixed_content = re.sub(pattern, r'\1\'/backlog/api/notes\'', content)
        
        # Verificar se houve mudança
        if fixed_content != content:
            # Escrever o conteúdo corrigido de volta no arquivo
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            print("URL corrigida com sucesso!")
            return True
        else:
            print("Nenhuma alteração foi necessária.")
            return False
    else:
        # Tentar outro padrão, mais específico
        pattern2 = r'const url = this\.currentEditingNoteId\s*\?\s*`/backlog/api/notes/\${this\.currentEditingNoteId}`\s*\n\s*:\s*[\'"](/?)api/notes[\'"];'
        
        if re.search(pattern2, content):
            fixed_content = re.sub(pattern2, r'const url = this.currentEditingNoteId \
                ? `/backlog/api/notes/${this.currentEditingNoteId}`\
                : \'/backlog/api/notes\';', content)
            
            # Verificar se houve mudança
            if fixed_content != content:
                # Escrever o conteúdo corrigido de volta no arquivo
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)
                print("URL corrigida com sucesso (segundo padrão)!")
                return True
            else:
                print("Nenhuma alteração foi necessária (segundo padrão).")
                return False
        else:
            # Tentativa final - substituição manual
            pattern3 = r'const url = this\.currentEditingNoteId[^;]+;'
            replacement3 = 'const url = this.currentEditingNoteId \
                ? `/backlog/api/notes/${this.currentEditingNoteId}`\
                : \'/backlog/api/notes\';'
            
            fixed_content = re.sub(pattern3, replacement3, content)
            
            if fixed_content != content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)
                print("URL corrigida com sucesso (substituição manual)!")
                return True
            else:
                print("Não foi possível corrigir a URL. Padrão não encontrado.")
                return False

if __name__ == "__main__":
    fix_notes_api_url() 