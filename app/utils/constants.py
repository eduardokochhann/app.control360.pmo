# Status dos projetos
STATUS_ATIVO = 'ATIVO'
STATUS_CRITICO = 'CRITICO'
STATUS_CONCLUIDO = 'CONCLUIDO'
STATUS_ATENDIMENTO = 'EM ATENDIMENTO'

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
    'CANCELADO': 'danger',
    'CRITICO': 'danger',
    'CONCLUIDO': 'success'
}

# Cores para conclusão
CORES_CONCLUSAO = {
    'success': 90,  # Verde
    'info': 70,     # Azul
    'warning': 50,  # Amarelo
    'danger': 0     # Vermelho
}

# Colunas obrigatórias (usando os nomes do CSV)
COLUNAS_OBRIGATORIAS = ['Cliente (Completo)', 'Status', 'Serviço (2º Nível)', 'Tipo de faturamento', 'Tempo trabalhado']

# Colunas opcionais (novas estruturas de dados)
COLUNAS_OPCIONAIS = ['Assunto', 'Serviço (3º Nível)']

# Colunas para conversão numérica
COLUNAS_NUMERICAS = ['Esforço estimado', 'Tempo trabalhado', 'Andamento']

# Colunas de texto
COLUNAS_TEXTO = ['Serviço (2º Nível)', 'Status', 'Tipo de faturamento', 'Responsável', 'Account Manager'] 