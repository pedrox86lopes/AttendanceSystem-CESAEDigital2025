import streamlit as st
from django.core.exceptions import ObjectDoesNotExist
from Gestao.models import Utilizador

def login_user():
    st.subheader("Login")
    username = st.text_input("Nome de utilizador")
    password = st.text_input("Palavra-passe", type="password")

    if st.button("Entrar"):
        try:
            user = Utilizador.objects.get(username=username)
            if user.check_password(password):
                st.session_state["user"] = user
                st.rerun()
            else:
                st.error("Palavra-passe incorreta")
        except ObjectDoesNotExist:
            st.error("Utilizador não encontrado")
