import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURACIÓN CORPORATIVA SCT ---
st.set_page_config(page_title="Gestión de Recursos SCT", page_icon="📊", layout="wide")

COLOR_CYAN = "#008B8B"
COLOR_RED = "#E74C3C"
LIMITE_POLITICA = 18.0

st.title("📊 Dashboard Gerencial: Ocupación y Desocupación")

# --- CONEXIÓN EN VIVO ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=300)
def cargar_datos():
    url = "https://docs.google.com/spreadsheets/d/1IQhd4LR8CjEd3PIYb7WUCW364vaKS4QVpCtLNQOpFB8/edit#gid=280416127"
    return conn.read(spreadsheet=url, worksheet="BD HH")

try:
    df = cargar_datos()
    # Limpieza de decimales
    df['Dias'] = df['Dias'].astype(str).str.replace(',', '.').astype(float)
    
    # --- FILTROS DE PANEL ---
    st.sidebar.header("Filtros de Análisis")
    
    # 1. Filtro de Mes
    meses = df['Mes'].dropna().unique()
    mes_sel = st.sidebar.selectbox("Mes", meses)
    
    # 2. Filtro Único de Proyecto
    proyectos = df['Proyecto'].dropna().unique()
    opciones_proy = ["Todos los Proyectos"] + list(proyectos)
    proy_sel = st.sidebar.selectbox("Filtrar por Proyecto", opciones_proy)
    
    # Lógica de filtrado
    df_filtrado = df[df['Mes'] == mes_sel]
    if proy_sel != "Todos los Proyectos":
        df_filtrado = df_filtrado[df_filtrado['Proyecto'] == proy_sel]
    
    # --- PROCESAMIENTO DE DATOS ---
    resumen = df_filtrado.groupby('Nombre consultor')['Dias'].sum().reset_index()
    resumen['Color'] = resumen['Dias'].apply(lambda x: COLOR_RED if x < LIMITE_POLITICA else COLOR_CYAN)

    # --- CÁLCULO DE RATIOS ---
    total_dias_ocupados = resumen['Dias'].sum()
    capacidad_teorica = len(resumen) * LIMITE_POLITICA
    
    # Desocupación (Días libres)
    total_desocupacion = capacidad_teorica - total_dias_ocupados
    if total_desocupacion < 0: total_desocupacion = 0 # En caso de sobrecarga masiva
        
    ocupacion_porcentaje = (total_dias_ocupados / capacidad_teorica) * 100 if capacidad_teorica > 0 else 0
    
    # --- MÉTRICAS SUPERIORES ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Ocupación Global", f"{ocupacion_porcentaje:.1f}%")
    m2.metric("Días Ocupados", f"{total_dias_ocupados:.1f}")
    m3.metric("Desocupación (Días)", f"{total_desocupacion:.1f}")
    m4.metric("Consultores < 18d", len(resumen[resumen['Dias'] < LIMITE_POLITICA]))

    st.divider()

    # --- GRÁFICOS ---
    col_barras, col_dona = st.columns([7, 3])

    with col_barras:
        st.subheader(f"Ocupación Nominal: {proy_sel}")
        fig_bar = px.bar(
            resumen, x='Nombre consultor', y='Dias',
            color='Color', color_discrete_map="identity",
            text_auto='.1f'
        )
        fig_bar.add_hline(y=LIMITE_POLITICA, line_dash="dash", line_color=COLOR_RED, annotation_text="Meta 18d")
        fig_bar.update_layout(xaxis_title="", yaxis_title="Días")
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_dona:
        st.subheader("Estado de Capacidad")
        # Gráfico de Dona Maximizada
        fig_pie = go.Figure(data=[go.Pie(
            labels=['Ocupado', 'Desocupado'],
            values=[total_dias_ocupados, total_desocupacion],
            hole=.4,
            marker_colors=[COLOR_CYAN, "#E5E7E9"],
            textinfo='percent'
        )])
        
        fig_pie.update_layout(
            margin=dict(t=20, b=20, l=10, r=10),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- TABLA DE DETALLE ---
    st.subheader("Listado de Consultores")
    resumen['Días Desocupados'] = resumen['Dias'].apply(lambda x: max(0, LIMITE_POLITICA - x))
    st.dataframe(
        resumen[['Nombre consultor', 'Dias', 'Días Desocupados']].sort_values(by='Dias'),
        use_container_width=True,
        hide_index=True
    )

except Exception as e:
    st.error(f"Error al cargar la información: {e}")
