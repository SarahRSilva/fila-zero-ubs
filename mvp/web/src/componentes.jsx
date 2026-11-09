import { useNavigate } from "react-router-dom";

export function IconeMarca({ pequeno = false }) {
  return (
    <div className={`marca__icone${pequeno ? " marca__icone--p" : ""}`} aria-hidden="true">
      <svg width={pequeno ? 18 : 24} height={pequeno ? 18 : 24} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
        <path d="M12 4v16M4 12h16" />
      </svg>
    </div>
  );
}

export function Cabecalho({ titulo, sub, etiqueta, voltarPara }) {
  const navegar = useNavigate();
  return (
    <header className="cabecalho">
      {voltarPara && (
        <button type="button" className="cabecalho__voltar" aria-label="Voltar" onClick={() => navegar(voltarPara)}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
      )}
      <div>
        <span className="cabecalho__titulo">{titulo}</span>
        {sub && <span className="cabecalho__sub">{sub}</span>}
      </div>
      {etiqueta && <span className="etiqueta">{etiqueta}</span>}
    </header>
  );
}

export const ROTULO_COR = {
  verde: "Verde · rotina, pode agendar",
  amarelo: "Amarelo · atendimento o quanto antes",
  vermelho: "Vermelho · procure a UPA agora",
};

export function Classificacao({ cor, texto }) {
  return (
    <div className={`classificacao cor-${cor}`}>
      <span className="ponto" aria-hidden="true" />
      <span>{texto ?? ROTULO_COR[cor]}</span>
    </div>
  );
}

export function AlertaEmergencia() {
  return (
    <div className="cartao alerta">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#D03B3B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 9v4M12 17h.01" />
        <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
      </svg>
      <p>
        <strong>Emergência?</strong> Dor no peito, falta de ar forte ou sangramento que não para: ligue <strong>192 (SAMU)</strong> ou vá à UPA agora.
      </p>
    </div>
  );
}
