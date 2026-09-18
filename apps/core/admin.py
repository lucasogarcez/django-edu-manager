from django.contrib import admin
from .models import CategoriaFAQ, PerguntaFrequente, TicketSuporte
from django.utils import timezone

# Cria um sub-módulo (shield) visual para as perguntas
class PerguntaInline(admin.TabularInline):
    model = PerguntaFrequente
    extra = 1 # Deixa sempre 1 linha em branco pronta para ser preenchida

# Registra a Categoria e acopla o sub-módulo dentro dela
@admin.register(CategoriaFAQ)
class CategoriaFAQAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ordem')
    search_fields = ('nome',)
    inlines = [PerguntaInline] # Acoplamento físico na tela
    
@admin.register(TicketSuporte)
class TicketSuporteAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo', 'status', 'criado_em')
    list_filter = ('status', 'tipo', 'criado_em')
    search_fields = ('usuario__first_name', 'usuario__username', 'passo_a_passo')
    readonly_fields = ('usuario', 'criado_em')
    
    def has_module_permission(self, request):
        # Esconde o modelo do menu lateral para quem não é superuser
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        # Bloqueia a leitura (mesmo que a pessoa adivinhe a URL /admin/core/ticketsuporte/)
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
    # Adiciona uma Ação em Massa rápida no Admin para você marcar vários como resolvidos
    actions = ['marcar_como_resolvido', 'marcar_como_erro_usuario']

    @admin.action(description="Marcar chamados como Resolvidos")
    def marcar_como_resolvido(self, request, queryset):
        queryset.update(status='RESOLVIDO', resolvido_em=timezone.now())
        self.message_user(request, f"{queryset.count()} chamado(s) marcado(s) como solucionado(s)!")

    @admin.action(description="Descartar (Avisar que foi Erro do Usuário)")
    def marcar_como_erro_usuario(self, request, queryset):
        queryset.update(status='DESCARTADO', resolvido_em=timezone.now())
        self.message_user(request, f"{queryset.count()} chamado(s) descartado(s).")