// Alertas por tratar: tickets que el SIEM crea en GLPI. Requiere el simulador (soc-prueba-sim); va después de e2e_config.
import fs from "fs";
import { execFileSync } from "child_process";
const [puerto, env] = process.argv.slice(2); const B = `http://127.0.0.1:${puerto}/api`;
const pw = /^ADMIN_PASSWORD=(.*)$/m.exec(fs.readFileSync(env, "utf8"))[1].trim(), P = "Prueba-local-123";
const ent = async (u, p) => (await (await fetch(B + "/auth/login", { method: "POST", body: new URLSearchParams({ username: u, password: p }) })).json()).access_token;
const j = async (t, u, m = "GET", d) => { const r = await fetch(B + u, { method: m, headers: { Authorization: "Bearer " + t, ...(d ? { "Content-Type": "application/json" } : {}) }, body: d ? JSON.stringify(d) : undefined }); return [r.status, await r.json().catch(() => null)]; };
const dk = (...a) => execFileSync("docker", a, { encoding: "utf8" });
const sql = (q) => dk("exec", "soc-prueba-db-1", "sh", "-c", `psql -U $POSTGRES_USER -d $POSTGRES_DB -tAc "${q}"`).trim();
const py = (c) => dk("exec", "-e", "PYTHONPATH=/srv", "soc-prueba-api-1", "python", "-c", c).trim();
const sim = (r) => py(`import httpx;print(httpx.get('http://sim:9000${r}').text)`);
const ticket = (id, ent, urg, est, atras, titulo) => sim(`/_ticket/${id}/${ent}/${urg}/${est}/${atras}/${encodeURIComponent(titulo)}`);
const peticiones = () => JSON.parse(sim("/_ver")).peticiones;
const S = (ms) => new Promise(r => setTimeout(r, ms));
let f = 0, n = 0; const ver = (t, ok, x = "") => { n++; if (!ok) { f++; console.log("  [X] ", t, JSON.stringify(x)?.slice(0, 300)); } };
const A = await ent("admin", pw), T = {};
for (const r of ["N1", "N1B", "N2", "LIDER", "CISO"]) {
  const rol = r === "N1B" ? "N1" : r, u = "al." + r.toLowerCase();
  await j(A, "/usuarios", "POST", { usuario: u, nombre: "Alertas " + r, rol, password: P, email: `${u}@wexler.com.co` }); T[r] = await ent(u, P);
}
const put = (g, valores, borrar = []) => j(T.LIDER, "/config/" + g, "PUT", { valores, borrar });
let s, r;
const ca = (await j(A, "/clientes", "POST", { codigo: "ALA", nombre: "Cliente alertas A", glpi_entidad_id: 77 }))[1];
const cb = (await j(A, "/clientes", "POST", { codigo: "ALB", nombre: "Cliente alertas B" }))[1];
const base = { servicio: "SOC", cliente_id: ca.id, alerta: "Alerta GLPI", criticidad: "Alta", resumen_ejecutivo: "x", analisis: "x", acciones_recomendadas: "x", fecha_evento: new Date(Date.now() - 600e3).toISOString() };

// ---------- sin configurar
ver("sin sesión", (await fetch(B + "/alertas")).status === 401);
[s, r] = await j(T.N1, "/alertas/traer", "POST"); ver("GLPI inactivo", s === 400, r);
[s, r] = await j(T.N1, "/alertas"); ver("bandeja vacía e inactiva", s === 200 && r.total === 0 && r.integracion.activo === false, r);
ver("CISO no busca", (await j(T.CISO, "/alertas/traer", "POST"))[0] === 403);
await put("glpi", { glpi_url: "http://sim:9000/apirest.php", glpi_app_token: "app-bueno", glpi_user_token: "user-bueno", glpi_sync_minutos: 0 });
ver("GLPI activo", (await j(A, "/glpi/estado"))[1].activo === true);
[s, r] = await j(T.N1, "/alertas/traer", "POST"); ver("bandeja sin activar", s === 400 && /no está activada/.test(r.detail), r);
[s, r] = await put("glpi", { glpi_alertas_activo: true }); ver("activar exige un criterio", s === 422 && /al menos un criterio/.test(r.detail), r);
[s, r] = await put("glpi", { glpi_alertas_activo: true, glpi_alertas_origen_id: 2, glpi_alertas_texto: "FortiSIEM", glpi_alertas_minutos: 60 }); ver("activa la bandeja", s === 200, r);
ver("N1 no configura", (await j(T.N1, "/config/glpi", "PUT", { valores: { glpi_alertas_activo: false }, borrar: [] }))[0] === 403);
await put("avisos", { smtp_servidor: "sim", smtp_puerto: 2525, smtp_seguridad: "NINGUNA", smtp_remitente: "plataforma@wexler.com.co", avisos_destino: "soc@wexler.com.co", avisos_activo: true, aviso_alerta_sin_tomar: true });

// ---------- tickets del SIEM en GLPI
ticket(9101, 77, 5, 1, 50, "FortiSIEM - Fuerza bruta en VPN");   // crítica, ya pasó su SLA
ticket(9102, 88, 3, 1, 10, "FortiSIEM - Malware detectado");      // entidad sin cliente
ticket(9103, 77, 4, 5, 20, "FortiSIEM - Ya resuelto");            // resuelto: no se trae
ticket(9104, 77, 4, 1, 15, "FortiSIEM - Ya tiene caso");
[s, r] = await j(T.N2, "/casos", "POST", { ...base, alerta: "Caso con ticket digitado", glpi_ticket_id: 9104 }); ver("caso manual con ticket", s === 201 && r.glpi_ticket_id === 9104, r);
const sinAvisos = sql("select count(*) from avisos where tipo='alerta'");
[s, r] = await j(T.N1, "/alertas/traer", "POST"); ver("trae las nuevas", s === 200 && r.nuevas === 2, r);
[s, r] = await j(T.N1, "/alertas/traer", "POST"); ver("no las repite", s === 200 && r.nuevas === 0, r);
const busq = peticiones().filter(x => x.ruta.includes("/search/Ticket")).at(-1)?.ruta || "";
const dq = decodeURIComponent(busq.replace(/\+/g, " "));
ver("busca con los criterios", dq.includes("criteria[0][value]=notold") && dq.includes("criteria[1][field]=15") && dq.includes("criteria[2][field]=9") && dq.includes("criteria[2][value]=2") && dq.includes("criteria[3][searchtype]=contains") && dq.includes("criteria[3][value]=FortiSIEM"), dq);
[s, r] = await j(T.N1, "/alertas"); const lista = r;
const a1 = r.items.find(x => x.glpi_ticket_id === 9101), a2 = r.items.find(x => x.glpi_ticket_id === 9102);
ver("pendientes", s === 200 && r.total === 2 && a1 && a2 && !r.items.some(x => [9103, 9104].includes(x.glpi_ticket_id)), r.items?.map(x => x.glpi_ticket_id));
ver("cliente por la entidad", a1?.cliente?.codigo === "ALA" && a2?.cliente === null && a2?.glpi_entidad_id === 88, [a1?.cliente, a2?.cliente]);
ver("criticidad por la urgencia", a1?.criticidad === "Crítica" && a2?.criticidad === "Media");
ver("hora de llegada a GLPI", Math.abs(Date.now() - 50 * 60e3 - Date.parse(a1?.fecha_alerta)) < 90e3 && a1.minutos >= 49 && a1.minutos <= 51, [a1?.fecha_alerta, a1?.minutos]);
ver("más antigua primero", r.items[0].glpi_ticket_id === 9101);
ver("resumen", lista.resumen.por_reportar === 2 && lista.resumen.vencidas === 1 && lista.resumen.sin_cliente === 1 && lista.resumen.en_gestion === 0, lista.resumen);
ver("la lista no trae el contenido", !JSON.stringify(lista).includes("203.0.113.7"));
[s, r] = await j(T.N1, "/alertas/" + a1.id); const txt = r?.contenido || "";
ver("contenido en texto", s === 200 && txt.includes("FortiSIEM: Fuerza bruta en VPN\nIP origen: 203.0.113.7") && txt.includes("Usuario\tjperez") && txt.includes('Acción: "Permitida"'), txt);
ver("sin HTML ni scripts", !/[<>]/.test(txt) && !txt.includes("alert(1)"), txt);
ver("buscar por ticket", (await j(T.N1, "/alertas?q=9102"))[1].items.map(x => x.glpi_ticket_id).join() === "9102");
ver("buscar por título", (await j(T.N1, "/alertas?q=malware"))[1].total === 1);
ver("filtrar por cliente", (await j(T.N1, "/alertas?cliente_id=" + ca.id))[1].total === 1);
ver("contador del menú", (await j(T.N1, "/casos/pendientes"))[1].alertas === 2 && (await j(T.CISO, "/casos/pendientes"))[1].alertas === 0);
ver("el CISO ve la bandeja", (await j(T.CISO, "/alertas"))[0] === 200);
ver("aviso de sin tomar, una vez", +sql("select count(*) from avisos where tipo='alerta'") === +sinAvisos + 1 && sql("select count(*) from alertas where avisada_en is not null") === "1",
  sql("select string_agg(asunto, ' | ') from avisos where tipo='alerta'"));
ver("aviso sin el detalle", !sql("select string_agg(cuerpo, ' ') from avisos where tipo='alerta'").includes("203.0.113.7") && sql("select asunto from avisos where tipo='alerta'") === "Alerta sin tomar: ticket GLPI 9101");

// ---------- tomar y liberar
ver("CISO no toma", (await j(T.CISO, `/alertas/${a1.id}/tomar`, "POST"))[0] === 403);
[s, r] = await j(T.N1, `/alertas/${a1.id}/tomar`, "POST"); ver("toma", s === 200 && r.estado === "EN_GESTION" && r.analista?.nombre === "Alertas N1" && r.tomada_en, r);
[s, r] = await j(T.N1B, `/alertas/${a1.id}/tomar`, "POST"); ver("otro no la toma", s === 409 && r.detail.includes("Alertas N1"), r);
ver("tomarla otra vez no falla", (await j(T.N1, `/alertas/${a1.id}/tomar`, "POST"))[0] === 200);
ver("otro N1 no la libera", (await j(T.N1B, `/alertas/${a1.id}/liberar`, "POST"))[0] === 403);
ver("el menú cuenta solo las no tomadas", (await j(T.N1, "/casos/pendientes"))[1].alertas === 1);
[s, r] = await j(T.N1B, "/casos?alerta_id=" + a1.id, "POST", { ...base, alerta: "Robo" }); ver("otro N1 no la reporta", s === 409, r);
[s, r] = await j(T.N2, `/alertas/${a1.id}/liberar`, "POST"); ver("un revisor la libera", s === 200 && r.estado === "POR_REPORTAR" && r.analista === null, r);
ver("liberar dos veces", (await j(T.N2, `/alertas/${a1.id}/liberar`, "POST"))[0] === 409);
await j(T.N1, `/alertas/${a1.id}/tomar`, "POST");

// ---------- reportar: el caso lleva el ticket del SIEM
const posts = () => peticiones().filter(x => x.metodo === "POST");
const antesTicket = posts().filter(x => x.ruta.endsWith("/Ticket")).length, antesSeg = posts().filter(x => x.ruta.endsWith("/ITILFollowup")).length;
const ev = new Date(Date.parse(a1.fecha_alerta)).toISOString(), t0 = Date.now();
[s, r] = await j(T.N1, `/casos?crear_ticket=true&alerta_id=${a1.id}`, "POST", { ...base, alerta: a1.titulo, criticidad: "Crítica", fecha_evento: ev, glpi_ticket_id: 555 }); const k1 = r;
ver("crea el caso", s === 201 && r.numero?.startsWith("WX"), r);
ver("con el ticket del SIEM", r.glpi_ticket_id === 9101 && r.glpi_estado === 1, [r.glpi_ticket_id, r.glpi_estado]);
ver("no crea otro ticket", posts().filter(x => x.ruta.endsWith("/Ticket")).length === antesTicket);
const seg = posts().filter(x => x.ruta.endsWith("/ITILFollowup"));
ver("deja seguimiento en GLPI", seg.length === antesSeg + 1 && seg.at(-1).cuerpo.includes(k1.numero) && /"items_id":\s?9101/.test(seg.at(-1).cuerpo), seg.at(-1));
ver("hora de reporte del servidor", Math.abs(Date.parse(k1.fecha_reporte) - t0) < 60e3 && k1.minutos_respuesta >= 49 && k1.dentro_sla === false, [k1.fecha_reporte, k1.minutos_respuesta]);
ver("queda en el historial", (await j(T.N1, `/casos/${k1.id}/seguimientos`))[1]?.some?.(x => /Alertas por tratar.*9101/.test(x.comentario)) || sql(`select count(*) from seguimientos where caso_id=${k1.id} and comentario like '%Alertas por tratar%9101%'`) === "1");
[s, r] = await j(T.N1, "/alertas/" + a1.id); ver("alerta reportada", r.estado === "REPORTADA" && r.caso_id === k1.id && r.caso_numero === k1.numero && r.reportada_en && r.minutos >= 49, r);
ver("sale de pendientes", (await j(T.N1, "/alertas"))[1].items.every(x => x.id !== a1.id) && (await j(T.N1, "/alertas?vista=reportadas"))[1].items.some(x => x.id === a1.id));
[s, r] = await j(T.N1, "/casos?alerta_id=" + a1.id, "POST", { ...base }); ver("no se reporta dos veces", s === 409 && r.detail.includes(k1.numero), r);
[s, r] = await j(T.N1, "/casos", "POST", { ...base, glpi_ticket_id: 9101 }); ver("ticket de alerta reportada no se repite", s === 409, r);
[s, r] = await j(T.N2, "/casos/" + k1.id, "PUT", { ...base, alerta: a1.titulo, criticidad: "Crítica", fecha_evento: ev, glpi_ticket_id: 1234 }); ver("su ticket no se cambia", s === 422, r);
[s, r] = await j(T.N2, "/casos/" + k1.id, "PUT", { ...base, alerta: a1.titulo, criticidad: "Crítica", fecha_evento: ev, glpi_ticket_id: 9101 }); ver("se edita igual", s === 200 && r.glpi_ticket_id === 9101, r);
ver("cuenta en la lista de casos", (await j(T.N1, "/casos?q=" + k1.numero))[1].total === 1);
ver("alerta inexistente", (await j(T.N1, "/casos?alerta_id=999999", "POST", base))[0] === 404);
// el analista elige el cliente si la entidad no tiene uno
[s, r] = await j(T.N1B, `/alertas/${a2.id}/tomar`, "POST"); ver("N1B toma la otra", s === 200);

// ---------- cliente asignado después, cierre en GLPI y casos manuales
await j(A, "/clientes/" + cb.id, "PUT", { codigo: "ALB", nombre: "Cliente alertas B", glpi_entidad_id: 88 });
await j(T.N1, "/alertas/traer", "POST"); ver("asigna el cliente después", (await j(T.N1, "/alertas/" + a2.id))[1].cliente?.codigo === "ALB");
ticket(9105, 77, 2, 1, 5, "FortiSIEM - Se cierra en GLPI"); await j(T.N1, "/alertas/traer", "POST");
const a5 = (await j(T.N1, "/alertas?q=9105"))[1].items[0]; ver("trae la tercera", a5?.estado === "POR_REPORTAR" && a5.criticidad === "Baja", a5);
sim("/_estado/9105/6"); [s, r] = await j(T.N1, "/alertas/traer", "POST"); ver("detecta el cierre en GLPI", s === 200 && r.cerradas === 1, r);
[s, r] = await j(T.N1, "/alertas/" + a5.id); ver("cerrada en GLPI", r.estado === "CERRADA_GLPI" && r.glpi_estado === 6 && r.cerrada_en, r);
ver("en la vista de cerradas", (await j(T.N1, "/alertas?vista=cerradas"))[1].items.some(x => x.id === a5.id));
ver("cerrada no se reporta", (await j(T.N1, "/casos?alerta_id=" + a5.id, "POST", base))[0] === 409);
ver("cerrada no se toma", (await j(T.N1, `/alertas/${a5.id}/tomar`, "POST"))[0] === 409);
// el flujo manual sigue igual: el N1 crea el caso y el ticket
[s, r] = await j(T.N1, "/casos?crear_ticket=true", "POST", { ...base, alerta: "Cliente nuevo sin afinar" }); ver("flujo manual con ticket", s === 201 && r.glpi_ticket_id === 7001, r);
ticket(7001, 77, 3, 1, 1, "FortiSIEM - Ticket creado por la plataforma"); [s, r] = await j(T.N1, "/alertas/traer", "POST");
ver("el ticket propio no vuelve como alerta", r.nuevas === 0 && sql("select count(*) from alertas where glpi_ticket_id=7001") === "0", r);
// ticket digitado en un caso manual que era de una alerta pendiente
ticket(9106, 88, 4, 1, 3, "FortiSIEM - Digitado"); await j(T.N1, "/alertas/traer", "POST");
const a6 = (await j(T.N1, "/alertas?q=9106"))[1].items[0];
[s, r] = await j(T.N2, "/casos", "POST", { ...base, cliente_id: cb.id, alerta: "Digitado a mano", glpi_ticket_id: 9106 }); ver("caso manual con el ticket", s === 201);
ver("la alerta queda reportada", (await j(T.N1, "/alertas/" + a6.id))[1].caso_id === r.id);
// carrera: dos analistas reportan la misma alerta
ticket(9107, 77, 3, 1, 2, "FortiSIEM - Carrera"); await j(T.N1, "/alertas/traer", "POST");
const a7 = (await j(T.N1, "/alertas?q=9107"))[1].items[0];
const dos = await Promise.all([T.N1, T.N1B].map(t => j(t, "/casos?alerta_id=" + a7.id, "POST", { ...base, alerta: "Carrera" })));
ver("solo un caso por alerta", dos.filter(x => x[0] === 201).length === 1 && dos.filter(x => x[0] === 409).length === 1, dos.map(x => x[0]));
ver("base consistente", sql("select count(*) from alertas where estado='REPORTADA' and caso_id is null") === "0" && sql("select count(*) from casos where glpi_ticket_id=9107") === "1");

// ---------- desactivar
await put("glpi", { glpi_alertas_activo: false }); ver("desactivada", (await j(T.N1, "/alertas/traer", "POST"))[0] === 400 && (await j(T.N1, "/alertas/estado"))[1].activo === false);
ver("la bandeja se sigue viendo", (await j(T.N1, "/alertas?vista=todas"))[1].total === 5);
console.log(f ? `FALLOS ${f} de ${n}` : `TODO BIEN: ${n} comprobaciones`);
