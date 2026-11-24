// Requiere e2e.mjs antes (informes de los dos clientes de control en borrador)
import fs from "fs";
import { execFileSync } from "child_process";
import CT from "./control.mjs";
const [X1, X2] = CT.clientes, T1 = X1.totales.join("/"), T2 = X2.totales.join("/"), menos = (t) => [...t.slice(0, 2), t[2] - 1].join("/"), N1 = X1.totales[2];
const [puerto, env, S, SAL] = process.argv.slice(2); const B = `http://127.0.0.1:${puerto}/api`;
const pw = /^ADMIN_PASSWORD=(.*)$/m.exec(fs.readFileSync(env, "utf8"))[1].trim(), P = "Prueba-local-123";
const ent = async (u, p) => (await (await fetch(B + "/auth/login", { method: "POST", body: new URLSearchParams({ username: u, password: p }) })).json()).access_token;
const j = async (t, u, m = "GET", d) => { const r = await fetch(B + u, { method: m, headers: { Authorization: "Bearer " + t, ...(d ? { "Content-Type": "application/json" } : {}) }, body: d ? JSON.stringify(d) : undefined }); return [r.status, await r.json().catch(() => null)]; };
const img = async (t, u, f, m = "POST", nombre = f) => { const fd = new FormData(); fd.append("archivo", new Blob([typeof f === "string" ? fs.readFileSync(`${S}/archivos/${f}`) : f]), typeof nombre === "string" ? nombre : "x.png"); const r = await fetch(B + u, { method: m, headers: { Authorization: "Bearer " + t }, body: fd }); return [r.status, await r.json().catch(() => null)]; };
const raw = async (t, u) => { const r = await fetch(B + u, { headers: t ? { Authorization: "Bearer " + t } : {} }); return [r.status, Buffer.from(await r.arrayBuffer()), r.headers]; };
let f = 0, n = 0; const ver = (t, ok, x = "") => { n++; if (!ok) { f++; console.log("  [X] ", t, JSON.stringify(x)?.slice(0, 300)); } };
const A = await ent("admin", pw), T = {};
for (const r of ["N1", "N2", "LIDER", "CISO"]) { await j(A, "/usuarios", "POST", { usuario: "q." + r.toLowerCase(), nombre: "Pres " + r, rol: r, password: P }); T[r] = await ent("q." + r.toLowerCase(), P); }
const cl = (await j(A, "/clientes"))[1], ca = cl.find(c => c.codigo === X1.codigo); const infs = (await j(A, "/informes"))[1], iu = infs.find(i => i.cliente.codigo === X1.codigo), ic = infs.find(i => i.cliente.codigo === X2.codigo);
let s, r, b, h; const L = `/clientes/${ca.id}/logo`;
// ---------- logo
ver("sin logo", !ca.tiene_logo && (await raw(A, L))[0] === 404);
for (const x of ["N1", "N2", "CISO"]) ver(x + " no carga logo", (await img(T[x], L, "logo_oscuro.png", "PUT"))[0] === 403);
[s, r] = await img(T.LIDER, L, "logo_oscuro.png", "PUT"); ver("líder carga logo", s === 200 && r.tiene_logo && r.logo_claro === false, r);
[s, b, h] = await raw(T.CISO, L); ver("todos ven el logo", s === 200 && h.get("content-type") === "image/png" && h.get("content-security-policy").includes("sandbox"));
ver("recorta bordes vacíos", b.readUInt32BE(16) <= 900 && b.readUInt32BE(16) / b.readUInt32BE(20) > 3, [b.readUInt32BE(16), b.readUInt32BE(20)]);
ver("sin sesión no", (await raw(null, L))[0] === 401);
[s, r] = await img(A, L, "logo_blanco.png", "PUT"); ver("detecta logo blanco", r.logo_claro === true, r);
[s, r] = await img(A, L, "logo.jpg", "PUT"); ver("jpg", s === 200 && r.logo_claro === false); [s, b] = await raw(A, L); ver("sin metadatos", !b.includes("DATO PRIVADO"));
for (const [d, x, nom] of [["svg", Buffer.from("<svg/>"), "x.svg"], ["pdf", Buffer.from("%PDF-1.4"), "x.pdf"], ["texto", Buffer.from("hola"), "x.png"], ["muy pequeño", "mini.png", "mini.png"], ["grande", Buffer.alloc(6e6, 1), "x.png"]]) { [s, r] = await img(A, L, x, "PUT", nom); ver("rechaza " + d, s === 422, [s, r]); }
ver("rechazo no borra el actual", (await raw(A, L))[0] === 200);
ver("editar cliente conserva logo", (await j(A, "/clientes/" + ca.id, "PUT", { codigo: X1.codigo, nombre: ca.nombre, dia_corte: ca.dia_corte, eps_contratados: ca.eps_contratados, fuentes_licencia: ca.fuentes_licencia }))[1].tiene_logo === true);
ver("lista no trae el contenido", JSON.stringify((await j(A, "/clientes"))[1]).length < 20000);
// ---------- boletines
const I = `/informes/${iu.id}`, det = (await j(A, I))[1];
const guardar = (t, bol) => j(t, I, "PUT", { eps_promedio: det.eps_promedio, fuentes_integradas: det.fuentes_integradas, boletines_enviados: det.boletines_enviados, boletines: bol, textos: {} });
for (const x of ["N1", "CISO"]) ver(x + " no carga imagen", (await img(T[x], I + "/imagenes", "boletin_v.png"))[0] === 403);
const v = (await img(T.N2, I + "/imagenes", "boletin_v.png"))[1], hh = (await img(T.N2, I + "/imagenes", "boletin_h.jpg"))[1]; ver("N2 carga imágenes", v?.id && hh?.id, [v, hh]);
[s, b] = await raw(T.CISO, `${I}/imagenes/${v.id}`); ver("se reduce a 2000 px", s === 200 && b.readUInt32BE(20) === 2000, b.readUInt32BE(20));
ver("N1 no la ve", (await raw(T.N1, `${I}/imagenes/${v.id}`))[0] === 403); ver("no se cruza entre informes", (await raw(A, `/informes/${ic.id}/imagenes/${v.id}`))[0] === 404);
ver("rechaza archivo no imagen", (await img(A, I + "/imagenes", Buffer.from("MZ"), "POST", "x.png"))[0] === 422);
const bol = [{ nombre: "Amenaza <script>alert(1)</script> & Cía", tipo: "Ransomware", fecha: "2026-10-05", resumen: "Texto\n\nSegundo párrafo", imagen_id: v.id }, { nombre: "Segundo boletín", tipo: null, fecha: null, resumen: "y", imagen_id: hh.id }, { nombre: "Sin imagen", resumen: "z" }];
[s, r] = await guardar(T.N2, bol); ver("guarda con imágenes", s === 200 && r.boletines[0].imagen_id === v.id, r);
ver("imagen ajena", (await j(A, `/informes/${ic.id}`, "PUT", { boletines: [{ nombre: "xxxx", imagen_id: v.id }], textos: {} }))[0] === 422);
// ---------- presentación
let [st, html, hd] = await raw(T.CISO, I + "/presentacion"); let t = html.toString(); ver("CISO ve presentación", st === 200 && t.includes('id="b-pdf"') && t.includes("--cli"));
ver("escapa el HTML", !t.includes("<script>alert(1)") && t.includes("&lt;script&gt;alert(1)"));
ver("boletines e imágenes", (t.match(/<div class="bol[" ]/g) || []).length === 3 && (t.match(/<div class="img"><img/g) || []).length === 2 && t.includes("05/10/2026"));
ver("sin recursos externos salvo el mapa", [...t.matchAll(/(?:src|href)="(https?:[^"]+)"/g)].length === 0 && !t.includes("fonts.googleapis"), [...t.matchAll(/(?:src|href)="(https?:[^"]+)"/g)].map(x => x[1]));
const D = JSON.parse(/id="datos">(.*?)<\/script>/s.exec(t)[1]); ver("mapa con ubicaciones", D.mapa.entrantes.length > 5 && D.mapa.entrantes.every(p => Math.abs(p.lat) < 80 && Math.abs(p.lon) <= 180) && !D.mapa.sin.entrantes.length && !D.mapa.sin.salientes.length, D.mapa.sin);
ver("sin datos de sesión dentro", !t.includes(A.slice(0, 30)));
[st, html, hd] = await raw(T.CISO, I + "/presentacion?descargar=true"); t = html.toString(); ver("HTML descargable", st === 200 && /attachment; filename="Presentacion_.*\.html"/.test(hd.get("content-disposition")) && !t.includes('id="b-pdf"'), hd.get("content-disposition"));
ver("N1 no la ve", (await raw(T.N1, I + "/presentacion"))[0] === 403);
const t0 = Date.now(); [st, b] = await raw(A, I + "/presentacion.pdf"); ver("PDF", st === 200 && b.subarray(0, 4).toString() === "%PDF" && b.length > 400000, [st, b.length]); console.log("   PDF", (b.length / 1e6).toFixed(1), "MB", ((Date.now() - t0) / 1000).toFixed(1), "s"); fs.writeFileSync(SAL + "/presentacion.pdf", b);
// ---------- presentación ejecutiva
const E = I + "/presentacion?estilo=ejecutiva"; const salvar = (x) => j(T.N2, I, "PUT", { boletines: bol, textos: {}, ...x });
const act = [{ frente: "SIEM", actividad: "Integrar <b>firewall</b>", responsable: "CLIENTE", avance: 40, compromiso: "2026-12-10" }, { frente: "SIEM", actividad: "Terminada", responsable: "WX", avance: 100 }, { frente: "Casos de uso", actividad: "Sin iniciar", responsable: "AMBOS", avance: 0, compromiso: null }];
for (const [d, x] of [["avance 101", { avance: 101 }], ["avance negativo", { avance: -1 }], ["responsable", { responsable: "OTRO" }], ["sin actividad", { actividad: "" }]]) ver("actividad rechaza " + d, (await salvar({ actividades: [{ ...act[0], ...x }] }))[0] === 422);
[s, r] = await salvar({ actividades: act }); ver("guarda actividades", s === 200 && r.actividades.length === 3, r); [s, r] = await salvar({}); ver("guardar sin actividades las conserva", r.actividades.length === 3);
ver("estilo inválido", (await raw(A, I + "/presentacion?estilo=otro"))[0] === 422); ver("N1 no ve la ejecutiva", (await raw(T.N1, E))[0] === 403 && (await raw(T.N1, I + "/presentacion.pdf?estilo=ejecutiva"))[0] === 403);
[st, html] = await raw(T.CISO, E); t = html.toString(); ver("CISO ve la ejecutiva", st === 200 && t.includes("Informe ejecutivo") && t.includes("--cli") && t.includes('id="b-pdf"'));
const met = (await j(A, I))[1].metricas.servicios.SOC, de = met.detalle, tot = met.periodos[2].total; ver("detalle cuadra con el total", tot === X1.totales[2] && de.por_dia.reduce((a, x) => a + x.total, 0) === tot && de.por_semana.reduce((a, b) => a + b, 0) === tot && de.casos.length === tot && de.casos_total === tot && de.tiempos.reduce((a, x) => a + x.total, 0) === met.periodos[2].con_tiempo, [tot, de.casos.length]);
ver("pendientes cuadran", de.sin_respuesta.length === Math.min(60, met.periodos[2].sin_retro)); ver("tiempos cuadran con el objetivo", de.tiempos.slice(0, 3).reduce((a, x) => a + x.total, 0) === met.periodos[2].dentro_sla, [de.tiempos, met.periodos[2].dentro_sla]);
const anexo = t.slice(t.indexOf("Detalle de eventos SOC")); ver("anexo con todos los eventos", de.casos.every(x => anexo.includes(`>${x.numero}<`)));
ver("escapa actividades", !t.includes("<b>firewall</b>") && t.includes("&lt;b&gt;firewall")); ver("avance y responsables", t.includes("47 %") && t.includes("1 de 3") && t.includes(">" + X1.codigo + "<"), t.match(/avance global/g));
ver("sin recursos externos", [...t.matchAll(/(?:src|href)="(https?:[^"]+)"/g)].length === 0);
[st, html, hd] = await raw(A, E + "&descargar=true"); ver("HTML ejecutivo", /Informe_ejecutivo_.*\.html/.test(hd.get("content-disposition")) && !html.toString().includes('id="b-pdf"'), hd.get("content-disposition"));
[st, b, hd] = await raw(A, I + "/presentacion.pdf?estilo=ejecutiva"); ver("PDF ejecutivo", st === 200 && b.subarray(0, 4).toString() === "%PDF" && /Informe_ejecutivo_/.test(hd.get("content-disposition")), [st, b.length]); console.log("   PDF ejecutivo", (b.length / 1e6).toFixed(1), "MB");
const docx = async () => execFileSync("docker", ["exec", "-i", "soc-prueba-api-1", "python", "-c", "import sys,io,docx;d=docx.Document(io.BytesIO(sys.stdin.buffer.read()));sys.stdout.buffer.write('\\n'.join(p.text for p in d.paragraphs).encode())"], { input: (await raw(A, I + "/docx"))[1], maxBuffer: 1e8 }).toString(); const TX = "tiempo mediano entre";
let w = await docx(); ver("Word sin tiempos por defecto", w.length > 2000 && !w.includes(TX) && !/dentro del objetivo/.test(w)); ver("el texto se conserva en el informe", (await j(A, I))[1].textos.tiempos_SOC.includes(TX));
ver("tiempos ocultos por defecto", !t.includes("Tiempo de notificación") && !t.includes(">en objetivo<")); await salvar({ textos: { gestion: "Notificación SOC: mediana de 1 minutos\nOtra" } }); t = (await raw(A, E))[1].toString(); ver("filtra la línea de tiempos", !t.includes("mediana de 1 minutos") && t.includes("<li>Otra</li>"));
await j(A, "/config/general", "PUT", { valores: { mostrar_tiempos: true } }); await j(A, I + "/textos/regenerar", "POST", { claves: ["gestion"] }); t = (await raw(A, E))[1].toString(); ver("se pueden activar", t.includes("Tiempo de notificación") && t.includes("dentro del objetivo")); ver("Word con tiempos al activar", (await docx()).includes(TX));
await j(A, I + "/estado", "POST", { estado: "FINAL" }); await j(A, "/config/general/restablecer", "POST"); ver("final conserva lo que tenía", (await docx()).includes(TX) && (await raw(A, E))[1].toString().includes("Tiempo de notificación"));
await j(A, I + "/estado", "POST", { estado: "BORRADOR" }); ver("al volver a borrador se ocultan", !(await docx()).includes(TX)); await j(A, I + "/estado", "POST", { estado: "FINAL" }); await j(A, "/config/general", "PUT", { valores: { mostrar_tiempos: true } }); ver("final oculto no los muestra después", !(await docx()).includes(TX));
await j(A, I + "/estado", "POST", { estado: "BORRADOR" });
const tt = (await j(A, I))[1].textos; ver("gestión automática", tt.gestion.includes("eventos escalados")); await salvar({ textos: { tiempos_SOC: "", gestion: "Solo esta línea" } }); t = (await raw(A, E))[1].toString(); ver("sin texto no muestra tiempos; gestión editable", !t.includes("Tiempo de notificación") && t.includes("<li>Solo esta línea</li>")); await salvar({ textos: { tiempos_SOC: tt.tiempos_SOC, gestion: tt.gestion } }); await j(A, "/config/general/restablecer", "POST");
const [sn, sig] = await j(A, "/informes", "POST", { cliente_id: ca.id, anio: X1.mes === 12 ? X1.anio + 1 : X1.anio, mes: X1.mes % 12 + 1 }); ver("pasan las actividades sin terminar", sn === 201 && sig.actividades.length === 2 && !sig.actividades.some(x => x.avance === 100), sig?.actividades); await j(A, `/informes/${sig.id}`, "DELETE");
// ---------- limpieza y final
[s] = await guardar(A, [{ ...bol[0] }]); ver("borra las imágenes que ya no se usan", s === 200 && (await raw(A, `${I}/imagenes/${hh.id}`))[0] === 404 && (await raw(A, `${I}/imagenes/${v.id}`))[0] === 200);
[s, r] = await guardar(A, bol); ver("imagen borrada avisa", s === 422 && r.detail.includes("de nuevo"), r);
await j(A, I + "/estado", "POST", { estado: "FINAL" }); ver("final no admite imágenes", (await img(A, I + "/imagenes", "boletin_v.png"))[0] === 409 && (await raw(A, I + "/presentacion"))[0] === 200);
await j(A, I + "/estado", "POST", { estado: "BORRADOR" });
ver("quita logo", (await j(T.LIDER, L, "DELETE"))[1].tiene_logo === false && !(await raw(A, I + "/presentacion"))[1].toString().includes("--cli:"));
r = JSON.stringify((await j(A, "/usuarios/cambios?q=logo"))[1]); ver("registro de cambios", r.includes("logo cargado") && r.includes("logo reemplazado") && r.includes("logo eliminado"));
// informe sin anexos ni boletines, y eliminar informe con imágenes
const ot = cl.find(c => c.codigo === CT.sin_anexos); const [s2, i2] = await j(A, "/informes", "POST", { cliente_id: ot.id, anio: 2026, mes: 10 }); ver("informe sin anexos", s2 === 201 && (await raw(A, `/informes/${i2.id}/presentacion`))[0] === 200 && (await raw(A, `/informes/${i2.id}/presentacion.pdf`))[0] === 200);
await img(A, `/informes/${i2.id}/imagenes`, "boletin_h.jpg"); ver("elimina informe con imágenes", (await j(A, `/informes/${i2.id}`, "DELETE"))[0] === 204);
await img(A, L, "logo_oscuro.png", "PUT"); await guardar(A, [{ nombre: "Boletín de prueba", tipo: "Ransomware", fecha: "2026-10-05", resumen: "Resumen de prueba. ".repeat(30), imagen_id: (await img(A, I + "/imagenes", "boletin_v.png"))[1].id }, { nombre: "Segundo boletín", tipo: "Phishing", fecha: "2026-10-12", resumen: "Impacto y medidas. ".repeat(20), imagen_id: (await img(A, I + "/imagenes", "boletin_h.jpg"))[1].id }]);
console.log(f ? `FALLOS ${f} de ${n}` : `TODO BIEN: ${n} comprobaciones`, "informe", iu.id);
