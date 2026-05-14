import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- CONFIGURACIÓN CORPORATIVA ---
# Cambiamos el nombre que aparece en la pestaña del navegador
st.set_page_config(page_title="Módulo de Aprobaciones INNSPIRAL", page_icon="🔐", layout="wide")

# --- LOGO DE LA EMPRESA ---
# Intentará cargar el logo desde GitHub. El width controla el tamaño (250 píxeles es un buen estándar).
try:
    st.image("logo.png", width=250)
except Exception:
    # Si aún no subes la imagen, esto evita que la pantalla muestre un error feo en rojo
    pass

# Cambiamos el título principal
st.title("🛡️ Portal de Aprobaciones - INNSPIRAL")

# --- CONEXIÓN ---
# Se utiliza ttl=0 para que no use memoria caché y siempre traiga los datos más frescos del Excel
conn = st.connection("gsheets", type=GSheetsConnection)
URL_HOJA = "https://docs.google.com/spreadsheets/d/1IQhd4LR8CjEd3PIYb7WUCW364vaKS4QVpCtLNQOpFB8/edit#gid=280416127"

def cargar_permisos():
    return conn.read(spreadsheet=URL_HOJA, worksheet="Permisos_Gerencia", ttl=0)

def cargar_bd():
    df = conn.read(spreadsheet=URL_HOJA, worksheet="BD HH", ttl=0)
    
    # Asegurar que existan las columnas nuevas (por si acaso aún no se han escrito en Excel)
    columnas_requeridas = ['Estado Aprobación', 'Aprobado Por', 'Comentarios Gerencia', 'Fecha de Acción']
    for col in columnas_requeridas:
        if col not in df.columns:
            df[col] = None
            
    # Limpieza de días a formato numérico
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
                # Filtrar la hoja de permisos buscando coincidencias exactas
                match = df_permisos[
                    (df_permisos['Email Gerente'].astype(str).str.strip().str.lower() == email_input.strip().lower()) & 
                    (df_permisos['Clave'].astype(str).str.strip() == clave_input.strip())
                ]
                
                if not match.empty:
                    st.session_state.usuario = email_input
                    # Guardamos la lista de proyectos que le pertenecen a este gerente
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
        # Cargar base de datos completa
        df_bd = cargar_bd()
        
        # Filtrar SOLO las filas de los proyectos que le pertenecen a este gerente
        df_gerente = df_bd[df_bd['Proyecto'].isin(st.session_state.proyectos_asignados)].copy()
        
        if df_gerente.empty:
            st.info("No tienes consultores asignados en tus proyectos para revisar en este momento.")
        else:
            st.write("Haz doble clic en las celdas de las columnas **Dias**, **Estado Aprobación** o **Comentarios Gerencia** para modificar.")
            
            # Bloqueamos todas las columnas excepto las 3 que puede editar
            columnas_bloqueadas = [col for col in df_gerente.columns if col not in ['Dias', 'Estado Aprobación', 'Comentarios Gerencia']]
            
            with st.form("editor_form"):
                # Mostrar el editor interactivo
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
                        # Identificamos qué filas cambiaron comparando el df original del gerente con el editado
                        cambios = df_editado.compare(df_gerente)
                        
                        if cambios.empty:
                            st.warning("No detectamos ningún cambio para guardar.")
                        else:
                            # Actualizar campos automáticos a las filas que el gerente acaba de ver/editar
                            timestamp_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            # Actualizamos el dataframe editado con los datos de auditoría
                            df_editado['Aprobado Por'] = st.session_state.usuario
                            df_editado['Fecha de Acción'] = timestamp_actual
                            
                            # Combinar los cambios en el dataframe maestro (df_bd)
                            # Actualizamos usando el índice para asegurar que modificamos las filas correctas
                            df_bd.update(df_editado)
                            
                            # Enviar el dataframe actualizado a Google Sheets
                            conn.update(worksheet="BD HH", data=df_bd)
                            
                            st.success(f"¡Cambios guardados con éxito! Finanzas ha recibido la actualización.")
                            st.rerun()

    except Exception as e:
        st.error(f"Error técnico durante la carga de datos: {e}")
