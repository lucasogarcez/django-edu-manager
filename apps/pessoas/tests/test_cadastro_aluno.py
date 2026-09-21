import os
import pytest
import re
import tempfile
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from pytest_django.asserts import assertTemplateUsed, assertRedirects
from apps.saude.models import Doenca, Objetivo, QuestionarioSaude
from apps.pessoas.models import Aluno
from apps.academico.models import Turma

# Imports do Playwright
from playwright.sync_api import expect

# Configuração para permitir acesso síncrono ao DB em testes async
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

# --- Helper de Login ---
def login_admin(page, live_server_url):
    """ Faz login e espera o redirecionamento para a home """
    login_url = f"{live_server_url}/accounts/login/" 
    page.goto(login_url)
    page.fill('input[name="username"]', 'admin_teste')
    page.fill('input[name="password"]', 'password')
    with page.expect_navigation():
        page.click('button[type="submit"]')

# =============================================================================
# TESTES DE BACK-END (Unitários/Integração)
# =============================================================================

@pytest.mark.django_db
def test_get_pagina_cadastro_sucesso(client, setup_dados): 
    user = setup_dados['admin_user'] 
    client.force_login(user) 

    url = reverse('pessoas:cadastro_geral_aluno')
    response = client.get(url)
    
    assert response.status_code == 200
    assertTemplateUsed(response, 'pessoas/aluno/aluno_questionario_form.html')

@pytest.mark.django_db
def test_validacao_outros_doencas_falha(client, setup_dados):
    """ Testa se o clean() do forms.py falha se 'Outra' for marcado sem texto. """
    user = setup_dados['admin_user']
    client.force_login(user)
    
    doenca_outra, _ = Doenca.objects.get_or_create(nome="Outra")
    doenca_hipertensao, _ = Doenca.objects.get_or_create(nome="Hipertensão")
    objetivo_perder_peso, _ = Objetivo.objects.get_or_create(nome="Perder peso")

    url = reverse('pessoas:cadastro_geral_aluno')
    
    post_data = {
        'nome_completo': 'Aluno Teste', 'data_nascimento': '2000-01-01',
        # [MUDANÇA DE ARQUITETURA] Usando o novo polimorfismo de documentos
        'tipo_documento': 'CPF', 'numero_documento': '11144477735', 
        'email': 'teste@teste.com',
        'endereco': 'Rua Teste', 'telefone': '34999998888',
        
        # Dados inválidos: Marcado 'Outra' mas texto vazio
        'doencas': [doenca_hipertensao.id, doenca_outra.id], 
        'outras_doencas': '', 
        'objetivos': [objetivo_perder_peso.id],
        'declaracao_aptidao': 'on',
    }
    response = client.post(url, post_data)
    
    assert response.status_code == 200 
    form_errors = response.context['questionario_form'].errors
    assert 'outras_doencas' in form_errors

@pytest.mark.django_db
def test_envio_completo_sucesso(client, setup_dados):
    """ Testa se um formulário 100% válido salva tudo e redireciona """
    client.force_login(setup_dados['admin_user'])
    url = reverse('pessoas:cadastro_geral_aluno')
    
    doenca_hipertensao = setup_dados['doenca_hipertensao']
    objetivo_perder_peso = setup_dados['objetivo_perder_peso']
    turma = setup_dados['turma']

    post_data = {
        # --- Aba 1: Aluno ---
        'nome_completo': 'Aluno Teste Válido', 
        'data_nascimento': '2000-01-01',
        # [MUDANÇA DE ARQUITETURA]
        'tipo_documento': 'CPF', 
        'numero_documento': '84967481035', 
        'email': 'valido@teste.com',
        'endereco': 'Rua Teste', 
        'telefone': '34999998888',
        
        # --- Aba 2: Questionário ---
        'doencas': [doenca_hipertensao.id],
        'outras_doencas': '', 
        'objetivos': [objetivo_perder_peso.id],
        'outros_objetivos': '', 
        'pratica_exercicio': 'on', 
        'tipo_exercicio': 'Corrida', 
        'frequencia_exercicio': '3x+', 
        'declaracao_aptidao': 'on',
        
        # --- Aba 3: Turmas ---
        'turmas_selecionadas_ids': str(turma.id), 
    }
    
    response = client.post(url, post_data)
    assertRedirects(response, reverse('pessoas:questionario_sucesso'))
    
    # [MUDANÇA DE ARQUITETURA] Atualização das consultas do ORM
    assert Aluno.objects.filter(numero_documento='84967481035', tipo_documento='CPF').exists()
    assert QuestionarioSaude.objects.filter(aluno__numero_documento='84967481035').count() == 1
    from apps.academico.models import Matricula
    assert Matricula.objects.filter(aluno_id__numero_documento='84967481035', turma_id=turma).exists()

# =============================================================================
# TESTES DE FRONT-END (Playwright)
# =============================================================================

@pytest.mark.django_db(transaction=True)
def test_js_validacao_proximo_falha_playwright(live_server, page, setup_dados):
    login_admin(page, live_server.url)
    url = live_server.url + reverse('pessoas:cadastro_geral_aluno')
    page.goto(url)
    
    page.click("#btn-validar-e-proximo")
    
    expect(page.locator("#aluno-tab")).to_have_class(re.compile(r"active"))
    erro_nome = page.locator("#id_nome_completo-error-js")
    expect(erro_nome).to_be_visible()
    expect(erro_nome).to_contain_text('obrigatório')

@pytest.mark.django_db(transaction=True)
def test_js_toggle_pratica_exercicio_playwright(live_server, page, setup_dados):
    login_admin(page, live_server.url)
    url = live_server.url + reverse('pessoas:cadastro_geral_aluno')
    page.goto(url)
    page.click("#questionario-tab")
    
    div_tipo_exercicio = page.locator("#div_id_tipo_exercicio")
    expect(div_tipo_exercicio).to_be_hidden()
    
    page.locator("#id_pratica_exercicio").check()
    expect(div_tipo_exercicio).to_be_visible()

@pytest.mark.django_db(transaction=True)
def test_js_fluxo_validacao_abas_e_salvar(live_server, page, setup_dados):
    turma = setup_dados['turma']
    
    with transaction.atomic():
        Doenca.objects.get_or_create(nome="Outra")
        Objetivo.objects.get_or_create(nome="Outro")
        Turma.objects.get_or_create(id=turma.id, defaults={
            'modalidade_id': turma.modalidade_id, 'polo_id': turma.polo_id, 
            'categoria': turma.categoria, 'horario': turma.horario, 'capacidade': 10
        })

    login_admin(page, live_server.url)
    url = live_server.url + reverse('pessoas:cadastro_geral_aluno')
    page.goto(url)

    # --- ABA 1 ---
    page.fill("#id_nome_completo", "Aluno Teste Playwright")
    page.fill("#id_data_nascimento", "2000-01-01") 
    
    # [MUDANÇA DE ARQUITETURA] Selecionando os novos campos do Playwright
    page.select_option("#id_tipo_documento", "CPF")
    page.fill("#id_numero_documento", "01267588080")
    
    page.fill("#id_email", "teste@teste.com")
    page.fill("#id_endereco", "Rua Teste")
    page.fill("#id_telefone", "34999998888")

    page.click("#btn-validar-e-proximo")
    expect(page.locator("#questionario")).to_be_visible()

    # --- ABA 2 ---
    page.locator("#id_declaracao_aptidao").check()
    page.click("#btn-questionario-proximo", force=True)
    
    expect(page.locator("#modalidade")).not_to_be_visible()
    expect(page.locator("#objetivos-group-error")).to_be_visible()

    objetivo_seguro = page.locator('label:has-text("Perder peso")')
    objetivo_seguro.wait_for(state="attached")
    objetivo_seguro.scroll_into_view_if_needed()
    objetivo_seguro.click()

    page.click("#btn-questionario-proximo")
    
    # --- ABA 3 ---
    page.click("#btn-atestado-proximo")
    
    # --- ABA 4 ---
    expect(page.locator("#modalidade")).to_be_visible()

    page.wait_for_selector('#turmas-data', state='attached')
    page.click('button[type="submit"]:has-text("Salvar")')

    expect(page.locator("#confirmacaoModal")).to_be_hidden()
    expect(page.locator("#turmas-group-error")).to_be_visible()

    page.click('button:has-text("Selecionar Turmas")')
    expect(page.locator('#modalSelecaoTurmas')).to_be_visible()
    
    btn_accordion = page.locator('button.accordion-button:has-text("Futsal")')
    if "collapsed" in btn_accordion.get_attribute("class"):
        btn_accordion.click()
        
    input_id = f"turma-{turma.id}"
    input_locator = page.locator(f'input[id="{input_id}"]')
    input_locator.wait_for(state="visible")
    page.locator(f'label[for="{input_id}"]').click()
    
    page.click('#btn-confirmar-selecao-turmas')
    expect(page.locator('#modalSelecaoTurmas')).to_be_hidden()

    page.click('button[type="submit"]:has-text("Salvar")')

    expect(page.locator("#confirmacaoModal")).to_be_visible()
    page.click("#btnConfirmarSalvar")
    page.wait_for_url(live_server.url + reverse('pessoas:questionario_sucesso'))

# =============================================================================
# [NOVO TESTE] Máquina de Estados: Cadastro Pendente
# =============================================================================
@pytest.mark.django_db(transaction=True)
def test_js_fluxo_cadastro_pendente_playwright(live_server, page, setup_dados):
    """ Garante que marcar 'Pendente' desobriga os documentos e o backend aceita. """
    turma = setup_dados['turma']
    
    with transaction.atomic():
        Objetivo.objects.get_or_create(nome="Perder peso")
        Turma.objects.get_or_create(id=turma.id, defaults={
            'modalidade_id': turma.modalidade_id, 'polo_id': turma.polo_id, 
            'categoria': turma.categoria, 'horario': turma.horario, 'capacidade': 10
        })

    login_admin(page, live_server.url)
    url = live_server.url + reverse('pessoas:cadastro_geral_aluno')
    page.goto(url)

    # Preenche apenas o básico
    page.fill("#id_nome_completo", "Aluno Pendente Fantasma")
    page.fill("#id_data_nascimento", "2010-01-01") 
    
    # ACIONA A MÁQUINA DE ESTADOS (Bypass)
    page.check("#id_cadastro_pendente")

    # Tenta avançar (o JS deve permitir, pois a máquina de estados perdoa os documentos)
    page.click("#btn-validar-e-proximo")
    expect(page.locator("#questionario")).to_be_visible()

    # Preenche o resto rapidamente para salvar
    page.locator("#id_declaracao_aptidao").check()
    page.locator('label:has-text("Perder peso")').click()
    page.click("#btn-questionario-proximo")
    
    page.click("#btn-atestado-proximo")
    
    page.click('button:has-text("Selecionar Turmas")')
    btn_accordion = page.locator('button.accordion-button:has-text("Futsal")')
    if "collapsed" in btn_accordion.get_attribute("class"):
        btn_accordion.click()
    page.locator(f'label[for="turma-{turma.id}"]').wait_for(state="visible")
    page.locator(f'label[for="turma-{turma.id}"]').click()
    page.click('#btn-confirmar-selecao-turmas')
    
    # Salva
    page.click('button[type="submit"]:has-text("Salvar")')
    expect(page.locator("#confirmacaoModal")).to_be_visible()
    page.click("#btnConfirmarSalvar")
    
    # Verifica sucesso
    page.wait_for_url(live_server.url + reverse('pessoas:questionario_sucesso'))
    
    # Verifica o banco de dados
    aluno_salvo = Aluno.objects.get(primeiro_nome="Aluno", ultimo_nome="Pendente Fantasma")
    assert aluno_salvo.status_documentacao == 'PENDENTE'
    assert aluno_salvo.numero_documento is None
    
@pytest.mark.django_db
def test_backend_salva_atestado_com_sucesso(client, setup_dados):
    """
    [Teste de I/O de Arquivos] Garante que a view.py está recebendo o request.FILES 
    e salvando fisicamente o arquivo atrelado ao Questionário de Saúde do Aluno.
    """
    client.force_login(setup_dados['admin_user'])
    url = reverse('pessoas:cadastro_geral_aluno')
    
    objetivo = setup_dados['objetivo_perder_peso']
    doenca_hipertensao = setup_dados['doenca_hipertensao']
    turma = setup_dados['turma']

    # Simulando um PDF falso em memória (Evita criar lixo no HD durante o teste)
    pdf_falso = SimpleUploadedFile(
        "atestado_teste_automatizado.pdf", 
        b"conteudo_falso_do_pdf", 
        content_type="application/pdf"
    )

    post_data = {
        # Dados Aba 1
        'nome_completo': 'Paciente Teste Upload', 
        'data_nascimento': '2000-01-01',
        'tipo_documento': 'CPF', 
        'numero_documento': '01267588080', 
        'telefone': '34999998888',
        'email': 'teste@teste.com',
        'endereco': 'Rua Teste 123',
        
        # Dados Aba 2 (Com Arquivo e Data)
        'pratica_exercicio': 'on', 
        'tipo_exercicio': 'Natação', 
        'frequencia_exercicio': '2x',
        'doencas': [doenca_hipertensao.id],
        'outras_doencas': '',
        'objetivos': [objetivo.id],
        'outros_objetivos': '',
        'declaracao_aptidao': 'on',
        'data_atestado_aptidao': '2026-08-06', # Formato de Máquina ISO
        'arquivo_atestado': pdf_falso, # <--- O Cabo de Dados Crítico
        
        # Dados Aba 3
        'turmas_selecionadas_ids': str(turma.id), 
    }
    
    response = client.post(url, post_data)
    if response.status_code == 200:
        erros_aluno = response.context['form'].errors if 'form' in response.context else "OK"
        erros_quest = response.context['questionario_form'].errors if 'questionario_form' in response.context else "OK"
        pytest.fail(f"O Formulário recusou os dados!\nErros Aba 1: {erros_aluno}\nErros Aba 2: {erros_quest}")
    
    assert response.status_code == 302
    
    # 2. Verifica se o Aluno e o Questionário nasceram
    aluno_salvo = Aluno.objects.get(numero_documento='01267588080')
    questionario = QuestionarioSaude.objects.get(aluno=aluno_salvo)
    
    # 3. O Multímetro Final: A data gravou certo e o arquivo existe?
    assert str(questionario.data_atestado_aptidao) == '2026-08-06'
    assert questionario.arquivo_atestado.name.startswith('atestados/'), "O arquivo não foi salvo na pasta correta!"
    assert 'atestado_teste_automatizado' in questionario.arquivo_atestado.name
    
@pytest.mark.django_db(transaction=True)
def test_e2e_ihm_anexo_atestado_playwright(live_server, page, setup_dados):
    """
    [Teste de Interface e UX] Simula a Secretária selecionando um PDF no PC dela.
    Verifica se o JS gera a "Etiqueta Verde" de confirmação visual.
    """
    turma = setup_dados['turma']
    
    with transaction.atomic():
        Objetivo.objects.get_or_create(nome="Perder peso")

    # Helper de login
    page.goto(f"{live_server.url}/accounts/login/")
    page.fill('input[name="username"]', 'admin_teste')
    page.fill('input[name="password"]', 'password')
    with page.expect_navigation():
        page.click('button[type="submit"]')

    # Navega para o Cadastro
    page.goto(live_server.url + reverse('pessoas:cadastro_geral_aluno'))

    # Preenche Aba 1
    page.fill("#id_nome_completo", "Teste Etiqueta PDF")
    page.check("#id_cadastro_pendente") # Bypass de documentos
    page.click("#btn-validar-e-proximo")

    # =================================================================
    # SIMULAÇÃO DE UPLOAD FÍSICO
    # =================================================================
    # Cria um arquivo temporário físico para o navegador conseguir "ler"
    fd, caminho_pdf = tempfile.mkstemp(suffix='.pdf', prefix='exame_medico_')
    os.write(fd, b"%PDF-1.4\nTeste Falso")
    os.close(fd)
    
    try:
        page.locator("#id_declaracao_aptidao").check()
        page.locator('label:has-text("Perder peso")').click()
        page.click("#btn-questionario-proximo")
        
        # Pula para a aba e preenche a data
        page.fill("#id_data_atestado_aptidao", "2026-08-06")
        
        # O Robô clica em "Procurar Arquivo" e injeta o nosso PDF
        page.set_input_files("#id_arquivo_atestado", caminho_pdf)
    
        page.click("#btn-atestado-proximo")
        
        # Pula as turmas e vai para o Resumo Final
        page.click('button:has-text("Selecionar Turmas")')
        btn_accordion = page.locator('button.accordion-button:has-text("Futsal")')
        if "collapsed" in btn_accordion.get_attribute("class"):
            btn_accordion.click()
        page.locator(f'label[for="turma-{turma.id}"]').wait_for(state="visible")
        page.locator(f'label[for="turma-{turma.id}"]').click()
        page.click('#btn-confirmar-selecao-turmas')
        
        page.click('button[type="submit"]:has-text("Salvar")')
        
        # =================================================================
        # VALIDAÇÃO VISUAL DO SENSOR JS (A mágica da Etiqueta Verde)
        # =================================================================
        modal = page.locator("#confirmacaoModal")
        modal.wait_for(state="visible")
        
        # O HTML que dividiu a tela colocou o ID 'confirm-data-atestado' na direita
        span_data = modal.locator("#confirm-data-atestado")
        expect(span_data).to_contain_text("06/08/2026")
        
        # O JS precisa ter lido o nome do arquivo que injetamos e criado o Badge verde
        badge_arquivo = modal.locator("#confirm-arquivo-atestado .badge.bg-success")
        expect(badge_arquivo).to_be_visible()
        expect(badge_arquivo).to_contain_text("exame_medico_")

    finally:
        # Limpeza da Bancada: Apaga o PDF falso do sistema operacional
        if os.path.exists(caminho_pdf):
            os.remove(caminho_pdf)