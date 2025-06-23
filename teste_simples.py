#!/usr/bin/env python3
"""
Teste simples para verificar se há erros de sintaxe
"""
try:
    print("Testando importação...")
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    from app.macro.periodo_fiscal_service import StatusReportHistoricoService
    print("✅ Importação bem-sucedida!")
    
except SyntaxError as e:
    print(f"❌ Erro de sintaxe: {e}")
    print(f"   Arquivo: {e.filename}")
    print(f"   Linha: {e.lineno}")
    print(f"   Texto: {e.text}")
except Exception as e:
    print(f"❌ Outro erro: {e}") 