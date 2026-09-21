import pytest
from playwright.sync_api import Page, expect

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

@pytest.mark.django_db
def test_robo_cria_turma_via_interface(page: Page, live_server, setup_dados):
    """Simula a operação ponta-a-ponta na IHM de Turmas"""
    
    login_admin(page, live_server.url)
    
    # DADOS DA FONTE (Fixture)
    modalidade = setup_dados['turma'].modalidade_id
    polo = setup_dados['turma'].polo_id
    professor = setup_dados['professor']
    categoria = setup_dados['turma'].categoria
    
    # Aguarda o redirecionamento pós-login (Confirmação de sessão ativa)
    #expect(page).not_to_have_url(f"{live_server.url}/login/")

    # 2. Navegação para a Malha de Criação
    page.goto(f"{live_server.url}/academico/turma/nova/") # Ajuste se a sua URL for diferente
    
    # 3. Atuadores Nativos (Inputs comuns)
    page.fill("#id_capacidade", "25")
    page.fill("#id_horario", "15:30")
    
    # 4. Atuadores Multiplexados (Integração forçada com TomSelect)
    # O TomSelect esconde o <select> original. Usamos force=True para injetar o sinal diretamente no barramento oculto.
    page.evaluate(
        f"document.getElementById('id_modalidade_id').tomselect.setValue('{modalidade.id}')"
    )
    page.evaluate(
        f"document.getElementById('id_polo_id').tomselect.setValue('{polo.id}')"
    )
    page.evaluate(
        f"document.getElementById('id_categoria').tomselect.setValue('{categoria.id}')"
    )
    
    # Para componentes de escolha múltipla (Multiple): Envia um Array de strings
    page.evaluate(
        f"document.getElementById('id_professores').tomselect.setValue(['{professor.id}'])"
    )
    page.evaluate(
        f"document.getElementById('id_dias_semana').tomselect.setValue(['SEGUNDA', 'QUINTA'])"
    )
    
    # 5. Fechamento do Circuito
    page.click('button[type="submit"]:has-text("Salvar Nova Turma")')
    
    # 6. Sensor de Confirmação Visual
    # Procura pela tarja verde do Bootstrap garantindo que a transaction.atomic rodou perfeitamente
    alerta = page.locator(".alert-success")
    expect(alerta).to_be_visible(timeout=5000)