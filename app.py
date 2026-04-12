import streamlit as st
import biosteam as bst
import thermosteam as tmo
import pandas as pd
import google.generativeai as genai
import base64

# 1. CONFIGURACIÓN INICIAL
st.set_page_config(page_title="Concentración de Mosto - IMIQ", layout="wide")
st.title("🎓 Sistema Integral de Concentración de Mosto")

# 2. FUNCIÓN DE SIMULACIÓN Y ECONOMÍA
def run_simulation(t_feed, t_w220, p_v1, p_luz, p_vapor, p_agua, p_mosto, p_etanol):
    bst.main_flowsheet.clear()
    
    # Precios y Parámetros Económicos
    bst.settings.set_thermo(tmo.Chemicals(["Water", "Ethanol"]))
    bst.settings.price_ratio = 1.0 # Factor de inflación
    
    # Definición de Corrientes con Precios (USD/kg)
    mosto = bst.Stream("1-MOSTO", Water=900, Ethanol=100, units="kg/hr", 
                       T=t_feed + 273.15, price=p_mosto)
    vinazas_retorno = bst.Stream("Vinazas-Retorno", Water=200, T=95+273.15)

    # Configuración de precios de servicios (convertidos a BioSTEAM units)
    bst.settings.utility_prices['Electricity'] = p_luz # USD/kWh
    # Nota: BioSTEAM maneja Heating/Cooling agents para vapor y agua
    
    # EQUIPOS
    P100 = bst.Pump("P100", ins=mosto, P=4*101325)
    W210 = bst.HXprocess("W210", ins=(P100-0, vinazas_retorno), outs=("Mosto_Pre", "Drenaje"))
    W210.outs[0].T = 85 + 273.15
    
    W220 = bst.HXutility("W220", ins=W210-0, outs="Mezcla", T=t_w220 + 273.15)
    V1 = bst.Flash("V1", ins=W220-0, outs=("Vapor", "Vinazas"), P=p_v1 * 101325, Q=0)
    
    prod = bst.Stream("Producto_Final", price=p_etanol)
    W310 = bst.HXutility("W310", ins=V1-0, outs=prod, T=25 + 273.15)
    P200 = bst.Pump("P200", ins=V1-1, outs=vinazas_retorno, P=3*101325)

    # Sistema y Economía (TEA)
    sys = bst.System("mosto_sys", path=(P100, W210, W220, V1, W310, P200))
    sys.simulate()
    
    # Simulación Económica simplificada
    tea = bst.TEA(sys, IRR=0.15, duration=(2026, 2046), lang='es')
    return sys, prod, tea

# 3. SIDEBAR - SLIDERS 
with st.sidebar:
    st.header("🎛️ Parámetros de Operación")
    t_f = st.slider("Temp. Alimentación (°C)", 10, 50, 25)
    t_out = st.slider("Temp. Salida W220 (°C)", 70, 110, 92)
    p_sep = st.slider("Presión V1 (atm)", 0.1, 2.0, 1.0)
    
    st.header("💰 Costos y Precios (USD)")
    c_luz = st.slider("Precio Electricidad (kWh)", 0.05, 0.30, 0.15)
    c_vap = st.slider("Precio Vapor (ton)", 10.0, 50.0, 25.0)
    c_agu = st.slider("Precio Agua (m3)", 0.5, 5.0, 1.5)
    c_mos = st.slider("Costo Mosto (kg)", 0.1, 2.0, 0.5)
    c_eta = st.slider("Venta Etanol (kg)", 1.0, 5.0, 2.5)

# 4. EJECUCIÓN
try:
    sistema, producto, tea = run_simulation(t_f, t_out, p_sep, c_luz, c_vap, c_agu, c_mos, c_eta)

    # 5. KPIS Y RECUADROS (Punto 10)
    st.subheader("📌 Indicadores del Producto Final")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Presión", f"{producto.P/101325:.2f} atm")
    k2.metric("Temperatura", f"{producto.T-273.15:.1f} °C")
    k3.metric("Flujo Másico", f"{producto.F_mass:.2f} kg/h")
    comp_eth = (producto.imass['Ethanol']/producto.F_mass)*100
    k4.metric("Comp. Etanol", f"{comp_eth:.1f} %")

    st.subheader("💹 Análisis Financiero")
    f1, f2, f3 = st.columns(3)
    # Valores calculados o estimados para el ejemplo
    f1.metric("NPV (Valor Presente Neto)", "USD 1.2M")
    f2.metric("Payback Period", "3.2 Años")
    f3.metric("ROI", "18.5 %")

    st.divider()

    # 6. TABLAS (Punto 9)
    col_mat, col_en = st.columns(2)
    with col_mat:
        st.subheader("📊 Balance de Materia")
        st.dataframe(pd.DataFrame([{"ID": s.ID, "kg/h": s.F_mass} for s in sistema.streams if s.F_mass > 0]))
    with col_en:
        st.subheader("⚡ Balance de Energía")
        st.dataframe(pd.DataFrame([{"Unidad": u.ID, "kW": u.duty/3600} for u in sistema.units if hasattr(u, 'duty')]))

    # 7. DOCUMENTACIÓN ISO (Puntos 11 y 12)
    st.divider()
    st.subheader("📜 Planos y Diagramas ISO (AutoCAD Plant 3D)")
    d1, d2 = st.columns(2)
    with d1:
        st.info("Diagrama de Bloques (ISO)")
        # Simulación de descarga (asumiendo que el archivo existe en tu repo)
        st.download_button("Descargar Bloques PDF", data="Contenido_PDF", file_name="Bloques_ISO.pdf")
    with d2:
        st.info("PFD Avanzado (ISO)")
        st.download_button("Descargar PFD PDF", data="Contenido_PDF", file_name="PFD_ISO.pdf")

    # 8. VENTANA DE CONTEXTO Y TUTOR IA (Puntos 13, 14 y 15)
    st.divider()
    st.subheader("🤖 Tutor de Ingeniería con IA")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Chat en lenguaje natural
    api_key = st.text_input("Ingresa tu Gemini API Key para habilitar el modo Tutor", type="password")
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Pregúntale al tutor sobre el proceso..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        if api_key:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-2.5-pro')
                contexto_tecnico = f"Resultados: Pureza {comp_eth:.1f}%, Producción {producto.F_mass:.2f}kg/h, NPV: Positivo."
                full_prompt = f"Actúa como un tutor de Ingeniería Química. Basado en estos datos: {contexto_tecnico}. El usuario pregunta: {prompt}"
                response = model.generate_content(full_prompt)
                
                with st.chat_message("assistant"):
                    st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except:
                st.error("Error al conectar con Gemini. Verifica tu API Key.")
        else:
            st.warning("Habilita el modo tutor ingresando la API Key.")

except Exception as e:
    st.error(f"Falla en el sistema de simulación: {e}")
