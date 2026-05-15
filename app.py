import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

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

def cargar_permisos():
    return conn.read(spreadsheet=URL_HOJA, worksheet="Permisos_Gerencia", ttl=0)

def cargar_bd():
    df = conn.read(spreadsheet=URL_HOJA, worksheet="BD HH", ttl=0)
    
    # Columnas que el gerente puede editar
    cols_editables = ['Estado Aprobación', 'Comentarios Gerencia', 'Dias']
    # Columnas que se llenan solas al guardar
    cols_auto = ['Aprobado Por', 'Fecha de Acción']
    # Columnas informativas (se muestran pero no se editan)
    cols_info = ['Socio Responsable', 'Email', 'Proyecto', 'Estado Consultor', 'Estado del Proyecto', 'Mes']
    
    todas_las_nuevas = cols_editables + cols_auto + cols_info
    
    for col in todas_las_nuevas:
        if col not in df.columns:
            df[col] = ""
        else:
            if col != 'Dias': # Dias debe ser numerico
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
        
        # Filtro de Mes
        meses_disp = sorted(df_bd['Mes'].unique())
        mes_sel = st.sidebar.selectbox("Seleccionar Mes", meses_disp)
        
        # Filtro de Proyecto (Solo los que tiene asignados)
        proyectos_permitidos = [p for p in st.session_state.proyectos_asignados if p in df_bd['Proyecto'].unique()]
        proy_sel = st.sidebar.selectbox("Seleccionar Proyecto", ["Todos mis Proyectos"] + proyectos_permitidos)

        if st.sidebar.button("Cerrar Sesión"):
            st.session_state.usuario = None
            st.rerun()

        # --- APLICAR FILTROS A LA DATA ---
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
            # Definir qué columnas mostrar y en qué orden
            cols_a_mostrar = [
                'Nombre consultor', 'Proyecto', 'Mes', 'Dias', 
                'Estado Aprobación', 'Comentarios Gerencia', 
                'Socio Responsable', 'Email', 'Estado Consultor', 'Estado del Proyecto'
            ]
            
            # Bloquear todo excepto lo editable
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
                    # Unir los cambios de vuelta al dataframe maestro
                    df_editado['Aprobado Por'] = st.session_state.usuario
                    df_editado['Fecha de Acción'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    # Usamos el índice original para actualizar la BD maestra
                    df_bd.update(df_editado)
                    conn.update(worksheet="BD HH", data=df_bd)
                    st.success("Sincronización exitosa con la base central.")
                    st.rerun()

    except Exception as e:
        st.error(f"Error técnico: {e}")
