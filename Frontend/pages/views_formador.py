import streamlit as st
from Gestao.models import Modulo, Aula, RegistoPresenca
from django.utils import timezone
from datetime import timedelta



def mostrar_interface_formador(user):
    st.subheader("Meus Módulos")
    
    # Add a date range selector
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Data inicial", value=timezone.now().date() - timedelta(days=7))
    with col2:
        end_date = st.date_input("Data final", value=timezone.now().date())
    
    modulos = Modulo.objects.filter(formador=user)
    
    # Create tabs for different views
    tab1, tab2, tab3 = st.tabs(["Visão Geral", "Detalhes por Aula", "Estatísticas"])
    
    with tab1:
        for modulo in modulos:
            with st.expander(f"{modulo.nome} - Resumo"):
                # Summary cards
                col1, col2, col3 = st.columns(3)
                total_aulas = Aula.objects.filter(modulo=modulo).count()
                col1.metric("Total de Aulas", total_aulas)
                
                presencas = RegistoPresenca.objects.filter(aula__modulo=modulo, entrada__isnull=False).count()
                col2.metric("Presenças Registadas", presencas)
                
                faltas = RegistoPresenca.objects.filter(aula__modulo=modulo, entrada__isnull=True).count()
                col3.metric("Faltas", faltas)
                
                # Mini chart
                chart_data = {
                    "Presenças": presencas,
                    "Faltas": faltas
                }
                st.bar_chart(chart_data)
    
    with tab2:
        st.write("Detalhamento por aula")
        for modulo in modulos:
            aulas = Aula.objects.filter(modulo=modulo, data__range=[start_date, end_date]).order_by("data")
            
            for aula in aulas:
                with st.expander(f"{aula.data} ({aula.periodo})"):
                    presencas = RegistoPresenca.objects.filter(aula=aula)
                    
                    # Interactive attendance editor
                    df = pd.DataFrame([{
                        "Nome": p.formando.username,
                        "Status": "Presente" if p.entrada else "Falta",
                        "Hora": p.entrada.time() if p.entrada else "-",
                        "Justificação": p.motivo_atraso if p.motivo_atraso else ""
                    } for p in presencas])
                    
                    edited_df = st.data_editor(
                        df,
                        column_config={
                            "Status": st.column_config.SelectboxColumn(
                                "Status",
                                options=["Presente", "Falta", "Atrasado"],
                                required=True
                            ),
                            "Justificação": st.column_config.TextColumn(
                                "Justificação (se aplicável)"
                            )
                        },
                        key=f"attendance_editor_{aula.id}"
                    )
                    
                    if st.button("Salvar Alterações", key=f"save_{aula.id}"):
                        # Update logic here
                        st.success("Alterações salvas!")
    
    with tab3:
        st.write("Estatísticas avançadas")
        # Add advanced analytics here