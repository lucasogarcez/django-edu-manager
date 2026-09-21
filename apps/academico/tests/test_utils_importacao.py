import pytest
from datetime import time, date
from apps.academico.models import DiaSemana, Modalidade
from apps.academico.views import corrigir_nome_modalidade, parse_horario, parse_data, get_dias_canonicos

@pytest.fixture
def popular_modalidades():
    """ 
    Simula o estado do banco de dados antes de iniciar os testes.
    Cria uma planta base com modalidades específicas.
    """
    Modalidade.objects.bulk_create([
        Modalidade(nome="Ginástica Orientada"),
        Modalidade(nome="Ginástica Localizada"),
        Modalidade(nome="Vôlei"),
        Modalidade(nome="Natação"),
        Modalidade(nome="Futsal"),
    ])

@pytest.mark.django_db
@pytest.mark.parametrize("sinal_entrada, sinal_esperado", [
    # Cenário A: Sinal Perfeito (Sem ruído)
    ("Vôlei", "Vôlei"),
    ("Futsal", "Futsal"),
    
    # Cenário B: Ruído de Digitação (Case insensitive e espaços soltos)
    ("  nAtAçÃO  ", "Natação"),
    ("ginastica orientada", "Ginástica Orientada"),
    
    # Cenário C: Filtragem de Ruído Conhecido (Variáveis da lista PALAVRAS_RUIDO)
    ("AULA DE VÔLEI", "Vôlei"),
    ("TURMA INFANTIL NATAÇÃO", "Natação"),
    
    # Cenário D: Mapeamento de Siglas (SINONIMOS)
    ("GO", "Ginástica Orientada"),
    ("NAT", "Natação"),
    
    # Cenário E: Distorção de Sinal (Fuzzy Matching > 70%)
    ("Ginastica Lokalizada", "Ginástica Localizada"), # Letra K no meio
    ("Voleibol", "Vôlei"), # Semelhança de string
    ("Nataçao", "Natação"), # Falta do til
])
def test_corrigir_modalidade_sinal_valido(popular_modalidades, sinal_entrada, sinal_esperado):
    """ Testa se o Demultiplexador roteia corretamente os sinais ruidosos """
    resultado = corrigir_nome_modalidade(sinal_entrada)
    assert resultado == sinal_esperado

# =============================================================================
# 3. TESTES DE RUPTURA (Disjuntores e Tratamento de Erros)
# =============================================================================
@pytest.mark.django_db
def test_disjuntor_sugestao_fuzzy_media(popular_modalidades):
    """ 
    Testa se o sistema sugere a correção correta quando o sinal cai na faixa 
    frequência média (Fuzzy entre 50% e 70%).
    """
    sinal_distorcido = "Futebol" # Ruído muito alto para aprovação automática
    
    # O pytest verifica se a exceção ValueError foi armada e se a mensagem está correta
    with pytest.raises(ValueError, match="Você quis dizer 'Futsal'"):
        corrigir_nome_modalidade(sinal_distorcido)

@pytest.mark.django_db
def test_disjuntor_sinal_desconhecido(popular_modalidades):
    """ 
    Testa o bloqueio total para sinais fora da frequência conhecida (< 50%).
    """
    sinal_invalido = "Basquete" # Não existe na nossa fixture
    
    with pytest.raises(ValueError, match="Nenhuma modalidade similar encontrada"):
        corrigir_nome_modalidade(sinal_invalido)

def test_disjuntor_sinal_vazio():
    """ Testa a injeção de valores nulos """
    with pytest.raises(ValueError, match="vazio"):
        corrigir_nome_modalidade("")
    
@pytest.mark.parametrize("entrada, esperado", [
    ("14:30", time(14, 30)),
    ("14h30", time(14, 30)),
    ("14.30", time(14, 30)),
    ("14", time(14, 0)),
    ("invalid", None),
    (None, None),
])
def test_parse_horario(entrada, esperado):
    assert parse_horario(entrada) == esperado

@pytest.mark.parametrize("entrada, esperado", [
    ("1990-05-15", date(1990, 5, 15)),
    ("15/05/1990", date(1990, 5, 15)),
    ("2024-01-01 00:00:00", date(2024, 1, 1)),
    ("data_errada", None),
    (None, None),
])
def test_parse_data_nascimento(entrada, esperado):
    assert parse_data(entrada) == esperado
    
def test_get_dias_canonicos_sucesso():
    entrada = "SEG/QUA/SEX"
    display, enums, qtd = get_dias_canonicos(entrada)
    
    assert "SEGUNDA-FEIRA" in display
    assert DiaSemana.SEGUNDA in enums
    assert DiaSemana.QUARTA in enums
    assert DiaSemana.SEXTA in enums
    assert qtd == 3

def test_get_dias_canonicos_vazio():
    display, enums, qtd = get_dias_canonicos(None)
    assert display == "A DEFINIR"
    assert enums == []
    assert qtd == 0