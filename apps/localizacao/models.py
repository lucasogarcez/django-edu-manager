from django.db import models

class Polo(models.Model):
    id = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=100)
    endereco = models.CharField(max_length=255)

    def __str__(self):
        return f"Polo {self.id} - {self.nome}"