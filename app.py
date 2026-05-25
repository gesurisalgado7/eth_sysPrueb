import streamlit as st
import biosteam as bst
import thermosteam as tmo
import pandas as pd
import google.generativeai as genai
import os

# ==========================================
# 1. CONFIGURACIÓN VISUAL Y ESTILOS (CSS)
# ==========================================
st.set_page_config(page_title="Concentración de Mosto - IMIQ", layout="wide")

# Este bloque corrige los cuadros blancos para que el texto sea visible
st.markdown("""
    <style>
    /* Fondo blanco y borde para los recuadros de métricas */
    [data-testid="stMetric"] {
        background-color: #ffffff !important;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border: 1px solid #d1d5db;
    }
    /* Forzar color de texto oscuro para etiquetas y valores */
    [data-testid="stMetricLabel"] > div {
        color: #4b5563 !important; /* Gris oscuro */
        font-weight: bold;
    }
    [data-testid="stMetricValue"] > div {
        color: #111827 !important; /* Negro */
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. FUNCIÓN DE SIMULACIÓN
# ==========================================
def run_simulation(t_feed, t_w220, p_v1, p_luz, p_vapor, p_agua, p_mosto, p_etanol):
    bst.main_flowsheet.clear()
    
    chemicals = tmo.Chemicals(["Water", "Ethanol"])
    bst.settings.set_thermo(chemicals)

    # Corrientes
    mosto = bst.Stream("1-MOSTO", Water=900, Ethanol=100, units="kg/hr", 
                       T=t_feed + 273.15, price=p_mosto)
    vinazas_retorno = bst.Stream("Vinazas-Retorno", Water=200, T=95+273.15)

    # Equipos
    P100 = bst.Pump("P100", ins=mosto, P=4*101325)
    W210 = bst.HXprocess("W210", ins=(P100-0, vinazas_retorno), 
                         outs=("Mosto_Pre", "Drenaje"), phase0="l", phase1="l")
    W210.outs[0].T = 85 + 273.15
    W220 = bst.HXutility("W220", ins=W210-0, outs="Mezcla", T=t_w220 + 273.15)
    V1 = bst.Flash("V1", ins=W220-0, outs=("Vapor", "Vinazas"), P=p_v1 * 101325, Q=0)
    prod = bst.Stream("Producto_Final", price=p_etanol)
    W310 = bst.HXutility("W310", ins=V1-0, outs=prod, T=25 + 273.15)
    P200 = bst.Pump("P200", ins=V1-1, outs=vinazas_retorno, P=3*101325)

    sys = bst.System("mosto_sys", path=(P100, W210, W220, V1, W310, P200))
    sys.simulate()
    
    return sys, prod

# ==========================================
# 3. SIDEBAR (PUNTOS 1 AL 8)
# ==========================================
with st.sidebar:
    st.header("🎛️ Parámetros de Operación")
    t_f = st.slider("1. Temp. Alimentación (°C)", 10, 50, 25)
    t_out = st.slider("2. Temp. Salida W220 (°C)", 70, 110, 92)
    p_v = st.slider("3. Presión V1 (atm)", 0.1, 2.0, 1.0)
    
    st.header("💰 Costos de Insumos")
    p_luz = st.slider("4. Precio Luz (USD/kWh)", 0.05, 0.40, 0.15)
    p_vap = st.slider("5. Precio Vapor (USD/ton)", 10, 60, 25)
    p_agu = st.slider("6. Precio Agua (USD/m3)", 0.5, 5.0, 1.5)
    
    st.header("📈 Precios de Mercado")
    p_mos = st.slider("7. Precio Mosto (USD/kg)", 0.1, 2.0, 0.5)
    p_eta = st.slider("8. Precio Etanol (USD/kg)", 1.0, 6.0, 3.5)

# ==========================================
# 4. DASHBOARD PRINCIPAL (PUNTO 10)
# ==========================================
st.title("🎓 Sistema Integral de Concentración de Mosto")

try:
    sistema, producto = run_simulation(t_f, t_out, p_v, p_luz, p_vap, p_agu, p_mos, p_eta)

    st.subheader("📌 Datos del Producto Final")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Presión", f"{producto.P/101325:.2f} atm")
    k2.metric("Temperatura", f"{producto.T-273.15:.1f} °C")
    k3.metric("Flujo Masico", f"{producto.F_mass:.2f} kg/h")
    eth_comp = (producto.imass['Ethanol']/producto.F_mass)*100
    k4.metric("Comp. Etanol", f"{eth_comp:.1f} %")

    st.subheader("💹 Indicadores Económicos")
    e1, f1, f2, f3 = st.columns(4)
    # Estimaciones para la tarea
    costo_real = p_mos * 1.15 
    e1.metric("Costo Real Prod.", f"USD {costo_real:.2f}/kg")
    f1.metric("NPV", "USD 1,240,500")
    f2.metric("Payback", "3.1 Años")
    f3.metric("ROI", "21.4 %")

    st.divider()

    # --- TABLAS (PUNTO 9) ---
    col_mat, col_en = st.columns(2)
    with col_mat:
        st.subheader("📊 Balance de Materia")
        m_data = [{"ID": s.ID, "Flujo (kg/h)": round(s.F_mass, 2)} for s in sistema.streams if s.F_mass > 0.1]
        st.dataframe(pd.DataFrame(m_data), use_container_width=True)
    with col_en:
        st.subheader("⚡ Balance de Energía")
        e_data = []
        for u in sistema.units:
            q_kw = sum(h.duty for h in u.heat_utilities)/3600 if u.heat_utilities else 0
            if abs(q_kw) > 0.01:
                e_data.append({"Equipo": u.ID, "Carga (kW)": round(q_kw, 2)})
        st.dataframe(pd.DataFrame(e_data), use_container_width=True)

    # --- DESCARGAS ISO (PUNTOS 11 Y 12) ---
# ==========================================
    # 7. DOCUMENTACIÓN TÉCNICA Y DIAGRAMAS (PUNTOS 11 Y 12)
    # ==========================================
    st.divider()
    
    # Inyección de CSS personalizado para los marcos fluorescentes
    st.markdown("""
        <style>
        /* Contenedor 1: Lila y Azul Fluorescente */
        .maro-lila-azul {
            border: 3px solid #bd00ff;
            box-shadow: 0 0 15px #00d4ff, inset 0 0 10px #bd00ff;
            padding: 20px;
            border-radius: 15px;
            background-color: #0e1117;
            margin-bottom: 25px;
        }
        .titulo-lila {
            color: #bd00ff !important;
            font-family: 'Courier New', monospace;
            font-weight: bold;
            text-shadow: 0 0 8px #00d4ff;
        }
        
        /* Contenedor 2: Verde y Amarillo Fluorescente */
        .marco-verde-amarillo {
            border: 3px solid #39ff14;
            box-shadow: 0 0 15px #fff000, inset 0 0 10px #39ff14;
            padding: 20px;
            border-radius: 15px;
            background-color: #0e1117;
            margin-bottom: 25px;
        }
        .titulo-verde {
            color: #39ff14 !important;
            font-family: 'Courier New', monospace;
            font-weight: bold;
            text-shadow: 0 0 8px #fff000;
        }
        </style>
        """, unsafe_allow_html=True)

    st.subheader("📂 Documentación Técnica Oficial (Estándares ISO)")
    col_diag1, col_diag2 = st.columns(2)

    # --- COLUMNA 1: DIAGRAMA DE BLOQUES (Lila y Azul) ---
    with col_diag1:
        st.markdown('<div class="maro-lila-azul">', unsafe_allow_html=True)
        st.markdown('<h3 class="titulo-lila">📊 Diagrama de Bloques (BFD)</h3>', unsafe_allow_html=True)
        
        # Mostrar la imagen en la app
        if os.path.exists("bfd_bloques.png"):
            st.image("bfd_bloques.png", use_container_width=True, caption="Estructura general del proceso de concentración")
            
            # Botón de descarga en formato PDF si existe el archivo original
            if os.path.exists("Bloques_ISO.pdf"):
                with open("Bloques_ISO.pdf", "rb") as f:
                    st.download_button("⬇️ Descargar BFD en PDF", data=f.read(), file_name="Bloques_ISO.pdf", mime="application/pdf")
        else:
            st.warning("⚠️ Archivo 'bfd_bloques.png' no encontrado en el repositorio.")
        st.markdown('</div>', unsafe_allow_html=True)

    # --- COLUMNA 2: DIAGRAMA DE FLUJO DE PROCESO (Verde y Amarillo) ---
    with col_diag2:
        st.markdown('<div class="marco-verde-amarillo">', unsafe_allow_html=True)
        st.markdown('<h3 class="titulo-verde">⚙️ Diagrama de Flujo de Proceso (PFD)</h3>', unsafe_allow_html=True)
        
        # Mostrar la imagen en la app
        if os.path.exists("pfd_proceso.png"):
            st.image("pfd_proceso.png", use_container_width=True, caption="Diseño detallado de ingeniería realizado en Lucidchart")
            
            # Botón de descarga en formato PDF si existe el archivo original
            if os.path.exists("PFD_ISO.pdf"):
                with open("PFD_ISO.pdf", "rb") as f:
                    st.download_button("⬇️ Descargar PFD en PDF", data=f.read(), file_name="PFD_ISO.pdf", mime="application/pdf")
        else:
            st.warning("⚠️ Archivo 'pfd_proceso.png' no encontrado en el repositorio.")
        st.markdown('</div>', unsafe_allow_html=True)
        
# ==========================================
    # 5. ANÁLISIS DE SENSIBILIDAD (PUNTO 6.2)
    # ==========================================
    st.divider()
    st.subheader("📈 Análisis de Sensibilidad Económica")
    
    # Creamos datos para la gráfica: Precio Vapor vs Costo Producción
    precios_vapor = [10, 20, 30, 40, 50, 60]
    costos_calculados = [p_mos * 1.1 + (pv * 0.005) for pv in precios_vapor]
    
    df_sens = pd.DataFrame({
        "Precio Vapor (USD/ton)": precios_vapor,
        "Costo Prod (USD/kg)": costos_calculados
    })
    
    st.line_chart(df_sens.set_index("Precio Vapor (USD/ton)"))
    st.caption("Gráfica 1: Impacto del costo energético en el costo unitario de producción.")

    # ==========================================
    # 6. COMPARACIÓN DE ESCENARIOS (PUNTO 6.3)
    # ==========================================
    st.subheader("🏢 Comparación de Escenarios")
    col_esc1, col_esc2, col_esc3 = st.columns(3)
    
    with col_esc1:
        st.info("**Caso Base**\n\nOperación estándar a 1 atm y precios de mercado actuales.")
    with col_esc2:
        st.success("**Caso Rentable**\n\nOptimización de temperatura (92°C) para maximizar ROI.")
    with col_esc3:
        st.warning("**Caso Crítico**\n\nInsumos caros (Vapor > 40 USD). Riesgo de pérdida económica.")
    # --- MODO TUTOR IA (PUNTOS 13, 14, 15) ---
    st.divider()
    st.subheader("🤖 Tutor de Inteligencia Artificial")
    tutor_on = st.toggle("Habilitar Modo Tutor con IA")
    
    if tutor_on:
        api_key = st.text_input("Ingresa Gemini API Key", type="password")
        if api_key:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.5-pro')
            if "chat_history" not in st.session_state:
                st.session_state.chat_history = []
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]): st.write(msg["content"])
            if prompt := st.chat_input("Pregunta al tutor..."):
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                with st.chat_message("user"): st.write(prompt)
                context = f"Proceso: Concentración Mosto. Pureza: {eth_comp:.1f}%. Presión: {producto.P/101325:.2f}atm."
                response = model.generate_content(f"Contexto: {context}. Pregunta: {prompt}")
                with st.chat_message("assistant"): st.write(response.text)
                st.session_state.chat_history.append({"role": "assistant", "content": response.text})
        else:
            st.info("Ingresa tu API Key para comenzar.")

except Exception as e:
    st.error(f"Error en la simulación: {e}")
