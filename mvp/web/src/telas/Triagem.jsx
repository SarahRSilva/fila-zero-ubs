import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, sessao } from "../lib/api.js";
import { Cabecalho, Classificacao, IconeMarca } from "../componentes.jsx";

const UBS_PADRAO = "UBS Jardim Esperanca";
const CHAVE_TRIAGEM = "filazero.triagem";

function Balao({ de, children }) {
  return (
    <div className={`balao${de === "eu" ? " balao--eu" : ""}`}>
      {de === "bot" && <IconeMarca pequeno />}
      {typeof children === "string" ? <p className="balao__texto">{children}</p> : <div className="balao__texto balao__corpo">{children}</div>}
    </div>
  );
}

export default function Triagem() {
  const navegar = useNavigate();
  const s = sessao();
  const primeiroNome = s?.nome?.split(" ")[0] ?? "";
  const [mensagens, setMensagens] = useState([
    { de: "bot", texto: `Oi${primeiroNome ? `, ${primeiroNome}` : ""}. Me conta o que você está sentindo ou do que precisa na UBS.` },
  ]);
  const [texto, setTexto] = useState("");
  const [relato, setRelato] = useState(null); // primeiro relato, mantido para a 2ª chamada
  const [pergunta, setPergunta] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const fim = useRef(null);

  useEffect(() => {
    fim.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensagens, resultado]);

  async function classificar(relatoAtual, respostaAnterior) {
    setOcupado(true);
    try {
      const r = await api.triagem(relatoAtual, respostaAnterior);
      if (r.pergunta && !respostaAnterior) {
        setPergunta(r.pergunta);
        setMensagens((m) => [...m, { de: "bot", texto: r.pergunta }]);
        if (r.cor === "verde" && !r.orientacao) setRelato(null); // relato curto: começa de novo
        return;
      }
      setPergunta(null);
      setResultado(r);
      sessionStorage.setItem(CHAVE_TRIAGEM, JSON.stringify({ ...r, relato: relatoAtual, ubs: UBS_PADRAO }));
      setMensagens((m) => [...m, { de: "bot", resultado: r }]);
    } catch (err) {
      setMensagens((m) => [...m, { de: "bot", texto: `Não consegui classificar agora (${err.message}). Tente de novo.` }]);
    } finally {
      setOcupado(false);
    }
  }

  function responder(conteudo) {
    const limpo = conteudo.trim();
    if (!limpo || ocupado || resultado) return;
    setMensagens((m) => [...m, { de: "eu", texto: limpo }]);
    setTexto("");
    if (pergunta && relato) {
      classificar(relato, limpo);
    } else {
      setRelato(limpo);
      classificar(limpo);
    }
  }

  const vermelho = resultado?.cor === "vermelho";

  return (
    <main className="tela">
      <Cabecalho titulo="Pré-triagem" sub={UBS_PADRAO.replace("Esperanca", "Esperança")} etiqueta="Passo 1 de 2" voltarPara="/" />

      <div className="chat" aria-live="polite">
        {mensagens.map((m, i) =>
          m.resultado ? (
            <Balao key={i} de="bot">
              <p>{m.resultado.orientacao}</p>
              <Classificacao cor={m.resultado.cor} />
            </Balao>
          ) : (
            <Balao key={i} de={m.de}>{m.texto}</Balao>
          ),
        )}
        {pergunta && !resultado && (
          <div className="opcoes">
            <button type="button" className="botao botao--pilula" onClick={() => responder("Não, nada disso")} disabled={ocupado}>Não, nada disso</button>
            <button type="button" className="botao botao--pilula" onClick={() => responder("Sim, alguma delas")} disabled={ocupado}>Sim, alguma delas</button>
          </div>
        )}
        {ocupado && <Balao de="bot">…</Balao>}
        <div ref={fim} />
      </div>

      {resultado && (
        <div className="chat__acao">
          {vermelho ? (
            <a className="botao" href="https://www.google.com/maps/search/UPA+mais+próxima" target="_blank" rel="noreferrer">Ver UPA mais próxima</a>
          ) : (
            <button type="button" className="botao" onClick={() => navegar("/turno")}>Ver turno sugerido</button>
          )}
          {vermelho && (
            <p className="mudo" style={{ textAlign: "center", marginTop: 8 }}>
              Se preferir, <Link to="/turno">veja mesmo assim os turnos da UBS</Link>.
            </p>
          )}
        </div>
      )}

      <form
        className="chat__entrada"
        onSubmit={(e) => {
          e.preventDefault();
          responder(texto);
        }}
      >
        <label htmlFor="msg" className="visualmente-oculto">Mensagem</label>
        <input id="msg" type="text" value={texto} onChange={(e) => setTexto(e.target.value)} placeholder={resultado ? "Triagem concluída" : "Escreva aqui…"} disabled={ocupado || !!resultado} maxLength={600} />
        <button type="submit" className="chat__enviar" aria-label="Enviar" disabled={ocupado || !!resultado}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M5 12h14M13 6l6 6-6 6" />
          </svg>
        </button>
      </form>
    </main>
  );
}

export function triagemGuardada() {
  try {
    return JSON.parse(sessionStorage.getItem(CHAVE_TRIAGEM));
  } catch {
    return null;
  }
}
