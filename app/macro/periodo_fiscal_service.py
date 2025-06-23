import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import pandas as pd
from app.macro.services import MacroService
import os

logger = logging.getLogger(__name__)

class PeriodoFiscalManager:
    """Gerencia detecção e cálculo de períodos fiscais Microsoft"""
    
    def __init__(self):
        # Calendário fiscal Microsoft: termina em 30 de junho
        self.fim_ano_fiscal = (6, 30)  # 30 de junho
        
    def detectar_periodos_disponiveis(self, dados):
        """Detecta períodos trimestrais e semestrais disponíveis nos dados"""
        if dados.empty or 'DataTermino' not in dados.columns:
            return {'trimestral': [], 'semestral': []}
        
        # Converte DataTermino para datetime se necessário
        dados_temp = dados.copy()
        dados_temp['DataTermino'] = pd.to_datetime(dados_temp['DataTermino'], errors='coerce')
        
        # Remove registros sem data de término
        dados_temp = dados_temp.dropna(subset=['DataTermino'])
        
        if dados_temp.empty:
            return {'trimestral': [], 'semestral': []}
        
        # Obtém range de datas
        data_min = dados_temp['DataTermino'].min()
        data_max = dados_temp['DataTermino'].max()
        
        periodos = {'trimestral': [], 'semestral': []}
        
        # Gera períodos trimestrais (últimos 3 meses)
        data_atual = data_max
        while data_atual >= data_min:
            inicio_trim = data_atual - timedelta(days=89)  # ~3 meses
            if inicio_trim <= data_max:
                periodos['trimestral'].append({
                    'inicio': inicio_trim,
                    'fim': data_atual,
                    'label': f"Trimestral até {data_atual.strftime('%m/%Y')}"
                })
            data_atual = data_atual - timedelta(days=30)  # Move 1 mês para trás
        
        # Gera períodos semestrais (últimos 6 meses)
        data_atual = data_max
        while data_atual >= data_min:
            inicio_sem = data_atual - timedelta(days=179)  # ~6 meses
            if inicio_sem <= data_max:
                periodos['semestral'].append({
                    'inicio': inicio_sem,
                    'fim': data_atual,
                    'label': f"Semestral até {data_atual.strftime('%m/%Y')}"
                })
            data_atual = data_atual - timedelta(days=90)  # Move 3 meses para trás
        
        # Limita a 3 períodos de cada tipo
        periodos['trimestral'] = periodos['trimestral'][:3]
        periodos['semestral'] = periodos['semestral'][:3]
        
        return periodos

class StatusReportHistoricoService:
    """
    Serviço para análise de períodos históricos usando apenas arquivos apt_mes
    (dados arquivados/fechados) - SEM usar dadosr.csv atual
    """
    
    def __init__(self):
        self.macro_service = MacroService()
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
        
        # Mapeamento de meses disponíveis (apenas dados históricos)
        self.meses_disponiveis = {
            'jan': {'arquivo': 'dadosr_apt_jan.csv', 'nome': 'Janeiro', 'numero': 1, 'filtro_mes': '2025-01'},
            'fev': {'arquivo': 'dadosr_apt_fev.csv', 'nome': 'Fevereiro', 'numero': 2, 'filtro_mes': '2025-02'},
            'mar': {'arquivo': 'dadosr_apt_mar.csv', 'nome': 'Março', 'numero': 3, 'filtro_mes': '2025-03'},
            'abr': {'arquivo': 'dadosr_apt_abr.csv', 'nome': 'Abril', 'numero': 4, 'filtro_mes': '2025-04'},
            'mai': {'arquivo': 'dadosr_apt_mai.csv', 'nome': 'Maio', 'numero': 5, 'filtro_mes': '2025-05'},
            'jun': {'arquivo': 'dadosr_parc_jun.csv', 'nome': 'Junho', 'numero': 6, 'filtro_mes': '2025-06'},
        }
    
    def listar_meses_disponiveis(self):
        """
        Lista os meses históricos disponíveis para análise
        """
        meses_encontrados = []
        
        for mes_key, info in self.meses_disponiveis.items():
            arquivo_path = os.path.join(self.data_dir, info['arquivo'])
            if os.path.exists(arquivo_path):
                meses_encontrados.append({
                    'key': mes_key,
                    'nome': info['nome'],
                    'numero': info['numero'],
                    'arquivo': info['arquivo'],
                    'disponivel': True
                })
            else:
                logger.warning(f"Arquivo não encontrado: {arquivo_path}")
        
        return sorted(meses_encontrados, key=lambda x: x['numero'])
    
    def calcular_kpis_periodo_historico(self, meses_selecionados):
        """
        Calcula KPIs para um período específico usando apenas dados históricos
        
        Args:
            meses_selecionados: Lista de meses (ex: ['jan', 'fev', 'mar'])
        
        Returns:
            Dictionary com KPIs calculados
        """
        try:
            if not meses_selecionados:
                return self._criar_resultado_vazio("Nenhum mês selecionado")
            
            logger.info(f"📊 Calculando KPIs históricos para: {meses_selecionados}")
            
            # Valida meses selecionados
            meses_validos = []
            for mes in meses_selecionados:
                if mes in self.meses_disponiveis:
                    meses_validos.append(mes)
                else:
                    logger.warning(f"Mês inválido ignorado: {mes}")
            
            if not meses_validos:
                return self._criar_resultado_vazio("Nenhum mês válido selecionado")
            
            # Inicializa variáveis de acumulação
            total_projetos_fechados = 0
            total_projetos_abertos = 0 
            total_horas_trabalhadas = 0.0
            total_horas_estimadas = 0.0
            total_horas_trabalhadas_kpis = 0.0
            total_projetos_no_prazo = 0
            total_projetos_com_prazo = 0
            total_faturamento = {}
            detalhes_por_mes = {}
            lista_horas_mensais = []  # Para calcular média das horas
            
            # Carrega dados de todos os meses do período
            dados_por_mes = {}
            for mes_key in meses_validos:
                info_mes = self.meses_disponiveis[mes_key]
                dados_mes = self._carregar_dados_mes_historico(info_mes['arquivo'])
                if not dados_mes.empty:
                    dados_por_mes[mes_key] = dados_mes
            
            # === SOLUÇÃO AUTOMÁTICA: EXECUTA STATUS REPORT MENSAL PARA CADA MÊS ===
            # Executa o Status Report individual de cada mês em background e consolida
            logger.info("🔄 Executando Status Reports mensais automaticamente...")
            
            dados_mensais_prazo = []
            mes_anterior_key = None
            
            for i, mes_key in enumerate(meses_validos):
                try:
                    info_mes = self.meses_disponiveis[mes_key]
                    logger.info(f"📅 Executando Status Report para {info_mes['nome']}...")
                    
                    # Carrega dados do mês
                    if mes_key not in dados_por_mes:
                        logger.warning(f"⚠️ Dados vazios para {info_mes['nome']}")
                        continue
                    
                    dados_mes = dados_por_mes[mes_key]
                    
                    # EXECUTA O STATUS REPORT MENSAL COMPLETO
                    # Simula a data de referência do mês
                    mes_ref = datetime(2025, info_mes['numero'], 1)
                    
                    # 1. Calcula projetos entregues (fechados) usando lógica do MacroService
                    projetos_entregues_resultado = self.macro_service.calcular_projetos_entregues(dados_mes, mes_ref)
                    fechados_mes = projetos_entregues_resultado.get('total_mes', 0)
                    
                    # 2. Projetos abertos (novos) no mês  
                    novos_projetos = self.macro_service.calcular_novos_projetos_mes(dados_mes, mes_ref)
                    abertos_mes = novos_projetos.get('total', 0)
                    
                    # 3. Faturamento APENAS dos novos projetos do mês (não todos os ativos)
                    # Primeiro obtém os novos projetos
                    novos_projetos_data = novos_projetos.get('novos_projetos', pd.DataFrame())
                    
                    if not novos_projetos_data.empty and 'Faturamento' in novos_projetos_data.columns:
                        # Calcula faturamento apenas dos projetos NOVOS
                        # FILTRO: Exclui projetos com cliente "SOU.cloud" do faturamento
                        projetos_para_faturamento = novos_projetos_data[novos_projetos_data['Cliente'] != 'SOU.cloud'].copy()
                        
                        if not projetos_para_faturamento.empty:
                            # MODIFICAÇÃO: Converte ENGAJAMENTO para TERMINO antes da contagem
                            faturamento_modificado = projetos_para_faturamento['Faturamento'].copy()
                            faturamento_modificado = faturamento_modificado.replace('ENGAJAMENTO', 'TERMINO')
                            contagem_fat = faturamento_modificado.value_counts().to_dict()
                            
                            # Log com informações sobre filtros aplicados
                            total_novos = len(novos_projetos_data)
                            total_filtrados = len(projetos_para_faturamento)
                            excluidos_sou = total_novos - total_filtrados
                            
                            if excluidos_sou > 0:
                                logger.info(f"📊 {info_mes['nome']} - {excluidos_sou} projetos SOU.cloud excluídos do faturamento")
                            logger.info(f"📊 {info_mes['nome']} - Faturamento dos NOVOS projetos (Engajamento→Término, sem SOU.cloud): {contagem_fat}")
                        else:
                            # Todos os projetos eram SOU.cloud
                            contagem_fat = {}
                            logger.info(f"📊 {info_mes['nome']} - Todos os projetos novos são SOU.cloud - faturamento vazio")
                    else:
                        # Fallback: usa o método antigo se não conseguir obter os novos projetos
                        # FILTRO: Aplica o mesmo filtro SOU.cloud no fallback
                        dados_sem_sou = dados_mes[dados_mes['Cliente'] != 'SOU.cloud'].copy()
                        faturamento_mes = self.macro_service.calcular_projetos_por_faturamento(dados_sem_sou, mes_ref)
                        contagem_fat_original = faturamento_mes.get('contagem', {})
                        # Aplica a mesma conversão no fallback
                        contagem_fat = {}
                        for tipo, qtd in contagem_fat_original.items():
                            if tipo == 'ENGAJAMENTO':
                                contagem_fat['TERMINO'] = contagem_fat.get('TERMINO', 0) + qtd
                            else:
                                contagem_fat[tipo] = qtd
                        
                        # Log informando sobre o filtro aplicado no fallback
                        total_original = len(dados_mes)
                        total_filtrado = len(dados_sem_sou)
                        excluidos_sou_fallback = total_original - total_filtrado
                        if excluidos_sou_fallback > 0:
                            logger.warning(f"⚠️ {info_mes['nome']} - Fallback: {excluidos_sou_fallback} projetos SOU.cloud excluídos")
                        logger.warning(f"⚠️ {info_mes['nome']} - Usando faturamento de todos os projetos ativos (fallback, Engajamento→Término, sem SOU.cloud)")
                    
                    # 4. Horas trabalhadas INCREMENTAIS (diferença do mês anterior)
                    horas_incrementais = self._calcular_horas_incrementais(
                        dados_mes, 
                        dados_por_mes.get(mes_anterior_key) if mes_anterior_key else None,
                        info_mes['nome']
                    )
                    
                    # 4b. Horas trabalhadas TOTAIS do mês (para comparação)
                    horas_totais_mes = dados_mes['HorasTrabalhadas'].fillna(0).sum()
                    
                    # 5. KPIs avançados do mês (incluindo análise de prazo)
                    kpis_mes = self._calcular_kpis_mes(dados_mes, info_mes['nome'])
                    
                    # 6. Extrai informações detalhadas de prazo do resultado de projetos entregues
                    no_prazo_mes = projetos_entregues_resultado.get('no_prazo', 0)
                    fora_prazo_mes = projetos_entregues_resultado.get('fora_prazo', 0)
                    
                    # Se não tiver dados de prazo no resultado de entregues, usa KPIs
                    if no_prazo_mes == 0 and fora_prazo_mes == 0 and fechados_mes > 0:
                        no_prazo_mes = kpis_mes.get('projetos_no_prazo', 0)
                        projetos_com_prazo_mes = kpis_mes.get('projetos_com_prazo', fechados_mes)
                        if projetos_com_prazo_mes > no_prazo_mes:
                            fora_prazo_mes = projetos_com_prazo_mes - no_prazo_mes
                    
                    # Calcula taxa de prazo
                    if fechados_mes > 0:
                        taxa_prazo_mes = round((no_prazo_mes / fechados_mes) * 100, 1)
                    else:
                        taxa_prazo_mes = 0.0
                    
                    # Valida consistência
                    if (no_prazo_mes + fora_prazo_mes) != fechados_mes and fechados_mes > 0:
                        logger.warning(f"⚠️ Inconsistência em {info_mes['nome']}: {no_prazo_mes} + {fora_prazo_mes} != {fechados_mes}")
                        # Ajusta fora_prazo para manter consistência
                        fora_prazo_mes = fechados_mes - no_prazo_mes
                        if fora_prazo_mes < 0:
                            fora_prazo_mes = 0
                            no_prazo_mes = fechados_mes
                    
                    # Acumula totais GERAIS
                    total_projetos_fechados += fechados_mes
                    total_projetos_abertos += abertos_mes
                    total_horas_trabalhadas += horas_incrementais  # SOMA as horas incrementais de cada mês
                    total_horas_estimadas += kpis_mes.get('horas_estimadas', 0)
                    total_horas_trabalhadas_kpis += kpis_mes.get('horas_trabalhadas', 0)
                    total_projetos_no_prazo += no_prazo_mes
                    total_projetos_com_prazo += fechados_mes  # Usa fechados como base para prazo
                    
                    # Adiciona horas incrementais para o total (não horas totais)
                    lista_horas_mensais.append(horas_incrementais)
                    
                    # Soma faturamento
                    for tipo, qtd in contagem_fat.items():
                        if tipo not in total_faturamento:
                            total_faturamento[tipo] = 0
                        total_faturamento[tipo] += qtd
                    
                    # Guarda detalhes do mês
                    detalhes_por_mes[mes_key] = {
                        'nome': info_mes['nome'],
                        'fechados': fechados_mes,
                        'abertos': abertos_mes,
                        'horas': round(horas_incrementais, 1),  # Usa horas INCREMENTAIS (não totais)
                        'horas_totais_mes': round(horas_totais_mes, 1),  # Mantém totais para debug
                        'eficiencia_recursos': kpis_mes.get('eficiencia_recursos', 0.0),
                        'eficiencia_composta': kpis_mes.get('eficiencia_composta', 0.0),  # Nova métrica
                        'eficiencia_horas': kpis_mes.get('eficiencia_horas', 0.0),       # Componente horas
                        'eficiencia_prazo': kpis_mes.get('eficiencia_prazo', 0.0),       # Componente prazo
                        'taxa_prazo': taxa_prazo_mes,
                        'tempo_medio_vida': kpis_mes.get('tempo_medio_vida', 0.0),
                        'projetos_analisados': kpis_mes.get('projetos_analisados', 0),   # Total analisados
                        'projetos_fechados': kpis_mes.get('projetos_fechados', 0),       # Fechados
                        'projetos_andamento': kpis_mes.get('projetos_andamento', 0),     # Em andamento
                        'projetos_no_prazo': kpis_mes.get('projetos_no_prazo', 0),       # No prazo
                        'projetos_com_prazo': kpis_mes.get('projetos_com_prazo', 0),     # Com prazo válido
                        'horas_estimadas': kpis_mes.get('horas_estimadas', 0.0),         # Horas estimadas
                        'horas_trabalhadas': kpis_mes.get('horas_trabalhadas', 0.0),     # Horas trabalhadas
                        'faturamento': contagem_fat
                    }
                    
                    # Armazena dados para consolidação de prazo
                    dados_mensais_prazo.append({
                        'mes': mes_key,
                        'nome': info_mes['nome'],
                        'total_fechados': fechados_mes,
                        'no_prazo': no_prazo_mes,
                        'fora_prazo': fora_prazo_mes,
                        'taxa_prazo': taxa_prazo_mes
                    })
                    
                    logger.info(f"✅ {info_mes['nome']}: {fechados_mes} fechados, {no_prazo_mes} no prazo, {fora_prazo_mes} fora prazo ({taxa_prazo_mes}%), {abertos_mes} abertos, {horas_totais_mes:.1f}h totais ({horas_incrementais:.1f}h incrementais)")
                    
                    # Atualiza mês anterior para próxima iteração
                    mes_anterior_key = mes_key
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao processar Status Report de {info_mes['nome']}: {str(e)}")
                    # Em caso de erro, tenta usar dados básicos se disponível
                    if mes_key in dados_por_mes:
                        dados_mes = dados_por_mes[mes_key]
                        # Conta projetos básicos como fallback
                        fechados_basico = len(dados_mes[dados_mes['Status'] == 'Fechado']) if 'Status' in dados_mes.columns else 0
                        if fechados_basico > 0:
                            total_projetos_fechados += fechados_basico
                            logger.info(f"🔄 {info_mes['nome']} (fallback básico): {fechados_basico} fechados")
                    continue
            
            # CONSOLIDA OS RESULTADOS DOS STATUS REPORTS MENSAIS
            if dados_mensais_prazo:
                total_projetos_com_prazo_consolidado = sum(d['total_fechados'] for d in dados_mensais_prazo)
                total_projetos_no_prazo_consolidado = sum(d['no_prazo'] for d in dados_mensais_prazo)
                total_projetos_fora_prazo_consolidado = sum(d['fora_prazo'] for d in dados_mensais_prazo)
                
                # Calcula taxa geral do período
                if total_projetos_com_prazo_consolidado > 0:
                    taxa_prazo_geral = round((total_projetos_no_prazo_consolidado / total_projetos_com_prazo_consolidado * 100), 1)
                else:
                    taxa_prazo_geral = 0.0
                
                logger.info(f"📊 === CONSOLIDAÇÃO DOS STATUS REPORTS AUTOMÁTICOS ===")
                for dados in dados_mensais_prazo:
                    logger.info(f"📊 {dados['nome'].upper()}: {dados['no_prazo']} no prazo + {dados['fora_prazo']} fora prazo = {dados['total_fechados']} total")
                
                logger.info(f"📊 === RESULTADO FINAL CONSOLIDADO ===")
                logger.info(f"📊 Total de projetos fechados: {total_projetos_com_prazo_consolidado}")
                logger.info(f"📊 Projetos NO PRAZO: {total_projetos_no_prazo_consolidado}")
                logger.info(f"📊 Projetos FORA DO PRAZO: {total_projetos_fora_prazo_consolidado}")
                logger.info(f"📊 Taxa de entrega no prazo: {taxa_prazo_geral}%")
                
            else:
                logger.info("📊 Nenhum Status Report mensal executado com sucesso")
                taxa_prazo_geral = 0.0
                total_projetos_no_prazo_consolidado = 0
                total_projetos_com_prazo_consolidado = total_projetos_fechados
                total_projetos_fora_prazo_consolidado = 0
            
            # === OUTROS KPIs GERAIS ===
            eficiencia_recursos_geral = 0.0
            if total_horas_estimadas > 0 and total_horas_trabalhadas_kpis > 0:
                # FÓRMULA INVERTIDA: (Horas Estimadas / Horas Trabalhadas) * 100
                # Maior = melhor (120% = 20% mais eficiente que estimado)
                eficiencia_recursos_geral = round((total_horas_estimadas / total_horas_trabalhadas_kpis * 100), 1)
            
            # === TEMPO MÉDIO DE VIDA CONSOLIDADO ===
            tempo_medio_vida_geral = 0.0
            tempos_vida_todos_projetos = []
            
            # Coleta tempos de vida de todos os meses
            for mes_key in meses_validos:
                if mes_key in detalhes_por_mes and 'tempo_medio_vida' in detalhes_por_mes[mes_key]:
                    tmv_mes = detalhes_por_mes[mes_key]['tempo_medio_vida']
                    if tmv_mes > 0:
                        # Para consolidação, vamos coletar os projetos individuais de cada mês
                        # e calcular uma média ponderada por número de projetos
                        projetos_fechados_mes = detalhes_por_mes[mes_key].get('projetos_fechados', 0)
                        if projetos_fechados_mes > 0:
                            # Adiciona o tempo médio do mês, repetido pelo número de projetos
                            # (aproximação para média ponderada)
                            tempos_vida_todos_projetos.extend([tmv_mes] * projetos_fechados_mes)
            
            if tempos_vida_todos_projetos:
                tempo_medio_vida_geral = round(sum(tempos_vida_todos_projetos) / len(tempos_vida_todos_projetos), 1)
                logger.info(f"📊 Tempo médio de vida consolidado: {tempo_medio_vida_geral} dias (baseado em {len(tempos_vida_todos_projetos)} projetos)")
            
            # Calcula TOTAL das horas incrementais (não média)
            total_horas_incrementais_periodo = round(total_horas_trabalhadas, 1)
            
            # Log das horas calculadas
            if lista_horas_mensais:
                logger.info(f"📊 Horas incrementais por mês: {[round(h, 1) for h in lista_horas_mensais]}")
                logger.info(f"📊 Total de horas trabalhadas no período: {total_horas_incrementais_periodo}")
                logger.info(f"📊 Validação (soma manual): {round(sum(lista_horas_mensais), 1)}")
            
            # === DISTRIBUIÇÃO POR SQUAD (CONSOLIDADA) ===
            # Agora os arquivos mensais já têm os squads classificados corretamente
            # Podemos usar diretamente os dados dos novos projetos mensais
            
            logger.info(f"📊 === CALCULANDO DISTRIBUIÇÃO BASEADA NOS NOVOS PROJETOS MENSAIS ===")
            
            # Coleta dados dos novos projetos por squad de cada mês
            distribuicao_mensal = {'AZURE': 0, 'M365': 0, 'DATA&POWER': 0}
            projetos_nao_classificados = 0
            
            for mes_key in meses_validos:
                dados_mes = dados_por_mes.get(mes_key, {})
                if 'novos_projetos' in dados_mes:
                    novos_projetos_data = dados_mes['novos_projetos']
                    total_mes = novos_projetos_data.get('total', 0)
                    
                    if 'por_squad' in novos_projetos_data:
                        squad_mes = novos_projetos_data['por_squad']
                        logger.info(f"📊 {mes_key.upper()}: {squad_mes} (Total: {total_mes})")
                        
                        # Soma os valores, mapeando os nomes corretamente
                        azure_mes = squad_mes.get('AZURE', 0)
                        m365_mes = squad_mes.get('M365', 0)  
                        data_mes = squad_mes.get('DATA E POWER', 0)
                        
                        distribuicao_mensal['AZURE'] += azure_mes
                        distribuicao_mensal['M365'] += m365_mes
                        distribuicao_mensal['DATA&POWER'] += data_mes
                        
                        # Verifica se há projetos não classificados por squad
                        soma_squad = azure_mes + m365_mes + data_mes
                        if total_mes > soma_squad:
                            nao_classificados = total_mes - soma_squad
                            projetos_nao_classificados += nao_classificados
                            logger.info(f"⚠️ {mes_key.upper()}: {nao_classificados} projetos não classificados por squad")
                    else:
                        # Se não tem dados por squad mas tem total, conta como não classificados
                        if total_mes > 0:
                            projetos_nao_classificados += total_mes
                            logger.info(f"⚠️ {mes_key.upper()}: {total_mes} projetos não classificados (sem dados por squad)")
                elif 'abertos_mes' in dados_mes:
                    # Fallback: se não tem novos_projetos mas tem dados do mês
                    total_mes = dados_mes.get('abertos_mes', 0)
                    if total_mes > 0:
                        projetos_nao_classificados += total_mes
                        logger.info(f"⚠️ {mes_key.upper()}: {total_mes} projetos não classificados (usando fallback)")
            
            logger.info(f"📊 Total de projetos não classificados detectados: {projetos_nao_classificados}")
            
            # Calcula discrepância total entre projetos abertos e squads classificados
            total_squad_calculado = sum(distribuicao_mensal.values())
            discrepancia_total = total_projetos_abertos - total_squad_calculado
            
            logger.info(f"📊 === VERIFICAÇÃO DE CONSISTÊNCIA ===")
            logger.info(f"📊 Projetos abertos no período: {total_projetos_abertos}")
            logger.info(f"📊 Projetos classificados por squad: {total_squad_calculado}")
            logger.info(f"📊 Discrepância detectada: {discrepancia_total}")
            
            # Se há discrepância grande, tenta recalcular usando os dados dos arquivos mensais diretamente
            if abs(discrepancia_total) > 5:  # Tolerância de 5 projetos
                logger.info(f"📊 Discrepância significativa detectada ({discrepancia_total}) - recalculando com dados diretos dos arquivos")
                
                # Recalcula usando os dados brutos dos arquivos mensais
                distribuicao_recalculada = {'AZURE': 0, 'M365': 0, 'DATA&POWER': 0}
                total_recalculado = 0
                
                for mes_key in meses_validos:
                    if mes_key in dados_por_mes:
                        dados_mes_raw = dados_por_mes[mes_key]
                        info_mes = self.meses_disponiveis[mes_key]
                        
                        # Filtra projetos novos do mês usando DataInicio
                        if 'DataInicio' in dados_mes_raw.columns:
                            try:
                                dados_mes_copy = dados_mes_raw.copy()
                                dados_mes_copy['DataInicio'] = pd.to_datetime(dados_mes_copy['DataInicio'], errors='coerce')
                                
                                # Filtra por mês/ano correto
                                filtro_mes = dados_mes_copy['DataInicio'].dt.strftime('%Y-%m') == info_mes['filtro_mes']
                                projetos_novos_mes = dados_mes_copy[filtro_mes]
                                
                                logger.info(f"📊 {mes_key.upper()}: {len(projetos_novos_mes)} projetos novos encontrados diretamente")
                                
                                # Conta por squad se a coluna existe
                                if 'Squad' in projetos_novos_mes.columns:
                                    squad_counts = projetos_novos_mes['Squad'].value_counts()
                                    
                                    # Mapeia os nomes corretamente
                                    azure_count = 0
                                    m365_count = 0 
                                    data_count = 0
                                    
                                    for squad, count in squad_counts.items():
                                        if pd.isna(squad):
                                            continue
                                        squad_str = str(squad).strip()
                                        
                                        if squad_str.upper() in ['AZURE', 'Azure']:
                                            azure_count += count
                                        elif squad_str.upper() in ['M365']:
                                            m365_count += count
                                        elif 'DATA' in squad_str.upper() or 'POWER' in squad_str.upper():
                                            data_count += count
                                    
                                    distribuicao_recalculada['AZURE'] += azure_count
                                    distribuicao_recalculada['M365'] += m365_count  
                                    distribuicao_recalculada['DATA&POWER'] += data_count
                                    
                                    total_mes_direto = azure_count + m365_count + data_count
                                    total_recalculado += total_mes_direto
                                    
                                    logger.info(f"📊 {mes_key.upper()} direto: AZURE={azure_count}, M365={m365_count}, DATA&POWER={data_count}, Total={total_mes_direto}")
                                
                            except Exception as e:
                                logger.warning(f"⚠️ Erro ao recalcular {mes_key}: {e}")
                
                if total_recalculado > 0:
                    logger.info(f"📊 === RESULTADO RECALCULADO ===")
                    logger.info(f"📊 AZURE: {distribuicao_recalculada['AZURE']}")
                    logger.info(f"📊 M365: {distribuicao_recalculada['M365']}")  
                    logger.info(f"📊 DATA&POWER: {distribuicao_recalculada['DATA&POWER']}")
                    logger.info(f"📊 Total recalculado: {total_recalculado}")
                    
                    # Usa o resultado recalculado
                    distribuicao_mensal = distribuicao_recalculada.copy()
                    
                    # Ajusta o total se necessário
                    if total_recalculado != total_projetos_abertos:
                        logger.info(f"📊 Ajustando total de {total_recalculado} para {total_projetos_abertos}")
                else:
                    logger.warning("⚠️ Recálculo não produziu resultados válidos")
            
            total_distribuicao = sum(distribuicao_mensal.values())
            
            logger.info(f"📊 === RESULTADO FINAL DA DISTRIBUIÇÃO ===")
            logger.info(f"📊 AZURE: {distribuicao_mensal['AZURE']}")
            logger.info(f"📊 M365: {distribuicao_mensal['M365']}")  
            logger.info(f"📊 DATA&POWER: {distribuicao_mensal['DATA&POWER']}")
            logger.info(f"📊 Total: {total_distribuicao}")
            
            distribuicao_squad_geral = {
                'total_squad': distribuicao_mensal,
                'status_squad': {},
                'total_geral': total_distribuicao
            }
            
            logger.info(f"📊 === COMPARAÇÃO PROJETOS ABERTOS ===")
            logger.info(f"📊 Projetos abertos (soma novos mensais): {total_projetos_abertos}")
            logger.info(f"📊 Projetos abertos (distribuição por squad): {total_distribuicao}")
            
            # Verifica se os valores batem
            if total_distribuicao == total_projetos_abertos:
                logger.info(f"✅ Valores consistentes: {total_projetos_abertos}")
            else:
                logger.warning(f"⚠️ Ainda há discrepância: {total_distribuicao} vs {total_projetos_abertos}")
                # Mantém o total validado mas força consistência
                distribuicao_squad_geral['total_geral'] = total_projetos_abertos
            
            # Monta resultado final
            resultado = {
                'periodo': {
                    'inicio': meses_validos[0],
                    'fim': meses_validos[-1],
                    'descricao': f"{self.meses_disponiveis[meses_validos[0]]['nome']} a {self.meses_disponiveis[meses_validos[-1]]['nome']}"
                },
                'kpis_gerais': {
                    'projetos_fechados': total_projetos_fechados,
                    'projetos_abertos': total_projetos_abertos,
                    'horas_trabalhadas': total_horas_incrementais_periodo,
                    'eficiencia_recursos': eficiencia_recursos_geral,
                    'taxa_entrega_prazo': taxa_prazo_geral,
                    'tempo_medio_vida': tempo_medio_vida_geral,
                    'projetos_no_prazo': total_projetos_no_prazo_consolidado,
                    'projetos_com_prazo': total_projetos_com_prazo_consolidado,
                    'distribuicao_faturamento': total_faturamento,
                    'distribuicao_squad': distribuicao_squad_geral
                },
                'detalhes_mensais': detalhes_por_mes,
                'success': True,
                'message': f'Período processado com sucesso: {len(meses_validos)} meses analisados'
            }
            
            logger.info(f"✅ Status Report por período concluído: {len(meses_validos)} meses processados")
            return resultado
            
        except Exception as e:
            logger.error(f"❌ Erro geral ao processar período histórico: {str(e)}")
            return self._criar_resultado_vazio(f"Erro ao processar período: {str(e)}")
    
    def _calcular_horas_incrementais(self, dados_mes_atual, dados_mes_anterior, nome_mes):
        """
        Calcula as horas incrementais trabalhadas no mês atual comparando com o mês anterior
        
        Args:
            dados_mes_atual: DataFrame do mês atual
            dados_mes_anterior: DataFrame do mês anterior (ou None se for o primeiro mês)
            nome_mes: Nome do mês para logs
        
        Returns:
            float: Horas incrementais trabalhadas no mês
        """
        try:
            # Projetos com ajustes retroativos específicos para ignorar (apenas as horas)
            PROJETOS_OUTLIERS_ABRIL = {
                '6889': 'Marilan - ajuste retroativo',
                '5481': 'PHARLAB - ajuste retroativo', 
                '4956': 'Tuper - ajuste retroativo',
                '6574': 'ENFORCE - ajuste retroativo'
            }
            
            # Mapeamento de mês atual -> arquivo do mês anterior
            MAPEAMENTO_MES_ANTERIOR = {
                'JANEIRO': None,  # Janeiro não tem mês anterior disponível
                'FEVEREIRO': 'dadosr_apt_jan.csv',
                'MARÇO': 'dadosr_apt_fev.csv', 
                'ABRIL': 'dadosr_apt_mar.csv',
                'MAIO': 'dadosr_apt_abr.csv'
            }
            
            if dados_mes_anterior is None:
                # CASO GERAL: Se qualquer mês for selecionado individualmente, carrega o mês anterior automaticamente
                mes_key = nome_mes.upper()
                arquivo_anterior = MAPEAMENTO_MES_ANTERIOR.get(mes_key)
                
                if arquivo_anterior:
                    logger.info(f"   🔄 {nome_mes} selecionado individualmente - carregando mês anterior para cálculo incremental")
                    try:
                        # Carrega dados do mês anterior automaticamente
                        dados_anterior = self._carregar_dados_mes_historico(arquivo_anterior)
                        if not dados_anterior.empty:
                            logger.info(f"   ✅ Mês anterior carregado com {len(dados_anterior)} registros para cálculo incremental")
                            # Recursão com os dados do mês anterior
                            return self._calcular_horas_incrementais(dados_mes_atual, dados_anterior, nome_mes)
                        else:
                            logger.warning(f"   ⚠️ Não foi possível carregar dados do mês anterior - usando horas totais")
                    except Exception as e:
                        logger.warning(f"   ⚠️ Erro ao carregar mês anterior: {str(e)} - usando horas totais")
                else:
                    logger.info(f"   ℹ️ {nome_mes} não tem mês anterior disponível - usando horas totais")
                
                # Primeiro mês: todas as horas são incrementais
                horas_total = dados_mes_atual['HorasTrabalhadas'].fillna(0).sum()
                
                # APLICAR FILTRO DE OUTLIERS ESPECÍFICO PARA ABRIL
                if nome_mes.upper() == 'ABRIL':
                    logger.info(f"   🟦 {nome_mes} (primeiro mês): {horas_total:.1f}h totais ANTES do filtro")
                    
                    # Aplica o mesmo filtro de outliers
                    dados_atual = dados_mes_atual[['Numero', 'HorasTrabalhadas']].copy()
                    dados_atual['HorasTrabalhadas'] = pd.to_numeric(dados_atual['HorasTrabalhadas'], errors='coerce').fillna(0)
                    dados_atual = dados_atual.groupby('Numero')['HorasTrabalhadas'].max().reset_index()
                    
                    horas_filtradas = 0
                    projetos_filtrados = 0
                    
                    for idx, row in dados_atual.iterrows():
                        numero_str = str(row['Numero'])
                        if numero_str in PROJETOS_OUTLIERS_ABRIL:
                            horas_original = row['HorasTrabalhadas']
                            horas_total -= horas_original  # Remove as horas do outlier
                            horas_filtradas += horas_original
                            projetos_filtrados += 1
                            logger.info(f"   🚫 Projeto {numero_str} ({PROJETOS_OUTLIERS_ABRIL[numero_str]}): {horas_original:.1f}h filtradas")
                    
                    if projetos_filtrados > 0:
                        logger.info(f"   🟦 {nome_mes} (primeiro mês): {projetos_filtrados} projetos filtrados ({horas_filtradas:.1f}h removidas)")
                    
                    logger.info(f"   🟦 {nome_mes} (primeiro mês): {horas_total:.1f}h totais APÓS filtro")
                else:
                    logger.info(f"   🟦 {nome_mes} (primeiro mês): {horas_total:.1f}h totais")
                
                return horas_total
            
            # Prepara dados para comparação por projeto
            atual = dados_mes_atual[['Numero', 'HorasTrabalhadas']].copy()
            anterior = dados_mes_anterior[['Numero', 'HorasTrabalhadas']].copy()
            
            # Garante que HorasTrabalhadas é numérico
            atual['HorasTrabalhadas'] = pd.to_numeric(atual['HorasTrabalhadas'], errors='coerce').fillna(0)
            anterior['HorasTrabalhadas'] = pd.to_numeric(anterior['HorasTrabalhadas'], errors='coerce').fillna(0)
            
            # Remove duplicatas (mantém o maior valor de horas por projeto)
            atual = atual.groupby('Numero')['HorasTrabalhadas'].max().reset_index()
            anterior = anterior.groupby('Numero')['HorasTrabalhadas'].max().reset_index()
            
            # Merge para comparar projetos comuns
            comparacao = atual.merge(anterior, on='Numero', how='left', suffixes=('_atual', '_anterior'))
            comparacao['HorasTrabalhadas_anterior'] = comparacao['HorasTrabalhadas_anterior'].fillna(0)
            
            # Calcula incremento por projeto
            comparacao['incremento'] = comparacao['HorasTrabalhadas_atual'] - comparacao['HorasTrabalhadas_anterior']
            
            # FILTRO ESPECÍFICO: Ignora horas dos projetos outliers em Abril
            projetos_filtrados = 0
            horas_filtradas = 0
            
            if nome_mes.upper() == 'ABRIL':
                for idx, row in comparacao.iterrows():
                    numero_str = str(row['Numero'])
                    if numero_str in PROJETOS_OUTLIERS_ABRIL:
                        horas_original = row['incremento']
                        comparacao.at[idx, 'incremento'] = 0  # Zera o incremento
                        projetos_filtrados += 1
                        horas_filtradas += max(0, horas_original)
                        logger.info(f"   🚫 Projeto {numero_str} ({PROJETOS_OUTLIERS_ABRIL[numero_str]}): {horas_original:.1f}h filtradas")
            
            # Garante que incrementos negativos sejam zero (correções de dados)
            comparacao['incremento'] = comparacao['incremento'].clip(lower=0)
            
            # Soma total de incrementos
            horas_incrementais = comparacao['incremento'].sum()
            
            # Log detalhado
            projetos_novos = len(comparacao[comparacao['HorasTrabalhadas_anterior'] == 0])
            projetos_continuos = len(comparacao[comparacao['HorasTrabalhadas_anterior'] > 0])
            
            logger.info(f"   🟩 {nome_mes}: {projetos_novos} projetos novos, {projetos_continuos} contínuos")
            if projetos_filtrados > 0:
                logger.info(f"   🟩 {nome_mes}: {projetos_filtrados} projetos filtrados ({horas_filtradas:.1f}h removidas)")
            logger.info(f"   🟩 {nome_mes}: {horas_incrementais:.1f}h incrementais (após filtros)")
            
            return horas_incrementais
            
        except Exception as e:
            logger.error(f"Erro ao calcular horas incrementais para {nome_mes}: {str(e)}")
            # Fallback: retorna horas totais do mês
            return dados_mes_atual['HorasTrabalhadas'].fillna(0).sum()
    
    def _calcular_kpis_mes(self, dados_mes, nome_mes):
        """
        Calcula KPIs avançados para um mês específico com Eficiência Composta
        
        Args:
            dados_mes: DataFrame do mês
            nome_mes: Nome do mês para logs
        
        Returns:
            dict: Dados de KPIs do mês (eficiência composta, taxa de prazo, etc.)
        """
        try:
            # Filtra projetos da CDB DATA SOLUTIONS (mesma lógica do macro)
            if 'Especialista' in dados_mes.columns:
                dados_filtrados = dados_mes[~dados_mes['Especialista'].astype(str).str.upper().isin(['CDB DATA SOLUTIONS'])]
                logger.debug(f"   📊 {nome_mes}: Removidos {len(dados_mes) - len(dados_filtrados)} projetos CDB")
            else:
                dados_filtrados = dados_mes.copy()
            
            # === NOVA LÓGICA: PROJETOS FECHADOS + EM ANDAMENTO ===
            # Status considerados como "ativos" (em andamento)
            status_ativos = ['NOVO', 'AGUARDANDO', 'EM ATENDIMENTO', 'BLOQUEADO']
            status_fechados = ['FECHADO', 'ENCERRADO', 'RESOLVIDO', 'CANCELADO']
            
            # Projetos fechados (lógica original)
            projetos_fechados = dados_filtrados[
                dados_filtrados['Status'].str.upper().isin(status_fechados)
            ].copy()
            
            # Projetos em andamento (nova inclusão)
            projetos_andamento = dados_filtrados[
                dados_filtrados['Status'].str.upper().isin(status_ativos)
            ].copy()
            
            # Combina fechados + em andamento para análise de eficiência composta
            projetos_para_eficiencia = pd.concat([projetos_fechados, projetos_andamento], ignore_index=True)
            
            if len(projetos_para_eficiencia) == 0:
                logger.debug(f"   📊 {nome_mes}: Nenhum projeto para análise de eficiência")
                return {
                    'eficiencia_recursos': 0.0,
                    'eficiencia_composta': 0.0,
                    'eficiencia_horas': 0.0,
                    'eficiencia_prazo': 0.0,
                    'taxa_entrega_prazo': 0.0,
                    'produtividade': 0.0,
                    'horas_estimadas': 0.0,
                    'horas_trabalhadas': 0.0,
                    'projetos_analisados': 0,
                    'projetos_fechados': 0,
                    'projetos_andamento': 0,
                    'projetos_no_prazo': 0,
                    'projetos_com_prazo': 0
                }
            
            # === 1. EFICIÊNCIA DE HORAS (APENAS Projetos Fechados) ===
            # Usa apenas projetos fechados para cálculo de eficiência de horas
            # pois projetos em andamento ainda não finalizaram e podem ter estimativas infladas
            projetos_com_horas = projetos_fechados[
                (projetos_fechados['Horas'].fillna(0) > 0) &
                (projetos_fechados['HorasTrabalhadas'].fillna(0) > 0)
            ].copy()
            
            eficiencia_horas = 0.0
            horas_estimadas_total = 0.0
            horas_trabalhadas_total = 0.0
            
            if len(projetos_com_horas) > 0:
                horas_estimadas_total = projetos_com_horas['Horas'].sum()
                horas_trabalhadas_total = projetos_com_horas['HorasTrabalhadas'].sum()
                
                if horas_estimadas_total > 0 and horas_trabalhadas_total > 0:
                    # FÓRMULA INVERTIDA: (Horas Estimadas / Horas Trabalhadas) * 100  
                    # Maior = melhor (120% = 20% mais eficiente que estimado)
                    eficiencia_horas = round((horas_estimadas_total / horas_trabalhadas_total * 100), 1)
            
            # === 2. EFICIÊNCIA DE PRAZO (Fechados + Em Andamento) ===
            # Mapeia nomes de colunas se necessário
            if 'Resolvido em' in projetos_para_eficiencia.columns:
                projetos_para_eficiencia['DataTermino'] = projetos_para_eficiencia['Resolvido em']
            if 'Vencimento em' in projetos_para_eficiencia.columns:
                projetos_para_eficiencia['VencimentoEm'] = projetos_para_eficiencia['Vencimento em']
            
            # Para projetos EM ANDAMENTO, usa data atual como "data de entrega"
            from datetime import datetime
            data_atual = datetime.now()
            
            # Cria coluna unificada de "data de análise"
            projetos_para_eficiencia['DataAnalise'] = projetos_para_eficiencia['DataTermino'].fillna(data_atual)
            
            # Filtra projetos com datas válidas para análise de prazo
            projetos_com_datas = projetos_para_eficiencia[
                projetos_para_eficiencia['VencimentoEm'].notna() & 
                (projetos_para_eficiencia['VencimentoEm'] != '')
            ].copy()
            
            eficiencia_prazo = 0.0
            projetos_no_prazo = 0
            projetos_com_prazo = 0
            
            logger.debug(f"   📊 {nome_mes}: {len(projetos_com_datas)} projetos com data de vencimento para análise")
            
            if len(projetos_com_datas) > 0:
                try:
                    # Converte datas
                    projetos_com_datas['VencimentoEm'] = pd.to_datetime(
                        projetos_com_datas['VencimentoEm'], 
                        errors='coerce', 
                        dayfirst=True
                    )
                    projetos_com_datas['DataAnalise'] = pd.to_datetime(
                        projetos_com_datas['DataAnalise'], 
                        errors='coerce'
                    )
                    
                    # Normaliza datas
                    projetos_com_datas['VencimentoEm'] = projetos_com_datas['VencimentoEm'].dt.normalize()
                    projetos_com_datas['DataAnalise'] = projetos_com_datas['DataAnalise'].dt.normalize()
                    
                    # Remove projetos com datas inválidas
                    validos_para_prazo = projetos_com_datas.dropna(subset=['VencimentoEm', 'DataAnalise']).copy()
                    
                    logger.debug(f"   📊 {nome_mes}: {len(validos_para_prazo)} projetos válidos para análise de prazo")
                    
                    if not validos_para_prazo.empty:
                        # Aplica MESMA lógica do Status Report mensal para prazo
                        for _, projeto in validos_para_prazo.iterrows():
                            data_analise = projeto['DataAnalise']  # Término (fechados) ou hoje (andamento)
                            data_vencimento = projeto['VencimentoEm']
                            
                            # Início do mês de análise (lógica consistente)
                            inicio_mes_analise = datetime(data_analise.year, data_analise.month, 1)
                            inicio_mes_analise = pd.Timestamp(inicio_mes_analise).normalize()
                            
                            # Projeto no prazo se VencimentoEm >= início do mês de análise
                            if data_vencimento >= inicio_mes_analise:
                                projetos_no_prazo += 1
                        
                        projetos_com_prazo = len(validos_para_prazo)
                        eficiencia_prazo = round((projetos_no_prazo / projetos_com_prazo) * 100, 1)
                        
                        logger.debug(f"   📊 {nome_mes}: {projetos_no_prazo} de {projetos_com_prazo} no prazo ({eficiencia_prazo}%)")
                        
                except Exception as e:
                    logger.warning(f"Erro ao processar datas para {nome_mes}: {str(e)}")
                    eficiencia_prazo = 0.0
                    projetos_no_prazo = 0
                    projetos_com_prazo = 0
            
            # === 3. EFICIÊNCIA COMPOSTA (70% Horas + 30% Prazo) ===
            peso_horas = 0.7  # 70% para eficiência de horas
            peso_prazo = 0.3  # 30% para eficiência de prazo
            
            eficiencia_composta = round(
                (eficiencia_horas * peso_horas) + (eficiencia_prazo * peso_prazo), 1
            )
            
            # === 4. TAXA DE ENTREGA NO PRAZO (apenas projetos fechados - compatibilidade) ===
            taxa_entrega_prazo = 0.0
            if len(projetos_fechados) > 0:
                # Usa apenas projetos fechados para taxa de entrega (lógica original)
                projetos_fechados_com_prazo = projetos_fechados[
                    projetos_fechados['VencimentoEm'].notna() & 
                    projetos_fechados['DataTermino'].notna() &
                    (projetos_fechados['VencimentoEm'] != '') &
                    (projetos_fechados['DataTermino'] != '')
                ].copy()
                
                if len(projetos_fechados_com_prazo) > 0:
                    # Mesmo cálculo original para compatibilidade
                    fechados_no_prazo = 0
                    for _, projeto in projetos_fechados_com_prazo.iterrows():
                        data_termino = pd.to_datetime(projeto['DataTermino'], errors='coerce')
                        data_vencimento = pd.to_datetime(projeto['VencimentoEm'], errors='coerce')
                        
                        if pd.notna(data_termino) and pd.notna(data_vencimento):
                            inicio_mes_entrega = datetime(data_termino.year, data_termino.month, 1)
                            inicio_mes_entrega = pd.Timestamp(inicio_mes_entrega).normalize()
                            
                            if data_vencimento.normalize() >= inicio_mes_entrega:
                                fechados_no_prazo += 1
                    
                    taxa_entrega_prazo = round((fechados_no_prazo / len(projetos_fechados_com_prazo)) * 100, 1)
            
            # === 5. TEMPO MÉDIO DE VIDA (USA EXATAMENTE O MESMO MÉTODO DO MACROSERVICE) ===
            tempo_medio_vida = 0.0
            
            # Usa EXATAMENTE o mesmo método que o MacroService
            try:
                from datetime import datetime
                
                # Determina a data de referência do mês
                meses_map = {
                    'JANEIRO': 1, 'FEVEREIRO': 2, 'MARÇO': 3, 
                    'ABRIL': 4, 'MAIO': 5, 'JUNHO': 6,
                    'JULHO': 7, 'AGOSTO': 8, 'SETEMBRO': 9,
                    'OUTUBRO': 10, 'NOVEMBRO': 11, 'DEZEMBRO': 12
                }
                
                mes_num = meses_map.get(nome_mes.upper(), 1)
                data_ref = datetime(2025, mes_num, 15)  # Meio do mês como referência
                
                # Usa o método EXATO do MacroService
                macro_service = self.macro_service if hasattr(self, 'macro_service') else None
                if macro_service:
                    resultado_tmv = macro_service.calcular_tempo_medio_vida(dados_mes, data_ref)
                    tempo_medio_vida = resultado_tmv.get('media_dias', 0.0)
                    
                    logger.debug(f"   📊 {nome_mes}: TMV usando MacroService = {tempo_medio_vida} dias ({resultado_tmv.get('total_projetos', 0)} projetos)")
                
            except Exception as e:
                logger.warning(f"Erro ao calcular tempo médio de vida usando MacroService para {nome_mes}: {str(e)}")
                tempo_medio_vida = 0.0
            

            
            # === 7. LOGS DETALHADOS ===
            logger.debug(f"   📊 {nome_mes}: Eficiência Horas {eficiencia_horas}%, Eficiência Prazo {eficiencia_prazo}%")
            logger.debug(f"   📊 {nome_mes}: Eficiência Composta {eficiencia_composta}% ({peso_horas*100}% horas + {peso_prazo*100}% prazo)")
            logger.debug(f"   📊 {nome_mes}: {len(projetos_fechados)} fechados, {len(projetos_andamento)} em andamento")
            
            return {
                'eficiencia_recursos': eficiencia_composta,  # Usa eficiência composta como principal
                'eficiencia_composta': eficiencia_composta,  # Nova métrica
                'eficiencia_horas': eficiencia_horas,       # Componente de horas
                'eficiencia_prazo': eficiencia_prazo,       # Componente de prazo  
                'taxa_entrega_prazo': taxa_entrega_prazo,   # Taxa original (apenas fechados)
                'tempo_medio_vida': tempo_medio_vida,
                'horas_estimadas': horas_estimadas_total,
                'horas_trabalhadas': horas_trabalhadas_total,
                'projetos_analisados': len(projetos_para_eficiencia),
                'projetos_fechados': len(projetos_fechados),
                'projetos_andamento': len(projetos_andamento),
                'projetos_no_prazo': projetos_no_prazo,
                'projetos_com_prazo': projetos_com_prazo,
                'tempo_medio_vida': tempo_medio_vida
            }
            
        except Exception as e:
            logger.error(f"Erro ao calcular KPIs para {nome_mes}: {str(e)}")
            return {
                'eficiencia_recursos': 0.0,
                'eficiencia_composta': 0.0,
                'eficiencia_horas': 0.0,
                'eficiencia_prazo': 0.0,
                'taxa_entrega_prazo': 0.0,
                'horas_estimadas': 0.0,
                'horas_trabalhadas': 0.0,
                'projetos_analisados': 0,
                'projetos_fechados': 0,
                'projetos_andamento': 0,
                'projetos_no_prazo': 0,
                'projetos_com_prazo': 0,
                'tempo_medio_vida': 0.0
            }
    
    def _carregar_dados_mes_historico(self, nome_arquivo):
        """
        Carrega dados de um arquivo histórico específico
        """
        try:
            arquivo_path = os.path.join(self.data_dir, nome_arquivo)
            
            if not os.path.exists(arquivo_path):
                logger.error(f"Arquivo histórico não encontrado: {arquivo_path}")
                return pd.DataFrame()
            
            # Usa a mesma lógica do MacroService para carregar
            logger.info(f"Carregando fonte histórica: {arquivo_path}")
            return self.macro_service.carregar_dados(fonte=arquivo_path)
            
        except Exception as e:
            logger.error(f"Erro ao carregar dados históricos de {nome_arquivo}: {str(e)}")
            return pd.DataFrame()
    
    def _criar_resultado_vazio(self, motivo):
        """Cria estrutura vazia para KPIs"""
        return {
            'periodo': {
                'meses_selecionados': [],
                'label': motivo,
                'tipo': 'historico'
            },
            'kpis': {
                'projetos_fechados': 0,
                'projetos_abertos': 0,
                'horas_trabalhadas': 0.0,
                'distribuicao_faturamento': {}
            },
            'detalhes_por_mes': {},
            'primeira_execucao': True,
            'comparacao': None,
            'erro': motivo
        } 