import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURACIÓN VISUAL SCT ---
st.set_page_config(page_title="Gestión de Recursos SCT", page_icon="📊", layout="wide")

COLOR_CYAN = "#008B8B"    # Óptimo (18 días)
COLOR_RED = "#E74C3C"     # Alerta Baja (< 18 días)
COLOR_PURPLE = "#6A5ACD"  # Sobrecarga (> 18 días)
LIMITE_POLITICA = 18.0

st.title("📊 Control de Gestión: Ocupación y Desocupación")

# --- CONEXIÓN ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=300)
def cargar_datos():
    url = "https://docs.google.com/spreadsheets/d/1IQhd4LR8CjEd3PIYb7WUCW364vaKS4QVpCtLNQOpFB8/edit#gid=280416127"
    df = conn.read(spreadsheet=url, worksheet="BD HH")
    # Limpieza: Convertir comas a puntos y asegurar que sea número
    df['Dias'] = df['Dias'].astype(str).str.replace(',', '.').str.strip().astype(float)
    return df

try:
    df = cargar_datos()
    
    # --- LÓGICA DE MESES (CRONOLÓGICA) ---
    meses_reales = df['Mes'].dropna().unique()
    try:
        # Intenta ordenar por fecha (01/2026)
        orden_meses = sorted(meses_reales, key=lambda x: pd.to_datetime(x, format='%m/%Y'))
    except:
        orden_meses = sorted(meses_reales)
    
    # --- SIDEBAR (FILTROS) ---
    st.sidebar.header("🔍 Filtros de Análisis")
    mes_sel = st.sidebar.selectbox("Mes de Análisis", orden_meses)
    
    # Filtro de Proyecto único
    proy_lista = ["Todos los Proyectos"] + list(df['Proyecto'].dropna().unique())
    proy_sel = st.sidebar.selectbox("Proyecto", proy_lista)

    # Aplicar Filtros
    df_mes = df[df['Mes'] == mes_sel]
    if proy_sel != "Todos los Proyectos":
        df_mes = df_mes[df_mes['Proyecto'] == proy_sel]

    # --- PROCESAMIENTO DE KPIs ---
    resumen = df_mes.groupby('Nombre consultor')['Dias'].sum().reset_index()
    
    total_dias = resumen['Dias'].sum()
    total_personas = len(resumen)
    capacidad_teorica = total_personas * LIMITE_POLITICA
    
    # Ratio de Ocupación
    porcentaje_ocupacion = (total_dias / capacidad_teorica * 100) if capacidad_teorica > 0 else 0
    desocupacion_dias = max(0, capacidad_teorica - total_dias)

    # --- INDICADORES (KPIs) ---
    st.subheader(f"Resumen Ejecutivo - {mes_sel}")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    kpi1.metric("Ocupación Global", f"{porcentaje_ocupacion:.1f}%")
    kpi2.metric("Días Totales", f"{total_dias:.1f}")
    kpi3.metric("Desocupación (Días)", f"{desocupacion_dias:.1f}")
    kpi4.metric("Personal fuera de meta", len(resumen[resumen['Dias'] != LIMITE_POLITICA]))

    st.divider()

    # --- GRÁFICOS PRINCIPALES ---
    col_izq, col_der = st.columns([7, 3])

    with col_izq:
        st.write(f"**Asignación por Consultor ({proy_sel})**")
        # Semáforo de colores
        def get_color(d):
            if d < LIMITE_POLITICA: return COLOR_RED
            if d > LIMITE_POLITICA: return COLOR_PURPLE
            return COLOR_CYAN
        
        resumen['Color'] = resumen['Dias'].apply(get_color)
        
        fig_bar = px.bar(resumen, x='Nombre consultor', y='Dias', 
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
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- SECCIÓN DE GERENCIA (MODO SEGURO) ---
    st.sidebar.divider()
    st.sidebar.subheader("🔒 Panel de Control")
    password = st.sidebar.text_input("Clave Gerencial", type="password")
    
    if password == st.secrets.get("CLAVE_GERENCIA", "SCT2026"):
        with st.expander("📥 Enviar Notificaciones de Ajuste"):
            st.info("Aquí puedes enviar un correo con los consultores que están fuera de la política.")
            email_to = st.text_input("Correo del responsable:")
            btn_enviar = st.button("Enviar Reporte")
            if btn_enviar:
                st.warning("Configuración de correo pendiente (Esperando credenciales).")

    st.divider()

    # --- CONSOLIDADO FINAL ---
    st.header("📈 Historial y Tendencias")
    
    # Matriz Consultor vs Mes
    matriz = df.pivot_table(index='Nombre consultor', columns='Mes', values='Dias', aggfunc='sum', fill_value=0)
    matriz = matriz[orden_meses] # Orden cronológico
    
    def style_matriz(val):
        if val == 0: return 'color: #D5D8DC'
        if val < LIMITE_POLITICA: return f'color: {COLOR_RED}'
        if val > LIMITE_POLITICA: return f'color: {COLOR_PURPLE}'
        return f'color: {COLOR_CYAN}'

    st.subheader("Matriz de Ocupación Histórica")
    st.dataframe(matriz.style.format("{:.1f}").map(style_matriz), use_container_width=True)

    # Gráfico de Tendencia Mensual
    st.subheader("Evolución de Ocupación por Mes")
    tendencia = df.groupby('Mes')['Dias'].sum().reindex(orden_meses).reset_index()
    fig_tend = px.bar(tendencia, x='Mes', y='Dias', color_discrete_sequence=[COLOR_CYAN], text_auto='.1f')
    st.plotly_chart(fig_tend, use_container_width=True)

except Exception as e:
    st.error(f"Error al cargar el Dashboard: {e}")
    st.info("Asegúrate de que la hoja de Google Sheets tenga los datos actualizados.")
