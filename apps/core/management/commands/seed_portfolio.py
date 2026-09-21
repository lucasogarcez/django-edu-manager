from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from faker import Faker
import datetime
import random
import re

from apps.academico.models import Modalidade, Turma, Matricula, Categoria, TurmaDias, Chamada, Presenca
from apps.academico.utils import get_dias_canonicos
from apps.core.models import TicketSuporte, CategoriaFAQ, PerguntaFrequente
from apps.localizacao.models import Polo
from apps.pessoas.models import Aluno, Professor, Estagiario
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
        
        self.stdout.write("Fabricando crachás de demonstração (Diretoria, Secretaria, Estagiário)...")

        try:
            grupo_professor = Group.objects.get(name='Professores')
            grupo_estagiario = Group.objects.get(name='Estagiarios')
            grupo_secretaria = Group.objects.get(name='Secretaria')
            grupo_diretoria = Group.objects.get(name='Diretoria')
        except Group.DoesNotExist:
            self.stdout.write(self.style.ERROR("ERRO: Grupos ausentes. Rode o setup_grupos primeiro."))
            return
        
        # CRIAÇÃO DE DIRETORIA (Usuário)
        user_dir, _ = Usuario.objects.get_or_create(
            email='diretor@portfolio.com',
            defaults={'username': 'diretor@portfolio.com', 'first_name': 'Diretor', 'is_staff': True}
        )
        if _:
            user_dir.set_password('senha123')
            user_dir.save()
        user_dir.groups.add(grupo_diretoria)

        # CRIAÇÃO DE SECRETARIA (Usuário)
        user_sec, _ = Usuario.objects.get_or_create(
            email='secretaria@portfolio.com',
            defaults={'username': 'secretaria@portfolio.com', 'first_name': 'Secretaria', 'is_staff': True}
        )
        if _:
            user_sec.set_password('senha123')
            user_sec.save()
        user_sec.groups.add(grupo_secretaria)

        # CRIAÇÃO DE ESTAGIÁRIO (Usuário)
        user_est, _ = Usuario.objects.get_or_create(
            email='estagiario@portfolio.com',
            defaults={'username': 'estagiario@portfolio.com', 'first_name': 'Estagiário', 'is_staff': False}
        )
        if _:
            user_est.set_password('senha123')
            user_est.save()
        user_est.groups.add(grupo_estagiario)
        Estagiario.objects.get_or_create(usuario=user_est)
        

        # CRIAÇÃO DE PROFESSORES (Usuários)
        user_prof, prof_criado = Usuario.objects.get_or_create(
            username='professor@portfolio.com',
            defaults={
                'first_name': 'Professor',
                'last_name': 'Demonstração',
                'email': 'professor@portfolio.com',
                'is_staff': False, 
                'is_superuser': False,
            }
        )

        if prof_criado:
            user_prof.set_password('senha123')
            user_prof.save()
            Professor.objects.create(usuario=user_prof)
        
        user_prof.groups.add(grupo_professor)
            
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
                    'is_staff': False
                }
            )
            
            if created:
                usuario.set_password('senha123')
                usuario.save()
        
            professor, prof_created = Professor.objects.get_or_create(usuario=usuario)
            usuario.groups.add(grupo_professor)
            
            professores.append(professor)
            
        self.stdout.write(self.style.SUCCESS('6 Professores criados (Senha: senha123).'))

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
            
            TurmaDias.objects.filter(turma_id=turma).delete()
            
            padroes_funcionamento = [
                "SEG E QUA", 
                "TER/QUI", 
                "SEG, QUA e SEX", 
                "SAB",
                "3 e 5"
            ]
            
            string_bruta = random.choice(padroes_funcionamento)
            
            _, lista_enums_dias, _ = get_dias_canonicos(string_bruta)
            
            for enum_dia in lista_enums_dias:
                TurmaDias.objects.create(
                    turma_id=turma, 
                    dia_semana=enum_dia.value
                )
                
            turmas.append(turma)

        self.stdout.write(self.style.SUCCESS('10 Turmas geradas.'))
        
        professor_portfolio = Professor.objects.get(usuario__email='professor@portfolio.com')

        if len(turmas) >= 2:
            self.stdout.write("Soldando turmas ao painel do Professor de Demonstração...")
            
            turmas[0].professores.add(professor_portfolio)
            turmas[1].professores.add(professor_portfolio)
            
            self.stdout.write(self.style.SUCCESS("Intertravamento de turmas M2M concluído."))

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
            
            turmas_com_vaga = [t for t in turmas if Matricula.objects.filter(turma_id=t).count() < t.capacidade]
            
            if turmas_com_vaga:
                turma_alvo = random.choice(turmas_com_vaga)
                Matricula.objects.create(
                    aluno_id=aluno, 
                    turma_id=turma_alvo,
                    data_inicio='2026-07-12',
                    status='ATIVA'
                )
                
        email_admin = 'admin@portfolio.com'
        senha_admin = 'senha123'
            
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
        
        self.stdout.write("Gravando Firmware de Ajuda (Categorias e FAQs)...")

        cat_matricula, _ = CategoriaFAQ.objects.get_or_create(nome='Matrículas e Alunos', defaults={'ordem': 1})
        cat_sistema, _ = CategoriaFAQ.objects.get_or_create(nome='Sistema e Erros Técnicos', defaults={'ordem': 2})
        cat_relatorio, _ = CategoriaFAQ.objects.get_or_create(nome='Exportação e Relatórios', defaults={'ordem': 3})

        # Matriz de dados: (Categoria, Pergunta, Resposta, Status Público, Autor)
        faqs_dados = [
            (cat_matricula, "Como transfiro um aluno de turma?", "Acesse o painel do aluno, clique em 'Editar Matrícula' e selecione a nova turma no menu suspenso.", True, None),
            (cat_sistema, "O que significa 'Erro 500'?", "O Erro 500 indica uma falha de processamento no servidor (Backend). Quando ocorrer, abra um ticket anexando o print da tela.", True, None),
            (cat_relatorio, "Posso exportar a lista de chamadas em Excel?", "Atualmente o sistema exporta apenas em PDF. Estamos trabalhando na integração com planilhas para a próxima versão.", True, user_prof), # Sugerida pelo professor
            (cat_sistema, "Adicionar aviso automático para os pais", "Seria ótimo o sistema enviar notificações via WhatsApp quando o aluno faltar.", False, user_sec), # Sugestão em análise (oculta no frontend)
        ]

        for categoria, pergunta, resposta, status, autor in faqs_dados:
            PerguntaFrequente.objects.get_or_create(
                pergunta=pergunta,
                defaults={
                    'categoria': categoria,
                    'resposta': resposta,
                    'is_publicada': status,
                    'autor': autor,
                    'ordem': 1
                }
            )

        self.stdout.write("Injetando Telemetria Operacional (Tickets de Suporte)...")


        # Ticket 1: Dúvida Resolvida (Registrado pelo Professor)
        TicketSuporte.objects.get_or_create(
            passo_a_passo="Tentando registrar a presença da turma de Basquete Sub-15.",
            defaults={
                'usuario': user_prof,
                'tipo': 'DUVIDA',
                'mensagem_erro': 'Nenhuma mensagem, apenas não acho o botão.',
                'status': 'RESOLVIDO',
                'resposta_tecnica': 'A funcionalidade de chamadas foi movida para a aba "Diário de Classe" na barra lateral esquerda. As permissões foram corrigidas.',
                'resolvido_em': timezone.now() - datetime.timedelta(days=2)
            }
        )

        # Ticket 2: Falha de Inserção (Registrado pela Secretaria, aguardando análise)
        TicketSuporte.objects.get_or_create(
            passo_a_passo="Importando a planilha de novos alunos do polo central.",
            defaults={
                'usuario': user_sec,
                'tipo': 'ERRO_DIGITACAO',
                'mensagem_erro': 'IntegrityError: duplicate key value violates unique constraint',
                'status': 'ANALISE',
                'resposta_tecnica': '',
            }
        )

        # Ticket 3: Quebra de Sistema (Registrado pelo Estagiário, totalmente aberto)
        TicketSuporte.objects.get_or_create(
            passo_a_passo="Usando o filtro de busca avançada por data de nascimento.",
            defaults={
                'usuario': user_est,
                'tipo': 'BUG',
                'mensagem_erro': 'Error 500: Timeout na requisição do banco de dados',
                'status': 'ABERTO',
                'resposta_tecnica': '',
            }
        )
        
        self.stdout.write(self.style.SUCCESS('Módulos de FAQ e Suporte carregados com sucesso.'))
        
        self.stdout.write("Calibrando painéis de telemetria e gráficos gerenciais...")

        secretarias = Usuario.objects.filter(groups__name='Secretaria')
        if secretarias.exists():
            self.stdout.write("Distribuindo matrículas entre a equipe de atendimento...")
            todas_matriculas = Matricula.objects.all()
            for matricula in todas_matriculas:
                matricula.realizado_por = random.choice(secretarias)
                matricula.save()

        # Seleciona 10% dos alunos da esteira para serem as cobaias do radar de risco (< 70% de presença)
        todos_alunos = list(Aluno.objects.all())
        qtd_evasao = max(1, int(len(todos_alunos) * 0.10))
        alunos_em_risco = random.sample(todos_alunos, qtd_evasao)

        self.stdout.write("Forjando histórico de chamadas e controle de catracas...")
        agora = timezone.now()
        turmas_ativas = Turma.objects.all()

        for turma in turmas_ativas:
            matriculas_da_turma = Matricula.objects.filter(turma_id=turma, status='ATIVA')
            
            if not matriculas_da_turma.exists():
                continue

            # Simula a abertura de 4 a 8 diários de classe no último mês
            qtd_aulas = random.randint(4, 8)
            
            for i in range(qtd_aulas):
                # Retrocede o relógio para espalhar as chamadas no último mês
                dias_atras = random.randint(1, 30)
                data_simulada = agora - timedelta(days=dias_atras)
                
                # O construtor usa 'turma_id' como você definiu na Foreign Key do models.py
                chamada = Chamada.objects.create(
                    turma_id=turma,
                    is_reposicao=False
                )
                
                # Sobrescreve a data de criação automática (auto_now_add) para enganar os gráficos
                Chamada.objects.filter(id=chamada.id).update(data_chamada=data_simulada)
                
                for matricula in matriculas_da_turma:
                    aluno = matricula.aluno_id
                    
                    # Se o aluno for uma cobaia de evasão, o sensor tem 85% de chance de falhar (FALTA)
                    if aluno in alunos_em_risco:
                        status_sorteado = 'FALTA' if random.random() < 0.85 else 'PRESENTE'
                    else:
                        # Aluno normal: 90% de chance de estar presente, 5% atraso, 5% falta
                        peso = random.random()
                        if peso < 0.90:
                            status_sorteado = 'PRESENTE'
                        elif peso < 0.95:
                            status_sorteado = 'ATRASO'
                        else:
                            status_sorteado = 'FALTA'
                    
                    # Instancia o registro na tabela de presenças
                    Presenca.objects.create(
                        chamada_id=chamada,
                        aluno_id=aluno,
                        status=status_sorteado,
                        observacoes="Log gerado por simulador de telemetria" if status_sorteado == 'FALTA' else ""
                    )
                    
        self.stdout.write(self.style.SUCCESS("Painéis e gráficos calibrados com sucesso!"))
        
        self.stdout.write(self.style.SUCCESS('SEED CONCLUÍDO COM SUCESSO! O sistema está pronto para demonstração.'))