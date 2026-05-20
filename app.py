import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import plotly.express as px

# --- CONFIGURACIÓN CORPORATIVA ---
st.set_page_config(page_title="Portal de Horas INNSPIRAL", page_icon="🔐", layout="wide")

try:
    st.image("logo.png", width=250)
except Exception:
    pass

st.title("🛡️ Sistema de Control y Flujo de HH - INNSPIRAL")

# --- CONEXIÓN CENTRAL ---
conn = st.connection("gsheets", type=GSheetsConnection)
URL_HOJA = "https://docs.google.com/spreadsheets/d/1IQhd4LR8CjEd3PIYb7WUCW364vaKS4QVpCtLNQOpFB8/edit#gid=280416127"

COLOR_CYAN = "#008B8B"
COLOR_RED = "#E74C3C"
COLOR_PURPLE = "#6A5ACD"
LIMITE_POLITICA = 18.0

def cargar_permisos():
    return conn.read(spreadsheet=URL_HOJA, worksheet="Permisos_Gerencia", ttl=0)

def cargar_bd():
    df = conn.read(spreadsheet=URL_HOJA, worksheet="BD HH", ttl=0)
    
    # AQUÍ ESTÁ LA CORRECCIÓN: Agregamos 'Socio Responsable' a la lista segura
    columnas_texto = [
        'Observaciones Admin', 'Estado GG', 'Comentarios GG', 
        'Estado Socio', 'Comentarios Socio', 'Aprobado Por', 'Fecha de Acción', 
        'Proyecto', 'Mes', 'Socio Responsable'
    ]
    for col in columnas_texto:
        if col not in df.columns:
            df[col] = "" # Si no existe, la crea vacía para que no se caiga
        else:
            df[col] = df[col].fillna("").astype(str).str.strip()
            
    df['Dias'] = df['Dias'].astype(str).str.replace(',', '.').str.strip()
    df['Dias'] = pd.to_numeric(df['Dias'], errors='coerce').fillna(0.0)
    return df

# --- CONTROL DE SESIÓN ---
if 'usuario' not in st.session_state:
    st.session_state.usuario = None
if 'proyectos_asignados' not in st.session_state:
    st.session_state.proyectos_asignados = []
if 'rol' not in st.session_state:
    st.session_state.rol = None

# 1. PANTALLA DE ACCESO
if st.session_state.usuario is None:
    st.subheader("🔒 Identificación de Usuario")
    st.write("El sistema adaptará tus permisos de visualización y edición según tu rol asignado.")
    
    with st.form("login_form"):
        email_input = st.text_input("Correo corporativo").strip().lower()
        clave_input = st.text_input("Clave de acceso", type="password").strip()
        btn_login = st.form_submit_button("Ingresar al Sistema")
        
        if btn_login:
            try:
                df_permisos = cargar_permisos()
                
                def limpiar_clave(c):
                    c_str = str(c).strip()
                    if c_str.endswith('.0'): return c_str[:-2]
                    return c_str
                
                df_permisos['Clave_Limpia'] = df_permisos['Clave'].apply(limpiar_clave)
                
                match = df_permisos[
                    (df_permisos['Email Gerente'].astype(str).str.strip().str.lower() == email_input) & 
                    (df_permisos['Clave_Limpia'] == clave_input)
                ]
                
                if not match.empty:
                    st.session_state.usuario = email_input
                    st.session_state.rol = str(match['Rol'].iloc[0]).strip()
                    st.session_state.proyectos_asignados = match['Proyecto Asignado'].tolist()
                    st.success(f"Acceso correcto. Rol detectado: {st.session_state.rol}")
                    st.rerun()
                else:
                    st.error("❌ Credenciales no válidas o rol no configurado.")
            except Exception as e:
                st.error(f"Error de autenticación: {e}")

# 2. PORTAL TRANSACCIONAL
else:
    st.sidebar.success(f"👤 **{st.session_state.usuario}**\n\n🔑 Rol: **{st.session_state.rol}**")
    
    try:
        df_bd = cargar_bd()
        
        st.sidebar.header("🎯 Filtros de Vista")
        meses_disp = sorted(df_bd['Mes'].unique())
        mes_sel = st.sidebar.selectbox("Mes", meses_disp)
        
        if st.session_state.rol in ['Admin', 'GG']:
            proyectos_visibles = sorted(list(df_bd['Proyecto'].unique()))
        else:
            proyectos_visibles = [p for p in st.session_state.proyectos_asignados if p in df_bd['Proyecto'].unique()]
            
        proy_sel = st.sidebar.selectbox("Proyecto", ["Todos mis Proyectos"] + proyectos_visibles)

        if st.sidebar.button("🔒 Cerrar Sesión"):
            st.session_state.usuario = None
            st.session_state.rol = None
            st.session_state.proyectos_asignados = []
            st.rerun()

        mask = (df_bd['Mes'] == mes_sel)
        
        if st.session_state.rol in ['Admin', 'GG']:
            if proy_sel != "Todos mis Proyectos":
                mask = mask & (df_bd['Proyecto'] == proy_sel)
        else: 
            if proy_sel != "Todos mis Proyectos":
                mask = mask & (df_bd['Proyecto'] == proy_sel)
            else:
                mask = mask & (df_bd['Proyecto'].isin(st.session_state.proyectos_asignados))
                
        df_vista = df_bd[mask].copy()

        st.subheader(f"📋 Panel de Revisión - Periodo: {mes_sel}")
        
        if df_vista.empty:
            st.info("No se encontraron registros para los filtros seleccionados.")
        else:
            resumen_grafico = df_vista.groupby('Nombre consultor')['Dias'].sum().reset_index()
            resumen_grafico['Color'] = resumen_grafico['Dias'].apply(
                lambda d: COLOR_RED if d < LIMITE_POLITICA else (COLOR_PURPLE if d > LIMITE_POLITICA else COLOR_CYAN)
            )
            fig = px.bar(resumen_grafico, x='Nombre consultor', y='Dias', color='Color', 
                         color_discrete_map="identity", text_auto='.1f', title="Carga de HH consolidada en la vista")
            fig.add_hline(y=LIMITE_POLITICA, line_dash="dash", line_color="gray")
            st.plotly_chart(fig, use_container_width=True)
            
            st.divider()

            cols_a_mostrar = [
                'Nombre consultor', 'Proyecto', 'Mes', 'Dias', 
                'Observaciones Admin', 'Estado GG', 'Comentarios GG', 
                'Estado Socio', 'Comentarios Socio', 'Socio Responsable'
            ]
            
            if st.session_state.rol == 'Admin':
                cols_editables = ['Dias', 'Observaciones Admin']
                st.caption("🛠️ **Modo Administración**: Tienes permiso exclusivo para modificar los Días de ocupación y añadir observaciones iniciales.")
            elif st.session_state.rol == 'GG':
                cols_editables = ['Estado GG', 'Comentarios GG']
                st.caption("👑 **Modo Gerencia General**: Puedes proponer modificaciones y cambiar tu estado de revisión. La cantidad de días es de solo lectura.")
            elif st.session_state.rol == 'Socio':
                cols_editables = ['Estado Socio', 'Comentarios Socio']
                st.caption("👔 **Modo Socio Responsable**: Puedes emitir tus comentarios y aprobación para tus proyectos asignados. La cantidad de días es de solo lectura.")
            else:
                cols_editables = []

            columnas_bloqueadas = [c for c in cols_a_mostrar if c not in cols_editables]

            with st.form("flujo_trabajo_form"):
                df_editado = st.data_editor(
                    df_vista[cols_a_mostrar],
                    disabled=columnas_bloqueadas,
                    column_config={
                        "Dias": st.column_config.NumberColumn(format="%.1f", min_value=0.0, max_value=31.0, step=0.5),
                        "Estado GG": st.column_config.SelectboxColumn(options=["Pendiente", "Aprobado", "Con Sugerencias"]),
                        "Estado Socio": st.column_config.SelectboxColumn(options=["Pendiente", "Aprobado", "Con Sugerencias"]),
                        "Observaciones Admin": st.column_config.TextColumn(),
                        "Comentarios GG": st.column_config.TextColumn(),
                        "Comentarios Socio": st.column_config.TextColumn()
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                if st.form_submit_button("💾 Sincronizar Cambios y Comentarios"):
                    df_editado['Aprobado Por'] = st.session_state.usuario
                    df_editado['Fecha de Acción'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    df_bd.update(df_editado)
                    conn.update(spreadsheet=URL_HOJA, worksheet="BD HH", data=df_bd)
                    st.success("¡Sincronización exitosa! Los comentarios y estados se han actualizado en la base central.")
                    st.rerun()

    except Exception as e:
        st.error(f"Error en la ejecución del flujo: {e}")
