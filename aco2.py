# coding: utf-8
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from unidecode import unidecode

# --- Constantes ---
FILE_PATH = 'https://raw.githubusercontent.com/rdzomer/Analise-Mensal/refs/heads/main/H_EXPORTACAO_E%20IMPORTACAO_GERAL_2024-01_2025-12_DT20250506.xlsx'
SHEET_NAME = 'Resultado'

COL_MES = 'Mês'
COL_NCM_CODIGO = 'Código NCM'
COL_NCM_DESCRICAO = 'Descrição NCM'
COL_PAIS = 'Países'
COL_EXPORT_VALOR_FORMAT = "Exportação - {} - Valor US$ FOB"
COL_EXPORT_KG_FORMAT = "Exportação - {} - Quilograma Líquido"
COL_IMPORT_VALOR_FORMAT = "Importação - {} - Valor US$ FOB"
COL_IMPORT_KG_FORMAT = "Importação - {} - Quilograma Líquido"

SMA_WINDOW = 3

NCM_GROUPS = {
    "ABITAM": ["73051100", "73051200", "73061900"],
    "IABr": [
        "72083700", "72083890", "72083910", "72083990", "72091600",
        "72091700", "72104910", "72106100", "72139190", "73041900"
    ]
}
GROUP_DESCRIPTIONS = {
    "ABITAM": "Agregado NCMs ABITAM (7305.11.00; 7305.12.00; 7306.19.00)",
    "IABr": "Agregado NCMs IABr (Diversos)"
}

# --- Funções de Utilidade (sem alteração em relação à versão anterior) ---
def format_number_br(value, decimal_places=2):
    try:
        num = float(value)
        return f"{num:,.{decimal_places}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(value)

MESES_MAP = {
    unidecode(k.split('. ')[1].upper()): int(k.split('. ')[0])
    for k in [
        "01. Janeiro", "02. Fevereiro", "03. Março", "04. Abril",
        "05. Maio", "06. Junho", "07. Julho", "08. Agosto",
        "09. Setembro", "10. Outubro", "11. Novembro", "12. Dezembro"
    ]
}
MESES_NUM_TO_NOME_ABBR = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"
}

@st.cache_data
def load_data(file_path_url, sheet_name):
    try:
        df = pd.read_excel(file_path_url, sheet_name=sheet_name, engine='openpyxl')
        if COL_NCM_CODIGO in df.columns:
            df[COL_NCM_CODIGO] = df[COL_NCM_CODIGO].astype(str).str.replace('.', '', regex=False)
        return df
    except FileNotFoundError:
        st.error(f"Arquivo/URL não encontrado: {file_path_url}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar dados do URL '{file_path_url}': {e}")
        if "Worksheet named" in str(e) and "not found" in str(e):
             st.info(f"Verifique se a aba '{sheet_name}' existe no arquivo online.")
        return pd.DataFrame()

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    df_copy = df.copy()
    if COL_MES in df_copy.columns:
        df_copy["month_name_original"] = df_copy[COL_MES]
        df_copy[COL_MES] = df_copy[COL_MES].apply(lambda x: unidecode(str(x).split('. ')[1].upper()) if isinstance(x, str) and '. ' in x else unidecode(str(x).upper()))
        df_copy["month_num"] = df_copy[COL_MES].map(MESES_MAP)
        if df_copy["month_num"].isnull().any():
            #st.warning(f"Alguns meses não puderam ser mapeados para números e serão descartados: {df_copy[df_copy['month_num'].isnull()]['month_name_original'].unique()}")
            df_copy.dropna(subset=["month_num"], inplace=True)
        if "month_num" in df_copy.columns and not df_copy["month_num"].empty:
             df_copy["month_num"] = df_copy["month_num"].astype(int)

    for year in [2024, 2025]:
        for col_format, col_type_desc in [
            (COL_EXPORT_KG_FORMAT, "Exportação KG"),
            (COL_EXPORT_VALOR_FORMAT, "Exportação Valor"),
            (COL_IMPORT_KG_FORMAT, "Importação KG"),
            (COL_IMPORT_VALOR_FORMAT, "Importação Valor")
        ]:
            col_name = col_format.format(year)
            if col_name in df_copy.columns:
                df_copy[col_name] = pd.to_numeric(df_copy[col_name], errors='coerce').fillna(0)
            else:
                df_copy[col_name] = 0

    if COL_PAIS in df_copy.columns:
        df_copy[COL_PAIS] = df_copy[COL_PAIS].astype(str).str.strip().str.upper()
    return df_copy

def prep_yearly_data(df_input: pd.DataFrame, ano: int, meses_a_considerar: int) -> pd.DataFrame:
    col_exp_kg_actual = COL_EXPORT_KG_FORMAT.format(ano)
    col_imp_kg_actual = COL_IMPORT_KG_FORMAT.format(ano)
    required_cols_in_prep = [col_exp_kg_actual, col_imp_kg_actual, COL_PAIS, COL_NCM_CODIGO, "month_num"]
    missing_cols = [col for col in required_cols_in_prep if col not in df_input.columns]
    if missing_cols:
        return pd.DataFrame(columns=[COL_NCM_CODIGO, "month_num", col_exp_kg_actual, "Importacao_kg_Total", "Importacao_kg_China"])
    df_input_copy = df_input.copy()
    if "month_num" not in df_input_copy.columns or df_input_copy["month_num"].isnull().all():
        return pd.DataFrame(columns=[COL_NCM_CODIGO, "month_num", col_exp_kg_actual, "Importacao_kg_Total", "Importacao_kg_China"])
    df_sub = df_input_copy[
        (df_input_copy["month_num"] >= 1) &
        (df_input_copy["month_num"] <= meses_a_considerar)
    ].copy()
    if df_sub.empty:
        return pd.DataFrame(columns=[COL_NCM_CODIGO, "month_num", col_exp_kg_actual, "Importacao_kg_Total", "Importacao_kg_China"])
    df_sub[col_exp_kg_actual] = pd.to_numeric(df_sub[col_exp_kg_actual], errors='coerce').fillna(0)
    df_sub[col_imp_kg_actual] = pd.to_numeric(df_sub[col_imp_kg_actual], errors='coerce').fillna(0)
    grouped_total = (
        df_sub.groupby([COL_NCM_CODIGO, "month_num", COL_PAIS])[[col_exp_kg_actual, col_imp_kg_actual]]
        .sum().reset_index()
    )
    export_sum = grouped_total.groupby([COL_NCM_CODIGO, "month_num"])[col_exp_kg_actual].sum().reset_index()
    import_china_df = grouped_total[grouped_total[COL_PAIS].str.strip().str.upper() == 'CHINA'].copy()
    import_china_df = import_china_df.groupby([COL_NCM_CODIGO, "month_num"])[col_imp_kg_actual].sum().reset_index()
    import_china_df.rename(columns={col_imp_kg_actual: "Importacao_kg_China"}, inplace=True)
    import_total_sum = grouped_total.groupby([COL_NCM_CODIGO, "month_num"])[col_imp_kg_actual].sum().reset_index()
    import_total_sum.rename(columns={col_imp_kg_actual: "Importacao_kg_Total"}, inplace=True)
    current_year_data = pd.merge(export_sum, import_total_sum, on=[COL_NCM_CODIGO, "month_num"], how='outer')
    current_year_data = pd.merge(current_year_data, import_china_df, on=[COL_NCM_CODIGO, "month_num"], how='left')
    current_year_data["Importacao_kg_China"] = current_year_data["Importacao_kg_China"].fillna(0)
    current_year_data["Importacao_kg_Total"] = current_year_data["Importacao_kg_Total"].fillna(0)
    current_year_data[col_exp_kg_actual] = current_year_data[col_exp_kg_actual].fillna(0)
    return current_year_data

def process_and_display_data(df_cleaned: pd.DataFrame, selected_key_display: str, selected_description: str, selected_graphs: list):
    st.header(f"Análise para: {selected_key_display} - {selected_description}")
    is_group = selected_key_display in NCM_GROUPS
    ncms_to_process = NCM_GROUPS.get(selected_key_display) if is_group else [selected_key_display]
    if not ncms_to_process:
        st.error(f"Nenhum NCM encontrado para a seleção: {selected_key_display}")
        return
    meses_2024 = 12
    meses_2025 = 12
    df_2024_prepared = prep_yearly_data(df_cleaned.copy(), 2024, meses_2024)
    df_2025_prepared = prep_yearly_data(df_cleaned.copy(), 2025, meses_2025)
    data_2024_filtered = df_2024_prepared[df_2024_prepared[COL_NCM_CODIGO].isin(ncms_to_process)].copy() if not df_2024_prepared.empty else pd.DataFrame()
    data_2025_filtered = df_2025_prepared[df_2025_prepared[COL_NCM_CODIGO].isin(ncms_to_process)].copy() if not df_2025_prepared.empty else pd.DataFrame()
    export_col_2024 = COL_EXPORT_KG_FORMAT.format(2024)
    export_col_2025 = COL_EXPORT_KG_FORMAT.format(2025)
    cols_to_aggregate_2024 = [export_col_2024, "Importacao_kg_Total", "Importacao_kg_China"]
    cols_to_aggregate_2025 = [export_col_2025, "Importacao_kg_Total", "Importacao_kg_China"]
    for col in cols_to_aggregate_2024:
        if col not in data_2024_filtered.columns and not data_2024_filtered.empty: data_2024_filtered[col] = 0
    for col in cols_to_aggregate_2025:
        if col not in data_2025_filtered.columns and not data_2025_filtered.empty: data_2025_filtered[col] = 0
    if is_group:
        if not data_2024_filtered.empty:
            ncm_data_2024 = data_2024_filtered.groupby("month_num")[cols_to_aggregate_2024].sum().reset_index()
        else:
            ncm_data_2024 = pd.DataFrame(columns=["month_num"] + cols_to_aggregate_2024)
        if not data_2025_filtered.empty:
            ncm_data_2025 = data_2025_filtered.groupby("month_num")[cols_to_aggregate_2025].sum().reset_index()
        else:
            ncm_data_2025 = pd.DataFrame(columns=["month_num"] + cols_to_aggregate_2025)
    else:
        ncm_data_2024 = data_2024_filtered
        ncm_data_2025 = data_2025_filtered
    if not ncm_data_2024.empty and export_col_2024 in ncm_data_2024.columns:
        ncm_data_2024.rename(columns={export_col_2024: 'Exportacao_kg'}, inplace=True)
    if not ncm_data_2025.empty and export_col_2025 in ncm_data_2025.columns:
        ncm_data_2025.rename(columns={export_col_2025: 'Exportacao_kg'}, inplace=True)
    plot_data_list = []
    if not ncm_data_2024.empty:
        ncm_data_2024['Ano'] = 2024
        plot_data_list.append(ncm_data_2024)
    if not ncm_data_2025.empty:
        ncm_data_2025['Ano'] = 2025
        plot_data_list.append(ncm_data_2025)
    ncm_plot_data = pd.DataFrame()
    if plot_data_list:
        ncm_plot_data = pd.concat(plot_data_list, ignore_index=True)
    if ncm_plot_data.empty or "month_num" not in ncm_plot_data.columns or ncm_plot_data["month_num"].isnull().all():
        st.info(f"Não há dados suficientes para os gráficos de série temporal de {selected_key_display}.")
    else:
        ncm_plot_data.sort_values(by=['Ano', 'month_num'], inplace=True)
        ncm_plot_data['Mês/Ano (Eixo X)'] = ncm_plot_data['month_num'].map(MESES_NUM_TO_NOME_ABBR) + '/' + ncm_plot_data['Ano'].astype(str).str[-2:]
        for col in ['Exportacao_kg', 'Importacao_kg_Total', 'Importacao_kg_China']:
            if col in ncm_plot_data.columns:
                ncm_plot_data[f'{col}_SMA'] = ncm_plot_data[col].rolling(window=SMA_WINDOW, min_periods=1).mean()
            else:
                ncm_plot_data[col] = 0
                ncm_plot_data[f'{col}_SMA'] = 0
        if "Exportação (KG)" in selected_graphs:
            st.subheader("Análise de Exportação (KG)")
            if 'Exportacao_kg' in ncm_plot_data.columns and not ncm_plot_data['Exportacao_kg'].fillna(0).eq(0).all():
                hover_data_exp = ncm_plot_data['Exportacao_kg'].apply(lambda x: format_number_br(x, 0))
                fig_export = px.bar(ncm_plot_data, x='Mês/Ano (Eixo X)', y='Exportacao_kg',
                                    title=f"<b>Exportação (KG) - {selected_key_display}</b>",
                                    labels={"Exportacao_kg": "KG Exportado", "Mês/Ano (Eixo X)": "Mês/Ano"},
                                    color_discrete_sequence=['rgb(26, 118, 255)'])
                fig_export.update_traces(customdata=hover_data_exp, hovertemplate="Mês/Ano: %{x}<br>KG Exportado: %{customdata}<extra></extra>")
                if 'Exportacao_kg_SMA' in ncm_plot_data.columns:
                    hover_data_sma_exp = ncm_plot_data['Exportacao_kg_SMA'].apply(lambda x: format_number_br(x, 2))
                    fig_export.add_trace(go.Scatter(x=ncm_plot_data['Mês/Ano (Eixo X)'], y=ncm_plot_data['Exportacao_kg_SMA'], mode='lines',
                                                    name=f'Média Móvel ({SMA_WINDOW} meses)',
                                                    line=dict(color='rgba(0,0,139,0.7)', width=2, dash='dot'),
                                                    customdata=hover_data_sma_exp,
                                                    hovertemplate="Média Móvel: %{customdata}<extra></extra>"))
                fig_export.update_xaxes(categoryorder='array', categoryarray=ncm_plot_data['Mês/Ano (Eixo X)'].unique(),
                                        showgrid=True, gridwidth=1, gridcolor='LightGrey', griddash='dot')
                max_y_exp = (ncm_plot_data['Exportacao_kg'].max() if ncm_plot_data['Exportacao_kg'].notna().any() else 0)
                if 'Exportacao_kg_SMA' in ncm_plot_data.columns and ncm_plot_data['Exportacao_kg_SMA'].notna().any():
                    max_y_exp = max(max_y_exp, ncm_plot_data['Exportacao_kg_SMA'].max())
                if max_y_exp > 0:
                    tickvals_exp = np.linspace(0, max_y_exp * 1.1, num=6)
                    ticktext_exp = [format_number_br(val, 0) for val in tickvals_exp]
                    fig_export.update_yaxes(tickvals=tickvals_exp, ticktext=ticktext_exp, showgrid=True, gridwidth=1, gridcolor='LightGrey')
                else:
                    fig_export.update_yaxes(tickformat="d", showgrid=True, gridwidth=1, gridcolor='LightGrey')
                fig_export.update_layout(hovermode="x unified", plot_bgcolor='white', legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))
                st.plotly_chart(fig_export, use_container_width=True)
            else:
                st.write(f"<i>Sem dados de exportação significativos para {selected_key_display}.</i>", unsafe_allow_html=True)
        if "Importação (KG) - Total vs China" in selected_graphs:
            st.subheader("Análise de Importação (KG) - Total vs. China")
            if 'Importacao_kg_Total' in ncm_plot_data.columns and not ncm_plot_data['Importacao_kg_Total'].fillna(0).eq(0).all():
                fig_import = go.Figure()
                hover_data_total = ncm_plot_data['Importacao_kg_Total'].apply(lambda x: format_number_br(x, 0))
                fig_import.add_trace(go.Bar(x=ncm_plot_data['Mês/Ano (Eixo X)'], y=ncm_plot_data['Importacao_kg_Total'],
                                            name='Importação Total (KG)', marker_color='rgb(255, 165, 0)',
                                            customdata=hover_data_total,
                                            hovertemplate="Mês/Ano: %{x}<br>Importação Total: %{customdata}<extra></extra>"))
                if 'Importacao_kg_Total_SMA' in ncm_plot_data.columns:
                    hover_data_sma_total = ncm_plot_data['Importacao_kg_Total_SMA'].apply(lambda x: format_number_br(x, 2))
                    fig_import.add_trace(go.Scatter(x=ncm_plot_data['Mês/Ano (Eixo X)'], y=ncm_plot_data['Importacao_kg_Total_SMA'],
                                                    name=f'Média Móvel Total ({SMA_WINDOW}m)', mode='lines',
                                                    line=dict(color='rgba(205,133,63,0.7)', width=2, dash='dot'),
                                                    customdata=hover_data_sma_total,
                                                    hovertemplate="Média Móvel Total: %{customdata}<extra></extra>"))
                if 'Importacao_kg_China' in ncm_plot_data.columns and not ncm_plot_data['Importacao_kg_China'].fillna(0).eq(0).all():
                    hover_data_china = ncm_plot_data['Importacao_kg_China'].apply(lambda x: format_number_br(x, 0))
                    fig_import.add_trace(go.Scatter(x=ncm_plot_data['Mês/Ano (Eixo X)'], y=ncm_plot_data['Importacao_kg_China'],
                                                    name='Importação China (KG)', mode='lines+markers',
                                                    line=dict(color='rgb(220, 20, 60)', width=2), marker=dict(size=5),
                                                    customdata=hover_data_china,
                                                    hovertemplate="Mês/Ano: %{x}<br>Importação China: %{customdata}<extra></extra>"))
                    if 'Importacao_kg_China_SMA' in ncm_plot_data.columns:
                        hover_data_sma_china = ncm_plot_data['Importacao_kg_China_SMA'].apply(lambda x: format_number_br(x, 2))
                        fig_import.add_trace(go.Scatter(x=ncm_plot_data['Mês/Ano (Eixo X)'], y=ncm_plot_data['Importacao_kg_China_SMA'],
                                                        name=f'Média Móvel China ({SMA_WINDOW}m)', mode='lines',
                                                        line=dict(color='rgba(139,0,0,0.7)', width=2, dash='dash'),
                                                        customdata=hover_data_sma_china,
                                                        hovertemplate="Média Móvel China: %{customdata}<extra></extra>"))
                fig_import.update_layout(title=f"<b>Importação (KG) Total vs China - {selected_key_display}</b>",
                                        xaxis_title="Mês/Ano", yaxis_title="KG Importado", barmode='group',
                                        hovermode="x unified", plot_bgcolor='white', legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))
                fig_import.update_xaxes(categoryorder='array', categoryarray=ncm_plot_data['Mês/Ano (Eixo X)'].unique(),
                                        showgrid=True, gridwidth=1, gridcolor='LightGrey', griddash='dot')
                max_y_imp = 0
                for col_check in ['Importacao_kg_Total', 'Importacao_kg_Total_SMA', 'Importacao_kg_China', 'Importacao_kg_China_SMA']:
                    if col_check in ncm_plot_data and ncm_plot_data[col_check].notna().any():
                        max_y_imp = max(max_y_imp, ncm_plot_data[col_check].max())
                if max_y_imp > 0:
                    tickvals_imp = np.linspace(0, max_y_imp * 1.1, num=6)
                    ticktext_imp = [format_number_br(val, 0) for val in tickvals_imp]
                    fig_import.update_yaxes(tickvals=tickvals_imp, ticktext=ticktext_imp, showgrid=True, gridwidth=1, gridcolor='LightGrey')
                else:
                    fig_import.update_yaxes(tickformat="d", showgrid=True, gridwidth=1, gridcolor='LightGrey')
                st.plotly_chart(fig_import, use_container_width=True)
            else:
                st.write(f"<i>Sem dados de importação significativos para {selected_key_display}.</i>", unsafe_allow_html=True)
    if "Origem da Importação (Treemap)" in selected_graphs:
        st.subheader(f"Origem da Importação (KG) - Total 2024 & 2025 para {selected_key_display}")
        df_filtered_for_treemap = df_cleaned[df_cleaned[COL_NCM_CODIGO].isin(ncms_to_process)].copy()
        if df_filtered_for_treemap.empty:
            st.write(f"<i>Nenhum dado encontrado para {selected_key_display} para o gráfico de origem.</i>", unsafe_allow_html=True)
        else:
            imp_kg_2024_col = COL_IMPORT_KG_FORMAT.format(2024)
            imp_kg_2025_col = COL_IMPORT_KG_FORMAT.format(2025)
            if imp_kg_2024_col not in df_filtered_for_treemap.columns: df_filtered_for_treemap[imp_kg_2024_col] = 0
            if imp_kg_2025_col not in df_filtered_for_treemap.columns: df_filtered_for_treemap[imp_kg_2025_col] = 0
            df_filtered_for_treemap['Total_Import_KG'] = pd.to_numeric(df_filtered_for_treemap[imp_kg_2024_col], errors='coerce').fillna(0) + \
                                                         pd.to_numeric(df_filtered_for_treemap[imp_kg_2025_col], errors='coerce').fillna(0)
            origin_data = df_filtered_for_treemap.groupby(COL_PAIS)['Total_Import_KG'].sum().reset_index()
            origin_data = origin_data[origin_data['Total_Import_KG'] > 0].sort_values(by='Total_Import_KG', ascending=False)
            if origin_data.empty:
                st.write(f"<i>Nenhuma importação registrada para {selected_key_display} em 2024 ou 2025 para o gráfico de origem.</i>", unsafe_allow_html=True)
            else:
                total_geral_import = origin_data['Total_Import_KG'].sum()
                if total_geral_import > 0:
                    origin_data[' udział (%)'] = (origin_data['Total_Import_KG'] / total_geral_import) * 100
                else:
                    origin_data[' udział (%)'] = 0
                origin_data['hover_text_kg'] = origin_data['Total_Import_KG'].apply(lambda x: format_number_br(x, 0))
                origin_data['hover_text_perc'] = origin_data[' udział (%)'].apply(lambda x: format_number_br(x, 2) + "%")
                fig_treemap = px.treemap(origin_data,
                                         path=[px.Constant(f"Importações {selected_key_display}"), COL_PAIS],
                                         values='Total_Import_KG',
                                         color='Total_Import_KG',
                                         color_continuous_scale='Blues',
                                         title=f"<b>Origem das Importações (KG) - {selected_key_display} (Total 2024-2025)</b>",
                                         custom_data=['hover_text_kg', 'hover_text_perc', COL_PAIS])
                fig_treemap.update_traces(
                    textinfo='label+percent root',
                    hovertemplate="<b>País:</b> %{customdata[2]}<br><b>KG Importado:</b> %{customdata[0]}<br><b>Participação:</b> %{customdata[1]}<extra></extra>"
                )
                fig_treemap.update_layout(margin = dict(t=50, l=25, r=25, b=25))
                st.plotly_chart(fig_treemap, use_container_width=True)
                st.write(f"Top 10 Países de Origem para {selected_key_display} (Importação KG):")
                origin_data_display = origin_data.head(10).copy()
                origin_data_display['Total_Import_KG'] = origin_data_display['Total_Import_KG'].apply(lambda x: format_number_br(x,0))
                origin_data_display[' udział (%)'] = origin_data_display[' udział (%)'].apply(lambda x: format_number_br(x,2) + " %")
                st.dataframe(origin_data_display[[COL_PAIS, 'Total_Import_KG', ' udział (%)']].reset_index(drop=True), hide_index=True)

# --- Streamlit App ---
st.set_page_config(layout="wide", page_title="Análise de Comércio Exterior de Aço")
st.title("Dashboard de Análise de Comércio Exterior - Produtos Siderúrgicos")

df_raw = load_data(FILE_PATH, SHEET_NAME)

if df_raw.empty:
    st.warning("Nenhum dado carregado. Verifique o URL do arquivo e a aba.")
    st.stop()

df_cleaned = clean_data(df_raw)

if df_cleaned.empty:
    st.warning("Dados resultaram vazios após a limpeza e processamento de meses.") # Mensagem ajustada
    # Mostrar mensagem de boas-vindas se o df_cleaned estiver vazio, mas df_raw não.
    if not df_raw.empty:
        st.info("Selecione um NCM ou Grupo na barra lateral para iniciar a análise.")
    st.stop() # Parar aqui se df_cleaned for vazio

# --- Geração de Opções para o Selectbox ---
st.sidebar.header("Filtros")
PLACEHOLDER_OPTION = "--- Selecione uma opção ---" # Placeholder
selector_options_display_list = [PLACEHOLDER_OPTION] # Lista para o selectbox, começando com o placeholder
selector_options_map = {} # Dicionário para mapear display -> (key, description)

# Adicionar Grupos
for group_name, ncms in NCM_GROUPS.items():
    display_option = f"GRUPO: {group_name}"
    description = GROUP_DESCRIPTIONS.get(group_name, f"Agregado do grupo {group_name}")
    selector_options_display_list.append(display_option)
    selector_options_map[display_option] = (group_name, description)

# Adicionar NCMs Individuais
if COL_NCM_CODIGO in df_cleaned.columns and COL_NCM_DESCRICAO in df_cleaned.columns:
    # Garantir que df_cleaned não está vazio antes de tentar acessar colunas
    if not df_cleaned.empty:
        ncm_individual_options = df_cleaned[[COL_NCM_CODIGO, COL_NCM_DESCRICAO]].drop_duplicates().sort_values(by=COL_NCM_CODIGO)
        for _, row in ncm_individual_options.iterrows():
            ncm_cod = row[COL_NCM_CODIGO]
            ncm_desc = row[COL_NCM_DESCRICAO]
            display_option = f"{ncm_cod} - {ncm_desc}"
            selector_options_display_list.append(display_option)
            selector_options_map[display_option] = (ncm_cod, ncm_desc)
    # else: # Caso df_cleaned seja vazio, ncm_individual_options não será populado
        # st.sidebar.warning("Nenhum NCM individual disponível para seleção pois os dados estão vazios após limpeza.")
elif not df_cleaned.empty : # Se df_cleaned não for vazio mas as colunas NCM não existirem
    st.sidebar.error(f"Colunas '{COL_NCM_CODIGO}' ou '{COL_NCM_DESCRICAO}' não encontradas nos dados limpos.")


# Seletor de NCM/Grupo
selected_display_option = st.sidebar.selectbox(
    "Selecione NCM ou Grupo:",
    options=selector_options_display_list,
    index=0 # Define o placeholder como padrão
)

# Seleção de Gráficos a exibir
graph_options_available = [
    "Exportação (KG)",
    "Importação (KG) - Total vs China",
    "Origem da Importação (Treemap)"
]

# Definir gráficos default com base na seleção do NCM/Grupo
default_graphs = []
if selected_display_option != PLACEHOLDER_OPTION:
    default_graphs = graph_options_available


selected_graphs_to_display = st.sidebar.multiselect(
    "Selecione os gráficos para exibir:",
    options=graph_options_available,
    default=default_graphs # Usa a lista default_graphs
)

# Lógica principal de exibição
if selected_display_option != PLACEHOLDER_OPTION and selected_display_option is not None:
    if selected_graphs_to_display: # Só processa se houver gráficos selecionados
        key_for_processing, description_for_header = selector_options_map[selected_display_option]
        process_and_display_data(df_cleaned, key_for_processing, description_for_header, selected_graphs_to_display)
    elif selected_display_option != PLACEHOLDER_OPTION : # Se um NCM/Grupo está selecionado mas nenhum gráfico
        st.info("Selecione os tipos de gráficos que deseja visualizar na barra lateral.")
else:
    st.info("Bem-vindo! Por favor, selecione um NCM ou um Grupo na barra lateral para iniciar a análise.")
    st.markdown("Utilize também o seletor de gráficos para customizar sua visualização.")

st.sidebar.markdown("---")




