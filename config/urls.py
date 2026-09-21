from django.contrib import admin
from django.contrib.auth import views as auth_views
from apps.core import views as core_views
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include, re_path
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', core_views.home, name='home'),
    path('relatorios/', core_views.relatorios_gerenciais, name='relatorios_gerenciais'),
    path('relatorios/exportar/', core_views.exportar_relatorio_excel, name='exportar_relatorio_excel'),
    path('faq/', core_views.painel_faq, name='faq'),
    path('faq/moderacao/', core_views.moderar_faq, name='moderar_faq'),
    path('suporte/', core_views.abrir_ticket_suporte, name='suporte'),
    path('suporte/meus-chamados/', core_views.meus_chamados, name='meus_chamados'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('academico/', include('apps.academico.urls', namespace='academico')),
    path('pessoas/', include('apps.pessoas.urls', namespace='pessoas')),
    path('saude/', include('apps.saude.urls', namespace='saude')),
    path('trocar-senha/', auth_views.PasswordChangeView.as_view(template_name='registration/trocar_senha.html', success_url='/trocar-senha/sucesso/'), name='trocar_senha'),
    path('trocar-senha/sucesso/', auth_views.PasswordChangeDoneView.as_view(template_name='registration/trocar_senha_sucesso.html'), name='trocar_senha_sucesso'),
    path('recuperar-senha/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html',email_template_name='registration/password_reset_email.html',subject_template_name='registration/password_reset_subject.txt'), name='password_reset'),
    path('recuperar-senha/enviado/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('recuperar-senha/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
    path('recuperar-senha/completo/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),
    path('session-timeout/', core_views.session_idle_timeout, name='session_idle_timeout'),
]

if not settings.DEBUG:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {
            'document_root': settings.MEDIA_ROOT,
        }),
    ]
else:
    # O comportamento normal caso você volte para o ambiente de testes
    from django.conf.urls.static import static
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
if 'hijack' in settings.INSTALLED_APPS:
    urlpatterns += [
        path('hijack/', include('hijack.urls')),
    ]
    
