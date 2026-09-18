from django.urls import path
from . import views

app_name = 'saude'

urlpatterns = [
    path('alunos/<int:aluno_id>/questionario/', views.detalhes_questionario_aluno, name='detalhes_questionario'),
    path('aluno/<int:aluno_id>/renovar-aptidao/', views.renovar_atestado_aptidao, name='renovar_atestado_aptidao'),
    path('aluno/<int:aluno_id>/editar_questionario/', views.editar_questionario_saude, name='editar_questionario_saude')
]