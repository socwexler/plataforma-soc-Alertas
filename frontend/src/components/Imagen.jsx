import { useEffect, useState } from "react";
import { token } from "../api";

/** Imagen protegida de la API (se pide con la sesión). version: cambia cuando se reemplaza. */
export function ImagenPrivada({ ruta, version = 0, className = "", alt = "" }) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let url; let vivo = true;
    setSrc(null);
    fetch(`/api${ruta}`, { headers: { Authorization: `Bearer ${token.get()}` } })
      .then((r) => (r.ok ? r.blob() : Promise.reject(new Error())))
      .then((b) => { url = URL.createObjectURL(b); if (vivo) setSrc(url); else URL.revokeObjectURL(url); }).catch(() => {});
    return () => { vivo = false; if (url) URL.revokeObjectURL(url); };
  }, [ruta, version]);
  return src ? <img className={className} src={src} alt={alt} /> : <span className={className} />;
}

export async function subirImagen(ruta, archivo, metodo = "POST") {
  const fd = new FormData();
  fd.append("archivo", archivo);
  const r = await fetch(`/api${ruta}`, { method: metodo, headers: { Authorization: `Bearer ${token.get()}` }, body: fd });
  const c = await r.json().catch(() => null);
  if (!r.ok) throw new Error(typeof c?.detail === "string" ? c.detail : `Error ${r.status} al subir la imagen`);
  return c;
}
