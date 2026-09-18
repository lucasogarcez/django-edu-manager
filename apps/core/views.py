import calendar
import json
import openpyxl
from .forms import SugestaoFAQForm, TicketSuporteForm
from .models import CategoriaFAQ, PerguntaFrequente, TicketSuporte
from .utils import get_dashboard_data, get_anos_disponiveis
from datetime import datetime, date
from django.contrib import messages
from django.db.models import Prefetch, Count, Q, F, FloatField, ExpressionWrapper
from django.db.models.functions import Cast, TruncMonth
from django.http import HttpResponse
from django.utils import timezone
from django.contrib.auth import logout
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from openpyxl.styles import Font, Alignment, PatternFill
from apps.academico.models import Matricula, Presenca, Chamada, Turma

def home(request):
    return render(request, 'home.html')

def session_idle_timeout(request):
    """
    Desloga o usuário e mostra a página de aviso de inatividade.
    """
    logout(request) # Garante o logout
    return render(request, 'session_timeout.html')

@login_required
@permission_required('academico.view_fechamentomensal', raise_exception=True)
def relatorios_gerenciais(request):
    hoje = timezone.now().date()
    
    ano_str = request.GET.get('ano', '')
    mes_str = request.GET.get('mes', '')
    semana_str = request.GET.get('semana', '')

    filtro_ano = int(ano_str) if ano_str.isdigit() else hoje.year
    # Se enviar '0' ou vazio, significa "Ano Inteiro"
    filtro_mes = int(mes_str) if mes_str.isdigit() and int(mes_str) > 0 else 0
    filtro_semana = int(semana_str) if semana_str.isdigit() else 0

    # Conta os alunos que estão com status "ATIVA" hoje nas turmas.
    retrato_atual = Matricula.objects.filter(status='ATIVA').aggregate(
        total_ativos=Count('id'),
        esporte_ativos=Count('id', filter=Q(turma_id__modalidade_id__departamento='ESPORTE')),
        lazer_ativos=Count('id', filter=Q(turma_id__modalidade_id__departamento='LAZER')),
    )

    # Conta apenas os eventos que ocorreram no Mês/Ano/Semana selecionado.
    q_tempo = Q(data_inicio__year=filtro_ano)
    if filtro_mes > 0:
        q_tempo &= Q(data_inicio__month=filtro_mes)
        
        # A semana só faz sentido matemático se estivermos dentro de um Mês
        if filtro_semana > 0:
            inicio_dia = (filtro_semana - 1) * 7 + 1
            fim_dia = filtro_semana * 7
            
            # Trava de limite do mês (fevereiro tem 28, outros 31)
            ultimo_dia_mes = calendar.monthrange(filtro_ano, filtro_mes)[1]
            if fim_dia > ultimo_dia_mes or filtro_semana == 5:
                fim_dia = ultimo_dia_mes
                
            data_inicio_semana = date(filtro_ano, filtro_mes, inicio_dia)
            data_fim_semana = date(filtro_ano, filtro_mes, fim_dia)
            
            # Filtro exato de fatiamento
            q_tempo &= Q(data_inicio__gte=data_inicio_semana, data_inicio__lte=data_fim_semana)

    fluxo_periodo = Matricula.objects.filter(q_tempo).aggregate(
        novas_matriculas=Count('id'),
        esporte_matriculas=Count('id', filter=Q(turma_id__modalidade_id__departamento='ESPORTE')),
        lazer_matriculas=Count('id', filter=Q(turma_id__modalidade_id__departamento='LAZER')),
    )

    # Junta os dois dicionários para mandar para a tela
    kpis_executivos = {**retrato_atual, **fluxo_periodo}
    
    # --- MÓDULO 2: Desempenho e Engajamento (Frequência) ---
    
    q_presenca = Q(chamada_id__data_chamada__year=filtro_ano)
    
    if filtro_mes > 0:
        q_presenca &= Q(chamada_id__data_chamada__month=filtro_mes)
        # Aplica o fatiamento de semanas nas chamadas também (se selecionado)
        if filtro_semana > 0:
            q_presenca &= Q(chamada_id__data_chamada__gte=data_inicio_semana, chamada_id__data_chamada__lte=data_fim_semana)
    
    # 1. GRÁFICO: Média de Frequência por Turma (No Mês)
    freq_por_turma = Presenca.objects.filter(q_presenca).values(
        turma_id=F('chamada_id__turma_id__id'),
        modalidade=F('chamada_id__turma_id__modalidade_id__nome'),
        polo=F('chamada_id__turma_id__polo_id__nome')
    ).annotate(
        # Conta quantas presenças e atrasos a turma teve
        qtd_presencas=Count('id', filter=Q(status__in=['PRESENTE', 'ATRASO'])),
        # Conta quantas pessoas responderam a chamada
        qtd_total=Count('id')
    ).annotate(
        # Fórmula: (Presenças * 100) / Total. O Cast transforma Int em Float.
        percentual=ExpressionWrapper(
            Cast('qtd_presencas', FloatField()) * 100.0 / Cast('qtd_total', FloatField()),
            output_field=FloatField()
        )
    ).order_by('-percentual') # Melhores turmas no topo

    # 2. RADAR DE EVASÃO: Top 10 Alunos em Risco (Abaixo de 70% no Mês)
    alunos_em_risco = Presenca.objects.filter(
        q_presenca,
        aluno_id__ativo=True
    ).values(
        id_aluno=F('aluno_id'),
        nome_aluno=F('aluno_id__primeiro_nome'), # Ajuste para o nome do campo no seu model Aluno
        sobrenome_aluno=F('aluno_id__ultimo_nome'),
        modalidade=F('chamada_id__turma_id__modalidade_id__nome')
    ).annotate(
        qtd_presencas=Count('id', filter=Q(status__in=['PRESENTE', 'ATRASO'])),
        qtd_total=Count('id')
    ).annotate(
        percentual=ExpressionWrapper(
            Cast('qtd_presencas', FloatField()) * 100.0 / Cast('qtd_total', FloatField()),
            output_field=FloatField()
        )
    ).filter(percentual__lt=70.0).order_by('percentual')[:10] # Piores no topo (ordem crescente)

    # 3. SÉRIE TEMPORAL: Evolução Mensal da Modalidade (Para o Gráfico de Linhas)
    # Filtra o Ano inteiro, agrupa por Mês e por Modalidade
    evolucao_modalidades = Presenca.objects.filter(
        chamada_id__data_chamada__year=filtro_ano
    ).annotate(
        mes_data=TruncMonth('chamada_id__data_chamada')
    ).values(
        'mes_data', 
        modalidade=F('chamada_id__turma_id__modalidade_id__nome')
    ).annotate(
        qtd_presencas=Count('id', filter=Q(status__in=['PRESENTE', 'ATRASO'])),
        qtd_total=Count('id')
    ).annotate(
        percentual=ExpressionWrapper(
            Cast('qtd_presencas', FloatField()) * 100.0 / Cast('qtd_total', FloatField()),
            output_field=FloatField()
        )
    ).order_by('mes_data')
    
    evolucao_list = []
    for item in evolucao_modalidades:
        evolucao_list.append({
            'mes': item['mes_data'].isoformat() if item['mes_data'] else None,
            'modalidade': item['modalidade'],
            'percentual': round(item['percentual'], 1) if item['percentual'] else 0
        })
    
    # --- MÓDULO 3: Operações Equipe (Polos, Professores e Secretaria) ---

    # 1. AUDITORIA DE POLOS: Quais modalidades estão ativas em cada local?
    # Busca combinações únicas de Polo e Modalidade (Query super leve)
    polos_modalidades_raw = Turma.objects.values(
        nome_polo=F('polo_id__nome'),
        nome_modalidade=F('modalidade_id__nome')
    ).distinct().order_by('nome_polo', 'nome_modalidade')

    # Agrupa em um dicionário para facilitar a renderização HTML: {'FUNEL': ['Futsal', 'Vôlei']}
    auditoria_polos = {}
    for item in polos_modalidades_raw:
        polo = item['nome_polo']
        if polo not in auditoria_polos:
            auditoria_polos[polo] = []
        auditoria_polos[polo].append(item['nome_modalidade'])
        
    lista_polos = [{'nome': p, 'modalidades': m} for p, m in auditoria_polos.items()]
    
    paginator_polos = Paginator(lista_polos, 8) # 8 cards = 2 linhas exatas no Desktop
    page_number_polos = request.GET.get('page_polos')
    auditoria_polos = paginator_polos.get_page(page_number_polos)
    
    custom_range_polos = auditoria_polos.paginator.get_elided_page_range(
        auditoria_polos.number, on_each_side=1, on_ends=1
    )
        
    # Filtro de tempo específico para a Tabela de Chamadas
    q_chamada = Q(data_chamada__year=filtro_ano)
    if filtro_mes > 0:
        q_chamada &= Q(data_chamada__month=filtro_mes)
        if filtro_semana > 0:
            q_chamada &= Q(data_chamada__gte=data_inicio_semana, data_chamada__lte=data_fim_semana)

    # 2. PRODUTIVIDADE DE PROFESSORES: Quantas aulas cada um deu no mês?
    produtividade_prof = Chamada.objects.filter(q_chamada).values(
        nome_prof=F('turma_id__professores__usuario__username')
    ).annotate(
        aulas_dadas=Count('id')
    ).order_by('-aulas_dadas')

    # 3. MÉTRICAS DA SECRETARIA: Matrículas por Atendente no mês
    matriculas_secretaria_raw = Matricula.objects.filter(q_tempo).values(
        atendente=F('realizado_por__first_name')
    ).annotate(
        total=Count('id')
    ).order_by('-total')

    # Calcula a Média de Matrículas (Matemática no Python)
    lista_matriculas_sec = list(matriculas_secretaria_raw)
    media_matriculas_sec = 0
    if lista_matriculas_sec:
        total_mat = sum(item['total'] for item in lista_matriculas_sec)
        media_matriculas_sec = round(total_mat / len(lista_matriculas_sec), 1)
        
    context = {
        'filtro_mes': filtro_mes,
        'filtro_ano': filtro_ano,
        'filtro_semana': str(filtro_semana) if filtro_semana else '',
        'active_dashboard_tab': request.GET.get('tab', 'visao_geral'),
        'anos_disponiveis': get_anos_disponiveis(),
        'lista_meses': [(1, 'Janeiro'), (2, 'Fevereiro'), (3, 'Março'), (4, 'Abril'),
            (5, 'Maio'), (6, 'Junho'), (7, 'Julho'), (8, 'Agosto'),
            (9, 'Setembro'), (10, 'Outubro'), (11, 'Novembro'), (12, 'Dezembro')
        ],
            
        # --- Módulo 1 (Visão Executiva) ---
        'kpis_executivos': kpis_executivos,
            
        # --- Módulo 2 (Saúde das Turmas) ---
        'freq_por_turma': freq_por_turma,
        'alunos_em_risco': alunos_em_risco,
        'evolucao_modalidades_json': json.dumps(evolucao_list), 
            
        # --- Módulo 3 (Operações e Equipe) ---
        'auditoria_polos': auditoria_polos,
        'custom_range_polos': custom_range_polos,
        'produtividade_prof': produtividade_prof,
        'matriculas_secretaria_json': json.dumps(lista_matriculas_sec),
        'media_matriculas_sec': media_matriculas_sec,
    }

    return render(request, 'relatorio_gerencial.html', context)

@login_required
@permission_required('academico.view_fechamentomensal', raise_exception=True)
def exportar_relatorio_excel(request):
    # 1. Captura os mesmos filtros da tela
    agora = datetime.now()
    try:
        ano = int(request.GET.get('ano', agora.year))
        # Se mes for 0 ou não enviado, fica None (Ano todo)
        mes_get = request.GET.get('mes')
        
        if mes_get is not None:
            # Cenário A: O usuário CLICOU em filtrar.
            # Se escolheu "Todo o Ano" (valor "0"), 'mes' vira None.
            # Se escolheu "Novembro" (valor "11"), 'mes' vira 11.
            mes = int(mes_get) if int(mes_get) > 0 else None
        else:
            # Cenário B: O usuário ACABOU DE ENTRAR na página (URL limpa).
            # O padrão deve ser o MÊS ATUAL (igual ao que ele vê na tela).
            mes = agora.month
    except ValueError:
        ano = agora.year
        mes = agora.month

    # 2. Busca os dados usando a MESMA função do dashboard
    dados = get_dashboard_data(periodo_mes=mes, periodo_ano=ano)
    
    # 3. Cria o Arquivo Excel
    workbook = openpyxl.Workbook()
    
    # --- ABA 1: Resumo e Alunos ---
    ws1 = workbook.active
    ws1.title = "Resumo e Alunos"
    
    # Cabeçalho do Relatório
    periodo_str = f"{mes}/{ano}" if mes else f"Ano {ano}"
    ws1.merge_cells('A1:D1')
    ws1['A1'] = f"Relatório Gerencial - {periodo_str}"
    ws1['A1'].font = Font(size=16, bold=True)
    ws1['A1'].alignment = Alignment(horizontal='center')

    # KPIs
    ws1['A3'] = "KPIs Gerais"
    ws1['A3'].font = Font(bold=True)
    
    ws1.append(["Atendimentos", "Matrículas", "Alunos Ativos", "Alunos Inativados"])
    ws1.append([
        dados['kpis']['atendimentos'],
        dados['kpis']['matriculas'],
        dados['kpis']['alunos_ativos'],
        dados['kpis']['alunos_inativados']
    ])
    
    # Tabela de Funcionários
    ws1['A7'] = "Produtividade da Equipe"
    ws1['A7'].font = Font(bold=True)
    
    ws1.append([]) # Linha vazia
    # Cabeçalho da Tabela
    headers_func = ["Funcionário", "Cargo", "Atendimentos", "Matrículas"]
    ws1.append(headers_func)
    
    # Estiliza cabeçalho
    for cell in ws1[9]: # Linha 9 é onde os headers foram escritos
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")

    # Dados
    for func in dados['funcionarios']:
        ws1.append([
            func['nome'],
            func['cargo'],
            func['atend'],
            func['matric']
        ])
        
    # Ajusta largura das colunas
    ws1.column_dimensions['A'].width = 35
    ws1.column_dimensions['B'].width = 20
    ws1.column_dimensions['C'].width = 20
    ws1.column_dimensions['D'].width = 25

    # --- ABA 2: Turmas ---
    ws2 = workbook.create_sheet(title="Saúde das Turmas")
    
    ws2['A1'] = "Detalhamento de Turmas"
    ws2['A1'].font = Font(size=14, bold=True)
    
    headers_turma = ["Modalidade", "Categoria", "Horário", "Equipe", "Alunos", "Capacidade", "Ocupação (%)", "Frequência (%)", "Status"]
    ws2.append([])
    ws2.append(headers_turma)
    
    for cell in ws2[3]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
        

    for t in dados['turmas']:
        # Define status texto
        if t['frequencia'] < 70: status = "CRÍTICO"
        elif t['frequencia'] < 85: status = "ATENÇÃO"
        else: status = "BOM"

        ocupacao = round((t['alunos'] / t['capacidade'] * 100), 1) if t['capacidade'] > 0 else 0
        
        ws2.append([
            t['modalidade'],
            t['categoria'],
            t['horario'],
            t['prof'],
            t['alunos'],
            t['capacidade'],
            f"{ocupacao}%",
            f"{t['frequencia']}%",
            status
        ])

    # Ajusta largura
    ws2.column_dimensions['A'].width = 20
    ws2.column_dimensions['B'].width = 15
    ws2.column_dimensions['C'].width = 10
    ws2.column_dimensions['D'].width = 30
    ws2.column_dimensions['E'].width = 15
    ws2.column_dimensions['F'].width = 15
    ws2.column_dimensions['H'].width = 15
    ws2.column_dimensions['I'].width = 15

    # 4. Prepara a resposta HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename=Relatorio_FUNEL_{ano}_{mes or "Total"}.xlsx'
    
    workbook.save(response)
    return response
    
@login_required
def painel_faq(request):
    """
    Renderiza o painel do FAQ e processa o envio de novas sugestões.
    """
    # 1. PROCESSADOR DE SINAL DE ENTRADA (Post Request)
    if request.method == 'POST':
        form = SugestaoFAQForm(request.POST)
        if form.is_valid():
            nova_pergunta = form.save(commit=False) # Para a gravação na memória RAM
            nova_pergunta.is_publicada = False      # Trava de Segurança: Força o estado Pendente
            nova_pergunta.autor = request.user      # Assinatura digital do remetente
            nova_pergunta.save()                    # Grava fisicamente no banco
            
            messages.success(request, "Sugestão enviada! A sua pergunta foi para a fila de moderação e será publicada em breve.")
            return redirect('faq') # Redireciona para limpar o buffer do formulário (evita duplo clique)
        else:
            messages.error(request, "Falha na validação dos dados. Verifique os campos.")
    else:
        form = SugestaoFAQForm()

    # 2. FILTRO PASSA-ALTA (Exibe apenas as Aprovadas)
    # Utilizamos o Prefetch para garantir que a página carregue APENAS as perguntas onde is_publicada=True
    perguntas_aprovadas = PerguntaFrequente.objects.filter(is_publicada=True)
    
    categorias = CategoriaFAQ.objects.prefetch_related(
        Prefetch('perguntas', queryset=perguntas_aprovadas)
    ).all()

    context = {
        'categorias': categorias,
        'faq_form': form
    }
    return render(request, 'core/faq.html', context)

@login_required
@staff_member_required
def moderar_faq(request):
    """
    Estação de Triagem (Quality Control): 
    Painel exclusivo para administradores avaliarem sugestões do buffer (is_publicada=False).
    """
    # 1. DISJUNTOR DE SEGURANÇA LÓGICA (Relé de Permissão)
    # Apenas usuários com status de 'staff' (ou diretoria) podem acessar este painel.
    if not request.user.is_staff:
        messages.error(request, "Acesso Negado: Você não possui credenciais para a Estação de Moderação.")
        return redirect('faq')

    # 2. PROCESSADOR DE SINAIS DE DECISÃO (Aprovar / Rejeitar)
    if request.method == 'POST':
        acao = request.POST.get('acao') # Pode ser 'aprovar' ou 'rejeitar'
        pergunta_id = request.POST.get('pergunta_id')
        
        # Localiza o registro na memória do banco
        pergunta = get_object_or_404(PerguntaFrequente, id=pergunta_id)

        if acao == 'aprovar':
            # 1. CAPTURA O SINAL CALIBRADO PELO MODERADOR
            nova_pergunta = request.POST.get('pergunta_editada')
            nova_resposta = request.POST.get('resposta_editada')
            
            # 2. ATUALIZA A PLACA NA MEMÓRIA
            if nova_pergunta and nova_resposta:
                pergunta.pergunta = nova_pergunta
                pergunta.resposta = nova_resposta
                pergunta.is_publicada = True
                
                # 3. SOLDA NO BANCO DE DADOS
                pergunta.save()
                messages.success(request, f"A pergunta '{pergunta.pergunta}' foi avalidada e publicada.")
            else:
                messages.error(request, "Falha de I/O: A pergunta e a resposta não podem ficar em branco.")
            
        elif acao == 'rejeitar':
            # Fio Terra: Descarta o pacote de dados permanentemente
            pergunta.delete()
            messages.success(request, "A sugestão foi removida do sistema.")

        # Recarrega o painel após a operação
        return redirect('moderar_faq')

    # 3. LEITURA DE BARRAMENTO (Filtra apenas as perguntas pendentes)
    # Utilizamos select_related para otimizar os JOINs com as tabelas de Categoria e Autor
    perguntas_pendentes = PerguntaFrequente.objects.filter(is_publicada=False).select_related('categoria', 'autor').order_by('id')

    context = {
        'perguntas_pendentes': perguntas_pendentes
    }
    return render(request, 'core/moderar_faq.html', context)

@login_required
def abrir_ticket_suporte(request):
    """ View onde o usuário relata o problema, com fricção educacional. """
    
    if request.method == 'POST':
        form = TicketSuporteForm(request.POST, request.FILES)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.usuario = request.user # Assina digitalmente o ticket
            ticket.save()
            
            # Resposta Psicológica: Dá um senso de que entrou numa fila técnica
            messages.success(request, "Chamado técnico aberto com sucesso! A Engenharia foi notificada e avaliará o seu caso (SLA Padrão: 24 a 48 horas).")
            return redirect('home') # Ou redirecione para uma lista de "Meus Chamados"
    else:
        form = TicketSuporteForm()

    return render(request, 'core/suporte.html', {'form': form})

@login_required
def meus_chamados(request):
    """ 
    Terminal de Telemetria do Usuário: 
    Mostra o histórico e status de todos os chamados abertos por ele.
    """
    # 1. Filtra os tickets pela assinatura digital do usuário logado
    chamados = TicketSuporte.objects.filter(
        usuario=request.user
    ).order_by('-criado_em')

    # 2. Paginação leve (10 por página)
    paginator = Paginator(chamados, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'core/meus_chamados.html', {'page_obj': page_obj})