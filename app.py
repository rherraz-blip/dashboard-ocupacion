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
    
    # LIMPIEZA: Quitar espacios y estandarizar números
    df['Mes'] = df['Mes'].astype(str).str.strip() # Quita espacios al inicio/final
    df['Dias'] = df['Dias'].astype(str).str.replace(',', '.').str.strip().astype(float)
    return df

try:
    df = cargar_datos()
    
    # 1. DEFINIR ORDEN CRONOLÓGICO MAESTRO
    meses_reales = df['Mes'].unique()
    # Ordenamos usando fechas reales para que 06 y 07 vayan donde corresponden
    orden_meses = sorted(meses_reales, key=lambda x: pd.to_datetime(x, format='%m/%Y'))
    
    # Aplicamos el orden al DataFrame principal
    df['Mes'] = pd.Categorical(df['Mes'], categories=orden_meses, ordered=True)
    
    # --- FILTROS LATERALES ---
    st.sidebar.header("🔍 Filtros Globales")
    mes_sel = st.sidebar.selectbox("Seleccionar Mes de Análisis", orden_meses)
    
    lista_proyectos = ["Todos los Proyectos"] + sorted(list(df['Proyecto'].dropna().unique()))
    proy_sel = st.sidebar.selectbox("Seleccionar Proyecto", lista_proyectos)
    
    # Aplicar Filtros
    df_filtrado = df.copy()
    if proy_sel != "Todos los Proyectos":
        df_filtrado = df[df['Proyecto'] == proy_sel]

    # --- DATOS DEL MES SELECCIONADO ---
    df_mes = df_filtrado[df_filtrado['Mes'] == mes_sel]
    resumen_mes = df_mes.groupby('Nombre consultor')['Dias'].sum().reset_index()
    
    total_dias = resumen_mes['Dias'].sum()
    total_personas = len(resumen_mes)
    capacidad_teorica = total_personas * LIMITE_POLITICA
    porcentaje_ocupacion = (total_dias / capacidad_teorica * 100) if capacidad_teorica > 0 else 0
    desocupacion_dias = max(0, capacidad_teorica - total_dias)

    # --- BLOQUE 1: KPIs ---
    st.subheader(f"Estado de Gestión: {proy_sel} ({mes_sel})")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Ocupación Proyecto", f"{porcentaje_ocupacion:.1f}%")
    k2.metric("Días Asignados", f"{total_dias:.1f}")
    k3.metric("Desocupación Relativa", f"{desocupacion_dias:.1f} d")
    k4.metric("Personal en el Proyecto", total_personas)

    st.divider()

    # --- BLOQUE 2: GRÁFICOS DEL MES (CON 3 COLORES) ---
    col_izq, col_der = st.columns([7, 3])

    with col_izq:
        st.write(f"**Carga por Consultor en {mes_sel}**")
        def get_color(d):
            if d < LIMITE_POLITICA: return COLOR_RED
            if d > LIMITE_POLITICA: return COLOR_PURPLE
            return COLOR_CYAN
        
        resumen_mes['Color'] = resumen_mes['Dias'].apply(get_color)
        
        fig_bar = px.bar(resumen_mes, x='Nombre consultor', y='Dias', 
                         color='Color', color_discrete_map="identity", text_auto='.1f')
        fig_bar.add_hline(y=LIMITE_POLITICA, line_dash="dash", line_color="gray")
        fig_bar.update_layout(xaxis_title="", yaxis_title="Días")
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_der:
        st.write("**Mix Capacidad vs Carga**")
        fig_pie = go.Figure(data=[go.Pie(
            labels=['Ocupado', 'Desocupado'],
            values=[total_dias, desocupacion_dias],
            hole=.5,
            marker_colors=[COLOR_CYAN, "#F2F3F4"],
            textinfo='percent'
        )])
        fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0), 
                              legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"))
        st.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    # --- BLOQUE 3: PROYECCIÓN A FUTURO (ORDENADA) ---
    st.header(f"🚀 Proyección de Carga: {proy_sel}")
    
    # Agrupamos y forzamos el orden
    proyeccion = df_filtrado.groupby(['Mes', 'Proyecto'], observed=False)['Dias'].sum().reset_index()
    proyeccion = proyeccion.sort_values('Mes') # Ordena según la categoría definida arriba

    # Usamos category_orders para obligar a Plotly a respetar nuestro orden
    fig_proy = px.bar(proyeccion, x='Mes', y='Dias', color='Proyecto',
                      color_discrete_sequence=px.colors.qualitative.Prism,
                      text_auto='.1f',
                      category_orders={"Mes": orden_meses}) # <-- CLAVE DEL ORDEN
    
    fig_proy.update_layout(
        barmode='stack', 
        xaxis_title="Timeline de Proyectos", 
        yaxis_title="Días Totales Comprometidos"
    )
    st.plotly_chart(fig_proy, use_container_width=True)

    st.divider()

    # --- BLOQUE 4: MATRIZ HISTÓRICA ---
    st.header("📈 Historial de Asignaciones")
    matriz = df_filtrado.pivot_table(index='Nombre consultor', columns='Mes', values='Dias', aggfunc='sum', fill_value=0)
    
    # Aseguramos que las columnas de la matriz también sigan el orden cronológico
    meses_columnas = [m for m in orden_meses if m in matriz.columns]
    matriz = matriz[meses_columnas]
    
    def style_matriz(val):
        if val == 0: return 'color: #D5D8DC'
        if val < LIMITE_POLITICA: return f'color: {COLOR_RED}'
        if val > LIMITE_POLITICA: return f'color: {COLOR_PURPLE}'
        return f'color: {COLOR_CYAN}'

    st.dataframe(matriz.style.format("{:.1f}").map(style_matriz), use_container_width=True)

except Exception as e:
    st.error(f"Error al procesar la información: {e}")
