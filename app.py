import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import os

st.set_page_config(layout="wide")

st.title("🔬 Ferramenta de Diagnóstico Fiiinal de CSAT")

# Funções de carregamento (mantidas da versão anterior)
@st.cache_data(ttl=30)
def carregar_dados_operacionais(url, headers):
    try:
        resposta = requests.get(url, headers=headers)
        resposta.raise_for_status()
        df = pd.read_excel(arquivo_bytes=resposta.content)
        if 'Nº Chamado' in df.columns:
            df['Nº Chamado'] = df['Nº Chamado'].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados operacionais: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def carregar_dados_csat(url, headers):
    try:
        resposta = requests.get(url, headers=headers)
        resposta.raise_for_status()
        df = pd.read_excel(arquivo_bytes=resposta.content)
        if 'Código do Chamado' in df.columns:
            df['Código do Chamado'] = df['Código do Chamado'].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados de CSAT: {e}")
        return pd.DataFrame()

# Carregamento
URL_OPERACIONAL = st.secrets.get("ELOCA_URL")
HEADERS_OPERACIONAL = {"DeskManager": st.secrets.get("DESKMANAGER_TOKEN")}
URL_CSAT = st.secrets.get("CSAT_URL")
HEADERS_CSAT = {"DeskManager": st.secrets.get("CSAT_TOKEN")}

df_operacional_raw = carregar_dados_operacionais(URL_OPERACIONAL, HEADERS_OPERACIONAL)
df_csat_raw = carregar_dados_csat(URL_CSAT, HEADERS_CSAT)

st.info("Este é um script de diagnóstico. Ele vai nos ajudar a encontrar o problema com o CSAT.")

if df_operacional_raw.empty or df_csat_raw.empty:
    st.error("Não foi possível carregar uma ou ambas as planilhas. Verifique as URLs e Tokens nos Secrets.")
else:
    # 1. Pegar um analista como exemplo
    analista_exemplo = "Caio Moraes"
    df_analista_op = df_operacional_raw[df_operacional_raw['Nome Completo do Operador'] == analista_exemplo]

    st.subheader(f"1. Análise para o operador: {analista_exemplo}")
    
    if df_analista_op.empty:
        st.warning(f"Não foram encontrados chamados para o operador '{analista_exemplo}'. O nome pode estar incorreto.")
    else:
        # 2. Mostrar chaves de junção de cada lado
        st.write("**Chamados do operador (da planilha operacional):**")
        st.dataframe(df_analista_op[['Nº Chamado', 'Nome Completo do Operador', 'Possui Pesquisa de Satisfação']].head(10))
        
        chamados_com_pesquisa = df_analista_op[df_analista_op['Possui Pesquisa de Satisfação'] == 'Sim']
        st.write(f"Destes, **{chamados_com_pesquisa.shape[0]}** chamados deveriam ter uma pesquisa.")

        lista_chamados_op = chamados_com_pesquisa['Nº Chamado'].tolist()
        st.write("**IDs dos chamados do operador que deveriam ter pesquisa:**")
        st.write(lista_chamados_op[:20]) # Mostra os 20 primeiros
        
        st.markdown("---")

        st.write("**Pesquisas (da planilha de CSAT):**")
        st.dataframe(df_csat_raw[['Código do Chamado', 'Operador']].head(10))
        lista_chamados_csat = df_csat_raw['Código do Chamado'].tolist()
        st.write("**IDs dos chamados na planilha de CSAT:**")
        st.write(lista_chamados_csat[:20]) # Mostra os 20 primeiros

        # 3. Encontrar a intersecção
        st.markdown("---")
        st.subheader("2. Verificação de Correspondência")
        
        set_op = set(lista_chamados_op)
        set_csat = set(lista_chamados_csat)
        
        correspondencias = set_op.intersection(set_csat)
        
        st.write(f"Encontramos **{len(correspondencias)}** códigos de chamado correspondentes entre os chamados do analista (com pesquisa) e a planilha de CSAT.")
        
        if correspondencias:
            st.write("Exemplos de códigos que deram 'match':")
            st.write(list(correspondencias)[:10])
            st.success("Diagnóstico: A junção deveria funcionar! O problema pode ser outro.")
        else:
            st.error("Diagnóstico: NENHUMA correspondência encontrada! O formato dos códigos pode estar diferente ou não há pesquisas para os chamados deste operador nos dados carregados.")
