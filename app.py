import streamlit as st
import biosteam as bst
import thermosteam as tmo
import pandas as pd
import google.generativeai as genai

# Configuración visual
st.set_page_config(page_title="BioSTEAM Dashboard", layout="wide")

# Lógica de la simulación
def run_simulation(flow_water, flow_eth, temp_feed):
    bst.main_flowsheet.clear()
    chemicals = tmo.Chemicals(["Water", "Ethanol"])
    bst.settings.set_thermo(chemicals)

    mosto = bst.Stream("MOSTO", Water=flow_water, Ethanol=flow_eth, 
                       units="kg/hr", T=temp_feed + 273.15)
    vinazas_retorno = bst.Stream("Vinazas_Retorno", Water=200, T=95+273.15)

    P100 = bst.Pump("P100", ins=mosto, P=4*101325)
    W210 = bst.HXprocess("W210", ins=(P100-0, vinazas_retorno), 
                         outs=("Mosto_Pre", "Drenaje"), phase0="l", phase1="l")
    W210.outs[0].T = 85 + 273.15
    W220 = bst.HXutility("W220", ins=W210-0, outs="Mezcla", T=92+273.15)
    V100 = bst.IsenthalpicValve("V100", ins=W220-0, outs="Mezcla_Bif", P=101325)
    V1 = bst.Flash("V1", ins=V100-0, outs=("Vapor", "Vinazas"), P=101325, Q=0)
    W310 = bst.HXutility("W310", ins=V1-0, outs="Producto", T=25+273.15)
    P200 = bst.Pump("P200", ins=V1-1, outs=vinazas_retorno, P=3*101325)

    sys = bst.System("eth_sys", path=(P100, W210, W220, V100, V1, W310, P200))
    sys.simulate()
    return sys, W310.outs[0]

# Interfaz
st.title("🏭 Planta de Bioetanol - Simulación Química")

# Sidebar
st.sidebar.header("Entradas")
f_w = st.sidebar.slider("Agua (kg/h)", 500, 1500, 900)
f_e = st.sidebar.slider("Etanol (kg/h)", 50, 500, 100)
t_f = st.sidebar.slider("Temp (°C)", 15, 40, 25)

try:
    sistema, producto = run_simulation(f_w, f_e, t_f)
    
    # KPIs
    c1, c2, c3 = st.columns(3)
    pureza = (producto.imass['Ethanol']/producto.F_mass)*100
    c1.metric("Pureza Etanol", f"{pureza:.1f}%")
    c2.metric("Producción Total", f"{producto.F_mass:.1f} kg/h")
    c3.metric("Temp. Producto", f"{producto.T-273.15:.1f} °C")

    st.divider()

    # Tablas Lado a Lado
    col_mat, col_en = st.columns(2)
    
    with col_mat:
        st.subheader("Balance de Materia")
        df_m = pd.DataFrame([{"ID": s.ID, "Flujo": f"{s.F_mass:.2f}"} for s in sistema.streams if s.F_mass > 0])
        st.dataframe(df_m, use_container_width=True)

    with col_en:
        st.subheader("Balance de Energía")
        df_e = pd.DataFrame([{"Equipo": u.ID, "kW": round(sum(h.duty for h in u.heat_utilities)/3600, 2)} 
                            for u in sistema.units if u.heat_utilities])
        st.dataframe(df_e, use_container_width=True)

    # Diagrama (Con corrección de visualización)
    st.divider()
    st.subheader("Diagrama de Proceso (PFD)")
    try:
        sistema.diagram(file="pfd", format="png", display=False)
        st.image("pfd.png")
    except:
        st.error("Error al generar imagen. Asegúrate de tener packages.txt con 'graphviz'.")

except Exception as err:
    st.error(f"Error: {err}")
