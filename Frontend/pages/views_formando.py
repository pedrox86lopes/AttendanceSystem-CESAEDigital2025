import streamlit as st
from datetime import datetime, timedelta
from django.utils import timezone
from Gestao.models import Modulo, Aula, RegistoPresenca

def mostrar_interface_formando(user):
    st.subheader("Módulos disponíveis")
    modulos = Modulo.objects.all()
    hoje = timezone.now().date()

    for modulo in modulos:
        aulas = Aula.objects.filter(modulo=modulo, data=hoje)
        if aulas.exists():
            with st.expander(modulo.nome):
                for aula in aulas:
                    st.markdown(f"Aula de hoje ({aula.periodo})")
                    if st.button(f"Registar presença ({aula.periodo})", key=f"{aula.id}"):
                        _, created = RegistoPresenca.objects.get_or_create(
                            formando=user,
                            aula=aula,
                            defaults={
                                "entrada": timezone.now(),
                                "saida": timezone.now() + timedelta(hours=3),
                                "motivo_atraso": "",
                                "falta_justificada": False
                            }
                        )
                        if created:
                            st.success("Presença registada!")
                        else:
                            st.info("Já existe presença para esta aula.")
