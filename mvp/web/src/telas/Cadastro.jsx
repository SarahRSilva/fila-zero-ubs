import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, guardarSessao } from "../lib/api.js";
import { IconeMarca } from "../componentes.jsx";

export default function Cadastro() {
  const navegar = useNavigate();
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState(null);
  const [enviando, setEnviando] = useState(false);

  async function criar(e) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      guardarSessao(await api.cadastrar(nome.trim(), email.trim(), senha));
      navegar("/triagem", { replace: true });
    } catch (err) {
      setErro(err.status === 422 ? "Confira os dados: a senha precisa ter pelo menos 8 caracteres." : err.message);
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

      <h1 className="titulo" style={{ marginTop: 56, marginBottom: 8 }}>Criar conta</h1>
      <p className="lead" style={{ marginBottom: 32 }}>Não pedimos CPF nem dados de saúde no cadastro.</p>

      <form onSubmit={criar} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div className="campo">
          <label htmlFor="nome">Nome</label>
          <input id="nome" type="text" autoComplete="name" required minLength={2} maxLength={80} value={nome} onChange={(e) => setNome(e.target.value)} />
        </div>
        <div className="campo">
          <label htmlFor="email">E-mail</label>
          <input id="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="voce@exemplo.com" />
        </div>
        <div className="campo">
          <label htmlFor="senha">Senha</label>
          <input id="senha" type="password" autoComplete="new-password" required minLength={8} maxLength={72} value={senha} onChange={(e) => setSenha(e.target.value)} placeholder="Pelo menos 8 caracteres" />
        </div>
        {erro && <p className="erro" role="alert">{erro}</p>}
        <button type="submit" className="botao" disabled={enviando} style={{ marginTop: 8 }}>
          {enviando ? "Criando…" : "Criar conta"}
        </button>
      </form>

      <p className="lead" style={{ marginTop: 20, textAlign: "center", fontSize: 14 }}>
        Já tem conta? <Link to="/" style={{ fontWeight: 600 }}>Entrar</Link>
      </p>
    </main>
  );
}
