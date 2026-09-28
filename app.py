from __future__ import annotations

import io
import os
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

import pandas as pd
import plotly.express as px
import streamlit as st

# Configuração da página e layout
st.set_page_config(
    page_title="Painel de acompanhamento de atividades OMNI Sesi",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Diretórios base de trabalho
WORKSPACE_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = WORKSPACE_DIR.parent


# Leitura de variáveis de ambiente ou segredos do Streamlit
def setting(name: str, default: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    try:
        value = st.secrets.get(name)
    except (FileNotFoundError, KeyError):
        value = None
    return str(value) if value else default


# Fontes de dados padrão (Google Sheets exportados em CSV)
IMPROVEMENTS_SOURCE = setting(
    "OMNI_MELHORIAS_CSV_URL",
    "https://docs.google.com/spreadsheets/d/1mOL5gvWcekfgbKvqxTKYUEv3kiPrFGW2JfUWva6x5V8/export?format=csv&gid=394660906",
)
INCIDENTS_SOURCE = setting(
    "OMNI_INCIDENTES_CSV_URL",
    "https://docs.google.com/spreadsheets/d/1m_NJ_mPxvGNvZpPXqYysnSmb9EI-Kd_2Phz1LJ0ScqQ/export?format=csv&gid=1170584752",
)
UPDATES_SOURCE = setting(
    "OMNI_ATUALIZACOES_CSV_URL",
    "https://docs.google.com/spreadsheets/d/12wDYwtSrFC_rieT37lK1MJ-d66DOCpLuMUfMOJqu3c0/export?format=csv",
)
CACHE_TTL = int(os.getenv("OMNI_CACHE_TTL_SECONDS", "300"))

# Mapeamento de colunas principais para exibição
IMPROVEMENT_COLUMNS = [
    "Categoria",
    "Melhoria",
    "Descrição",
    "Prioridade",
    "Início",
    "Fim",
    "Status",
    "Profissional alocado",
]
INCIDENT_COLUMNS = [
    "Número",
    "Aberto(a)",
    "Resumo",
    "Solicitante",
    "Estado",
    "Atribuição a",
    "Atualizado em",
]


# Injeção dos estilos CSS para o Kanban e ajuste de exibição do cabeçalho
def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'DM Sans', sans-serif;
            color: var(--text-color);
        }

        h1, h2, h3 {
            font-family: 'Space Grotesk', sans-serif !important;
            letter-spacing: 0 !important;
            color: var(--text-color) !important;
        }

        /* 1. Oculta o menu, botão de deploy e a barra superior (Fork/GitHub) */
        #MainMenu, 
        [data-testid="stAppDeployButton"], 
        [data-testid="stToolbar"] {
            display: none !important;
            visibility: hidden !important;
        }

        /* 2. Mantém o cabeçalho invisível mas não quebra a seta da sidebar */
        [data-testid="stHeader"] {
            background-color: transparent !important;
            z-index: 100 !important;
        }

        /* 3. Aniquila o rodapé e TODOS os ícones do canto inferior direito (Perfil, Logo, Status) */
        footer, 
        [data-testid="stFooter"], 
        [data-testid="stStatusWidget"], 
        [data-testid="stAppCreatorBadge"], 
        [data-testid="stAppViewerBadge"],
        .stAppBadge, 
        div[class*="viewerBadge"],
        #creatorIndicator,
        #viewerBadge {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            height: 0 !important;
            width: 0 !important;
            pointer-events: none !important;
        }

        /* Ajustes de layout principal e sidebar */
        [data-testid="stMainBlockContainer"] { 
            max-width: 1550px; 
            padding-top: 1.5rem !important; 
        }

        [data-testid="stSidebar"] {
            border-right: 1px solid rgba(128, 128, 128, 0.2);
        }

        /* Cartão do cabeçalho principal */
        .hero {
            padding: 1.4rem 1.5rem 1.35rem;
            border: 1px solid rgba(128, 128, 128, 0.2);
            border-radius: 1rem;
            margin-bottom: 1.2rem;
            background: var(--secondary-background-color);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
        }
        .eyebrow {
            color: var(--primary-color);
            text-transform: uppercase;
            font-size: .75rem;
            font-weight: 700;
            letter-spacing: .12em;
        }
        .hero h1 {
            font-size: clamp(2rem, 4vw, 3.55rem);
            line-height: 1;
            margin: .28rem 0 .5rem;
        }

        /* Cartões de métricas KPI */
        [data-testid="stMetric"] {
            background: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            padding: 1rem;
            border-radius: 1rem;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
        }

        .section-label {
            color: var(--primary-color);
            font-size: .8rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: .1em;
            margin: 1.5rem 0 .4rem;
        }

        div[data-testid="stPlotlyChart"] {
            background: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            border-radius: 1rem;
            padding: .5rem;
        }

        /* Estilização específica dos cartões Kanban */
        .kanban-card {
            background: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            border-radius: 0.75rem;
            padding: 0.85rem;
            margin-bottom: 0.65rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.03);
            transition: transform 0.1s ease, border-color 0.1s ease;
        }
        .kanban-card:hover {
            border-color: var(--primary-color);
        }
        .kanban-card-title {
            font-weight: 700;
            font-size: 0.9rem;
            margin-bottom: 0.35rem;
            line-height: 1.3;
        }
        .kanban-badge {
            display: inline-block;
            padding: 0.15rem 0.45rem;
            border-radius: 0.35rem;
            font-size: 0.68rem;
            font-weight: 600;
            margin-right: 0.25rem;
            margin-bottom: 0.35rem;
        }
        .kanban-meta {
            font-size: 0.75rem;
            opacity: 0.75;
            display: flex;
            justify-content: flex-end;
            margin-top: 0.4rem;
            padding-top: 0.35rem;
            border-top: 1px dashed rgba(128,128,128,0.2);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def chart_figure(figure):
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=28, r=28, t=56, b=28),
        hoverlabel=dict(font_size=13),
    )
    return figure


def format_number(value: int | float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def format_date(value: object) -> str:
    if pd.isna(value):
        return "-"
    return pd.Timestamp(value).strftime("%d/%m/%Y")


def canonical(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def normalize_improvement_status(value: object) -> str:
    if pd.isna(value):
        return "Não informado"
    key = canonical(value)
    if not key:
        return "Não informado"
    if any(term in key for term in ["conclu", "finaliz", "encerr", "resolvid"]):
        return "Concluída"
    if any(term in key for term in ["desenvolv", "andamento", "execucao", "fazendo", "progresso"]):
        return "Em desenvolvimento"
    if "homolog" in key or "validac" in key:
        return "Em validação"
    if "backlog" in key or "proxima" in key:
        return "Próximas entregas"
    return str(value).strip()


def parse_improvement_date(value: object) -> pd.Timestamp:
    if pd.isna(value) or not str(value).strip():
        return pd.NaT
    text = str(value).strip()
    if re.fullmatch(r"\d{1,2}/\d{1,2}", text):
        text = f"{text}/{pd.Timestamp.now().year}"
    return pd.to_datetime(text, errors="coerce", dayfirst=True)


def resolve_column(columns: Iterable[object], aliases: Iterable[str]) -> str | None:
    by_key = {canonical(column): str(column) for column in columns}
    for alias in aliases:
        if canonical(alias) in by_key:
            return by_key[canonical(alias)]
    return None


def normalize_columns(frame: pd.DataFrame, schema: dict[str, list[str]]) -> pd.DataFrame:
    renamed: dict[str, str] = {}
    for target, aliases in schema.items():
        source = resolve_column(frame.columns, [target, *aliases])
        if source:
            renamed[source] = target
    result = frame.rename(columns=renamed).copy()
    for column in schema:
        if column not in result:
            result[column] = ""
    return result


def downloadable_url(source: str) -> str:
    if "sharepoint.com/" not in source.lower():
        return source
    parsed = urlparse(source)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["download"] = "1"
    return urlunparse(parsed._replace(query=urlencode(query)))


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_source(source: str, source_name: str) -> tuple[pd.DataFrame, str | None]:
    try:
        if not source:
            return pd.DataFrame(), None
        if source.startswith(("http://", "https://")):
            request = Request(downloadable_url(source), headers={"User-Agent": "OMNI-dashboard/1.0"})
            with urlopen(request, timeout=30) as response:
                payload = response.read()
                content_type = response.headers.get_content_type().lower()
            is_excel = (
                source.lower().split("?", 1)[0].endswith((".xlsx", ".xls"))
                or "spreadsheet" in content_type
                or "excel" in content_type
                or payload[:2] == b"PK"
            )
            frame = pd.read_excel(io.BytesIO(payload)) if is_excel else pd.read_csv(io.BytesIO(payload), encoding="utf-8-sig")
        else:
            source_path = Path(source)
            if not source_path.exists():
                return pd.DataFrame(), f"Arquivo de {source_name} não encontrado: {source_path}"
            frame = pd.read_excel(source_path)
        if frame.empty:
            return pd.DataFrame(), f"A fonte de {source_name} está vazia."
        return frame, None
    except Exception as exc:
        return pd.DataFrame(), f"Não foi possível carregar {source_name}: {exc}"


def prepare_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    improvements, improvement_error = load_source(IMPROVEMENTS_SOURCE, "melhorias")
    incidents, incident_error = load_source(INCIDENTS_SOURCE, "incidentes")
    updates, updates_error = load_source(UPDATES_SOURCE, "últimas atualizações")
    
    improvements = normalize_columns(
        improvements,
        {
            "Categoria": ["category"], "Melhoria": ["improvement", "titulo"], "Descrição": ["description"], "Prioridade": ["priority"],
            "Início": ["inicio", "start", "data inicio"], "Fim": ["fim", "end", "data fim", "termino"],
            "Status": ["status", "estado"],
            "Profissional alocado": ["profissional alocado", "responsavel", "responsável", "analista", "owner", "atribuido a"],
        },
    )
    incidents = normalize_columns(
        incidents,
        {
            "Número": ["numero", "number", "ticket"], "Aberto(a)": ["aberto", "opened"],
            "Resumo": ["short description", "descricao"], "Solicitante": ["requester"],
            "Prioridade": ["priority"], "Estado": ["state", "status"], "Categoria": ["category"],
            "Grupo de atribuição": ["assignment group"], "Atribuição a": ["assigned to"],
            "Atualizado em": ["updated"], "Sistema": ["system"],
        },
    )
    updates = normalize_columns(
        updates,
        {
            "PR": ["numero do card", "card"], "Service Now": ["service now", "chamado"],
            "Tema": ["assunto", "titulo"], "Serviços": ["servicos"], "Observações": ["observacoes"], "Mês": ["mes"],
        },
    )
    
    incidents["Aberto(a)"] = pd.to_datetime(incidents["Aberto(a)"], errors="coerce", dayfirst=True)
    incidents["Atualizado em"] = pd.to_datetime(incidents["Atualizado em"], errors="coerce", dayfirst=True)
    incidents["Atualizado em"] = incidents["Atualizado em"].fillna(incidents["Aberto(a)"])
    
    improvements["Início"] = improvements["Início"].map(parse_improvement_date)
    improvements["Fim"] = improvements["Fim"].map(parse_improvement_date)
    improvements["Status"] = improvements["Status"].map(normalize_improvement_status)
    
    return improvements.fillna(""), incidents.fillna(""), updates.fillna(""), [e for e in [improvement_error, incident_error, updates_error] if e]


def options(frame: pd.DataFrame, column: str) -> list[str]:
    return sorted(value for value in frame[column].astype(str).unique() if value.strip())


def select_filter(label: str, values: list[str], key: str) -> list[str]:
    return st.multiselect(label, values, default=[], key=key, placeholder="Todos")


def apply_values(frame: pd.DataFrame, column: str, selected: list[str]) -> pd.DataFrame:
    return frame if not selected else frame[frame[column].astype(str).isin(selected)]


def csv_download(frame: pd.DataFrame, filename: str, label: str) -> None:
    payload = frame.to_csv(index=False).encode("utf-8-sig")
    st.download_button(label, data=payload, file_name=filename, mime="text/csv", use_container_width=False)


# Mapeamento dinâmico de cores para Prioridade (Bolinhas coloridas ●)
def get_priority_style(priority_value: str) -> tuple[str, str]:
    key = canonical(priority_value)
    if "alta" in key or "alto" in key:
        return "rgba(239, 68, 68, 0.15)", "#ef4444"    # Vermelho
    if "media" in key or "medio" in key:
        return "rgba(245, 158, 11, 0.15)", "#f59e0b"   # Amarelo/Laranja
    if "baixa" in key or "baixo" in key:
        return "rgba(16, 185, 129, 0.15)", "#10b981"   # Verde
    return "rgba(100, 116, 139, 0.15)", "#64748b"       # Cinza neutro


# Barra lateral com inclusão do Filtro de Status
def render_sidebar(improvements: pd.DataFrame, incidents: pd.DataFrame, updates: pd.DataFrame, section: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    with st.sidebar:
        st.markdown("## OMNI\n**Governança operacional**")
        st.caption(f"Filtros de {section.lower()}")
        improvement_statuses, improvement_categories, improvement_priorities = [], [], []
        improvement_search = ""
        incident_categories, incident_priorities, incident_states, incident_assignees, incident_groups = [], [], [], [], []
        update_months = []
        update_search = ""
        date_range = (date.today(), date.today())
        
        if section == "Melhorias":
            improvement_statuses = select_filter("Status", options(improvements, "Status"), "improvement_status")
            improvement_categories = select_filter("Categoria", options(improvements, "Categoria"), "improvement_category")
            improvement_priorities = select_filter("Prioridade", options(improvements, "Prioridade"), "improvement_priority")
            improvement_search = st.text_input("Busca textual", placeholder="Melhoria ou descrição", key="improvement_search")
            valid_dates = improvements["Início"].dropna()
            min_date = valid_dates.min().date() if not valid_dates.empty else date.today() - timedelta(days=30)
            max_date = valid_dates.max().date() if not valid_dates.empty else date.today()
            date_range = st.date_input("Intervalo de início", value=(min_date, max_date), min_value=min_date, max_value=max_date, key="improvement_date")
        elif section == "Incidentes":
            incident_categories = select_filter("Categoria", options(incidents, "Categoria"), "incident_category")
            incident_priorities = select_filter("Prioridade", options(incidents, "Prioridade"), "incident_priority")
            incident_states = select_filter("Estado do incidente", options(incidents, "Estado"), "incident_state")
            incident_assignees = select_filter("Atribuição", options(incidents, "Atribuição a"), "incident_assignee")
            incident_groups = select_filter("Grupo de atribuição", options(incidents, "Grupo de atribuição"), "incident_group")
            valid_dates = incidents["Atualizado em"].dropna()
            min_date = valid_dates.min().date() if not valid_dates.empty else date.today() - timedelta(days=30)
            max_date = valid_dates.max().date() if not valid_dates.empty else date.today()
            date_range = st.date_input("Intervalo de atualização", value=(min_date, max_date), min_value=min_date, max_value=max_date, key="incident_date")
            
        st.divider()
        st.caption(f"Atualização automática: a cada {CACHE_TTL // 60 or 1} min")

    # Aplicando filtros nas Melhorias (incluindo Status)
    filtered_improvements = improvements.copy()
    filtered_improvements = apply_values(filtered_improvements, "Status", improvement_statuses)
    filtered_improvements = apply_values(filtered_improvements, "Categoria", improvement_categories)
    filtered_improvements = apply_values(filtered_improvements, "Prioridade", improvement_priorities)
    if improvement_search:
        query = improvement_search.casefold()
        searchable = filtered_improvements["Melhoria"].astype(str) + " " + filtered_improvements["Descrição"].astype(str)
        filtered_improvements = filtered_improvements[searchable.str.casefold().str.contains(query, na=False)]
    if len(date_range) == 2 and section == "Melhorias":
        filtered_improvements = filtered_improvements[filtered_improvements["Início"].notna() & filtered_improvements["Início"].dt.date.between(date_range[0], date_range[1])]
    
    # Aplicando filtros nos Incidentes
    filtered_incidents = incidents.copy()
    for col, sel in [("Categoria", incident_categories), ("Prioridade", incident_priorities), ("Estado", incident_states), ("Atribuição a", incident_assignees), ("Grupo de atribuição", incident_groups)]:
        filtered_incidents = apply_values(filtered_incidents, col, sel)
    if len(date_range) == 2 and section == "Incidentes":
        filtered_incidents = filtered_incidents[filtered_incidents["Atualizado em"].dt.date.between(date_range[0], date_range[1])]
    
    filtered_updates = apply_values(updates.copy(), "Mês", update_months)
    return filtered_improvements, filtered_incidents, filtered_updates


# Renderizador de Card individual do Kanban
def render_kanban_card(row: pd.Series) -> str:
    categoria = row['Categoria'] if row['Categoria'] else 'Geral'
    prioridade = row['Prioridade'] if row['Prioridade'] else 'Normal'
    responsavel = row['Profissional alocado'] if row['Profissional alocado'] else 'Não atribuído'
    dt_inicio = format_date(row['Início'])
    desc = str(row['Descrição'])
    if len(desc) > 75:
        desc = desc[:75] + "..."
        
    prio_bg, prio_color = get_priority_style(prioridade)

    return f"""
    <div class="kanban-card">
        <div class="kanban-card-title">{row['Melhoria']}</div>
        <div>
            <span class="kanban-badge" style="background:rgba(59, 130, 246, 0.15); color:#3b82f6;">🏷️ {categoria}</span>
            <span class="kanban-badge" style="background:{prio_bg}; color:{prio_color};">● {prioridade}</span>
        </div>
        <div style="font-size: 0.78rem; opacity: 0.8; margin-top: 0.2rem;">{desc}</div>
        <div class="kanban-meta">
            <span>👤 {responsavel}</span>
            <span>📅 {dt_inicio}</span>
        </div>
    </div>
    """


# Quadro Kanban com mecanismo "Ver mais" retrátil por coluna
def render_kanban_board(frame: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Quadro Kanban de Melhorias</div>', unsafe_allow_html=True)
    
    columns_config = [
        {"title": "Próximas entregas", "color": "#f59e0b", "bg": "#f59e0b18"},
        {"title": "Em desenvolvimento", "color": "#3b82f6", "bg": "#3b82f618"},
        {"title": "Em validação", "color": "#8b5cf6", "bg": "#8b5cf618"},
        {"title": "Concluída", "color": "#10b981", "bg": "#10b98118"},
    ]
    
    if (frame["Status"] == "Não informado").any():
        columns_config.append({"title": "Não informado", "color": "#64748b", "bg": "#64748b18"})

    cols = st.columns(len(columns_config))
    CARDS_LIMITE_INICIAL = 3  # Número de cards visíveis diretamente antes de recolher

    for col, cfg in zip(cols, columns_config):
        status_name = cfg["title"]
        items = frame[frame["Status"] == status_name]
        
        with col:
            # Cabeçalho da coluna
            st.markdown(
                f"""
                <div style="background:{cfg['bg']}; border-top: 3px solid {cfg['color']}; padding: 8px 12px; border-radius: 8px 8px 0 0; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 700; font-size: 0.88rem;">{status_name}</span>
                    <span style="background: {cfg['color']}; color: white; border-radius: 12px; padding: 2px 8px; font-size: 0.72rem; font-weight: 700;">{len(items)}</span>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            if items.empty:
                st.caption("Nenhum item")
            else:
                visible_items = items.iloc[:CARDS_LIMITE_INICIAL]
                hidden_items = items.iloc[CARDS_LIMITE_INICIAL:]
                
                # Exibe primeiros N cards
                for _, row in visible_items.iterrows():
                    st.markdown(render_kanban_card(row), unsafe_allow_html=True)
                
                # Se houver excedentes, agrupa em seção retrátil "Ver mais"
                if not hidden_items.empty:
                    with st.expander(f"➕ Ver mais {len(hidden_items)} item(ns)", expanded=False):
                        for _, row in hidden_items.iterrows():
                            st.markdown(render_kanban_card(row), unsafe_allow_html=True)


# Desenha a seção de Melhorias na ordem reestruturada
def render_improvements(frame: pd.DataFrame) -> None:
    start_values = frame["Início"].dropna()
    end_values = frame["Fim"].dropna()
    if not start_values.empty and not end_values.empty:
        period_str = f"Período: {start_values.min().strftime('%d/%m/%Y')} a {end_values.max().strftime('%d/%m/%Y')}"
    else:
        period_str = "Período: Não informado"
    st.caption(period_str)
    
    if frame.empty:
        st.info("Nenhuma melhoria encontrada para os filtros selecionados.")
        return

    # Métricas
    total = len(frame)
    completed = int(frame["Status"].eq("Concluída").sum())
    developing = int(frame["Status"].eq("Em desenvolvimento").sum())
    validation = int(frame["Status"].eq("Em validação").sum())
    upcoming = int(frame["Status"].eq("Próximas entregas").sum())
    unreported = int(frame["Status"].eq("Não informado").sum())

    # 1. Indicadores (KPIs)
    st.markdown('<div class="section-label">Indicadores executivos</div>', unsafe_allow_html=True)
    overview = st.columns(5)
    overview[0].metric("Total de melhorias", format_number(total))
    overview[1].metric("Concluídas", format_number(completed))
    overview[2].metric("Em desenvolvimento", format_number(developing))
    overview[3].metric("Em validação", format_number(validation))
    overview[4].metric("Próximas entregas", format_number(upcoming))

    # 2. Volume por status (Gráfico)
    st.markdown('<div class="section-label">Acompanhamento por status</div>', unsafe_allow_html=True)
    status_counts = pd.DataFrame({
        "Status": ["Concluída", "Em desenvolvimento", "Em validação", "Próximas entregas", "Não informado"],
        "Quantidade": [completed, developing, validation, upcoming, unreported]
    })
    status_counts = status_counts[status_counts["Quantidade"] > 0]
    
    status_chart = px.bar(
        status_counts,
        x="Status",
        y="Quantidade",
        text="Quantidade",
        title="Volume atual por status",
        color="Status",
        color_discrete_map={"Concluída": "#10b981", "Em desenvolvimento": "#3b82f6", "Em validação": "#8b5cf6", "Próximas entregas": "#f59e0b", "Não informado": "#64748b"},
    )
    status_chart.update_traces(texttemplate="%{y:.0f}", textposition="outside", textfont_size=11, cliponaxis=False)
    st.plotly_chart(chart_figure(status_chart), use_container_width=True)

    # 3. Quadro Kanban Retrátil
    render_kanban_board(frame)

    # 4. Gráficos de Categoria (Gráfico de Barras Horizontal para legibilidade) e Prioridade
    st.markdown('<div class="section-label">Análise de Categoria e Prioridade</div>', unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        category_data = (
            frame["Categoria"]
            .replace("", "Não informado")
            .value_counts()
            .rename_axis("Categoria")
            .reset_index(name="Quantidade")
            .sort_values("Quantidade", ascending=True)
        )
        category_chart = px.bar(
            category_data,
            x="Quantidade",
            y="Categoria",
            orientation="h",
            title="Composição por categoria",
            text="Quantidade",
            color="Quantidade",
            color_continuous_scale="Blues",
        )
        category_chart.update_layout(coloraxis_showscale=False)
        category_chart.update_traces(textposition="outside", cliponaxis=False)
        st.plotly_chart(chart_figure(category_chart), use_container_width=True)
        
    with right:
        priority_data = frame["Prioridade"].replace("", "Não informado").value_counts().rename_axis("Prioridade").reset_index(name="Quantidade")
        priority_chart = px.bar(
            priority_data,
            x="Prioridade",
            y="Quantidade",
            title="Volume por prioridade",
            color="Prioridade",
            color_discrete_map={
                "Alta": "#ef4444",
                "Alto": "#ef4444",
                "Média": "#f59e0b",
                "Médio": "#f59e0b",
                "Baixa": "#10b981",
                "Baixo": "#10b981",
                "Não informado": "#64748b"
            }
        )
        st.plotly_chart(chart_figure(priority_chart), use_container_width=True)

    # 5. Exportação
    st.markdown("---")
    table_to_export = frame[IMPROVEMENT_COLUMNS].copy()
    for col in ["Início", "Fim"]:
        table_to_export[col] = pd.to_datetime(table_to_export[col], errors="coerce").dt.strftime("%d/%m/%Y")
    csv_download(table_to_export, "omni_melhorias.csv", "⇩ Exportar melhorias filtradas em CSV")


# Desenha o painel de Incidentes
def render_incidents(frame: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Central de incidentes</div>', unsafe_allow_html=True)
    total = len(frame)
    closed = int(frame["Estado"].astype(str).str.casefold().isin(["encerrado(a)", "encerrado", "closed", "resolvido(a)", "resolvido", "cancelado(a)", "cancelado"]).sum())
    opened = total - closed
    
    kpi = st.columns(3)
    kpi[0].metric("Volume total", format_number(total))
    kpi[1].metric("Resolvidos / Encerrados", format_number(closed))
    kpi[2].metric("Abertos / Pendentes", format_number(opened))
    st.markdown('<div class="incident-spacer"></div>', unsafe_allow_html=True)
    
    if frame.empty:
        st.info("Nenhum incidente corresponde aos filtros selecionados.")
        return

    timeline = frame.dropna(subset=["Aberto(a)"]).copy()
    timeline["Data"] = timeline["Aberto(a)"].dt.normalize()
    daily_counts = timeline.groupby("Data").size().rename("Incidentes").reset_index().sort_values("Data").reset_index(drop=True)
    daily_counts["Rótulo"] = daily_counts["Incidentes"].astype(int).astype(str)
    
    bar_chart = px.bar(daily_counts, x="Data", y="Incidentes", title="Volume diário de incidentes", text="Rótulo", color_discrete_sequence=["#3b82f6"])
    bar_chart.update_traces(texttemplate="%{text}", textposition="outside", cliponaxis=False)
    st.plotly_chart(chart_figure(bar_chart), use_container_width=True)

    st.markdown('<div class="section-label">Fila detalhada</div>', unsafe_allow_html=True)
    table = frame[INCIDENT_COLUMNS].sort_values("Atualizado em", ascending=False).copy()
    for col in ["Aberto(a)", "Atualizado em"]:
        table[col] = table[col].dt.strftime("%d/%m/%Y %H:%M")
    csv_download(table, "omni_incidentes.csv", "⇩ Exportar incidentes em CSV")
    st.dataframe(table, hide_index=True, use_container_width=True, height=420)

# Função Principal
def main() -> None:
    inject_styles()
    improvements, incidents, updates, errors = prepare_data()
    
    st.markdown('<div class="hero"><div class="eyebrow">OMNI / Acompanhamento</div><h1>Painel de acompanhamento de atividades OMNI Sesi</h1><p>Visão executiva do portfólio de melhorias e da operação de incidentes com fontes atualizadas.</p></div>', unsafe_allow_html=True)
    
    for error in errors:
        st.warning(error)
        
    section = st.radio("Seção", ["Melhorias", "Incidentes"], horizontal=True, label_visibility="collapsed", key="active_section")
    filtered_improvements, filtered_incidents, filtered_updates = render_sidebar(improvements, incidents, updates, section)
    
    if section == "Melhorias":
        render_improvements(filtered_improvements)
    else:
        render_incidents(filtered_incidents)


if __name__ == "__main__":
    main()