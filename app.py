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
        resposta.raise_for_status()  # Lança um erro para códigos de status ruins (4xx ou 5xx)
        arquivo = BytesIO(resposta.content)
        df = pd.read_excel(arquivo)
        
        # --- Limpeza e Conversão de Tipos ---
        # Converte colunas de data/hora
        for col in ['Data de Criação', 'Data da Primeira Resposta', 'Data da Resolução', 'Data do Primeiro Atendimento', 'Data do Segundo Atendimento']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

        # Converte colunas de tempo para numérico (minutos)
        for col in df.columns:
            if 'Tempo Útil' in col:
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

        # Renomear coluna de avaliação para facilitar o acesso
        coluna_avaliacao = next((col for col in df.columns if 'Como você avalia a qualidade' in col), None)
        if not coluna_avaliacao:
            st.warning("Coluna de avaliação do CSAT não encontrada.")
            return df
        
        df.rename(columns={coluna_avaliacao: 'Avaliacao_Qualidade'}, inplace=True)
        
        # --- Lógica de Desduplicação do CSAT ---
        df['Avaliacao_Qualidade'] = df['Avaliacao_Qualidade'].astype(str)
        
        # 1. Ordenar para priorizar as melhores avaliações
        df['prioridade_avaliacao'] = df['Avaliacao_Qualidade'].apply(
            lambda x: 1 if x.startswith('Ótimo') else (2 if x.startswith('Bom') else 3)
        )
        df_sorted = df.sort_values(by=['Código do Chamado', 'prioridade_avaliacao'])
        
        # 2. Manter apenas a primeira ocorrência após a ordenação
        df_final = df_sorted.drop_duplicates(subset='Código do Chamado', keep='first')
        
        return df_final.drop(columns=['prioridade_avaliacao'])
        
    except requests.exceptions.RequestException as e:
        st.error(f"Erro de conexão ao buscar dados de CSAT: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao processar dados de CSAT: {e}")
        return pd.DataFrame()

# --- Carregamento dos Dados Usando Secrets ---
# Use st.secrets para um ambiente de produção no Streamlit Cloud
# Para teste local, pode usar os valores diretamente ou um arquivo .env
URL_OPERACIONAL = st.secrets.get("ELOCA_URL", os.getenv("ELOCA_URL"))
HEADERS_OPERACIONAL = {"DeskManager": st.secrets.get("DESKMANAGER_TOKEN", os.getenv("DESKMANAGER_TOKEN"))}

URL_CSAT = st.secrets.get("CSAT_URL", os.getenv("CSAT_URL"))
HEADERS_CSAT = {"DeskManager": st.secrets.get("CSAT_TOKEN", os.getenv("CSAT_TOKEN"))}

df_operacional = carregar_dados_operacionais(URL_OPERACIONAL, HEADERS_OPERACIONAL)
df_csat = carregar_dados_csat(URL_CSAT, HEADERS_CSAT)

# --- Barra Lateral de Filtros ---
st.sidebar.header("Filtros Globais")

# Filtro de Período
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
        df_operacional = df_operacional[df_operacional['Data de Criação'].between(start_date, end_date)]
else:
    st.sidebar.warning("Dados operacionais ou coluna 'Data de Criação' não disponíveis para filtro.")

# Filtro de Analista
if not df_operacional.empty and 'Analista da Resolução' in df_operacional.columns:
    lista_analistas = sorted(df_operacional['Analista da Resolução'].dropna().unique())
    analista_selecionado = st.sidebar.multiselect(
        "Selecione o(s) Analista(s)",
        options=lista_analistas,
        default=lista_analistas
    )
    df_operacional = df_operacional[df_operacional['Analista da Resolução'].isin(analista_selecionado)]
else:
    st.sidebar.warning("Coluna 'Analista da Resolução' não disponível para filtro.")


# --- Navegação Principal ---
st.sidebar.title("Navegação")
paginas = [
    "Resultados Área 1 (TMA, TME, TMR)",
    "Resultados Área 2 (CSAT)",
    "Gráfico Individual 1 (Desempenho Diário)",
    "Gráfico Individual 2 (CSAT por Analista)",
    "Metas Individuais",
    "Base de Dados Completa"
]
pagina_selecionada = st.sidebar.radio("Escolha a página", paginas)

# --- Conteúdo das Páginas ---

if pagina_selecionada == "Resultados Área 1 (TMA, TME, TMR)":
    st.title("📈 Resultados Área 1: Tempo Médio de Atendimento, Espera e Resolução")
    
    if not df_operacional.empty:
        # Cálculos dos KPIs
        tme = df_operacional['Tempo Útil até o primeiro atendimento'].mean()
        tma = df_operacional['Tempo Útil até o segundo atendimento'].mean()
        tmr = df_operacional['Tempo Útil da Resolução'].mean()

        col1, col2, col3 = st.columns(3)
        col1.metric("Tempo Médio de Espera (TME)", f"{tme:.2f} min")
        col2.metric("Tempo Médio de Atendimento (TMA)", f"{tma:.2f} min")
        col3.metric("Tempo Médio de Resolução (TMR)", f"{tmr:.2f} min")
        
        st.markdown("---")
        st.subheader("Evolução Diária dos Tempos Médios")
        
        df_diario = df_operacional.groupby(df_operacional['Data de Criação'].dt.date).agg({
            'Tempo Útil até o primeiro atendimento': 'mean',
            'Tempo Útil até o segundo atendimento': 'mean',
            'Tempo Útil da Resolução': 'mean'
        }).reset_index()

        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_diario['Data de Criação'], y=df_diario['Tempo Útil até o primeiro atendimento'], name='TME'))
        fig.add_trace(go.Bar(x=df_diario['Data de Criação'], y=df_diario['Tempo Útil até o segundo atendimento'], name='TMA'))
        fig.add_trace(go.Scatter(x=df_diario['Data de Criação'], y=df_diario['Tempo Útil da Resolução'], name='TMR', mode='lines+markers', yaxis='y2'))

        fig.update_layout(
            title="TME, TMA e TMR por Dia",
            xaxis_title="Data",
            yaxis_title="Tempo (minutos)",
            yaxis2=dict(title="TMR (minutos)", overlaying='y', side='right'),
            legend_title="Métricas",
            barmode='group'
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Não há dados operacionais para exibir.")

elif pagina_selecionada == "Resultados Área 2 (CSAT)":
    st.title("😊 Resultados Área 2: Satisfação do Cliente (CSAT)")
    
    if not df_csat.empty:
        # Merge para obter o analista
        df_csat_merged = pd.merge(df_csat, df_operacional[['Código', 'Analista da Resolução']], left_on='Código do Chamado', right_on='Código', how='left')

        # Filtra CSAT com base nos analistas selecionados no filtro global
        df_csat_merged = df_csat_merged[df_csat_merged['Analista da Resolução'].isin(analista_selecionado)]
        
        total_respostas = len(df_csat_merged)
        
        # Extrai a nota da avaliação (assumindo que a nota é o primeiro caractere)
        df_csat_merged['Nota'] = pd.to_numeric(df_csat_merged['Avaliacao_Qualidade'].str[0], errors='coerce')
        
        media_notas = df_csat_merged['Nota'].mean()
        
        # Considera "satisfeitos" quem deu nota 4 ou 5
        satisfeitos = df_csat_merged[df_csat_merged['Nota'].isin([4, 5])].shape[0]
        percent_satisfeitos = (satisfeitos / total_respostas * 100) if total_respostas > 0 else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Respostas", total_respostas)
        col2.metric("Média de Notas (1-5)", f"{media_notas:.2f}")
        col3.metric("% de Satisfação (Notas 4 e 5)", f"{percent_satisfeitos:.2f}%")
        
        st.markdown("---")
        st.subheader("Distribuição das Notas de Avaliação")
        
        dist_notas = df_csat_merged['Nota'].value_counts().sort_index()
        fig = px.bar(dist_notas, x=dist_notas.index, y=dist_notas.values, labels={'x': 'Nota', 'y': 'Quantidade'}, title="Contagem por Nota de Avaliação")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Não há dados de CSAT para exibir.")

elif pagina_selecionada == "Gráfico Individual 1 (Desempenho Diário)":
    st.title("📅 Gráfico Individual 1: Desempenho Diário por Analista")
    
    if not df_operacional.empty:
        df_agrupado = df_operacional.groupby(['Analista da Resolução', df_operacional['Data de Criação'].dt.date]).agg(
            Chamados_Resolvidos=('Código', 'count'),
            TMA=('Tempo Útil até o segundo atendimento', 'mean')
        ).reset_index()
        
        fig = px.scatter(df_agrupado, x='Data de Criação', y='Chamados_Resolvidos', size='TMA', color='Analista da Resolução',
                         hover_name='Analista da Resolução', size_max=60,
                         title="Chamados Resolvidos vs. TMA por Dia e Analista")
        fig.update_layout(
            xaxis_title="Data",
            yaxis_title="Quantidade de Chamados Resolvidos",
            legend_title="Analista"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Não há dados operacionais para exibir.")

elif pagina_selecionada == "Gráfico Individual 2 (CSAT por Analista)":
    st.title("🧑‍💻 Gráfico Individual 2: Desempenho de CSAT por Analista")

    if not df_csat.empty and not df_operacional.empty:
        df_csat_merged = pd.merge(df_csat, df_operacional[['Código', 'Analista da Resolução']], left_on='Código do Chamado', right_on='Código', how='left')
        df_csat_merged = df_csat_merged[df_csat_merged['Analista da Resolução'].isin(analista_selecionado)]
        
        df_csat_merged['Nota'] = pd.to_numeric(df_csat_merged['Avaliacao_Qualidade'].str[0], errors='coerce')
        
        csat_analista = df_csat_merged.groupby('Analista da Resolução').agg(
            Media_Nota=('Nota', 'mean'),
            Total_Avaliacoes=('Código', 'count')
        ).reset_index().sort_values(by='Media_Nota', ascending=False)
        
        st.subheader("Média de Nota e Total de Avaliações por Analista")
        fig = px.bar(csat_analista, x='Analista da Resolução', y='Media_Nota', color='Total_Avaliacoes',
                     title="CSAT por Analista", labels={'Analista da Resolução': 'Analista', 'Media_Nota': 'Média da Nota'},
                     color_continuous_scale=px.colors.sequential.Viridis)
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(csat_analista)
    else:
        st.warning("Não há dados de CSAT ou operacionais para exibir.")

elif pagina_selecionada == "Metas Individuais":
    st.title("🎯 Metas Individuais")
    
    st.info("Esta seção é um modelo. As metas podem ser carregadas de um arquivo Excel/CSV ou inseridas manualmente.")
    
    # --- Modelo de Metas ---
    # Em um cenário real, isso viria de um arquivo ou banco de dados
    metas = {
        'TMA': 30, # minutos
        'TME': 15, # minutos
        'CSAT': 4.5 # nota média
    }
    
    st.subheader("Definição das Metas Atuais")
    col1, col2, col3 = st.columns(3)
    col1.info(f"TMA: < {metas['TMA']} min")
    col2.info(f"TME: < {metas['TME']} min")
    col3.info(f"CSAT: > {metas['CSAT']}")
    
    st.markdown("---")
    
    # Cálculo dos resultados por analista
    resultados_op = df_operacional.groupby('Analista da Resolução').agg(
        TMA_Realizado=('Tempo Útil até o segundo atendimento', 'mean'),
        TME_Realizado=('Tempo Útil até o primeiro atendimento', 'mean')
    ).reset_index()
    
    df_csat_merged = pd.merge(df_csat, df_operacional[['Código', 'Analista da Resolução']], left_on='Código do Chamado', right_on='Código', how='left')
    df_csat_merged['Nota'] = pd.to_numeric(df_csat_merged['Avaliacao_Qualidade'].str[0], errors='coerce')
    resultados_csat = df_csat_merged.groupby('Analista da Resolução').agg(
        CSAT_Realizado=('Nota', 'mean')
    ).reset_index()
    
    # Unindo os resultados
    df_resultados = pd.merge(resultados_op, resultados_csat, on='Analista da Resolução', how='outer')
    
    # Comparando com as metas
    df_resultados['Atingiu_TMA'] = df_resultados['TMA_Realizado'] < metas['TMA']
    df_resultados['Atingiu_TME'] = df_resultados['TME_Realizado'] < metas['TME']
    df_resultados['Atingiu_CSAT'] = df_resultados['CSAT_Realizado'] > metas['CSAT']
    
    st.subheader("Resultados vs. Metas por Analista")
    
    # Função para formatar visualmente
    def formatar_meta(df):
        def colorir_booleano(val):
            color = 'lightgreen' if val else 'lightcoral'
            return f'background-color: {color}'
        
        return df.style.applymap(colorir_booleano, subset=['Atingiu_TMA', 'Atingiu_TME', 'Atingiu_CSAT']) \
                       .format({
                           'TMA_Realizado': '{:.2f}',
                           'TME_Realizado': '{:.2f}',
                           'CSAT_Realizado': '{:.2f}'
                       })

    st.dataframe(formatar_meta(df_resultados), use_container_width=True)

elif pagina_selecionada == "Base de Dados Completa":
    st.title("🗂️ Base de Dados Completa")
    
    st.subheader("Dados Operacionais")
    if not df_operacional.empty:
        st.dataframe(df_operacional)
    else:
        st.warning("Não há dados operacionais para exibir.")
        
    st.subheader("Dados de CSAT (Após Tratamento)")
    if not df_csat.empty:
        st.dataframe(df_csat)
    else:
        st.warning("Não há dados de CSAT para exibir.")
