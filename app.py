import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURACIÓN CORPORATIVA ---
st.set_page_config(page_title="Gestión de Recursos SCT", layout="wide")

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
    
    # --- FILTROS GERENCIALES (ACTUALIZADOS) ---
    st.sidebar.header("Filtros de Análisis")
    
    # Filtro de Mes
    meses = df['Mes'].dropna().unique()
    mes_sel = st.sidebar.selectbox("Mes", meses)
    
    # Filtro Único de Proyecto (Con opción 'Todos')
    proyectos = df['Proyecto'].dropna().unique()
    opciones_proy = ["Todos los Proyectos"] + list(proyectos)
    proy_sel = st.sidebar.selectbox("Filtrar por Proyecto", opciones_proy)
    
    # Aplicar Filtros a la Base de Datos
    df_filtrado = df[df['Mes'] == mes_sel]
    if proy_sel != "Todos los Proyectos":
        df_filtrado = df_filtrado[df_filtrado['Proyecto'] == proy_sel]
    
    # --- PROCESAMIENTO ---
    resumen = df_filtrado.groupby('Nombre consultor')['Dias'].sum().reset_index()
    resumen['Color'] = resumen['Dias'].apply(lambda x: COLOR_RED if x < LIMITE_POLITICA else COLOR_CYAN)

    # --- MÉTRICAS DE ALTO NIVEL ---
    total_dias_mes = resumen['Dias'].sum()
    # Calculamos la capacidad basada en los consultores que aparecen en el filtro
    personas_activas = len(resumen)
    capacidad_total_equipo = personas_activas * LIMITE_POLITICA
    
    # Evitamos negativos si hay sobrecarga global
    capacidad_ociosa = capacidad_total_equipo - total_dias_mes
    if capacidad_ociosa < 0:
        capacidad_ociosa = 0 
        
    utilizacion_global = (total_dias_mes / capacidad_total_equipo) * 100 if capacidad_total_equipo > 0 else 0
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Utilización", f"{utilizacion_global:.1f}%")
    m2.metric("Días Asignados", f"{total_dias_mes:.1f}")
    m3.metric("Capacidad Ociosa", f"{capacidad_ociosa:.1f} días")
    m4.metric("Personal < 18 días", len(resumen[resumen['Dias'] < LIMITE_POLITICA]))

    st.divider()

    # --- VISUALIZACIONES ---
    # Ajustamos un poco las proporciones de las columnas (70% izquierda, 30% derecha)
    col_izq, col_der = st.columns([7, 3])

    with col_izq:
        st.subheader(f"Ocupación por Consultor: {proy_sel}")
        fig_bar = px.bar(
            resumen, x='Nombre consultor', y='Dias',
            color='Color', color_discrete_map="identity",
            text_auto='.1f'
        )
        fig_bar.add_hline(y=LIMITE_POLITICA, line_dash="dash", line_color=COLOR_RED, annotation_text="Límite 18d")
        fig_bar.update_layout(xaxis_title="", yaxis_title="Días")
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_der:
        st.subheader("Capacidad Total")
        # Gráfico de Dona
        fig_pie = go.Figure(data=[go.Pie(
            labels=['Ocupado', 'Disponible'],
            values=[total_dias_mes, capacidad_ociosa],
            hole=.4,
            marker_colors=[COLOR_CYAN, "#E5E7E9"],
            textinfo='percent'
        )])
        
        # EL SECRETO PARA QUE SE VEA GRANDE: Quitar márgenes y bajar la leyenda
        fig_pie.update_layout(
            margin=dict(t=10, b=10, l=10, r=10), # Quita el espacio en blanco alrededor
            legend=dict(
                orientation="h",       # Leyenda horizontal
                yanchor="top",         
                y=-0.1,                # La pone debajo del gráfico
                xanchor="center", 
                x=0.5
            )
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- TABLA FINAL ---
    st.subheader("Detalle Nominal")
    st.dataframe(
        resumen[['Nombre consultor', 'Dias']].sort_values(by='Dias'),
        use_container_width=True,
        hide_index=True
    )

except Exception as e:
    st.error(f"Error cargando los datos. Revisa la conexión. Detalle: {e}")
