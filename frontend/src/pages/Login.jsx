import { useState } from "react";
import { useAuth } from "../auth";
import { Escudo } from "../components/Layout";
import { Campo, MsgError } from "../components/Ui";

export default function Login() {
  const { entrar } = useAuth();
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);

  const enviar = async (e) => {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try { await entrar(u, p); } catch (err) { setError(err); }
    setEnviando(false);
  };

  return (
    <div className="login">
      <form className="caja" onSubmit={enviar}>
        <Escudo size={40} />
        <h1>Plataforma SOC</h1>
        <p className="tenue" style={{ marginTop: 0 }}>Registro de casos y base de conocimiento</p>
        <MsgError e={error} />
        <div className="grid">
          <Campo etiqueta="Usuario"><input autoFocus value={u} onChange={(e) => setU(e.target.value)} autoComplete="username" required /></Campo>
          <Campo etiqueta="Contraseña"><input type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" required /></Campo>
          <button className="btn primario" disabled={enviando} style={{ justifyContent: "center" }}>
            {enviando ? "Ingresando…" : "Ingresar"}
          </button>
        </div>
      </form>
    </div>
  );
}
