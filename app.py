import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Control Ocupación - SCT", page_icon="📊", layout="wide")

# Colores y Política
COLOR_CYAN = "#008B8B"
COLOR_ALERTA = "#E74C3C"
LIMITE_DIAS = 18.0

st.title("📊 Gestión de Ocupación por Proyectos")
st.markdown(f"Monitor de capacidad basado en la política interna de **{LIMITE_DIAS} días hábiles**.")

# --- CONEXIÓN EN VIVO A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=600) # Se actualiza automáticamente cada 10 minutos
def cargar_datos():
    # Enlace directo a tu planilla
    url_hoja = "https://docs.google.com/spreadsheets/d/1IQhd4LR8CjEd3PIYb7WUCW364vaKS4QVpCtLNQOpFB8/edit#gid=280416127"
    return conn.read(spreadsheet=url_hoja, worksheet="BD HH")

try:
    # 1. Carga de información
    df = cargar_datos()
    
    # 2. Limpieza de datos (Conversión de "6,00" a número)
    df['Dias'] = df['Dias'].astype(str).str.strip().str.replace(',', '.').astype(float)
    
    # 3. Filtros laterales
    st.sidebar.header("Panel de Control")
    meses_disponibles = df['Mes'].dropna().unique()
    mes_sel = st.sidebar.selectbox("Seleccionar Mes de Análisis", meses_disponibles)
    
    # Filtrado por mes
    df_mes = df[df['Mes'] == mes_sel]
    
    # 4. Procesamiento por Consultor
    resumen = df_mes.groupby('Nombre consultor')['Dias'].sum().reset_index()
    resumen['Estado'] = resumen['Dias'].apply(lambda x: "Sobrecarga" if x > LIMITE_DIAS else "Óptimo")
    resumen['Color'] = resumen['Estado'].apply(lambda x: COLOR_ALERTA if x == "Sobrecarga" else COLOR_CYAN)

    # 5. Visualización de Gráficos
    st.subheader(f"Días Asignados en {mes_sel}")
    
    fig = px.bar(
        resumen, 
        x='Nombre consultor', 
        y='Dias', 
        color='Color',
        color_discrete_map="identity",
        text_auto='.1f'
    )
    
    # Línea de referencia de los 18 días
    fig.add_hline(
        y=LIMITE_DIAS, 
        line_dash="dash", 
        line_color=COLOR_ALERTA,
        annotation_text=f"Límite Político ({LIMITE_DIAS} días)",
        annotation_position="top right"
    )
    
    fig.update_layout(xaxis_title="", yaxis_title="Días Totales Sumados", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # 6. Tabla de Alertas Críticas
    sobrecargados = resumen[resumen['Estado'] == "Sobrecarga"].sort_values(by='Dias', ascending=False)
    
    if not sobrecargados.empty:
        st.error(f"⚠️ Alerta: {len(sobrecargados)} consultores superan la política de {LIMITE_DIAS} días.")
        st.dataframe(
            sobrecargados[['Nombre consultor', 'Dias']], 
            hide_index=True,
            use_container_width=True
        )
    else:
        st.success(f"✅ Todos los consultores cumplen con la política de {LIMITE_DIAS} días en {mes_sel}.")

except Exception as e:
    st.error("Error al conectar con la sábana de datos.")
    st.info("Verifica que los 'Secrets' en Streamlit Cloud tengan el formato TOML correcto y que la hoja se llame 'BD HH'.")
    st.write(f"Detalle: {e}")
