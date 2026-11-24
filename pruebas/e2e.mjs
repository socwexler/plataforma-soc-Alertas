// Uso: node e2e.mjs <puerto> <ruta .env> <xlsx> <carpeta csv>
import fs from "fs";
import CT from "./control.mjs";
const [X1, X2] = CT.clientes, T1 = X1.totales.join("/"), T2 = X2.totales.join("/"), menos = (t) => [...t.slice(0, 2), t[2] - 1].join("/"), N1 = X1.totales[2];
const [puerto, env, xlsx, csv] = process.argv.slice(2);
const B = `http://127.0.0.1:${puerto}/api`;
const pw = /^ADMIN_PASSWORD=(.*)$/m.exec(fs.readFileSync(env, "utf8"))[1].trim();
const ent = async (u, p) => (await (await fetch(B + "/auth/login", { method: "POST", body: new URLSearchParams({ username: u, password: p }) })).json()).access_token;
const tok = await ent("admin", pw);
const j = async (u, m = "GET", d, t = tok) => { const r = await fetch(B + u, { method: m, headers: { Authorization: "Bearer " + t, ...(d ? { "Content-Type": "application/json" } : {}) }, body: d ? JSON.stringify(d) : undefined }); return [r.status, await r.json().catch(() => null)]; };
let fallos = 0;
const ver = (n, ok, x = "") => { if (!ok) fallos++; console.log(ok ? "  [ok]" : "  [X] ", n, x); };

const fd = new FormData(); fd.append("archivo", new Blob([fs.readFileSync(xlsx)]), "Bitácora producción.xlsx");
const a = await (await fetch(B + "/importaciones/archivo", { method: "POST", headers: { Authorization: "Bearer " + tok }, body: fd })).json();
ver("archivo con tildes", !!a.archivo_id);
const imp = (modo, simular) => j("/importaciones", "POST", { archivo_id: a.archivo_id, hoja: "BITACORA", modo, simular, cargar_catalogos: true });
let [s, r] = await imp("solo_nuevos", true);
ver("simulación no guarda", s === 200 && (await j("/casos?tamano=1"))[1].total === 0, JSON.stringify(r.resumen));
[s, r] = await imp("solo_nuevos", false);
ver("importa todos los casos", r.resumen.insertados === CT.importados, JSON.stringify(r.siguiente_numero));
console.log("      ", r.detalle.filter(d => /cruce/.test(d.concepto)).map(d => d.total + " " + d.concepto).join(" | "));
[s, r] = await imp("actualizar", true);
ver("reimportar no cambia nada", r.resumen.actualizados === 0 && r.resumen.insertados === 0, JSON.stringify(r.resumen));

const c = (await j(`/casos?q=${CT.medianoche.numero}&tamano=1`))[1].items[0];
ver("caso que cruza la medianoche", CT.medianoche.evento.some(x => c.fecha_evento.startsWith(x)), c.fecha_evento + " " + c.minutos_respuesta + " min");

const cl = (await j("/clientes"))[1];
for (const { codigo: cod, anio, mes, totales, retro, anexos } of CT.clientes) {
  const esp = totales.join("/");
  const id = cl.find(x => x.codigo === cod).id;
  const [st, inf] = await j("/informes", "POST", { cliente_id: id, anio, mes });
  const P = inf.metricas.servicios.SOC.periodos;
  ver(`${cod} totales`, st === 201 && P.map(p => p.total).join("/") === esp, P.map(p => p.total).join("/"));
  ver(`${cod} retroalimentación`, P[2].con_retro === retro, P[2].con_retro);
  for (const p of P) {
    const n = (await j(`/casos?cliente_id=${id}&servicio=SOC&desde=${p.inicio}&hasta=${p.fin}&tamano=1`))[1].total;
    const t = (await j(`/tablero?cliente_id=${id}&servicio=SOC&desde=${p.inicio}&hasta=${p.fin}`))[1];
    ver(`${cod} ${p.corta}: informe = lista = tablero = suma diaria`, n === p.total && t.indicadores.total === p.total && t.por_dia.reduce((x, d) => x + d["Crítica"] + d.Alta + d.Media + d.Baja + d.Sin, 0) === p.total, `${p.total}/${n}/${t.indicadores.total}`);
  }
  if (anexos) {
    const f2 = new FormData(); for (const x of anexos) f2.append("archivos", new Blob([fs.readFileSync(csv + "/" + x)]), x);
    const an = await (await fetch(`${B}/informes/${inf.id}/anexos`, { method: "POST", headers: { Authorization: "Bearer " + tok }, body: f2 })).json();
    ver("anexos " + cod, an.errores?.length === 0);
  }
  for (const x of ["docx", "pdf", "presentacion", "presentacion.pdf"]) { const q = await fetch(`${B}/informes/${inf.id}/${x}`, { headers: { Authorization: "Bearer " + tok } }); const b = await q.arrayBuffer(); ver(`${cod} ${x}`, q.status === 200 && b.byteLength > 50000, b.byteLength + " B"); }
}
// caso nuevo desde la plataforma y permisos N1
await j("/usuarios", "POST", { usuario: "prueba.n1", nombre: "Prueba N1", rol: "N1", password: "Prueba-local-123" });
const n1 = await ent("prueba.n1", "Prueba-local-123");
const hoy = new Date(Date.now() - 5 * 3600e3).toISOString().slice(0, 10);
const [sc, nc] = await j("/casos", "POST", { servicio: "SOC", cliente_id: cl.find(x => x.codigo === X1.codigo).id, alerta: "PRUEBA instalación", criticidad: "Baja", fecha_evento: new Date(Date.now() - 600e3).toISOString() }, n1);
ver("N1 registra el siguiente número", sc === 201 && nc.numero === CT.siguiente, nc?.numero);
ver("el caso nuevo cuenta hoy", (await j(`/casos?q=PRUEBA instalación&desde=${hoy}&hasta=${hoy}`))[1].total === 1);
ver("N1 no administra ni importa", (await j("/usuarios", "GET", null, n1))[0] === 403 && (await j("/importaciones", "GET", null, n1))[0] === 403);
ver("sin sesión no entra", (await fetch(B + "/casos")).status === 401);
console.log(fallos ? `FALLOS: ${fallos}` : "TODO BIEN");
