const CLAVE = "soc_token";

export const token = {
  get: () => { try { return localStorage.getItem(CLAVE); } catch { return null; } },
  set: (t) => { try { localStorage.setItem(CLAVE, t); } catch { /* sin almacenamiento */ } },
  borrar: () => { try { localStorage.removeItem(CLAVE); } catch { /* sin almacenamiento */ } },
};

export class ErrorApi extends Error {
  constructor(status, mensaje) { super(mensaje); this.status = status; }
}

function mensajeError(cuerpo, status) {
  const d = cuerpo?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => `${(e.loc || []).slice(-1)[0] ?? ""}: ${e.msg}`).join(" · ");
  return `Error ${status}`;
}

export async function api(ruta, { metodo = "GET", datos, form, params } = {}) {
  let url = `/api${ruta}`;
  if (params) {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") q.set(k, v); });
    const s = q.toString();
    if (s) url += `?${s}`;
  }
  const headers = {};
  const t = token.get();
  if (t) headers.Authorization = `Bearer ${t}`;
  let body;
  if (form) body = new URLSearchParams(form);
  else if (datos !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(datos); }

  const r = await fetch(url, { method: metodo, headers, body });
  if (r.status === 401 && ruta !== "/auth/login") {
    token.borrar();
    window.dispatchEvent(new Event("sesion-vencida"));
  }
  if (r.status === 204) return null;
  const cuerpo = await r.json().catch(() => null);
  if (!r.ok) throw new ErrorApi(r.status, mensajeError(cuerpo, r.status));
  return cuerpo;
}
