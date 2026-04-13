import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURACIÓN CORPORATIVA SCT ---
st.set_page_config(page_title="Gestión de Recursos SCT", page_icon="📊", layout="wide")

COLOR_CYAN = "#008B8B"    # Óptimo (18 días)
COLOR_RED = "#E74C3C"     # Alerta Baja (< 18 días)
COLOR_PURPLE = "#6A5ACD"  # Sobrecarga (> 18 días)
LIMITE_POLITICA = 18.0

st.title("📊 Planificación Estratégica: Ocupación y Proyección")

# --- CONEXIÓN ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=300)
def cargar_datos():
    url = "https://docs.google.com/spreadsheets/d/1IQhd4LR8CjEd3PIYb7WUCW364vaKS4QVpCtLNQOpFB8/edit#gid=280416127"
    df = conn.read(spreadsheet=url, worksheet="BD HH")
    # Limpieza de datos
    df['Dias'] = df['Dias'].astype(str).str.replace(',', '.').str.strip().astype(float)
    return df

try:
    df = cargar_datos()
    
    # 1. ORDENAMIENTO CRONOLÓGICO
    meses_reales = df['Mes'].dropna().unique()
    try:
        orden_meses = sorted(meses_reales, key=lambda x: pd.to_datetime(x, format='%m/%Y'))
    except:
        orden_meses = sorted(meses_reales)
    
    # --- FILTROS LATERALES ---
    st.sidebar.header("🔍 Filtros de Consulta")
    mes_sel = st.sidebar.selectbox("Seleccionar Mes para Análisis Detallado", orden_meses)
    
    # --- PROCESAMIENTO DE DATOS ---
    df_mes = df[df['Mes'] == mes_sel]
    resumen_mes = df_mes.groupby('Nombre consultor')['Dias'].sum().reset_index()
    
    total_dias = resumen_mes['Dias'].sum()
    total_personas = len(resumen_mes)
    capacidad_teorica = total_personas * LIMITE_POLITICA
    porcentaje_ocupacion = (total_dias / capacidad_teorica * 100) if capacidad_teorica > 0 else 0
    desocupacion_dias = max(0, capacidad_teorica - total_dias)

    # --- INDICADORES (KPIs) ---
    st.subheader(f"Estado de Carga - {mes_sel}")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Ocupación Global", f"{porcentaje_ocupacion:.1f}%")
    k2.metric("Días Ocupados", f"{total_dias:.1f}")
    k3.metric("Desocupación", f"{desocupacion_dias:.1f} d")
    k4.metric("Fuera de Meta", len(resumen_mes[resumen_mes['Dias'] != LIMITE_POLITICA]))

    st.divider()

    # --- ANÁLISIS DEL MES ACTUAL ---
    col_izq, col_der = st.columns([7, 3])

    with col_izq:
        st.write(f"**Distribución de Carga por Consultor ({mes_sel})**")
        def get_color(d):
            if d < LIMITE_POLITICA: return COLOR_RED
            if d > LIMITE_POLITICA: return COLOR_PURPLE
            return COLOR_CYAN
        
        resumen_mes['Color'] = resumen_mes['Dias'].apply(get_color)
        
        fig_bar = px.bar(resumen_mes, x='Nombre consultor', y='Dias', 
                         color='Color', color_discrete_map="identity", text_auto='.1f')
        fig_bar.add_hline(y=LIMITE_POLITICA, line_dash="dash", line_color="gray", annotation_text="Meta 18d")
        fig_bar.update_layout(margin=dict(t=20, b=20), xaxis_title="")
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_der:
        st.write("**Análisis de Capacidad**")
        fig_pie = go.Figure(data=[go.Pie(
            labels=['Ocupado', 'Desocupado'],
            values=[total_dias, desocupacion_dias],
            hole=.5,
            marker_colors=[COLOR_CYAN, "#F2F3F4"],
            textinfo='percent'
        )])
        fig_pie.update_layout(
            margin=dict(t=0, b=0, l=0, r=0),
            legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    # --- NUEVA SECCIÓN: PROYECCIÓN A FUTURO POR PROYECTO ---
    st.header("🚀 Proyección de Carga por Proyecto")
    st.info("Este gráfico muestra cómo se distribuyen los días en los próximos meses según los proyectos asignados.")
    
    # Agrupamos por Mes y Proyecto
    proyeccion = df.groupby(['Mes', 'Proyecto'])['Dias'].sum().reset_index()
    # Aseguramos el orden cronológico
    proyeccion['Mes'] = pd.Categorical(proyeccion['Mes'], categories=orden_meses, ordered=True)
    proyeccion = proyeccion.sort_values('Mes')

    fig_proy = px.bar(proyeccion, x='Mes', y='Dias', color='Proyecto',
                      title="Evolución de HH Comprometidas por Proyecto",
                      color_discrete_sequence=px.colors.qualitative.Prism,
                      text_auto='.1f')
    
    fig_proy.update_layout(barmode='stack', xaxis_title="Meses Cronológicos", yaxis_title="Días Totales")
    st.plotly_chart(fig_proy, use_container_width=True)

    st.divider()

    # --- MATRIZ CONSOLIDADA ---
    st.header("📈 Matriz de Seguimiento Histórico")
    matriz = df.pivot_table(index='Nombre consultor', columns='Mes', values='Dias', aggfunc='sum', fill_value=0)
    meses_en_datos = [m for m in orden_meses if m in matriz.columns]
    matriz = matriz[meses_en_datos]
    
    def style_matriz(val):
        if val == 0: return 'color: #D5D8DC'
        if val < LIMITE_POLITICA: return f'color: {COLOR_RED}'
        if val > LIMITE_POLITICA: return f'color: {COLOR_PURPLE}'
        return f'color: {COLOR_CYAN}'

    st.dataframe(matriz.style.format("{:.1f}").map(style_matriz), use_container_width=True)

except Exception as e:
    st.error(f"Hubo un problema al generar el reporte: {e}")
