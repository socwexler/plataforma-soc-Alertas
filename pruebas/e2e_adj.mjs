import fs from "fs";
const [puerto, env, S, SAL] = process.argv.slice(2); const B = `http://127.0.0.1:${puerto}/api`;
const pw = /^ADMIN_PASSWORD=(.*)$/m.exec(fs.readFileSync(env, "utf8"))[1].trim();
const ent = async (u, p) => (await (await fetch(B + "/auth/login", { method: "POST", body: new URLSearchParams({ username: u, password: p }) })).json()).access_token;
const j = async (t, u, m = "GET", d) => { const r = await fetch(B + u, { method: m, headers: { Authorization: "Bearer " + t, ...(d ? { "Content-Type": "application/json" } : {}) }, body: d ? JSON.stringify(d) : undefined }); return [r.status, await r.json().catch(() => null)]; };
let f = 0, n = 0; const ver = (t, ok, x = "") => { n++; if (!ok) { f++; console.log("  [X] ", t, typeof x === "string" ? x : JSON.stringify(x)); } };
const A = await ent("admin", pw), T = {};
for (const r of ["N1", "N2", "CISO"]) { await j(A, "/usuarios", "POST", { usuario: "a." + r.toLowerCase(), nombre: "Adj " + r, rol: r, password: "Prueba-local-123" }); T[r] = await ent("a." + r.toLowerCase(), "Prueba-local-123"); }
const cl = async (codigo, d) => { const c = (await j(A, "/clientes", "POST", { codigo, nombre: "Cliente " + codigo }))[1]; await j(A, `/clientes/${c.id}/correos`, "PUT", { dominios: d, para: "x@" + d, cc: "" }); return c; };
const a = await cl("AQA", "aqa.example"), b = await cl("BQB", "bqb.example");
const caso = { servicio: "SOC", cliente_id: a.id, alerta: "Prueba adjuntos", criticidad: "Alta", resumen_ejecutivo: "r", analisis: "a", acciones_recomendadas: "x", fecha_evento: new Date(Date.now() - 600e3).toISOString() };
const c1 = (await j(T.N1, "/casos", "POST", caso))[1], c2 = (await j(T.N2, "/casos", "POST", caso))[1];
const img = fs.readFileSync(S + "/banner_prueba.png");
const subir = async (t, id, lista, tipo = "ADJUNTO") => { const fd = new FormData(); lista.forEach(([nom, d]) => fd.append("archivos", new Blob([d]), nom)); fd.append("tipo", tipo); const r = await fetch(`${B}/casos/${id}/adjuntos`, { method: "POST", headers: { Authorization: "Bearer " + t }, body: fd }); return [r.status, await r.json().catch(() => null)]; };
const zip = fs.readFileSync(S + "/archivos/malo.zip"), zipok = fs.readFileSync(S + "/archivos/bueno.zip"), docm = fs.readFileSync(S + "/archivos/macro.docx"), docx = fs.readFileSync(S + "/archivos/ok.docx"), jpg = fs.readFileSync(S + "/archivos/gps.jpg");

let [s, r] = await subir(T.N1, c1.id, [["captura.png", img]], "EVIDENCIA"); ver("sube evidencia", s === 201 && r.adjuntos.length === 1 && r.adjuntos[0].tipo === "EVIDENCIA", [s, r?.detail]);
ver("la lista no trae el contenido", !JSON.stringify(r).includes("contenido"));
[s, r] = await subir(T.N1, c1.id, [["detalle ñandú.csv", "ip,total\n10.0.0.1,5\n"], ["informe.pdf", "%PDF-1.4 prueba"], ["doc.docx", docx], ["logs.zip", zipok]]); ver("sube varios adjuntos", s === 201 && r.adjuntos.length === 5, [s, r?.detail]);
for (const [d, lista, tipo] of [["exe", [["virus.exe", "MZ"]]], ["exe disfrazado de pdf", [["x.pdf", "MZ\x90"]]], ["exe disfrazado de png", [["x.png", "MZ"]]], ["jpg con nombre png", [["x.png", jpg]]], ["html", [["x.html", "<script>"]]], ["svg", [["x.svg", "<svg>"]]], ["docm", [["x.docm", docm]]], ["docx con macros", [["x.docx", docm]]], ["zip con exe", [["x.zip", zip]]], ["zip dañado", [["x.zip", "PK123"]]], ["binario como txt", [["x.txt", new Uint8Array([77, 0, 1])]]], ["vacío", [["x.txt", ""]]], ["sin extensión", [["nombre", "x"]]], ["pdf como evidencia", [["x.pdf", "%PDF-1.4"]], "EVIDENCIA"], ["demasiado grande", [["x.txt", "a".repeat(15 * 1048576 + 1)]]], ["repetido", [["otro.png", img]], "EVIDENCIA"], ["tipo inventado", [["x.txt", "x"]], "OTRO"]]) { [s, r] = await subir(T.N1, c1.id, lista, tipo); ver("rechaza " + d, s === 422, [s, r?.detail ?? "aceptado"]); }
[s] = await subir(T.N1, c1.id, [["bien.txt", "hola"], ["mal.exe", "MZ"]]); ver("todo o nada", s === 422 && (await j(T.N1, "/casos/" + c1.id))[1].adjuntos.length === 5);
[s, r] = await subir(T.N2, c2.id, [["../../etc/passwd.txt", "x"], ["a‮gnp.txt", "y"]]); ver("limpia nombres", s === 201 && r.adjuntos.map(x => x.nombre).join() === "passwd.txt,agnp.txt", r?.adjuntos?.map(x => x.nombre));
ver("N1 no sube a caso ajeno", (await subir(T.N1, c2.id, [["x.txt", "x"]]))[0] === 403); ver("CISO no sube", (await subir(T.CISO, c1.id, [["x.txt", "x"]]))[0] === 403);
let c = (await j(T.N1, "/casos/" + c1.id))[1]; const de = x => c.adjuntos.find(y => y.nombre.endsWith(x));
const baja = async (t, id, aid) => fetch(`${B}/casos/${id}/adjuntos/${aid}`, { headers: t ? { Authorization: "Bearer " + t } : {} });
const q = await baja(T.CISO, c1.id, de(".csv").id), tx = await q.text(); ver("CISO descarga", q.status === 200 && tx.startsWith("ip,total") && q.headers.get("content-disposition").startsWith("attachment") && (q.headers.get("content-security-policy") || "").includes("sandbox"));
ver("sin sesión no descarga", (await baja(null, c1.id, de(".csv").id)).status === 401); ver("no se cruza entre casos", (await baja(T.N2, c2.id, de(".csv").id)).status === 404);
ver("N1 no quita de caso ajeno", (await j(T.N1, `/casos/${c2.id}/adjuntos/${(await j(T.N2, "/casos/" + c2.id))[1].adjuntos[0].id}`, "DELETE"))[0] === 403);
// correo
[s, r] = await j(T.N1, `/casos/${c1.id}/correo`); ver("correo lista archivos", r.archivos.length === 5 && !r.bloqueos.length && !r.advertencias.length && r.html.includes("data:image/png;base64") && r.html.split("data:image").length === 4, [r.bloqueos, r.advertencias]);
await j(T.N1, `/casos/${c1.id}/adjuntos/${de(".zip").id}`, "PATCH", { incluir: false });
const e = await fetch(`${B}/casos/${c1.id}/correo.eml`, { method: "POST", headers: { Authorization: "Bearer " + T.N1 } }); fs.writeFileSync(SAL + "/adj.eml", Buffer.from(await e.arrayBuffer())); ver("genera borrador", e.status === 200, e.status);
c = (await j(T.N1, "/casos/" + c1.id))[1]; ver("nota con archivos", c.seguimientos.some(x => x.tipo === "correo" && x.comentario.includes("informe.pdf") && !x.comentario.includes("logs.zip")));
await subir(T.N1, c1.id, [["reporte_BQB.txt", "nada"], ["lista.log", "user@bqb.example"]]); r = (await j(T.N1, `/casos/${c1.id}/correo`))[1]; ver("avisa archivo de otro cliente", r.advertencias.filter(x => x.includes("BQB")).length === 2, r.advertencias);
[s] = await subir(T.N2, c2.id, [["g1.log", "a".repeat(9e6)], ["g2.log", "b".repeat(9e6)]]); r = (await j(T.N2, `/casos/${c2.id}/correo`))[1]; ver("bloquea correo muy pesado", s === 201 && r.bloqueos.some(x => x.includes("MB")), r.bloqueos);
for (let i = 0; i < 4; i++) s = (await subir(T.N2, c2.id, [[`h${i}.log`, String(i).repeat(14e6)]]))[0]; ver("límite por caso", s === 422, s);
// revisión
await j(T.N2, `/casos/${c1.id}/revision`, "POST", { resultado: "REVISADO" }); await j(T.N1, `/casos/${c1.id}/adjuntos/${de(".pdf").id}`, "DELETE"); c = (await j(T.N1, "/casos/" + c1.id))[1];
ver("quitar archivo vuelve a por revisar y queda registrado", c.revision === "PENDIENTE" && c.seguimientos.some(x => x.comentario.startsWith("Archivo eliminado: informe.pdf")) && !c.adjuntos.some(x => x.nombre === "informe.pdf"));
console.log(f ? `FALLOS ${f} de ${n}` : `TODO BIEN: ${n} comprobaciones`);
