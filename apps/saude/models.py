from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from apps.pessoas.models import Aluno
from django.core.validators import FileExtensionValidator

class FrequenciaExercicio(models.TextChoices):
    UMA_VEZ = '1x', '1 vez por semana'
    DUAS_VEZES = '2x', '2 vezes por semana'
    TRES_OU_MAIS = '3x+', '3 vezes ou mais por semana'
    
# Entidade auxiliar
class Doenca(models.Model):
    nome = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nome
    
# Entidade auxiliar
class Objetivo(models.Model):
    nome = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nome
    
class QuestionarioSaude(models.Model):
    aluno = models.OneToOneField(Aluno, on_delete=models.CASCADE, related_name='questionario_saude')
    
    # Campos do questionário de saúde
    # 1. Pergunta sobre desmaios ou vertigens
    desmaios_ou_vertigens = models.BooleanField(default=False, blank=True)

    # 2. Doenças diagnosticadas (várias opções)
    doencas = models.ManyToManyField(Doenca, blank=True, related_name='questionarios')
    outras_doencas = models.CharField(max_length=255, blank=True)
    
    # 3. Histórico cardíaco familiar
    historico_cardiaco_familiar = models.BooleanField(default=False, blank=True)
    
    # 4. Frequência de exercício físico
    pratica_exercicio = models.BooleanField(default=False, blank=True)
    tipo_exercicio = models.CharField(max_length=255, blank=True)
    frequencia_exercicio = models.CharField(max_length=3, choices=FrequenciaExercicio.choices, blank=True)
    
    # 5. Objetivos com a prática de atividades físicas
    objetivos = models.ManyToManyField(Objetivo, blank=False, related_name='questionarios')
    outros_objetivos = models.CharField(max_length=255, blank=True)
    
    # 6. Declarações
    declaracao_aptidao = models.BooleanField(default=False, blank=False)
    declaracao_condicao_especial = models.BooleanField(default=False, blank=True)

    # Controle de preenchimento
    data_preenchimento = models.DateField(auto_now_add=True)
    
    # Data de emissão do atestado de aptidão física
    data_atestado_aptidao = models.DateField(null=True, blank=True, verbose_name="Data do Atestado de Aptidão")
    
    # Caminho para arquivo do atestado de aptidão física
    arquivo_atestado = models.FileField(
        upload_to='atestados/%Y/%m/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'png', 'jpg', 'jpeg'])],
        verbose_name="Arquivo do Atestado de Aptidão Física"
    )
    
    def __str__(self):
        return f"Questionário de Saúde - {self.aluno.primeiro_nome} {self.aluno.ultimo_nome}"
    
    @property
    def status_validade_atestado(self):
        """
        Retorna: 'valido', 'aviso' (vence em 30 dias) ou 'vencido'.
        """
        if not self.data_atestado_aptidao:
            return 'pendente' # Nunca entregou

        hoje = timezone.now().date()
        
        if self.data_atestado_aptidao.year == 2025:
            validade = self.data_atestado_aptidao + relativedelta(months=6)
        else:
            validade = self.data_atestado_aptidao + relativedelta(years=1)
            
        aviso_inicio = validade - relativedelta(days=30)

        if hoje > validade:
            return 'vencido'
        elif hoje >= aviso_inicio:
            return 'aviso'
        else:
            return 'valido'
    
@receiver(post_save, sender=Aluno)
def criar_questionario_automatico(sender, instance, created, **kwargs):
    """
    Se a ação for de 'criação' (created=True) de um aluno novo,
    é criado um Questionário vazio automaticamente e atrelado a ele.
    """
    
    if created:
        QuestionarioSaude.objects.create(aluno=instance)