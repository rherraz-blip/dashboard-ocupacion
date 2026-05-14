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
    
    # Aseguramos las columnas y FORZAMOS que sean de texto
    columnas_texto = ['Estado Aprobación', 'Aprobado Por', 'Comentarios Gerencia', 'Fecha de Acción']
    for col in columnas_texto:
        if col not in df.columns:
            df[col] = ""  # En vez de None, usamos texto vacío
        else:
            # Rellena vacíos con "" y convierte todo a string (texto)
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
    st.write("Por favor, ingresa tus credenciales de gerencia para autorizar horas.")
    
    with st.form("login_form"):
        email_input = st.text_input("Correo electrónico corporativo")
        clave_input = st.text_input("Clave de acceso", type="password")
        btn_login = st.form_submit_button("Ingresar al Portal")
        
        if btn_login:
            try:
                df_permisos = cargar_permisos()
                
                def limpiar_clave(c):
                    c_str = str(c).strip()
                    if c_str.endswith('.0'):
                        return c_str[:-2]
                    return c_str
                
                df_permisos['Clave_Limpia'] = df_permisos['Clave'].apply(limpiar_clave)
                
                match = df_permisos[
                    (df_permisos['Email Gerente'].astype(str).str.strip().str.lower() == email_input.strip().lower()) & 
                    (df_permisos['Clave_Limpia'] == clave_input.strip())
                ]
                
                if not match.empty:
                    st.session_state.usuario = email_input
                    st.session_state.proyectos_asignados = match['Proyecto Asignado'].tolist()
                    st.success("Acceso concedido. Cargando tus proyectos...")
                    st.rerun()
                else:
                    st.error("❌ Credenciales incorrectas. Verifica tu correo o contraseña.")
            except Exception as e:
                st.error(f"Error al conectar con la base de permisos: {e}")

# 2. PANTALLA DE APROBACIÓN (USUARIO LOGUEADO)
else:
    st.sidebar.success(f"👤 Conectado como:\n**{st.session_state.usuario}**")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.usuario = None
        st.session_state.proyectos_asignados = []
        st.rerun()
        
    st.subheader("✅ Revisión y Aprobación de Carga (HH)")
    
    try:
        df_bd = cargar_bd()
        df_gerente = df_bd[df_bd['Proyecto'].isin(st.session_state.proyectos_asignados)].copy()
        
        if df_gerente.empty:
            st.info("No tienes consultores asignados en tus proyectos para revisar en este momento.")
        else:
            st.write("Haz doble clic en las celdas de las columnas **Dias**, **Estado Aprobación** o **Comentarios Gerencia** para modificar.")
            
            columnas_bloqueadas = [col for col in df_gerente.columns if col not in ['Dias', 'Estado Aprobación', 'Comentarios Gerencia']]
            
            with st.form("editor_form"):
                df_editado = st.data_editor(
                    df_gerente,
                    disabled=columnas_bloqueadas,
                    column_config={
                        "Estado Aprobación": st.column_config.SelectboxColumn(
                            "Estado Aprobación",
                            help="Selecciona el estado de revisión",
                            options=["Pendiente", "Aprobado", "Rechazado"],
                            required=True
                        ),
                        "Comentarios Gerencia": st.column_config.TextColumn(
                            "Comentarios Gerencia",
                            help="Explica por qué ajustaste los días o el rechazo"
                        ),
                        "Dias": st.column_config.NumberColumn(
                            "Dias",
                            help="Días totales asignados",
                            min_value=0.0,
                            max_value=31.0,
                            step=0.5
                        )
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                btn_guardar = st.form_submit_button("💾 Guardar y Sincronizar Cambios")
                
                if btn_guardar:
                    with st.spinner("Sincronizando con la base central de Finanzas..."):
                        cambios = df_editado.compare(df_gerente)
                        
                        if cambios.empty:
                            st.warning("No detectamos ningún cambio para guardar.")
                        else:
                            timestamp_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            df_editado['Aprobado Por'] = st.session_state.usuario
                            df_editado['Fecha de Acción'] = timestamp_actual
                            
                            df_bd.update(df_editado)
                            conn.update(worksheet="BD HH", data=df_bd)
                            
                            st.success(f"¡Cambios guardados con éxito! Finanzas ha recibido la actualización.")
                            st.rerun()

    except Exception as e:
        st.error(f"Error técnico durante la carga de datos: {e}")
