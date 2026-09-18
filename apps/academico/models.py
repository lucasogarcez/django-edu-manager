from apps.localizacao.models import Polo
from apps.pessoas.models import Professor, Estagiario, Aluno, Usuario
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Case, When
from django.utils import timezone
from django.conf import settings

class Situacao(models.TextChoices):
    ATIVA = 'ATIVA', 'Ativa'
    INATIVA = 'INATIVA', 'Inativa'
    TRANSFERIDA = 'TRANSFERIDA', 'Transferida'
    CANCELADA = 'CANCELADA', 'Cancelada'
    
class PresencaStatus(models.TextChoices):
    PRESENTE = 'PRESENTE', 'Presente'
    FALTA = 'FALTA', 'Falta'
    FALTA_JUSTIFICADA = 'FALTA JUSTIFICADA', 'Falta justificada'
    ATESTADO = 'ATESTADO', 'Atestado'
    ATRASO = 'ATRASO', 'Atraso'
    
class DiaSemana(models.TextChoices):
    SEGUNDA = 'SEGUNDA', 'Segunda-feira'
    TERCA = 'TERCA', 'Terça-feira'
    QUARTA = 'QUARTA', 'Quarta-feira'
    QUINTA = 'QUINTA', 'Quinta-feira'
    SEXTA = 'SEXTA', 'Sexta-feira'
    SABADO = 'SABADO', 'Sábado'
    DOMINGO = 'DOMINGO', 'Domingo'
    
class DepartamentoChoices(models.TextChoices):
    ESPORTE = 'ESPORTE', 'Esporte'
    LAZER = 'LAZER', 'Lazer'
    
class Categoria(models.Model):
    nome = models.CharField(max_length=50, unique=True, verbose_name="Nome da Categoria")
    
    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        ordering = ['nome'] # Ordena alfabeticamente por padrão

    def __str__(self):
        # Isso é o que vai aparecer no "select" do formulário e no painel Admin
        return self.nome
class Modalidade(models.Model):
    id = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=100)
    departamento = models.CharField(max_length=10, choices=DepartamentoChoices.choices, default=DepartamentoChoices.LAZER, verbose_name="Departamento")
    descricao = models.TextField(blank=True)

    def __str__(self):
        return f"Modalidade {self.id} - {self.nome} ({self.departamento})"

class Turma(models.Model):
    id = models.AutoField(primary_key=True)
    modalidade_id = models.ForeignKey(Modalidade, on_delete=models.CASCADE, related_name='turmas')
    professores = models.ManyToManyField(Professor, limit_choices_to={'is_ativo': True}, related_name='turmas',verbose_name="Professores",blank=True) # Permite que a turma não tenha nenhum professor (ex: só estagiário)
    estagiarios = models.ManyToManyField(Estagiario, limit_choices_to={'is_ativo': True}, related_name='turmas_atuadas',verbose_name="Estagiários",blank=True) # Permite que a turma não tenha nenhum estagiário (ex: só professor)
    polo_id = models.ForeignKey(Polo, on_delete=models.CASCADE, related_name='turmas')
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)
    horario = models.TimeField()
    capacidade = models.IntegerField()
    
    exige_atestado = models.BooleanField(
        default=True,
        verbose_name="Exige Atestado Médico",
        help_text="Define se a presença do atestado é obrigatória para esta turma."
    )

    def __str__(self):
        prof_nomes = ", ".join([p.usuario.get_full_name() for p in self.professores.all()])
        est_nomes = ", ".join([e.usuario.get_full_name() for e in self.estagiarios.all()])
        
        staff = prof_nomes or "Nenhum Prof."
        if est_nomes:
            staff += f" (Est: {est_nomes})"
        dias = ", ".join([dia.get_dia_semana_display() for dia in self.dias.all()])
        return f"{self.modalidade_id.nome} ({self.categoria}) - {staff} - {dias} {self.horario.strftime('%H:%M')} - ({self.polo_id.nome})"
    
    @property
    def is_atestado_obrigatorio(self):
        """ 
        PORTA LÓGICA OR (Global Override):
        Se o sistema inteiro exigir atestado (True), ignora a placa local.
        Se o sistema global estiver frouxo (False), obedece à regra da Turma.
        """
        global_override = getattr(settings, 'OBRIGATORIEDADE_GLOBAL_ATESTADO', True)
        return global_override or self.exige_atestado
    
    def get_professores_nomes(self):
        """
        Retorna uma string com os nomes dos professores desta turma, 
        separados por vírgula.
        """
        # .all() aqui usará os dados pré-buscados (prefetched) pela view
        professores_qs = self.professores.all()
        if not professores_qs:
            return "N/D" # (Nenhum professor definido)
        
        nomes = [p.usuario.get_full_name() for p in professores_qs]
        return ", ".join(nomes)

    def get_estagiarios_nomes(self):
        """
        Retorna uma string com os nomes dos estagiários desta turma, 
        separados por vírgula.
        """
        estagiarios_qs = self.estagiarios.all()
        if not estagiarios_qs:
            return "Nenhum" # (Nenhum estagiário)
            
        nomes = [e.usuario.get_full_name() for e in estagiarios_qs]
        return ", ".join(nomes)
    
    def get_dias_semana(self):
        """ 
        Retorna uma string com os dias da semana da turma,
        lendo a partir do modelo TurmaDias.
        'self' é a instância da Turma.
        'dias' é o related_name='dias' do seu modelo TurmaDias.
        """
        ordem_dias = Case(
            When(dia_semana=DiaSemana.SEGUNDA, then=0),
            When(dia_semana=DiaSemana.TERCA, then=1),
            When(dia_semana=DiaSemana.QUARTA, then=2),
            When(dia_semana=DiaSemana.QUINTA, then=3),
            When(dia_semana=DiaSemana.SEXTA, then=4),
            When(dia_semana=DiaSemana.SABADO, then=5),
            When(dia_semana=DiaSemana.DOMINGO, then=6),
            default=7 # Apenas por segurança
        )
        dias_ordenados = self.dias.all().order_by(ordem_dias) 
        dias_list = [dia.get_dia_semana_display() for dia in dias_ordenados]
        
        return ", ".join(dias_list) if dias_list else "Dias não definidos"
    
class Matricula(models.Model):
    id = models.AutoField(primary_key=True)
    aluno_id = models.ForeignKey(Aluno, on_delete=models.CASCADE, related_name='matriculas')
    turma_id = models.ForeignKey(Turma, on_delete=models.CASCADE, related_name='matriculas')
    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Situacao.choices, default=Situacao.ATIVA)
    realizado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True,related_name='matriculas_realizadas',verbose_name="Realizado por")
    
    def __str__(self):
        return f"Matricula {self.id} - Aluno {self.aluno_id.primeiro_nome} {self.aluno_id.ultimo_nome} - Turma {self.turma_id.id}"

class Chamada(models.Model):
    id = models.AutoField(primary_key=True)
    turma_id = models.ForeignKey(Turma, on_delete=models.CASCADE, related_name='chamadas')
    data_chamada = models.DateTimeField(auto_now_add=True, db_index=True)
    is_reposicao = models.BooleanField(default=False, verbose_name="É Reposição?")
    
    @property
    def dia_local(self):
        return timezone.localtime(self.data_chamada).day
    
    def __str__(self):
        return f"Chamada {self.id} - Turma {self.turma_id.id} - {self.data_chamada}"

class Presenca(models.Model):
    id = models.AutoField(primary_key=True)
    chamada_id = models.ForeignKey(Chamada, on_delete=models.CASCADE, related_name='presencas')
    aluno_id = models.ForeignKey(Aluno, on_delete=models.CASCADE, related_name='presencas')
    status = models.CharField(max_length=20, choices=PresencaStatus.choices, default=PresencaStatus.FALTA, db_index=True)
    observacoes = models.TextField(blank=True)
    
    def __str__(self):
        return f"Presença {self.id} - Aluno {self.aluno_id.primeiro_nome} {self.aluno_id.ultimo_nome} - Chamada {self.chamada_id.id} - Status {self.status}"
    
class TurmaDias(models.Model):
    id = models.AutoField(primary_key=True)
    turma_id = models.ForeignKey(Turma, on_delete=models.CASCADE, related_name='dias')
    dia_semana = models.CharField(max_length=20, choices=DiaSemana.choices)
    
    def __str__(self):
        return f"TurmaDias {self.id} - Turma {self.turma_id.id} - Dia {self.dia_semana}"
    
class Atestado(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE, related_name='atestados')
    motivo = models.CharField(max_length=255, blank=True)
    data_inicio = models.DateField(verbose_name="Data de Início")
    data_fim = models.DateField(verbose_name="Data de Validade/Fim")
    data_cadastro = models.DateTimeField(auto_now_add=True)
    arquivo_documento = models.FileField(
        upload_to='justificativas/%Y/%m',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        verbose_name="Arquivo do Atestado de Justificativas"
    )

    class Meta:
        ordering = ['-data_inicio'] # Mais recentes primeiro

    def __str__(self):
        return f"Atestado {self.aluno} ({self.data_inicio} a {self.data_fim})"

    @property
    def is_ativo(self):
        """ Verifica se o atestado é válido hoje. """
        # Pega o momento atual
        agora = timezone.now()
        
        # Converte o horário UTC para o fuso horário local (Brasil)
        hoje = timezone.localtime(agora).date()
        
        if (self.data_inicio <= hoje <= self.data_fim):
            return "Ativo"
        elif self.data_inicio > hoje:
            return "Agendado"
        
        return "Expirado"
    
class RegistroAtendimento(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='atendimentos_rapidos')
    data_hora = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Atendimento por {self.usuario} em {self.data_hora}"
    
class FechamentoMensal(models.Model):
    turma = models.ForeignKey('Turma', on_delete=models.CASCADE)
    mes = models.IntegerField()
    ano = models.IntegerField()
    
    # Controle de Emissão
    data_emissao = models.DateTimeField(auto_now_add=True)
    emitido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    # Opcional: Upload da ficha assinada (O "Scan")
    arquivo_assinado = models.FileField(upload_to='fichas_assinadas/%Y/%m/', null=True, blank=True)

    class Meta:
        unique_together = ('turma', 'mes', 'ano')

    def __str__(self):
        return f"Ficha {self.mes}/{self.ano} - {self.turma}"