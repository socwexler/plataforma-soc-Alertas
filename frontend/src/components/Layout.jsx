import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { useTema } from "../tema";
import { ROLES } from "../util";
import Isotipo from "./Isotipo";

// Iconos de línea del menú (24×24)
const I = {
  inicio: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
  tablero: <><path d="M4 20V10M10 20V4M16 20v-7M21 20H3" /></>,
  sla: <><circle cx="12" cy="13" r="8" /><path d="M12 9v4l2.5 2.5M10 2h4M12 2v3" /></>,
  nuevo: <><rect x="3" y="3" width="18" height="18" rx="4" /><path d="M12 8v8M8 12h8" /></>,
  casos: <><path d="M9 6h11M9 12h11M9 18h11" /><circle cx="4.5" cy="6" r="1" /><circle cx="4.5" cy="12" r="1" /><circle cx="4.5" cy="18" r="1" /></>,
  mios: <><circle cx="12" cy="8" r="4" /><path d="M4 20c1.2-4 4.3-6 8-6s6.8 2 8 6" /></>,
  revisar: <><path d="M9 4h6v3H9zM7 5H5v15h14V5h-2" /><path d="m9 13 2 2 4-4" /></>,
  kb: <><path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z" /><path d="M4 19V5M8 7h7" /></>,
  informes: <><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" /><path d="M14 3v6h6M8 13h8M8 17h5" /></>,
  clientes: <><path d="M4 21V5l8-2v18M12 8h8v13M8 8h.01M8 12h.01M8 16h.01M16 12h.01M16 16h.01M2 21h20" /></>,
  importar: <><path d="M12 15V3m0 12-4-4m4 4 4-4" /><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" /></>,
  usuarios: <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c.8-3.4 3.3-5.5 6.5-5.5s5.7 2.1 6.5 5.5M16 4.5a3.5 3.5 0 0 1 0 7M18 14.6c1.8.7 3 2.6 3.5 5.4" /></>,
  config: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></>,
  salir: <><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M15 12H3" /></>,
  sol: <><circle cx="12" cy="12" r="4.5" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>,
  luna: <><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></>,
};
export const Icono = ({ n }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{I[n]}</svg>
);

export default function Layout() {
  const { usuario, salir, puede } = useAuth();
  const [tema, alternarTema] = useTema();
  const { pathname, search } = useLocation();
  const [pend, setPend] = useState({ por_revisar: 0, mis_observados: 0 });
  const mios = `analista_id=${usuario.id}`;
  const en = (ruta, consulta) => pathname === ruta && search.replace(/^\?/, "") === consulta;
  const oscuro = tema === "oscuro";

  useEffect(() => {
    const cargar = () => api("/casos/pendientes").then(setPend).catch(() => {});
    cargar();
    const t = setInterval(cargar, 60000);
    window.addEventListener("revision-cambio", cargar);
    return () => { clearInterval(t); window.removeEventListener("revision-cambio", cargar); };
  }, [pathname]);
  return (
    <div className="app">
      <aside className="lateral">
        <div className="marca"><Isotipo className="iso" /><div><b>Plataforma <span>SOC</span></b><small>Wexler · Monitoreo 7x24</small></div></div>
        <nav className="menu">
          {puede("tablero.ver") && <NavLink to="/" end><Icono n="inicio" />Inicio</NavLink>}
          {puede("tablero.ver") && <NavLink to="/tablero"><Icono n="tablero" />Tablero</NavLink>}
          {puede("tablero.ver") && <NavLink to="/sla"><Icono n="sla" />SLA por analista</NavLink>}
          {puede("casos.crear") && <NavLink to="/casos/nuevo"><Icono n="nuevo" />Nuevo caso</NavLink>}
          <NavLink to="/casos" end className={() => (en("/casos", "") ? "active" : "")}><Icono n="casos" />Casos</NavLink>
          {puede("casos.crear") && !puede("casos.revisar") && (
            <NavLink to={`/casos?${mios}`} className={() => (en("/casos", mios) ? "active" : "")}><Icono n="mios" />Mis casos
              {pend.mis_observados > 0 && <span className="cuenta" title="Devueltos para corregir">{pend.mis_observados}</span>}</NavLink>
          )}
          {puede("casos.revisar") && (
            <NavLink to="/casos?revision=PENDIENTE" className={() => (en("/casos", "revision=PENDIENTE") ? "active" : "")}><Icono n="revisar" />Por revisar
              {pend.por_revisar > 0 && <span className="cuenta">{pend.por_revisar}</span>}</NavLink>
          )}
          {puede("kb.ver") && <NavLink to="/conocimiento"><Icono n="kb" />Base de conocimiento</NavLink>}
          {puede("informes.ver") && <NavLink to="/informes"><Icono n="informes" />Informes</NavLink>}
          {(puede("clientes.admin") || puede("usuarios.admin")) && <span className="sep">Administración</span>}
          {puede("clientes.admin") && <NavLink to="/clientes"><Icono n="clientes" />Clientes</NavLink>}
          {puede("importar") && <NavLink to="/importar"><Icono n="importar" />Importar bitácora</NavLink>}
          {puede("usuarios.admin") && <NavLink to="/usuarios"><Icono n="usuarios" />Usuarios</NavLink>}
          {puede("config.admin") && <NavLink to="/configuracion"><Icono n="config" />Configuración</NavLink>}
        </nav>
        <div className="usuario-box">
          <div className="quien"><b>{usuario.nombre}</b><span>{ROLES[usuario.rol]}</span></div>
          <button type="button" className="lado-btn" onClick={salir}><Icono n="salir" />Cerrar sesión</button>
          <button type="button" className="lado-btn" role="switch" aria-checked={oscuro} onClick={alternarTema}
                  title={oscuro ? "Cambiar a modo día" : "Cambiar a modo noche"}>
            <Icono n={oscuro ? "luna" : "sol"} />{oscuro ? "Modo noche" : "Modo día"}<span className={`interruptor ${oscuro ? "on" : ""}`} aria-hidden="true" />
          </button>
        </div>
      </aside>
      <main className="principal"><Outlet /></main>
    </div>
  );
}
