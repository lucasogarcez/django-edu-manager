import os
import sentry_sdk
from django.conf import settings
from django.shortcuts import render

class SentryUserContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Trava de Segurança: Só analisa se o Django já tiver injetado o atributo 'user'
        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                # Captura o primeiro grupo do seu modelo Usuario customizado
                grupo = request.user.groups.first()
                nome_grupo = grupo.name if grupo else "Superuser/Sem Cargo"
                
                sentry_sdk.set_tag("cargo_operador", nome_grupo)
                sentry_sdk.set_user({
                    "id": request.user.id,
                    "username": request.user.username,
                    "email": request.user.email,
                    "perfil": nome_grupo
                })
            except Exception as e:
                # Se qualquer lógica interna falhar, o Sentry reporta a falha do sensor, 
                # mas não impede a página do usuário de carregar
                sentry_sdk.capture_exception(e)
        else:
            sentry_sdk.set_user(None)

        # Garante a continuidade do fluxo para as views do sistema
        return self.get_response(request)
    
class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        caminho_flag = os.path.join(settings.BASE_DIR, 'maintenance.flag')
        
        if os.path.exists(caminho_flag):
            if request.user.is_authenticated and request.user.is_superuser:
                return self.get_response(request)
            
            # Gera a resposta com status 503
            response = render(request, 'manutencao.html', status=503)
            
            # Instrui os robôs e navegadores a tentarem novamente em 60 segundos
            response['Retry-After'] = '60'
            
            return response

        return self.get_response(request)