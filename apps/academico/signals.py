from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from .models import Professor, Estagiario 

Usuario = get_user_model()

@receiver(m2m_changed, sender=Usuario.groups.through)
def provisionar_perfil_automatico(sender, instance, action, pk_set, **kwargs):
    """
    Sensor Lógico Bidirecional (Soft Delete) com Filtro Anti-Ruído.
    """
    
    # 1. ROTA DE MONTAGEM (Ligando a energia)
    if action == "post_add" and pk_set:
        # FILTRO PASSA-BAIXA: Converte todos os nomes de grupos para minúsculas
        grupos_db = Group.objects.filter(pk__in=pk_set).values_list('name', flat=True)
        grupos_adicionados = [str(nome).lower() for nome in grupos_db]

        # MULTÍMETRO INTELIGENTE: Verifica singular, plural, com e sem acento
        is_professor = any(p in grupos_adicionados for p in ['professor', 'professores'])
        is_estagiario = any(e in grupos_adicionados for e in ['estagiário', 'estagiários', 'estagiario', 'estagiarios'])

        if is_professor:
            prof, created = Professor.objects.get_or_create(usuario=instance)
            if not created and not prof.is_ativo:
                prof.is_ativo = True
                prof.save()
            
        if is_estagiario: 
            est, created = Estagiario.objects.get_or_create(usuario=instance)
            if not created and not est.is_ativo:
                est.is_ativo = True
                est.save()

    # 2. ROTA DE DESMONTAGEM (Cortando a energia - Soft Delete)
    elif action in ["post_remove", "post_clear"]:
        grupos_removidos = []
        if pk_set:
            grupos_db = Group.objects.filter(pk__in=pk_set).values_list('name', flat=True)
            grupos_removidos = [str(nome).lower() for nome in grupos_db]
            
        # MULTÍMETRO INTELIGENTE DA DESMONTAGEM
        lost_professor = any(p in grupos_removidos for p in ['professor', 'professores'])
        lost_estagiario = any(e in grupos_removidos for e in ['estagiário', 'estagiários', 'estagiario', 'estagiarios'])
            
        # O usuário perdeu o grupo Professores (ou a lista foi limpa)
        if not pk_set or lost_professor:
            Professor.objects.filter(usuario=instance).update(is_ativo=False)
            
        # O usuário perdeu o grupo Estagiarios
        if not pk_set or lost_estagiario:
            Estagiario.objects.filter(usuario=instance).update(is_ativo=False)