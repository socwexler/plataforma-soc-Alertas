import { useState } from "react";
import { useAuth } from "../auth";
import Isotipo from "../components/Isotipo";
import "../login.css";

// Mismo diseño del ingreso de CYWEX (vulnerabilidades). Las cuentas las crea el administrador: no hay registro.
const RECORDADO = "soc_usuario";
const leer = () => { try { return localStorage.getItem(RECORDADO) || ""; } catch { return ""; } };
const recordar = (u) => { try { if (u) localStorage.setItem(RECORDADO, u); else localStorage.removeItem(RECORDADO); } catch { /* sin almacenamiento */ } };

const Icono = ({ children }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>
);

function Ilustracion() {
  return (
    <svg viewBox="0 0 220 220" fill="none" aria-hidden="true">
      <circle cx="110" cy="110" r="96" fill="#EDE4FF" />
      <circle cx="110" cy="110" r="72" stroke="#C4B5FD" strokeWidth="1.5" strokeDasharray="4 6" />
      <rect x="34" y="120" width="34" height="54" rx="6" fill="#FFFFFF" stroke="#A78BFA" strokeWidth="2" />
      <circle cx="43" cy="132" r="2.4" fill="#7C3AED" />
      <circle cx="43" cy="142" r="2.4" fill="#C4B5FD" />
      <path d="M52 130h8M52 140h8" stroke="#C4B5FD" strokeWidth="2" />
      <rect x="152" y="108" width="34" height="66" rx="6" fill="#FFFFFF" stroke="#A78BFA" strokeWidth="2" />
      <circle cx="161" cy="120" r="2.4" fill="#7C3AED" />
      <circle cx="161" cy="130" r="2.4" fill="#C4B5FD" />
      <path d="M170 118h8M170 128h8" stroke="#C4B5FD" strokeWidth="2" />
      <path d="M110 46 L146 60 V96 C146 126 130 148 110 158 C90 148 74 126 74 96 V60 Z" fill="#FFFFFF" stroke="#7C3AED" strokeWidth="3" />
      <rect x="98" y="92" width="24" height="20" rx="4" fill="#7C3AED" />
      <path d="M102 92 V84 a8 8 0 0 1 16 0 v8" stroke="#7C3AED" strokeWidth="3" />
      <rect x="96" y="168" width="6" height="14" rx="2" fill="#C4B5FD" />
      <rect x="107" y="162" width="6" height="20" rx="2" fill="#A78BFA" />
      <rect x="118" y="172" width="6" height="10" rx="2" fill="#DDD0FB" />
      <path d="M150 60 a20 20 0 0 1 0 -12" stroke="#A78BFA" strokeWidth="2" strokeLinecap="round" />
      <path d="M155 62 a28 28 0 0 1 0 -16" stroke="#C4B5FD" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="52" cy="70" r="3" fill="#A855F7" opacity="0.6" />
      <circle cx="176" cy="72" r="2.4" fill="#7C3AED" opacity="0.5" />
      <circle cx="60" cy="160" r="2.4" fill="#C4B5FD" />
      <circle cx="164" cy="164" r="3" fill="#A855F7" opacity="0.5" />
    </svg>
  );
}

export default function Login() {
  const { entrar } = useAuth();
  const [inicial] = useState(leer);
  const [u, setU] = useState(inicial);
  const [p, setP] = useState("");
  const [guardar, setGuardar] = useState(!!inicial);
  const [ver, setVer] = useState(false);
  const [ayuda, setAyuda] = useState(false);
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);

  const enviar = async (e) => {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    recordar(guardar ? u.trim() : "");   // solo el usuario, nunca la contraseña
    try { await entrar(u, p); } catch (err) { setError(err); }
    setEnviando(false);
  };

  return (
    <div className="login">
      <div className="login-caja">
        <div className="login-forma">
          <div className="login-marca"><Isotipo className="login-isotipo" /><h1>Plataforma <span>SOC</span></h1></div>
          <p className="login-intro">Ingrese con las credenciales que le fueron asignadas.</p>
          <form onSubmit={enviar}>
            <label className="login-campo">
              <Icono><circle cx="12" cy="8" r="4" /><path d="M4 20c1.2-4 4.3-6 8-6s6.8 2 8 6" /></Icono>
              <input aria-label="Usuario" placeholder="Usuario" autoFocus={!inicial} value={u} onChange={(e) => setU(e.target.value)}
                     autoComplete="username" autoCapitalize="none" spellCheck={false} required />
            </label>
            <label className="login-campo">
              <Icono><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></Icono>
              <input aria-label="Contraseña" placeholder="Contraseña" autoFocus={!!inicial} type={ver ? "text" : "password"} value={p}
                     onChange={(e) => setP(e.target.value)} autoComplete="current-password" required />
              <button type="button" onClick={() => setVer(!ver)} aria-label={ver ? "Ocultar contraseña" : "Mostrar contraseña"}>
                {ver
                  ? <Icono><path d="M3 3l18 18" /><path d="M10.6 5.1A10.7 10.7 0 0 1 12 5c7 0 10.5 7 10.5 7a13.2 13.2 0 0 1-3.1 4.1M6.6 6.6C3.5 8.6 1.5 12 1.5 12S5 19 12 19a10.6 10.6 0 0 0 4.1-.8" /><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" /></Icono>
                  : <Icono><path d="M1.5 12S5 5 12 5s10.5 7 10.5 7-3.5 7-10.5 7S1.5 12 1.5 12Z" /><circle cx="12" cy="12" r="3" /></Icono>}
              </button>
            </label>
            <div className="login-fila">
              <label><input type="checkbox" checked={guardar} onChange={(e) => setGuardar(e.target.checked)} />Recordar mi usuario</label>
              <button type="button" className="login-enlace" aria-expanded={ayuda} onClick={() => setAyuda(!ayuda)}>¿Olvidó su contraseña?</button>
            </div>
            {ayuda && <p className="login-ayuda">Pida al líder SOC o al administrador que se la restablezca.</p>}
            {error && <p className="login-error" role="alert">{error.message || String(error)}</p>}
            <button className="login-entrar" disabled={enviando}>{enviando ? "Validando…" : "Ingresar"}</button>
          </form>
        </div>
        <aside className="login-lado">
          <div className="login-ilustracion"><Ilustracion /></div>
          <h2>Mantén tu <span>infraestructura segura</span></h2>
          <p>Servicios de NG SOC, detección de vulnerabilidades, inteligencia de amenazas y protección de marca, aseguramiento mediante guías de hardening.</p>
          <div className="login-pie">Wexler<i aria-hidden="true">•</i>Monitoreo 7x24</div>
        </aside>
      </div>
    </div>
  );
}
