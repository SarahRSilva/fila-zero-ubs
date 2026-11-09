"""Pipeline do data lake do Fila Zero UBS: bronze -> silver -> gold.

Uso:
    python bigdata/pipeline.py                 # usa bigdata/lake
    python bigdata/pipeline.py --lake outro/caminho

bronze      CSV como chega (atendimentos_YYYY-MM.csv, clima_diario.csv, feriados.csv, lotacao_YYYY-MM.csv)
silver      limpo e tipado, em Parquet
gold        modelo estrela em Parquet: fato_atendimento, fato_lotacao, dim_data, dim_turno, dim_ubs, dim_feriado
rejeitados  linhas que não passaram na validação, com o motivo
"""
from __future__ import annotations

import argparse
import logging
import sys
import unicodedata
from pathlib import Path

import pandas as pd

LAKE = Path(__file__).resolve().parent / "lake"
log = logging.getLogger("pipeline")

TURNOS = pd.DataFrame({
    "turno": ["manha", "tarde", "noite"],
    "ordem": [1, 2, 3],
    "abre": ["07:00", "13:00", "18:00"],
    "fecha": ["12:00", "17:00", "21:00"],
})
CORES = {"verde", "amarelo", "vermelho"}
NOMES_DIA = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
COLUNAS_BRONZE = ["id", "cpf_hash", "ubs", "data", "turno", "hora_chegada", "hora_atendimento",
                  "espera_min", "motivo", "cor_triagem", "atendido"]


def sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def turno_pela_hora(hora: pd.Series) -> pd.Series:
    """Quem chega até 11h29 quer a manhã; até 16h59, a tarde; depois, a noite."""
    minutos = hora.dt.hour * 60 + hora.dt.minute
    turno = pd.Series("noite", index=hora.index)
    turno[minutos < 17 * 60] = "tarde"
    turno[minutos < 11 * 60 + 30] = "manha"
    return turno.where(hora.notna(), "")


def ler_bronze(bronze: Path) -> pd.DataFrame:
    arquivos = sorted(bronze.glob("atendimentos_*.csv"))
    if not arquivos:
        raise FileNotFoundError(f"nenhum atendimentos_*.csv em {bronze}. Rode data/gerar_dataset.py antes.")
    partes = []
    for arq in arquivos:
        parte = pd.read_csv(arq, dtype=str, keep_default_na=False)
        faltando = set(COLUNAS_BRONZE) - set(parte.columns)
        if faltando:
            raise ValueError(f"{arq.name} sem as colunas {sorted(faltando)}")
        partes.append(parte[COLUNAS_BRONZE].assign(arquivo=arq.name))
    bruto = pd.concat(partes, ignore_index=True)
    log.info("bronze lido: %d linhas em %d arquivos", len(bruto), len(arquivos))
    return bruto


def validar(bruto: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa linhas válidas (já tipadas) das rejeitadas (como chegaram, com o motivo)."""
    df = bruto.apply(lambda c: c.str.strip())
    data = pd.to_datetime(df["data"], format="%Y-%m-%d", errors="coerce")
    chegada = pd.to_datetime(df["data"] + " " + df["hora_chegada"], format="%Y-%m-%d %H:%M", errors="coerce")
    saida = pd.to_datetime(df["data"] + " " + df["hora_atendimento"], format="%Y-%m-%d %H:%M", errors="coerce")
    espera = pd.to_numeric(df["espera_min"], errors="coerce")
    cor = df["cor_triagem"].map(sem_acento).str.lower()
    turno = df["turno"].map(sem_acento).str.lower()
    turno = turno.where(turno != "", turno_pela_hora(chegada))  # turno derivado da hora quando não vem
    atendido = df["atendido"].str.upper()

    regras = [
        ("sem data", df["data"] == ""),
        ("data invalida", (df["data"] != "") & data.isna()),
        ("sem ubs", df["ubs"] == ""),
        ("hora de chegada invalida", data.notna() & chegada.isna()),
        ("turno invalido", ~turno.isin(TURNOS["turno"])),
        ("cor de triagem invalida", ~cor.isin(CORES)),
        ("campo atendido invalido", ~atendido.isin(["S", "N"])),
        ("espera negativa", espera < 0),
        ("hora de atendimento invalida", data.notna() & (df["hora_atendimento"] != "") & saida.isna()),
        ("atendido sem espera ou hora de atendimento",
         (atendido == "S") & (espera.isna() | (df["hora_atendimento"] == ""))),
        ("atendimento antes da chegada", saida < chegada),
        ("id duplicado", df["id"].duplicated(keep="first") | (df["id"] == "")),
    ]
    motivos = pd.Series("", index=df.index)
    for motivo, falhou in regras:
        motivos[falhou & (motivos != "")] += "; " + motivo
        motivos[falhou & (motivos == "")] = motivo

    ok = motivos == ""
    rejeitados = bruto[~ok].assign(motivo_rejeicao=motivos[~ok])
    validos = pd.DataFrame({
        "id": df.loc[ok, "id"].astype("int64"),
        "cpf_hash": df.loc[ok, "cpf_hash"],
        "ubs": df.loc[ok, "ubs"],
        "data": data[ok].dt.date,
        "turno": turno[ok],
        "hora_chegada": chegada[ok],
        "hora_atendimento": saida[ok],
        "espera_min": espera[ok].astype("Int64"),
        "motivo": df.loc[ok, "motivo"],
        "cor_triagem": cor[ok],
        "atendido": atendido[ok] == "S",
    }).reset_index(drop=True)

    log.info("validacao: %d validas, %d rejeitadas", len(validos), len(rejeitados))
    for motivo, n in rejeitados["motivo_rejeicao"].value_counts().items():
        log.warning("rejeitadas por '%s': %d", motivo, n)
    return validos, rejeitados


def ler_clima(bronze: Path) -> pd.DataFrame:
    clima = pd.read_csv(bronze / "clima_diario.csv")
    clima["data"] = pd.to_datetime(clima["data"], errors="coerce")
    clima = clima.dropna(subset=["data"]).drop_duplicates("data").sort_values("data")
    clima["data"] = clima["data"].dt.date
    return clima.astype({"temp_max": "float64", "chuva_mm": "float64"}).reset_index(drop=True)


def ler_feriados(bronze: Path) -> pd.DataFrame:
    feriados = pd.read_csv(bronze / "feriados.csv")
    feriados["data"] = pd.to_datetime(feriados["data"], errors="coerce").dt.date
    return feriados.dropna(subset=["data"]).drop_duplicates("data").sort_values("data").reset_index(drop=True)


def montar_dim_data(clima: pd.DataFrame, dim_feriado: pd.DataFrame) -> pd.DataFrame:
    feriados = set(dim_feriado["data"])
    dim = clima.copy()
    dias = pd.to_datetime(dim["data"])
    dim["dia_semana"] = dias.dt.day_of_week
    dim["nome_dia"] = dim["dia_semana"].map(dict(enumerate(NOMES_DIA)))
    dim["mes"] = dias.dt.month
    dim["feriado"] = dim["data"].isin(feriados).astype(int)
    util_anterior = dias - pd.to_timedelta(dim["dia_semana"].map(lambda d: 3 if d == 0 else 1), unit="D")
    dim["pos_feriado"] = util_anterior.dt.date.isin(feriados).astype(int)
    # chuva acumulada nos 7 dias anteriores (não inclui o próprio dia)
    dim["chuva_7d_mm"] = dim["chuva_mm"].rolling(7, min_periods=1).sum().shift(1).fillna(0).round(1)
    return dim[["data", "dia_semana", "nome_dia", "mes", "feriado", "pos_feriado",
                "temp_max", "chuva_mm", "chuva_7d_mm"]]


def ler_lotacao(bronze: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Leituras do sensor da sala (do coletor MQTT ou do gerador sintético).
    Devolve (válidas tipadas, rejeitadas com motivo); sem arquivos, devolve vazios."""
    arquivos = sorted(bronze.glob("lotacao_*.csv"))
    if not arquivos:
        return pd.DataFrame(), pd.DataFrame()
    bruto = pd.concat([pd.read_csv(a, dtype=str, keep_default_na=False).assign(arquivo=a.name) for a in arquivos],
                      ignore_index=True)
    ts = pd.to_datetime(bruto["ts"], errors="coerce", utc=True).dt.tz_convert("America/Sao_Paulo")
    ocupacao = pd.to_numeric(bruto["ocupacao"], errors="coerce")
    capacidade = pd.to_numeric(bruto["capacidade"], errors="coerce")
    temperatura = pd.to_numeric(bruto.get("temperatura", ""), errors="coerce")
    regras = [
        ("ts invalido", ts.isna()),
        ("sem ubs", bruto["ubs"].str.strip() == ""),
        ("ocupacao invalida", ocupacao.isna() | (ocupacao < 0)),
        ("capacidade invalida", capacidade.isna() | (capacidade <= 0)),
        ("temperatura fora da faixa", temperatura.notna() & ((temperatura < 5) | (temperatura > 50))),
        ("leitura duplicada", bruto.duplicated(["ts", "ubs"], keep="first")),
    ]
    motivos = pd.Series("", index=bruto.index)
    for motivo, falhou in regras:
        motivos[falhou & (motivos != "")] += "; " + motivo
        motivos[falhou & (motivos == "")] = motivo
    ok = motivos == ""
    validas = pd.DataFrame({
        "ts": ts[ok].dt.tz_localize(None),
        "data": ts[ok].dt.date,
        "hora": ts[ok].dt.hour,
        "ubs": bruto.loc[ok, "ubs"].str.strip(),
        "ocupacao": ocupacao[ok].astype("int64"),
        "capacidade": capacidade[ok].astype("int64"),
        "temperatura": temperatura[ok],
        "origem": bruto.loc[ok, "origem"].str.strip(),
    }).reset_index(drop=True)
    validas["taxa_ocupacao"] = (validas["ocupacao"] / validas["capacidade"]).round(3)
    validas["alerta"] = validas["taxa_ocupacao"] >= 0.9
    log.info("lotacao: %d leituras validas, %d rejeitadas", len(validas), int((~ok).sum()))
    return validas, bruto[~ok].assign(motivo_rejeicao=motivos[~ok])


def rodar(lake: Path = LAKE) -> dict:
    bronze, silver, gold, rej = (lake / p for p in ("bronze", "silver", "gold", "rejeitados"))
    for pasta in (silver, gold, rej):
        pasta.mkdir(parents=True, exist_ok=True)

    validos, rejeitados = validar(ler_bronze(bronze))
    rejeitados.to_csv(rej / "atendimentos_rejeitados.csv", index=False)
    lotacao, lotacao_rej = ler_lotacao(bronze)
    if not lotacao_rej.empty:
        lotacao_rej.to_csv(rej / "lotacao_rejeitadas.csv", index=False)

    clima = ler_clima(bronze)
    validos.to_parquet(silver / "atendimentos.parquet", index=False)
    clima.to_parquet(silver / "clima.parquet", index=False)
    if not lotacao.empty:
        lotacao.to_parquet(silver / "lotacao.parquet", index=False)
    log.info("silver gravado: atendimentos (%d), clima (%d)", len(validos), len(clima))

    dim_feriado = ler_feriados(bronze)  # inclui feriados futuros, que a previsão precisa conhecer
    dim_data = montar_dim_data(clima, dim_feriado)
    dim_ubs = pd.DataFrame({"ubs": sorted(validos["ubs"].unique())})
    dim_ubs.insert(0, "ubs_id", range(1, len(dim_ubs) + 1))
    fato = validos.assign(hora_chegada_h=validos["hora_chegada"].dt.hour)
    sem_calendario = ~fato["data"].isin(dim_data["data"])
    if sem_calendario.any():
        log.warning("%d atendimentos em datas fora do calendario (sem clima)", int(sem_calendario.sum()))

    fato.to_parquet(gold / "fato_atendimento.parquet", index=False)
    dim_data.to_parquet(gold / "dim_data.parquet", index=False)
    TURNOS.to_parquet(gold / "dim_turno.parquet", index=False)
    dim_ubs.to_parquet(gold / "dim_ubs.parquet", index=False)
    dim_feriado.to_parquet(gold / "dim_feriado.parquet", index=False)
    if not lotacao.empty:
        fato_lot = lotacao.merge(dim_data[["data", "dia_semana", "nome_dia", "mes"]], on="data", how="left")
        fato_lot.to_parquet(gold / "fato_lotacao.parquet", index=False)
        log.info("gold gravado: fato_lotacao (%d)", len(fato_lot))
    log.info("gold gravado: fato_atendimento (%d), dim_data (%d), dim_turno (%d), dim_ubs (%d)",
             len(fato), len(dim_data), len(TURNOS), len(dim_ubs))
    return {"lidas": len(validos) + len(rejeitados), "validas": len(validos), "rejeitadas": len(rejeitados)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Pipeline bronze -> silver -> gold")
    ap.add_argument("--lake", type=Path, default=LAKE)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s %(message)s")
    try:
        rodar(args.lake)
    except (FileNotFoundError, ValueError) as erro:
        log.error("%s", erro)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
