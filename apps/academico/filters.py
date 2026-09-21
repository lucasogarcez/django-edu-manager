import django_filters
from django import forms
from .models import Turma, Modalidade, Professor, Estagiario, Polo, DiaSemana, Categoria, Chamada

class TurmaFilter(django_filters.FilterSet):
    
    # Filtro 1: Modalidade (Dropdown)
    modalidade_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Modalidade.objects.all(),
        label="Modalidade(s)",
        widget=forms.SelectMultiple(attrs={'class': 'tomselect'})
    )
    
    # Filtro 2: Professor (Dropdown com Múltipla Escolha)
    # Busca turmas que tenham PELO MENOS UM dos professores selecionados
    professores = django_filters.ModelMultipleChoiceFilter(
        queryset=Professor.objects.all(),
        label="Professor(es)",
        widget=forms.SelectMultiple(attrs={'class': 'tomselect'})
    )
    
    # Filtro 3: Estagiário (Dropdown com Múltipla Escolha)
    estagiarios = django_filters.ModelMultipleChoiceFilter(
        queryset=Estagiario.objects.all(),
        label="Estagiário(s)",
        widget=forms.SelectMultiple(attrs={'class': 'tomselect'})
    )

    # Filtro 4: Polo (Dropdown FK)
    polo_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Polo.objects.all(),
        label="Polo",
        widget=forms.SelectMultiple(attrs={'class': 'tomselect'})
    )
    
    # Filtro 5: Categoria (Dropdown FK)
    categoria = django_filters.ModelMultipleChoiceFilter(
        queryset=Categoria.objects.all(),
        label="Categoria(s)",
        widget=forms.SelectMultiple(attrs={'class': 'tomselect'})
    )
    
    # Filtro 6: Dia da Semana (Dropdown Múltiplo)
    # Busca turmas que tenham AQUELE dia da semana
    dias__dia_semana = django_filters.MultipleChoiceFilter(
        choices=DiaSemana.choices,
        label="Dia(s) da Semana",
        widget=forms.SelectMultiple(attrs={'class': 'tomselect'})
    )

    class Meta:
        model = Turma
        fields = ['modalidade_id', 'professores', 'estagiarios', 'polo_id', 'categoria', 'dias__dia_semana']
        
def get_available_years():
    """ Busca os anos distintos em que houve chamadas no banco. """
    # Busca datas distintas, agrupa por ano, 'DESC' põe o mais recente primeiro
    years_dates = Chamada.objects.dates('data_chamada', 'year', order='DESC')
    # Retorna lista simples de tuplas (valor, label)
    return [(date.year, str(date.year)) for date in years_dates]

# Lista de meses (valor numérico, label em texto)
MONTH_CHOICES = [
    (1, 'Janeiro'), (2, 'Fevereiro'), (3, 'Março'), (4, 'Abril'),
    (5, 'Maio'), (6, 'Junho'), (7, 'Julho'), (8, 'Agosto'),
    (9, 'Setembro'), (10, 'Outubro'), (11, 'Novembro'), (12, 'Dezembro'),
]

class ChamadaFilter(django_filters.FilterSet):
    
    # Filtro 1: Ano
    ano = django_filters.ChoiceFilter(
        field_name='data_chamada__year',
        choices=get_available_years, # Usa a função que busca os anos
        label="Ano(s)",
        empty_label="Qualquer Ano",
        widget=forms.Select(attrs={'class': 'tomselect'})
    )
    
    # Filtro 2: Mês
    mes = django_filters.ChoiceFilter(
        field_name='data_chamada__month',
        choices=MONTH_CHOICES,
        label="Mês(es)",
        empty_label="Qualquer Mês",
        widget=forms.Select(attrs={'class': 'tomselect'})
    )
    
    class Meta:
        model = Chamada
        fields = ['ano', 'mes']