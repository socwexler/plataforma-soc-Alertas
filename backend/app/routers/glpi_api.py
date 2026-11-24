from fastapi import APIRouter, Depends, HTTPException

from .. import glpi
from ..security import requiere, usuario_actual

router = APIRouter(prefix="/api/glpi", tags=["glpi"])


@router.get("/estado")
def estado(_=Depends(usuario_actual)):
    return glpi.estado_integracion()


@router.post("/probar")
def probar(_=Depends(requiere("config.admin"))):
    """Abre una sesión en GLPI con las credenciales configuradas y devuelve el usuario y la entidad."""
    try:
        with glpi.ClienteGLPI() as g:
            return {"ok": True, **g.sesion()}
    except glpi.ErrorGLPI as e:
        raise HTTPException(502, str(e))


@router.post("/sincronizar")
def sincronizar(_=Depends(requiere("clientes.admin"))):
    if not glpi.settings.glpi_activo:
        raise HTTPException(400, "La integración con GLPI no está configurada")
    r = glpi.ejecutar_sincronizacion()
    if r["error"]:
        raise HTTPException(502, r["error"])
    return r
