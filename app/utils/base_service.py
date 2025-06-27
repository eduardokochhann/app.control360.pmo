import pandas as pd
from pathlib import Path
import logging
from datetime import datetime, timedelta, date
import os
import numpy as np
from typing import List, Dict, Optional, Tuple
import json
import holidays

class BaseService:
    """Classe base para serviços de processamento de dados."""
    
    def __init__(self):
        """Inicializa o serviço com configurações básicas."""
        self.csv_path = Path(__file__).parent.parent.parent / 'data' / 'dadosr.csv'
        logger = logging.getLogger(__name__)
        logger.info(f"Caminho do CSV definido para: {self.csv_path}")
        
    def carregar_dados(self):
        """Carrega dados do arquivo CSV."""
        try:
            if not self.csv_path.exists():
                raise FileNotFoundError(f"Arquivo CSV não encontrado: {self.csv_path}")
                
            dados = pd.read_csv(self.csv_path, 
                              sep=';',
                              encoding='latin1',
                              quoting=1)  # QUOTE_ALL
                              
            if dados.empty:
                logger.warning("Arquivo CSV está vazio")
                return pd.DataFrame()
                
            # Verifica colunas obrigatórias
            colunas_obrigatorias = ['Status', 'Squad', 'Especialista', 'Conclusao']
            colunas_faltantes = [col for col in colunas_obrigatorias if col not in dados.columns]
            if colunas_faltantes:
                raise ValueError(f"Colunas obrigatórias ausentes: {colunas_faltantes}")
                
            # Converte datas
            for col in ['DataInicio', 'DataTermino', 'VencimentoEm']:
                if col in dados.columns:
                    dados[col] = pd.to_datetime(dados[col], errors='coerce')
                    
            # Padroniza texto
            for col in ['Status', 'Squad', 'Especialista', 'Account Manager']:
                if col in dados.columns:
                    dados[col] = dados[col].fillna('').astype(str).str.strip()
                    
            # Converte conclusão para numérico
            if 'Conclusao' in dados.columns:
                dados['Conclusao'] = pd.to_numeric(dados['Conclusao'], errors='coerce')
                dados['Conclusao'] = dados['Conclusao'].clip(0, 100)
                
            # Converte horas trabalhadas
            if 'HorasTrabalhadas' in dados.columns:
                dados['HorasTrabalhadas'] = dados['HorasTrabalhadas'].apply(self.converter_tempo_para_horas)
                
            # Limpa nomes de projetos
            if 'Projeto' in dados.columns:
                dados['Projeto'] = dados['Projeto'].apply(self.limpar_nome_projeto)
                
            # Calcula horas restantes
            dados = self.calcular_horas_restantes(dados)
            
            logger.info(f"Dados carregados com sucesso: {len(dados)} registros")
            return dados
            
        except Exception as e:
            logger.error(f"Erro ao carregar dados: {str(e)}", exc_info=True)
            return pd.DataFrame()
            
    def converter_tempo_para_horas(self, tempo_str):
        """Converte string de tempo (HH:MM) para horas decimais."""
        try:
            if pd.isna(tempo_str) or tempo_str == '':
                return 0.0
                
            if isinstance(tempo_str, (int, float)):
                return float(tempo_str)
                
            # Remove espaços e converte para string
            tempo_str = str(tempo_str).strip()
            
            # Se já for um número, retorna como float
            try:
                return float(tempo_str)
            except ValueError:
                pass
                
            # Tenta diferentes formatos
            if ':' in tempo_str:
                # Formato HH:MM
                horas, minutos = tempo_str.split(':')
                return float(horas) + float(minutos)/60
            elif 'h' in tempo_str.lower():
                # Formato Xh Ym
                tempo_str = tempo_str.lower().replace(' ', '')
                if 'h' in tempo_str:
                    horas = float(tempo_str.split('h')[0])
                    minutos = float(tempo_str.split('h')[1].replace('m', '')) if 'm' in tempo_str else 0
                    return horas + minutos/60
                    
            return 0.0
            
        except Exception as e:
            logger.error(f"Erro ao converter tempo '{tempo_str}': {str(e)}")
            return 0.0
            
    def calcular_horas_restantes(self, dados):
        """Calcula horas restantes para cada projeto."""
        try:
            if 'HorasTrabalhadas' not in dados.columns or 'HorasPrevistas' not in dados.columns:
                return dados
                
            dados['HorasRestantes'] = dados['HorasPrevistas'] - dados['HorasTrabalhadas']
            dados['HorasRestantes'] = dados['HorasRestantes'].clip(lower=0)
            
            return dados
            
        except Exception as e:
            logger.error(f"Erro ao calcular horas restantes: {str(e)}")
            return dados
            
    def limpar_nome_projeto(self, nome):
        """Remove partes do nome do projeto após vírgulas."""
        try:
            if pd.isna(nome) or nome == '':
                return ''
                
            nome = str(nome).strip()
            if ',' in nome:
                nome = nome.split(',')[0].strip()
                
            return nome
            
        except Exception as e:
            logger.error(f"Erro ao limpar nome do projeto '{nome}': {str(e)}")
            return str(nome)

class DateCalculationService:
    """Serviço para cálculo sequencial de datas baseado em configurações de especialistas."""
    
    @staticmethod
    def calculate_sequential_dates(tasks: List[Dict], sprint_start_date: datetime) -> List[Dict]:
        """
        Calcula datas sequenciais para lista de tarefas agrupadas por especialista.
        
        Args:
            tasks: Lista de tarefas com formato:
                   [{'specialist_name': str, 'estimated_effort': float, 'id': int, ...}, ...]
            sprint_start_date: Data de início da sprint
            
        Returns:
            Lista de tarefas com start_date e due_date calculadas
        """
        from ..models import SpecialistConfiguration
        
        # Agrupa tarefas por especialista
        tasks_by_specialist = {}
        for task in tasks:
            specialist = task.get('specialist_name') or 'Não Atribuído'
            if specialist not in tasks_by_specialist:
                tasks_by_specialist[specialist] = []
            tasks_by_specialist[specialist].append(task)
        
        updated_tasks = []
        
        # Processa cada especialista sequencialmente
        for specialist_name, specialist_tasks in tasks_by_specialist.items():
            if specialist_name == 'Não Atribuído':
                # Para tarefas não atribuídas, use configuração padrão
                config = DateCalculationService._get_default_config()
            else:
                config = SpecialistConfiguration.get_or_create_config(specialist_name)
            
            # Calcula datas para tarefas do especialista
            specialist_updated_tasks = DateCalculationService._calculate_specialist_tasks(
                specialist_tasks, sprint_start_date, config
            )
            updated_tasks.extend(specialist_updated_tasks)
        
        return updated_tasks
    
    @staticmethod
    def _calculate_specialist_tasks(tasks: List[Dict], start_date: datetime, config) -> List[Dict]:
        """Calcula datas para tarefas de um especialista específico."""
        current_date = start_date.date() if isinstance(start_date, datetime) else start_date
        
        for task in tasks:
            effort_hours = task.get('estimated_effort', 0) or 0
            
            if effort_hours <= 0:
                # Se não há esforço estimado, use configuração mínima
                task['start_date'] = current_date.isoformat()
                task['due_date'] = current_date.isoformat()
                continue
            
            # Aplica buffer se configurado
            if hasattr(config, 'buffer_percentage') and config.buffer_percentage > 0:
                effort_hours *= (1 + config.buffer_percentage / 100)
            
            # Calcula data de início
            task_start_date = current_date
            
            # Calcula data de fim baseada no esforço
            task_end_date = DateCalculationService._calculate_end_date(
                task_start_date, effort_hours, config
            )
            
            # Atualiza tarefa
            task['start_date'] = task_start_date.isoformat()
            task['due_date'] = task_end_date.isoformat()
            
            # Próxima tarefa começa após esta terminar
            current_date = DateCalculationService._get_next_work_day(task_end_date, config)
        
        return tasks
    
    @staticmethod
    def _calculate_end_date(start_date: date, effort_hours: float, config) -> date:
        """Calcula data de fim baseada no esforço e configuração do especialista."""
        daily_hours = getattr(config, 'daily_work_hours', 8.0)
        work_days_config = config.get_work_days_config() if hasattr(config, 'get_work_days_config') else DateCalculationService._get_default_work_days()
        
        remaining_hours = effort_hours
        current_date = start_date
        
        while remaining_hours > 0:
            if DateCalculationService._is_work_day(current_date, work_days_config, config):
                # Desconta horas do dia
                daily_capacity = min(remaining_hours, daily_hours)
                remaining_hours -= daily_capacity
                
                if remaining_hours <= 0:
                    break
            
            current_date += timedelta(days=1)
        
        return current_date
    
    @staticmethod
    def _is_work_day(check_date: date, work_days_config: Dict, config) -> bool:
        """Verifica se uma data é dia útil."""
        # Mapeia dia da semana para nome em inglês
        weekday_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        weekday_name = weekday_names[check_date.weekday()]
        
        # Verifica se é dia útil na configuração
        if not work_days_config.get(weekday_name, True):
            return False
        
        # Verifica feriados se configurado
        if hasattr(config, 'consider_holidays') and config.consider_holidays:
            if DateCalculationService._is_holiday(check_date, config):
                return False
        
        return True
    
    @staticmethod
    def _is_holiday(check_date: date, config) -> bool:
        """Verifica se uma data é feriado."""
        # Feriados brasileiros padrão
        br_holidays = holidays.Brazil(years=check_date.year)
        if check_date in br_holidays:
            return True
        
        # Feriados personalizados
        if hasattr(config, 'get_custom_holidays'):
            custom_holidays = config.get_custom_holidays()
            date_str = check_date.isoformat()
            if date_str in custom_holidays:
                return True
        
        return False
    
    @staticmethod
    def _get_next_work_day(current_date: date, config) -> date:
        """Retorna o próximo dia útil após a data atual."""
        next_date = current_date + timedelta(days=1)
        work_days_config = config.get_work_days_config() if hasattr(config, 'get_work_days_config') else DateCalculationService._get_default_work_days()
        
        while not DateCalculationService._is_work_day(next_date, work_days_config, config):
            next_date += timedelta(days=1)
        
        return next_date
    
    @staticmethod
    def _get_default_config():
        """Retorna configuração padrão para especialistas não configurados."""
        class DefaultConfig:
            daily_work_hours = 8.0
            buffer_percentage = 10.0
            consider_holidays = True
            
            def get_work_days_config(self):
                return DateCalculationService._get_default_work_days()
            
            def get_custom_holidays(self):
                return []
        
        return DefaultConfig()
    
    @staticmethod
    def _get_default_work_days():
        """Retorna configuração padrão de dias úteis."""
        return {
            "monday": True, "tuesday": True, "wednesday": True,
            "thursday": True, "friday": True, "saturday": False, "sunday": False
        }

    @staticmethod
    def calculate_sprint_capacity_alerts(tasks: List[Dict], sprint_dates: Dict) -> Dict:
        """
        Calcula alertas e sugestões de capacidade para uma sprint.
        
        Args:
            tasks: Lista de tarefas da sprint
            sprint_dates: {'start_date': datetime, 'end_date': datetime}
            
        Returns:
            Dict com alertas e sugestões
        """
        from ..models import SpecialistConfiguration
        
        alerts = {
            'capacity_warnings': [],
            'date_conflicts': [],
            'suggestions': [],
            'sprint_health': 'healthy',  # healthy, warning, critical
            'total_effort': 0,
            'total_capacity': 0,
            'utilization_percentage': 0
        }
        
        # Agrupa tarefas por especialista
        specialist_data = {}
        total_effort = 0
        
        for task in tasks:
            specialist = task.get('specialist_name') or 'Não Atribuído'
            effort = task.get('estimated_effort', 0) or 0
            total_effort += effort
            
            if specialist not in specialist_data:
                specialist_data[specialist] = {
                    'tasks': [],
                    'total_effort': 0,
                    'capacity': 0,
                    'config': None
                }
            
            specialist_data[specialist]['tasks'].append(task)
            specialist_data[specialist]['total_effort'] += effort
        
        # Calcula capacidade e alertas por especialista
        total_capacity = 0
        for specialist_name, data in specialist_data.items():
            if specialist_name == 'Não Atribuído':
                config = DateCalculationService._get_default_config()
            else:
                config = SpecialistConfiguration.get_or_create_config(specialist_name)
            
            data['config'] = config
            
            # Calcula capacidade do especialista na sprint
            sprint_capacity = DateCalculationService._calculate_sprint_capacity(
                sprint_dates['start_date'], sprint_dates['end_date'], config
            )
            data['capacity'] = sprint_capacity
            total_capacity += sprint_capacity
            
            # Verifica sobrecarga
            utilization = (data['total_effort'] / sprint_capacity * 100) if sprint_capacity > 0 else 0
            
            if utilization > 100:
                alerts['capacity_warnings'].append({
                    'specialist': specialist_name,
                    'effort': data['total_effort'],
                    'capacity': sprint_capacity,
                    'overload': data['total_effort'] - sprint_capacity,
                    'utilization': utilization,
                    'severity': 'critical' if utilization > 150 else 'warning'
                })
            elif utilization > 80:
                alerts['capacity_warnings'].append({
                    'specialist': specialist_name,
                    'effort': data['total_effort'],
                    'capacity': sprint_capacity,
                    'utilization': utilization,
                    'severity': 'warning'
                })
        
        # Calcula métricas gerais
        alerts['total_effort'] = total_effort
        alerts['total_capacity'] = total_capacity
        alerts['utilization_percentage'] = (total_effort / total_capacity * 100) if total_capacity > 0 else 0
        
        # Define saúde geral da sprint
        critical_warnings = [w for w in alerts['capacity_warnings'] if w.get('severity') == 'critical']
        warning_count = len([w for w in alerts['capacity_warnings'] if w.get('severity') == 'warning'])
        
        if critical_warnings:
            alerts['sprint_health'] = 'critical'
        elif warning_count > 0 or alerts['utilization_percentage'] > 85:
            alerts['sprint_health'] = 'warning'
        
        # Gera sugestões
        alerts['suggestions'] = DateCalculationService._generate_suggestions(specialist_data, alerts)
        
        return alerts
    
    @staticmethod
    def _calculate_sprint_capacity(start_date: datetime, end_date: datetime, config) -> float:
        """Calcula capacidade total de trabalho entre duas datas."""
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00')).date()
        elif isinstance(start_date, datetime):
            start_date = start_date.date()
            
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00')).date()
        elif isinstance(end_date, datetime):
            end_date = end_date.date()
        
        daily_hours = getattr(config, 'daily_work_hours', 8.0)
        work_days_config = config.get_work_days_config() if hasattr(config, 'get_work_days_config') else DateCalculationService._get_default_work_days()
        
        current_date = start_date
        total_hours = 0
        
        while current_date <= end_date:
            if DateCalculationService._is_work_day(current_date, work_days_config, config):
                total_hours += daily_hours
            current_date += timedelta(days=1)
        
        return total_hours
    
    @staticmethod
    def _generate_suggestions(specialist_data: Dict, alerts: Dict) -> List[Dict]:
        """Gera sugestões baseadas na análise de capacidade."""
        suggestions = []
        
        # Sugestão para especialistas sobrecarregados
        overloaded = [w for w in alerts['capacity_warnings'] if w.get('severity') in ['critical', 'warning']]
        if overloaded:
            suggestions.append({
                'type': 'capacity_redistribution',
                'message': f'Redistribuir tarefas de {len(overloaded)} especialista(s) sobrecarregado(s)',
                'specialists': [w['specialist'] for w in overloaded],
                'priority': 'high' if any(w.get('severity') == 'critical' for w in overloaded) else 'medium'
            })
        
        # Sugestão para utilização geral alta
        if alerts['utilization_percentage'] > 90:
            suggestions.append({
                'type': 'sprint_scope',
                'message': 'Sprint com alta utilização - considere reduzir escopo',
                'utilization': alerts['utilization_percentage'],
                'priority': 'high'
            })
        
        # Sugestão para especialistas subutilizados
        underutilized = []
        for specialist, data in specialist_data.items():
            if data['capacity'] > 0:
                utilization = (data['total_effort'] / data['capacity'] * 100)
                if utilization < 60:
                    underutilized.append({
                        'specialist': specialist,
                        'utilization': utilization,
                        'available_capacity': data['capacity'] - data['total_effort']
                    })
        
        if underutilized:
            suggestions.append({
                'type': 'capacity_optimization',
                'message': f'{len(underutilized)} especialista(s) com capacidade ociosa disponível',
                'specialists': underutilized,
                'priority': 'low'
            })
        
        return suggestions 