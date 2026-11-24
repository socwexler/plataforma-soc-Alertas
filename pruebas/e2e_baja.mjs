import fs from "fs";
const [puerto, env] = process.argv.slice(2); const B = `http://127.0.0.1:${puerto}/api`;
const pw = /^ADMIN_PASSWORD=(.*)$/m.exec(fs.readFileSync(env, "utf8"))[1].trim(), P = "Prueba-local-123";
const ent = async (u, p) => (await (await fetch(B + "/auth/login", { method: "POST", body: new URLSearchParams({ username: u, password: p }) })).json()).access_token;
const j = async (t, u, m = "GET", d) => { const r = await fetch(B + u, { method: m, headers: { Authorization: "Bearer " + t, ...(d ? { "Content-Type": "application/json" } : {}) }, body: d ? JSON.stringify(d) : undefined }); return [r.status, await r.json().catch(() => null)]; };
let f = 0, n = 0; const ver = (t, ok, x = "") => { n++; if (!ok) { f++; console.log("  [X] ", t, JSON.stringify(x)); } };
const A = await ent("admin", pw), T = {}, U = {};
for (const r of ["N1", "N2", "N3", "LIDER", "CISO", "ADMIN"]) { U[r] = (await j(A, "/usuarios", "POST", { usuario: "b." + r.toLowerCase(), nombre: "Baja " + r, rol: r, password: P }))[1]; T[r] = await ent("b." + r.toLowerCase(), P); }
const nuevo = async (s) => (await j(A, "/usuarios", "POST", { usuario: "t.usr" + s, nombre: "Temporal " + s, rol: "N1", password: P }))[1];
const yo = (await j(A, "/auth/yo"))[1]; let s, r;
// cliente y casos de uso de prueba
const c = (await j(A, "/clientes", "POST", { codigo: "BAJ", nombre: "Cliente Baja" }))[1], c0 = (await j(A, "/clientes", "POST", { codigo: "VAC", nombre: "Vacío" }))[1];
const cu = (await j(T.N2, "/casos-uso", "POST", { nombre: "CDU de baja" }))[1], cu0 = (await j(T.N2, "/casos-uso", "POST", { nombre: "CDU vacío" }))[1];
// permisos
const x = await nuevo("x");
for (const rol of ["N1", "N2", "N3", "CISO"]) for (const [u, m, d] of [[`/usuarios/${x.id}`, "DELETE"], [`/usuarios/${x.id}/estado`, "PATCH", { activo: false }], ["/usuarios/cambios", "GET"], [`/clientes/${c0.id}`, "DELETE"], [`/clientes/${c0.id}/estado`, "PATCH", { activo: false }], [`/casos-uso/${cu0.id}`, "DELETE"]]) ver(`${rol} no ${m} ${u}`, (await j(T[rol], u, m, d))[0] === 403);
for (const rol of ["N1", "CISO"]) ver(rol + " no deshabilita caso de uso", (await j(T[rol], `/casos-uso/${cu0.id}/estado`, "PATCH", { activo: false }))[0] === 403);
ver("sin sesión", (await fetch(`${B}/usuarios/${x.id}`, { method: "DELETE" })).status === 401);
// deshabilitar usuario
const tx = await ent("t.usrx", P); ver("x ingresa", (await j(tx, "/auth/yo"))[0] === 200);
[s, r] = await j(T.LIDER, `/usuarios/${x.id}/estado`, "PATCH", { activo: false }); ver("líder deshabilita", s === 200 && r.activo === false, r);
ver("sesión abierta muere", (await j(tx, "/auth/yo"))[0] === 401); ver("no ingresa", !(await ent("t.usrx", P)));
[s] = await j(T.LIDER, `/usuarios/${x.id}/estado`, "PATCH", { activo: true }); ver("vuelve a ingresar", s === 200 && !!(await ent("t.usrx", P)));
ver("estado inválido", (await j(A, `/usuarios/${x.id}/estado`, "PATCH", {}))[0] === 422); ver("inexistente", (await j(A, "/usuarios/99999", "DELETE"))[0] === 404);
// protecciones
for (const [t, id, q] of [[A, yo.id, "admin"], [T.LIDER, U.LIDER.id, "líder"]]) { ver(q + " no se elimina", (await j(t, `/usuarios/${id}`, "DELETE"))[0] === 400); ver(q + " no se deshabilita", (await j(t, `/usuarios/${id}/estado`, "PATCH", { activo: false }))[0] === 400); }
ver("líder no elimina admin", (await j(T.LIDER, `/usuarios/${U.ADMIN.id}`, "DELETE"))[0] === 403); ver("líder no deshabilita admin", (await j(T.LIDER, `/usuarios/${U.ADMIN.id}/estado`, "PATCH", { activo: false }))[0] === 403);
ver("admin elimina a otro admin", (await j(A, `/usuarios/${U.ADMIN.id}`, "DELETE"))[0] === 204); ver("su sesión muere", (await j(T.ADMIN, "/auth/yo"))[0] === 401);
ver("elimina sin historial", (await j(T.LIDER, `/usuarios/${x.id}`, "DELETE"))[0] === 204 && !(await j(A, "/usuarios"))[1].some(u => u.id === x.id));
// con historial no se elimina
const caso = { servicio: "SOC", cliente_id: c.id, caso_uso_id: cu.id, alerta: "CDU de baja", criticidad: "Alta", resumen_ejecutivo: "r", analisis: "a", acciones_recomendadas: "x", fecha_evento: new Date(Date.now() - 600e3).toISOString() };
const k = (await j(T.N1, "/casos", "POST", caso))[1];
[s, r] = await j(A, `/usuarios/${U.N1.id}`, "DELETE"); ver("no elimina analista con casos", s === 409 && r.detail.includes("1 caso") && r.detail.includes("Deshabil"), r);
r = (await j(A, "/usuarios"))[1].find(u => u.id === U.N1.id); ver("lista indica el uso", r.uso?.startsWith("1 caso"), r);
[s, r] = await j(A, `/clientes/${c.id}`, "DELETE"); ver("no elimina cliente con casos", s === 409, r); [s, r] = await j(T.LIDER, `/casos-uso/${cu.id}`, "DELETE"); ver("no elimina CDU con casos", s === 409, r);
ver("elimina cliente vacío", (await j(T.LIDER, `/clientes/${c0.id}`, "DELETE"))[0] === 204);
ver("líder elimina CDU vacío", (await j(T.LIDER, `/casos-uso/${cu0.id}`, "DELETE"))[0] === 204);
// deshabilitados
ver("deshabilita cliente", (await j(T.LIDER, `/clientes/${c.id}/estado`, "PATCH", { activo: false }))[1].activo === false); ver("N3 deshabilita CDU", (await j(T.N3, `/casos-uso/${cu.id}/estado`, "PATCH", { activo: false }))[1].activo === false);
ver("no crea caso con cliente deshabilitado", (await j(T.N1, "/casos", "POST", { ...caso, caso_uso_id: null }))[0] === 422);
ver("no crea informe", (await j(T.N2, "/informes", "POST", { cliente_id: c.id, anio: 2026, mes: 10 }))[0] === 422);
ver("correo bloqueado", (await j(T.N1, `/casos/${k.id}/correo`))[1].bloqueos.some(b => b.includes("inactivo")));
[s, r] = await j(T.N1, `/casos/${k.id}`, "PUT", { ...caso, estado: "CERRADO", acciones_cliente: "ok" }); ver("sí cierra caso existente", s === 200 && r.estado === "CERRADO", r);
await j(A, `/clientes/${c.id}/estado`, "PATCH", { activo: true }); ver("no crea caso con CDU deshabilitado", (await j(T.N1, "/casos", "POST", caso))[0] === 422);
ver("no aparece en el selector", !(await j(T.N1, "/casos-uso/opciones"))[1].some(o => o.id === cu.id));
const otro = (await j(A, "/clientes", "POST", { codigo: "OTR", nombre: "Otro" }))[1]; await j(A, `/clientes/${otro.id}/estado`, "PATCH", { activo: false });
ver("no mueve caso a cliente deshabilitado", (await j(T.N1, `/casos/${k.id}`, "PUT", { ...caso, cliente_id: otro.id }))[0] === 422);
[s, r] = await j(A, `/clientes/${otro.id}`, "PUT", { codigo: "baj", nombre: "Otro" }); ver("código repetido avisa", s === 409, [s, r]);
// analista deshabilitado conserva casos
await j(A, `/usuarios/${U.N1.id}/estado`, "PATCH", { activo: false }); r = (await j(A, "/casos/" + k.id))[1]; ver("caso conserva analista", r.analista?.nombre === "Baja N1", r.analista);
// informe y registro
const inf = (await j(T.N2, "/informes", "POST", { cliente_id: c.id, anio: 2026, mes: 10 }))[1]; ver("elimina informe", (await j(T.LIDER, `/informes/${inf.id}`, "DELETE"))[0] === 204);
const n2 = { usuario: "b.n2", nombre: "Baja N2", rol: "N3", activo: true };
await j(A, `/usuarios/${U.N2.id}`, "PUT", { ...n2, password: "Otra-clave-987" }); await j(A, `/usuarios/${U.N2.id}`, "PUT", n2);
await j(T.LIDER, `/clientes/${c.id}/correos`, "PUT", { dominios: "baj.example", para: "a@baj.example", cc: "" });
r = (await j(T.LIDER, "/usuarios/cambios"))[1]; const t = JSON.stringify(r);
for (const e of ["eliminar\",\"objeto\":\"el usuario Temporal x (t.usrx)", "deshabilitar\",\"objeto\":\"el usuario Temporal x", "eliminar\",\"objeto\":\"el cliente VAC", "eliminar\",\"objeto\":\"el caso de uso CDU vacío", "el informe de BAJ", "rol: N2 → N3; contraseña cambiada", "Para agrega a@baj.example"]) ver("registro: " + e, t.includes(e));
ver("sin contraseñas", !t.includes(P) && !t.includes("Otra-clave") && !t.includes("$2b$")); ver("editar sin cambios no registra", r.items.filter(i => i.objeto.includes("Baja N2") && i.accion === "editar").length === 1);
r = (await j(A, "/usuarios/cambios?q=VAC"))[1]; ver("búsqueda", r.total > 0 && r.items.every(i => /vac/i.test(JSON.stringify(i))), r.total);
for (const m of ["PUT", "DELETE", "POST"]) ver("registro no se modifica " + m, [404, 405, 422].includes((await j(A, "/usuarios/cambios", m, m === "DELETE" ? undefined : {}))[0]));
console.log(f ? `FALLOS ${f} de ${n}` : `TODO BIEN: ${n} comprobaciones`);
