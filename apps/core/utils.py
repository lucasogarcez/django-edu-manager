import datetime
import json
from django.db.models import Count, Q
from django.db.models.functions import ExtractYear
from django.utils import timezone
from apps.pessoas.models import Usuario, Aluno
from apps.academico.models import Turma, Matricula, Presenca, PresencaStatus, Situacao

def formatar_data(data):
    """Formata uma data no formato brasileiro (DD/MM/AAAA)."""
    if isinstance(data, datetime.date):
        return data.strftime('%d/%m/%Y')
    return None

def get_anos_disponiveis():
    """
    Retorna uma lista de anos que possuem matrículas registradas,
    ordenada do mais recente para o mais antigo.
    Ex: [2026, 2025, 2024]
    """
    # Pega todos os anos distintos das datas de início de matrícula
    anos = Matricula.objects.annotate(
        ano=ExtractYear('data_inicio')
    ).values_list('ano', flat=True).distinct().order_by('-ano')
    
    # Se não tiver nada, retorna pelo menos o ano atual
    if not anos:
        return [timezone.localtime(timezone.now()).year]
        
    return list(anos)

def get_dashboard_data(periodo_mes=None, periodo_ano=None):
    """
    Gera os dados para o Dashboard (Home).
    Como não temos o modelo 'Atendimento', a produtividade é medida por 'Matrículas'.
    """
    # Se periodo_mes for 0, consideramos None (Ano todo)
    if periodo_mes == 0:
        periodo_mes = None
    
    
    # Filtro base para as matrículas deste período
    filtro_base_matricula = Q(data_inicio__year=periodo_ano)
    filtro_base_presenca = Q(chamada_id__data_chamada__year=periodo_ano)
    
    # Se tiver MÊS, adicionamos ao filtro
    if periodo_mes:
        filtro_base_matricula &= Q(data_inicio__month=periodo_mes)
        filtro_base_presenca &= Q(chamada_id__data_chamada__month=periodo_mes)
    
    # Filtro simples para usar direto no modelo Matricula (KPIs)
    filtro_usuario_matricula = Q(matriculas_realizadas__data_inicio__year=periodo_ano)
    if periodo_mes:
        filtro_usuario_matricula &= Q(matriculas_realizadas__data_inicio__month=periodo_mes)
        
    filtro_atendimento_rapido = Q(atendimentos_rapidos__data_hora__year=periodo_ano)
    if periodo_mes:
        filtro_atendimento_rapido &= Q(atendimentos_rapidos__data_hora__month=periodo_mes)
        
    # Filtra pela data que o aluno saiu (data_inativacao)
    filtro_inativacao = Q(data_inativacao__year=periodo_ano)
    if periodo_mes:
        filtro_inativacao &= Q(data_inativacao__month=periodo_mes)

    # --- 1. KPIs (Indicadores) ---
    total_matriculas_mes = Matricula.objects.filter(filtro_base_matricula).count()
    
    # Mostra o tamanho atual da escola (independente do mês filtrado, 
    # pois 'ativo' é o estado presente).
    total_alunos_ativos = Aluno.objects.filter(ativo=True).count()
    
    # Mostra quantos saíram naquele mês/ano específico (Churn)
    total_inativados = Aluno.objects.filter(filtro_inativacao, ativo=False).count()

    # --- 2. RANKING DE FUNCIONÁRIOS ---
    # Agrupa por usuário e conta quantas matrículas ele fez (realizado_por) no período
    funcionarios_qs = Usuario.objects.filter(is_active=True).annotate(
        qtd_matriculas=Count('matriculas_realizadas__id', filter=filtro_usuario_matricula, distinct=True),
        qtd_atendimentos_rapidos=Count('atendimentos_rapidos__id', filter=filtro_atendimento_rapido, distinct=True)
    ).prefetch_related('groups').order_by('-qtd_matriculas')

    lista_funcionarios = []
    total_atendimentos_geral = 0
    
    for func in funcionarios_qs:
        
        total_interacoes = func.qtd_atendimentos_rapidos + func.qtd_matriculas
        
        total_atendimentos_geral += total_interacoes
        
        # Verifica os grupos do usuário em memória
        if func.is_superuser:
            cargo = "Administrador"
        elif func.groups.filter(name='Professor').exists():
            cargo = "Professor"
        elif func.groups.filter(name='Estagiário').exists():
            cargo = "Estagiário"
        else:
            # Se for staff mas não tiver grupo definido
            cargo = "Sem grupo"
        
        # Vamos listar todos para o ranking ficar completo
        lista_funcionarios.append({
            'nome': func.get_full_name() or func.username,
            'cargo': cargo,
            'atend': total_interacoes,
            'matric': func.qtd_matriculas
        })
        
    # Ordena por total de interações
    lista_funcionarios.sort(key=lambda x: x['atend'], reverse=True)
    
    # Pega os Top 10 para o gráfico
    top_10_funcionarios = lista_funcionarios[:10]

    # --- 4. SAÚDE DAS TURMAS (Frequência) ---
    # Anota as turmas com o total de alunos ativos
    turmas_qs = Turma.objects.all().annotate(
        total_alunos=Count('matriculas', filter=Q(matriculas__status=Situacao.ATIVA))
    )

    lista_turmas = []

    for t in turmas_qs:
        # Filtra presenças usando o filtro dinâmico (Ano ou Ano+Mês)
        qs_presenca_base = Presenca.objects.filter(filtro_base_presenca, chamada_id__turma_id=t)
        
        total_registros = qs_presenca_base.count()
        presencas = qs_presenca_base.filter(status=PresencaStatus.PRESENTE).count()
        
        # Se não teve aula (chamada) no mês, consideramos 100% ou 0% (depende da regra). 
        # Vamos por 100% para não alarmar turmas novas.
        frequencia = 100 
        
        if total_registros > 0:
            frequencia = int((presencas / total_registros) * 100)

        if frequencia < 70:
            status_code = 'critico'
        elif frequencia < 85:
            status_code = 'atencao' 
        else:
            status_code = 'bom'     

        # Busca nome do professor ou estagiário
        prof = t.professores.first()
        estg = t.estagiarios.first()
        
        if prof:
            # Se seu model usa usuario_id, use prof.usuario_id.get_full_name()
            # Se usa usuario, use prof.usuario.get_full_name()
            nome_prof = prof.usuario.get_full_name() 
        elif estg:
            nome_prof = estg.usuario.get_full_name()
        else:
            nome_prof = "Sem Prof."
            
        lista_turmas.append({
            'id': t.id,
            'nome': str(t),
            
            # Dados separados para o visual limpo:
            'modalidade': t.modalidade_id.nome,       # Ex: "Futsal"
            'categoria': t.categoria.nome,   # Ex: "Juvenil"
            'horario': t.horario.strftime('%H:%M'),   # Ex: "14:00"
            
            'prof': nome_prof,
            'alunos': t.total_alunos,
            'capacidade': t.capacidade,
            'frequencia': frequencia,
            'status_code': status_code,
        })

    # Ordena turmas: as de menor frequência (críticas) aparecem primeiro
    lista_turmas.sort(key=lambda x: x['frequencia'])

    # --- 5. RETORNO DOS DADOS ---
    return {
        'kpis': {
            'matriculas': total_matriculas_mes,
            'atendimentos': total_atendimentos_geral, # Repetimos o valor pois não temos a tabela Atendimento
            'alunos_ativos': total_alunos_ativos,
            'alunos_inativados': total_inativados
        },
        'funcionarios': lista_funcionarios,
        'turmas': lista_turmas,
        
        # JSON Prontos para o Chart.js
        'chart_equipe_labels': json.dumps([f['nome'] for f in top_10_funcionarios]),
        'chart_equipe_data': json.dumps([f['atend'] for f in top_10_funcionarios]),
        
        'chart_turmas_labels': json.dumps([t['nome'] for t in lista_turmas[:20]]),
        'chart_turmas_data': json.dumps([t['frequencia'] for t in lista_turmas[:20]]),
    }