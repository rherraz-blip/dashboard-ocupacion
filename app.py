import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURACIÓN CORPORATIVA ---
st.set_page_config(page_title="Gestión de Recursos SCT", layout="wide")

# Estilo de colores SCT
COLOR_CYAN = "#008B8B"
COLOR_RED = "#E74C3C"
LIMITE_POLITICA = 18.0

st.title("📊 Dashboard Gerencial: Ocupación y Capacidad")

# --- CONEXIÓN ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=300)
def cargar_datos():
    url = "https://docs.google.com/spreadsheets/d/1IQhd4LR8CjEd3PIYb7WUCW364vaKS4QVpCtLNQOpFB8/edit#gid=280416127"
    return conn.read(spreadsheet=url, worksheet="BD HH")

try:
    df = cargar_datos()
    df['Dias'] = df['Dias'].astype(str).str.replace(',', '.').astype(float)
    
    # --- FILTROS GERENCIALES ---
    st.sidebar.header("Filtros de Análisis")
    
    meses = df['Mes'].dropna().unique()
    mes_sel = st.sidebar.selectbox("Mes", meses)
    
    proyectos = df['Proyecto'].unique()
    proy_sel = st.sidebar.multiselect("Filtrar por Proyectos", proyectos, default=proyectos)
    
    # Aplicar Filtros
    df_filtrado = df[(df['Mes'] == mes_sel) & (df['Proyecto'].isin(proy_sel))]
    
    # --- PROCESAMIENTO ---
    resumen = df_filtrado.groupby('Nombre consultor')['Dias'].sum().reset_index()
    resumen['Desocupacion'] = resumen['Dias'].apply(lambda x: LIMITE_POLITICA - x if x < LIMITE_POLITICA else 0)
    resumen['Color'] = resumen['Dias'].apply(lambda x: COLOR_RED if x < LIMITE_POLITICA else COLOR_CYAN)

    # --- MÉTRICAS DE ALTO NIVEL ---
    total_dias_mes = resumen['Dias'].sum()
    capacidad_total_equipo = len(resumen) * LIMITE_POLITICA
    utilizacion_global = (total_dias_mes / capacidad_total_equipo) * 100 if capacidad_total_equipo > 0 else 0
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Utilización Global", f"{utilizacion_global:.1f}%")
    m2.metric("Días Totales Asignados", f"{total_dias_mes:.1f}")
    m3.metric("Capacidad Ociosa (Días)", f"{(capacidad_total_equipo - total_dias_mes):.1f}")
    m4.metric("Consultores < 18 días", len(resumen[resumen['Dias'] < LIMITE_POLITICA]))

    st.divider()

    # --- VISUALIZACIONES ---
    col_izq, col_der = st.columns([2, 1])

    with col_izq:
        st.subheader("Análisis de Ocupación por Consultor")
        fig_bar = px.bar(
            resumen, x='Nombre consultor', y='Dias',
            color='Color', color_discrete_map="identity",
            text_auto='.1f'
        )
        fig_bar.add_hline(y=LIMITE_POLITICA, line_dash="dash", line_color=COLOR_RED, annotation_text="Límite Político")
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_der:
        st.subheader("Distribución de Capacidad")
        # Gráfico de torta para Desocupación vs Ocupación
        fig_pie = go.Figure(data=[go.Pie(
            labels=['Ocupado', 'Disponible (Capacidad Ociosa)'],
            values=[total_dias_mes, (capacidad_total_equipo - total_dias_mes)],
            hole=.4,
            marker_colors=[COLOR_CYAN, "#E5E7E9"]
        )])
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- DETALLE POR PROYECTO ---
    st.subheader("Concentración de HH por Proyecto")
    proy_data = df_filtrado.groupby('Proyecto')['Dias'].sum().reset_index()
    fig_proy = px.bar(proy_data, x='Dias', y='Proyecto', orientation='h', color_discrete_sequence=[COLOR_CYAN])
    st.plotly_chart(fig_proy, use_container_width=True)

    # --- TABLA FINAL ---
    st.subheader("Detalle Nominal")
    st.dataframe(
        resumen[['Nombre consultor', 'Dias', 'Desocupacion']].sort_values(by='Dias'),
        use_container_width=True,
        hide_index=True
    )

except Exception as e:
    st.error(f"Error en la conexión: {e}")
