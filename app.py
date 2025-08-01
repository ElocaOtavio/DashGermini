import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(
    page_title="Dashboard de Indicadores",
    page_icon="📊",
    layout="wide"
)

# --- Funções de Carregamento e Tratamento de Dados ---

@st.cache_data(ttl=3600) # Cache de 1 hora
def carregar_dados_operacionais(url, headers):
    try:
        resposta = requests.get(url, headers=headers)
        resposta.raise_for_status()
        arquivo = BytesIO(resposta.content)
        df = pd.read_excel(arquivo)
        for col in ['Data de Criação', 'Data de Finalização']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        for col in ['Tempo Útil até o Primeiro Atendimento', 'Tempo Útil até o Segundo Atendimento']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados operacionais: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600) # Cache de 1 hora
def carregar_dados_csat(url, headers):
    try:
        resposta = requests.get(url, headers=headers)
        resposta.raise_for_status()
        arquivo = BytesIO(resposta.content)
        df = pd.read_excel(arquivo)
        coluna_avaliacao = 'Atendimento - CES e CSAT - [ANALISTA] Como você avalia a qualidade do atendimento prestado pelo analista neste chamado?'
        if coluna_avaliacao not in df.columns:
            st.warning(f"Coluna de avaliação '{coluna_avaliacao}' não encontrada no CSAT.")
            return pd.DataFrame()
        df.rename(columns={coluna_avaliacao: 'Avaliacao_Qualidade'}, inplace=True)
        df['Avaliacao_Qualidade'] = df['Avaliacao_Qualidade'].astype(str)
        df['prioridade_avaliacao'] = df['Avaliacao_Qualidade'].apply(
            lambda x: 1 if x.strip().startswith('Ótimo') else (2 if x.strip().startswith('Bom') else 3)
        )
        df_sorted = df.sort_values(by=['Código do Chamado', 'prioridade_avaliacao'])
        df_final = df_sorted.drop_duplicates(subset='Código do Chamado', keep='first')
        return df_final.drop(columns=['prioridade_avaliacao'])
    except Exception as e:
        st.error(f"Erro ao carregar dados de CSAT: {e}")
        return pd.DataFrame()

# --- Carregamento dos Dados ---
URL_OPERACIONAL = st.secrets.get("ELOCA_URL")
HEADERS_OPERACIONAL = {"DeskManager": st.secrets.get("DESKMANAGER_TOKEN")}
URL_CSAT = st.secrets.get("CSAT_URL")
HEADERS_CSAT = {"DeskManager": st.secrets.get("CSAT_TOKEN")}

df_operacional_raw = carregar_dados_operacionais(URL_OPERACIONAL, HEADERS_OPERACIONAL)
df_csat_raw = carregar_dados_csat(URL_CSAT, HEADERS_CSAT)

# --- Barra Lateral de Filtros ---
st.sidebar.header("Filtros Globais")

if not df_operacional_raw.empty:
    data_min = df_operacional_raw['Data de Criação'].min().date()
    data_max = df_operacional_raw['Data de Criação'].max().date()
    
    data_selecionada = st.sidebar.date_input(
        "Selecione o Período",
        value=(data_min, data_max),
        min_value=data_min,
        max_value=data_max,
    )
    if len(data_selecionada) == 2:
        start_date, end_date = pd.to_datetime(data_selecionada[0]), pd.to_datetime(data_selecionada[1]).replace(hour=23, minute=59, second=59)
        df_operacional = df_operacional_raw[df_operacional_raw['Data de Criação'].between(start_date, end_date)]
    else:
        df_operacional = df_operacional_raw.copy()

    lista_analistas = sorted(df_operacional['Nome Completo do Operador'].dropna().unique())
    analista_selecionado = st.sidebar.multiselect(
        "Selecione o(s) Analista(s)",
        options=lista_analistas,
        default=lista_analistas
    )
    df_operacional = df_operacional[df_operacional['Nome Completo do Operador'].isin(analista_selecionado)]
else:
    df_operacional = pd.DataFrame()
    st.sidebar.warning("Dados operacionais não disponíveis.")


# --- Navegação Principal ---
st.sidebar.title("Navegação")
paginas = [
    "Visão Geral",
    "Desempenho por Analista",
    "Análise Temporal (TMA/TME)",
    "Análise de CSAT",
    "Base de Dados Completa"
]
pagina_selecionada = st.sidebar.radio("Escolha a página", paginas)

# --- Merge dos Dados ---
if not df_operacional.empty and not df_csat_raw.empty:
    df_merged = pd.merge(
        df_operacional, 
        df_csat_raw, 
        left_on='Nº Chamado', 
        right_on='Código do Chamado', 
        how='left'
    )
    df_merged['Nota'] = pd.to_numeric(df_merged['Avaliacao_Qualidade'].str.strip().str[0], errors='coerce')
else:
    df_merged = df_operacional.copy()
    if 'Nota' not in df_merged.columns:
        df_merged['Nota'] = pd.NA

# --- Conteúdo das Páginas ---

if pagina_selecionada == "Visão Geral":
    st.title(" dashboards : Visão Geral dos Indicadores")

    if not df_operacional.empty:
        total_chamados = df_operacional.shape[0]
        sla_atendimento_ok = df_operacional[df_operacional['SLA de Primeiro Atendimento Expirado'] == 'Não'].shape[0]
        sla_solucao_ok = df_operacional[df_operacional['SLA de Solução Expirado'] == 'Não'].shape[0]
        
        percent_sla_atendimento = (sla_atendimento_ok / total_chamados * 100) if total_chamados > 0 else 0
        percent_sla_solucao = (sla_solucao_ok / total_chamados * 100) if total_chamados > 0 else 0
        
        tma_geral = df_operacional['Tempo Útil até o Segundo Atendimento'].mean()
        
        csat_total_avaliacoes = df_merged['Nota'].count()
        csat_satisfeitos = df_merged[df_merged['Nota'] >= 4].shape[0]
        percent_csat = (csat_satisfeitos / csat_total_avaliacoes * 100) if csat_total_avaliacoes > 0 else 0
        
        chamados_com_pesquisa = df_operacional[df_operacional['Possui Pesquisa de Satisfação'] == 'Sim'].shape[0]
        percent_resp_pesquisa = (csat_total_avaliacoes / chamados_com_pesquisa * 100) if chamados_com_pesquisa > 0 else 0

        st.subheader("Indicadores Gerais da Equipe")
        cols = st.columns(5)
        with cols[0]:
            st.metric(label="Total de Chamados", value=f"{total_chamados}")
        with cols[1]:
            st.metric(label="SLA 1º Atendimento", value=f"{percent_sla_atendimento:.1f}%")
        with cols[2]:
            st.metric(label="SLA de Solução", value=f"{percent_sla_solucao:.1f}%")
        with cols[3]:
            st.metric(label="CSAT Geral", value=f"{percent_csat:.1f}%")
        with cols[4]:
            st.metric(label="% Resposta Pesquisa", value=f"{percent_resp_pesquisa:.1f}%")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Total de Chamados por Dia")
            chamados_dia = df_operacional.groupby(df_operacional['Data de Criação'].dt.date).size()
            st.bar_chart(chamados_dia)
        with col2:
            st.subheader("Chamados por Categoria")
            chamados_cat = df_operacional['Nome da Categoria'].value_counts()
            st.bar_chart(chamados_cat)
            
    else:
        st.warning("Não há dados para exibir com os filtros selecionados.")


elif pagina_selecionada == "Desempenho por Analista":
    st.title("🧑‍💻 Desempenho por Analista")

    if not df_merged.empty:
        analistas = sorted(df_merged['Nome Completo do Operador'].unique())
        num_cols = 3
        
        for i in range(0, len(analistas), num_cols):
            cols = st.columns(num_cols)
            for j in range(num_cols):
                if i + j < len(analistas):
                    analista = analistas[i+j]
                    df_analista = df_merged[df_merged['Nome Completo do Operador'] == analista]
                    
                    with cols[j]:
                        with st.container(border=True):
                            st.subheader(analista)
                            
                            # KPIs
                            atendimentos = df_analista.shape[0]
                            tma = df_analista['Tempo Útil até o Segundo Atendimento'].mean()
                            
                            csat_avaliacoes = df_analista['Nota'].count()
                            csat_satisfeitos = df_analista[df_analista['Nota'] >= 4].shape[0]
                            percent_csat = (csat_satisfeitos / csat_avaliacoes * 100) if csat_avaliacoes > 0 else 0
                            
                            chamados_com_pesquisa = df_analista[df_analista['Possui Pesquisa de Satisfação'] == 'Sim'].shape[0]
                            percent_resp = (csat_avaliacoes / chamados_com_pesquisa * 100) if chamados_com_pesquisa > 0 else 0
                            
                            c1, c2 = st.columns(2)
                            c1.metric("Atendimentos", f"{atendimentos}")
                            c2.metric("TMA (min)", f"{tma:.2f}")
                            
                            c3, c4 = st.columns(2)
                            c3.metric("CSAT", f"{percent_csat:.0f}%")
                            c4.metric("% Resp. Pesq.", f"{percent_resp:.0f}%")
    else:
        st.warning("Não há dados para exibir com os filtros selecionados.")


elif pagina_selecionada == "Análise Temporal (TMA/TME)":
    st.title("📈 Análise Temporal: TMA e TME")
    
    if not df_operacional.empty:
        df_diario = df_operacional.groupby(df_operacional['Data de Criação'].dt.date).agg(
            TME=('Tempo Útil até o Primeiro Atendimento', 'mean'),
            TMA=('Tempo Útil até o Segundo Atendimento', 'mean')
        ).reset_index()

        fig = px.bar(df_diario, x='Data de Criação', y=['TME', 'TMA'],
                     labels={'value': 'Tempo (minutos)', 'variable': 'Métrica', 'Data de Criação': 'Data'},
                     title="Evolução diária de TME e TMA", barmode='group')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Não há dados operacionais para exibir com os filtros selecionados.")

elif pagina_selecionada == "Análise de CSAT":
    st.title("😊 Análise de Satisfação do Cliente (CSAT)")
    
    if not df_merged.empty and df_merged['Nota'].notna().any():
        st.subheader("Distribuição Geral das Notas")
        dist_notas = df_merged['Nota'].dropna().value_counts().sort_index()
        fig_dist = px.bar(dist_notas, x=dist_notas.index, y=dist_notas.values, 
                          labels={'x': 'Nota', 'y': 'Quantidade'}, title="Contagem por Nota de Avaliação")
        st.plotly_chart(fig_dist, use_container_width=True)

        st.subheader("Média de Nota por Analista")
        csat_analista = df_merged.dropna(subset=['Nota']).groupby('Nome Completo do Operador').agg(
            Media_Nota=('Nota', 'mean'),
            Total_Avaliacoes=('Nota', 'count')
        ).reset_index().sort_values(by='Media_Nota', ascending=False)
        
        fig_analista = px.bar(csat_analista, x='Nome Completo do Operador', y='Media_Nota', color='Total_Avaliacoes',
                             title="CSAT por Analista", labels={'Nome Completo do Operador': 'Analista', 'Media_Nota': 'Média da Nota'},
                             color_continuous_scale=px.colors.sequential.Viridis)
        st.plotly_chart(fig_analista, use_container_width=True)
    else:
        st.warning("Não há dados de CSAT para exibir com os filtros selecionados.")

elif pagina_selecionada == "Base de Dados Completa":
    st.title("🗂️ Base de Dados Completa")
    st.subheader("Dados Operacionais (Filtrados)")
    st.dataframe(df_operacional)
    st.subheader("Dados de CSAT (Brutos)")
    st.dataframe(df_csat_raw)
