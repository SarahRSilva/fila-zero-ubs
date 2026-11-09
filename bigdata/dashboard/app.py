"""Dashboard da gestora (Streamlit) sobre a camada gold do data lake.

Uso:
    streamlit run bigdata/dashboard/app.py
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

GOLD = Path(os.getenv("LAKE_GOLD") or Path(__file__).resolve().parents[1] / "lake" / "gold")

AZUL, LARANJA, CINZA = "#2a78d6", "#eb6834", "#898781"
COR_TRIAGEM = {"verde": "#0ca30c", "amarelo": "#fab219", "vermelho": "#d03b3b"}
TURNOS = {"manha": "Manhã", "tarde": "Tarde", "noite": "Noite"}
DIAS = {0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta", 4: "Sexta"}
HORA_ABERTURA = 7

st.set_page_config(page_title="Fila Zero UBS", page_icon="🏥", layout="wide")


@st.cache_data(show_spinner=False)
def carregar(gold: str, versao: float) -> tuple[pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    """`versao` é a data de modificação do gold: se o pipeline rodar de novo, o cache é refeito."""
    pasta = Path(gold)
    fato = pd.read_parquet(pasta / "fato_atendimento.parquet").merge(
        pd.read_parquet(pasta / "dim_data.parquet"), on="data", how="left")
    fato["data"] = pd.to_datetime(fato["data"])
    fato["mes_ref"] = fato["data"].dt.strftime("%Y-%m")
    previsao = None
    if (pasta / "fato_previsao.parquet").exists():
        previsao = pd.read_parquet(pasta / "fato_previsao.parquet")
        previsao["data"] = pd.to_datetime(previsao["data"])
        previsao["mes_ref"] = previsao["data"].dt.strftime("%Y-%m")
        previsao["dia_semana"] = previsao["data"].dt.day_of_week
    lotacao = None
    if (pasta / "fato_lotacao.parquet").exists():
        lotacao = pd.read_parquet(pasta / "fato_lotacao.parquet")
        lotacao["mes_ref"] = pd.to_datetime(lotacao["data"]).dt.strftime("%Y-%m")
        lotacao["turno"] = pd.cut(lotacao["hora"], [0, 12, 17, 24], labels=["manha", "tarde", "noite"], right=False)
        lotacao["turno"] = lotacao["turno"].astype(str)
    return fato, previsao, lotacao


def grafico(fig: go.Figure, altura: int = 320, **layout) -> None:
    padrao = dict(height=altura, margin=dict(l=8, r=8, t=8, b=8), hovermode="x unified",
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    fig.update_layout(**{**padrao, **layout})
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def tabela(df: pd.DataFrame) -> None:
    with st.expander("Ver como tabela"):
        st.dataframe(df, hide_index=True, width="stretch")


if not (GOLD / "fato_atendimento.parquet").exists():
    st.error(f"Camada gold não encontrada em `{GOLD}`. Rode `python data/gerar_dataset.py` "
             "e depois `python bigdata/pipeline.py`.")
    st.stop()

fato, previsao, lotacao = carregar(str(GOLD), (GOLD / "fato_atendimento.parquet").stat().st_mtime)

st.title("Fila Zero UBS")
st.caption("Painel da gestora. Dados sintéticos de 12 meses, com fila por ordem de chegada: "
           "é o cenário antes da solução.")

# ---------------------------------------------------------------- filtros
f1, f2, f3, f4 = st.columns(4)
ubs_sel = f1.multiselect("UBS", sorted(fato["ubs"].unique()), placeholder="Todas")
mes_sel = f2.multiselect("Mês", sorted(fato["mes_ref"].unique()), placeholder="Todos")
dia_sel = f3.multiselect("Dia da semana", list(DIAS), format_func=DIAS.get, placeholder="Todos")
turno_sel = f4.multiselect("Turno", list(TURNOS), format_func=TURNOS.get, placeholder="Todos")


def filtrar(df: pd.DataFrame) -> pd.DataFrame:
    for coluna, escolhidos in (("ubs", ubs_sel), ("mes_ref", mes_sel), ("dia_semana", dia_sel), ("turno", turno_sel)):
        if escolhidos:
            df = df[df[coluna].isin(escolhidos)]
    return df


dados = filtrar(fato)
if dados.empty:
    st.warning("Nenhum atendimento com esses filtros.")
    st.stop()
atendidos = dados[dados["atendido"]]

# ---------------------------------------------------------------- números do período
k1, k2, k3, k4 = st.columns(4)
k1.metric("Idas à UBS", f"{len(dados):,}".replace(",", "."))
k2.metric("Espera média", f"{atendidos['espera_min'].mean():.0f} min")
k3.metric("Voltaram sem atendimento", f"{(~dados['atendido']).mean():.1%}".replace(".", ","))
k4.metric(f"Chegaram antes das {HORA_ABERTURA}h", f"{(dados['hora_chegada_h'] < HORA_ABERTURA).mean():.0%}")

# ---------------------------------------------------------------- 1. previsto x real
st.subheader("A previsão está acertando?")
if previsao is None:
    st.info("Ainda não há previsão no gold. Rode `python ia/treinar.py`.")
else:
    so_teste = st.toggle("Só o período de teste (dias que o modelo não viu no treino)", value=True)
    prev = filtrar(previsao)
    if so_teste:
        prev = prev[prev["conjunto"] == "teste"]
    if prev.empty:
        st.warning("O período de teste fica fora dos filtros escolhidos. Desligue a chave acima ou mude o mês.")
    else:
        por_dia = prev.groupby("data")[["real", "previsto"]].sum().reset_index()
        erro = (prev["real"] - prev["previsto"]).abs().mean()
        erro_txt = f"{erro:.1f}".replace(".", ",")
        st.caption(f"Procura por dia, somando os turnos escolhidos. Erro médio por turno: **{erro_txt} pessoas** "
                   f"(a procura média por turno é {prev['real'].mean():.0f}).")
        fig = go.Figure([
            go.Scatter(x=por_dia["data"], y=por_dia["real"], name="Real", mode="lines+markers",
                       line=dict(color=AZUL, width=2), marker=dict(size=6)),
            go.Scatter(x=por_dia["data"], y=por_dia["previsto"], name="Previsto", mode="lines+markers",
                       line=dict(color=LARANJA, width=2, dash="dot"), marker=dict(size=6, symbol="diamond")),
        ])
        grafico(fig, yaxis=dict(title="pessoas", rangemode="tozero"),
                xaxis=dict(tickformat="%d/%m", hoverformat="%d/%m/%Y"))
        por_turno = prev.assign(erro=(prev["real"] - prev["previsto"]).abs()).groupby("turno").agg(
            procura_media=("real", "mean"), erro_medio=("erro", "mean")).reindex(list(TURNOS)).dropna()
        por_turno["erro_pct_da_media"] = 100 * por_turno["erro_medio"] / por_turno["procura_media"]
        tabela(por_turno.round(1).rename(index=TURNOS).reset_index())

esq, dir_ = st.columns(2)

# ---------------------------------------------------------------- 2. chegadas por hora
with esq:
    st.subheader("A que horas as pessoas chegam?")
    por_hora = dados.groupby("hora_chegada_h").size().rename("chegadas").reset_index()
    cedo = por_hora["hora_chegada_h"] < HORA_ABERTURA
    st.caption(f"Em laranja, quem chegou antes de a UBS abrir, às {HORA_ABERTURA}h.")
    fig = go.Figure(go.Bar(
        x=por_hora["hora_chegada_h"].astype(str) + "h", y=por_hora["chegadas"],
        marker=dict(color=[LARANJA if c else AZUL for c in cedo], cornerradius=4),
        hovertemplate="%{x}: %{y:,} chegadas<extra></extra>"))
    grafico(fig, yaxis=dict(title="chegadas"), bargap=0.25, hovermode="closest")
    tabela(por_hora.rename(columns={"hora_chegada_h": "hora"}))

# ---------------------------------------------------------------- 3. espera por turno
with dir_:
    st.subheader("Quanto se espera em cada turno?")
    espera = atendidos.groupby("turno")["espera_min"].mean().reindex(list(TURNOS)).dropna().round(0)
    st.caption("Espera média de quem foi atendido, em minutos.")
    fig = go.Figure(go.Bar(
        x=[TURNOS[t] for t in espera.index], y=espera.values, text=[f"{v:.0f} min" for v in espera.values],
        textposition="outside", cliponaxis=False, marker=dict(color=AZUL, cornerradius=4),
        hovertemplate="%{x}: %{y:.0f} min<extra></extra>"))
    grafico(fig, yaxis=dict(title="minutos", rangemode="tozero"), bargap=0.45, hovermode="closest")
    tabela(espera.rename(index=TURNOS).rename("espera_media_min").reset_index())

esq, dir_ = st.columns(2)

# ---------------------------------------------------------------- 4. cores da triagem
with esq:
    st.subheader("Quanto da demanda é rotina?")
    cores = (dados.groupby(["mes_ref", "cor_triagem"]).size().unstack(fill_value=0)
             .reindex(columns=list(COR_TRIAGEM), fill_value=0))
    pct = cores.div(cores.sum(axis=1), axis=0) * 100
    pct_verde = dados["cor_triagem"].eq("verde").mean()
    st.caption(f"Verde é rotina que poderia ser agendada: {pct_verde:.0%} das idas no período.")
    fig = go.Figure([
        go.Bar(x=pct.index, y=pct[cor], name=cor.capitalize(),
               marker=dict(color=hexa, line=dict(color="rgba(0,0,0,0)", width=2)),
               hovertemplate=cor.capitalize() + ": %{y:.0f}%<extra></extra>")
        for cor, hexa in COR_TRIAGEM.items()
    ])
    grafico(fig, barmode="stack", bargap=0.3, yaxis=dict(title="% das idas", range=[0, 100]),
            xaxis=dict(type="category"))
    tabela(pct.round(1).reset_index().rename(columns={"mes_ref": "mes"}))

# ---------------------------------------------------------------- 5. retorno sem atendimento
with dir_:
    st.subheader("Quem está sendo mandado embora?")
    retorno = (dados.assign(sem=~dados["atendido"]).groupby(["ubs", "turno"])["sem"].mean().mul(100)
               .unstack("ubs").reindex(list(TURNOS)).dropna(how="all"))
    st.caption("Percentual de quem foi à UBS e voltou para casa sem ser atendido.")
    fig = go.Figure([
        go.Bar(x=[TURNOS[t] for t in retorno.index], y=retorno[ubs], name=ubs,
               marker=dict(color=cor, cornerradius=4), hovertemplate=ubs + ": %{y:.1f}%<extra></extra>")
        for ubs, cor in zip(retorno.columns, [AZUL, LARANJA], strict=False)
    ])
    grafico(fig, barmode="group", bargap=0.35, bargroupgap=0.08, showlegend=True,
            yaxis=dict(title="% sem atendimento", rangemode="tozero"))
    tabela(retorno.round(1).rename(index=TURNOS).reset_index())

# ---------------------------------------------------------------- 6. lotação da sala (sensor IoT)
st.subheader("Quando a sala passa do limite?")
if lotacao is None:
    st.info("Sem leituras do sensor no gold. Rode `python iot/coletor.py` com o sensor (ou o mock) publicando, "
            "depois `python bigdata/pipeline.py`.")
else:
    lot = filtrar(lotacao)
    if lot.empty:
        st.warning("Nenhuma leitura do sensor com esses filtros.")
    else:
        por_hora = (lot.groupby("hora").agg(ocupacao_media=("taxa_ocupacao", "mean"), pct_alerta=("alerta", "mean"),
                                           leituras=("alerta", "size")).reset_index())
        por_hora["ocupacao_media"] *= 100
        por_hora["pct_alerta"] *= 100
        pior = por_hora.loc[por_hora["pct_alerta"].idxmax()]
        st.caption(f"Percentual das leituras do sensor em que a sala estava com 90% ou mais das cadeiras ocupadas, "
                   f"por hora do dia. Em laranja, da abertura da fila até uma hora depois de a UBS abrir. "
                   f"Pior hora: **{int(pior['hora'])}h**, em alerta em {pior['pct_alerta']:.0f}% das leituras.")
        fig = go.Figure(go.Bar(
            x=por_hora["hora"].astype(str) + "h", y=por_hora["pct_alerta"],
            marker=dict(color=[LARANJA if h < HORA_ABERTURA + 2 else AZUL for h in por_hora["hora"]], cornerradius=4),
            customdata=por_hora[["ocupacao_media", "leituras"]],
            hovertemplate="%{x}: sala lotada em %{y:.0f}% das leituras<br>"
                          "ocupação média %{customdata[0]:.0f}% das cadeiras<extra></extra>"))
        grafico(fig, yaxis=dict(title="% das leituras em alerta", range=[0, 100]), bargap=0.25, hovermode="closest")
        tabela(por_hora.round(1))
