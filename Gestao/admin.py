from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Utilizador, Curso, Modulo, Aula, RegistoPresenca

@admin.register(Utilizador)
class UtilizadorAdmin(UserAdmin):
    model = Utilizador

    # Mostra estes campos na listagem
    list_display = ('username', 'email', 'first_name', 'last_name', 'tipo', 'is_staff')

    # Campos a mostrar ao editar utilizador
    fieldsets = UserAdmin.fieldsets + (
        ('Informações adicionais', {'fields': ('tipo',)}),  # adiciona nif aqui se usares
    )

    # Campos ao criar novo utilizador
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Informações adicionais', {'fields': ('tipo',)}),
    )

# Registar os outros modelos normalmente
admin.site.register(Curso)
admin.site.register(Modulo)
admin.site.register(Aula)
admin.site.register(RegistoPresenca)
