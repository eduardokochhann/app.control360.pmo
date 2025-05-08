#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script simplificado para modificar o template status_report.html
"""

def main():
    # Constantes
    file_path = 'templates/macro/status_report.html'
    search_text = '<div class="card shadow h-100">'
    marker_text = '<h6 class="section-title mb-0 text-center">Marcos Recentes</h6>'
    
    # Novo conteúdo para o card de Marcos Recentes
    new_content = '''<div class="placeholder-section">
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
            </div>'''
    
    # Ler o arquivo
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.readlines()
    
    # Encontrar a linha com o marcador do card de Marcos Recentes
    marker_line_index = -1
    for i, line in enumerate(content):
        if marker_text in line:
            # Verificar se temos um card antes desse marcador
            for j in range(i-10, i):
                if j >= 0 and search_text in content[j]:
                    marker_line_index = j
                    break
            if marker_line_index != -1:
                break
    
    if marker_line_index == -1:
        print("Não foi possível encontrar o card de Marcos Recentes.")
        return
    
    # Encontrar o início do card (div com classe col-md-4)
    col_start_index = -1
    for i in range(marker_line_index-10, marker_line_index):
        if i >= 0 and '<div class="col-md-4">' in content[i]:
            col_start_index = i
            break
    
    if col_start_index == -1:
        print("Não foi possível encontrar o início do card de Marcos Recentes.")
        return
    
    # Encontrar o fim do card (fechamento do div col-md-4)
    card_end_index = -1
    depth = 0
    for i in range(col_start_index, len(content)):
        line = content[i]
        # Conta divs abertos
        depth += line.count('<div')
        # Conta divs fechados
        depth -= line.count('</div')
        
        # Quando depth volta a 0, encontramos o fim do col-md-4
        if depth <= 0:
            card_end_index = i
            break
    
    if card_end_index == -1:
        print("Não foi possível encontrar o fim do card de Marcos Recentes.")
        return
    
    # Construir novo conteúdo
    new_lines = content[:col_start_index]
    new_lines.append('        <div class="col-md-4">\n')
    new_lines.append('            ' + new_content + '\n')
    new_lines.append('        </div>\n')
    new_lines.extend(content[card_end_index+1:])
    
    # Salvar o arquivo
    with open(file_path, 'w', encoding='utf-8') as file:
        file.writelines(new_lines)
    
    print(f"Template atualizado com sucesso! Modificado de linha {col_start_index} a {card_end_index}.")

if __name__ == "__main__":
    main() 