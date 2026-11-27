import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Campo, Confirmar, Modal, MsgError } from "../components/Ui";
import PasosSharePoint from "../components/PasosSharePoint";
import { copiarTexto, duracion, fecha, fechaHora, num, olvidarGlpi } from "../util";

const PESTANAS = [["sistema", "Estado"], ["general", "General"], ["correo_cliente", "Correo al cliente"], ["avisos", "Avisos internos"],
  ["glpi", "GLPI"], ["fortisiem", "FortiSIEM"], ["sharepoint", "SharePoint"], ["conexiones", "Otras APIs"], ["claves", "Claves de acceso"]];
const INTRO = {
  general: "Parámetros de toda la plataforma. El SLA es el tiempo entre la alerta del SIEM y el reporte al cliente: cambia el cumplimiento en inicio, tablero, casos e informes en borrador; los finales no cambian.",
  correo_cliente: "Datos fijos del borrador de alerta. Los destinatarios de cada cliente se administran en Clientes → Correos. La plataforma no envía correos a clientes.",
  avisos: "Correos automáticos solo para el equipo de Wexler: casos por revisar, devueltos y fallas de GLPI. Llevan número, cliente, alerta y criticidad, sin el detalle del caso.",
  glpi: "Integración de tickets con GLPI 10.",
  fortisiem: "Guarda y prueba la conexión. Por ahora los anexos se siguen cargando por archivo en cada informe.",
  sharepoint: "Anexos del informe desde las carpetas de SharePoint, solo lectura. «Carpeta sincronizada» lee la carpeta de OneDrive montada en el equipo (SHAREPOINT_CARPETA_LOCAL en el .env); «Microsoft Graph» necesita una aplicación de Entra ID con Sites.Selected de lectura sobre el sitio.",
};

function Entrada({ c, valor, onCambio, borrar, onBorrar }) {
  const set = (e) => onCambio(e.target.value);
  const ayuda = [c.ayuda, c.clave.startsWith("sla_") && Number(valor) >= 60 && duracion(Number(valor)), c.ilegible && "no se pudo leer: escríbala de nuevo"].filter(Boolean).join(" · ") || undefined;
  if (c.tipo === "si_no") return <label className="check"><input type="checkbox" checked={!!valor} onChange={(e) => onCambio(e.target.checked)} /> {c.etiqueta}{c.ayuda && <span className="ayuda"> · {c.ayuda}</span>}</label>;
  if (c.tipo === "opcion") return <Campo etiqueta={c.etiqueta} ayuda={ayuda}><select value={valor ?? ""} onChange={set}>{c.opciones.map((o) => <option key={o} value={o}>{c.nombres?.[o] || o}</option>)}</select></Campo>;
  if (c.tipo === "correos" && !c.uno) return <Campo etiqueta={c.etiqueta} ayuda={ayuda}><textarea rows={2} value={valor ?? ""} onChange={set} /></Campo>;
  if (c.tipo === "secreto") return (
    <Campo etiqueta={c.etiqueta} ayuda={ayuda}>
      <div className="acciones" style={{ flexWrap: "nowrap" }}>
        <input type="password" autoComplete="new-password" value={valor || ""} disabled={borrar} onChange={set}
               placeholder={borrar ? "se borrará al guardar" : c.definida ? "guardada · escriba para reemplazarla" : "sin definir"} />
        {c.definida && <button type="button" className="btn chico" onClick={(e) => { e.preventDefault(); onBorrar(); }}>{borrar ? "Deshacer" : "Borrar"}</button>}
      </div>
    </Campo>
  );
  return <Campo etiqueta={c.etiqueta} ayuda={ayuda}><input type={c.tipo === "entero" ? "number" : "text"} min={c.min} max={c.max} value={valor ?? ""} onChange={set} autoComplete="off" /></Campo>;
}

function Grupo({ g, onGuardado, children }) {
  const inicial = useCallback(() => Object.fromEntries(g.campos.filter((c) => c.tipo !== "secreto").map((c) => [c.clave, c.valor])), [g]);
  const [f, setF] = useState(inicial);
  const [borrar, setBorrar] = useState([]);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const [restablecer, setRestablecer] = useState(false);
  useEffect(() => { setF(inicial()); setBorrar([]); }, [inicial]);
  const cambiada = g.campos.some((c) => c.origen === "pantalla");
  const ultimo = g.campos.filter((c) => c.en).sort((a, b) => (a.en < b.en ? 1 : -1))[0];

  const guardar = async (e) => {
    e.preventDefault();
    setOcupado(true); setError(null); setMsg(null);
    const valores = {};
    g.campos.forEach((c) => {
      const v = f[c.clave];
      if (c.tipo === "secreto") { if (v) valores[c.clave] = v; } else if (c.tipo === "entero") valores[c.clave] = v === "" || v === null ? null : Number(v); else valores[c.clave] = v;
    });
    try { onGuardado(await api(`/config/${g.grupo}`, { metodo: "PUT", datos: { valores, borrar } })); olvidarGlpi(); setMsg("Configuración guardada. Ya está en uso."); }
    catch (err) { setError(err); }
    setOcupado(false);
  };
  return (
    <>
      <form className="panel" onSubmit={guardar} autoComplete="off">
        <p className="tenue" style={{ marginTop: 0 }}>{INTRO[g.grupo]}</p>
        {msg && <div className="alerta ok">{msg}</div>}
        <MsgError e={error} />
        <div className="grid g2">
          {g.campos.map((c) => <Entrada key={c.clave} c={c} valor={f[c.clave]} onCambio={(v) => { setMsg(null); setF((x) => ({ ...x, [c.clave]: v })); }}
            borrar={borrar.includes(c.clave)} onBorrar={() => { setF((x) => ({ ...x, [c.clave]: "" })); setBorrar((b) => (b.includes(c.clave) ? b.filter((k) => k !== c.clave) : [...b, c.clave])); }} />)}
        </div>
        <div className="acciones" style={{ marginTop: 16 }}>
          <button className="btn primario" disabled={ocupado}>{ocupado ? "Guardando…" : "Guardar"}</button>
          {cambiada && <button type="button" className="btn" onClick={() => setRestablecer(true)}>Restablecer</button>}
          {ultimo && <span className="tenue">Última modificación: {ultimo.por}, {fechaHora(ultimo.en)}</span>}
        </div>
      </form>
      {children}
      {restablecer && (
        <Confirmar titulo={`Restablecer ${g.titulo}`} boton="Restablecer" peligro onCerrar={() => setRestablecer(false)}
                   onAceptar={async () => { onGuardado(await api(`/config/${g.grupo}/restablecer`, { metodo: "POST" })); olvidarGlpi(); setRestablecer(false); setMsg("Se restablecieron los valores de la instalación."); }}>
          <p style={{ margin: 0 }}>Se borran los cambios hechos en esta pantalla, incluidas las claves, y se vuelve a los valores de la instalación.</p>
        </Confirmar>
      )}
    </>
  );
}

function Probar({ titulo, boton, ejecutar, children }) {
  const [msg, setMsg] = useState(null);
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const probar = async () => {
    setOcupado(true); setMsg(null); setError(null);
    try { setMsg(await ejecutar()); } catch (e) { setError(e); }
    setOcupado(false);
  };
  return (
    <div className="panel"><h2>{titulo}</h2>
      {msg && <div className="alerta ok">{msg}</div>}
      <MsgError e={error} />
      <div className="acciones">{children}<button className="btn" disabled={ocupado} onClick={probar}>{ocupado ? "Probando…" : boton}</button>
        <span className="tenue">Usa lo que está guardado.</span></div>
    </div>
  );
}

function Avisos() {
  const { usuario } = useAuth();
  const [para, setPara] = useState(usuario.email || "");
  const [d, setD] = useState(null);
  const [error, setError] = useState(null);
  const cargar = () => api("/config/avisos").then(setD).catch(setError);
  useEffect(() => { cargar(); }, []);
  const E = { PENDIENTE: "Pendiente", ENVIADO: "Enviado", ERROR: "Error", DESCARTADO: "Descartado" };
  return (
    <>
      <Probar titulo="Probar el correo" boton="Enviar prueba" ejecutar={async () => { await api("/config/avisos/probar", { metodo: "POST", datos: { para } }); return `Prueba enviada a ${para}.`; }}>
        <input value={para} onChange={(e) => setPara(e.target.value)} placeholder="destinatario" style={{ maxWidth: 300 }} />
      </Probar>
      <div className="panel">
        <div className="cabecera" style={{ marginBottom: 8 }}><h2 style={{ margin: 0 }}>Últimos avisos</h2>
          <div className="acciones"><button className="btn chico" onClick={cargar}>Actualizar</button>
            {d && (d.cuenta.ERROR || d.cuenta.PENDIENTE) ? <button className="btn chico" onClick={() => api("/config/avisos/reintentar", { metodo: "POST" }).then(cargar).catch(setError)}>Reintentar pendientes</button> : null}</div></div>
        <MsgError e={error} />
        <div className="tabla-scroll"><table className="tabla"><thead><tr><th>Fecha</th><th>Asunto</th><th>Estado</th><th>Detalle</th></tr></thead><tbody>
          {d?.items.map((a) => <tr key={a.id}><td style={{ whiteSpace: "nowrap" }}>{fechaHora(a.creado_en)}</td><td>{a.asunto}</td><td>{E[a.estado]}</td><td>{a.error ? `${a.error} (intento ${a.intentos})` : a.enviado_en ? fechaHora(a.enviado_en) : "—"}</td></tr>)}
          {d && !d.items.length && <tr><td colSpan={4} className="vacio">Sin avisos.</td></tr>}
        </tbody></table></div>
      </div>
    </>
  );
}

const CX = { nombre: "", url: "", autenticacion: "cabecera", cabecera: "x-apikey", usuario: "", notas: "", activo: true, clave: "" };
function Conexiones() {
  const [lista, setLista] = useState([]);
  const [editar, setEditar] = useState(null);
  const [quitar, setQuitar] = useState(null);
  const [error, setError] = useState(null);
  const [prueba, setPrueba] = useState({});
  const cargar = () => api("/config/conexiones").then(setLista).catch(setError);
  useEffect(() => { cargar(); }, []);
  const set = (k) => (e) => setEditar((x) => ({ ...x, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  const guardar = async () => {
    setError(null);
    const d = { ...editar }; ["clave", "cabecera", "usuario", "notas"].forEach((k) => { d[k] = d[k] || null; });
    try { await api(d.id ? `/config/conexiones/${d.id}` : "/config/conexiones", { metodo: d.id ? "PUT" : "POST", datos: d }); setEditar(null); cargar(); } catch (e) { setError(e); }
  };
  const probar = async (c) => {
    setPrueba((p) => ({ ...p, [c.id]: "Probando…" }));
    try { const r = await api(`/config/conexiones/${c.id}/probar`, { metodo: "POST" }); setPrueba((p) => ({ ...p, [c.id]: `Respondió ${r.codigo} en ${r.ms} ms` })); } catch (e) { setPrueba((p) => ({ ...p, [c.id]: e.message })); }
  };
  return (
    <div className="panel">
      <div className="cabecera" style={{ marginBottom: 8 }}><p className="tenue" style={{ margin: 0 }}>Registro de otros servicios (VirusTotal, AbuseIPDB…). Se guardan y se prueban; usarlos dentro de los casos requiere desarrollo.</p>
        <button className="btn primario" onClick={() => { setError(null); setEditar({ ...CX }); }}>+ Agregar API</button></div>
      <MsgError e={!editar && error} />
      <div className="tabla-scroll"><table className="tabla"><thead><tr><th>Nombre</th><th>Dirección</th><th>Clave</th><th>Prueba</th><th>Acciones</th></tr></thead><tbody>
        {lista.map((c) => <tr key={c.id} className={c.activo ? "" : "inactiva"}><td><b>{c.nombre}</b>{c.notas && <div className="tenue">{c.notas}</div>}</td><td className="mono" style={{ overflowWrap: "anywhere" }}>{c.url}</td>
          <td>{c.autenticacion === "ninguna" ? "No requiere" : c.definida ? "Guardada" : <span className="badge crit-Media">Falta</span>}</td><td>{prueba[c.id] || "—"}</td>
          <td><div className="acciones fila"><button className="btn chico" onClick={() => probar(c)}>Probar</button><button className="btn chico" onClick={() => { setError(null); setEditar({ ...CX, ...c, cabecera: c.cabecera || "", usuario: c.usuario || "", notas: c.notas || "", clave: "" }); }}>Editar</button><button className="btn chico peligro" onClick={() => setQuitar(c)}>Eliminar</button></div></td></tr>)}
        {!lista.length && <tr><td colSpan={5} className="vacio">Sin conexiones.</td></tr>}
      </tbody></table></div>
      {quitar && <Confirmar titulo={`Eliminar ${quitar.nombre}`} boton="Eliminar" peligro onCerrar={() => setQuitar(null)} onAceptar={async () => { await api(`/config/conexiones/${quitar.id}`, { metodo: "DELETE" }); setQuitar(null); cargar(); }}><p style={{ margin: 0 }}>Se borra la conexión con su clave.</p></Confirmar>}
      {editar && (
        <Modal titulo={editar.id ? `Editar ${editar.nombre}` : "Agregar API"} onCerrar={() => setEditar(null)} pie={<><button className="btn" onClick={() => setEditar(null)}>Cancelar</button><button className="btn primario" onClick={guardar}>Guardar</button></>}>
          <MsgError e={error} />
          <div className="grid g2">
            <Campo etiqueta="Nombre"><input value={editar.nombre} onChange={set("nombre")} /></Campo>
            <Campo etiqueta="Autenticación"><select value={editar.autenticacion} onChange={set("autenticacion")}><option value="cabecera">Clave en una cabecera</option><option value="bearer">Token Bearer</option><option value="basica">Usuario y contraseña</option><option value="ninguna">Ninguna</option></select></Campo>
            <Campo etiqueta="Dirección" ayuda="la que se consulta al probar" className="span-todo"><input value={editar.url} onChange={set("url")} placeholder="https://" /></Campo>
            {editar.autenticacion === "cabecera" && <Campo etiqueta="Nombre de la cabecera"><input value={editar.cabecera} onChange={set("cabecera")} /></Campo>}
            {editar.autenticacion === "basica" && <Campo etiqueta="Usuario"><input value={editar.usuario} onChange={set("usuario")} autoComplete="off" /></Campo>}
            {editar.autenticacion !== "ninguna" && <Campo etiqueta="Clave" ayuda={editar.definida ? "guardada; vacío = no cambiar" : undefined}><input type="password" value={editar.clave} onChange={set("clave")} autoComplete="new-password" /></Campo>}
            <Campo etiqueta="Notas" className="span-todo"><input value={editar.notas} onChange={set("notas")} /></Campo>
            <label className="check"><input type="checkbox" checked={editar.activo} onChange={set("activo")} /> Activa</label>
          </div>
        </Modal>
      )}
    </div>
  );
}

function Claves() {
  const [lista, setLista] = useState([]);
  const [clientes, setClientes] = useState([]);
  const [nueva, setNueva] = useState(null);
  const [creada, setCreada] = useState(null);
  const [revocar, setRevocar] = useState(null);
  const [error, setError] = useState(null);
  const cargar = () => api("/config/claves").then(setLista).catch(setError);
  useEffect(() => { cargar(); api("/clientes").then(setClientes).catch(() => {}); }, []);
  const set = (k) => (e) => setNueva((x) => ({ ...x, [k]: e.target.value }));
  const permiso = (p) => (e) => setNueva((x) => ({ ...x, permisos: e.target.checked ? [...x.permisos, p] : x.permisos.filter((y) => y !== p) }));
  const crear = async () => {
    setError(null);
    try { const r = await api("/config/claves", { metodo: "POST", datos: { nombre: nueva.nombre, permisos: nueva.permisos, cliente_id: nueva.cliente_id ? Number(nueva.cliente_id) : null, dias: Number(nueva.dias) } }); setNueva(null); setCreada(r); cargar(); } catch (e) { setError(e); }
  };
  return (
    <div className="panel">
      <div className="cabecera" style={{ marginBottom: 8 }}><p className="tenue" style={{ margin: 0 }}>Para que otro sistema (por ejemplo Power BI) consulte esta plataforma. Son de solo lectura, vencen y se pueden revocar. Entregan datos del caso, sin análisis ni registros.</p>
        <button className="btn primario" onClick={() => { setError(null); setNueva({ nombre: "", permisos: ["resumen"], cliente_id: "", dias: 180 }); }}>+ Crear clave</button></div>
      <MsgError e={!nueva && error} />
      <div className="tabla-scroll"><table className="tabla"><thead><tr><th>Nombre</th><th>Clave</th><th>Permisos</th><th>Cliente</th><th>Vence</th><th>Último uso</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>
        {lista.map((k) => <tr key={k.id} className={k.estado === "Activa" ? "" : "inactiva"}><td><b>{k.nombre}</b><div className="tenue">{k.creada_por}</div></td><td className="mono">{k.prefijo}…</td><td>{k.permisos.join(", ")}</td><td>{k.cliente || "Todos"}</td><td>{fecha(k.vence_en)}</td><td>{k.ultimo_uso ? fechaHora(k.ultimo_uso) : "Sin uso"}</td><td>{k.estado}</td>
          <td>{k.estado === "Activa" && <div className="acciones fila"><button className="btn chico peligro" onClick={() => setRevocar(k)}>Revocar</button></div>}</td></tr>)}
        {!lista.length && <tr><td colSpan={8} className="vacio">Sin claves.</td></tr>}
      </tbody></table></div>
      <p className="tenue" style={{ margin: "10px 0 0" }}>Uso: cabecera <span className="mono">X-Api-Key</span> en <span className="mono">/api/externo/casos?desde=AAAA-MM-DD&hasta=AAAA-MM-DD</span> o <span className="mono">/api/externo/resumen?desde=…&hasta=…</span></p>
      {revocar && <Confirmar titulo={`Revocar ${revocar.nombre}`} boton="Revocar" peligro onCerrar={() => setRevocar(null)} onAceptar={async () => { await api(`/config/claves/${revocar.id}/revocar`, { metodo: "POST" }); setRevocar(null); cargar(); }}><p style={{ margin: 0 }}>El sistema que la usa dejará de consultar de inmediato. No se puede deshacer.</p></Confirmar>}
      {nueva && (
        <Modal titulo="Crear clave de acceso" onCerrar={() => setNueva(null)} pie={<><button className="btn" onClick={() => setNueva(null)}>Cancelar</button><button className="btn primario" disabled={!nueva.permisos.length} onClick={crear}>Crear</button></>}>
          <MsgError e={error} />
          <div className="grid g2">
            <Campo etiqueta="Nombre" ayuda="qué sistema la usará"><input value={nueva.nombre} onChange={set("nombre")} /></Campo>
            <Campo etiqueta="Vigencia"><select value={nueva.dias} onChange={set("dias")}>{[30, 90, 180, 365].map((d) => <option key={d} value={d}>{d} días</option>)}</select></Campo>
            <Campo etiqueta="Cliente"><select value={nueva.cliente_id} onChange={set("cliente_id")}><option value="">Todos</option>{clientes.map((c) => <option key={c.id} value={c.id}>{c.codigo}</option>)}</select></Campo>
            <div><label className="check"><input type="checkbox" checked={nueva.permisos.includes("resumen")} onChange={permiso("resumen")} /> Totales (resumen)</label><label className="check"><input type="checkbox" checked={nueva.permisos.includes("casos")} onChange={permiso("casos")} /> Lista de casos</label></div>
          </div>
        </Modal>
      )}
      {creada && (
        <Modal titulo="Clave creada" onCerrar={() => setCreada(null)} pie={<><button className="btn" onClick={() => copiarTexto(creada.clave)}>Copiar</button><button className="btn primario" onClick={() => setCreada(null)}>Ya la guardé</button></>}>
          <div className="alerta aviso">Guárdela ahora: no se puede volver a mostrar.</div>
          <p className="mono" style={{ overflowWrap: "anywhere", userSelect: "all", margin: 0 }}>{creada.clave}</p>
        </Modal>
      )}
    </div>
  );
}

function Sistema() {
  const [s, setS] = useState(null);
  const [error, setError] = useState(null);
  const { puede } = useAuth();
  useEffect(() => { api("/config/sistema").then(setS).catch(setError); }, []);
  if (!s) return error ? <MsgError e={error} /> : <div className="vacio">Cargando…</div>;
  const K = ({ t, v, sub }) => <div className="kpi"><div className="etiqueta">{t}</div><div className="valor">{v}</div>{sub && <div className="sub">{sub}</div>}</div>;
  return (
    <>
      {s.claves_ilegibles.length > 0 && <div className="alerta error">Hay claves guardadas que ya no se pueden leer (cambió JWT_SECRET). Escríbalas de nuevo: {s.claves_ilegibles.join(", ")}.</div>}
      <div className="kpis">
        <K t="Casos" v={num(s.casos)} sub={s.casos_anulados ? `${num(s.casos_anulados)} anulados` : null} />
        <K t="Base de datos" v={`${num(s.base_mb)} MB`} sub={`${num(s.adjuntos_mb)} MB en adjuntos`} />
        <K t="Usuarios con acceso" v={num(s.usuarios_activos)} />
        <K t="Clientes sin correos" v={num(s.clientes_sin_correos)} />
      </div>
      <div className="panel"><table className="tabla"><tbody>
        <tr><td>Versión del esquema</td><td>{s.esquema}</td></tr>
        <tr><td>Convertidor de PDF</td><td>{s.convertidor ? "Responde" : <span className="badge crit-Alta">No responde</span>}</td></tr>
        <tr><td>GLPI</td><td>{!s.glpi.activo ? "Desactivado" : s.glpi.error_sincronizacion ? `Con error: ${s.glpi.error_sincronizacion}` : s.glpi.ultima_sincronizacion ? `Activo · última sincronización ${fechaHora(s.glpi.ultima_sincronizacion)}` : "Activo · sin sincronizar desde el inicio"}</td></tr>
        <tr><td>Avisos internos</td><td>{s.avisos_activos ? "Activos" : "Desactivados"}</td></tr>
        <tr><td>Hora del servidor</td><td>{fechaHora(s.hora)}</td></tr>
      </tbody></table></div>
      <div className="panel"><h2>Otras tareas de administración</h2><div className="acciones">
        {puede("usuarios.admin") && <Link className="btn" to="/usuarios">Usuarios y roles</Link>}
        {puede("clientes.admin") && <Link className="btn" to="/clientes">Clientes, correos y logos</Link>}
        {puede("kb.editar") && <Link className="btn" to="/conocimiento">Base de conocimiento</Link>}
        {puede("importar") && <Link className="btn" to="/importar">Importar bitácora</Link>}
        {puede("usuarios.admin") && <Link className="btn" to="/cambios">Registro de cambios</Link>}
      </div></div>
    </>
  );
}

export default function Configuracion() {
  const [sp, setSp] = useSearchParams();
  const tab = PESTANAS.some(([k]) => k === sp.get("t")) ? sp.get("t") : "sistema";
  const [grupos, setGrupos] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { api("/config").then(setGrupos).catch(setError); }, []);
  const g = grupos?.find((x) => x.grupo === tab);
  return (
    <>
      <div className="cabecera"><div><h1>Configuración</h1><p>Parámetros, conexiones a otras APIs, avisos y estado de la plataforma. Las claves se guardan cifradas y no se vuelven a mostrar.</p></div></div>
      <MsgError e={error} />
      <div className="tabs" style={{ flexWrap: "wrap" }}>{PESTANAS.map(([k, t]) => <button key={k} className={tab === k ? "activo" : ""} onClick={() => setSp({ t: k })}>{t}</button>)}</div>
      {tab === "sistema" && <Sistema />}
      {tab === "conexiones" && <Conexiones />}
      {tab === "claves" && <Claves />}
      {tab === "sharepoint" && grupos && <PasosSharePoint version={grupos} />}
      {g && (
        <Grupo key={g.grupo} g={g} onGuardado={setGrupos}>
          {tab === "avisos" && <Avisos />}
          {tab === "glpi" && <Probar titulo="Probar la conexión" boton="Probar GLPI" ejecutar={async () => { const r = await api("/glpi/probar", { metodo: "POST" }); return `Conexión correcta como «${r.usuario}» (entidad activa: ${r.entidad_activa}).`; }} />}
          {tab === "sharepoint" && <Probar titulo="Probar la conexión" boton="Probar SharePoint" ejecutar={async () => {
            const r = await api("/config/sharepoint/probar", { metodo: "POST" });
            return <div>Conexión correcta: {r.carpetas_base} carpetas en la carpeta base.
              {r.tipos.map((t) => <div key={t.tipo}>· <b>{t.nombre}:</b> {t.error || `${t.carpeta}${t.sin_carpeta.length ? ` · sin subcarpeta: ${t.sin_carpeta.join(", ")}` : " · todos los clientes tienen subcarpeta"}`}</div>)}</div>;
          }} />}
          {tab === "fortisiem" && <Probar titulo="Probar la conexión" boton="Probar FortiSIEM" ejecutar={async () => { const r = await api("/config/fortisiem/probar", { metodo: "POST" }); return `FortiSIEM aceptó las credenciales (${r.ms} ms).`; }} />}
        </Grupo>
      )}
    </>
  );
}
