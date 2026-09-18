from django.test import TransactionTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

from apps.pessoas.models import Aluno
from apps.pessoas.services import mesclar_cadastros_aluno

Usuario = get_user_model()

class MultiplexadorMergeTests(TransactionTestCase):
    """
    Bancada de Testes (QA) para o Circuito de Mesclagem de Cadastros.
    Verifica a integridade do banco de dados e a segurança das views.
    """

    def setUp(self):
        # 1. PREPARAÇÃO DA BANCADA (Setup de Hardware)
        
        # Criação de um operador autorizado (Diretor)
        self.operador = Usuario.objects.create_user(
            username="engenheiro_teste", 
            password="password123"
        )
        permissao_merge = Permission.objects.get(codename='change_aluno')
        self.operador.user_permissions.add(permissao_merge)

        # Criação dos terminais de teste (Alunos)
        self.aluno_errado = Aluno.objects.create(
            primeiro_nome="Lucas Silv",
            data_nascimento="2000-02-04",
            ativo=True,
            is_merged=False
        )
        
        self.aluno_correto = Aluno.objects.create(
            primeiro_nome="Lucas Silva", 
            data_nascimento="2000-02-04",
            ativo=True,
            is_merged=False
        )

        # Rota da IHM
        self.url_painel = reverse('pessoas:painel_merge_alunos')

    # =========================================================
    # TESTES DO MOTOR (Lógica de Negócios / Services)
    # =========================================================

    def test_transistor_merge_sucesso(self):
        """
        [TESTE DE CARGA] Verifica se o motor transfere a corrente e 
        desenergiza a placa de origem corretamente.
        """
        # Aciona o motor
        sucesso = mesclar_cadastros_aluno(self.aluno_errado.id, self.aluno_correto.id)
        
        # Recarrega as instâncias direto do banco (Refresh da RAM)
        self.aluno_errado.refresh_from_db()
        self.aluno_correto.refresh_from_db()

        # Aferições com o Multímetro (Asserts)
        self.assertTrue(sucesso, "O motor de merge retornou falha estrutural.")
        
        # A placa errada deve estar desenergizada (Fantasma)
        self.assertTrue(self.aluno_errado.is_merged, "A flag is_merged não foi ativada.")
        self.assertFalse(self.aluno_errado.ativo, "O disjuntor ativo não foi desligado.")
        
        # O relé de redirecionamento deve apontar para o ID correto
        self.assertEqual(self.aluno_errado.merged_into, self.aluno_correto)
        
        # A placa correta deve permanecer intacta
        self.assertFalse(self.aluno_correto.is_merged)

    def test_protecao_curto_circuito(self):
        """
        [TESTE DE SEGURANÇA] Verifica se o sistema desarma (ValueError) 
        ao tentar mesclar um ID com ele mesmo (Loop infinito).
        """
        with self.assertRaisesMessage(ValueError, "Curto-circuito"):
            mesclar_cadastros_aluno(self.aluno_correto.id, self.aluno_correto.id)

    def test_ponteiro_de_redirecionamento(self):
        """
        [TESTE DE ROTEAMENTO] Verifica se a função get_cadastro_real() 
        pula do nó fantasma para o nó ativo corretamente.
        """
        # Executa a soldagem
        mesclar_cadastros_aluno(self.aluno_errado.id, self.aluno_correto.id)
        self.aluno_errado.refresh_from_db()

        # Testa o Jump de Memória
        aluno_alvo = self.aluno_errado.get_cadastro_real()
        self.assertEqual(aluno_alvo.id, self.aluno_correto.id)

    # =========================================================
    # TESTES DO CONTROLADOR (IHM / Views)
    # =========================================================

    def test_ihm_bloqueia_acesso_sem_permissao(self):
        """
        [TESTE DE ACESSO] Um usuário sem a chave 'change_aluno' não 
        pode acessar o painel SCADA.
        """
        invasor = Usuario.objects.create_user(username="hacker", password="123")
        self.client.login(username="hacker", password="123")
        
        response = self.client.get(self.url_painel)
        self.assertEqual(response.status_code, 403, "O disjuntor de permissão (403) falhou.")

    def test_ihm_executa_merge_via_post(self):
        """
        [TESTE DE FLUXO E2E] Simula o operador preenchendo o formulário 
        e clicando em 'Soldar'.
        """
        self.client.login(username="engenheiro_teste", password="password123")

        # Injeção do Payload de Dados (Formulário)
        payload = {
            'aluno_origem': self.aluno_errado.id,
            'aluno_destino': self.aluno_correto.id
        }

        # Disparo HTTP
        response = self.client.post(self.url_painel, data=payload)

        # O circuito deve redirecionar (302) de volta para a lista (ou IHM) após sucesso
        self.assertEqual(response.status_code, 302)

        # Afere fisicamente no banco se a view acionou o motor
        self.aluno_errado.refresh_from_db()
        self.assertTrue(self.aluno_errado.is_merged)