# app/macro/typeservice_reader.py
import pandas as pd
import logging
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

class TypeServiceReader:
    """
    Classe simples para ler e processar o arquivo typeservices.csv
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Caminho para o arquivo CSV
        base_dir = Path(__file__).resolve().parent.parent.parent
        data_dir = base_dir / 'data'
        self.csv_path = data_dir / 'typeservices.csv'
        
        # Cache dos dados
        self._tipos_cache = None
        self._categorias_cache = None
        
    def carregar_tipos_servico(self, force_reload=False) -> Dict[str, str]:
        """
        Carrega o mapeamento TipoServico -> Categoria do CSV
        
        Args:
            force_reload (bool): Força recarregamento ignorando cache
        
        Returns:
            Dict[str, str]: Dicionário {tipo_servico: categoria}
        """
        if self._tipos_cache is not None and not force_reload:
            self.logger.info(f"📋 Usando cache: {len(self._tipos_cache)} tipos carregados")
            return self._tipos_cache
        
        try:
            if not self.csv_path.exists():
                self.logger.error(f"❌ Arquivo não encontrado: {self.csv_path}")
                return {}
            
            self.logger.info(f"📁 Carregando CSV: {self.csv_path}")
            
            # Tenta diferentes encodings
            encodings = ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']
            df = None
            
            for encoding in encodings:
                try:
                    self.logger.info(f"🔄 Tentando encoding: {encoding}")
                    df = pd.read_csv(
                        self.csv_path,
                        sep=';',
                        encoding=encoding,
                        dtype=str
                    )
                    self.logger.info(f"✅ Sucesso com encoding: {encoding}")
                    break
                except UnicodeDecodeError:
                    self.logger.warning(f"⚠️ Falha com encoding: {encoding}")
                    continue
                except Exception as e:
                    self.logger.warning(f"⚠️ Erro com {encoding}: {str(e)}")
                    continue
            
            if df is None:
                self.logger.error("❌ Falha em todos os encodings")
                return {}
            
            # Debug das colunas
            self.logger.info(f"📊 Colunas encontradas: {list(df.columns)}")
            self.logger.info(f"📏 Total de linhas: {len(df)}")
            
            # Verifica colunas
            if 'TipoServico' not in df.columns or 'Categoria' not in df.columns:
                self.logger.error(f"❌ CSV deve ter colunas 'TipoServico' e 'Categoria'. Encontradas: {list(df.columns)}")
                return {}
            
            # Remove vazios
            inicial = len(df)
            df = df.dropna(subset=['TipoServico', 'Categoria'])
            self.logger.info(f"🧹 Removidas {inicial - len(df)} linhas vazias")
            
            # Remove linhas com strings vazias
            df = df[(df['TipoServico'].str.strip() != '') & (df['Categoria'].str.strip() != '')]
            self.logger.info(f"📋 Linhas válidas após limpeza: {len(df)}")
            
            # Debug: mostra primeiras linhas
            if len(df) > 0:
                self.logger.info("🔍 Primeiras 3 linhas:")
                for i, row in df.head(3).iterrows():
                    self.logger.info(f"  - '{row['TipoServico']}' -> '{row['Categoria']}'")
            
            # DEBUG: Procura especificamente pelos tipos problemáticos
            tipos_problema = [
                'Migração de tenant CSP para EA',
                'Assessment for Rapid Migration', 
                'Migração de workload de Cloud privada para Azure'
            ]
            
            self.logger.info("🔍 Verificando tipos problemáticos no CSV:")
            for tipo in tipos_problema:
                matches = df[df['TipoServico'].str.contains(tipo, case=False, na=False)]
                if not matches.empty:
                    for _, row in matches.iterrows():
                        self.logger.info(f"  ✅ ENCONTRADO: '{row['TipoServico']}' -> '{row['Categoria']}'")
                else:
                    self.logger.warning(f"  ❌ NÃO ENCONTRADO: '{tipo}'")
            
            # Cria mapeamento
            mapeamento = df.set_index('TipoServico')['Categoria'].to_dict()
            
            # DEBUG: Verifica se os tipos problemáticos estão no mapeamento final
            self.logger.info("🔍 Verificando tipos problemáticos no mapeamento final:")
            for tipo in tipos_problema:
                if tipo in mapeamento:
                    self.logger.info(f"  ✅ MAPEADO: '{tipo}' -> '{mapeamento[tipo]}'")
                else:
                    self.logger.warning(f"  ❌ NÃO MAPEADO: '{tipo}'")
                    # Procura por match parcial
                    matches = [k for k in mapeamento.keys() if tipo.lower() in k.lower() or k.lower() in tipo.lower()]
                    if matches:
                        self.logger.info(f"    🔍 Matches parciais encontrados: {matches[:3]}")
            
            # Limpa cache anterior
            self._tipos_cache = None
            self._categorias_cache = None
            
            self._tipos_cache = mapeamento
            self.logger.info(f"✅ Carregados {len(mapeamento)} tipos de serviço do CSV")
            
            return mapeamento
            
        except Exception as e:
            self.logger.error(f"Erro ao carregar CSV: {str(e)}")
            return {}
    
    def obter_categoria(self, tipo_servico: str) -> str:
        """
        Retorna a categoria de um tipo de serviço
        
        Args:
            tipo_servico (str): Nome do tipo de serviço
            
        Returns:
            str: Categoria ou 'Outros' se não encontrado
        """
        tipos = self.carregar_tipos_servico()
        return tipos.get(tipo_servico, 'Outros')
    
    def obter_categorias_disponiveis(self) -> List[str]:
        """
        Retorna lista de todas as categorias disponíveis
        
        Returns:
            List[str]: Lista de categorias únicas
        """
        if self._categorias_cache is not None:
            return self._categorias_cache
        
        tipos = self.carregar_tipos_servico()
        categorias = sorted(set(tipos.values()))
        
        self._categorias_cache = categorias
        return categorias
    
    def obter_tipos_por_categoria(self) -> Dict[str, List[str]]:
        """
        Retorna dicionário organizando tipos por categoria
        
        Returns:
            Dict[str, List[str]]: {categoria: [lista_de_tipos]}
        """
        tipos = self.carregar_tipos_servico()
        
        categorias_dict = {}
        for tipo, categoria in tipos.items():
            if categoria not in categorias_dict:
                categorias_dict[categoria] = []
            categorias_dict[categoria].append(tipo)
        
        # Ordena tipos dentro de cada categoria
        for categoria in categorias_dict:
            categorias_dict[categoria].sort()
        
        return categorias_dict
    
    def contar_tipos_por_categoria(self) -> Dict[str, int]:
        """
        Conta quantos tipos há em cada categoria
        
        Returns:
            Dict[str, int]: {categoria: count}
        """
        tipos_por_categoria = self.obter_tipos_por_categoria()
        return {categoria: len(tipos) for categoria, tipos in tipos_por_categoria.items()}
    
    def limpar_cache(self):
        """Limpa o cache forçando reload na próxima consulta"""
        self._tipos_cache = None
        self._categorias_cache = None
        self.logger.info("🔄 Cache limpo - próxima consulta irá recarregar CSV")
    
    def recarregar_csv(self) -> Dict[str, str]:
        """Força recarregamento do CSV ignorando cache"""
        self.logger.info("🔄 Forçando recarregamento do CSV...")
        return self.carregar_tipos_servico(force_reload=True)
    
    def validar_arquivo(self) -> Tuple[bool, str]:
        """
        Valida se o arquivo CSV está correto
        
        Returns:
            Tuple[bool, str]: (valido, mensagem)
        """
        try:
            if not self.csv_path.exists():
                return False, f"Arquivo não encontrado: {self.csv_path}"
            
            df = pd.read_csv(self.csv_path, sep=';', encoding='latin1', nrows=5)
            
            if 'TipoServico' not in df.columns:
                return False, "Coluna 'TipoServico' não encontrada"
            
            if 'Categoria' not in df.columns:
                return False, "Coluna 'Categoria' não encontrada"
            
            tipos = self.carregar_tipos_servico()
            if len(tipos) == 0:
                return False, "Nenhum tipo de serviço válido encontrado"
            
            return True, f"✅ Arquivo válido com {len(tipos)} tipos de serviço"
            
        except Exception as e:
            return False, f"Erro na validação: {str(e)}"

# Instância global
type_service_reader = TypeServiceReader() 