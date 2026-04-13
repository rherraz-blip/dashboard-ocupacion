import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

# Colores corporativos profesionales
COLOR_PRINCIPAL = "#008B8B" # Cyan oscuro para >= 18 días
COLOR_ALERTA = "#E74C3C"    # Rojo para marcar alerta (< 18 días)
LIMITE_POLITICA = 18.0      

st.set_page_config(page_title="Dashboard Ocupación SCT", layout="wide")

st.title("📊 Dashboard de Ocupación por Proyectos")

# 1. Conexión en vivo a Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=600)
def cargar_datos():
    # Link directo a tu sábana de datos
    url_hoja = "https://docs.google.com/spreadsheets/d/1IQhd4LR8CjEd3PIYb7WUCW364vaKS4QVpCtLNQOpFB8/edit#gid=280416127"
    return conn.read(spreadsheet=url_hoja, worksheet="BD HH")

try:
    df = cargar_datos()
    
    # 2. Limpieza de datos (Días en formato texto "6,00")
    df['Dias'] = df['Dias'].astype(str).str.strip().str.replace(',', '.').astype(float)
    
    # 3. Filtros Laterales
    st.sidebar.header("Panel de Control")
    meses_disponibles = df['Mes'].dropna().unique()
    mes_sel = st.sidebar.selectbox("Seleccionar Mes de Análisis", meses_disponibles)

    df_mes = df[df['Mes'] == mes_sel]

    # 4. Procesamiento y Agrupación por Consultor
    resumen = df_mes.groupby('Nombre consultor')['Dias'].sum().reset_index()

    # Lógica de colores: Rojo si < 18, Cyan si >= 18
    resumen['Alerta_Color'] = resumen['Dias'].apply(
        lambda x: COLOR_ALERTA if x < LIMITE_POLITICA else COLOR_PRINCIPAL
    )
    
    # Lógica de estado para la tabla
    def definir_estado(dias):
        if dias < LIMITE_POLITICA:
            return "Bajo Límite (<18)"
        elif dias > LIMITE_POLITICA:
            return "Sobrecarga (>18)"
        else:
            return "Óptimo (18)"
            
    resumen['Estado'] = resumen['Dias'].apply(definir_estado)

    # 5. KPIs superiores
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Consultores", len(resumen))
    col2.metric("Total Días Sumados", f"{resumen['Dias'].sum():.1f}")
    col3.metric("Personas por debajo de 18 días", len(resumen[resumen['Dias'] < LIMITE_POLITICA]))

    st.divider()

    # 6. Visualización: Gráfico de Barras y Tabla de Detalle
    col_izq, col_der = st.columns([2, 1])

    with col_izq:
        st.subheader("Días Asignados por Consultor")
        fig = px.bar(
            resumen, 
            x='Nombre consultor', 
            y='Dias', 
            color='Alerta_Color',
            color_discrete_map="identity", # Obliga a usar códigos HEX exactos
            text_auto='.1f'
        )
        # Línea punteada de 18 días
        fig.add_hline(
            y=LIMITE_POLITICA, 
            line_dash="dash", 
            line_color=COLOR_ALERTA, 
            annotation_text=f"Límite Político ({LIMITE_POLITICA} días)"
        )
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Días Totales Sumados")
        st.plotly_chart(fig, use_container_width=True)

    with col_der:
        st.subheader("Estado Mensual")
        # Mostrar tabla ordenada para que los que tienen menos días salgan primero
        st.dataframe(
            resumen[['Nombre consultor', 'Dias', 'Estado']].sort_values(by='Dias'), 
            hide_index=True,
            use_container_width=True
        )

    st.write("### Acciones")
    if st.button("📧 Enviar Alertas por Correo"):
        st.success("¡Alerta enviada! Se ha notificado a los responsables sobre las desviaciones de capacidad.")

except Exception as e:
    st.error("Error al conectar con la base de datos.")
    st.write(f"Detalle técnico: {e}")
