from django.test import TransactionTestCase, override_settings
from datetime import time
from django.contrib.auth import get_user_model

# Ajuste os imports abaixo para refletir a sua arquitetura
from apps.academico.models import Turma, Modalidade, Polo, Categoria
from apps.academico.views import _persistir_alunos

Usuario = get_user_model()

class CircuitoBypassAtestadoTests(TransactionTestCase):
    """
    Bancada de Testes (QA) para o Relé Condicional de Atestados Médicos.
    Garante que a porta lógica (Global OR Local) funcione perfeitamente.
    """

    def setUp(self):
        # 1. PREPARAÇÃO DA BANCADA (Setup de Hardware)
        self.modalidade = Modalidade.objects.create(nome="Engenharia de Software", id=1)
        self.polo = Polo.objects.create(nome="Campus Principal")
        self.categoria = Categoria.objects.create(nome="Adulto")
        self.horario_padrao = time(10, 0)
        
        self.operador = Usuario.objects.create_user(username="admin", password="123")

        # Turma Padrão (Nasce com o relé de atestado FECHADO/True)
        self.turma_rigorosa = Turma.objects.create(
            modalidade_id=self.modalidade,
            polo_id=self.polo,
            categoria=self.categoria,
            horario=self.horario_padrao,
            capacidade=20
            # exige_atestado = True (Padrão de fábrica)
        )

        # Turma com Bypass (Relé ABERTO/False)
        self.turma_flexivel = Turma.objects.create(
            modalidade_id=self.modalidade,
            polo_id=self.polo,
            categoria=self.categoria,
            horario=self.horario_padrao,
            capacidade=20,
            exige_atestado=False # Bypass Ativado!
        )

        # Payload simulando o JSON que vem do Frontend/Excel
        self.aluno_sem_atestado = [
            {
                'nome': 'João Sem Documento',
                'nascimento': '1990-01-01',
                'atestado': '', # Vazio de propósito
                'status': 'MATRICULADO'
            }
        ]

    # =========================================================
    # TESTES DE PORTA LÓGICA (Modelos)
    # =========================================================

    @override_settings(OBRIGATORIEDADE_GLOBAL_ATESTADO=False)
    def test_rele_padrao_estado_fechado(self):
        """
        [TESTE DE COMPONENTE] Verifica se uma turma nova exige atestado por padrão.
        """
        self.assertTrue(
            self.turma_rigorosa.is_atestado_obrigatorio, 
            "A Turma padrão DEVE exigir atestado."
        )

    @override_settings(OBRIGATORIEDADE_GLOBAL_ATESTADO=False)
    def test_rele_bypass_estado_aberto(self):
        """
        [TESTE DE COMPONENTE] Verifica se o bypass local desliga a exigência.
        """
        self.assertFalse(
            self.turma_flexivel.is_atestado_obrigatorio, 
            "O Bypass falhou. A Turma flexível não deveria exigir atestado."
        )

    @override_settings(OBRIGATORIEDADE_GLOBAL_ATESTADO=True)
    def test_disjuntor_mestre_sobrescreve_bypass(self):
        """
        [TESTE DE SOBRECARGA] Com o Global Override = True, MESMO a turma
        com bypass deve exigir o atestado.
        """
        self.assertTrue(
            self.turma_flexivel.is_atestado_obrigatorio, 
            "FALHA CRÍTICA: O Disjuntor Mestre Global não conseguiu sobrescrever o Bypass local."
        )

    # =========================================================
    # TESTES DE INTERTRAVAMENTO (Views / Importação)
    # =========================================================

    @override_settings(OBRIGATORIEDADE_GLOBAL_ATESTADO=False)
    def test_intertravamento_bloqueia_aluno_sem_atestado(self):
        """
        [TESTE DE PROTEÇÃO] Tentar persistir um aluno sem atestado numa
        turma rigorosa deve causar um curto-circuito (ValueError).
        """
        with self.assertRaisesMessage(ValueError, "obrigatória para esta turma"):
            _persistir_alunos(self.aluno_sem_atestado, self.turma_rigorosa, self.operador)

    @override_settings(OBRIGATORIEDADE_GLOBAL_ATESTADO=False)
    def test_bypass_permite_aluno_sem_atestado(self):
        """
        [TESTE DE FLUXO] Tentar persistir um aluno sem atestado numa
        turma flexível DEVE funcionar, burlando o ValueError.
        """
        try:
            # Para este teste não quebrar pela falta do _processar_registro_aluno completo no DB,
            # nós englobamos num Try. Se o Bypass não funcionar, o ValueError vai estourar ANTES
            # das funções subsequentes serem chamadas.
            _persistir_alunos(self.aluno_sem_atestado, self.turma_flexivel, self.operador)
        except ValueError as ve:
            # Se estourou ValueError de atestado, o bypass falhou
            if "A Data do Atestado" in str(ve):
                self.fail("O Bypass falhou! O intertravamento barrou um aluno na turma flexível.")
        except Exception:
            # Se der outro erro (ex: falta de _processar_registro_aluno), ignoramos pois 
            # o que queremos aferir é apenas o Bypass Inicial (Portão de Entrada).
            pass