import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import streamlit.components.v1 as components

# Configuração da Página
st.set_page_config(
    page_title="Painel de Acompanhamento - OMNI Sesi",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Script para forçar a remoção de elementos flutuantes injetados pelo host
components.html(
    """
    <script>
        const removeElements = () => {
            const doc = window.parent.document;
            const selectors = [
                '[data-testid="stStatusWidget"]',
                '[data-testid="stAppCreatorBadge"]',
                '[data-testid="stAppViewerBadge"]',
                '.stAppBadge',
                '#viewerBadge'
            ];
            selectors.forEach(selector => {
                doc.querySelectorAll(selector).forEach(el => el.remove());
            });
        };
        setInterval(removeElements, 500);
    </script>
    """,
    height=0,
)

# Injeção de Estilos CSS Customizados
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

        /* Oculta menu, botão de deploy e barra superior */
        #MainMenu, 
        [data-testid="stAppDeployButton"], 
        [data-testid="stToolbar"] {
            display: none !important;
            visibility: hidden !important;
        }

        [data-testid="stHeader"] {
            background-color: transparent !important;
            z-index: 100 !important;
        }

        /* Aniquila rodapé e emblemas flutuantes */
        footer, 
        [data-testid="stFooter"], 
        [data-testid="stStatusWidget"], 
        [data-testid="stAppCreatorBadge"], 
        [data-testid="stAppViewerBadge"],
        .stAppBadge, 
        div[class*="viewerBadge"] {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            height: 0 !important;
            width: 0 !important;
            pointer-events: none !important;
        }

        [data-testid="stMainBlockContainer"] { 
            max-width: 1550px; 
            padding-top: 1.5rem !important; 
        }

        [data-testid="stSidebar"] {
            border-right: 1px solid rgba(128, 128, 128, 0.2);
        }

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

        /* Cartões Kanban */
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

# Função para carregar dados simulados ou reais
@st.cache_data
def load_data():
    # Substitua futuramente pelo carregamento real (CSV, Banco ou API DevOps)
    data_improvements = pd.DataFrame({
        'Melhoria': [
            'Integração de Cadastro Unificado', 
            'Dashboard de Produtividade SESI', 
            'Automação de Relatórios OMNI', 
            'Refatoração da API de Alertas',
            'Painel Executivo de Incidentes',
            'Módulo de Exportação PDF'
        ],
        'Categoria': ['Integração', 'Analytics', 'Automação', 'Backend', 'Analytics', 'Frontend'],
        'Prioridade': ['Alta', 'Média', 'Alta', 'Baixa', 'Média', 'Baixa'],
        'Status': ['Concluída', 'Em desenvolvimento', 'Em validação', 'Próximas entregas', 'Concluída', 'Em desenvolvimento'],
        'Descrição': [
            'Unifica os cadastros legados da base OMNI com validação em tempo real.',
            'Criação de visões analíticas por unidade operacional.',
            'Disparo automatizado de e-mails diários de status.',
            'Correção de gargalos de performance na rota principal.',
            'Consolidação de chamados críticos abertos no plantão.',
            'Permitir download direto dos relatórios formatados.'
        ],
        'Início': pd.to_datetime(['2026-07-10', '2026-08-01', '2026-08-15', '2026-09-01', '2026-07-15', '2026-09-05']),
        'Fim': pd.to_datetime(['2026-07-25', pd.NaT, pd.NaT, pd.NaT, '2026-07-30', pd.NaT])
    })

    data_incidents = pd.DataFrame({
        'Melhoria': ['Queda na API de Autenticação', 'Lentidão no Banco de Dados OMNI'],
        'Categoria': ['Infraestrutura', 'Banco de Dados'],
        'Prioridade': ['Alta', 'Alta'],
        'Status': ['Concluída', 'Em validação'],
        'Descrição': ['Instabilidade momentânea no provedor de SSO.', 'Pico de conexões simultâneas esgotou o pool.'],
        'Início': pd.to_datetime(['2026-07-12', '2026-08-10']),
        'Fim': pd.to_datetime(['2026-07-12', pd.NaT])
    })

    data_updates = pd.DataFrame({
        'Melhoria': ['Lançamento da Versão 2.1 OMNI'],
        'Categoria': ['Release'],
        'Prioridade': ['Média'],
        'Status': ['Concluída'],
        'Descrição': ['Deploy oficial com melhorias gerais de usabilidade e correções.'],
        'Início': pd.to_datetime(['2026-08-20']),
        'Fim': pd.to_datetime(['2026-08-20'])
    })

    return data_improvements, data_incidents, data_updates

def format_date(dt):
    if pd.isna(dt):
        return "N/D"
    if isinstance(dt, str):
        try:
            dt = pd.to_datetime(dt)
        except:
            return dt
    return dt.strftime('%d/%m/%Y')

def get_priority_style(priority):
    p = str(priority).strip().lower()
    if 'alta' in p:
        return 'rgba(239, 68, 68, 0.15)', '#ef4444'
    elif 'média' in p or 'media' in p:
        return 'rgba(245, 158, 11, 0.15)', '#f59e0b'
    else:
        return 'rgba(16, 185, 129, 0.15)', '#10b981'

def render_kanban_card(row: pd.Series) -> str:
    categoria = row['Categoria'] if row['Categoria'] else 'Geral'
    prioridade = row['Prioridade'] if row['Prioridade'] else 'Normal'
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
        <div class="kanban-meta" style="justify-content: flex-end;">
            <span>📅 {dt_inicio}</span>
        </div>
    </div>
    """

def render_sidebar(improvements, incidents, updates, section):
    st.sidebar.markdown("<h2 style='font-size: 1.2rem; margin-bottom: 0.5rem;'>OMNI</h2>", unsafe_allow_html=True)
    st.sidebar.markdown("<p style='font-size: 0.85rem; font-weight: 600; color: #3b82f6;'>Governança operacional</p>", unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Filtros de melhorias")

    # Filtro de Status multi-select
    all_statuses = ['Concluída', 'Em desenvolvimento', 'Em validação', 'Próximas entregas']
    selected_statuses = st.sidebar.multiselect("Status", all_statuses, default=all_statuses)

    # Categoria
    all_cats = ['Todos'] + sorted(list(improvements['Categoria'].dropna().unique()))
    selected_cat = st.sidebar.selectbox("Categoria", all_cats)

    # Prioridade
    all_prios = ['Todos'] + sorted(list(improvements['Prioridade'].dropna().unique()))
    selected_prio = st.sidebar.selectbox("Prioridade", all_prios)

    # Busca textual
    search_query = st.sidebar.text_input("Busca textual", placeholder="Melhoria ou descrição")

    # Intervalo de datas
    min_date = improvements['Início'].min()
    max_date = improvements['Início'].max()
    if pd.isna(min_date):
        min_date = datetime(2026, 1, 1).date()
    else:
        min_date = min_date.date()
        
    if pd.isna(max_date):
        max_date = datetime(2027, 12, 31).date()
    else:
        max_date = max_date.date()

    date_range = st.sidebar.date_input("Intervalo de início", value=(min_date, max_date))

    st.sidebar.markdown("---")
    st.sidebar.markdown("<div style='font-size: 0.75rem; opacity: 0.6;'>Atualização automática: a cada 5 min</div>", unsafe_allow_html=True)

    # Aplicação dos filtros em Melhorias
    filtered_improvements = improvements.copy()
    
    if selected_statuses:
        filtered_improvements = filtered_improvements[filtered_improvements["Status"].isin(selected_statuses)]
    if selected_cat != 'Todos':
        filtered_improvements = filtered_improvements[filtered_improvements["Categoria"] == selected_cat]
    if selected_prio != 'Todos':
        filtered_improvements = filtered_improvements[filtered_improvements["Prioridade"] == selected_prio]
    if search_query:
        q = search_query.lower()
        filtered_improvements = filtered_improvements[
            filtered_improvements["Melhoria"].str.lower().str.contains(q, na=False) |
            filtered_improvements["Descrição"].str.lower().str.contains(q, na=False)
        ]
    
    if len(date_range) == 2:
        inicio_dates = pd.to_datetime(filtered_improvements["Início"], errors='coerce').dt.date
        filtered_improvements = filtered_improvements[
            filtered_improvements["Início"].notna() & 
            inicio_dates.between(date_range[0], date_range[1])
        ]

    # Aplicação dos mesmos filtros básicos em Incidentes e Atualizações
    filtered_incidents = incidents.copy()
    if selected_statuses:
        filtered_incidents = filtered_incidents[filtered_incidents["Status"].isin(selected_statuses)]
    if selected_cat != 'Todos':
        filtered_incidents = filtered_incidents[filtered_incidents["Categoria"] == selected_cat]

    filtered_updates = updates.copy()

    return filtered_improvements, filtered_incidents, filtered_updates

def main():
    inject_styles()
    
    improvements, incidents, updates = load_data()

    # Seletor de Seção no topo da Sidebar
    section = st.sidebar.radio("Seção Principal", ["Melhorias", "Incidentes"], label_visibility="collapsed")

    filtered_improvements, filtered_incidents, filtered_updates = render_sidebar(improvements, incidents, updates, section)

    # Cabeçalho Principal (Hero)
    st.markdown("""
        <div class="hero">
            <div class="eyebrow">OMNI / Acompanhamento</div>
            <h1>Painel de acompanhamento de atividades OMNI Sesi</h1>
            <p style="opacity: 0.8; margin-bottom: 0;">Visão executiva do portfólio de melhorias e da operação de incidentes com fontes atualizadas.</p>
        </div>
    """, unsafe_allow_html=True)

    # Abas principais da Visão
    tab_visao, tab_kanban, tab_dados = st.tabs(["📈 Visão Executiva", "📋 Kanban Operacional", "🗄️ Base de Dados"])

    with tab_visao:
        st.markdown("<div class='section-label'>Indicadores Executivos</div>", unsafe_allow_html=True)
        
        total_melhorias = len(filtered_improvements)
        concluidas = len(filtered_improvements[filtered_improvements['Status'] == 'Concluída'])
        em_desenv = len(filtered_improvements[filtered_improvements['Status'] == 'Em desenvolvimento'])
        em_validacao = len(filtered_improvements[filtered_improvements['Status'] == 'Em validação'])
        proximas = len(filtered_improvements[filtered_improvements['Status'] == 'Próximas entregas'])

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total de melhorias", total_melhorias)
        col2.metric("Concluídas", concluidas)
        col3.metric("Em desenvolvimento", em_desenv)
        col4.metric("Em validação", em_validacao)
        col5.metric("Próximas entregas", proximas)

        st.markdown("<div class='section-label'>Acompanhamento por Status</div>", unsafe_allow_html=True)
        
        # Gráfico de Barras por Status
        status_counts = filtered_improvements['Status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Quantidade']
        
        if not status_counts.empty:
            color_map = {
                'Concluída': '#10b981',
                'Em desenvolvimento': '#3b82f6',
                'Em validação': '#8b5cf6',
                'Próximas entregas': '#f59e0b'
            }
            fig_status = px.bar(
                status_counts, 
                x='Status', 
                y='Quantidade', 
                color='Status',
                color_discrete_map=color_map,
                text='Quantidade'
            )
            fig_status.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#ffffff', family='DM Sans'),
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.15)'),
                showlegend=False,
                margin=dict(t=20, b=20, l=20, r=20)
            )
            st.plotly_chart(fig_status, use_container_width=True)
        else:
            st.info("Nenhum dado encontrado para os filtros selecionados.")

        st.markdown("<div class='section-label'>Composição por Categoria</div>", unsafe_allow_html=True)
        
        cat_counts = filtered_improvements['Categoria'].value_counts().reset_index()
        cat_counts.columns = ['Categoria', 'Quantidade']
        cat_counts = cat_counts.sort_values(by='Quantidade', ascending=True)

        if not cat_counts.empty:
            fig_cat = px.bar(
                cat_counts,
                x='Quantidade',
                y='Categoria',
                orientation='h',
                text='Quantidade',
                color='Quantidade',
                color_continuous_scale='Blues'
            )
            fig_cat.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#ffffff', family='DM Sans'),
                xaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.15)'),
                yaxis=dict(showgrid=False),
                coloraxis_showscale=False,
                margin=dict(t=20, b=20, l=20, r=20)
            )
            st.plotly_chart(fig_cat, use_container_width=True)
        else:
            st.info("Nenhuma categoria para exibir.")

    with tab_kanban:
        st.markdown("<div class='section-label'>Fluxo de Trabalho (Kanban)</div>", unsafe_allow_html=True)
        
        col_k1, col_k2, col_k3, col_k4 = st.columns(4)
        
        status_columns = [
            ("Próximas entregas", col_k1),
            ("Em desenvolvimento", col_k2),
            ("Em validação", col_k3),
            ("Concluída", col_k4)
        ]

        for status_name, col in status_columns:
            with col:
                st.markdown(f"**{status_name}**")
                subset = filtered_improvements[filtered_improvements['Status'] == status_name]
                
                if subset.empty:
                    st.markdown("<div style='font-size:0.8rem; opacity:0.5; padding: 0.5rem 0;'>Vazio</div>", unsafe_allow_html=True)
                else:
                    # Mostra os 3 primeiros cards diretamente
                    for _, row in subset.head(3).iterrows():
                        st.markdown(render_kanban_card(row), unsafe_allow_html=True)
                    
                    # Se houver mais de 3, agrupa o restante num expander retrátil
                    if len(subset) > 3:
                        with st.expander(f"➕ Ver mais {len(subset) - 3} itens"):
                            for _, row in subset.iloc[3:].iterrows():
                                st.markdown(render_kanban_card(row), unsafe_allow_html=True)

    with tab_dados:
        st.markdown("<div class='section-label'>Registros Detalhados</div>", unsafe_allow_html=True)
        st.dataframe(filtered_improvements, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()