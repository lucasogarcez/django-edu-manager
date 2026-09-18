import pytest
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.saude.models import QuestionarioSaude

@pytest.mark.django_db
def test_recalibracao_data_sem_arquivo(client, setup_dados):
    """ 
    Testa o Módulo Híbrido: Verifica se o sistema permite atualizar 
    apenas a data de um atestado existente, sem exigir um novo upload.
    """
    client.force_login(setup_dados['admin_user'])
    aluno = setup_dados['aluno']

    # 1. Preparação de Estado (Acesso ao Slot de Memória)
    arquivo_antigo = SimpleUploadedFile("atestado_2025.pdf", b"pdf fake", content_type="application/pdf")
    
    # RELÉ DE ATUALIZAÇÃO: Busca a placa existente ou cria se não houver, evitando a Colisão (IntegrityError)
    questionario, _ = QuestionarioSaude.objects.get_or_create(aluno=aluno)
    questionario.data_atestado_aptidao = '2025-01-01'
    questionario.arquivo_atestado = arquivo_antigo
    questionario.save()

    # 2. Injeção de Sinal (Apenas a nova data, simulando o input vazio no arquivo)
    url = reverse('saude:renovar_atestado_aptidao', kwargs={'aluno_id': aluno.id})
    post_data = {
        'data_atestado_aptidao': '2026-07-09',
        'arquivo_atestado': '' # PINO DESCONECTADO
    }

    response = client.post(url, post_data)

    # 3. Leitura dos Sensores
    assert response.status_code == 302 

    questionario.refresh_from_db()
    assert str(questionario.data_atestado_aptidao) == '2026-07-09'
    assert 'atestado_2025' in questionario.arquivo_atestado.name


@pytest.mark.django_db
def test_supressor_de_redundancia_arquivo_duplicado(client, setup_dados):
    """ 
    Testa o Filtro Anti-Duplicação: Verifica se o sistema descarta 
    o reenvio do mesmíssimo arquivo para proteger o disco.
    """
    client.force_login(setup_dados['admin_user'])
    aluno = setup_dados['aluno']

    # DEFINIÇÃO DE MASSA PADRÃO
    # Garante que tanto o arquivo original quanto a cópia tenham exatamente o mesmo peso
    conteudo_binario_padrao = b"estrutura_binaria_de_tamanho_identico"

    # 1. Preparação de Estado
    arquivo_original = SimpleUploadedFile("exame_medico.pdf", conteudo_binario_padrao, content_type="application/pdf")
    
    questionario, _ = QuestionarioSaude.objects.get_or_create(aluno=aluno)
    questionario.data_atestado_aptidao = '2026-01-01'
    questionario.arquivo_atestado = arquivo_original
    questionario.save()
    
    caminho_salvo_original = questionario.arquivo_atestado.name

    # 2. Injeção de Sinal de Erro (Arquivo idêntico em nome e massa)
    arquivo_duplicado = SimpleUploadedFile("exame_medico.pdf", conteudo_binario_padrao, content_type="application/pdf")
    
    url = reverse('saude:renovar_atestado_aptidao', kwargs={'aluno_id': aluno.id})
    post_data = {
        'data_atestado_aptidao': '2026-02-01', 
        'arquivo_atestado': arquivo_duplicado  
    }

    response = client.post(url, post_data)

    # 3. Verificação do Supressor
    assert response.status_code == 302

    questionario.refresh_from_db()
    assert str(questionario.data_atestado_aptidao) == '2026-02-01'
    
    # Agora o comparador vai encontrar pesos iguais e barrar a gravação física,
    # garantindo que o caminho salvo continue intocado.
    assert questionario.arquivo_atestado.name == caminho_salvo_original