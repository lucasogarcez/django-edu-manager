from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Div
from .models import QuestionarioSaude

CHECKBOX_WRAPPER_CLASS = 'form-check form-check-reverse text-start'

FREQUENCIA_CHOICES = (
    ("", "Selecione a frequência"),
    ("1x", "1 vez por semana"),
    ("2x", "2 vezes por semana"),
    ("3x+", "3 vezes ou mais por semana"),
)

class QuestionarioSaudeForm(forms.ModelForm):
    class Meta:
        model = QuestionarioSaude
        fields = [
            'desmaios_ou_vertigens',
            'doencas',
            'outras_doencas',
            'historico_cardiaco_familiar',
            'pratica_exercicio',
            'tipo_exercicio',
            'frequencia_exercicio',
            'objetivos',
            'outros_objetivos',
            'declaracao_aptidao',
            'declaracao_condicao_especial',
            'data_atestado_aptidao',
            'arquivo_atestado',
        ]
        labels = {
            'desmaios_ou_vertigens': "Você desmaia com frequência ou tem episódios importantes de vertigem?",
            'historico_cardiaco_familiar': "Algum parente próximo teve ataque cardíaco ou outro problema relacionado com o coração?",
            'pratica_exercicio': "Você pratica exercícios físicos regularmente?",
            'tipo_exercicio': "Qual(is) tipo(s) de exercício?",
            'frequencia_exercicio': "Com que frequência você pratica exercícios físicos?",
            'objetivos': "Quais são seus objetivos com a prática de atividades físicas?",
            'outros_objetivos': "Outros objetivos:",
            'doencas': "Você foi diagnosticado com alguma das seguintes doenças?",
            'outras_doencas': "Especifique quais outras doenças:",
            'declaracao_aptidao': "Declaro estar apto(a) para prática esportiva na qual me inscrevi.",
            'declaracao_condicao_especial': "Declaro ter condição(es) especial(is) de saúde e irei apresentar atestado médico no ato da matrícula.",
        }
        widgets = {
            'desmaios_ou_vertigens': forms.CheckboxInput(),
            'historico_cardiaco_familiar': forms.CheckboxInput(),
            'pratica_exercicio': forms.CheckboxInput(),
            'tipo_exercicio': forms.TextInput(),
            'frequencia_exercicio': forms.Select(choices=FREQUENCIA_CHOICES),
            'doencas': forms.CheckboxSelectMultiple(),
            'outras_doencas': forms.TextInput(),
            'objetivos': forms.CheckboxSelectMultiple(),
            'outros_objetivos': forms.TextInput(),
            'declaracao_aptidao': forms.CheckboxInput(),
            'declaracao_condicao_especial': forms.CheckboxInput(),
            'data_atestado_aptidao': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'arquivo_atestado': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf, .png, .jpg, .jpeg'
            }),
        }

    def __init__(self, *args, **kwargs):
        remover_atestados = kwargs.pop('remover_atestados', False)
        
        super().__init__(*args, **kwargs)

        if remover_atestados:
            if 'data_atestado_aptidao' in self.fields:
                del self.fields['data_atestado_aptidao']
            if 'arquivo_atestado' in self.fields:
                del self.fields['arquivo_atestado']
        
        self.fields['frequencia_exercicio'].choices = FREQUENCIA_CHOICES
        self.fields['declaracao_aptidao'].required = True
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Field('desmaios_ou_vertigens', wrapper_class=CHECKBOX_WRAPPER_CLASS),
            Field('doencas'),
            Div('outras_doencas', css_class='ms-3', css_id='outras-doencas-div', style='display:none;'),
            Field('historico_cardiaco_familiar', wrapper_class=CHECKBOX_WRAPPER_CLASS),
            Field('pratica_exercicio', wrapper_class=CHECKBOX_WRAPPER_CLASS),
            Field('tipo_exercicio'),
            Field('frequencia_exercicio'),
            Field('objetivos'),
            Div('outros_objetivos', css_class='ms-3', css_id='outros-objetivos-div', style='display:none;'),
            Field('declaracao_aptidao', wrapper_class=CHECKBOX_WRAPPER_CLASS),
            Field('declaracao_condicao_especial', wrapper_class=CHECKBOX_WRAPPER_CLASS),
        )

    # --- VALIDAÇÃO CUSTOMIZADA PARA OS CAMPOS DOENÇAS, EXERCÍCIOS E OBJETIVOS ---
    def clean(self):
        cleaned_data = super().clean()
        
        doencas = cleaned_data.get('doencas')
        outras_doencas = cleaned_data.get('outras_doencas')
        
        lista_nomes_doencas = [str(doenca).lower() for doenca in doencas]

        foi_marcado_outra = any(s in ['outras', 'outra'] for s in lista_nomes_doencas)

        if foi_marcado_outra and not outras_doencas:
            self.add_error('outras_doencas', "Você marcou 'Outras', por favor, especifique a(s) doença(s).")
        
        pratica_exercicio = cleaned_data.get('pratica_exercicio')
        tipo_exercicio = cleaned_data.get('tipo_exercicio')
        frequencia_exercicio = cleaned_data.get('frequencia_exercicio')

        if pratica_exercicio and not tipo_exercicio:
            msg = "Você marcou que pratica exercícios, por favor, especifique o tipo."
            self.add_error('tipo_exercicio', msg)

        if pratica_exercicio and not frequencia_exercicio:
            msg = "Você marcou que pratica exercícios, por favor, especifique a frequência."
            self.add_error('frequencia_exercicio', msg)
            
        objetivos = cleaned_data.get('objetivos')
        outros_objetivos = cleaned_data.get('outros_objetivos')
        
        if objetivos:
            foi_marcado_outro = objetivos.filter(nome__iexact='Outros').exists()

        if objetivos and foi_marcado_outro and not outros_objetivos:
             self.add_error('outros_objetivos', "Você marcou 'Outros', por favor, especifique o(s) objetivo(s).")

        return cleaned_data
    
class RenovarAptidaoForm(forms.ModelForm):
    class Meta:
        model = QuestionarioSaude
        fields = ['data_atestado_aptidao', 'arquivo_atestado']
        widgets = {
            'data_atestado_aptidao': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'}, 
                format='%Y-%m-%d'
            ),
        }
        labels = {
            'data_atestado_aptidao': 'Data de Emissão do Novo Atestado'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # SENSOR DE ESTADO DE MEMÓRIA:
        # Se a instância já possui um arquivo físico registrado no banco de dados,
        # o pino de upload deixa de ser obrigatório para o operador administrativo.
        if self.instance and self.instance.arquivo_atestado:
            self.fields['arquivo_atestado'].required = False
        else:
            self.fields['arquivo_atestado'].required = True

    def clean_arquivo_atestado(self):
        arquivo_enviado = self.cleaned_data.get('arquivo_atestado')
        
        # Se um arquivo foi enviado, mas já existia um na memória
        if arquivo_enviado and self.instance and self.instance.arquivo_atestado:
            try:
                # SENSOR DE MASSA: Compara o peso exato em bytes.
                # Se o peso for idêntico, assumimos que é o mesmo documento anexado por engano
                # e devolvemos o ponteiro do arquivo original do banco, cortando o novo upload.
                if arquivo_enviado.size == self.instance.arquivo_atestado.size:
                    return self.instance.arquivo_atestado
            except Exception:
                # Failsafe: Se o disco de armazenamento estiver inacessível para leitura de peso, 
                # deixa o fluxo seguir seu curso normal.
                pass
                
        return arquivo_enviado