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
    df['Mes'] = df['Mes'].astype(str).str.strip()
    df['Dias'] = df['Dias'].astype(str).str.replace(',', '.').str.strip().astype(float)
    return df

try:
    df = cargar_datos()
    
    # Orden cronológico
    meses_reales = df['Mes'].unique()
    orden_meses = sorted(meses_reales, key=lambda x: pd.to_datetime(x, format='%m/%Y'))
    df['Mes'] = pd.Categorical(df['Mes'], categories=orden_meses, ordered=True)
    
    # --- FILTROS LATERALES ---
    st.sidebar.header("🔍 Filtros Globales")
    mes_sel = st.sidebar.selectbox("Seleccionar Mes de Análisis", orden_meses)
    
    # Filtro de Proyecto
    lista_proyectos = ["Todos los Proyectos"] + sorted(list(df['Proyecto'].dropna().unique()))
    proy_sel = st.sidebar.selectbox("Seleccionar Proyecto", lista_proyectos)

    # NUEVO: Buscador de Consultor específico
    st.sidebar.divider()
    st.sidebar.write("👤 **Buscador de Consultor**")
    busqueda_nombre = st.sidebar.text_input("Escribir nombre:", placeholder="Ej: ABADIA")
    
    # Aplicar Filtros Globales
    df_filtrado = df.copy()
    if proy_sel != "Todos los Proyectos":
        df_filtrado = df_filtrado[df_filtrado['Proyecto'] == proy_sel]
    if busqueda_nombre:
        df_filtrado = df_filtrado[df_filtrado['Nombre consultor'].str.contains(busqueda_nombre, case=False, na=False)]

    # --- DATOS DEL MES SELECCIONADO ---
    df_mes = df_filtrado[df_filtrado['Mes'] == mes_sel]
    # Para el semáforo necesitamos el TOTAL por consultor
    resumen_total_persona = df_mes.groupby('Nombre consultor')['Dias'].sum().reset_index()
    
    # --- KPIs ---
    total_dias = resumen_total_persona['Dias'].sum()
    capacidad_teorica = len(resumen_total_persona) * LIMITE_POLITICA
    desocupacion = max(0, capacidad_teorica - total_dias)

    st.subheader(f"Estado de Gestión: {proy_sel} ({mes_sel})")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Ocupación Proyecto", f"{(total_dias/capacidad_teorica*100 if capacidad_teorica > 0 else 0):.1f}%")
    k2.metric("Días Asignados", f"{total_dias:.1f}")
    k3.metric("Desocupación", f"{desocupacion:.1f} d")
    k4.metric("Consultores en vista", len(resumen_total_persona))

    st.divider()

    # --- BLOQUE MENSUAL ---
    col_izq, col_der = st.columns([7, 3])

    with col_izq:
        # Pestañas para elegir qué ver
        tab_total, tab_proyectos = st.tabs(["🚦 Ver Semáforo (Totales)", "🎨 Ver por Proyectos (Detalle)"])
        
        with tab_total:
            st.write("**Gráfico de alertas de política (Total días por persona)**")
            def get_color(d):
                if d < LIMITE_POLITICA: return COLOR_RED
                if d > LIMITE_POLITICA: return COLOR_PURPLE
                return COLOR_CYAN
            
            resumen_total_persona['Color'] = resumen_total_persona['Dias'].apply(get_color)
            fig_total = px.bar(resumen_total_persona, x='Nombre consultor', y='Dias', 
                              color='Color', color_discrete_map="identity", text_auto='.1f')
            fig_total.add_hline(y=LIMITE_POLITICA, line_dash="dash", line_color="gray")
            st.plotly_chart(fig_total, use_container_width=True)

        with tab_proyectos:
            st.write("**Desglose: ¿En qué proyectos está cada consultor?**")
            # Este gráfico muestra las barras compuestas por colores de proyectos
            fig_stack = px.bar(df_mes, x='Nombre consultor', y='Dias', color='Proyecto',
                              color_discrete_sequence=px.colors.qualitative.Pastel,
                              text_auto='.1f')
            fig_stack.update_layout(barmode='stack', xaxis_title="")
            st.plotly_chart(fig_stack, use_container_width=True)

    with col_der:
        st.write("**Análisis de Capacidad**")
        fig_pie = go.Figure(data=[go.Pie(
            labels=['Ocupado', 'Desocupado'],
            values=[total_dias, desocupacion],
            hole=.5, marker_colors=[COLOR_CYAN, "#F2F3F4"], textinfo='percent'
        )])
        fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0), 
                              legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"))
        st.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    # --- NUEVO: TABLA DE DETALLE NOMINAL ---
    st.subheader("📋 Detalle de Asignación por Proyecto")
    st.write("Esta tabla muestra la 'sábana' filtrada para auditoría rápida.")
    st.dataframe(
        df_mes[['Nombre consultor', 'Proyecto', 'Cargo', 'Dias']].sort_values(by='Nombre consultor'),
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # --- PROYECCIÓN Y MATRIZ (Igual que antes) ---
    st.header(f"🚀 Proyección de Carga: {proy_sel}")
    proyeccion = df_filtrado.groupby(['Mes', 'Proyecto'], observed=False)['Dias'].sum().reset_index()
    fig_proy = px.bar(proyeccion.sort_values('Mes'), x='Mes', y='Dias', color='Proyecto',
                      color_discrete_sequence=px.colors.qualitative.Prism, text_auto='.1f',
                      category_orders={"Mes": orden_meses})
    st.plotly_chart(fig_proy, use_container_width=True)

    st.header("📈 Historial de Asignaciones")
    matriz = df_filtrado.pivot_table(index='Nombre consultor', columns='Mes', values='Dias', aggfunc='sum', fill_value=0)
    meses_col = [m for m in orden_meses if m in matriz.columns]
    st.dataframe(matriz[meses_col].style.format("{:.1f}").map(
        lambda v: f'color: {COLOR_RED}' if 0 < v < LIMITE_POLITICA else (f'color: {COLOR_PURPLE}' if v > LIMITE_POLITICA else f'color: {COLOR_CYAN}' if v == LIMITE_POLITICA else 'color: lightgray')
    ), use_container_width=True)

except Exception as e:
    st.error(f"Error al procesar la información: {e}")
