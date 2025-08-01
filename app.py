import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go
import os

# --- Configuração da Página ---
st.set_page_config(
    page_title="Dashboard de Indicadores",
    page_icon="📊",
    layout="wide"
)

# --- Funções de Utilitário ---
def format_timedelta(td):
    if pd.isna(td):
        return "00:00:00"
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

# --- Funções de Carregamento e Tratamento de Dados ---
@st.cache_data(ttl=3600)
def carregar_dados_operacionais(url, headers):
    try:
        resposta = requests.get(url, headers=headers)
        resposta.raise_for_status()
        arquivo = BytesIO(resposta.content)
        df = pd.read_excel(arquivo)

        for col in ['Data de Criação', 'Data de Finalização']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

        for col in ['Tempo Útil até o Primeiro Atendimento', 'Tempo Útil até o Segundo Atendimento', 'Tempo Útil da Resolução']:
            if col in df.columns:
                df[col] = pd.to_timedelta(df[col].astype(str), errors='coerce').fillna(pd.Timedelta(seconds=0))

        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados operacionais: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def carregar_dados_csat(url, headers):
    try:
        resposta = requests.get(url, headers=headers)
        resposta.raise_for_status()
        arquivo = BytesIO(resposta.content)
        df = pd.read_excel(arquivo)

        coluna_avaliacao = next((col for col in df.columns if 'Como você avalia a qualidade' in col), None)
        if not coluna_avaliacao:
            st.warning("Coluna de avaliação do CSAT não encontrada.")
            return df

        df.rename(columns={coluna_avaliacao: 'Avaliacao_Qualidade'}, inplace=True)
        df['Avaliacao_Qualidade'] = df['Avaliacao_Qualidade'].astype(str)
        df['prioridade_avaliacao'] = df['Avaliacao_Qualidade'].apply(
            lambda x: 1 if x.startswith('Ótimo') else (2 if x.startswith('Bom') else 3)
        )
        df_sorted = df.sort_values(by=['Código do Chamado', 'prioridade_avaliacao'])
        df_final = df_sorted.drop_duplicates(subset='Código do Chamado', keep='first')
        return df_final.drop(columns=['prioridade_avaliacao'])
    except Exception as e:
        st.error(f"Erro ao carregar dados de CSAT: {e}")
        return pd.DataFrame()

# --- Carregamento Inicial ---
URL_OPERACIONAL = st.secrets.get("ELOCA_URL")
HEADERS_OPERACIONAL = {"DeskManager": st.secrets.get("DESKMANAGER_TOKEN")}
URL_CSAT = st.secrets.get("CSAT_URL")
HEADERS_CSAT = {"DeskManager": st.secrets.get("CSAT_TOKEN")}

df_operacional_raw = carregar_dados_operacionais(URL_OPERACIONAL, HEADERS_OPERACIONAL)
df_csat_raw = carregar_dados_csat(URL_CSAT, HEADERS_CSAT)

# --- Filtros ---
st.sidebar.header("Filtros Globais")
df_operacional = pd.DataFrame()
if not df_operacional_raw.empty:
    data_min = df_operacional_raw['Data de Criação'].min().date()
    data_max = df_operacional_raw['Data de Criação'].max().date()
    data_selecionada = st.sidebar.date_input("Selecione o Período", value=(data_min, data_max), min_value=data_min, max_value=data_max)

    if len(data_selecionada) == 2:
        start_date = pd.to_datetime(data_selecionada[0])
        end_date = pd.to_datetime(data_selecionada[1]).replace(hour=23, minute=59, second=59)
        df_operacional = df_operacional_raw[df_operacional_raw['Data de Criação'].between(start_date, end_date)]
    else:
        df_operacional = df_operacional_raw.copy()

    lista_analistas = sorted(df_operacional['Nome Completo do Operador'].dropna().unique())
    analista_selecionado = st.sidebar.multiselect("Selecione o(s) Analista(s)", options=lista_analistas, default=lista_analistas)

    if analista_selecionado:
        df_operacional = df_operacional[df_operacional['Nome Completo do Operador'].isin(analista_selecionado)]
    else:
        df_operacional = pd.DataFrame(columns=df_operacional.columns)
else:
    st.sidebar.warning("Dados operacionais não disponíveis.")

# --- Merge ---
df_merged = pd.DataFrame()
if not df_operacional.empty and not df_csat_raw.empty:
    df_merged = pd.merge(df_operacional, df_csat_raw, left_on='Nº Chamado', right_on='Código do Chamado', how='left')
    df_merged['Nota'] = pd.to_numeric(df_merged['Avaliacao_Qualidade'].str.strip().str[0], errors='coerce')
else:
    df_merged = df_operacional.copy()
    df_merged['Nota'] = pd.NA

# --- Navegação ---
paginas = [
    "Visão Geral",
    "Desempenho por Analista",
    "Análise Temporal (TMA/TME)",
    "Análise de CSAT"
]
pagina_selecionada = st.sidebar.radio("Escolha a página", paginas)

# --- Visão Geral ---
if pagina_selecionada == "Visão Geral":
    st.title("Visão Geral dos Indicadores")
    if not df_operacional.empty:
        total_chamados = df_operacional.shape[0]
        sla_ok = df_operacional[df_operacional['SLA de Primeiro Atendimento Expirado'] == 'Não'].shape[0]
        percent_sla = (sla_ok / total_chamados * 100) if total_chamados > 0 else 0

        csat_avaliacoes = df_merged['Nota'].count()
        csat_satisfeitos = df_merged[df_merged['Nota'] >= 4].shape[0]
        percent_csat = (csat_satisfeitos / csat_avaliacoes * 100) if csat_avaliacoes > 0 else 0

        chamados_com_pesquisa = df_operacional[df_operacional['Possui Pesquisa de Satisfação'] == 'Sim'].shape[0]
        percent_resposta = (csat_avaliacoes / chamados_com_pesquisa * 100) if chamados_com_pesquisa > 0 else 0

        cols = st.columns(4)
        cols[0].metric("Total de Chamados", total_chamados)
        cols[1].metric("SLA 1º Atendimento", f"{percent_sla:.1f}%")
        cols[2].metric("CSAT Geral", f"{percent_csat:.1f}%")
        cols[3].metric("% Resposta Pesquisa", f"{percent_resposta:.1f}%")

# --- Desempenho por Analista ---
elif pagina_selecionada == "Desempenho por Analista":
    st.title("Desempenho por Analista")
    if not df_merged.empty:
        num_cols = 3
        for i in range(0, len(analista_selecionado), num_cols):
            cols = st.columns(num_cols)
            for j in range(num_cols):
                if i + j < len(analista_selecionado):
                    nome = analista_selecionado[i + j]
                    df_a = df_merged[df_merged['Nome Completo do Operador'] == nome]
                    with cols[j]:
                        st.subheader(nome)
                        atendimentos = df_a.shape[0]
                        tma = df_a['Tempo Útil até o Segundo Atendimento'].mean()
                        csat_avaliacoes = df_a['Nota'].count()
                        csat_satisfeitos = df_a[df_a['Nota'] >= 4].shape[0]
                        percent_csat = (csat_satisfeitos / csat_avaliacoes * 100) if csat_avaliacoes > 0 else 0
                        chamados_pesquisa = df_a[df_a['Possui Pesquisa de Satisfação'] == 'Sim'].shape[0]
                        percent_resposta = (csat_avaliacoes / chamados_pesquisa * 100) if chamados_pesquisa > 0 else 0
                        st.metric("Atendimentos", atendimentos)
                        st.metric("TMA", format_timedelta(tma))
                        st.metric("CSAT", f"{percent_csat:.1f}%")
                        st.metric("% Resp. Pesq.", f"{percent_resposta:.1f}%")

# --- Análise Temporal ---
elif pagina_selecionada == "Análise Temporal (TMA/TME)":
    st.title("📈 Análise Temporal: TMA, TME e TMR")
    if not df_operacional.empty:
        df_diario = df_operacional.groupby(df_operacional['Data de Criação'].dt.date).agg(
            TME=('Tempo Útil até o Primeiro Atendimento', lambda x: x.mean().total_seconds() / 60),
            TMA=('Tempo Útil até o Segundo Atendimento', lambda x: x.mean().total_seconds() / 60),
            TMR=('Tempo Útil da Resolução', lambda x: x.mean().total_seconds() / 60),
        ).reset_index()

        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_diario['Data de Criação'], y=df_diario['TMA'], name='TMA', marker_color='#00cc96', text=df_diario['TMA'].round(0), textposition='auto'))
        fig.add_trace(go.Bar(x=df_diario['Data de Criação'], y=df_diario['TME'], name='TME', marker_color='#006c67', text=df_diario['TME'].round(0), textposition='auto'))
        fig.add_trace(go.Scatter(x=df_diario['Data de Criação'], y=df_diario['TMR'], name='TMR', mode='lines+markers+text', line=dict(color='orangered', width=2), marker=dict(size=6), text=df_diario['TMR'].round(0), textposition='top center'))

        fig.update_layout(barmode='group', xaxis_title='Data', yaxis_title='Tempo (min)', height=500, margin=dict(l=30, r=30, t=50, b=50))
        st.plotly_chart(fig, use_container_width=True)

# --- Análise de CSAT ---
elif pagina_selecionada == "Análise de CSAT":
    st.title("😊 Análise de Satisfação do Cliente (CSAT)")
    if not df_merged.empty and df_merged['Nota'].notna().any():
        dist_notas = df_merged['Nota'].dropna().astype(int).value_counts().sort_index()
        st.bar_chart(dist_notas)

        csat_analista = df_merged.dropna(subset=['Nota']).groupby('Nome Completo do Operador').agg(
            Media_Nota=('Nota', 'mean'),
            Total_Avaliacoes=('Nota', 'count')
        ).reset_index().sort_values(by='Media_Nota', ascending=False)

        fig = px.bar(csat_analista, x='Nome Completo do Operador', y='Media_Nota', color='Total_Avaliacoes',
                     title="CSAT por Analista", labels={'Nome Completo do Operador': 'Analista', 'Media_Nota': 'Média da Nota'},
                     color_continuous_scale=px.colors.sequential.Viridis)
        st.plotly_chart(fig, use_container_width=True)
