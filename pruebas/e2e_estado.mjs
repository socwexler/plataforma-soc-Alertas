// Cambio de estado con evidencias. Uso: node e2e_estado.mjs <puerto> <.env> <carpeta pruebas>
import fs from "fs";
const [puerto, env, S] = process.argv.slice(2); const B = `http://127.0.0.1:${puerto}/api`;
const pw = /^ADMIN_PASSWORD=(.*)$/m.exec(fs.readFileSync(env, "utf8"))[1].trim();
const ent = async (u, p) => (await (await fetch(B + "/auth/login", { method: "POST", body: new URLSearchParams({ username: u, password: p }) })).json()).access_token;
const j = async (t, u, m = "GET", d) => { const r = await fetch(B + u, { method: m, headers: { Authorization: "Bearer " + t, ...(d ? { "Content-Type": "application/json" } : {}) }, body: d ? JSON.stringify(d) : undefined }); return [r.status, await r.json().catch(() => null)]; };
let f = 0, n = 0; const ver = (t, ok, x = "") => { n++; if (!ok) { f++; console.log("  [X] ", t, typeof x === "string" ? x : JSON.stringify(x)); } };
const A = await ent("admin", pw), T = { ADMIN: A };
for (const [k, rol] of [["N1", "N1"], ["N1B", "N1"], ["N2", "N2"], ["N3", "N3"], ["LIDER", "LIDER"], ["CISO", "CISO"]]) { await j(A, "/usuarios", "POST", { usuario: "e." + k.toLowerCase(), nombre: "Est " + k, rol, password: "Prueba-local-123" }); T[k] = await ent("e." + k.toLowerCase(), "Prueba-local-123"); }
const cl = (await j(A, "/clientes", "POST", { codigo: "EST", nombre: "Cliente estado" }))[1]; await j(A, `/clientes/${cl.id}/correos`, "PUT", { dominios: "est.example", para: "x@est.example", cc: "" });
const caso = async t => (await j(t, "/casos", "POST", { servicio: "SOC", cliente_id: cl.id, alerta: "Prueba estado", criticidad: "Alta", resumen_ejecutivo: "r", analisis: "a", acciones_recomendadas: "x", fecha_evento: new Date(Date.now() - 600e3).toISOString() }))[1];
const ar = x => fs.readFileSync(`${S}/archivos/${x}`), img = fs.readFileSync(S + "/banner_prueba.png");
const est = async (t, id, estado, lista = [], comentario) => { const fd = new FormData(); if (estado) fd.append("estado", estado); if (comentario !== undefined) fd.append("comentario", comentario); lista.forEach(([nom, d]) => fd.append("archivos", new Blob([d]), nom)); const r = await fetch(`${B}/casos/${id}/estado`, { method: "POST", headers: t ? { Authorization: "Bearer " + t } : {}, body: fd }); return [r.status, await r.json().catch(() => null)]; };
const c1 = await caso(T.N1), ver1 = async () => (await j(T.N1, "/casos/" + c1.id))[1]; let s, r;

// correo, imagen y documento en un solo cambio
[s, r] = await est(T.N1, c1.id, "CON_RETRO", [["RE caso.msg", ar("respuesta.msg")], ["RE caso.eml", ar("respuesta.eml")], ["captura.png", img], ["acta.docx", ar("ok.docx")], ["acta.pdf", "%PDF-1.4 x"]], "  El cliente confirma actividad autorizada  ");
ver("cambia el estado con 5 archivos", s === 200 && r.estado === "CON_RETRO" && r.adjuntos.length === 5 && r.adjuntos.every(a => a.tipo === "GESTION" && !a.incluir && a.subido_por === "Est N1"), [s, r?.detail]);
let sg = r.seguimientos.at(-1); ver("queda en el seguimiento", sg.tipo === "estado" && sg.autor_nombre === "Est N1" && sg.comentario === "Estado: SIN RETROALIMENTACIÓN → CON RETROALIMENTACIÓN\nEl cliente confirma actividad autorizada\nArchivos: RE caso.msg, RE caso.eml, captura.png, acta.docx, acta.pdf", sg);
ver("archivos enlazados al cambio", r.adjuntos.every(a => a.seguimiento_id === sg.id)); ver("sigue por revisar sin cambios", r.revision === "PENDIENTE");
const msg = r.adjuntos.find(a => a.nombre.endsWith(".msg")), baja = await fetch(`${B}/casos/${c1.id}/adjuntos/${msg.id}`, { headers: { Authorization: "Bearer " + T.CISO } });
ver("el CISO lo descarga íntegro", baja.status === 200 && Buffer.from(await baja.arrayBuffer()).equals(ar("respuesta.msg")) && baja.headers.get("content-disposition").startsWith("attachment") && baja.headers.get("content-security-policy").includes("sandbox"));
// nunca al cliente
[s, r] = await j(T.N1, `/casos/${c1.id}/correo`); ver("no van en el correo", s === 200 && r.archivos.length === 0 && !r.bloqueos.length && !r.html.includes("captura.png"), r);
ver("no van en la plantilla", !(await j(T.N1, `/casos/${c1.id}/notificacion`))[1].html.includes("<img"));
const eml = await (await fetch(`${B}/casos/${c1.id}/correo.eml`, { method: "POST", headers: { Authorization: "Bearer " + T.N1 } })).text(); ver("no van en el borrador", eml.includes("X-Unsent") && !/acta|captura|RE caso/.test(eml));
ver("no se pueden incluir", (await j(T.N1, `/casos/${c1.id}/adjuntos/${msg.id}`, "PATCH", { incluir: true }))[0] === 422 && !(await ver1()).adjuntos.some(a => a.incluir));
// el borrador de la plataforma (sin remitente ni fecha) sirve como evidencia
[s, r] = await est(T.N1, c1.id, "CON_RETRO", [["borrador.eml", eml]]); ver("acepta el borrador de la plataforma", s === 200 && r.adjuntos.some(a => a.nombre === "borrador.eml"), r?.detail);
[s, r] = await est(T.N1, c1.id, "CON_RETRO", [["bom.eml", "\ufeff\r\nSubject: RE: caso\r\nTo: a@b.co\r\n\r\nok"]]); ver("acepta eml con marca inicial", s === 200, r?.detail); ver("el borrador no llega al correo", !(await j(T.N1, `/casos/${c1.id}/correo`))[1].archivos.length);
// rechazos: nada cambia
const antes = await ver1();
for (const [d, lista] of [["exe", [["x.exe", "MZ"]]], ["msg con exe", [["a.msg", ar("malo.msg")]]], ["msg con js (nombre ANSI)", [["a.msg", ar("malo_ansi.msg")]]], ["documento disfrazado de msg", [["a.msg", ar("word97.msg")]]], ["texto disfrazado de msg", [["a.msg", "hola"]]], ["msg cortado", [["a.msg", ar("respuesta.msg").subarray(0, 700)]]], ["eml con exe", [["a.eml", ar("malo.eml")]]], ["eml anidado con html", [["a.eml", ar("anidado_malo.eml")]]], ["texto disfrazado de eml", [["a.eml", "hola\nmundo"]]], ["nota con dos puntos", [["a.eml", "Subject: x\n\nnada"]]], ["pdf como eml", [["a.eml", "%PDF-1.4\nx: y"]]], ["binario como eml", [["a.eml", Buffer.concat([Buffer.from("From: a@b.co\nTo: c@d.co\n\n"), Buffer.alloc(9)])]]], ["html", [["a.html", "<b>"]]], ["docx con macros", [["a.docx", ar("macro.docx")]]], ["zip con exe", [["a.zip", ar("malo.zip")]]], ["repetido", [["otro nombre.msg", ar("respuesta.msg")]]], ["demasiados", [...Array(21)].map((_, i) => [`t${i}.txt`, "t" + i])], ["uno bueno y uno malo", [["ok.txt", "ok"], ["x.exe", "MZ"]]], ["muy grande", [["x.txt", "a".repeat(15 * 1048576 + 1)]]]]) { [s, r] = await est(T.N1, c1.id, "CERRADO", lista); ver("rechaza " + d, s === 422 && typeof r.detail === "string", [s, r?.detail ?? "aceptado"]); }
ver("estado inventado", (await est(T.N1, c1.id, "OTRO"))[0] === 422); ver("sin estado", (await est(T.N1, c1.id, null))[0] === 422); ver("detalle muy largo", (await est(T.N1, c1.id, "CERRADO", [], "a".repeat(4001)))[0] === 422); ver("caso inexistente", (await est(T.N1, 99999999, "CERRADO"))[0] === 404);
let d1 = await ver1(); ver("un rechazo no cambia nada", d1.estado === "CON_RETRO" && d1.adjuntos.length === antes.adjuntos.length && d1.seguimientos.length === antes.seguimientos.length);
ver("msg y eml no van como adjunto del correo", await (async () => { const fd = new FormData(); fd.append("archivos", new Blob([ar("respuesta.eml")]), "x.eml"); fd.append("tipo", "ADJUNTO"); const q = await fetch(`${B}/casos/${c1.id}/adjuntos`, { method: "POST", headers: { Authorization: "Bearer " + T.N1 }, body: fd }); fd.set("tipo", "GESTION"); const q2 = await fetch(`${B}/casos/${c1.id}/adjuntos`, { method: "POST", headers: { Authorization: "Bearer " + T.N1 }, body: fd }); return q.status === 422 && q2.status === 422; })());
// mismo estado
ver("mismo estado sin archivos no hace nada", (await est(T.N1, c1.id, "CON_RETRO", [], "x"))[0] === 422);
[s, r] = await est(T.N1, c1.id, "CON_RETRO", [["anidado.eml", ar("anidado.eml")]]); ver("mismo estado agrega evidencia (correo reenviado)", s === 200 && r.seguimientos.at(-1).comentario === "Evidencia agregada (estado: CON RETROALIMENTACIÓN)\nArchivos: anidado.eml", r?.detail ?? r?.seguimientos?.at(-1));
// sin archivos ni detalle sigue funcionando
[s, r] = await est(T.N1, c1.id, "CERRADO"); ver("sin archivos", s === 200 && r.estado === "CERRADO" && r.seguimientos.at(-1).comentario === "Estado: CON RETROALIMENTACIÓN → CERRADO");
// perfiles: todos menos CISO, en casos propios o ajenos
for (const [k, e] of [["N1B", "CON_RETRO"], ["N2", "CERRADO"], ["N3", "SIN_RETRO"], ["LIDER", "CON_RETRO"], ["ADMIN", "CERRADO"]]) { [s, r] = await est(T[k], c1.id, e, [[k + ".txt", "ev " + k]]); ver(k + " en caso ajeno", s === 200 && r.estado === e && r.seguimientos.at(-1).comentario.includes(k + ".txt"), [s, r?.detail]); }
ver("CISO no", (await est(T.CISO, c1.id, "SIN_RETRO", [["z.txt", "z"]]))[0] === 403); ver("sin sesión no", (await est(null, c1.id, "SIN_RETRO"))[0] === 401);
d1 = await ver1(); ver("el autor es quien lo hizo", d1.seguimientos.some(x => x.autor_nombre === "Est N1B" && x.tipo === "estado") && d1.analista.nombre === "Est N1");
// lo demás de un caso ajeno sigue vedado al N1
const aB = d1.adjuntos.find(a => a.nombre === "N1B.txt"); ver("N1 ajeno no edita", (await j(T.N1B, "/casos/" + c1.id, "PUT", { servicio: "SOC", cliente_id: cl.id, alerta: "otra cosa", criticidad: "Baja", fecha_evento: d1.fecha_evento }))[0] === 403); ver("N1 ajeno no quita archivos", (await j(T.N1B, `/casos/${c1.id}/adjuntos/${aB.id}`, "DELETE"))[0] === 403); ver("N1 ajeno no genera correo", (await j(T.N1B, `/casos/${c1.id}/correo`))[0] === 403);
// revisión: no la altera
await j(T.N2, `/casos/${c1.id}/revision`, "POST", { resultado: "REVISADO" }); [s, r] = await est(T.N1, c1.id, "SIN_RETRO", [["post.txt", "post"]]); ver("no devuelve a revisión", s === 200 && r.revision === "REVISADO");
[s, r] = await j(T.N1, `/casos/${c1.id}/adjuntos/${aB.id}`, "DELETE"); ver("quitar una evidencia queda registrado y no altera la revisión", s === 200 && r.revision === "REVISADO" && r.seguimientos.some(x => x.comentario.startsWith("Archivo eliminado: N1B.txt")) && r.seguimientos.some(x => x.comentario.includes("Archivos: N1B.txt")));
// la misma imagen puede ser además evidencia de la plantilla
{ const fd = new FormData(); fd.append("archivos", new Blob([img]), "plantilla.png"); fd.append("tipo", "EVIDENCIA"); const q = await fetch(`${B}/casos/${c1.id}/adjuntos`, { method: "POST", headers: { Authorization: "Bearer " + T.N1 }, body: fd }); const h = (await j(T.N1, `/casos/${c1.id}/notificacion`))[1].html; ver("plantilla solo con su evidencia", q.status === 201 && h.split("<img").length === 2 && h.includes("plantilla.png") && !h.includes("captura.png")); }
// anulado
await j(T.N2, `/casos/${c1.id}/anular`, "POST", { motivo: "registrado por error" }); ver("anulado no cambia", (await est(T.N2, c1.id, "CERRADO", [["q.txt", "q"]]))[0] === 409);
console.log(f ? `FALLOS ${f} de ${n}` : `TODO BIEN: ${n} comprobaciones`);
