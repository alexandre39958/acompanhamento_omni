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
    page_title="OMNI | Governança operacional",
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
CACHE_TTL = int(os.getenv("OMNI_CACHE_TTL_SECONDS", "300"))

IMPROVEMENT_COLUMNS = ["Categoria", "Melhoria", "Descrição", "Prioridade", "Sprint", "Início", "Fim", "Status"]
INCIDENT_COLUMNS = [
    "Número",
    "Aberto(a)",
    "Descrição resumida",
    "Solicitante",
    "Prioridade",
    "Estado",
    "Categoria",
    "Grupo de atribuição",
    "Atribuição a",
    "Atualizado em",
    "Sistema",
]


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
        :root { --ink:#f8fafc; --muted:#94a3b8; --slate-950:#020617; --slate-900:#0f172a; --slate-850:#151f32; --blue:#3b82f6; --green:#10b981; --red:#ef4444; --yellow:#f59e0b; --purple:#8b5cf6; --line:rgba(255,255,255,.09); }
        html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; color: var(--ink); }
        body { background: var(--slate-950); }
        .stApp { background: radial-gradient(circle at 0% 0%, rgba(59,130,246,.15), transparent 34rem), radial-gradient(circle at 100% 100%, rgba(139,92,246,.1), transparent 32rem), var(--slate-950); color: #f8fafc; }
        [data-testid="stAppViewContainer"] { background: transparent; }
        [data-testid="stHeader"] { background: rgba(2,6,23,.72); }
        [data-testid="stMainBlockContainer"] { max-width: 1450px; padding-top: 2rem; }
        h1, h2, h3 { font-family: 'Space Grotesk', sans-serif !important; letter-spacing: 0 !important; }
        [data-testid="stSidebar"] { background: linear-gradient(180deg, #0b1222, #020617); border-right: 1px solid var(--line); }
        [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
        [data-testid="stSidebar"] .stMultiSelect div[data-baseweb="select"], [data-testid="stSidebar"] input { background: rgba(255,255,255,.06); border-color: rgba(255,255,255,.12); }
        .hero { padding: 1.4rem 1.5rem 1.35rem; border: 1px solid var(--line); border-radius: 1rem; margin-bottom: 1.2rem; background: linear-gradient(110deg, rgba(255,255,255,.075), rgba(255,255,255,.025)); box-shadow: 0 8px 32px rgba(0,0,0,.3); }
        .eyebrow { color: #60a5fa; text-transform: uppercase; font-size: .72rem; font-weight: 700; letter-spacing: .12em; }
        .hero h1 { font-size: clamp(2rem, 4vw, 3.55rem); line-height: 1; margin: .28rem 0 .5rem; }
        .hero p { color: var(--muted); margin: 0; max-width: 760px; font-size: 1.02rem; }
        [data-testid="stMetric"] { background: linear-gradient(145deg, rgba(255,255,255,.075), rgba(255,255,255,.025)); border: 1px solid var(--line); padding: 1rem; border-radius: 1rem; box-shadow: 0 8px 32px rgba(0,0,0,.25); }
        [data-testid="stMetricLabel"] { color: var(--muted); }
        [data-testid="stMetricValue"] { font-family: 'Space Grotesk', sans-serif; color: var(--ink); }
        [data-testid="stMetricDelta"] { color: #60a5fa !important; }
        .section-label { color: #60a5fa; font-size: .75rem; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; margin: 1.5rem 0 .4rem; }
        .status-note { color: var(--muted); font-size: .85rem; }
        div[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 1rem; overflow: hidden; }
        button[data-baseweb="tab"] { font-weight: 600; color: #94a3b8; }
        button[data-baseweb="tab"][aria-selected="true"] { color: #60a5fa; }
        div[role="radiogroup"] { gap: .45rem; }
        div[role="radiogroup"] label { background: rgba(255,255,255,.045); border: 1px solid var(--line); border-radius: .7rem; padding: .35rem .8rem; }
        div[role="radiogroup"] label:has(input:checked) { background: rgba(59,130,246,.18); border-color: rgba(59,130,246,.65); }
        .incident-spacer { height: 1.25rem; }
        .incident-caption { color: #94a3b8; font-size: .78rem; margin: .1rem 0 .45rem; }
        div[data-testid="stAlert"] { background: rgba(245,158,11,.1); border-color: rgba(245,158,11,.35); }
        div[data-testid="stPlotlyChart"] { background: rgba(255,255,255,.035); border: 1px solid var(--line); border-radius: 1rem; padding: .25rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    px.defaults.template = "plotly_dark"


def chart_figure(figure):
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#cbd5e1",
        title_font_color="#f8fafc",
        margin=dict(l=28, r=28, t=56, b=28),
    )
    return figure


def format_number(value: int | float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def rounded_percent(value: int, total: int) -> str:
    return f"{round((value / total) * 100):.0f}%" if total else "0%"


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
        return "Homologação"
    if "backlog" in key:
        return "Backlog"
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


def prepare_data() -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    improvements, improvement_error = load_source(IMPROVEMENTS_SOURCE, "melhorias")
    incidents, incident_error = load_source(INCIDENTS_SOURCE, "incidentes")
    improvements = normalize_columns(
        improvements,
        {
            "Categoria": ["category"], "Melhoria": ["improvement", "titulo"], "Descrição": ["description"], "Prioridade": ["priority"],
            "Sprint": ["sprint", "ciclo", "iteracao"], "Início": ["inicio", "start", "data inicio"],
            "Fim": ["fim", "end", "data fim", "termino"], "Status": ["status", "estado"],
        },
    )
    incidents = normalize_columns(
        incidents,
        {
            "Número": ["numero", "number", "ticket", "incidente"], "Aberto(a)": ["aberto", "opened", "data abertura"],
            "Descrição resumida": ["descricao resumida", "short description", "descricao"], "Solicitante": ["requester"],
            "Prioridade": ["priority"], "Estado": ["state", "status"], "Categoria": ["category"],
            "Grupo de atribuição": ["assignment group", "grupo"], "Atribuição a": ["assigned to", "atribuido a", "analista"],
            "Atualizado em": ["updated", "updated at", "data atualizacao"], "Sistema": ["system", "sistema"],
        },
    )
    incidents["Aberto(a)"] = pd.to_datetime(incidents["Aberto(a)"], errors="coerce", dayfirst=True)
    incidents["Atualizado em"] = pd.to_datetime(incidents["Atualizado em"], errors="coerce", dayfirst=True)
    incidents["Atualizado em"] = incidents["Atualizado em"].fillna(incidents["Aberto(a)"])
    improvements["Início"] = improvements["Início"].map(parse_improvement_date)
    improvements["Fim"] = improvements["Fim"].map(parse_improvement_date)
    if improvements["Sprint"].astype(str).str.strip().eq("").all() and not improvements.empty:
        improvements["Sprint"] = "Backlog"
    improvements["Status"] = improvements["Status"].map(normalize_improvement_status)
    return improvements.fillna(""), incidents.fillna(""), [error for error in [improvement_error, incident_error] if error]


def options(frame: pd.DataFrame, column: str) -> list[str]:
    return sorted(value for value in frame[column].astype(str).unique() if value.strip())


def select_filter(label: str, values: list[str], key: str) -> list[str]:
    return st.multiselect(label, values, default=[], key=key, placeholder="Todos")


def apply_values(frame: pd.DataFrame, column: str, selected: list[str]) -> pd.DataFrame:
    return frame if not selected else frame[frame[column].astype(str).isin(selected)]


def csv_download(frame: pd.DataFrame, filename: str, label: str) -> None:
    payload = frame.to_csv(index=False).encode("utf-8-sig")
    st.download_button(label, data=payload, file_name=filename, mime="text/csv", use_container_width=False)


def render_sidebar(improvements: pd.DataFrame, incidents: pd.DataFrame, section: str) -> tuple[pd.DataFrame, pd.DataFrame, str, tuple[date, date]]:
    with st.sidebar:
        st.markdown("## OMNI\n**Governança operacional**")
        st.caption(f"Filtros de {section.lower()}")
        improvement_categories: list[str] = []
        improvement_priorities: list[str] = []
        improvement_sprints: list[str] = []
        improvement_statuses: list[str] = []
        improvement_search = ""
        incident_categories: list[str] = []
        incident_priorities: list[str] = []
        incident_states: list[str] = []
        incident_assignees: list[str] = []
        incident_groups: list[str] = []
        date_range: tuple[date, date] = (date.today(), date.today())
        if section == "Melhorias":
            improvement_categories = select_filter("Categoria", options(improvements, "Categoria"), "improvement_category")
            improvement_priorities = select_filter("Prioridade", options(improvements, "Prioridade"), "improvement_priority")
            improvement_sprints = select_filter("Sprint", options(improvements, "Sprint"), "improvement_sprint")
            improvement_statuses = select_filter("Status", options(improvements, "Status"), "improvement_status")
            improvement_search = st.text_input("Busca textual", placeholder="Melhoria ou descrição", key="improvement_search")
        else:
            incident_categories = select_filter("Categoria", options(incidents, "Categoria"), "incident_category")
            incident_priorities = select_filter("Prioridade", options(incidents, "Prioridade"), "incident_priority")
            incident_states = select_filter("Estado do chamado", options(incidents, "Estado"), "incident_state")
            incident_assignees = select_filter("Atribuição", options(incidents, "Atribuição a"), "incident_assignee")
            incident_groups = select_filter("Grupo de atribuição", options(incidents, "Grupo de atribuição"), "incident_group")
            valid_dates = incidents["Atualizado em"].dropna()
            min_date = valid_dates.min().date() if not valid_dates.empty else date.today() - timedelta(days=30)
            max_date = valid_dates.max().date() if not valid_dates.empty else date.today()
            date_range = st.date_input("Intervalo de atualização", value=(min_date, max_date), min_value=min_date, max_value=max_date, key="incident_date")
        st.divider()
        st.caption(f"Atualização automática: a cada {CACHE_TTL // 60 or 1} min")

    filtered_improvements = improvements.copy()
    filtered_improvements = apply_values(filtered_improvements, "Categoria", improvement_categories)
    filtered_improvements = apply_values(filtered_improvements, "Prioridade", improvement_priorities)
    filtered_improvements = apply_values(filtered_improvements, "Sprint", improvement_sprints)
    filtered_improvements = apply_values(filtered_improvements, "Status", improvement_statuses)
    if improvement_search:
        query = improvement_search.casefold()
        searchable = filtered_improvements["Melhoria"].astype(str) + " " + filtered_improvements["Descrição"].astype(str)
        filtered_improvements = filtered_improvements[searchable.str.casefold().str.contains(query, na=False)]
    filtered_incidents = incidents.copy()
    for column, selected in [("Categoria", incident_categories), ("Prioridade", incident_priorities), ("Estado", incident_states), ("Atribuição a", incident_assignees), ("Grupo de atribuição", incident_groups)]:
        filtered_incidents = apply_values(filtered_incidents, column, selected)
    if len(date_range) == 2:
        filtered_incidents = filtered_incidents[filtered_incidents["Atualizado em"].dt.date.between(date_range[0], date_range[1])]
    return filtered_improvements, filtered_incidents, improvement_search, date_range


def render_improvements(frame: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Portfólio de evolução</div>', unsafe_allow_html=True)
    st.caption(f"{len(frame):,} melhorias no recorte atual".replace(",", "."))
    total = len(frame)
    high = int(frame["Prioridade"].astype(str).str.casefold().isin(["alta", "altíssima", "altissima", "crítica", "critica"]).sum())
    pending = int(frame["Prioridade"].astype(str).str.strip().ne("").sum())
    completed = int(frame["Status"].eq("Concluída").sum())
    developing = int(frame["Status"].eq("Em desenvolvimento").sum())
    homologation = int(frame["Status"].eq("Homologação").sum())
    backlog = int(frame["Status"].eq("Backlog").sum())
    unreported = int(frame["Status"].eq("Não informado").sum())
    kpi = st.columns(4)
    kpi[0].metric("Total de melhorias", format_number(total))
    kpi[1].metric("Alta criticidade", format_number(high), delta=f"{rounded_percent(high, total)} do total" if total else None)
    kpi[2].metric("Concluídas", format_number(completed), delta=rounded_percent(completed, total))
    kpi[3].metric("Em desenvolvimento", format_number(developing), delta=rounded_percent(developing, total))
    if frame.empty:
        st.info("Nenhuma melhoria corresponde aos filtros selecionados.")
        return
    status_order = ["Concluída", "Em desenvolvimento", "Homologação", "Backlog", "Não informado"]
    status_counts = pd.DataFrame({"Status": status_order, "Quantidade": [completed, developing, homologation, backlog, unreported]})
    st.markdown('<div class="section-label">Acompanhamento por status</div>', unsafe_allow_html=True)
    status_chart = px.bar(
        status_counts,
        x="Status",
        y="Quantidade",
        text="Quantidade",
        title="Distribuição das melhorias",
        color="Status",
        color_discrete_map={"Concluída": "#10b981", "Em desenvolvimento": "#3b82f6", "Homologação": "#8b5cf6", "Backlog": "#f59e0b", "Não informado": "#64748b"},
    )
    status_chart.update_traces(texttemplate="%{y:.0f}", textposition="outside", textfont_size=11, cliponaxis=False)
    st.plotly_chart(chart_figure(status_chart), use_container_width=True)
    status_groups = st.columns(5)
    for column, label, value in zip(status_groups, ["Concluídas", "Em desenvolvimento", "Homologação", "Backlog", "Não informadas"], [completed, developing, homologation, backlog, unreported]):
        column.metric(label, format_number(value), delta=rounded_percent(value, total))
    st.markdown('<div class="section-label">Listagem por status</div>', unsafe_allow_html=True)
    list_columns = ["Categoria", "Melhoria", "Prioridade", "Sprint", "Status"]
    for status in status_order:
        status_frame = frame.loc[frame["Status"] == status, list_columns].copy()
        with st.expander(f"{status} ({format_number(len(status_frame))})", expanded=status == "Em desenvolvimento"):
            if status_frame.empty:
                st.caption("Nenhuma melhoria nesta categoria.")
            else:
                st.dataframe(status_frame, hide_index=True, use_container_width=True, height=min(280, 80 + len(status_frame) * 35))
    st.markdown('<div class="section-label">Planejamento por sprint</div>', unsafe_allow_html=True)
    schedule = frame[
        frame["Início"].notna()
        & frame["Fim"].notna()
        & frame["Início"].astype(str).str.strip().ne("")
        & frame["Fim"].astype(str).str.strip().ne("")
    ].copy()
    if not schedule.empty:
        schedule["Trabalho"] = schedule["Melhoria"].astype(str)
        schedule["Sprint"] = schedule["Sprint"].replace("", "Backlog")
        gantt = px.timeline(
            schedule,
            x_start="Início",
            x_end="Fim",
            y="Trabalho",
            color="Sprint",
            hover_data=["Categoria", "Prioridade", "Status"],
            title="Roadmap de melhorias",
            color_discrete_sequence=["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444"],
        )
        gantt.update_yaxes(autorange="reversed", title=None)
        gantt.update_xaxes(title=None, showgrid=True, gridcolor="rgba(148,163,184,.12)")
        st.plotly_chart(chart_figure(gantt), use_container_width=True)
    else:
        st.info("Adicione Início e Fim à fonte de melhorias para visualizar o roadmap por sprint.")
    left, right = st.columns(2)
    with left:
        category_data = frame["Categoria"].replace("", "Não informado").value_counts().rename_axis("Categoria").reset_index(name="Quantidade")
        st.plotly_chart(chart_figure(px.pie(category_data, names="Categoria", values="Quantidade", hole=.55, title="Composição por categoria", color_discrete_sequence=["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444"])), use_container_width=True)
    with right:
        priority_data = frame["Prioridade"].replace("", "Não informado").value_counts().rename_axis("Prioridade").reset_index(name="Quantidade")
        st.plotly_chart(chart_figure(px.bar(priority_data, x="Prioridade", y="Quantidade", title="Volume por prioridade", color="Prioridade", color_discrete_sequence=["#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6"])), use_container_width=True)
    st.markdown('<div class="section-label">Detalhamento</div>', unsafe_allow_html=True)
    table = frame[IMPROVEMENT_COLUMNS].sort_values(["Sprint", "Início", "Prioridade", "Categoria"])
    for column in ["Início", "Fim"]:
        table[column] = pd.to_datetime(table[column], errors="coerce").dt.strftime("%d/%m/%Y")
    csv_download(table, "omni_melhorias.csv", "⇩ Exportar melhorias")
    st.dataframe(table, hide_index=True, use_container_width=True, height=360)


def render_incidents(frame: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Central de incidentes ITSM</div>', unsafe_allow_html=True)
    st.caption(f"{len(frame):,} chamados no recorte atual".replace(",", "."))
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
            ("MAIOR PICO DIÁRIO", f"{peak_count} chamados em {peak_day.strftime('%d/%m/%Y')}", "#f59e0b"),
            ("MENOR VOLUME ATIVO", f"{quiet_count} chamados em {quiet_day.strftime('%d/%m/%Y')}", "#10b981"),
            ("MÉDIA SEMANAL", f"Aprox. {round(total / weeks):.0f} / semana", "#3b82f6"),
            ("MÉDIA MENSAL", f"Aprox. {round(total / months):.0f} / mês", "#8b5cf6"),
        ]
        for column, (title, text, color) in zip(insights, insight_values):
            column.markdown(f'<div style="border:1px solid {color}55;background:{color}12;border-radius:.8rem;padding:.75rem;height:100%"><div style="color:{color};font-size:.68rem;font-weight:700;letter-spacing:.08em">{title}</div><div style="color:#e2e8f0;font-size:.82rem;margin-top:.45rem">{text}</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="incident-spacer"></div>', unsafe_allow_html=True)
    kpi = st.columns(3)
    kpi[0].metric("Volume total", format_number(total))
    kpi[1].metric("Resolvidos / Encerrados", format_number(closed), delta=rounded_percent(closed, total))
    kpi[2].metric("Abertos / Pendentes", format_number(opened), delta=rounded_percent(opened, total))
    st.markdown('<div class="incident-spacer"></div>', unsafe_allow_html=True)
    if frame.empty:
        st.info("Nenhum incidente corresponde aos filtros selecionados.")
        return
    chart_a, chart_b = st.columns(2)
    with chart_a:
        timeline = frame.dropna(subset=["Aberto(a)"]).copy()
        timeline["Data"] = timeline["Aberto(a)"].dt.date
        timeline = timeline.groupby(["Data", "Categoria"], as_index=False).size().rename(columns={"size": "Chamados"})
        title = "Volume de abertura (dia a dia)"
        if not timeline.empty:
            st.markdown(f'<div class="incident-caption">{format_date(timeline["Data"].min())} até {format_date(timeline["Data"].max())}</div>', unsafe_allow_html=True)
        bar_chart = px.bar(timeline, x="Data", y="Chamados", color="Categoria", title=title, text="Chamados", color_discrete_sequence=["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b"])
        bar_chart.update_traces(texttemplate="%{y:.0f}", textposition="outside", textfont_size=10, cliponaxis=False)
        st.plotly_chart(chart_figure(bar_chart), use_container_width=True)
    with chart_b:
        state_data = frame["Estado"].replace("", "Não informado").value_counts().rename_axis("Estado").reset_index(name="Chamados")
        pie_chart = px.pie(state_data, names="Estado", values="Chamados", hole=.58, title="Distribuição do status atual", color_discrete_sequence=["#10b981", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6"])
        pie_chart.update_traces(textinfo="percent", texttemplate="%{percent:.0%}", textfont_size=11, hovertemplate="%{label}: %{value} chamados (%{percent:.0%})<extra></extra>")
        st.plotly_chart(chart_figure(pie_chart), use_container_width=True)
    fallback_system = frame["Categoria"].replace("", "Não informado")
    system = frame["Sistema"].where(frame["Sistema"].astype(str).str.strip().ne(""), fallback_system)
    stack = pd.DataFrame({"Sistema": system, "Prioridade": frame["Prioridade"].replace("", "Não informado")}).value_counts().reset_index(name="Chamados")
    st.plotly_chart(chart_figure(px.bar(stack, x="Sistema", y="Chamados", color="Prioridade", title="Sistemas x Prioridades", barmode="stack", color_discrete_sequence=["#ef4444", "#f59e0b", "#3b82f6", "#8b5cf6"])), use_container_width=True)
    st.markdown('<div class="section-label">Fila detalhada</div>', unsafe_allow_html=True)
    table_columns = [column for column in INCIDENT_COLUMNS if column != "Sistema"]
    table = frame[table_columns].sort_values("Atualizado em", ascending=False).copy()
    for column in ["Aberto(a)", "Atualizado em"]:
        table[column] = table[column].dt.strftime("%d/%m/%Y %H:%M")
    csv_download(table, "omni_incidentes.csv", "⇩ Exportar incidentes")
    st.dataframe(table, hide_index=True, use_container_width=True, height=420)


def main() -> None:
    inject_styles()
    improvements, incidents, errors = prepare_data()
    st.markdown('<div class="hero"><div class="eyebrow">OMNI / Acompanhamento</div><h1>Painel de Gestão - OMNI</h1><p>Visão executiva do portfólio de melhorias e da operação de incidentes, com dados atualizados a partir das fontes corporativas.</p></div>', unsafe_allow_html=True)
    for error in errors:
        st.warning(error)
    section = st.radio("Seção", ["Melhorias", "Incidentes"], horizontal=True, label_visibility="collapsed", key="active_section")
    filtered_improvements, filtered_incidents, _, _ = render_sidebar(improvements, incidents, section)
    if section == "Melhorias":
        render_improvements(filtered_improvements)
    else:
        render_incidents(filtered_incidents)


if __name__ == "__main__":
    main()