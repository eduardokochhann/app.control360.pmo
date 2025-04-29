from enum import Enum

class Status(Enum):
    FECHADO = 'FECHADO'
    ENCERRADO = 'ENCERRADO'
    RESOLVIDO = 'RESOLVIDO'
    CANCELADO = 'CANCELADO'
    NOVO = 'NOVO'
    AGUARDANDO = 'AGUARDANDO'
    BLOQUEADO = 'BLOQUEADO'
    EM_ATENDIMENTO = 'EM ATENDIMENTO'
    ATRASADO = 'ATRASADO'
    ATIVO = 'ATIVO'

class TipoFaturamento(Enum):
    PRIME = 'PRIME'
    PLUS = 'PLUS'
    INICIO = 'INICIO'
    TERMINO = 'TERMINO'
    FEOP = 'FEOP'
    ENGAJAMENTO = 'ENGAJAMENTO'

# Grupos de status
STATUS_NAO_ATIVOS = [Status.FECHADO, Status.ENCERRADO, Status.RESOLVIDO, Status.CANCELADO]
STATUS_EM_ANDAMENTO = [Status.NOVO, Status.AGUARDANDO, Status.BLOQUEADO, Status.EM_ATENDIMENTO]
STATUS_ATRASADO = [Status.ATRASADO]
STATUS_ATIVO = [Status.ATIVO]

# Colunas obrigatórias
COLUNAS_OBRIGATORIAS = ['Projeto', 'Status', 'Squad', 'Faturamento', 'HorasTrabalhadas']
COLUNAS_NUMERICAS = ['Horas', 'HorasRestantes', 'Conclusao', 'HorasTrabalhadas']
COLUNAS_TEXTO = ['Squad', 'Status', 'Faturamento', 'Especialista', 'Account Manager']

# Configurações
HORAS_POR_PESSOA = 180  # horas/mês
PESSOAS_POR_SQUAD = 3   # pessoas por squad
CAPACIDADE_TOTAL = HORAS_POR_PESSOA * PESSOAS_POR_SQUAD  # 540 horas por squad 