// Uso: node e2e_roles.mjs <puerto> <ruta .env>
import fs from "fs";
const [puerto, env] = process.argv.slice(2);
const B = `http://127.0.0.1:${puerto}/api`;
const pw = /^ADMIN_PASSWORD=(.*)$/m.exec(fs.readFileSync(env, "utf8"))[1].trim();
const ent = async (u, p) => (await (await fetch(B + "/auth/login", { method: "POST", body: new URLSearchParams({ username: u, password: p }) })).json()).access_token;
const j = async (t, u, m = "GET", d) => { const r = await fetch(B + u, { method: m, headers: { Authorization: "Bearer " + t, ...(d ? { "Content-Type": "application/json" } : {}) }, body: d ? JSON.stringify(d) : undefined }); return [r.status, await r.json().catch(() => null)]; };
let fallos = 0, n = 0;
const ver = (t, ok, x = "") => { n++; if (!ok) { fallos++; console.log("  [X] ", t, x); } else if (process.env.V) console.log("  [ok]", t); };

const T = { ADMIN: await ent("admin", pw) }, U = {};
const clave = "Prueba-local-123";
for (const rol of ["N1", "N2", "N3", "LIDER", "CISO"]) {
  const [s, u] = await j(T.ADMIN, "/usuarios", "POST", { usuario: "p." + rol.toLowerCase(), nombre: "Prueba " + rol, rol, password: clave });
  ver("crear " + rol, s === 201, s); U[rol] = u; T[rol] = await ent("p." + rol.toLowerCase(), clave);
}
const [, u1b] = await j(T.ADMIN, "/usuarios", "POST", { usuario: "p.n1b", nombre: "Prueba N1 B", rol: "N1", password: clave }); T.N1B = await ent("p.n1b", clave);
ver("rol viejo COORDINADOR no se acepta", (await j(T.ADMIN, "/usuarios", "POST", { usuario: "p.coord", nombre: "Viejo rol", rol: "COORDINADOR", password: clave }))[0] === 422);
const [, cli] = await j(T.ADMIN, "/clientes", "POST", { codigo: "PRB", nombre: "Cliente prueba", dia_corte: 1 });
const caso = { servicio: "SOC", cliente_id: cli.id, alerta: "PRUEBA roles", criticidad: "Baja", analisis: "original", fecha_evento: new Date(Date.now() - 600e3).toISOString() };
const [, cN1] = await j(T.N1, "/casos", "POST", caso), [, cN2] = await j(T.N2, "/casos", "POST", caso);
const hoy = new Date(Date.now() - 5 * 3600e3);
const [, inf] = await j(T.N2, "/informes", "POST", { cliente_id: cli.id, anio: hoy.getFullYear(), mes: hoy.getMonth() + 1 });

// --- matriz: [descripcion, petición, roles permitidos]
const TODOS = ["N1", "N2", "N3", "LIDER", "CISO", "ADMIN"], REV = ["N2", "N3", "LIDER", "ADMIN"], LID = ["LIDER", "ADMIN"];
const M = [
  ["ver casos", r => j(T[r], "/casos?tamano=1"), TODOS],
  ["ver detalle", r => j(T[r], "/casos/" + cN1.id), TODOS],
  ["ver notificación", r => j(T[r], `/casos/${cN1.id}/notificacion`), TODOS],
  ["crear caso", r => j(T[r], "/casos", "POST", caso), ["N1", ...REV]],
  ["editar caso ajeno", r => j(T[r], "/casos/" + cN2.id, "PUT", caso), REV],
  ["cambiar estado de caso ajeno", async r => { const fd = new FormData(); fd.append("estado", "CON_RETRO"); fd.append("archivos", new Blob(["evidencia " + r]), r + ".txt"); const x = await fetch(`${B}/casos/${cN2.id}/estado`, { method: "POST", headers: { Authorization: "Bearer " + T[r] }, body: fd }); return [x.status]; }, ["N1", ...REV]],
  ["comentar caso ajeno", r => j(T[r], `/casos/${cN2.id}/seguimientos`, "POST", { comentario: "hola" }), REV],
  ["tablero", r => j(T[r], "/tablero"), [...REV, "CISO"]],
  ["resumen de inicio", r => j(T[r], "/casos/resumen"), [...REV, "CISO"]],
  ["base de conocimiento", r => j(T[r], "/casos-uso"), ["N1", ...REV]],
  ["editar conocimiento", r => j(T[r], "/casos-uso", "POST", { nombre: "Regla " + r + Math.random() }), REV],
  ["ver informes", r => j(T[r], "/informes"), [...REV, "CISO"]],
  ["ver informe", r => j(T[r], "/informes/" + inf.id), [...REV, "CISO"]],
  ["editar informe", r => j(T[r], "/informes/" + inf.id, "PUT", { textos: {}, boletines: [] }), REV],
  ["cerrar informe", r => j(T[r], `/informes/${inf.id}/estado`, "POST", { estado: "BORRADOR" }), LID],
  ["modificar cliente", r => j(T[r], "/clientes/" + cli.id, "PUT", { codigo: "PRB", nombre: "Cliente prueba", dia_corte: 1 }), LID],
  ["historial de importación", r => j(T[r], "/importaciones"), LID],
  ["lista de usuarios", r => j(T[r], "/usuarios"), LID],
  ["probar GLPI (sin configurar)", r => j(T[r], "/glpi/probar", "POST"), ["LIDER", "ADMIN"]],
  ["ver configuración", r => j(T[r], "/config"), ["LIDER", "ADMIN"]],
];
for (const [d, f, ok] of M) for (const r of TODOS) { const [s] = await f(r); ver(`${d} · ${r}`, ok.includes(r) ? s !== 403 && s !== 401 && (s < 400 || d.startsWith("probar")) : s === 403, s); }
for (const x of ["docx", "pdf", "presentacion", "presentacion.pdf"]) for (const r of ["N1", "CISO"]) { const q = await fetch(`${B}/informes/${inf.id}/${x}`, { headers: { Authorization: "Bearer " + T[r] } }); await q.arrayBuffer(); ver(`descargar ${x} · ${r}`, q.status === (r === "CISO" ? 200 : 403), q.status); }

// --- revisión
const rev = (r, id, resultado, observacion) => j(T[r], `/casos/${id}/revision`, "POST", { resultado, observacion });
ver("caso de N1 nace por revisar", cN1.revision === "PENDIENTE"); ver("caso de N2 no requiere", cN2.revision === null);
ver("N1 no revisa", (await rev("N1", cN1.id, "REVISADO"))[0] === 403); ver("CISO no revisa", (await rev("CISO", cN1.id, "REVISADO"))[0] === 403);
ver("no aplica a caso N2", (await rev("N3", cN2.id, "REVISADO"))[0] === 409);
ver("devolver exige observación", (await rev("N2", cN1.id, "OBSERVADO", "  "))[0] === 422);
const p0 = (await j(T.N2, "/casos/pendientes"))[1].por_revisar; ver("contador del revisor", p0 >= 1, p0);
let [s, c] = await rev("N2", cN1.id, "OBSERVADO", "Falta la IP origen"); ver("N2 devuelve", s === 200 && c.revision === "OBSERVADO" && c.revisado_por === "Prueba N2");
ver("contador baja", (await j(T.N2, "/casos/pendientes"))[1].por_revisar === p0 - 1); ver("N1 ve 1 devuelto", (await j(T.N1, "/casos/pendientes"))[1].mis_observados === 1);
ver("otro N1 no lo ve como suyo", (await j(T.N1B, "/casos/pendientes"))[1].mis_observados === 0);
ver("otro N1 no puede editarlo", (await j(T.N1B, "/casos/" + cN1.id, "PUT", caso))[0] === 403);
const base = { ...c, cliente_id: c.cliente.id };
[s, c] = await j(T.N1, "/casos/" + cN1.id, "PUT", { ...base, estado: "CON_RETRO", acciones_cliente: "ok" }); ver("cambiar solo el estado no reenvía", s === 200 && c.revision === "OBSERVADO", c.revision);
[s, c] = await j(T.N1, "/casos/" + cN1.id, "PUT", { ...base, estado: "CON_RETRO", analisis: "corregido" }); ver("corregir lo devuelve a por revisar", c.revision === "PENDIENTE" && c.revisado_por === null, c.revision);
[s, c] = await rev("N3", cN1.id, "REVISADO"); ver("N3 lo marca revisado", c.revision === "REVISADO");
[s, c] = await j(T.N2, "/casos/" + cN1.id, "PUT", { ...base, analisis: "ajuste del N2" }); ver("si edita un revisor sigue revisado", c.revision === "REVISADO");
ver("queda en el historial", c.seguimientos.filter(x => x.tipo === "revision").length === 3, c.seguimientos.filter(x => x.tipo === "revision").length);
ver("filtro por revisar", (await j(T.N2, "/casos?revision=PENDIENTE&tamano=200"))[1].items.every(x => x.revision === "PENDIENTE"));
ver("SLA sin cambio: la revisión no mueve la hora de reporte", new Date(c.fecha_reporte).getTime() === new Date(cN1.fecha_reporte).getTime());

// --- el Líder no toca administradores
const [, us] = await j(T.ADMIN, "/usuarios"); const adm = us.find(u => u.usuario === "admin");
const d = (u, x = {}) => ({ usuario: u.usuario, nombre: u.nombre, rol: u.rol, activo: u.activo, ...x });
ver("Líder no edita al admin", (await j(T.LIDER, "/usuarios/" + adm.id, "PUT", d(adm, { password: "Otra-clave-123" })))[0] === 403);
ver("Líder no crea admin", (await j(T.LIDER, "/usuarios", "POST", { usuario: "x.admin", nombre: "Intento", rol: "ADMIN", password: clave }))[0] === 403);
ver("Líder no asciende a admin", (await j(T.LIDER, "/usuarios/" + U.N2.id, "PUT", d(U.N2, { rol: "ADMIN" })))[0] === 403);
ver("Líder no se asciende", (await j(T.LIDER, "/usuarios/" + U.LIDER.id, "PUT", d(U.LIDER, { rol: "N3" })))[0] === 400);
ver("Líder sí gestiona analistas", (await j(T.LIDER, "/usuarios/" + u1b.id, "PUT", d(u1b, { activo: false })))[0] === 200);
ver("usuario desactivado pierde acceso al instante", (await j(T.N1B, "/casos"))[0] === 401);
ver("/auth/yo trae permisos", (await j(T.CISO, "/auth/yo"))[1].permisos.join() === "informes.ver,tablero.ver");
console.log(fallos ? `FALLOS: ${fallos} de ${n}` : `TODO BIEN: ${n} comprobaciones`);
