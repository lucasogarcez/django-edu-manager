from django.db import migrations

def carregar_dados_faq(apps, schema_editor):
    # Puxa os modelos através do histórico do Django para manter a consistência
    CategoriaFAQ = apps.get_model('core', 'CategoriaFAQ')
    PerguntaFrequente = apps.get_model('core', 'PerguntaFrequente')

    # --- SCRIPT DE CARGA ---
    cat_seguranca, _ = CategoriaFAQ.objects.get_or_create(nome="Acesso e Segurança (Login)", ordem=1)
    PerguntaFrequente.objects.get_or_create(
        categoria=cat_seguranca, pergunta="Esqueci minha senha, como recuperar o acesso?", ordem=1,
        defaults={'resposta': "Na tela inicial de login, clique no link 'Esqueceu sua senha?'..."}
    )

    cat_alunos, _ = CategoriaFAQ.objects.get_or_create(nome="Secretaria: Gestão de Alunos", ordem=2)
    PerguntaFrequente.objects.get_or_create(
        categoria=cat_alunos, pergunta="Posso excluir um aluno do sistema?", ordem=2,
        defaults={'resposta': "Não. Para manter o histórico acadêmico e financeiro íntegro..."}
    )

    cat_diretoria, _ = CategoriaFAQ.objects.get_or_create(nome="Diretoria: Administração do Sistema", ordem=3)
    PerguntaFrequente.objects.get_or_create(
        categoria=cat_diretoria, pergunta="Como criar um acesso para um novo Professor ou Secretária?", ordem=1,
        defaults={'resposta': "1. Acesse o Painel de Controle (Admin)..."}
    )

def remover_dados_faq(apps, schema_editor):
    # Função de rollback caso você precise reverter a migration
    CategoriaFAQ = apps.get_model('core', 'CategoriaFAQ')
    CategoriaFAQ.objects.filter(nome__in=[
        "Acesso e Segurança (Login)", 
        "Secretaria: Gestão de Alunos", 
        "Diretoria: Administração do Sistema"
    ]).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'), # Garante que a tabela FAQ foi criada antes de rodar este código
    ]

    operations = [
        # Dispara a gravação automática
        migrations.RunPython(carregar_dados_faq, reverse_code=remover_dados_faq),
    ]