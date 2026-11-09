import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ATENDIMENTOS_POR_PROFISSIONAL, EQUIPE, api, dataPorExtenso, iso, proximaDataAberta, sair, turnosDisponiveis } from "../lib/api.js";
import { Cabecalho, Classificacao } from "../componentes.jsx";
import { triagemGuardada } from "./Triagem.jsx";

// Espera estimada: cada profissional atende ~14 min; a fila cresce quando a
// procura passa da capacidade do turno.
function esperaEstimada(pessoas, turno) {
  const capacidade = EQUIPE[turno] * ATENDIMENTOS_POR_PROFISSIONAL;
  const ocupacao = pessoas / capacidade;
  return Math.round(10 + Math.max(0, ocupacao - 0.5) * 80 + Math.max(0, ocupacao - 1) * 120);
}

export default function Turno() {
  const navegar = useNavigate();
  const triagem = triagemGuardada();
  const [data, setData] = useState(null);
  const [sala, setSala] = useState(null);
  const [previsao, setPrevisao] = useState(null);
  const [erro, setErro] = useState(null);
  const [escolhido, setEscolhido] = useState(null);
  const [confirmado, setConfirmado] = useState(false);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (!triagem) {
      navegar("/triagem", { replace: true });
      return;
    }
    // amarelo e vermelho não devem esperar: tenta hoje antes do próximo dia de funcionamento
    proximaDataAberta(triagem.ubs, { incluirHoje: triagem.cor !== "verde" })
      .then((r) => {
        setData(r.data);
        setPrevisao(r.previsao);
      })
      .catch((e) => setErro(e.message));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const turnos = useMemo(() => {
    if (!previsao) return [];
    const maior = Math.max(...Object.values(previsao.turnos), 1);
    const lista = turnosDisponiveis(data).map((t) => {
      const pessoas = previsao.turnos[t.id];
      const espera = esperaEstimada(pessoas, t.id);
      return { ...t, pessoas, espera, barra: `${Math.round((pessoas / maior) * 100)}%`, cor: espera > 50 ? "var(--vermelho)" : espera > 30 ? "var(--amarelo)" : "var(--verde)" };
    });
    const melhor = [...lista].sort((a, b) => a.espera - b.espera)[0]?.id;
    return lista.map((t) => ({ ...t, melhor: t.id === melhor }));
  }, [previsao, data]);

  useEffect(() => {
    if (turnos.length && !escolhido) {
      setEscolhido(turnos.find((t) => t.melhor).id); // pré-seleciona o turno com menor espera prevista
    }
  }, [turnos]); // eslint-disable-line react-hooks/exhaustive-deps

  async function confirmar() {
    setEnviando(true);
    setErro(null);
    try {
      await api.registrar({
        ubs: triagem.ubs,
        data,
        turno: escolhido,
        motivo: triagem.motivo_resumido || triagem.relato,
        cor_triagem: triagem.cor,
        hora_chegada: turnos.find((t) => t.id === escolhido).inicio,
      });
      setConfirmado(true);
      api.salaAgora(triagem.ubs).then(setSala).catch(() => setSala(null));
    } catch (e) {
      setErro(e.message);
    } finally {
      setEnviando(false);
    }
  }

  if (!triagem) return null;
  const turnoEscolhido = turnos.find((t) => t.id === escolhido);
  const nomeUbs = triagem.ubs.replace("Esperanca", "Esperança");
  const sub = data ? `${nomeUbs} · ${dataPorExtenso(data, true)}` : nomeUbs;

  if (confirmado && turnoEscolhido) {
    return (
      <main className="tela">
        <Cabecalho titulo="Quando ir" sub={sub} etiqueta="Passo 2 de 2" />
        <div className="confirmado">
          <div className="confirmado__icone" aria-hidden="true">
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12l5 5L20 7" /></svg>
          </div>
          <h1 className="titulo titulo--m">Combinado: {turnoEscolhido.nome.toLowerCase()} de {dataPorExtenso(data).split(",")[0]}</h1>
          <p className="lead" style={{ maxWidth: 300 }}>
            Chegue a partir das <strong style={{ color: "var(--tinta)" }}>{turnoEscolhido.horario.split(" ")[0]}</strong>. Não precisa chegar antes: a UBS já sabe que você vem.
          </p>
          <div className="cartao" style={{ width: "100%", textAlign: "left", display: "flex", flexDirection: "column", gap: 6 }}>
            <span className="rotulo">Leve com você</span>
            <span style={{ fontSize: 14, lineHeight: "20px" }}>Cartão do SUS e documento com foto. Se piorar antes, procure a UPA ou ligue 192.</span>
          </div>
          <div className="cartao" style={{ width: "100%", textAlign: "left", display: "flex", flexDirection: "column", gap: 6 }}>
            <span className="rotulo">Seu atendimento</span>
            <span style={{ fontSize: 14, lineHeight: "20px" }}>
              Espera prevista: cerca de {turnoEscolhido.espera} min.
              {sala && ` Sala de espera agora: ${sala.ocupacao} de ${sala.capacidade} lugares.`}
            </span>
          </div>
          <button type="button" className="botao botao--secundario" style={{ width: "auto", padding: "0 20px", marginTop: 8 }} onClick={() => setConfirmado(false)}>Trocar de turno</button>
          <Link to="/" onClick={sair} style={{ fontSize: 14, fontWeight: 600 }}>Sair</Link>
        </div>
      </main>
    );
  }

  return (
    <main className="tela">
      <Cabecalho titulo="Quando ir" sub={sub} etiqueta="Passo 2 de 2" voltarPara="/triagem" />

      <div className="chat" style={{ gap: 16 }}>
        <Classificacao cor={triagem.cor} />
        <div>
          <h1 className="titulo titulo--m">{turnos.find((t) => t.melhor) ? `A ${turnos.find((t) => t.melhor).nome.toLowerCase()} deve ter menos fila` : "Calculando a previsão…"}</h1>
          <p className="lead" style={{ fontSize: 14, marginTop: 4 }}>{data === iso(new Date()) ? "Previsão para hoje" : "Previsão para o próximo dia de funcionamento"}, com base em 12 meses de atendimentos e no tempo.</p>
        </div>

        {erro && <p className="erro" role="alert">{erro}</p>}

        <div className="turnos">
          {turnos.map((t) => (
            <button key={t.id} type="button" className={`turno${t.id === escolhido ? " ativo" : ""}`} onClick={() => setEscolhido(t.id)} aria-pressed={t.id === escolhido}>
              <div className="turno__cabeca">
                <span className="turno__nome">{t.nome}</span>
                <span className="turno__horario">{t.horario}</span>
              </div>
              <div className="turno__meio">
                <div className="barra"><span style={{ width: t.barra, background: t.cor }} /></div>
                <span className="mudo" style={{ color: "var(--tinta-2)" }}>{t.pessoas} pessoas previstas · espera ~{t.espera} min</span>
              </div>
              {t.melhor && <span className="selo">MELHOR</span>}
            </button>
          ))}
        </div>

        {previsao && (
          <p className="mudo">
            Previsão do modelo para {dataPorExtenso(data, true)}: {previsao.turnos.manha} pessoas de manhã, {previsao.turnos.tarde} à tarde e {previsao.turnos.noite} à noite. A espera é estimada pela equipe de cada turno.
          </p>
        )}
      </div>

      <div className="rodape">
        <button type="button" className="botao" onClick={confirmar} disabled={!turnoEscolhido || enviando}>
          {enviando ? "Registrando…" : turnoEscolhido ? `Vou na ${turnoEscolhido.nome.toLowerCase()}` : "Aguarde…"}
        </button>
        <Link to="/" onClick={sair} style={{ textAlign: "center", fontSize: 14, fontWeight: 600, padding: 10 }}>Sair</Link>
      </div>
    </main>
  );
}
