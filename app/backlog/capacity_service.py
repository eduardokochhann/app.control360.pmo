from datetime import datetime, timedelta, time
from collections import defaultdict
from typing import Dict, List, Tuple
import logging
from flask import current_app

from ..models import Task, TaskSegment, TaskStatus, Sprint
from ..macro.services import MacroService

logger = logging.getLogger(__name__)

class CapacityService:
    """Serviço para gerenciar capacidade de trabalho dos especialistas"""
    
    HORAS_POR_DIA = 7.2  # 36h ÷ 5 dias = 7.2h por dia
    DIAS_UTEIS_SEMANA = 5  # Segunda a Sexta
    HORAS_POR_SEMANA = 36.0  # 36h por semana conforme especificação
    
    HORARIO_INICIO = time(9, 0)  # 9:00
    HORARIO_FIM = time(18, 0)    # 18:00
    
    def __init__(self):
        self.macro_service = MacroService()
    
    def calcular_capacidade_semana(self, specialist_name: str, week_start: datetime) -> Dict:
        """
        Calcula a capacidade disponível do especialista para uma semana específica
        
        Args:
            specialist_name: Nome do especialista
            week_start: Data de início da semana (segunda-feira)
            
        Returns:
            Dict com informações de capacidade da semana
        """
        try:
            week_end = week_start + timedelta(days=4)  # Sexta-feira
            
            # Busca segmentos existentes na semana
            segments_semana = self._get_segments_semana(specialist_name, week_start, week_end)
            
            # Calcula horas por dia
            capacidade_por_dia = {}
            total_horas_alocadas = 0
            
            for dia_offset in range(5):  # Segunda a Sexta
                data_dia = week_start + timedelta(days=dia_offset)
                nome_dia = self._get_nome_dia(data_dia.weekday())
                
                # Horas já alocadas neste dia
                horas_dia = sum(
                    seg.get('estimated_hours', 0) 
                    for seg in segments_semana 
                    if self._mesmo_dia(seg['start_datetime'], data_dia)
                )
                
                capacidade_por_dia[nome_dia] = {
                    'data': data_dia.strftime('%Y-%m-%d'),
                    'horas_alocadas': round(horas_dia, 1),
                    'horas_disponiveis': round(self.HORAS_POR_DIA - horas_dia, 1),
                    'percentual_ocupacao': round((horas_dia / self.HORAS_POR_DIA) * 100, 1),
                    'status': self._get_status_dia(horas_dia),
                    'conflitos': horas_dia > self.HORAS_POR_DIA
                }
                
                total_horas_alocadas += horas_dia
            
            return {
                'specialist_name': specialist_name,
                'week_start': week_start.strftime('%Y-%m-%d'),
                'week_end': week_end.strftime('%Y-%m-%d'),
                'capacidade_por_dia': capacidade_por_dia,
                'resumo': {
                    'total_horas_semana': round(total_horas_alocadas, 1),
                    'total_horas_disponiveis': round(self.HORAS_POR_SEMANA - total_horas_alocadas, 1),
                    'percentual_ocupacao_semana': round((total_horas_alocadas / self.HORAS_POR_SEMANA) * 100, 1),
                    'dias_sobrecarregados': sum(1 for dia in capacidade_por_dia.values() if dia['conflitos']),
                    'status_semana': self._get_status_semana(total_horas_alocadas)
                }
            }
            
        except Exception as e:
            logger.error(f"Erro ao calcular capacidade da semana: {str(e)}")
            return self._get_capacidade_vazia(specialist_name, week_start)
    
    def verificar_conflitos_capacidade(self, specialist_name: str, task_hours: float, 
                                     target_date: datetime) -> Dict:
        """
        Verifica se adicionar uma tarefa causaria conflito de capacidade
        
        Args:
            specialist_name: Nome do especialista
            task_hours: Horas da tarefa a ser adicionada
            target_date: Data alvo para a tarefa
            
        Returns:
            Dict com informações sobre conflitos
        """
        try:
            # Calcula início da semana
            week_start = target_date - timedelta(days=target_date.weekday())
            capacidade = self.calcular_capacidade_semana(specialist_name, week_start)
            
            # Verifica conflito no dia específico
            nome_dia = self._get_nome_dia(target_date.weekday())
            dia_info = capacidade['capacidade_por_dia'].get(nome_dia, {})
            
            horas_disponiveis_dia = dia_info.get('horas_disponiveis', 0)
            causaria_conflito_dia = task_hours > horas_disponiveis_dia
            
            # Verifica conflito na semana
            horas_disponiveis_semana = capacidade['resumo']['total_horas_disponiveis']
            causaria_conflito_semana = task_hours > horas_disponiveis_semana
            
            return {
                'tem_conflito': causaria_conflito_dia or causaria_conflito_semana,
                'conflito_dia': causaria_conflito_dia,
                'conflito_semana': causaria_conflito_semana,
                'horas_disponiveis_dia': horas_disponiveis_dia,
                'horas_disponiveis_semana': horas_disponiveis_semana,
                'sugestoes': self._gerar_sugestoes_conflito(
                    specialist_name, task_hours, target_date, capacidade
                )
            }
            
        except Exception as e:
            logger.error(f"Erro ao verificar conflitos de capacidade: {str(e)}")
            return {'tem_conflito': False, 'erro': str(e)}
    
    def sugerir_melhor_horario(self, specialist_name: str, task_hours: float, 
                             semanas_futuras: int = 4) -> List[Dict]:
        """
        Sugere os melhores horários para alocar uma tarefa
        
        Args:
            specialist_name: Nome do especialista
            task_hours: Horas da tarefa
            semanas_futuras: Quantas semanas futuras considerar
            
        Returns:
            Lista de sugestões ordenadas por prioridade
        """
        try:
            sugestoes = []
            hoje = datetime.now().date()
            
            # Analisa próximas semanas
            for semana_offset in range(semanas_futuras):
                # Calcula início da semana
                dias_ate_proxima_segunda = (7 - hoje.weekday()) % 7
                if dias_ate_proxima_segunda == 0:
                    dias_ate_proxima_segunda = 7
                
                proxima_segunda = hoje + timedelta(days=dias_ate_proxima_segunda)
                week_start = proxima_segunda + timedelta(weeks=semana_offset)
                
                capacidade = self.calcular_capacidade_semana(specialist_name, datetime.combine(week_start, datetime.min.time()))
                
                # Analisa cada dia da semana
                for nome_dia, dia_info in capacidade['capacidade_por_dia'].items():
                    if dia_info['horas_disponiveis'] >= task_hours:
                        data_sugestao = datetime.strptime(dia_info['data'], '%Y-%m-%d').date()
                        
                        # Calcula score de prioridade
                        score = self._calcular_score_sugestao(
                            data_sugestao, hoje, dia_info, task_hours
                        )
                        
                        sugestoes.append({
                            'data': dia_info['data'],
                            'nome_dia': nome_dia,
                            'horas_disponiveis': dia_info['horas_disponiveis'],
                            'percentual_ocupacao_pos': round(
                                ((dia_info['horas_alocadas'] + task_hours) / self.HORAS_POR_DIA) * 100, 1
                            ),
                            'score': score,
                            'recomendacao': self._get_recomendacao_score(score),
                            'semana': f"Semana {semana_offset + 1}"
                        })
            
            # Ordena por score (melhor primeiro)
            sugestoes.sort(key=lambda x: x['score'], reverse=True)
            
            return sugestoes[:10]  # Retorna top 10
            
        except Exception as e:
            logger.error(f"Erro ao sugerir horários: {str(e)}")
            return []
    
    def _get_segments_semana(self, specialist_name: str, week_start: datetime, week_end: datetime) -> List[Dict]:
        """Busca segmentos de um especialista em uma semana específica"""
        try:
            # Busca tarefas do especialista
            tasks = Task.query.filter(
                Task.specialist_name.ilike(f'%{specialist_name}%')
            ).all()
            
            if not tasks:
                return []
            
            task_ids = [task.id for task in tasks]
            
            # Busca segmentos na semana
            segments = TaskSegment.query.filter(
                TaskSegment.task_id.in_(task_ids),
                TaskSegment.segment_start_datetime >= week_start,
                TaskSegment.segment_start_datetime <= week_end
            ).all()
            
            return [{
                'id': seg.id,
                'start_datetime': seg.segment_start_datetime.isoformat(),
                'estimated_hours': seg.task.estimated_effort or 0
            } for seg in segments]
            
        except Exception as e:
            logger.error(f"Erro ao buscar segmentos da semana: {str(e)}")
            return []
    
    def _mesmo_dia(self, datetime_str: str, data_referencia: datetime) -> bool:
        """Verifica se duas datas são do mesmo dia"""
        try:
            data_seg = datetime.fromisoformat(datetime_str).date()
            return data_seg == data_referencia.date()
        except:
            return False
    
    def _get_nome_dia(self, weekday: int) -> str:
        """Converte número do dia da semana para nome em português"""
        nomes = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        return nomes[weekday]
    
    def _get_status_dia(self, horas_alocadas: float) -> str:
        """Determina o status de um dia baseado nas horas alocadas"""
        if horas_alocadas > self.HORAS_POR_DIA:
            return 'sobrecarga'
        elif horas_alocadas >= self.HORAS_POR_DIA * 0.9:
            return 'quase_cheio'
        elif horas_alocadas >= self.HORAS_POR_DIA * 0.7:
            return 'bom'
        elif horas_alocadas > 0:
            return 'disponivel'
        else:
            return 'vazio'
    
    def _get_status_semana(self, total_horas: float) -> str:
        """Determina o status de uma semana baseado no total de horas"""
        if total_horas > self.HORAS_POR_SEMANA:
            return 'sobrecarga'
        elif total_horas >= self.HORAS_POR_SEMANA * 0.9:
            return 'quase_cheia'
        elif total_horas >= self.HORAS_POR_SEMANA * 0.7:
            return 'boa'
        elif total_horas > 0:
            return 'disponivel'
        else:
            return 'vazia'
    
    def _gerar_sugestoes_conflito(self, specialist_name: str, task_hours: float, 
                                target_date: datetime, capacidade: Dict) -> List[str]:
        """Gera sugestões para resolver conflitos de capacidade"""
        sugestoes = []
        
        if capacidade['resumo']['dias_sobrecarregados'] > 0:
            sugestoes.append("Redistribuir tarefas entre os dias da semana")
        
        if task_hours > self.HORAS_POR_DIA:
            sugestoes.append(f"Dividir tarefa de {task_hours}h em segmentos menores")
        
        if capacidade['resumo']['percentual_ocupacao_semana'] > 90:
            sugestoes.append("Mover tarefa para próxima semana")
        
        sugestoes.append("Verificar se outras tarefas podem ser reorganizadas")
        
        return sugestoes
    
    def _calcular_score_sugestao(self, data_sugestao: datetime, hoje: datetime, 
                                dia_info: Dict, task_hours: float) -> float:
        """Calcula score de prioridade para uma sugestão de horário"""
        score = 100.0
        
        # Penaliza datas muito distantes
        dias_diferenca = (data_sugestao - hoje).days
        if dias_diferenca > 7:
            score -= dias_diferenca * 2
        
        # Favorece dias com mais espaço disponível
        percentual_livre = (dia_info['horas_disponiveis'] / self.HORAS_POR_DIA) * 100
        score += percentual_livre * 0.5
        
        # Penaliza se vai deixar o dia muito cheio
        ocupacao_pos = ((dia_info['horas_alocadas'] + task_hours) / self.HORAS_POR_DIA) * 100
        if ocupacao_pos > 90:
            score -= 20
        
        return max(score, 0)
    
    def _get_recomendacao_score(self, score: float) -> str:
        """Converte score em recomendação textual"""
        if score >= 90:
            return 'Excelente'
        elif score >= 70:
            return 'Boa'
        elif score >= 50:
            return 'Aceitável'
        else:
            return 'Não recomendado'
    
    def _get_capacidade_vazia(self, specialist_name: str, week_start: datetime) -> Dict:
        """Retorna estrutura vazia de capacidade em caso de erro"""
        return {
            'specialist_name': specialist_name,
            'week_start': week_start.strftime('%Y-%m-%d'),
            'capacidade_por_dia': {},
            'resumo': {
                'total_horas_semana': 0,
                'total_horas_disponiveis': self.HORAS_POR_SEMANA,
                'percentual_ocupacao_semana': 0,
                'dias_sobrecarregados': 0,
                'status_semana': 'vazia'
            },
            'erro': True
        }
    
    def calcular_capacidade_sprint(self, sprint_id: int, specialist_name: str = None) -> Dict:
        """
        Calcula a capacidade total disponível para uma sprint baseada na sua duração
        
        Args:
            sprint_id: ID da sprint
            specialist_name: Nome do especialista (opcional, para cálculo individual)
            
        Returns:
            Dict com informações de capacidade da sprint
        """
        try:
            # Busca a sprint
            sprint = Sprint.query.get(sprint_id)
            if not sprint:
                return {'erro': 'Sprint não encontrada'}
            
            # Calcula duração em semanas
            if sprint.start_date and sprint.end_date:
                duration_days = (sprint.end_date - sprint.start_date).days + 1
                weeks = max(1, duration_days // 7)  # Mínimo de 1 semana, divide por 7 dias
                if duration_days % 7 > 0:  # Se sobrar dias, conta como semana extra
                    weeks += 1
            else:
                weeks = 1  # Default 1 semana se não tiver datas
            
            # Capacidade total por especialista para esta sprint
            capacidade_total_por_especialista = self.HORAS_POR_SEMANA * weeks
            
            result = {
                'sprint_id': sprint_id,
                'sprint_name': sprint.name,
                'start_date': sprint.start_date.strftime('%Y-%m-%d') if sprint.start_date else None,
                'end_date': sprint.end_date.strftime('%Y-%m-%d') if sprint.end_date else None,
                'duration_weeks': weeks,
                'duration_days': duration_days if sprint.start_date and sprint.end_date else 7,
                'capacidade_semanal': self.HORAS_POR_SEMANA,
                'capacidade_total_por_especialista': capacidade_total_por_especialista
            }
            
            if specialist_name:
                # Cálculo para um especialista específico
                tasks_specialist = Task.query.filter(
                    Task.sprint_id == sprint_id,
                    Task.specialist_name.ilike(f'%{specialist_name}%')
                ).all()
                
                horas_alocadas = sum(task.estimated_effort or 0 for task in tasks_specialist)
                horas_restantes = capacidade_total_por_especialista - horas_alocadas
                percentual_utilizacao = (horas_alocadas / capacidade_total_por_especialista) * 100
                
                result.update({
                    'specialist_name': specialist_name,
                    'horas_alocadas': round(horas_alocadas, 1),
                    'horas_restantes': round(horas_restantes, 1),
                    'percentual_utilizacao': round(percentual_utilizacao, 1),
                    'status': self._get_status_capacidade_sprint(percentual_utilizacao),
                    'sobrecarga': percentual_utilizacao > 100
                })
            else:
                # Cálculo geral da sprint
                all_tasks = Task.query.filter(Task.sprint_id == sprint_id).all()
                specialists = {}
                
                for task in all_tasks:
                    specialist = task.specialist_name or 'Não Atribuído'
                    if specialist not in specialists:
                        specialists[specialist] = {
                            'horas_alocadas': 0,
                            'total_tasks': 0
                        }
                    
                    specialists[specialist]['horas_alocadas'] += task.estimated_effort or 0
                    specialists[specialist]['total_tasks'] += 1
                
                # Calcula métricas para cada especialista
                specialist_details = {}
                for spec_name, data in specialists.items():
                    if spec_name != 'Não Atribuído':
                        horas_alocadas = data['horas_alocadas']
                        horas_restantes = capacidade_total_por_especialista - horas_alocadas
                        percentual_utilizacao = (horas_alocadas / capacidade_total_por_especialista) * 100
                        
                        specialist_details[spec_name] = {
                            'horas_alocadas': round(horas_alocadas, 1),
                            'horas_restantes': round(horas_restantes, 1),
                            'percentual_utilizacao': round(percentual_utilizacao, 1),
                            'total_tasks': data['total_tasks'],
                            'status': self._get_status_capacidade_sprint(percentual_utilizacao),
                            'sobrecarga': percentual_utilizacao > 100
                        }
                
                result.update({
                    'total_specialists': len([s for s in specialists.keys() if s != 'Não Atribuído']),
                    'total_tasks': len(all_tasks),
                    'specialist_details': specialist_details
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Erro ao calcular capacidade da sprint: {str(e)}")
            return {'erro': str(e)}
    
    def _get_status_capacidade_sprint(self, percentual_utilizacao: float) -> str:
        """Retorna status baseado no percentual de utilização da capacidade"""
        if percentual_utilizacao > 100:
            return 'Sobrecarga'
        elif percentual_utilizacao > 90:
            return 'Limite'
        elif percentual_utilizacao > 70:
            return 'Ideal'
        elif percentual_utilizacao > 40:
            return 'Confortável'
        else:
            return 'Subutilizado' 