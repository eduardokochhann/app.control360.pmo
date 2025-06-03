#!/usr/bin/env python3
from app import create_app

app = create_app()

with app.app_context():
    from app.macro.services import MacroService
    
    service = MacroService()
    dados = service.carregar_dados()
    
    print("=== TESTE DE BACKLOG_EXISTS EM TODOS OS MODAIS ===\n")
    
    # 1. Projetos Ativos
    projetos_ativos = service.calcular_projetos_ativos(dados)
    print(f"✅ Projetos Ativos: {projetos_ativos['total']} projetos")
    if projetos_ativos['dados'].empty:
        print("  - DataFrame vazio")
    else:
        has_backlog = 'backlog_exists' in projetos_ativos['dados'].columns
        print(f"  - Campo backlog_exists: {'✅ SIM' if has_backlog else '❌ NÃO'}")
        if has_backlog:
            with_backlog = projetos_ativos['dados']['backlog_exists'].sum()
            print(f"  - Projetos com backlog: {with_backlog}")
    
    # 2. Projetos Críticos
    projetos_criticos = service.calcular_projetos_criticos(dados)
    print(f"\n✅ Projetos Críticos: {projetos_criticos['total']} projetos")
    if projetos_criticos['dados'].empty:
        print("  - DataFrame vazio")
    else:
        has_backlog = 'backlog_exists' in projetos_criticos['dados'].columns
        print(f"  - Campo backlog_exists: {'✅ SIM' if has_backlog else '❌ NÃO'}")
        if has_backlog:
            with_backlog = projetos_criticos['dados']['backlog_exists'].sum()
            print(f"  - Projetos com backlog: {with_backlog}")
    
    # 3. Projetos Concluídos
    projetos_concluidos = service.calcular_projetos_concluidos(dados)
    print(f"\n✅ Projetos Concluídos: {projetos_concluidos['total']} projetos")
    if projetos_concluidos['dados'].empty:
        print("  - DataFrame vazio")
    else:
        has_backlog = 'backlog_exists' in projetos_concluidos['dados'].columns
        print(f"  - Campo backlog_exists: {'✅ SIM' if has_backlog else '❌ NÃO'}")
        if has_backlog:
            with_backlog = projetos_concluidos['dados']['backlog_exists'].sum()
            print(f"  - Projetos com backlog: {with_backlog}")
    
    # 4. Projetos Eficiência
    projetos_eficiencia = service.calcular_eficiencia_entrega(dados)
    print(f"\n✅ Projetos Eficiência: Total {len(projetos_eficiencia['dados'])} projetos")
    if projetos_eficiencia['dados'].empty:
        print("  - DataFrame vazio")
    else:
        has_backlog = 'backlog_exists' in projetos_eficiencia['dados'].columns
        print(f"  - Campo backlog_exists: {'✅ SIM' if has_backlog else '❌ NÃO'}")
        if has_backlog:
            with_backlog = projetos_eficiencia['dados']['backlog_exists'].sum()
            print(f"  - Projetos com backlog: {with_backlog}")
    
    print("\n=== TESTE CONCLUÍDO ===") 