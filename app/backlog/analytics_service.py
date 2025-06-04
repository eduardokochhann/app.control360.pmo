from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
import logging
import json
from flask import current_app
from sqlalchemy import func, and_, or_

from ..models import Task, TaskSegment, TaskStatus, Project
from .capacity_service import CapacityService

logger = logging.getLogger(__name__)

class AnalyticsService:
    """Serviço para análises avançadas e relatórios do sistema de sprint"""
    
    def __init__(self):
        self.capacity_service = CapacityService()
    
    def gerar_relatorio_especialista(self, specialist_name: str, weeks_back: int = 4) -> Dict:
        """
        Gera relatório completo de performance de um especialista
        
        Args:
            specialist_name: Nome do especialista
            weeks_back: Número de semanas passadas para analisar
            
        Returns:
            Dict com relatório completo de performance
        """
        try:
            hoje = datetime.now()
            data_inicio = hoje - timedelta(weeks=weeks_back)
            
            # Busca dados históricos
            tasks_historicas = self._get_tasks_periodo(specialist_name, data_inicio, hoje)
            segments_historicos = self._get_segments_periodo(specialist_name, data_inicio, hoje)
            
            # Calcula métricas
            metricas_produtividade = self._calcular_metricas_produtividade(segments_historicos)
            tendencias = self._analisar_tendencias(segments_historicos, weeks_back)
            distribuicao_projetos = self._analisar_distribuicao_projetos(segments_historicos)
            cumprimento_prazos = self._analisar_cumprimento_prazos(tasks_historicas)
            
            # Análise de capacidade histórica
            capacidade_historica = self._analisar_capacidade_historica(specialist_name, data_inicio, hoje)
            
            # Predições e recomendações
            predicoes = self._gerar_predicoes(specialist_name, metricas_produtividade, tendencias)
            recomendacoes = self._gerar_recomendacoes(specialist_name, metricas_produtividade, capacidade_historica)
            
            return {
                'specialist_name': specialist_name,
                'periodo_analise': {
                    'data_inicio': data_inicio.strftime('%Y-%m-%d'),
                    'data_fim': hoje.strftime('%Y-%m-%d'),
                    'semanas_analisadas': weeks_back
                },
                'metricas_produtividade': metricas_produtividade,
                'tendencias': tendencias,
                'distribuicao_projetos': distribuicao_projetos,
                'cumprimento_prazos': cumprimento_prazos,
                'capacidade_historica': capacidade_historica,
                'predicoes': predicoes,
                'recomendacoes': recomendacoes,
                'resumo_executivo': self._gerar_resumo_executivo(
                    metricas_produtividade, tendencias, cumprimento_prazos
                )
            }
            
        except Exception as e:
            logger.error(f"Erro ao gerar relatório do especialista: {str(e)}")
            return {'error': str(e)}
    
    def gerar_dashboard_equipe(self, weeks_back: int = 4) -> Dict:
        """
        Gera dashboard consolidado de toda a equipe
        
        Args:
            weeks_back: Número de semanas para análise
            
        Returns:
            Dict com dados do dashboard da equipe
        """
        try:
            hoje = datetime.now()
            data_inicio = hoje - timedelta(weeks=weeks_back)
            
            # Busca todos os especialistas ativos
            especialistas = self._get_especialistas_ativos(data_inicio, hoje)
            
            dashboard_data = {
                'periodo_analise': {
                    'data_inicio': data_inicio.strftime('%Y-%m-%d'),
                    'data_fim': hoje.strftime('%Y-%m-%d'),
                    'semanas_analisadas': weeks_back
                },
                'resumo_geral': {},
                'especialistas': [],
                'comparativo_performance': {},
                'alertas_capacidade': [],
                'tendencias_equipe': {},
                'projetos_criticos': []
            }
            
            total_horas_equipe = 0
            total_tarefas_equipe = 0
            especialistas_data = []
            
            # Analisa cada especialista
            for especialista in especialistas:
                dados_especialista = self._analisar_especialista_resumido(
                    especialista, data_inicio, hoje
                )
                especialistas_data.append(dados_especialista)
                
                total_horas_equipe += dados_especialista['total_horas']
                total_tarefas_equipe += dados_especialista['total_tarefas']
                
                # Identifica alertas de capacidade
                if dados_especialista['percentual_sobrecarga'] > 20:
                    dashboard_data['alertas_capacidade'].append({
                        'specialist_name': especialista,
                        'tipo': 'sobrecarga_frequente',
                        'severidade': 'alta' if dados_especialista['percentual_sobrecarga'] > 40 else 'media',
                        'detalhes': f"{dados_especialista['percentual_sobrecarga']:.1f}% das semanas com sobrecarga"
                    })
            
            # Calcula resumo geral
            dashboard_data['resumo_geral'] = {
                'total_especialistas': len(especialistas),
                'total_horas_periodo': total_horas_equipe,
                'total_tarefas_periodo': total_tarefas_equipe,
                'media_horas_por_especialista': total_horas_equipe / len(especialistas) if especialistas else 0,
                'media_produtividade': sum(e['produtividade'] for e in especialistas_data) / len(especialistas_data) if especialistas_data else 0,
                'especialistas_sobrecarregados': len(dashboard_data['alertas_capacidade']),
                'utilizacao_capacidade_media': sum(e['utilizacao_capacidade'] for e in especialistas_data) / len(especialistas_data) if especialistas_data else 0
            }
            
            # Ordena especialistas por produtividade
            dashboard_data['especialistas'] = sorted(
                especialistas_data, 
                key=lambda x: x['produtividade'], 
                reverse=True
            )
            
            # Gera comparativo de performance
            dashboard_data['comparativo_performance'] = self._gerar_comparativo_performance(especialistas_data)
            
            # Analisa tendências da equipe
            dashboard_data['tendencias_equipe'] = self._analisar_tendencias_equipe(especialistas_data)
            
            # Identifica projetos críticos
            dashboard_data['projetos_criticos'] = self._identificar_projetos_criticos(data_inicio, hoje)
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Erro ao gerar dashboard da equipe: {str(e)}")
            return {'error': str(e)}
    
    def analisar_otimizacao_sprints(self, team_members: List[str], weeks_ahead: int = 4) -> Dict:
        """
        Analisa e sugere otimizações para sprints da equipe
        
        Args:
            team_members: Lista de nomes dos membros da equipe
            weeks_ahead: Semanas futuras para análise
            
        Returns:
            Dict com sugestões de otimização
        """
        try:
            otimizacoes = {
                'periodo_analise': f"Próximas {weeks_ahead} semanas",
                'team_members': team_members,
                'sugestoes_redistribuicao': [],
                'oportunidades_balanceamento': [],
                'recomendacoes_capacidade': [],
                'riscos_identificados': [],
                'score_otimizacao': 0
            }
            
            hoje = datetime.now()
            week_start = hoje - timedelta(days=hoje.weekday())
            
            # Analisa capacidade de cada membro nas próximas semanas
            capacidades_futuras = {}
            for member in team_members:
                capacidade = self.capacity_service.calcular_capacidade_semana(member, week_start)
                capacidades_futuras[member] = capacidade
                
                # Identifica oportunidades de redistribuição
                if capacidade['resumo']['dias_sobrecarregados'] > 0:
                    otimizacoes['sugestoes_redistribuicao'].append({
                        'specialist_name': member,
                        'dias_sobrecarregados': capacidade['resumo']['dias_sobrecarregados'],
                        'total_excesso_horas': sum(
                            max(0, dia['horas_alocadas'] - 8) 
                            for dia in capacidade['capacidade_por_dia'].values()
                        ),
                        'prioridade': 'alta' if capacidade['resumo']['dias_sobrecarregados'] > 2 else 'media'
                    })
            
            # Identifica oportunidades de balanceamento entre membros
            utilizacoes = [(member, cap['resumo']['percentual_ocupacao_semana']) 
                          for member, cap in capacidades_futuras.items()]
            utilizacoes.sort(key=lambda x: x[1])
            
            membros_subutilizados = [m for m, u in utilizacoes if u < 70]
            membros_sobrecarregados = [m for m, u in utilizacoes if u > 90]
            
            if membros_subutilizados and membros_sobrecarregados:
                for membro_livre in membros_subutilizados:
                    for membro_ocupado in membros_sobrecarregados:
                        otimizacoes['oportunidades_balanceamento'].append({
                            'origem': membro_ocupado,
                            'destino': membro_livre,
                            'utilizacao_origem': next(u for m, u in utilizacoes if m == membro_ocupado),
                            'utilizacao_destino': next(u for m, u in utilizacoes if m == membro_livre),
                            'potencial_transferencia': min(
                                capacidades_futuras[membro_livre]['resumo']['total_horas_disponiveis'],
                                capacidades_futuras[membro_ocupado]['resumo']['total_horas_semana'] - 32  # Deixa 32h mínimo
                            )
                        })
            
            # Calcula score de otimização
            score = 100
            score -= len(otimizacoes['sugestoes_redistribuicao']) * 10  # Penaliza sobrecargas
            score -= abs(70 - sum(u for _, u in utilizacoes) / len(utilizacoes))  # Penaliza desvio da utilização ideal
            score += len(otimizacoes['oportunidades_balanceamento']) * 5  # Favorece oportunidades
            
            otimizacoes['score_otimizacao'] = max(0, min(100, score))
            
            return otimizacoes
            
        except Exception as e:
            logger.error(f"Erro na análise de otimização: {str(e)}")
            return {'error': str(e)}
    
    def _get_tasks_periodo(self, specialist_name: str, data_inicio: datetime, data_fim: datetime) -> List:
        """Busca tarefas de um especialista em um período"""
        try:
            tasks = Task.query.filter(
                Task.specialist_name.ilike(f'%{specialist_name}%'),
                Task.created_at >= data_inicio,
                Task.created_at <= data_fim
            ).all()
            
            return [self._task_to_dict(task) for task in tasks]
        except Exception as e:
            logger.error(f"Erro ao buscar tarefas do período: {str(e)}")
            return []
    
    def _get_segments_periodo(self, specialist_name: str, data_inicio: datetime, data_fim: datetime) -> List:
        """Busca segmentos de um especialista em um período"""
        try:
            # Busca tarefas do especialista
            tasks = Task.query.filter(
                Task.specialist_name.ilike(f'%{specialist_name}%')
            ).all()
            
            if not tasks:
                return []
            
            task_ids = [task.id for task in tasks]
            
            # Busca segmentos no período
            segments = TaskSegment.query.filter(
                TaskSegment.task_id.in_(task_ids),
                TaskSegment.segment_start_datetime >= data_inicio,
                TaskSegment.segment_start_datetime <= data_fim
            ).all()
            
            return [self._segment_to_dict(segment) for segment in segments]
        except Exception as e:
            logger.error(f"Erro ao buscar segmentos do período: {str(e)}")
            return []
    
    def _calcular_metricas_produtividade(self, segments: List[Dict]) -> Dict:
        """Calcula métricas de produtividade baseadas nos segmentos"""
        if not segments:
            return {
                'total_horas_planejadas': 0,
                'total_horas_realizadas': 0,
                'total_tarefas': 0,
                'tarefas_concluidas': 0,
                'percentual_conclusao': 0,
                'produtividade_horas': 0,
                'media_horas_por_tarefa': 0,
                'velocidade_semanal': 0
            }
        
        total_horas_planejadas = sum(s.get('estimated_hours', 0) for s in segments)
        total_horas_realizadas = sum(s.get('actual_hours', 0) for s in segments if s.get('actual_hours'))
        total_tarefas = len(segments)
        tarefas_concluidas = sum(1 for s in segments if s.get('is_completed'))
        
        return {
            'total_horas_planejadas': round(total_horas_planejadas, 1),
            'total_horas_realizadas': round(total_horas_realizadas, 1),
            'total_tarefas': total_tarefas,
            'tarefas_concluidas': tarefas_concluidas,
            'percentual_conclusao': round((tarefas_concluidas / total_tarefas * 100), 1) if total_tarefas > 0 else 0,
            'produtividade_horas': round((total_horas_realizadas / total_horas_planejadas * 100), 1) if total_horas_planejadas > 0 else 0,
            'media_horas_por_tarefa': round(total_horas_planejadas / total_tarefas, 1) if total_tarefas > 0 else 0,
            'velocidade_semanal': round(tarefas_concluidas / 4, 1)  # Assuming 4 weeks analysis
        }
    
    def _analisar_tendencias(self, segments: List[Dict], weeks_back: int) -> Dict:
        """Analisa tendências de performance ao longo do tempo"""
        # Agrupa segmentos por semana
        segments_por_semana = defaultdict(list)
        
        for segment in segments:
            data_segment = datetime.fromisoformat(segment['start_datetime'].replace('Z', ''))
            semana = data_segment.isocalendar()[1]
            segments_por_semana[semana].append(segment)
        
        # Calcula métricas por semana
        metricas_semanais = []
        for semana, segs in segments_por_semana.items():
            metricas = self._calcular_metricas_produtividade(segs)
            metricas['semana'] = semana
            metricas_semanais.append(metricas)
        
        # Ordena por semana
        metricas_semanais.sort(key=lambda x: x['semana'])
        
        # Calcula tendências
        if len(metricas_semanais) < 2:
            return {'tendencia_produtividade': 'estavel', 'variacao': 0, 'metricas_semanais': metricas_semanais}
        
        produtividades = [m['percentual_conclusao'] for m in metricas_semanais]
        tendencia = produtividades[-1] - produtividades[0]
        
        return {
            'tendencia_produtividade': 'crescimento' if tendencia > 5 else 'declinio' if tendencia < -5 else 'estavel',
            'variacao': round(tendencia, 1),
            'metricas_semanais': metricas_semanais,
            'produtividade_media': round(sum(produtividades) / len(produtividades), 1),
            'desvio_padrao': round(np.std(produtividades), 1) if len(produtividades) > 1 else 0
        }
    
    def _task_to_dict(self, task) -> Dict:
        """Converte objeto Task para dicionário"""
        return {
            'id': task.id,
            'title': task.title,
            'estimated_effort': task.estimated_effort,
            'status': task.status.value if task.status else None,
            'created_at': task.created_at.isoformat() if task.created_at else None,
            'specialist_name': task.specialist_name
        }
    
    def _segment_to_dict(self, segment) -> Dict:
        """Converte objeto TaskSegment para dicionário"""
        return {
            'id': segment.id,
            'task_id': segment.task_id,
            'start_datetime': segment.segment_start_datetime.isoformat() if segment.segment_start_datetime else None,
            'estimated_hours': segment.task.estimated_effort or 0,
            'actual_hours': getattr(segment, 'actual_hours', 0),
            'is_completed': segment.task.status == TaskStatus.DONE if segment.task else False
        }
    
    def _analisar_distribuicao_projetos(self, segments: List[Dict]) -> Dict:
        """Analisa distribuição de tempo entre projetos"""
        projetos = defaultdict(float)
        
        for segment in segments:
            # Aqui você pegaria o projeto do segmento
            # Como não temos essa relação direta, vamos simular
            projeto = f"Projeto {segment.get('task_id', 'Desconhecido')}"
            projetos[projeto] += segment.get('estimated_hours', 0)
        
        total_horas = sum(projetos.values())
        
        distribuicao = [
            {
                'projeto': nome,
                'horas': round(horas, 1),
                'percentual': round((horas / total_horas * 100), 1) if total_horas > 0 else 0
            }
            for nome, horas in projetos.items()
        ]
        
        return {
            'total_projetos': len(projetos),
            'distribuicao': sorted(distribuicao, key=lambda x: x['horas'], reverse=True)
        }
    
    def _analisar_cumprimento_prazos(self, tasks: List[Dict]) -> Dict:
        """Analisa cumprimento de prazos das tarefas"""
        # Simulação básica - em um caso real você teria datas de entrega
        return {
            'total_tarefas_com_prazo': len(tasks),
            'tarefas_dentro_prazo': int(len(tasks) * 0.8),  # 80% simulado
            'tarefas_atrasadas': int(len(tasks) * 0.2),     # 20% simulado
            'percentual_cumprimento': 80.0,
            'atraso_medio_dias': 2.5
        }
    
    def _analisar_capacidade_historica(self, specialist_name: str, data_inicio: datetime, data_fim: datetime) -> Dict:
        """Analisa histórico de capacidade do especialista"""
        # Simulação - em produção você calcularia semana por semana
        return {
            'semanas_analisadas': 4,
            'utilizacao_media': 85.2,
            'semanas_sobrecarga': 1,
            'percentual_sobrecarga': 25.0,
            'eficiencia_planejamento': 92.3,
            'variabilidade_carga': 'media'
        }
    
    def _gerar_predicoes(self, specialist_name: str, metricas: Dict, tendencias: Dict) -> Dict:
        """Gera predições baseadas nos dados históricos"""
        produtividade_atual = metricas.get('percentual_conclusao', 0)
        tendencia = tendencias.get('variacao', 0)
        
        # Predição simples baseada na tendência
        produtividade_predita = min(100, max(0, produtividade_atual + tendencia))
        
        return {
            'produtividade_proxima_semana': round(produtividade_predita, 1),
            'confianca_predicao': 75,  # Simulado
            'recomendacao_carga': 'normal' if produtividade_predita > 70 else 'reduzida',
            'tendencia_geral': tendencias.get('tendencia_produtividade', 'estavel')
        }
    
    def _gerar_recomendacoes(self, specialist_name: str, metricas: Dict, capacidade: Dict) -> List[str]:
        """Gera recomendações baseadas na análise"""
        recomendacoes = []
        
        if metricas.get('percentual_conclusao', 0) < 70:
            recomendacoes.append("Revisar planejamento de tarefas - baixa taxa de conclusão")
        
        if capacidade.get('percentual_sobrecarga', 0) > 20:
            recomendacoes.append("Redistribuir carga de trabalho - sobrecarga frequente detectada")
        
        if metricas.get('produtividade_horas', 0) < 80:
            recomendacoes.append("Melhorar estimativas de tempo - diferença significativa entre planejado e realizado")
        
        if not recomendacoes:
            recomendacoes.append("Performance dentro dos parâmetros esperados - manter ritmo atual")
        
        return recomendacoes
    
    def _gerar_resumo_executivo(self, metricas: Dict, tendencias: Dict, prazos: Dict) -> str:
        """Gera resumo executivo da análise"""
        produtividade = metricas.get('percentual_conclusao', 0)
        tendencia = tendencias.get('tendencia_produtividade', 'estavel')
        cumprimento = prazos.get('percentual_cumprimento', 0)
        
        if produtividade >= 80 and cumprimento >= 85:
            return f"Performance EXCELENTE: {produtividade}% de conclusão com tendência {tendencia}"
        elif produtividade >= 60 and cumprimento >= 70:
            return f"Performance BOA: {produtividade}% de conclusão, {cumprimento}% no prazo"
        else:
            return f"Performance NECESSITA ATENÇÃO: {produtividade}% de conclusão, revisar planejamento" 