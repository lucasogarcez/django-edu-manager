import json
import logging
import openpyxl
import unicodedata
from calendar import monthrange
from datetime import datetime, date, time
from config import settings
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.db import transaction
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView
from .models import Turma, TurmaDias, Matricula, Situacao, Chamada, Presenca, DiaSemana, Atestado, PresencaStatus, RegistroAtendimento, Modalidade, Categoria
from .filters import TurmaFilter, ChamadaFilter
from .forms import PresencaFormSet, get_turmas_com_vagas, AtestadoForm, TurmaForm
from .utils import get_alunos_em_risco, get_atestados_vencidos, corrigir_nome_modalidade, corrigir_nome_polo, parse_horario, parse_data, get_dias_canonicos, corrigir_nome_categoria, calcular_status_aluno, ler_ficha_chamada, normalizar_merges, verifica_se_turma_existe, rastrear_placas_docentes, demultiplexar_docentes_m2m
from apps.pessoas.models import Professor, Estagiario, Aluno
from apps.saude.models import QuestionarioSaude
from apps.localizacao.models import Polo
from django.conf import settings

logger = logging.getLogger('gestoredu')

DIA_SEMANA_MAP = {
    0: DiaSemana.SEGUNDA, 1: DiaSemana.TERCA, 2: DiaSemana.QUARTA,
    3: DiaSemana.QUINTA, 4: DiaSemana.SEXTA, 5: DiaSemana.SABADO, 6: DiaSemana.DOMINGO,
}

class TurmaCreateView(PermissionRequiredMixin, CreateView):
    model = Turma
    form_class = TurmaForm
    template_name = 'academico/turma_form.html'
    permission_required = 'academico.add_turma'
    raise_exception=True
    
    @transaction.atomic 
    def form_valid(self, form):
        # 1. Salva a Turma + Professores + Estagiários (tudo nativo do form)
        self.object = form.save()
        
        # 2. Solda as Placas de Expansão (Dias da Semana)
        dias_selecionados = form.cleaned_data.get('dias_semana')
        for dia in dias_selecionados:
            TurmaDias.objects.create(turma_id=self.object, dia_semana=dia)
            
        messages.success(self.request, "Turma criada com sucesso!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('academico:alunos_por_turma', kwargs={'turma_id': self.object.pk})

# ==========================================
# MÓDULO DE RECALIBRAÇÃO (Edição)
# ==========================================
class TurmaUpdateView(PermissionRequiredMixin, UpdateView):
    model = Turma
    form_class = TurmaForm
    template_name = 'academico/turma_form.html'
    permission_required = 'academico.change_turma'
    raise_exception=True
    
    # SENSOR DE RETORNO: Lê a telemetria do banco e injeta no Pino Virtual
    def get_initial(self):
        initial = super().get_initial()
        # Captura os dias da semana atuais desta turma num vetor simples: ['SEG', 'QUA']
        dias_cadastrados = TurmaDias.objects.filter(turma_id=self.object).values_list('dia_semana', flat=True)
        initial['dias_semana'] = list(dias_cadastrados)
        return initial

    @transaction.atomic
    def form_valid(self, form):
        # 1. Atualiza a Turma + Professores + Estagiários na memória
        self.object = form.save()
        
        # 2. Recalibra os Dias (Limpa o barramento antigo e solda os novos pinos)
        TurmaDias.objects.filter(turma_id=self.object).delete() # Remove os curtos velhos
        
        dias_selecionados = form.cleaned_data.get('dias_semana')
        for dia in dias_selecionados:
            TurmaDias.objects.create(turma_id=self.object, dia_semana=dia)
            
        messages.success(self.request, "Dados da turma editados com sucesso.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('academico:alunos_por_turma', kwargs={'turma_id': self.object.pk})

def turmas_disponiveis_json():
    turmas_qs = get_turmas_com_vagas() # Usa a função que já filtra vagas

    data = []
    for turma in turmas_qs.prefetch_related('professores__usuario', 'estagiarios__usuario'): # Otimiza
        vagas_restantes = turma.capacidade - turma.matriculas_ativas_count # (Do annotate no get_turmas_com_vagas)
        
        # Cria os nomes dos professores e estagiários
        prof_nomes = ", ".join([p.usuario.get_full_name() for p in turma.professores.all()])
        est_nomes = ", ".join([e.usuario.get_full_name() for e in turma.estagiarios.all()])
        
        detalhes_display = f"Prof(s): {prof_nomes or 'Nenhum'}"
        if est_nomes:
            detalhes_display += f" | Est: {est_nomes}"
        detalhes_display += f" | Polo: {turma.polo_id.nome}"
        
        data.append({
            'id': turma.id,
            'nome': str(turma), # O __str__ do modelo Turma (que também atualizamos)
            'detalhes': detalhes_display,
            'vagas_restantes': vagas_restantes
        })

    return JsonResponse(data, safe=False)

@login_required
@permission_required('academico.view_turma', raise_exception=True) # Permissão para ver turmas
def listar_turmas(request):
    """ Exibe uma lista de turmas com filtros avançados. """
    
    # 1. Inicia o queryset base, otimizando consultas M2M (professores e dias)
    turma_qs = Turma.objects.prefetch_related(
        'professores__usuario', 'estagiarios__usuario', 'dias'
    ).select_related(
        'modalidade_id', 'polo_id',
    ).distinct().order_by('modalidade_id__nome', 'horario')

    # 2. Aplica os filtros com base nos parâmetros GET (ex: ?modalidade_id=1&categoria=ADULTO)
    turma_filter = TurmaFilter(request.GET, queryset=turma_qs)
    
    # 3. Paginação
    paginator = Paginator(turma_filter.qs, 9) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # get_elided_page_range cria a lista inteligente (ex: 1, ..., 4, 5, 6, ..., 10)
    # on_each_side=1 -> Mostra 1 página ao lado da atual
    # on_ends=1 -> Mostra a primeira e a última página sempre
    custom_page_range = page_obj.paginator.get_elided_page_range(
        page_obj.number, 
        on_each_side=1, 
        on_ends=1
    )
    
    request.session['ultima_tela_lista'] = request.get_full_path()
    
    undo = request.session.get('undo_importacao', None)
    
    qtd_alunos = 0
    qtd_matriculas = 0
    qtd_turmas = 0

    if undo:
        qtd_alunos = len(undo.get('alunos_ids', []))
        qtd_matriculas = len(undo.get('matriculas_ids', []))
        qtd_turmas = 1 if undo.get('turma_id') else 0

    context = {
        'turmas': page_obj, # Passamos apenas a página
        'page_obj': page_obj, # Necessário para os controles no template
        'filter_form': turma_filter.form, # O formulário de filtro para renderizar
        'custom_page_range': custom_page_range,
        'qtd_alunos': qtd_alunos,
        'qtd_matriculas': qtd_matriculas,
        'qtd_turmas': qtd_turmas,
    }
    return render(request, 'academico/listar_turmas.html', context)

@login_required
@permission_required('academico.view_matricula', raise_exception=True) # Permissão para ver matrículas
def alunos_por_turma(request, turma_id):
    turma = get_object_or_404(
        Turma.objects.prefetch_related(
            'professores__usuario',
            'estagiarios__usuario',
            'dias'
        ).select_related('modalidade_id', 'polo_id'), 
        id=turma_id
    )
    
    matriculas_ativas = Matricula.objects.filter(
        turma_id=turma, 
        status=Situacao.ATIVA
    ).select_related('aluno_id').order_by('aluno_id__primeiro_nome', 'aluno_id__ultimo_nome')
    
    # Validação: dia da semana
    hoje_int = timezone.localtime(timezone.now()).weekday()
    hoje_str_enum = DIA_SEMANA_MAP.get(hoje_int)
    
    # Verifica se a string de hoje (ex: 'QUARTA') existe nos dias de aula da turma
    is_dia_de_aula_hoje = False # Começa como Falso
    if hoje_str_enum:
        dias_cadastrados = [dia.dia_semana for dia in turma.dias.all()]
        if hoje_str_enum in dias_cadastrados:
            is_dia_de_aula_hoje = True
    
    context = {
        'turma': turma,
        'matriculas_ativas': matriculas_ativas,
        'is_dia_de_aula_hoje': is_dia_de_aula_hoje,
        'hoje': timezone.localtime(timezone.now()),
    }
    return render(request, 'academico/alunos_por_turma.html', context)

@login_required # Garante que o usuário esteja logado
@permission_required('academico.change_matricula', raise_exception=True) # Exige permissão para 'mudar' matrícula
@require_POST # Só permite requisições POST para esta view
def inativar_matricula(request, matricula_id):
    """ Marca uma matrícula como INATIVA e define a data_fim. """
    matricula = get_object_or_404(Matricula, id=matricula_id)
    turma_id_para_redirect = matricula.turma_id_id # Guarda o ID da turma para redirecionar de volta

    if matricula.status == Situacao.ATIVA:
        matricula.status = Situacao.INATIVA
        matricula.data_fim = timezone.localtime(timezone.now()).date()
        matricula.save()
        messages.success(request, f"Matrícula do aluno {matricula.aluno_id} na turma {matricula.turma_id} foi inativada.")
    else:
        messages.warning(request, "Esta matrícula já estava inativa.")

    # Redireciona de volta para a lista de alunos daquela turma
    return redirect('academico:alunos_por_turma', turma_id=turma_id_para_redirect)

@login_required
@permission_required('academico.view_turma', raise_exception=True)
def minhas_turmas(request):
    """ Exibe uma lista de turmas associadas ao professor ou estagiário logado. """
    
    professor_profile = Professor.objects.filter(usuario=request.user).first()
    estagiario_profile = Estagiario.objects.filter(usuario=request.user).first()

    if not professor_profile and not estagiario_profile:
        messages.error(request, "Você não está cadastrado como professor ou estagiário.")
        return redirect('home')

    # Constrói o filtro Q
    filtro = Q()
    if professor_profile:
        # Filtra turmas que TÊM este professor na lista M2M
        filtro |= Q(professores=professor_profile) 
    if estagiario_profile:
         # Filtra turmas que TÊM este estagiário na lista M2M
        filtro |= Q(estagiarios=estagiario_profile) 

    turmas_qs = Turma.objects.filter(filtro).distinct().prefetch_related(
        'professores__usuario', 
        'estagiarios__usuario', # Adiciona prefetch para estagiários
        'dias'
    ).select_related('modalidade_id', 'polo_id')

    context = {
        'turmas': turmas_qs,
    }
    return render(request, 'academico/minhas_turmas.html', context)

@login_required
@permission_required('academico.add_chamada', raise_exception=True)
@transaction.atomic
def realizar_chamada(request, turma_id):
    qs_turma = Turma.objects.prefetch_related('dias')
    
    if request.method == 'POST':
        # Se for POST (estamos salvando), usamos select_for_update().
        # Isso TRAVA a linha desta turma no banco de dados até o fim da transação.
        # Se outro professor tentar salvar chamada para esta mesma turma no mesmo 
        # instante, ele ficará "na fila" esperando este processo terminar.
        turma = get_object_or_404(qs_turma.select_for_update(), id=turma_id)
    else:
        # Se for GET (apenas visualizando a tela), não precisamos travar o banco.
        # Isso mantém o sistema rápido para quem só está abrindo a página.
        turma = get_object_or_404(qs_turma, id=turma_id)
    
    # --- Lógica de Validação de Dia e Reposição (Mantida) ---
    is_reposicao = request.GET.get('reposicao') == 'true'
    
    data_atual = timezone.localtime(timezone.now())
    hoje_int = data_atual.weekday()
    hoje_str_enum = DIA_SEMANA_MAP.get(hoje_int)
    dia_de_aula_hoje = turma.dias.filter(dia_semana=hoje_str_enum).first()
    
    if not dia_de_aula_hoje and not is_reposicao:
        messages.warning(request, f"Não é possível realizar chamada. Hoje não é um dia de aula agendado para esta turma.")
        return redirect('academico:alunos_por_turma', turma_id=turma.id)
    
    data_hoje = data_atual.date() # Data da chamada (para atestados)
    
    chamada_existente = Chamada.objects.filter(turma_id=turma, data_chamada__date=data_hoje).first()
    if chamada_existente:
        messages.warning(request, f"A chamada para esta turma no dia de hoje já foi realizada.")
        return redirect('academico:detalhe_chamada', chamada_id=chamada_existente.id)
    
    if is_reposicao:
        nome_dia_semana_hoje = DiaSemana(hoje_str_enum).label
        nome_do_dia_hoje = f"Aula de Reposição ({nome_dia_semana_hoje})"
    else:
        nome_do_dia_hoje = dia_de_aula_hoje.get_dia_semana_display()
    # --- Fim da Lógica de Dia ---

    matriculas_ativas = Matricula.objects.filter(
        turma_id=turma, 
        status=Situacao.ATIVA
    ).select_related('aluno_id').order_by('aluno_id__primeiro_nome')
    
    # --- INSTANCIAÇÃO DO FORMSET ---
    # (Movemos para cá para o POST poder usar também)
    formset = PresencaFormSet(request.POST or None, prefix='presenca')

    if request.method == 'POST':
        if formset.is_valid():
            chamada = Chamada.objects.create(
                turma_id=turma,
                data_chamada=data_atual,
                is_reposicao=is_reposicao,
            )
            
            for i, form in enumerate(formset):
                # Garante que estamos pegando o aluno certo (índice alinhado)
                aluno_correspondente = matriculas_ativas[i].aluno_id
                
                # --- VERIFICAÇÃO DE ATESTADO NO POST ---
                # (Segurança para garantir que o atestado seja respeitado mesmo se o HTML for alterado)
                tem_atestado = Atestado.objects.filter(
                    aluno=aluno_correspondente,
                    data_inicio__lte=data_hoje,
                    data_fim__gte=data_hoje
                ).exists()
                
                status_final = form.cleaned_data.get('status')
                obs_final = form.cleaned_data.get('observacoes', '')

                if tem_atestado:
                    status_final = PresencaStatus.ATESTADO
                    if not obs_final:
                        obs_final = "Atestado Médico (Automático)"
                # --- FIM VERIFICAÇÃO ---

                Presenca.objects.create(
                    chamada_id=chamada,
                    aluno_id=aluno_correspondente,
                    status=status_final,
                    observacoes=obs_final
                )
            
            messages.success(request, "Chamada realizada e salva com sucesso!")
            return redirect('academico:detalhe_chamada', chamada_id=chamada.id) # Redireciona para o detalhe
        else:
            messages.error(request, "Erro ao salvar a chamada. Verifique os campos.")
            
    else: # GET
        initial_data = []
        
        # --- PREPARAÇÃO DOS DADOS INICIAIS (ATESTADOS) ---
        for matricula in matriculas_ativas:
            aluno = matricula.aluno_id
            
            atestado_valido = Atestado.objects.filter(
                aluno=aluno,
                data_inicio__lte=data_hoje,
                data_fim__gte=data_hoje
            ).first()
            
            if atestado_valido:
                initial_data.append({
                    'status': PresencaStatus.ATESTADO,
                    'observacoes': f"{atestado_valido.motivo}"
                })
            else:
                initial_data.append({'status': PresencaStatus.PRESENTE})
        
        # Cria o formset com os dados iniciais calculados
        formset = PresencaFormSet(initial=initial_data, prefix='presenca')

        # Desabilita campos visualmente
        for i, form in enumerate(formset):
             if initial_data[i]['status'] == PresencaStatus.ATESTADO:
                 form.fields['status'].widget.attrs['disabled'] = 'disabled'

    alunos_e_formularios = zip(matriculas_ativas, formset)

    context = {
        'turma': turma,
        'formset': formset,
        'alunos_e_formularios': alunos_e_formularios,
        'nome_do_dia_hoje': nome_do_dia_hoje,
        'data_atual': data_atual,
        'is_reposicao': is_reposicao
    }
    return render(request, 'academico/realizar_chamada.html', context)

@login_required
@permission_required('academico.view_chamada', raise_exception=True) # Permissão para Admin
def historico_chamadas_turma(request, turma_id):
    """ Mostra todas as chamadas já realizadas para uma turma (com filtros). """
    turma = get_object_or_404(Turma, id=turma_id)
    
    # Cria o queryset base (apenas para esta turma)
    chamadas_qs = Chamada.objects.filter(
        turma_id=turma
    ).order_by('-data_chamada') # Mais recentes primeiro

    # Aplica os filtros (ex: ?ano=2025&mes=10)
    chamada_filter = ChamadaFilter(request.GET, queryset=chamadas_qs)

    context = {
        'turma': turma,
        'chamadas': chamada_filter.qs, # Passa o queryset JÁ FILTRADO
        'filter_form': chamada_filter.form, # Passa o formulário de filtro
    }
    return render(request, 'academico/historico_chamadas_turma.html', context)

@login_required
@permission_required('academico.view_presenca', raise_exception=True) # Permissão para Admin
def detalhe_chamada(request, chamada_id):
    """ Mostra os detalhes de uma chamada específica (a 'ficha.xlsx'). """
    chamada = get_object_or_404(Chamada.objects.select_related('turma_id'), id=chamada_id)
    
    # Busca todas as presenças daquela chamada, já incluindo os dados do aluno
    presencas = Presenca.objects.filter(
        chamada_id=chamada
    ).select_related('aluno_id').order_by('aluno_id__primeiro_nome')

    context = {
        'chamada': chamada,
        'presencas': presencas,
    }
    return render(request, 'academico/detalhe_chamada.html', context)

@login_required
@permission_required('academico.add_atestado', raise_exception=True)
def gerenciar_atestados(request, aluno_id):
    aluno = get_object_or_404(Aluno, id=aluno_id)
    atestados = Atestado.objects.filter(aluno=aluno)    
    
    if request.method == 'POST':
        form = AtestadoForm(request.POST, request.FILES)
        if form.is_valid():
            atestado = form.save(commit=False)
            atestado.aluno = aluno
            atestado.save()
            messages.success(request, "Atestado adicionado com sucesso.")
            return redirect('academico:gerenciar_atestados', aluno_id=aluno.id)
    else:
        form = AtestadoForm()

    context = {
        'aluno': aluno,
        'atestados': atestados,
        'form': form,
    }
    return render(request, 'academico/gerenciar_atestados.html', context)

@login_required
@permission_required('academico.delete_atestado', raise_exception=True)
def excluir_atestado(request, atestado_id):
    atestado = get_object_or_404(Atestado, id=atestado_id)
    aluno_id = atestado.aluno.id
    atestado.delete()
    messages.success(request, "Atestado removido.")
    return redirect('academico:gerenciar_atestados', aluno_id=aluno_id)

@login_required
@permission_required('academico.change_turma', raise_exception=True)
def relatorio_risco(request):
    # 1. LEITURA DE ESTADO DA IHM (Qual aba o usuário está visualizando?)
    # Se não vier nada na URL, o padrão de fábrica é 'faltas'
    active_tab = request.GET.get('tab', 'faltas') 
    
    # Pega o termo de busca geral
    termo_busca = request.GET.get('q', '').strip()
    
    # Filtro de Remoção de Acentos
    def limpar_texto(texto):
        if not texto:
            return ""
        texto = str(texto).strip().lower()
        return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

    # 2. COLETA DE DADOS BRUTOS (Sem filtro)
    lista_risco = get_alunos_em_risco() 
    atestados_qs = get_atestados_vencidos()
    
    alunos_pendentes_doc = Aluno.objects.filter(
        ativo=True, 
        status_documentacao='PENDENTE'
    ).order_by('primeiro_nome_limpo', 'ultimo_nome_limpo')

    # 3. MULTIPLEXADOR DE FILTRO (Filtra APENAS a aba ativa)
    if termo_busca:
        
        # Limpa a string digitada pelo usuário (Ex: "Âng" -> "ang")
        termo_limpo = limpar_texto(termo_busca)
        
        # CAMINHO A: O usuário está na aba de Faltas
        if active_tab == 'faltas':
            lista_filtrada = []
            
            for aluno in lista_risco:
                # Limpa os nomes que vieram da memória
                nome_limpo = limpar_texto(aluno.get('nome', ''))
                sobrenome_limpo = limpar_texto(aluno.get('sobrenome', ''))
                
                # A comparação agora é perfeita: "ang" in "angela"
                match_nome = termo_limpo in nome_limpo or termo_limpo in sobrenome_limpo
                
                match_modalidade = any(termo_limpo in limpar_texto(t['modalidade']) for t in aluno['turmas_risco'])
                
                if match_nome or match_modalidade:
                    lista_filtrada.append(aluno)
                    
            lista_risco = lista_filtrada
            
        # CAMINHO B: O usuário está na aba de Atestados
        elif active_tab == 'atestados':
            atestados_qs = atestados_qs.filter(
                Q(primeiro_nome_limpo__icontains=termo_limpo) | 
                Q(ultimo_nome_limpo__icontains=termo_limpo)
            )
        
        # CAMINHO C: O usuário está na aba de Documentações Pendentes
        elif active_tab == 'pendentes-doc':
            alunos_pendentes_doc = alunos_pendentes_doc.filter(
                Q(primeiro_nome_limpo__icontains=termo_limpo) | 
                Q(ultimo_nome_limpo__icontains=termo_limpo)
            )

    # 4. CIRCUITO DE PAGINAÇÃO (Mantido independente)
    paginator_faltas = Paginator(lista_risco, 10)
    page_obj_faltas = paginator_faltas.get_page(request.GET.get('page_faltas'))

    paginator_atestados = Paginator(atestados_qs, 10)
    page_obj_atestados = paginator_atestados.get_page(request.GET.get('page_atestados'))
    
    paginator_pendentes_doc = Paginator(alunos_pendentes_doc, 10)
    page_obj_pendentes_doc = paginator_pendentes_doc.get_page(request.GET.get('page_pendentes_doc'))

    custom_range_faltas = page_obj_faltas.paginator.get_elided_page_range(
        page_obj_faltas.number, on_each_side=1, on_ends=1
    )
    
    custom_range_atestados = page_obj_atestados.paginator.get_elided_page_range(
        page_obj_atestados.number, on_each_side=1, on_ends=1
    )
    
    custom_range_pendentes_doc = page_obj_pendentes_doc.paginator.get_elided_page_range(
        page_obj_pendentes_doc.number, on_each_side=1, on_ends=1
    )
    
    request.session['ultima_tela_lista'] = request.get_full_path()

    context = {
        'page_obj': page_obj_faltas,
        'page_obj_atestados': page_obj_atestados,
        'page_obj_pendentes_doc': page_obj_pendentes_doc,
        'custom_range_faltas': custom_range_faltas,
        'custom_range_atestados': custom_range_atestados,
        'custom_range_pendentes_doc': custom_range_pendentes_doc,
        'termo_busca': termo_busca,
        'atestados_vencidos': page_obj_atestados,
        'alunos_pendentes_doc': page_obj_pendentes_doc,
        'total_pendentes_doc': alunos_pendentes_doc.count(),
        'active_tab': active_tab # Injeta o estado atual para o HTML desenhar a aba certa
    }
    
    return render(request, 'academico/relatorios/relatorio_risco.html', context)

@login_required
@permission_required('academico.add_registroatendimento', raise_exception=True)
@require_POST # Garante que só aceita cliques via POST (segurança)
def registrar_atendimento_rapido(request):
    # Cria o registro
    RegistroAtendimento.objects.create(usuario=request.user)
    
    # Feedback visual
    messages.success(request, "Atendimento contabilizado com sucesso!")
    
    # Retorna para a página anterior (onde o usuário estava)
    return redirect(request.META.get('HTTP_REFERER', 'home'))

URL_IMPORTAR_FICHA = 'academico:importar_ficha_chamada'

@login_required
@permission_required('academico.view_chamada', raise_exception=True)
def importar_ficha_chamada_view(request):
    """ View principal: recebe a requisição e direciona para o processamento correto. """
    if request.method == 'POST':
        if 'payload_json' in request.POST:
            return _salvar_dados_importacao(request)
        
        elif request.FILES.get('arquivo_ficha'):
            return _processar_preview_planilha(request)

    return render(request, 'academico/importar_ficha.html')

# -- PROCESSAMENTO E GRAVAÇÃO -- #

def _processar_preview_planilha(request):
    """ Lê a planilha enviada, valida os dados e renderiza a tela de preview (JSON). """
    excel_file = request.FILES.get('arquivo_ficha')
    forcar_bypass = request.POST.get('bypass_atestado') == 'on'
    
    if not excel_file.name.endswith(('.xlsx', '.xlsm', '.xltx', '.xltm')):
        messages.error(request, f"Erro: O arquivo '{excel_file.name}' não é suportado. Por favor, envie uma planilha do Excel (.xlsx).")
        return redirect('academico:importar_ficha_chamada') # Substitua pela sua variável URL_IMPORTAR_FICHA

    logger.info(f"Upload de planilha iniciado pelo usuário {request.user.username}. Arquivo: '{excel_file.name}'. Bypass Manual ativado: {forcar_bypass}")
    
    try:
        wb = openpyxl.load_workbook(excel_file, data_only=True)
        ws = wb.active
        logger.debug("Planilha carregada na memória. Iniciando normalização de células mescladas.")
        normalizar_merges(ws)

        dados = ler_ficha_chamada(ws)
        
        # Remove "Alunos Fantasmas" (linhas vazias do Excel lidas acidentalmente)
        alunos_reais = []
        for aluno in dados.get('alunos', []):
            nome_bruto = aluno.get('nome')
            # Só deixa passar se o nome não for nulo/vazio após retirar os espaços
            if nome_bruto and str(nome_bruto).strip() and str(nome_bruto).strip().lower() not in ['none', 'null']:
                aluno['nascimento'] = parse_data(aluno.get('nascimento'))
                aluno['atestado'] = parse_data(aluno.get('atestado'))
                alunos_reais.append(aluno)
        
        # Substitui a leitura bruta pela leitura filtrada e estabilizada
        dados['alunos'] = alunos_reais

        logger.debug(f"Extração bruta finalizada. Total de alunos reais: {len(dados.get('alunos', []))}")
        
        if not dados.get('modalidade'):
            messages.error(request, "A célula de 'Modalidade' está vazia na planilha. Preencha-a (Ex: Futsal) antes de tentar importar novamente.")
            return redirect(URL_IMPORTAR_FICHA)

        try:
            nome_mod_limpo = corrigir_nome_modalidade(str(dados['modalidade']))
        except ValueError as e:
            messages.error(request, str(e))
            return redirect(URL_IMPORTAR_FICHA)

        horario_obj = parse_horario(dados['horario'])
        if not horario_obj:
            messages.error(request, f"Atenção: O horário '{dados.get('horario')}' não foi reconhecido. O sistema espera formatos como '14:00' ou '14h'. Verifique a célula de Horário.")
        local_limpo = corrigir_nome_polo(dados.get('local'))
        
        _, dias_enums, _ = get_dias_canonicos(str(dados['dias']).replace('Dias', '').replace('-', '').strip())
        
        dias_brutos = [d.value if hasattr(d, 'value') else d for d in dias_enums]
        
        if not dados.get('categoria'):
            messages.error(request, "A célula de 'Categoria' está vazia na planilha. Preencha-a (Ex: Adulto) antes de tentar importar novamente.")
            return redirect(URL_IMPORTAR_FICHA)
        
        try:
            categoria_limpa = corrigir_nome_categoria(str(dados['categoria']))
        except ValueError as e:
            messages.error(request, str(e))
            return redirect(URL_IMPORTAR_FICHA)
        
        nome_prof_planilha = str(dados.get('professor') or "").strip()
        nome_estag_planilha = str(dados.get('estagiario') or "").strip()
        
        estados_nulos = ["", "não informado", "nao informado", "sem professor", "sem estagiário", "sem estagiario", "nenhum"]

        # RELÉ DE PROTEÇÃO PRIMÁRIA (Failsafe)
        # Corta a alimentação do sistema se a malha de comando estiver completamente vazia
        if nome_prof_planilha.lower() in estados_nulos and nome_estag_planilha.lower() in estados_nulos:
            messages.error(request, "Impossível importar: A planilha não possui nenhum Professor ou Estagiário preenchido no cabeçalho. Preencha pelo menos um deles e tente novamente.")
            # Aborta a operação e devolve o operador para a tela de upload
            return redirect(URL_IMPORTAR_FICHA)
        
        professores_encontrados = []
        if nome_prof_planilha.lower() not in estados_nulos:
            professores_encontrados = rastrear_placas_docentes(nome_prof_planilha, 'professor')
            
        estagiarios_encontrados = []
        if nome_estag_planilha.lower() not in estados_nulos:
            estagiarios_encontrados = rastrear_placas_docentes(nome_estag_planilha, 'estagiario')

        turma_id_existente = verifica_se_turma_existe(
            nome_mod_limpo, 
            local_limpo, 
            horario_obj, 
            dias_brutos, 
            professores_encontrados,
            estagiarios_encontrados
        )
        
        if turma_id_existente:
            turma_status = "EXISTENTE"
        else:
            turma_status = "NOVA"
            
        global_override = getattr(settings, 'OBRIGATORIEDADE_GLOBAL_ATESTADO', True)
        
        if global_override:
            # Se a chave mestra da escola obriga atestado, ignora o botão do operador
            exige_atestado_final = True
            if forcar_bypass:
                messages.warning(request, "A não obrigatoriedade de atestado foi ignorada porque a Diretoria ativou a Segurança Máxima Global.")
        else:
            # Se o sistema global for flexível, avaliamos o interruptor local
            if forcar_bypass:
                # O operador decidiu forçar o desligamento do relé para esta importação
                exige_atestado_final = False
            elif turma_id_existente:
                # Sem ordem do operador, obedece à configuração que já está gravada na Turma
                turma_obj = Turma.objects.filter(id=turma_id_existente).first()
                exige_atestado_final = turma_obj.exige_atestado if turma_obj else True
            else:
                # Turma nova e sem bypass do operador nasce com proteção ligada
                exige_atestado_final = True
                
        def is_celula_vazia(valor):
            if not valor:
                return True
            texto = str(valor).strip().lower()
            return texto in ['', '-', 'none', 'null', 'não informado', 'nao informado', 'n/a', 's/a', 'S/A']
            
        alunos_incompletos = []
        for aluno in dados.get('alunos', []):
            falta_nascimento = is_celula_vazia(aluno.get('nascimento'))
            falta_atestado = is_celula_vazia(aluno.get('atestado'))
            
            # A data de nascimento é energia primária (sempre obrigatória).
            # O atestado só é exigido se o relé (exige_atestado_final) estiver fechado.
            if falta_nascimento or (falta_atestado and exige_atestado_final):
                alunos_incompletos.append(aluno.get('nome', 'Sem Nome'))
                
        if alunos_incompletos:
            qtd = len(alunos_incompletos)
            amostra = ", ".join(alunos_incompletos[:2])
            
            # Mensagem de telemetria adaptativa (esconde a palavra 'Atestado' se for bypass)
            if exige_atestado_final:
                msg_alerta = f"Aviso: {qtd} aluno(s) (Ex: {amostra}) estão sem Data de Nascimento ou Atestado."
            else:
                msg_alerta = f"Aviso: {qtd} aluno(s) (Ex: {amostra}) estão sem Data de Nascimento."
                
            messages.warning(request, msg_alerta + " Você DEVE preencher essas datas na tela abaixo clicando em cima delas antes de confirmar.")
        
        ORDEM_MAP = {enum_obj: indice for indice, enum_obj in DIA_SEMANA_MAP.items()}

        # Ordena os componentes pelo índice de clock (0, 1, 2...)
        dias_ordenados = sorted(dias_enums, key=lambda d: ORDEM_MAP.get(d, 99))

        # 3. Extrai diretamente a string que já está embutida no chip do Enum
        dias_formatados = ", ".join([d.value for d in dias_ordenados])
        
        prof_list = [nome.strip() for nome in nome_prof_planilha.split('/') if nome.strip()]
        estag_list = [nome.strip() for nome in nome_estag_planilha.split('/') if nome.strip()]
        
        display_prof = "<br>".join(prof_list)
        display_estag = "<br>".join(estag_list)
        
        json_prof = " / ".join(prof_list)
        json_estag = " / ".join(estag_list)
        
        dados_turma_display = {
            'modalidade': nome_mod_limpo, 'local': local_limpo, 'horario': horario_obj.strftime('%H:%M'),
            'dias': dias_formatados, 'categoria': categoria_limpa, 'status': turma_status, 'id_existente': turma_id_existente,
            'professor': display_prof if display_prof else "Não Informado",
            'estagiario': display_estag if display_estag else "Sem Estagiário",
            'exige_atestado': exige_atestado_final,
        }
        
        dados_turma_json = dados_turma_display.copy()
        dados_turma_json['professor'] = json_prof if json_prof else "Não Informado"
        dados_turma_json['estagiario'] = json_estag if json_estag else "Sem Estagiário"

        lista_alunos = _gerar_preview_alunos(dados.get('alunos', []), turma_id_existente)

        payload_json = json.dumps({'turma': dados_turma_json, 'alunos': lista_alunos}, default=str)
        
        return render(request, 'academico/preview_importacao.html', {
            'turma': dados_turma_display, 
            'alunos': lista_alunos, 
            'payload_json': payload_json
        })
        
    except ValueError as ve:
        # Relé de Intertravamento Rigoroso (Hard Fault) acionado pelo import_utils.py
        messages.error(request, str(ve)) # Mostra a tarja vermelha ao utilizador ("O professor X não existe...")
        return redirect(URL_IMPORTAR_FICHA)

    except Exception as e:
        logger.exception(f"Erro no processamento do arquivo Excel: {str(e)}", exc_info=True)
        messages.error(request, "Falha crítica ao ler o arquivo. Certifique-se de que não há planilhas mescladas incorretamente, senhas no arquivo ou abas ocultas.")
        return redirect(URL_IMPORTAR_FICHA)


def _salvar_dados_importacao(request):
    """ Processa o payload JSON aprovado pelo usuário e salva no banco de dados. """
    logger.info(f"Confirmação de importação recebida do usuário {request.user.username}.")
    json_data = request.POST.get('payload_json')
    
    if not json_data:
        logger.error("Payload JSON vazio ao tentar salvar importação.")
        messages.error(request, "Erro ao importar planilha. Os dados enviados estão vazios.")
        return redirect(URL_IMPORTAR_FICHA)

    try:
        dados = json.loads(json_data)
        logger.debug(f"JSON decodificado. Processando {len(dados.get('alunos', []))} alunos.")
        
        with transaction.atomic():
            turma, turma_status = _persistir_turma(dados['turma'])
            if not turma:
                messages.error(request, "Erro de integridade. Modalidade ou Polo não localizados no banco.")
                return redirect(URL_IMPORTAR_FICHA)

            metricas = _persistir_alunos(dados['alunos'], turma, request.user)

            logger.debug("Gravando estado anterior na sessão para permitir possível desfazer.")
            request.session['undo_importacao'] = {
                'turma_id': turma.id if turma_status == "Criada" else None,
                'alunos_ids': metricas['ids_criados'],
                'matriculas_ids': metricas['ids_matriculas'],
                'alunos_atualizados': metricas['estado_anterior']
            }
            request.session.modified = True
            
            logger.info(f"Gravação no banco de dados concluída. Turma ID: {turma.id} | Novas matrículas: {metricas['qtd_matriculas']}.")
            messages.success(request, f"Sucesso! Turma {turma_status}. {metricas['qtd_matriculas']} alunos matriculados.")
            return redirect('academico:listar_turmas')

    except ValueError as ve:
        logger.warning(f"Transação abortada por regra de negócio: {str(ve)}")
        messages.error(request, str(ve))
        return redirect(URL_IMPORTAR_FICHA)

    except Exception as e:
        logger.error(f"Erro interno durante a transação de banco de dados: {str(e)}", exc_info=True)
        messages.error(request, "Erro interno ao salvar os dados. Por favor, notifique a equipe técnica.")
        return redirect(URL_IMPORTAR_FICHA)
    
# -- FUNÇÕES AUXILIARES DE BANCO DE DADOS -- #

def _persistir_turma(dturma):
    """ Cria uma nova turma ou retorna uma existente com base nos dados. """
    logger.debug(f"Processando persistência da Turma: {dturma['modalidade']} no polo {dturma['local']}.")
    
    mod = Modalidade.objects.filter(nome__iexact=dturma['modalidade']).first()
    polo = Polo.objects.filter(nome__iexact=dturma['local']).first()
    cat = Categoria.objects.filter(nome__iexact=dturma['categoria']).first()
    
    if not mod or not polo or not cat:
        logger.error(f"Falha: Modalidade '{dturma['modalidade']}', Polo '{dturma['local']}' ou Categoria '{dturma['categoria']}' não encontrados no banco.")
        return None, "Erro"

    h_parts = dturma['horario'].split(':')
    horario_obj = time(int(h_parts[0]), int(h_parts[1]))
    _, dias_enums, _ = get_dias_canonicos(dturma['dias'])
    set_dias_novos = set(dias_enums)

    turma_encontrada = None
    candidatas = Turma.objects.filter(modalidade_id=mod, polo_id=polo, horario=horario_obj)
    for cand in candidatas:
        if set(cand.dias.values_list('dia_semana', flat=True)) == set_dias_novos:
            logger.debug(f"Turma existente identificada (ID: {cand.id}). Reutilizando registro.")
            turma_encontrada = cand
            break
        
    if turma_encontrada:
        logger.debug(f"Turma existente identificada (ID: {turma_encontrada.id}). Reutilizando a placa-mãe.")
        turma = turma_encontrada
        status = "Encontrada"
        
        # [MANUTENÇÃO DE HARDWARE M2M] 
        # Removemos os pinos antigos para que a placa reflita exatamente os docentes da NOVA planilha.
        turma.professores.clear()
        turma.estagiarios.clear()
        
        if 'exige_atestado' in dturma:
            turma.exige_atestado = dturma['exige_atestado']
    else:
        capacidade_final = int(dturma.get('capacidade') or 20)
        
        estado_rele_atestado = dturma.get('exige_atestado', True)
        
        turma = Turma.objects.create(
            modalidade_id=mod, polo_id=polo, horario=horario_obj, 
            categoria=cat, capacidade=capacidade_final,
            exige_atestado=estado_rele_atestado,
        )
        for dia in dias_enums:
            TurmaDias.objects.create(turma_id=turma, dia_semana=dia)
        logger.info(f"Nova turma criada no banco de dados (ID: {turma.id}).")
        status = "Criada"

    prof_nome_bruto = str(dturma.get('professor') or "").strip()
    estag_nome_bruto = str(dturma.get('estagiario') or "").strip()

    estados_nulos = ["", "não informado", "nao informado", "sem professor", "sem estagiário", "sem estagiario", "nenhum"]

    # Aciona o Demux para Professores (Lê a string múltipla e solda na turma)
    if prof_nome_bruto.lower() not in estados_nulos:
        demultiplexar_docentes_m2m(turma, prof_nome_bruto, tipo_componente='professor')
    else:
        logger.debug("Sinal nulo no canal de Professores. Pulando soldagem.")

    # Aciona o Demux para Estagiários (Lê a string múltipla e solda na turma)
    if estag_nome_bruto.lower() not in estados_nulos:
        demultiplexar_docentes_m2m(turma, estag_nome_bruto, tipo_componente='estagiario')
    else:
        logger.debug("Sinal nulo no canal de Estagiários. Pulando soldagem.")
    
    turma.save()
    return turma, status


def _persistir_alunos(alunos_dados, turma, user):
    """ Itera sobre os alunos do payload, coordenando a persistência de registros e matrículas. """
    logger.debug("Iniciando iteração para persistência de alunos e matrículas.")
    metricas = {'ids_criados': [], 'ids_matriculas': [], 'estado_anterior': [], 'qtd_matriculas': 0}

    exige_atestado = turma.is_atestado_obrigatorio

    for daluno in alunos_dados:
        nasc = daluno.get('nascimento')
        
        atestado_bruto = daluno.get('data_atestado') or daluno.get('atestado') 

        atestado_limpo = None
        if atestado_bruto and str(atestado_bruto).strip() not in ['', '-']:
            atestado_limpo = atestado_bruto

        # ---------------------------------------------------------------------
        # DISJUNTOR PRIMÁRIO: Nascimento (Sempre obrigatório - Essencial)
        # ---------------------------------------------------------------------
        if not nasc or str(nasc).strip() == '-':
            logger.error(f"[Intertravamento] Matrícula bloqueada. Nascimento ausente para: {daluno.get('nome')}")
            raise ValueError(f"A Data de Nascimento do aluno '{daluno.get('nome')}' é obrigatória para o cadastro.")
        
        # ---------------------------------------------------------------------
        # DISJUNTOR CONDICIONAL (Porta Lógica AND): Atestado Médico
        # Só dispara o desarme SE o atestado estiver vazio E a turma exigir atestado!
        # ---------------------------------------------------------------------
        if exige_atestado and not atestado_limpo:
            logger.error(f"[Intertravamento] Matrícula bloqueada. Atestado ausente para: {daluno.get('nome')}")
            raise ValueError(f"A Data do Atestado do aluno '{daluno.get('nome')}' é obrigatória para esta turma.")
        
        # 1. Busca ou cria o aluno
        aluno = _processar_registro_aluno(daluno, metricas)
        
        # 2. Atualiza os dados de saúde
        _atualizar_questionario_saude(aluno.id, atestado_limpo)
        
        # 3. Efetiva a matrícula
        _processar_matricula_aluno(aluno, turma, daluno.get('status'), user, metricas)

    return metricas

def _processar_registro_aluno(daluno, metricas):
    """ Busca, atualiza ou cria um registro de aluno no banco de dados. """
    parts = daluno['nome'].split()
    p_nome = parts[0]
    u_nome = ' '.join(parts[1:]) if len(parts) > 1 else ''

    # Busca o aluno por ID ou Nome
    aluno = None
    if daluno.get('id'):
        aluno = Aluno.objects.filter(id=daluno['id']).first()
    else:
        aluno = Aluno.objects.filter(primeiro_nome__iexact=p_nome, ultimo_nome__iexact=u_nome).first()

    raw_nasc = daluno.get('nascimento')
    dt_nasc = parse_data(raw_nasc) if raw_nasc and raw_nasc != '-' else None

    if aluno:
        # Registra o estado atual para possível Rollback
        metricas['estado_anterior'].append({
            'id': aluno.id, 
            'primeiro_nome': aluno.primeiro_nome, 
            'ultimo_nome': aluno.ultimo_nome, 
            'data_nascimento': aluno.data_nascimento.isoformat() if aluno.data_nascimento else None
        })
        
        # Atualiza os dados do aluno existente
        aluno.primeiro_nome = p_nome
        aluno.ultimo_nome = u_nome
        if dt_nasc: 
            aluno.data_nascimento = dt_nasc
        aluno.save()
    else:
        # Cria um novo aluno
        aluno = Aluno.objects.create(
            primeiro_nome=p_nome, 
            ultimo_nome=u_nome, 
            data_nascimento=dt_nasc, 
            endereco='Não informado', 
            telefone='0000000000'
        )
        metricas['ids_criados'].append(aluno.id)
        
    return aluno


def _atualizar_questionario_saude(aluno_id, data_atestado_raw):
    """ Atualiza a data do atestado médico do aluno, caso tenha sido fornecida na planilha. """
    dt_atestado = parse_data(data_atestado_raw)
    
    try:
        if dt_atestado:
            # Sua lógica existente de gravação... (exemplo abaixo)
            qs, _ = QuestionarioSaude.objects.get_or_create(aluno_id=aluno_id)
            qs.dt_atestado = dt_atestado
            qs.save()
            logger.debug(f"  -> Questionário de saúde atualizado para o aluno ID {aluno_id}.")
        else:
            # Tolerância a falha (Bypass): Apenas regista que a etapa foi pulada com segurança.
            logger.debug(f"  -> Bypass ativo: Atestado nulo ignorado com sucesso para o aluno ID {aluno_id}.")
                
    except Exception as e:
        logger.warning(f"Falha ao atualizar dados de saúde para o aluno {aluno_id}: {str(e)}")


def _processar_matricula_aluno(aluno, turma, status_excel, user, metricas):
    """ Efetiva a matrícula do aluno na turma caso ele ainda não esteja ativo. """
    if status_excel == 'MATRICULADO':
        return

    matricula_existe = Matricula.objects.filter(
        aluno_id=aluno.id, 
        turma_id=turma.id, 
        status=Situacao.ATIVA
    ).exists()

    if not matricula_existe:
        mat = Matricula.objects.create(
            aluno_id=aluno, 
            turma_id=turma, 
            data_inicio=timezone.localtime(timezone.now()).date(), 
            status=Situacao.ATIVA, 
            realizado_por=user
        )
        metricas['ids_matriculas'].append(mat.id)
        metricas['qtd_matriculas'] += 1

def _gerar_preview_alunos(alunos_brutos, turma_id_existente):
    """ Gera a lista formatada de alunos para a tela de preview. """
    lista_alunos = []
    for aluno_excel in alunos_brutos:
        status, aluno_db = calcular_status_aluno(aluno_excel['nome'], turma_id_existente)
        nasc = aluno_excel.get('nascimento')
        at = aluno_excel.get('atestado')
        
        nasc_date = nasc.date() if isinstance(nasc, datetime) else nasc
        at_date = at.date() if isinstance(at, datetime) else at

        lista_alunos.append({
            'id': aluno_db.id if aluno_db else None,
            'nome': aluno_excel['nome'],
            'nascimento': nasc_date.strftime('%Y-%m-%d') if nasc_date else '-',
            'data_atestado': at_date.strftime('%Y-%m-%d') if at_date else '-',
            'status': status
        })
    return lista_alunos

@login_required
@permission_required('academico.delete_turma', raise_exception=True)
def desfazer_importacao(request):
    undo = request.session.get('undo_importacao')

    if not undo:
        logger.warning("Sinal de Rollback vazio: Nenhuma importação recente encontrada na memória temporária (sessão).")
        messages.warning(request, "Nenhuma importação recente para desfazer.")
        return redirect('academico:listar_turmas')
    
    logger.info(f"Iniciando rotina de Desfazer Importação. Operador: {request.user.username}")

    try:
        with transaction.atomic():
            
            # Reverte alunos atualizados
            alunos_atualizados = undo.get('alunos_atualizados', [])
            logger.debug(f"Restaurando backup de {len(alunos_atualizados)} alunos modificados...")
            
            for data in undo.get('alunos_atualizados', []):
                aluno = Aluno.objects.filter(id=data['id']).first()
                if aluno:
                    aluno.primeiro_nome = data['primeiro_nome']
                    aluno.ultimo_nome = data['ultimo_nome']
                    aluno.data_nascimento = data['data_nascimento']
                    aluno.save()
                    
            # Apaga matrículas
            matriculas_ids = undo.get('matriculas_ids', [])
            logger.debug(f"Deletando {len(matriculas_ids)} matrículas (conexões Aluno-Turma) criadas acidentalmente.")
            Matricula.objects.filter(id__in=undo['matriculas_ids']).delete()

            # Apaga alunos criados
            alunos_ids = undo.get('alunos_ids', [])
            logger.debug(f"Limpando {len(alunos_ids)} novos registros de alunos da base de dados.")
            Aluno.objects.filter(id__in=undo['alunos_ids']).delete()

            # Apaga turma (se foi criada)
            turma_id = undo.get('turma_id')
            if turma_id:
                logger.info(f"Destruindo a Turma gerada na importação (ID: {turma_id}).")
                Turma.objects.filter(id=undo['turma_id']).delete()

        # Limpa a sessão
        request.session.pop('undo_importacao', None)

        logger.info("Rollback de importação concluído com sucesso. Sistema estabilizado.")
        messages.success(request, "Importação desfeita com sucesso.")
    
    except Exception as e:
        logger.error(f"Falha Crítica no Hardware de Rollback: {str(e)}", exc_info=True)
        messages.error(request, "Ocorreu um erro crítico ao tentar desfazer a importação. A equipe técnica já foi notificada via logs.")
        
    return redirect('academico:listar_turmas')

@login_required
@permission_required('academico.view_presenca', raise_exception=True)
def imprimir_ficha_frequencia(request, turma_id, mes, ano):
    turma = get_object_or_404(Turma, id=turma_id)
    
    # 1. DEFINIR O "HOJE" CORRETO PARA EXIBIÇÃO
    # Isso garante que no rodapé saia "09/12/2025 21:15" (Horário de Brasília)
    agora_local = timezone.localtime(timezone.now())

    # 2. DEFINIR O INTERVALO DO MÊS (FILTRO DO BANCO)
    # Precisamos criar datas "Naive" (sem fuso) primeiro e depois torná-las "Aware"
    # considerando o fuso horário local.
    
    _, ultimo_dia = monthrange(ano, mes)
    
    # Cria 01/MM/AAAA 00:00:00 e UD/MM/AAAA 23:59:59
    dt_inicio_naive = datetime(ano, mes, 1, 0, 0, 0)
    dt_fim_naive = datetime(ano, mes, ultimo_dia, 23, 59, 59)
    
    # Converte para Aware usando o Timezone atual do projeto (Brasil)
    # Isso evita o RuntimeWarning
    if settings.USE_TZ:
        dt_inicio = timezone.make_aware(dt_inicio_naive)
        dt_fim = timezone.make_aware(dt_fim_naive)
    else:
        dt_inicio = dt_inicio_naive
        dt_fim = dt_fim_naive
        
    dias_do_mes = range(1, ultimo_dia + 1)
    
    # 3. BUSCAR DADOS
    chamadas_do_mes = turma.chamadas.filter(
        data_chamada__range=(dt_inicio, dt_fim)
    )
    dias_com_aula = {c.dia_local for c in chamadas_do_mes}
    
    reposicoes = chamadas_do_mes.filter(is_reposicao=True).order_by('data_chamada')
    
    lista_datas_reposicao = [r.data_chamada.strftime('%d/%m') for r in reposicoes]
    
    # Busca matrículas ativas nesse período
    matriculas_historicas = Matricula.objects.filter(
        turma_id=turma.id,
        data_inicio__lte=dt_fim
    ).filter(
        Q(data_fim__isnull=True) | Q(data_fim__gte=dt_inicio)
    ).select_related('aluno_id').order_by('aluno_id__primeiro_nome')
    
    # 4. MONTAR MATRIZ (Igual ao anterior)
    dados_tabela = []
    
    for mat in matriculas_historicas:
        linha = {
            'aluno': mat.aluno_id, 
            'dias': [], 
            'total_faltas': 0,
            'status_final': 'Ativo'
        }
        
        # Comparação segura de datas (Date vs Date)
        data_inat = mat.data_fim # Já é date
        
        if data_inat and data_inat <= dt_fim.date():
            linha['status_final'] = f"Inativo em {data_inat.day}/{data_inat.month}"

        presencas = Presenca.objects.filter(
            chamada_id__in=chamadas_do_mes,
            aluno_id=mat.aluno_id 
        ).select_related('chamada_id')
        
        mapa_presenca = {p.chamada_id.dia_local: p.status for p in presencas}
        
        for dia in dias_do_mes:
            data_atual = date(ano, mes, dia) # Date simples
            
            # Verificações de Matrícula
            antes_da_matricula = data_atual < mat.data_inicio
            apos_inativacao = mat.data_fim and data_atual > mat.data_fim
            
            if antes_da_matricula or apos_inativacao:
                sigla = '•'
                
            elif dia in dias_com_aula:
                raw_status = mapa_presenca.get(dia)
                
                # TRATAMENTO DO NONE + MAIÚSCULAS
                if raw_status is None:
                    # Assume presença se não tiver linha no banco mas teve aula
                    status = 'PRESENTE' 
                else:
                    # Converte para string e maiúsculo para garantir
                    status = str(raw_status).strip().upper()

                if status in ['PRESENTE', 'P', 'PRESENT']:
                    sigla = '●'
                elif status in ['FALTA', 'F', 'AUSENTE']:
                    sigla = 'F'
                    linha['total_faltas'] += 1
                elif status in ['FALTA JUSTIFICADA', 'JUSTIFICADA', 'J', 'FJ']:
                    sigla = 'J'
                elif status in ['ATESTADO', 'A']:
                    sigla = 'A'
                elif status in ['ATRASO', 'L']:
                    sigla = '●'
                else:
                    sigla = '?'
            else:
                sigla = ''
            
            linha['dias'].append(sigla)
            
        dados_tabela.append(linha)

    context = {
        'turma': turma,
        'mes': mes,
        'ano': ano,
        'dias_do_mes': dias_do_mes,
        'dados_tabela': dados_tabela,
        'hoje': agora_local,
        'lista_reposicao': lista_datas_reposicao,
    }
    
    return render(request, 'academico/relatorios/ficha_impressao.html', context)