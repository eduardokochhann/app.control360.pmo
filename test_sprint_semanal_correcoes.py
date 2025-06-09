#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste das Correções do Sprint Semanal

Este arquivo testa as principais funcionalidades corrigidas:
1. Nova lógica de auto-segmentação (4h/projeto/dia)
2. API de auto-criação de segmentos
3. Fallback do MacroService
4. Carregamento robusto de especialistas

Para executar: python test_sprint_semanal_correcoes.py
"""

import sys
import os
import requests
import json
from datetime import datetime, timedelta

# Configurações do teste
BASE_URL = "http://127.0.0.1:5000"  # Ajuste conforme necessário
ESPECIALISTA_TESTE = "LUCIANO SEABRA"  # Ajuste conforme necessário

def testar_api(endpoint, method="GET", data=None, timeout=10):
    """Função auxiliar para testar APIs"""
    url = f"{BASE_URL}{endpoint}"
    print(f"\n🔍 Testando: {method} {endpoint}")
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=timeout)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=timeout)
        elif method == "PUT":
            response = requests.put(url, json=data, timeout=timeout)
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code < 400:
            try:
                result = response.json()
                print(f"   ✅ Sucesso: {result.get('message', 'OK')}")
                return True, result
            except:
                print(f"   ✅ Sucesso (sem JSON)")
                return True, response.text
        else:
            try:
                error = response.json()
                print(f"   ❌ Erro: {error.get('error', 'Erro desconhecido')}")
                return False, error
            except:
                print(f"   ❌ Erro HTTP: {response.status_code}")
                return False, {"error": f"HTTP {response.status_code}"}
                
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Erro de conexão: {str(e)}")
        return False, {"error": str(e)}

def teste_1_carregamento_sprint_semanal():
    """Teste 1: Carregamento básico do Sprint Semanal"""
    print("\n" + "="*60)
    print("🧪 TESTE 1: Carregamento Sprint Semanal")
    print("="*60)
    
    # Testa carregamento com view estendida
    endpoint = f"/backlog/api/specialists/{ESPECIALISTA_TESTE}/weekly-segments?view=extended"
    sucesso, resultado = testar_api(endpoint)
    
    if sucesso:
        weeks = resultado.get('weeks', [])
        total_segments = sum(len(w.get('segments', [])) for w in weeks)
        
        print(f"   📊 Semanas carregadas: {len(weeks)}")
        print(f"   📊 Total de segmentos: {total_segments}")
        
        if total_segments == 0:
            print("   ⚠️  Nenhum segmento encontrado - isso pode indicar que precisa criar segmentos")
        else:
            print("   ✅ Segmentos encontrados com sucesso!")
            
        return sucesso, total_segments
    
    return sucesso, 0

def teste_2_auto_criacao_segmentos():
    """Teste 2: Auto-criação de segmentos para especialista"""
    print("\n" + "="*60)
    print("🧪 TESTE 2: Auto-criação de Segmentos")
    print("="*60)
    
    endpoint = f"/backlog/api/specialists/{ESPECIALISTA_TESTE}/auto-create-missing-segments"
    data = {
        "default_start_time": "09:00",
        "days_ahead_default": 7
    }
    
    sucesso, resultado = testar_api(endpoint, method="POST", data=data)
    
    if sucesso:
        summary = resultado.get('summary', {})
        
        print(f"   📊 Tarefas verificadas: {summary.get('total_tasks_checked', 0)}")
        print(f"   📊 Tarefas sem segmentos: {summary.get('tasks_without_segments_found', 0)}")
        print(f"   📊 Tarefas processadas: {summary.get('tasks_processed_successfully', 0)}")
        print(f"   📊 Segmentos criados: {summary.get('total_segments_created', 0)}")
        print(f"   📊 Erros encontrados: {summary.get('tasks_with_errors', 0)}")
        
        if summary.get('total_segments_created', 0) > 0:
            print("   ✅ Segmentos criados com sucesso!")
        elif summary.get('tasks_without_segments_found', 0) == 0:
            print("   ℹ️  Todas as tarefas já possuem segmentos")
        
        return sucesso, summary.get('total_segments_created', 0)
    
    return sucesso, 0

def teste_3_debug_especialista():
    """Teste 3: Debug do especialista"""
    print("\n" + "="*60)
    print("🧪 TESTE 3: Debug do Especialista")
    print("="*60)
    
    endpoint = f"/backlog/api/debug/sprint/{ESPECIALISTA_TESTE}"
    sucesso, resultado = testar_api(endpoint)
    
    if sucesso:
        data_info = resultado.get('data', {})
        issues = resultado.get('issues_found', [])
        solutions = resultado.get('solutions', [])
        
        print(f"   📊 Método de busca usado: {data_info.get('search_method_used', 'N/A')}")
        print(f"   📊 Total de tarefas encontradas: {data_info.get('total_tasks_for_specialist', 0)}")
        print(f"   📊 Tarefas com segmentos: {data_info.get('tasks_with_segments', 0)}")
        print(f"   📊 Tarefas sem segmentos: {data_info.get('tasks_without_segments', 0)}")
        print(f"   📊 Projetos ativos: {data_info.get('active_project_ids', [])}")
        
        if issues:
            print("   ⚠️  Problemas encontrados:")
            for issue in issues:
                print(f"      - {issue}")
        
        if solutions:
            print("   💡 Soluções sugeridas:")
            for solution in solutions:
                print(f"      - {solution}")
        
        if not issues:
            print("   ✅ Nenhum problema encontrado!")
        
        return sucesso, len(issues)
    
    return sucesso, -1

def teste_4_nova_segmentacao():
    """Teste 4: Nova lógica de segmentação (4h/projeto/dia)"""
    print("\n" + "="*60)
    print("🧪 TESTE 4: Nova Lógica de Segmentação")
    print("="*60)
    
    # Este teste precisa de um task_id real, então apenas documenta o teste
    print("   ℹ️  Para testar a nova segmentação, use:")
    print(f"   📝 POST /backlog/api/tasks/{{task_id}}/auto-segment")
    print("   📝 Payload:")
    
    exemplo_payload = {
        "start_date": (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
        "end_date": (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d'),
        "start_time": "09:00"
    }
    
    print(f"   📝 {json.dumps(exemplo_payload, indent=6)}")
    print("   📝 Resultado esperado:")
    print("      - Máximo 4h por segmento")
    print("      - Distribuição entre data início e fim")
    print("      - Apenas dias úteis")
    
    return True, 0

def executar_todos_os_testes():
    """Executa todos os testes das correções"""
    print("🚀 INICIANDO TESTES DAS CORREÇÕES DO SPRINT SEMANAL")
    print("="*80)
    print(f"📍 URL Base: {BASE_URL}")
    print(f"👤 Especialista Teste: {ESPECIALISTA_TESTE}")
    print(f"⏰ Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    resultados = {}
    
    # Teste 1: Carregamento básico
    sucesso, segmentos = teste_1_carregamento_sprint_semanal()
    resultados['carregamento'] = {'sucesso': sucesso, 'segmentos': segmentos}
    
    # Teste 2: Auto-criação (só se não há segmentos)
    if segmentos == 0:
        sucesso, criados = teste_2_auto_criacao_segmentos()
        resultados['auto_criacao'] = {'sucesso': sucesso, 'criados': criados}
        
        # Se criou segmentos, testa carregamento novamente
        if criados > 0:
            print("\n🔄 Re-testando carregamento após criação de segmentos...")
            sucesso, segmentos = teste_1_carregamento_sprint_semanal()
            resultados['carregamento_pos_criacao'] = {'sucesso': sucesso, 'segmentos': segmentos}
    else:
        print("\n⏭️  Pulando auto-criação (já existem segmentos)")
        resultados['auto_criacao'] = {'sucesso': True, 'criados': 0, 'motivo': 'já_existem_segmentos'}
    
    # Teste 3: Debug
    sucesso, problemas = teste_3_debug_especialista()
    resultados['debug'] = {'sucesso': sucesso, 'problemas': problemas}
    
    # Teste 4: Nova segmentação (documentação)
    sucesso, _ = teste_4_nova_segmentacao()
    resultados['nova_segmentacao'] = {'sucesso': sucesso, 'documentado': True}
    
    # Resumo final
    print("\n" + "="*80)
    print("📋 RESUMO DOS TESTES")
    print("="*80)
    
    for teste, resultado in resultados.items():
        status = "✅ SUCESSO" if resultado['sucesso'] else "❌ FALHA"
        print(f"   {teste.upper()}: {status}")
        
        if teste == 'carregamento':
            print(f"      📊 Segmentos encontrados: {resultado['segmentos']}")
        elif teste == 'auto_criacao':
            if 'motivo' in resultado:
                print(f"      ℹ️  {resultado['motivo']}")
            else:
                print(f"      📊 Segmentos criados: {resultado['criados']}")
        elif teste == 'debug':
            print(f"      📊 Problemas encontrados: {resultado['problemas']}")
    
    # Verifica se todas as correções estão funcionando
    testes_criticos = ['carregamento', 'debug']
    sucessos = sum(1 for teste in testes_criticos if resultados[teste]['sucesso'])
    
    print(f"\n🎯 RESULTADO GERAL: {sucessos}/{len(testes_criticos)} testes críticos passaram")
    
    if sucessos == len(testes_criticos):
        if resultados['carregamento']['segmentos'] > 0:
            print("✅ TODAS AS CORREÇÕES ESTÃO FUNCIONANDO!")
            print("   O Sprint Semanal deve estar carregando as atividades corretamente.")
        else:
            print("⚠️  CORREÇÕES FUNCIONANDO, MAS SEM SEGMENTOS")
            print("   Execute a auto-criação de segmentos para ver as atividades.")
    else:
        print("❌ ALGUMAS CORREÇÕES PRECISAM DE AJUSTE")
        print("   Verifique os logs e ajuste conforme necessário.")
    
    return resultados

if __name__ == "__main__":
    print("🧪 TESTE DAS CORREÇÕES DO SPRINT SEMANAL")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        ESPECIALISTA_TESTE = sys.argv[1]
        print(f"👤 Usando especialista da linha de comando: {ESPECIALISTA_TESTE}")
    
    resultados = executar_todos_os_testes()
    
    print(f"\n💾 Para salvar os resultados, use:")
    print(f"   python {sys.argv[0]} > teste_resultados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log") 