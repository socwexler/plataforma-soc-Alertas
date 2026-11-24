export const ESTADOS = {
  SIN_RETRO: "Sin retroalimentación",
  CON_RETRO: "Con retroalimentación",
  CERRADO: "Cerrado",
};
export const CRITICIDADES = ["Crítica", "Alta", "Media", "Baja"];
export const ROLES = { N1: "Analista N1", N2: "Analista N2", N3: "Especialista N3", LIDER: "Líder SOC", CISO: "CISO", ADMIN: "Administrador" };
export const REVISIONES = { PENDIENTE: "Por revisar", REVISADO: "Revisado", OBSERVADO: "Devuelto" };

const fmtFecha = new Intl.DateTimeFormat("es-CO", { day: "2-digit", month: "short", year: "numeric" });
const fmtFechaHora = new Intl.DateTimeFormat("es-CO", {
  day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false,
});
const fmtNum = new Intl.NumberFormat("es-CO");

export const fecha = (v) => (v ? fmtFecha.format(new Date(v)) : "—");
export const fechaHora = (v) => (v ? fmtFechaHora.format(new Date(v)) : "—");
export const num = (v) => (v === null || v === undefined ? "—" : fmtNum.format(v));

export function duracion(min) {
  if (min === null || min === undefined) return "—";
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60), m = min % 60;
  return m ? `${h} h ${m} min` : `${h} h`;
}

/** Date -> valor de <input type="datetime-local"> en hora local. */
export function aInputLocal(d) {
  if (!d) return "";
  const x = new Date(d);
  const p = (n) => String(n).padStart(2, "0");
  return `${x.getFullYear()}-${p(x.getMonth() + 1)}-${p(x.getDate())}T${p(x.getHours())}:${p(x.getMinutes())}`;
}
export const deInputLocal = (s) => (s ? new Date(s).toISOString() : null);

/** Texto sin tildes y en minúsculas, para búsquedas. */
export const clave = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Copia HTML enriquecido (para pegar en Outlook) con texto plano de respaldo. */
export async function copiarHtml(html, texto) {
  try {
    if (window.ClipboardItem && navigator.clipboard?.write) {
      await navigator.clipboard.write([new ClipboardItem({
        "text/html": new Blob([html], { type: "text/html" }),
        "text/plain": new Blob([texto], { type: "text/plain" }),
      })]);
      return true;
    }
  } catch { /* se intenta el método alternativo */ }
  // Sitios http sin HTTPS: se usa una selección temporal
  const div = document.createElement("div");
  div.innerHTML = html;
  div.style.cssText = "position:fixed;left:-9999px;top:0";
  document.body.appendChild(div);
  const rango = document.createRange();
  rango.selectNodeContents(div);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(rango);
  const ok = document.execCommand("copy");
  sel.removeAllRanges();
  div.remove();
  return ok;
}

export async function copiarTexto(texto) {
  try { await navigator.clipboard.writeText(texto); return true; } catch { /* alternativo */ }
  const ta = document.createElement("textarea");
  ta.value = texto;
  ta.style.cssText = "position:fixed;left:-9999px";
  document.body.appendChild(ta);
  ta.select();
  const ok = document.execCommand("copy");
  ta.remove();
  return ok;
}

export const ESTADOS_GLPI = { 1: "Nuevo", 2: "En curso (asignado)", 3: "En curso (planificado)", 4: "En espera", 5: "Resuelto", 6: "Cerrado" };

let _glpi = null;
/** Estado de la integración GLPI (se consulta una vez por sesión). */
/** Tras cambiar la configuración se vuelve a consultar. */
export function olvidarGlpi() { _glpi = null; }
export function infoGlpi(api) {
  if (!_glpi) _glpi = api("/glpi/estado").catch(() => ({ activo: false }));
  return _glpi;
}
