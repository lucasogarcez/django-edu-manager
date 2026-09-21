from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import Modalidade, Turma, TurmaDias, Categoria

# Para adicionar dias diretamente na página da Turma
class TurmaDiasInline(admin.TabularInline):
    model = TurmaDias
    extra = 1 # Quantos formulários extras de dia mostrar

@admin.register(Modalidade)
class ModalidadeAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome')
    search_fields = ('nome',)

@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    # --- MUDANÇAS AQUI ---
    list_display = ('id', 'modalidade_id', 'get_professores', 'get_estagiarios', 'polo_id', 'categoria', 'horario') # Troca estagiario_id
    list_filter = ('modalidade_id', 'polo_id', 'categoria', 'professores', 'estagiarios') # Adiciona estagiarios
    search_fields = (
        'modalidade_id__nome', 
        'professores__usuario__first_name', 
        'estagiarios__usuario__first_name' # Adiciona busca por estagiário
    )
    
    # Widgets aprimorados para M2M
    filter_horizontal = ('professores', 'estagiarios',) # Adiciona 'estagiarios'
    
    inlines = [TurmaDiasInline] 
    # --- FIM DAS MUDANÇAS ---

    @admin.display(description='Professores')
    def get_professores(self, obj):
        return ", ".join([p.usuario.get_full_name() for p in obj.professores.all()])
    
    # --- NOVO MÉTODO PARA EXIBIR ESTAGIÁRIOS ---
    @admin.display(description='Estagiários')
    def get_estagiarios(self, obj):
        return ", ".join([e.usuario.get_full_name() for e in obj.estagiarios.all()])
    
    @admin.display(description='Dias da Semana')
    def get_dias_semana(self, obj):
        return ", ".join([dia.get_dia_semana_display() for dia in obj.dias.all()])

    # --- VALIDAÇÃO DAS REGRAS DE NEGÓCIO (ESSENCIAL) ---
    def clean(self):
        """ Validação customizada no Admin (chamada antes de salvar) """
        super().clean()
        
        # 'cleaned_data' contém os valores do formulário
        professores = self.cleaned_data.get('professores')
        estagiarios = self.cleaned_data.get('estagiarios')
        
        if not professores and not estagiarios:
            # Regra 1: Não pode salvar turma sem ninguém
            raise ValidationError("A turma deve ter pelo menos um professor ou um estagiário alocado.")
        
        # Regra 2: Limite máximo (Ex: 2 pessoas no total)
        total_staff = 0
        if professores:
            total_staff += professores.count()
        if estagiarios:
            total_staff += estagiarios.count()
            
        MAX_STAFF_POR_TURMA = 2 # Defina seu limite
        if total_staff > MAX_STAFF_POR_TURMA:
            raise ValidationError(
                f"Uma turma pode ter no máximo {MAX_STAFF_POR_TURMA} responsáveis. "
                f"(Você selecionou {professores.count()} professor(es) e {estagiarios.count()} estagiário(s))."
            )
            
@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome')
    search_fields = ('nome',)