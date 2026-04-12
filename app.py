import streamlit as st
import biosteam as bst
import thermosteam as tmo
import pandas as pd
import google.generativeai as genai

def run_simulation(flow_water, flow_eth, temp_feed):
    # CRÍTICO: Limpia el flujo de trabajo anterior para evitar IDs duplicados
    bst.main_flowsheet.clear() 
    
    # Configuración Termodinámica
    chemicals = tmo.Chemicals(["Water", "Ethanol"])
    bst.settings.set_thermo(chemicals)

    # Definición de Corrientes con parámetros dinámicos
    mosto = bst.Stream("MOSTO", Water=flow_water, Ethanol=flow_eth, 
                       units="kg/hr", T=temp_feed + 273.15)
    
    vinazas_retorno = bst.Stream("Vinazas_Retorno", Water=200, T=95+273.15)

    # Construcción de Equipos (Lógica original encapsulada)
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
    return sys
