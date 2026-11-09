import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, guardarSessao } from "../lib/api.js";
import { AlertaEmergencia, IconeMarca } from "../componentes.jsx";

export default function Login() {
  const navegar = useNavigate();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState(null);
  const [enviando, setEnviando] = useState(false);

  async function entrar(e) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      const dados = await api.login(email.trim(), senha);
      guardarSessao(dados);
      navegar(dados.perfil === "gestora" ? "/painel" : "/triagem", { replace: true });
    } catch (err) {
      setErro(err.status === 401 ? "E-mail ou senha incorretos." : err.message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="tela tela--centro">
      <div className="marca">
        <IconeMarca />
        <div>
          <span className="marca__nome">Fila Zero UBS</span>
          <span className="marca__sub">Sua UBS sem fila de madrugada</span>
        </div>
      </div>

      <h1 className="titulo" style={{ marginTop: 56, marginBottom: 8 }}>Entrar</h1>
      <p className="lead" style={{ marginBottom: 32 }}>Conte o que está sentindo e saiba o melhor horário para ir à UBS.</p>

      <form onSubmit={entrar} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div className="campo">
          <label htmlFor="email">E-mail</label>
          <input id="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="voce@exemplo.com" />
        </div>
        <div className="campo">
          <label htmlFor="senha">Senha</label>
          <input id="senha" type="password" autoComplete="current-password" required value={senha} onChange={(e) => setSenha(e.target.value)} placeholder="••••••••" />
        </div>
        {erro && <p className="erro" role="alert">{erro}</p>}
        <button type="submit" className="botao" disabled={enviando} style={{ marginTop: 8 }}>
          {enviando ? "Entrando…" : "Entrar"}
        </button>
      </form>

      <p className="lead" style={{ marginTop: 20, textAlign: "center", fontSize: 14 }}>
        Primeira vez? <Link to="/cadastro" style={{ fontWeight: 600 }}>Criar conta</Link>
      </p>

      <div style={{ flex: 1 }} />
      <AlertaEmergencia />
      <p className="mudo" style={{ marginTop: 16, textAlign: "center", fontSize: 11 }}>
        Este aplicativo não substitui a avaliação do enfermeiro nem marca consulta: ele sugere um turno.
      </p>
    </main>
  );
}
