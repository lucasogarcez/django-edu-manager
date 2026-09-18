from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

class CategoriaFAQ(models.Model):
    nome = models.CharField('Nome da Categoria', max_length=100)
    # A ordem define a prioridade de exibição no painel (ex: 1 aparece antes de 2)
    ordem = models.PositiveIntegerField('Ordem de Exibição', default=0)

    class Meta:
        verbose_name = 'Categoria de Ajuda'
        verbose_name_plural = 'Categorias de Ajuda'
        ordering = ['ordem', 'nome']

    def __str__(self):
        return self.nome

class PerguntaFrequente(models.Model):
    # A chave estrangeira liga o pino da pergunta ao pino da categoria
    categoria = models.ForeignKey(CategoriaFAQ, on_delete=models.CASCADE, related_name='perguntas')
    pergunta = models.CharField('Pergunta', max_length=255)
    resposta = models.TextField('Resposta')
    ordem = models.PositiveIntegerField('Ordem de Exibição', default=0)
    
    is_publicada = models.BooleanField('Aprovada / Publicada?', default=True, 
        help_text="Desmarque para ocultar. Sugestões de usuários nascem como 'False'.")
    
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Sugerido por", help_text="Usuário que enviou esta sugestão para o FAQ.")


    class Meta:
        verbose_name = 'Pergunta Frequente'
        verbose_name_plural = 'Perguntas Frequentes'
        ordering = ['ordem', 'pergunta']

    def __str__(self):
        status = "[PÚBLICA]" if self.is_publicada else "[PENDENTE]"
        return f"{status} {self.pergunta}"
    
def validar_tamanho_imagem(arquivo):
    limite_mb = 2
    if arquivo.size > limite_mb * 1024 * 1024:
        raise ValidationError(f"O anexo é muito pesado. O tamanho máximo permitido é {limite_mb}MB.")

class TicketSuporte(models.Model):
    TIPO_CHOICES = [
        ('DUVIDA', 'Dúvida de Uso (Como fazer algo)'),
        ('ERRO_DIGITACAO', 'Erro de Planilha / Digitação (O sistema avisou um erro)'),
        ('BUG', 'Bug do Sistema (Tela de Erro 500 / Quebrou)'),
        ('SUGESTAO', 'Sugestão de Melhoria'),
    ]

    STATUS_CHOICES = [
        ('ABERTO', 'Aberto (Aguardando Engenharia)'),
        ('ANALISE', 'Em Análise'),
        ('RESOLVIDO', 'Resolvido'),
        ('DESCARTADO', 'Descartado (Erro do Usuário)'),
    ]

    # Captura automática de quem abriu o chamado (Sem ele precisar digitar o nome)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tickets')
    
    tipo = models.CharField('Tipo do Problema', max_length=20, choices=TIPO_CHOICES, default='DUVIDA')
    
    # A Barreira de Fricção (Perguntas Direcionadas)
    passo_a_passo = models.TextField('O que você estava tentando fazer?', 
                                     help_text='Ex: Tentando importar a ficha de Futsal do polo FUNEL.')
    
    mensagem_erro = models.TextField('Qual a mensagem de erro exata na tela?', blank=True,
                                     help_text='Se o sistema exibiu uma tarja amarela ou vermelha, copie o texto e cole aqui.')
    
    resposta_tecnica = models.TextField(blank=True, null=True, 
        help_text="Solução, laudo ou instrução para o usuário. Deixe em branco se não houver."
    )
    
    anexo = models.ImageField(
        upload_to='chamados_suporte/%Y/%m/', # Organiza em pastas por Ano/Mês
        blank=True, 
        null=True,
        validators=[validar_tamanho_imagem],
        help_text="Anexe um print da tela com o erro (Opcional. Máx 2MB)."
    )
    
    status = models.CharField('Status', max_length=15, choices=STATUS_CHOICES, default='ABERTO')
    criado_em = models.DateTimeField('Aberto em', auto_now_add=True)
    resolvido_em = models.DateTimeField('Resolvido em', null=True, blank=True)

    class Meta:
        verbose_name = 'Ticket de Suporte'
        verbose_name_plural = 'Tickets de Suporte'
        ordering = ['-criado_em']

    def __str__(self):
        return f"[{self.get_status_display()}] {self.get_tipo_display()} - {self.usuario.first_name}"