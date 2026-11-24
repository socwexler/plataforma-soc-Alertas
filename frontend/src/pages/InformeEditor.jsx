import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, token } from "../api";
import { useAuth } from "../auth";
import { imagenesPegadas } from "../components/Adjuntos";
import { ImagenPrivada, subirImagen } from "../components/Imagen";
import { Campo, MsgError } from "../components/Ui";
import { duracion, fechaHora, num } from "../util";

const CRITS = ["Crítica", "Alta", "Media", "Baja"];
const NOMBRE_ANEXO = { paises_entrantes: "Países entrantes", paises_salientes: "Países salientes", puertos: "Puertos no comunes",
  ips: "Ataques IPS", fuentes: "Fuentes integradas (SOC)", fuentes_noc: "Fuentes integradas (NOC)", eps: "Histórico de EPS" };

async function descargar(ruta, nombre) {
  const r = await fetch(`/api${ruta}`, { headers: { Authorization: `Bearer ${token.get()}` } });
  if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail || `Error ${r.status}`);
  const blob = await r.blob();
  const nombreServidor = /filename="([^"]+)"/.exec(r.headers.get("Content-Disposition") || "")?.[1];
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = nombreServidor || nombre; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

function TablaServicio({ s, d, clienteId }) {
  const casos = (p) => `/casos?cliente_id=${clienteId}&servicio=${s}&desde=${p.inicio}&hasta=${p.fin}`;
  return (
    <div className="tabla-scroll">
      <table className="tabla">
        <thead><tr><th>{s}</th>{d.periodos.map((p) => <th key={p.inicio} className="num">{p.corta}</th>)}</tr></thead>
        <tbody>
          <tr><td><b>Eventos escalados</b></td>{d.periodos.map((p) => (
            <td key={p.inicio} className="num"><Link to={casos(p)} target="_blank" title="Ver los casos de este periodo"><b>{num(p.total)}</b></Link></td>))}</tr>
          {CRITS.map((c) => <tr key={c}><td>{c}</td>{d.periodos.map((p) => <td key={p.inicio} className="num">{num(p.criticidad[c])}</td>)}</tr>)}
          <tr><td>Con retroalimentación</td>{d.periodos.map((p) => <td key={p.inicio} className="num">{num(p.con_retro)}</td>)}</tr>
          <tr><td>Tiempo mediano de reporte</td>{d.periodos.map((p) => <td key={p.inicio} className="num">{duracion(p.mediana_minutos)}</td>)}</tr>
        </tbody>
      </table>
    </div>
  );
}

export default function InformeEditor() {
  const { id } = useParams();
  const nav = useNavigate();
  const { puede } = useAuth();
  const [inf, setInf] = useState(null);
  const [f, setF] = useState(null);           // campos editables
  const [sucio, setSucio] = useState(false);
  const [msg, setMsg] = useState(null);
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(null);
  const [carga, setCarga] = useState(null);
  const archivo = useRef(null);

  const aplicar = useCallback((d) => {
    setInf(d);
    setF({ eps_promedio: d.eps_promedio ?? "", fuentes_integradas: d.fuentes_integradas ?? "", boletines_enviados: d.boletines_enviados ?? "",
      boletines: d.boletines, textos: { ...d.textos } });
    setSucio(false);
  }, []);
  useEffect(() => { api(`/informes/${id}`).then(aplicar).catch(setError); }, [id, aplicar]);

  useEffect(() => {
    const aviso = (e) => { if (sucio) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", aviso);
    return () => window.removeEventListener("beforeunload", aviso);
  }, [sucio]);

  if (!inf || !f) return error ? <MsgError e={error} /> : <div className="vacio">Cargando…</div>;
  const final = inf.estado === "FINAL";
  const editable = !final && puede("informes.editar");
  const cambiar = (k, v) => { setF((x) => ({ ...x, [k]: v })); setSucio(true); };
  const cambiarTexto = (k, v) => { setF((x) => ({ ...x, textos: { ...x.textos, [k]: v } })); setSucio(true); };
  // forma funcional: la carga de la imagen termina después y no debe pisar lo que se escribió mientras tanto
  const cambiarBoletin = (i, k, v) => { setF((x) => ({ ...x, boletines: x.boletines.map((b, j) => (j === i ? { ...b, [k]: v } : b)) })); setSucio(true); };
  const imagenBoletin = async (i, archivo) => {
    if (!archivo) return;
    setOcupado(`img${i}`); setError(null);
    try { cambiarBoletin(i, "imagen_id", (await subirImagen(`/informes/${id}/imagenes`, archivo)).id); } catch (e) { setError(e); }
    setOcupado(null);
  };

  const accion = async (nombre, fn, ok) => {
    setOcupado(nombre); setError(null); setMsg(null);
    try { const r = await fn(); if (r) aplicar(r.informe || r); if (ok) setMsg(ok); } catch (e) { setError(e); }
    setOcupado(null);
  };
  const datosGuardar = () => ({
    eps_promedio: f.eps_promedio === "" ? null : Number(f.eps_promedio),
    fuentes_integradas: f.fuentes_integradas === "" ? null : Number(f.fuentes_integradas),
    boletines_enviados: f.boletines_enviados === "" ? null : Number(f.boletines_enviados),
    boletines: f.boletines.filter((b) => b.nombre?.trim()),
    textos: f.textos,
  });
  const guardar = () => accion("guardar", () => api(`/informes/${id}`, { metodo: "PUT", datos: datosGuardar() }), "Cambios guardados.");
  const conGuardado = async (fn) => { if (sucio && editable) await api(`/informes/${id}`, { metodo: "PUT", datos: datosGuardar() }).then(aplicar); return fn(); };

  const subir = async (lista) => {
    if (!lista?.length) return;
    const fd = new FormData();
    [...lista].forEach((a) => fd.append("archivos", a));
    setOcupado("anexos"); setError(null); setMsg(null); setCarga(null);
    try {
      const r = await fetch(`/api/informes/${id}/anexos`, { method: "POST", headers: { Authorization: `Bearer ${token.get()}` }, body: fd });
      const c = await r.json();
      if (!r.ok) throw new Error(c?.detail || `Error ${r.status}`);
      aplicar(c.informe);
      setCarga(c);
    } catch (e) { setError(e); }
    setOcupado(null);
    if (archivo.current) archivo.current.value = "";
  };
  const regenerar = (claves) => {
    if (!claves && !window.confirm("Se reemplazarán todos los textos por la redacción automática con los datos actuales. ¿Continuar?")) return;
    accion("regenerar", () => conGuardado(() => api(`/informes/${id}/textos/regenerar`, { metodo: "POST", datos: { claves } })),
      claves ? "Texto regenerado." : "Textos regenerados.");
  };
  const servicios = Object.entries(inf.metricas.servicios);
  const clavesVisibles = Object.entries(inf.claves_textos).filter(([k]) => {
    const s = k.split("_").pop();
    return !["SOC", "NOC"].includes(s) || inf.metricas.servicios[s];
  });

  return (
    <>
      <div className="cabecera">
        <div>
          <h1>Informe {inf.cliente.codigo} · {inf.nombre}</h1>
          <p>{inf.cliente.nombre} · {inf.periodo} · {final ? <span className="badge est-CON_RETRO">Final</span> : <span className="badge etq">Borrador</span>}</p>
        </div>
        <div className="acciones">
          <Link className="btn" to="/informes">Volver</Link>
          <button className="btn primario" disabled={!!ocupado} onClick={() => accion("docx", () => conGuardado(() => descargar(`/informes/${id}/docx`, "informe.docx")))}>
            {ocupado === "docx" ? "Generando…" : "Descargar Word"}</button>
          <button className="btn primario" disabled={!!ocupado} onClick={() => accion("pdf", () => conGuardado(() => descargar(`/informes/${id}/pdf`, "informe.pdf")))}>
            {ocupado === "pdf" ? "Generando…" : "Descargar PDF"}</button>
          <Link className="btn" to={`/informes/${id}/presentacion`} target="_blank" rel="noopener"
                onClick={(e) => { if (sucio) { e.preventDefault(); window.alert("Guarde los cambios antes de ver la presentación."); } }}>Ver presentación</Link>
          <button className="btn" disabled={!!ocupado} title="Un solo archivo que se abre con doble clic" onClick={() => accion("preshtml", () => conGuardado(() => descargar(`/informes/${id}/presentacion?descargar=true`, "presentacion.html")))}>
            {ocupado === "preshtml" ? "Generando…" : "Presentación HTML"}</button>
          <button className="btn" disabled={!!ocupado} onClick={() => accion("prespdf", () => conGuardado(() => descargar(`/informes/${id}/presentacion.pdf`, "presentacion.pdf")))}>
            {ocupado === "prespdf" ? "Generando…" : "Presentación PDF"}</button>
        </div>
      </div>
      {msg && <div className="alerta ok">{msg}</div>}
      <MsgError e={error} />
      {final && <div className="alerta aviso">Informe final: las cifras quedaron congeladas el {fechaHora(inf.metricas.calculado_en)} y no se puede editar.</div>}

      <div className="panel">
        <h2>1. Casos del periodo (desde la bitácora)</h2>
        <p className="tenue" style={{ marginTop: 0 }}>Se comparan los tres últimos periodos según el día de corte del cliente. Haga clic en un total para ver esos casos y conciliarlos.{!final && " Las cifras se recalculan cada vez que se genera el informe."}</p>
        <div className={servicios.length > 1 ? "grid g2" : ""}>{servicios.map(([s, d]) => <TablaServicio key={s} s={s} d={d} clienteId={inf.cliente.id} />)}</div>
        {!servicios.length && <p className="tenue">El cliente no tiene casos en estos periodos.</p>}
      </div>

      <div className="panel">
        <h2>2. Anexos de FortiSIEM</h2>
        <p className="tenue" style={{ marginTop: 0 }}>
          Cargue los CSV exportados de FortiSIEM (países entrantes y salientes, puertos, ataques IPS, fuentes) o el Excel del informe con sus hojas.
          El tipo se reconoce por los encabezados. Un archivo nuevo del mismo tipo reemplaza al anterior.
        </p>
        {editable && (
          <div className="acciones" style={{ marginBottom: 12 }}>
            <input ref={archivo} type="file" multiple accept=".csv,.txt,.xlsx,.xlsm" style={{ display: "none" }} onChange={(e) => subir(e.target.files)} />
            <button className="btn primario" disabled={!!ocupado} onClick={() => archivo.current.click()}>{ocupado === "anexos" ? "Procesando…" : "Cargar archivos"}</button>
          </div>
        )}
        {carga && (
          <div className={`alerta ${carga.errores.length ? "aviso" : "ok"}`}>
            {carga.resultados.map((r) => <div key={r.archivo}><b>{r.archivo}:</b> {r.tablas.map((t) => `${t.nombre} (${t.resumen})`).join(" · ")}</div>)}
            {carga.errores.map((e) => <div key={e}>⚠ {e}</div>)}
          </div>
        )}
        <table className="tabla">
          <thead><tr><th>Anexo</th><th>Contenido</th><th></th></tr></thead>
          <tbody>
            {Object.entries(NOMBRE_ANEXO).map(([k, nombre]) => {
              const r = inf.anexos_resumen[k];
              return (
                <tr key={k}>
                  <td>{nombre}</td>
                  <td>{r || <span className="tenue">sin cargar (la sección se omite del informe)</span>}</td>
                  <td style={{ textAlign: "right" }}>{r && editable && k !== "eps" &&
                    <button className="btn chico peligro" onClick={() => accion("quitar", () => api(`/informes/${id}/anexos/${k}`, { metodo: "DELETE" }))}>Quitar</button>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h2>3. Datos del servicio</h2>
        <div className="grid g3">
          <Campo etiqueta="Promedio de EPS del periodo" ayuda={inf.eps_contratados ? `${num(inf.eps_contratados)} contratados` : undefined}>
            <input type="number" step="0.01" min="0" value={f.eps_promedio} disabled={!editable} onChange={(e) => cambiar("eps_promedio", e.target.value)} />
          </Campo>
          <Campo etiqueta="Fuentes integradas"><input type="number" min="0" value={f.fuentes_integradas} disabled={!editable} onChange={(e) => cambiar("fuentes_integradas", e.target.value)} /></Campo>
          <Campo etiqueta="Boletines enviados en el periodo"><input type="number" min="0" value={f.boletines_enviados} disabled={!editable} onChange={(e) => cambiar("boletines_enviados", e.target.value)} /></Campo>
        </div>
        {inf.eps_historico.length > 0 && <p className="tenue" style={{ marginBottom: 0 }}>EPS de periodos anteriores: {inf.eps_historico.map((x) => `${x.periodo} ${num(x.valor)}`).join(" · ")}</p>}
      </div>

      <div className="panel">
        <div className="cabecera" style={{ marginBottom: 8 }}>
          <h2 style={{ margin: 0 }}>4. Boletines de inteligencia de amenazas</h2>
          {editable && <button className="btn chico" onClick={() => cambiar("boletines", [...f.boletines, { nombre: "", tipo: "", fecha: "", resumen: "" }])}>+ Agregar boletín</button>}
        </div>
        {!f.boletines.length && <p className="tenue">Sin boletines: la sección se omite del informe.</p>}
        {f.boletines.map((b, i) => (
          <div key={i} className="grid g4" style={{ borderTop: "1px solid var(--borde)", paddingTop: 12, marginTop: 12 }}
               onPaste={(e) => { const p = editable ? imagenesPegadas(e) : []; if (p.length) { e.preventDefault(); imagenBoletin(i, p[0]); } }}>
            <Campo etiqueta="Nombre de la amenaza" className="span2"><input value={b.nombre} disabled={!editable} onChange={(e) => cambiarBoletin(i, "nombre", e.target.value)} /></Campo>
            <Campo etiqueta="Tipo"><input value={b.tipo || ""} disabled={!editable} onChange={(e) => cambiarBoletin(i, "tipo", e.target.value)} /></Campo>
            <Campo etiqueta="Fecha"><input type="date" value={b.fecha || ""} disabled={!editable} onChange={(e) => cambiarBoletin(i, "fecha", e.target.value)} /></Campo>
            <Campo etiqueta="Resumen e impacto" className="span-todo"><textarea rows={3} value={b.resumen || ""} disabled={!editable} onChange={(e) => cambiarBoletin(i, "resumen", e.target.value)} /></Campo>
            <div className="span-todo boletin-img">
              {b.imagen_id ? <ImagenPrivada ruta={`/informes/${id}/imagenes/${b.imagen_id}`} alt={`Imagen de ${b.nombre}`} /> : <span className="tenue">Sin imagen</span>}
              {editable && <div className="acciones">
                <label className="btn chico">{ocupado === `img${i}` ? "Cargando…" : b.imagen_id ? "Cambiar imagen" : "Cargar imagen"}
                  <input type="file" accept=".png,.jpg,.jpeg" hidden disabled={!!ocupado} onChange={(e) => { const a = e.target.files[0]; e.target.value = ""; imagenBoletin(i, a); }} /></label>
                {b.imagen_id && <button type="button" className="btn chico" onClick={() => cambiarBoletin(i, "imagen_id", null)}>Quitar imagen</button>}
                <span className="tenue">PNG o JPG; también puede pegarla con Ctrl+V en cualquier campo del boletín.</span>
              </div>}
            </div>
            {editable && <div><button className="btn chico peligro" onClick={() => cambiar("boletines", f.boletines.filter((_, j) => j !== i))}>Quitar boletín</button></div>}
          </div>
        ))}
      </div>

      <div className="panel">
        <div className="cabecera" style={{ marginBottom: 8 }}>
          <div><h2 style={{ margin: 0 }}>5. Textos del informe</h2>
            <p className="tenue" style={{ margin: "4px 0 0" }}>Redactados automáticamente con los datos; revíselos y ajústelos antes de generar. Separe párrafos con una línea en blanco.</p></div>
          {editable && <button className="btn chico" disabled={!!ocupado} onClick={() => regenerar(null)}>Regenerar todos</button>}
        </div>
        <div className="grid">
          {clavesVisibles.map(([k, etiqueta]) => (
            <Campo key={k} etiqueta={<span className="acciones" style={{ justifyContent: "space-between", width: "100%" }}>{etiqueta}
              {editable && <button type="button" className="btn fantasma chico" onClick={(e) => { e.preventDefault(); regenerar([k]); }}>Regenerar</button>}</span>}>
              <textarea rows={k === "recomendaciones" ? 8 : 4} value={f.textos[k] || ""} disabled={!editable} onChange={(e) => cambiarTexto(k, e.target.value)}
                        placeholder="Sin texto: la parte correspondiente queda vacía." />
            </Campo>
          ))}
        </div>
      </div>

      <div className="panel acciones" style={{ position: "sticky", bottom: 0, justifyContent: "space-between", zIndex: 4 }}>
        <div className="acciones">
          {editable && <button className="btn primario" disabled={!sucio || !!ocupado} onClick={guardar}>{ocupado === "guardar" ? "Guardando…" : sucio ? "Guardar cambios" : "Sin cambios"}</button>}
          {sucio && <span className="tenue">Hay cambios sin guardar</span>}
        </div>
        <div className="acciones">
          {puede("informes.cerrar") && !final && (
            <button className="btn" disabled={!!ocupado} onClick={() => window.confirm("Al marcarlo como final se congelan las cifras y ya no se puede editar. ¿Continuar?") &&
              accion("estado", () => conGuardado(() => api(`/informes/${id}/estado`, { metodo: "POST", datos: { estado: "FINAL" } })), "Informe marcado como final.")}>Marcar como final</button>
          )}
          {puede("informes.cerrar") && final && (
            <button className="btn" disabled={!!ocupado} onClick={() => accion("estado", () => api(`/informes/${id}/estado`, { metodo: "POST", datos: { estado: "BORRADOR" } }), "El informe volvió a borrador.")}>Volver a borrador</button>
          )}
          {puede("informes.cerrar") && !final && (
            <button className="btn peligro" disabled={!!ocupado} onClick={async () => {
              if (!window.confirm("¿Eliminar este informe borrador?")) return;
              try { await api(`/informes/${id}`, { metodo: "DELETE" }); nav("/informes"); } catch (e) { setError(e); }
            }}>Eliminar</button>
          )}
        </div>
      </div>
    </>
  );
}
