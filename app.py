import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURACIÓN SCT ---
st.set_page_config(page_title="Gestión de Recursos SCT", page_icon="📊", layout="wide")

COLOR_CYAN = "#008B8B"
COLOR_RED = "#E74C3C"
LIMITE_POLITICA = 18.0

st.title("📊 Dashboard Gerencial: Ocupación y Desocupación")

conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=300)
def cargar_datos():
    url = "https://docs.google.com/spreadsheets/d/1IQhd4LR8CjEd3PIYb7WUCW364vaKS4QVpCtLNQOpFB8/edit#gid=280416127"
    return conn.read(spreadsheet=url, worksheet="BD HH")

try:
    df = cargar_datos()
    df['Dias'] = df['Dias'].astype(str).str.replace(',', '.').astype(float)
    
    # --- FILTROS ---
    st.sidebar.header("Filtros de Análisis")
    meses_ordenados = df['Mes'].dropna().unique() # Asumimos que vienen ordenados en la base
    mes_sel = st.sidebar.selectbox("Analizar Mes Específico", meses_ordenados)
    
    # --- BLOQUE 1: ANÁLISIS DEL MES SELECCIONADO ---
    df_mes = df[df['Mes'] == mes_sel]
    resumen_mes = df_mes.groupby('Nombre consultor')['Dias'].sum().reset_index()
    
    total_dias_mes = resumen_mes['Dias'].sum()
    capacidad_mes = len(resumen_mes) * LIMITE_POLITICA
    total_desocupacion = max(0, capacidad_mes - total_dias_mes)
    
    st.header(f"Detalle Mensual: {mes_sel}")
    m1, m2, m3 = st.columns(3)
    m1.metric("Ocupación Global", f"{(total_dias_mes/capacidad_mes*100):.1f}%")
    m2.metric("Días Ocupados", f"{total_dias_mes:.1f}")
    m3.metric("Desocupación (Días Libres)", f"{total_desocupacion:.1f}")

    col_bar, col_pie = st.columns([7, 3])
    with col_bar:
        fig_bar = px.bar(resumen_mes, x='Nombre consultor', y='Dias', 
                         color_discrete_sequence=[COLOR_CYAN], text_auto='.1f')
        fig_bar.add_hline(y=LIMITE_POLITICA, line_dash="dash", line_color=COLOR_RED)
        st.plotly_chart(fig_bar, use_container_width=True)
    
    with col_pie:
        fig_pie = go.Figure(data=[go.Pie(labels=['Ocupado', 'Desocupado'], 
                                         values=[total_dias_mes, total_desocupacion], 
                                         hole=.4, marker_colors=[COLOR_CYAN, "#E5E7E9"])])
        fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0), legend=dict(orientation="h", y=-0.1))
        st.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    # --- BLOQUE 2: CUADRO RESUMEN Y RATIOS (LO QUE PIDIÓ AL FINAL) ---
    st.header("📈 Resumen Consolidado y Tendencias")
    
    # Matriz Consultor vs Mes
    matriz = df.pivot_table(index='Nombre consultor', columns='Mes', values='Dias', aggfunc='sum', fill_value=0)
    # Reordenar columnas según los meses encontrados
    matriz = matriz[meses_ordenados]
    
    st.subheader("Matriz de Ocupación por Consultor (Días)")
    # Aplicar un estilo para resaltar en rojo los que no llegan a 18
    def resaltar_bajos(val):
        color = COLOR_RED if val < LIMITE_POLITICA and val > 0 else 'black'
        return f'color: {color}'
    
    st.dataframe(matriz.style.applymap(resaltar_bajos), use_container_width=True)

    # Gráfico de Ratios de Ocupación y Desocupación por Mes
    st.subheader("Evolución de Ratios: Ocupación vs Desocupación")
    
    # Calculamos totales mensuales para el gráfico
    tendencia = df.groupby('Mes')['Dias'].sum().reindex(meses_ordenados).reset_index()
    # Para la capacidad, contamos cuántos consultores únicos hubo cada mes
    consultores_mes = df.groupby('Mes')['Nombre consultor'].nunique().reindex(meses_ordenados)
    tendencia['Capacidad'] = consultores_mes.values * LIMITE_POLITICA
    tendencia['Desocupacion'] = (tendencia['Capacidad'] - tendencia['Dias']).clip(lower=0)
    
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Bar(name='Ocupación', x=tendencia['Mes'], y=tendencia['Dias'], marker_color=COLOR_CYAN))
    fig_trend.add_trace(go.Bar(name='Desocupación', x=tendencia['Mes'], y=tendencia['Desocupacion'], marker_color="#E5E7E9"))
    
    fig_trend.update_layout(barmode='stack', xaxis_title="Mes", yaxis_title="Días Totales Equipo")
    st.plotly_chart(fig_trend, use_container_width=True)

except Exception as e:
    st.error(f"Error al generar el consolidado: {e}")
