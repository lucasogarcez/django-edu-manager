import pytest
from django.utils import timezone
from django.urls import reverse
from apps.academico.models import Matricula, Situacao
from apps.pessoas.models import Aluno

@pytest.mark.django_db
def test_listar_alunos_filtros(client, setup_dados):
    """ Testa se a busca e o filtro de status funcionam """
    client.force_login(setup_dados['admin_user'])
    
    # Cria um aluno inativo para testar o filtro
    Aluno.objects.create(primeiro_nome="Inativo", ultimo_nome="User", cpf="222", data_nascimento="2000-01-01", telefone="00", ativo=False)

    # 1. Testa Busca por nome
    url = reverse('pessoas:listar_alunos')
    response = client.get(url, {'q': 'João'})
    assert len(response.context['alunos']) == 1
    assert response.context['alunos'][0].primeiro_nome == "João"

    # 2. Testa Filtro de Inativos
    response = client.get(url, {'status': 'inativos'})
    assert len(response.context['alunos']) == 1
    assert response.context['alunos'][0].primeiro_nome == "Inativo"

@pytest.mark.django_db
def test_inativar_aluno_cascata(client, setup_dados):
    """ Testa se inativar aluno TAMBÉM inativa as matrículas (Regra de Negócio) """
    client.force_login(setup_dados['admin_user'])
    aluno = setup_dados['aluno']
    turma = setup_dados['turma']

    # 1. Cria uma matrícula ativa
    Matricula.objects.create(aluno_id=aluno, turma_id=turma, data_inicio='2024-01-01', status=Situacao.ATIVA)
    
    # 2. Envia POST para inativar o aluno
    url = reverse('pessoas:inativar_aluno', kwargs={'pk': aluno.id})
    client.post(url)

    # 3. Verificações
    aluno.refresh_from_db()
    assert aluno.ativo is False # Aluno inativado?
    
    matricula = Matricula.objects.get(aluno_id=aluno, turma_id=turma)
    assert matricula.status == Situacao.INATIVA # Matrícula inativada automaticamente?
    assert matricula.data_fim is not None

@pytest.mark.django_db
def test_reativar_aluno_sem_matr(client, setup_dados):
    """ Testa se reativar aluno NÃO reativa matrículas (Regra de Negócio) """
    client.force_login(setup_dados['admin_user'])
    aluno = setup_dados['aluno']
    aluno.ativo = False
    aluno.save()
    
    # Matrícula antiga inativa
    Matricula.objects.create(aluno_id=aluno, turma_id=setup_dados['turma'], status=Situacao.INATIVA, data_inicio=timezone.now().date())

    # Reativa
    url = reverse('pessoas:ativar_aluno', kwargs={'pk': aluno.id})
    client.post(url)

    aluno.refresh_from_db()
    assert aluno.ativo is True
    
    # Matrícula deve continuar inativa!
    assert Matricula.objects.filter(aluno_id=aluno, status=Situacao.INATIVA).exists()