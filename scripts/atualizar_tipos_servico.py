#!/usr/bin/env python3
"""
Script para atualizar configurações de tipos de serviço

Uso:
    python scripts/atualizar_tipos_servico.py --add-tipo "Novo Tipo" --categoria "azure_infrastructure"
    python scripts/atualizar_tipos_servico.py --list-categorias
    python scripts/atualizar_tipos_servico.py --list-tipos
"""

import sys
import json
import argparse
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.append(str(Path(__file__).parent.parent))

from app.macro.config_service import tipos_servico_config

def listar_categorias():
    """Lista todas as categorias disponíveis"""
    print("📋 Categorias disponíveis:")
    print("-" * 50)
    
    categorias = tipos_servico_config.obter_categorias()
    
    for key, info in categorias.items():
        print(f"🔹 {key}")
        print(f"   Nome: {info['nome']}")
        print(f"   Cor: {info['cor']}")
        print(f"   Ícone: {info['icone']}")
        print(f"   Tipos: {len(info.get('tipos', []))}")
        print()

def listar_tipos():
    """Lista todos os tipos de serviço organizados por categoria"""
    print("📊 Tipos de serviço por categoria:")
    print("-" * 50)
    
    categorias = tipos_servico_config.obter_categorias()
    
    for key, info in categorias.items():
        print(f"\n🏷️  {info['nome']} ({key})")
        tipos = info.get('tipos', [])
        
        if tipos:
            for i, tipo in enumerate(tipos, 1):
                print(f"   {i:2d}. {tipo}")
        else:
            print("   (nenhum tipo cadastrado)")

def adicionar_tipo(nome_tipo, categoria_key):
    """Adiciona um novo tipo de serviço a uma categoria"""
    try:
        config = tipos_servico_config.carregar_configuracao()
        
        if categoria_key not in config['categorias']:
            print(f"❌ Categoria '{categoria_key}' não encontrada!")
            print("Use --list-categorias para ver as categorias disponíveis")
            return False
        
        # Verifica se o tipo já existe
        for cat_key, cat_info in config['categorias'].items():
            if nome_tipo in cat_info.get('tipos', []):
                print(f"⚠️  Tipo '{nome_tipo}' já existe na categoria '{cat_key}'")
                return False
        
        # Adiciona o tipo
        if 'tipos' not in config['categorias'][categoria_key]:
            config['categorias'][categoria_key]['tipos'] = []
        
        config['categorias'][categoria_key]['tipos'].append(nome_tipo)
        
        # Salva a configuração
        if tipos_servico_config.salvar_configuracao(config):
            print(f"✅ Tipo '{nome_tipo}' adicionado à categoria '{categoria_key}' com sucesso!")
            return True
        else:
            print("❌ Erro ao salvar configuração")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        return False

def remover_tipo(nome_tipo):
    """Remove um tipo de serviço"""
    try:
        config = tipos_servico_config.carregar_configuracao()
        removido = False
        
        for cat_key, cat_info in config['categorias'].items():
            tipos = cat_info.get('tipos', [])
            if nome_tipo in tipos:
                tipos.remove(nome_tipo)
                cat_info['tipos'] = tipos
                removido = True
                print(f"🗑️  Tipo '{nome_tipo}' removido da categoria '{cat_key}'")
                break
        
        if not removido:
            print(f"⚠️  Tipo '{nome_tipo}' não encontrado")
            return False
        
        # Salva a configuração
        if tipos_servico_config.salvar_configuracao(config):
            print("✅ Configuração salva com sucesso!")
            return True
        else:
            print("❌ Erro ao salvar configuração")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        return False

def criar_categoria(key, nome, cor="#6c757d", icone="bi-gear", descricao=""):
    """Cria uma nova categoria"""
    try:
        config = tipos_servico_config.carregar_configuracao()
        
        if key in config['categorias']:
            print(f"⚠️  Categoria '{key}' já existe!")
            return False
        
        config['categorias'][key] = {
            'nome': nome,
            'cor': cor,
            'icone': icone,
            'descricao': descricao,
            'tipos': []
        }
        
        if tipos_servico_config.salvar_configuracao(config):
            print(f"✅ Categoria '{nome}' ({key}) criada com sucesso!")
            return True
        else:
            print("❌ Erro ao salvar configuração")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        return False

def exportar_config(arquivo_saida):
    """Exporta configuração atual para arquivo"""
    try:
        config = tipos_servico_config.carregar_configuracao()
        
        with open(arquivo_saida, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        print(f"📁 Configuração exportada para: {arquivo_saida}")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao exportar: {str(e)}")
        return False

def importar_config(arquivo_entrada):
    """Importa configuração de arquivo"""
    try:
        with open(arquivo_entrada, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        if tipos_servico_config.salvar_configuracao(config):
            print(f"📥 Configuração importada de: {arquivo_entrada}")
            return True
        else:
            print("❌ Erro ao salvar configuração importada")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao importar: {str(e)}")
        return False

def main():
    print("🔧 Script de Configuração de Tipos de Serviço")
    print("=" * 50)
    print()
    print("📋 Para editar as configurações:")
    print("   1. Edite o arquivo: config/tipos_servico_config.json")
    print("   2. Reinicie o servidor Flask")
    print("   3. As mudanças serão aplicadas automaticamente")
    print()
    print("🚀 Recursos disponíveis:")
    print("   • Categorias personalizadas com cores e ícones")
    print("   • Classificação automática de complexidade")
    print("   • Interface visual organizada por categoria")
    print("   • Rankings e análises configuráveis")

if __name__ == '__main__':
    main() 