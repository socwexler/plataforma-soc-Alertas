import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { api, token } from "../api";
import { useAuth } from "../auth";
import Adjuntos, { peso } from "../components/Adjuntos";
import { Confirmar, Crit, Dato, Estado, MsgError, Revision } from "../components/Ui";
import { copiarHtml, copiarTexto, duracion, ESTADOS, ESTADOS_GLPI, fechaHora, infoGlpi } from "../util";

const CAMPOS_IN = ["servicio", "cliente_id", "caso_uso_id", "alerta", "criticidad", "tecnica", "tactica_id", "resumen_ejecutivo",
  "analisis", "acciones_recomendadas", "geolocalizacion", "reporting_ip", "log_evento", "fecha_evento", "fecha_reporte",
  "estado", "acciones_cliente", "glpi_ticket_id"];

export default function CasoDetalle() {
  const { id } = useParams();
  const { state } = useLocation();
  const { usuario, puede } = useAuth();
  const [c, setC] = useState(null);
  const [notif, setNotif] = useState(null);
  const [tab, setTab] = useState("vista");
  const [comentario, setComentario] = useState("");
  const [tipoCom, setTipoCom] = useState("comentario");
  const [msg, setMsg] = useState(state?.creado ? "Caso registrado correctamente." : null);
  const [error, setError] = useState(state?.errorArchivos ? new Error(state.errorArchivos) : null);
  const [glpi, setGlpi] = useState({ activo: false });
  const [publicar, setPublicar] = useState(false);
  const [obs, setObs] = useState("");
  const [correo, setCorreo] = useState(null);
  const [confirmo, setConfirmo] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [anular, setAnular] = useState(false);
  const [motivo, setMotivo] = useState("");
  useEffect(() => { infoGlpi(api).then(setGlpi); }, []);

  const cargarNotif = useCallback(() => api(`/casos/${id}/notificacion`).then(setNotif).catch(setError), [id]);
  const cargar = useCallback(() => {
    api(`/casos/${id}`).then(setC).catch(setError);
    cargarNotif();
  }, [id, cargarNotif]);
  useEffect(cargar, [cargar]);

  if (!c) return error ? <MsgError e={error} /> : <div className="vacio">Cargando…</div>;

  const puedeComentar = puede("casos.crear") && (c.analista?.id === usuario.id || puede("casos.revisar"));
  const puedeEditar = puedeComentar && !c.anulado_en;
  const anularORestaurar = async () => {
    const x = await api(`/casos/${id}/${c.anulado_en ? "restaurar" : "anular"}`, { metodo: "POST", datos: { motivo } });
    setC(x); setAnular(false); setMotivo(""); setTab("vista"); setError(null);
    setMsg(x.anulado_en ? "Caso anulado: ya no cuenta en el tablero ni en los informes." : "Caso restaurado: vuelve a contar en el tablero y los informes.");
    window.dispatchEvent(new Event("revision-cambio"));
  };
  const puedeRevisar = puede("casos.revisar") && !c.anulado_en && c.revision && c.analista?.id !== usuario.id;
  const revisar = async (resultado) => {
    setOcupado(true); setError(null); setMsg(null);
    try {
      setC(await api(`/casos/${id}/revision`, { metodo: "POST", datos: { resultado, observacion: obs } }));
      setObs("");
      setMsg(resultado === "REVISADO" ? "Caso marcado como revisado." : "Caso devuelto al analista.");
      window.dispatchEvent(new Event("revision-cambio"));
    } catch (e) { setError(e); }
    setOcupado(false);
  };

  const cambiarEstado = async (estado) => {
    const datos = Object.fromEntries(CAMPOS_IN.map((k) => [k, k === "cliente_id" ? c.cliente.id : c[k]]));
    datos.estado = estado;
    try { await api(`/casos/${id}`, { metodo: "PUT", datos }); setMsg(`Estado actualizado a: ${ESTADOS[estado]}`); cargar(); }
    catch (e) { setError(e); }
  };

  const comentar = async (e) => {
    e.preventDefault();
    try {
      const s = await api(`/casos/${id}/seguimientos`, { metodo: "POST", datos: { comentario, tipo: tipoCom, publicar_glpi: publicar } });
      if (s.glpi_error) setError(new Error(`El comentario se guardó, pero no se publicó en GLPI: ${s.glpi_error}`));
      setComentario("");
      setPublicar(false);
      cargar();
    } catch (err) { setError(err); }
  };

  const verCorreo = async () => {
    setTab("correo"); setConfirmo(false); setError(null);
    try { setCorreo(await api(`/casos/${id}/correo`)); } catch (e) { setError(e); }
  };
  const abrirBorrador = async () => {
    setOcupado(true); setError(null); setMsg(null);
    try {
      const r = await fetch(`/api/casos/${id}/correo.eml?confirmar=${confirmo}`, { method: "POST", headers: { Authorization: `Bearer ${token.get()}` } });
      if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail || `Error ${r.status}`);
      const url = URL.createObjectURL(await r.blob());
      const a = document.createElement("a");
      a.href = url; a.download = `${c.numero}_${c.cliente.codigo}.eml`; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      setMsg("Borrador descargado. Ábralo con Outlook, revise destinatarios, evidencias y adjuntos, y envíelo.");
      cargar(); verCorreo();
    } catch (e) { setError(e); }
    setOcupado(false);
  };

  const accionGlpi = async (ruta, ok) => {
    setOcupado(true); setError(null);
    try { setC(await api(`/casos/${id}/${ruta}`, { metodo: "POST" })); setMsg(ok); }
    catch (e) { setError(e); }
    setOcupado(false);
  };

  const copiar = async (que) => {
    const ok = que === "html" ? await copiarHtml(notif.html, notif.texto)
      : que === "asunto" ? await copiarTexto(notif.asunto_correo) : await copiarTexto(notif.texto);
    setMsg(ok ? (que === "html" ? "Notificación copiada. Péguela en el correo (Outlook conserva el formato)." : "Copiado al portapapeles.") : null);
    if (!ok) setError(new Error("No se pudo copiar automáticamente; seleccione el texto y cópielo manualmente."));
  };

  return (
    <>
      <div className="cabecera">
        <div>
          <h1 className={c.anulado_en ? "tachado" : ""}>{c.numero} · {c.alerta}</h1>
          <p>{c.cliente.codigo} - {c.cliente.nombre} · {c.servicio} · registrado por {c.analista?.nombre || "—"}</p>
        </div>
        <div className="acciones">
          <Link className="btn" to="/casos">Volver</Link>
          {puedeEditar && <Link className="btn primario" to={`/casos/${id}/editar`}>Editar</Link>}
          {puede("casos.anular") && <button className={`btn ${c.anulado_en ? "" : "peligro"}`} onClick={() => setAnular(true)}>{c.anulado_en ? "Restaurar" : "Anular"}</button>}
        </div>
      </div>
      {c.anulado_en && <div className="alerta aviso"><b>Caso anulado</b> por {c.anulado_por}, {fechaHora(c.anulado_en)}. Motivo: {c.anulado_motivo}<br />No cuenta en el tablero ni en los informes y no se puede modificar.</div>}
      {anular && (
        <Confirmar titulo={`${c.anulado_en ? "Restaurar" : "Anular"} ${c.numero}`} boton={c.anulado_en ? "Restaurar" : "Anular caso"} peligro={!c.anulado_en} listo={motivo.trim().length >= 10}
                   onCerrar={() => { setAnular(false); setMotivo(""); }} onAceptar={anularORestaurar}>
          <p style={{ marginTop: 0 }}>{c.anulado_en ? "Vuelve a contar en el tablero y en los informes en borrador."
            : "Conserva su número e historial, pero deja de contar en el tablero y en los informes en borrador. Los informes finales no cambian. Se puede restaurar."}</p>
          {!c.anulado_en && c.seguimientos.some((s) => s.tipo === "correo") && <div className="alerta aviso">Ya se generó un borrador de correo de este caso. Si se envió, avise al cliente: anularlo aquí no retira el correo.</div>}
          {!c.anulado_en && c.glpi_ticket_id && <div className="alerta aviso">El ticket GLPI {c.glpi_ticket_id} no se modifica: ciérrelo en GLPI si corresponde.</div>}
          <label className="campo"><span>Motivo <span className="ayuda">· mínimo 10 caracteres</span></span>
            <textarea rows={3} maxLength={500} value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Ej.: registrado por error, duplicado de WX…" /></label>
        </Confirmar>
      )}
      {msg && <div className="alerta ok">{msg}</div>}
      <MsgError e={error} />

      <div className="grid detalle-caso">
        <div>
          <div className="panel">
            <div className="grid g-auto">
              <Dato t="Criticidad"><Crit v={c.criticidad} /></Dato>
              <Dato t="Estado">{c.anulado_en ? <span className="badge est-anulado">Anulado</span> : <Estado v={c.estado} />}</Dato>
              <Dato t="Táctica">{c.tactica ? `${c.tactica.nombre} (${c.tactica.id})` : c.tactica_original}</Dato>
              <Dato t="Técnica">{c.tecnica}</Dato>
              <Dato t="Evento en SIEM">{fechaHora(c.fecha_evento)}</Dato>
              <Dato t="Reporte al cliente">{fechaHora(c.fecha_reporte)}</Dato>
              <Dato t="Tiempo de reporte">{duracion(c.minutos_respuesta)}</Dato>
              <Dato t="Ticket GLPI">
                {c.glpi_ticket_id
                  ? <>{glpi.url_web ? <a href={`${glpi.url_web}${c.glpi_ticket_id}`} target="_blank" rel="noreferrer">{c.glpi_ticket_id}</a> : c.glpi_ticket_id}
                      {c.glpi_estado && <div className="tenue">{ESTADOS_GLPI[c.glpi_estado]}</div>}</>
                  : null}
              </Dato>
              <Dato t="Reporting IP">{c.reporting_ip}</Dato>
              <Dato t="Geolocalización">{c.geolocalizacion}</Dato>
              <Dato t="Caso de uso">{!c.caso_uso_id ? "No vinculado" : puede("kb.ver") ? <Link to={`/conocimiento?id=${c.caso_uso_id}`}>Ver en base de conocimiento</Link> : "Vinculado"}</Dato>
              <Dato t="Origen">{c.origen === "migracion" ? "Bitácora Excel" : "Plataforma"}</Dato>
            </div>
          </div>

          <Adjuntos caso={c} editable={puedeEditar} onError={setError}
                    onCambio={(x) => { setC(x); cargarNotif(); window.dispatchEvent(new Event("revision-cambio")); if (tab === "correo") verCorreo(); }} />

          <div className="panel">
            <div className="tabs">
              <button className={tab === "vista" ? "activo" : ""} onClick={() => setTab("vista")}>Notificación</button>
              {puedeEditar && <button className={tab === "correo" ? "activo" : ""} onClick={verCorreo}>Correo al cliente</button>}
              <button className={tab === "detalle" ? "activo" : ""} onClick={() => setTab("detalle")}>Detalle técnico</button>
            </div>
            {tab === "vista" && notif && (
              <>
                {!c.anulado_en && <div className="acciones" style={{ marginBottom: 10 }}>
                  <button className="btn primario chico" onClick={() => copiar("html")}>Copiar para correo</button>
                  <button className="btn chico" onClick={() => copiar("asunto")}>Copiar asunto</button>
                  <button className="btn chico" onClick={() => copiar("texto")}>Copiar texto plano</button>
                  <span className="tenue">Asunto: {notif.asunto_correo}</span>
                </div>}
                {/* HTML generado por el servidor con todo el contenido escapado */}
                <div className="vista-correo" dangerouslySetInnerHTML={{ __html: notif.html }} />
              </>
            )}
            {tab === "correo" && correo && (
              <>
                <div className="panel" style={{ marginBottom: 12 }}>
                  <div><b>Cliente:</b> {correo.cliente}</div>
                  <div><b>Para:</b> {correo.para.join("; ") || "—"}</div>
                  <div><b>CC:</b> {correo.cc.join("; ") || "—"}</div>
                  <div><b>CCO:</b> {correo.cco.join("; ") || "—"}</div>
                  <div><b>Asunto:</b> {correo.asunto}</div>
                  <div><b>Archivos:</b> {correo.archivos.map((x) => `${x.nombre} (${x.tipo === "EVIDENCIA" ? "evidencia" : "adjunto"}, ${peso(x.tamano)})`).join("; ") || "ninguno"}</div>
                </div>
                {correo.bloqueos.map((b) => <div key={b} className="alerta error">{b}</div>)}
                {correo.advertencias.length > 0 && (
                  <div className="alerta aviso">
                    {correo.advertencias.map((a) => <div key={a}>• {a}</div>)}
                    <label className="check" style={{ marginTop: 8 }}><input type="checkbox" checked={confirmo} onChange={(e) => setConfirmo(e.target.checked)} /> Lo revisé y deseo continuar</label>
                  </div>
                )}
                <div className="acciones" style={{ marginBottom: 10 }}>
                  <button className="btn primario chico" disabled={ocupado || correo.bloqueos.length > 0 || (correo.advertencias.length > 0 && !confirmo)} onClick={abrirBorrador}>Generar borrador de Outlook</button>
                  <span className="tenue">No se envía nada: usted lo revisa y lo envía desde Outlook.</span>
                </div>
                <div className="vista-correo" dangerouslySetInnerHTML={{ __html: correo.html }} />
              </>
            )}
            {tab === "detalle" && (
              <>
                <Dato t="Resumen ejecutivo"><div className="pre">{c.resumen_ejecutivo}</div></Dato>
                <Dato t="Análisis de seguridad"><div className="pre">{c.analisis}</div></Dato>
                <Dato t="Acciones recomendadas"><div className="pre">{c.acciones_recomendadas}</div></Dato>
                <Dato t="Log del evento">{c.log_evento && <pre className="log mono pre">{c.log_evento}</pre>}</Dato>
                <Dato t="Acciones ejecutadas por el cliente"><div className="pre">{c.acciones_cliente}</div></Dato>
              </>
            )}
          </div>
        </div>

        <div>
          {c.revision && (
            <div className="panel">
              <h2>Revisión</h2>
              <p style={{ marginTop: 0 }}><Revision v={c.revision} />
                {c.revisado_por && <span className="tenue"> · {c.revisado_por}, {fechaHora(c.revisado_en)}</span>}</p>
              {c.revision === "OBSERVADO" && c.analista?.id === usuario.id && (
                <div className="alerta aviso">Este caso fue devuelto. La observación está en el seguimiento; al corregirlo vuelve a quedar por revisar.</div>
              )}
              {puedeRevisar && (
                <div className="grid">
                  <textarea rows={2} value={obs} onChange={(e) => setObs(e.target.value)} placeholder="Observación (obligatoria para devolver)" />
                  <div className="acciones">
                    {c.revision !== "REVISADO" && <button className="btn primario chico" disabled={ocupado} onClick={() => revisar("REVISADO")}>Marcar revisado</button>}
                    <button className="btn chico" disabled={ocupado || obs.trim().length < 5} onClick={() => revisar("OBSERVADO")}>Devolver al analista</button>
                  </div>
                </div>
              )}
            </div>
          )}
          {glpi.activo && (
            <div className="panel">
              <h2>GLPI</h2>
              {c.glpi_error && <div className="alerta error">{c.glpi_error}</div>}
              {c.glpi_ticket_id ? (
                <>
                  <p style={{ marginTop: 0 }}>Ticket <b>{c.glpi_ticket_id}</b> · {ESTADOS_GLPI[c.glpi_estado] || "estado desconocido"}
                    <br /><span className="tenue">Actualizado {fechaHora(c.glpi_sincronizado_en)}</span></p>
                  <div className="acciones">
                    {glpi.url_web && <a className="btn chico" href={`${glpi.url_web}${c.glpi_ticket_id}`} target="_blank" rel="noreferrer">Abrir en GLPI</a>}
                    {puedeEditar && <button className="btn chico" disabled={ocupado} onClick={() => accionGlpi("glpi/sincronizar", "Estado del ticket actualizado.")}>Actualizar estado</button>}
                  </div>
                </>
              ) : (
                <>
                  <p className="tenue" style={{ marginTop: 0 }}>Este caso aún no tiene ticket en GLPI.</p>
                  {puedeEditar && <button className="btn primario chico" disabled={ocupado}
                    onClick={() => accionGlpi("glpi", "Ticket creado en GLPI.")}>{c.glpi_error ? "Reintentar crear ticket" : "Crear ticket en GLPI"}</button>}
                </>
              )}
            </div>
          )}
          {puedeEditar && (
            <div className="panel">
              <h2>Estado</h2>
              <div className="acciones">
                {Object.entries(ESTADOS).filter(([k]) => k !== c.estado).map(([k, v]) => (
                  <button key={k} className="btn chico" onClick={() => cambiarEstado(k)}>Marcar: {v}</button>
                ))}
              </div>
            </div>
          )}
          <div className="panel">
            <h2>Seguimiento</h2>
            {c.seguimientos.length === 0 && <p className="tenue">Sin comentarios.</p>}
            {c.seguimientos.map((s) => (
              <div key={s.id} className={`seguimiento tipo-${s.tipo}`}>
                <div className="meta">{s.autor_nombre} · {fechaHora(s.creado_en)}{s.tipo === "cliente" && " · respuesta del cliente"}{s.tipo === "glpi" && " · GLPI"}{s.tipo === "revision" && " · revisión"}{s.tipo === "correo" && " · correo"}{s.tipo === "adjunto" && " · archivos"}{s.tipo === "anulacion" && " · anulación"}</div>
                <div className="pre">{s.comentario}</div>
              </div>
            ))}
            {puedeComentar && <form onSubmit={comentar} className="grid" style={{ marginTop: 12 }}>
              <textarea rows={3} value={comentario} onChange={(e) => setComentario(e.target.value)} placeholder="Agregar comentario o respuesta del cliente…" required />
              <div className="acciones" style={{ justifyContent: "space-between" }}>
                <select value={tipoCom} onChange={(e) => setTipoCom(e.target.value)} style={{ width: "auto" }}>
                  <option value="comentario">Comentario interno</option>
                  <option value="cliente">Respuesta del cliente</option>
                </select>
                {glpi.activo && c.glpi_ticket_id && !c.anulado_en && (
                  <label className="check"><input type="checkbox" checked={publicar} onChange={(e) => setPublicar(e.target.checked)} /> Publicar en GLPI</label>
                )}
                <button className="btn primario chico">Agregar</button>
              </div>
            </form>}
          </div>
        </div>
      </div>
    </>
  );
}
