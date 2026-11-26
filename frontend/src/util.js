export const ESTADOS = {
  SIN_RETRO: "Sin retroalimentación",
  CON_RETRO: "Con retroalimentación",
  CERRADO: "Cerrado",
};
export const CRITICIDADES = ["Crítica", "Alta", "Media", "Baja"];
export const ROLES = { N1: "Analista N1", N2: "Analista N2", N3: "Especialista N3", LIDER: "Líder SOC", CISO: "CISO", ADMIN: "Administrador" };
export const REVISIONES = { PENDIENTE: "Por revisar", REVISADO: "Revisado", OBSERVADO: "Devuelto" };

// Las fechas se muestran y se escriben en hora de Colombia (UTC−5, sin horario de verano), sin importar la zona del equipo
export const ZONA = "America/Bogota";
const fmtFecha = new Intl.DateTimeFormat("es-CO", { day: "2-digit", month: "short", year: "numeric", timeZone: ZONA });
const fmtFechaHora = new Intl.DateTimeFormat("es-CO", {
  day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: ZONA,
});
const fmtIso = new Intl.DateTimeFormat("sv-SE", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: ZONA });
/** Fecha AAAA-MM-DD de Colombia (para filtros de fecha). */
export const isoCol = (d) => fmtIso.format(new Date(d)).slice(0, 10);
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

/** Objetivos por criticidad en una línea: «Crítica 35 min · Alta 45 min · Media 2 h · Baja 4 h». */
export const textoSla = (o) => Object.entries(o || {}).map(([c, m]) => `${c} ${duracion(m)}`).join(" · ");

/** Date -> valor de <input type="datetime-local"> en hora de Colombia. */
export const aInputLocal = (d) => (d ? fmtIso.format(new Date(d)).replace(" ", "T") : "");
/** Valor de <input type="datetime-local"> (hora de Colombia) -> ISO. */
export const deInputLocal = (s) => (s ? new Date(`${s.length === 16 ? `${s}:00` : s}-05:00`).toISOString() : null);

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
