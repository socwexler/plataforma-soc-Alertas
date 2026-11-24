// Requiere el contenedor simulador (soc-prueba-sim) en la red de soc-prueba. Va de último: cambia la configuración.
import fs from "fs";
import CT from "./control.mjs";
const [X1, X2] = CT.clientes, T1 = X1.totales.join("/"), T2 = X2.totales.join("/"), menos = (t) => [...t.slice(0, 2), t[2] - 1].join("/"), N1 = X1.totales[2];
import { execFileSync } from "child_process";
const [puerto, env] = process.argv.slice(2); const B = `http://127.0.0.1:${puerto}/api`;
const pw = /^ADMIN_PASSWORD=(.*)$/m.exec(fs.readFileSync(env, "utf8"))[1].trim(), P = "Prueba-local-123";
const ent = async (u, p) => (await (await fetch(B + "/auth/login", { method: "POST", body: new URLSearchParams({ username: u, password: p }) })).json()).access_token;
const j = async (t, u, m = "GET", d) => { const r = await fetch(B + u, { method: m, headers: { Authorization: "Bearer " + t, ...(d ? { "Content-Type": "application/json" } : {}) }, body: d ? JSON.stringify(d) : undefined }); return [r.status, await r.json().catch(() => null)]; };
const dk = (...a) => execFileSync("docker", a, { encoding: "utf8" });
const sql = (q) => dk("exec", "soc-prueba-db-1", "sh", "-c", `psql -U $POSTGRES_USER -d $POSTGRES_DB -tAc "${q}"`).trim();
const py = (c) => dk("exec", "-e", "PYTHONPATH=/srv", "soc-prueba-api-1", "python", "-c", c).trim();
const sim = (r) => py(`import httpx;print(httpx.get('http://sim:9000${r}').text)`);
const S = (ms) => new Promise(r => setTimeout(r, ms));
let f = 0, n = 0; const ver = (t, ok, x = "") => { n++; if (!ok) { f++; console.log("  [X] ", t, JSON.stringify(x)?.slice(0, 300)); } };
const A = await ent("admin", pw), T = {};
for (const r of ["N1", "N2", "N3", "LIDER", "CISO"]) { await j(A, "/usuarios", "POST", { usuario: "g." + r.toLowerCase(), nombre: "Conf " + r, rol: r, password: P, email: `g.${r.toLowerCase()}@wexler.com.co` }); T[r] = await ent("g." + r.toLowerCase(), P); }
const put = (g, valores, borrar = [], t = T.LIDER) => j(t, "/config/" + g, "PUT", { valores, borrar });
const val = async (k) => (await j(A, "/config"))[1].flatMap(g => g.campos).find(c => c.clave === k);
let s, r;
// ---------- permisos
for (const x of ["N1", "N2", "N3", "CISO"]) for (const [u, m, d] of [["/config", "GET"], ["/config/general", "PUT", { valores: { sla_media: 5 } }], ["/config/glpi/restablecer", "POST"], ["/config/conexiones", "GET"], ["/config/conexiones", "POST", {}], ["/config/claves", "GET"], ["/config/claves", "POST", {}], ["/config/avisos", "GET"], ["/config/sistema", "GET"], ["/config/avisos/probar", "POST", { para: "x" }], ["/config/fortisiem/probar", "POST"], ["/glpi/probar", "POST"]]) ver(`${x} no ${m} ${u}`, (await j(T[x], u, m, d))[0] === 403);
ver("sin sesión", (await fetch(B + "/config")).status === 401);
[s, r] = await j(T.LIDER, "/config/sistema"); ver("estado del sistema", s === 200 && r.esquema >= "0011" && r.convertidor === true && r.casos > 0, r);
// ---------- general
const sla0 = (await val("sla_media")).valor;
[s, r] = await put("general", { sla_media: 45, jwt_horas: 8 }); ver("guarda", s === 200 && (await val("sla_media")).valor === 45 && (await val("sla_media")).origen === "pantalla", r);
ver("se usa de inmediato", (await j(A, "/casos/resumen"))[1].sla.Media === 45);
for (const v of [0, 1441, "abc", null, 1.5, true, -3]) ver("sla inválido " + v, (await put("general", { sla_media: v }))[0] === 422);
for (const [g, v] of [["nada", {}], ["general", { jwt_secret: "x" }], ["general", { smtp_clave: "x" }], ["general", { mapa_activo: "sí" }]]) ver("rechaza " + JSON.stringify([g, v]), (await put(g, v))[0] === 422);
ver("no se borra lo que no es secreto", (await put("general", {}, ["sla_media"]))[0] === 422);
for (const u of ["javascript:alert(1)", "http://a:b@x.com", "ftp://x", "http://", "http://x:99999"]) ver("url inválida " + u, (await put("general", { url_plataforma: u }))[0] === 422, u);
await put("general", { url_plataforma: "http://soc.interno:8080/" });
dk("restart", "soc-prueba-api-1"); for (let i = 0; i < 30; i++) { try { if ((await fetch(B + "/salud")).status === 200) break; } catch { /* iniciando */ } await S(1000); }
ver("persiste al reiniciar", (await val("sla_media")).valor === 45 && (await val("url_plataforma")).valor === "http://soc.interno:8080");
[s] = await j(T.LIDER, "/config/general/restablecer", "POST"); ver("restablece", s === 200 && (await val("sla_media")).valor === sla0 && (await val("sla_media")).origen !== "pantalla");
// ---------- SLA por criticidad
const OBJ = { "Crítica": 35, Alta: 45, Media: 120, Baja: 240 }; ver("SLA predeterminado", JSON.stringify((await j(A, "/casos/resumen"))[1].sla) === JSON.stringify(OBJ), (await j(A, "/casos/resumen"))[1].sla);
for (const [t, v] of [["crítica sobre alta", { sla_critica: 46 }], ["alta sobre media", { sla_alta: 121 }], ["media sobre baja", { sla_media: 241 }], ["baja bajo media", { sla_baja: 100 }]]) { [s, r] = await put("general", v); ver("orden del SLA: " + t, s === 422 && /no puede ser mayor/.test(r.detail), r); }
ver("sin cambios tras el rechazo", JSON.stringify((await j(A, "/casos/resumen"))[1].sla) === JSON.stringify(OBJ));
const cs = (await j(A, "/clientes", "POST", { codigo: "SLA", nombre: "Cliente SLA" }))[1], rep0 = Math.floor(Date.now() / 1000) * 1000 - 60e3;
for (const [crit, m] of Object.entries(OBJ)) for (const seg of [0, 1]) {
  [s, r] = await j(T.N2, "/casos", "POST", { servicio: "SOC", cliente_id: cs.id, alerta: "SLA", criticidad: crit, resumen_ejecutivo: "x", analisis: "x", acciones_recomendadas: "x", fecha_evento: new Date(rep0 - m * 60e3 - seg * 1000).toISOString(), fecha_reporte: new Date(rep0).toISOString() });
  ver(`${crit} a ${m} min y ${seg} s`, s === 201 && r.dentro_sla === !seg && r.sla_minutos === m, [s, r?.dentro_sla, r?.sla_minutos, r?.detail]);
}
const tab = async () => (await j(A, "/tablero?cliente_id=" + cs.id))[1]; let tb = await tab();
ver("tablero por criticidad", tb.por_sla.length === 4 && tb.por_sla.every(x => x.con_tiempo === 2 && x.dentro === 1 && x.objetivo === OBJ[x.criticidad]), tb.por_sla);
ver("total y analista cuadran", tb.indicadores.con_tiempo === 8 && tb.indicadores.dentro_sla === 4 && tb.por_analista[0].dentro_sla === 4, [tb.indicadores, tb.por_analista]);
[s] = await put("general", { sla_alta: 46, sla_media: 121 }); tb = await tab(); ver("el cambio se aplica a lo ya registrado", s === 200 && tb.indicadores.dentro_sla === 6, tb.por_sla);
const tg = (await j(A, "/tablero"))[1]; ver("todo el tablero cuadra", tg.por_sla.reduce((a, x) => a + x.dentro, 0) === tg.indicadores.dentro_sla && tg.por_sla.reduce((a, x) => a + x.con_tiempo, 0) === tg.indicadores.con_tiempo, tg.por_sla);
const rs = (await j(A, "/casos/resumen"))[1], t30 = (await j(A, "/tablero?desde=" + new Date(Date.now() - 5 * 3600e3 - 30 * 864e5).toISOString().slice(0, 10)))[1].indicadores; ver("inicio y tablero coinciden", rs.fuera_sla_30 === t30.con_tiempo - t30.dentro_sla && rs.con_tiempo_30 === t30.con_tiempo, [rs, t30]);
r = JSON.stringify((await j(A, "/usuarios/cambios"))[1]); ver("SLA en el registro de cambios", r.includes("SLA de notificación · Alta (minutos): 45 → 46"), r.slice(0, 300)); await j(A, "/config/general/restablecer", "POST");
sql("update casos set criticidad=null where cliente_id=" + cs.id + " and criticidad='Baja'"); tb = await tab(); ver("sin criticidad usa el de Media", tb.indicadores.dentro_sla === 3, tb.indicadores); sql("update casos set criticidad='Baja' where cliente_id=" + cs.id + " and criticidad is null");
await put("general", { url_plataforma: "http://soc.interno:8080" });
// ---------- correo al cliente
ver("copia ajena", (await put("correo_cliente", { correo_cc: "x@gmail.com" }))[0] === 422); ver("copia mal escrita", (await put("correo_cliente", { correo_cco: "nada" }))[0] === 422);
ver("dominio público", (await put("correo_cliente", { correo_dominio_propio: "gmail.com" }))[0] === 422);
const c = (await j(A, "/clientes", "POST", { codigo: "CFG", nombre: "Cliente config" }))[1]; await j(A, `/clientes/${c.id}/correos`, "PUT", { dominios: "cfg.example", para: "a@cfg.example", cc: "" });
for (const d of ["cfg.example", "sub.cfg.example", "example"]) ver("dominio de un cliente " + d, (await put("correo_cliente", { correo_dominio_propio: d }))[0] === 422);
ver("cambiar dominio exige cambiar copias", (await put("correo_cliente", { correo_dominio_propio: "otra.co" }))[0] === 422);
ver("tlp", (await put("correo_cliente", { correo_tlp: "ROJO" }))[0] === 422);
[s] = await put("correo_cliente", { correo_cc: "uno@wexler.com.co; Dos <dos@wexler.com.co>", correo_tlp: "TLP:AMBER", correo_plazo_horas: 24 }); ver("cambia copias", s === 200 && (await val("correo_cc")).valor === "uno@wexler.com.co; dos@wexler.com.co", await val("correo_cc"));
const caso = { servicio: "SOC", cliente_id: c.id, alerta: "Alerta de configuración", criticidad: "Alta", resumen_ejecutivo: "DETALLE-RESERVADO", analisis: "ANALISIS-RESERVADO", acciones_recomendadas: "x", fecha_evento: new Date(Date.now() - 600e3).toISOString() };
const k1 = (await j(T.N2, "/casos", "POST", caso))[1]; r = (await j(T.N2, `/casos/${k1.id}/correo`))[1]; ver("el borrador usa lo nuevo", r.cc.includes("dos@wexler.com.co") && r.html.includes("TLP:AMBER") && r.html.includes("24 horas"), r.cc);
await put("correo_cliente", { correo_cc: "" }); ver("copia vacía", (await j(T.N2, `/casos/${k1.id}/correo`))[1].cc.length === 0); await j(A, "/config/correo_cliente/restablecer", "POST");
// ---------- GLPI
for (const u of ["http://localhost/apirest.php", "http://127.0.0.1", "http://db:5432", "http://api:8000", "http://convertidor:3000", "http://web", "http://169.254.169.254/x", "http://[::1]/", "http://0.0.0.0", "http://soc-prueba-db-1:5432", "http://2130706433/"]) ver("destino prohibido " + u, (await put("glpi", { glpi_url: u }))[0] === 422, u);
[s, r] = await put("glpi", { glpi_url: "http://sim:9000/apirest.php", glpi_app_token: "app-bueno", glpi_user_token: "user-malo", glpi_sync_minutos: 0 }); ver("guarda GLPI", s === 200);
const todo = JSON.stringify((await j(A, "/config"))[1]); ver("no devuelve las claves", !todo.includes("app-bueno") && !todo.includes("user-malo") && (await val("glpi_app_token")).definida === true && (await val("glpi_app_token")).valor === null);
ver("cifradas en la base", sql("select valor from configuracion where clave='glpi_app_token'").startsWith("gAAAA") && !sql("select string_agg(valor,'|') from configuracion").includes("app-bueno"));
[s, r] = await j(T.LIDER, "/glpi/probar", "POST"); ver("detecta token malo", s === 502, r);
await put("glpi", { glpi_user_token: "user-bueno" }); [s, r] = await j(T.LIDER, "/glpi/probar", "POST"); ver("prueba correcta", s === 200 && r.usuario === "soc.api", r);
ver("activa sin reiniciar", (await j(T.N1, "/glpi/estado"))[1].activo === true);
await put("glpi", { glpi_resolver_al_cerrar: false }); ver("guardar sin claves las conserva", (await j(A, "/glpi/probar", "POST"))[0] === 200);
[s, r] = await put("glpi", { glpi_url: "http://otro.example/apirest.php" }); ver("cambiar de servidor exige las claves", s === 422 && r.detail.includes("vuelva a escribir"), r);
[s, r] = await put("glpi", { glpi_url: "http://otro.example/apirest.php", glpi_app_token: "nuevo" }); ver("exige todas las claves", s === 422, r);
ver("mismo servidor, otra ruta, no", (await put("glpi", { glpi_url: "http://sim:9000/apirest.php/" }))[0] === 200);
// ---------- FortiSIEM
ver("fortisiem sin datos", (await j(A, "/config/fortisiem/probar", "POST"))[0] === 400);
await put("fortisiem", { fortisiem_url: "http://sim:9000", fortisiem_usuario: "lector", fortisiem_clave: "mala" }); [s, r] = await j(A, "/config/fortisiem/probar", "POST"); ver("fortisiem rechaza", s === 502 && !JSON.stringify(r).includes("mala"), r);
await put("fortisiem", { fortisiem_clave: "forti-buena" }); [s, r] = await j(A, "/config/fortisiem/probar", "POST"); ver("fortisiem acepta", s === 200 && r.codigo === 200, r);
ver("fortisiem no acepta borrar url y robar clave", (await put("fortisiem", { fortisiem_url: "http://ladron.example" }))[0] === 422);
// ---------- otras APIs
const X = (d, i) => j(T.LIDER, "/config/conexiones" + (i ? "/" + i : ""), i ? "PUT" : "POST", d); const base = { nombre: "VirusTotal", url: "http://sim:9000/generica", autenticacion: "cabecera", cabecera: "x-apikey", clave: "clave-generica" };
for (const [t, d] of [["interna", { url: "http://db:5432" }], ["sin cabecera", { cabecera: "" }], ["cabecera rara", { cabecera: "x: y" }], ["host", { cabecera: "Host" }], ["salto de línea", { clave: "a\r\nX: 1" }], ["url", { url: "file:///etc/passwd" }]]) ver("conexión rechaza " + t, (await X({ ...base, ...d }))[0] === 422);
[s, r] = await X(base); const cx = r.id; ver("crea conexión", s === 201 && r.definida && !JSON.stringify(r).includes("clave-generica"), r); ver("nombre repetido", (await X({ ...base, nombre: "virustotal" }))[0] === 409);
[s, r] = await j(A, `/config/conexiones/${cx}/probar`, "POST"); ver("prueba sin contenido", s === 200 && r.codigo === 200 && !JSON.stringify(r).includes("contenido-remoto"), r);
ver("editar conserva la clave", (await X({ ...base, clave: null, notas: "n" }, cx))[1].definida && (await j(A, `/config/conexiones/${cx}/probar`, "POST"))[1].codigo === 200);
ver("cambiar servidor exige clave", (await X({ ...base, url: "http://otro.example/x", clave: null }, cx))[0] === 422);
await X({ ...base, url: "http://sim:9000/redirige", clave: null }, cx); ver("no sigue redirecciones", (await j(A, `/config/conexiones/${cx}/probar`, "POST"))[1].codigo === 302);
ver("elimina", (await j(A, "/config/conexiones/" + cx, "DELETE"))[0] === 204);
// ---------- claves de acceso
const K = (d) => j(T.LIDER, "/config/claves", "POST", d); const ext = async (k, u) => { const q = await fetch(B + "/externo" + u, { headers: k ? { "X-Api-Key": k } : {} }); return [q.status, await q.json().catch(() => null)]; };
for (const d of [{ nombre: "ab", permisos: ["casos"] }, { nombre: "abc", permisos: [] }, { nombre: "abc", permisos: ["todo"] }, { nombre: "abc", permisos: ["casos"], dias: 999 }, { nombre: "abc", permisos: ["casos"], cliente_id: 999999 }]) ver("clave inválida " + JSON.stringify(d), (await K(d))[0] === 422);
const k2 = (await K({ nombre: "Power BI", permisos: ["casos", "resumen"], dias: 30 }))[1], kc = (await K({ nombre: "Solo CFG", permisos: ["casos", "resumen"], cliente_id: c.id }))[1], kr = (await K({ nombre: "Solo totales", permisos: ["resumen"] }))[1];
ver("se entrega una vez", k2.clave?.startsWith("soc_") && !JSON.stringify((await j(A, "/config/claves"))[1]).includes(k2.clave) && !sql("select string_agg(huella,'|') from claves_api").includes(k2.clave));
[s, r] = await ext(k2.clave, "/casos?tamano=5"); ver("lista casos", s === 200 && r.items.length === 5 && r.total === (await j(A, "/casos?tamano=1"))[1].total, r?.total);
ver("sin textos reservados", !JSON.stringify((await ext(kc.clave, "/casos"))[1]).includes("RESERVADO")); ver("máximo 500", (await ext(k2.clave, "/casos?tamano=99999"))[1].items.length <= 500);
[s, r] = await ext(kc.clave, "/casos"); ver("limitada a su cliente", r.total === 1 && r.items.every(x => x.cliente === "CFG"), r?.total); ver("no se sale con el filtro", (await ext(kc.clave, "/casos?cliente=" + X1.codigo))[1].total === 0);
const pm = (await j(A, "/informes/" + (await j(A, "/informes"))[1].find(i => i.cliente.codigo === X2.codigo).id))[1].metricas.servicios.SOC.periodos[1];
const tot = (await ext(k2.clave, `/resumen?desde=${pm.inicio}&hasta=${pm.fin}&cliente=${X2.codigo.toLowerCase()}&servicio=soc`))[1]; ver("resumen cuadra con el informe", tot.total === X2.totales[1] && Object.values(tot.por_dia).reduce((a, b) => a + b, 0) === X2.totales[1], tot?.total);
ver("permiso por clave", (await ext(kr.clave, "/casos"))[0] === 403 && (await ext(kr.clave, "/resumen?desde=2026-10-01&hasta=2026-10-31"))[0] === 200);
for (const x of [null, "soc_", "soc_falsa", k2.clave + "x", A]) ver("clave mala", (await ext(x, "/casos"))[0] === 401); ver("la clave no abre lo demás", (await fetch(B + "/casos", { headers: { "X-Api-Key": k2.clave, Authorization: "Bearer " + k2.clave } })).status === 401);
const nu = (await j(A, `/casos/${k1.id}/anular`, "POST", { motivo: "prueba de consulta externa" }))[0]; ver("anulados no salen", nu === 200 && (await ext(kc.clave, "/casos"))[1].total === 0);
await j(A, `/config/claves/${k2.id}/revocar`, "POST"); ver("revocada", (await ext(k2.clave, "/casos"))[0] === 401); sql(`update claves_api set vence_en=now()-interval '1 minute' where id=${kc.id}`); ver("vencida", (await ext(kc.clave, "/casos"))[0] === 401);
ver("último uso", (await j(A, "/config/claves"))[1].find(x => x.id === kr.id).ultimo_uso);
// ---------- avisos
const base2 = { smtp_servidor: "sim", smtp_puerto: 2525, smtp_seguridad: "NINGUNA", smtp_remitente: "plataforma@wexler.com.co", avisos_destino: "soc@wexler.com.co", avisos_agrupar_min: 0 };
ver("activar sin datos", (await put("avisos", { avisos_activo: true }))[0] === 422);
for (const [t, d] of [["destino ajeno", { avisos_destino: "x@cfg.example" }], ["remitente ajeno", { smtp_remitente: "x@gmail.com" }], ["dos remitentes", { smtp_remitente: "a@wexler.com.co; b@wexler.com.co" }], ["clave sin cifrar", { smtp_usuario: "u", smtp_clave: "c" }], ["servidor interno", { smtp_servidor: "db" }], ["servidor con ruta", { smtp_servidor: "http://x" }]]) ver("avisos rechaza " + t, (await put("avisos", { ...base2, ...d }))[0] === 422);
// sin activar, no se encola
await j(T.N1, "/casos", "POST", caso); ver("desactivado no encola", sql("select count(*) from avisos") === "0");
[s, r] = await put("avisos", { ...base2, avisos_activo: true }); ver("activa avisos", s === 200, r);
ver("prueba a otro dominio", (await j(A, "/config/avisos/probar", "POST", { para: "x@cfg.example" }))[0] === 502); [s, r] = await j(T.LIDER, "/config/avisos/probar", "POST", { para: "lider@wexler.com.co" }); ver("envía prueba", s === 200, r);
const correos = () => JSON.parse(sim("/_ver")).correos; ver("llegó la prueba", correos().length === 1 && correos()[0].para[0] === "lider@wexler.com.co", correos());
const q = (await j(T.N1, "/casos", "POST", { ...caso, alerta: "Uno\r\nBcc: robo@x.co" }))[1]; await j(T.N1, "/casos", "POST", { ...caso, alerta: "Dos por revisar" }); await j(T.N2, `/casos/${q.id}/revision`, "POST", { resultado: "OBSERVADO", observacion: "Falta el análisis" });
await j(T.N2, "/casos", "POST", { ...caso, alerta: "De N2 no avisa" });
const enviar = () => py("from app.db import SessionLocal;from app import configuracion,avisos;db=SessionLocal();configuracion.cargar(db);print(avisos.procesar(db))");
for (let i = 0; i < 15 && sql("select count(*) from avisos where estado='PENDIENTE'") !== "0"; i++) await S(2000); // lo envía el hilo
let m = correos(); ver("el hilo envía solo", sql("select count(*) from avisos where estado='ENVIADO'") === "3", sql("select estado||':'||coalesce(error,'') from avisos"));
const dev = m.find(x => x.texto.includes("devuelto")), rev = m.filter(x => x.texto.includes("por revisar")); ver("devuelto va al analista", dev?.para.join() === "g.n1@wexler.com.co", dev?.para); ver("por revisar va a los destinatarios", rev.length >= 1 && rev.every(x => x.para.join() === "soc@wexler.com.co"), rev.map(x => x.para));
ver("sin detalle del caso", !m.some(x => /RESERVADO/.test(x.texto))); ver("sin inyección de cabeceras", !m.some(x => /^Bcc:/mi.test(x.texto))); ver("con enlace", m.some(x => x.texto.includes("http://soc.interno:8080/casos/")));
ver("N2 no genera aviso", !m.some(x => x.texto.includes("De N2 no avisa")));
// agrupar
await put("avisos", { avisos_agrupar_min: 30 }); for (const i of [1, 2, 3]) await j(T.N1, "/casos", "POST", { ...caso, alerta: "Grupo " + i }); enviar(); ver("espera para agrupar", sql("select count(*) from avisos where estado='PENDIENTE'") === "3"); sql("update avisos set creado_en=now()-interval '31 minutes' where estado='PENDIENTE'"); const antes = correos().length; enviar(); await S(500); m = correos(); ver("un solo correo agrupado", sql("select count(*) from avisos where estado='PENDIENTE'") === "0" && m.length === antes + 1 && ["Grupo 1", "Grupo 2", "Grupo 3"].every(x => m.at(-1).texto.includes(x)), [antes, m.length]);
// servidor caído: el caso se guarda y se reintenta
sim("/_poner/smtp/no"); await put("avisos", { avisos_agrupar_min: 0 }); [s] = await j(T.N1, "/casos", "POST", { ...caso, alerta: "Con correo caído" }); ver("el caso se guarda igual", s === 201); enviar(); ver("queda pendiente con error", /^PENDIENTE:\d+:.+/.test(sql("select estado||':'||intentos||':'||coalesce(error,'') from avisos order by id desc limit 1")), sql("select estado||':'||intentos||':'||coalesce(error,'') from avisos order by id desc limit 1"));
sim("/_poner/smtp/si"); await j(A, "/config/avisos/reintentar", "POST"); for (let i = 0; i < 15 && sql("select count(*) from avisos where estado='PENDIENTE'") !== "0"; i++) await S(2000); ver("reintenta", sql("select estado from avisos order by id desc limit 1") === "ENVIADO");
// falla de GLPI
sim("/_poner/glpi/no"); await j(A, "/clientes/" + c.id, "PUT", { codigo: "CFG", nombre: "Cliente config", glpi_entidad_id: 5 }); const kg = (await j(T.N2, "/casos?crear_ticket=true", "POST", { ...caso, alerta: "Con GLPI caído" }))[1]; ver("avisa falla de GLPI", kg.glpi_error && sql("select count(*) from avisos where tipo='glpi'") === "1", kg.glpi_error);
sim("/_poner/glpi/si"); [s, r] = await j(T.N2, `/casos/${kg.id}/glpi`, "POST"); ver("ticket con lo configurado en pantalla", s === 200 && r.glpi_ticket_id === 7001, r);
// ---------- auditoría y cambio de llave
r = JSON.stringify((await j(A, "/usuarios/cambios"))[1]) + JSON.stringify((await j(A, "/usuarios/cambios?pagina=2"))[1]); ver("queda en el registro", r.includes("la configuración de GLPI") && r.includes("App-Token: guardada") && r.includes("Power BI") && r.includes("la configuración de Avisos internos"));
ver("registro sin claves", !["app-bueno", "user-bueno", "user-malo", "forti-buena", "clave-generica", k2.clave].some(x => r.includes(x))); ver("registros del servidor sin claves", !["app-bueno", "user-bueno", "forti-buena", "clave-generica", k2.clave].some(x => dk("logs", "soc-prueba-api-1").includes(x)));
const il = py("import os;os.environ['JWT_SECRET']='otra-llave-distinta';from app.db import SessionLocal;from app import configuracion as c;db=SessionLocal();c.cargar(db);print(sorted(c.ILEGIBLES),c.settings.glpi_app_token)"); ver("otra llave no las abre ni falla", il.includes("glpi_app_token") && il.endsWith("None"), il);
[s] = await put("glpi", {}, ["glpi_app_token"]); ver("borrar clave desactiva", s === 200 && (await j(A, "/glpi/estado"))[1].activo === false);
console.log(f ? `FALLOS ${f} de ${n}` : `TODO BIEN: ${n} comprobaciones`);
