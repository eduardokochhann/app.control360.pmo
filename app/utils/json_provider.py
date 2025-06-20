# app/utils/json_provider.py
import numpy as np
import pandas as pd
from datetime import date, datetime
from flask.json.provider import JSONProvider
# Remova a importação de flask_dumps e flask_loads se não for usar loads customizado
# from flask.json import dumps as flask_dumps
# from flask.json import loads as flask_loads
import json # Importa a biblioteca JSON padrão do Python
import logging
import enum  # Importa módulo enum para suporte a enums

logger = logging.getLogger(__name__)

class NumpyJSONProvider(JSONProvider):
    """
    JSONProvider customizado para lidar com tipos NumPy/Pandas e Enums,
    corrigido para usar json.dumps diretamente e evitar recursão.
    """
    def default(self, o):
        """
        Converte tipos específicos não serializáveis para tipos Python nativos.
        Se um tipo não for reconhecido aqui, permite que json.dumps levante TypeError.
        """
        if isinstance(o, (np.integer, np.int64)):
            return int(o)
        elif isinstance(o, (np.floating, np.float64)):
            return None if np.isnan(o) else float(o)
        elif isinstance(o, np.bool_):
            return bool(o)
        elif isinstance(o, np.ndarray):
            return o.tolist()
        elif isinstance(o, (datetime, date, pd.Timestamp)):
             return None if pd.isna(o) else o.isoformat()
        elif pd.isna(o):
             # logger.warning(f"Valor genérico pd.isna() encontrado: {type(o)}. Convertendo para None.")
             return None
        elif isinstance(o, enum.Enum):
             # Serializa enums usando seu nome (ou value se preferir)
             return o.name  # ou o.value se quiser o valor em vez do nome

        # Se não foi tratado, deixa o json.dumps padrão levantar TypeError
        # Não precisamos levantar explicitamente aqui, o json.dumps fará isso.
        # A linha abaixo foi removida:
        # raise TypeError(f"Objeto do tipo {type(o).__name__} não é serializável pelo NumpyJSONProvider.default")
        # Em vez disso, chamamos o default da classe base do *encoder* padrão do json
        try:
            return json.JSONEncoder.default(self, o)
        except TypeError:
             logger.error(f"Tipo não serializável não tratado pelo default: {type(o).__name__}", exc_info=False)
             # Retornar None é mais seguro para a estrutura JSON
             return None


    def dumps(self, obj, **kwargs):
        """
        Serializa um objeto Python para uma string JSON usando json.dumps (padrão Python),
        fornecendo nosso método 'default' e tratando erros.
        """
        # Garante que nosso 'default' seja usado e define outras opções
        kwargs['default'] = self.default
        kwargs.setdefault('ensure_ascii', False)
        # kwargs.setdefault('indent', 2) # Para debug
        kwargs.setdefault('sort_keys', True)

        try:
            # *** CHAMA json.dumps DIRETAMENTE ***
            # Isso evita a delegação recursiva do flask_dumps
            return json.dumps(obj, **kwargs)
        except TypeError as e:
            # Loga o erro se a serialização falhar mesmo após nosso 'default'
            logger.error(f"Erro final de serialização JSON (TypeError): {e}. Objeto raiz (tipo): {type(obj)}", exc_info=True)
            raise # Re-levanta para Flask tratar
        except RecursionError as e:
             # Este bloco agora só deve ser atingido se houver um objeto *realmente* circular
             # nos seus dados, não por causa da chamada de serialização em si.
             logger.critical(f"RecursionError durante a serialização JSON! Verifique objetos circulares nos dados. {e}", exc_info=True)
             raise # Re-levanta para Flask tratar

    def loads(self, s, **kwargs):
        """
        Deserializa uma string JSON para um objeto Python usando json.loads.
        """
        # Usa json.loads padrão. Se precisar do flask_loads por algum motivo, importe-o.
        return json.loads(s, **kwargs)

