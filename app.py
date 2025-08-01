
import streamlit as st
import pandas as pd

# Simulação de carregamento dos dataframes (substitua com sua lógica real)
# df_operacional = carregar_df_operacional()
# df_csat = carregar_df_csat()

# Página principal
st.sidebar.title("Navegação")
pagina_selecionada = st.sidebar.selectbox("Escolha a página", ["Resumo Individual"])

if pagina_selecionada == "Resumo Individual":
    st.title("📋 Painel Individual de Desempenho (Hoje)")

    # Filtra o último dia disponível
    ultimo_dia = df_operacional["Data de Criação"].max()
    df_dia = df_operacional[df_operacional["Data de Criação"] == ultimo_dia]

    # Agrupa por analista
    analistas = df_dia["Responsável"].unique()

    for analista in analistas:
        col1, col2, col3 = st.columns(3)
        df_analista = df_dia[df_dia["Responsável"] == analista]

        atendimentos = len(df_analista)
        tma = round(df_analista["TMA"].mean(), 2)
        sla1 = round(df_analista["SLA Primeiro Atendimento"].mean(), 2)
        sla_res = round(df_analista["SLA Resolução"].mean(), 2)

        # CSAT
        df_csat_analista = df_csat[df_csat["Responsável"] == analista]
        csat = round(df_csat_analista["CSAT"].mean(), 2)
        resposta_pesquisa = round((df_csat_analista["CSAT"].count() / atendimentos) * 100, 2)

        col1.metric("👤 Analista", analista)
        col2.metric("📅 Atendimentos", atendimentos)
        col3.metric("⏱️ TMA", f"{tma} min")

        col1.metric("😄 CSAT", f"{csat}%")
        col2.metric("📈 SLA 1º Atendimento", f"{sla1}%")
        col3.metric("🛠️ SLA Resolução", f"{sla_res}%")

        if analista.lower() == "elô":
            st.metric("📊 % Resposta Pesquisa", f"{resposta_pesquisa}%")

        st.markdown("---")
