import { useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { ImagenPrivada, subirImagen } from "../components/Imagen";
import { AccionesFila, Campo, Confirmar, Modal, MsgError } from "../components/Ui";
import { fechaHora, num } from "../util";

const NUEVO = { codigo: "", nombre: "", servicio_soc: true, servicio_noc: false, dia_corte: 1, eps_contratados: "",
  fuentes_licencia: "", glpi_entidad_id: "", sharepoint_carpeta: "", activo: true };

function PanelGlpi() {
  const { puede } = useAuth();
  const [g, setG] = useState(null);
  const [msg, setMsg] = useState(null);
  const [error, setError] = useState(null);
  const cargar = () => api("/glpi/estado").then(setG).catch(setError);
  useEffect(() => { cargar(); }, []);
  if (!g) return null;

  const accion = async (ruta, texto) => {
    setMsg(null); setError(null);
    try { const r = await api(ruta, { metodo: "POST" }); setMsg(texto(r)); cargar(); } catch (e) { setError(e); }
  };
  const ult = g.resultado_sincronizacion;
  return (
    <div className="panel">
      <h2>Integración con GLPI</h2>
      {!g.activo ? (
        <p className="tenue" style={{ margin: 0 }}>Desactivada. Se activa en Configuración → GLPI.</p>
      ) : (
        <>
          <p style={{ marginTop: 0 }}>
            Activa · sincroniza el estado de los tickets cada {g.sync_minutos} min.{" "}
            {g.ultima_sincronizacion
              ? <span className="tenue">Última: {fechaHora(g.ultima_sincronizacion)}{ult && ` (${ult.revisados} revisados, ${ult.cambios} cambios)`}</span>
              : <span className="tenue">Aún no se ha sincronizado desde que inició el servicio.</span>}
          </p>
          {g.error_sincronizacion && <div className="alerta error">Última sincronización con error: {g.error_sincronizacion}</div>}
          {msg && <div className="alerta ok">{msg}</div>}
          <MsgError e={error} />
          <div className="acciones">
            {puede("config.admin") && <button className="btn chico" onClick={() => accion("/glpi/probar", (r) => `Conexión correcta como «${r.usuario}» (entidad activa: ${r.entidad_activa}).`)}>Probar conexión</button>}
            <button className="btn chico" onClick={() => accion("/glpi/sincronizar", (r) => `Sincronización: ${r.resultado.revisados} tickets revisados, ${r.resultado.cambios} cambios.`)}>Sincronizar ahora</button>
          </div>
        </>
      )}
    </div>
  );
}

function ModalCorreos({ cliente, onCerrar, onGuardado }) {
  const [f, setF] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    api(`/clientes/${cliente.id}/correos`)
      .then((d) => setF({ ...d, para: d.para.join("\n"), cc: d.cc.join("\n"), dominios: d.dominios.join(", ") })).catch(setError);
  }, [cliente.id]);
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));
  const guardar = async () => {
    setError(null);
    try { await api(`/clientes/${cliente.id}/correos`, { metodo: "PUT", datos: { para: f.para, cc: f.cc, dominios: f.dominios } }); onGuardado(); }
    catch (e) { setError(e); }
  };
  return (
    <Modal titulo={`Correos de ${cliente.codigo} - ${cliente.nombre}`} onCerrar={onCerrar} pie={<>
      <button className="btn" onClick={onCerrar}>Cancelar</button>
      <button className="btn primario" disabled={!f} onClick={guardar}>Guardar</button>
    </>}>
      <MsgError e={error} />
      {f && (
        <div className="grid">
          <Campo etiqueta="Dominios del cliente" ayuda="solo se aceptan direcciones de estos dominios o de Wexler">
            <input value={f.dominios} onChange={set("dominios")} placeholder="cliente.gov.co" />
          </Campo>
          <Campo etiqueta="Para" ayuda="uno por línea, o pegue la lista de Outlook"><textarea rows={5} value={f.para} onChange={set("para")} /></Campo>
          <Campo etiqueta="CC" ayuda={`además de ${f.cc_fijo}, que va siempre`}><textarea rows={3} value={f.cc} onChange={set("cc")} /></Campo>
          <p className="tenue" style={{ margin: 0 }}>Copia oculta en todos los correos: {f.cco_fijo}.{f.por && ` Última modificación: ${f.por}, ${fechaHora(f.en)}.`}</p>
        </div>
      )}
    </Modal>
  );
}

function ModalLogo({ cliente, onCerrar, onCambio }) {
  const [c, setC] = useState(cliente);
  const [version, setVersion] = useState(0);
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const hacer = async (fn) => {
    setOcupado(true); setError(null);
    try { setC(await fn()); setVersion((v) => v + 1); onCambio(); } catch (e) { setError(e); }
    setOcupado(false);
  };
  return (
    <Modal titulo={`Logo de ${c.codigo} - ${c.nombre}`} onCerrar={onCerrar} pie={<>
      {c.tiene_logo && <button className="btn peligro" disabled={ocupado} onClick={() => hacer(() => api(`/clientes/${c.id}/logo`, { metodo: "DELETE" }))}>Quitar logo</button>}
      <button className="btn primario" onClick={onCerrar}>Cerrar</button>
    </>}>
      <MsgError e={error} />
      <div className={`logo-previa${c.logo_claro ? " oscura" : ""}`}>{c.tiene_logo ? <ImagenPrivada ruta={`/clientes/${c.id}/logo`} version={version} alt={`Logo de ${c.codigo}`} /> : <span className="tenue">Sin logo</span>}</div>
      <label className="btn" style={{ marginTop: 12 }}>{ocupado ? "Procesando…" : c.tiene_logo ? "Reemplazar logo" : "Cargar logo"}
        <input type="file" accept=".png,.jpg,.jpeg" hidden disabled={ocupado} onChange={(e) => { const a = e.target.files[0]; e.target.value = ""; if (a) hacer(() => subirImagen(`/clientes/${c.id}/logo`, a, "PUT")); }} /></label>
      <p className="tenue" style={{ margin: "10px 0 0" }}>PNG o JPG de hasta 5 MB; lo ideal es un PNG con fondo transparente. Se recortan los bordes vacíos. Aparece en la presentación.</p>
    </Modal>
  );
}

export default function Clientes() {
  const [lista, setLista] = useState([]);
  const [editar, setEditar] = useState(null);
  const [error, setError] = useState(null);
  const [correos, setCorreos] = useState(null);
  const [logo, setLogo] = useState(null);
  const [version, setVersion] = useState(0);
  const [confirmar, setConfirmar] = useState(null);  // { tipo, c }
  const ejecutar = async () => {
    const { tipo, c } = confirmar;
    if (tipo === "eliminar") await api(`/clientes/${c.id}`, { metodo: "DELETE" });
    else await api(`/clientes/${c.id}/estado`, { metodo: "PATCH", datos: { activo: !c.activo } });
    setConfirmar(null);
    cargar();
  };

  const cargar = () => api("/clientes").then(setLista).catch(setError);
  useEffect(() => { cargar(); }, []);

  const set = (k) => (e) => setEditar((x) => ({ ...x, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  const guardar = async () => {
    setError(null);
    const d = { ...editar };
    ["eps_contratados", "fuentes_licencia", "glpi_entidad_id"].forEach((k) => { d[k] = d[k] === "" || d[k] === null ? null : Number(d[k]); });
    d.dia_corte = Number(d.dia_corte);
    try {
      if (d.id) await api(`/clientes/${d.id}`, { metodo: "PUT", datos: d });
      else await api("/clientes", { metodo: "POST", datos: d });
      setEditar(null);
      cargar();
    } catch (e) { setError(e); }
  };

  const periodo = (d) => (Number(d) === 1 ? "Mes calendario" : `Del ${d} al ${d - 1} del mes siguiente`);

  return (
    <>
      <div className="cabecera">
        <div><h1>Clientes</h1><p>Servicios contratados, destinatarios de las alertas y datos usados para los informes y GLPI.</p></div>
        <button className="btn primario" onClick={() => { setError(null); setEditar({ ...NUEVO }); }}>+ Nuevo cliente</button>
      </div>
      <MsgError e={!editar && error} />
      <PanelGlpi />
      <div className="panel">
        <div className="tabla-scroll">
        <table className="tabla">
          <thead><tr><th>Logo</th><th>Código</th><th>Nombre</th><th>Servicios</th><th>Periodo del informe</th><th className="num">EPS contratados</th><th className="num">Entidad GLPI</th><th>Correos</th><th>Estado</th><th>Acciones</th></tr></thead>
          <tbody>
            {lista.map((c) => (
              <tr key={c.id} className={c.activo ? "" : "inactiva"}>
                <td><button className="logo-mini" title={c.tiene_logo ? "Ver o cambiar el logo" : "Cargar logo"} onClick={() => setLogo(c)}>
                  {c.tiene_logo ? <ImagenPrivada ruta={`/clientes/${c.id}/logo`} version={version} alt="" /> : "+ Logo"}</button></td>
                <td><b>{c.codigo}</b></td>
                <td>{c.nombre}</td>
                <td>{[c.servicio_soc && "SOC", c.servicio_noc && "NOC"].filter(Boolean).join(" + ") || "—"}</td>
                <td>{periodo(c.dia_corte)}</td>
                <td className="num">{num(c.eps_contratados)}</td>
                <td className="num">{c.glpi_entidad_id ?? <span className="tenue">sin asignar</span>}</td>
                <td><button className="btn chico" onClick={(e) => { e.stopPropagation(); setCorreos(c); }}>
                  {c.total_correos ? `${c.total_correos} destinatario${c.total_correos > 1 ? "s" : ""}` : "Configurar"}</button></td>
                <td>{c.activo ? "Habilitado" : <span className="badge etq">Deshabilitado</span>}</td>
                <td><AccionesFila activo={c.activo} uso={c.uso}
                  onEditar={() => { setError(null); setEditar({ ...NUEVO, ...c, eps_contratados: c.eps_contratados ?? "", fuentes_licencia: c.fuentes_licencia ?? "", glpi_entidad_id: c.glpi_entidad_id ?? "", sharepoint_carpeta: c.sharepoint_carpeta ?? "" }); }}
                  onEstado={() => setConfirmar({ tipo: "estado", c })} onEliminar={() => setConfirmar({ tipo: "eliminar", c })} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      {confirmar && (
        <Confirmar peligro={confirmar.tipo === "eliminar" || confirmar.c.activo} onCerrar={() => setConfirmar(null)} onAceptar={ejecutar}
                   titulo={`${confirmar.tipo === "eliminar" ? "Eliminar" : confirmar.c.activo ? "Deshabilitar" : "Habilitar"} ${confirmar.c.codigo}`}
                   boton={confirmar.tipo === "eliminar" ? "Eliminar" : confirmar.c.activo ? "Deshabilitar" : "Habilitar"}>
          <p style={{ margin: 0 }}>{confirmar.tipo === "eliminar" ? "Se borra el cliente con su lista de correos y no se puede recuperar. Si sigue en el Excel, una importación lo vuelve a crear."
            : confirmar.c.activo ? "No se podrán registrar casos nuevos ni generar correos para este cliente. Sus casos e informes se conservan y los casos abiertos se pueden seguir gestionando."
              : "Volverá a aparecer al registrar casos y crear informes."}</p>
        </Confirmar>
      )}
      {logo && <ModalLogo cliente={logo} onCerrar={() => setLogo(null)} onCambio={() => { cargar(); setVersion((v) => v + 1); }} />}
      {correos && <ModalCorreos cliente={correos} onCerrar={() => setCorreos(null)} onGuardado={() => { setCorreos(null); cargar(); }} />}
      {editar && (
        <Modal titulo={editar.id ? `Editar ${editar.codigo}` : "Nuevo cliente"} onCerrar={() => setEditar(null)} pie={<>
          <button className="btn" onClick={() => setEditar(null)}>Cancelar</button>
          <button className="btn primario" onClick={guardar}>Guardar</button>
        </>}>
          <MsgError e={error} />
          <div className="grid g4">
            <Campo etiqueta="Código"><input value={editar.codigo} onChange={set("codigo")} /></Campo>
            <Campo etiqueta="Nombre" className="span-todo" ><input value={editar.nombre} onChange={set("nombre")} /></Campo>
            <label className="check"><input type="checkbox" checked={editar.servicio_soc} onChange={set("servicio_soc")} /> Servicio SOC</label>
            <label className="check"><input type="checkbox" checked={editar.servicio_noc} onChange={set("servicio_noc")} /> Servicio NOC</label>
            <label className="check span2"><input type="checkbox" checked={editar.activo} onChange={set("activo")} /> Cliente activo</label>
            <Campo etiqueta="Día de corte" ayuda={periodo(editar.dia_corte || 1)}><input type="number" min={1} max={28} value={editar.dia_corte} onChange={set("dia_corte")} /></Campo>
            <Campo etiqueta="EPS contratados"><input type="number" value={editar.eps_contratados} onChange={set("eps_contratados")} /></Campo>
            <Campo etiqueta="Fuentes por licencia"><input type="number" value={editar.fuentes_licencia} onChange={set("fuentes_licencia")} /></Campo>
            <Campo etiqueta="ID de entidad en GLPI"><input type="number" value={editar.glpi_entidad_id} onChange={set("glpi_entidad_id")} /></Campo>
            <Campo etiqueta="Carpeta en SharePoint" ayuda="vacío = el código"><input value={editar.sharepoint_carpeta || ""} onChange={set("sharepoint_carpeta")} maxLength={80} placeholder={editar.codigo || "código"} /></Campo>
          </div>
        </Modal>
      )}
    </>
  );
}
