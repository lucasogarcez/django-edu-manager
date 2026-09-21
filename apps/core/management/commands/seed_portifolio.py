from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from faker import Faker
import random
import re
from datetime import timedelta

from apps.academico.models import Modalidade, Turma, Matricula, Categoria
from apps.localizacao.models import Polo
from apps.pessoas.models import Aluno, Professor
from apps.saude.models import QuestionarioSaude, Objetivo

Usuario = get_user_model()
fake = Faker('pt_BR')

class Command(BaseCommand):
    help = 'Popula o banco de dados do Portfólio com dados fictícios realistas.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Iniciando o Seed do Portfólio...'))

        # CRIAÇÃO DE DADOS ESTRUTURAIS (Polos e Modalidades)
        polos_nomes = ['Alpha Sede', 'Centro Olímpico', 'Ginásio Nacional']
        modalidades_nomes = ['Futsal', 'Natação', 'Basquete', 'Vôlei', 'Ginástica Artística']
        
        polos = [Polo.objects.get_or_create(nome=nome)[0] for nome in polos_nomes]
        modalidades = [Modalidade.objects.get_or_create(nome=nome)[0] for nome in modalidades_nomes]
        
        self.stdout.write(self.style.SUCCESS(f'{len(polos)} Polos e {len(modalidades)} Modalidades criados.'))

        # CRIAÇÃO DE PROFESSORES (Usuários)
        professores = []
        for _ in range(5):
            nome= fake.first_name()
            sobrenome = fake.last_name()
            username = f"{nome.lower()}.{sobrenome.lower()}"
            usuario, created = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': nome,
                    'last_name': sobrenome,
                    'email': fake.email(),
                    'password': 'senha123',
                    'is_staff': True
                }
            )
            professor = Professor.objects.create(
                usuario=usuario
            )
            
            professores.append(professor)
            
        self.stdout.write(self.style.SUCCESS('5 Professores criados (Senha: senha123).'))

        # CRIAÇÃO DE TURMAS
        turmas = []
        horarios = ['08:00', '10:00', '14:00', '16:00']
        
        categorias_nomes = ['Adulto', 'Juvenil', 'Infantil']
        categorias = [Categoria.objects.get_or_create(nome=nome)[0] for nome in categorias_nomes]
        
        for _ in range(10):
            turma, _ = Turma.objects.get_or_create(
                modalidade_id=random.choice(modalidades),
                categoria=random.choice(categorias),
                polo_id=random.choice(polos),
                horario=random.choice(horarios),
                defaults={
                    'capacidade': random.randint(15, 30),
                    'exige_atestado': True
                }
            )
            turma.professores.add(random.choice(professores))
            turmas.append(turma)

        self.stdout.write(self.style.SUCCESS('10 Turmas geradas.'))

        # CRIAÇÃO DE ALUNOS E MATRÍCULAS (O Core do Negócio)
        objetivos = [Objetivo.objects.get_or_create(nome=obj)[0] for obj in ['Saúde', 'Emagrecimento', 'Lazer', 'Competição']]
        
        qtd_alunos = 60
        self.stdout.write(self.style.WARNING(f'Gerando {qtd_alunos} alunos... Isso pode levar alguns segundos.'))
        
        telefone_sujo = fake.cellphone_number()
        telefone_limpo = re.sub(r'\D', '', telefone_sujo)
        
        for i in range(qtd_alunos):
            aluno = Aluno.objects.create(
                primeiro_nome=fake.first_name(),
                ultimo_nome=fake.last_name(),
                data_nascimento=fake.date_of_birth(minimum_age=8, maximum_age=65),
                tipo_documento='CPF',
                numero_documento=fake.cpf().replace('.', '').replace('-', ''),
                status_documentacao='COMPLETO',
                telefone=telefone_limpo,
                email=fake.email(),
                ativo=True
            )
            
            # Questionário de Saúde com datas realistas (alguns vencidos para mostrar no painel de risco!)
            data_atestado = timezone.now().date() - timedelta(days=random.randint(10, 400))
            
            questionario, created = QuestionarioSaude.objects.update_or_create(
                aluno=aluno,
                defaults={
                    'pratica_exercicio': random.choice([True, False]),
                    'data_atestado_aptidao': data_atestado,
                    'declaracao_aptidao': True
                }
            )
            questionario.objetivos.add(random.choice(objetivos))

            # Matrícula em 1 ou 2 turmas
            turmas_escolhidas = random.sample(turmas, random.randint(1, 2))
            for t in turmas_escolhidas:
                Matricula.objects.create(
                    aluno_id=aluno,
                    turma_id=t,
                    data_inicio='2026-07-12',
                    status='ATIVA'
                )
                
        email_admin = 'admin@portfolio.com'
        senha_admin = 'admin123'
            
        if not Usuario.objects.filter(email=email_admin).exists():
            self.stdout.write("Forjando chave mestra do recrutador...")
            Usuario.objects.create_superuser(
                username=email_admin,
                email=email_admin,
                password=senha_admin,
                first_name='Avaliador',
                last_name='Técnico'
            )
        self.stdout.write(self.style.SUCCESS(f"Acesso garantido: {email_admin} | Senha: {senha_admin}"))

        self.stdout.write(self.style.SUCCESS(f'{qtd_alunos} Alunos criados e matriculados com sucesso!'))
        self.stdout.write(self.style.SUCCESS('SEED CONCLUÍDO COM SUCESSO! O sistema está pronto para demonstração.'))