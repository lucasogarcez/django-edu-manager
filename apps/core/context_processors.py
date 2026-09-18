from django.conf import settings

def indicador_ambiente(request):
    """
    Injeta o status da máquina em TODAS as telas do sistema simultaneamente.
    Isso permite que o HTML base reaja e mude de cor se não for Produção.
    """
    env_name = getattr(settings, 'ENVIRONMENT_NAME', 'Produção')
    
    return {
        'ENV_NAME': env_name,
        'ENV_COLOR': getattr(settings, 'ENVIRONMENT_COLOR', 'primary'),
        # Relé lógico: Se for diferente de Produção, fecha o circuito para True
        'IS_HOMOLOGATION': env_name.lower() != 'produção' 
    }