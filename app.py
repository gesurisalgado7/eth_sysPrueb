import streamlit as st
import biosteam as bst
import thermosteam as tmo
import pandas as pd
import google.generativeai as genai

# ==========================================
# 1. CONFIGURACIÓN DE PÁGINA
# ==========================================
st.set_page_config(page_title="Bioetanol Dashboard", layout="wide")

# ==========================================
# 2. FUNCIÓN DE SIMULACIÓN
# ==========================================
def run_simulation(flow_water, flow_eth, temp_feed):
    # Limpia el flowsheet para evitar errores de IDs duplicados
    bst.main_flowsheet.clear()
    
    # Termodinámica básica
    chemicals = tmo.Chemicals(["Water", "Ethanol"])
    bst.settings.set_thermo(chemicals)

    # Definición de Corrientes
    # Usamos variables intermedias para evitar cálculos dentro de BioSTEAM
    t_kelvin = temp_feed + 273.15
    mosto = bst.Stream("MOSTO", Water=flow_water, Ethanol=flow_eth, 
                       units="kg/hr", T=t_kelvin)
    
    vinazas_retorno = bst.Stream("Vinazas_Retorno", Water=200, T=95+273.15)

    # Construcción de la Planta
    P100 = bst.Pump("P100", ins=mosto, P=4*101325)
    
    W210 = bst.HXprocess("W210", ins=(P100-0, vinazas_retorno), 
                         outs=("Mosto_Pre", "Drenaje"), phase0="l", phase1="l")
    W210.outs[0].T = 85 + 273.15
    
    W220 = bst.HXutility("W220", ins=W210-0, outs="Mezcla", T=92+273.15)
    
    V100 = bst.IsenthalpicValve("V100", ins=W220-0, outs="Mezcla_Bif", P=101325)
    
    V1 = bst.Flash("V1", ins=V100-0, outs=("Vapor", "Vinazas"), P=101325, Q=0)
    
    W310 = bst.HXutility("W310", ins=V1-0, outs="Producto", T=25+273.15)
    
    P200 = bst.Pump("P200", ins=V1-1, outs=vinazas_retorno, P=3*101325)

    # Crear sistema y simular
    sys = bst.System("eth_sys", path=(P100, W210, W220, V100, V1, W310, P200))
    sys.simulate()
    
    return sys, W310.outs[0]

# ==========================================
# 3. INTERFAZ DE USUARIO (SIDEBAR)
# ==========================================
st.title("🏭 Planta de Bioetanol | Simulación de Procesos")
st.sidebar.header("📥 Parámetros de Entrada")

f_w = st.sidebar.slider("Flujo de Agua (kg/h)", 500, 1500, 900)
f_e = st.sidebar.slider("Flujo de Etanol (kg/h)", 50, 500, 100)
temp = st.sidebar.slider("Temperatura (°C)", 15, 45, 25)

# ==========================================
# 4. EJECUCIÓN Y VISUALIZACIÓN
# ==========================================
try:
    sistema, prod = run_simulation(f_w, f_e, temp)
    
    # --- MÉTRICAS PRINCIPALES (KPIs) ---
    c1, c2, c3 = st.columns(3)
    
    # Cálculo de pureza seguro
    pureza_val = (prod.imass['Ethanol'] / prod.F_mass) * 100 if prod.F_mass > 0 else 0
    temp_final = prod.T - 273.15

    c1.metric("Pureza Etanol", f"{pureza_val:.2f} %")
    c2.metric("Producción Total", f"{prod.F_mass:.2f} kg/h")
    c3.metric("Temperatura Salida", f"{temp_final:.1f} °C")

    st.divider()

    # --- TABLAS DE RESULTADOS (Lado a Lado) ---
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📊 Balance de Materia")
        materia_data = []
        for s in sistema.streams:
            if s.F_mass > 0.01:
                # Calculamos el % de etanol antes para evitar el error de f-string
                per_eth = (s.imass['Ethanol'] / s.F_mass) * 100
                materia_data.append({
                    "Corriente": s.ID,
                    "Flujo [kg/h]": round(s.F_mass, 2),
                    "% Etanol": f"{per_eth:.1f}%"
                })
        st.dataframe(pd.DataFrame(materia_data), use_container_width=True)

    with col_right:
        st.subheader("⚡ Balance de Energía")
        energia_data = []
        for u in sistema.units:
            # Obtenemos el calor total de los servicios auxiliares
            q_kw = sum(h.duty for h in u.heat_utilities) / 3600 if u.heat_utilities else 0
            if abs(q_kw) > 0.001:
                energia_data.append({
                    "Equipo": u.ID,
                    "Carga [kW]": round(q_kw, 2)
                })
        st.dataframe(pd.DataFrame(energia_data), use_container_width=True)

    # --- DIAGRAMA PFD ---
    st.divider()
    st.subheader("🎨 Diagrama de Flujo (PFD)")
    try:
        # display=False evita que intente abrir una ventana externa en el servidor
        sistema.diagram(file="planta_pfd", format="png", display=False)
        st.image("planta_pfd.png")
    except Exception as e:
        st.info("Nota: El diagrama se visualizará una vez que configures 'packages.txt' con graphviz.")

except Exception as err:
    st.error(f"Hubo un error en la simulación: {err}")

# ==========================================
# 5. INTEGRACIÓN IA (OPCIONAL)
# ==========================================
st.sidebar.divider()
st.sidebar.subheader("🤖 Consultar Tutor IA")
user_key = st.sidebar.text_input("Ingresa Gemini API Key", type="password")

if st.sidebar.button("Analizar Resultados"):
    if user_key:
        try:
            genai.configure(api_key=user_key)
            model = genai.GenerativeModel('gemini-2.5-pro')
            prompt_ia = f"Como ingeniero químico, analiza: Pureza {pureza_val:.1f}%, Producción {prod.F_mass:.1f}kg/h. ¿Sugerencias?"
            response = model.generate_content(prompt_ia)
            st.info(response.text)
        except:
            st.error("Error al conectar con Gemini.")
    else:
        st.sidebar.warning("Falta la API Key")
