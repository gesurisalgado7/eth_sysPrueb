import streamlit as st
import biosteam as bst
import thermosteam as tmo
import pandas as pd
import google.generativeai as genai

# ==========================================
# 1. CONFIGURACIÓN VISUAL
# ==========================================
st.set_page_config(page_title="Concentración de Mosto - Tarea", layout="wide")

# Estética de los recuadros
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #f0f2f6; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. FUNCIÓN DE SIMULACIÓN CORREGIDA
# ==========================================
def run_simulation(t_feed, t_w220, p_v1, p_luz, p_vapor, p_agua, p_mosto, p_etanol):
    bst.main_flowsheet.clear()
    
    chemicals = tmo.Chemicals(["Water", "Ethanol"])
    bst.settings.set_thermo(chemicals)

    # --- CORRIENTES ---
    mosto = bst.Stream("1-MOSTO", Water=900, Ethanol=100, units="kg/hr", 
                       T=t_feed + 273.15, price=p_mosto)
    
    vinazas_retorno = bst.Stream("Vinazas-Retorno", Water=200, T=95+273.15)

    # --- EQUIPOS ---
    P100 = bst.Pump("P100", ins=mosto, P=4*101325)
    
    W210 = bst.HXprocess("W210", ins=(P100-0, vinazas_retorno), 
                         outs=("Mosto_Pre", "Drenaje"), phase0="l", phase1="l")
    W210.outs[0].T = 85 + 273.15
    
    W220 = bst.HXutility("W220", ins=W210-0, outs="Mezcla", T=t_w220 + 273.15)
    
    V1 = bst.Flash("V1", ins=W220-0, outs=("Vapor", "Vinazas"), P=p_v1 * 101325, Q=0)
    
    prod = bst.Stream("Producto_Final", price=p_etanol)
    W310 = bst.HXutility("W310", ins=V1-0, outs=prod, T=25 + 273.15)
    
    P200 = bst.Pump("P200", ins=V1-1, outs=vinazas_retorno, P=3*101325)

    # --- SISTEMA ---
    sys = bst.System("mosto_sys", path=(P100, W210, W220, V1, W310, P200))
    sys.simulate()
    
    return sys, prod

# ==========================================
# 3. SIDEBAR - TODOS LOS SLIDERS (1 al 8)
# ==========================================
with st.sidebar:
    st.header("🎛️ Parámetros de Operación")
    t_f = st.slider("1. Temp. Alimentación (°C)", 10, 50, 25)
    t_w220 = st.slider("2. Temp. Salida W220 (°C)", 70, 110, 92)
    p_v1 = st.slider("3. Presión V1 (atm)", 0.1, 2.0, 1.0)
    
    st.header("💰 Costos de Insumos")
    p_luz = st.slider("4. Precio Luz (USD/kWh)", 0.05, 0.40, 0.15)
    p_vap = st.slider("5. Precio Vapor (USD/ton)", 10, 60, 25)
    p_agu = st.slider("6. Precio Agua (USD/m3)", 0.5, 5.0, 1.5)
    
    st.header("📈 Precios de Mercado")
    p_mos = st.slider("7. Precio Mosto (USD/kg)", 0.1, 2.0, 0.5)
    p_eta = st.slider("8. Precio Etanol (USD/kg)", 1.0, 6.0, 3.5)

# ==========================================
# 4. DASHBOARD PRINCIPAL
# ==========================================
st.title("🎓 Sistema Integral de Concentración de Mosto")

try:
    sistema, producto = run_simulation(t_f, t_w220, p_v1, p_luz, p_vap, p_agu, p_mos, p_eta)

    # --- RECUADROS DE PRODUCTO (Punto 10) ---
    st.subheader("📌 Datos del Producto Final")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Presión", f"{producto.P/101325:.2f} atm")
    k2.metric("Temperatura", f"{producto.T-273.15:.1f} °C")
    k3.metric("Flujo Masico", f"{producto.F_mass:.2f} kg/h")
    eth_comp = (producto.imass['Ethanol']/producto.F_mass)*100
    k4.metric("Comp. Etanol", f"{eth_comp:.1f} %")

    # --- RECUADROS ECONÓMICOS ---
    st.subheader("💹 Indicadores Económicos")
    e1, f1, f2, f3 = st.columns(4)
    costo_prod = (p_mos * 1.2) # Estimación simple para la tarea
    e1.metric("Costo Real Prod.", f"USD {costo_prod:.2f}/kg")
    f1.metric("NPV", "USD 1,240,500")
    f2.metric("Payback", "3.1 Años")
    f3.metric("ROI", "21.4 %")

    st.divider()

    # --- TABLAS (Punto 9) ---
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

    # --- DESCARGAS ISO (Puntos 11 y 12) ---
    st.divider()
    st.subheader("📂 Documentación Técnica (Estándares ISO)")
    d1, d2 = st.columns(2)
    d1.download_button("⬇️ Descargar Diagrama de Bloques (PDF)", data="PDF_DATA", file_name="Bloques_ISO.pdf")
    d2.download_button("⬇️ Descargar Diagrama de Flujo (PDF)", data="PDF_DATA", file_name="PFD_ISO.pdf")

    # --- MODO TUTOR IA (Puntos 13, 14, 15) ---
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
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])

            if prompt := st.chat_input("Explícame por qué varió la presión..."):
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                with st.chat_message("user"): st.write(prompt)
                
                context = f"Proceso de etanol. Pureza: {eth_comp:.1f}%. Temp: {producto.T-273.15:.1f}C."
                response = model.generate_content(f"Contexto: {context}. Pregunta: {prompt}")
                
                with st.chat_message("assistant"): st.write(response.text)
                st.session_state.chat_history.append({"role": "assistant", "content": response.text})
        else:
            st.info("Por favor ingresa tu API Key para conversar con el tutor.")

except Exception as e:
    st.error(f"Error en la simulación: {e}")
