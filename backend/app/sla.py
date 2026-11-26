"""SLA de notificación por criticidad: minutos entre la alerta del SIEM y el reporte al cliente.

Los objetivos se leen de `settings` en cada consulta, porque se cambian desde Configuración.
"""
from sqlalchemy import case, func

from .config import settings
from .models import Caso

MINUTOS = func.extract("epoch", Caso.fecha_reporte - Caso.fecha_evento) / 60
CON_TIEMPO = Caso.fecha_reporte.is_not(None) & Caso.fecha_evento.is_not(None)


def objetivo():
    """Expresión SQL: minutos objetivo según la criticidad del caso (sin criticidad, el de Media)."""
    o = settings.sla_objetivos
    return case(*[(Caso.criticidad == c, m) for c, m in o.items()], else_=o["Media"])


def dentro():
    """Condición SQL: el caso tiene tiempos y cumple el objetivo de su criticidad."""
    return CON_TIEMPO & (MINUTOS <= objetivo())


def fuera():
    return CON_TIEMPO & ~dentro()


def duracion(m: int) -> str:
    if m % 60:
        return f"{m} minutos" if m != 1 else "1 minuto"
    return f"{m // 60} horas" if m != 60 else "1 hora"


def texto(objetivos: dict[str, int]) -> str:
    """«crítica 35 minutos, alta 45 minutos, media 2 horas y baja 4 horas»."""
    p = [f"{c.lower()} {duracion(m)}" for c, m in objetivos.items()]
    return ", ".join(p[:-1]) + f" y {p[-1]}"
