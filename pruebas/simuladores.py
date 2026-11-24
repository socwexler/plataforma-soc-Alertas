"""Simuladores para las pruebas de configuración (solo biblioteca estándar): GLPI, FortiSIEM, API genérica y SMTP.

Corre en un contenedor aparte de la red de soc-prueba. HTTP en 9000 y SMTP en 2525. GET /_ver devuelve lo recibido.
"""
import base64
import json
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CORREOS: list[dict] = []
PETICIONES: list[dict] = []
ESTADO = {"smtp": True, "glpi": True}


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
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self._r(400 if not ESTADO["glpi"] else 201, b'["ERROR","falla simulada"]' if not ESTADO["glpi"] else b'{"id": 7001}')

    def do_GET(self):
        p, h = self.path, self.headers
        if p == "/_ver":
            return self._r(200, json.dumps({"correos": CORREOS, "peticiones": PETICIONES}).encode())
        if p.startswith("/_poner/"):
            _, _, k, v = p.split("/")
            ESTADO[k] = v == "si"
            return self._r(200)
        PETICIONES.append({"ruta": p, "auth": h.get("Authorization"), "apikey": h.get("x-apikey"), "app": h.get("App-Token")})
        if p.endswith("/initSession"):
            if h.get("App-Token") != "app-bueno" or h.get("Authorization") != "user_token user-bueno":
                return self._r(401, b'["ERROR_GLPI_LOGIN","token"]')
            return self._r(200, b'{"session_token": "s"}')
        if p.endswith("/getFullSession"):
            return self._r(200, b'{"session": {"glpiname": "soc.api", "glpiactive_entity_name": "Raiz"}}')
        if "/Ticket/" in p:
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
