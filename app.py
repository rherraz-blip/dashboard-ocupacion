import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURACIÓN SCT ---
st.set_page_config(page_title="Gestión de Recursos SCT", page_icon="📊", layout="wide")

COLOR_CYAN = "#008B8B"    # Óptimo (18 días)
COLOR_RED = "#E74C3C"     # Alerta Baja (< 18 días)
COLOR_PURPLE = "#6A5ACD"  # Sobrecarga (> 18 días)
LIMITE_POLITICA = 18.0

st.title("📊 Dashboard Gerencial: Control de Ocupación")

conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=300)
def cargar_datos():
    url = "https://docs.google.com/spreadsheets/d/1IQhd4LR8CjEd3PIYb7WUCW364vaKS4QVpCtLNQOpFB8/edit#gid=280416127"
    df = conn.read(spreadsheet=url, worksheet="BD HH")
    # Limpieza de datos (decimales)
    df['Dias'] = df['Dias'].astype(str).str.replace(',', '.').astype(float)
    return df

try:
    df = cargar_datos()
    
    # 1. ORDENAMIENTO CRONOLÓGICO REAL (Adaptado a tu formato 01/2026)
    # Extraemos los meses que realmente existen en tu Excel
    meses_reales = df['Mes'].dropna().unique()
    
    # Los ordenamos cronológicamente interpretándolos como fecha (Mes/Año)
    try:
        orden_meses = sorted(meses_reales, key=lambda x: pd.to_datetime(x, format='%m/%Y'))
    except Exception:
        # Si llega a haber un texto raro en la columna, los ordena alfabéticamente como plan B
        orden_meses = sorted(meses_reales) 
        
    df['Mes'] = pd.Categorical(df['Mes'], categories=orden_meses, ordered=True)
    
    # --- FILTROS ---
    st.sidebar.header("Filtros de Análisis")
    mes_sel = st.sidebar.selectbox("Mes de Análisis", orden_meses)
    
    proyectos = ["Todos"] + list(df['Proyecto'].dropna().unique())
    proy_sel = st.sidebar.selectbox("Proyecto", proyectos)

    # Filtrado
    df_filtrado = df[df['Mes'] == mes_sel]
    if proy_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Proyecto'] == proy_sel]

    # --- PROCESAMIENTO ---
    resumen_mes = df_filtrado.groupby('Nombre consultor')['Dias'].sum().reset_index()
    
    def definir_color(dias):
        if dias < LIMITE_POLITICA: return COLOR_RED
        elif dias > LIMITE_POLITICA: return COLOR_PURPLE
        return COLOR_CYAN

    resumen_mes['Color'] = resumen_mes['Dias'].apply(definir_color)

    # --- BLOQUE MENSUAL ---
    st.header(f"Análisis Mensual: {mes_sel}")
    col1, col2, col3 = st.columns(3)
    col1.metric("Consultores", len(resumen_mes))
    col2.metric("Total Días", f"{resumen_mes['Dias'].sum():.1f}")
    col3.metric("Fuera de Política", len(resumen_mes[resumen_mes['Dias'] != LIMITE_POLITICA]))

    fig_bar = px.bar(resumen_mes, x='Nombre consultor', y='Dias', 
                     color='Color', color_discrete_map="identity", text_auto='.1f')
    fig_bar.add_hline(y=LIMITE_POLITICA, line_dash="dash", line_color="gray")
    fig_bar.update_layout(xaxis_title="", yaxis_title="Días Asignados")
    st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()

    # --- BLOQUE CONSOLIDADO ---
    st.header("📈 Consolidado Histórico")
    
    # Matriz Consultor vs Mes
    matriz = df.pivot_table(index='Nombre consultor', columns='Mes', values='Dias', aggfunc='sum', fill_value=0)
    # Filtramos para que solo muestre las columnas de los meses que realmente existen y en orden
    meses_en_datos = [m for m in orden_meses if m in matriz.columns]
    matriz = matriz[meses_en_datos]
    
    st.subheader("Matriz de Ocupación por Consultor (Días)")
    def color_celda(val):
        if val == 0: return 'color: lightgray'
        if val < LIMITE_POLITICA: return f'color: {COLOR_RED}'
        if val > LIMITE_POLITICA: return f'color: {COLOR_PURPLE}'
        return f'color: {COLOR_CYAN}'

    st.dataframe(matriz.style.format("{:.1f}").map(color_celda), use_container_width=True)

    # Evolución de Ocupación Total
    st.subheader("Tendencia de Ocupación Total por Mes")
    # Aseguramos que el gráfico de barras respete el orden cronológico
    tendencia = df.groupby('Mes', observed=False)['Dias'].sum().reindex(meses_en_datos).reset_index()
    
    fig_tend = px.bar(tendencia, x='Mes', y='Dias', color_discrete_sequence=[COLOR_CYAN], text_auto='.1f')
    fig_tend.update_layout(xaxis_title="Meses", yaxis_title="Días Totales Equipo")
    st.plotly_chart(fig_tend, use_container_width=True)

except Exception as e:
    st.error(f"Error en el dashboard: {e}")
