import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import os

# --- Configuração da Página ---
st.set_page_config(
    page_title="Diagnóstico de CSAT",
    layout="wide"
)

# --- Funções de Carregamento (versão mais recente e corrigida) ---
@st.cache_data(ttl=30)
def carregar_dados_operacionais(url, headers):
    try:
        resposta = requests.get(url, headers=headers)
        resposta.raise_for_status()
        arquivo = BytesIO(resposta.content)
        df = pd.read_excel(arquivo)
        if 'Nº Chamado' in df.columns:
            df['Nº Chamado'] = df['Nº Chamado'].astype(str).str.strip()
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=30)
def carregar_dados_csat(url, headers):
    try:
        resposta = requests.get(url, headers=headers)
        resposta.raise_for_status()
        arquivo = BytesIO(resposta.content)
        df = pd.read_excel(arquivo)
        if 'Código do Chamado' in df.columns:
            df['Código do Chamado'] = df['Código do Chamado'].astype(str).str.strip()
        coluna_avaliacao = 'Atendimento - CES e CSAT - [ANALISTA] Como você avalia a qualidade do atendimento prestado pelo analista neste chamado?'
        if coluna_avaliacao in df.columns:
            df.rename(columns={coluna_avaliacao: 'Avaliacao_Qualidade'}, inplace=True)
            df['Avaliacao_Qualidade'] = df['Avaliacao_Qualidade'].astype(str)
        return df
    except Exception:
        return pd.DataFrame()

st.title("🔬 Diagnóstico Final do Cálculo de CSAT")

# --- Carregamento ---
URL_OPERACIONAL = st.secrets.get("ELOCA_URL")
HEADERS_OPERACIONAL = {"DeskManager": st.secrets.get("DESKMANAGER_TOKEN")}
URL_CSAT = st.secrets.get("CSAT_URL")
HEADERS_CSAT = {"DeskManager": st.secrets.get("CSAT_TOKEN")}

df_operacional_raw = carregar_dados_operacionais(URL_OPERACIONAL, HEADERS_OPERACIONAL)
df_csat_raw = carregar_dados_csat(URL_CSAT, HEADERS_CSAT)

if df_operacional_raw.empty or df_csat_raw.empty:
    st.error("Falha ao carregar uma ou ambas as planilhas.")
else:
    # --- Merge ---
    df_merged = pd.merge(df_operacional_raw, df_csat_raw, left_on='Nº Chamado', right_on='Código do Chamado', how='left')
    if 'Avaliacao_Qualidade' in df_merged.columns:
        df_merged['Nota'] = pd.to_numeric(df_merged['Avaliacao_Qualidade'].str.strip().str[0], errors='coerce')

    # --- Análise para um operador específico ---
    analista_exemplo = "Caio Moraes"
    st.header(f"Analisando dados para: {analista_exemplo}")
    
    df_analista = df_merged[df_merged['Nome Completo do Operador'] == analista_exemplo]

    if df_analista.empty:
        st.warning(f"Nenhum dado encontrado para '{analista_exemplo}' no dataframe mesclado.")
    else:
        # --- Cálculo dos componentes do CSAT ---
        st.subheader("1. Componentes do Cálculo de CSAT")
        
        # Total de avaliações (todas as notas não-nulas)
        df_avaliacoes_total = df_analista.dropna(subset=['Nota'])
        csat_avaliacoes = len(df_avaliacoes_total)
        st.write(f"**Total de Avaliações Contadas (denominador):** `{csat_avaliacoes}`")

        # Total de notas satisfeitas (>= 4)
        df_avaliacoes_satisfeitas = df_analista[df_analista['Nota'] >= 4]
        csat_satisfeitos = len(df_avaliacoes_satisfeitas)
        st.write(f"**Notas Boas (>=4) Contadas (numerador):** `{csat_satisfeitos}`")
        
        # Fórmula
        percent_csat = (csat_satisfeitos / csat_avaliacoes * 100) if csat_avaliacoes > 0 else 0
        st.metric("CSAT Calculado", f"{percent_csat:.2f}%")

        st.markdown("---")

        # --- Exibição das tabelas usadas ---
        st.subheader("2. Tabelas Usadas para os Cálculos")
        
        st.write("**Tabela usada para contar o TOTAL de avaliações (`csat_avaliacoes`):**")
        st.dataframe(df_avaliacoes_total[['Nº Chamado', 'Nome Completo do Operador', 'Avaliacao_Qualidade', 'Nota']])
        
        st.write("**Tabela usada para contar as NOTAS BOAS (`csat_satisfeitos`):**")
        st.dataframe(df_avaliacoes_satisfeitas[['Nº Chamado', 'Nome Completo do Operador', 'Avaliacao_Qualidade', 'Nota']])
