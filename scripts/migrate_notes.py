"""
Script para auxiliar na migração dos dados do sistema de notas.
Este script deve ser executado após a criação das novas tabelas.
"""
import os
import sqlite3
from datetime import datetime

def backup_database(db_path, backup_suffix=None):
    """Cria um backup do banco de dados."""
    if backup_suffix is None:
        backup_suffix = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.backup_{backup_suffix}"
    
    print(f"Criando backup do banco de dados: {backup_path}")
    with open(db_path, 'rb') as source:
        with open(backup_path, 'wb') as target:
            target.write(source.read())
    return backup_path

def migrate_data(old_db_path, new_db_path):
    """Migra os dados do banco antigo para o novo."""
    print("Iniciando migração dos dados...")
    
    # Conectar aos bancos
    old_conn = sqlite3.connect(old_db_path)
    new_conn = sqlite3.connect(new_db_path)
    
    try:
        # Migrar tags existentes
        print("Migrando tags...")
        old_tags = old_conn.execute("SELECT * FROM tags").fetchall()
        for tag in old_tags:
            new_conn.execute(
                "INSERT INTO tags (id, name, created_at) VALUES (?, ?, ?)",
                tag
            )
        
        # Migrar notas
        print("Migrando notas...")
        old_notes = old_conn.execute("SELECT * FROM notes").fetchall()
        for note in old_notes:
            # Adaptar os valores ENUM para strings
            category = str(note[3]).lower() if note[3] else 'general'
            priority = str(note[4]).lower() if note[4] else 'medium'
            report_status = str(note[5]).lower() if note[5] else 'draft'
            
            new_conn.execute("""
                INSERT INTO notes (
                    id, content, note_type, category, priority, report_status,
                    project_id, task_id, created_at, updated_at, report_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                note[0], note[1], note[2], category, priority, report_status,
                note[6], note[7], note[8], note[9], note[10]
            ))
        
        # Migrar associações note_tags
        print("Migrando associações note_tags...")
        old_note_tags = old_conn.execute("SELECT * FROM note_tags").fetchall()
        for note_tag in old_note_tags:
            new_conn.execute(
                "INSERT INTO note_tags (note_id, tag_id) VALUES (?, ?)",
                note_tag
            )
        
        # Commit das alterações
        new_conn.commit()
        print("Migração concluída com sucesso!")
        
    except Exception as e:
        print(f"Erro durante a migração: {str(e)}")
        new_conn.rollback()
        raise
    finally:
        old_conn.close()
        new_conn.close()

def main():
    """Função principal do script de migração."""
    # Caminhos dos bancos de dados
    db_path = "instance/app.db"
    backup_path = backup_database(db_path)
    
    try:
        # Migrar os dados
        migrate_data(backup_path, db_path)
    except Exception as e:
        print(f"Erro durante o processo de migração: {str(e)}")
        print(f"O backup do banco de dados está disponível em: {backup_path}")
        return 1
    
    print("Processo de migração concluído com sucesso!")
    return 0

if __name__ == "__main__":
    exit(main()) 