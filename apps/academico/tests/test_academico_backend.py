import pytest
from django.urls import reverse
from django.utils import timezone
from apps.academico.models import Matricula, Situacao, TurmaDias
from apps.academico.forms import MatriculaTurmaForm

@pytest.mark.django_db
def test_matricula_duplicada_form(setup_dados):
    """ Testa se o Form impede matricular na mesma turma duas vezes """
    aluno = setup_dados['aluno']
    turma = setup_dados['turma']
    
    # Já matriculado
    Matricula.objects.create(aluno_id=aluno, turma_id=turma, status=Situacao.ATIVA, data_inicio=timezone.now().date())

    # Tenta matricular de novo na mesma turma
    form = MatriculaTurmaForm(data={'turmas_selecionadas_ids': str(turma.id)}, aluno=aluno)
    
    assert form.is_valid() is False    
    
    erros_reais = form.errors.as_text().lower()
    print(f"\n[Osciloscópio] Erros reais do Form: {erros_reais}\n")
    
    assert "já está matriculado" in form.errors.as_text() # ou onde o erro for adicionado

@pytest.mark.django_db
def test_logica_dia_aula_reposicao(client, setup_dados):
    """ Testa se a view bloqueia dia errado e permite reposição """
    client.force_login(setup_dados['admin_user'])
    turma = setup_dados['turma'] # Tem aulas Segunda e Quarta
    
    # Vamos simular que hoje é DOMINGO (Dia sem aula)
    # Nota: Mockar datas é complexo, então vamos apenas alterar os dias da turma para o teste
    TurmaDias.objects.filter(turma_id=turma).delete() # Remove dias reais
    # Agora a turma não tem aula hoje (seja qual for o dia que você rodar o teste)

    url = reverse('academico:realizar_chamada', kwargs={'turma_id': turma.id})

    # 1. Tenta acessar diretamente (Sem ser dia de aula)
    response = client.get(url)
    # Deve redirecionar (bloqueado)
    assert response.status_code == 302 

    # 2. Tenta acessar como Reposição (?reposicao=true)
    response = client.get(url + '?reposicao=true')
    # Deve permitir (200 OK)
    assert response.status_code == 200
    assert "Aula de Reposição" in response.content.decode()