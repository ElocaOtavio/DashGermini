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
    """Carrega e trata os dados operacionais da Eloca."""
    try:
        resposta = requests.get(url, headers=headers)
        resposta.raise_for_status()
        arquivo = BytesIO(resposta.content)
        df = pd.read_excel(arquivo)
        
        # --- Limpeza e Conversão de Tipos ---
        for col in ['Data de Criação', 'Data de Finalização']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

        for col in ['Tempo Útil até o Primeiro Atendimento', 'Tempo Útil até o Segundo Atendimento']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"Erro de conexão ao buscar dados operacionais: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao processar dados operacionais: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600) # Cache de 1 hora
def carregar_dados_csat(url, headers):
    """Carrega, trata e aplica a regra de desduplicação nos dados de CSAT."""
    try:
        resposta = requests.get(url, headers=headers)
        resposta.raise_for_status()
        arquivo = BytesIO(resposta.content)
        df = pd.read_excel(arquivo)

        coluna_avaliacao = 'Atendimento - CES e CSAT - [ANALISTA] Como você avalia a qualidade do atendimento prestado pelo analista neste chamado?'
        if coluna_avaliacao not in df.columns:
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
        
    except requests.exceptions.RequestException as e:
        st.error(f"Erro de conexão ao buscar dados de CSAT: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao processar dados de CSAT: {e}")
        return pd.DataFrame()

# --- Carregamento dos Dados Usando Secrets ---
URL_OPERACIONAL = st.secrets.get("ELOCA_URL")
HEADERS_OPERACIONAL = {"DeskManager": st.secrets.get("DESKMANAGER_TOKEN")}

URL_CSAT = st.secrets.get("CSAT_URL")
HEADERS_CSAT = {"DeskManager": st.secrets.get("CSAT_TOKEN")}

df_operacional = carregar_dados_operacionais(URL_OPERACIONAL, HEADERS_OPERACIONAL)
df_csat = carregar_dados_csat(URL_CSAT, HEADERS_CSAT)

# --- Barra Lateral de Filtros ---
st.sidebar.header("Filtros Globais")

if not df_operacional.empty and 'Data de Criação' in df_operacional.columns:
    data_min = df_operacional['Data de Criação'].min().date()
    data_max = df_operacional['Data de Criação'].max().date()
    
    data_selecionada = st.sidebar.date_input(
        "Selecione o Período",
        value=(data_min, data_max),
        min_value=data_min,
        max_value=data_max,
    )
    if len(data_selecionada) == 2:
        start_date, end_date = pd.to_datetime(data_selecionada[0]), pd.to_datetime(data_selecionada[1])
        df_operacional_filtrado = df_operacional[df_operacional['Data de Criação'].between(start_date, end_date)]
    else:
        df_operacional_filtrado = df_operacional.copy()
else:
    df_operacional_filtrado = pd.DataFrame()
    st.sidebar.warning("Dados operacionais ou coluna 'Data de Criação' não disponíveis para filtro.")

if not df_operacional_filtrado.empty and 'Nome Completo do Operador' in df_operacional_filtrado.columns:
    lista_analistas = sorted(df_operacional_filtrado['Nome Completo do Operador'].dropna().unique())
    analista_selecionado = st.sidebar.multiselect(
        "Selecione o(s) Analista(s)",
        options=lista_analistas,
        default=lista_analistas
    )
    df_operacional_filtrado = df_operacional_filtrado[df_operacional_filtrado['Nome Completo do Operador'].isin(analista_selecionado)]
else:
    st.sidebar.warning("Coluna 'Nome Completo do Operador' não disponível para filtro.")


# --- Navegação Principal ---
st.sidebar.title("Navegação")
paginas = [
    "Resultados Área 1 (TMA, TME)",
    "Resultados Área 2 (CSAT)",
    "Gráfico Individual 1 (Desempenho Diário)",
    "Gráfico Individual 2 (CSAT por Analista)",
    "Metas Individuais",
    "Base de Dados Completa"
]
pagina_selecionada = st.sidebar.radio("Escolha a página", paginas)

# --- Conteúdo das Páginas ---

if pagina_selecionada == "Resultados Área 1 (TMA, TME)":
    st.title("📈 Resultados Área 1: Tempo Médio de Atendimento e Espera")
    
    if not df_operacional_filtrado.empty:
        tme = df_operacional_filtrado['Tempo Útil até o Primeiro Atendimento'].mean()
        tma = df_operacional_filtrado['Tempo Útil até o Segundo Atendimento'].mean()

        col1, col2 = st.columns(2)
        col1.metric("Tempo Médio de Espera (TME)", f"{tme:.2f} min")
        col2.metric("Tempo Médio de Atendimento (TMA)", f"{tma:.2f} min")
        
        st.markdown("---")
        st.subheader("Evolução Diária dos Tempos Médios")
        
        df_diario = df_operacional_filtrado.groupby(df_operacional_filtrado['Data de Criação'].dt.date).agg({
            'Tempo Útil até o Primeiro Atendimento': 'mean',
            'Tempo Útil até o Segundo Atendimento': 'mean'
        }).reset_index()

        fig = px.bar(df_diario, x='Data de Criação', y=['Tempo Útil até o Primeiro Atendimento', 'Tempo Útil até o Segundo Atendimento'],
                     labels={'value': 'Tempo (minutos)', 'variable': 'Métrica'},
                     title="TME e TMA por Dia", barmode='group')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Não há dados operacionais para exibir com os filtros selecionados.")

elif pagina_selecionada == "Resultados Área 2 (CSAT)":
    st.title("😊 Resultados Área 2: Satisfação do Cliente (CSAT)")
    
    if not df_csat.empty and not df_operacional.empty:
        df_csat_merged = pd.merge(df_csat, df_operacional[['Nº Chamado', 'Nome Completo do Operador']], left_on='Código do Chamado', right_on='Nº Chamado', how='left')
        df_csat_merged.dropna(subset=['Nome Completo do Operador'], inplace=True)
        df_csat_filtrado = df_csat_merged[df_csat_merged['Nome Completo do Operador'].isin(analista_selecionado)]
        
        if not df_csat_filtrado.empty:
            total_respostas = len(df_csat_filtrado)
            df_csat_filtrado['Nota'] = pd.to_numeric(df_csat_filtrado['Avaliacao_Qualidade'].str[0], errors='coerce')
            media_notas = df_csat_filtrado['Nota'].mean()
            satisfeitos = df_csat_filtrado[df_csat_filtrado['Nota'].isin([4, 5])].shape[0]
            percent_satisfeitos = (satisfeitos / total_respostas * 100) if total_respostas > 0 else 0

            col1, col2, col3 = st.columns(3)
            col1.metric("Total de Respostas", total_respostas)
            col2.metric("Média de Notas (1-5)", f"{media_notas:.2f}")
            col3.metric("% de Satisfação (Notas 4 e 5)", f"{percent_satisfeitos:.2f}%")
            
            st.markdown("---")
            st.subheader("Distribuição das Notas de Avaliação")
            
            dist_notas = df_csat_filtrado['Nota'].value_counts().sort_index()
            fig = px.bar(dist_notas, x=dist_notas.index, y=dist_notas.values, labels={'x': 'Nota', 'y': 'Quantidade'}, title="Contagem por Nota de Avaliação")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Não há dados de CSAT para exibir com os filtros selecionados.")
    else:
        st.warning("Dados de CSAT ou Operacionais não disponíveis.")


elif pagina_selecionada == "Gráfico Individual 1 (Desempenho Diário)":
    st.title("📅 Gráfico Individual 1: Desempenho Diário por Analista")
    
    if not df_operacional_filtrado.empty:
        df_agrupado = df_operacional_filtrado.groupby(['Nome Completo do Operador', df_operacional_filtrado['Data de Criação'].dt.date]).agg(
            Chamados_Atendidos=('Nº Chamado', 'count'),
            TMA=('Tempo Útil até o Segundo Atendimento', 'mean')
        ).reset_index()
        
        fig = px.scatter(df_agrupado, x='Data de Criação', y='Chamados_Atendidos', size='TMA', color='Nome Completo do Operador',
                         hover_name='Nome Completo do Operador', size_max=60,
                         title="Chamados Atendidos vs. TMA por Dia e Analista")
        fig.update_layout(
            xaxis_title="Data",
            yaxis_title="Quantidade de Chamados Atendidos",
            legend_title="Analista"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Não há dados operacionais para exibir com os filtros selecionados.")

elif pagina_selecionada == "Gráfico Individual 2 (CSAT por Analista)":
    st.title("🧑‍💻 Gráfico Individual 2: Desempenho de CSAT por Analista")

    if not df_csat.empty and not df_operacional.empty:
        df_csat_merged = pd.merge(df_csat, df_operacional[['Nº Chamado', 'Nome Completo do Operador']], left_on='Código do Chamado', right_on='Nº Chamado', how='left')
        df_csat_merged.dropna(subset=['Nome Completo do Operador'], inplace=True)
        df_csat_filtrado = df_csat_merged[df_csat_merged['Nome Completo do Operador'].isin(analista_selecionado)]
        
        if not df_csat_filtrado.empty:
            df_csat_filtrado['Nota'] = pd.to_numeric(df_csat_filtrado['Avaliacao_Qualidade'].str[0], errors='coerce')
            
            csat_analista = df_csat_filtrado.groupby('Nome Completo do Operador').agg(
                Media_Nota=('Nota', 'mean'),
                Total_Avaliacoes=('Código do Chamado', 'count')
            ).reset_index().sort_values(by='Media_Nota', ascending=False)
            
            st.subheader("Média de Nota e Total de Avaliações por Analista")
            fig = px.bar(csat_analista, x='Nome Completo do Operador', y='Media_Nota', color='Total_Avaliacoes',
                         title="CSAT por Analista", labels={'Nome Completo do Operador': 'Analista', 'Media_Nota': 'Média da Nota'},
                         color_continuous_scale=px.colors.sequential.Viridis)
            st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(csat_analista)
        else:
            st.warning("Não há dados de CSAT para exibir com os filtros selecionados.")
    else:
        st.warning("Dados de CSAT ou Operacionais não disponíveis.")

elif pagina_selecionada == "Metas Individuais":
    st.title("🎯 Metas Individuais")
    
    st.info("Esta seção é um modelo. As metas podem ser carregadas de um arquivo Excel/CSV ou inseridas manualmente no futuro.")
    
    metas = { 'TMA': 30, 'TME': 15, 'CSAT': 4.5 }
    
    st.subheader("Definição das Metas Atuais")
    col1, col2, col3 = st.columns(3)
    col1.info(f"TMA: < {metas['TMA']} min")
    col2.info(f"TME: < {metas['TME']} min")
    col3.info(f"CSAT: > {metas['CSAT']}")
    
    st.markdown("---")
    
    if not df_operacional_filtrado.empty:
        resultados_op = df_operacional_filtrado.groupby('Nome Completo do Operador').agg(
            TMA_Realizado=('Tempo Útil até o Segundo Atendimento', 'mean'),
            TME_Realizado=('Tempo Útil até o Primeiro Atendimento', 'mean')
        ).reset_index()
        
        df_csat_merged = pd.merge(df_csat, df_operacional[['Nº Chamado', 'Nome Completo do Operador']], left_on='Código do Chamado', right_on='Nº Chamado', how='left')
        df_csat_merged.dropna(subset=['Nome Completo do Operador'], inplace=True)
        df_csat_filtrado = df_csat_merged[df_csat_merged['Nome Completo do Operador'].isin(analista_selecionado)]
        
        if not df_csat_filtrado.empty:
            df_csat_filtrado['Nota'] = pd.to_numeric(df_csat_filtrado['Avaliacao_Qualidade'].str[0], errors='coerce')
            resultados_csat = df_csat_filtrado.groupby('Nome Completo do Operador').agg(
                CSAT_Realizado=('Nota', 'mean')
            ).reset_index()
            df_resultados = pd.merge(resultados_op, resultados_csat, on='Nome Completo do Operador', how='outer')
        else:
            df_resultados = resultados_op.copy()
            df_resultados['CSAT_Realizado'] = pd.NA
            
        df_resultados['Atingiu_TMA'] = df_resultados['TMA_Realizado'] < metas['TMA']
        df_resultados['Atingiu_TME'] = df_resultados['TME_Realizado'] < metas['TME']
        df_resultados['Atingiu_CSAT'] = df_resultados['CSAT_Realizado'] > metas['CSAT']
        
        st.subheader("Resultados vs. Metas por Analista")
        
        def formatar_meta(df):
            def colorir_booleano(val):
                if pd.isna(val): return ''
                color = 'lightgreen' if val else 'lightcoral'
                return f'background-color: {color}'
            
            return df.style.applymap(colorir_booleano, subset=['Atingiu_TMA', 'Atingiu_TME', 'Atingiu_CSAT']) \
                           .format({
                               'TMA_Realizado': '{:.2f}',
                               'TME_Realizado': '{:.2f}',
                               'CSAT_Realizado': '{:.2f}'
                           }, na_rep='-')

        st.dataframe(formatar_meta(df_resultados), use_container_width=True)
    else:
        st.warning("Não há dados operacionais para exibir com os filtros selecionados.")

elif pagina_selecionada == "Base de Dados Completa":
    st.title("🗂️ Base de Dados Completa")
    
    st.subheader("Dados Operacionais (Filtrados)")
    if not df_operacional_filtrado.empty:
        st.dataframe(df_operacional_filtrado)
    else:
        st.warning("Não há dados operacionais para exibir.")
        
    st.subheader("Dados de CSAT (Tratados e sem filtro de data/analista)")
    if not df_csat.empty:
        st.dataframe(df_csat)
    else:
        st.warning("Não há dados de CSAT para exibir.")
