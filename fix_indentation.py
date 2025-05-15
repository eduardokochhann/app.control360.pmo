import re

def fix_indentation():
    print("Corrigindo indentação no arquivo services.py...")
    
    # Ler o arquivo
    with open('app/macro/services.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Corrigir a primeira seção problemática
    pattern1 = r'if dados_todos\.empty:(\s+)self\.logger\.error'
    replacement1 = 'if dados_todos.empty:\n                self.logger.error'
    content = re.sub(pattern1, replacement1, content)

    # Corrigir a segunda seção problemática
    pattern2 = r'try:(\s+)project_id_int = int\(project_id\)'
    replacement2 = 'try:\n                project_id_int = int(project_id)'
    content = re.sub(pattern2, replacement2, content)

    # Corrigir a terceira seção problemática
    pattern3 = r'if \'Numero\' not in dados_todos\.columns:(\s+)self\.logger\.error'
    replacement3 = 'if \'Numero\' not in dados_todos.columns:\n                self.logger.error'
    content = re.sub(pattern3, replacement3, content)

    # Corrigir a quarta seção problemática
    pattern4 = r'if dados_projeto_df\.empty:(\s+)self\.logger\.warning'
    replacement4 = 'if dados_projeto_df.empty:\n                self.logger.warning'
    content = re.sub(pattern4, replacement4, content)

    # Corrigir a quinta seção problemática
    pattern5 = r'# INÍCIO: Buscar notas do projeto(\s+)notas_do_projeto = \[\]'
    replacement5 = '# INÍCIO: Buscar notas do projeto\n            notas_do_projeto = []'
    content = re.sub(pattern5, replacement5, content)

    # Corrigir a sexta seção problemática
    pattern6 = r'except Exception as e:(\s+)self\.logger\.exception'
    replacement6 = 'except Exception as e:\n            self.logger.exception'
    content = re.sub(pattern6, replacement6, content)

    # Corrigir a sétima seção problemática
    pattern7 = r'def gerar_status_report\(self, project_id\):(\s+)\"\"\"'
    replacement7 = 'def gerar_status_report(self, project_id):\n        \"\"\"'
    content = re.sub(pattern7, replacement7, content)

    # Salvar as alterações
    with open('app/macro/services.py', 'w', encoding='utf-8') as f:
        f.write(content)

    print('Arquivo corrigido com sucesso!')

if __name__ == "__main__":
    fix_indentation() 