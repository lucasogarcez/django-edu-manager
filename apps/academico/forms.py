from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Count, F, Q
from apps.pessoas.models import Professor, Estagiario
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, HTML
from .models import Turma, Matricula, Situacao, Presenca, PresencaStatus, Atestado, DiaSemana
from .utils import verifica_se_turma_existe

def get_turmas_com_vagas():
        # Conta as matrículas ativas para cada turma
        turmas_com_contagem = Turma.objects.annotate(
            matriculas_ativas_count=Count(
                'matriculas', 
                filter=Q(matriculas__status=Situacao.ATIVA)
            )
        )
        # Filtra as turmas onde a contagem é menor que a capacidade
        return turmas_com_contagem.filter(
            matriculas_ativas_count__lt=F('capacidade')
        ).order_by('modalidade_id__nome', 'horario')
        
class TurmaForm(forms.ModelForm):
    
    dias_semana = forms.MultipleChoiceField(
        choices=DiaSemana.choices, # Puxa as opções do seu TextChoices
        widget=forms.SelectMultiple(attrs={'class': 'tomselect-multiple'}),
        label="Dias de Aula",
        required=True
    )
    
    class Meta:
        model = Turma
        
        # 1. Mapeamento de Pinos: Defina exatamente quais campos o usuário pode alterar
        # IMPORTANTE: Confirme se os nomes abaixo estão idênticos aos do seu models.py
        fields = [
            'modalidade_id',
            'professores',
            'estagiarios',
            'categoria',
            'horario',
            'capacidade', 
            'polo_id',
            'exige_atestado',
        ]
        
        # 2. Revestimento da Interface (Widgets): Adiciona o CSS do Bootstrap
        widgets = {
            'modalidade_id': forms.Select(attrs={
                'class': 'tomselect-single',
            }),
            'professores': forms.SelectMultiple(attrs={
                'class': 'tomselect-multiple',
            }),
            'estagiarios': forms.SelectMultiple(attrs={
                'class': 'tomselect-multiple',
            }),
            'categoria': forms.Select(attrs={
                'class': 'tomselect-single',
            }),
            'horario': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control',
            }),
            'capacidade': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1', # Filtro físico de hardware: impede números negativos na interface
            }),
            'polo_id': forms.Select(attrs={
                'class': 'tomselect-single',
            }),
            'exige_atestado': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'role': 'switch',
                'id': 'switchAtestado'
            }),
        }
        
        # 3. Etiquetas (Opcional): Se quiser mudar os rótulos exibidos para o usuário
        labels = {
            'modalidade_id': 'Modalidade de Ensino',
            'professores': 'Professor responsável',
            'estagiarios': 'Estagiário responsável (se houver)',
            'categoria': 'Categoria de Idade',
            'horario': 'Horário de início das aulas',
            'capacidade': 'Número Máximo de Vagas',
            'polo_id': 'Polo de Operação',
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['professores'].queryset = Professor.objects.filter(is_ativo=True)
        self.fields['estagiarios'].queryset = Estagiario.objects.filter(is_ativo=True)
        
        # Modo Aberto: Nenhum é obrigatório individualmente por padrão
        self.fields['estagiarios'].required = False
        self.fields['professores'].required = False
        
    def clean_capacidade(self):
        # Lê a tensão que o usuário digitou no campo
        nova_capacidade = self.cleaned_data.get('capacidade')
        
        # SENSOR DE ESTADO: O 'pk' só existe se for uma Edição. 
        # Se for Criação (pk é None), esse bloco inteiro é ignorado pelo bypass.
        if self.instance and self.instance.pk:
            
            # Conta o número de alunos com a corrente ativa nesta turma
            alunos_ativos = Matricula.objects.filter(
                turma_id=self.instance, 
                status=Situacao.ATIVA
            ).count()
            
            # Se a nova capacidade for menor que o número de alunos já alocados, desarma o disjuntor
            if nova_capacidade < alunos_ativos:
                raise ValidationError(
                    f"Risco de sobrecarga: Esta turma já possui {alunos_ativos} aluno(s) ativo(s). "
                    "Você não pode calibrar a capacidade máxima abaixo da ocupação atual."
                )
                
        return nova_capacidade
    
    def clean(self):
        cleaned_data = super().clean()
        
        professores = cleaned_data.get('professores')
        estagiarios = cleaned_data.get('estagiarios')
        modalidade = cleaned_data.get('modalidade_id')
        polo = cleaned_data.get('polo_id')
        horario = cleaned_data.get('horario')
        dias_semana = cleaned_data.get('dias_semana')

        # 1. TRAVA DE COMANDO (Porta NOR)
        if not professores and not estagiarios:
            raise ValidationError(
                "Erro de Alocação: A turma não pode operar sem comando. "
                "Atribua pelo menos um Professor ou um Estagiário para salvar."
            )

        # 2. INTERLOCK DE DUPLICIDADE (Usa a regra de prioridade do utils.py)
        if modalidade and polo and horario and dias_semana:
            # Passamos os objetos coletados direto para a máscara de validação
            turma_colisao_id = verifica_se_turma_existe(
                nome_mod=modalidade.nome,
                nome_polo=polo.nome,
                obj_horario=horario,
                lista_dias=dias_semana,
                professores_selecionados=professores or [],
                estagiarios_selecionados=estagiarios or []
            )

            if turma_colisao_id:
                # Se for uma nova turma OU se for a edição de uma turma mas colidiu com OUTRA ID
                if not self.instance.pk or self.instance.pk != turma_colisao_id:
                    raise ValidationError(
                        "Conflito de Barramento: Já existe uma turma idêntica cadastrada "
                        "com este mesmo polo, horário, dias e regente responsável."
                    )

        return cleaned_data
        
class MatriculaTurmaForm(forms.Form):
    
    turmas_selecionadas_ids = forms.CharField(
        widget=forms.HiddenInput(),
        label="Escolha até 4 turmas (apenas turmas com vagas são exibidas)",
        required=True
    )

    def __init__(self, *args, **kwargs):
        self.aluno = kwargs.pop('aluno', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        matriculas_atuais_count = 0
        if self.aluno: # Se um aluno existente foi passado (não é um cadastro novo)
            matriculas_atuais_count = Matricula.objects.filter(
                aluno_id=self.aluno,
                status=Situacao.ATIVA
            ).count()
            
        # Adiciona o 'data-' atributo ao widget do campo escondido
        # O JavaScript usará isso para saber o limite de novas seleções
        self.fields['turmas_selecionadas_ids'].widget.attrs.update({
            'data-matriculas-atuais': matriculas_atuais_count
        })
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_tag = False # Essencial para não aninhar forms
        self.helper.layout = Layout(
            HTML("""
                <div class="mb-3">
                    <label class="form-label">Escolha até 4 turmas:</label>
                    <div>
                        <button type="button" class="btn btn-outline-primary" 
                                data-bs-toggle="modal" data-bs-target="#modalSelecaoTurmas">
                            Selecionar Turmas
                        </button>
                    </div>
                    <div id="turmas-selecionadas-display" class="mt-2 text-muted small">
                        Nenhuma turma selecionada.
                    </div>
                </div>
            """),
            # Renderiza o campo escondido
            Field('turmas_selecionadas_ids')
        )

    # Validação de turmas (essencial)
    def clean_turmas_selecionadas_ids(self):
        ids_str = self.cleaned_data.get('turmas_selecionadas_ids', '')
        if not ids_str:
            raise ValidationError("Selecione pelo menos uma turma.")

        try:
            # Converte a string "1,2,3" em lista de inteiros [1, 2, 3]
            turma_ids = [int(id_str) for id_str in ids_str.split(',') if id_str.isdigit()]
        except ValueError:
            raise ValidationError("Seleção de turmas inválida.")

        if not turma_ids:
             raise ValidationError("Nenhuma turma válida selecionada.")

        if len(turma_ids) > 4:
            raise ValidationError(f"Você só pode selecionar até 4 turmas (selecionou {len(turma_ids)}).")
        
        # Pega a contagem de matrículas atuais (do __init__)
        matriculas_atuais_count = 0
        if self.aluno:
             matriculas_atuais_count = Matricula.objects.filter(
                 aluno_id=self.aluno,
                 status=Situacao.ATIVA
             ).count()
             
        # Calcula o total
        limite_total = 4 # MAX_SELECOES
        total_selecionado = len(turma_ids) + matriculas_atuais_count
        
        if total_selecionado > limite_total:
            raise ValidationError(
                f"Você só pode estar em {limite_total} turmas no total. "
                f"Você já está em {matriculas_atuais_count} e selecionou {len(turma_ids)} nova(s)."
            )

        turmas_existentes_count = Turma.objects.filter(id__in=turma_ids).count()
        if turmas_existentes_count != len(turma_ids):
             raise ValidationError("Uma ou mais turmas selecionadas são inválidas ou não existem mais.")

        # RETORNA A LISTA DE IDs LIMPA (NÃO a string)
        return turma_ids
    
    # Método clean geral (valida vagas e guarda queryset)
    def clean(self):
        cleaned_data = super().clean()
        turma_ids = cleaned_data.get('turmas_selecionadas_ids') # Pega a LISTA de IDs retornada pelo clean_ anterior

        if not turma_ids:
            # Se a validação anterior falhou, não continue
            return cleaned_data
        
        # Verifica se o aluno JÁ está matriculado em alguma das turmas escolhidas
        if self.aluno:
            turmas_duplicadas = Matricula.objects.filter(
                aluno_id=self.aluno,
                turma_id__in=turma_ids,
                status=Situacao.ATIVA
            )
            if turmas_duplicadas.exists():
                # Pega os nomes para mostrar no erro (opcional)
                nomes = ", ".join([str(m.turma_id) for m in turmas_duplicadas])
                raise ValidationError(f"O aluno já está matriculado na(s) turma(s): {nomes}")

        # Busca os objetos Turma correspondentes
        turmas_selecionadas = Turma.objects.filter(id__in=turma_ids)
        
        # Valida Vagas
        erros_vagas = []
        for turma in turmas_selecionadas:
            matriculas_ativas = Matricula.objects.filter(turma_id=turma, status=Situacao.ATIVA).count()
            if matriculas_ativas >= turma.capacidade:
                erros_vagas.append(f"Turma '{turma}' ficou lotada.")
        
        if erros_vagas:
            # Adiciona o erro ao campo original para exibição
            self.add_error('turmas_selecionadas_ids', ValidationError(erros_vagas))
        else:
             # Se tudo estiver OK, guarda o queryset para a view usar
             cleaned_data['turmas_selecionadas_ids'] = turmas_selecionadas 

        return cleaned_data

    # Método para criar MÚLTIPLAS Matrículas na view
    def criar_matriculas(self, aluno_obj):
        if not self.is_valid():
            raise ValidationError("Formulário de modalidades inválido.")
            
        turmas_selecionadas = self.cleaned_data['turmas_selecionadas_ids']
        matriculas_criadas = []
        
        from django.utils import timezone
        from django.db import transaction # Import transaction

        # Garante que ou todas as matrículas são criadas ou nenhuma é
        with transaction.atomic():
            for turma_obj in turmas_selecionadas:
                matricula = Matricula.objects.create(
                    aluno_id=aluno_obj, 
                    turma_id=turma_obj,
                    data_inicio=timezone.now().date(),
                    status=Situacao.ATIVA,
                    realizado_por=self.user
                )
                matriculas_criadas.append(matricula)
                
        return matriculas_criadas
    
class PresencaForm(forms.ModelForm):
    """
    Formulário para um único registro de presença de aluno.
    """
    # Sobrescreve o widget padrão para usar Radio Buttons em vez de Dropdown
    status = forms.ChoiceField(
        choices=PresencaStatus.choices,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        initial=PresencaStatus.FALTA, # Define 'Presente' como padrão
        label="" # O nome do aluno já será o label
    )

    observacoes = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Obs...'}),
        required=False,
        label=""
    )

    class Meta:
        model = Presenca
        fields = ['status', 'observacoes'] # A view cuidará de 'aluno_id' e 'chamada_id'

# Cria um FormSet baseado no PresencaForm
# 'extra=0' significa que não mostraremos formulários vazios por padrão
PresencaFormSet = forms.formset_factory(PresencaForm, extra=0)

class AtestadoForm(forms.ModelForm):
    class Meta:
        model = Atestado
        fields = ['motivo', 'data_inicio', 'data_fim', 'arquivo_documento']
        widgets = {
            'data_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'data_fim': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'motivo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Gripe, Consulta Médica...'}),
            'arquivo_documento': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf, .png, .jpg, .jpeg'
            })
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # SENSOR DE ESTADO: Se a instância já tem um ID, é uma Edição (Recalibração).
        # Logo, o operador não precisa enviar o arquivo físico novamente.
        if self.instance and self.instance.pk:
            self.fields['arquivo_documento'].required = False
        else:
            self.fields['arquivo_documento'].required = True
            
    def clean(self):
        cleaned_data = super().clean()
        inicio = cleaned_data.get('data_inicio')
        fim = cleaned_data.get('data_fim')

        if inicio and fim and fim < inicio:
            self.add_error('data_fim', "A data de validade não pode ser anterior à data de início.")
        
        return cleaned_data