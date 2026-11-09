// Cliente da API. O token fica em sessionStorage: some ao fechar a aba.
// Sem VITE_API_URL, a API é procurada no mesmo endereço que serviu o front, porta 8000.
// Assim o celular na mesma rede Wi-Fi (http://192.168.x.y:5173) acha a API sozinho.
const API = import.meta.env.VITE_API_URL || `${window.location.protocol}//${window.location.hostname}:8000`;
const CHAVE = "filazero.sessao";

export function sessao() {
  try {
    return JSON.parse(sessionStorage.getItem(CHAVE)) ?? null;
  } catch {
    return null;
  }
}

export function guardarSessao(dados) {
  sessionStorage.setItem(CHAVE, JSON.stringify(dados));
}

export function sair() {
  sessionStorage.removeItem(CHAVE);
}

export class ErroApi extends Error {
  constructor(status, detalhe) {
    super(typeof detalhe === "string" ? detalhe : "Erro na API");
    this.status = status;
    this.detalhe = detalhe;
  }
}

async function chamar(caminho, { metodo = "GET", corpo, autenticado = true } = {}) {
  const cabecalhos = { "Content-Type": "application/json" };
  const s = sessao();
  if (autenticado && s?.access_token) cabecalhos.Authorization = `Bearer ${s.access_token}`;

  let resposta;
  try {
    resposta = await fetch(`${API}${caminho}`, {
      method: metodo,
      headers: cabecalhos,
      body: corpo ? JSON.stringify(corpo) : undefined,
    });
  } catch {
    throw new ErroApi(0, "Não consegui falar com o servidor. Verifique sua conexão.");
  }

  if (resposta.status === 401 && autenticado) {
    sair();
    window.location.assign("/");
  }
  const dados = resposta.status === 204 ? null : await resposta.json().catch(() => null);
  if (!resposta.ok) throw new ErroApi(resposta.status, dados?.detail ?? "Erro na API");
  return dados;
}

export const api = {
  login: (email, senha) => chamar("/login", { metodo: "POST", corpo: { email, senha }, autenticado: false }),
  cadastrar: (nome, email, senha) => chamar("/cadastro", { metodo: "POST", corpo: { nome, email, senha }, autenticado: false }),
  triagem: (relato, respostaAnterior) =>
    chamar("/triagem", { metodo: "POST", corpo: { relato, resposta_anterior: respostaAnterior ?? null } }),
  previsao: (data, ubs) => chamar(`/previsao?data=${data}${ubs ? `&ubs=${encodeURIComponent(ubs)}` : ""}`),
  atendimentos: (data, ubs) =>
    chamar(`/atendimento?${[data && `data=${data}`, ubs && `ubs=${encodeURIComponent(ubs)}`].filter(Boolean).join("&")}`),
  registrar: (dados) => chamar("/atendimento", { metodo: "POST", corpo: dados }),
  ubs: () => chamar("/ubs", { autenticado: false }),
  salaAgora: (ubs) => chamar(`/sala/agora${ubs ? `?ubs=${encodeURIComponent(ubs)}` : ""}`),
};

// Equipe por turno: até existir cadastro na API, a capacidade é estimada
// com 18 atendimentos por profissional em cada turno.
export const EQUIPE = { manha: 4, tarde: 3, noite: 2 };
export const ATENDIMENTOS_POR_PROFISSIONAL = 18;
export const TURNOS = [
  { id: "manha", nome: "Manhã", horario: "7h às 12h", inicio: "07:00", fim: 12 },
  { id: "tarde", nome: "Tarde", horario: "13h às 17h", inicio: "13:00", fim: 17 },
  { id: "noite", nome: "Noite", horario: "18h às 21h", inicio: "18:00", fim: 21 },
];

// Data no fuso de quem usa; toISOString() devolveria o dia seguinte depois das 21h no Brasil.
export function iso(d) {
  const mes = String(d.getMonth() + 1).padStart(2, "0");
  const dia = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mes}-${dia}`;
}

// Hoje só valem os turnos que ainda não acabaram; nos outros dias, todos.
export function turnosDisponiveis(data, agora = new Date()) {
  return data === iso(agora) ? TURNOS.filter((t) => agora.getHours() < t.fim) : TURNOS;
}

// Quem sabe se a UBS abre é a API, que conhece os feriados.
export async function proximaDataAberta(ubs, { incluirHoje = false } = {}) {
  const d = new Date();
  if (!incluirHoje) d.setDate(d.getDate() + 1);
  for (let i = 0; i < 15; i += 1) {
    const data = iso(d);
    const previsao = await api.previsao(data, ubs);
    if (previsao.aberta && turnosDisponiveis(data).length) return { data, previsao };
    d.setDate(d.getDate() + 1);
  }
  throw new ErroApi(0, "Não encontrei um dia de funcionamento nas próximas semanas.");
}

export function dataPorExtenso(isoData, curta = false) {
  const d = new Date(`${isoData}T12:00:00`);
  const opcoes = curta
    ? { weekday: "short", day: "2-digit", month: "2-digit" }
    : { weekday: "long", day: "numeric", month: "long" };
  const texto = d.toLocaleDateString("pt-BR", opcoes).replace(".", "");
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}
