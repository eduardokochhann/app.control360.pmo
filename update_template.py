#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para modificar o template status_report.html e padronizar 
o estilo visual do card de Marcos Recentes.
"""

import os
import re

def main():
    file_path = 'templates/macro/status_report.html'
    
    # Verifica se o arquivo existe
    if not os.path.exists(file_path):
        print(f"Arquivo não encontrado: {file_path}")
        return
    
    # Lê o conteúdo do arquivo
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Define o padrão a ser substituído (card dos Marcos Recentes)
    old_pattern = r'<div class="col-md-4">\s*<div class="card shadow h-100">\s*<div class="card-header bg-light">\s*<h6 class="section-title mb-0 text-center">Marcos Recentes</h6>\s*</div>\s*<div class="card-body p-0">[^<]*(?:<[^>]*>[^<]*)*?</div>\s*</div>\s*</div>'
    
    # Define o novo conteúdo (estilo placeholder-section)
    new_content = '''<div class="col-md-4">
            <div class="placeholder-section">
                <i class="bi bi-calendar-check"></i>
                <h6 class="section-title text-center">Marcos Recentes</h6>
                {% if report_data and report_data.marcos_recentes and report_data.marcos_recentes|length > 0 %}
                    <div class="table-responsive">
                        <table class="table table-sm table-borderless">
                            <tbody>
                                {% for marco in report_data.marcos_recentes %}
                                    <tr>
                                        <td class="text-start ps-0" style="width: 65%;">
                                            {% if marco.atrasado %}<span class="badge bg-danger me-1">!</span>{% endif %}
                                            <small><strong>{{ marco.nome }}</strong></small>
                                        </td>
                                        <td class="text-muted" style="width: 20%;"><small>{{ marco.data_planejada }}</small></td>
                                        <td class="text-end pe-0" style="width: 15%;">
                                            <span class="badge {% if marco.status == 'COMPLETED' or marco.status == 'CONCLUÍDO' %}bg-success{% elif marco.status == 'IN_PROGRESS' or marco.status == 'EM ANDAMENTO' %}bg-warning text-dark{% elif marco.status == 'DELAYED' or marco.status == 'ATRASADO' %}bg-danger{% else %}bg-secondary{% endif %}" style="font-size: 0.7em;">
                                                {% if marco.status == 'COMPLETED' or marco.status == 'CONCLUÍDO' %}Concl.
                                                {% elif marco.status == 'IN_PROGRESS' or marco.status == 'EM ANDAMENTO' %}Em And.
                                                {% elif marco.status == 'DELAYED' or marco.status == 'ATRASADO' %}Atras.
                                                {% else %}Pend.{% endif %}
                                            </span>
                                        </td>
                                    </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                {% else %}
                    <p class="text-muted" style="font-size: 0.85rem;">Nenhum marco definido para este projeto.</p>
                {% endif %}
            </div>
        </div>'''
    
    # Substitui o padrão pelo novo conteúdo
    modified_content = re.sub(old_pattern, new_content, content, flags=re.DOTALL)
    
    # Se o conteúdo for modificado, salva o arquivo
    if modified_content != content:
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(modified_content)
        print(f"Template atualizado com sucesso: {file_path}")
    else:
        print("Não foi possível encontrar o padrão para substituir no template.")

if __name__ == "__main__":
    main() 