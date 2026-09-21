import pytest
from django.urls import reverse
from playwright.sync_api import expect
from django.db import transaction
from apps.saude.models import Doenca, Objetivo

# --- FUNÇÃO AUXILIAR DE LOGIN CORRIGIDA ---
def login_admin(page, live_server_url):
    """
    Faz login e ESPERA o redirecionamento para a home para garantir
    que o cookie de sessão foi definido.
    """
    login_url = f"{live_server_url}/accounts/login/" 
    page.goto(login_url)

    page.fill('input[name="username"]', 'admin_teste')
    page.fill('input[name="password"]', 'password')
    
    # Clica e espera navegar. Isso é mais robusto que wait_for_url fixo.
    with page.expect_navigation():
        page.click('button[type="submit"]')

@pytest.mark.django_db(transaction=True)
def test_fluxo_filtros_lista_turmas(live_server, page, setup_dados):
    """ Testa se os filtros lado a lado (Bootstrap) funcionam """
    
    # 1. Login (agora robusto)
    login_admin(page, live_server.url)

    # 2. Vai para Lista de Turmas
    url_lista = live_server.url + reverse('academico:listar_turmas')
    page.goto(url_lista)

    # Verifica se realmente chegou na página certa (não foi redirecionado p/ login)
    expect(page).to_have_url(url_lista)

    # 3. Interage com o filtro de Professor
    # Usa o ID do botão dropdown que definimos manualmente no HTML
    tom_select_control = page.locator('#div_id_professores .ts-control') 
    # Espera o botão estar visível
    expect(tom_select_control).to_be_visible()
    tom_select_control.click()
    
    # 4. Seleciona o checkbox dentro do dropdown
    prof_name = f"{setup_dados['professor'].usuario.first_name} {setup_dados['professor'].usuario.last_name}"
    # Espera a opção (com o nome do professor) aparecer no dropdown e clica nela
    option_locator = page.locator(f'.ts-dropdown .option:has-text("{prof_name}")')
    expect(option_locator).to_be_visible() # Espera a opção aparecer
    option_locator.click()
    
    # 5. Clica em Filtrar
    page.click('button[type="submit"]:has-text("Filtrar")')

    # 6. Verifica o resultado
    # Espera que o card com o título da turma apareça
    expect(page.locator('.card-title').first).to_contain_text("Futsal")


@pytest.mark.django_db(transaction=True)
def test_modal_selecao_turmas(live_server, page, setup_dados):
    """ Testa o Modal de Matrícula na página de matricular aluno """
    
    # 1. Login (agora robusto)
    login_admin(page, live_server.url)

    # 2. Vai para Matrícula do Aluno
    aluno_id = setup_dados['aluno'].id
    url_matricula = live_server.url + reverse('pessoas:matricular_aluno', kwargs={'aluno_id': aluno_id})
    page.goto(url_matricula)

    # Verifica se chegou na página certa (se falhar aqui, é erro de permissão/login)
    expect(page).to_have_url(url_matricula)

    # 3. Espera o script de dados carregar (Correção do Timeout)
    # Se isso falhar, verifique se a view está passando 'turmas_json' no contexto
    page.wait_for_selector('#turmas-data', state='attached')

    # 4. Abre Modal
    page.click('button:has-text("Selecionar Turmas")')
    
    # Espera o modal animar e ficar visível
    modal = page.locator('#modalSelecaoTurmas')
    expect(modal).to_be_visible()

    nome_modalidade = setup_dados["turma"].modalidade_id.nome
    
    # Localiza o botão do accordion que contém o nome da modalidade
    btn_accordion = page.locator(f'button.accordion-button:has-text("{nome_modalidade}")')

    # Se o botão estiver colapsado (tem a classe 'collapsed'), clica para abrir
    if "collapsed" in btn_accordion.get_attribute("class"):
        btn_accordion.click()
        # Espera a animação de abertura terminar (o painel fica visível)
        # O painel correspondente é controlado pelo atributo aria-controls
        panel_id = btn_accordion.get_attribute("aria-controls")
        expect(page.locator(f"#{panel_id}")).to_be_visible()

    # 5. Seleciona a turma
    turma_id = setup_dados["turma"].id
    turma_check = page.locator(f'input[id="turma-{turma_id}"]')
    
    # force=True garante o clique mesmo se o estilo CSS cobrir o input
    turma_check.check(force=True)

    # 6. Confirma seleção
    page.click('#btn-confirmar-selecao-turmas')
    
    # Espera o modal fechar
    expect(modal).to_be_hidden()

    # 7. Verifica display
    display = page.locator('#turmas-selecionadas-display')
    expect(display).to_contain_text("Futsal") # Nome da turma criada na fixture
    
    # 8. Salva e Espera Navegação
    page.click('button[type="submit"]:has-text("Salvar Novas Matrículas")')
    
    # Espera ser redirecionado para a lista de alunos
    page.wait_for_url(live_server.url + reverse('pessoas:listar_alunos'))