"""
Serviços administrativos para gerenciamento de configurações do sistema
"""

from flask import current_app
from .. import db
from ..models import ComplexityCriteria, ComplexityCriteriaOption, ComplexityThreshold, ComplexityCategory
from datetime import datetime
import json
import pandas as pd
import os
import shutil
from pathlib import Path
import csv
import re
import logging
# import chardet  # Temporariamente comentado
from io import StringIO
import pytz

# Define o fuso horário brasileiro
br_timezone = pytz.timezone('America/Sao_Paulo')

class AdminService:
    """Serviço principal para operações administrativas"""
    
    @staticmethod
    def get_system_stats():
        """Retorna estatísticas do sistema"""
        try:
            stats = {
                'complexity': {
                    'criteria_count': ComplexityCriteria.query.filter_by(is_active=True).count(),
                    'options_count': ComplexityCriteriaOption.query.filter_by(is_active=True).count(),
                    'thresholds_count': ComplexityThreshold.query.count(),
                    'last_modified': datetime.now(br_timezone)
                },
                'system': {
                    'version': '1.0.0',
                    'modules': ['admin', 'backlog', 'macro', 'micro', 'gerencial', 'sprints'],
                    'uptime': datetime.now(br_timezone)
                }
            }
            return stats
            
        except Exception as e:
            current_app.logger.error(f"Erro ao obter estatísticas do sistema: {e}")
            return None
    
    @staticmethod
    def validate_threshold_data(threshold_data):
        """Valida dados de threshold antes de salvar"""
        errors = []
        
        for i, threshold in enumerate(threshold_data):
            if not isinstance(threshold.get('min_score'), int) or threshold['min_score'] < 0:
                errors.append(f"Threshold {i+1}: Score mínimo deve ser um número inteiro positivo")
            
            max_score = threshold.get('max_score')
            if max_score is not None and (not isinstance(max_score, int) or max_score <= threshold['min_score']):
                errors.append(f"Threshold {i+1}: Score máximo deve ser maior que o mínimo")
        
        # Verifica sobreposições
        sorted_thresholds = sorted(threshold_data, key=lambda x: x['min_score'])
        for i in range(len(sorted_thresholds) - 1):
            current = sorted_thresholds[i]
            next_threshold = sorted_thresholds[i + 1]
            
            if current.get('max_score') and current['max_score'] >= next_threshold['min_score']:
                errors.append(f"Sobreposição entre thresholds: {current['category']} e {next_threshold['category']}")
        
        return errors
    
    @staticmethod
    def backup_complexity_config():
        """Cria backup das configurações de complexidade"""
        try:
            criteria = ComplexityCriteria.query.all()
            options = ComplexityCriteriaOption.query.all()
            thresholds = ComplexityThreshold.query.all()
            
            backup = {
                'timestamp': datetime.now(br_timezone).isoformat(),
                'version': '1.0',
                'complexity_config': {
                    'criteria': [
                        {
                            'id': c.id,
                            'name': c.name,
                            'description': c.description,
                            'is_active': c.is_active,
                            'order': c.criteria_order
                        } for c in criteria
                    ],
                    'options': [
                        {
                            'id': o.id,
                            'criteria_id': o.criteria_id,
                            'label': o.option_label or o.option_name,
                            'description': o.description,
                            'points': o.points,
                            'order': o.option_order,
                            'is_active': o.is_active
                        } for o in options
                    ],
                    'thresholds': [
                        {
                            'id': t.id,
                            'category': t.category.name,
                            'min_score': t.min_score,
                            'max_score': t.max_score
                        } for t in thresholds
                    ]
                }
            }
            
            return backup
            
        except Exception as e:
            current_app.logger.error(f"Erro ao criar backup: {e}")
            return None
    
    @staticmethod
    def restore_complexity_config(backup_data):
        """Restaura configurações de complexidade a partir do backup"""
        try:
            if not backup_data or 'complexity_config' not in backup_data:
                return False, "Dados de backup inválidos"
            
            config = backup_data['complexity_config']
            
            # Restaura thresholds
            for threshold_data in config.get('thresholds', []):
                threshold = ComplexityThreshold.query.get(threshold_data['id'])
                if threshold:
                    threshold.min_score = threshold_data['min_score']
                    threshold.max_score = threshold_data.get('max_score')
            
            # Restaura opções
            for option_data in config.get('options', []):
                option = ComplexityCriteriaOption.query.get(option_data['id'])
                if option:
                    option.option_label = option_data['label']
                    option.option_name = option_data['label']
                    option.description = option_data.get('description')
                    option.points = option_data['points']
                    option.option_order = option_data['order']
                    option.is_active = option_data['is_active']
            
            # Restaura critérios
            for criteria_data in config.get('criteria', []):
                criterion = ComplexityCriteria.query.get(criteria_data['id'])
                if criterion:
                    criterion.name = criteria_data['name']
                    criterion.description = criteria_data.get('description')
                    criterion.criteria_order = criteria_data['order']
                    criterion.is_active = criteria_data['is_active']
            
            db.session.commit()
            return True, "Configurações restauradas com sucesso"
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao restaurar backup: {e}")
            return False, f"Erro ao restaurar: {str(e)}"
    
    @staticmethod
    def get_data_statistics():
        """Retorna estatísticas dos dados atuais"""
        try:
            csv_path = Path("data/dadosr.csv")
            
            if not csv_path.exists():
                return {
                    'total_records': 0,
                    'file_size': 0,
                    'last_modified': None,
                    'columns': []
                }
            
            # Tenta diferentes encodings para ler o CSV (CP1252 primeiro - arquivo atual)
            df = None
            encodings = ['cp1252', 'utf-8', 'latin1', 'iso-8859-1']
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(csv_path, sep=';', encoding=encoding)
                    print(f"Estatísticas carregadas com encoding: {encoding}")
                    break
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    print(f"Erro com encoding {encoding}: {str(e)}")
                    continue
            
            if df is None:
                return {
                    'total_records': 0,
                    'file_size': csv_path.stat().st_size,
                    'last_modified': datetime.fromtimestamp(csv_path.stat().st_mtime).isoformat(),
                    'columns': [],
                    'error': 'Não foi possível ler o arquivo CSV'
                }
            
            # Estatísticas básicas
            stats = {
                'total_records': len(df),
                'file_size': csv_path.stat().st_size,
                'last_modified': datetime.fromtimestamp(csv_path.stat().st_mtime).isoformat(),
                'columns': list(df.columns),
                'status_distribution': df['Status'].value_counts().to_dict() if 'Status' in df.columns else {},
                'service_distribution': df['Serviço (2º Nível)'].value_counts().head(10).to_dict() if 'Serviço (2º Nível)' in df.columns else {}
            }
            
            return stats
            
        except Exception as e:
            print(f"Erro ao obter estatísticas: {str(e)}")
            return {
                'total_records': 0,
                'file_size': 0,
                'last_modified': None,
                'columns': [],
                'error': str(e)
            }
    
    @staticmethod
    def detect_file_info(file_path):
        """Detecta informações do arquivo CSV: encoding, separador e encoding válido"""
        encodings = ['cp1252', 'utf-8', 'latin1', 'iso-8859-1', 'utf-16']
        separators = [';', ',', '\t', '|']
        
        # Detectar encoding usando chardet (temporariamente comentado)
        # with open(file_path, 'rb') as f:
        #     raw_data = f.read()
        #     detected = chardet.detect(raw_data)
        #     detected_encoding = detected.get('encoding', 'utf-8')
        #     if detected_encoding not in encodings:
        #         encodings.insert(0, detected_encoding)
        
        # Testar diferentes combinações de encoding e separador
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    first_line = f.readline()
                    second_line = f.readline()
                
                # Testar separadores
                for sep in separators:
                    if first_line.count(sep) >= 5:  # Assumindo pelo menos 6 colunas
                        columns = first_line.strip().split(sep)
                        if len(columns) >= 6:
                            return encoding, sep, len(columns)
                            
            except (UnicodeDecodeError, Exception):
                continue
        
        # Fallback: latin1 com ';' (padrão ITSM brasileiro)
        return 'latin1', ';', 0

    @staticmethod
    def process_csv_upload(file_path, backup_dir='data/backups'):
        """Processa upload de CSV com correções automáticas"""
        
        try:
            # Detectar encoding e separador
            encoding, separator, num_columns = AdminService.detect_file_info(file_path)
            logging.info(f"Arquivo detectado: encoding={encoding}, separador='{separator}', colunas={num_columns}")
            
            # Ler o arquivo CSV
            df = pd.read_csv(file_path, encoding=encoding, sep=separator, low_memory=False)
            logging.info(f"CSV carregado: {len(df)} registros, {len(df.columns)} colunas")
            
            # Log das colunas originais
            logging.info(f"Colunas originais: {list(df.columns)}")
            
            # Aplicar correções automáticas
            df = AdminService.apply_automatic_corrections(df)
            
            # Validar estrutura flexível
            validation_result = AdminService.validate_structure_flexible(df)
            if not validation_result['valid']:
                logging.warning(f"Validação falhou: {validation_result['message']}")
                # Continuar mesmo com validação falhando para permitir análise
            
            # Criar backup automático
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            timestamp = datetime.now(br_timezone).strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(backup_dir, f"dadosr_backup_{timestamp}.csv")
            
            # Backup do arquivo atual se existir
            current_file = 'data/dadosr.csv'
            if os.path.exists(current_file):
                shutil.copy2(current_file, backup_file)
                logging.info(f"Backup criado: {backup_file}")
            
            # Salvar como arquivo temporário para preview, com formato de data padronizado
            temp_file = 'data/dadosr_temp.csv'
            df.to_csv(
                temp_file, 
                index=False, 
                encoding='cp1252', 
                sep=';',
                date_format='%d/%m/%Y %H:%M'
            )
            
            # Estatísticas
            stats = {
                'records_count': len(df),
                'columns_count': len(df.columns),
                'file_size_kb': round(os.path.getsize(temp_file) / 1024, 2),
                'encoding_used': encoding,
                'separator_used': separator,
                'backup_created': backup_file if os.path.exists(current_file) else None,
                'preview_file': temp_file
            }
            
            # Preparar preview dos dados (convertendo timestamps para strings)
            preview_df = df.head(10).copy()
            
            # Converter timestamps para strings no preview
            for col in preview_df.columns:
                if preview_df[col].dtype == 'datetime64[ns]':
                    preview_df[col] = preview_df[col].dt.strftime('%d/%m/%Y %H:%M').fillna('')
                elif preview_df[col].dtype == 'object':
                    # Converter timestamps individuais para string
                    preview_df[col] = preview_df[col].apply(
                        lambda x: x.strftime('%d/%m/%Y %H:%M') if hasattr(x, 'strftime') else (x if pd.notna(x) else '')
                    )
            
            # Converter DataFrame para dict e substituir NaN por null
            preview_records = preview_df.to_dict('records')
            
            # Limpar valores NaN que causam erro no JSON
            def clean_nan_values(obj):
                if isinstance(obj, dict):
                    return {k: clean_nan_values(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [clean_nan_values(item) for item in obj]
                elif pd.isna(obj):
                    return None
                elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
                    # Para outros iteráveis (exceto strings)
                    return [clean_nan_values(item) for item in obj]
                else:
                    return obj
            
            cleaned_preview = clean_nan_values(preview_records)
            
            return {
                'success': True,
                'message': f'Arquivo processado com sucesso! {stats["records_count"]} registros carregados.',
                'stats': stats,
                'data_preview': cleaned_preview
            }
            
        except Exception as e:
            logging.error(f"Erro no processamento: {str(e)}")
            return {
                'success': False,
                'message': f'Erro ao processar arquivo: {str(e)}',
                'stats': None
            }

    @staticmethod
    def apply_automatic_corrections(df):
        """Aplica correções automáticas nos dados"""
        
        logging.info("Iniciando correções automáticas...")
        
        # Mapear colunas por palavras-chave (case insensitive)
        column_mapping = AdminService.identify_columns(df)
        
        for col in df.columns:
            col_lower = col.lower()
            
            try:
                # Correção de datas
                if any(keyword in col_lower for keyword in ['data', 'vencimento', 'resolvido', 'aberto']):
                    df[col] = AdminService.fix_dates(df[col])
                    logging.info(f"Datas corrigidas na coluna: {col}")
            except Exception as e:
                logging.warning(f"Erro ao corrigir datas em {col}: {e}")
            
            try:
                # Correção de percentuais
                if any(keyword in col_lower for keyword in ['andamento', 'progresso', '%']):
                    df[col] = AdminService.fix_percentages(df[col])
                    logging.info(f"Percentuais corrigidos na coluna: {col}")
            except Exception as e:
                logging.warning(f"Erro ao corrigir percentuais em {col}: {e}")
            
            try:
                # Correção de valores monetários e numéricos
                if any(keyword in col_lower for keyword in ['esforço', 'estimado', 'valor', 'custo', 'preço']):
                    df[col] = AdminService.fix_monetary_values(df[col])
                    logging.info(f"Valores monetários corrigidos na coluna: {col}")
            except Exception as e:
                logging.warning(f"Erro ao corrigir valores monetários em {col}: {e}")
            
            try:
                # Correção de tempo trabalhado
                if any(keyword in col_lower for keyword in ['tempo', 'trabalhado', 'horas']):
                    df[col] = AdminService.fix_time_format(df[col])
                    logging.info(f"Formato de tempo corrigido na coluna: {col}")
            except Exception as e:
                logging.warning(f"Erro ao corrigir tempo em {col}: {e}")
            
            try:
                # Normalizar status
                if any(keyword in col_lower for keyword in ['status', 'estado', 'situação']):
                    df[col] = AdminService.normalize_status(df[col])
                    logging.info(f"Status normalizado na coluna: {col}")
            except Exception as e:
                logging.warning(f"Erro ao normalizar status em {col}: {e}")
        
        logging.info("Correções automáticas concluídas")
        return df

    @staticmethod
    def identify_columns(df):
        """Identifica colunas por palavras-chave"""
        mapping = {}
        
        for col in df.columns:
            col_lower = col.lower()
            
            if any(keyword in col_lower for keyword in ['número', 'numero', 'id', 'ticket']):
                mapping['numero'] = col
            elif any(keyword in col_lower for keyword in ['cliente', 'company', 'empresa']):
                mapping['cliente'] = col
            elif any(keyword in col_lower for keyword in ['serviço', 'servico', 'service']):
                mapping['servico'] = col
            elif any(keyword in col_lower for keyword in ['status', 'estado', 'state']):
                mapping['status'] = col
            elif any(keyword in col_lower for keyword in ['esforço', 'esforco', 'effort', 'estimado']):
                mapping['esforco'] = col
            elif any(keyword in col_lower for keyword in ['tempo', 'time', 'trabalhado', 'worked']):
                mapping['tempo'] = col
            elif any(keyword in col_lower for keyword in ['andamento', 'progresso', 'progress', '%']):
                mapping['andamento'] = col
        
        return mapping

    @staticmethod
    def fix_dates(series):
        """Corrige formatos de data de forma mais robusta."""
        def parse_date(date_str):
            if pd.isna(date_str) or date_str == '':
                return None  # Retorna None para valores vazios
            
            date_str = str(date_str).strip()
            
            # Formatos comuns do ITSM brasileiro, do mais específico para o mais geral
            formats = [
                '%d/%m/%Y %H:%M:%S',
                '%d/%m/%Y %H:%M',
                '%Y-%m-%d %H:%M:%S',
                '%d/%m/%Y',
                '%Y-%m-%d',
                '%d-%m-%Y',
                '%d/%m/%y'
            ]
            
            for fmt in formats:
                try:
                    # Converte para datetime primeiro
                    dt = pd.to_datetime(date_str, format=fmt)
                    # PADRONIZAÇÃO: Sempre retorna no formato '%d/%m/%Y %H:%M'
                    return dt.strftime('%d/%m/%Y %H:%M')
                except (ValueError, TypeError):
                    continue
            
            # Se nenhum formato específico funcionou, tenta a conversão genérica do Pandas
            try:
                # dayfirst=True ajuda a interpretar dd/mm/yyyy corretamente
                dt = pd.to_datetime(date_str, dayfirst=True, errors='coerce')
                if pd.notna(dt):
                    # PADRONIZAÇÃO: Sempre retorna no formato '%d/%m/%Y %H:%M'
                    return dt.strftime('%d/%m/%Y %H:%M')
                else:
                    return None
            except Exception:
                # Se tudo falhar, retorna None para não quebrar o processo
                logging.warning(f"Não foi possível converter a data '{date_str}' para um formato conhecido.")
                return None
        
        # Aplica a função de conversão na coluna inteira
        return series.apply(parse_date)

    @staticmethod
    def fix_percentages(series):
        """Corrige percentuais removendo % e convertendo para decimal"""
        def parse_percentage(value):
            if pd.isna(value) or value == '':
                return None
            
            value_str = str(value).strip()
            
            # Remover símbolo de %
            if '%' in value_str:
                value_str = value_str.replace('%', '')
            
            try:
                # Substituir vírgula por ponto
                value_str = value_str.replace(',', '.')
                return float(value_str)
            except:
                return value
        
        return series.apply(parse_percentage)

    @staticmethod
    def fix_monetary_values(series):
        """Corrige valores monetários"""
        def parse_money(value):
            if pd.isna(value) or value == '':
                return None
            
            value_str = str(value).strip()
            
            # Remover símbolos de moeda
            value_str = re.sub(r'[R$€£¥]', '', value_str)
            
            # Remover pontos que são separadores de milhares (formato brasileiro)
            # Ex: 1.650,000 -> 1650,000
            if ',' in value_str and '.' in value_str:
                # Se tem tanto ponto quanto vírgula, assumir formato brasileiro
                # onde ponto = separador de milhares e vírgula = decimal
                parts = value_str.split(',')
                if len(parts) == 2:
                    integer_part = parts[0].replace('.', '')
                    decimal_part = parts[1]
                    value_str = f"{integer_part}.{decimal_part}"
            elif ',' in value_str and '.' not in value_str:
                # Apenas vírgula = separador decimal brasileiro
                value_str = value_str.replace(',', '.')
            
            try:
                return float(value_str)
            except:
                return value
        
        return series.apply(parse_money)

    @staticmethod
    def fix_time_format(series):
        """Corrige formato de tempo (HH:MM:SS)"""
        def parse_time(value):
            if pd.isna(value) or value == '':
                return None
            
            value_str = str(value).strip()
            
            # Verificar se já está no formato correto HH:MM:SS
            if re.match(r'^\d+:\d{2}:\d{2}$', value_str):
                return value_str
            
            # Tentar converter formatos diferentes
            try:
                # Se for apenas HH:MM, adicionar :00
                if re.match(r'^\d+:\d{2}$', value_str):
                    return value_str + ':00'
                
                # Se for decimal (ex: 8.5 horas), converter para HH:MM:SS
                if '.' in value_str or ',' in value_str:
                    hours = float(value_str.replace(',', '.'))
                    total_minutes = int(hours * 60)
                    h = total_minutes // 60
                    m = total_minutes % 60
                    return f"{h:d}:{m:02d}:00"
                
                return value_str
            except:
                return value
        
        return series.apply(parse_time)

    @staticmethod
    def normalize_status(series):
        """Normaliza valores de status"""
        status_mapping = {
            'em atendimento': 'Em Atendimento',
            'fechado': 'Fechado',
            'aguardando': 'Aguardando',
            'resolvido': 'Resolvido',
            'novo': 'Novo',
            'bloqueado': 'Bloqueado',
            'cancelado': 'Cancelado',
            'pendente': 'Pendente'
        }
        
        def normalize_value(value):
            if pd.isna(value) or value == '':
                return None
            
            value_str = str(value).strip().lower()
            return status_mapping.get(value_str, str(value).strip())
        
        return series.apply(normalize_value)

    @staticmethod
    def validate_structure_flexible(df):
        """Validação flexível da estrutura do CSV"""
        
        # Verificar se temos pelo menos algumas colunas essenciais
        required_keywords = ['número', 'cliente', 'status']
        found_columns = []
        
        for keyword in required_keywords:
            found = False
            for col in df.columns:
                if keyword in col.lower():
                    found_columns.append(col)
                    found = True
                    break
            
            if not found:
                logging.warning(f"Coluna com palavra-chave '{keyword}' não encontrada")
        
        # Considerar válido se encontrou pelo menos 2 das 3 colunas essenciais
        if len(found_columns) >= 2:
            return {
                'valid': True,
                'message': f'Estrutura válida. Colunas identificadas: {found_columns}',
                'identified_columns': found_columns
            }
        else:
            return {
                'valid': False,
                'message': f'Estrutura inválida. Apenas {len(found_columns)} colunas essenciais encontradas: {found_columns}',
                'identified_columns': found_columns
            }
    
    @staticmethod
    def get_data_preview(page=1, per_page=50, search=''):
        """Retorna preview paginado dos dados"""
        try:
            csv_path = Path("data/dadosr.csv")
            
            # Tenta diferentes encodings (CP1252 primeiro - arquivo atual)
            df = None
            working_encoding = None
            encodings = ['cp1252', 'utf-8', 'latin1', 'iso-8859-1']
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(csv_path, sep=';', encoding=encoding)
                    working_encoding = encoding
                    break
                except UnicodeDecodeError:
                    continue
                except Exception:
                    continue
            
            if df is None:
                return {
                    'data': [],
                    'total': 0,
                    'page': 1,
                    'per_page': per_page,
                    'total_pages': 0,
                    'error': 'Não foi possível ler o arquivo CSV'
                }
            
            # Log do encoding usado para leitura
            try:
                from flask import current_app
                current_app.logger.info(f"📖 Preview carregado com encoding: {working_encoding}")
            except:
                pass
            
            # Garantir que as datas sejam parseadas corretamente para exibição
            date_columns = ['DataInicio', 'DataTermino', 'VencimentoEm', 'UltimaInteracao']
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], format='%d/%m/%Y %H:%M', errors='coerce')

            # Filtro de busca e manutenção dos índices originais
            if search:
                search_term = search.lower()
                mask = df.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)
                # Mantém os índices originais antes de filtrar
                df_filtered = df[mask].copy()
                df_filtered['_original_index'] = df[mask].index
            else:
                df_filtered = df.copy()
                df_filtered['_original_index'] = df.index
            
            # Paginação
            total = len(df_filtered)
            start = (page - 1) * per_page
            end = start + per_page
            
            data = df_filtered.iloc[start:end].to_dict('records')
            
            # Adiciona ID único para cada registro usando o índice original do arquivo
            for record in data:
                # CORREÇÃO CRÍTICA: usa o índice original do arquivo, não da página
                record['_id'] = record['_original_index']
                # Remove o campo auxiliar
                record.pop('_original_index', None)
                # Limpa valores NaN e None que podem causar problemas no JSON
                for key, value in record.items():
                    if pd.isna(value) or value is None:
                        record[key] = ''
                    elif isinstance(value, float) and pd.isna(value):
                        record[key] = ''
                    else:
                        record[key] = str(value)
            
            return {
                'data': data,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page
            }
            
        except Exception as e:
            return {
                'data': [],
                'total': 0,
                'page': 1,
                'per_page': per_page,
                'total_pages': 0,
                'error': str(e)
            }
    
    @staticmethod
    def get_record_by_id(record_id):
        """Retorna um registro específico por ID"""
        try:
            csv_path = Path("data/dadosr.csv")
            
            # Tenta diferentes encodings (CP1252 primeiro - arquivo atual)
            df = None
            encodings = ['cp1252', 'utf-8', 'latin1', 'iso-8859-1']
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(csv_path, sep=';', encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
                except Exception:
                    continue
            
            if df is None:
                return {'error': 'Não foi possível ler o arquivo CSV'}
            
            if record_id >= len(df):
                return {'error': 'Registro não encontrado'}
            
            record = df.iloc[record_id].to_dict()
            record['_id'] = record_id
            
            # Limpa valores problemáticos
            for key, value in record.items():
                if pd.isna(value) or value is None:
                    record[key] = ''
                else:
                    record[key] = str(value)
            
            return record
            
        except Exception as e:
            return {'error': str(e)}
    
    @staticmethod
    def update_record(record_id, data):
        """Atualiza um registro específico"""
        try:
            csv_path = Path("data/dadosr.csv")
            
            # Tenta diferentes encodings para ler e salva no mesmo encoding (CP1252 primeiro - arquivo atual)
            df = None
            working_encoding = None
            encodings = ['cp1252', 'utf-8', 'latin1', 'iso-8859-1']
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(csv_path, sep=';', encoding=encoding)
                    working_encoding = encoding
                    break
                except UnicodeDecodeError:
                    continue
                except Exception:
                    continue
            
            if df is None:
                return {'error': 'Não foi possível ler o arquivo CSV'}
            
            if record_id >= len(df):
                return {'error': 'Registro não encontrado'}
            
            # Remove campos de controle
            data.pop('_id', None)
            
            # Atualiza o registro
            for key, value in data.items():
                if key in df.columns:
                    df.iloc[record_id, df.columns.get_loc(key)] = value
            
            # Salva no mesmo encoding que foi lido
            df.to_csv(csv_path, sep=';', index=False, encoding=working_encoding)
            
            # Log da atualização
            from flask import current_app
            current_app.logger.info(f"✅ Registro {record_id} atualizado com sucesso. Encoding: {working_encoding}")
            
            # Teste de verificação imediata - lê novamente para confirmar que salvou corretamente
            try:
                df_test = pd.read_csv(csv_path, sep=';', encoding=working_encoding)
                if record_id < len(df_test):
                    current_app.logger.info(f"✅ Verificação: Dados salvos e lidos corretamente")
                else:
                    current_app.logger.warning(f"⚠️ Verificação: Registro não encontrado após salvar")
            except Exception as e:
                current_app.logger.error(f"❌ Verificação: Erro ao ler arquivo após salvar: {str(e)}")
            
            return {'success': True, 'record_id': record_id, 'encoding_used': working_encoding}
            
        except Exception as e:
            return {'error': str(e)}
    
    @staticmethod
    def delete_record(record_id):
        """Deleta um registro específico"""
        try:
            csv_path = Path("data/dadosr.csv")
            
            # Tenta diferentes encodings para ler e salva no mesmo encoding (CP1252 primeiro - arquivo atual)
            df = None
            working_encoding = None
            encodings = ['cp1252', 'utf-8', 'latin1', 'iso-8859-1']
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(csv_path, sep=';', encoding=encoding)
                    working_encoding = encoding
                    break
                except UnicodeDecodeError:
                    continue
                except Exception:
                    continue
            
            if df is None:
                return {'error': 'Não foi possível ler o arquivo CSV'}
            
            if record_id >= len(df):
                return {'error': 'Registro não encontrado'}
            
            # Remove o registro
            df = df.drop(df.index[record_id])
            
            # Salva no mesmo encoding que foi lido
            df.to_csv(csv_path, sep=';', index=False, encoding=working_encoding)
            
            return {'success': True}
            
        except Exception as e:
            return {'error': str(e)}
    
    @staticmethod
    def create_data_backup():
        """Cria backup do arquivo de dados atual"""
        try:
            csv_path = Path("data/dadosr.csv")
            
            if not csv_path.exists():
                return {'error': 'Arquivo de dados não encontrado'}
            
            # Cria diretório de backup se não existir
            backup_dir = Path("data/backups")
            backup_dir.mkdir(exist_ok=True)
            
            # Nome do backup com timestamp
            timestamp = datetime.now(br_timezone).strftime("%Y%m%d_%H%M%S")
            backup_filename = f"dadosr_backup_{timestamp}.csv"
            backup_path = backup_dir / backup_filename
            
            # Copia o arquivo
            shutil.copy2(csv_path, backup_path)
            
            return {
                'success': True,
                'filename': backup_filename,
                'path': str(backup_path),
                'timestamp': timestamp,
                'size': backup_path.stat().st_size
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    @staticmethod
    def validate_data_integrity(data):
        """Valida integridade dos dados"""
        errors = []
        warnings = []
        
        # Validações básicas
        if not data:
            errors.append("Nenhum dado fornecido")
            return {'valid': False, 'errors': errors, 'warnings': warnings}
        
        # Verifica campos obrigatórios
        required_fields = ['Número', 'Cliente (Completo)', 'Status']
        
        for field in required_fields:
            if field not in data or not data[field]:
                errors.append(f"Campo obrigatório '{field}' está vazio")
        
        # Validações específicas
        if 'Número' in data:
            try:
                int(data['Número'])
            except (ValueError, TypeError):
                errors.append("Campo 'Número' deve ser um número válido")
        
        if 'Andamento' in data:
            try:
                andamento = float(str(data['Andamento']).replace('%', ''))
                if andamento < 0 or andamento > 100:
                    warnings.append("Andamento deve estar entre 0% e 100%")
            except (ValueError, TypeError):
                warnings.append("Campo 'Andamento' deve ser um número válido")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    @staticmethod
    def apply_data_changes(changes_data):
        """Aplica todas as alterações pendentes"""
        try:
            # Cria backup antes das alterações
            backup_result = AdminService.create_data_backup()
            
            affected_records = 0
            errors = []
            
            # Processa cada alteração
            for change in changes_data.get('changes', []):
                try:
                    if change['type'] == 'update':
                        AdminService.update_record(change['record_id'], change['data'])
                        affected_records += 1
                    elif change['type'] == 'delete':
                        AdminService.delete_record(change['record_id'])
                        affected_records += 1
                except Exception as e:
                    errors.append(f"Erro no registro {change.get('record_id', 'N/A')}: {str(e)}")
            
            return {
                'success': len(errors) == 0,
                'affected_records': affected_records,
                'errors': errors,
                'backup_created': backup_result.get('filename', '')
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'affected_records': 0
            }


class ComplexityAdminService:
    """Serviço específico para administração de complexidade"""
    
    @staticmethod
    def get_complexity_overview():
        """Retorna visão geral das configurações de complexidade"""
        try:
            criteria = ComplexityCriteria.query.filter_by(is_active=True).order_by(ComplexityCriteria.criteria_order).all()
            thresholds = ComplexityThreshold.query.order_by(ComplexityThreshold.min_score).all()
            
            overview = {
                'criteria_count': len(criteria),
                'total_combinations': 1,
                'score_range': {
                    'min': 0,
                    'max': 0
                },
                'categories': []
            }
            
            # Calcula combinações possíveis e faixa de pontuação
            for criterion in criteria:
                options = ComplexityCriteriaOption.query.filter_by(criteria_id=criterion.id, is_active=True).all()
                if options:
                    overview['total_combinations'] *= len(options)
                    overview['score_range']['max'] += max(opt.points for opt in options)
            
            # Informações das categorias
            for threshold in thresholds:
                overview['categories'].append({
                    'name': threshold.category.value,
                    'range': f"{threshold.min_score}-{threshold.max_score or '∞'}",
                    'min_score': threshold.min_score,
                    'max_score': threshold.max_score
                })
            
            return overview
            
        except Exception as e:
            current_app.logger.error(f"Erro ao obter overview de complexidade: {e}")
            return None
    
    @staticmethod
    def simulate_scoring(test_selections):
        """Simula pontuação baseada em seleções de teste"""
        try:
            total_score = 0
            details = []
            
            for criteria_id, option_id in test_selections.items():
                option = ComplexityCriteriaOption.query.get(option_id)
                if option:
                    total_score += option.points
                    details.append({
                        'criteria_id': criteria_id,
                        'option_id': option_id,
                        'points': option.points,
                        'label': option.option_label or option.option_name
                    })
            
            # Determina categoria
            category = 'ALTA'
            thresholds = ComplexityThreshold.query.order_by(ComplexityThreshold.min_score).all()
            for threshold in thresholds:
                if total_score >= threshold.min_score and (threshold.max_score is None or total_score <= threshold.max_score):
                    category = threshold.category.value
                    break
            
            return {
                'total_score': total_score,
                'category': category,
                'details': details
            }
            
        except Exception as e:
            current_app.logger.error(f"Erro na simulação de pontuação: {e}")
            return None 