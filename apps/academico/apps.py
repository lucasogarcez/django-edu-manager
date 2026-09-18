from django.apps import AppConfig


class AcademicoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.academico'

    def ready(self):
        """
        Rotina de Inicialização (POST): 
        Liga os sensores de automação assim que o servidor dá o boot.
        """
        import apps.academico.signals # Dispara a leitura do arquivo de gatilhos