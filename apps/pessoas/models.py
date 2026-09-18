import unicodedata
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError

class Usuario(AbstractUser):
    telefone = models.CharField(max_length=15)
    
    def __str__(self):
        return self.get_full_name() or self.username
    
class AlunoManager(models.Manager):
    """
    Controlador Lógico: Oculta automaticamente as placas desenergizadas (mescladas) 
    de todas as consultas padrão do sistema, evitando que o aluno fantasma apareça nas listas.
    """
    def get_queryset(self):
        # Retorna apenas os nós ativos (não mesclados)
        return super().get_queryset().filter(is_merged=False)
        
    def all_with_merged(self):
        # Bypass de Manutenção: Permite que o sistema acesse a base completa (ativos + fantasmas)
        return super().get_queryset()

class Aluno(models.Model):
    TIPO_DOC_CHOICES = [
        ('CPF', 'CPF'),
        ('RG', 'RG'),
        ('CERTIDAO_NASCIMENTO', 'Certidão de Nascimento'),
    ]
    
    STATUS_DOC_CHOICES = [
        ('COMPLETO', 'Completo (Validado)'),
        ('PENDENTE', 'Cadastro Pendente'),
    ]
    
    id = models.AutoField(primary_key=True)
    endereco = models.CharField(max_length=255)
    primeiro_nome = models.CharField(max_length=150)
    ultimo_nome = models.CharField(max_length=150)
    primeiro_nome_responsavel = models.CharField(max_length=150, blank=True)
    ultimo_nome_responsavel = models.CharField(max_length=150, blank=True)
    data_nascimento = models.DateField('Data de Nascimento', null=True, blank=True)
    tipo_documento = models.CharField('Tipo de Documento', max_length=30, choices=TIPO_DOC_CHOICES, null=True, blank=True)
    numero_documento = models.CharField('Número do Documento', max_length=50, null=True, blank=True)
    status_documentacao = models.CharField('Status do Cadastro', max_length=20, choices=STATUS_DOC_CHOICES, default='COMPLETO')
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=15, null=True, blank=True)
    telefone_emergencia = models.CharField(max_length=15, null=True, blank=True)
    ativo = models.BooleanField(default=True, verbose_name="Ativo no Sistema")
    data_inativacao = models.DateField(null=True, blank=True)
    is_merged = models.BooleanField(
        default=False, 
        verbose_name="Cadastro Mesclado (Desenergizado)",
        help_text="Indica se este cadastro foi absorvido por outro e não deve mais ser listado."
    )
    # Ponteiro Auto-Referencial
    merged_into = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='cadastros_absorvidos',
        verbose_name="Mesclado para (Redirecionamento)",
        help_text="Ponteiro de memória: Se este aluno é duplicado, para qual ID ele foi movido?"
    )
    primeiro_nome_limpo = models.CharField(max_length=150, blank=True, null=True, db_index=True, editable=False)
    ultimo_nome_limpo = models.CharField(max_length=150, blank=True, null=True, db_index=True, editable=False)
    
    objects = AlunoManager()
    
    def clean(self):
        super().clean()
    
    def save(self, *args, **kwargs):
        """
        Gatilho de Hardware: Antes de soldar os dados no banco, 
        limpa os acentos e converte para minúsculas automaticamente.
        """
        if self.primeiro_nome:
            # Remove acentos e joga para minúsculas (Ex: "João" -> "joao")
            nome = str(self.primeiro_nome).strip().lower()
            self.primeiro_nome_limpo = ''.join(c for c in unicodedata.normalize('NFD', nome) if unicodedata.category(c) != 'Mn')
            
        if self.ultimo_nome:
            sobrenome = str(self.ultimo_nome).strip().lower()
            self.ultimo_nome_limpo = ''.join(c for c in unicodedata.normalize('NFD', sobrenome) if unicodedata.category(c) != 'Mn')

        super().save(*args, **kwargs)

    def __str__(self):
        if self.is_merged:
            return f"{self.primeiro_nome} [MERGED -> ID:{self.merged_into_id}]"
    
        return f"{self.primeiro_nome} {self.ultimo_nome}"
    
    def get_cadastro_real(self):
        """
        Função Auxiliar de Roteamento (Jump Instruction):
        Se o sistema tentar ler os dados desta placa, mas ela estiver mesclada,
        ele segue o cabo físico recursivamente até achar o Aluno verdadeiro.
        """
        if self.is_merged and self.merged_into:
            return self.merged_into.get_cadastro_real()
        return self
    
    @property
    def cpf(self):
        """
        Sensor de Leitura: Se algum template antigo pedir 'aluno.cpf', 
        nós entregamos o numero_documento (somente se for do tipo CPF).
        """
        if self.tipo_documento == 'CPF':
            return self.numero_documento
        return None

    @cpf.setter
    def cpf(self, valor):
        """
        Sensor de Gravação: Se algum formulário antigo tentar salvar 'aluno.cpf = 123',
        nós convertemos isso magicamente para a nova estrutura polimórfica.
        """
        self.numero_documento = valor
        self.tipo_documento = 'CPF'
        
    @property
    def rg(self):
        if self.tipo_documento == 'RG':
            return self.numero_documento
        return None

    @rg.setter
    def rg(self, valor):
        self.numero_documento = valor
        self.tipo_documento = 'RG'
    
    @property
    def documento_exibicao(self):
        """
        Máquina de Formatação: Lê o tipo do documento e aplica a máscara 
        visual correta de pontuação sem alterar o valor real no banco.
        """
        if self.status_documentacao == 'PENDENTE' or not self.numero_documento:
            return "Pendente"
            
        import re
        # Limpa tudo que não for alfanumérico (mantém 'X' para RGs de SP)
        num_limpo = re.sub(r'[^a-zA-Z0-9]', '', self.numero_documento).upper()

        if self.tipo_documento == 'CPF' and len(num_limpo) == 11:
            # Padrão: 000.000.000-00
            return f"{num_limpo[:3]}.{num_limpo[3:6]}.{num_limpo[6:9]}-{num_limpo[9:]}"
            
        elif self.tipo_documento == 'CERTIDAO_NASCIMENTO' and len(num_limpo) == 32:
            # Padrão Nacional de Matrícula (32 dígitos)
            # Ex: 123456.01.55.2023.1.00001.222.0000000-00
            return f"{num_limpo[:6]}.{num_limpo[6:8]}.{num_limpo[8:10]}.{num_limpo[10:14]}.{num_limpo[14:15]}.{num_limpo[15:20]}.{num_limpo[20:23]}.{num_limpo[23:30]}-{num_limpo[30:]}"
            
        elif self.tipo_documento == 'RG':
            # RG varia muito de estado para estado. 
            # Se for o padrão MG (8 dígitos), formatamos: XX.XXX.XXX
            if len(num_limpo) == 8:
                return f"{num_limpo[:2]}.{num_limpo[2:5]}.{num_limpo[5:8]}"
            # Para RGs de outros estados (Ex: SP, RJ, que tem tamanhos diferentes), 
            # devolvemos o número limpo sem pontuação para evitar quebras.
            return num_limpo

        # Fallback genérico se a pessoa digitou um documento com tamanho incompleto
        return self.numero_documento
    
    @property
    def telefone_formatado(self):
        """
        Retorna o telefone formatado (ex: (34) 99999-8888 ou (34) 3333-4444).
        Assume que 'self.telefone' contém apenas dígitos (como o clean_telefone faz).
        """
        tel = self.telefone
        
        # Se estiver vazio ou for None, retorne um placeholder
        if not tel:
            return "-"
            
        # Remove qualquer caractere não numérico (segurança extra)
        tel_limpo = "".join(filter(str.isdigit, tel))

        # Formato Celular (11 dígitos): (XX) 9XXXX-XXXX
        if len(tel_limpo) == 11:
            return f"({tel_limpo[0:2]}) {tel_limpo[2:7]}-{tel_limpo[7:11]}"
        
        # Formato Fixo (10 dígitos): (XX) XXXX-XXXX
        elif len(tel_limpo) == 10:
            return f"({tel_limpo[0:2]}) {tel_limpo[2:6]}-{tel_limpo[6:10]}"
            
        # Se for um formato inesperado, retorna o dado original
        else:
            return self.telefone
        
    @property
    def status_atestado_formatado(self):
        """
        Retorna o status do atestado de forma segura.
        Se o aluno não tiver questionário preenchido, retorna 'sem_cadastro'.
        """
        try:
            return self.questionario_saude.status_validade_atestado
        except Exception:
            # Se o questionário não existir (RelatedObjectDoesNotExist), cai aqui
            return 'sem_cadastro'

    @property
    def data_atestado_safe(self):
        """
        Tenta pegar a data do atestado. 
        Se não tiver questionário ou data, retorna None.
        Isso evita o erro 500 no template.
        """
        try:
            return self.questionario_saude.data_atestado_aptidao
        except Exception:
            # Se der erro (não existe questionário), retorna None
            return None
        
    @property
    def atestado_aptidao_seguro(self):
        """
        Tenta acessar o questionário de saúde. Se ele não existir (ex.: alunos importados),
        retorna None de forma segura em vez de "crashar" o sistema.
        """
        
        if hasattr(self, 'questionario_saude'):
            return self.questionario_saude
        return None

class Professor(models.Model):
    id = models.AutoField(primary_key=True)
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='professor')
    
    is_ativo = models.BooleanField(default=True, verbose_name="Professor Ativo")
    
    def __str__(self):
        status = "" if self.is_ativo else " [INATIVO]"
        return f"{self.usuario.get_full_name() or self.usuario.username}{status}"
    
class Estagiario(models.Model):
    id = models.AutoField(primary_key=True)
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='estagiario')
    
    is_ativo = models.BooleanField(default=True, verbose_name="Estagiario Ativo")
    
    def __str__(self):
        status = "" if self.is_ativo else " [INATIVO]"
        return f"{self.usuario.get_full_name() or self.usuario.username}{status}"