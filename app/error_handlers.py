from flask import render_template, make_response
import pandas as pd
import logging

def handle_errors(e):
    if isinstance(e, pd.errors.EmptyDataError):
        msg = "Arquivo CSV vazio ou inválido"
    elif isinstance(e, FileNotFoundError):
        msg = "Arquivo de dados não encontrado"
    elif isinstance(e, pd.errors.ParserError):
        msg = "Formato do arquivo CSV inválido"
    else:
        msg = f"Erro inesperado: {str(e)}"

    try:
        return render_template('gerencial/erro.html', mensagem=msg)
    except:
        # Fallback caso o template não seja encontrado
        return make_response(f"""
            <h1>Erro</h1>
            <p>{msg}</p>
            <p><small>(Template de erro não encontrado)</small></p>
        """, 500)
    


