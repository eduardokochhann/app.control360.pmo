import pandas as pd
from datetime import datetime
import logging
from app.macro.services import MacroService

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    service = MacroService()
    
    # Lista dos números dos projetos que devem ser contados
    projetos_corretos = [
        11157,  # CAMPOS MELLO ADVOGADOS - M365
        11031,  # SUPLEY - Data e Power
        10878,  # SANTACLARA - M365
        10879,  # SANTACLARA - M365
        10663,  # BILD - M365
        10665,  # Cerradinho - M365
        10666,  # Cerradinho - M365
        10870,  # GNG Fundações - M365
        11052,  # PRO - LINHAS - Azure
        10973,  # FOSNOR - GALVANI - Azure
        10869,  # SR EMBALAGENS - Azure
        10764,  # IPM SISTEMAS - Azure
        10695,  # TRIUNFO - Azure
        11000,  # CAIXA RESIDENCIAL - M365
        11013,  # CAIXA RESIDENCIAL - M365
        11014,  # TENDA ATACADO - M365
        10927,  # IAUDIT - M365
        10946,  # BILD - M365
        10787,  # APPAI - M365
        10775,  # FSA SOLUCOES - Azure
        10651,  # Droga Fonte - M365
        10726   # TENDA ATACADO - Azure
    ]
    
    # Carregar dados
    dados = service.carregar_dados()
    logger.info(f"Total de registros carregados: {len(dados)}")
    
    # Converter datas
    dados['DataInicio'] = pd.to_datetime(dados['DataInicio'], errors='coerce')
    dados['DataTermino'] = pd.to_datetime(dados['DataTermino'], errors='coerce')
    
    # Filtrar apenas os projetos que devem ser contados
    projetos_marco = dados[dados['Numero'].isin(projetos_corretos)].copy()
    
    # Análise dos projetos
    logger.info("\n=== Projetos Novos em Março 2025 (Lista Correta) ===")
    logger.info(f"Total de projetos novos: {len(projetos_marco)}")
    
    # Contagem por Squad
    logger.info("\nContagem por Squad:")
    contagem_squad = projetos_marco['Squad'].value_counts()
    for squad, count in contagem_squad.items():
        logger.info(f"{squad}: {count}")
    
    # Detalhes dos projetos
    logger.info("\nDetalhes dos projetos encontrados vs esperados:")
    for numero in projetos_corretos:
        projeto = projetos_marco[projetos_marco['Numero'] == numero]
        if not projeto.empty:
            projeto = projeto.iloc[0]
            logger.info("---")
            logger.info(f"Número: {numero}")
            logger.info(f"Nome: {projeto.get('Projeto', 'N/A')}")
            logger.info(f"Squad: {projeto.get('Squad', 'N/A')}")
            logger.info(f"Data Início: {projeto.get('DataInicio', 'N/A')}")
            logger.info(f"Status: {projeto.get('Status', 'N/A')}")
        else:
            logger.warning(f"Projeto {numero} não encontrado nos dados!")
    
    # Verificar se os números batem com o que está sendo mostrado na interface
    logger.info("\n=== Verificação com Interface ===")
    squad_mapping = {
        'AZURE': ['AZURE', 'Azure', 'azure'],
        'M365': ['M365', 'M365', 'm365'],
        'DATA E POWER': ['DATA E POWER', 'Data e Power', 'Data & Power', 'data e power', 'data & power'],
        'CDB': ['CDB', 'Cdb', 'cdb']
    }
    
    contagem_normalizada = {
        'Azure': 0,
        'M365': 0,
        'Data&Power': 0,
        'CDB': 0
    }
    
    for _, projeto in projetos_marco.iterrows():
        squad_original = str(projeto['Squad']).strip()
        for squad_padrao, variacoes in squad_mapping.items():
            if any(squad_original.upper() == v.upper() for v in variacoes):
                if squad_padrao == 'AZURE':
                    contagem_normalizada['Azure'] += 1
                elif squad_padrao == 'M365':
                    contagem_normalizada['M365'] += 1
                elif squad_padrao == 'DATA E POWER':
                    contagem_normalizada['Data&Power'] += 1
                elif squad_padrao == 'CDB':
                    contagem_normalizada['CDB'] += 1
                break
    
    logger.info("\nContagem Normalizada (como deveria estar na interface):")
    logger.info(f"Azure: {contagem_normalizada['Azure']}")
    logger.info(f"M365: {contagem_normalizada['M365']}")
    logger.info(f"Data&Power: {contagem_normalizada['Data&Power']}")
    logger.info(f"CDB: {contagem_normalizada['CDB']}")
    logger.info(f"Total: {sum(contagem_normalizada.values())}")

if __name__ == "__main__":
    main() 