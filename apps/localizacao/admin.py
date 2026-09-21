from django.contrib import admin
from .models import Polo

@admin.register(Polo)
class PoloAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'endereco')
    search_fields = ('nome',)