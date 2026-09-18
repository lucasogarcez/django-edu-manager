from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

# Importe os seus modelos para puxar as permissões deles
from apps.pessoas.models import Aluno
from apps.academico.models import Chamada, Atestado

class Command(BaseCommand):
    help = 'Provisiona os grupos de acesso e permissões padrão do sistema'

    def handle(self, *args, **kwargs):
        self.stdout.write("Iniciando calibração de Grupos e Permissões...")

        # 1. Definimos a matriz de acesso (Quais grupos existem e o que eles podem fazer)
        # O padrão do Django é: 'ação_nomedomodelo' (add, change, delete, view)
        matriz_acesso = {
            'Professores': [
                # Leituras de Sensores (Apenas Visualização)
                'view_aluno', 'view_turma', 'view_turmadias', 'view_modalidade', 
                'view_polo', 'view_atestado',
                'view_questionariosaude', 'view_doenca', 'view_objetivo',
                
                # Atuadores (Inserção e Edição do fluxo de aula diário)
                'add_chamada', 'change_chamada', 'view_chamada',
                'add_presenca', 'change_presenca', 'view_presenca',
                'add_registroatendimento', 'change_registroatendimento', 'view_registroatendimento',
            ],
            'Estagiarios': [
                'view_aluno', 'view_turma', 'view_turmadias', 'view_modalidade', 
                'view_polo', 'view_atestado', 
                'view_questionariosaude', 'view_doenca', 'view_objetivo',
                'add_chamada', 'change_chamada', 'view_chamada',
                'add_presenca', 'change_presenca', 'view_presenca',
                'add_registroatendimento', 'change_registroatendimento', 'view_registroatendimento',
            ],
            'Secretaria': [
                # A Secretaria faz todo o trabalho braçal de inserção (add), edição (change) e leitura (view).
                # Eles também precisam apagar (delete) matrículas erradas ou atestados inseridos por engano.
                
                'add_aluno', 'change_aluno', 'delete_aluno', 'view_aluno',
                'add_turma', 'change_turma', 'delete_turma', 'view_turma',
                'add_turmadias', 'change_turmadias', 'delete_turmadias', 'view_turmadias',
                'add_modalidade', 'change_modalidade', 'delete_modalidade', 'view_modalidade',
                'add_matricula', 'change_matricula', 'delete_matricula', 'view_matricula',
                
                'add_atestado', 'change_atestado', 'delete_atestado', 'view_atestado',
                'add_questionariosaude', 'change_questionariosaude', 'delete_questionariosaude', 'view_questionariosaude',
                
                # A Secretaria VÊ os diários, mas não apaga (quem apaga chamada é a diretoria ou o próprio sistema)
                'view_chamada', 'view_presenca', 'view_registroatendimento',
            ],
            'Diretoria': [
                # Módulo Pessoas (CRUD Completo)
                'add_aluno', 'change_aluno', 'delete_aluno', 'view_aluno',
                'add_estagiario', 'change_estagiario', 'delete_estagiario', 'view_estagiario',
                'add_professor', 'change_professor', 'delete_professor', 'view_professor',
                
                # Módulo Acadêmico / Estrutural (CRUD Completo)
                'add_turma', 'change_turma', 'delete_turma', 'view_turma',
                'add_turmadias', 'change_turmadias', 'delete_turmadias', 'view_turmadias',
                'add_modalidade', 'change_modalidade', 'delete_modalidade', 'view_modalidade',
                'add_polo', 'change_polo', 'delete_polo', 'view_polo',
                'add_matricula', 'change_matricula', 'delete_matricula', 'view_matricula',
                
                # Módulo Diário de Classe e Financeiro/Gestão (CRUD Completo)
                'add_chamada', 'change_chamada', 'delete_chamada', 'view_chamada',
                'add_presenca', 'change_presenca', 'delete_presenca', 'view_presenca',
                'add_registroatendimento', 'change_registroatendimento', 'delete_registroatendimento', 'view_registroatendimento',
                'add_fechamentomensal', 'change_fechamentomensal', 'delete_fechamentomensal', 'view_fechamentomensal',
                
                # Módulo de Saúde e Justificativas (CRUD Completo)
                'add_atestado', 'change_atestado', 'delete_atestado', 'view_atestado',
                'add_questionariosaude', 'change_questionariosaude', 'delete_questionariosaude', 'view_questionariosaude',
                
                # Dicionários Médicos (CRUD - para adicionar novas doenças/objetivos se necessário)
                'add_doenca', 'change_doenca', 'delete_doenca', 'view_doenca',
                'add_objetivo', 'change_objetivo', 'delete_objetivo', 'view_objetivo',
                
                # Usuários
                'add_usuario', 'change_usuario', 'delete_usuario', 'view_usuario',
                
                # Grupos
                'add_group', 'change_group', 'delete_group', 'view_group',
                
                # FAQ
                'add_CategoriadeAjuda', 'change_CategoriadeAjuda', 'delete_CategoriadeAjuda', 'view_CategoriadeAjuda',
            ]
        }

        # 2. O Loop de Montagem
        for nome_grupo, lista_permissoes in matriz_acesso.items():
            # get_or_create atua como uma solda segura: se já existir, não duplica
            grupo, created = Group.objects.get_or_create(name=nome_grupo)
            
            if created:
                self.stdout.write(self.style.SUCCESS(f"Grupo '{nome_grupo}' criado no banco!"))
            
            # Limpa as permissões antigas e conecta as novas (garante que o código é a fonte da verdade)
            grupo.permissions.clear()
            
            for codename in lista_permissoes:
                try:
                    # Busca a permissão no painel elétrico do Django
                    permissao = Permission.objects.get(codename=codename)
                    grupo.permissions.add(permissao)
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"Aviso: Permissão '{codename}' não encontrada. Verifique o nome."))

        self.stdout.write(self.style.SUCCESS("Provisionamento de segurança concluído com sucesso!"))