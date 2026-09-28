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


st.set_page_config(
    page_title="Painel de acompanhamento de atividades OMNI Sesi",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)


WORKSPACE_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = WORKSPACE_DIR.parent


def setting(name: str, default: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    try:
        value = st.secrets.get(name)
    except (FileNotFoundError, KeyError):
        value = None
    return str(value) if value else default


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

IMPROVEMENT_COLUMNS = [
    "Categoria",
    "Melhoria",
    "Descrição",
    "Prioridade",
    "Sprint",
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

        /* Oculta topo nativo, menu, toolbar e botão Fork */
        #MainMenu { visibility: hidden !important; }
        footer { display: none !important; visibility: hidden !important; }
        header { display: none !important; visibility: hidden !important; }
        [data-testid="stHeader"] { display: none !important; }
        [data-testid="stToolbar"] { display: none !important; }
        [data-testid="stDecoration"] { display: none !important; }
        [data-testid="stStatusWidget"] { display: none !important; }
        
        /* Oculta o selo "Hosted with Streamlit" e perfil */
        div[class*="viewerBadge"] { display: none !important; }
        a[class*="viewerBadge"] { display: none !important; }
        div[class*="ProfileButton"] { display: none !important; }
        .viewerBadge_container__1QSob { display: none !important; }

        [data-testid="stMainBlockContainer"] { 
            max-width: 1450px; 
            padding-top: 1.5rem !important; 
        }

        /* Sidebar adaptável */
        [data-testid="stSidebar"] {
            border-right: 1px solid rgba(128, 128, 128, 0.2);
        }
        [data-testid="stSidebar"] .stMultiSelect div[data-baseweb="select"], 
        [data-testid="stSidebar"] input {
            background: var(--secondary-background-color);
            border-color: rgba(128, 128, 128, 0.3);
        }

        /* Card Hero */
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
        .hero p {
            opacity: 0.8;
            margin: 0;
            max-width: 760px;
            font-size: 1.05rem;
        }

        /* Cards de Métricas */
        [data-testid="stMetric"] {
            background: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            padding: 1rem;
            border-radius: 1rem;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
        }
        [data-testid="stMetricLabel"] {
            opacity: 0.8;
            font-weight: 500;
        }
        [data-testid="stMetricValue"] {
            font-family: 'Space Grotesk', sans-serif;
            color: var(--text-color);
        }

        .section-label {
            color: var(--primary-color);
            font-size: .8rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: .1em;
            margin: 1.5rem 0 .4rem;
        }

        div[data-testid="stDataFrame"] {
            border: 1px solid rgba(128, 128, 128, 0.2);
            border-radius: 1rem;
            overflow: hidden;
            background: var(--secondary-background-color);
        }

        button[data-baseweb="tab"] { font-weight: 600; }
        div[role="radiogroup"] { gap: .45rem; }
        div[role="radiogroup"] label {
            background: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            border-radius: .7rem;
            padding: .35rem .8rem;
        }
        div[role="radiogroup"] label:has(input:checked) {
            background: rgba(59, 130, 246, 0.15);
            border-color: var(--primary-color);
        }

        .incident-spacer { height: 1.25rem; }
        .incident-caption { opacity: 0.8; font-size: .85rem; margin: .1rem 0 .45rem; }
        div[data-testid="stPlotlyChart"] {
            background: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            border-radius: 1rem;
            padding: .5rem;
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
    if "homolog" in key:
        return "Em validação"
    if "backlog" in key:
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
            "Sprint": ["sprint", "ciclo", "iteracao"], "Início": ["inicio", "start", "data inicio"],
            "Fim": ["fim", "end", "data fim", "termino"], "Status": ["status", "estado"],
            "Profissional alocado": ["profissional alocado", "responsavel", "responsável", "analista", "owner", "atribuido a", "attributed to"],
        },
    )
    incidents = normalize_columns(
        incidents,
        {
            "Número": ["numero", "number", "ticket", "incidente"], "Aberto(a)": ["aberto", "opened", "data abertura"],
            "Resumo": ["descricao resumida", "short description", "descricao", "resumo", "summary"], "Solicitante": ["requester"],
            "Prioridade": ["priority"], "Estado": ["state", "status"], "Categoria": ["category"],
            "Grupo de atribuição": ["assignment group", "grupo"], "Atribuição a": ["assigned to", "atribuido a", "analista"],
            "Atualizado em": ["updated", "updated at", "data atualizacao"], "Sistema": ["system", "sistema"],
        },
    )
    updates = normalize_columns(
        updates,
        {
            "PR": ["numero do card", "card", "devops", "pull request", "número", "setembro"],
            "Service Now": ["service now", "chamado", "incident", "incidente", "numero incidente"],
            "Tema": ["assunto", "titulo", "título"],
            "Serviços": ["servicos", "serviços", "servico", "serviço", "servicos afetados"],
            "Observações": ["observacoes", "observações", "obs", "comentarios", "comentários"],
            "Mês": ["mes", "mês", "month"],
        },
    )
    incidents["Aberto(a)"] = pd.to_datetime(incidents["Aberto(a)"], errors="coerce", dayfirst=True)
    incidents["Atualizado em"] = pd.to_datetime(incidents["Atualizado em"], errors="coerce", dayfirst=True)
    incidents["Atualizado em"] = incidents["Atualizado em"].fillna(incidents["Aberto(a)"])
    improvements["Início"] = improvements["Início"].map(parse_improvement_date)
    improvements["Fim"] = improvements["Fim"].map(parse_improvement_date)
    if improvements["Sprint"].astype(str).str.strip().eq("").all() and not improvements.empty:
        improvements["Sprint"] = "Próximas entregas"
    improvements["Status"] = improvements["Status"].map(normalize_improvement_status)
    return improvements.fillna(""), incidents.fillna(""), updates.fillna(""), [error for error in [improvement_error, incident_error, updates_error] if error]


def options(frame: pd.DataFrame, column: str) -> list[str]:
    return sorted(value for value in frame[column].astype(str).unique() if value.strip())


def select_filter(label: str, values: list[str], key: str) -> list[str]:
    return st.multiselect(label, values, default=[], key=key, placeholder="Todos")


def apply_values(frame: pd.DataFrame, column: str, selected: list[str]) -> pd.DataFrame:
    return frame if not selected else frame[frame[column].astype(str).isin(selected)]


def csv_download(frame: pd.DataFrame, filename: str, label: str) -> None:
    payload = frame.to_csv(index=False).encode("utf-8-sig")
    st.download_button(label, data=payload, file_name=filename, mime="text/csv", use_container_width=False)


def render_sidebar(improvements: pd.DataFrame, incidents: pd.DataFrame, updates: pd.DataFrame, section: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str, tuple[date, date]]:
    with st.sidebar:
        st.markdown("## OMNI\n**Governança operacional**")
        st.caption(f"Filtros de {section.lower()}")
        improvement_categories: list[str] = []
        improvement_priorities: list[str] = []
        improvement_sprints: list[str] = []
        improvement_search = ""
        incident_categories: list[str] = []
        incident_priorities: list[str] = []
        incident_states: list[str] = []
        incident_assignees: list[str] = []
        incident_groups: list[str] = []
        update_months: list[str] = []
        update_search = ""
        date_range: tuple[date, date] = (date.today(), date.today())
        if section == "Melhorias":
            improvement_categories = select_filter("Categoria", options(improvements, "Categoria"), "improvement_category")
            improvement_priorities = select_filter("Prioridade", options(improvements, "Prioridade"), "improvement_priority")
            improvement_sprints = select_filter("Sprint", options(improvements, "Sprint"), "improvement_sprint")
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
        else:
            update_months = select_filter("Mês", options(updates, "Mês"), "update_month")
            update_search = st.text_input("Busca textual", placeholder="Tema, PR ou serviço", key="update_search")
        st.divider()
        st.caption(f"Atualização automática: a cada {CACHE_TTL // 60 or 1} min")

    filtered_improvements = improvements.copy()
    filtered_improvements = apply_values(filtered_improvements, "Categoria", improvement_categories)
    filtered_improvements = apply_values(filtered_improvements, "Prioridade", improvement_priorities)
    filtered_improvements = apply_values(filtered_improvements, "Sprint", improvement_sprints)
    if improvement_search:
        query = improvement_search.casefold()
        searchable = filtered_improvements["Melhoria"].astype(str) + " " + filtered_improvements["Descrição"].astype(str)
        filtered_improvements = filtered_improvements[searchable.str.casefold().str.contains(query, na=False)]
    if len(date_range) == 2 and section == "Melhorias":
        filtered_improvements = filtered_improvements[filtered_improvements["Início"].notna() & filtered_improvements["Início"].dt.date.between(date_range[0], date_range[1])]
    filtered_incidents = incidents.copy()
    for column, selected in [("Categoria", incident_categories), ("Prioridade", incident_priorities), ("Estado", incident_states), ("Atribuição a", incident_assignees), ("Grupo de atribuição", incident_groups)]:
        filtered_incidents = apply_values(filtered_incidents, column, selected)
    if len(date_range) == 2:
        filtered_incidents = filtered_incidents[filtered_incidents["Atualizado em"].dt.date.between(date_range[0], date_range[1])]
    filtered_updates = updates.copy()
    filtered_updates = apply_values(filtered_updates, "Mês", update_months)
    if update_search:
        query = update_search.casefold()
        searchable = filtered_updates.astype(str).agg(" ".join, axis=1)
        filtered_updates = filtered_updates[searchable.str.casefold().str.contains(query, na=False)]
    return filtered_improvements, filtered_incidents, filtered_updates, improvement_search, date_range


def render_improvements(frame: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Resumo das melhorias</div>', unsafe_allow_html=True)
    start_values = frame["Início"].dropna()
    end_values = frame["Fim"].dropna()
    if not start_values.empty and not end_values.empty:
        period_start = start_values.min().strftime("%d/%m/%Y")
        period_end = end_values.max().strftime("%d/%m/%Y")
    elif not start_values.empty:
        period_start = start_values.min().strftime("%d/%m/%Y")
        period_end = start_values.max().strftime("%d/%m/%Y")
    elif not end_values.empty:
        period_start = end_values.min().strftime("%d/%m/%Y")
        period_end = end_values.max().strftime("%d/%m/%Y")
    else:
        period_start = "Não informado"
        period_end = "Não informado"
    st.caption(f"Período: {period_start} a {period_end}")
    total = len(frame)
    completed = int(frame["Status"].eq("Concluída").sum())
    developing = int(frame["Status"].eq("Em desenvolvimento").sum())
    validation = int(frame["Status"].eq("Em validação").sum())
    upcoming = int(frame["Status"].eq("Próximas entregas").sum())
    unreported = int(frame["Status"].eq("Não informado").sum())
    if frame.empty:
        st.info("Nenhuma melhoria corresponde aos filtros selecionados.")
        return
    status_order = ["Concluída", "Em desenvolvimento", "Em validação", "Próximas entregas", "Não informado"]
    status_counts = pd.DataFrame({"Status": status_order, "Quantidade": [completed, developing, validation, upcoming, unreported]})
    overview = st.columns(5)
    overview[0].metric("Total de melhorias", format_number(total))
    for column, label, value in zip(overview[1:], ["Concluídas", "Em desenvolvimento", "Em validação", "Próximas entregas"], [completed, developing, validation, upcoming]):
        column.metric(label, format_number(value))
    st.markdown('<div class="section-label">Acompanhamento por status</div>', unsafe_allow_html=True)
    status_chart = px.bar(
        status_counts,
        x="Status",
        y="Quantidade",
        text="Quantidade",
        title="Distribuição das melhorias",
        color="Status",
        color_discrete_map={"Concluída": "#10b981", "Em desenvolvimento": "#3b82f6", "Em validação": "#8b5cf6", "Próximas entregas": "#f59e0b", "Não informado": "#64748b"},
    )
    status_chart.update_traces(texttemplate="%{y:.0f}", textposition="outside", textfont_size=11, cliponaxis=False)
    st.plotly_chart(chart_figure(status_chart), use_container_width=True)

    st.markdown('<div class="section-label">Listagem por status</div>', unsafe_allow_html=True)
    list_columns = ["Categoria", "Melhoria", "Prioridade", "Sprint", "Status"]
    for status in status_order:
        status_frame = frame.loc[frame["Status"] == status, [c for c in list_columns if c in frame.columns]].copy()
        with st.expander(f"{status} ({format_number(len(status_frame))})", expanded=False):
            if status_frame.empty:
                st.caption("Nenhuma melhoria nesta categoria.")
            else:
                st.dataframe(status_frame, hide_index=True, use_container_width=True, height=min(280, 80 + len(status_frame) * 35))
    left, right = st.columns(2)
    with left:
        category_data = frame["Categoria"].replace("", "Não informado").value_counts().rename_axis("Categoria").reset_index(name="Quantidade")
        st.plotly_chart(chart_figure(px.pie(category_data, names="Categoria", values="Quantidade", hole=.55, title="Composição por categoria", color_discrete_sequence=["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444"])), use_container_width=True)
    with right:
        priority_data = frame["Prioridade"].replace("", "Não informado").value_counts().rename_axis("Prioridade").reset_index(name="Quantidade")
        st.plotly_chart(chart_figure(px.bar(priority_data, x="Prioridade", y="Quantidade", title="Volume por prioridade", color="Prioridade", color_discrete_sequence=["#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6"])), use_container_width=True)
    st.markdown('<div class="section-label">Detalhamento</div>', unsafe_allow_html=True)
    detail_statuses = st.multiselect(
        "Status",
        options=sorted(frame["Status"].dropna().astype(str).unique().tolist()),
        default=[],
        key="detail_improvement_status",
        placeholder="Todos",
    )
    if detail_statuses:
        frame = frame[frame["Status"].astype(str).isin(detail_statuses)].copy()
    table = frame[IMPROVEMENT_COLUMNS].sort_values(["Sprint", "Início", "Prioridade", "Categoria"])
    for column in ["Início", "Fim"]:
        table[column] = pd.to_datetime(table[column], errors="coerce").dt.strftime("%d/%m/%Y")
    csv_download(table, "omni_melhorias.csv", "⇩ Exportar melhorias")
    st.dataframe(table, hide_index=True, use_container_width=True, height=360)


def render_incidents(frame: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Central de incidentes</div>', unsafe_allow_html=True)
    st.caption("Acompanhamento e volumetria de falhas e interrupções sistêmicas relatadas no OMNI Sesi.")
    total = len(frame)
    closed = int(frame["Estado"].astype(str).str.casefold().isin(["encerrado(a)", "encerrado", "closed", "resolvido(a)", "resolvido", "cancelado(a)", "cancelado"]).sum())
    opened = total - closed
    insights = st.columns(4)
    if total and frame["Aberto(a)"].notna().any():
        daily = frame.dropna(subset=["Aberto(a)"]).copy()
        daily["Data"] = daily["Aberto(a)"].dt.date
        counts = daily["Data"].value_counts()
        peak_day, peak_count = counts.idxmax(), int(counts.max())
        quiet_day, quiet_count = counts.idxmin(), int(counts.min())
        weeks = max(daily["Data"].nunique() / 7, 1)
        months = max(daily["Data"].nunique() / 30, 1)
        insight_values = [
            ("MAIOR PICO DIÁRIO", f"{peak_count} incidentes em {peak_day.strftime('%d/%m/%Y')}", "#f59e0b"),
            ("MENOR VOLUME ATIVO", f"{quiet_count} incidentes em {quiet_day.strftime('%d/%m/%Y')}", "#10b981"),
            ("MÉDIA SEMANAL", f"Aprox. {round(total / weeks):.0f} / semana", "#3b82f6"),
            ("MÉDIA MENSAL", f"Aprox. {round(total / months):.0f} / mês", "#8b5cf6"),
        ]
        for column, (title, text, color) in zip(insights, insight_values):
            column.markdown(f'<div style="border:1px solid {color}55;background:{color}12;border-radius:.8rem;padding:.75rem;height:100%"><div style="color:{color};font-size:.68rem;font-weight:700;letter-spacing:.08em">{title}</div><div style="font-size:.82rem;margin-top:.45rem">{text}</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="incident-spacer"></div>', unsafe_allow_html=True)
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
    first_day = timeline["Data"].min()
    last_day = timeline["Data"].max()
    daily_counts = timeline.groupby("Data").size().rename("Incidentes").reset_index()
    daily_counts = daily_counts.sort_values("Data").reset_index(drop=True)
    daily_counts["Rótulo"] = daily_counts["Incidentes"].astype(int).astype(str)
    tick_step = max(1, len(daily_counts) // 9)
    tick_dates = daily_counts.loc[::tick_step, "Data"].tolist()
    if daily_counts["Data"].iloc[-1] not in tick_dates:
        tick_dates.append(daily_counts["Data"].iloc[-1])
    title = "Volume diário de incidentes"
    st.markdown(f'<div class="incident-caption">{format_date(first_day)} até {format_date(last_day)}</div>', unsafe_allow_html=True)
    bar_chart = px.bar(daily_counts, x="Data", y="Incidentes", title=title, text="Rótulo", color_discrete_sequence=["#3b82f6"])
    bar_chart.update_traces(
        texttemplate="%{text}",
        textposition="outside",
        textfont_size=12,
        cliponaxis=False,
        hovertemplate="Data: %{x|%d/%m/%Y}<br>Incidentes: %{y:.0f}<extra></extra>",
    )
    bar_chart.update_layout(height=430, bargap=0.25)
    bar_chart.update_xaxes(title=None, tickvals=tick_dates, tickformat="%d/%m/%Y", tickangle=-35, tickfont=dict(size=10), showgrid=False)
    bar_chart.update_yaxes(title="Incidentes", dtick=5, tickfont=dict(size=11), gridcolor="rgba(148,163,184,.16)")
    st.plotly_chart(chart_figure(bar_chart), use_container_width=True)

    st.markdown('<div class="section-label">Fila detalhada</div>', unsafe_allow_html=True)
    table = frame[INCIDENT_COLUMNS].sort_values("Atualizado em", ascending=False).copy()
    for column in ["Aberto(a)", "Atualizado em"]:
        table[column] = table[column].dt.strftime("%d/%m/%Y %H:%M")
    csv_download(table, "omni_incidentes.csv", "⇩ Exportar incidentes")
    st.dataframe(table, hide_index=True, use_container_width=True, height=420)


def main() -> None:
    inject_styles()
    improvements, incidents, updates, errors = prepare_data()
    st.markdown('<div class="hero"><div class="eyebrow">OMNI / Acompanhamento</div><h1>Painel de acompanhamento de atividades OMNI Sesi</h1><p>Visão executiva do portfólio de melhorias e da operação de incidentes, com dados atualizados a partir das fontes corporativas.</p></div>', unsafe_allow_html=True)
    for error in errors:
        st.warning(error)
    section = st.radio("Seção", ["Melhorias", "Incidentes"], horizontal=True, label_visibility="collapsed", key="active_section")
    filtered_improvements, filtered_incidents, filtered_updates, _, _ = render_sidebar(improvements, incidents, updates, section)
    if section == "Melhorias":
        render_improvements(filtered_improvements)
    else:
        render_incidents(filtered_incidents)


if __name__ == "__main__":
    main()