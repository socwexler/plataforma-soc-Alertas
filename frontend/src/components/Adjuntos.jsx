import { useEffect, useRef, useState } from "react";
import { api, token } from "../api";

export const TIPOS = ".png,.jpg,.jpeg,.pdf,.docx,.xlsx,.pptx,.txt,.log,.csv,.json,.zip";
export const TIPOS_GESTION = `.eml,.msg,${TIPOS}`;
export const peso = (b) => (b >= 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);

export async function subirAdjuntos(casoId, archivos, tipo) {
  const fd = new FormData();
  [...archivos].forEach((a) => fd.append("archivos", a));
  fd.append("tipo", tipo);
  const r = await fetch(`/api/casos/${casoId}/adjuntos`, { method: "POST", headers: { Authorization: `Bearer ${token.get()}` }, body: fd });
  const c = await r.json().catch(() => null);
  if (!r.ok) throw new Error(typeof c?.detail === "string" ? c.detail : `Error ${r.status} al subir el archivo`);
  return c;
}

/** Imágenes del portapapeles (Ctrl+V de un recorte de pantalla), con nombre por fecha. */
export function imagenesPegadas(e) {
  const imgs = [...(e.clipboardData?.files || [])].filter((f) => ["image/png", "image/jpeg"].includes(f.type));
  const sello = new Date().toISOString().slice(0, 19).replace(/\D/g, "");
  return imgs.map((f, i) => new File([f], `captura_${sello}${i ? `_${i}` : ""}.${f.type === "image/png" ? "png" : "jpg"}`, { type: f.type }));
}

/** Cambia el estado (o solo agrega soporte, con el mismo estado). archivos: correos, imágenes o documentos. */
export async function enviarEstado(casoId, estado, comentario, archivos) {
  const fd = new FormData();
  fd.append("estado", estado);
  fd.append("comentario", comentario);
  archivos.forEach((a) => fd.append("archivos", a));
  const r = await fetch(`/api/casos/${casoId}/estado`, { method: "POST", headers: { Authorization: `Bearer ${token.get()}` }, body: fd });
  const c = await r.json().catch(() => null);
  if (!r.ok) throw new Error(typeof c?.detail === "string" ? c.detail : `Error ${r.status} al cambiar el estado`);
  return c;
}

async function traer(casoId, a) {
  const r = await fetch(`/api/casos/${casoId}/adjuntos/${a.id}`, { headers: { Authorization: `Bearer ${token.get()}` } });
  if (!r.ok) throw new Error(`No se pudo abrir ${a.nombre}`);
  return URL.createObjectURL(await r.blob());
}

export async function descargar(casoId, a) {
  const url = await traer(casoId, a);
  const l = document.createElement("a"); l.href = url; l.download = a.nombre; l.click();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

function Miniatura({ casoId, a }) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let url; let vivo = true;
    traer(casoId, a).then((u) => { url = u; if (vivo) setSrc(u); else URL.revokeObjectURL(u); }).catch(() => {});
    return () => { vivo = false; if (url) URL.revokeObjectURL(url); };
  }, [casoId, a.id]);
  return src ? <img className="mini" src={src} alt={a.nombre} /> : <span className="mini" />;
}

const ETIQUETA = { EVIDENCIA: "Evidencia (en la plantilla)", ADJUNTO: "Adjunto (archivo aparte)", GESTION: "Cambio de estado (interno)" };

export default function Adjuntos({ caso, editable, onCambio, onError }) {
  const ev = useRef(null), ad = useRef(null);
  const [ocupado, setOcupado] = useState(false);
  const hacer = async (fn) => {
    setOcupado(true); onError(null);
    try { onCambio(await fn()); } catch (e) { onError(e); }
    setOcupado(false);
    [ev, ad].forEach((x) => { if (x.current) x.current.value = ""; });
  };
  const subir = (archivos, tipo) => { if (archivos.length) hacer(() => subirAdjuntos(caso.id, archivos, tipo)); };
  const abrir = async (a) => {
    try { await descargar(caso.id, a); } catch (e) { onError(e); }
  };
  const total = caso.adjuntos.filter((a) => a.incluir).reduce((s, a) => s + a.tamano, 0);

  return (
    <div className="panel" tabIndex={editable ? 0 : undefined} onPaste={(e) => { if (!editable) return; const i = imagenesPegadas(e); if (i.length) { e.preventDefault(); subir(i, "EVIDENCIA"); } }}>
      <h2>Evidencias y adjuntos</h2>
      {editable && (
        <>
          <input ref={ev} type="file" multiple accept=".png,.jpg,.jpeg" hidden onChange={(e) => subir([...e.target.files], "EVIDENCIA")} />
          <input ref={ad} type="file" multiple accept={TIPOS} hidden onChange={(e) => subir([...e.target.files], "ADJUNTO")} />
          <div className="acciones" style={{ marginBottom: 10 }}>
            <button className="btn chico primario" disabled={ocupado} onClick={() => ev.current.click()}>+ Evidencia (imagen)</button>
            <button className="btn chico" disabled={ocupado} onClick={() => ad.current.click()}>+ Adjuntar archivo</button>
            <span className="tenue">{ocupado ? "Procesando…" : "o haga clic aquí y pegue un recorte con Ctrl+V"}</span>
          </div>
        </>
      )}
      {!caso.adjuntos.length && <p className="tenue" style={{ margin: 0 }}>Sin archivos.</p>}
      {caso.adjuntos.map((a) => (
        <div key={a.id} className="adjunto">
          {a.mime.startsWith("image/") ? <Miniatura casoId={caso.id} a={a} /> : <span className="mini ext">{a.nombre.split(".").pop().toUpperCase()}</span>}
          <div style={{ flex: 1, minWidth: 0 }}>
            <button className="enlace" onClick={() => abrir(a)}>{a.nombre}</button>
            <div className="tenue" style={{ fontSize: 12 }}>{ETIQUETA[a.tipo]} · {peso(a.tamano)} · {a.subido_por}</div>
          </div>
          {a.tipo !== "GESTION" && <label className="check" style={{ fontSize: 13 }}>
            <input type="checkbox" checked={a.incluir} disabled={!editable || ocupado} onChange={(e) => { const incluir = e.target.checked; hacer(() => api(`/casos/${caso.id}/adjuntos/${a.id}`, { metodo: "PATCH", datos: { incluir } })); }} /> En el correo
          </label>}
          {editable && <button className="btn chico peligro" disabled={ocupado} onClick={() => window.confirm(`¿Eliminar ${a.nombre}? No se puede recuperar.`) && hacer(() => api(`/casos/${caso.id}/adjuntos/${a.id}`, { metodo: "DELETE" }))}>Quitar</button>}
        </div>
      ))}
      {total > 0 && <p className="tenue" style={{ margin: "8px 0 0" }}>En el correo: {peso(total)}.</p>}
    </div>
  );
}
