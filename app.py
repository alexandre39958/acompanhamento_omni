from __future__ import annotations

import html
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
MAX_PAYLOAD_BYTES = 50 * 1024 * 1024  # Limite de segurança de 50 MB

# Mapeamento oficial de cores por status
STATUS_COLOR_MAP = {
    "Próximas entregas": "#f59e0b",
    "Em desenvolvimento": "#3b82f6",
    "Em validação": "#8b5cf6",
    "Concluída": "#10b981",
}


# Leitura segura de variáveis de ambiente ou segredos do Streamlit
def setting(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value:
        return value
    try:
        value = st.secrets.get(name)
    except (FileNotFoundError, KeyError):
        value = None
    return str(value) if value else default


# Fontes de dados lidas via secrets/env
IMPROVEMENTS_SOURCE = setting("OMNI_MELHORIAS_CSV_URL")
INCIDENTS_SOURCE = setting("OMNI_INCIDENTES_CSV_URL")
UPDATES_SOURCE = setting("OMNI_ATUALIZACOES_CSV_URL")
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
    "Descrição",
    "Solicitante",
    "Estado",
    "Atribuição a",
    "Atualizado em",
]


# Injeção dos estilos CSS globais
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
        }

        /* 1. Oculta menus padrão e deploy do Streamlit */
        #MainMenu, 
        [data-testid="stAppDeployButton"], 
        [data-testid="stToolbar"] {
            display: none !important;
            visibility: hidden !important;
        }

        [data-testid="stHeader"] {
            background-color: transparent !important;
            z-index: 99 !important;
        }

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

        [data-testid="stMainBlockContainer"] { 
            max-width: 1600px; 
            padding-top: 1.5rem !important; 
        }

        /* 2. Barra lateral compacta, esguia e organizada */
        [data-testid="stSidebar"] {
            min-width: 260px !important;
            max-width: 275px !important;
            width: 270px !important;
            border-right: 1px solid rgba(128, 128, 128, 0.2);
        }

        [data-testid="stSidebarUserContent"] {
            padding: 1rem 0.75rem 1.5rem 0.75rem !important;
        }

        /* Reduz espaçamento vertical entre filtros da sidebar */
        [data-testid="stSidebar"] [data-testid="stElementContainer"] {
            margin-bottom: 0.25rem !important;
        }

        [data-testid="stSidebar"] label {
            font-size: 0.75rem !important;
            font-weight: 600 !important;
            margin-bottom: 0.1rem !important;
            color: rgba(255, 255, 255, 0.85) !important;
        }

        [data-testid="stSidebar"] .stMultiSelect div[data-baseweb="select"] > div {
            min-height: 1.95rem !important;
            padding-top: 0.05rem !important;
            padding-bottom: 0.05rem !important;
            font-size: 0.78rem !important;
        }

        [data-testid="stSidebar"] input {
            font-size: 0.78rem !important;
            height: 1.95rem !important;
        }

        /* 3. BOTÃO DE REABRIR A SIDEBAR SEMPRE VISÍVEL COM DESTAQUE */
        [data-testid="stSidebarCollapsedControl"] {
            display: flex !important;
            visibility: visible !important;
            position: fixed !important;
            top: 0.75rem !important;
            left: 0.75rem !important;
            z-index: 999999 !important;
            opacity: 1 !important;
        }

        [data-testid="stSidebarCollapsedControl"] button {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            background-color: var(--secondary-background-color) !important;
            border: 1px solid rgba(128, 128, 128, 0.4) !important;
            border-radius: 0.5rem !important;
            width: 2.2rem !important;
            height: 2.2rem !important;
            color: #ffffff !important;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35) !important;
            cursor: pointer !important;
        }

        [data-testid="stSidebarCollapsedControl"] svg,
        [data-testid="stSidebarCollapsedControl"] path {
            fill: #ffffff !important;
            stroke: #ffffff !important;
            color: #ffffff !important;
        }

        /* Hero Header */
        .hero {
            padding: 1.3rem 1.5rem;
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
            font-size: clamp(1.8rem, 3.5vw, 2.8rem);
            line-height: 1.1;
            margin: .25rem 0 .4rem;
        }

        /* Cartões de Métricas */
        [data-testid="stMetric"] {
            background: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            padding: 0.85rem 1rem;
            border-radius: 0.85rem;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
        }

        .section-label {
            color: var(--primary-color);
            font-size: .8rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: .1em;
            margin: 1.3rem 0 .4rem;
        }

        div[data-testid="stPlotlyChart"] {
            background: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            border-radius: 1rem;
            padding: .5rem;
        }

        /* Container do Cartão Kanban */
        div[class*="st-key-cont_card_"] {
            position: relative !important;
            margin-bottom: 0.75rem !important;
            transition: transform 0.15s ease;
        }
        div[class*="st-key-cont_card_"]:hover {
            transform: translateY(-2px);
        }
        div[class*="st-key-cont_card_"]:hover .kanban-card {
            border-color: var(--primary-color) !important;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12) !important;
        }

        /* Cartão Kanban */
        .kanban-card {
            background: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            border-radius: 0.75rem;
            padding: 0.85rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.03);
            transition: border-color 0.15s ease, box-shadow 0.15s ease;
            cursor: pointer;
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
            justify-content: space-between;
            margin-top: 0.4rem;
            padding-top: 0.35rem;
            border-top: 1px dashed rgba(128,128,128,0.2);
        }

        /* Botão invisível sobreposto cobrindo todo o cartão */
        div[class*="st-key-cont_card_"] div[data-testid="stElementContainer"]:has(.stButton) {
            position: absolute !important;
            top: 0 !important;
            left: 0 !important;
            width: 100% !important;
            height: 100% !important;
            z-index: 5 !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        div[class*="st-key-cont_card_"] .stButton {
            width: 100% !important;
            height: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        div[class*="st-key-cont_card_"] .stButton > button {
            width: 100% !important;
            height: 100% !important;
            opacity: 0 !important;
            border: none !important;
            background: transparent !important;
            cursor: pointer !important;
            padding: 0 !important;
            margin: 0 !important;
        }

        /* Janela Modal compacta e elegante */
        div[role="dialog"] {
            width: 760px !important;
            max-width: 90vw !important;
            border-radius: 1rem !important;
            border: 1px solid rgba(128, 128, 128, 0.25) !important;
            background-color: var(--secondary-background-color) !important;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.45) !important;
            overflow: hidden !important;
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
        return "Próximas entregas"
    key = canonical(value)
    if not key:
        return "Próximas entregas"
    if any(term in key for term in ["conclu", "finaliz", "encerr", "resolvid"]):
        return "Concluída"
    if any(term in key for term in ["desenvolv", "andamento", "execucao", "fazendo", "progresso"]):
        return "Em desenvolvimento"
    if "homolog" in key or "validac" in key:
        return "Em validação"
    return "Próximas entregas"


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
            return pd.DataFrame(), f"A URL de {source_name} não está configurada (defina via ambiente ou .streamlit/secrets.toml)."
        
        if source.startswith(("http://", "https://")):
            request = Request(downloadable_url(source), headers={"User-Agent": "OMNI-dashboard/1.0"})
            with urlopen(request, timeout=30) as response:
                payload = response.read(MAX_PAYLOAD_BYTES + 1)
                if len(payload) > MAX_PAYLOAD_BYTES:
                    return pd.DataFrame(), f"A fonte de {source_name} excede o limite seguro de 50 MB."
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
            "Número": ["numero", "number", "ticket"],
            "Aberto(a)": ["aberto", "opened"],
            "Descrição": ["descricao", "resumo", "short description", "short_description"],
            "Descrição resumida": ["descricao resumida", "descricao resumid", "resumo curto"],
            "Solicitante": ["requester"],
            "Prioridade": ["priority"],
            "Estado": ["state", "status"],
            "Categoria": ["category"],
            "Grupo de atribuição": ["assignment group", "grupo de atribuicao"],
            "Atribuição a": ["assigned to", "atribuicao a"],
            "Atualizado em": ["updated", "atualizado em"],
            "Código de resolução": ["codigo de resolucao", "resolucao", "fechamento"],
            "Sistema": ["system"],
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


def get_priority_style(priority_value: str) -> tuple[str, str]:
    key = canonical(priority_value)
    if any(term in key for term in ["altissima", "alta", "alto", "urgente"]):
        return "rgba(239, 68, 68, 0.15)", "#ef4444"
    if any(term in key for term in ["media", "medio", "moderada"]):
        return "rgba(245, 158, 11, 0.15)", "#f59e0b"
    if any(term in key for term in ["baixa", "baixo"]):
        return "rgba(16, 185, 129, 0.15)", "#10b981"
    return "rgba(100, 116, 139, 0.15)", "#64748b"


def render_kanban_card(row: pd.Series) -> str:
    categoria = html.escape(str(row["Categoria"])) if row["Categoria"] else "Geral"
    prioridade = html.escape(str(row["Prioridade"])) if row["Prioridade"] else "Normal"
    responsavel = html.escape(str(row["Profissional alocado"])) if row["Profissional alocado"] else "Não atribuído"
    dt_inicio = html.escape(format_date(row["Início"]))
    
    desc_raw = str(row["Descrição"])
    if len(desc_raw) > 80:
        desc_raw = desc_raw[:80] + "..."
    desc = html.escape(desc_raw)
    melhoria = html.escape(str(row["Melhoria"]))
        
    prio_bg, prio_color = get_priority_style(prioridade)

    return f"""
    <div class="kanban-card">
        <div class="kanban-card-title">{melhoria}</div>
        <div>
            <span class="kanban-badge" style="background:rgba(59, 130, 246, 0.15); color:#3b82f6;">🏷️ {categoria}</span>
            <span class="kanban-badge" style="background:{prio_bg}; color:{prio_color};">● {prioridade}</span>
        </div>
        <div style="font-size: 0.78rem; opacity: 0.8; margin-top: 0.35rem; line-height: 1.35;">{desc}</div>
        <div class="kanban-meta">
            <span>👤 {responsavel}</span>
            <span>📅 {dt_inicio}</span>
        </div>
    </div>
    """


def render_modal_content(row: pd.Series) -> None:
    melhoria = html.escape(str(row["Melhoria"]))
    categoria = html.escape(str(row["Categoria"] or "Geral"))
    prioridade = html.escape(str(row["Prioridade"] or "Normal"))
    status = html.escape(str(row["Status"] or "Próximas entregas"))
    responsavel = html.escape(str(row["Profissional alocado"] or "Não atribuído"))
    desc = str(row["Descrição"]) if row["Descrição"] else "Nenhuma descrição detalhada informada."
    
    prio_bg, prio_color = get_priority_style(prioridade)
    header_bg = STATUS_COLOR_MAP.get(str(row["Status"]), "#3b82f6")

    st.markdown(
        f"""
        <style>
        div[role="dialog"] button[aria-label="Close"],
        [data-testid="stDialog"] button[aria-label="Close"] {{
            position: absolute !important;
            top: 0.95rem !important;
            right: 1.15rem !important;
            z-index: 100000 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            width: 2rem !important;
            height: 2rem !important;
            background: rgba(0, 0, 0, 0.25) !important;
            border-radius: 50% !important;
            border: none !important;
            color: #ffffff !important;
            opacity: 1 !important;
            visibility: visible !important;
            cursor: pointer !important;
        }}
        div[role="dialog"] button[aria-label="Close"] svg,
        div[role="dialog"] button[aria-label="Close"] path {{
            fill: #ffffff !important;
            stroke: #ffffff !important;
            color: #ffffff !important;
            width: 1rem !important;
            height: 1rem !important;
        }}
        </style>
        <div style="background-color: {header_bg}; margin: -3.6rem -1.5rem 1rem -1.5rem; padding: 1.7rem 1.4rem 0.9rem 1.4rem; border-top-left-radius: 0.85rem; border-top-right-radius: 0.85rem; display: flex; align-items: center; justify-content: space-between; border-bottom: 2px solid rgba(255, 255, 255, 0.2);">
            <span style="color: #ffffff !important; font-size: 1.05rem; font-weight: 700; font-family: 'Space Grotesk', sans-serif;">
                Demanda / Detalhes do Card
            </span>
            <span style="background: rgba(255, 255, 255, 0.25); color: #ffffff !important; font-weight: 700; font-size: 0.78rem; padding: 0.22rem 0.75rem; border-radius: 12px; margin-right: 3.2rem;">
                📌 {status}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div style="margin-bottom: 0.85rem;">
            <div style="font-size: 0.68rem; font-weight: 700; text-transform: uppercase; color: var(--primary-color); letter-spacing: 0.1em; margin-bottom: 0.15rem;">
                Melhoria
            </div>
            <h3 style="margin: 0 0 0.45rem 0; font-size: 1.25rem; line-height: 1.3; color: #ffffff;">{melhoria}</h3>
            <div style="display: flex; gap: 0.35rem; flex-wrap: wrap;">
                <span class="kanban-badge" style="background:rgba(59, 130, 246, 0.15); color:#3b82f6; font-size:0.72rem; padding: 0.18rem 0.5rem;">🏷️ {categoria}</span>
                <span class="kanban-badge" style="background:{prio_bg}; color:{prio_color}; font-size:0.72rem; padding: 0.18rem 0.5rem;">● {prioridade}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_desc, col_meta = st.columns([1.9, 1.1], gap="medium")

    with col_desc:
        st.markdown("<p style='font-weight: 700; font-size: 0.82rem; margin-bottom: 0.3rem; color: #ffffff;'>📝 Descrição Completa</p>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div style="background: rgba(128, 128, 128, 0.06); border: 1px solid rgba(128, 128, 128, 0.2); border-radius: 0.5rem; padding: 0.75rem 0.9rem; font-size: 0.84rem; line-height: 1.45; white-space: pre-wrap; min-height: 80px; color: #ffffff;">
                {html.escape(desc)}
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_meta:
        st.markdown("<p style='font-weight: 700; font-size: 0.82rem; margin-bottom: 0.3rem; color: #ffffff;'>⚙ Detalhes e Prazos</p>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div style="background: rgba(128, 128, 128, 0.06); border: 1px solid rgba(128, 128, 128, 0.2); border-radius: 0.5rem; padding: 0.7rem 0.85rem; font-size: 0.8rem; line-height: 1.4; color: #ffffff;">
                <p style="margin-bottom: 0.4rem;"><strong>👤 Responsável:</strong><br><span style="opacity: 0.9;">{responsavel}</span></p>
                <p style="margin-bottom: 0.4rem;"><strong>📅 Início:</strong> {format_date(row['Início'])}</p>
                <p style="margin-bottom: 0;"><strong>🏁 Previsão:</strong> {format_date(row['Fim'])}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<div style='margin-top: 0.6rem;'></div>", unsafe_allow_html=True)
        if st.button("✕ Fechar janela", key="close_card_modal", use_container_width=True):
            st.rerun()


dialog_decorator = getattr(st, "dialog", getattr(st, "experimental_dialog", None))

if dialog_decorator:
    try:
        @dialog_decorator(title=" ", width="large")
        def show_card_details(row: pd.Series):
            render_modal_content(row)
    except TypeError:
        @dialog_decorator(" ")
        def show_card_details(row: pd.Series):
            render_modal_content(row)
else:
    def show_card_details(row: pd.Series):
        render_modal_content(row)


def render_kanban_board(frame: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Quadro Kanban de Melhorias</div>', unsafe_allow_html=True)
    
    columns_config = [
        {"title": "Próximas entregas", "color": "#f59e0b", "bg": "#f59e0b18"},
        {"title": "Em desenvolvimento", "color": "#3b82f6", "bg": "#3b82f618"},
        {"title": "Em validação", "color": "#8b5cf6", "bg": "#8b5cf618"},
        {"title": "Concluída", "color": "#10b981", "bg": "#10b98118"},
    ]

    cols = st.columns(len(columns_config))
    CARDS_LIMITE_INICIAL = 1

    for col_idx, (col, cfg) in enumerate(zip(cols, columns_config)):
        status_name = cfg["title"]
        items = frame[frame["Status"] == status_name]
        
        with col:
            st.markdown(
                f"""
                <div style="background:{cfg['bg']}; border-top: 3px solid {cfg['color']}; padding: 8px 12px; border-radius: 8px 8px 0 0; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 700; font-size: 0.88rem;">{html.escape(status_name)}</span>
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
                
                for idx, (_, row) in enumerate(visible_items.iterrows()):
                    card_uid = f"card_vis_{col_idx}_{idx}_{row.name}"
                    with st.container(key=f"cont_{card_uid}"):
                        st.markdown(render_kanban_card(row), unsafe_allow_html=True)
                        if st.button("Abrir", key=f"btn_{card_uid}"):
                            show_card_details(row)
                
                if not hidden_items.empty:
                    with st.expander(f"➕ Ver mais {len(hidden_items)} item(ns)", expanded=False):
                        for idx, (_, row) in enumerate(hidden_items.iterrows()):
                            card_uid = f"card_hid_{col_idx}_{idx}_{row.name}"
                            with st.container(key=f"cont_{card_uid}"):
                                st.markdown(render_kanban_card(row), unsafe_allow_html=True)
                                if st.button("Abrir", key=f"btn_{card_uid}"):
                                    show_card_details(row)


# Barra lateral com filtros compactos
def render_sidebar(improvements: pd.DataFrame, incidents: pd.DataFrame, updates: pd.DataFrame, section: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    with st.sidebar:
        st.markdown(
            """
            <div style="margin-bottom: 0.65rem;">
                <div style="font-size: 1.1rem; font-weight: 700; font-family: 'Space Grotesk', sans-serif;">OMNI</div>
                <div style="font-size: 0.68rem; font-weight: 600; text-transform: uppercase; color: var(--primary-color); letter-spacing: 0.08em;">Governança operacional</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(f"Filtros de {section.lower()}")
        improvement_statuses, improvement_categories, improvement_priorities = [], [], []
        improvement_search = ""
        incident_categories, incident_priorities, incident_states, incident_assignees, incident_groups = [], [], [], [], []
        incident_search = ""
        update_months = []
        date_range = (date.today(), date.today())
        
        if section == "Melhorias":
            improvement_search = st.text_input("Busca textual", placeholder="Nome ou descrição", key="imp_search")
            improvement_statuses = select_filter("Status", options(improvements, "Status"), "imp_status")
            improvement_categories = select_filter("Categoria", options(improvements, "Categoria"), "imp_cat")
            improvement_priorities = select_filter("Prioridade", options(improvements, "Prioridade"), "imp_prio")
            valid_dates = improvements["Início"].dropna()
            min_date = valid_dates.min().date() if not valid_dates.empty else date.today() - timedelta(days=30)
            max_date = valid_dates.max().date() if not valid_dates.empty else date.today()
            date_range = st.date_input("Início", value=(min_date, max_date), min_value=min_date, max_value=max_date, key="imp_date")
        elif section == "Incidentes":
            incident_search = st.text_input("Busca textual", placeholder="Número, autor, texto", key="inc_search")
            incident_states = select_filter("Estado", options(incidents, "Estado"), "inc_state")
            incident_priorities = select_filter("Prioridade", options(incidents, "Prioridade"), "inc_prio")
            incident_categories = select_filter("Categoria", options(incidents, "Categoria"), "inc_cat")
            incident_assignees = select_filter("Atribuição", options(incidents, "Atribuição a"), "inc_assignee")
            incident_groups = select_filter("Grupo de atribuição", options(incidents, "Grupo de atribuição"), "inc_group")
            valid_dates = incidents["Atualizado em"].dropna()
            min_date = valid_dates.min().date() if not valid_dates.empty else date.today() - timedelta(days=30)
            max_date = valid_dates.max().date() if not valid_dates.empty else date.today()
            date_range = st.date_input("Atualizado em", value=(min_date, max_date), min_value=min_date, max_value=max_date, key="inc_date")
            
        st.divider()
        st.caption(f"Atualização: a cada {CACHE_TTL // 60 or 1} min")

    # Filtros de Melhorias
    filtered_improvements = improvements.copy()
    filtered_improvements = apply_values(filtered_improvements, "Status", improvement_statuses)
    filtered_improvements = apply_values(filtered_improvements, "Categoria", improvement_categories)
    filtered_improvements = apply_values(filtered_improvements, "Prioridade", improvement_priorities)
    if improvement_search:
        query = improvement_search.casefold()
        searchable = filtered_improvements["Melhoria"].astype(str) + " " + filtered_improvements["Descrição"].astype(str)
        filtered_improvements = filtered_improvements[searchable.str.casefold().str.contains(query, na=False)]
    
    if len(date_range) == 2 and section == "Melhorias":
        start_ts = pd.Timestamp(date_range[0])
        end_ts = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        filtered_improvements = filtered_improvements[
            filtered_improvements["Início"].isna() | 
            filtered_improvements["Início"].between(start_ts, end_ts)
        ]
    
    # Filtros de Incidentes
    filtered_incidents = incidents.copy()
    for col, sel in [("Categoria", incident_categories), ("Prioridade", incident_priorities), ("Estado", incident_states), ("Atribuição a", incident_assignees), ("Grupo de atribuição", incident_groups)]:
        filtered_incidents = apply_values(filtered_incidents, col, sel)
        
    if incident_search:
        query = incident_search.casefold()
        searchable = (
            filtered_incidents["Número"].astype(str) + " " +
            filtered_incidents["Descrição"].astype(str) + " " +
            filtered_incidents["Solicitante"].astype(str)
        )
        filtered_incidents = filtered_incidents[searchable.str.casefold().str.contains(query, na=False)]

    if len(date_range) == 2 and section == "Incidentes":
        start_ts = pd.Timestamp(date_range[0])
        end_ts = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        filtered_incidents = filtered_incidents[
            filtered_incidents["Atualizado em"].isna() | 
            filtered_incidents["Atualizado em"].between(start_ts, end_ts)
        ]
    
    filtered_updates = apply_values(updates.copy(), "Mês", update_months)
    return filtered_improvements, filtered_incidents, filtered_updates


# Painel de Melhorias
def render_improvements(frame: pd.DataFrame) -> None:
    start_values = frame["Início"].dropna()
    end_values = frame["Fim"].dropna()
    if not start_values.empty and not end_values.empty:
        period_str = f"Período: {start_values.min().strftime('%d/%m/%Y')} a {end_values.max().strftime('%d/%m/%Y')}"
    else:
        period_str = "Período:  "
    st.caption(period_str)
    
    if frame.empty:
        st.info("Nenhuma melhoria encontrada para os filtros selecionados.")
        return

    total = len(frame)
    completed = int(frame["Status"].eq("Concluída").sum())
    developing = int(frame["Status"].eq("Em desenvolvimento").sum())
    validation = int(frame["Status"].eq("Em validação").sum())
    upcoming = int(frame["Status"].eq("Próximas entregas").sum())
    
    # Cálculo das porcentagens de avanço
    completion_rate = (completed / total * 100) if total > 0 else 0
    in_progress_rate = ((completed + validation + developing) / total * 100) if total > 0 else 0

    # 1. Indicadores Executivos (com % de Conclusão)
    st.markdown('<div class="section-label">Indicadores executivos</div>', unsafe_allow_html=True)
    overview = st.columns(6)
    overview[0].metric("Total", format_number(total))
    overview[1].metric("Concluídas", format_number(completed))
    overview[2].metric("Em validação", format_number(validation))
    overview[3].metric("Em andamento", format_number(developing))
    overview[4].metric("Backlog", format_number(upcoming))
    overview[5].metric("Taxa de Entrega", f"{completion_rate:.1f}%", help="Percentual de melhorias entregues em relação ao total")

    # 2. Barra de Progresso Executiva Multi-Estágio
    pct_concl = (completed / total * 100) if total > 0 else 0
    pct_val = (validation / total * 100) if total > 0 else 0
    pct_dev = (developing / total * 100) if total > 0 else 0
    pct_upc = (upcoming / total * 100) if total > 0 else 0

    st.markdown(
        f"""
        <div style="margin: 0.75rem 0 1.25rem 0;">
            <div style="display: flex; justify-content: space-between; font-size: 0.76rem; font-weight: 700; margin-bottom: 0.35rem;">
                <span>Progresso do Portfólio ({in_progress_rate:.1f}% em andamento ou concluído)</span>
                <span style="color: #10b981;">{completion_rate:.1f}% Concluído</span>
            </div>
            <div style="height: 10px; width: 100%; background: rgba(128, 128, 128, 0.2); border-radius: 6px; overflow: hidden; display: flex;">
                <div style="width: {pct_concl}%; background-color: #10b981;" title="Concluídas: {pct_concl:.1f}%"></div>
                <div style="width: {pct_val}%; background-color: #8b5cf6;" title="Em validação: {pct_val:.1f}%"></div>
                <div style="width: {pct_dev}%; background-color: #3b82f6;" title="Em desenvolvimento: {pct_dev:.1f}%"></div>
                <div style="width: {pct_upc}%; background-color: #f59e0b;" title="Próximas entregas: {pct_upc:.1f}%"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 3. Quadro Kanban
    render_kanban_board(frame)

    # 4. Volume atual por status
    st.markdown('<div class="section-label">Acompanhamento por status</div>', unsafe_allow_html=True)
    status_counts = pd.DataFrame({
        "Status": ["Concluída", "Em desenvolvimento", "Em validação", "Próximas entregas"],
        "Quantidade": [completed, developing, validation, upcoming]
    })
    status_counts = status_counts[status_counts["Quantidade"] > 0]
    
    status_chart = px.bar(
        status_counts,
        x="Status",
        y="Quantidade",
        text="Quantidade",
        title="Volume atual por status",
        color="Status",
        color_discrete_map={"Concluída": "#10b981", "Em desenvolvimento": "#3b82f6", "Em validação": "#8b5cf6", "Próximas entregas": "#f59e0b"},
    )
    status_chart.update_traces(texttemplate="%{y:.0f}", textposition="outside", textfont_size=11, cliponaxis=False)
    st.plotly_chart(chart_figure(status_chart), use_container_width=True)

    # 5. Análise de Categoria e Prioridade
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
                "Altíssima": "#ef4444",
                "Alta": "#ef4444",
                "Alto": "#ef4444",
                "Média": "#f59e0b",
                "Médio": "#f59e0b",
                "Moderada": "#f59e0b",
                "Baixa": "#10b981",
                "Baixo": "#10b981",
                "Não informado": "#64748b"
            }
        )
        st.plotly_chart(chart_figure(priority_chart), use_container_width=True)

    # 6. Exportação
    st.markdown("---")
    table_to_export = frame[IMPROVEMENT_COLUMNS].copy()
    for col in ["Início", "Fim"]:
        table_to_export[col] = pd.to_datetime(table_to_export[col], errors="coerce").dt.strftime("%d/%m/%Y")
    csv_download(table_to_export, "omni_melhorias.csv", "⇩ Exportar melhorias filtradas em CSV")


# Painel de Incidentes
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
    
    st.markdown(
        '<div class="hero"><div class="eyebrow">OMNI / Acompanhamento</div><h1>Painel de acompanhamento de atividades OMNI Sesi</h1><p>Visão executiva do portfólio de melhorias e da operação de incidentes com fontes atualizadas.</p></div>',
        unsafe_allow_html=True,
    )
    
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