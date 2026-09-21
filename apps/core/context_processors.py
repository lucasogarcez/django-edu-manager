from django.conf import settings

def indicador_ambiente(request):
    """
    Injeta o status da máquina em TODAS as telas do sistema simultaneamente.
    Isso permite que o HTML base reaja e mude de cor se não for Produção.
    """
    env_name = getattr(settings, 'ENVIRONMENT_NAME', 'Produção')
    env_name_lower = env_name.lower()
    
    return {
        'ENV_NAME': env_name,
        'ENV_COLOR': getattr(settings, 'ENVIRONMENT_COLOR', 'primary'),
        'IS_HOMOLOGATION': env_name_lower not in ('produção', 'portfolio'),
        'IS_PORTFOLIO': env_name_lower == 'portfolio'
    }