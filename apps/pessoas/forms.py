from django import forms
from .models import Aluno
from django.utils.safestring import mark_safe
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column
from localflavor.br.validators import BRCPFValidator
from django.core.exceptions import ValidationError

class AlunoForm(forms.ModelForm):
    nome_completo = forms.CharField(label=mark_safe("Nome completo<br>do aluno"))
    nome_completo_responsavel = forms.CharField(label=mark_safe("Nome completo<br>do responsável"), required=False)
    
    cadastro_pendente = forms.BooleanField(
        label="Marcar como Cadastro Pendente (Falta de Documentação)",
        required=False,
        help_text="Marque esta caixa se o aluno for iniciar as atividades mas ainda não entregou os documentos."
    )
    class Meta:
        model = Aluno
        fields = [
            'nome_completo',
            'nome_completo_responsavel',
            'data_nascimento',
            'tipo_documento',
            'numero_documento',
            'email',
            'endereco',
            'telefone',
            'telefone_emergencia',
        ]
        labels = {
            'data_nascimento': 'Data de nascimento',
            'telefone_emergencia': 'Telefone do responsável (Emergência)',
            'endereco': 'Endereço',
            'tipo_documento': 'Tipo do documento',
            'numero_documento': 'Número do documento',
            'email': 'E-mail',
            'telefone': 'Telefone do Aluno',
        }
        widgets = {
            'data_nascimento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control', 'placeholder': 'DD/MM/AAAA'}),
            'endereco': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Rua, número, bairro, cidade, estado, CEP'}),
            'tipo_documento': forms.Select(attrs={'class': 'form-select'}),
            'numero_documento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apenas números'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@exemplo.com'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(##) #########'}),
            'telefone_emergencia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(##) #########'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 1. Deixa os campos opcionais individualmente
        self.fields['tipo_documento'].required = False
        self.fields['numero_documento'].required = False
        self.fields['telefone'].required = False
        self.fields['telefone_emergencia'].required = False
        self.fields['endereco'].required = False
        self.fields['data_nascimento'].required = False
        
        # --- LÓGICA PARA PREENCHER OS NOMES COMPLETOS NA EDIÇÃO ---
        if self.instance and self.instance.pk: 
            self.initial['cadastro_pendente'] = (self.instance.status_documentacao == 'PENDENTE')
            
            partes_nome = [self.instance.primeiro_nome, self.instance.ultimo_nome]
            self.initial['nome_completo'] = ' '.join(filter(None, partes_nome)) 

            if hasattr(self.instance, 'primeiro_nome_responsavel'):
                 partes_resp = [self.instance.primeiro_nome_responsavel, self.instance.ultimo_nome_responsavel]
                 self.initial['nome_completo_responsavel'] = ' '.join(filter(None, partes_resp))
                 
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_tag = False
        
        self.helper.layout = Layout(
            Row(
                Column('nome_completo', css_class='col-md-6'),
                Column('nome_completo_responsavel', css_class='col-md-6'),
                css_class='g-3'
            ),
            Row(
                Column('data_nascimento', css_class='col-md-12'),
                css_class='mb-3'
            ),
            Row(
                Column('cadastro_pendente', css_class='col-md-12 text-danger fw-bold border border-danger rounded p-2 mb-3 bg-light'),
                css_class='g-0'
            ),
            Row(
                Column('tipo_documento', css_class='col-md-4'),
                Column('numero_documento', css_class='col-md-8'),
                css_class='g-3 mb-3'
            ),
            Row(
                Column('email', css_class='col-md-12'),
                css_class='mb-3'
            ),
            Row(
                Column('endereco', css_class='col-md-12'),
                css_class='mb-3'
            ),
            Row(
                Column('telefone', css_class='col-md-6'),
                Column('telefone_emergencia', css_class='col-md-6'),
                css_class='g-3 mb-3'
            )
        )
        
    def clean(self):
        cleaned_data = super().clean()
        
        is_pendente = cleaned_data.get('cadastro_pendente')
        tipo_doc = cleaned_data.get('tipo_documento')
        numero_doc = cleaned_data.get('numero_documento')
        tel_emergencia = cleaned_data.get('telefone_emergencia', '')
        nome_resp = cleaned_data.get('nome_completo_responsavel', '')
        
        if is_pendente:
            self.instance.status_documentacao = 'PENDENTE'
        else:
            self.instance.status_documentacao = 'COMPLETO'

        # MÁQUINA DE ESTADOS: VIA DE EXCEÇÃO (PENDENTE)
        if is_pendente:
            # Perdoa todos os erros automáticos gerados pelo Django
            for field in ['tipo_documento', 'numero_documento', 'telefone', 'telefone_emergencia', 'nome_completo_responsavel', 'data_nascimento']:
                if field in self._errors:
                    del self._errors[field]
            
            # Higieniza o banco: Se está pendente, não salvamos lixo na documentação
            cleaned_data['numero_documento'] = None
            cleaned_data['tipo_documento'] = None
            cleaned_data['telefone'] = None
            cleaned_data['telefone_emergencia'] = None
            cleaned_data['nome_completo_responsavel'] = None
            cleaned_data['data_nascimento'] = None
            
        # MÁQUINA DE ESTADOS: VIA PRINCIPAL (COMPLETO)
        else: 
            # 1. Regra Estrutural
            if not tipo_doc:
                self.add_error('tipo_documento', "Obrigatório para cadastros completos.")
            if not numero_doc:
                self.add_error('numero_documento', "Obrigatório para cadastros completos.")
            
            # 2. Regra da Certidão (Menores de Idade)
            if tipo_doc == 'CERTIDAO_NASCIMENTO':
                if not nome_resp:
                    self.add_error('nome_completo_responsavel', "O nome do responsável é obrigatório para menores de idade.")
                if not tel_emergencia:
                    self.add_error('telefone_emergencia', "O telefone do responsável é obrigatório para menores de idade.")
                
            # 3. Checagem de Hardware (Formatos e Validades)
            if tipo_doc == 'CPF' and numero_doc:
                cpf_numerico = ''.join(filter(str.isdigit, str(numero_doc)))
                try:
                    BRCPFValidator()(cpf_numerico)
                except ValidationError:
                    self.add_error('numero_documento', "O CPF digitado é inválido.")
                else:
                    # Trava de Segurança contra Duplicidade
                    ja_existe = Aluno.objects.filter(numero_documento=cpf_numerico, tipo_documento='CPF').exclude(pk=self.instance.pk).exists()
                    if ja_existe:
                        self.add_error('numero_documento', "Este CPF já está cadastrado no sistema.")
                    cleaned_data['numero_documento'] = cpf_numerico

            elif tipo_doc == 'RG' and numero_doc:
                rg_numerico = ''.join(filter(str.isdigit, str(numero_doc)))
                if not 5 <= len(rg_numerico) <= 14:
                    self.add_error('numero_documento', "O RG deve ter entre 5 e 14 dígitos.")
                cleaned_data['numero_documento'] = rg_numerico
            
        return cleaned_data
        
    # --- VALIDAÇÃO CUSTOMIZADA PARA A DATA DE NASCIMENTO ---    
    def clean_data_nascimento(self):
        data = self.cleaned_data['data_nascimento'] or ''
        
        if not data:
            return data
            
        if data is None:
            raise forms.ValidationError("Data de nascimento inválida.")
        
        if data > forms.fields.datetime.date.today():
            raise forms.ValidationError("A data de nascimento não pode ser no futuro.")
        
        if data < forms.fields.datetime.date(1900, 1, 1):
            raise forms.ValidationError("A data de nascimento não pode ser anterior a 01/01/1900.")
        
        return data
    
    # --- VALIDAÇÃO CUSTOMIZADA PARA O TELEFONE ---
    def clean_telefone(self):
        data = self.cleaned_data.get('telefone', '') or ''
        
        if not data:
            return data
        
        # Limpa tudo que não for um dígito (remove '(', ')', '-', ' ')
        telefone_numerico = ''.join(filter(str.isdigit, data))
        
        if not 10 <= len(telefone_numerico) <= 11: # considerando DDD
            raise forms.ValidationError("O telefone deve estar no formato (##) ######## ou (##) ######### (ex: (34) 123456789).")
        
        return telefone_numerico
    
    # --- VALIDAÇÃO CUSTOMIZADA PARA O TELEFONE DE EMERGÊNCIA ---
    def clean_telefone_emergencia(self):
        data = self.cleaned_data.get('telefone_emergencia', '') or ''

        if not data:
            return data  # Campo opcional, retorna vazio se não preenchido
        
        # Limpa tudo que não for um dígito (remove '(', ')', '-', ' ')
        telefone_numerico = ''.join(filter(str.isdigit, data))

        if not (10 <= len(telefone_numerico) <= 11):
            raise forms.ValidationError("O telefone deve conter 10 ou 11 dígitos (incluindo DDD).")
        
        return telefone_numerico
        

    def save(self, commit=True):
        aluno = super().save(commit=False)

        # Tradutor de Estado: Grava a decisão do Checkbox no banco
        if self.cleaned_data.get('cadastro_pendente'):
            aluno.status_documentacao = 'PENDENTE'
        else:
            aluno.status_documentacao = 'COMPLETO'

        # Separar nome completo do aluno
        nome = self.cleaned_data.get('nome_completo', '').strip()
        if nome:
            partes = nome.split(' ')
            aluno.primeiro_nome = partes[0]
            aluno.ultimo_nome = ' '.join(partes[1:]) if len(partes) > 1 else ''

        # Separar nome completo do responsável
        nome_resp = self.cleaned_data.get('nome_completo_responsavel', '')
        if nome_resp:
            nome_resp.strip()
            partes_resp = nome_resp.split(' ')
            aluno.primeiro_nome_responsavel = partes_resp[0]
            aluno.ultimo_nome_responsavel = ' '.join(partes_resp[1:]) if len(partes_resp) > 1 else ''
        else:
            aluno.primeiro_nome_responsavel = ''
            aluno.ultimo_nome_responsavel = ''

        if commit:
            aluno.save()
        return aluno
    
class ImportarAlunosForm(forms.Form):
    arquivo_excel = forms.FileField(
        label="Planilha Cadastro Geral (.xlsx)",
        help_text="O sistema importará Alunos e tentará vinculá-los às Turmas existentes baseado em Modalidade, Horário e Dias."
    )