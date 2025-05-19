import os
import sys
import django
import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import io
import time
import secrets
from streamlit.runtime.scriptrunner import RerunData, RerunException
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile


# Configure Django
sys.path.append(os.path.abspath(".."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Projecto_Final.settings")
django.setup()

from django.utils import timezone
from Gestao.models import Modulo, Aula, RegistoPresenca, CodigoPresenca
from auth.login import login_user

# Constants
CODE_VALIDITY_MINUTES = 30

# Global dictionary to store active codes
ACTIVE_CODES = {}

# LOGO
st.logo(
    "./images/cesae-digital-logo.svg",
    link="http://localhost:8502/",
    icon_image="",
)

# Page config
st.set_page_config(
    page_title="Gestão de Presenças CESAE",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --------------------------
# Code Generation
# --------------------------
def generate_attendance_code(aula_id):
    """Generate a unique attendance code"""
    # Generate a 6-character code (letters and numbers)
    code = secrets.token_hex(3).upper()  # 6 characters
    
    # Create code in database
    try:
        aula = Aula.objects.get(id=aula_id)
        codigo = CodigoPresenca.objects.create(
            aula=aula,
            codigo=code
        )
        return code, codigo.timestamp
    except Exception as e:
        st.error(f"Erro ao gerar código: {str(e)}")
        return None, None

def is_code_valid(code):
    """Check if code is still valid (within 30 minutes)"""
    try:
        codigo = CodigoPresenca.objects.get(codigo=code, valido=True)
        return codigo.is_valid()
    except CodigoPresenca.DoesNotExist:
        return False

def get_aula_id_from_code(code):
    """Get aula_id from a valid code"""
    try:
        codigo = CodigoPresenca.objects.get(codigo=code, valido=True)
        if codigo.is_valid():
            return codigo.aula.id
    except CodigoPresenca.DoesNotExist:
        pass
    return None

def invalidate_code(code):
    """Mark a code as invalid"""
    try:
        codigo = CodigoPresenca.objects.get(codigo=code)
        codigo.valido = False
        codigo.save()
    except CodigoPresenca.DoesNotExist:
        pass

# --------------------------
# Teacher Interface
# --------------------------
def mostrar_interface_formador(user):
    # Initialize last refresh time if not exists
    if 'last_refresh_time' not in st.session_state:
        st.session_state.last_refresh_time = datetime.now().strftime('%H:%M:%S')
        st.session_state.last_refresh_timestamp = time.time()
    
    # Date range selector
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        start_date = st.date_input("Data inicial", 
                                 value=timezone.now().date() - timedelta(days=7),
                                 key="start_date")
    with col2:
        end_date = st.date_input("Data final", 
                                value=timezone.now().date(),
                                key="end_date")
    
    # Display refresh info in col3
    with col3:
        time_remaining = 120 - (time.time() - st.session_state.last_refresh_timestamp)
        if time_remaining > 0:
            st.caption(f"🔄 Próxima atualização em: {int(time_remaining)}s (Última: {st.session_state.last_refresh_time})")
        else:
            st.caption(f"⏳ Atualizando agora... (Última: {st.session_state.last_refresh_time})")

    modulos = Modulo.objects.filter(formador=user)
    
    # Check if teacher has any modules assigned
    if not modulos.exists():
        st.warning("Não tem nenhum módulo atribuído a si.")
        st.info("Por favor, contacte a administração para lhe atribuírem módulos.")
        return
    
    # Create tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Visão Geral", "📝 Registos", "📈 Estatísticas", "⚙️ Configurações"])
    
    with tab1:
        st.subheader("Resumo dos Módulos")
        
        # Summary cards for each module
        for modulo in modulos:
            with st.expander(f"📌 {modulo.nome}", expanded=True):
                col1, col2, col3, col4 = st.columns(4)
                
                # Calculate metrics
                aulas = Aula.objects.filter(modulo=modulo)
                total_aulas = aulas.count()
                
                registos = RegistoPresenca.objects.filter(aula__in=aulas)
                total_registos = registos.count()
                
                presencas = registos.filter(entrada__isnull=False).count()
                faltas = registos.filter(entrada__isnull=True).count()
                atrasos = registos.exclude(motivo_atraso__exact='').count()
                
                # Display metrics
                with col1:
                    st.metric("Total de Aulas", total_aulas)
                with col2:
                    st.metric("Presenças", presencas)
                with col3:
                    st.metric("Faltas", faltas)
                with col4:
                    st.metric("Atrasos", atrasos)
                
                # Mini chart
                if total_registos > 0:
                    chart_data = pd.DataFrame({
                        "Tipo": ["Presenças", "Faltas", "Atrasos"],
                        "Quantidade": [presencas, faltas, atrasos]
                    })
                    st.bar_chart(chart_data, x="Tipo", y="Quantidade", use_container_width=True)
                else:
                    st.info("Ainda não há registos de presenças para este módulo")

    with tab2:
        st.subheader("Gestão de Presenças")
        
        # Module selector
        modulo_selecionado = st.selectbox(
            "Selecione o módulo",
            options=[m.nome for m in modulos],
            key="modulo_select"
        )
        
        try:
            modulo = Modulo.objects.get(nome=modulo_selecionado, formador=user)
            aulas = Aula.objects.filter(
                modulo=modulo,
                data__range=[start_date, end_date]
            ).order_by("-data")
            
            if not aulas.exists():
                st.info("Não há aulas agendadas para este período")
            
            # Code Generation Section for Today's Classes
            st.subheader("🎯 Gerador de Código para Presença")
            aulas_hoje = aulas.filter(data=timezone.now().date())
            
            if aulas_hoje.exists():
                aula_selecionada = st.selectbox(
                    "Selecione a aula para gerar código",
                    options=[(a.id, f"{a.periodo} - {a.modulo.nome}") for a in aulas_hoje],
                    format_func=lambda x: x[1],
                    key="aula_code_select"
                )
                
                if aula_selecionada:
                    aula_id = aula_selecionada[0]
                    
                    # Generate or get existing code
                    if 'current_code' not in st.session_state or 'code_timestamp' not in st.session_state:
                        code, timestamp = generate_attendance_code(aula_id)
                        st.session_state.current_code = code
                        st.session_state.code_timestamp = timestamp
                        st.session_state.code_start_time = time.time()
                    
                    # Display code with timer
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown(f"""
                        <div style='text-align: center; padding: 20px; background-color: #f0f2f6; border-radius: 10px;'>
                            <h2 style='margin: 0;'>{st.session_state.current_code}</h2>
                        </div>
                        """, unsafe_allow_html=True)
                    with col2:
                        st.info("""
                        **Instruções:**
                        1. Mostre este código aos formandos
                        2. O código expira em 30 minutos
                        3. Os formandos devem inserir este código
                        4. Gere um novo quando necessário
                        """)
                    
                    # Timer display
                    time_elapsed = time.time() - st.session_state.code_start_time
                    time_remaining = max(0, (CODE_VALIDITY_MINUTES * 60) - time_elapsed)
                    
                    st.progress(time_remaining / (CODE_VALIDITY_MINUTES * 60))
                    st.caption(f"Tempo restante: {int(time_remaining / 60)} minutos e {int(time_remaining % 60)} segundos")
                    
                    # Generate new code button
                    if st.button("🔄 Gerar Novo Código", key="new_code_btn"):
                        code, timestamp = generate_attendance_code(aula_id)
                        st.session_state.current_code = code
                        st.session_state.code_timestamp = timestamp
                        st.session_state.code_start_time = time.time()
                        st.rerun()
            else:
                st.info("Não há aulas agendadas para hoje")
            
            # Attendance editor for each class
            st.subheader("📝 Registos de Presença")
            for aula in aulas:
                with st.expander(f"📅 {aula.data.strftime('%d/%m/%Y')} - {aula.periodo}", expanded=False):
                    presencas = RegistoPresenca.objects.filter(aula=aula)
                    
                    if not presencas.exists():
                        st.info("Nenhum formando registado nesta aula")
                        continue
                    
                    # Create editable dataframe
                    df = pd.DataFrame([{
                        "ID": p.id,
                        "Formando": p.formando.username,
                        "Status": "Presente" if p.entrada else "Falta",
                        "Hora": p.entrada.time() if p.entrada else "-",
                        "Justificação": p.motivo_atraso if p.motivo_atraso else ""
                    } for p in presencas])
                    
                    # Data editor with custom styling
                    edited_df = st.data_editor(
                        df,
                        column_config={
                            "ID": None,
                            "Status": st.column_config.SelectboxColumn(
                                "Status",
                                options=["Presente", "Falta", "Atrasado"],
                                required=True
                            ),
                            "Justificação": st.column_config.TextColumn(
                                "Justificação (se aplicável)"
                            )
                        },
                        key=f"attendance_editor_{aula.id}",
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # Save button
                    if st.button("Salvar Alterações", key=f"save_{aula.id}"):
                        for _, row in edited_df.iterrows():
                            registro = RegistoPresenca.objects.get(id=row['ID'])
                            
                            # Update status
                            if row['Status'] == "Presente":
                                registro.entrada = aula.data
                                registro.motivo_atraso = ""
                            elif row['Status'] == "Falta":
                                registro.entrada = None
                                registro.motivo_atraso = ""
                            elif row['Status'] == "Atrasado":
                                registro.entrada = aula.data
                                registro.motivo_atraso = row['Justificação']
                            
                            registro.save()
                        
                        st.success("Alterações salvas com sucesso!")
                        time.sleep(1)
                        st.rerun()
        
        except Modulo.DoesNotExist:
            st.error("Módulo não encontrado ou não está atribuído a si")
            st.stop()

    with tab3:
        st.subheader("Análise Estatística")
        
        # Module selector for statistics
        modulo_stats = st.selectbox(
            "Selecione o módulo para análise",
            options=[m.nome for m in modulos],
            key="modulo_stats"
        )
        
        try:
            modulo = Modulo.objects.get(nome=modulo_stats, formador=user)
            aulas = Aula.objects.filter(modulo=modulo).order_by('data')
            
            if not aulas.exists():
                st.info("Não há aulas registadas para este módulo")
            else:
                # Time series data - ensure consistent column names
                time_data = []
                for aula in aulas:
                    presencas = RegistoPresenca.objects.filter(aula=aula, entrada__isnull=False).count()
                    total = RegistoPresenca.objects.filter(aula=aula).count()
                    
                    time_data.append({
                        "date": aula.data,
                        "presencas": presencas,
                        "taxa_presenca": (presencas/total)*100 if total > 0 else 0,
                        "aula_info": f"{aula.data.strftime('%d/%m')} {aula.periodo}"
                    })
                
                df_time = pd.DataFrame(time_data)
                
                # Ensure we have data to display
                if not df_time.empty:
                    # Charts
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Evolução de Presenças**")
                        st.line_chart(
                            df_time,
                            x="date",
                            y="taxa_presenca"
                        )
                    
                    with col2:
                        st.markdown("**Distribuição de Presenças**")
                        st.bar_chart(
                            df_time,
                            x="aula_info",
                            y="presencas"
                        )
                    
                    # Export button
                    export_df = df_time.rename(columns={
                        "date": "Data",
                        "presencas": "Presenças",
                        "taxa_presenca": "Taxa de Presença (%)",
                        "aula_info": "Aula"
                    })
                    
                    st.download_button(
                        "Exportar Dados (CSV)",
                        export_df.to_csv(index=False, sep=';').encode('utf-8'),
                        f"estatisticas_{modulo.nome}.csv",
                        "text/csv"
                    )
                else:
                    st.warning("Dados insuficientes para gerar gráficos")
        
        except Modulo.DoesNotExist:
            st.error("Módulo não encontrado ou não está atribuído a si")
            st.stop()

    with tab4:
        st.subheader("Configurações")
        st.markdown("**Configurações de Notificação**")
        email_notif = st.checkbox("Receber notificações por email", value=True)
        push_notif = st.checkbox("Receber notificações no sistema", value=True)
        
        if st.button("Guardar Configurações"):
            st.success("Configurações guardadas com sucesso!")
    
    # Auto-refresh logic
    if time.time() - st.session_state.last_refresh_timestamp > 120:  # 2 minutes
        st.session_state.last_refresh_time = datetime.now().strftime('%H:%M:%S')
        st.session_state.last_refresh_timestamp = time.time()
        st.rerun()

# --------------------------
# Student Interface
# --------------------------
def mostrar_interface_formando(user):
    st.subheader(f"🎓 Bem-vindo, {user.first_name}")
    
    # Get today's classes
    hoje = timezone.now().date()
    aulas_hoje = Aula.objects.filter(data=hoje).order_by('periodo')
    
    if not aulas_hoje.exists():
        st.info("Não há aulas agendadas para hoje")
        return
    
    # Display today's classes with code input for each
    st.subheader("📅 Suas Aulas Hoje")

    for aula in aulas_hoje:
        with st.expander(f"📘 {aula.modulo.nome} - {aula.periodo}", expanded=True):
            # Get current attendance status
            registro = RegistoPresenca.objects.filter(
                formando=user,
                aula=aula
            ).first()
            
            # Display class information first
            st.markdown(f"""
            **Informações da Aula:**
            - 📝 Curso: {aula.modulo.curso.nome}
            - 📚 Módulo: {aula.modulo.nome}
            - 📅 Data: {aula.data.strftime('%d/%m/%Y')}
            - ⏰ Período: {aula.periodo}
            - 👨‍🏫 Formador: {aula.modulo.formador.get_full_name() or aula.modulo.formador.username}
            - ⏱️ Carga Horária: {aula.modulo.carga_horaria} horas
            """)
            
            st.markdown("---")
            
            # Display current status
            if registro and registro.entrada:
                st.success("✅ Presença registada")
                if registro.motivo_atraso:
                    st.info(f"Motivo do atraso: {registro.motivo_atraso}")
                    if registro.justificativo:
                        st.info(f"Documento justificativo: {registro.justificativo.name}")
            else:
                # Code input form for this specific class
                with st.form(key=f"attendance_form_{aula.id}"):
                    st.markdown("**Registrar Presença**")
                    
                    # Code input
                    code = st.text_input(
                        "Digite o código fornecido pelo formador:",
                        max_chars=6,
                        placeholder="Ex: A1B2C3",
                        key=f"code_input_{aula.id}"
                    ).upper()
                    
                    # Attendance status
                    status = st.radio(
                        "Status da Presença:",
                        ["Presente", "Atrasado"],
                        key=f"status_{aula.id}"
                    )
                    
                    # Justification fields (only shown if status is "Atrasado")
                    motivo_atraso = ""
                    justificativo = None
                    
                    if status == "Atrasado":
                        motivo_atraso = st.text_area(
                            "Motivo do atraso:",
                            placeholder="Descreva o motivo do seu atraso...",
                            key=f"motivo_{aula.id}"
                        )
                        
                        justificativo = st.file_uploader(
                            "Documento justificativo (PDF ou PNG):",
                            type=['pdf', 'png'],
                            key=f"file_{aula.id}"
                        )
                    
                    if st.form_submit_button("Confirmar Presença"):
                        if code:
                            if is_code_valid(code):
                                aula_id = get_aula_id_from_code(code)
                                if aula_id == aula.id:
                                    try:
                                        # Handle file upload if present
                                        justificativo_path = None
                                        if justificativo is not None:
                                            # Create directory if it doesn't exist
                                            upload_dir = f'justificativos/{user.username}/{aula.id}'
                                            os.makedirs(upload_dir, exist_ok=True)
                                            
                                            # Save file
                                            file_path = os.path.join(upload_dir, justificativo.name)
                                            with open(file_path, 'wb') as f:
                                                f.write(justificativo.getvalue())
                                            justificativo_path = file_path
                                        
                                        # Register attendance
                                        registro = RegistoPresenca.objects.create(
                                            formando=user,
                                            aula=aula,
                                            entrada=timezone.now(),
                                            saida=timezone.now() + timedelta(hours=3),
                                            motivo_atraso=motivo_atraso if status == "Atrasado" else "",
                                            justificativo=justificativo_path if justificativo_path else None
                                        )
                                        
                                        # Invalidate the used code
                                        invalidate_code(code)
                                        
                                        st.success("✅ Presença registada com sucesso!")
                                        st.rerun()  # Refresh to show updated status
                                    except Exception as e:
                                        st.error(f"Erro ao registrar presença: {str(e)}")
                                else:
                                    st.error("❌ Código inválido para esta aula")
                            else:
                                st.error("❌ Código inválido ou expirado")
                        else:
                            st.warning("Por favor, insira o código de presença")

# --------------------------
# Display Attendance Status
# --------------------------
def display_attendance_status(registro):
    """Show current attendance status"""
    if registro.entrada:
        status_msg = "✅ Presença registada"
        if registro.motivo_atraso:
            status_msg += f" | Atraso: {registro.motivo_atraso}"
        st.success(status_msg)
    else:
        st.error("❌ Falta registada")

# --------------------------
# Main App Logic
# --------------------------
def main():
    st.title("Gestão de Presenças - CESAE Braga")
    
    # Session and login
    user = st.session_state.get("user", None)
    
    if not user:
        login_user()
    else:
        st.success(f"Bem-vindo, {user.first_name} ({user.tipo})")
        
        # Right-aligned logout button using columns
        col1, col2, col3 = st.columns([6, 1, 1])
        with col3:
            if st.button("Sair", icon="🔴", key="logout_btn"):
                st.session_state.clear()
                st.rerun()
        
        # Role-based interface
        if user.tipo == "Formador":
            mostrar_interface_formador(user)
        elif user.tipo == "Formando":
            mostrar_interface_formando(user)

if __name__ == "__main__":
    main()