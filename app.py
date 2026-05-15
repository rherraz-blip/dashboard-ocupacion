import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import plotly.express as px

# --- CONFIGURACIÓN CORPORATIVA ---
st.set_page_config(page_title="Módulo de Aprobaciones INNSPIRAL", page_icon="🔐", layout="wide")

try:
    st.image("logo.png", width=250)
except Exception:
    pass

st.title("🛡️ Portal de Aprobaciones - INNSPIRAL")

# --- CONEXIÓN ---
conn = st.connection("gsheets", type=GSheetsConnection)
URL_HOJA = "https://docs.google.com/spreadsheets/d/1IQhd4LR8CjEd3PIYb7WUCW364vaKS4QVpCtLNQOpFB8/edit#gid=280416127"

# Colores corporativos para el gráfico
COLOR_CYAN = "#008B8B"
COLOR_RED = "#E74C3C"
COLOR_PURPLE = "#6A5ACD"
LIMITE_POLITICA = 18.0

def cargar_permisos():
    return conn.read(spreadsheet=URL_HOJA, worksheet="Permisos_Gerencia", ttl=0)

def cargar_bd():
    df = conn.read(spreadsheet=URL_HOJA, worksheet="BD HH", ttl=0)
    
    # Columnas que el gerente puede editar
    cols_editables = ['Estado Aprobación', 'Comentarios Gerencia', 'Dias']
    # Columnas automáticas e informativas clave
    cols_auto_info = ['Aprobado Por', 'Fecha de Acción', 'Socio Responsable', 'Proyecto', 'Mes']
    
    todas_las_nuevas = cols_editables + cols_auto_info
    
    for col in todas_las_nuevas:
        if col not in df.columns:
            df[col] = ""
        else:
            if col != 'Dias': 
                df[col] = df[col].fillna("").astype(str)
            
    df['Dias'] = df['Dias'].astype(str).str.replace(',', '.').str.strip()
    df['Dias'] = pd.to_numeric(df['Dias'], errors='coerce').fillna(0.0)
    return df

# --- GESTIÓN DE SESIÓN (LOGIN) ---
if 'usuario' not in st.session_state:
    st.session_state.usuario = None
if 'proyectos_asignados' not in st.session_state:
    st.session_state.proyectos_asignados = []

# 1. PANTALLA DE LOGIN
if st.session_state.usuario is None:
    st.subheader("🔒 Acceso Restringido")
    st.write("Ingresa tus credenciales para autorizar horas.")
    
    with st.form("login_form"):
        email_input = st.text_input("Correo electrónico corporativo")
        clave_input = st.text_input("Clave de acceso", type="password")
        btn_login = st.form_submit_button("Ingresar al Portal")
        
        if btn_login:
            try:
                df_permisos = cargar_permisos()
                def limpiar_clave(c):
                    c_str = str(c).strip()
                    if c_str.endswith('.0'): return c_str[:-2]
                    return c_str
                
                df_permisos['Clave_Limpia'] = df_permisos['Clave'].apply(limpiar_clave)
                match = df_permisos[
                    (df_permisos['Email Gerente'].astype(str).str.strip().str.lower() == email_input.strip().lower()) & 
                    (df_permisos['Clave_Limpia'] == clave_input.strip())
                ]
                
                if not match.empty:
                    st.session_state.usuario = email_input
                    st.session_state.proyectos_asignados = match['Proyecto Asignado'].tolist()
                    st.rerun()
                else:
                    st.error("❌ Credenciales incorrectas.")
            except Exception as e:
                st.error(f"Error: {e}")

# 2. PANTALLA DE APROBACIÓN
else:
    st.sidebar.success(f"👤 **{st.session_state.usuario}**")
    
    try:
        df_bd = cargar_bd()
        
        # --- FILTROS LATERALES ---
        st.sidebar.header("🎯 Filtros de Revisión")
        meses_disp = sorted(df_bd['Mes'].unique())
        mes_sel = st.sidebar.selectbox("Seleccionar Mes", meses_disp)
        
        proyectos_permitidos = [p for p in st.session_state.proyectos_asignados if p in df_bd['Proyecto'].unique()]
        proy_sel = st.sidebar.selectbox("Seleccionar Proyecto", ["Todos mis Proyectos"] + proyectos_permitidos)

        if st.sidebar.button("Cerrar Sesión"):
            st.session_state.usuario = None
            st.rerun()

        # --- APLICAR FILTROS ---
        mask = (df_bd['Mes'] == mes_sel)
        if proy_sel != "Todos mis Proyectos":
            mask = mask & (df_bd['Proyecto'] == proy_sel)
        else:
            mask = mask & (df_bd['Proyecto'].isin(st.session_state.proyectos_asignados))
            
        df_gerente = df_bd[mask].copy()

        st.subheader(f"✅ Revisión: {mes_sel}")
        
        if df_gerente.empty:
            st.info(f"No hay registros para {mes_sel} en los proyectos seleccionados.")
        else:
            # --- GRÁFICO DE APOYO VISUAL ---
            resumen_grafico = df_gerente.groupby('Nombre consultor')['Dias'].sum().reset_index()
            
            def get_color(d):
                if d < LIMITE_POLITICA: return COLOR_RED
                if d > LIMITE_POLITICA: return COLOR_PURPLE
                return COLOR_CYAN
            
            resumen_grafico['Color'] = resumen_grafico['Dias'].apply(get_color)
            
            fig = px.bar(resumen_grafico, x='Nombre consultor', y='Dias', 
                         color='Color', color_discrete_map="identity", text_auto='.1f',
                         title=f"Carga actual en la vista (Límite: {LIMITE_POLITICA}d)")
            fig.add_hline(y=LIMITE_POLITICA, line_dash="dash", line_color="gray")
            fig.update_layout(xaxis_title="", yaxis_title="Días Totales", margin=dict(t=40, b=20))
            
            st.plotly_chart(fig, use_container_width=True)
            
            st.divider()

            # --- TABLA DE EDICIÓN ---
            st.write("📝 **Tabla de Aprobación** (Modifica los campos permitidos y guarda)")
            
            cols_a_mostrar = [
                'Nombre consultor', 'Proyecto', 'Mes', 'Dias', 
                'Estado Aprobación', 'Comentarios Gerencia', 'Socio Responsable'
            ]
            
            columnas_bloqueadas = [c for c in cols_a_mostrar if c not in ['Dias', 'Estado Aprobación', 'Comentarios Gerencia']]

            with st.form("editor_form"):
                df_editado = st.data_editor(
                    df_gerente[cols_a_mostrar],
                    disabled=columnas_bloqueadas,
                    column_config={
                        "Estado Aprobación": st.column_config.SelectboxColumn(
                            options=["Pendiente", "Aprobado", "Rechazado"],
                            required=True
                        ),
                        "Dias": st.column_config.NumberColumn(format="%.1f", min_value=0.0, max_value=31.0)
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                if st.form_submit_button("💾 Guardar Cambios"):
                    df_editado['Aprobado Por'] = st.session_state.usuario
                    df_editado['Fecha de Acción'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    df_bd.update(df_editado)
                    
                    # ¡AQUÍ ESTÁ LA CORRECCIÓN! Agregamos spreadsheet=URL_HOJA
                    conn.update(spreadsheet=URL_HOJA, worksheet="BD HH", data=df_bd)
                    
                    st.success("Sincronización exitosa con la base central.")
                    st.rerun()

    except Exception as e:
        st.error(f"Error técnico: {e}")
