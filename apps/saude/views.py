import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from apps.pessoas.models import Aluno
from .models import QuestionarioSaude
from .forms import RenovarAptidaoForm, QuestionarioSaudeForm
from django.http import Http404


logger = logging.getLogger('gestoredu')

@login_required
@permission_required('saude.view_questionariosaude', raise_exception=True)
def detalhes_questionario_aluno(request, aluno_id):
    """ Exibe os detalhes do questionário de saúde para um aluno específico. """
    aluno = get_object_or_404(Aluno, id=aluno_id)
    
    try:
        # Tenta buscar o questionário associado a este aluno.
        questionario = QuestionarioSaude.objects.get(aluno_id=aluno) 
    except QuestionarioSaude.DoesNotExist:
        # Levanta 404 se não houver questionário para este aluno
        raise Http404("Questionário de Saúde não encontrado para este aluno.")
        
    context = {
        'aluno': aluno,
        'questionario': questionario,
    }
    return render(request, 'saude/detalhes_questionario.html', context)

@login_required
@permission_required('saude.change_questionariosaude', raise_exception=True)
def renovar_atestado_aptidao(request, aluno_id):
    """Permite salvar a data de emissão e upload do arquivo do atestado do aluno especificado."""
    try:
        aluno = get_object_or_404(Aluno, id=aluno_id)
        questionario, created = QuestionarioSaude.objects.get_or_create(aluno=aluno)
    except Exception as e:
        logger.error(f"Erro crítico ao buscar Aluno ID {aluno_id}. Exceção: {str(e)}")
        messages.error(request, "Erro interno ao buscar o registro.")
        url_de_retorno = request.session.get('ultima_tela_lista', 'home')
        return redirect(url_de_retorno)
    
    if created:
        logger.debug(f"Novo QuestionarioSaude criado em branco para o Aluno ID: {aluno.id}")
    
    if request.method == 'POST':
        form = RenovarAptidaoForm(request.POST, request.FILES, instance=questionario)
        if form.is_valid():
            try:
                form.save()
                logger.info(f"Atestado de aptidão atualizado: Aluno ID {aluno.id} | Ação realizada por: {request.user}")
                messages.success(request, f"Atestado de aptidão física de {aluno.primeiro_nome} atualizado com sucesso!")
            except Exception as e:
                logger.error(f"FALHA FATAL ao salvar Aluno ID {aluno.id} pelo usuário {request.user.username}. Erro: {str(e)}")
                messages.error(request, "Erro crítico no servidor ao tentar salvar o registro.")
                
        else:
            logger.warning(
                f"Falha de validação no atestado do Aluno ID {aluno.id} | "
                f"Usuário: {request.user} | Erros: {form.errors.as_json()}"
            )
            messages.error(request, "Erro ao renovar atestado de aptidão física. Verifique se todos os campos foram preenchidos corretamente.")
            
    return redirect('academico:gerenciar_atestados', aluno_id=aluno.id)

@login_required
@permission_required('saude.change_questionariosaude', raise_exception=True)
def editar_questionario_saude(request, aluno_id):
    """Permite editar todos os campos do questionário de saúde de um aluno específico."""
    try:
        aluno = get_object_or_404(Aluno, id=aluno_id)
        questionario, _ = QuestionarioSaude.objects.get_or_create(aluno=aluno)
    except Exception as e:
        logger.error(f"Erro crítico ao buscar Aluno ID {aluno_id}. Exceção: {str(e)}")
        messages.error(request, "Erro interno ao buscar o registro.")
        url_de_retorno = request.session.get('ultima_tela_lista', 'home')
        return redirect(url_de_retorno)
    
    if request.method == "POST":
        logger.info(f"Usuário [{request.user}] iniciou atualização do questionário de saúde do Aluno ID: {aluno.id}")
        form = QuestionarioSaudeForm(request.POST, request.FILES, instance=questionario)
        
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f"Questionário de saúde de {aluno.primeiro_nome} atualizado!")
                logger.info(f"SUCESSO: Questionário do Aluno ID: {aluno.id} atualizado pelo usuário [{request.user}].")
                
                url_de_retorno = request.session.get('ultima_tela_lista', 'home')
                return redirect(url_de_retorno)
            except Exception as e:
                logger.error(f"FALHA FATAL ao salvar QuestionarioSaude ID {questionario.id} pelo usuário {request.user.username}. Erro: {str(e)}")
                messages.error(request, "Erro crítico no servidor ao tentar salvar o registro.")
            
        else:
            logger.warning(
                f"FALHA DE VALIDAÇÃO: Usuário [{request.user}] tentou atualizar Aluno ID: {aluno.id}, "
                f"mas o payload foi rejeitado. Erros: {form.errors.as_json()}"
            )
            
    else:
        form = QuestionarioSaudeForm(instance=questionario, remover_atestados=True)
            
    context = {
        'form': form,
        'aluno': aluno
    }
        
    return render(request, 'pessoas/aluno/editar_questionario_saude.html', context)