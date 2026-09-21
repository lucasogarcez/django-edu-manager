# conftest.py
import os
import pytest
from apps.pessoas.models import Aluno, Professor
from apps.academico.models import Turma, Modalidade, Polo, DiaSemana, TurmaDias, Categoria
from apps.localizacao.models import Polo
from apps.saude.models import QuestionarioSaude, Doenca, Objetivo
from django.contrib.auth import get_user_model
from django.db import connection

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

User = get_user_model()

@pytest.fixture(autouse=True)
def bypass_firewall_axes(settings):
    """Desativa o intertravamento do django-axes durante a esteira de testes"""
    settings.AXES_ENABLED = False

@pytest.fixture
def setup_dados(db):
    # 1. Criar Usuário Admin (para login)
    admin_user = User.objects.create_user(username='admin_teste', email='admin@teste.com', password='password', is_staff=True, is_superuser=True)

    # 2. Criar Staff (Professor)
    prof_user = User.objects.create_user(username='prof_teste', password='password', is_staff=True, first_name='Professor', last_name='Teste')
    professor = Professor.objects.create(usuario=prof_user)

    # 3. Dados Básicos
    polo = Polo.objects.create(nome="Alpha", endereco="Rua X")
    modalidade = Modalidade.objects.create(nome="Futsal")
    cat = Categoria.objects.create(nome="Adulto")
    
    # 4. Criar Turma (Segunda e Quarta)
    turma = Turma.objects.create(
        modalidade_id=modalidade, polo_id=polo, categoria=cat,
        horario='14:00:00', capacidade=10
    )
    turma.professores.add(professor)
    TurmaDias.objects.create(turma_id=turma, dia_semana=DiaSemana.SEGUNDA)
    TurmaDias.objects.create(turma_id=turma, dia_semana=DiaSemana.QUARTA)
    
    # 5. BUSCAR/CRIAR DOENÇAS E OBJETIVOS ---
    # Como são populações, usamos get_or_create para garantir que existam
    doenca_outra, _ = Doenca.objects.get_or_create(nome="Outra")
    doenca_hipertensao, _ = Doenca.objects.get_or_create(nome="Hipertensão")
    
    objetivo_outro, _ = Objetivo.objects.get_or_create(nome="Outro")
    objetivo_perder_peso, _ = Objetivo.objects.get_or_create(nome="Perder peso")

    # 6. Criar Aluno
    aluno = Aluno.objects.create(
        primeiro_nome="João", ultimo_nome="Silva", cpf="925.528.320-08",
        data_nascimento="2000-01-01", telefone="11999999999", ativo=True
    )

    return {
        'admin_user': admin_user,
        'professor': professor,
        'turma': turma,
        'aluno': aluno,
        'password': 'password',
        'doenca_outra': doenca_outra,
        'doenca_hipertensao': doenca_hipertensao,
        'objetivo_outro': objetivo_outro,
        'objetivo_perder_peso': objetivo_perder_peso,
    }
    
def limpar_banco(db):
    Aluno.objects.all().delete()
    QuestionarioSaude.objects.all().delete()
    
@pytest.fixture(autouse=True)
def fechar_conexoes_banco():
    """
    Descarregador de Corrente: 
    Executa silenciosamente após CADA teste para garantir que o Django 
    soltou os cabos do PostgreSQL, evitando erro de Teardown.
    """
    yield # Deixa o teste rodar normalmente
    
    # Após o teste acabar, força o encerramento da conexão na Thread atual
    connection.close()