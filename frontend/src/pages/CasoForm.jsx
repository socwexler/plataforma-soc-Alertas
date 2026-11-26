import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { imagenesPegadas, peso, subirAdjuntos, TIPOS } from "../components/Adjuntos";
import { Campo, Combo, Crit, MsgError } from "../components/Ui";
import { useAuth } from "../auth";
import { aInputLocal, clave, CRITICIDADES, deInputLocal, duracion, ESTADOS, fechaHora, infoGlpi } from "../util";

const VACIO = {
  servicio: "SOC", cliente_id: "", caso_uso_id: null, alerta: "", criticidad: "", tecnica: "", tactica_id: "",
  resumen_ejecutivo: "", analisis: "", acciones_recomendadas: "", geolocalizacion: "", reporting_ip: "",
  log_evento: "", fecha_evento: "", fecha_reporte: "", estado: "SIN_RETRO", acciones_cliente: "", glpi_ticket_id: "",
};

const PISTA_ANALISIS = `DETALLES DEL EVENTO

USUARIO:
IP ORIGEN:
IP DESTINO:
ACCIÓN:

Se evidenció …`;

export default function CasoForm() {
  const { id } = useParams();
  const editando = Boolean(id);
  const [sp] = useSearchParams();
  const alertaId = editando ? null : sp.get("alerta");
  const [alerta, setAlerta] = useState(null);   // ticket del SIEM que se está reportando
  const nav = useNavigate();
  const [f, setF] = useState(VACIO);
  const [numero, setNumero] = useState(null);
  const [clientes, setClientes] = useState([]);
  const [tacticas, setTacticas] = useState([]);
  const [opciones, setOpciones] = useState([]);
  const [alertaLibre, setAlertaLibre] = useState(false);
  const [similares, setSimilares] = useState([]);
  const [error, setError] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const [glpi, setGlpi] = useState({ activo: false });
  const [crearTicket, setCrearTicket] = useState(false);
  const [original, setOriginal] = useState(null);
  const { puede, usuario } = useAuth();
  const [reporteOriginal, setReporteOriginal] = useState(null);   // {texto del campo, ISO guardado}
  const [archivos, setArchivos] = useState([]);  // [{archivo, tipo}] se suben después de crear el caso
  const agregar = (lista, tipo) => {
    const nuevos = [...lista].map((archivo) => ({ archivo, tipo }));  // copia: al limpiar el <input> la lista se vacía
    setArchivos((x) => [...x, ...nuevos]);
  };

  useEffect(() => { infoGlpi(api).then((g) => { setGlpi(g); setCrearTicket(!!g.activo && !!g.crear_por_defecto); }); }, []);

  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));

  useEffect(() => {
    Promise.all([api("/clientes", { params: { solo_activos: editando ? "" : true } }), api("/tacticas")])
      .then(([c, t]) => { setClientes(c); setTacticas(t); }).catch(setError);
    if (editando) {
      api(`/casos/${id}`).then((c) => {
        const x = { ...VACIO };
        Object.keys(VACIO).forEach((k) => { x[k] = c[k] ?? VACIO[k]; });
        x.fecha_evento = aInputLocal(c.fecha_evento);
        x.fecha_reporte = aInputLocal(c.fecha_reporte);
        setReporteOriginal({ texto: x.fecha_reporte, iso: c.fecha_reporte });
        x.glpi_ticket_id = c.glpi_ticket_id ?? "";
        setF(x);
        if (c.anulado_en) { nav(`/casos/${id}`, { replace: true }); return; }
        setNumero(c.numero);
        setOriginal({ cliente_id: c.cliente_id, caso_uso_id: c.caso_uso_id, alerta: c.alerta });
        setAlertaLibre(!c.caso_uso_id);
      }).catch(setError);
    } else if (alertaId) {
      // Reportar una alerta de GLPI: se toma (los demás ven quién la tiene) y se llenan los datos del ticket
      (async () => {
        let a = await api(`/alertas/${alertaId}`);
        if (a.estado === "POR_REPORTAR") a = { ...a, ...(await api(`/alertas/${alertaId}/tomar`, { metodo: "POST" })) };
        if (a.estado === "REPORTADA") { nav(`/casos/${a.caso_id}`, { replace: true }); return; }
        if (a.estado === "CERRADA_GLPI") throw new Error(`El ticket ${a.glpi_ticket_id} se cerró en GLPI: ya no está por reportar.`);
        setAlerta(a);
        setAlertaLibre(true);
        setF((x) => ({ ...x, servicio: "SOC", cliente_id: a.cliente_id ?? "", alerta: a.titulo, criticidad: a.criticidad || "",
          fecha_evento: aInputLocal(a.fecha_alerta), glpi_ticket_id: a.glpi_ticket_id }));
      })().catch(setError);
    } else {
      setF((x) => ({ ...x, fecha_evento: aInputLocal(new Date()) }));
    }
  }, [id, editando, alertaId]);

  useEffect(() => {
    api("/casos-uso/opciones", { params: { servicio: f.servicio } }).then(setOpciones).catch(setError);
  }, [f.servicio]);

  // Aviso de posibles duplicados (mismo cliente y alerta en las últimas 24 h)
  useEffect(() => {
    if (editando || !f.cliente_id || f.alerta.trim().length < 4) { setSimilares([]); return; }
    const t = setTimeout(() => {
      api("/casos/similares", { params: { cliente_id: f.cliente_id, alerta: f.alerta } }).then(setSimilares).catch(() => {});
    }, 400);
    return () => clearTimeout(t);
  }, [f.cliente_id, f.alerta, editando]);

  const elegirCasoUso = async (o) => {
    const cu = await api(`/casos-uso/${o.id}`);
    const tieneTexto = f.resumen_ejecutivo || f.acciones_recomendadas;
    const reemplazar = !tieneTexto || window.confirm("¿Reemplazar el resumen ejecutivo y las acciones recomendadas con la plantilla del caso de uso?");
    setF((x) => ({
      ...x,
      caso_uso_id: cu.id,
      alerta: cu.nombre,
      criticidad: cu.criticidad || x.criticidad,
      tecnica: cu.tecnica || x.tecnica,
      tactica_id: cu.tactica_id || x.tactica_id,
      ...(reemplazar ? {
        resumen_ejecutivo: cu.resumen_ejecutivo || x.resumen_ejecutivo,
        acciones_recomendadas: cu.acciones_recomendadas || x.acciones_recomendadas,
        analisis: x.analisis || cu.guia_analisis || "",
      } : {}),
    }));
  };

  // Si el título de la alerta es un caso de uso de la base de conocimiento, se propone con su plantilla
  const [propuesto, setPropuesto] = useState(false);
  useEffect(() => {
    if (!alerta || propuesto || !opciones.length) return;
    setPropuesto(true);
    const o = opciones.find((x) => clave(x.nombre) === clave(alerta.titulo));
    if (o) { setAlertaLibre(false); elegirCasoUso(o); }
  }, [alerta, opciones, propuesto]);   // eslint-disable-line react-hooks/exhaustive-deps

  // Al editar se conserva el cliente o caso de uso del caso aunque ya esté deshabilitado
  const clientesServicio = clientes.filter((c) => (c.activo || c.id === original?.cliente_id) && (f.servicio === "SOC" ? c.servicio_soc : c.servicio_noc));
  const clienteSel = clientes.find((c) => String(c.id) === String(f.cliente_id));

  const guardar = async (e) => {
    e.preventDefault();
    setError(null);
    if (!alertaLibre && !f.caso_uso_id) {
      setError(new Error("Seleccione el caso de uso o marque que la alerta no está en la base de conocimiento."));
      return;
    }
    setGuardando(true);
    const datos = {
      ...f,
      cliente_id: Number(f.cliente_id),
      caso_uso_id: alertaLibre ? null : f.caso_uso_id,
      tactica_id: f.tactica_id || null,
      fecha_evento: deInputLocal(f.fecha_evento),
      // solo se envía si un revisor la corrigió; al crear la pone el servidor
      fecha_reporte: editando && reporteOriginal && f.fecha_reporte !== reporteOriginal.texto ? deInputLocal(f.fecha_reporte) : null,
      glpi_ticket_id: f.glpi_ticket_id ? Number(f.glpi_ticket_id) : null,
    };
    Object.keys(datos).forEach((k) => { if (datos[k] === "") datos[k] = null; });
    try {
      const r = editando
        ? await api(`/casos/${id}`, { metodo: "PUT", datos })
        : await api("/casos", { metodo: "POST", datos, params: alerta ? { alerta_id: alerta.id } : { crear_ticket: glpi.activo && crearTicket } });
      // El caso ya quedó guardado: si un archivo falla, se informa en el detalle y se puede volver a subir
      const fallas = [];
      for (const x of archivos) {
        try { await subirAdjuntos(r.id, [x.archivo], x.tipo); } catch (err) { fallas.push(err.message); }
      }
      nav(`/casos/${r.id}`, { state: { creado: !editando, errorArchivos: fallas.length ? `El caso se guardó, pero no estos archivos: ${fallas.join("; ")}` : null } });
    } catch (err) {
      setError(err);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
    setGuardando(false);
  };

  return (
    <form onSubmit={guardar}>
      <div className="cabecera">
        <div>
          <h1>{editando ? `Editar caso ${numero || ""}` : alerta ? `Reportar alerta · ticket GLPI ${alerta.glpi_ticket_id}` : "Registrar caso"}</h1>
          <p>{editando ? "Los cambios de estado quedan en el historial del caso." : "El número de reporte se asigna automáticamente al guardar."}</p>
        </div>
        <div className="acciones">
          <Link className="btn" to={editando ? `/casos/${id}` : alerta ? "/alertas" : "/casos"}>Cancelar</Link>
          <button className="btn primario" disabled={guardando}>{guardando ? "Guardando…" : "Guardar caso"}</button>
        </div>
      </div>
      <MsgError e={error} />

      {alerta && (
        <div className="panel ficha-alerta">
          <h2>Alerta del SIEM en GLPI</h2>
          <p style={{ marginTop: -4 }}>
            <b>Ticket {alerta.glpi_ticket_id}</b> · llegó a GLPI el {fechaHora(alerta.fecha_alerta)} · lleva {duracion(alerta.minutos)}
            {" "}(SLA de {alerta.criticidad || "Media"}: {duracion(alerta.sla_minutos)}).
            {" "}El caso queda con este ticket: no se crea otro en GLPI.
          </p>
          {alerta.estado === "EN_GESTION" && alerta.analista && alerta.analista.id !== usuario.id && (
            <div className="alerta aviso">La está gestionando {alerta.analista.nombre}{puede("casos.revisar") ? "; como revisor puede reportarla." : ": solo quien la tomó o un revisor pueden reportarla."}</div>
          )}
          {!alerta.cliente_id && <div className="alerta aviso">La entidad de GLPI de este ticket ({alerta.glpi_entidad_id ?? "sin dato"}) no está asignada a ningún cliente: elija el cliente abajo.</div>}
          <pre className="contenido-ticket">{alerta.contenido || "El ticket no tiene descripción."}</pre>
          {alerta.contenido && (
            <div className="acciones" style={{ marginTop: 8 }}>
              <button type="button" className="btn chico" onClick={() => setF((x) => ({ ...x, log_evento: alerta.contenido }))}>Usar como log del evento</button>
              <span className="tenue">La hora del evento se llenó con la llegada a GLPI; corríjala con la del SIEM si la trae el correo.</span>
            </div>
          )}
        </div>
      )}

      <div className="panel">
        <h2>1. Cliente y alerta</h2>
        <div className="grid g4">
          <Campo etiqueta="Servicio">
            <select value={f.servicio} disabled={editando}
                    onChange={(e) => setF((x) => ({ ...x, servicio: e.target.value, cliente_id: "", caso_uso_id: null }))}>
              <option>SOC</option><option>NOC</option>
            </select>
          </Campo>
          <Campo etiqueta="Cliente" className="span2">
            <select value={f.cliente_id} onChange={set("cliente_id")} required>
              <option value="">Seleccione…</option>
              {clientesServicio.map((c) => <option key={c.id} value={c.id}>{c.codigo} - {c.nombre}</option>)}
            </select>
          </Campo>
          <Campo etiqueta="Criticidad">
            <select value={f.criticidad} onChange={set("criticidad")} required>
              <option value="">Seleccione…</option>
              {CRITICIDADES.map((c) => <option key={c}>{c}</option>)}
            </select>
          </Campo>

          <div className="span-todo">
            {!alertaLibre ? (
              <Campo etiqueta="Caso de uso (alerta detectada)" ayuda="escriba para buscar; los más usados aparecen primero">
                <Combo
                  opciones={original?.caso_uso_id && !opciones.some((o) => o.id === original.caso_uso_id)
                    ? [...opciones, { id: original.caso_uso_id, nombre: original.alerta }] : opciones}
                  valor={f.caso_uso_id}
                  onCambio={elegirCasoUso}
                  placeholder="Ej.: fuerza bruta VPN, conexión entrante maliciosa, descarga masiva O365…"
                  render={(o) => (<><span>{o.nombre}</span><span className="acciones">{o.tiene_plantilla && <small>plantilla</small>}<Crit v={o.criticidad} /></span></>)}
                />
              </Campo>
            ) : (
              <Campo etiqueta="Alerta detectada" ayuda="texto libre">
                <input value={f.alerta} onChange={set("alerta")} required maxLength={300} />
              </Campo>
            )}
            <label className="check" style={{ marginTop: 8 }}>
              <input type="checkbox" checked={alertaLibre} onChange={(e) => setAlertaLibre(e.target.checked)} />
              La alerta no está en la base de conocimiento (escribirla manualmente)
            </label>
          </div>

          {similares.length > 0 && (
            <div className="alerta aviso span-todo" style={{ marginBottom: 0 }}>
              <b>Posible duplicado:</b> este cliente ya tiene {similares.length} caso(s) con esta alerta en las últimas 24 h:{" "}
              {similares.map((s, i) => (
                <span key={s.id}>{i > 0 && ", "}<Link to={`/casos/${s.id}`} target="_blank">{s.numero}</Link> ({fechaHora(s.fecha_evento)})</span>
              ))}
            </div>
          )}

          <Campo etiqueta="Técnica" className="span2"><input value={f.tecnica || ""} onChange={set("tecnica")} /></Campo>
          <Campo etiqueta="Táctica (MITRE ATT&CK)" className="span2">
            <select value={f.tactica_id || ""} onChange={set("tactica_id")}>
              <option value="">Sin táctica</option>
              {tacticas.map((t) => <option key={t.id} value={t.id}>{t.nombre} ({t.id})</option>)}
            </select>
          </Campo>
        </div>
      </div>

      <div className="panel">
        <h2>2. Evento</h2>
        <div className="grid g4">
          <Campo etiqueta="Fecha y hora del evento en el SIEM" ayuda="hora de Colombia">
            <input type="datetime-local" value={f.fecha_evento} onChange={set("fecha_evento")} required />
          </Campo>
          {editando && puede("casos.revisar") ? (
            <Campo etiqueta="Hora de reporte al cliente" ayuda="solo para corregir; queda en el seguimiento">
              <input type="datetime-local" value={f.fecha_reporte} onChange={set("fecha_reporte")} />
            </Campo>
          ) : (
            <Campo etiqueta="Hora de reporte al cliente" ayuda="automática">
              <input value={editando ? fechaHora(reporteOriginal?.iso) : "Se registra al guardar"} disabled title="Hora de Colombia en que se guarda el caso" />
            </Campo>
          )}
          <Campo etiqueta="Reporting IP / fuente"><input value={f.reporting_ip || ""} onChange={set("reporting_ip")} placeholder="172.20.0.10" /></Campo>
          <Campo etiqueta="Geolocalización"><input value={f.geolocalizacion || ""} onChange={set("geolocalizacion")} placeholder="N/A, Colombia, Estados Unidos…" /></Campo>
          <Campo etiqueta="Análisis de seguridad" className="span-todo">
            <textarea rows={9} value={f.analisis || ""} onChange={set("analisis")} placeholder={PISTA_ANALISIS} required />
          </Campo>
          <Campo etiqueta="Log del evento" className="span-todo">
            <textarea rows={6} className="mono" value={f.log_evento || ""} onChange={set("log_evento")} placeholder="Pegue aquí el log crudo del SIEM" />
          </Campo>
        </div>
      </div>

      <div className="panel">
        <h2>3. Comunicación al cliente</h2>
        <div className="grid g2">
          <Campo etiqueta="Resumen ejecutivo" ayuda="se llena con la plantilla del caso de uso">
            <textarea rows={8} value={f.resumen_ejecutivo || ""} onChange={set("resumen_ejecutivo")} />
          </Campo>
          <Campo etiqueta="Acciones de seguridad recomendadas">
            <textarea rows={8} value={f.acciones_recomendadas || ""} onChange={set("acciones_recomendadas")} />
          </Campo>
        </div>
      </div>

      {editando && (
        <div className="panel">
          <h2>4. Seguimiento</h2>
          <div className="grid g4">
            <Campo etiqueta="Estado">
              <select value={f.estado} onChange={set("estado")}>
                {Object.entries(ESTADOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </Campo>
            <Campo etiqueta="Ticket GLPI"><input type="number" value={f.glpi_ticket_id} onChange={set("glpi_ticket_id")} /></Campo>
            <Campo etiqueta="Acciones ejecutadas por el cliente" className="span-todo">
              <textarea rows={4} value={f.acciones_cliente || ""} onChange={set("acciones_cliente")} />
            </Campo>
          </div>
        </div>
      )}

      {!editando && (
        <div className="panel" tabIndex={0} onPaste={(e) => { const i = imagenesPegadas(e); if (i.length) { e.preventDefault(); agregar(i, "EVIDENCIA"); } }}>
          <h2>4. Evidencias y adjuntos</h2>
          <div className="acciones">
            <label className="btn chico primario">+ Evidencia (imagen)<input type="file" multiple accept=".png,.jpg,.jpeg" hidden onChange={(e) => { agregar(e.target.files, "EVIDENCIA"); e.target.value = ""; }} /></label>
            <label className="btn chico">+ Adjuntar archivo<input type="file" multiple accept={TIPOS} hidden onChange={(e) => { agregar(e.target.files, "ADJUNTO"); e.target.value = ""; }} /></label>
            <span className="tenue">Opcional. También puede hacer clic aquí y pegar un recorte con Ctrl+V.</span>
          </div>
          {archivos.map((x, i) => (
            <div key={i} className="adjunto">
              <span className="mini ext">{x.archivo.name.split(".").pop().toUpperCase()}</span>
              <div style={{ flex: 1 }}>{x.archivo.name}<div className="tenue" style={{ fontSize: 12 }}>{x.tipo === "EVIDENCIA" ? "Evidencia (en la plantilla)" : "Adjunto (archivo aparte)"} · {peso(x.archivo.size)}</div></div>
              <button type="button" className="btn chico peligro" onClick={() => setArchivos((l) => l.filter((_, k) => k !== i))}>Quitar</button>
            </div>
          ))}
        </div>
      )}

      {!editando && !alerta && glpi.activo && (
        <div className="panel">
          <label className="check">
            <input type="checkbox" checked={crearTicket} onChange={(e) => setCrearTicket(e.target.checked)} />
            <b>Crear ticket en GLPI al guardar</b>
          </label>
          {crearTicket && clienteSel && !clienteSel.glpi_entidad_id && (
            <div className="alerta aviso" style={{ margin: "10px 0 0" }}>
              {clienteSel.codigo} no tiene asignada la entidad de GLPI: el caso se guardará, pero el ticket no se podrá crear
              hasta que un coordinador la configure en Clientes.
            </div>
          )}
        </div>
      )}

      <div className="acciones" style={{ justifyContent: "flex-end", marginTop: 16 }}>
        <Link className="btn" to={editando ? `/casos/${id}` : alerta ? "/alertas" : "/casos"}>Cancelar</Link>
        <button className="btn primario" disabled={guardando}>{guardando ? "Guardando…" : "Guardar caso"}</button>
      </div>
    </form>
  );
}
