import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { sessao } from "./lib/api.js";
import Login from "./telas/Login.jsx";
import Cadastro from "./telas/Cadastro.jsx";
import Triagem from "./telas/Triagem.jsx";
import Turno from "./telas/Turno.jsx";
import Painel from "./telas/Painel.jsx";

function Protegida({ perfil }) {
  const s = sessao();
  if (!s) return <Navigate to="/" replace />;
  if (perfil && s.perfil !== perfil) return <Navigate to={s.perfil === "gestora" ? "/painel" : "/triagem"} replace />;
  return <Outlet />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/cadastro" element={<Cadastro />} />
        <Route element={<Protegida />}>
          <Route path="/triagem" element={<Triagem />} />
          <Route path="/turno" element={<Turno />} />
        </Route>
        <Route element={<Protegida perfil="gestora" />}>
          <Route path="/painel" element={<Painel />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
