# Status dos projetos
STATUS_NAO_ATIVOS = ['FECHADO', 'ENCERRADO', 'RESOLVIDO', 'CANCELADO']
STATUS_EM_ANDAMENTO = ['NOVO', 'AGUARDANDO', 'BLOQUEADO', 'EM ATENDIMENTO']
STATUS_ATRASADO = ['ATRASADO']
STATUS_ATIVO = ['ATIVO']

# Constantes para cálculos
DIAS_POR_MES = 30
HORAS_POR_DIA = 8
DIAS_POR_SEMANA = 5

# Limites para alertas
LIMITE_HORAS_NEGATIVAS = 0
LIMITE_ATRASO_DIAS = 7
LIMITE_CONCLUSAO_MINIMA = 30

# Cores para visualização
CORES_STATUS = {
    'NOVO': 'info',
    'EM ATENDIMENTO': 'primary',
    'AGUARDANDO': 'warning',
    'ENCERRADO': 'success',
    'RESOLVIDO': 'success',
    'FECHADO': 'success',
    'BLOQUEADO': 'dark',
    'ATRASADO': 'warning',
    'CANCELADO': 'danger'
}

# Cores para conclusão
CORES_CONCLUSAO = {
    'success': 90,  # Verde
    'info': 70,     # Azul
    'warning': 50,  # Amarelo
    'danger': 0     # Vermelho
}

# Colunas obrigatórias
COLUNAS_OBRIGATORIAS = ['Projeto', 'Status', 'Squad', 'Faturamento', 'HorasTrabalhadas']
COLUNAS_NUMERICAS = ['Horas', 'HorasRestantes', 'Conclusao', 'HorasTrabalhadas']
COLUNAS_TEXTO = ['Squad', 'Status', 'Faturamento', 'Especialista', 'Account Manager'] 