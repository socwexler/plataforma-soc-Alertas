// Anexos del informe desde SharePoint: carpeta sincronizada (montada en /sharepoint) y Microsoft Graph (simulador).
// Argumentos: puerto, .env, carpeta montada (datos/sharepoint de la copia), carpeta de insumos (CSV reales de FortiSIEM).
import fs from "fs";
import path from "path";
import { execFileSync } from "child_process";
const [puerto, env, SPDIR, RDIR] = process.argv.slice(2); const B = `http://127.0.0.1:${puerto}/api`;
const pw = /^ADMIN_PASSWORD=(.*)$/m.exec(fs.readFileSync(env, "utf8"))[1].trim(), P = "Prueba-local-123";
const ent = async (u, p) => (await (await fetch(B + "/auth/login", { method: "POST", body: new URLSearchParams({ username: u, password: p }) })).json()).access_token;
const j = async (t, u, m = "GET", d) => { const r = await fetch(B + u, { method: m, headers: { Authorization: "Bearer " + t, ...(d ? { "Content-Type": "application/json" } : {}) }, body: d ? JSON.stringify(d) : undefined }); return [r.status, await r.json().catch(() => null)]; };
const dk = (...a) => execFileSync("docker", a, { encoding: "utf8" });
const sql = (q) => dk("exec", "soc-prueba-db-1", "sh", "-c", `psql -U $POSTGRES_USER -d $POSTGRES_DB -tAc "${q}"`).trim();
const py = (c) => dk("exec", "-e", "PYTHONPATH=/srv", "soc-prueba-api-1", "python", "-c", c).trim();
const sim = (r) => py(`import httpx;print(httpx.get('http://sim:9000${r}').text)`);
let f = 0, n = 0; const ver = (t, ok, x = "") => { n++; if (!ok) { f++; console.log("  [X] ", t, JSON.stringify(x)?.slice(0, 300)); } };
const A = await ent("admin", pw), T = {};
for (const r of ["N1", "N2", "LIDER", "CISO"]) { const u = "sp." + r.toLowerCase(); await j(A, "/usuarios", "POST", { usuario: u, nombre: "SP " + r, rol: r, password: P }); T[r] = await ent(u, P); }
const put = (valores, borrar = []) => j(T.LIDER, "/config/sharepoint", "PUT", { valores, borrar });
let s, r;

// ---------- carpeta de prueba: misma estructura que SharePoint
const BASE = "01 Gestión SOC NOC", raiz = path.join(SPDIR, BASE);
const C = { eps: "04 WX - Promedio Mensual EPS", fuentes: "07 WX - Consolidado dispositivos y su estado", paises_entrantes: "10 WX - Eventos de paises diferentes a Colombia entrantes permitidos",
  paises_salientes: "12 WX - Eventos de paises diferentes a Colombia salientes permitidos", puertos: "14 WX - Trafico por Puerto Saliente Entrante Permitido", ips: "15 WX - IPS Ataques PermitidosBloqueados" };
for (const d of [...Object.values(C), "01 WX - bitácora SOC", "100 Otra carpeta", "11 WX - TOP Eventos de paises entrantes permitidos"]) fs.mkdirSync(path.join(raiz, d), { recursive: true });
const poner = (tipo, cli, nombre, contenido) => { const d = path.join(raiz, C[tipo], cli); fs.mkdirSync(d, { recursive: true }); fs.writeFileSync(path.join(d, nombre), contenido); };
const real = (x) => fs.readFileSync(path.join(RDIR, x));
const cx = (await j(A, "/clientes", "POST", { codigo: "SPX", nombre: "Cliente SharePoint", dia_corte: 16, servicio_noc: true }))[1];
const cw = (await j(A, "/clientes", "POST", { codigo: "SPW", nombre: "Cliente carpeta propia", sharepoint_carpeta: "SPW-Carpeta" }))[1];
ver("ficha con carpeta", cw.sharepoint_carpeta === "SPW-Carpeta");
for (const mala of ["../x", "a/b", "..", "a\\b", "x:y"]) ver("carpeta inválida " + mala, (await j(A, "/clientes/" + cw.id, "PUT", { codigo: "SPW", nombre: "x", sharepoint_carpeta: mala }))[0] === 422);
ver("carpeta vacía = código", (await j(A, "/clientes/" + cx.id, "PUT", { codigo: "SPX", nombre: "Cliente SharePoint", dia_corte: 16, servicio_noc: true, sharepoint_carpeta: "  " }))[1].sharepoint_carpeta === null);
const nuevo = async (cid) => (await j(A, "/informes", "POST", { cliente_id: cid, anio: 2026, mes: 10 }))[1];
const i1 = await nuevo(cx.id), ini = i1.periodo_inicio, AM = ini.slice(0, 7), PAT = `SPX_${AM}`;
ver("periodo del informe", /^2026-10-16$/.test(ini), ini);
poner("eps", "SPX", PAT + ".csv", "Mes Periodo;Cantidad\nAgosto 2026;1200\nSeptiembre 2026;1300,5\nOctubre 2026;1250\n");
poner("fuentes", "SPX", PAT + ".csv", "Nombre;IP;Tipo;Estado;Envia logs\nfw-1;10.0.0.1;Firewall;Aprobado;Sí\nsrv-1;10.0.0.2;Windows;Aprobado;No\nsw-1;10.0.0.3;Switch;No administrado;Sí\n");
poner("fuentes", "SPX", PAT + "_NOC.csv", "Nombre;IP;Tipo;Estado\nrt-1;10.1.0.1;Router;Aprobado\n");
poner("paises_entrantes", "SPX", PAT + ".csv", real("pasiesnetentrrantres.csv"));
poner("paises_entrantes", "SPX", "SPX_2026-09.csv", real("pasiesnetentrrantres.csv"));
poner("paises_entrantes", "SPX", "otro nombre.csv", real("pasiesnetentrrantres.csv"));
poner("paises_entrantes", "SPX", "~$abierto.xlsx", "x"); poner("paises_entrantes", "SPX", "notas.docx", "x");
poner("paises_salientes", "SPX", PAT + ".csv", real("Paises salientes.csv"));
poner("paises_salientes", "SPX", "SPX_mal.csv", real("pasiesnetentrrantres.csv"));   // entrantes en la carpeta de salientes
poner("puertos", "SPX", PAT + ".csv", real("report1794971796.csv"));
poner("ips", "SPX", PAT + ".csv", "Attack Name;Firewall Action;Severity;Total\nSQL Injection;Drop;High;5\nPort Scan;Accept;Low;3\nXSS;Block;Medium;2\n");
poner("eps", "SPW-Carpeta", "SPW-Carpeta_2026-10.csv", "Mes Periodo;Cantidad\nOctubre 2026;10\n");
poner("eps", "SPW-Carpeta", "SPW_2026-10.csv", "Mes Periodo;Cantidad\nOctubre 2026;11\n");

// ---------- sin activar y permisos
[s, r] = await j(A, `/informes/${i1.id}/sharepoint`); ver("desactivado", s === 400 && /no está activada/.test(r.detail), r);
ver("el editor no ofrece el botón", (await j(A, `/informes/${i1.id}`))[1].sharepoint === false);
for (const x of ["N1", "CISO"]) { ver(`${x} no busca`, (await j(T[x], `/informes/${i1.id}/sharepoint`))[0] === 403); ver(`${x} no trae`, (await j(T[x], `/informes/${i1.id}/sharepoint`, "POST", { archivos: [{ tipo: "eps", nombre: "x" }] }))[0] === 403); }
ver("N2 no configura", (await j(T.N2, "/config/sharepoint", "PUT", { valores: { sharepoint_modo: "carpeta" }, borrar: [] }))[0] === 403);
ver("N2 no prueba", (await j(T.N2, "/config/sharepoint/probar", "POST"))[0] === 403);
ver("N2 no ve la guía", (await j(T.N2, "/config/sharepoint/estado"))[0] === 403);
const est = async () => (await j(T.LIDER, "/config/sharepoint/estado"))[1];
[s, r] = await j(T.LIDER, "/config/sharepoint/estado"); ver("guía: montada y sin activar", s === 200 && r.modo === "no" && r.carpeta_montada === true && r.carpetas.eps === "04" && r.nombres.ips === "Ataques IPS" && Object.values(r.graph).every(x => x === false), r);

// ---------- carpeta sincronizada
[s, r] = await put({ sharepoint_modo: "carpeta", sharepoint_ruta: "no-existe" }); ver("guarda modo carpeta", s === 200, r);
ver("guía: carpeta base inexistente", (await est()).carpeta_base_existe === false);
[s, r] = await j(T.LIDER, "/config/sharepoint/probar", "POST"); ver("avisa carpeta base inexistente", s === 502 && /No se encuentra la carpeta/.test(r.detail), r);
ver("ruta base no sale de la carpeta", (await put({ sharepoint_ruta: "../../etc" }))[0] === 200 && (await j(T.LIDER, "/config/sharepoint/probar", "POST"))[0] === 502);
await put({ sharepoint_ruta: BASE });
ver("guía: carpeta lista", (await est()).carpeta_base_existe === true && (await est()).modo === "carpeta");
[s, r] = await j(T.LIDER, "/config/sharepoint/probar", "POST");
ver("prueba la carpeta", s === 200 && r.tipos.every(t => t.carpeta && !t.error) && r.tipos.find(t => t.tipo === "paises_entrantes").carpeta === C.paises_entrantes, r);
ver("clientes sin subcarpeta", r.tipos.find(t => t.tipo === "ips").sin_carpeta.includes("SPW") && !r.tipos.find(t => t.tipo === "ips").sin_carpeta.includes("SPX") && !r.tipos.find(t => t.tipo === "eps").sin_carpeta.includes("SPW"), r.tipos.find(t => t.tipo === "ips"));
[s, r] = await j(T.N2, `/informes/${i1.id}/sharepoint`); const b1 = r;
ver("busca", s === 200 && r.patron === PAT && r.tipos.length === 6 && r.tipos.every(t => !t.error), r);
const T1 = (t) => b1.tipos.find(x => x.tipo === t);
ver("«10» no confunde «100»", T1("paises_entrantes").carpeta === C.paises_entrantes);
ver("propone el del periodo", Object.keys(C).every(t => T1(t).archivos[0]?.nombre.startsWith(PAT) && T1(t).archivos[0].sugerido), b1.tipos.map(t => t.archivos[0]));
ver("propone también el NOC", T1("fuentes").archivos.filter(a => a.sugerido).map(a => a.nombre).sort().join() === `${PAT}.csv,${PAT}_NOC.csv`);
ver("lista los demás sin proponerlos", T1("paises_entrantes").archivos.length === 3 && T1("paises_entrantes").archivos.filter(a => a.sugerido).length === 1, T1("paises_entrantes").archivos);
ver("ignora temporales y otros formatos", !T1("paises_entrantes").archivos.some(a => /~\$|docx/.test(a.nombre)), T1("paises_entrantes").archivos);
ver("con fecha y tamaño", T1("eps").archivos[0].modificado && T1("eps").archivos[0].tamano > 10);
const elegir = (b) => b.tipos.flatMap(t => t.archivos.filter(a => a.sugerido).map(a => ({ tipo: t.tipo, nombre: a.nombre })));
[s, r] = await j(T.N2, `/informes/${i1.id}/sharepoint`, "POST", { archivos: elegir(b1) }); const c1 = r;
ver("trae los 7 archivos", s === 200 && r.resultados.length === 7 && r.errores.length === 0, r.errores || r);
ver("con su ruta en SharePoint", r.resultados.every(x => x.origen === "SharePoint" && x.ruta.includes("/SPX/") && x.modificado));
const an1 = sql(`select string_agg(k, ',' order by k) from informes, jsonb_object_keys(anexos) k where id=${i1.id}`);
ver("los 6 anexos y el NOC", an1 === "eps_historico,fuentes,fuentes_noc,ips,paises_entrantes,paises_salientes,puertos", an1);
ver("datos del servicio", r.informe.eps_promedio === 1250 && r.informe.fuentes_integradas === 3, [r.informe.eps_promedio, r.informe.fuentes_integradas]);
ver("queda en el historial", sql(`select count(*) from informes, jsonb_array_elements(archivos) a where id=${i1.id} and a->>'origen'='SharePoint' and a->>'ruta' like '%SPX%'`) === "7");
// igual que subirlos a mano
const i2 = await nuevo(cw.id); const fd = new FormData();
for (const x of elegir(b1)) fd.append("archivos", new Blob([fs.readFileSync(path.join(raiz, C[x.tipo], "SPX", x.nombre))]), x.nombre);
const m2 = await (await fetch(`${B}/informes/${i2.id}/anexos`, { method: "POST", headers: { Authorization: "Bearer " + A }, body: fd })).json();
ver("subida manual sin errores", m2.errores?.length === 0, m2.errores);
ver("mismo resultado que a mano", sql(`select (select anexos from informes where id=${i1.id}) = (select anexos from informes where id=${i2.id})`) === "t");
ver("el CSV _NOC va a fuentes NOC también a mano", /1 fuentes/.test(m2.informe.anexos_resumen.fuentes_noc), m2.informe.anexos_resumen);
// archivos en la carpeta equivocada o inexistentes
[s, r] = await j(T.N2, `/informes/${i1.id}/sharepoint`, "POST", { archivos: [{ tipo: "paises_salientes", nombre: "SPX_mal.csv" }] });
ver("rechaza entrantes en salientes", s === 200 && r.resultados.length === 0 && /se reconoció como Países entrantes.*destino/.test(r.errores[0]), r);
[s, r] = await j(T.N2, `/informes/${i1.id}/sharepoint`, "POST", { archivos: [{ tipo: "puertos", nombre: `../../${C.ips}/SPX/${PAT}.csv` }, { tipo: "ips", nombre: `${PAT}.csv` }] });
ver("no sale de la carpeta del cliente", s === 200 && r.errores.some(e => /ya no está en la carpeta/.test(e)) && r.resultados.length === 1, r);
for (const [t, d] of [["tipo inválido", { archivos: [{ tipo: "otro", nombre: "x.csv" }] }], ["sin archivos", { archivos: [] }], ["demasiados", { archivos: Array(13).fill({ tipo: "eps", nombre: "x" }) }]]) {
  [s, r] = await j(T.N2, `/informes/${i1.id}/sharepoint`, "POST", d); ver(t, s === 422 || (s === 200 && r.errores.length === 1), [s, r]);
}
// carpeta propia del cliente (sharepoint_carpeta)
[s, r] = await j(T.N2, `/informes/${i2.id}/sharepoint`); const e2 = r.tipos.find(t => t.tipo === "eps");
ver("usa la carpeta de la ficha", s === 200 && e2.carpeta_cliente === "SPW-Carpeta" && e2.archivos.filter(a => a.sugerido).length === 2, e2);
ver("sin subcarpeta lo dice", /No hay una subcarpeta SPW-Carpeta o SPW/.test(r.tipos.find(t => t.tipo === "ips").error), r.tipos.find(t => t.tipo === "ips"));
// carpeta del anexo configurable y ambigua
fs.mkdirSync(path.join(raiz, "15 copia")); [s, r] = await j(T.N2, `/informes/${i1.id}/sharepoint`); ver("número ambiguo", /2 carpetas que empiezan por «15»/.test(r.tipos.find(t => t.tipo === "ips").error), r.tipos.find(t => t.tipo === "ips")); fs.rmdirSync(path.join(raiz, "15 copia"));
await put({ sharepoint_carpeta_ips: C.ips }); [s, r] = await j(T.N2, `/informes/${i1.id}/sharepoint`); ver("nombre completo", r.tipos.find(t => t.tipo === "ips").carpeta === C.ips);
await put({ sharepoint_carpeta_ips: "99" }); [s, r] = await j(T.N2, `/informes/${i1.id}/sharepoint`); ver("carpeta que no existe", /No hay una carpeta «99…»/.test(r.tipos.find(t => t.tipo === "ips").error) && !r.tipos.find(t => t.tipo === "eps").error);
await put({ sharepoint_carpeta_ips: "15" });
// informe final
await j(A, `/informes/${i2.id}/estado`, "POST", { estado: "FINAL" });
ver("final no se modifica", (await j(T.N2, `/informes/${i2.id}/sharepoint`))[0] === 409 && (await j(T.N2, `/informes/${i2.id}/sharepoint`, "POST", { archivos: [{ tipo: "eps", nombre: "x" }] }))[0] === 409);
ver("solo lectura en el contenedor", py("import os;print(os.access('/sharepoint', os.W_OK))") === "False");

// ---------- Microsoft Graph (simulador sobre la misma carpeta)
const G = { sharepoint_modo: "graph", sharepoint_sitio: "https://empresa.sharepoint.com/sites/SOC", sharepoint_tenant: "tenant-prueba", sharepoint_cliente_id: "cid-bueno",
  sharepoint_login_url: "http://sim:9000", sharepoint_graph_url: "http://sim:9000/v1.0", sharepoint_ruta: BASE };
[s, r] = await put(G); ver("graph exige el secreto", s === 422 && /faltan/.test(r.detail), r);
for (const u of ["http://localhost:9000", "http://db:5432", "http://api:8000/v1.0", "http://169.254.169.254"]) ver("destino prohibido " + u, (await put({ ...G, sharepoint_graph_url: u, sharepoint_secreto: "x" }))[0] === 422);
[s, r] = await put({ ...G, sharepoint_secreto: "secreto-malo" }); ver("guarda graph", s === 200, r);
ver("no devuelve el secreto", !JSON.stringify((await j(A, "/config"))[1]).includes("secreto-malo") && sql("select valor from configuracion where clave='sharepoint_secreto'").startsWith("gAAAA"));
[s, r] = await j(T.LIDER, "/config/sharepoint/probar", "POST"); ver("secreto malo", s === 502 && /rechazó la aplicación/.test(r.detail), r);
ver("cambiar el tenant exige el secreto", (await put({ sharepoint_tenant: "otro" }))[0] === 422);
await put({ sharepoint_secreto: "secreto-bueno" });
ver("guía: graph completo sin mostrar el secreto", (r = await est()) && r.modo === "graph" && Object.values(r.graph).every(x => x === true) && !JSON.stringify(r).includes("secreto-bueno"), r);
[s, r] = await j(T.LIDER, "/config/sharepoint/probar", "POST"); ver("prueba graph", s === 200 && r.modo === "graph" && r.tipos.every(t => t.carpeta && !t.error) && r.carpetas_base === 9, r);
const i3b = (await j(A, "/informes", "POST", { cliente_id: cx.id, anio: 2026, mes: 11 }))[1];
[s, r] = await j(T.N2, `/informes/${i1.id}/sharepoint`); const bg = r;
ver("graph lista lo mismo que la carpeta", s === 200 && JSON.stringify(bg.tipos.map(t => [t.tipo, t.carpeta, t.carpeta_cliente, t.archivos.map(a => [a.nombre, a.sugerido, a.tamano])])) === JSON.stringify(b1.tipos.map(t => [t.tipo, t.carpeta, t.carpeta_cliente, t.archivos.map(a => [a.nombre, a.sugerido, a.tamano])])), [bg, b1].map(x => x?.tipos?.map(t => t.archivos.length)));
ver("sigue las páginas de Graph", JSON.parse(sim("/_ver")).peticiones.some(x => x.ruta.includes("pag=2")));
[s, r] = await j(T.N2, `/informes/${i3b.id}/sharepoint`); ver("periodo siguiente sin archivos", s === 200 && r.patron === "SPX_2026-11" && r.tipos.every(t => !t.archivos.some(a => a.sugerido)));
const antes = JSON.parse(sim("/_ver")).peticiones.length;
[s, r] = await j(T.N2, `/informes/${i3b.id}/sharepoint`, "POST", { archivos: elegir(b1) });
ver("graph trae los 7", s === 200 && r.resultados.length === 7 && r.errores.length === 0, r.errores);
ver("mismo resultado por Graph", sql(`select (select anexos from informes where id=${i1.id}) = (select anexos from informes where id=${i3b.id})`) === "t");
const desc = JSON.parse(sim("/_ver")).peticiones.slice(antes).filter(x => x.ruta.startsWith("/_descarga/"));
ver("descarga sin el token", desc.length === 7 && desc.every(x => !x.auth), desc.map(x => x.auth));
await put({ sharepoint_biblioteca: "otra" }); [s, r] = await j(T.N2, `/informes/${i1.id}/sharepoint`); ver("biblioteca por nombre", s === 200 && r.tipos.every(t => /No hay una carpeta/.test(t.error)), r);
await put({ sharepoint_biblioteca: "Documentos" }); ver("biblioteca de documentos", (await j(T.N2, `/informes/${i1.id}/sharepoint`))[1]?.tipos?.every(t => !t.error));
await put({ sharepoint_biblioteca: "NoExiste" }); [s, r] = await j(T.N2, `/informes/${i1.id}/sharepoint`); ver("biblioteca inexistente", s === 502 && /No existe la biblioteca/.test(r.detail), r);
await put({ sharepoint_biblioteca: "" });
sim("/_poner/ajeno/si"); [s, r] = await j(T.N2, `/informes/${i1.id}/sharepoint`); ver("no sigue páginas a otro servidor", s === 502 && /no válida/.test(r.detail), r); sim("/_poner/ajeno/no");
await put({ sharepoint_sitio: "https://empresa.sharepoint.com/sites/NOEXISTE" }); [s, r] = await j(T.N2, `/informes/${i1.id}/sharepoint`); ver("sitio inexistente", s >= 400, r);
await put({ sharepoint_modo: "no" }); ver("se desactiva", (await j(T.N2, `/informes/${i1.id}/sharepoint`))[0] === 400 && (await j(A, `/informes/${i1.id}`))[1].sharepoint === false);
ver("nada se escribió en la carpeta", fs.readdirSync(path.join(raiz, C.eps, "SPX")).join() === `${PAT}.csv`);
ver("queda en el registro de cambios", JSON.stringify((await j(A, "/usuarios/cambios"))[1]).includes("SharePoint"));
console.log(f ? `FALLOS ${f} de ${n}` : `TODO BIEN: ${n} comprobaciones`);
