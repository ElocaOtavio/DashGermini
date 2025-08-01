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

# --- Funções de Carregamento de Dados ---
@st.cache_data(ttl=30)
def carregar_dados_operacionais(url, headers):
    try:
        resposta = requests.get(url, headers=headers)
        resposta.raise_for_status()
        df = pd.read_excel(BytesIO(resposta.content))
        
        # Limpeza agressiva das chaves
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

        # Limpeza agressiva das chaves
        if 'Código do Chamado' in df.columns:
            df['Código do Chamado'] = df['Código do Chamado'].astype(str).str.strip()
        if 'Operador' in df.columns:
            df['Operador'] = df['Operador'].astype(str).str.strip()

        coluna_avaliacao = 'Atendimento - CES e CSAT - [ANALISTA] Como você avalia a qualidade do atendimento prestado pelo analista neste chamado?'
        if coluna_avaliacao in df.columns:
            df.rename(columns={coluna_avaliacao: 'Avaliacao_Qualidade'}, inplace=True)
            df['Avaliacao_Qualidade'] = df['Avaliacao_Qualidade'].astype(str)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados de CSAT: {e}")
        return pd.DataFrame()

st.title("🔬 Diagnóstico Focado no Cálculo de CSAT")

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
    st.header("1. Junção (Merge) dos Dados")
    df_merged = pd.merge(
        df_operacional_raw,
        df_csat_raw,
        left_on='Nº Chamado',
        right_on='Código do Chamado',
        how='left'
    )
    if 'Avaliacao_Qualidade' in df_merged.columns:
        df_merged['Nota'] = pd.to_numeric(df_merged['Avaliacao_Qualidade'].str.strip().str[0], errors='coerce')
    st.success("Junção das planilhas concluída.")

    # --- Análise para um operador específico ---
    analista_exemplo = "Caio Moraes"
    st.header(f"2. Análise para o operador: '{analista_exemplo}'")
    
    df_analista = df_merged[df_merged['Nome Completo do Operador'] == analista_exemplo].copy()

    if df_analista.empty:
        st.warning(f"Nenhum dado encontrado para '{analista_exemplo}' no dataframe mesclado.")
    else:
        st.write(f"Foram encontrados {len(df_analista)} registros para este operador.")
        
        # --- Cálculo dos componentes do CSAT ---
        st.subheader("3. Componentes do Cálculo de CSAT")
        
        df_avaliacoes_total = df_analista.dropna(subset=['Nota'])
        csat_avaliacoes = len(df_avaliacoes_total)
        st.write(f"**Total de Avaliações Contadas (denominador):** `{csat_avaliacoes}`")

        df_avaliacoes_satisfeitas = df_analista[df_analista['Nota'] >= 4]
        csat_satisfeitos = len(df_avaliacoes_satisfeitas)
        st.write(f"**Notas Boas (>=4) Contadas (numerador):** `{csat_satisfeitos}`")
        
        percent_csat = (csat_satisfeitos / csat_avaliacoes * 100) if csat_avaliacoes > 0 else 0
        st.metric("Resultado Final do CSAT:", f"{percent_csat:.2f}%")

        st.markdown("---")

        # --- Exibição das tabelas usadas ---
        st.subheader("4. Tabela de Avaliações Encontradas para o Operador")
        st.write("Se esta tabela estiver vazia, a junção não encontrou pesquisas para os chamados deste operador.")
        st.dataframe(df_avaliacoes_total[['Nº Chamado', 'Nome Completo do Operador', 'Avaliacao_Qualidade', 'Nota']])
