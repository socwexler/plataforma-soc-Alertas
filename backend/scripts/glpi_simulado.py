"""Simulador mínimo de la API REST de GLPI 10, solo para pruebas.

Uso (dentro del contenedor api):
    SIM_APP_TOKEN=app SIM_USER_TOKEN=user uvicorn scripts.glpi_simulado:app --port 8099
y en .env:  GLPI_URL=http://127.0.0.1:8099/apirest.php  GLPI_APP_TOKEN=app  GLPI_USER_TOKEN=user

La entidad 999 devuelve error (para probar fallos). GET /apirest.php/_tickets lista lo creado.
"""
import itertools
import os
import uuid

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

app = FastAPI()
TICKETS: dict[int, dict] = {}
SESIONES: set[str] = set()
_ids = itertools.count(5001)
P = "/apirest.php"


def error(status, codigo, msg):
    return JSONResponse([codigo, msg], status_code=status)


def sesion_valida(token, app_token):
    return app_token == os.environ.get("SIM_APP_TOKEN") and token in SESIONES


@app.get(P + "/initSession")
def init(authorization: str = Header(""), app_token: str = Header("")):
    if app_token != os.environ.get("SIM_APP_TOKEN"):
        return error(400, "ERROR_WRONG_APP_TOKEN_PARAMETER", "parameter app_token seems wrong")
    if authorization != f"user_token {os.environ.get('SIM_USER_TOKEN')}":
        return error(401, "ERROR_GLPI_LOGIN_USER_TOKEN", "parameter user_token seems invalid")
    t = uuid.uuid4().hex
    SESIONES.add(t)
    return {"session_token": t}


@app.get(P + "/killSession")
def kill(session_token: str = Header("")):
    SESIONES.discard(session_token)
    return []


@app.get(P + "/getFullSession")
def full(session_token: str = Header(""), app_token: str = Header("")):
    if not sesion_valida(session_token, app_token):
        return error(401, "ERROR_SESSION_TOKEN_INVALID", "session_token seems invalid")
    return {"session": {"glpiname": "soc-api", "glpiactive_entity_name": "Entidad raíz"}}


@app.post(P + "/Ticket")
async def crear(req: Request, session_token: str = Header(""), app_token: str = Header("")):
    if not sesion_valida(session_token, app_token):
        return error(401, "ERROR_SESSION_TOKEN_INVALID", "session_token seems invalid")
    entrada = (await req.json())["input"]
    if entrada.get("entities_id") == 999:
        return error(400, "ERROR_GLPI_ADD", "You don't have permission to perform this action.")
    tid = next(_ids)
    TICKETS[tid] = {**entrada, "id": tid, "status": 1, "seguimientos": [], "solucion": None}
    return JSONResponse({"id": tid, "message": f"Elemento agregado con éxito: {entrada.get('name')}"}, 201)


@app.get(P + "/Ticket/{tid}")
def ver(tid: int, session_token: str = Header(""), app_token: str = Header("")):
    if not sesion_valida(session_token, app_token):
        return error(401, "ERROR_SESSION_TOKEN_INVALID", "session_token seems invalid")
    if tid not in TICKETS:
        return error(404, "ERROR_ITEM_NOT_FOUND", "Item not found")
    return TICKETS[tid]


@app.put(P + "/Ticket/{tid}")
async def editar(tid: int, req: Request, session_token: str = Header(""), app_token: str = Header("")):
    if not sesion_valida(session_token, app_token):
        return error(401, "ERROR_SESSION_TOKEN_INVALID", "session_token seems invalid")
    if tid not in TICKETS:
        return error(404, "ERROR_ITEM_NOT_FOUND", "Item not found")
    TICKETS[tid].update({k: v for k, v in (await req.json())["input"].items() if k != "id"})
    return [{str(tid): True, "message": ""}]


@app.post(P + "/{tipo}")
async def hijo(tipo: str, req: Request, session_token: str = Header(""), app_token: str = Header("")):
    if not sesion_valida(session_token, app_token):
        return error(401, "ERROR_SESSION_TOKEN_INVALID", "session_token seems invalid")
    entrada = (await req.json())["input"]
    t = TICKETS.get(entrada.get("items_id"))
    if not t:
        return error(400, "ERROR_GLPI_ADD", "Ticket inexistente")
    if tipo == "ITILFollowup":
        t["seguimientos"].append(entrada["content"])
    elif tipo == "ITILSolution":
        t["solucion"] = entrada["content"]
        t["status"] = 5
    else:
        return error(400, "ERROR_RESOURCE_NOT_FOUND_NOR_COMMONDBTM", "resource not found")
    return JSONResponse({"id": next(_ids), "message": ""}, 201)


@app.get(P + "/_tickets")
def listar():
    return list(TICKETS.values())
