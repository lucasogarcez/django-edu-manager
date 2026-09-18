from django.urls import path
from . import views
from .views import TurmaCreateView, TurmaUpdateView

app_name = 'academico' # Define um namespace

urlpatterns = [
    path('turmas/', views.listar_turmas, name='listar_turmas'),
    path('turma/nova/', TurmaCreateView.as_view(), name='criar_turma'),
    path('turma/<int:pk>/editar/', TurmaUpdateView.as_view(), name='editar_turma'),
    path('turmas/<int:turma_id>/alunos/', views.alunos_por_turma, name='alunos_por_turma'),
    path('matricula/<int:matricula_id>/inativar/', views.inativar_matricula, name='inativar_matricula'),
    path('minhas-turmas/', views.minhas_turmas, name='minhas_turmas'),
    path('turma/<int:turma_id>/chamada/realizar/', views.realizar_chamada, name='realizar_chamada'),
    path('turma/<int:turma_id>/historico/', views.historico_chamadas_turma, name='historico_chamadas_turma'),
    path('chamada/<int:chamada_id>/', views.detalhe_chamada, name='detalhe_chamada'),
    path('aluno/<int:aluno_id>/atestados/', views.gerenciar_atestados, name='gerenciar_atestados'),
    path('atestado/<int:atestado_id>/excluir/', views.excluir_atestado, name='excluir_atestado'),
    path('relatorios/risco-frequencia/', views.relatorio_risco, name='relatorio_risco'),
    path('registrar-atendimento/', views.registrar_atendimento_rapido, name='registrar_atendimento_rapido'),
    path('importar-ficha/', views.importar_ficha_chamada_view, name='importar_ficha_chamada'),
    path('importar-ficha/desfazer/', views.desfazer_importacao, name='desfazer_importacao'),
    path('relatorios/ficha/<int:turma_id>/<int:mes>/<int:ano>/', views.imprimir_ficha_frequencia, name='imprimir_ficha'),
]