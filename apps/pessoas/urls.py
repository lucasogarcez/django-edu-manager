from django.urls import path
from . import views

app_name = 'pessoas'

urlpatterns = [
    path('aluno/questionario/', views.cadastro_geral_aluno, name='cadastro_geral_aluno'),
    path('questionario/sucesso/', views.questionario_sucesso, name='questionario_sucesso'),
    path('alunos/', views.ListarAlunosView.as_view(), name='listar_alunos'),
    path('aluno/<int:pk>/editar/', views.EditarAlunoView.as_view(), name='editar_aluno'),
    path('aluno/<int:pk>/inativar/', views.inativar_aluno, name='inativar_aluno'),
    path('aluno/<int:pk>/ativar/', views.ativar_aluno, name='ativar_aluno'),
    path('aluno/<int:aluno_id>/matricular/', views.matricular_aluno_view, name='matricular_aluno'),
    path('alunos/manutencao/merge/', views.painel_merge_alunos, name='painel_merge_alunos'),
]
