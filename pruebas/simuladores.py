"""Simuladores para las pruebas de configuración (solo biblioteca estándar): GLPI, FortiSIEM, API genérica y SMTP.

Corre en un contenedor aparte de la red de soc-prueba. HTTP en 9000 y SMTP en 2525. GET /_ver devuelve lo recibido.
"""
import base64
import json
import os
import socketserver
import threading
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, unquote, urlsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CORREOS: list[dict] = []
PETICIONES: list[dict] = []
ESTADO = {"smtp": True, "glpi": True, "ajeno": False}
SP = "/sp"   # carpeta de SharePoint de prueba (la misma que se monta en la plataforma)


def _id(rel: str) -> str:
    return base64.urlsafe_b64encode(rel.encode()).decode().rstrip("=")


def _rel(i: str) -> str:
    return base64.urlsafe_b64decode(i + "=" * (-len(i) % 4)).decode()


def _item(rel: str) -> dict:
    f = os.path.join(SP, rel)
    st = os.stat(f)
    mod = datetime.fromtimestamp(st.st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    x = {"id": _id(rel), "name": os.path.basename(rel), "lastModifiedDateTime": mod, "size": st.st_size}
    x["folder" if os.path.isdir(f) else "file"] = {"childCount": len(os.listdir(f))} if os.path.isdir(f) else {"mimeType": "text/csv"}
    return x
# Tickets «del SIEM» en GLPI: /_ticket/<id>/<entidad>/<urgencia>/<estado>/<minutos atrás>/<título>
TICKETS: dict[int, dict] = {}
CONTENIDO = ("&lt;p&gt;FortiSIEM: Fuerza bruta en VPN&lt;br&gt;IP origen: 203.0.113.7&lt;/p&gt;"
             "&lt;table&gt;&lt;tr&gt;&lt;td&gt;Usuario&lt;/td&gt;&lt;td&gt;jperez&lt;/td&gt;&lt;/tr&gt;&lt;/table&gt;"
             "&lt;script&gt;alert(1)&lt;/script&gt;&lt;p&gt;Acción: &amp;quot;Permitida&amp;quot;&lt;/p&gt;")


class Web(BaseHTTPRequestHandler):
    def _r(self, codigo, cuerpo=b"{}", tipo="application/json", extra=()):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *a):
        pass

    def do_POST(self):
        cuerpo = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        PETICIONES.append({"ruta": self.path, "metodo": "POST", "cuerpo": cuerpo.decode("utf-8", "replace")})
        if self.path.endswith("/oauth2/v2.0/token"):   # inicio de sesión de Microsoft (Entra ID)
            f = parse_qs(cuerpo.decode())
            ok = f.get("client_id") == ["cid-bueno"] and f.get("client_secret") == ["secreto-bueno"] and f.get("grant_type") == ["client_credentials"]
            return self._r(200, b'{"access_token": "tok-sp", "expires_in": 3600}') if ok else self._r(401, b'{"error": "invalid_client"}')
        self._r(400 if not ESTADO["glpi"] else 201, b'["ERROR","falla simulada"]' if not ESTADO["glpi"] else b'{"id": 7001}')

    def do_GET(self):
        p, h = self.path, self.headers
        if p == "/_ver":
            return self._r(200, json.dumps({"correos": CORREOS, "peticiones": PETICIONES}).encode())
        if p.startswith("/_poner/"):
            _, _, k, v = p.split("/")
            ESTADO[k] = v == "si"
            return self._r(200)
        u = urlsplit(p)
        if u.path.startswith(("/v1.0/", "/_descarga/")):
            PETICIONES.append({"ruta": p, "auth": h.get("Authorization")})
        if u.path.startswith("/v1.0/"):   # Microsoft Graph (solo lectura)
            if h.get("Authorization") != "Bearer tok-sp":
                return self._r(401, b'{"error": {"code": "InvalidAuthenticationToken"}}')
            ruta = unquote(u.path[len("/v1.0"):])
            if ruta.startswith("/sites/") and ":" in ruta:
                return self._r(404) if ruta.endswith("/NOEXISTE") else self._r(200, b'{"id": "sitio1"}')
            if ruta == "/sites/sitio1/drive":
                return self._r(200, b'{"id": "drive1"}')
            if ruta == "/sites/sitio1/drives":
                return self._r(200, b'{"value": [{"id": "drive1", "name": "Documentos"}, {"id": "drive2", "name": "Otra"}]}')
            if ruta.startswith("/drives/drive1/root") and ruta.endswith("/children"):
                rel = ruta[len("/drives/drive1/root:/"):-len(":/children")] if ruta.startswith("/drives/drive1/root:/") else ""
                d = os.path.join(SP, rel)
                if ".." in rel.split("/") or not os.path.isdir(d):
                    return self._r(404, b'{"error": {"code": "itemNotFound"}}')
                todos = sorted(os.listdir(d))
                pag = int(parse_qs(u.query).get("pag", ["1"])[0])
                trozo = todos[(pag - 1) * 4:pag * 4]   # páginas de 4 para probar @odata.nextLink
                res = {"value": [_item(os.path.join(rel, n) if rel else n) for n in trozo]}
                if pag * 4 < len(todos):
                    host = "http://otro.example:9000" if ESTADO["ajeno"] else "http://sim:9000"
                    res["@odata.nextLink"] = f"{host}{u.path}?pag={pag + 1}"
                return self._r(200, json.dumps(res).encode())
            if ruta.startswith("/drives/drive1/items/") and ruta.endswith("/content"):
                i = ruta.split("/")[4]
                return self._r(302, b"", extra=[("Location", f"http://sim:9000/_descarga/{i}")])
            return self._r(404)
        if u.path.startswith("/_descarga/"):
            rel = _rel(u.path.split("/")[2])
            if ".." in rel.split("/"):
                return self._r(404)
            with open(os.path.join(SP, rel), "rb") as f:
                return self._r(200, f.read(), "application/octet-stream")
        if p.startswith("/_ticket/"):
            _, _, tid, ent, urg, est, atras, titulo = p.split("/", 7)
            fecha = (datetime.now(timezone(timedelta(hours=-5))) - timedelta(minutes=int(atras))).strftime("%Y-%m-%d %H:%M:%S")
            TICKETS[int(tid)] = {"id": int(tid), "name": unquote(titulo), "content": CONTENIDO, "entities_id": int(ent),
                                 "urgency": int(urg), "status": int(est), "date": fecha}
            return self._r(200)
        if p.startswith("/_estado/"):
            _, _, tid, est = p.split("/")
            TICKETS[int(tid)]["status"] = int(est)
            return self._r(200)
        PETICIONES.append({"ruta": p, "auth": h.get("Authorization"), "apikey": h.get("x-apikey"), "app": h.get("App-Token")})
        if p.endswith("/initSession"):
            if h.get("App-Token") != "app-bueno" or h.get("Authorization") != "user_token user-bueno":
                return self._r(401, b'["ERROR_GLPI_LOGIN","token"]')
            return self._r(200, b'{"session_token": "s"}')
        if p.endswith("/getFullSession"):
            return self._r(200, b'{"session": {"glpiname": "soc.api", "glpiactive_entity_name": "Raiz"}}')
        if urlsplit(p).path.endswith("/search/Ticket"):
            q = parse_qs(urlsplit(p).query)
            abiertos = [t for t in sorted(TICKETS) if TICKETS[t]["status"] < 5] if q.get("criteria[0][value]") == ["notold"] else sorted(TICKETS)
            return self._r(200, json.dumps({"totalcount": len(abiertos), "count": len(abiertos), "data": [{"2": t} for t in abiertos]}).encode())
        if "/Ticket/" in p:
            tid = p.rsplit("/", 1)[-1]
            if tid.isdigit() and int(tid) in TICKETS:
                return self._r(200, json.dumps(TICKETS[int(tid)]).encode())
            return self._r(200, b'{"status": 2}')
        if p.startswith("/phoenix/rest/config/Domain"):
            return self._r(200 if h.get("Authorization") == "Basic " + base64.b64encode(b"super/lector:forti-buena").decode() else 401, b"<r/>", "text/xml")
        if p == "/redirige":
            return self._r(302, b"", extra=[("Location", "http://db:5432/")])
        if p == "/generica":
            return self._r(200 if h.get("x-apikey") == "clave-generica" else 403, b'{"secreto":"contenido-remoto"}')
        self._r(404)


class Smtp(socketserver.StreamRequestHandler):
    def di(self, s):
        self.wfile.write((s + "\r\n").encode())

    def handle(self):
        if not ESTADO["smtp"]:
            return self.di("421 no disponible")
        self.di("220 sim")
        para, datos = [], None
        while True:
            l = self.rfile.readline()
            if not l:
                return
            c = l.decode("utf-8", "replace").strip()
            u = c.upper()
            if u.startswith(("EHLO", "HELO")):
                self.di("250 sim")
            elif u.startswith("MAIL"):
                para = []
                self.di("250 ok")
            elif u.startswith("RCPT"):
                para.append(c[8:].strip("<>: "))
                self.di("250 ok")
            elif u == "DATA":
                self.di("354 va")
                datos = b""
                while (x := self.rfile.readline()) not in (b".\r\n", b""):
                    datos += x
                CORREOS.append({"para": para, "texto": datos.decode("utf-8", "replace")})
                self.di("250 ok")
            elif u == "QUIT":
                return self.di("221 chao")
            else:
                self.di("250 ok")


socketserver.ThreadingTCPServer.allow_reuse_address = True
threading.Thread(target=socketserver.ThreadingTCPServer(("0.0.0.0", 2525), Smtp).serve_forever, daemon=True).start()
ThreadingHTTPServer(("0.0.0.0", 9000), Web).serve_forever()
