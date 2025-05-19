import os
import sys
import django
import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from django.utils import timezone
from django.db.models import Count, Q
import numpy as np

# Configure Django
sys.path.append(os.path.abspath(".."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Projecto_Final.settings")
django.setup()

from Gestao.models import Modulo, Aula, RegistoPresenca, CodigoPresenca, Utilizador
from auth.login import login_user

# LOGO
st.logo(
    "./images/cesae-digital-logo.svg",
    link="http://localhost:8502/",
    icon_image="",
)

# Page config
st.set_page_config(
    page_title="Monitor de Códigos - CESAE",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

def generate_time_series_data(codes):
    """Generate time series data for visualization"""
    df = pd.DataFrame(codes.values('timestamp', 'valido'))
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['date'] = df['timestamp'].dt.date
    df['hour'] = df['timestamp'].dt.hour
    
    # Group by date and count codes
    daily_counts = df.groupby('date').size().reset_index(name='count')
    daily_counts['date'] = pd.to_datetime(daily_counts['date'])
    
    # Group by hour and count codes
    hourly_counts = df.groupby('hour').size().reset_index(name='count')
    
    return daily_counts, hourly_counts

def show_anomaly_detection(df):
    """Detect and display potential anomalies in code usage"""
    anomalies = []
    
    # Check for multiple uses of the same code
    code_uses = df[df['Status'] == 'Usado'].groupby('Código').size()
    multiple_uses = code_uses[code_uses > 1]
    if not multiple_uses.empty:
        anomalies.append({
            'type': 'Códigos Múltiplos',
            'description': f'Encontrados {len(multiple_uses)} códigos usados mais de uma vez',
            'severity': 'Alta'
        })
    
    # Check for very quick code generation (potential abuse)
    if 'Hora' in df.columns:
        df['timestamp'] = pd.to_datetime(df['Data'] + ' ' + df['Hora'])
        df['time_diff'] = df.groupby('Formador')['timestamp'].diff()
        quick_generation = df[df['time_diff'] < pd.Timedelta(seconds=30)]
        if not quick_generation.empty:
            anomalies.append({
                'type': 'Geração Rápida',
                'description': f'Encontrados {len(quick_generation)} códigos gerados em menos de 30 segundos',
                'severity': 'Média'
            })
    
    return anomalies

def mostrar_interface_admin(user):
    st.title("🔍 Monitor de Códigos de Presença")
    
    # Security check - only allow teachers
    if user.tipo != "Formador":
        st.error("Acesso não autorizado. Apenas formadores podem acessar esta página.")
        return
    
    # Date range selector with more options
    col1, col2, col3 = st.columns(3)
    with col1:
        date_range = st.selectbox(
            "Período",
            ["Últimos 7 dias", "Últimos 30 dias", "Este mês", "Mês anterior", "Personalizado"]
        )
        
        if date_range == "Últimos 7 dias":
            start_date = timezone.now().date() - timedelta(days=7)
            end_date = timezone.now().date()
        elif date_range == "Últimos 30 dias":
            start_date = timezone.now().date() - timedelta(days=30)
            end_date = timezone.now().date()
        elif date_range == "Este mês":
            start_date = timezone.now().date().replace(day=1)
            end_date = timezone.now().date()
        elif date_range == "Mês anterior":
            last_month = timezone.now().date().replace(day=1) - timedelta(days=1)
            start_date = last_month.replace(day=1)
            end_date = last_month
        else:
            with col2:
                start_date = st.date_input("Data inicial", value=timezone.now().date() - timedelta(days=7))
            with col3:
                end_date = st.date_input("Data final", value=timezone.now().date())
    
    # Advanced filter options
    st.subheader("🔍 Filtros Avançados")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        formador = st.selectbox(
            "Formador",
            options=["Todos"] + list(Utilizador.objects.filter(tipo="Formador").values_list("username", flat=True))
        )
    with col2:
        modulo = st.selectbox(
            "Módulo",
            options=["Todos"] + list(Modulo.objects.values_list("nome", flat=True))
        )
    with col3:
        status = st.selectbox(
            "Status do Código",
            options=["Todos", "Válido", "Usado", "Expirado"]
        )
    with col4:
        periodo = st.selectbox(
            "Período da Aula",
            options=["Todos", "Manhã", "Tarde"]
        )
    
    # Query codes with advanced filtering
    codes = CodigoPresenca.objects.filter(
        timestamp__date__range=[start_date, end_date]
    ).select_related('aula', 'aula__modulo', 'aula__modulo__formador')
    
    if formador != "Todos":
        codes = codes.filter(aula__modulo__formador__username=formador)
    if modulo != "Todos":
        codes = codes.filter(aula__modulo__nome=modulo)
    if periodo != "Todos":
        codes = codes.filter(aula__periodo=periodo.lower())
    
    # Create DataFrame for display
    data = []
    for code in codes:
        # Get attendance record if code was used
        registro = RegistoPresenca.objects.filter(
            aula=code.aula,
            entrada__gte=code.timestamp
        ).first()
        
        # Determine code status
        if not code.valido:
            code_status = "Usado"
        elif not code.is_valid():
            code_status = "Expirado"
        else:
            code_status = "Válido"
        
        if status != "Todos" and code_status != status:
            continue
            
        data.append({
            "Código": code.codigo,
            "Data": code.timestamp.strftime("%d/%m/%Y"),
            "Hora": code.timestamp.strftime("%H:%M:%S"),
            "Módulo": code.aula.modulo.nome,
            "Formador": code.aula.modulo.formador.get_full_name() or code.aula.modulo.formador.username,
            "Aula": f"{code.aula.data.strftime('%d/%m/%Y')} - {code.aula.periodo}",
            "Status": code_status,
            "Usado por": registro.formando.get_full_name() if registro else "-",
            "Hora de uso": registro.entrada.strftime("%H:%M:%S") if registro else "-",
            "Motivo atraso": registro.motivo_atraso if registro and registro.motivo_atraso else "-",
            "Justificativo": registro.justificativo.name if registro and registro.justificativo else "-"
        })
    
    if data:
        df = pd.DataFrame(data)
        
        # Display statistics
        st.subheader("📊 Estatísticas")
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total de Códigos", len(df))
        with col2:
            st.metric("Códigos Válidos", len(df[df["Status"] == "Válido"]))
        with col3:
            st.metric("Códigos Usados", len(df[df["Status"] == "Usado"]))
        with col4:
            st.metric("Códigos Expirados", len(df[df["Status"] == "Expirado"]))
        with col5:
            st.metric("Taxa de Uso", f"{(len(df[df['Status'] == 'Usado']) / len(df) * 100):.1f}%")
        
        # Visualizations
        st.subheader("📈 Visualizações")
        tab1, tab2, tab3 = st.tabs(["Distribuição Temporal", "Análise por Formador", "Detecção de Anomalias"])
        
        with tab1:
            # Time series visualization
            daily_counts, hourly_counts = generate_time_series_data(codes)
            
            col1, col2 = st.columns(2)
            with col1:
                fig_daily = px.line(daily_counts, x='date', y='count',
                                  title='Códigos Gerados por Dia')
                st.plotly_chart(fig_daily, use_container_width=True)
            
            with col2:
                fig_hourly = px.bar(hourly_counts, x='hour', y='count',
                                  title='Códigos Gerados por Hora')
                st.plotly_chart(fig_hourly, use_container_width=True)
        
        with tab2:
            # Formador analysis
            formador_stats = df.groupby('Formador').agg({
                'Código': 'count',
                'Status': lambda x: (x == 'Usado').sum()
            }).reset_index()
            formador_stats.columns = ['Formador', 'Total Códigos', 'Códigos Usados']
            formador_stats['Taxa de Uso'] = (formador_stats['Códigos Usados'] / formador_stats['Total Códigos'] * 100).round(1)
            
            fig_formador = px.bar(formador_stats, x='Formador', y=['Total Códigos', 'Códigos Usados'],
                                title='Análise por Formador', barmode='group')
            st.plotly_chart(fig_formador, use_container_width=True)
        
        with tab3:
            # Anomaly detection
            anomalies = show_anomaly_detection(df)
            if anomalies:
                st.warning("⚠️ Anomalias Detectadas")
                for anomaly in anomalies:
                    st.error(f"**{anomaly['type']}** ({anomaly['severity']}): {anomaly['description']}")
            else:
                st.success("✅ Nenhuma anomalia detectada")
        
        # Display detailed table with sorting and filtering
        st.subheader("📝 Detalhes dos Códigos")
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Código": st.column_config.TextColumn("Código", width="medium"),
                "Data": st.column_config.TextColumn("Data", width="small"),
                "Hora": st.column_config.TextColumn("Hora", width="small"),
                "Módulo": st.column_config.TextColumn("Módulo", width="large"),
                "Formador": st.column_config.TextColumn("Formador", width="medium"),
                "Aula": st.column_config.TextColumn("Aula", width="medium"),
                "Status": st.column_config.TextColumn("Status", width="small"),
                "Usado por": st.column_config.TextColumn("Usado por", width="medium"),
                "Hora de uso": st.column_config.TextColumn("Hora de uso", width="small"),
                "Motivo atraso": st.column_config.TextColumn("Motivo atraso", width="large"),
                "Justificativo": st.column_config.TextColumn("Justificativo", width="medium")
            }
        )
    else:
        st.info("Nenhum código encontrado para os filtros selecionados.")

def main():
    # Session and login
    user = st.session_state.get("user", None)
    
    if not user:
        login_user()
    else:
        mostrar_interface_admin(user)

if __name__ == "__main__":
    main()