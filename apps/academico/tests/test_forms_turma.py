import pytest
from apps.academico.forms import TurmaForm
from apps.academico.models import Matricula, Situacao

@pytest.mark.django_db
def test_criacao_turma_bloqueada_sem_professor(setup_dados):
    """Verifica se o formulário recusa inicializar uma turma sem docente (Malha Aberta)"""
    turma_existente = setup_dados['turma']
    
    dados_ruidosos = {
        'modalidade_id': turma_existente.modalidade_id.id,
        'polo_id': turma_existente.polo_id.id,
        'capacidade': 20,
        'horario': '16:00',
        'professores': [], # Desconectado
        'estagiarios': [], # Desconectado
        'dias_semana': ['SEG', 'SEX'],
    }
    
    form = TurmaForm(data=dados_ruidosos)
    
    assert not form.is_valid()
    assert "A turma não pode operar sem comando" in str(form.errors.get('__all__'))

@pytest.mark.django_db
def test_edicao_turma_bloqueada_por_sobrecarga(setup_dados):
    """Verifica se o sensor de carga impede reduzir a capacidade abaixo do número de alunos ativos"""
    turma = setup_dados['turma']
    aluno = setup_dados['aluno']
    professor = setup_dados['professor']
    
    # 1. Injeta um aluno real na turma para gerar corrente (Ocupação = 1)
    Matricula.objects.create(
        aluno_id=aluno,
        turma_id=turma,
        data_inicio='2026-07-01',
        status=Situacao.ATIVA,
        # realizado_por=setup_dados['admin_user'] # Descomente se o seu modelo exigir a auditoria
    )
    
    # 2. Operador tenta editar a turma reduzindo a capacidade para 0 (Abaixo da ocupação de 1)
    dados_sobrecarga = {
        'modalidade_id': turma.modalidade_id.id,
        'polo_id': turma.polo_id.id,
        'capacidade': 0, # <-- TENSÃO IRREGULAR
        'horario': '14:00',
        'professores': [professor.id],
        'dias_semana': ['SEG', 'QUA'],
    }
    
    # Pluga o objeto 'turma' no form simulando uma Edição (UpdateView)
    form = TurmaForm(data=dados_sobrecarga, instance=turma)
    
    assert not form.is_valid()
    assert 'capacidade' in form.errors
    assert "Você não pode calibrar a capacidade máxima abaixo da ocupação" in str(form.errors['capacidade'])