import streamlit as st
import pandas as pd
import plotly.express as px

# Colores corporativos profesionales
COLOR_PRINCIPAL = "#008B8B" # Cyan oscuro para datos profesionales y analíticos
COLOR_ALERTA = "#E74C3C"    # Rojo para marcar alerta (< 18 días)
LIMITE_POLITICA = 18.0      # Límite de días para la alerta

st.set_page_config(page_title="Dashboard Ocupación SCT", layout="wide")

st.title("📊 Dashboard de Ocupación por Proyectos")

# 1. Carga de datos
@st.cache_data
def cargar_datos():
    # Asegúrate de que el CSV esté en la misma carpeta que este script
    df = pd.read_csv("HH PV  equipo 2026 - BD HH.csv")
    # Limpieza de datos (Días en formato texto "6,00")
    df['Dias'] = df['Dias'].astype(str).str.replace(',', '.').astype(float)
    return df

df = cargar_datos()

# 2. Filtros Laterales
st.sidebar.header("Panel de Control")
meses_disponibles = df['Mes'].dropna().unique()
mes_sel = st.sidebar.selectbox("Seleccionar Mes de Análisis", meses_disponibles)

# Filtramos la tabla original por el mes seleccionado
df_mes = df[df['Mes'] == mes_sel]

# 3. Procesamiento y Agrupación por Consultor
# Sumamos los días totales asignados a cada persona en ese mes
resumen = df_mes.groupby('Nombre consultor')['Dias'].sum().reset_index()

# Lógica de colores corporativos: Rojo si < 18, Cyan si >= 18
resumen['Alerta_Color'] = resumen['Dias'].apply(
    lambda x: COLOR_ALERTA if x < LIMITE_POLITICA else COLOR_PRINCIPAL
)

# 4. KPIs superiores
col1, col2, col3 = st.columns(3)
col1.metric("Total Consultores", len(resumen))
col2.metric("Total Días Sumados", resumen['Dias'].sum())
col3.metric("Personas por debajo de 18 días", len(resumen[resumen['Dias'] < LIMITE_DIAS]))

st.divider()

# 5. Visualización: Gráfico de Barras y Tabla de Detalle
col_izq, col_der = st.columns([2, 1])

with col_izq:
    # Gráfico Profesional
    st.subheader("Días Asignados por Consultor (Límite Político 18 días)")
    fig = px.bar(
        resumen, 
        x='Nombre consultor', 
        y='Dias', 
        color='Alerta_Color',
        color_discrete_map="identity" # Forza a Plotly a usar los códigos HEX exactos
    )
    # Añadimos la línea punteada roja para marcar el límite de 18 días
    fig.add_hline(
        y=LIMITE_DIAS, 
        line_dash="dash", 
        line_color=COLOR_ALERTA, 
        annotation_text=f"Límite Político ({LIMITE_DIAS} días)"
    )
    fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Días Totales Sumados")
    st.plotly_chart(fig, use_container_width=True)

with col_der:
    # Tabla Analítica
    st.subheader("Detalle de Asignaciones en el Mes")
    # Mostramos la sábana filtrada para que puedan ver en qué proyectos está cada quien
    # Usamos st.dataframe para permitir filtros y ordenamiento en la tabla
    st.dataframe(
        df_mes[['Nombre consultor', 'Proyecto', 'Cargo', 'Dias', 'Estado proyecto']], 
        use_container_width=True
    )

st.write("### Acciones")
if st.button("📧 Enviar Alertas por Correo"):
    # Aquí iría tu script de envío automático
    st.success("¡Alerta enviada! Se ha notificado a los socios responsables sobre las personas que exceden o están por debajo del límite de días.")
