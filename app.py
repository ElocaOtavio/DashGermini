import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import os

# --- Configuração da Página ---
st.set_page_config(
    page_title="TESTE DE CARGA - CSAT",
    layout="wide"
)

st.title("🔬 Teste Final: Carregando a Planilha de CSAT")

# --- Função de Carregamento de Dados ---
@st.cache_data(ttl=30)
def carregar_dados_csat_teste(url, headers):
    try:
        st.write("Tentando baixar dados da URL de CSAT...")
        resposta = requests.get(url, headers=headers)
        resposta.raise_for_status()
        st.success(f"Download concluído com sucesso! Status: {resposta.status_code}")
        
        st.write("Tentando ler o arquivo Excel...")
        df = pd.read_excel(BytesIO(resposta.content))
        st.success("Arquivo Excel lido com sucesso!")
        
        return df
    except Exception as e:
        st.error(f"Ocorreu um erro na função de carregamento: {e}")
        return pd.DataFrame()

# --- Carregamento ---
URL_CSAT = st.secrets.get("CSAT_URL")
HEADERS_CSAT = {"DeskManager": st.secrets.get("CSAT_TOKEN")}

if not URL_CSAT or not HEADERS_CSAT.get("DeskManager"):
    st.error("As secrets 'CSAT_URL' ou 'CSAT_TOKEN' não foram encontradas!")
else:
    df_csat_raw = carregar_dados_csat_teste(URL_CSAT, HEADERS_CSAT)

    st.markdown("---")

    if not df_csat_raw.empty:
        st.header("Resultado do Carregamento da Planilha de CSAT")
        st.write(f"**Total de linhas carregadas:** `{len(df_csat_raw)}`")
        
        st.subheader("Nomes das Colunas Encontradas:")
        st.write(df_csat_raw.columns.tolist())
        
        st.subheader("Amostra dos Dados (5 primeiras linhas):")
        st.dataframe(df_csat_raw.head())
    else:
        st.error("A planilha de CSAT foi carregada, mas está vazia ou ocorreu um erro na leitura.")
