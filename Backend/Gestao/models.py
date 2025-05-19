from django.db import models
from django.contrib.auth.models import AbstractUser # Adicionar componentes à classe user!
from django.contrib.auth import get_user_model
from django.utils import timezone


# Create your models here.
class Utilizador(AbstractUser):
    TIPO_CHOICES = [
        ('Formando', 'Formando'),
        ('Formador', 'Formador'),
    ]
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    nif = models.PositiveIntegerField(unique=True, null=True, blank=True)  # <--- Aqui adicionas
    def __str__(self):
        return f"{self.username} ({self.tipo})"


# Vamos agora criar o modelo para o curso, que vai ter um nome e uma carga horária total.
class Curso(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.CharField(max_length=1000)
    carga_horaria_total = models.PositiveIntegerField(help_text="Em Horas")
    def __str__(self):
        return self.nome  # Exibe apenas o nome do curso

# O modelo módulo vai se relacionar com o curso, ou seja, um curso tem vários módulos.
class Modulo(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    formador = models.ForeignKey(Utilizador, on_delete=models.CASCADE, limit_choices_to={'tipo': 'Formador'})
    nome = models.CharField(max_length=100)
    descricao = models.CharField(max_length=1000)
    carga_horaria = models.PositiveIntegerField(help_text="Em Horas")
    def __str__(self):
        return f"{self.nome} ({self.curso.nome})"  # Exibe nome do módulo e nome do curso


# O modelo aula será onde vamos registar as aulas realizadas, com data e período (manhã/tarde).
class Aula(models.Model):
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE)
    data = models.DateField()
    periodo = models.CharField(max_length=10, choices=[('manha', 'Manhã'), ('tarde', 'Tarde')])
    def __str__(self):
        return f"Aula em {self.data} ({self.periodo}) - {self.modulo.nome}"  # Exibe a data, o período e o nome do módulo


class RegistoPresenca(models.Model):
    formando = models.ForeignKey(Utilizador, on_delete=models.CASCADE)
    aula = models.ForeignKey(Aula, on_delete=models.CASCADE)
    entrada = models.DateTimeField(null=True, blank=True)
    saida = models.DateTimeField(null=True, blank=True)
    motivo_atraso = models.TextField(blank=True)
    justificativo = models.FileField(upload_to='justificativos/%Y/%m/%d/', null=True, blank=True)
    falta_justificada = models.BooleanField(default=False)

    class Meta:
        unique_together = ('formando', 'aula')

    def __str__(self):
        return f"{self.formando.username} - {self.aula}"


# Classe para as Notificações no Frontend
class Notificacao(models.Model):
    TIPO_CHOICES = [
        ('presenca', 'Registo de Presença'),
        ('aula', 'Nova Aula'),
        ('aviso', 'Aviso Geral'),
        ('outro', 'Outro'),
    ]
    
    formando = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='notificacoes')
    titulo = models.CharField(max_length=100)
    mensagem = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='aviso')
    data = models.DateTimeField(auto_now_add=True)
    lida = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-data']
        verbose_name = 'Notificação'
        verbose_name_plural = 'Notificações'
    
    def __str__(self):
        return f"{self.titulo} ({'Lida' if self.lida else 'Não lida'})"


class CodigoPresenca(models.Model):
    aula = models.ForeignKey(Aula, on_delete=models.CASCADE)
    codigo = models.CharField(max_length=6, unique=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    valido = models.BooleanField(default=True)

    def is_valid(self):
        """Check if code is still valid (within 30 minutes)"""
        time_diff = timezone.now() - self.timestamp
        return time_diff.total_seconds() <= (30 * 60)  # 30 minutes

    def __str__(self):
        return f"{self.codigo} - {self.aula}"

    class Meta:
        ordering = ['-timestamp']