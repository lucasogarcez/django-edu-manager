from django import forms
from .models import PerguntaFrequente, TicketSuporte

class SugestaoFAQForm(forms.ModelForm):
    """
    Interface de captura de dados. Exibe apenas os campos seguros para o usuário final,
    escondendo os controles de administração (ordem, aprovação, etc).
    """
    class Meta:
        model = PerguntaFrequente
        fields = ['categoria', 'pergunta', 'resposta']
        widgets = {
            'categoria': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'pergunta': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Como faço para...', 'required': True}),
            'resposta': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Descreva a resposta sugerida...', 'required': True}),
        }
        
class TicketSuporteForm(forms.ModelForm):
    class Meta:
        model = TicketSuporte
        fields = ['tipo', 'passo_a_passo', 'mensagem_erro', 'anexo']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'passo_a_passo': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descreva detalhadamente a ação...'}),
            'mensagem_erro': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Copie o aviso amarelo/vermelho aqui...'}),
            'anexo': forms.ClearableFileInput(attrs={'class': 'form-control','accept': '.pdf, .png, .jpg, .jpeg'})
        }