"""
Serviço para gestão de fases de projetos (Waterfall/Ágil)
Gerencia transições automáticas, marcos e configurações de fases
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from flask import current_app

from .. import db
from ..models import (
    Backlog, ProjectMilestone, ProjectPhaseConfiguration, 
    ProjectType, MilestoneStatus, PhaseStatus,
    get_brasilia_now
)

logger = logging.getLogger(__name__)

class ProjectPhaseService:
    """Serviço para gerenciar fases de projetos e transições automáticas"""
    
    def __init__(self):
        self.logger = logger

    def get_project_type(self, project_id: str) -> Optional[ProjectType]:
        """Retorna o tipo do projeto (Waterfall/Ágil)"""
        try:
            backlog = Backlog.query.filter_by(project_id=project_id).first()
            return backlog.project_type if backlog else None
        except Exception as e:
            self.logger.error(f"Erro ao obter tipo do projeto {project_id}: {e}")
            return None

    def set_project_type(self, project_id: str, project_type: ProjectType) -> bool:
        """Define o tipo do projeto e inicializa as fases"""
        try:
            backlog = Backlog.query.filter_by(project_id=project_id).first()
            if not backlog:
                self.logger.error(f"Backlog não encontrado para projeto {project_id}")
                return False

            # Define o tipo
            backlog.project_type = project_type
            
            # Cria marcos automáticos se necessário
            self.create_automatic_milestones(project_id, project_type)
            
            # ✅ DETECÇÃO INTELIGENTE DE FASE ATUAL
            detected_phase = self.detect_current_phase_from_milestones(project_id, project_type)
            backlog.current_phase = detected_phase
            backlog.phase_started_at = get_brasilia_now()
            
            db.session.commit()
            self.logger.info(f"Projeto {project_id} configurado como {project_type.value}, fase detectada: {detected_phase}")
            return True
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao definir tipo do projeto {project_id}: {e}")
            return False

    def detect_current_phase_from_milestones(self, project_id: str, project_type: ProjectType) -> int:
        """Detecta a fase atual baseada no status dos marcos existentes"""
        try:
            backlog = Backlog.query.filter_by(project_id=project_id).first()
            if not backlog:
                return 1

            # Busca todas as fases do tipo de projeto (ordenadas por número)
            phases = ProjectPhaseConfiguration.query.filter_by(
                project_type=project_type,
                is_active=True
            ).order_by(ProjectPhaseConfiguration.phase_number).all()

            if not phases:
                return 1

            # Busca todos os marcos do projeto
            milestones = ProjectMilestone.query.filter_by(backlog_id=backlog.id).all()
            
            current_phase = 1  # Fase padrão

            for phase in phases:
                phase_milestone_names = phase.get_milestone_names()
                if not phase_milestone_names:
                    continue

                # Verifica status dos marcos desta fase
                phase_milestones = [m for m in milestones if m.name in phase_milestone_names]
                
                if not phase_milestones:
                    # Se não há marcos para esta fase, assumimos que ainda não chegamos aqui
                    break

                # Conta marcos concluídos, em andamento e pendentes
                completed_count = sum(1 for m in phase_milestones 
                                    if m.status == MilestoneStatus.COMPLETED)
                in_progress_count = sum(1 for m in phase_milestones 
                                      if m.status == MilestoneStatus.IN_PROGRESS)
                
                total_milestones = len(phase_milestones)

                # Lógica de detecção de fase:
                if completed_count == total_milestones:
                    # Todos os marcos desta fase estão concluídos
                    # Verificar se há próxima fase
                    next_phase = phase.phase_number + 1
                    next_phase_config = next((p for p in phases if p.phase_number == next_phase), None)
                    
                    if next_phase_config:
                        current_phase = next_phase  # Avançou para próxima fase
                    else:
                        current_phase = phase.phase_number  # Última fase
                        
                elif completed_count > 0 or in_progress_count > 0:
                    # Há marcos concluídos ou em andamento nesta fase
                    current_phase = phase.phase_number
                    break  # Para aqui, encontrou a fase atual
                else:
                    # Nenhum marco concluído ou em andamento
                    # Se é a primeira fase, assumimos que estamos nela
                    if phase.phase_number == 1:
                        current_phase = 1
                    break

            self.logger.info(f"Fase detectada para projeto {project_id}: {current_phase}")
            return current_phase

        except Exception as e:
            self.logger.error(f"Erro ao detectar fase atual do projeto {project_id}: {e}")
            return 1  # Retorna fase 1 em caso de erro

    def get_current_phase_info(self, project_id: str) -> Dict:
        """Retorna informações da fase atual do projeto"""
        try:
            backlog = Backlog.query.filter_by(project_id=project_id).first()
            if not backlog or not backlog.project_type:
                return {'error': 'Projeto não encontrado ou tipo não definido'}

            # Busca configuração da fase atual
            phase_config = ProjectPhaseConfiguration.query.filter_by(
                project_type=backlog.project_type,
                phase_number=backlog.current_phase,
                is_active=True
            ).first()

            if not phase_config:
                return {'error': f'Configuração da fase {backlog.current_phase} não encontrada'}

            # Busca próxima fase
            next_phase_config = ProjectPhaseConfiguration.query.filter_by(
                project_type=backlog.project_type,
                phase_number=backlog.current_phase + 1,
                is_active=True
            ).first()

            # ✅ CALCULA DATAS DE INÍCIO E CONCLUSÃO DA FASE ATUAL
            phase_dates = self.calculate_phase_dates(project_id, backlog.current_phase)

            return {
                'project_id': project_id,
                'project_type': backlog.project_type.value,
                'current_phase': {
                    'number': backlog.current_phase,
                    'name': phase_config.phase_name,
                    'description': phase_config.phase_description,
                    'color': phase_config.phase_color,
                    'started_at': phase_dates.get('started_at'),
                    'completed_at': phase_dates.get('completed_at'),
                    'planned_completion': phase_dates.get('planned_completion'),
                    'is_delayed': phase_dates.get('is_delayed', False),
                    'milestone_names': phase_config.get_milestone_names(),
                    'status': phase_dates.get('status', 'pending')
                },
                'next_phase': {
                    'number': next_phase_config.phase_number,
                    'name': next_phase_config.phase_name,
                    'color': next_phase_config.phase_color
                } if next_phase_config else None,
                'total_phases': self.get_total_phases(backlog.project_type)
            }

        except Exception as e:
            self.logger.error(f"Erro ao obter informações da fase do projeto {project_id}: {e}")
            return {'error': f'Erro interno: {str(e)}'}

    def calculate_phase_dates(self, project_id: str, phase_number: int) -> Dict:
        """Calcula as datas de início e conclusão de uma fase baseado nos marcos"""
        try:
            backlog = Backlog.query.filter_by(project_id=project_id).first()
            if not backlog:
                return {}

            # Busca configuração da fase
            phase_config = ProjectPhaseConfiguration.query.filter_by(
                project_type=backlog.project_type,
                phase_number=phase_number,
                is_active=True
            ).first()

            if not phase_config:
                return {}

            # Busca marcos desta fase
            milestone_names = phase_config.get_milestone_names()
            if not milestone_names:
                return {'status': 'not_started'}

            milestones = ProjectMilestone.query.filter(
                ProjectMilestone.backlog_id == backlog.id,
                ProjectMilestone.name.in_(milestone_names)
            ).all()

            if not milestones:
                return {'status': 'not_started'}

            # Calcula datas baseado nos marcos
            started_dates = [m.started_at for m in milestones if m.started_at]
            completed_dates = [m.actual_date for m in milestones if m.actual_date]
            planned_dates = [m.planned_date for m in milestones if m.planned_date]

            # Data de início da fase: menor data de início dos marcos
            started_at = min(started_dates) if started_dates else None
            
            # Data de conclusão da fase: maior data de conclusão dos marcos (se todos concluídos)
            completed_at = None
            all_completed = all(m.status == MilestoneStatus.COMPLETED for m in milestones)
            if all_completed and completed_dates:
                completed_at = max(completed_dates)

            # Data planejada de conclusão: maior data planejada dos marcos
            planned_completion = max(planned_dates) if planned_dates else None

            # Determina status da fase
            if completed_at:
                status = 'completed'
            elif started_at:
                status = 'in_progress'
            else:
                status = 'not_started'

            # Verifica se está atrasada
            is_delayed = False
            if planned_completion and not completed_at:
                is_delayed = planned_completion < get_brasilia_now().date()

            return {
                'started_at': started_at.isoformat() if started_at else None,
                'completed_at': completed_at.isoformat() if completed_at else None,
                'planned_completion': planned_completion.isoformat() if planned_completion else None,
                'is_delayed': is_delayed,
                'status': status,
                'milestones_count': len(milestones),
                'completed_milestones': len([m for m in milestones if m.status == MilestoneStatus.COMPLETED])
            }

        except Exception as e:
            self.logger.error(f"Erro ao calcular datas da fase {phase_number} do projeto {project_id}: {e}")
            return {}

    def get_total_phases(self, project_type: ProjectType) -> int:
        """Retorna o número total de fases para um tipo de projeto"""
        try:
            return ProjectPhaseConfiguration.query.filter_by(
                project_type=project_type,
                is_active=True
            ).count()
        except:
            return 0

    def can_advance_to_next_phase(self, project_id: str) -> Tuple[bool, str]:
        """Verifica se o projeto pode avançar para a próxima fase"""
        try:
            backlog = Backlog.query.filter_by(project_id=project_id).first()
            if not backlog or not backlog.project_type:
                return False, "Projeto não encontrado ou tipo não definido"

            # Busca marcos da fase atual que disparam próxima fase
            current_phase_config = ProjectPhaseConfiguration.query.filter_by(
                project_type=backlog.project_type,
                phase_number=backlog.current_phase,
                is_active=True
            ).first()

            if not current_phase_config:
                return False, f"Configuração da fase {backlog.current_phase} não encontrada"

            # Verifica se existem marcos gatilho concluídos
            milestone_names = current_phase_config.get_milestone_names()
            if not milestone_names:
                return True, "Fase sem marcos obrigatórios"

            completed_milestones = ProjectMilestone.query.filter(
                ProjectMilestone.backlog_id == backlog.id,
                ProjectMilestone.name.in_(milestone_names),
                ProjectMilestone.status == MilestoneStatus.COMPLETED,
                ProjectMilestone.triggers_next_phase == True
            ).count()

            trigger_milestones = ProjectMilestone.query.filter(
                ProjectMilestone.backlog_id == backlog.id,
                ProjectMilestone.name.in_(milestone_names),
                ProjectMilestone.triggers_next_phase == True
            ).count()

            if trigger_milestones == 0:
                return True, "Nenhum marco configurado como gatilho"

            if completed_milestones >= trigger_milestones:
                return True, "Todos os marcos gatilho foram concluídos"
            else:
                return False, f"Aguardando conclusão de marcos: {trigger_milestones - completed_milestones} pendentes"

        except Exception as e:
            self.logger.error(f"Erro ao verificar avanço de fase do projeto {project_id}: {e}")
            return False, f"Erro interno: {str(e)}"

    def advance_to_next_phase(self, project_id: str) -> Tuple[bool, str]:
        """Avança o projeto para a próxima fase"""
        try:
            can_advance, message = self.can_advance_to_next_phase(project_id)
            if not can_advance:
                return False, f"Não é possível avançar: {message}"

            backlog = Backlog.query.filter_by(project_id=project_id).first()
            if not backlog:
                return False, "Projeto não encontrado"

            # Verifica se existe próxima fase
            next_phase = backlog.current_phase + 1
            next_phase_config = ProjectPhaseConfiguration.query.filter_by(
                project_type=backlog.project_type,
                phase_number=next_phase,
                is_active=True
            ).first()

            if not next_phase_config:
                return False, "Projeto já está na última fase"

            # Avança para próxima fase
            old_phase = backlog.current_phase
            backlog.current_phase = next_phase
            backlog.phase_started_at = get_brasilia_now()

            # Cria marcos automáticos da nova fase se necessário
            self.create_phase_milestones(project_id, next_phase_config)

            db.session.commit()
            
            self.logger.info(f"Projeto {project_id} avançou da fase {old_phase} para {next_phase}")
            return True, f"Projeto avançou para fase {next_phase}: {next_phase_config.phase_name}"

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao avançar fase do projeto {project_id}: {e}")
            return False, f"Erro interno: {str(e)}"

    def create_automatic_milestones(self, project_id: str, project_type: ProjectType) -> bool:
        """Cria marcos automáticos para todas as fases do projeto"""
        try:
            backlog = Backlog.query.filter_by(project_id=project_id).first()
            if not backlog:
                return False

            # Busca todas as fases do tipo de projeto
            phases = ProjectPhaseConfiguration.get_phases_for_type(project_type)
            
            for phase in phases:
                self.create_phase_milestones(project_id, phase)

            self.logger.info(f"Marcos automáticos criados para projeto {project_id} ({project_type.value})")
            return True

        except Exception as e:
            self.logger.error(f"Erro ao criar marcos automáticos para projeto {project_id}: {e}")
            return False

    def create_phase_milestones(self, project_id: str, phase_config: ProjectPhaseConfiguration) -> bool:
        """Cria marcos para uma fase específica"""
        try:
            backlog = Backlog.query.filter_by(project_id=project_id).first()
            if not backlog:
                return False

            milestone_names = phase_config.get_milestone_names()
            if not milestone_names:
                return True

            for i, milestone_name in enumerate(milestone_names):
                # Verifica se marco já existe
                existing = ProjectMilestone.query.filter_by(
                    backlog_id=backlog.id,
                    name=milestone_name
                ).first()

                if existing:
                    # ✅ ATUALIZA MARCO EXISTENTE para ser gatilho
                    existing.triggers_next_phase = True
                    existing.phase_order = phase_config.phase_number
                    existing.auto_created = False  # Mantém como não auto-criado se já existia
                    self.logger.info(f"Marco existente '{milestone_name}' configurado como gatilho da fase {phase_config.phase_number}")
                else:
                    # Cria novo marco
                    milestone = ProjectMilestone(
                        name=milestone_name,
                        description=f"Marco automático da fase: {phase_config.phase_name}",
                        planned_date=get_brasilia_now().date(),  # Data planejada padrão (pode ser ajustada)
                        backlog_id=backlog.id,
                        triggers_next_phase=True,  # Marca como gatilho por padrão
                        phase_order=phase_config.phase_number,
                        auto_created=True
                    )
                    db.session.add(milestone)
                    self.logger.info(f"Novo marco '{milestone_name}' criado para fase {phase_config.phase_number}")

            db.session.commit()
            return True

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao criar marcos da fase {phase_config.phase_name}: {e}")
            return False

    def recalculate_project_phase(self, project_id: str) -> Tuple[bool, str]:
        """Recalcula e atualiza a fase do projeto baseada no status dos marcos"""
        try:
            backlog = Backlog.query.filter_by(project_id=project_id).first()
            if not backlog or not backlog.project_type:
                return False, "Projeto não encontrado ou tipo não definido"

            # Detecta a fase atual baseada nos marcos
            detected_phase = self.detect_current_phase_from_milestones(project_id, backlog.project_type)
            old_phase = backlog.current_phase

            if detected_phase != old_phase:
                # Atualiza a fase do projeto
                backlog.current_phase = detected_phase
                backlog.phase_started_at = get_brasilia_now()
                db.session.commit()
                
                self.logger.info(f"Fase do projeto {project_id} recalculada: {old_phase} → {detected_phase}")
                return True, f"Fase atualizada de {old_phase} para {detected_phase}"
            else:
                return True, f"Projeto já está na fase correta: {detected_phase}"

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao recalcular fase do projeto {project_id}: {e}")
            return False, f"Erro interno: {str(e)}"

    def check_milestone_triggers(self, milestone_id: int) -> bool:
        """Verifica se um marco concluído deve disparar transição de fase"""
        try:
            milestone = ProjectMilestone.query.get(milestone_id)
            if not milestone or not milestone.triggers_next_phase:
                return False

            if milestone.status != MilestoneStatus.COMPLETED:
                return False

            # Obtém projeto do marco
            backlog = milestone.backlog
            if not backlog or not backlog.project_type:
                return False

            project_id = backlog.project_id

            # ✅ RECALCULA A FASE BASEADA NO STATUS DOS MARCOS
            recalc_success, recalc_message = self.recalculate_project_phase(project_id)
            if recalc_success:
                self.logger.info(f"Marco {milestone.name} acionou recálculo de fase: {recalc_message}")
                return True

            # Fallback: Verifica se pode avançar usando o método tradicional
            can_advance, message = self.can_advance_to_next_phase(project_id)
            if can_advance:
                success, result_message = self.advance_to_next_phase(project_id)
                if success:
                    self.logger.info(f"Transição automática de fase disparada pelo marco {milestone.name} (projeto {project_id})")
                    return True

            return False

        except Exception as e:
            self.logger.error(f"Erro ao verificar gatilhos do marco {milestone_id}: {e}")
            return False

    def get_project_phases_overview(self, project_id: str) -> Dict:
        """Retorna visão geral de todas as fases do projeto"""
        try:
            backlog = Backlog.query.filter_by(project_id=project_id).first()
            if not backlog or not backlog.project_type:
                return {'error': 'Projeto não encontrado ou tipo não definido'}

            phases = ProjectPhaseConfiguration.get_phases_for_type(backlog.project_type)
            phases_info = []

            for phase in phases:
                # ✅ CALCULA DATAS REAIS DA FASE BASEADO NOS MARCOS
                phase_dates = self.calculate_phase_dates(project_id, phase.phase_number)
                
                # Determina status da fase baseado nos marcos
                phase_status_str = phase_dates.get('status', 'not_started')
                
                # Busca marcos da fase
                milestone_names = phase.get_milestone_names()
                milestones_info = []
                
                if milestone_names:
                    milestones = ProjectMilestone.query.filter(
                        ProjectMilestone.backlog_id == backlog.id,
                        ProjectMilestone.name.in_(milestone_names)
                    ).all()
                    
                    milestones_info = [
                        {
                            'id': m.id,
                            'name': m.name,
                            'status': m.status.value,
                            'planned_date': m.planned_date.isoformat() if m.planned_date else None,
                            'started_at': m.started_at.isoformat() if m.started_at else None,
                            'actual_date': m.actual_date.isoformat() if m.actual_date else None,
                            'triggers_next_phase': m.triggers_next_phase,
                            'is_delayed': m.is_delayed
                        }
                        for m in milestones
                    ]

                phases_info.append({
                    'phase_number': phase.phase_number,
                    'phase_name': phase.phase_name,
                    'phase_description': phase.phase_description,
                    'phase_color': phase.phase_color,
                    'status': phase_status_str,
                    'is_current': phase.phase_number == backlog.current_phase,
                    'is_completed': phase_status_str == 'completed',
                    'started_at': phase_dates.get('started_at'),
                    'completed_at': phase_dates.get('completed_at'),
                    'planned_completion': phase_dates.get('planned_completion'),
                    'is_delayed': phase_dates.get('is_delayed', False),
                    'milestones': milestones_info,
                    'progress': {
                        'total': phase_dates.get('milestones_count', 0),
                        'completed': phase_dates.get('completed_milestones', 0)
                    }
                })

            return {
                'project_id': project_id,
                'project_type': backlog.project_type.value,
                'current_phase': backlog.current_phase,
                'phases': phases_info
            }

        except Exception as e:
            self.logger.error(f"Erro ao obter visão geral das fases do projeto {project_id}: {e}")
            return {'error': f'Erro interno: {str(e)}'}

    @staticmethod
    def initialize_phase_configurations():
        """Inicializa configurações padrão de fases (chamado na inicialização do app)"""
        try:
            ProjectPhaseConfiguration.initialize_default_phases()
        except Exception as e:
            logger.error(f"Erro ao inicializar configurações de fases: {e}") 