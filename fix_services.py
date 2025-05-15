import re

def fix_functions():
    print("Substituindo as funções problemáticas...")
    
    with open('app/macro/services.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Primeira parte - Localizar o início da função gerar_dados_status_report
    function_start_pattern = r'# <<< INÍCIO: Nova função para dados do Status Report >>>\s+def gerar_dados_status_report\(self, project_id\):'
    match = re.search(function_start_pattern, content)
    
    if not match:
        print("Não foi possível encontrar o início da função gerar_dados_status_report")
        return
    
    start_pos = match.start()
    
    # Localizar o final da função - antes do início da próxima função
    function_end_pattern = r'# <<< FIM: Nova função para dados do Status Report >>>'
    match_end = re.search(function_end_pattern, content[start_pos:])
    
    if not match_end:
        print("Não foi possível encontrar o final da função gerar_dados_status_report")
        return
    
    end_pos = start_pos + match_end.end()
    
    # Nova implementação correta das funções
    new_function_code = '''# <<< INÍCIO: Nova função para dados do Status Report >>>
    def gerar_dados_status_report(self, project_id):
        """
        Prepara os dados necessários para o Status Report de um projeto.
        """
        try:
            self.logger.info(f"[Status Report] Gerando dados para projeto ID: {project_id}")

            # 1. Carrega todos os dados (padrão)
            dados_todos = self.carregar_dados(fonte=None)
            if dados_todos.empty:
                self.logger.error("[Status Report] Falha ao carregar dados gerais.")
                return {
                    'info_geral': {
                        'id': project_id,
                        'nome': 'N/A',
                        'squad': 'N/A',
                        'especialista': 'N/A',
                        'status_atual': 'N/A'
                    },
                    'erro': 'Falha ao carregar dados gerais',
                    'progresso': {'percentual_concluido': 0, 'data_prevista_termino': 'N/A', 'status_prazo': 'N/A'},
                    'esforco': {'horas_planejadas': 0, 'horas_utilizadas': 0, 'percentual_consumido': 0},
                    'status_geral_indicador': 'cinza',
                    'marcos_recentes': [],
                    'riscos_impedimentos': [],
                    'notas': [],
                    'proximos_passos': []
                }

            # 2. Converte ID para int para filtro
            try:
                project_id_int = int(project_id)
            except (ValueError, TypeError):
                self.logger.error(f"[Status Report] project_id inválido: {project_id}")
                return {
                    'info_geral': {
                        'id': project_id,
                        'nome': 'N/A',
                        'squad': 'N/A',
                        'especialista': 'N/A',
                        'status_atual': 'N/A'
                    },
                    'erro': 'ID de projeto inválido',
                    'progresso': {'percentual_concluido': 0, 'data_prevista_termino': 'N/A', 'status_prazo': 'N/A'},
                    'esforco': {'horas_planejadas': 0, 'horas_utilizadas': 0, 'percentual_consumido': 0},
                    'status_geral_indicador': 'cinza',
                    'marcos_recentes': [],
                    'riscos_impedimentos': [],
                    'notas': [],
                    'proximos_passos': []
                }
            
            # Garante que a coluna 'Numero' existe e é numérica
            if 'Numero' not in dados_todos.columns:
                self.logger.error("[Status Report] Coluna 'Numero' não encontrada nos dados.")
                return {
                    'info_geral': {
                        'id': project_id,
                        'nome': 'N/A',
                        'squad': 'N/A',
                        'especialista': 'N/A',
                        'status_atual': 'N/A'
                    },
                    'erro': 'Coluna Numero não encontrada nos dados',
                    'progresso': {'percentual_concluido': 0, 'data_prevista_termino': 'N/A', 'status_prazo': 'N/A'},
                    'esforco': {'horas_planejadas': 0, 'horas_utilizadas': 0, 'percentual_consumido': 0},
                    'status_geral_indicador': 'cinza',
                    'marcos_recentes': [],
                    'riscos_impedimentos': [],
                    'notas': [],
                    'proximos_passos': []
                }
            dados_todos['Numero'] = pd.to_numeric(dados_todos['Numero'], errors='coerce').astype('Int64')

            # 3. Filtra pelo projeto específico
            dados_projeto_df = dados_todos[dados_todos['Numero'] == project_id_int]

            if dados_projeto_df.empty:
                self.logger.warning(f"[Status Report] Projeto ID {project_id_int} não encontrado nos dados carregados.")
                return {
                    'info_geral': {
                        'id': project_id,
                        'nome': 'N/A',
                        'squad': 'N/A',
                        'especialista': 'N/A',
                        'status_atual': 'N/A'
                    },
                    'erro': 'Projeto não encontrado',
                    'progresso': {'percentual_concluido': 0, 'data_prevista_termino': 'N/A', 'status_prazo': 'N/A'},
                    'esforco': {'horas_planejadas': 0, 'horas_utilizadas': 0, 'percentual_consumido': 0},
                    'status_geral_indicador': 'cinza',
                    'marcos_recentes': [],
                    'riscos_impedimentos': [],
                    'notas': [],
                    'proximos_passos': []
                }
            
            dados_projeto = dados_projeto_df.iloc[0]

            # 4. Extrair e Calcular Dados para o Report
            
            # Progresso
            percentual_concluido = float(dados_projeto.get('Conclusao', 0.0))
            data_prevista_termino_dt = pd.to_datetime(dados_projeto.get('VencimentoEm'), errors='coerce')
            data_prevista_termino_str = data_prevista_termino_dt.strftime('%d/%m/%Y') if pd.notna(data_prevista_termino_dt) else 'N/A'

            # Calcular Status do Prazo
            status_prazo = 'A Definir'
            hoje_data = datetime.now().date() # Pega apenas a data atual
            if pd.notna(data_prevista_termino_dt):
                data_prevista_termino_data = data_prevista_termino_dt.date() # Pega apenas a data prevista
                if data_prevista_termino_data < hoje_data:
                    status_prazo = 'Atrasado'
                # Compara apenas as datas
                elif data_prevista_termino_data >= hoje_data and data_prevista_termino_data <= hoje_data + timedelta(days=15):
                     status_prazo = 'Próximo (15d)'
                else: 
                    status_prazo = 'No Prazo'
            else:
                 status_prazo = 'Sem Prazo Definido'

            # Esforço
            horas_planejadas = float(dados_projeto.get('Horas', 0.0))
            horas_utilizadas = float(dados_projeto.get('HorasTrabalhadas', 0.0))
            percentual_consumido = 0.0
            if horas_planejadas > 0:
                percentual_consumido = round((horas_utilizadas / horas_planejadas) * 100, 1)
            
            # Status Geral (Lógica Refinada)
            status_geral_indicador = 'cinza' # Default: Sem prazo e sem estouro
            horas_estouradas = horas_utilizadas > horas_planejadas and horas_planejadas > 0

            if status_prazo == 'Atrasado' or horas_estouradas:
                status_geral_indicador = 'vermelho'
            elif status_prazo == 'Próximo (15d)':
                # Atenção se próximo e progresso baixo OU consumo desproporcional
                if percentual_concluido < 70 or (percentual_consumido >= 80 and percentual_concluido < 70):
                    status_geral_indicador = 'amarelo' 
                else:
                    status_geral_indicador = 'verde' # Próximo, mas progresso/consumo OK
            elif status_prazo == 'No Prazo':
                status_geral_indicador = 'verde'
            elif status_prazo == 'Sem Prazo Definido':
                status_geral_indicador = 'cinza' # Mantém cinza se não tem prazo e não estourou horas
            
            # INÍCIO: Buscar marcos do projeto
            marcos_recentes = []
            try:
                # Buscar backlog associado ao projeto
                from ..models import Backlog, ProjectMilestone
                backlog = Backlog.query.filter_by(project_id=str(project_id)).first()
                
                if backlog:
                    # Busca os marcos mais recentes
                    milestones = ProjectMilestone.query.filter_by(backlog_id=backlog.id).order_by(ProjectMilestone.planned_date.desc()).limit(5).all()
                    
                    for milestone in milestones:
                        # Converter para dicionário e adicionar à lista
                        marcos_recentes.append({
                            'id': milestone.id,
                            'nome': milestone.name,
                            'data_planejada': milestone.planned_date.strftime('%d/%m/%Y') if milestone.planned_date else 'N/A',
                            'data_real': milestone.actual_date.strftime('%d/%m/%Y') if milestone.actual_date else 'N/A',
                            'status': milestone.status.value,
                            'criticidade': milestone.criticality.value,
                            'atrasado': milestone.is_delayed
                        })
                    self.logger.info(f"[Status Report] {len(marcos_recentes)} marcos encontrados para o projeto {project_id}")
                else:
                    self.logger.warning(f"[Status Report] Nenhum backlog encontrado para o projeto {project_id}")
            except Exception as e:
                self.logger.error(f"[Status Report] Erro ao buscar marcos do projeto: {str(e)}")
                # Continua com a lista vazia em caso de erro
            # FIM: Buscar marcos do projeto
            
            # INÍCIO: Buscar riscos do projeto
            riscos_do_projeto = []
            if backlog: # Garante que o backlog foi encontrado
                try:
                    from ..models import ProjectRisk # Importar dentro da função ou no topo do arquivo
                    
                    project_risks = ProjectRisk.query.filter_by(backlog_id=backlog.id).order_by(ProjectRisk.created_at.desc()).all()
                    if project_risks:
                        self.logger.info(f"[Status Report] {len(project_risks)} riscos encontrados para o backlog ID {backlog.id} do projeto {project_id}")
                        for risk in project_risks:
                            riscos_do_projeto.append(risk.to_dict())
                    else:
                        self.logger.info(f"[Status Report] Nenhum risco encontrado para o backlog ID {backlog.id} do projeto {project_id}")
                except Exception as e:
                    self.logger.error(f"[Status Report] Erro ao buscar riscos do projeto {project_id}: {str(e)}")
            else:
                self.logger.warning(f"[Status Report] Backlog não encontrado para projeto {project_id}, não é possível buscar riscos.")
            # FIM: Buscar riscos do projeto
            
            # INÍCIO: Buscar notas do projeto
            notas_do_projeto = []
            try:
                # Importar Note dentro do try para evitar erro de importação
                from ..models import Note, Task
                # Garantir que o project_id seja uma string limpa (apenas números)
                project_id_str = str(project_id).strip().split('.')[0]  # Remove qualquer parte decimal
                self.logger.info(f"[Status Report] Tentando buscar notas para o projeto {project_id_str} (tipo: {type(project_id_str)})")
                
                # Busca todas as notas relacionadas ao projeto diretamente
                project_notes = Note.query.filter(Note.project_id == project_id_str).order_by(Note.created_at.desc()).all()

                self.logger.info(f"[Status Report] Query SQL: {Note.query.filter(Note.project_id == project_id_str)}")
                self.logger.info(f"[Status Report] Project ID: {project_id_str}")
                self.logger.info(f"[Status Report] Notas encontradas: {len(project_notes)}")
                
                if project_notes:
                    self.logger.info(f"[Status Report] {len(project_notes)} notas encontradas para o projeto {project_id_str}")
                    for note in project_notes:
                        self.logger.info(f"[Status Report] Processando nota: ID={note.id}, Project_ID={note.project_id}, Backlog_ID={note.backlog_id}, Categoria={note.category}, Task_ID={note.task_id}, Conteúdo={note.content[:50]}...")
                        # Busca o título da tarefa se a nota estiver vinculada a uma
                        task_title = None
                        if note.task_id:
                            task = Task.query.get(note.task_id)
                            if task:
                                task_title = task.title
                                self.logger.info(f"[Status Report] Título da tarefa encontrado: {task_title}")
                            else:
                                self.logger.warning(f"[Status Report] Tarefa {note.task_id} não encontrada")

                        # Define as cores dos badges baseado na categoria e prioridade
                        category_colors = {
                            'decision': 'primary',
                            'risk': 'danger',
                            'impediment': 'warning',
                            'status_update': 'info',
                            'general': 'secondary'
                        }
                        
                        priority_colors = {
                            'high': 'danger',
                            'medium': 'warning',
                            'low': 'success'
                        }

                        category_texts = {
                            'decision': 'Decisão',
                            'risk': 'Risco',
                            'impediment': 'Impedimento',
                            'status_update': 'Atualização',
                            'general': 'Geral'
                        }

                        priority_texts = {
                            'high': 'Alta',
                            'medium': 'Média',
                            'low': 'Baixa'
                        }

                        nota_dict = {
                            'id': note.id,
                            'content': note.content,
                            'category': note.category,
                            'category_color': category_colors.get(note.category, 'secondary'),
                            'category_text': category_texts.get(note.category, note.category),
                            'priority': note.priority,
                            'priority_color': priority_colors.get(note.priority, 'secondary'),
                            'priority_text': priority_texts.get(note.priority, note.priority),
                            'task_id': note.task_id,
                            'task_title': task_title,
                            'created_at': note.created_at.strftime('%d/%m/%Y %H:%M'),
                            'tags': [tag.name for tag in note.tags] if note.tags else []
                        }
                        self.logger.info(f"[Status Report] Nota processada: {nota_dict}")
                        notas_do_projeto.append(nota_dict)
                else:
                    self.logger.info(f"[Status Report] Nenhuma nota encontrada para o projeto {project_id_str}")
            except Exception as e:
                self.logger.error(f"[Status Report] Erro ao buscar notas do projeto {project_id_str}: {str(e)}")
                self.logger.exception(e)  # Log do traceback completo
            
            self.logger.info(f"[Status Report] Total de notas processadas: {len(notas_do_projeto)}")
            # FIM: Buscar notas do projeto

            # Se não encontrou marcos no banco de dados, usar uma lista vazia em vez dos marcos falsos
            if not marcos_recentes:
                self.logger.info(f"[Status Report] Não foram encontrados marcos para o projeto {project_id}")
                marcos_recentes = []
                
            # 5. Montar a estrutura do report
            report_data = {
                'info_geral': {
                    'id': project_id,
                    'nome': dados_projeto.get('Projeto', 'N/A'),
                    'squad': dados_projeto.get('Squad', 'N/A'),
                    'especialista': dados_projeto.get('Especialista', 'N/A'),
                    'status_atual': normalize_status(dados_projeto.get('Status', 'N/A'))
                },
                'progresso': {
                    'percentual_concluido': round(percentual_concluido, 1),
                    'data_prevista_termino': data_prevista_termino_str,
                    'status_prazo': status_prazo 
                },
                'esforco': {
                    'horas_planejadas': round(horas_planejadas, 1),
                    'horas_utilizadas': round(horas_utilizadas, 1),
                    'percentual_consumido': percentual_consumido
                },
                'status_geral_indicador': status_geral_indicador,
                'marcos_recentes': marcos_recentes,
                'riscos_impedimentos': riscos_do_projeto,
                'notas': notas_do_projeto,
                'proximos_passos': []
            }

            # Log detalhado para debug
            self.logger.info(f"[Status Report] Dados calculados para projeto {project_id}: " +
                             f"Progresso={percentual_concluido}%, " +
                             f"Prazo='{status_prazo}', " +
                             f"Status Geral='{status_geral_indicador}', " +
                             f"Marcos={len(marcos_recentes)}, " +
                             f"Notas={len(notas_do_projeto)}")
            
            # Verificar se as chaves existem no report_data
            for key in report_data.keys():
                self.logger.debug(f"[Status Report] Chave encontrada: '{key}' com tipo {type(report_data[key])}")
                if key == 'notas':
                    self.logger.info(f"[Status Report] Conteúdo de notas: {report_data['notas']}")

            return report_data

        except Exception as e:
            self.logger.exception(f"[Status Report] Erro ao gerar dados para projeto ID {project_id}: {str(e)}")
            # Em caso de erro, retornar uma estrutura mínima para não quebrar o frontend
            return {
                'info_geral': {
                    'id': project_id,
                    'nome': 'Erro',
                    'squad': 'N/A',
                    'especialista': 'N/A',
                    'status_atual': 'Erro'
                },
                'erro': str(e),
                'progresso': {'percentual_concluido': 0, 'data_prevista_termino': 'N/A', 'status_prazo': 'Erro'},
                'esforco': {'horas_planejadas': 0, 'horas_utilizadas': 0, 'percentual_consumido': 0},
                'status_geral_indicador': 'vermelho',
                'marcos_recentes': [],
                'riscos_impedimentos': [],
                'notas': [],
                'proximos_passos': []
            }
# <<< FIM: Nova função para dados do Status Report >>>'''

    # Segunda parte - Localizar o início da função gerar_status_report
    function2_start_pattern = r'def gerar_status_report\(self, project_id\):'
    match2 = re.search(function2_start_pattern, content[end_pos:])
    
    if not match2:
        print("Não foi possível encontrar o início da função gerar_status_report")
        return
    
    start_pos2 = end_pos + match2.start()
    
    # Localizar o final da função gerar_status_report - procura pela próxima função ou definição global
    function2_end_pattern = r'def \w+\(|^[\w]+ ='
    match_end2 = re.search(function2_end_pattern, content[start_pos2:], re.MULTILINE)
    
    if not match_end2:
        print("Não foi possível encontrar o final da função gerar_status_report")
        # Tenta outro padrão - uma definição de função global
        function2_end_pattern = r'def normalize_status\('
        match_end2 = re.search(function2_end_pattern, content[start_pos2:])
        if not match_end2:
            print("Não foi possível encontrar o final da função gerar_status_report usando padrão alternativo")
            return
    
    end_pos2 = start_pos2 + match_end2.start()
    
    # Nova implementação correta da função gerar_status_report
    new_function2_code = '''    def gerar_status_report(self, project_id):
        """Gera um status report para o projeto especificado"""
        logger.debug(f"Gerando status report para o projeto: {project_id}")
        try:
            # Usar a função gerar_dados_status_report que já tem toda a lógica necessária
            report_data = self.gerar_dados_status_report(project_id)
            # Não precisamos verificar se report_data é None porque gerar_dados_status_report
            # agora sempre retorna um dicionário com a estrutura correta
            
            # Retorna os dados completos que já incluem as notas
            return report_data
            
        except Exception as e:
            logger.error(f"Erro ao gerar status report para projeto {project_id}: {str(e)}")
            # Em caso de erro, retornar uma estrutura mínima para não quebrar o frontend
            return {
                'info_geral': {
                    'id': project_id,
                    'nome': 'Erro',
                    'squad': 'N/A',
                    'especialista': 'N/A',
                    'status_atual': 'Erro'
                },
                'erro': str(e),
                'progresso': {'percentual_concluido': 0, 'data_prevista_termino': 'N/A', 'status_prazo': 'Erro'},
                'esforco': {'horas_planejadas': 0, 'horas_utilizadas': 0, 'percentual_consumido': 0},
                'status_geral_indicador': 'vermelho',
                'marcos_recentes': [],
                'riscos_impedimentos': [],
                'notas': [],
                'proximos_passos': []
            }

'''

    # Implementa as substituições
    new_content = content[:start_pos] + new_function_code + content[end_pos:start_pos2] + new_function2_code + content[end_pos2:]
    
    # Escreve o novo conteúdo no arquivo
    with open('app/macro/services.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("Funções substituídas com sucesso!")

if __name__ == "__main__":
    fix_functions() 