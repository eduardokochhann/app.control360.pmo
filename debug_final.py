from app import create_app, db
from app.models import Task, TaskSegment

app = create_app()

with app.app_context():
    print("=== DIAGNÓSTICO FINAL ===")
    
    # Busca tarefas do LUCIANO SEABRA
    tasks = Task.query.filter(
        db.func.lower(db.func.trim(Task.specialist_name)) == 'luciano seabra'
    ).all()
    
    print(f"1. Tarefas encontradas: {len(tasks)}")
    
    if len(tasks) == 0:
        # Tenta buscar com variações do nome
        all_specialists = db.session.query(Task.specialist_name).distinct().all()
        print("2. Todos os especialistas no DB:")
        for spec in all_specialists[:10]:
            if spec[0]:
                print(f"   - '{spec[0]}'")
    else:
        print("2. Analisando tarefas:")
        sem_segmentos = 0
        for i, task in enumerate(tasks[:10]):
            segments = TaskSegment.query.filter_by(task_id=task.id).count()
            effort = getattr(task, 'estimated_effort', None)
            
            print(f"   Task {task.id}: '{task.title[:30]}...'")
            print(f"     - Esforço: {effort}")
            print(f"     - Segmentos: {segments}")
            
            if segments == 0 and effort and effort > 0:
                sem_segmentos += 1
                print(f"     ✓ PODE SER SEGMENTADA")
            else:
                print(f"     ✗ NÃO PODE SER SEGMENTADA")
            print()
        
        print(f"3. TOTAL DE TAREFAS SEGMENTÁVEIS: {sem_segmentos}")
        
        if sem_segmentos == 0:
            print("4. PROBLEMA IDENTIFICADO: Nenhuma tarefa tem esforço estimado!")
            # Vamos forçar um esforço para teste
            first_task = tasks[0]
            print(f"5. TESTE: Adicionando 8h à tarefa {first_task.id}")
            first_task.estimated_effort = 8.0
            db.session.commit()
            print("   ✓ Esforço adicionado! Teste novamente.") 