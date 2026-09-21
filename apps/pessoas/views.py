import json
import unicodedata
from django.views.generic.edit import UpdateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q, Value # Para busca
from django.db.models.functions import Concat
from .forms import AlunoForm
from .models import Aluno
from .services import mesclar_cadastros_aluno
from apps.saude.forms import QuestionarioSaudeForm
from apps.saude.models import QuestionarioSaude
from apps.academico.forms import MatriculaTurmaForm, get_turmas_com_vagas
from apps.academico.models import Matricula, Situacao, Turma

@login_required
@permission_required('pessoas.add_aluno', raise_exception=True)
def cadastro_geral_aluno(request):
    active_tab = 'aluno'
    
    if request.method == 'POST':
        aluno_form = AlunoForm(request.POST)
        questionario_form = QuestionarioSaudeForm(request.POST, request.FILES)
        matricula_turma_form = MatriculaTurmaForm(request.POST, user=request.user)

        if aluno_form.is_valid() and questionario_form.is_valid() and matricula_turma_form.is_valid():
            try:
                with transaction.atomic():
                    # Salva o Aluno
                    aluno = aluno_form.save()
                    
                    # Limpa o slot de memória preenchido pelo Signal para liberar espaço para os dados reais
                    QuestionarioSaude.objects.filter(aluno=aluno).delete()
                    
                    # Salva o Questionário de Saúde
                    questionario = questionario_form.save(commit=False)
                    questionario.aluno = aluno
                    questionario.save()
                    questionario_form.save_m2m()
                    
                    # Cria as Matrículas nas Turmas selecionadas
                    matricula_turma_form.criar_matriculas(aluno)
                    
                return redirect('pessoas:questionario_sucesso')
            except Exception as e:
                # Captura erros da transação ou de criar_matriculas
                # Adiciona o erro a um formulário para exibição (pode ser qualquer um)
                aluno_form.add_error(None, f"Erro ao processar matrícula: {e}") 
                # Tenta definir a aba correta, mas o erro pode ser geral
                if matricula_turma_form.errors: active_tab = 'modalidade'
                elif questionario_form.errors: active_tab = 'questionario'
                else: active_tab = 'aluno'
        else:
            if aluno_form.errors: active_tab = 'aluno'
            elif questionario_form.errors: active_tab = 'questionario'
            elif matricula_turma_form.errors: active_tab = 'modalidade'
    else:
        aluno_form = AlunoForm()
        questionario_form = QuestionarioSaudeForm()
        matricula_turma_form = MatriculaTurmaForm()
        
    # --- BUSCAR E FORMATAR DADOS DAS TURMAS PARA O JS ---
    turmas_qs = get_turmas_com_vagas().prefetch_related(
        'professores__usuario', 
        'estagiarios__usuario'
    )
    turmas_data_for_js = []
    for turma in turmas_qs:
        # Pega a contagem de vagas (já calculada pelo get_turmas_com_vagas)
        vagas_restantes = turma.capacidade - turma.matriculas_ativas_count 
        
        # Formata os nomes dos professores
        prof_nomes = turma.get_professores_nomes()
        # Formata os nomes dos estagiários
        est_nomes = turma.get_estagiarios_nomes()
        
        detalhes_display = f"Prof(s): {prof_nomes}"
        if est_nomes != "Nenhum": # Só adiciona estagiário se houver
            detalhes_display += f" | Est: {est_nomes}"
        detalhes_display += f" | Polo: {turma.polo_id.nome}"
        
        turmas_data_for_js.append({
            'id': turma.id,
            'nome': str(turma), # Usa o __str__ do modelo Turma (que já formatamos)
            'detalhes': detalhes_display, # Exemplo
            'vagas_restantes': vagas_restantes,
            'modalidade': turma.modalidade_id.nome
        })
    
    # Converte a lista Python para uma string JSON
    turmas_json_string = json.dumps(turmas_data_for_js)
        
    context = {
        'aluno_form': aluno_form,
        'aluno_helper': aluno_form.helper,
        
        'questionario_form': questionario_form,
        'questionario_helper': questionario_form.helper,
        
        'matricula_turma_form': matricula_turma_form, 
        'matricula_turma_helper': matricula_turma_form.helper,
        
        'active_tab': active_tab,
        
        'turmas_json': turmas_json_string
    }

    return render(request, 'pessoas/aluno/aluno_questionario_form.html', context)

def questionario_sucesso(request):
    return render(request, 'pessoas/aluno/questionario_sucesso.html')

class ListarAlunosView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Aluno
    template_name = 'pessoas/aluno/listar_alunos.html' # Novo template
    context_object_name = 'alunos' # Nome da variável no template
    permission_required = 'pessoas.view_aluno' # Permissão para ver a lista
    paginate_by = 10 # Adiciona paginação

    def get_queryset(self):
        # Otimização com select_related para evitar o problema N+1 queries
        queryset = super().get_queryset().select_related('questionario_saude').order_by('primeiro_nome_limpo', 'ultimo_nome_limpo')
        
        termo_busca = self.request.GET.get('q', '')
        status_filtro = self.request.GET.get('status', 'ativos')
        
        # Filtra por STATUS
        if status_filtro == 'inativos':
            queryset = queryset.filter(ativo=False)
        elif status_filtro == 'todos':
            pass
        else:
            queryset = queryset.filter(ativo=True)
            
        # Filtra pela BUSCA (q)
        if termo_busca:
            # 1. Filtro Passa-Baixa (Python): Remove acentos e joga pra minúsculo o que o usuário digitou
            # Ex: O usuário digita "JõAo SIlva", o filtro converte para "joao silva"
            termo_limpo = ''.join(c for c in unicodedata.normalize('NFD', str(termo_busca).strip().lower()) if unicodedata.category(c) != 'Mn')
            
            # 2. Conecta nas colunas de Hardware (O campo _limpo que já criamos no models.py)
            queryset = queryset.annotate(
                nome_completo_db_limpo=Concat('primeiro_nome_limpo', Value(' '), 'ultimo_nome_limpo')
            )
            
            # 3. Faz o cruzamento das informações
            queryset = queryset.filter(
                # Busca o termo limpo no nome limpo
                Q(nome_completo_db_limpo__icontains=termo_limpo) | 
                # Continua buscando o termo original nos outros campos
                Q(numero_documento__icontains=termo_busca) |
                Q(telefone__icontains=termo_busca) |
                Q(email__icontains=termo_busca)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        page_obj = context.get('page_obj')
        
        if page_obj:
            # Cria o range inteligente (1 ... 5 6 7 ... 20)
            context['custom_page_range'] = page_obj.paginator.get_elided_page_range(
                page_obj.number, 
                on_each_side=1, 
                on_ends=1
            )
        
        # Pega os parâmetros atuais para manter o estado no template
        termo_busca = self.request.GET.get('q', '')
        status_filtro = self.request.GET.get('status', 'ativos')
        
        context['termo_busca'] = self.request.GET.get('q', '')
        context['status_filtro_atual'] = status_filtro
        
        # Isso preserva a busca atual ao trocar de filtro de status
        context['query_busca'] = f"q={termo_busca}"
        
        importacao = self.request.session.get('ultimo_lote_alunos')
        if importacao:
            context['ids_novos_alunos'] = importacao.get('alunos', [])
            context['resumo_importacao'] = importacao
        else:
            context['ids_novos_alunos'] = []
            context['resumo_importacao'] = None
            
        self.request.session['ultima_tela_lista'] = self.request.get_full_path()
        
        return context
    
class EditarAlunoView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Aluno
    form_class = AlunoForm # Reutiliza o formulário existente
    template_name = 'pessoas/aluno/editar_aluno.html' # Novo template
    permission_required = 'pessoas.change_aluno' # Permissão necessária

    def get_success_url(self):
        url_de_retorno = self.request.session.get('ultima_tela_lista', 'home')
        
        if url_de_retorno:
            return url_de_retorno
        
        return reverse_lazy('pessoas:listar_alunos', kwargs={'pk': self.object.pk})
    
@login_required
@permission_required('pessoas.change_aluno', raise_exception=True) # Ou permissão 'inativar_aluno'
@require_POST
def inativar_aluno(request, pk): # pk é o ID do Aluno
    aluno = get_object_or_404(Aluno, pk=pk)
    
    if aluno.ativo:
        aluno.ativo = False
        aluno.data_inativacao = timezone.now().date()
        aluno.save()
        
        matriculas_ativas = Matricula.objects.filter(
            aluno_id=aluno, 
            status=Situacao.ATIVA
        )
        
        num_matriculas_inativadas = matriculas_ativas.update(
            status=Situacao.INATIVA,
            data_fim=timezone.now().date()
        )
        
        messages.success(request, f"Aluno {aluno} foi inativado do sistema. {num_matriculas_inativadas} matrícula(s) ativa(s) também foram inativadas.")
    else:
        messages.warning(request, f"Aluno {aluno} já estava inativo.")
        
    url_de_retorno = request.session.get('ultima_tela_lista', 'home')
        
    return redirect(url_de_retorno)

@login_required
@permission_required('pessoas.change_aluno', raise_exception=True) # Usa a mesma permissão de edição
@require_POST
def ativar_aluno(request, pk): # pk é o ID do Aluno
    aluno = get_object_or_404(Aluno, pk=pk)
    
    if not aluno.ativo:
        aluno.ativo = True
        aluno.data_inativacao = None # Limpa a data de inativação
        aluno.save()
        messages.success(request, f"Aluno {aluno} foi reativado no sistema. As matrículas anteriores continuam inativas e precisam ser refeitas, se necessário.")
    else:
        messages.warning(request, f"Aluno {aluno} já estava ativo.")
        
    url_de_retorno = request.session.get('ultima_tela_lista', 'home')
        
    return redirect(url_de_retorno)

@login_required
@permission_required('academico.add_matricula', raise_exception=True) # Permissão para criar matrícula
@transaction.atomic
def matricular_aluno_view(request, aluno_id):
    aluno = get_object_or_404(Aluno, id=aluno_id)

    # 1. Pega as turmas em que o aluno JÁ ESTÁ MATRICULADO (ativas)
    turmas_atuais_ids = Matricula.objects.filter(
        aluno_id=aluno,
        status=Situacao.ATIVA
    ).values_list('turma_id_id', flat=True)

    if request.method == 'POST':
        # Passa o 'aluno' para o formulário para a validação de duplicatas
        form = MatriculaTurmaForm(request.POST, aluno=aluno)
        
        if form.is_valid():
            # O 'clean' já validou vagas e duplicatas
            turmas_selecionadas_ids = form.cleaned_data['turmas_selecionadas_ids'] # Pega o QuerySet
            
            try:
                # Trava o banco para evitar "race conditions"
                turmas_objetos = Turma.objects.select_for_update().filter(id__in=turmas_selecionadas_ids)
                for turma_obj in turmas_objetos:
                    matriculas_ativas = Matricula.objects.filter(turma_id=turma_obj, status=Situacao.ATIVA).count()
                    
                    if matriculas_ativas >= turma_obj.capacidade:
                        raise Exception(f"A turma {turma_obj} lotou enquanto você preenchia o formulário.")
                    
                    Matricula.objects.create(
                        aluno_id=aluno,
                        turma_id=turma_obj,
                        data_inicio=timezone.localtime(timezone.now()).date(),
                        status=Situacao.ATIVA,
                        realizado_por=request.user
                    )
                messages.success(request, f"Aluno {aluno} matriculado com sucesso em {len(turmas_selecionadas_ids)} nova(s) turma(s).")
                return redirect('pessoas:listar_alunos') # Volta para a lista de alunos
            
            except Exception as e:
                messages.error(request, f"Ocorreu um erro ao salvar as matrículas: {e}")
    
    else: # Requisição GET
        # Instancia o formulário vazio (passando o aluno para o __init__)
        form = MatriculaTurmaForm(aluno=aluno)

    # --- Prepara o JSON para o Modal ---
    # 2. Pega todas as turmas com vagas
    turmas_com_vagas_qs = get_turmas_com_vagas()
    
    # 3. Filtra o queryset, EXCLUINDO as turmas em que o aluno já está
    turmas_disponiveis_qs = turmas_com_vagas_qs.exclude(id__in=turmas_atuais_ids)

    # 4. Constrói o JSON apenas com as turmas disponíveis
    turmas_data_for_js = []
    for turma in turmas_disponiveis_qs:
        vagas_restantes = turma.capacidade - turma.matriculas_ativas_count
        turmas_data_for_js.append({
            'id': turma.id,
            'nome': str(turma), # Usa o __str__ do modelo
            'detalhes': f"Prof(s): {turma.get_professores_nomes()} | Polo: {turma.polo_id.nome}",
            'vagas_restantes': vagas_restantes,
            'modalidade': turma.modalidade_id.nome
        })
    
    turmas_json_string = json.dumps(turmas_data_for_js)
    
    # Busca as matrículas atuais para exibir na página
    matriculas_atuais_obj = Matricula.objects.filter(
        aluno_id=aluno, 
        status=Situacao.ATIVA
    ).select_related('turma_id')

    context = {
        'aluno': aluno,
        'matricula_turma_form': form, # Nome da variável do form
        'matricula_turma_helper': form.helper,
        'matriculas_atuais': matriculas_atuais_obj, # Lista de turmas atuais
        'turmas_json': turmas_json_string, # JSON para o modal
    }
    return render(request, 'pessoas/aluno/matricular_aluno.html', context)

@login_required
@permission_required('pessoas.change_aluno', raise_exception=True)
def painel_merge_alunos(request):
    """
    Controlador IHM: Recebe os sinais do formulário e aciona o motor de multiplexação.
    """
    if request.method == 'POST':
        id_origem = request.POST.get('aluno_origem')
        id_destino = request.POST.get('aluno_destino')

        # Verificação de Tensão: Os cabos foram plugados?
        if not id_origem or not id_destino:
            messages.error(request, "Falha de Acoplamento: Você deve selecionar o cadastro de origem e o de destino.")
            return redirect('pessoas:painel_merge_alunos')

        # Proteção contra Curto-Circuito
        if id_origem == id_destino:
            messages.error(request, "Curto-Circuito Evitado: O cadastro de origem e destino não podem ser o mesmo terminal.")
            return redirect('pessoas:painel_merge_alunos')

        try:
            # Aciona a Transação Atômica (O serviço que criamos)
            sucesso = mesclar_cadastros_aluno(int(id_origem), int(id_destino))
            
            if sucesso:
                messages.success(request, "Operação concluída: Os dados foram transferidos e o cadastro duplicado foi desfeito com sucesso.")
            return redirect('pessoas:listar_alunos')
            
        except Exception as e:
            # Disjuntor de Segurança Geral
            messages.error(request, f"Falha no barramento durante o merge: {str(e)}")
            return redirect('pessoas:painel_merge_alunos')

    # Rota GET: Carrega o Painel para o Operador
    # Filtramos apenas os alunos ativos para evitar que tentem mesclar fantasmas
    alunos_disponiveis = Aluno.objects.filter(is_merged=False).order_by('primeiro_nome')
    
    context = {
        'alunos': alunos_disponiveis
    }
    return render(request, 'pessoas/aluno/merge_alunos.html', context)