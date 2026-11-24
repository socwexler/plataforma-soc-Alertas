import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { ROLES } from "../util";

export function Escudo({ size = 28 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <path d="M16 2 4 7v8c0 7.5 5.1 13.4 12 15 6.9-1.6 12-7.5 12-15V7z" fill="#1f9e89" />
      <path d="m11 16 3.5 3.5L21 13" stroke="#fff" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function Layout() {
  const { usuario, salir, puede } = useAuth();
  const { pathname, search } = useLocation();
  const [pend, setPend] = useState({ por_revisar: 0, mis_observados: 0 });
  const mios = `analista_id=${usuario.id}`;
  const en = (ruta, consulta) => pathname === ruta && search.replace(/^\?/, "") === consulta;

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
        <div className="marca"><Escudo /><div>Plataforma SOC<small>Wexler · Monitoreo 7x24</small></div></div>
        <nav className="menu">
          {puede("tablero.ver") && <NavLink to="/" end>Inicio</NavLink>}
          {puede("tablero.ver") && <NavLink to="/tablero">Tablero</NavLink>}
          {puede("casos.crear") && <NavLink to="/casos/nuevo">Nuevo caso</NavLink>}
          <NavLink to="/casos" end className={() => (en("/casos", "") ? "active" : "")}>Casos</NavLink>
          {puede("casos.crear") && !puede("casos.revisar") && (
            <NavLink to={`/casos?${mios}`} className={() => (en("/casos", mios) ? "active" : "")}>Mis casos
              {pend.mis_observados > 0 && <span className="cuenta" title="Devueltos para corregir">{pend.mis_observados}</span>}</NavLink>
          )}
          {puede("casos.revisar") && (
            <NavLink to="/casos?revision=PENDIENTE" className={() => (en("/casos", "revision=PENDIENTE") ? "active" : "")}>Por revisar
              {pend.por_revisar > 0 && <span className="cuenta">{pend.por_revisar}</span>}</NavLink>
          )}
          {puede("kb.ver") && <NavLink to="/conocimiento">Base de conocimiento</NavLink>}
          {puede("informes.ver") && <NavLink to="/informes">Informes</NavLink>}
          {(puede("clientes.admin") || puede("usuarios.admin")) && <span className="sep">Administración</span>}
          {puede("clientes.admin") && <NavLink to="/clientes">Clientes</NavLink>}
          {puede("importar") && <NavLink to="/importar">Importar bitácora</NavLink>}
          {puede("usuarios.admin") && <NavLink to="/usuarios">Usuarios</NavLink>}
          {puede("config.admin") && <NavLink to="/configuracion">Configuración</NavLink>}
        </nav>
        <div className="usuario-box">
          <b>{usuario.nombre}</b>
          {ROLES[usuario.rol]}
          <div><button className="btn chico" onClick={salir}>Cerrar sesión</button></div>
        </div>
      </aside>
      <main className="principal"><Outlet /></main>
    </div>
  );
}
