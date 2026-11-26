import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Campo, Crit, Modal, MsgError, Paginador } from "../components/Ui";
import { duracion, ESTADOS_GLPI, fechaHora, infoGlpi, num, ZONA } from "../util";

export const ESTADOS_ALERTA = { POR_REPORTAR: "Por reportar", EN_GESTION: "En gestión", REPORTADA: "Reportada", CERRADA_GLPI: "Cerrada en GLPI" };
const VISTAS = { pendientes: "Pendientes", reportadas: "Reportadas", cerradas: "Cerradas en GLPI", todas: "Todas" };
const TAMANO = 50;
const corta = new Intl.DateTimeFormat("es-CO", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: ZONA });

function Kpi({ etiqueta, valor, sub }) {
  return <div className="kpi"><div className="etiqueta">{etiqueta}</div><div className="valor">{valor}</div>{sub && <div className="sub">{sub}</div>}</div>;
}

/** Tiempo de espera (o hasta el reporte) frente al SLA de su criticidad. */
function Espera({ a }) {
  if (a.minutos === null || a.minutos === undefined) return <span className="tenue">—</span>;
  const r = a.minutos / a.sla_minutos;
  const clase = r > 1 ? "al-vencida" : r > 0.75 && a.estado !== "REPORTADA" ? "al-riesgo" : "";
  return <span className={clase} title={`SLA de ${a.criticidad || "Media"}: ${duracion(a.sla_minutos)}`}>{duracion(a.minutos)}</span>;
}

/** Bandeja de los tickets que el SIEM crea en GLPI: todos se deben reportar al cliente. */
export default function Alertas() {
  const { usuario, puede } = useAuth();
  const nav = useNavigate();
  const [sp, setSp] = useSearchParams();
  const [f, setF] = useState(() => ({ vista: sp.get("vista") || "pendientes", cliente_id: sp.get("cliente_id") || "", q: sp.get("q") || "" }));
  const [pagina, setPagina] = useState(1);
  const [d, setD] = useState(null);
  const [clientes, setClientes] = useState([]);
  const [glpi, setGlpi] = useState({});
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(null);
  const [ver, setVer] = useState(null);
  const [nota, setNota] = useState(null);

  const cargar = useCallback(() => api("/alertas", { params: { ...f, pagina, tamano: TAMANO } }).then((r) => { setD(r); setError(null); }).catch(setError), [f, pagina]);
  useEffect(() => { api("/clientes").then(setClientes).catch(() => {}); infoGlpi(api).then(setGlpi); }, []);
  useEffect(() => {
    setSp(Object.fromEntries(Object.entries(f).filter(([k, v]) => v && !(k === "vista" && v === "pendientes"))), { replace: true });
    cargar();
    const t = setInterval(cargar, 30000);
    return () => clearInterval(t);
  }, [cargar, f, setSp]);

  const set = (k) => (e) => { setPagina(1); setF((x) => ({ ...x, [k]: e.target.value })); };
  const accion = async (a, que) => {
    setOcupado(a.id); setError(null);
    try {
      await api(`/alertas/${a.id}/${que}`, { metodo: "POST" });
      await cargar();
      window.dispatchEvent(new Event("revision-cambio"));
    } catch (e) { setError(e); }
    setOcupado(null);
  };
  const buscar = async () => {
    setOcupado("buscar"); setError(null); setNota(null);
    try {
      const r = await api("/alertas/traer", { metodo: "POST" });
      setNota(r.nuevas ? `${r.nuevas} alerta(s) nueva(s)` : "No hay alertas nuevas");
      await cargar();
      window.dispatchEvent(new Event("revision-cambio"));
    } catch (e) { setError(e); }
    setOcupado(null);
  };
  const abrir = async (a) => { try { setVer(await api(`/alertas/${a.id}`)); } catch (e) { setError(e); } };
  const ticket = (n) => (glpi.url_web ? <a href={`${glpi.url_web}${n}`} target="_blank" rel="noreferrer">{n}</a> : n);
  const k = d?.resumen, integ = d?.integracion;

  return (
    <>
      <div className="cabecera">
        <div><h1>Alertas por tratar</h1>
          <p>Tickets que el SIEM crea en GLPI. Todos se reportan al cliente: al reportarla se crea el caso WX con el mismo ticket.</p></div>
        <div className="acciones">
          {puede("casos.crear") && integ?.activo && <button className="btn" onClick={buscar} disabled={ocupado === "buscar"}>{ocupado === "buscar" ? "Buscando…" : "Buscar ahora"}</button>}
          {puede("casos.crear") && <Link className="btn" to="/casos/nuevo" title="Para clientes que aún no están afinados en el SIEM">Nuevo caso manual</Link>}
        </div>
      </div>

      {integ && !integ.activo && (
        <div className="alerta aviso">La bandeja no está activada: un administrador la activa en Configuración → GLPI e indica cómo reconocer los tickets del SIEM.
          Mientras tanto los casos se registran como siempre en «Nuevo caso».</div>
      )}
      {integ?.error && <div className="alerta error">La última búsqueda en GLPI falló: {integ.error}</div>}
      {nota && <div className="alerta ok">{nota}</div>}
      <MsgError e={error} />

      {k && (
        <div className="kpis">
          <Kpi etiqueta="Por reportar" valor={num(k.por_reportar)} sub="nadie las ha tomado" />
          <Kpi etiqueta="En gestión" valor={num(k.en_gestion)} sub="un analista las está reportando" />
          <Kpi etiqueta="Fuera del SLA" valor={num(k.vencidas)} sub="pendientes que superan su SLA" />
          <Kpi etiqueta="Sin cliente" valor={num(k.sin_cliente)} sub="entidad de GLPI sin cliente asignado" />
        </div>
      )}

      <div className="panel">
        <div className="tabs">
          {Object.entries(VISTAS).map(([v, t]) => <button key={v} type="button" className={f.vista === v ? "activo" : ""} onClick={() => { setPagina(1); setF((x) => ({ ...x, vista: v })); }}>{t}</button>)}
        </div>
        <div className="filtros">
          <Campo etiqueta="Cliente"><select value={f.cliente_id} onChange={set("cliente_id")}><option value="">Todos</option>{clientes.map((c) => <option key={c.id} value={c.id}>{c.codigo}</option>)}</select></Campo>
          <Campo etiqueta="Buscar"><input value={f.q} onChange={set("q")} placeholder="Título o número de ticket" /></Campo>
        </div>
        {integ?.ultima && <p className="tenue" style={{ margin: "-4px 0 12px" }}>Última búsqueda en GLPI: {fechaHora(integ.ultima)} · se busca cada {integ.minutos} min</p>}

        {!d ? <div className="vacio">Cargando…</div> : !d.items.length ? (
          <div className="vacio">{f.vista === "pendientes" ? "No hay alertas por tratar." : "No hay alertas en esta vista."}</div>
        ) : (
          <div className="tabla-scroll">
            <table className="tabla">
              <thead><tr><th className="num">Ticket</th><th>Llegó a GLPI</th><th className="num">{f.vista === "pendientes" ? "Espera" : "Tiempo"}</th><th>Cliente</th>
                <th>Alerta</th><th>Criticidad</th><th>Estado</th><th></th></tr></thead>
              <tbody>{d.items.map((a) => {
                const mia = a.analista?.id === usuario.id;
                return (
                  <tr key={a.id}>
                    <td className="num"><b>{ticket(a.glpi_ticket_id)}</b>{a.glpi_estado && <div className="tenue" style={{ fontSize: 12 }}>{ESTADOS_GLPI[a.glpi_estado]}</div>}</td>
                    <td style={{ whiteSpace: "nowrap" }} title={fechaHora(a.fecha_alerta)}>{corta.format(new Date(a.fecha_alerta))}</td>
                    <td className="num"><Espera a={a} /></td>
                    <td>{a.cliente ? <span title={a.cliente.nombre}>{a.cliente.codigo}</span> : <span className="badge al-sin" title={`Entidad de GLPI ${a.glpi_entidad_id ?? "sin dato"}: asígnela a un cliente en Clientes`}>Sin cliente</span>}</td>
                    <td style={{ minWidth: 220 }}><button type="button" className="enlace" onClick={() => abrir(a)}>{a.titulo}</button></td>
                    <td><Crit v={a.criticidad} /></td>
                    <td><span className={`badge al-${a.estado}`}>{ESTADOS_ALERTA[a.estado]}</span>
                      {a.analista && <div className="tenue" style={{ fontSize: 12, marginTop: 3 }}>{a.analista.nombre}</div>}</td>
                    <td><div className="acciones" style={{ flexWrap: "nowrap", justifyContent: "flex-end" }}>
                      {a.estado === "REPORTADA" && <Link className="btn chico" to={`/casos/${a.caso_id}`}>{a.caso_numero}</Link>}
                      {puede("casos.crear") && a.estado === "POR_REPORTAR" && <button className="btn chico" disabled={ocupado === a.id} onClick={() => accion(a, "tomar")}>Tomar</button>}
                      {puede("casos.crear") && (a.estado === "POR_REPORTAR" || (a.estado === "EN_GESTION" && (mia || puede("casos.revisar")))) &&
                        <button className="btn chico primario" onClick={() => nav(`/casos/nuevo?alerta=${a.id}`)}>Reportar</button>}
                      {a.estado === "EN_GESTION" && (mia || puede("casos.revisar")) &&
                        <button className="btn chico" disabled={ocupado === a.id} onClick={() => accion(a, "liberar")} title="Devolverla a «Por reportar»">Liberar</button>}
                    </div></td>
                  </tr>
                );
              })}</tbody>
            </table>
          </div>
        )}
        {d && d.total > TAMANO && <Paginador total={d.total} pagina={pagina} tamano={TAMANO} onCambio={setPagina} />}
      </div>

      {ver && (
        <Modal titulo={`Ticket GLPI ${ver.glpi_ticket_id}`} onCerrar={() => setVer(null)}
               pie={<><button className="btn" onClick={() => setVer(null)}>Cerrar</button>
                 {puede("casos.crear") && (ver.estado === "POR_REPORTAR" || (ver.estado === "EN_GESTION" && (ver.analista?.id === usuario.id || puede("casos.revisar")))) &&
                   <button className="btn primario" onClick={() => nav(`/casos/nuevo?alerta=${ver.id}`)}>Reportar</button>}</>}>
          <p><b>{ver.titulo}</b></p>
          <p className="tenue">{ver.cliente ? `${ver.cliente.codigo} - ${ver.cliente.nombre}` : "Sin cliente asignado"} · llegó a GLPI el {fechaHora(ver.fecha_alerta)} · {ESTADOS_ALERTA[ver.estado]}</p>
          <pre className="contenido-ticket">{ver.contenido || "El ticket no tiene descripción."}</pre>
        </Modal>
      )}
    </>
  );
}
