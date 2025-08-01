import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import os

# --- Configuração da Página ---
st.set_page_config(
    page_title="Teste de CSAT - Correção Final",
    layout="wide"
)

# --- Funções de Carregamento (versão mais recente e corrigida) ---
@st.cache_data(ttl=30)
def carregar_dados_operacionais(url, headers):
    try:
        resposta = requests.get(url, headers=headers)
        resposta.raise_for_status()
        df = pd.read_excel(BytesIO(resposta.content))
        if 'Nº Chamado' in df.columns:
            df['Nº Chamado'] = df['Nº Chamado'].astype(str).str.strip()
        if 'Nome Completo do Operador' in df.columns:
            df['Nome Completo do Operador'] = df['Nome Completo do Operador'].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados operacionais: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def carregar_dados_csat(url, headers):
    try:
        resposta = requests.get(url, headers=headers)
        resposta.raise_for_status()
        df = pd.read_excel(BytesIO(resposta.content))
        if 'Código do Chamado' in df.columns:
            df['Código do Chamado'] = df['Código do Chamado'].astype(str).str.strip()
        coluna_avaliacao = 'Atendimento - CES e CSAT - [ANALISTA] Como você avalia a qualidade do atendimento prestado pelo analista neste chamado?'
        if coluna_avaliacao in df.columns:
            df.rename(columns={coluna_avaliacao: 'Avaliacao_Qualidade'}, inplace=True)
            df['Avaliacao_Qualidade'] = df['Avaliacao_Qualidade'].astype(str)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados de CSAT: {e}")
        return pd.DataFrame()

st.title("🔬 Teste Final de Cálculo de CSAT")

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
    # --- Filtro Simples ---
    st.sidebar.header("Filtro")
    lista_analistas = sorted(df_operacional_raw['Nome Completo do Operador'].dropna().unique())
    analista_selecionado = st.sidebar.multiselect(
        "Selecione o(s) Analista(s)",
        options=lista_analistas,
        default=lista_analistas[:3]
    )
    
    df_operacional_filtrado = df_operacional_raw
    if analista_selecionado:
        df_operacional_filtrado = df_operacional_raw[df_operacional_raw['Nome Completo do Operador'].isin(analista_selecionado)]

    # --- Merge ---
    st.header("1. Junção (Merge) dos Dados")
    df_merged = pd.merge(
        df_operacional_filtrado,
        df_csat_raw,
        left_on='Nº Chamado',
        right_on='Código do Chamado',
        how='left'
    )
    
    # --- CORREÇÃO DEFINITIVA AQUI ---
    if 'Avaliacao_Qualidade' in df_merged.columns:
        # Usando regex para extrair o primeiro dígito de forma robusta
        df_merged['Nota'] = df_merged['Avaliacao_Qualidade'].str.extract(r'(\d)', expand=False)
        df_merged['Nota'] = pd.to_numeric(df_merged['Nota'], errors='coerce')
    
    st.success(f"Junção das planilhas concluída. Total de {len(df_merged)} registros para os analistas selecionados.")
    
    # --- Cálculos ---
    st.header("2. Resultados do Cálculo para a Seleção Atual")
    
    csat_avaliacoes = df_merged['Nota'].count()
    csat_satisfeitos = df_merged[df_merged['Nota'] >= 4].shape[0]
    percent_csat = (csat_satisfeitos / csat_avaliacoes * 100) if csat_avaliacoes > 0 else 0
    
    chamados_com_pesquisa = df_merged[df_merged['Possui Pesquisa de Satisfação'] == 'Sim'].shape[0]
    percent_resp = (csat_avaliacoes / chamados_com_pesquisa * 100) if chamados_com_pesquisa > 0 else 0

    col1, col2 = st.columns(2)
    col1.metric("CSAT Calculado", f"{percent_csat:.2f}%")
    col2.metric("% de Resposta da Pesquisa", f"{percent_resp:.2f}%")
    
    st.write(f" - **Total de Avaliações Contadas:** {csat_avaliacoes}")
    st.write(f" - **Total de Notas Boas (>=4):** {csat_satisfeitos}")
    st.write(f" - **Total de Chamados com Pesquisa Enviada:** {chamados_com_pesquisa}")

    st.markdown("---")
    st.header("3. Amostra dos Dados Após a Junção (com nota)")
    st.write("Verifique se a coluna 'Nota' agora está sendo preenchida corretamente.")
    st.dataframe(df_merged.dropna(subset=['Avaliacao_Qualidade'])[[
        'Nº Chamado', 'Nome Completo do Operador', 'Possui Pesquisa de Satisfação', 
        'Código do Chamado', 'Operador', 'Avaliacao_Qualidade', 'Nota'
    ]])
