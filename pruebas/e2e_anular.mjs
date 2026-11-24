// Requiere haber corrido antes e2e.mjs (bitácora importada e informes de los dos clientes de control en borrador)
import fs from "fs";
import CT from "./control.mjs";
const [X1, X2] = CT.clientes, T1 = X1.totales.join("/"), T2 = X2.totales.join("/"), menos = (t) => [...t.slice(0, 2), t[2] - 1].join("/"), N1 = X1.totales[2];
const [puerto, env, XLSX] = process.argv.slice(2); const B = `http://127.0.0.1:${puerto}/api`;
const pw = /^ADMIN_PASSWORD=(.*)$/m.exec(fs.readFileSync(env, "utf8"))[1].trim(), P = "Prueba-local-123";
const ent = async (u, p) => (await (await fetch(B + "/auth/login", { method: "POST", body: new URLSearchParams({ username: u, password: p }) })).json()).access_token;
const j = async (t, u, m = "GET", d) => { const r = await fetch(B + u, { method: m, headers: { Authorization: "Bearer " + t, ...(d ? { "Content-Type": "application/json" } : {}) }, body: d ? JSON.stringify(d) : undefined }); return [r.status, await r.json().catch(() => null)]; };
let f = 0, n = 0; const ver = (t, ok, x = "") => { n++; if (!ok) { f++; console.log("  [X] ", t, JSON.stringify(x)); } };
const A = await ent("admin", pw), T = {};
for (const r of ["N1", "N2", "N3", "LIDER", "CISO"]) { await j(A, "/usuarios", "POST", { usuario: "x." + r.toLowerCase(), nombre: "Anula " + r, rol: r, password: P }); T[r] = await ent("x." + r.toLowerCase(), P); }
const cl = (await j(A, "/clientes"))[1], ca = cl.find(c => c.codigo === X1.codigo), cb = cl.find(c => c.codigo === X2.codigo);
const infs = (await j(A, "/informes"))[1]; const iu = infs.find(i => i.cliente.codigo === X1.codigo), ic = infs.find(i => i.cliente.codigo === X2.codigo);
const tot = async (i) => (await j(A, "/informes/" + i.id))[1].metricas.servicios.SOC.periodos.map(p => p.total).join("/");
const M = { motivo: "Registrado por error en la prueba" }; let s, r;

// --- caso importado dentro del periodo actual del informe
const per = (await j(A, "/informes/" + iu.id))[1].metricas.servicios.SOC.periodos[2];
const k = (await j(A, `/casos?cliente_id=${ca.id}&servicio=SOC&desde=${per.inicio}&hasta=${per.fin}&tamano=1`))[1].items[0];
const tablero = async () => (await j(A, `/tablero?cliente_id=${ca.id}&servicio=SOC&desde=${per.inicio}&hasta=${per.fin}`))[1];
const lista = async (x = "") => (await j(A, `/casos?cliente_id=${ca.id}&servicio=SOC&desde=${per.inicio}&hasta=${per.fin}&tamano=1${x}`))[1].total;
ver("antes", await tot(iu) === T1 && await lista() === N1, await tot(iu));
for (const x of ["N1", "CISO"]) for (const a of ["anular", "restaurar"]) ver(`${x} no puede ${a}`, (await j(T[x], `/casos/${k.id}/${a}`, "POST", M))[0] === 403);
ver("sin sesión", (await fetch(`${B}/casos/${k.id}/anular`, { method: "POST" })).status === 401);
for (const m of [{}, { motivo: "corto" }, { motivo: "          .          " }, { motivo: "x".repeat(501) }]) ver("exige motivo", (await j(T.N2, `/casos/${k.id}/anular`, "POST", m))[0] === 422);
ver("restaurar uno vigente", (await j(T.N2, `/casos/${k.id}/restaurar`, "POST", M))[0] === 409); ver("inexistente", (await j(T.N2, "/casos/999999/anular", "POST", M))[0] === 404);
// segundo informe final antes de anular
await j(A, `/informes/${ic.id}/estado`, "POST", { estado: "FINAL" }); const pc = (await j(A, "/informes/" + ic.id))[1].metricas.servicios.SOC.periodos[2];
const kc = (await j(A, `/casos?cliente_id=${cb.id}&servicio=SOC&desde=${pc.inicio}&hasta=${pc.fin}&tamano=1`))[1].items[0];

[s, r] = await j(T.N2, `/casos/${k.id}/anular`, "POST", M); ver("N2 anula", s === 200 && r.anulado_en && r.anulado_por === "Anula N2" && r.anulado_motivo === M.motivo && r.numero === k.numero, r);
ver("nota: regenerar borrador", r.seguimientos.some(x => x.tipo === "anulacion" && x.comentario.includes("Regenere los textos") && x.comentario.includes(M.motivo)), r.seguimientos?.at(-1));
ver("anular dos veces", (await j(T.N2, `/casos/${k.id}/anular`, "POST", M))[0] === 409);
ver("informe, lista y tablero bajan", await tot(iu) === menos(X1.totales) && await lista() === N1 - 1 && (await tablero()).indicadores.total === N1 - 1, [await tot(iu), await lista()]);
const t = await tablero(); ver("tablero cuadra por todos lados", t.por_dia.reduce((x, d) => x + d["Crítica"] + d.Alta + d.Media + d.Baja + d.Sin, 0) === N1 - 1 && t.por_analista.reduce((x, a) => x + a.total, 0) + t.sin_analista === N1 - 1 && t.por_hora.reduce((x, h) => x + h.total, 0) === N1 - 1 && Object.values(t.por_estado).reduce((a, b) => a + b, 0) === N1 - 1);
ver("filtros incluir y solo", await lista("&anulados=incluir") === N1 && await lista("&anulados=solo") === 1);
r = (await j(A, `/casos?q=${k.numero.toLowerCase()}`))[1]; ver("número exacto lo encuentra", r.items.some(x => x.id === k.id && x.anulado_en), r.total);
ver("por texto no aparece", !(await j(A, `/casos?q=${encodeURIComponent(k.alerta)}&tamano=200`))[1].items.some(x => x.id === k.id));
ver("todos lo ven en detalle", (await j(T.CISO, "/casos/" + k.id))[1].anulado_motivo === M.motivo);
for (const x of ["docx", "presentacion"]) { const q = await fetch(`${B}/informes/${iu.id}/${x}`, { headers: { Authorization: "Bearer " + A } }); ver("informe " + x, q.status === 200 && (await q.arrayBuffer()).byteLength > 50000); }
// final congelado
[s, r] = await j(T.LIDER, `/casos/${kc.id}/anular`, "POST", M); ver("nota: informe final no cambia", s === 200 && r.seguimientos.some(x => x.comentario.includes("No cambia el informe final")), r.seguimientos?.at(-1));
ver("final congelado", await tot(ic) === T2, await tot(ic));
await j(A, `/informes/${ic.id}/estado`, "POST", { estado: "BORRADOR" }); ver("al volver a borrador sí baja", await tot(ic) === menos(X2.totales), await tot(ic));

// --- bloqueos sobre el anulado
const caso = { servicio: "SOC", cliente_id: ca.id, alerta: "Prueba anular única", criticidad: "Alta", resumen_ejecutivo: "r", analisis: "a", acciones_recomendadas: "x", fecha_evento: new Date(Date.now() - 600e3).toISOString() };
const res0 = (await j(A, "/casos/resumen"))[1], p0 = (await j(T.N2, "/casos/pendientes"))[1].por_revisar;
const v = (await j(T.N1, "/casos", "POST", caso))[1];
const res1 = (await j(A, "/casos/resumen"))[1]; ver("cuenta al crear", res1.hoy === res0.hoy + 1 && (await j(T.N2, "/casos/pendientes"))[1].por_revisar === p0 + 1);
ver("similares lo muestra", (await j(T.N1, `/casos/similares?cliente_id=${ca.id}&alerta=${encodeURIComponent(caso.alerta)}`))[1].length === 1);
ver("N1 no anula ni el propio", (await j(T.N1, `/casos/${v.id}/anular`, "POST", M))[0] === 403);
[s] = await j(T.N3, `/casos/${v.id}/anular`, "POST", M); ver("N3 anula", s === 200);
const res2 = (await j(A, "/casos/resumen"))[1]; for (const c of ["hoy", "ultimos_30", "fuera_sla_30", "mediana_minutos_30", "por_estado_30", "por_cliente_30"]) ver("inicio vuelve: " + c, JSON.stringify(res2[c]) === JSON.stringify(res0[c]), [res0[c], res2[c]]);
ver("sale de por revisar", (await j(T.N2, "/casos/pendientes"))[1].por_revisar === p0);
ver("sale de similares", (await j(T.N1, `/casos/similares?cliente_id=${ca.id}&alerta=${encodeURIComponent(caso.alerta)}`))[1].length === 0);
ver("no edita", (await j(A, `/casos/${v.id}`, "PUT", { ...caso, estado: "CERRADO" }))[0] === 409); ver("no revisa", (await j(T.N2, `/casos/${v.id}/revision`, "POST", { resultado: "REVISADO" }))[0] === 409);
ver("no correo", (await j(A, `/casos/${v.id}/correo`))[0] === 409 && (await j(A, `/casos/${v.id}/correo.eml?confirmar=true`, "POST"))[0] === 409);
ver("no ticket", (await j(A, `/casos/${v.id}/glpi`, "POST"))[0] === 409);
const fd = new FormData(); fd.append("archivos", new Blob(["x"]), "x.txt"); fd.append("tipo", "ADJUNTO"); ver("no adjunta", (await fetch(`${B}/casos/${v.id}/adjuntos`, { method: "POST", headers: { Authorization: "Bearer " + A }, body: fd })).status === 409);
ver("sí comenta", (await j(T.N1, `/casos/${v.id}/seguimientos`, "POST", { comentario: "nota interna" }))[0] === 201); ver("no publica en GLPI", (await j(T.N1, `/casos/${v.id}/seguimientos`, "POST", { comentario: "x", publicar_glpi: true }))[0] === 409);
ver("otro N1 sigue sin comentar", (await j(T.CISO, `/casos/${v.id}/seguimientos`, "POST", { comentario: "x" }))[0] === 403);
const sig = (await j(T.N1, "/casos", "POST", caso))[1]; ver("no reutiliza el número", Number(sig.numero.slice(2)) === Number(v.numero.slice(2)) + 1, [v.numero, sig.numero]);

// --- importación
const up = new FormData(); up.append("archivo", new Blob([fs.readFileSync(XLSX)]), "b.xlsx"); const ar = await (await fetch(B + "/importaciones/archivo", { method: "POST", headers: { Authorization: "Bearer " + A }, body: up })).json();
const imp = (modo) => j(A, "/importaciones", "POST", { archivo_id: ar.archivo_id, hoja: "BITACORA", modo, simular: false, cargar_catalogos: false });
[s, r] = await imp("reemplazar"); ver("reemplazar bloqueado", s === 422 && r.detail.includes("anulados"), r.detail);
[s, r] = await imp("actualizar"); ver("actualizar conserva la anulación", s === 200 && (await j(A, "/casos/" + k.id))[1].anulado_en && await tot(iu) === menos(X1.totales), r.resumen);

// --- restaurar
[s, r] = await j(T.N2, `/casos/${v.id}/restaurar`, "POST", { motivo: "Se anuló por equivocación" }); ver("restaura y vuelve a por revisar", s === 200 && !r.anulado_en && !r.anulado_motivo && r.revision === "PENDIENTE" && r.seguimientos.some(x => x.comentario.startsWith("Caso restaurado")), r);
ver("se puede editar otra vez", (await j(T.N1, `/casos/${v.id}`, "PUT", caso))[0] === 200);
for (const x of [k, kc]) await j(A, `/casos/${x.id}/restaurar`, "POST", { motivo: "Fin de la prueba de anulación" });
ver("cifras originales", await tot(iu) === T1 && await tot(ic) === T2 && await lista() === N1, [await tot(iu), await tot(ic)]);
r = (await j(A, "/usuarios/cambios?q=" + k.numero))[1]; ver("registro de cambios", r.items.some(i => i.accion === "anular" && i.detalle.includes(M.motivo)) && r.items.some(i => i.accion === "restaurar"), r);
// deja un caso anulado para ver la pantalla
await j(T.N2, `/casos/${sig.id}/anular`, "POST", { motivo: "Duplicado de " + v.numero });
console.log(f ? `FALLOS ${f} de ${n}` : `TODO BIEN: ${n} comprobaciones`, "caso", v.id, sig.id);
