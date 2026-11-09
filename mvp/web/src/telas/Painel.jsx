import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ATENDIMENTOS_POR_PROFISSIONAL, EQUIPE, TURNOS, api, dataPorExtenso, proximaDataAberta, sair, sessao } from "../lib/api.js";
import { IconeMarca } from "../componentes.jsx";

const DASHBOARD = import.meta.env.VITE_DASHBOARD_URL || `${window.location.protocol}//${window.location.hostname}:8501`;
const NOME_COR = { verde: "Verde", amarelo: "Amarelo", vermelho: "Vermelho" };
const NOME_TURNO = Object.fromEntries(TURNOS.map((t) => [t.id, t.nome]));

function situacao(pessoas, turno) {
  const capacidade = EQUIPE[turno] * ATENDIMENTOS_POR_PROFISSIONAL;
  const sobra = capacidade - pessoas;
  if (sobra < 0) return { cor: "vermelho", aviso: `${-sobra} pessoas acima da capacidade`, capacidade };
  if (sobra <= capacidade * 0.1) return { cor: "amarelo", aviso: "No limite da equipe", capacidade };
  return { cor: "verde", aviso: `Folga de ${sobra} vagas`, capacidade };
}

export default function Painel() {
  const navegar = useNavigate();
  const s = sessao();
  const [data, setData] = useState(null);
  const [previsao, setPrevisao] = useState(null);
  const [fila, setFila] = useState([]);
  const [filtro, setFiltro] = useState("todos");
  const [erro, setErro] = useState(null);
  const [sala, setSala] = useState(null);

  // sensor da sala: consulta a cada 15 s enquanto o painel estiver aberto
  useEffect(() => {
    if (!s) return undefined;
    let ativo = true;
    const ler = () => api.salaAgora(s.ubs).then((r) => ativo && setSala(r)).catch(() => ativo && setSala(null));
    ler();
    const id = setInterval(ler, 15000);
    return () => { ativo = false; clearInterval(id); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!s) {
      navegar("/", { replace: true });
      return;
    }
    irParaProximoDia();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function irParaProximoDia() {
    proximaDataAberta(s.ubs).then((r) => setData(r.data)).catch((e) => setErro(e.message));
  }

  useEffect(() => {
    if (!s || !data) return;
    setErro(null);
    setPrevisao(null);
    Promise.all([api.previsao(data, s.ubs), api.atendimentos(data, s.ubs)])
      .then(([p, a]) => {
        setPrevisao(p);
        setFila(a);
      })
      .catch((e) => setErro(e.message));
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps

  const cartoes = useMemo(() => {
    if (!previsao) return [];
    return TURNOS.map((t) => {
      const pessoas = previsao.turnos[t.id];
      const st = situacao(pessoas, t.id);
      return { ...t, pessoas, ...st, barra: `${Math.min(100, Math.round((pessoas / st.capacidade) * 100))}%` };
    });
  }, [previsao]);

  const filaFiltrada = fila.filter((a) => filtro === "todos" || a.cor_triagem === filtro);
  const pctVerde = fila.length ? Math.round((fila.filter((a) => a.cor_triagem === "verde").length / fila.length) * 100) : 0;
  const sugestoes = useMemo(() => {
    const lista = [];
    const manha = cartoes.find((c) => c.id === "manha");
    const noite = cartoes.find((c) => c.id === "noite");
    if (manha?.cor === "vermelho") lista.push({ cor: "vermelho", texto: `Manhã acima da capacidade: remanejar 1 profissional${noite?.cor === "verde" ? " da noite" : ""} ou abrir vagas de rotina à tarde.` });
    const verdes = fila.filter((a) => a.cor_triagem === "verde").length;
    if (verdes) lista.push({ cor: "verde", texto: `${verdes} atendimento${verdes > 1 ? "s" : ""} de rotina já avisado${verdes > 1 ? "s" : ""}: receitas e vacinas podem ir direto para farmácia e sala de vacina.` });
    if (previsao && !previsao.aberta) lista.push({ cor: "amarelo", texto: `UBS fechada (${previsao.motivo_fechada}). O dia útil seguinte costuma ter 15% mais procura.` });
    if (!lista.length) lista.push({ cor: "verde", texto: "Equipe comporta a procura prevista em todos os turnos." });
    return lista;
  }, [cartoes, fila, previsao]);

  if (!s) return null;
  const iniciais = s.nome.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();

  return (
    <div className="pagina">
      <header className="topo">
        <div className="marca">
          <IconeMarca pequeno />
          <span className="marca__nome" style={{ fontSize: 17 }}>Fila Zero UBS</span>
        </div>
        <nav aria-label="Principal">
          <Link to="/painel" className="ativo">Hoje</Link>
          <a href={DASHBOARD} target="_blank" rel="noreferrer">Indicadores</a>
        </nav>
        <div className="topo__direita">
          <span>{(s.ubs ?? "").replace("Esperanca", "Esperança")}</span>
          <div className="avatar" aria-label={s.nome}>{iniciais}</div>
          <button type="button" className="sair" onClick={() => { sair(); navegar("/"); }}>Sair</button>
        </div>
      </header>

      <main className="conteudo">
        <div className="conteudo__cabeca">
          <div>
            <h1>{data ? dataPorExtenso(data) : "Carregando…"}</h1>
            <p className="lead" style={{ fontSize: 14, marginTop: 4 }}>
              {previsao ? `Modelo ${previsao.modelo} · erro médio de ${previsao.mae_teste.toLocaleString("pt-BR")} pessoas por turno no teste` : "Carregando previsão…"}
            </p>
          </div>
          <div className="datas">
            <label htmlFor="data" className="rotulo">Prever para</label>
            <input id="data" type="date" value={data ?? ""} onChange={(e) => e.target.value && setData(e.target.value)} />
            <button type="button" className="botao botao--p" onClick={irParaProximoDia}>Próximo dia útil</button>
          </div>
        </div>

        {erro && <p className="erro" role="alert">{erro}</p>}
        {previsao && !previsao.aberta && <p className="erro" style={{ background: "var(--amarelo-fundo)", color: "var(--amarelo-tinta)" }}>UBS fechada nesse dia ({previsao.motivo_fechada}).</p>}

        <section className="cartoes" aria-label="Previsão por turno">
          {cartoes.map((c) => (
            <article key={c.id} className="cartao-turno">
              <div className="cartao-turno__topo">{c.nome}<span>{c.horario}</span></div>
              <div className="numero"><strong>{c.pessoas}</strong><span>pessoas previstas</span></div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <div className="capacidade"><span>Capacidade da equipe</span><b>{EQUIPE[c.id]} profissionais · {c.capacidade}</b></div>
                <div className="barra barra--g"><span style={{ width: c.barra, background: `var(--${c.cor})` }} /></div>
              </div>
              <div className={`aviso cor-${c.cor}`}><span className="ponto" aria-hidden="true" />{c.aviso}</div>
            </article>
          ))}
        </section>

        <div className="duas-colunas">
          <section className="painel painel--fila" aria-label="Quem já avisou que vem">
            <div className="painel__cabeca">
              <div>
                <h2>Quem já avisou que vem</h2>
                <small>{fila.length} pessoa{fila.length === 1 ? "" : "s"} pré-triada{fila.length === 1 ? "" : "s"} pelo chat{fila.length ? ` · ${pctVerde}% em verde` : ""}</small>
              </div>
              <div className="filtros" role="group" aria-label="Filtrar por triagem">
                {["todos", "vermelho", "amarelo", "verde"].map((f) => (
                  <button key={f} type="button" className={filtro === f ? "ativo" : ""} onClick={() => setFiltro(f)}>{f === "todos" ? "Todos" : NOME_COR[f]}</button>
                ))}
              </div>
            </div>
            {filaFiltrada.length ? (
              <div className="tabela-caixa">
                <table>
                  <thead><tr><th>Turno</th><th>Cidadão</th><th>Motivo</th><th>Triagem</th><th>Chegada</th></tr></thead>
                  <tbody>
                    {filaFiltrada.map((a) => (
                      <tr key={a.id}>
                        <td>{NOME_TURNO[a.turno]}</td>
                        <td className="mono">{a.cidadao_hash.slice(0, 8)}</td>
                        <td>{a.motivo}</td>
                        <td><span className={`triagem-tag cor-${a.cor_triagem}`}><span className="ponto" aria-hidden="true" />{NOME_COR[a.cor_triagem]}</span></td>
                        <td style={{ color: "var(--tinta-3)" }}>{a.hora_chegada ? a.hora_chegada.slice(0, 5) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="vazio">Ninguém avisou ainda para esse dia.</p>
            )}
          </section>

          <aside className="lateral">
            <section className="painel" aria-label="Sala de espera agora">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h2>Sala de espera agora</h2>
                {sala ? (
                  <span className={sala.segundos_atras > 120 ? "selo-cinza" : "selo"}>{sala.segundos_atras > 120 ? "sensor parado" : "sensor ativo"}</span>
                ) : (
                  <span className="selo-cinza">sem sensor</span>
                )}
              </div>
              {sala ? (
                <>
                  <div className="numero"><strong style={{ fontSize: 40, lineHeight: "40px" }}>{sala.ocupacao}</strong><span>de {sala.capacidade} lugares</span></div>
                  <div className="barra barra--g"><span style={{ width: `${Math.min(100, Math.round(sala.taxa_ocupacao * 100))}%`, background: sala.alerta ? "var(--vermelho)" : sala.taxa_ocupacao > 0.6 ? "var(--amarelo)" : "var(--verde)" }} /></div>
                  <p className="mudo">
                    Última leitura há {sala.segundos_atras < 60 ? `${sala.segundos_atras} s` : `${Math.round(sala.segundos_atras / 60)} min`}
                    {sala.temperatura != null && ` · ${sala.temperatura.toLocaleString("pt-BR")} °C`}
                    {sala.alertas_hoje > 0 && ` · ${sala.alertas_hoje} leitura${sala.alertas_hoje > 1 ? "s" : ""} em alerta hoje`}
                    {sala.alerta && " · sala lotada agora"}
                  </p>
                </>
              ) : (
                <p className="mudo">Nenhuma leitura do sensor de lotação ainda. Ligue o ESP32 ou rode <code>python iot/mock_sensor.py</code>.</p>
              )}
            </section>
            <section className="painel" aria-label="Sugestões">
              <h2>Sugestões para o dia</h2>
              <ul className="sugestoes">
                {sugestoes.map((sg, i) => (
                  <li key={i}><span className={`ponto ponto--${sg.cor}`} aria-hidden="true" />{sg.texto}</li>
                ))}
              </ul>
              <a className="botao botao--secundario" href={DASHBOARD} target="_blank" rel="noreferrer" style={{ height: 44, fontSize: 14, marginTop: 4 }}>Abrir indicadores dos 12 meses</a>
            </section>
          </aside>
        </div>
      </main>
    </div>
  );
}
