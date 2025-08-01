import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import os

# --- Configuração da Página ---
st.set_page_config(layout="wide")

st.title("🔬 Ferramenta de Diagnóstico de Colunas")

@st.cache_data(ttl=30) # Cache baixo para sempre pegar dados novos
def carregar_dados_diagnostico(url, headers):
    try:
        resposta = requests.get(url, headers=headers)
        resposta.raise_for_status()
        arquivo = BytesIO(resposta.content)
        df = pd.read_excel(arquivo)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar os dados: {e}")
        return pd.DataFrame()

# Carregando dados operacionais
URL_OPERACIONAL = st.secrets.get("ELOCA_URL")
HEADERS_OPERACIONAL = {"DeskManager": st.secrets.get("DESKMANAGER_TOKEN")}
df_operacional = carregar_dados_diagnostico(URL_OPERACIONAL, HEADERS_OPERACIONAL)

if not df_operacional.empty:
    st.header("Colunas da Planilha Operacional")
    st.info("Por favor, copie a lista de nomes de colunas abaixo e me envie.")
    st.write(df_operacional.columns.tolist())
    
    st.header("Amostra dos Dados Operacionais (5 primeiras linhas)")
    st.dataframe(df_operacional.head())
else:
    st.warning("Não foi possível carregar os dados operacionais.")

# Carregando dados de CSAT
URL_CSAT = st.secrets.get("CSAT_URL")
HEADERS_CSAT = {"DeskManager": st.secrets.get("CSAT_TOKEN")}
df_csat = carregar_dados_diagnostico(URL_CSAT, HEADERS_CSAT)

if not df_csat.empty:
    st.header("Colunas da Planilha de CSAT")
    st.info("Por favor, copie também esta lista de nomes de colunas e me envie.")
    st.write(df_csat.columns.tolist())
    
    st.header("Amostra dos Dados de CSAT (5 primeiras linhas)")
    st.dataframe(df_csat.head())
else:
    st.warning("Não foi possível carregar os dados de CSAT.")
