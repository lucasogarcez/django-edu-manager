from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Usuario, Professor, Estagiario

@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    """
    Define o admin para o modelo Usuario customizado.
    Herda de BaseUserAdmin para manter toda a funcionalidade de senha/permissão.
    """
    
    # Adiciona o campo 'telefone' à lista de exibição no admin
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'telefone')

    # Adiciona o campo 'telefone' aos fieldsets da página de *edição*
    # Tivemos que copiar os fieldsets padrão do Django para adicionar 'telefone'
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Informações Pessoais', {'fields': ('first_name', 'last_name', 'email', 'telefone')}), # 'telefone' adicionado aqui
        ('Permissões', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Datas Importantes', {'fields': ('last_login', 'date_joined')}),
    )

    # Adiciona o campo 'telefone' ao formulário de *criação* de usuário
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            # Adiciona 'telefone' junto com os campos padrão de criação
            'fields': ('username', 'email', 'telefone', 'password1', 'password2'), 
        }),
    )
    
    def get_fieldsets(self, request, obj=None):
        # 1. Lê a placa de interface original
        fieldsets = super().get_fieldsets(request, obj)
        
        # 2. Se o operador for a Diretoria (não-superuser)...
        if not request.user.is_superuser:
            new_fieldsets = []
            
            # 3. Varre os painéis da tela procurando a seção "Permissões"
            for name, config in fieldsets:
                if name == 'Permissões':
                    # Transforma a tupla em lista para podermos manipular
                    fields = list(config['fields'])
                    
                    # Arranca a caixa de permissões avulsas (user_permissions) do painel
                    if 'user_permissions' in fields:
                        fields.remove('user_permissions')
                        
                    # Remonta o painel apenas com o que sobrou (is_active, is_staff e groups)
                    new_fieldsets.append((name, {'fields': tuple(fields)}))
                else:
                    new_fieldsets.append((name, config))
                    
            return tuple(new_fieldsets)
            
        # Se for você (superuser), devolve a placa completa com tudo liberado
        return fieldsets

    # Trava A: Isolar o pino de escalonamento de privilégio (is_superuser)
    def get_readonly_fields(self, request, obj=None):
        readonly = super().get_readonly_fields(request, obj)
        if not request.user.is_superuser:
            if isinstance(readonly, tuple):
                return readonly + ('is_superuser',)
            elif isinstance(readonly, list):
                return tuple(readonly) + ('is_superuser',)
        return readonly

    # Trava B: Impedir alteração no Kernel (Sua própria conta)
    def has_change_permission(self, request, obj=None):
        if obj and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    # Trava C: Impedir deleção do Kernel
    def has_delete_permission(self, request, obj=None):
        if obj and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)