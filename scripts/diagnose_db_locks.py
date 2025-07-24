#!/usr/bin/env python3
"""
Script de diagnóstico para problemas de "database is locked" em ambientes containerizados
Pode ser executado dentro do container para resolver problemas de lock do SQLite
"""

import sys
import os
import time
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime

def print_header(title):
    """Imprime cabeçalho formatado"""
    print("\n" + "="*60)
    print(f"🔍 {title}")
    print("="*60)

def print_status(status, message):
    """Imprime status formatado"""
    icons = {
        'ok': '✅',
        'warning': '⚠️',
        'error': '❌',
        'info': 'ℹ️'
    }
    print(f"{icons.get(status, '•')} {message}")

def check_sqlite_file(db_path):
    """Verifica o arquivo SQLite"""
    print_header("VERIFICAÇÃO DO ARQUIVO SQLite")
    
    if not os.path.exists(db_path):
        print_status('error', f"Arquivo do banco não encontrado: {db_path}")
        return False
    
    # Informações básicas do arquivo
    stat = os.stat(db_path)
    print_status('info', f"Arquivo: {db_path}")
    print_status('info', f"Tamanho: {stat.st_size / 1024 / 1024:.2f} MB")
    print_status('info', f"Modificado: {datetime.fromtimestamp(stat.st_mtime)}")
    
    # Verifica permissões
    permissions = oct(stat.st_mode)[-3:]
    print_status('info', f"Permissões: {permissions}")
    
    if not os.access(db_path, os.R_OK | os.W_OK):
        print_status('error', "Arquivo sem permissões de leitura/escrita")
        return False
    
    print_status('ok', "Arquivo SQLite acessível")
    return True

def check_sqlite_integrity(db_path):
    """Verifica integridade do banco SQLite"""
    print_header("VERIFICAÇÃO DE INTEGRIDADE")
    
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        cursor = conn.cursor()
        
        # Teste básico de conectividade
        cursor.execute("SELECT 1")
        print_status('ok', "Conexão com banco estabelecida")
        
        # Verifica integridade
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        if result[0] == 'ok':
            print_status('ok', "Integridade do banco: OK")
        else:
            print_status('error', f"Problemas de integridade: {result[0]}")
        
        # Verifica modo de journal
        cursor.execute("PRAGMA journal_mode")
        journal_mode = cursor.fetchone()[0]
        print_status('info', f"Modo de journal: {journal_mode}")
        
        # Verifica timeout
        cursor.execute("PRAGMA busy_timeout")
        timeout = cursor.fetchone()[0]
        print_status('info', f"Timeout configurado: {timeout}ms")
        
        # Lista tabelas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print_status('info', f"Tabelas encontradas: {len(tables)}")
        
        conn.close()
        return True
        
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e).lower():
            print_status('error', "BANCO ESTÁ BLOQUEADO!")
            return False
        else:
            print_status('error', f"Erro operacional: {e}")
            return False
    except Exception as e:
        print_status('error', f"Erro inesperado: {e}")
        return False

def check_wal_files(db_path):
    """Verifica arquivos WAL relacionados"""
    print_header("VERIFICAÇÃO DE ARQUIVOS WAL")
    
    base_path = Path(db_path).parent
    db_name = Path(db_path).stem
    
    wal_file = base_path / f"{db_name}.db-wal"
    shm_file = base_path / f"{db_name}.db-shm"
    
    if wal_file.exists():
        size = wal_file.stat().st_size
        print_status('info', f"Arquivo WAL encontrado: {size} bytes")
        
        if size > 1024 * 1024:  # 1MB
            print_status('warning', "Arquivo WAL grande, pode indicar problemas")
    else:
        print_status('info', "Nenhum arquivo WAL encontrado")
    
    if shm_file.exists():
        print_status('info', "Arquivo SHM encontrado")
    else:
        print_status('info', "Nenhum arquivo SHM encontrado")

def check_processes():
    """Verifica processos que podem estar usando o banco"""
    print_header("VERIFICAÇÃO DE PROCESSOS")
    
    try:
        # Lista processos Python
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        python_procs = [line for line in lines if 'python' in line.lower() and 'ps aux' not in line]
        
        print_status('info', f"Processos Python encontrados: {len(python_procs)}")
        
        for proc in python_procs[:5]:  # Mostra apenas os primeiros 5
            print(f"    {proc.strip()}")
        
        if len(python_procs) > 5:
            print_status('info', f"... e mais {len(python_procs) - 5} processos")
            
    except Exception as e:
        print_status('warning', f"Não foi possível listar processos: {e}")

def attempt_unlock(db_path):
    """Tenta desbloquear o banco"""
    print_header("TENTATIVA DE DESBLOQUEIO")
    
    try:
        # Método 1: Conexão com timeout longo
        print_status('info', "Tentando conexão com timeout longo...")
        conn = sqlite3.connect(db_path, timeout=30)
        
        # Tenta configurar WAL mode
        print_status('info', "Configurando modo WAL...")
        conn.execute("PRAGMA journal_mode=WAL")
        
        # Tenta um checkpoint
        print_status('info', "Executando checkpoint...")
        conn.execute("PRAGMA wal_checkpoint")
        
        conn.close()
        print_status('ok', "Banco desbloqueado com sucesso!")
        return True
        
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e).lower():
            print_status('error', "Banco ainda está bloqueado")
            
            # Método 2: Tentar remover arquivos WAL/SHM
            print_status('info', "Tentando remover arquivos WAL/SHM...")
            try:
                base_path = Path(db_path).parent
                db_name = Path(db_path).stem
                
                wal_file = base_path / f"{db_name}.db-wal"
                shm_file = base_path / f"{db_name}.db-shm"
                
                removed = False
                if wal_file.exists():
                    wal_file.unlink()
                    print_status('ok', "Arquivo WAL removido")
                    removed = True
                
                if shm_file.exists():
                    shm_file.unlink()
                    print_status('ok', "Arquivo SHM removido")
                    removed = True
                
                if removed:
                    # Tenta conectar novamente
                    conn = sqlite3.connect(db_path, timeout=5)
                    conn.execute("SELECT 1")
                    conn.close()
                    print_status('ok', "Banco desbloqueado após remoção de arquivos!")
                    return True
                else:
                    print_status('warning', "Nenhum arquivo WAL/SHM para remover")
                    
            except Exception as e:
                print_status('error', f"Erro ao remover arquivos: {e}")
                
            return False
        else:
            print_status('error', f"Erro diferente: {e}")
            return False
    except Exception as e:
        print_status('error', f"Erro inesperado: {e}")
        return False

def recommend_solutions():
    """Recomenda soluções para o problema"""
    print_header("RECOMENDAÇÕES")
    
    print("🔧 Para resolver problemas de 'database is locked':")
    print()
    print("1. REINICIAR APLICAÇÃO:")
    print("   - Pare todos os processos Python")
    print("   - Aguarde 30 segundos")
    print("   - Reinicie a aplicação")
    print()
    print("2. CONFIGURAÇÃO DE PRODUÇÃO:")
    print("   - Use WAL mode (journal_mode=WAL)")
    print("   - Configure busy_timeout=30000")
    print("   - Implemente retry logic nas operações")
    print()
    print("3. MONITORAMENTO:")
    print("   - Use /admin/api/database/health para monitorar")
    print("   - Configure alertas para locks frequentes")
    print("   - Monitore tamanho dos arquivos WAL")
    print()
    print("4. EMERGÊNCIA:")
    print("   - Use /admin/api/database/unlock para desbloqueio")
    print("   - Execute este script dentro do container")
    print("   - Em último caso, remova arquivos .db-wal e .db-shm")

def main():
    """Função principal"""
    print("🚨 DIAGNÓSTICO DE PROBLEMAS SQLite 'Database is Locked'")
    print(f"⏰ Executado em: {datetime.now()}")
    
    # Encontra o arquivo do banco
    possible_paths = [
        '/app/instance/app.db',
        './instance/app.db',
        '../instance/app.db',
        'instance/app.db',
        'app.db'
    ]
    
    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print_status('error', "Arquivo do banco não encontrado!")
        print_status('info', f"Locais verificados: {possible_paths}")
        return 1
    
    print_status('ok', f"Banco encontrado em: {db_path}")
    
    # Executa verificações
    file_ok = check_sqlite_file(db_path)
    if not file_ok:
        return 1
    
    check_wal_files(db_path)
    check_processes()
    
    integrity_ok = check_sqlite_integrity(db_path)
    
    if not integrity_ok:
        unlock_ok = attempt_unlock(db_path)
        if not unlock_ok:
            recommend_solutions()
            return 1
    
    print_header("DIAGNÓSTICO CONCLUÍDO")
    print_status('ok', "Banco SQLite operando normalmente!")
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 